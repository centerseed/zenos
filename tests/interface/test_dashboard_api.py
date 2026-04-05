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

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.application.task_service import TaskResult
from zenos.domain.models import Blindspot, Entity, Relationship, Tags, Task


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


_PARTNER = {
    "id": "p1",
    "email": "user@test.com",
    "displayName": "Test User",
    "apiKey": "key-123",  # pragma: allowlist secret
    "authorizedEntityIds": [],
    "status": "active",
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

    async def test_hides_role_restricted_entity_without_matching_role(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake-token"})
        hidden = _make_entity("e-hidden")
        hidden.visibility = "role-restricted"
        hidden.visible_to_roles = ["engineering"]

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

    async def test_uses_shared_partner_id_for_scoping(self):
        """When partner has sharedPartnerId, that ID is used for data scoping."""
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

        # The ContextVar should be set with the sharedPartnerId
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
