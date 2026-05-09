from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_monitor_report.py"
    spec = importlib.util.spec_from_file_location("build_monitor_report", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_monitor_report_merges_traffic_and_health(tmp_path: Path):
    mod = _load_script_module()

    monitor_path = tmp_path / "monitor.json"
    monitor_path.write_text(
        json.dumps(
            {
                "df_id": "DF-20260502-3",
                "total_mcp_calls": 5,
                "rejected_count": 1,
                "reject_rate": 0.2,
                "tool_contract": {"schema_freshness_blocker": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    quality_path = tmp_path / "quality.json"
    quality_path.write_text(
        json.dumps(
            {
                "data": {
                    "quality": {
                        "score": 82,
                        "active_l2_missing_impacts": 1,
                        "entry_saturation_count": 2,
                        "failed": [{"name": "l2_impacts_coverage"}],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    staleness_path = tmp_path / "staleness.json"
    staleness_path.write_text(
        json.dumps(
            {
                "data": {
                    "staleness": {
                        "count": 3,
                        "document_consistency_count": 1,
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    invalid_documents_path = tmp_path / "invalid_documents.json"
    invalid_documents_path.write_text(
        json.dumps(
            {
                "data": {
                    "invalid_documents": {
                        "count": 0,
                        "bundle_issue_count": 3,
                        "bundle_issues": [
                            {"issue_type": "current_formal_entry_missing_delivery_snapshot"},
                            {"issue_type": "current_formal_entry_missing_delivery_snapshot"},
                            {"issue_type": "current_formal_entry_stale_delivery_snapshot"},
                        ],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_repair_queue_path = tmp_path / "source-repair-queue.json"
    source_repair_queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {"doc_id": "d1", "alternative_uris": ["https://example.com/alt-1"]},
                    {"doc_id": "d2", "alternative_uris": []},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    github_secret_health_path = tmp_path / "github-secret-health.json"
    github_secret_health_path.write_text(
        json.dumps(
            {
                "status": "rejected",
                "error": "INVALID_GITHUB_TOKEN",
                "http_status": 401,
                "message": "Bad credentials",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(
        json.dumps(
            {
                "data": {
                    "tasks": [
                        {"id": "t1", "status": "todo", "updated_at": "2026-04-20T00:00:00Z"},
                        {"id": "t2", "status": "todo", "updated_at": "2026-05-02T00:00:00Z"},
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    blindspots_path = tmp_path / "blindspots.json"
    blindspots_path.write_text(
        json.dumps(
            {
                "data": {
                    "blindspots": [
                        {"id": "b1", "severity": "green", "status": "open"},
                        {"id": "b2", "severity": "yellow", "status": "open"},
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = mod.build_monitor_report(
        df_id="DF-20260502-3",
        existing_monitor=monitor_path,
        quality_json=quality_path,
        staleness_json=staleness_path,
        invalid_documents_json=invalid_documents_path,
        source_repair_queue_json=source_repair_queue_path,
        github_delivery_secret_health_json=github_secret_health_path,
        tasks_json=tasks_path,
        blindspots_json=blindspots_path,
    )

    payload = json.loads(monitor_path.read_text(encoding="utf-8"))
    assert result["findings_count"] == 12
    assert payload["total_mcp_calls"] == 5
    assert payload["health"]["l2_entities"]["score"] == 82
    assert payload["health"]["l3_documents"]["stale_count"] == 3
    assert payload["health"]["invalid_documents"]["current_formal_entry_missing_delivery_snapshot"] == 2
    assert payload["health"]["invalid_documents"]["current_formal_entry_stale_delivery_snapshot"] == 1
    assert payload["health"]["source_governance"]["source_not_found_count"] == 2
    assert payload["health"]["source_governance"]["alternative_uri_candidate_count"] == 1
    assert payload["health"]["delivery_auth"]["github_secret_invalid"] is True
    assert payload["health"]["delivery_auth"]["github_secret_http_status"] == 401
    assert payload["health"]["tasks"]["todo_count"] == 2
    assert payload["health"]["blindspots"]["green_open_count"] == 1
    assert "L2 missing impacts: 1" in payload["findings"]
    assert "Current formal-entry missing delivery snapshot: 2" in payload["findings"]
    assert "Current formal-entry SOURCE_NOT_FOUND during controlled replay: 2" in payload["findings"]
    assert "GitHub delivery secret invalid (401)" in payload["findings"]
    assert "Tool schema freshness blocker: expected preview param missing from transcript" in payload["findings"]


def test_build_monitor_report_creates_monitor_without_existing_base(tmp_path: Path):
    mod = _load_script_module()

    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(
        json.dumps({"data": {"tasks": []}}, ensure_ascii=False),
        encoding="utf-8",
    )

    result = mod.build_monitor_report(
        df_id="DF-20260502-4",
        tasks_json=tasks_path,
        out_root=tmp_path,
    )

    out_path = Path(result["out_path"])
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["df_id"] == "DF-20260502-4"
    assert payload["health"]["tasks"]["todo_count"] == 0
