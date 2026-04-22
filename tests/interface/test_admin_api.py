"""Tests for Admin REST API and Agent Identity (ContextVar).

Tests cover:
  A. ContextVar injection in ApiKeyMiddleware
  B. task created_by auto-fill from ContextVar
  C. Admin API endpoint validation (mock firebase_admin.auth)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.action import Task
from zenos.domain.knowledge import Tags


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Fix login",
        status="todo",
        priority="high",
        created_by="architect",
        description="Login broken on iOS",
        assignee="developer",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


# ===========================================================================
# A. ContextVar unit tests
# ===========================================================================

class TestContextVar:
    """Tests for _current_partner ContextVar lifecycle."""

    def test_default_is_none(self):
        from zenos.interface.mcp import _current_partner
        assert _current_partner.get() is None

    def test_set_and_get(self):
        from zenos.interface.mcp import _current_partner
        partner = {"displayName": "Alice", "email": "alice@example.com"}
        token = _current_partner.set(partner)
        try:
            assert _current_partner.get() == partner
            assert _current_partner.get()["displayName"] == "Alice"
        finally:
            _current_partner.reset(token)

    def test_reset_restores_default(self):
        from zenos.interface.mcp import _current_partner
        partner = {"displayName": "Bob", "email": "bob@example.com"}
        token = _current_partner.set(partner)
        _current_partner.reset(token)
        assert _current_partner.get() is None

    def test_nested_set_and_reset(self):
        from zenos.interface.mcp import _current_partner
        p1 = {"displayName": "Alice", "email": "alice@example.com"}
        p2 = {"displayName": "Bob", "email": "bob@example.com"}

        token1 = _current_partner.set(p1)
        try:
            assert _current_partner.get()["displayName"] == "Alice"
            token2 = _current_partner.set(p2)
            try:
                assert _current_partner.get()["displayName"] == "Bob"
            finally:
                _current_partner.reset(token2)
            assert _current_partner.get()["displayName"] == "Alice"
        finally:
            _current_partner.reset(token1)
        assert _current_partner.get() is None


# ===========================================================================
# B. task created_by auto-fill from ContextVar
# ===========================================================================

class TestTaskCreatedByAutoFill:
    """Tests for task tool auto-filling created_by from partner identity."""

    async def test_created_by_auto_filled_from_partner(self):
        from zenos.interface.mcp import _task_handler, _current_partner
        from zenos.application.action.task_service import TaskResult

        t = _make_task(created_by="Alice")
        create_result = TaskResult(task=t, cascade_updates=[])

        token = _current_partner.set({"id": "p_alice", "displayName": "Alice", "email": "alice@test.com"})
        try:
            with patch("zenos.interface.mcp.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)
                mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

                result = await _task_handler(
                    action="create",
                    title="Test task",
                    # created_by intentionally omitted
                )

                # Should succeed (not return INVALID_INPUT error)
                assert "error" not in result
                # Verify create_task was called with auto-filled created_by
                call_data = mock_ts.create_task.call_args[0][0]
                assert call_data["created_by"] == "p_alice"
        finally:
            _current_partner.reset(token)

    async def test_created_by_overridden_by_partner_context(self):
        from zenos.interface.mcp import _task_handler, _current_partner
        from zenos.application.action.task_service import TaskResult

        t = _make_task(created_by="Barry")
        create_result = TaskResult(task=t, cascade_updates=[])

        token = _current_partner.set({"id": "p_alice", "displayName": "Alice", "email": "alice@test.com"})
        try:
            with patch("zenos.interface.mcp.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)
                mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

                result = await _task_handler(
                    action="create",
                    title="Test task",
                    created_by="Barry",  # explicitly provided
                )

                assert "error" not in result
                call_data = mock_ts.create_task.call_args[0][0]
                assert call_data["created_by"] == "p_alice"
        finally:
            _current_partner.reset(token)

    async def test_created_by_error_when_no_partner_and_not_provided(self):
        from zenos.interface.mcp import _task_handler, _current_partner

        # Ensure ContextVar is None
        assert _current_partner.get() is None

        result = await _task_handler(
            action="create",
            title="Test task",
            # created_by intentionally omitted, no partner context
        )

        assert result["status"] == "rejected"
        assert "created_by" in result["rejection_reason"]

    async def test_superadmin_auto_fill(self):
        from zenos.interface.mcp import _task_handler, _current_partner
        from zenos.application.action.task_service import TaskResult

        t = _make_task(created_by="superadmin")
        create_result = TaskResult(task=t, cascade_updates=[])

        token = _current_partner.set({"id": "p_admin", "displayName": "superadmin", "email": "admin"})
        try:
            with patch("zenos.interface.mcp.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)
                mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

                result = await _task_handler(
                    action="create",
                    title="Admin task",
                )

                assert "error" not in result
                call_data = mock_ts.create_task.call_args[0][0]
                assert call_data["created_by"] == "p_admin"
        finally:
            _current_partner.reset(token)


# ===========================================================================
# C. Admin API endpoint tests
# ===========================================================================

def _mock_request(
    method: str = "POST",
    path: str = "/",
    headers: dict | None = None,
    body: dict | None = None,
    path_params: dict | None = None,
) -> MagicMock:
    """Create a mock Starlette Request."""
    req = MagicMock()
    req.method = method
    req.url = MagicMock()
    req.url.path = path
    req.headers = headers or {}
    req.path_params = path_params or {}

    async def json_coro():
        return body or {}

    req.json = json_coro
    return req


def _firebase_token(email: str = "admin@test.com", name: str = "Admin") -> dict:
    """Create a fake decoded Firebase token."""
    return {"email": email, "name": name, "uid": "uid-123"}


class TestInvitePartner:
    """Tests for POST /api/partners/invite."""

    async def test_invite_success(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={
                "email": "new@test.com",
                "access_mode": "scoped",
                "authorized_entity_ids": ["e-1", "e-2"],
            },
        )

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch(
                 "zenos.interface.admin_api._get_caller_partner",
                 return_value=(
                     "p1",
                     {
                         "email": "admin@test.com",
                         "isAdmin": True,
                     },
                 ),
             ), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await invite_partner(request)

            assert resp.status_code == 201
            import json
            body = json.loads(resp.body)
            assert body["email"] == "new@test.com"
            assert body["status"] == "invited"
            assert body["apiKey"] == ""
            assert body["authorizedEntityIds"] == ["e-1", "e-2"]
            assert body["accessMode"] == "scoped"
            assert body["workspaceRole"] == "guest"
            assert body["sharedPartnerId"] == "p1"
            assert "inviteExpiresAt" in body

    async def test_invite_defaults_to_unassigned_and_clears_scope(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "new3@test.com", "authorized_entity_ids": ["e-1"]},
        )

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):
            resp = await invite_partner(request)

        assert resp.status_code == 201
        import json
        body = json.loads(resp.body)
        assert body["accessMode"] == "unassigned"
        assert body["workspaceRole"] == "member"
        assert body["authorizedEntityIds"] == []

    async def test_invite_rejects_bootstrap_sources_outside_authorized_scope(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={
                "email": "new4@test.com",
                "access_mode": "scoped",
                "authorized_entity_ids": ["product-1"],
                "home_workspace_bootstrap_entity_ids": ["product-2"],
            },
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})):
            resp = await invite_partner(request)

        assert resp.status_code == 400
        assert "subset of authorized_entity_ids" in resp.body.decode()

    async def test_invite_sets_expires_at_7_days(self):
        """New invite must have inviteExpiresAt set to approximately now + 7 days."""
        from zenos.interface.admin_api import invite_partner
        from datetime import timedelta

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "new2@test.com"},
        )

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            before = datetime.now(timezone.utc)
            resp = await invite_partner(request)
            after = datetime.now(timezone.utc)

            assert resp.status_code == 201
            import json
            body = json.loads(resp.body)
            expires_at_str = body["inviteExpiresAt"]
            assert expires_at_str is not None
            # Verify it's roughly 7 days from now
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            assert before + timedelta(days=6, hours=23) <= expires_at <= after + timedelta(days=7, seconds=5)

    async def test_invite_authorized_entity_ids_from_body_not_caller(self):
        """authorized_entity_ids must come from request body, not caller's own entity IDs."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={
                "email": "client@test.com",
                "access_mode": "scoped",
                "authorized_entity_ids": ["entity-x"],
            },
        )

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "authorizedEntityIds": ["caller-entity"]})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await invite_partner(request)

            assert resp.status_code == 201
            import json
            body = json.loads(resp.body)
            # Must use body's entity IDs, not caller's
            assert body["authorizedEntityIds"] == ["entity-x"]

    async def test_reinvite_same_invited_email_returns_200_and_updates_expiry(self):
        """Re-inviting an already-invited email resets expires_at and returns 200."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "pending@test.com"},
        )

        mock_repo = AsyncMock()
        mock_repo.update_fields = AsyncMock(return_value=None)

        existing_partner = {
            "email": "pending@test.com",
            "status": "invited",
            "authorizedEntityIds": [],
            "displayName": "pending@test.com",
        }

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p2", existing_partner)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await invite_partner(request)

            assert resp.status_code == 200
            mock_repo.update_fields.assert_called_once()
            call_args = mock_repo.update_fields.call_args
            assert call_args[0][0] == "p2"
            assert "inviteExpiresAt" in call_args[0][1]

    async def test_reinvite_updates_authorized_entity_ids_when_provided(self):
        """Re-invite with authorized_entity_ids updates them on the existing record."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={
                "email": "pending@test.com",
                "access_mode": "scoped",
                "authorized_entity_ids": ["new-entity"],
            },
        )

        mock_repo = AsyncMock()
        mock_repo.update_fields = AsyncMock(return_value=None)

        existing_partner = {
            "email": "pending@test.com",
            "status": "invited",
            "authorizedEntityIds": ["old-entity"],
            "displayName": "pending@test.com",
        }

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p2", existing_partner)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await invite_partner(request)

            assert resp.status_code == 200
            import json
            body = json.loads(resp.body)
            assert body["authorizedEntityIds"] == ["new-entity"]
            call_fields = mock_repo.update_fields.call_args[0][1]
            assert call_fields["authorizedEntityIds"] == ["new-entity"]

    async def test_invite_requires_admin(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "new@test.com"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "user@test.com", "isAdmin": False})):

            resp = await invite_partner(request)

            assert resp.status_code == 403

    async def test_invite_requires_auth(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(method="POST", body={"email": "new@test.com"})

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=None):
            resp = await invite_partner(request)

            assert resp.status_code == 401

    async def test_invite_active_email_returns_409(self):
        """Inviting an email that is already active returns 409."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "existing@test.com"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p2", {"email": "existing@test.com", "status": "active"})):

            resp = await invite_partner(request)

            assert resp.status_code == 409

    async def test_invite_suspended_email_returns_409(self):
        """Inviting a suspended email returns 409."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "suspended@test.com"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p3", {"email": "suspended@test.com", "status": "suspended"})):

            resp = await invite_partner(request)

            assert resp.status_code == 409

    async def test_invite_invalid_email(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "not-an-email"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})):

            resp = await invite_partner(request)

            assert resp.status_code == 400


