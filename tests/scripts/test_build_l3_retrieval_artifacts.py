from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_l3_retrieval_artifacts.py"
    spec = importlib.util.spec_from_file_location("build_l3_retrieval_artifacts", script_path)
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
        "timestamp": "2026-05-02T00:00:02.000Z",
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
        "timestamp": "2026-05-02T00:00:03.000Z",
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": "Wall time: 0.1 seconds\nOutput:\n" + json.dumps(payload, ensure_ascii=False),
        },
    }


def _token_count(total: int) -> dict:
    return {
        "timestamp": "2026-05-02T00:00:02.100Z",
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "last_token_usage": {
                    "input_tokens": total - 2,
                    "output_tokens": 2,
                    "cached_input_tokens": 0,
                    "total_tokens": total,
                }
            },
        },
    }


def test_build_l3_retrieval_artifacts_builds_monitor_and_verdict(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    session = transcripts / "session.jsonl"
    _write_jsonl(
        session,
        [
            {
                "timestamp": "2026-05-02T00:00:00.000Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "我要跑 DF-20260502-27g clean-room verifier"},
            },
            _tool_call("c1", "search", {"collection": "entities", "query": "Action Layer", "entity_level": "L2", "include": ["summary"], "product_id": "prod-1", "limit": 5}),
            _token_count(100),
            _tool_output("c1", {"status": "ok", "data": {"entities": [{"id": "l2-1", "name": "Action Layer"}]}}),
            _tool_call("c2", "search", {"collection": "documents", "entity_name": "Action Layer", "include": ["summary_compact"], "product_id": "prod-1", "limit": 3}),
            _token_count(100),
            _tool_output("c2", {"status": "ok", "data": {"documents": [{"id": "doc-1", "name": "Action Layer PRD"}]}}),
            _tool_call("c3", "read_source", {"doc_id": "doc-1", "source_id": "src-1", "preview_chars": 1200}),
            _token_count(100),
            _tool_output("c3", {"status": "ok", "data": {"content_type": "full", "delivery_status": "ready", "preview_chars": 1200}}),
        ],
    )

    result = mod.build_l3_retrieval_artifacts(
        df_id="DF-20260502-27g",
        transcripts_dir=transcripts,
        session_file=str(session),
        since_text="DF-20260502-27g",
        token_budget=30000,
        out_root=tmp_path / "out",
    )

    assert result["total_mcp_calls"] == 3
    assert result["verdict"] == "PASS"
    assert Path(result["producer_path"]).exists()
    assert Path(result["monitor_path"]).exists()
    assert Path(result["verdict_path"]).exists()

    verdict = json.loads(Path(result["verdict_path"]).read_text(encoding="utf-8"))
    assert verdict["routing_pass"] is True
    assert verdict["source_delivery_pass"] is True
    assert verdict["token_gate_pass"] is True


def test_build_l3_retrieval_artifacts_marks_empty_slice_fail(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    session = transcripts / "empty.jsonl"
    _write_jsonl(
        session,
        [
            {
                "timestamp": "2026-05-02T00:00:00.000Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "DF-20260502-empty"},
            }
        ],
    )

    result = mod.build_l3_retrieval_artifacts(
        df_id="DF-20260502-empty",
        transcripts_dir=transcripts,
        session_file=str(session),
        since_text="DF-20260502-empty",
        token_budget=30000,
        out_root=tmp_path / "out",
    )

    assert result["total_mcp_calls"] == 0
    assert result["verdict"] == "FAIL"
    verdict = json.loads(Path(result["verdict_path"]).read_text(encoding="utf-8"))
    assert "unexpected_mcp_call_count" in verdict["failures"]
