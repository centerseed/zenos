from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_iteration_artifacts.py"
    spec = importlib.util.spec_from_file_location("build_iteration_artifacts", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_iteration_artifacts_writes_producer_and_monitor(tmp_path: Path):
    mod = _load_script_module()
    root = Path(__file__).resolve().parents[2]
    fixture_dir = root / "tests" / "fixtures" / "transcripts" / "fake-project"

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-1",
        transcripts_dir=fixture_dir,
        out_root=tmp_path,
    )

    producer_path = Path(result["producer_path"])
    monitor_path = Path(result["monitor_path"])

    assert producer_path.exists()
    assert monitor_path.exists()

    producer_lines = producer_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(producer_lines) == 4  # 2 tool_use + 2 paired tool_result

    monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
    assert monitor["df_id"] == "DF-20260502-1"
    assert monitor["total_mcp_calls"] == 2
    assert monitor["rejected_count"] == 1
    assert monitor["reject_rate"] == 0.5
    assert monitor["top_rejection_reasons"][0]["count"] == 1
    assert monitor["payload_bytes"]["total_result_bytes"] > 0
    assert monitor["payload_bytes"]["by_tool"]["mcp__zenos__search"] > 0
    assert monitor["producer_artifact"] == str(producer_path)


def test_build_iteration_artifacts_picks_latest_session_when_not_specified(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    older = transcripts / "older.jsonl"
    newer = transcripts / "newer.jsonl"
    older.write_text(
        '{"timestamp":"2026-05-01T00:00:00.000Z","message":{"role":"assistant","content":[{"type":"tool_use","id":"u1","name":"mcp__zenos__search","input":{"query":"old"}}]}}\n',
        encoding="utf-8",
    )
    newer.write_text(
        '{"timestamp":"2026-05-02T00:00:00.000Z","message":{"role":"assistant","content":[{"type":"tool_use","id":"u2","name":"mcp__zenos__search","input":{"query":"new"}}]}}\n',
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-2",
        transcripts_dir=transcripts,
        out_root=tmp_path / "out",
    )

    assert Path(result["session_file"]).name == "newer.jsonl"


def test_build_iteration_artifacts_sums_usage_tokens(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "usage.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {
                                "input_tokens": 10,
                                "output_tokens": 3,
                                "cache_creation_input_tokens": 2,
                                "cache_read_input_tokens": 5,
                            },
                            "content": [
                                {"type": "tool_use", "id": "u1", "name": "mcp__zenos__search", "input": {"query": "new"}}
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {"type": "tool_result", "tool_use_id": "u1", "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":[]}"}]}
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:02.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {
                                "input_tokens": 4,
                                "output_tokens": 1,
                            },
                            "content": [{"type": "text", "text": "done"}],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-usage",
        transcripts_dir=transcripts,
        out_root=tmp_path / "out",
    )

    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))
    assert monitor["usage"]["input_tokens"] == 14
    assert monitor["usage"]["output_tokens"] == 4
    assert monitor["usage"]["cache_creation_input_tokens"] == 2
    assert monitor["usage"]["cache_read_input_tokens"] == 5
    assert monitor["usage"]["total_tokens"] == 25


def test_build_iteration_artifacts_call_filter_keeps_only_broad_document_searches(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "filter-broad.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 10, "output_tokens": 2},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "u1",
                                    "name": "mcp__zenos__search",
                                    "input": {"collection": "documents", "query": "flora"},
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "u1",
                                    "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":{\"documents\":[]}}"}],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:02.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 50, "output_tokens": 5},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "u2",
                                    "name": "mcp__zenos__search",
                                    "input": {"collection": "documents", "entity_name": "FloraGLO 葉黃素知識庫"},
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:03.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "u2",
                                    "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":{\"documents\":[{\"id\":\"doc-1\"}]}}"}],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:04.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 99, "output_tokens": 1},
                            "content": [{"type": "text", "text": "summary"}],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-broad",
        transcripts_dir=transcripts,
        session_file=str(session),
        call_filter="documents_broad",
        out_root=tmp_path / "out",
    )

    producer_lines = Path(result["producer_path"]).read_text(encoding="utf-8").strip().splitlines()
    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))

    assert len(producer_lines) == 2
    assert monitor["total_mcp_calls"] == 1
    assert monitor["usage"]["total_tokens"] == 12
    assert monitor["call_filter"] == "documents_broad"


