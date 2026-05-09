from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_governance_review_task_draft.py"
    )
    spec = importlib.util.spec_from_file_location("build_governance_review_task_draft", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_governance_review_task_drafts_from_source_queue(tmp_path: Path):
    mod = _load_script_module()

    queue_path = tmp_path / "source-repair-queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "doc_id": "doc-1",
                        "title": "Spec A",
                        "source_uri": "https://github.com/acme/repo/blob/main/docs/spec-a.md",
                        "alternative_uris": ["https://github.com/acme/repo/blob/main/specs/spec-a.md"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = mod.build_governance_review_task_drafts(
        df_id="DF-20260502-task-draft",
        source_repair_queue_json=queue_path,
        product_id="product-1",
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert result["draft_count"] == 1
    draft = payload["drafts"][0]
    assert draft["title"].startswith("檢查並修正 Spec A")
    assert draft["product_id"] == "product-1"
    assert draft["linked_entities"] == ["doc-1"]
    assert "SOURCE_NOT_FOUND" in draft["description"]
    assert len(draft["acceptance_criteria"]) == 3
