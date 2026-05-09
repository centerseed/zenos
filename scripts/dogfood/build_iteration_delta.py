"""
build_iteration_delta.py

Compare two dogfooding iteration artifacts and emit a machine-readable delta.

Inputs:
- before monitor.json + producer.jsonl
- after monitor.json + producer.jsonl

Output:
- /tmp/zenos-dogfood/{DF-ID}/delta.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def _extract_documents_payload(result: dict[str, Any]) -> tuple[bool, list[Any]]:
    if not isinstance(result, dict):
        return False, []

    if result.get("status") == "ok":
        data = result.get("data", {})
        if isinstance(data, dict):
            documents = data.get("documents", [])
            if isinstance(documents, list):
                return True, documents

    documents = result.get("documents", [])
    if isinstance(documents, list):
        return True, documents

    data = result.get("data", {})
    if isinstance(data, dict):
        documents = data.get("documents", [])
        if isinstance(documents, list):
            return True, documents

    return False, []


def _extract_result_payload(event: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    text = _extract_text(item.get("content", ""))
    if text:
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    mcp_meta = event.get("mcpMeta", {})
    if isinstance(mcp_meta, dict):
        structured = mcp_meta.get("structuredContent", {})
        if isinstance(structured, dict):
            return structured

    tool_use_result = event.get("toolUseResult")
    if isinstance(tool_use_result, dict):
        structured = tool_use_result.get("structuredContent", {})
        if isinstance(structured, dict):
            return structured

    return {}


def _extract_codex_output_payload(output_text: str) -> dict[str, Any]:
    text = output_text.strip()
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


def _parse_producer(path: str | Path) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}

    with Path(path).open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            if not raw_line.strip():
                continue
            event = json.loads(raw_line)
            message = event.get("message")
            if isinstance(message, dict):
                role = message.get("role")
                content = message.get("content", [])
                if isinstance(content, list):
                    if role == "assistant":
                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_use":
                                continue
                            pending[str(item.get("id", ""))] = {
                                "name": str(item.get("name", "")),
                                "input": item.get("input", {}),
                            }
                    elif role == "user":
                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_result":
                                continue
                            tool_id = str(item.get("tool_use_id", ""))
                            call = pending.pop(tool_id, None)
                            if call is None:
                                continue
                            payload = _extract_result_payload(event, item)
                            calls.append({**call, "result": payload})
                    if role in {"assistant", "user"}:
                        continue

            if str(event.get("type", "")) != "response_item":
                continue
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            payload_type = str(payload.get("type", ""))
            if payload_type == "function_call":
                namespace = str(payload.get("namespace", ""))
                name = str(payload.get("name", ""))
                qualified_name = _qualify_codex_tool_name(namespace, name)
                arguments = payload.get("arguments")
                parsed_args: dict[str, Any] = {}
                if isinstance(arguments, str):
                    try:
                        maybe_args = json.loads(arguments)
                    except json.JSONDecodeError:
                        maybe_args = {}
                    if isinstance(maybe_args, dict):
                        parsed_args = maybe_args
                pending[str(payload.get("call_id", ""))] = {
                    "name": qualified_name,
                    "input": parsed_args,
                }
            elif payload_type == "function_call_output":
                tool_id = str(payload.get("call_id", ""))
                call = pending.pop(tool_id, None)
                if call is None:
                    continue
                result = _extract_codex_output_payload(str(payload.get("output", "")))
                calls.append({**call, "result": result})

    document_calls = 0
    successful_document_calls = 0
    targeted_document_calls = 0
    broad_document_calls = 0
    targeted_hit_within_3_calls = False
    result_bytes_total = 0
    result_bytes_by_tool: dict[str, int] = {}

    for idx, call in enumerate(calls, start=1):
        name = str(call.get("name", ""))
        result = call.get("result", {}) or {}
        result_bytes = len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) if result else 0
        result_bytes_total += result_bytes
        result_bytes_by_tool[name] = result_bytes_by_tool.get(name, 0) + result_bytes

        if call.get("name") != "mcp__zenos__search":
            continue
        payload = call.get("input", {}) or {}
        collection = str(payload.get("collection") or "").strip().lower()
        if collection != "documents":
            continue
        document_calls += 1
        targeted = bool(payload.get("entity_name") or payload.get("product_id"))
        if targeted:
            targeted_document_calls += 1
        else:
            broad_document_calls += 1
        ok, documents = _extract_documents_payload(result)
        if ok and len(documents) > 0:
            successful_document_calls += 1
            if targeted and idx <= 3:
                targeted_hit_within_3_calls = True

    hit_rate = successful_document_calls / document_calls if document_calls else None
    full_scan_ratio = broad_document_calls / document_calls if document_calls else None

    return {
        "total_calls": len(calls),
        "document_calls": document_calls,
        "successful_document_calls": successful_document_calls,
        "targeted_document_calls": targeted_document_calls,
        "broad_document_calls": broad_document_calls,
        "hit_rate": hit_rate,
        "full_scan_ratio": full_scan_ratio,
        "targeted_hit_within_3_calls": targeted_hit_within_3_calls,
        "payload_bytes_total": result_bytes_total,
        "payload_bytes_by_tool": result_bytes_by_tool,
    }


def _num_delta(before: float | int | None, after: float | int | None) -> float | None:
    if before is None or after is None:
        return None
    return float(after) - float(before)


def _bool_metric(value: Any) -> bool:
    return bool(value)


def _health_metric(payload: dict[str, Any], *path: str) -> Any:
    cursor: Any = payload.get("health") or {}
    for key in path:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def build_iteration_delta(
    *,
    df_id: str,
    before_monitor: str | Path,
    before_producer: str | Path,
    after_monitor: str | Path,
    after_producer: str | Path,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    before_monitor_payload = _read_json(before_monitor)
    after_monitor_payload = _read_json(after_monitor)
    before_metrics = _parse_producer(before_producer)
    after_metrics = _parse_producer(after_producer)

    before_calls = int(before_monitor_payload.get("total_mcp_calls") or before_metrics["total_calls"])
    after_calls = int(after_monitor_payload.get("total_mcp_calls") or after_metrics["total_calls"])
    before_reject_rate = before_monitor_payload.get("reject_rate")
    after_reject_rate = after_monitor_payload.get("reject_rate")
    before_tokens = ((before_monitor_payload.get("usage") or {}).get("total_tokens"))
    after_tokens = ((after_monitor_payload.get("usage") or {}).get("total_tokens"))
    before_payload_bytes = ((before_monitor_payload.get("payload_bytes") or {}).get("total_result_bytes"))
    after_payload_bytes = ((after_monitor_payload.get("payload_bytes") or {}).get("total_result_bytes"))
    if before_payload_bytes is None:
        before_payload_bytes = before_metrics["payload_bytes_total"]
    if after_payload_bytes is None:
        after_payload_bytes = after_metrics["payload_bytes_total"]
    before_search_payload_bytes = (
        ((before_monitor_payload.get("payload_bytes") or {}).get("by_tool") or {}).get("mcp__zenos__search")
    )
    after_search_payload_bytes = (
        ((after_monitor_payload.get("payload_bytes") or {}).get("by_tool") or {}).get("mcp__zenos__search")
    )
    if before_search_payload_bytes is None:
        before_search_payload_bytes = before_metrics["payload_bytes_by_tool"].get("mcp__zenos__search")
    if after_search_payload_bytes is None:
        after_search_payload_bytes = after_metrics["payload_bytes_by_tool"].get("mcp__zenos__search")
    before_read_source_payload_bytes = (
        ((before_monitor_payload.get("payload_bytes") or {}).get("by_tool") or {}).get("mcp__zenos__read_source")
    )
    after_read_source_payload_bytes = (
        ((after_monitor_payload.get("payload_bytes") or {}).get("by_tool") or {}).get("mcp__zenos__read_source")
    )
    if before_read_source_payload_bytes is None:
        before_read_source_payload_bytes = before_metrics["payload_bytes_by_tool"].get("mcp__zenos__read_source")
    if after_read_source_payload_bytes is None:
        after_read_source_payload_bytes = after_metrics["payload_bytes_by_tool"].get("mcp__zenos__read_source")
    before_missing_snapshot = _health_metric(
        before_monitor_payload, "invalid_documents", "current_formal_entry_missing_delivery_snapshot"
    )
    after_missing_snapshot = _health_metric(
        after_monitor_payload, "invalid_documents", "current_formal_entry_missing_delivery_snapshot"
    )
    before_stale_snapshot = _health_metric(
        before_monitor_payload, "invalid_documents", "current_formal_entry_stale_delivery_snapshot"
    )
    after_stale_snapshot = _health_metric(
        after_monitor_payload, "invalid_documents", "current_formal_entry_stale_delivery_snapshot"
    )
    before_source_not_found = _health_metric(before_monitor_payload, "source_governance", "source_not_found_count")
    after_source_not_found = _health_metric(after_monitor_payload, "source_governance", "source_not_found_count")
    before_delivery_auth_invalid = _bool_metric(
        _health_metric(before_monitor_payload, "delivery_auth", "github_secret_invalid")
    )
    after_delivery_auth_invalid = _bool_metric(
        _health_metric(after_monitor_payload, "delivery_auth", "github_secret_invalid")
    )
    before_schema_freshness_blocker = _bool_metric(
        (before_monitor_payload.get("tool_contract") or {}).get("schema_freshness_blocker")
    )
    after_schema_freshness_blocker = _bool_metric(
        (after_monitor_payload.get("tool_contract") or {}).get("schema_freshness_blocker")
    )

    delta_payload = {
        "df_id": df_id,
        "before": {
            "calls": before_calls,
            "tokens": before_tokens,
            "reject_rate": before_reject_rate,
            "hit_rate": before_metrics["hit_rate"],
            "full_scan_ratio": before_metrics["full_scan_ratio"],
            "targeted_hit_within_3_calls": before_metrics["targeted_hit_within_3_calls"],
            "payload_bytes": {
                "total_result_bytes": before_payload_bytes,
                "search_result_bytes": before_search_payload_bytes,
                "read_source_result_bytes": before_read_source_payload_bytes,
            },
            "health": {
                "missing_delivery_snapshot": before_missing_snapshot,
                "stale_delivery_snapshot": before_stale_snapshot,
                "source_not_found_count": before_source_not_found,
                "github_secret_invalid": before_delivery_auth_invalid,
                "schema_freshness_blocker": before_schema_freshness_blocker,
            },
        },
        "after": {
            "calls": after_calls,
            "tokens": after_tokens,
            "reject_rate": after_reject_rate,
            "hit_rate": after_metrics["hit_rate"],
            "full_scan_ratio": after_metrics["full_scan_ratio"],
            "targeted_hit_within_3_calls": after_metrics["targeted_hit_within_3_calls"],
            "payload_bytes": {
                "total_result_bytes": after_payload_bytes,
                "search_result_bytes": after_search_payload_bytes,
                "read_source_result_bytes": after_read_source_payload_bytes,
            },
            "health": {
                "missing_delivery_snapshot": after_missing_snapshot,
                "stale_delivery_snapshot": after_stale_snapshot,
                "source_not_found_count": after_source_not_found,
                "github_secret_invalid": after_delivery_auth_invalid,
                "schema_freshness_blocker": after_schema_freshness_blocker,
            },
        },
        "delta": {
            "calls": after_calls - before_calls,
            "tokens": _num_delta(before_tokens, after_tokens),
            "reject_rate": _num_delta(before_reject_rate, after_reject_rate),
            "hit_rate": _num_delta(before_metrics["hit_rate"], after_metrics["hit_rate"]),
            "full_scan_ratio": _num_delta(before_metrics["full_scan_ratio"], after_metrics["full_scan_ratio"]),
            "payload_bytes": {
                "total_result_bytes": _num_delta(before_payload_bytes, after_payload_bytes),
                "search_result_bytes": _num_delta(before_search_payload_bytes, after_search_payload_bytes),
                "read_source_result_bytes": _num_delta(before_read_source_payload_bytes, after_read_source_payload_bytes),
            },
            "health": {
                "missing_delivery_snapshot": _num_delta(before_missing_snapshot, after_missing_snapshot),
                "stale_delivery_snapshot": _num_delta(before_stale_snapshot, after_stale_snapshot),
                "source_not_found_count": _num_delta(before_source_not_found, after_source_not_found),
                "github_secret_invalid": (
                    int(bool(after_delivery_auth_invalid)) - int(bool(before_delivery_auth_invalid))
                ),
                "schema_freshness_blocker": (
                    int(bool(after_schema_freshness_blocker)) - int(bool(before_schema_freshness_blocker))
                ),
            },
        },
        "improved": {
            "calls": after_calls < before_calls,
            "tokens": (
                before_tokens is not None
                and after_tokens is not None
                and float(after_tokens) < float(before_tokens)
            ),
            "reject_rate": (
                before_reject_rate is not None
                and after_reject_rate is not None
                and float(after_reject_rate) < float(before_reject_rate)
            ),
            "hit_rate": (
                before_metrics["hit_rate"] is not None
                and after_metrics["hit_rate"] is not None
                and float(after_metrics["hit_rate"]) > float(before_metrics["hit_rate"])
            ),
            "full_scan_ratio": (
                before_metrics["full_scan_ratio"] is not None
                and after_metrics["full_scan_ratio"] is not None
                and float(after_metrics["full_scan_ratio"]) < float(before_metrics["full_scan_ratio"])
            ),
            "payload_bytes": {
                "total_result_bytes": (
                    before_payload_bytes is not None
                    and after_payload_bytes is not None
                    and float(after_payload_bytes) < float(before_payload_bytes)
                ),
                "search_result_bytes": (
                    before_search_payload_bytes is not None
                    and after_search_payload_bytes is not None
                    and float(after_search_payload_bytes) < float(before_search_payload_bytes)
                ),
                "read_source_result_bytes": (
                    before_read_source_payload_bytes is not None
                    and after_read_source_payload_bytes is not None
                    and float(after_read_source_payload_bytes) < float(before_read_source_payload_bytes)
                ),
            },
            "targeted_hit_within_3_calls": (
                (not before_metrics["targeted_hit_within_3_calls"])
                and bool(after_metrics["targeted_hit_within_3_calls"])
            ),
            "health": {
                "missing_delivery_snapshot": (
                    before_missing_snapshot is not None
                    and after_missing_snapshot is not None
                    and int(after_missing_snapshot) < int(before_missing_snapshot)
                ),
                "stale_delivery_snapshot": (
                    before_stale_snapshot is not None
                    and after_stale_snapshot is not None
                    and int(after_stale_snapshot) < int(before_stale_snapshot)
                ),
                "source_not_found_count": (
                    before_source_not_found is not None
                    and after_source_not_found is not None
                    and int(after_source_not_found) < int(before_source_not_found)
                ),
                "github_secret_invalid": (
                    bool(before_delivery_auth_invalid)
                    and not bool(after_delivery_auth_invalid)
                ),
                "schema_freshness_blocker": (
                    bool(before_schema_freshness_blocker)
                    and not bool(after_schema_freshness_blocker)
                ),
            },
        },
    }

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "delta.json"
    out_path.write_text(json.dumps(delta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"df_id": df_id, "out_path": str(out_path), **delta_payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dogfood before/after delta report")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--before-monitor", required=True)
    parser.add_argument("--before-producer", required=True)
    parser.add_argument("--after-monitor", required=True)
    parser.add_argument("--after-producer", required=True)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    payload = build_iteration_delta(
        df_id=args.df_id,
        before_monitor=args.before_monitor,
        before_producer=args.before_producer,
        after_monitor=args.after_monitor,
        after_producer=args.after_producer,
        out_root=args.out_root,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
