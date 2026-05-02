"""
build_l3_retrieval_verdict.py

Builds a machine-readable verdict for a single L3 graph retrieval dogfood run.

Inputs:
- producer.jsonl from build_iteration_artifacts.py
- monitor.json from build_iteration_artifacts.py

Output:
- /tmp/zenos-dogfood/{DF-ID}/verdict.json
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


def _extract_result_payload(event: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    text = _extract_text(item.get("content", ""))
    if text:
        payload = _maybe_parse_json_text(text)
        if payload:
            return payload

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


def _parse_producer(path: str | Path) -> list[dict[str, Any]]:
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
                                "input": item.get("input", {}) if isinstance(item.get("input"), dict) else {},
                            }
                    elif role == "user":
                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_result":
                                continue
                            tool_id = str(item.get("tool_use_id", ""))
                            call = pending.pop(tool_id, None)
                            if call is None:
                                continue
                            calls.append({**call, "result": _extract_result_payload(event, item)})
                    if role in {"assistant", "user"}:
                        continue

            if str(event.get("type", "")) != "response_item":
                continue
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            payload_type = str(payload.get("type", ""))
            if payload_type == "function_call":
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
                    "name": _qualify_codex_tool_name(str(payload.get("namespace", "")), str(payload.get("name", ""))),
                    "input": parsed_args,
                }
            elif payload_type == "function_call_output":
                tool_id = str(payload.get("call_id", ""))
                call = pending.pop(tool_id, None)
                if call is None:
                    continue
                calls.append({**call, "result": _maybe_parse_json_text(str(payload.get("output", "")))})

    return calls


def _document_count(result: dict[str, Any]) -> int:
    data = result.get("data")
    if isinstance(data, dict) and isinstance(data.get("documents"), list):
        return len(data["documents"])
    if isinstance(result.get("documents"), list):
        return len(result["documents"])
    return 0


def _read_source_data(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    if isinstance(data, dict):
        return data
    return result


def build_l3_retrieval_verdict(
    *,
    df_id: str,
    monitor_json: str | Path,
    producer_jsonl: str | Path,
    token_budget: int,
    expected_calls: int = 3,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    monitor = _read_json(monitor_json)
    calls = _parse_producer(producer_jsonl)
    failures: list[str] = []
    warnings: list[str] = []

    total_calls = int(monitor.get("total_mcp_calls") or len(calls))
    if total_calls != expected_calls:
        failures.append("unexpected_mcp_call_count")

    if int(monitor.get("rejected_count") or 0) > 0:
        failures.append("mcp_rejections_present")

    broad_document_searches = [
        call for call in calls
        if call.get("name") == "mcp__zenos__search"
        and str((call.get("input") or {}).get("collection") or "").lower() == "documents"
        and not (call.get("input") or {}).get("entity_name")
    ]
    if broad_document_searches:
        failures.append("documents_keyword_or_full_scan_used")

    entity_searches = [
        call for call in calls
        if call.get("name") == "mcp__zenos__search"
        and str((call.get("input") or {}).get("collection") or "").lower() == "entities"
    ]
    targeted_document_searches = [
        call for call in calls
        if call.get("name") == "mcp__zenos__search"
        and str((call.get("input") or {}).get("collection") or "").lower() == "documents"
        and bool((call.get("input") or {}).get("entity_name"))
    ]
    read_source_calls = [call for call in calls if call.get("name") == "mcp__zenos__read_source"]

    if len(entity_searches) != 1:
        failures.append("missing_single_l2_entity_search")
    if len(targeted_document_searches) != 1:
        failures.append("missing_single_targeted_l3_document_search")
    if len(read_source_calls) != 1:
        failures.append("missing_single_read_source_call")

    l2_hit = bool(entity_searches and _document_count(entity_searches[0].get("result") or {}) == 0)
    # Entity results use "entities", not documents; keep a direct check.
    if entity_searches:
        data = (entity_searches[0].get("result") or {}).get("data")
        entities = data.get("entities") if isinstance(data, dict) else None
        l2_hit = isinstance(entities, list) and len(entities) > 0
    if not l2_hit:
        failures.append("l2_entity_not_hit")

    l3_hit = bool(targeted_document_searches and _document_count(targeted_document_searches[0].get("result") or {}) > 0)
    if not l3_hit:
        failures.append("l3_bundle_not_hit")

    read_source_preview_present = bool(
        read_source_calls and (read_source_calls[0].get("input") or {}).get("preview_chars") is not None
    )
    if not read_source_preview_present:
        failures.append("read_source_preview_missing")

    read_source_actual_preview = False
    read_source_summary_fallback = False
    if read_source_calls:
        read_data = _read_source_data(read_source_calls[0].get("result") or {})
        content_type = str(read_data.get("content_type") or "")
        delivery_status = str(read_data.get("delivery_status") or "")
        read_source_summary_fallback = content_type == "document_summary" or delivery_status == "summary_fallback"
        read_source_actual_preview = bool(content_type and content_type != "document_summary" and delivery_status != "summary_fallback")
        if read_source_summary_fallback:
            failures.append("source_delivery_summary_fallback")
        elif not read_source_actual_preview:
            warnings.append("source_preview_unclassified")

    usage = monitor.get("usage") or {}
    total_tokens = int(usage.get("total_tokens") or 0)
    cache_read_tokens = int(usage.get("cache_read_input_tokens") or 0)
    token_gate_pass = total_tokens <= token_budget
    token_contaminated = cache_read_tokens > token_budget or (total_tokens > 0 and cache_read_tokens / max(total_tokens, 1) >= 0.5)
    if not token_gate_pass:
        failures.append("token_budget_exceeded")
    if token_contaminated:
        failures.append("token_budget_contaminated")

    tool_contract = monitor.get("tool_contract") or {}
    if tool_contract.get("schema_freshness_blocker"):
        failures.append("schema_freshness_blocker")

    routing_pass = (
        total_calls == expected_calls
        and not broad_document_searches
        and len(entity_searches) == 1
        and len(targeted_document_searches) == 1
        and len(read_source_calls) == 1
        and l2_hit
        and l3_hit
        and read_source_preview_present
    )
    source_delivery_pass = read_source_actual_preview and not read_source_summary_fallback

    if not failures:
        verdict = "PASS"
    elif routing_pass and ("source_delivery_summary_fallback" in failures or "token_budget_exceeded" in failures or "token_budget_contaminated" in failures):
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    payload = {
        "df_id": df_id,
        "verdict": verdict,
        "routing_pass": routing_pass,
        "source_delivery_pass": source_delivery_pass,
        "token_gate_pass": token_gate_pass and not token_contaminated,
        "failures": failures,
        "warnings": warnings,
        "metrics": {
            "total_mcp_calls": total_calls,
            "expected_mcp_calls": expected_calls,
            "rejected_count": int(monitor.get("rejected_count") or 0),
            "reject_rate": float(monitor.get("reject_rate") or 0.0),
            "usage_total_tokens": total_tokens,
            "cache_read_input_tokens": cache_read_tokens,
            "token_budget": token_budget,
            "payload_total_result_bytes": int(((monitor.get("payload_bytes") or {}).get("total_result_bytes")) or 0),
        },
        "artifacts": {
            "monitor_json": str(monitor_json),
            "producer_jsonl": str(producer_jsonl),
        },
    }

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "verdict.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"df_id": df_id, "out_path": str(out_path), "verdict": verdict}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build L3 retrieval dogfood verdict from monitor/producer artifacts")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--monitor-json", required=True)
    parser.add_argument("--producer-jsonl", required=True)
    parser.add_argument("--token-budget", type=int, required=True)
    parser.add_argument("--expected-calls", type=int, default=3)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    result = build_l3_retrieval_verdict(
        df_id=args.df_id,
        monitor_json=args.monitor_json,
        producer_jsonl=args.producer_jsonl,
        token_budget=args.token_budget,
        expected_calls=args.expected_calls,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
