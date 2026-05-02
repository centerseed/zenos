"""
build_iteration_artifacts.py

Builds dogfooding iteration artifacts from Claude Code transcript JSONL files.

Outputs:
- /tmp/zenos-dogfood/{DF-ID}/producer.jsonl
- /tmp/zenos-dogfood/{DF-ID}/monitor.json

The producer artifact keeps only MCP tool_use / tool_result lines from the
selected clean-room session. The monitor artifact summarizes the session's MCP
traffic and rejection reasons in machine-readable JSON.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MCP_PREFIX = "mcp__zenos__"
DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")


def _parse_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    ts_clean = ts.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_clean, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return ""


def _usage_total(usage: Any) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "total_tokens": 0}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    total = input_tokens + output_tokens + cache_creation + cache_read
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "total_tokens": total,
    }


def _codex_last_usage_total(info: Any) -> dict[str, int]:
    if not isinstance(info, dict):
        return {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "total_tokens": 0}
    last = info.get("last_token_usage", {})
    if not isinstance(last, dict):
        return {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "total_tokens": 0}
    input_tokens = int(last.get("input_tokens") or 0)
    output_tokens = int(last.get("output_tokens") or 0)
    cache_creation = 0
    cache_read = int(last.get("cached_input_tokens") or 0)
    total = int(last.get("total_tokens") or (input_tokens + output_tokens + cache_read))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "total_tokens": total,
    }


def _maybe_parse_json_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    candidates = [text]
    if "Output:\n" in text:
        candidates.append(text.split("Output:\n", 1)[1].strip())
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            inner_text = payload[0].get("text")
            if isinstance(inner_text, str):
                try:
                    nested = json.loads(inner_text)
                except json.JSONDecodeError:
                    continue
                if isinstance(nested, dict):
                    return nested
    return {}


def _qualify_codex_tool_name(namespace: str, name: str) -> str:
    namespace = namespace.strip()
    name = name.strip()
    if not namespace:
        return name
    if namespace.endswith("__"):
        return f"{namespace}{name}"
    return f"{namespace}__{name}"


def _contains_tool_error_text(text: str) -> bool:
    lowered = text.lower()
    return (
        "error calling tool" in lowered
        or "validation error" in lowered
        or "unexpected keyword argument" in lowered
    )


def _payload_size_bytes(text: str | None = None, payload: dict[str, Any] | None = None) -> int:
    normalized_text = (text or "").strip()
    if normalized_text:
        return len(normalized_text.encode("utf-8"))
    if isinstance(payload, dict) and payload:
        return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return 0


def _matches_call_filter(name: str, tool_input: dict[str, Any], call_filter: str | None) -> bool:
    if not call_filter:
        return True
    if call_filter == "documents_broad":
        return (
            name == "mcp__zenos__search"
            and str(tool_input.get("collection") or "").strip().lower() == "documents"
            and not tool_input.get("entity_name")
            and not tool_input.get("product_id")
        )
    if call_filter == "documents_targeted":
        return (
            name == "mcp__zenos__search"
            and str(tool_input.get("collection") or "").strip().lower() == "documents"
            and bool(tool_input.get("entity_name") or tool_input.get("product_id"))
        )
    return True


def _iter_mcp_session_events(
    session_file: Path,
    *,
    call_filter: str | None = None,
    expect_read_source_preview: bool = False,
    since_text: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    producer_lines: list[str] = []
    pending_calls: dict[str, dict[str, Any]] = {}
    calls_total = 0
    rejected_count = 0
    reasons: Counter[str] = Counter()
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    usage_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "total_tokens": 0,
    }
    payload_bytes_total = 0
    payload_bytes_by_tool: Counter[str] = Counter()
    codex_count_next_usage = bool(call_filter is None and since_text is None)
    read_source_calls = 0
    read_source_preview_present_count = 0
    read_source_preview_missing_count = 0
    slicing_active = since_text is None
    since_text_found = since_text is None
    slice_started_at: str | None = None

    def note_timestamp(value: str | None) -> None:
        nonlocal first_ts, last_ts
        ts = _parse_timestamp(value)
        if ts is None:
            return
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)

    with session_file.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.rstrip("\n")
            if not raw_line.strip():
                continue

            if not slicing_active:
                if since_text and since_text in raw_line:
                    slicing_active = True
                    since_text_found = True
                    try:
                        marker_event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        marker_event = {}
                    slice_started_at = marker_event.get("timestamp") if isinstance(marker_event, dict) else None
                continue

            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            message = event.get("message")
            if isinstance(message, dict):
                role = message.get("role")
                content = message.get("content", [])
                if isinstance(content, list):
                    if role == "assistant":
                        keep_assistant_line = False
                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_use":
                                continue
                            name = str(item.get("name", ""))
                            if not name.startswith(MCP_PREFIX):
                                continue
                            tool_input = item.get("input", {}) if isinstance(item.get("input", {}), dict) else {}
                            if not _matches_call_filter(name, tool_input, call_filter):
                                continue
                            if name == "mcp__zenos__read_source":
                                read_source_calls += 1
                                if tool_input.get("preview_chars") is not None:
                                    read_source_preview_present_count += 1
                                elif expect_read_source_preview:
                                    read_source_preview_missing_count += 1
                            tool_id = str(item.get("id", ""))
                            pending_calls[tool_id] = {
                                "name": name,
                                "input": tool_input,
                                "timestamp": event.get("timestamp"),
                            }
                            calls_total += 1
                            keep_assistant_line = True
                        if keep_assistant_line or (call_filter is None and since_text is None):
                            note_timestamp(event.get("timestamp"))
                            usage = _usage_total(message.get("usage"))
                            for key, value in usage.items():
                                usage_totals[key] += value
                        if keep_assistant_line:
                            producer_lines.append(raw_line + "\n")
                    elif role == "user":
                        keep_line = False
                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_result":
                                continue
                            tool_id = str(item.get("tool_use_id", ""))
                            call_info = pending_calls.get(tool_id)
                            if call_info is None:
                                continue
                            keep_line = True
                            text = _extract_text(item.get("content", ""))
                            payload = _maybe_parse_json_text(text)
                            payload_size = _payload_size_bytes(text=text, payload=payload)
                            payload_bytes_total += payload_size
                            payload_bytes_by_tool[call_info["name"]] += payload_size
                            if payload.get("status") == "rejected":
                                rejected_count += 1
                                reason = str(payload.get("rejection_reason") or "UNKNOWN")
                                reasons[reason] += 1
                            elif _contains_tool_error_text(text):
                                rejected_count += 1
                                reasons["TOOL_ERROR"] += 1
                            del pending_calls[tool_id]
                            note_timestamp(event.get("timestamp"))
                        if keep_line:
                            producer_lines.append(raw_line + "\n")
                    if role in {"assistant", "user"}:
                        continue

            event_type = str(event.get("type", ""))
            payload = event.get("payload", {})
            if event_type == "response_item" and isinstance(payload, dict):
                payload_type = str(payload.get("type", ""))
                if payload_type == "function_call":
                    namespace = str(payload.get("namespace", ""))
                    name = str(payload.get("name", ""))
                    qualified_name = _qualify_codex_tool_name(namespace, name)
                    if not qualified_name.startswith(MCP_PREFIX):
                        continue
                    tool_input: dict[str, Any] = {}
                    arguments = payload.get("arguments")
                    if isinstance(arguments, str):
                        try:
                            parsed_args = json.loads(arguments)
                        except json.JSONDecodeError:
                            parsed_args = {}
                        if isinstance(parsed_args, dict):
                            tool_input = parsed_args
                    if not _matches_call_filter(qualified_name, tool_input, call_filter):
                        continue
                    if qualified_name == "mcp__zenos__read_source":
                        read_source_calls += 1
                        if tool_input.get("preview_chars") is not None:
                            read_source_preview_present_count += 1
                        elif expect_read_source_preview:
                            read_source_preview_missing_count += 1
                    tool_id = str(payload.get("call_id", ""))
                    pending_calls[tool_id] = {
                        "name": qualified_name,
                        "input": tool_input,
                        "timestamp": event.get("timestamp"),
                    }
                    calls_total += 1
                    note_timestamp(event.get("timestamp"))
                    producer_lines.append(raw_line + "\n")
                    codex_count_next_usage = True
                elif payload_type == "function_call_output":
                    tool_id = str(payload.get("call_id", ""))
                    call_info = pending_calls.get(tool_id)
                    if call_info is None:
                        continue
                    output_text = str(payload.get("output", ""))
                    result_payload = _maybe_parse_json_text(output_text)
                    payload_size = _payload_size_bytes(text=output_text, payload=result_payload)
                    payload_bytes_total += payload_size
                    payload_bytes_by_tool[call_info["name"]] += payload_size
                    if result_payload.get("status") == "rejected":
                        rejected_count += 1
                        reason = str(result_payload.get("rejection_reason") or "UNKNOWN")
                        reasons[reason] += 1
                    elif _contains_tool_error_text(output_text):
                        rejected_count += 1
                        reasons["TOOL_ERROR"] += 1
                    del pending_calls[tool_id]
                    note_timestamp(event.get("timestamp"))
                    producer_lines.append(raw_line + "\n")
                continue

            if event_type == "event_msg" and isinstance(payload, dict) and payload.get("type") == "token_count":
                if not codex_count_next_usage:
                    continue
                usage = _codex_last_usage_total(payload.get("info"))
                for key, value in usage.items():
                    usage_totals[key] += value
                note_timestamp(event.get("timestamp"))
                codex_count_next_usage = bool(call_filter is None and since_text is None)

    if since_text and not since_text_found:
        raise ValueError(f"since_text marker not found in transcript: {since_text}")

    monitor = {
        "session_file": str(session_file),
        "session_id": session_file.stem,
        "slice": {
            "since_text": since_text,
            "started_at": slice_started_at,
        },
        "total_mcp_calls": calls_total,
        "rejected_count": rejected_count,
        "reject_rate": (rejected_count / calls_total) if calls_total else 0.0,
        "top_rejection_reasons": [
            {"reason": reason, "count": count}
            for reason, count in reasons.most_common()
        ],
        "window": {
            "started_at": first_ts.isoformat().replace("+00:00", "Z") if first_ts else None,
            "ended_at": last_ts.isoformat().replace("+00:00", "Z") if last_ts else None,
        },
        "usage": usage_totals,
        "payload_bytes": {
            "total_result_bytes": payload_bytes_total,
            "by_tool": dict(payload_bytes_by_tool),
        },
        "tool_contract": {
            "expect_read_source_preview": expect_read_source_preview,
            "read_source_calls": read_source_calls,
            "read_source_preview_present_count": read_source_preview_present_count,
            "read_source_preview_missing_count": read_source_preview_missing_count,
            "schema_freshness_blocker": bool(expect_read_source_preview and read_source_preview_missing_count > 0),
        },
    }
    return producer_lines, monitor


def _resolve_session_file(transcripts_dir: Path, session_file: str | None) -> Path:
    if session_file:
        path = Path(session_file)
        return path if path.is_absolute() else (transcripts_dir / session_file)

    candidates = sorted(transcripts_dir.rglob("*.jsonl"))
    if not candidates:
        raise FileNotFoundError(f"No transcript JSONL found under {transcripts_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def build_iteration_artifacts(
    *,
    df_id: str,
    transcripts_dir: str | Path,
    session_file: str | None = None,
    call_filter: str | None = None,
    expect_read_source_preview: bool = False,
    since_text: str | None = None,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    transcripts_path = Path(transcripts_dir)
    selected_session = _resolve_session_file(transcripts_path, session_file)
    producer_lines, monitor = _iter_mcp_session_events(
        selected_session,
        call_filter=call_filter,
        expect_read_source_preview=expect_read_source_preview,
        since_text=since_text,
    )

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    producer_path = out_dir / "producer.jsonl"
    producer_path.write_text("".join(producer_lines), encoding="utf-8")

    monitor_payload = {
        "df_id": df_id,
        **monitor,
        "call_filter": call_filter,
        "producer_artifact": str(producer_path),
    }
    monitor_path = out_dir / "monitor.json"
    monitor_path.write_text(
        json.dumps(monitor_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "df_id": df_id,
        "producer_path": str(producer_path),
        "monitor_path": str(monitor_path),
        "session_file": str(selected_session),
        "call_filter": call_filter,
        "since_text": since_text,
        "expect_read_source_preview": expect_read_source_preview,
        "total_mcp_calls": monitor["total_mcp_calls"],
        "rejected_count": monitor["rejected_count"],
        "reject_rate": monitor["reject_rate"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dogfood producer/monitor artifacts from transcripts")
    parser.add_argument("--df-id", required=True, help="Iteration id, e.g. DF-20260502-1")
    parser.add_argument("--transcripts-dir", required=True, help="Transcript root directory")
    parser.add_argument("--session-file", help="Optional session file path or relative path under transcripts-dir")
    parser.add_argument("--call-filter", choices=["documents_broad", "documents_targeted"], help="Optional focused call filter")
    parser.add_argument(
        "--since-text",
        help="Only include transcript events after the first line containing this marker text; fail if not found",
    )
    parser.add_argument(
        "--expect-read-source-preview",
        action="store_true",
        help="Mark missing preview_chars on read_source calls as a schema freshness blocker",
    )
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT), help="Output root (default: /tmp/zenos-dogfood)")
    args = parser.parse_args()

    payload = build_iteration_artifacts(
        df_id=args.df_id,
        transcripts_dir=args.transcripts_dir,
        session_file=args.session_file,
        call_filter=args.call_filter,
        expect_read_source_preview=args.expect_read_source_preview,
        since_text=args.since_text,
        out_root=args.out_root,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
