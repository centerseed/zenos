"""Tests for Dashboard REST API endpoints.

Tests cover:
  A. GET /api/partner/me
  B. GET /api/data/entities
  C. GET /api/data/entities/{id}
  D. GET /api/data/tasks (with filters)
  E. 401 unauthorized (no token)

All Firebase token verification and SQL repository calls are mocked.
⚠️ mock tests — no real DB or Firebase connection.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.datastructures import QueryParams

from zenos.application.action.task_service import TaskResult
from zenos.domain.action import Plan, Task
from zenos.domain.knowledge import Blindspot, Entity, Relationship, Tags


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_request(
    method: str = "GET",
    headers: dict | None = None,
    path_params: dict | None = None,
    query_params: dict | None = None,
) -> MagicMock:
    req = MagicMock()
    req.method = method
    req.headers = headers or {}
    req.path_params = path_params or {}
    req.query_params = query_params or {}
    return req


def _firebase_token(email: str = "user@test.com") -> dict:
    return {"email": email, "uid": "uid-1", "name": "Test User"}


def _make_entity(eid: str = "e1") -> Entity:
    return Entity(
        id=eid,
        name="Test Entity",
        type="module",
        level=2,
        parent_id=None,
        status="active",
        summary="A test entity",
        tags=Tags(what=["x"], why="because", how="do it", who=["Alice"]),
        details=None,
        confirmed_by_user=False,
        owner="Alice",
        sources=[],
        visibility="public",
        last_reviewed_at=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_document(eid: str = "doc-1", parent_id: str = "e1", *, status: str = "approved", summary: str = "Doc summary") -> Entity:
    return Entity(
        id=eid,
        name=f"Document {eid}",
        type="document",
        level=3,
        parent_id=parent_id,
        status=status,
        summary=summary,
        tags=Tags(what=["spec"], why="", how="", who=[]),
        details={"doc_type": "SPEC"},
        confirmed_by_user=False,
        owner="Alice",
        sources=[],
        visibility="public",
        last_reviewed_at=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )


def _make_task(tid: str = "t1") -> Task:
    return Task(
        id=tid,
        title="Fix it",
        description="desc",
        status="todo",
        priority="high",
        created_by="Alice",
        assignee="Bob",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_plan(pid: str = "plan-1") -> Plan:
    return Plan(
        id=pid,
        goal="Ship Console",
        status="active",
        created_by="Alice",
        owner="Barry",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )


_PARTNER = {
    "id": "p1",
    "email": "user@test.com",
    "displayName": "Test User",
    "apiKey": "key-123",  # pragma: allowlist secret
    "authorizedEntityIds": [],
    "status": "active",
    "accessMode": "internal",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "invitedBy": None,
    "roles": ["marketing"],
    "department": "marketing",
}


# ---------------------------------------------------------------------------
# A. GET /api/partner/me
# ---------------------------------------------------------------------------

class TestGetPartnerMe:

    async def test_returns_partner_info(self):
        from zenos.interface.dashboard_api import get_partner_me

        request = _make_request(headers={"authorization": "Bearer fake-token"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER):
            resp = await get_partner_me(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["partner"]["id"] == "p1"
        assert body["partner"]["apiKey"] == "key-123"  # pragma: allowlist secret
        assert body["partner"]["email"] == "user@test.com"
        assert body["partner"]["accessMode"] == "internal"
        assert body["partner"]["workspaceRole"] == "member"
        # S01: isHomeWorkspace is included in the session context
        assert body["partner"]["isHomeWorkspace"] is True  # sharedPartnerId is None

    async def test_defaults_to_home_workspace_for_shared_partner_without_header(self):
        """Without an active-workspace header, login falls back to home workspace."""
        from zenos.interface.dashboard_api import get_partner_me

        shared_partner = {
            **_PARTNER,
            "sharedPartnerId": "owner-partner-id",
            "workspaceRole": "guest",
            "accessMode": "scoped",
            "isAdmin": False,
            "authorizedEntityIds": ["l1-entity-1"],
        }
        request = _make_request(headers={"authorization": "Bearer fake-token"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=shared_partner), \
             patch("zenos.interface.dashboard_api._partner_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)):
            mock_repo.get_by_id = AsyncMock(return_value={
                "id": "owner-partner-id",
                "email": "owner@test.com",
                "displayName": "Barry",
            })
            resp = await get_partner_me(request)

        import json
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["partner"]["isHomeWorkspace"] is True
        assert body["partner"]["workspaceRole"] == "owner"

    async def test_returns_is_home_workspace_false_for_shared_partner_when_header_requests_shared(self):
        from zenos.interface.dashboard_api import get_partner_me

        shared_partner = {
            **_PARTNER,
            "id": "guest-home-id",
            "sharedPartnerId": "owner-partner-id",
            "workspaceRole": "guest",
            "accessMode": "scoped",
            "isAdmin": False,
            "authorizedEntityIds": ["l1-entity-1"],
        }
        request = _make_request(
            headers={
                "authorization": "Bearer fake-token",
                "x-active-workspace-id": "owner-partner-id",
            }
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=shared_partner), \
             patch("zenos.interface.dashboard_api._partner_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)):
            mock_repo.get_by_id = AsyncMock(return_value={
                "id": "owner-partner-id",
                "email": "owner@test.com",
                "displayName": "Barry",
            })
            resp = await get_partner_me(request)

        import json
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["partner"]["isHomeWorkspace"] is False
        assert body["partner"]["workspaceRole"] == "guest"

    async def test_returns_available_workspaces_and_honors_active_workspace_header(self):
        from zenos.interface.dashboard_api import get_partner_me

        shared_partner = {
            **_PARTNER,
            "id": "guest-home-id",
            "email": "guest@test.com",
            "displayName": "Guest User",
            "sharedPartnerId": "owner-partner-id",
            "workspaceRole": "guest",
            "accessMode": "scoped",
            "isAdmin": False,
            "authorizedEntityIds": ["l1-entity-1"],
        }
        request = _make_request(
            headers={
                "authorization": "Bearer fake-token",
                "x-active-workspace-id": "owner-partner-id",
            }
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token(email="guest@test.com")), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=shared_partner), \
             patch("zenos.interface.dashboard_api._partner_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)):
            mock_repo.get_by_id = AsyncMock(return_value={
                "id": "owner-partner-id",
                "email": "owner@test.com",
                "displayName": "Barry",
            })
            resp = await get_partner_me(request)

        import json
        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["partner"]["activeWorkspaceId"] == "owner-partner-id"
        assert body["partner"]["isHomeWorkspace"] is False
        assert body["partner"]["availableWorkspaces"] == [
            {"id": "guest-home-id", "name": "我的工作區", "hasUpdate": False},
            {"id": "owner-partner-id", "name": "Barry 的工作區", "hasUpdate": False},
        ]

    async def test_returns_401_without_token(self):
        from zenos.interface.dashboard_api import get_partner_me

        request = _make_request()

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await get_partner_me(request)

        assert resp.status_code == 401

    async def test_returns_404_when_partner_not_found(self):
        from zenos.interface.dashboard_api import get_partner_me

        request = _make_request(headers={"authorization": "Bearer fake-token"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=None):
            resp = await get_partner_me(request)

        assert resp.status_code == 404

    async def test_options_returns_204(self):
        from zenos.interface.dashboard_api import get_partner_me

        request = _make_request(method="OPTIONS")
        request.headers = {"origin": "https://zenos-naruvia.web.app"}
        resp = await get_partner_me(request)
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# B. GET /api/data/entities
# ---------------------------------------------------------------------------

class TestListEntities:

    async def test_returns_entities_list(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake-token"})
        entity = _make_entity("e1")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[entity])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await list_entities(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert len(body["entities"]) == 1
        assert body["entities"][0]["id"] == "e1"
        assert body["entities"][0]["name"] == "Test Entity"
        assert "confirmedByUser" in body["entities"][0]
        assert "parentId" in body["entities"][0]

    async def test_passes_type_filter(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params={"type": "product"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            await list_entities(request)

        mock_repo.list_all.assert_called_once_with(type_filter="product")

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request()

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await list_entities(request)

        assert resp.status_code == 401

    async def test_hides_confidential_entity_from_member(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake-token"})
        hidden = _make_entity("e-hidden")
        hidden.visibility = "confidential"

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[hidden])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await list_entities(request)

        import json
        body = json.loads(resp.body)
        assert body["entities"] == []


# ---------------------------------------------------------------------------
# C. GET /api/data/entities/{id}
# ---------------------------------------------------------------------------

class TestGetEntity:

    async def test_returns_entity_when_found(self):
        from zenos.interface.dashboard_api import get_entity

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "e1"},
        )
        entity = _make_entity("e1")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api._relationship_repo") as mock_rel_repo, \
             patch("zenos.interface.dashboard_api.OntologyService") as mock_ontology_service, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.get_by_id = AsyncMock(return_value=entity)
            mock_rel_repo.list_by_entity = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()
            mock_service = MagicMock()
            mock_service.compute_impact_chain = AsyncMock(side_effect=[[{"to_id": "e2"}], [{"from_id": "root"}]])
            mock_ontology_service.return_value = mock_service

            resp = await get_entity(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["entity"]["id"] == "e1"
        assert body["impact_chain"] == [{"to_id": "e2"}]
        assert body["reverse_impact_chain"] == [{"from_id": "root"}]

    async def test_returns_404_for_confidential_entity_without_membership(self):
        from zenos.interface.dashboard_api import get_entity

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "secret-1"},
        )
        confidential = _make_entity("secret-1")
        confidential.visibility = "confidential"
        confidential.visible_to_members = ["p-admin"]

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.get_by_id = AsyncMock(return_value=confidential)
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await get_entity(request)

        assert resp.status_code == 404

    async def test_returns_404_when_not_found(self):
        from zenos.interface.dashboard_api import get_entity

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "missing"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await get_entity(request)

        assert resp.status_code == 404

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import get_entity

        request = _make_request(path_params={"id": "e1"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await get_entity(request)

        assert resp.status_code == 401


class TestGetCoworkGraphContext:

    async def test_returns_l2_neighbors_and_documents(self):
        from zenos.interface.dashboard_api import get_cowork_graph_context

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params={"seed_id": "prod-1", "budget_tokens": "1500"},
        )
        seed = _make_entity("prod-1")
        seed.type = "product"
        seed.level = 1
        seed.name = "Paceriz"
        child = _make_entity("module-1")
        child.parent_id = "prod-1"
        child.updated_at = datetime(2026, 1, 4, tzinfo=timezone.utc)
        doc = _make_document("spec-1", parent_id="module-1", summary="A" * 620)

        with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(_PARTNER, "p1"))), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)), \
             patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(side_effect=[seed])), \
             patch("zenos.interface.dashboard_api._list_children_with_context", new=AsyncMock(side_effect=[[child], [doc]])), \
             patch("zenos.interface.dashboard_api._list_relationships_with_context", new=AsyncMock(return_value=[])):
            resp = await get_cowork_graph_context(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["seed"]["id"] == "prod-1"
        assert body["fallback_mode"] == "l1_tags_only"
        assert len(body["neighbors"]) == 1
        assert body["neighbors"][0]["id"] == "module-1"
        assert len(body["neighbors"][0]["documents"]) == 1
        assert body["neighbors"][0]["documents"][0]["doc_id"] == "spec-1"
        assert len(body["neighbors"][0]["documents"][0]["summary"]) <= 500
        assert body["estimated_tokens"] > 0

    async def test_marks_partial_when_document_lookup_fails(self):
        from zenos.interface.dashboard_api import get_cowork_graph_context

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params={"seed_id": "prod-1"},
        )
        seed = _make_entity("prod-1")
        seed.type = "product"
        seed.level = 1
        children = [_make_entity("module-1"), _make_entity("module-2")]
        children[0].parent_id = "prod-1"
        children[1].parent_id = "prod-1"

        async def list_children(_effective_id, entity_id):
            if entity_id == "prod-1":
                return children
            raise RuntimeError("timeout")

        with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(_PARTNER, "p1"))), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)), \
             patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(return_value=seed)), \
             patch("zenos.interface.dashboard_api._list_children_with_context", new=AsyncMock(side_effect=list_children)), \
             patch("zenos.interface.dashboard_api._list_relationships_with_context", new=AsyncMock(return_value=[])):
            resp = await get_cowork_graph_context(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["partial"] is True
        assert body["errors"]
        assert len(body["neighbors"]) == 1

    async def test_truncates_large_payload(self):
        from zenos.interface.dashboard_api import get_cowork_graph_context

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params={"seed_id": "prod-1", "budget_tokens": "40"},
        )
        seed = _make_entity("prod-1")
        seed.type = "product"
        seed.level = 1
        children = []
        docs_by_parent: dict[str, list[Entity]] = {}
        for index in range(3):
            child = _make_entity(f"module-{index}")
            child.parent_id = "prod-1"
            child.summary = "module summary " * 20
            children.append(child)
            docs_by_parent[child.id] = [
                _make_document(f"doc-{index}-a", parent_id=child.id, summary="doc summary " * 50),
                _make_document(f"doc-{index}-b", parent_id=child.id, summary="doc summary " * 50),
            ]

        async def list_children(_effective_id, entity_id):
            if entity_id == "prod-1":
                return children
            return docs_by_parent.get(entity_id, [])

        with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(_PARTNER, "p1"))), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)), \
             patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(return_value=seed)), \
             patch("zenos.interface.dashboard_api._list_children_with_context", new=AsyncMock(side_effect=list_children)), \
             patch("zenos.interface.dashboard_api._list_relationships_with_context", new=AsyncMock(return_value=[])):
            resp = await get_cowork_graph_context(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["truncated"] is True
        assert body["truncation_details"]["dropped_l2"] >= 0
        assert body["truncation_details"]["dropped_l3"] >= 0
        assert body["estimated_tokens"] <= 40


# ---------------------------------------------------------------------------
# D. GET /api/data/tasks
# ---------------------------------------------------------------------------

class TestListTasks:

    async def test_returns_tasks_list(self):
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(headers={"authorization": "Bearer fake-token"})
        task = _make_task("t1")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[task])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await list_tasks(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert len(body["tasks"]) == 1
        assert body["tasks"][0]["id"] == "t1"
        assert body["tasks"][0]["title"] == "Fix it"
        assert "createdBy" in body["tasks"][0]
        assert "linkedEntities" in body["tasks"][0]

    async def test_passes_status_filter(self):
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params={"status": "todo,in_progress"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            await list_tasks(request)

        call_kwargs = mock_repo.list_all.call_args[1]
        assert call_kwargs["status"] == ["todo", "in_progress"]

    async def test_passes_assignee_filter(self):
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params={"assignee": "Bob"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            await list_tasks(request)

        call_kwargs = mock_repo.list_all.call_args[1]
        assert call_kwargs["assignee"] == "Bob"

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request()

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await list_tasks(request)

        assert resp.status_code == 401

    async def test_defaults_to_home_workspace_scoping_without_header(self):
        """Without an active-workspace header, data queries scope to home workspace."""
        from zenos.interface.dashboard_api import list_tasks

        partner_with_shared = {**_PARTNER, "sharedPartnerId": "parent-p1"}
        request = _make_request(headers={"authorization": "Bearer fake-token"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=partner_with_shared), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            await list_tasks(request)

        mock_ctx.set.assert_called_once_with("p1")

    async def test_uses_shared_partner_id_for_scoping_when_header_requests_shared(self):
        """When the shared workspace is selected, data queries scope to sharedPartnerId."""
        from zenos.interface.dashboard_api import list_tasks

        partner_with_shared = {**_PARTNER, "sharedPartnerId": "parent-p1"}
        request = _make_request(
            headers={
                "authorization": "Bearer fake-token",
                "x-active-workspace-id": "parent-p1",
            }
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=partner_with_shared), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_repo.list_all = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            await list_tasks(request)

        mock_ctx.set.assert_called_once_with("parent-p1")


# ---------------------------------------------------------------------------
# E. JSON serialization — camelCase keys and datetime ISO format
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_entity_to_dict_camel_case(self):
        from zenos.interface.dashboard_api import _entity_to_dict

        entity = _make_entity("e1")
        result = _entity_to_dict(entity)

        assert "confirmedByUser" in result
        assert "parentId" in result
        assert "lastReviewedAt" in result
        assert "createdAt" in result
        assert "updatedAt" in result
        assert "confirmed_by_user" not in result

    def test_task_to_dict_camel_case(self):
        from zenos.interface.dashboard_api import _task_to_dict

        task = _make_task("t1")
        result = _task_to_dict(task)

        assert "createdBy" in result
        assert "linkedEntities" in result
        assert "priorityReason" in result
        assert "assigneeRoleId" in result
        assert "created_by" not in result

    def test_relationship_to_dict_camel_case(self):
        from zenos.interface.dashboard_api import _relationship_to_dict

        rel = Relationship(
            id="r1",
            source_entity_id="e1",
            target_id="e2",
            type="impacts",
            description="A impacts B",
            confirmed_by_user=True,
        )
        result = _relationship_to_dict(rel)

        assert "sourceEntityId" in result
        assert "targetId" in result
        assert "confirmedByUser" in result
        assert "source_entity_id" not in result

    def test_blindspot_to_dict_camel_case(self):
        from zenos.interface.dashboard_api import _blindspot_to_dict

        bs = Blindspot(
            id="b1",
            description="A blindspot",
            severity="red",
            related_entity_ids=["e1"],
            suggested_action="Do something",
            status="open",
            confirmed_by_user=False,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        result = _blindspot_to_dict(bs)

        assert "relatedEntityIds" in result
        assert "suggestedAction" in result
        assert "confirmedByUser" in result
        assert "createdAt" in result
        assert "related_entity_ids" not in result


# ---------------------------------------------------------------------------
# F. POST /api/data/tasks — create task
# ---------------------------------------------------------------------------

def _make_task_result(tid: str = "t-new") -> TaskResult:
    return TaskResult(task=_make_task(tid), cascade_updates=[])


class TestCreateTask:

    async def test_creates_task_with_title(self):
        from zenos.interface.dashboard_api import create_task

        request = _make_request(method="POST", headers={"authorization": "Bearer fake-token"})
        request.json = AsyncMock(return_value={"title": "New task"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.create_task = AsyncMock(return_value=_make_task_result("t-new"))
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await create_task(request)

        assert resp.status_code == 201
        import json
        body = json.loads(resp.body)
        assert body["task"]["id"] == "t-new"

    async def test_requires_title(self):
        from zenos.interface.dashboard_api import create_task

        request = _make_request(method="POST", headers={"authorization": "Bearer fake-token"})
        request.json = AsyncMock(return_value={"description": "No title"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER):
            resp = await create_task(request)

        assert resp.status_code == 400
        import json
        body = json.loads(resp.body)
        assert "title" in body["message"].lower()

    async def test_passes_partner_id_as_created_by(self):
        from zenos.interface.dashboard_api import create_task

        request = _make_request(method="POST", headers={"authorization": "Bearer fake-token"})
        request.json = AsyncMock(return_value={"title": "Task from p1"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.create_task = AsyncMock(return_value=_make_task_result())
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            await create_task(request)

        call_data = mock_svc.create_task.call_args[0][0]
        assert call_data["created_by"] == "p1"

    async def test_returns_400_on_service_value_error(self):
        from zenos.interface.dashboard_api import create_task

        request = _make_request(method="POST", headers={"authorization": "Bearer fake-token"})
        request.json = AsyncMock(return_value={"title": "Bad priority", "priority": "ultra"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.create_task = AsyncMock(side_effect=ValueError("Invalid priority 'ultra'"))
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await create_task(request)

        assert resp.status_code == 400

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import create_task

        request = _make_request(method="POST")
        request.json = AsyncMock(return_value={"title": "x"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await create_task(request)

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# G. PATCH /api/data/tasks/{taskId} — update task
# ---------------------------------------------------------------------------


class TestUpdateTask:

    async def test_updates_task_fields(self):
        from zenos.interface.dashboard_api import update_task

        request = _make_request(
            method="PATCH",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"priority": "high", "assignee": "Alice"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.update_task = AsyncMock(return_value=_make_task_result("t1"))
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await update_task(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["task"]["id"] == "t1"

    async def test_returns_404_when_task_not_found(self):
        from zenos.interface.dashboard_api import update_task

        request = _make_request(
            method="PATCH",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "missing"},
        )
        request.json = AsyncMock(return_value={"priority": "low"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.update_task = AsyncMock(side_effect=ValueError("Task 'missing' not found"))
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await update_task(request)

        assert resp.status_code == 404

    async def test_returns_400_on_invalid_transition(self):
        from zenos.interface.dashboard_api import update_task

        request = _make_request(
            method="PATCH",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"status": "done"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.update_task = AsyncMock(side_effect=ValueError("Cannot set status to 'done' via update"))
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await update_task(request)

        assert resp.status_code == 400

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import update_task

        request = _make_request(method="PATCH", path_params={"taskId": "t1"})
        request.json = AsyncMock(return_value={})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await update_task(request)

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# H. POST /api/data/tasks/{taskId}/confirm — approve/reject task
# ---------------------------------------------------------------------------


class TestConfirmTask:

    async def test_approve_task(self):
        from zenos.interface.dashboard_api import confirm_task

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"action": "approve"})

        done_task = _make_task("t1")
        done_task.status = "done"

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.confirm_task = AsyncMock(return_value=TaskResult(task=done_task, cascade_updates=[]))
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await confirm_task(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["task"]["id"] == "t1"
        mock_svc.confirm_task.assert_called_once_with(
            "t1", accepted=True, rejection_reason=None, updated_by="p1"
        )

    async def test_reject_task_without_reason_succeeds(self):
        """Spec R6: rejection_reason is optional."""
        from zenos.interface.dashboard_api import confirm_task

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"action": "reject"})

        in_progress_task = _make_task("t1")
        in_progress_task.status = "in_progress"

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.confirm_task = AsyncMock(
                return_value=TaskResult(task=in_progress_task, cascade_updates=[])
            )
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await confirm_task(request)

        assert resp.status_code == 200
        mock_svc.confirm_task.assert_called_once_with(
            "t1", accepted=False, rejection_reason=None, updated_by="p1"
        )

    async def test_reject_task_with_reason(self):
        from zenos.interface.dashboard_api import confirm_task

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"action": "reject", "rejection_reason": "Not ready"})

        in_progress_task = _make_task("t1")
        in_progress_task.status = "in_progress"

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.confirm_task = AsyncMock(
                return_value=TaskResult(task=in_progress_task, cascade_updates=[])
            )
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await confirm_task(request)

        assert resp.status_code == 200
        mock_svc.confirm_task.assert_called_once_with(
            "t1", accepted=False, rejection_reason="Not ready", updated_by="p1"
        )

    async def test_invalid_action_returns_400(self):
        from zenos.interface.dashboard_api import confirm_task

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"action": "maybe"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER):
            resp = await confirm_task(request)

        assert resp.status_code == 400

    async def test_task_not_in_review_returns_400(self):
        from zenos.interface.dashboard_api import confirm_task

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            path_params={"taskId": "t1"},
        )
        request.json = AsyncMock(return_value={"action": "approve"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos"), \
             patch("zenos.interface.dashboard_api._make_task_service") as mock_svc_factory, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_svc = MagicMock()
            mock_svc.confirm_task = AsyncMock(
                side_effect=ValueError("Can only confirm tasks in 'review' status. Current status: 'todo'")
            )
            mock_svc_factory.return_value = mock_svc
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await confirm_task(request)

        assert resp.status_code == 400

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import confirm_task

        request = _make_request(method="POST", path_params={"taskId": "t1"})
        request.json = AsyncMock(return_value={"action": "approve"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await confirm_task(request)

        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# F. GET /api/data/governance-health
# ---------------------------------------------------------------------------

class TestGetGovernanceHealth:

    async def test_returns_cached_health_when_fresh(self):
        """Cache hit < 24h returns directly without recomputation."""
        from zenos.interface.dashboard_api import get_governance_health

        request = _make_request(headers={"authorization": "Bearer fake-token"})
        fresh_time = datetime(2026, 4, 9, 10, 0, 0, tzinfo=timezone.utc)

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api.get_pool", new=AsyncMock(return_value=MagicMock())), \
             patch("zenos.interface.dashboard_api.get_cached_health", new=AsyncMock(return_value={
                 "overall_level": "yellow",
                 "computed_at": fresh_time,
             })), \
             patch("zenos.interface.dashboard_api.datetime") as mock_dt:
            mock_dt.now.return_value = fresh_time  # same time = 0 age
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            resp = await get_governance_health(request)

        import json as _json
        body = _json.loads(resp.body)
        assert resp.status_code == 200
        assert body["overall_level"] == "yellow"
        assert body["stale"] is False

    async def test_returns_green_on_no_cache_and_compute_failure(self):
        """No cache + compute failure = safe degradation to green."""
        from zenos.interface.dashboard_api import get_governance_health

        request = _make_request(headers={"authorization": "Bearer fake-token"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api.get_pool", new=AsyncMock(return_value=MagicMock())), \
             patch("zenos.interface.dashboard_api.get_cached_health", new=AsyncMock(return_value=None)), \
             patch("zenos.interface.dashboard_api.GovernanceService") as mock_gs_cls:
            mock_gs = MagicMock()
            mock_gs.compute_health_signal = AsyncMock(side_effect=RuntimeError("DB down"))
            mock_gs_cls.return_value = mock_gs
            resp = await get_governance_health(request)

        import json as _json
        body = _json.loads(resp.body)
        assert resp.status_code == 200
        assert body["overall_level"] == "green"
        assert body["stale"] is True
        assert body["cached_at"] is None

    async def test_recomputes_when_cache_stale(self):
        """Cache older than 24h triggers recomputation."""
        from zenos.interface.dashboard_api import get_governance_health

        request = _make_request(headers={"authorization": "Bearer fake-token"})
        old_time = datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)

        mock_pool = MagicMock()

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api.get_pool", new=AsyncMock(return_value=mock_pool)), \
             patch("zenos.interface.dashboard_api.get_cached_health", new=AsyncMock(return_value={
                 "overall_level": "green",
                 "computed_at": old_time,
             })), \
             patch("zenos.interface.dashboard_api.upsert_health_cache", new=AsyncMock()) as mock_upsert, \
             patch("zenos.interface.dashboard_api.GovernanceService") as mock_gs_cls, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_gs = MagicMock()
            mock_gs.compute_health_signal = AsyncMock(return_value={
                "overall_level": "red",
                "kpis": {},
            })
            mock_gs_cls.return_value = mock_gs
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()
            resp = await get_governance_health(request)

        import json as _json
        body = _json.loads(resp.body)
        assert resp.status_code == 200
        assert body["overall_level"] == "red"
        assert body["stale"] is False

    async def test_returns_401_without_auth(self):
        from zenos.interface.dashboard_api import get_governance_health

        request = _make_request()
        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value=None):
            resp = await get_governance_health(request)

        assert resp.status_code == 401


class TestGetProjectProgress:

    async def test_returns_project_progress_aggregate_contract(self):
        from zenos.interface.dashboard_api import get_project_progress

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "proj-1"},
        )
        project = _make_entity("proj-1")
        project.type = "product"
        project.name = "Project Console"
        milestone = _make_entity("goal-1")
        milestone.type = "goal"
        milestone.level = 3
        milestone.name = "Milestone Alpha"
        plan = _make_plan("plan-1")
        plan.goal = "Ship S01 aggregate"

        blocked_task = _make_task("task-1")
        blocked_task.title = "Unblock backend aggregate"
        blocked_task.status = "blocked"
        blocked_task.plan_id = "plan-1"
        blocked_task.linked_entities = ["proj-1", "goal-1"]
        blocked_task.blocked_by = ["dep-1"]
        blocked_task.blocked_reason = "Waiting on shared schema"
        blocked_task.updated_at = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
        blocked_task.plan_order = 2

        review_task = _make_task("task-2")
        review_task.title = "Review API contract"
        review_task.status = "review"
        review_task.plan_id = "plan-1"
        review_task.linked_entities = ["proj-1", "goal-1"]
        review_task.updated_at = datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)
        review_task.plan_order = 3

        parent_task = _make_task("task-3")
        parent_task.title = "Finish client contract"
        parent_task.status = "todo"
        parent_task.plan_id = "plan-1"
        parent_task.linked_entities = ["proj-1", "goal-1"]
        parent_task.due_date = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        parent_task.updated_at = datetime(2026, 4, 18, 8, 0, tzinfo=timezone.utc)
        parent_task.plan_order = 1

        subtask = _make_task("task-4")
        subtask.title = "Write TS types"
        subtask.status = "in_progress"
        subtask.plan_id = "plan-1"
        subtask.parent_task_id = "task-3"
        subtask.linked_entities = ["proj-1", "goal-1"]
        subtask.updated_at = datetime(2026, 4, 21, 8, 0, tzinfo=timezone.utc)
        subtask.plan_order = 4

        async def list_all_side_effect(**kwargs):
            if kwargs.get("linked_entity") == "proj-1":
                return [blocked_task, review_task, parent_task, subtask]
            if kwargs.get("plan_id") == "plan-1":
                return [blocked_task, review_task, parent_task, subtask]
            return []

        async def get_entity_side_effect(_effective_id: str, entity_id: str):
            if entity_id == "proj-1":
                return project
            if entity_id == "goal-1":
                return milestone
            return None

        with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(_PARTNER, "p1"))), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)), \
             patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(side_effect=get_entity_side_effect)), \
             patch("zenos.interface.dashboard_api._is_task_visible_for_partner", new=AsyncMock(return_value=True)), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._plan_repo") as mock_plan_repo, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_task_repo.list_all = AsyncMock(side_effect=list_all_side_effect)
            mock_plan_repo.get_by_id = AsyncMock(return_value=plan)
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await get_project_progress(request)

        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["project"]["id"] == "proj-1"
        assert body["active_plans"][0]["id"] == "plan-1"
        assert body["active_plans"][0]["goal"] == "Ship S01 aggregate"
        assert body["active_plans"][0]["open_count"] == 4
        assert body["active_plans"][0]["blocked_count"] == 1
        assert body["active_plans"][0]["review_count"] == 1
        assert body["active_plans"][0]["overdue_count"] == 1
        assert [task["id"] for task in body["active_plans"][0]["next_tasks"]] == ["task-3", "task-1", "task-2"]
        assert body["active_plans"][0]["next_tasks"][0]["plan_order"] == 1

        assert body["open_work_groups"][0]["plan_id"] == "plan-1"
        assert body["open_work_groups"][0]["plan_goal"] == "Ship S01 aggregate"
        assert [task["id"] for task in body["open_work_groups"][0]["tasks"]] == ["task-3", "task-1", "task-2"]
        assert body["open_work_groups"][0]["tasks"][0]["subtasks"][0]["id"] == "task-4"
        assert body["open_work_groups"][0]["tasks"][0]["subtasks"][0]["plan_order"] == 4

        assert body["milestones"] == [
            {"id": "goal-1", "name": "Milestone Alpha", "open_count": 4}
        ]
        assert body["recent_progress"][0]["id"] == "task-4"
        assert any(item["kind"] == "plan" and item["id"] == "plan-1" for item in body["recent_progress"])


class TestListPlans:

    async def test_returns_requested_plan_details_for_known_ids(self):
        from zenos.interface.dashboard_api import list_plans

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            query_params=QueryParams("id=plan-1&id=plan-1&id=plan-2"),
        )

        async def get_plan_side_effect(plan_id: str):
            if plan_id == "plan-1":
                return {"id": "plan-1", "goal": "Ship aggregate", "status": "active"}
            raise ValueError("not found")

        with patch("zenos.interface.dashboard_api._auth_and_scope", new=AsyncMock(return_value=(_PARTNER, "p1"))), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)), \
             patch("zenos.interface.dashboard_api.PlanService") as mock_plan_service_cls, \
             patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx:
            mock_plan_service = MagicMock()
            mock_plan_service.get_plan = AsyncMock(side_effect=get_plan_side_effect)
            mock_plan_service_cls.return_value = mock_plan_service
            mock_ctx.set = MagicMock(return_value="token")
            mock_ctx.reset = MagicMock()

            resp = await list_plans(request)

        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["plans"] == [{"id": "plan-1", "goal": "Ship aggregate", "status": "active"}]
        assert mock_plan_service.get_plan.await_args_list[0].args == ("plan-1",)
        assert len(mock_plan_service.get_plan.await_args_list) == 2
