from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "build_source_repair_queue.py"
    spec = importlib.util.spec_from_file_location("build_source_repair_queue", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_source_repair_queue_filters_source_not_found(tmp_path: Path):
    mod = _load_script_module()

    results_path = tmp_path / "snapshot-repair-results.json"
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "doc_id": "doc-1",
                        "title": "Spec A",
                        "partner_id": "workspace-1",
                        "error": "SOURCE_NOT_FOUND",
                        "source_uri": "https://github.com/acme/repo/blob/main/docs/spec-a.md",
                        "alternative_uris": ["https://github.com/acme/repo/blob/main/specs/spec-a.md"],
                    },
                    {
                        "doc_id": "doc-2",
                        "title": "Spec B",
                        "partner_id": "workspace-1",
                        "error": "SOURCE_FORBIDDEN",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = mod.build_source_repair_queue(
        df_id="DF-20260502-source-queue",
        repair_results_json=results_path,
        out_root=tmp_path,
    )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert result["queue_count"] == 1
    assert payload["queue"][0]["doc_id"] == "doc-1"
    assert payload["queue"][0]["alternative_uris"] == ["https://github.com/acme/repo/blob/main/specs/spec-a.md"]