class TestUpdatePartnerRole:
    """Tests for PUT /api/partners/{id}/role."""

    async def test_update_role_success_for_home_workspace_partner(self):
        from zenos.interface.admin_api import update_partner_role

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"isAdmin": True},
            path_params={"id": "partner-2"},
        )

        from datetime import datetime, timezone
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2", "email": "user@test.com", "displayName": "User",
            "isAdmin": False, "status": "active", "sharedPartnerId": None,
            "invitedBy": None, "createdAt": datetime(2026,1,1,tzinfo=timezone.utc),
            "updatedAt": datetime(2026,1,1,tzinfo=timezone.utc),
        })
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch(
                 "zenos.interface.admin_api._get_caller_partner",
                 return_value=("partner-2", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": None}),
             ), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await update_partner_role(request)

            assert resp.status_code == 200
            mock_repo.update_fields.assert_called_once()
            assert mock_repo.update_fields.call_args.args[1]["isAdmin"] is True
            assert "sharedPartnerId" not in mock_repo.update_fields.call_args.args[1]

    async def test_update_role_rejects_shared_workspace_partner(self):
        from zenos.interface.admin_api import update_partner_role

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"isAdmin": True},
            path_params={"id": "partner-2"},
        )

        from datetime import datetime, timezone
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2", "email": "user@test.com", "displayName": "User",
            "isAdmin": False, "status": "active", "sharedPartnerId": "p1",
            "invitedBy": None, "createdAt": datetime(2026,1,1,tzinfo=timezone.utc),
            "updatedAt": datetime(2026,1,1,tzinfo=timezone.utc),
        })
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await update_partner_role(request)

            assert resp.status_code == 409
            mock_repo.update_fields.assert_not_called()

    async def test_update_role_not_found(self):
        from zenos.interface.admin_api import update_partner_role

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"isAdmin": True},
            path_params={"id": "nonexistent"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await update_partner_role(request)

            assert resp.status_code == 404

    async def test_update_role_invalid_value(self):
        from zenos.interface.admin_api import update_partner_role

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"isAdmin": "yes"},  # not a boolean
            path_params={"id": "partner-2"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})):

            resp = await update_partner_role(request)

            assert resp.status_code == 400


