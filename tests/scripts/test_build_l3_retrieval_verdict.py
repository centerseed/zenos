from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_l3_retrieval_verdict.py"
    spec = importlib.util.spec_from_file_location("build_l3_retrieval_verdict", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def _tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "namespace": "mcp__zenos__",
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
            "call_id": call_id,
        },
    }


def _tool_output(call_id: str, payload: dict) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": "Wall time: 0.1 seconds\nOutput:\n" + json.dumps(payload, ensure_ascii=False),
        },
    }


def _happy_producer_lines(*, read_source_payload: dict) -> list[dict]:
    return [
        _tool_call(
            "c1",
            "search",
            {
                "collection": "entities",
                "query": "Action Layer",
                "entity_level": "L2",
                "include": ["summary"],
                "product_id": "prod-1",
                "limit": 5,
            },
        ),
        _tool_output("c1", {"status": "ok", "data": {"entities": [{"id": "l2-1", "name": "Action Layer"}]}}),
        _tool_call(
            "c2",
            "search",
            {
                "collection": "documents",
                "entity_name": "Action Layer",
                "include": ["summary_compact"],
                "product_id": "prod-1",
                "limit": 3,
            },
        ),
        _tool_output("c2", {"status": "ok", "data": {"documents": [{"id": "doc-1", "name": "Action Layer PRD"}]}}),
        _tool_call("c3", "read_source", {"doc_id": "doc-1", "source_id": "src-1", "preview_chars": 1200}),
        _tool_output("c3", read_source_payload),
    ]


def test_build_l3_retrieval_verdict_fails_empty_artifact(tmp_path: Path):
    mod = _load_script_module()
    monitor = tmp_path / "monitor.json"
    producer = tmp_path / "producer.jsonl"
    monitor.write_text(
        json.dumps({"total_mcp_calls": 0, "rejected_count": 0, "reject_rate": 0.0, "usage": {"total_tokens": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    producer.write_text("", encoding="utf-8")

    result = mod.build_l3_retrieval_verdict(
        df_id="DF-empty",
        monitor_json=monitor,
        producer_jsonl=producer,
        token_budget=30000,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["verdict"] == "FAIL"
    assert "unexpected_mcp_call_count" in payload["failures"]
    assert "missing_single_read_source_call" in payload["failures"]


def test_build_l3_retrieval_verdict_partial_for_routing_pass_but_source_and_token_fail(tmp_path: Path):
    mod = _load_script_module()
    monitor = tmp_path / "monitor.json"
    producer = tmp_path / "producer.jsonl"
    monitor.write_text(
        json.dumps(
            {
                "total_mcp_calls": 3,
                "rejected_count": 0,
                "reject_rate": 0.0,
                "usage": {"total_tokens": 156376, "cache_read_input_tokens": 150144},
                "payload_bytes": {"total_result_bytes": 8351},
                "tool_contract": {"schema_freshness_blocker": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        producer,
        _happy_producer_lines(
            read_source_payload={
                "status": "ok",
                "data": {
                    "content_type": "document_summary",
                    "delivery_status": "summary_fallback",
                    "preview_chars": 1200,
                },
            }
        ),
    )

    result = mod.build_l3_retrieval_verdict(
        df_id="DF-partial",
        monitor_json=monitor,
        producer_jsonl=producer,
        token_budget=30000,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["verdict"] == "PARTIAL"
    assert payload["routing_pass"] is True
    assert payload["source_delivery_pass"] is False
    assert payload["token_gate_pass"] is False
    assert "source_delivery_summary_fallback" in payload["failures"]
    assert "token_budget_exceeded" in payload["failures"]
    assert "token_budget_contaminated" in payload["failures"]


def test_build_l3_retrieval_verdict_passes_happy_path(tmp_path: Path):
    mod = _load_script_module()
    monitor = tmp_path / "monitor.json"
    producer = tmp_path / "producer.jsonl"
    monitor.write_text(
        json.dumps(
            {
                "total_mcp_calls": 3,
                "rejected_count": 0,
                "reject_rate": 0.0,
                "usage": {"total_tokens": 2500, "cache_read_input_tokens": 0},
                "payload_bytes": {"total_result_bytes": 5000},
                "tool_contract": {"schema_freshness_blocker": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        producer,
        _happy_producer_lines(
            read_source_payload={
                "status": "ok",
                "data": {
                    "content_type": "full",
                    "delivery_status": "ready",
                    "preview_chars": 1200,
                    "content_truncated": True,
                },
            }
        ),
    )

    result = mod.build_l3_retrieval_verdict(
        df_id="DF-pass",
        monitor_json=monitor,
        producer_jsonl=producer,
        token_budget=30000,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS"
    assert payload["routing_pass"] is True
    assert payload["source_delivery_pass"] is True
    assert payload["token_gate_pass"] is True
    assert payload["failures"] == []


def test_build_l3_retrieval_verdict_flags_read_source_preview_schema_error(tmp_path: Path):
    mod = _load_script_module()
    monitor = tmp_path / "monitor.json"
    producer = tmp_path / "producer.jsonl"
    monitor.write_text(
        json.dumps(
            {
                "total_mcp_calls": 3,
                "rejected_count": 1,
                "reject_rate": 1 / 3,
                "usage": {"total_tokens": 2500, "cache_read_input_tokens": 0},
                "payload_bytes": {"total_result_bytes": 5000},
                "tool_contract": {"schema_freshness_blocker": False},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        producer,
        [
            *_happy_producer_lines(read_source_payload={"status": "ok", "data": {"content_type": "full", "delivery_status": "ready"}})[:4],
            _tool_call("c3", "read_source", {"doc_id": "doc-1", "source_id": "src-1", "preview_chars": 1200}),
            _tool_output(
                "c3",
                [
                    {
                        "type": "text",
                        "text": (
                            "1 validation error for call[read_source]\n"
                            "preview_chars\n"
                            "  Unexpected keyword argument"
                        ),
                    }
                ],
            ),
        ],
    )

    result = mod.build_l3_retrieval_verdict(
        df_id="DF-schema-error",
        monitor_json=monitor,
        producer_jsonl=producer,
        token_budget=30000,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["verdict"] == "FAIL"
    assert "tool_result_rejected" in payload["failures"]
    assert "schema_freshness_blocker" in payload["failures"]
