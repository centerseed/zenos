"""
build_baseline_library.py

Builds a dogfood baseline scenario library from journal_read output.

Input accepts either:
- full MCP response: {"status":"ok","data":{"entries":[...]}}
- direct payload: {"entries":[...]}
- raw entry list: [{...}, {...}]

Expected usage:
1. Run journal_read(flow_type="capture", ...)
2. Save JSON response
3. Feed that JSON into this script

Output:
- /tmp/zenos-dogfood/baseline-library.json

The baseline library is used by the dogfood orchestrator to:
- pick replayable producer scenarios
- compare token/call deltas across iterations
- identify recurring friction clusters
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT_PATH = Path("/tmp/zenos-dogfood/baseline-library.json")


def _parse_dt(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _load_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("entries"), list):
            return [e for e in payload["data"]["entries"] if isinstance(e, dict)]
        if isinstance(payload.get("entries"), list):
            return [e for e in payload["entries"] if isinstance(e, dict)]
    if isinstance(payload, list):
        return [e for e in payload if isinstance(e, dict)]
    raise ValueError("Unsupported journal payload shape")


def _parse_metric(tags: list[str], prefix: str) -> int | None:
    needle = prefix + ":"
    for tag in tags:
        if not isinstance(tag, str) or not tag.startswith(needle):
            continue
        raw = tag[len(needle):].strip()
        if raw.isdigit():
            return int(raw)
    return None


def _estimate_tokens(summary: str) -> int:
    # crude but stable approximation for baseline when explicit metric missing
    text = str(summary or "").strip()
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _classify_topic(entry: dict[str, Any]) -> str:
    project = str(entry.get("project") or "").strip().lower()
    summary = str(entry.get("summary") or "").strip().lower()
    tags = [str(tag).strip().lower() for tag in entry.get("tags") or [] if str(tag).strip()]
    haystack = " ".join([project, summary, *tags])

    if "crm" in haystack:
        return "crm"
    if "marketing" in haystack:
        return "marketing"
    if "paceriz" in haystack or "havital" in haystack:
        return "paceriz"
    if "zenos" in haystack:
        return "zenos-core"
    return "other"


def build_baseline_library(entries: list[dict[str, Any]], *, generated_at: datetime | None = None) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)

    filtered = []
    for entry in entries:
        flow_type = str(entry.get("flow_type") or "").strip().lower()
        if flow_type != "capture":
            continue
        filtered.append(entry)

    scenarios = []
    topic_counter: Counter[str] = Counter()
    project_counter: Counter[str] = Counter()
    tokens_total = 0
    explicit_token_count = 0
    metric_coverage = defaultdict(int)

    for entry in filtered:
        entry_id = str(entry.get("id") or "").strip()
        summary = str(entry.get("summary") or "").strip()
        created_at = _parse_dt(entry.get("created_at"))
        project = str(entry.get("project") or "").strip() or "unknown"
        tags = [str(tag).strip() for tag in entry.get("tags") or [] if str(tag).strip()]

        tokens = _parse_metric(tags, "tokens")
        if tokens is None:
            tokens = _estimate_tokens(summary)
        else:
            explicit_token_count += 1
            metric_coverage["tokens"] += 1

        entries_count = _parse_metric(tags, "entries")
        if entries_count is not None:
            metric_coverage["entries"] += 1
        documents_count = _parse_metric(tags, "documents")
        if documents_count is not None:
            metric_coverage["documents"] += 1
        blindspots_count = _parse_metric(tags, "blindspots")
        if blindspots_count is not None:
            metric_coverage["blindspots"] += 1

        topic = _classify_topic(entry)
        topic_counter[topic] += 1
        project_counter[project] += 1
        tokens_total += tokens

        scenarios.append(
            {
                "entry_id": entry_id,
                "created_at": created_at.isoformat().replace("+00:00", "Z") if created_at else None,
                "project": project,
                "topic": topic,
                "summary": summary,
                "tags": tags,
                "estimated_tokens": tokens,
                "metrics": {
                    "entries": entries_count,
                    "documents": documents_count,
                    "blindspots": blindspots_count,
                },
            }
        )

    avg_tokens = (tokens_total / len(filtered)) if filtered else 0.0
    avg_metric_counts = {}
    for metric_name in ("entries", "documents", "blindspots"):
        values = [
            s["metrics"][metric_name]
            for s in scenarios
            if isinstance(s["metrics"].get(metric_name), int)
        ]
        avg_metric_counts[metric_name] = (sum(values) / len(values)) if values else None

    scenarios.sort(key=lambda item: (item["created_at"] or "", item["entry_id"]), reverse=True)

    return {
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "flow_type": "capture",
        "total_capture_sessions": len(filtered),
        "avg_tokens": avg_tokens,
        "explicit_token_count": explicit_token_count,
        "avg_outputs": avg_metric_counts,
        "topic_distribution": dict(topic_counter),
        "project_distribution": dict(project_counter),
        "metric_coverage": {
            "tokens": metric_coverage["tokens"],
            "entries": metric_coverage["entries"],
            "documents": metric_coverage["documents"],
            "blindspots": metric_coverage["blindspots"],
        },
        "scenarios": scenarios,
    }


def build_from_file(input_path: str | Path, out_path: str | Path = DEFAULT_OUT_PATH) -> dict[str, Any]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    entries = _load_entries(payload)
    library = build_baseline_library(entries)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(library, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "out_path": str(out),
        "total_capture_sessions": library["total_capture_sessions"],
        "topic_distribution": library["topic_distribution"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dogfood baseline scenario library from journal JSON")
    parser.add_argument("--journal-json", required=True, help="Path to saved journal_read JSON output")
    parser.add_argument("--out", default=str(DEFAULT_OUT_PATH), help="Output JSON path")
    args = parser.parse_args()

    result = build_from_file(args.journal_json, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