class TestUpdatePartnerStatus:
    """Tests for PUT /api/partners/{id}/status."""

    async def test_update_status_success(self):
        from zenos.interface.admin_api import update_partner_status

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"status": "suspended"},
            path_params={"id": "partner-2"},
        )

        from datetime import datetime, timezone
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2", "email": "user@test.com", "displayName": "User",
            "isAdmin": False, "status": "active", "sharedPartnerId": "p1",
            "invitedBy": None, "createdAt": datetime(2026,1,1,tzinfo=timezone.utc),
            "updatedAt": datetime(2026,1,1,tzinfo=timezone.utc),
        })
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await update_partner_status(request)

            assert resp.status_code == 200
            mock_repo.update_fields.assert_called_once()

    async def test_cannot_suspend_self(self):
        from zenos.interface.admin_api import update_partner_status

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"status": "suspended"},
            path_params={"id": "p1"},  # same as caller
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})):

            resp = await update_partner_status(request)

            assert resp.status_code == 403

    async def test_invalid_status_value(self):
        from zenos.interface.admin_api import update_partner_status

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"status": "deleted"},  # invalid
            path_params={"id": "partner-2"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})):

            resp = await update_partner_status(request)

            assert resp.status_code == 400


class TestUpdatePartnerScope:
    """Tests for PUT /api/partners/{id}/scope."""

    async def test_update_scope_sets_explicit_access_mode(self):
        from zenos.interface.admin_api import update_partner_scope

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={
                "roles": ["finance"],
                "department": "finance",
                "workspace_role": "guest",
                "authorized_entity_ids": ["product-abc"],
            },
            path_params={"id": "partner-2"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2",
            "email": "user@test.com",
            "displayName": "User",
            "isAdmin": False,
            "status": "active",
            "accessMode": "internal",
            "sharedPartnerId": "p1",
            "authorizedEntityIds": [],
            "roles": [],
            "department": "all",
            "invitedBy": None,
            "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updatedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
        })
        mock_repo.create_department = AsyncMock(return_value=None)
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):
            resp = await update_partner_scope(request)

        assert resp.status_code == 200
        fields = mock_repo.update_fields.call_args[0][1]
        assert fields["accessMode"] == "scoped"
        assert fields["authorizedEntityIds"] == ["product-abc"]

    async def test_update_scope_clears_scope_for_unassigned(self):
        from zenos.interface.admin_api import update_partner_scope

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={
                "roles": [],
                "department": "all",
                "access_mode": "unassigned",
                "authorized_entity_ids": ["product-abc"],
            },
            path_params={"id": "partner-2"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2",
            "email": "user@test.com",
            "displayName": "User",
            "isAdmin": False,
            "status": "active",
            "accessMode": "scoped",
            "sharedPartnerId": "p1",
            "authorizedEntityIds": ["product-abc"],
            "roles": [],
            "department": "all",
            "invitedBy": None,
            "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updatedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
        })
        mock_repo.create_department = AsyncMock(return_value=None)
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):
            resp = await update_partner_scope(request)

        assert resp.status_code == 200
        fields = mock_repo.update_fields.call_args[0][1]
        assert fields["accessMode"] == "unassigned"
        assert fields["authorizedEntityIds"] == []

    async def test_update_scope_accepts_camel_case_authorized_entity_ids(self):
        from zenos.interface.admin_api import update_partner_scope

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={
                "roles": ["engineering"],
                "department": "all",
                "access_mode": "scoped",
                "authorizedEntityIds": ["product-1", "product-2"],
            },
            path_params={"id": "partner-2"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2",
            "email": "user@test.com",
            "displayName": "User",
            "isAdmin": False,
            "status": "active",
            "accessMode": "internal",
            "sharedPartnerId": "p1",
            "authorizedEntityIds": [],
            "roles": [],
            "department": "all",
            "invitedBy": None,
            "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updatedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
        })
        mock_repo.create_department = AsyncMock(return_value=None)
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):
            resp = await update_partner_scope(request)

        assert resp.status_code == 200
        fields = mock_repo.update_fields.call_args[0][1]
        assert fields["accessMode"] == "scoped"
        assert fields["authorizedEntityIds"] == ["product-1", "product-2"]

    async def test_update_scope_rejects_bootstrap_sources_outside_authorized_scope(self):
        from zenos.interface.admin_api import update_partner_scope

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={
                "roles": [],
                "department": "all",
                "access_mode": "scoped",
                "authorized_entity_ids": ["product-1"],
                "home_workspace_bootstrap_entity_ids": ["product-2"],
            },
            path_params={"id": "partner-2"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-2",
            "email": "user@test.com",
            "displayName": "User",
            "isAdmin": False,
            "status": "active",
            "accessMode": "internal",
            "sharedPartnerId": "p1",
            "authorizedEntityIds": [],
            "roles": [],
            "department": "all",
            "invitedBy": None,
            "createdAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updatedAt": datetime(2026, 1, 1, tzinfo=timezone.utc),
        })

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):
            resp = await update_partner_scope(request)

        assert resp.status_code == 400
        assert "subset of authorized_entity_ids" in resp.body.decode()


