from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_iteration_delta.py"
    spec = importlib.util.spec_from_file_location("build_iteration_delta", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def test_build_iteration_delta_compares_before_and_after(tmp_path: Path):
    mod = _load_script_module()

    before_monitor = tmp_path / "before-monitor.json"
    before_monitor.write_text(
        json.dumps({
            "total_mcp_calls": 4,
            "reject_rate": 0.25,
            "usage": {"total_tokens": 120},
            "payload_bytes": {
                "total_result_bytes": 900,
                "by_tool": {"mcp__zenos__search": 700, "mcp__zenos__read_source": 200},
            },
            "health": {
                "invalid_documents": {"current_formal_entry_missing_delivery_snapshot": 3, "current_formal_entry_stale_delivery_snapshot": 1},
                "source_governance": {"source_not_found_count": 2},
                "delivery_auth": {"github_secret_invalid": True},
            },
            "tool_contract": {"schema_freshness_blocker": True},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    after_monitor = tmp_path / "after-monitor.json"
    after_monitor.write_text(
        json.dumps({
            "total_mcp_calls": 2,
            "reject_rate": 0.0,
            "usage": {"total_tokens": 70},
            "payload_bytes": {
                "total_result_bytes": 500,
                "by_tool": {"mcp__zenos__search": 250, "mcp__zenos__read_source": 250},
            },
            "health": {
                "invalid_documents": {"current_formal_entry_missing_delivery_snapshot": 1, "current_formal_entry_stale_delivery_snapshot": 0},
                "source_governance": {"source_not_found_count": 0},
                "delivery_auth": {"github_secret_invalid": False},
            },
            "tool_contract": {"schema_freshness_blocker": False},
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    before_producer = tmp_path / "before-producer.jsonl"
    _write_jsonl(before_producer, [
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "u1", "name": "mcp__zenos__search", "input": {"collection": "documents", "query": "foo"}}],
            }
        },
        {
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "u1", "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":{\"documents\":[]}}"}]}],
            }
        },
    ])

    after_producer = tmp_path / "after-producer.jsonl"
    _write_jsonl(after_producer, [
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "u2", "name": "mcp__zenos__search", "input": {"collection": "documents", "entity_name": "L2"}}],
            }
        },
        {
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "u2", "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":{\"documents\":[{\"id\":\"doc-1\"}]}}"}]}],
            }
        },
    ])

    result = mod.build_iteration_delta(
        df_id="DF-20260502-4",
        before_monitor=before_monitor,
        before_producer=before_producer,
        after_monitor=after_monitor,
        after_producer=after_producer,
        out_root=tmp_path,
    )

    out_path = Path(result["out_path"])
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["before"]["calls"] == 4
    assert payload["after"]["calls"] == 2
    assert payload["before"]["tokens"] == 120
    assert payload["after"]["tokens"] == 70
    assert payload["before"]["payload_bytes"]["total_result_bytes"] == 900
    assert payload["after"]["payload_bytes"]["search_result_bytes"] == 250
    assert payload["before"]["full_scan_ratio"] == 1.0
    assert payload["after"]["full_scan_ratio"] == 0.0
    assert payload["after"]["hit_rate"] == 1.0
    assert payload["improved"]["calls"] is True
    assert payload["improved"]["tokens"] is True
    assert payload["delta"]["payload_bytes"]["total_result_bytes"] == -400.0
    assert payload["improved"]["payload_bytes"]["search_result_bytes"] is True
    assert payload["improved"]["full_scan_ratio"] is True
    assert payload["improved"]["targeted_hit_within_3_calls"] is True
    assert payload["before"]["health"]["missing_delivery_snapshot"] == 3
    assert payload["after"]["health"]["source_not_found_count"] == 0
    assert payload["delta"]["health"]["missing_delivery_snapshot"] == -2.0
    assert payload["delta"]["health"]["github_secret_invalid"] == -1
    assert payload["delta"]["health"]["schema_freshness_blocker"] == -1
    assert payload["improved"]["health"]["source_not_found_count"] is True
    assert payload["improved"]["health"]["github_secret_invalid"] is True
    assert payload["improved"]["health"]["schema_freshness_blocker"] is True