def test_build_iteration_artifacts_call_filter_keeps_only_targeted_document_searches(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "filter-targeted.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 7, "output_tokens": 1},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "u1",
                                    "name": "mcp__zenos__search",
                                    "input": {"collection": "documents", "query": "flora"},
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "u1",
                                    "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":{\"documents\":[]}}"}],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:02.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 11, "output_tokens": 2},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "u2",
                                    "name": "mcp__zenos__search",
                                    "input": {"collection": "documents", "product_id": "prod-1"},
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:03.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "u2",
                                    "content": [{"type": "text", "text": "{\"status\":\"ok\",\"data\":{\"documents\":[{\"id\":\"doc-1\"}]}}"}],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-targeted",
        transcripts_dir=transcripts,
        session_file=str(session),
        call_filter="documents_targeted",
        out_root=tmp_path / "out",
    )

    producer_lines = Path(result["producer_path"]).read_text(encoding="utf-8").strip().splitlines()
    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))

    assert len(producer_lines) == 2
    assert monitor["total_mcp_calls"] == 1
    assert monitor["usage"]["total_tokens"] == 13
    assert monitor["call_filter"] == "documents_targeted"


def test_build_iteration_artifacts_supports_codex_session_schema(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "codex.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:23.877Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "search",
                            "namespace": "mcp__zenos__",
                            "arguments": json.dumps({"collection": "documents", "entity_name": "MCP 介面設計"}, ensure_ascii=False),
                            "call_id": "call_1",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:24.000Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 10,
                                    "output_tokens": 2,
                                    "cached_input_tokens": 5,
                                    "total_tokens": 17,
                                }
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:25.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call_1",
                            "output": "Wall time: 0.1 seconds\nOutput:\n{\"status\":\"ok\",\"data\":{\"documents\":[{\"id\":\"doc-1\"}]}}",
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-codex",
        transcripts_dir=transcripts,
        session_file=str(session),
        out_root=tmp_path / "out",
    )

    producer_lines = Path(result["producer_path"]).read_text(encoding="utf-8").strip().splitlines()
    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))

    assert len(producer_lines) == 2
    assert monitor["total_mcp_calls"] == 1
    assert monitor["rejected_count"] == 0
    assert monitor["usage"]["total_tokens"] == 17


def test_build_iteration_artifacts_counts_codex_tool_error_as_rejection(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "codex-error.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:23.877Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "read_source",
                            "namespace": "mcp__zenos__",
                            "arguments": json.dumps({"doc_id": "doc-1"}),
                            "call_id": "call_1",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:24.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call_1",
                            "output": "Wall time: 0.1 seconds\nOutput:\n[{\"type\":\"text\",\"text\":\"Error calling tool 'read_source': 401 Unauthorized\"}]",
                        },
                    }
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-codex-error",
        transcripts_dir=transcripts,
        session_file=str(session),
        out_root=tmp_path / "out",
    )

    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))
    assert monitor["total_mcp_calls"] == 1
    assert monitor["rejected_count"] == 1
    assert monitor["top_rejection_reasons"][0]["reason"] == "TOOL_ERROR"


def test_build_iteration_artifacts_counts_codex_validation_error_as_rejection(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "codex-validation-error.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:23.877Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "read_source",
                            "namespace": "mcp__zenos__",
                            "arguments": json.dumps({"doc_id": "doc-1", "preview_chars": 1200}),
                            "call_id": "call_1",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T08:24:24.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "call_1",
                            "output": (
                                "Wall time: 0.1 seconds\nOutput:\n"
                                "[{\"type\":\"text\",\"text\":\"1 validation error for call[read_source]\\n"
                                "preview_chars\\n  Unexpected keyword argument\"}]"
                            ),
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-codex-validation-error",
        transcripts_dir=transcripts,
        session_file=str(session),
        out_root=tmp_path / "out",
    )

    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))
    assert monitor["total_mcp_calls"] == 1
    assert monitor["rejected_count"] == 1
    assert monitor["top_rejection_reasons"][0]["reason"] == "TOOL_ERROR"


def test_build_iteration_artifacts_flags_schema_freshness_blocker_when_preview_expected_but_missing(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "preview-missing.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 10, "output_tokens": 2},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "u1",
                                    "name": "mcp__zenos__read_source",
                                    "input": {"doc_id": "doc-1", "source_id": "src-1"},
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "u1",
                                    "content": [{"type": "text", "text": "{\"status\":\"ok\",\"content\":\"abc\"}"}],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-preview-missing",
        transcripts_dir=transcripts,
        session_file=str(session),
        expect_read_source_preview=True,
        out_root=tmp_path / "out",
    )

    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))
    assert monitor["tool_contract"]["expect_read_source_preview"] is True
    assert monitor["tool_contract"]["read_source_calls"] == 1
    assert monitor["tool_contract"]["read_source_preview_present_count"] == 0
    assert monitor["tool_contract"]["read_source_preview_missing_count"] == 1
    assert monitor["tool_contract"]["schema_freshness_blocker"] is True


