from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_baseline_library.py"
    spec = importlib.util.spec_from_file_location("build_baseline_library", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_baseline_library_filters_capture_and_classifies_topics():
    mod = _load_script_module()
    entries = [
        {
            "id": "j1",
            "created_at": "2026-05-01T00:00:00Z",
            "project": "ZenOS",
            "flow_type": "capture",
            "summary": "整理 zenos governance flow",
            "tags": ["tokens:120", "entries:2", "documents:1", "blindspots:1"],
        },
        {
            "id": "j2",
            "created_at": "2026-05-01T01:00:00Z",
            "project": "Paceriz",
            "flow_type": "capture",
            "summary": "CRM customer call capture",
            "tags": ["entries:1"],
        },
        {
            "id": "j3",
            "created_at": "2026-05-01T02:00:00Z",
            "project": "Marketing",
            "flow_type": "feature",
            "summary": "should be ignored",
            "tags": ["tokens:999"],
        },
    ]

    baseline = mod.build_baseline_library(entries)

    assert baseline["total_capture_sessions"] == 2
    assert baseline["topic_distribution"]["zenos-core"] == 1
    assert baseline["topic_distribution"]["crm"] == 1
    assert baseline["project_distribution"]["ZenOS"] == 1
    assert baseline["project_distribution"]["Paceriz"] == 1
    assert baseline["avg_outputs"]["entries"] == 1.5
    assert baseline["avg_outputs"]["documents"] == 1.0
    assert baseline["avg_outputs"]["blindspots"] == 1.0
    assert baseline["explicit_token_count"] == 1
    assert len(baseline["scenarios"]) == 2


def test_build_baseline_library_accepts_journal_read_response_shape(tmp_path: Path):
    mod = _load_script_module()
    payload = {
        "status": "ok",
        "data": {
            "entries": [
                {
                    "id": "j1",
                    "created_at": "2026-05-02T00:00:00Z",
                    "project": "ZenOS",
                    "flow_type": "capture",
                    "summary": "baseline scenario",
                    "tags": ["tokens:80"],
                }
            ]
        },
    }
    input_path = tmp_path / "journal.json"
    out_path = tmp_path / "baseline.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    result = mod.build_from_file(input_path, out_path)

    assert result["out_path"] == str(out_path)
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert saved["total_capture_sessions"] == 1
    assert saved["scenarios"][0]["entry_id"] == "j1"