def test_build_iteration_delta_accepts_top_level_documents_payload(tmp_path: Path):
    mod = _load_script_module()

    monitor = tmp_path / "monitor.json"
    monitor.write_text(
        json.dumps({"total_mcp_calls": 1, "reject_rate": 0.0, "usage": {"total_tokens": 42}}, ensure_ascii=False),
        encoding="utf-8",
    )

    producer = tmp_path / "producer.jsonl"
    _write_jsonl(producer, [
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "u1", "name": "mcp__zenos__search", "input": {"collection": "documents", "product_id": "prod-1"}}],
            }
        },
        {
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "u1", "content": [{"type": "text", "text": "{\"documents\":[{\"id\":\"doc-1\"}]}"}]}],
            }
        },
    ])

    result = mod.build_iteration_delta(
        df_id="DF-20260502-top-level",
        before_monitor=monitor,
        before_producer=producer,
        after_monitor=monitor,
        after_producer=producer,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["before"]["hit_rate"] == 1.0
    assert payload["before"]["targeted_hit_within_3_calls"] is True
    assert payload["before"]["payload_bytes"]["search_result_bytes"] > 0


def test_build_iteration_delta_falls_back_to_mcp_meta_structured_content(tmp_path: Path):
    mod = _load_script_module()

    monitor = tmp_path / "monitor.json"
    monitor.write_text(
        json.dumps({"total_mcp_calls": 1, "reject_rate": 0.0, "usage": {"total_tokens": 42}}, ensure_ascii=False),
        encoding="utf-8",
    )

    producer = tmp_path / "producer.jsonl"
    _write_jsonl(producer, [
        {
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "u1", "name": "mcp__zenos__search", "input": {"collection": "documents", "query": "", "limit": 200}}],
            }
        },
        {
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "u1", "content": "Error: result exceeds maximum allowed tokens"}],
            },
            "mcpMeta": {
                "structuredContent": {
                    "documents": [{"id": "doc-1"}]
                }
            },
        },
    ])

    result = mod.build_iteration_delta(
        df_id="DF-20260502-mcpmeta",
        before_monitor=monitor,
        before_producer=producer,
        after_monitor=monitor,
        after_producer=producer,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["before"]["hit_rate"] == 1.0
    assert payload["before"]["full_scan_ratio"] == 1.0
    assert payload["before"]["payload_bytes"]["search_result_bytes"] > 0


def test_build_iteration_delta_supports_codex_producer_schema(tmp_path: Path):
    mod = _load_script_module()

    before_monitor = tmp_path / "before-monitor.json"
    before_monitor.write_text(
        json.dumps({"total_mcp_calls": 1, "reject_rate": 0.0, "usage": {"total_tokens": 100}}, ensure_ascii=False),
        encoding="utf-8",
    )
    after_monitor = tmp_path / "after-monitor.json"
    after_monitor.write_text(
        json.dumps({"total_mcp_calls": 1, "reject_rate": 0.0, "usage": {"total_tokens": 80}}, ensure_ascii=False),
        encoding="utf-8",
    )

    before_producer = tmp_path / "before-producer.jsonl"
    _write_jsonl(before_producer, [
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "search",
                "namespace": "mcp__zenos__",
                "arguments": json.dumps({"collection": "documents", "query": "flora"}),
                "call_id": "call_1",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "Output:\n{\"status\":\"ok\",\"data\":{\"documents\":[{\"id\":\"doc-broad\"}]}}",
            },
        },
    ])

    after_producer = tmp_path / "after-producer.jsonl"
    _write_jsonl(after_producer, [
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "search",
                "namespace": "mcp__zenos__",
                "arguments": json.dumps({"collection": "documents", "entity_name": "FloraGLO 葉黃素知識庫"}, ensure_ascii=False),
                "call_id": "call_2",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": "Output:\n{\"status\":\"ok\",\"data\":{\"documents\":[{\"id\":\"doc-targeted\"}]}}",
            },
        },
    ])

    result = mod.build_iteration_delta(
        df_id="DF-20260502-codex",
        before_monitor=before_monitor,
        before_producer=before_producer,
        after_monitor=after_monitor,
        after_producer=after_producer,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["before"]["hit_rate"] == 1.0
    assert payload["before"]["full_scan_ratio"] == 1.0
    assert payload["after"]["hit_rate"] == 1.0
    assert payload["after"]["full_scan_ratio"] == 0.0
    assert payload["improved"]["tokens"] is True
    assert payload["before"]["payload_bytes"]["search_result_bytes"] > 0
    assert payload["after"]["payload_bytes"]["search_result_bytes"] > 0
    assert payload["improved"]["full_scan_ratio"] is True


def test_build_iteration_delta_treats_missing_boolean_health_metrics_as_false(tmp_path: Path):
    mod = _load_script_module()

    before_monitor = tmp_path / "before-monitor.json"
    before_monitor.write_text(
        json.dumps({"total_mcp_calls": 1, "reject_rate": 0.0, "usage": {"total_tokens": 100}}, ensure_ascii=False),
        encoding="utf-8",
    )
    after_monitor = tmp_path / "after-monitor.json"
    after_monitor.write_text(
        json.dumps(
            {
                "total_mcp_calls": 1,
                "reject_rate": 0.0,
                "usage": {"total_tokens": 80},
                "tool_contract": {"schema_freshness_blocker": True},
                "health": {"delivery_auth": {"github_secret_invalid": True}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    before_producer = tmp_path / "before-producer.jsonl"
    after_producer = tmp_path / "after-producer.jsonl"
    _write_jsonl(before_producer, [])
    _write_jsonl(after_producer, [])

    result = mod.build_iteration_delta(
        df_id="DF-20260502-bool-health",
        before_monitor=before_monitor,
        before_producer=before_producer,
        after_monitor=after_monitor,
        after_producer=after_producer,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["before"]["health"]["github_secret_invalid"] is False
    assert payload["before"]["health"]["schema_freshness_blocker"] is False
    assert payload["after"]["health"]["github_secret_invalid"] is True
    assert payload["after"]["health"]["schema_freshness_blocker"] is True
    assert payload["delta"]["health"]["github_secret_invalid"] == 1
    assert payload["delta"]["health"]["schema_freshness_blocker"] == 1
