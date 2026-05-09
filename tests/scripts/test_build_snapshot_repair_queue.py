from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_snapshot_repair_queue.py"
    spec = importlib.util.spec_from_file_location("build_snapshot_repair_queue", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_snapshot_repair_queue_filters_supported_issue_types(tmp_path: Path):
    mod = _load_script_module()

    invalid_documents_path = tmp_path / "invalid_documents.json"
    invalid_documents_path.write_text(
        json.dumps(
            {
                "data": {
                    "invalid_documents": {
                        "bundle_issues": [
                            {
                                "issue_type": "current_formal_entry_missing_delivery_snapshot",
                                "entity_id": "doc-1",
                                "title": "Spec A",
                                "severity": "red",
                                "linked_entity_ids": ["module-1"],
                                "source_uri": "https://github.com/acme/repo/blob/main/docs/spec-a.md",
                                "suspected_root_cause": "source_uri_drift",
                                "alternative_uris": ["https://github.com/acme/repo/blob/main/specs/spec-a.md"],
                                "suggested_action": "publish snapshot",
                            },
                            {
                                "issue_type": "current_formal_entry_stale_delivery_snapshot",
                                "entity_id": "doc-2",
                                "title": "Spec B",
                                "severity": "yellow",
                                "linked_entity_ids": ["module-2"],
                                "suggested_action": "republish snapshot",
                            },
                            {
                                "issue_type": "index_missing_bundle_highlights",
                                "entity_id": "doc-3",
                                "title": "Ignore Me",
                            },
                        ]
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = mod.build_snapshot_repair_queue(
        df_id="DF-20260502-queue",
        invalid_documents_json=invalid_documents_path,
        out_root=tmp_path,
    )

    out_path = Path(result["out_path"])
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert result["queue_count"] == 2
    assert payload["queue"][0]["doc_id"] == "doc-1"
    assert payload["queue"][0]["source_uri"] == "https://github.com/acme/repo/blob/main/docs/spec-a.md"
    assert payload["queue"][0]["suspected_root_cause"] == "source_uri_drift"
    assert payload["queue"][0]["alternative_uris"] == ["https://github.com/acme/repo/blob/main/specs/spec-a.md"]
    assert payload["queue"][0]["repair_action"]["path"] == "/api/docs/doc-1/publish"
    assert payload["queue"][0]["priority"] == "high"
    assert payload["queue"][1]["priority"] == "medium"


def test_build_snapshot_repair_queue_accepts_raw_invalid_documents_payload(tmp_path: Path):
    mod = _load_script_module()

    invalid_documents_path = tmp_path / "invalid_documents-raw.json"
    invalid_documents_path.write_text(
        json.dumps(
            {
                "bundle_issues": [
                    {
                        "issue_type": "current_formal_entry_missing_delivery_snapshot",
                        "entity_id": "doc-9",
                        "title": "Spec Z",
                        "severity": "red",
                        "linked_entity_ids": [],
                        "suggested_action": "publish snapshot",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = mod.build_snapshot_repair_queue(
        df_id="DF-20260502-queue-raw",
        invalid_documents_json=invalid_documents_path,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert payload["queue_count"] == 1
    assert payload["queue"][0]["doc_id"] == "doc-9"