def test_build_iteration_artifacts_counts_present_preview_when_expected(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "preview-present.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.000Z",
                        "message": {
                            "role": "assistant",
                            "usage": {"input_tokens": 10, "output_tokens": 2},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "u1",
                                    "name": "mcp__zenos__read_source",
                                    "input": {"doc_id": "doc-1", "source_id": "src-1", "preview_chars": 1200},
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.000Z",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "u1",
                                    "content": [{"type": "text", "text": "{\"status\":\"ok\",\"content\":\"abc\"}"}],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        ) + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-preview-present",
        transcripts_dir=transcripts,
        session_file=str(session),
        expect_read_source_preview=True,
        out_root=tmp_path / "out",
    )

    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))
    assert monitor["tool_contract"]["read_source_calls"] == 1
    assert monitor["tool_contract"]["read_source_preview_present_count"] == 1
    assert monitor["tool_contract"]["read_source_preview_missing_count"] == 0
    assert monitor["tool_contract"]["schema_freshness_blocker"] is False


def test_build_iteration_artifacts_since_text_slices_to_current_df_marker(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()

    session = transcripts / "slice.jsonl"
    session.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "search",
                            "namespace": "mcp__zenos__",
                            "arguments": json.dumps({"collection": "documents", "query": "old"}, ensure_ascii=False),
                            "call_id": "old_call",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:00.100Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 900,
                                    "output_tokens": 10,
                                    "cached_input_tokens": 90,
                                    "total_tokens": 1000,
                                }
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.000Z",
                        "type": "event_msg",
                        "payload": {"type": "user_message", "message": "我要跑 DF-20260502-27f clean-room verifier"},
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:01.100Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 700,
                                    "output_tokens": 7,
                                    "cached_input_tokens": 70,
                                    "total_tokens": 777,
                                }
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:02.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "read_source",
                            "namespace": "mcp__zenos__",
                            "arguments": json.dumps({"doc_id": "doc-1", "preview_chars": 1200}),
                            "call_id": "new_call",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:02.100Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 11,
                                    "output_tokens": 2,
                                    "cached_input_tokens": 3,
                                    "total_tokens": 16,
                                }
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:03.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call_output",
                            "call_id": "new_call",
                            "output": "Wall time: 0.1 seconds\nOutput:\n{\"status\":\"ok\",\"data\":{\"content_type\":\"full\"}}",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2026-05-02T00:00:04.000Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {
                                    "input_tokens": 9000,
                                    "output_tokens": 90,
                                    "cached_input_tokens": 900,
                                    "total_tokens": 9990,
                                }
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.build_iteration_artifacts(
        df_id="DF-20260502-27f",
        transcripts_dir=transcripts,
        session_file=str(session),
        since_text="DF-20260502-27f",
        expect_read_source_preview=True,
        out_root=tmp_path / "out",
    )

    producer_lines = Path(result["producer_path"]).read_text(encoding="utf-8").strip().splitlines()
    monitor = json.loads(Path(result["monitor_path"]).read_text(encoding="utf-8"))

    assert len(producer_lines) == 2
    assert monitor["slice"]["since_text"] == "DF-20260502-27f"
    assert monitor["slice"]["started_at"] == "2026-05-02T00:00:01.000Z"
    assert monitor["total_mcp_calls"] == 1
    assert monitor["usage"]["total_tokens"] == 16
    assert monitor["tool_contract"]["read_source_preview_present_count"] == 1


def test_build_iteration_artifacts_since_text_missing_fails(tmp_path: Path):
    mod = _load_script_module()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    session = transcripts / "missing-marker.jsonl"
    session.write_text(
        '{"timestamp":"2026-05-02T00:00:00.000Z","type":"event_msg","payload":{"type":"user_message","message":"other run"}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="since_text marker not found"):
        mod.build_iteration_artifacts(
            df_id="DF-20260502-27f",
            transcripts_dir=transcripts,
            session_file=str(session),
            since_text="DF-20260502-27f",
            out_root=tmp_path / "out",
        )
