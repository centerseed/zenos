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
        doc_role="single",
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