class TestActivatePartner:
    """Tests for POST /api/partners/activate."""

    async def test_activate_success(self):
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        mock_repo = AsyncMock()
        mock_repo.update_fields = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="new@test.com", name="New User")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p-new", {"email": "new@test.com", "status": "invited", "displayName": "new@test.com"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await activate_partner(request)

            assert resp.status_code == 200
            mock_repo.update_fields.assert_called_once()
            import json
            body = json.loads(resp.body)
            assert body["status"] == "active"
            assert len(body["apiKey"]) > 0  # UUID generated
            assert body["displayName"] == "New User"

    async def test_activate_already_active_is_idempotent(self):
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="user@test.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p1", {"email": "user@test.com", "status": "active", "apiKey": "existing-key"})):

            resp = await activate_partner(request)

            assert resp.status_code == 200  # idempotent

    async def test_activate_suspended_forbidden(self):
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="suspended@test.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p1", {"email": "suspended@test.com", "status": "suspended"})):

            resp = await activate_partner(request)

            assert resp.status_code == 403

    async def test_activate_no_partner_found(self):
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="unknown@test.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)):

            resp = await activate_partner(request)

            assert resp.status_code == 404

    async def test_activate_requires_auth(self):
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(method="POST")

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=None):
            resp = await activate_partner(request)

            assert resp.status_code == 401

    async def test_activate_expired_invite_returns_410(self):
        """Activating with an expired invite_expires_at returns 410."""
        from zenos.interface.admin_api import activate_partner
        from datetime import timedelta

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        expired_at = datetime.now(timezone.utc) - timedelta(days=1)
        partner_data = {
            "email": "expired@test.com",
            "status": "invited",
            "displayName": "expired@test.com",
            "inviteExpiresAt": expired_at,
        }

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="expired@test.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p-exp", partner_data)):

            resp = await activate_partner(request)

            assert resp.status_code == 410
            import json
            body = json.loads(resp.body)
            assert body["error"] == "INVITATION_EXPIRED"

    async def test_activate_valid_invite_not_expired(self):
        """Activating with a future invite_expires_at succeeds."""
        from zenos.interface.admin_api import activate_partner
        from datetime import timedelta

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        mock_repo = AsyncMock()
        mock_repo.update_fields = AsyncMock(return_value=None)

        future_expires = datetime.now(timezone.utc) + timedelta(days=6)
        partner_data = {
            "email": "valid@test.com",
            "status": "invited",
            "displayName": "valid@test.com",
            "inviteExpiresAt": future_expires,
        }

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="valid@test.com", name="Valid User")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p-valid", partner_data)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await activate_partner(request)

            assert resp.status_code == 200
            import json
            body = json.loads(resp.body)
            assert body["status"] == "active"

    async def test_activate_no_expires_at_succeeds(self):
        """Activating with no invite_expires_at (NULL) succeeds (internal members)."""
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        mock_repo = AsyncMock()
        mock_repo.update_fields = AsyncMock(return_value=None)

        partner_data = {
            "email": "internal@test.com",
            "status": "invited",
            "displayName": "internal@test.com",
            "inviteExpiresAt": None,
        }

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="internal@test.com", name="Internal")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p-int", partner_data)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await activate_partner(request)

            assert resp.status_code == 200


