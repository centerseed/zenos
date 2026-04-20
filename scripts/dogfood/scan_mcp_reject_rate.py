"""
scan_mcp_reject_rate.py

Scans Claude Code transcript JSONL files to compute MCP reject rate.

CLI:
    python3 scripts/dogfood/scan_mcp_reject_rate.py --transcripts-dir <path> [--format json|markdown] [--since 7d|30d|90d|YYYY-MM-DD]

Stdlib only: json, pathlib, argparse, re, collections, datetime.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MCP_PREFIX = "mcp__zenos__"
REJECTED_PATTERN = re.compile(r'"status"\s*:\s*"rejected"')
REASON_PATTERN = re.compile(r'"rejection_reason"\s*:\s*"([^"]+)"')
SINCE_DAYS_PATTERN = re.compile(r"^(\d+)d$")
SAME_INPUT_WINDOW_MS = 10_000  # max milliseconds between two identical calls to count as a retry


def _parse_since(value: str) -> datetime | None:
    """Parse --since value into a timezone-aware datetime (UTC).

    Accepts:
    - "7d", "30d", "90d" — N days before now
    - "YYYY-MM-DD"       — absolute date (midnight UTC)

    Returns None if value is empty/None (no filter).
    """
    if not value:
        return None

    m = SINCE_DAYS_PATTERN.match(value.strip())
    if m:
        days = int(m.group(1))
        from datetime import timedelta
        return datetime.now(tz=timezone.utc) - timedelta(days=days)

    # Try absolute date YYYY-MM-DD
    try:
        dt = datetime.strptime(value.strip(), "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(
            f"--since value {value!r} is not recognized. "
            "Use Nd (e.g. 7d, 30d, 90d) or YYYY-MM-DD."
        )


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string into a UTC datetime. Returns None on failure."""
    if not ts:
        return None
    # Handle trailing Z
    ts_clean = ts.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_clean, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_text_from_content(content: Any) -> str:
    """Extract plain text from a tool_result content field.

    content may be:
    - a string
    - a list of objects with {type: "text", text: "..."}
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)
    return ""


def _scan_file(filepath: Path, since_dt: datetime | None) -> dict[str, Any]:
    """Scan a single JSONL file and return per-session stats.

    If since_dt is set:
    - Events whose tool_use timestamp < since_dt are excluded from counting.
    - If ALL tool_use events in the file are older than since_dt, the session
      is excluded (returns None to signal caller to skip this session).
    """
    # Map tool_use_id -> (tool name, timestamp)
    pending_calls: dict[str, tuple[str, datetime | None]] = {}
    calls_total = 0
    calls_rejected = 0
    rejection_reasons: list[str] = []
    same_input_retries = 0

    # For same_input_retries: track (name, input_key) -> list of (timestamp_ms, is_rejected)
    # We process events in order; for each tool_use we store the call info,
    # then when we get the tool_result we record the outcome.
    # recent_tool_calls: list of {name, input_key, ts_ms, is_rejected}
    recent_tool_calls: list[dict[str, Any]] = []
    # Map tool_use_id -> (name, input_key, ts_ms) for pairing with result
    pending_for_retry: dict[str, dict[str, Any]] = {}

    with filepath.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            event_ts_str = event.get("timestamp")
            event_dt = _parse_timestamp(event_ts_str)

            message = event.get("message", {})
            if not isinstance(message, dict):
                continue

            role = message.get("role", "")
            content_list = message.get("content", [])
            if not isinstance(content_list, list):
                continue

            if role == "assistant":
                for item in content_list:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "tool_use":
                        name = item.get("name", "")
                        if name.startswith(MCP_PREFIX):
                            # Apply since filter: skip events before since_dt
                            if since_dt is not None and event_dt is not None and event_dt < since_dt:
                                continue

                            tool_id = item.get("id", "")
                            ts_ms = int(event_dt.timestamp() * 1000) if event_dt else None
                            pending_calls[tool_id] = (name, event_dt)

                            # For same_input_retries tracking
                            input_key = json.dumps(item.get("input", {}), sort_keys=True)
                            pending_for_retry[tool_id] = {
                                "name": name,
                                "input_key": input_key,
                                "ts_ms": ts_ms,
                            }
                            calls_total += 1

            elif role == "user":
                for item in content_list:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "tool_result":
                        tool_use_id = item.get("tool_use_id", "")
                        if tool_use_id not in pending_calls:
                            continue
                        # This result pairs with an mcp__zenos__ call
                        result_content = item.get("content", "")
                        text = _extract_text_from_content(result_content)
                        is_rejected = bool(REJECTED_PATTERN.search(text))

                        if is_rejected:
                            calls_rejected += 1
                            match = REASON_PATTERN.search(text)
                            if match:
                                rejection_reasons.append(match.group(1))

                        # Check same_input_retries
                        if tool_use_id in pending_for_retry:
                            call_info = pending_for_retry.pop(tool_use_id)
                            call_info["is_rejected"] = is_rejected

                            # Look back in recent_tool_calls for a matching (name, input_key)
                            # within 10 seconds, where the FIRST occurrence was rejected
                            cur_ts = call_info["ts_ms"]
                            cur_name = call_info["name"]
                            cur_key = call_info["input_key"]

                            if cur_ts is not None:
                                for prev in reversed(recent_tool_calls):
                                    if prev["name"] != cur_name or prev["input_key"] != cur_key:
                                        continue
                                    prev_ts = prev["ts_ms"]
                                    if prev_ts is None:
                                        continue
                                    if abs(cur_ts - prev_ts) <= SAME_INPUT_WINDOW_MS:
                                        # Same call within 10s: check first result was rejected
                                        if prev.get("is_rejected"):
                                            same_input_retries += 1
                                        break
                                    # More than 10s apart — stop looking back
                                    break

                            recent_tool_calls.append(call_info)
                        # Remove from pending regardless
                        del pending_calls[tool_use_id]

    # If since_dt is set and there were no valid calls at all, signal to skip
    if since_dt is not None and calls_total == 0:
        return {
            "session_id": filepath.stem,
            "file": str(filepath),
            "calls": 0,
            "rejected": 0,
            "rate": 0.0,
            "rejection_reasons": [],
            "same_input_retries": same_input_retries,
            "_skip": True,
        }

    reject_rate = (calls_rejected / calls_total) if calls_total > 0 else 0.0
    return {
        "session_id": filepath.stem,
        "file": str(filepath),
        "calls": calls_total,
        "rejected": calls_rejected,
        "rate": reject_rate,
        "rejection_reasons": rejection_reasons,
        "same_input_retries": same_input_retries,
        "_skip": False,
    }


def scan(transcripts_dir: str | Path, since: str | None = None) -> dict[str, Any]:
    """Scan all *.jsonl files under transcripts_dir and aggregate results."""
    base = Path(transcripts_dir)
    jsonl_files = sorted(base.rglob("*.jsonl"))

    since_dt = _parse_since(since) if since else None
    window = since if since else "all"

    sessions = []
    grand_total = 0
    grand_rejected = 0
    grand_retries = 0
    reason_counter: Counter[str] = Counter()

    for filepath in jsonl_files:
        result = _scan_file(filepath, since_dt)
        if result.get("_skip"):
            continue
        sessions.append({
            "session_id": result["session_id"],
            "file": result["file"],
            "calls": result["calls"],
            "rejected": result["rejected"],
            "rate": result["rate"],
        })
        grand_total += result["calls"]
        grand_rejected += result["rejected"]
        grand_retries += result["same_input_retries"]
        reason_counter.update(result["rejection_reasons"])

    overall_rate = (grand_rejected / grand_total) if grand_total > 0 else 0.0
    top_reasons = [
        {"reason": reason, "count": count}
        for reason, count in reason_counter.most_common(10)
    ]

    return {
        "window": window,
        "sessions_scanned": len(sessions),
        "total_mcp_calls": grand_total,
        "rejected_count": grand_rejected,
        "reject_rate": overall_rate,
        "same_input_retries": grand_retries,
        "top_rejection_reasons": top_reasons,
        "sessions": sessions,
    }


def _render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# MCP Reject Rate Report",
        "",
        f"- Window: {data['window']}",
        f"- Sessions scanned: {data['sessions_scanned']}",
        f"- Total MCP calls: {data['total_mcp_calls']}",
        f"- Rejected count: {data['rejected_count']}",
        f"- Reject rate: {data['reject_rate']:.1%}",
        f"- Same-input retries: {data['same_input_retries']}",
        "",
        "## Top Rejection Reasons",
        "",
    ]
    if data["top_rejection_reasons"]:
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for item in data["top_rejection_reasons"]:
            lines.append(f"| {item['reason']} | {item['count']} |")
    else:
        lines.append("_No rejections found._")

    lines += [
        "",
        "## Per-Session Breakdown",
        "",
        "| Session | Calls | Rejected | Rate |",
        "|---------|-------|----------|------|",
    ]
    for s in data["sessions"]:
        lines.append(f"| {s['session_id']} | {s['calls']} | {s['rejected']} | {s['rate']:.1%} |")

    return "\n".join(lines)


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Scan Claude Code transcripts for MCP reject rate."
    )
    parser.add_argument(
        "--transcripts-dir",
        required=True,
        help="Root directory containing *.jsonl transcript files.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="Only include events at or after this time. Accepts Nd (e.g. 7d, 30d) or YYYY-MM-DD.",
    )
    parsed = parser.parse_args(args)

    data = scan(parsed.transcripts_dir, since=parsed.since)

    if parsed.format == "markdown":
        print(_render_markdown(data))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
