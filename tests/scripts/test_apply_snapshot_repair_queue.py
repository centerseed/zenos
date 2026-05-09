from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "dogfood" / "apply_snapshot_repair_queue.py"
    spec = importlib.util.spec_from_file_location("apply_snapshot_repair_queue", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_apply_snapshot_repair_queue_dry_run(tmp_path: Path):
    mod = _load_script_module()

    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "doc_id": "doc-1",
                        "title": "Spec A",
                        "repair_action": {"path": "/api/docs/doc-1/publish"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{"id": "doc-1", "partner_id": "partner-1"}])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_Acquire(conn))

    with patch.object(mod, "get_pool", new=AsyncMock(return_value=pool)):
        result = await mod.apply_snapshot_repair_queue(
            df_id="DF-20260502-apply",
            queue_json=queue_path,
            out_root=tmp_path,
            dry_run=True,
        )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert result["success_count"] == 1
    assert payload["results"][0]["status"] == "dry_run"
    assert payload["results"][0]["partner_id"] == "partner-1"


async def test_apply_snapshot_repair_queue_reports_source_forbidden(tmp_path: Path):
    mod = _load_script_module()

    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "doc_id": "doc-2",
                        "title": "Spec B",
                        "source_uri": "https://github.com/acme/repo/blob/main/docs/spec-b.md",
                        "repair_action": {"path": "/api/docs/doc-2/publish"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{"id": "doc-2", "partner_id": "partner-2"}])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_Acquire(conn))

    with (
        patch.object(mod, "get_pool", new=AsyncMock(return_value=pool)),
        patch.object(mod, "_publish_document_snapshot_internal", new=AsyncMock(side_effect=PermissionError())),
    ):
        result = await mod.apply_snapshot_repair_queue(
            df_id="DF-20260502-apply-fail",
            queue_json=queue_path,
            out_root=tmp_path,
            dry_run=False,
        )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert result["failed_count"] == 1
    assert payload["results"][0]["status"] == "failed"
    assert payload["results"][0]["error"] == "SOURCE_FORBIDDEN"


async def test_apply_snapshot_repair_queue_partner_override_skips_db_lookup(tmp_path: Path):
    mod = _load_script_module()

    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "doc_id": "doc-3",
                        "title": "Spec C",
                        "repair_action": {"path": "/api/docs/doc-3/publish"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with patch.object(mod, "_load_partner_ids", new=AsyncMock(side_effect=AssertionError("should not be called"))), \
         patch.object(mod, "_publish_document_snapshot_internal", new=AsyncMock(return_value={"revision_id": "rev-1"})):
        result = await mod.apply_snapshot_repair_queue(
            df_id="DF-20260502-apply-override",
            queue_json=queue_path,
            out_root=tmp_path,
            partner_id="workspace-1",
        )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert result["success_count"] == 1
    assert payload["results"][0]["partner_id"] == "workspace-1"
    assert payload["results"][0]["status"] == "ok"


async def test_apply_snapshot_repair_queue_records_alternative_uris_for_missing_source(tmp_path: Path):
    mod = _load_script_module()

    queue_path = tmp_path / "queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "queue": [
                    {
                        "doc_id": "doc-4",
                        "title": "Spec D",
                        "source_uri": "https://github.com/acme/repo/blob/main/docs/spec-d.md",
                        "repair_action": {"path": "/api/docs/doc-4/publish"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with (
        patch.object(mod, "_load_partner_ids", new=AsyncMock(return_value={"doc-4": "workspace-1"})),
        patch.object(mod, "_publish_document_snapshot_internal", new=AsyncMock(side_effect=FileNotFoundError())),
        patch.object(mod.GitHubAdapter, "search_alternatives_for_uri", new=AsyncMock(return_value=[
            "https://github.com/acme/repo/blob/main/specs/spec-d.md"
        ])),
    ):
        result = await mod.apply_snapshot_repair_queue(
            df_id="DF-20260502-apply-alt",
            queue_json=queue_path,
            out_root=tmp_path,
        )

    payload = json.loads(Path(result["out_path"]).read_text(encoding="utf-8"))
    assert result["failed_count"] == 1
    assert payload["results"][0]["error"] == "SOURCE_NOT_FOUND"
    assert payload["results"][0]["alternative_uris"] == [
        "https://github.com/acme/repo/blob/main/specs/spec-d.md"
    ]
