"""Tests for document delivery endpoints in dashboard_api.

Focused on ADR-032 Phase 1 backend behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from zenos.domain.knowledge import Entity, Tags


def _make_request(
    *,
    method: str = "GET",
    path_params: dict | None = None,
    body: dict | None = None,
) -> MagicMock:
    req = MagicMock()
    req.method = method
    req.headers = {}
    req.path_params = path_params or {}
    req.query_params = {}
    req.json = AsyncMock(return_value=body or {})
    return req


def _make_doc_entity(doc_id: str = "doc-1") -> Entity:
    now = datetime.now(timezone.utc)
    return Entity(
        id=doc_id,
        name="SPEC-demo",
        type="document",
        summary="demo",
        tags=Tags(what=["demo"], why="why", how="how", who=["team"]),
        sources=[{
            "source_id": "src-1",
            "uri": "https://github.com/acme/repo/blob/main/docs/SPEC-demo.md",
            "type": "github",
            "status": "valid",
            "source_status": "valid",
            "is_primary": True,
        }],
        visibility="public",
        created_at=now,
        updated_at=now,
        doc_role="index",
        bundle_highlights=[{
            "source_id": "src-1",
            "headline": "讀這份就能知道主流程",
            "reason_to_read": "它是 onboarding 的 SSOT",
            "priority": "primary",
        }],
        change_summary="新增 bundle-first 文件入口",
        highlights_updated_at=now,
        summary_updated_at=now,
    )


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_publish_document_snapshot_success():
    from zenos.interface.dashboard_api import publish_document_snapshot

    request = _make_request(method="POST", path_params={"docId": "doc-1"})
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}
    doc_entity = _make_doc_entity("doc-1")

    source_service_instance = MagicMock()
    source_service_instance.read_source = AsyncMock(return_value="# hello")

    with (
        patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._is_document_visible_for_partner", new=AsyncMock(return_value=True)),
        patch("zenos.interface.dashboard_api.SourceService", return_value=source_service_instance),
        patch("zenos.infrastructure.gcs_client.get_documents_bucket", return_value="docs-bucket"),
        patch("zenos.infrastructure.gcs_client.upload_blob", return_value=None),
        patch("zenos.interface.dashboard_api._create_revision_and_mark_ready", new=AsyncMock(return_value="rev-1")),
    ):
        mock_entity_repo.get_by_id = AsyncMock(return_value=doc_entity)
        resp = await publish_document_snapshot(request)

    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["revision_id"] == "rev-1"
    assert body["doc_id"] == "doc-1"
    assert body["delivery_status"] == "ready"


async def test_get_document_content_returns_404_when_no_revision():
    from zenos.interface.dashboard_api import get_document_content

    request = _make_request(path_params={"docId": "doc-1"})
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}
    doc_entity = _make_doc_entity("doc-1")

    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={
        "primary_snapshot_revision_id": None,
        "canonical_path": None,
        "delivery_status": None,
    })
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_Acquire(conn))

    with (
        patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._is_document_visible_for_partner", new=AsyncMock(return_value=True)),
        patch("zenos.interface.dashboard_api.get_pool", new=AsyncMock(return_value=pool)),
        patch("zenos.interface.dashboard_api._get_latest_revision", new=AsyncMock(return_value=None)),
    ):
        mock_entity_repo.get_by_id = AsyncMock(return_value=doc_entity)
        resp = await get_document_content(request)

    assert resp.status_code == 404
    body = json.loads(resp.body)
    assert body["error"] == "NOT_FOUND"


async def test_get_document_delivery_returns_bundle_metadata():
    from zenos.interface.dashboard_api import get_document_delivery

    request = _make_request(path_params={"docId": "doc-1"})
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}
    doc_entity = _make_doc_entity("doc-1")

    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={
        "canonical_path": "/docs/doc-1",
        "primary_snapshot_revision_id": "rev-1",
        "last_published_at": datetime.now(timezone.utc),
        "delivery_status": "ready",
    })
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_Acquire(conn))

    with (
        patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._is_document_visible_for_partner", new=AsyncMock(return_value=True)),
        patch("zenos.interface.dashboard_api.get_pool", new=AsyncMock(return_value=pool)),
        patch("zenos.interface.dashboard_api._get_latest_revision", new=AsyncMock(return_value={"id": "rev-1"})),
    ):
        mock_entity_repo.get_by_id = AsyncMock(return_value=doc_entity)
        resp = await get_document_delivery(request)

    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["document"]["doc_role"] == "index"
    assert body["document"]["bundle_highlights"][0]["priority"] == "primary"
    assert body["document"]["change_summary"] == "新增 bundle-first 文件入口"


async def test_access_document_share_link_success():
    from zenos.interface.dashboard_api import access_document_share_link

    request = _make_request(path_params={"token": "raw-token"})
    token_row = {
        "token_id": "tok-1",
        "partner_id": "p1",
        "doc_id": "doc-1",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "max_access_count": None,
        "used_count": 0,
        "revoked_at": None,
        "doc_name": "SPEC-demo",
        "primary_snapshot_revision_id": "rev-1",
    }
    revision = {
        "id": "rev-1",
        "snapshot_bucket": "docs-bucket",
        "snapshot_object_path": "docs/doc-1/revisions/rev-1.md",
    }

    with (
        patch("zenos.interface.dashboard_api._lookup_doc_for_share_token", new=AsyncMock(return_value=token_row)),
        patch("zenos.interface.dashboard_api._get_revision_by_id", new=AsyncMock(return_value=revision)),
        patch("zenos.infrastructure.gcs_client.download_blob", return_value=(b"# shared", "text/markdown")),
        patch("zenos.interface.dashboard_api._increment_share_token_usage", new=AsyncMock(return_value=None)),
    ):
        resp = await access_document_share_link(request)

    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["doc"]["id"] == "doc-1"
    assert body["revision_id"] == "rev-1"
    assert body["content"] == "# shared"


async def test_create_document_share_link_success():
    from zenos.interface.dashboard_api import create_document_share_link

    request = _make_request(
        method="POST",
        path_params={"docId": "doc-1"},
        body={"expires_in_hours": 2, "max_access_count": 10},
    )
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}
    doc_entity = _make_doc_entity("doc-1")

    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_Acquire(conn))

    with (
        patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._is_document_visible_for_partner", new=AsyncMock(return_value=True)),
        patch("zenos.interface.dashboard_api.get_pool", new=AsyncMock(return_value=pool)),
    ):
        mock_entity_repo.get_by_id = AsyncMock(return_value=doc_entity)
        resp = await create_document_share_link(request)

    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["doc_id"] == "doc-1"
    assert body["share_url"].startswith("/s?token=")
    assert body["max_access_count"] == 10


async def test_save_document_content_success():
    from zenos.interface.dashboard_api import save_document_content

    request = _make_request(
        method="POST",
        path_params={"docId": "doc-1"},
        body={
            "content": "# from agent\n\nhello",
            "source_version_ref": "manual-v1",
            "base_revision_id": "rev-1",
        },
    )
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}
    doc_entity = _make_doc_entity("doc-1")

    with (
        patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._is_document_visible_for_partner", new=AsyncMock(return_value=True)),
        patch("zenos.infrastructure.gcs_client.get_documents_bucket", return_value="docs-bucket"),
        patch("zenos.infrastructure.gcs_client.upload_blob", return_value=None),
        patch("zenos.interface.dashboard_api._create_revision_and_mark_ready", new=AsyncMock(return_value="rev-2")),
    ):
        mock_entity_repo.get_by_id = AsyncMock(return_value=doc_entity)
        resp = await save_document_content(request)

    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["doc_id"] == "doc-1"
    assert body["revision_id"] == "rev-2"
    assert body["source_version_ref"] == "manual-v1"


async def test_save_document_content_rejects_non_object_json_body():
    from zenos.interface.dashboard_api import save_document_content

    request = _make_request(
        method="POST",
        path_params={"docId": "doc-1"},
        body=[],
    )
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}

    with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))):
        resp = await save_document_content(request)

    assert resp.status_code == 400
    body = json.loads(resp.body)
    assert body["error"] == "INVALID_INPUT"


async def test_save_document_content_requires_base_revision_id():
    from zenos.interface.dashboard_api import save_document_content

    request = _make_request(
        method="POST",
        path_params={"docId": "doc-1"},
        body={"content": "# from agent\n\nhello"},
    )
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}

    with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))):
        resp = await save_document_content(request)

    assert resp.status_code == 400
    body = json.loads(resp.body)
    assert body["error"] == "INVALID_INPUT"
    assert "base_revision_id" in body["message"]


async def test_save_document_content_returns_revision_conflict():
    from zenos.interface.dashboard_api import RevisionConflictError, save_document_content

    request = _make_request(
        method="POST",
        path_params={"docId": "doc-1"},
        body={
            "content": "# from agent\n\nhello",
            "source_version_ref": "manual-v1",
            "base_revision_id": "rev-1",
        },
    )
    partner = {"id": "p1", "isAdmin": False, "sharedPartnerId": None}
    doc_entity = _make_doc_entity("doc-1")

    with (
        patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(partner, "p1"))),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._is_document_visible_for_partner", new=AsyncMock(return_value=True)),
        patch("zenos.infrastructure.gcs_client.get_documents_bucket", return_value="docs-bucket"),
        patch("zenos.infrastructure.gcs_client.upload_blob", return_value=None),
        patch(
            "zenos.interface.dashboard_api._create_revision_and_mark_ready",
            new=AsyncMock(
                side_effect=RevisionConflictError(
                    current_revision_id="rev-2",
                    canonical_path="/docs/doc-1",
                    last_published_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
                )
            ),
        ),
    ):
        mock_entity_repo.get_by_id = AsyncMock(return_value=doc_entity)
        resp = await save_document_content(request)

    assert resp.status_code == 409
    body = json.loads(resp.body)
    assert body["error"] == "REVISION_CONFLICT"
    assert body["current_revision_id"] == "rev-2"
    assert body["canonical_path"] == "/docs/doc-1"
