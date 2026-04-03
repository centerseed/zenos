"""Tests for GET /api/audit-events endpoint.

Verifies auth enforcement (401/403) and happy-path response shape.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_request(
    method: str = "GET",
    headers: dict | None = None,
    query_params: dict | None = None,
) -> MagicMock:
    req = MagicMock()
    req.method = method
    req.headers = headers or {}
    req.query_params = query_params or {}
    return req


def _firebase_token(email: str = "admin@test.com") -> dict:
    return {"email": email, "uid": "uid-1"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListAuditEventsAuth:
    """Auth enforcement for GET /api/audit-events."""

    async def test_no_token_returns_401(self):
        from zenos.interface.admin_api import list_audit_events

        request = _mock_request(headers={})

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=None):
            resp = await list_audit_events(request)

        assert resp.status_code == 401

    async def test_non_admin_returns_403(self):
        from zenos.interface.admin_api import list_audit_events

        request = _mock_request(headers={"authorization": "Bearer token"})

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner",
                   return_value=("p1", {"email": "user@test.com", "isAdmin": False})):
            resp = await list_audit_events(request)

        assert resp.status_code == 403

    async def test_partner_not_found_returns_403(self):
        from zenos.interface.admin_api import list_audit_events

        request = _mock_request(headers={"authorization": "Bearer token"})

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=(None, None)):
            resp = await list_audit_events(request)

        assert resp.status_code == 403

    async def test_options_returns_204(self):
        from zenos.interface.admin_api import list_audit_events

        request = _mock_request(method="OPTIONS")

        resp = await list_audit_events(request)

        assert resp.status_code == 204


class TestListAuditEventsHappyPath:
    """Happy path: Admin caller gets events list."""

    async def test_returns_events_list(self):
        from zenos.interface.admin_api import list_audit_events

        fake_events = [
            {
                "event_id": "uuid-1",
                "partner_id": "tenant-1",
                "actor_id": "partner-1",
                "actor_type": "partner",
                "operation": "task.create",
                "resource_type": "tasks",
                "resource_id": "task-abc",
                "changes_json": {},
                "timestamp": "2026-04-01T00:00:00+00:00",
            }
        ]
        mock_audit_repo = AsyncMock()
        mock_audit_repo.list_events = AsyncMock(return_value=fake_events)

        request = _mock_request(
            headers={"authorization": "Bearer token"},
            query_params={},
        )

        mock_pool = AsyncMock()

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner",
                   return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.infrastructure.sql_repo.get_pool", AsyncMock(return_value=mock_pool)), \
             patch("zenos.infrastructure.sql_repo.SqlAuditEventRepository", return_value=mock_audit_repo):
            resp = await list_audit_events(request)

        assert resp.status_code == 200
        body = resp.body
        import json
        data = json.loads(body)
        assert "events" in data
        assert len(data["events"]) == 1
        assert data["events"][0]["operation"] == "task.create"

    async def test_query_params_forwarded_to_repo(self):
        """since, until, operation, actor_id query params are forwarded."""
        from zenos.interface.admin_api import list_audit_events

        mock_audit_repo = AsyncMock()
        mock_audit_repo.list_events = AsyncMock(return_value=[])

        request = _mock_request(
            headers={"authorization": "Bearer token"},
            query_params={
                "operation": "task.create",
                "actor_id": "actor-42",
                "limit": "50",
            },
        )

        mock_pool = AsyncMock()

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner",
                   return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.infrastructure.sql_repo.get_pool", AsyncMock(return_value=mock_pool)), \
             patch("zenos.infrastructure.sql_repo.SqlAuditEventRepository", return_value=mock_audit_repo):
            resp = await list_audit_events(request)

        assert resp.status_code == 200
        call_kwargs = mock_audit_repo.list_events.call_args
        assert call_kwargs.kwargs["operation"] == "task.create"
        assert call_kwargs.kwargs["actor_id"] == "actor-42"
        assert call_kwargs.kwargs["limit"] == 50


class TestListAuditEventsImport:
    """Verify SqlAuditEventRepository is importable from admin_api context."""

    async def test_sql_audit_event_repository_importable(self):
        from zenos.infrastructure.sql_repo import SqlAuditEventRepository
        assert SqlAuditEventRepository is not None