class TestDeletePartner:
    """Tests for DELETE /api/partners/{id}."""

    def _make_invited_row(self, partner_id: str = "partner-invited", email: str = "invited@test.com") -> MagicMock:
        from datetime import datetime, timezone
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "id": partner_id,
            "email": email,
            "status": "invited",
            "shared_partner_id": "p1",
            "is_admin": False,
        }[k]
        return mock_row

    async def test_delete_invited_success(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(
            method="DELETE",
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "partner-invited"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-invited", "email": "invited@test.com",
            "status": "invited", "sharedPartnerId": "p1", "isAdmin": False,
        })
        mock_repo.delete = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await delete_partner(request)

            assert resp.status_code == 204
            mock_repo.delete.assert_called_once_with("partner-invited")

    async def test_delete_requires_admin(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(
            method="DELETE",
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "partner-invited"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "user@test.com", "isAdmin": False})):

            resp = await delete_partner(request)

            assert resp.status_code == 403

    async def test_delete_active_partner_succeeds(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(
            method="DELETE",
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "partner-active"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-active", "email": "active@test.com",
            "status": "active", "sharedPartnerId": "p1", "isAdmin": False,
        })
        mock_repo.delete = AsyncMock()

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await delete_partner(request)

            # Active partners can now be deleted (CRM FK cleanup handles cascading)
            assert resp.status_code == 204
            mock_repo.delete.assert_awaited_once_with("partner-active")

    async def test_delete_self_forbidden(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(
            method="DELETE",
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "p1"},  # same as caller
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})):

            resp = await delete_partner(request)

            assert resp.status_code == 403

    async def test_delete_requires_auth(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(method="DELETE", path_params={"id": "partner-invited"})

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=None):
            resp = await delete_partner(request)

            assert resp.status_code == 401

    async def test_delete_not_found(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(
            method="DELETE",
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "nonexistent"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await delete_partner(request)

            assert resp.status_code == 404

    async def test_delete_suspended_partner_success(self):
        from zenos.interface.admin_api import delete_partner

        request = _mock_request(
            method="DELETE",
            headers={"authorization": "Bearer fake-token"},
            path_params={"id": "partner-suspended"},
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value={
            "id": "partner-suspended", "email": "suspended@test.com",
            "status": "suspended", "sharedPartnerId": "p1", "isAdmin": False,
        })
        mock_repo.delete = AsyncMock()

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await delete_partner(request)

            assert resp.status_code == 204
            mock_repo.delete.assert_called_once_with("partner-suspended")


class TestCorsHandling:
    """Tests for CORS preflight handling."""

    async def test_options_returns_204(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(method="OPTIONS")
        request.headers = {"origin": "https://zenos-naruvia.web.app"}

        resp = await invite_partner(request)

        assert resp.status_code == 204

    async def test_cors_headers_for_allowed_origin(self):
        from zenos.interface.admin_api import _cors_headers

        request = MagicMock()
        request.headers = {"origin": "https://zenos-naruvia.web.app"}

        headers = _cors_headers(request)

        assert headers["access-control-allow-origin"] == "https://zenos-naruvia.web.app"
        assert "PATCH" in headers["access-control-allow-methods"]
        assert "X-Active-Workspace-Id" in headers["access-control-allow-headers"]

    async def test_cors_headers_for_firebaseapp_origin(self):
        from zenos.interface.admin_api import _cors_headers

        request = MagicMock()
        request.headers = {"origin": "https://zenos-naruvia.firebaseapp.com"}

        headers = _cors_headers(request)

        assert headers["access-control-allow-origin"] == "https://zenos-naruvia.firebaseapp.com"

    async def test_no_cors_headers_for_unknown_origin(self):
        from zenos.interface.admin_api import _cors_headers

        request = MagicMock()
        request.headers = {"origin": "https://evil.com"}

        headers = _cors_headers(request)

        assert len(headers) == 0
