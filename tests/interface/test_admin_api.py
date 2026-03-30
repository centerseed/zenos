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

from zenos.domain.models import Tags, Task


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
        from zenos.interface.tools import _current_partner
        assert _current_partner.get() is None

    def test_set_and_get(self):
        from zenos.interface.tools import _current_partner
        partner = {"displayName": "Alice", "email": "alice@example.com"}
        token = _current_partner.set(partner)
        try:
            assert _current_partner.get() == partner
            assert _current_partner.get()["displayName"] == "Alice"
        finally:
            _current_partner.reset(token)

    def test_reset_restores_default(self):
        from zenos.interface.tools import _current_partner
        partner = {"displayName": "Bob", "email": "bob@example.com"}
        token = _current_partner.set(partner)
        _current_partner.reset(token)
        assert _current_partner.get() is None

    def test_nested_set_and_reset(self):
        from zenos.interface.tools import _current_partner
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
        from zenos.interface.tools import _task_handler, _current_partner
        from zenos.application.task_service import TaskResult

        t = _make_task(created_by="Alice")
        create_result = TaskResult(task=t, cascade_updates=[])

        token = _current_partner.set({"displayName": "Alice", "email": "alice@test.com"})
        try:
            with patch("zenos.interface.tools.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)

                result = await _task_handler(
                    action="create",
                    title="Test task",
                    # created_by intentionally omitted
                )

                # Should succeed (not return INVALID_INPUT error)
                assert "error" not in result
                # Verify create_task was called with auto-filled created_by
                call_data = mock_ts.create_task.call_args[0][0]
                assert call_data["created_by"] == "Alice"
        finally:
            _current_partner.reset(token)

    async def test_created_by_not_overridden_when_provided(self):
        from zenos.interface.tools import _task_handler, _current_partner
        from zenos.application.task_service import TaskResult

        t = _make_task(created_by="Barry")
        create_result = TaskResult(task=t, cascade_updates=[])

        token = _current_partner.set({"displayName": "Alice", "email": "alice@test.com"})
        try:
            with patch("zenos.interface.tools.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)

                result = await _task_handler(
                    action="create",
                    title="Test task",
                    created_by="Barry",  # explicitly provided
                )

                assert "error" not in result
                call_data = mock_ts.create_task.call_args[0][0]
                assert call_data["created_by"] == "Barry"
        finally:
            _current_partner.reset(token)

    async def test_created_by_error_when_no_partner_and_not_provided(self):
        from zenos.interface.tools import _task_handler, _current_partner

        # Ensure ContextVar is None
        assert _current_partner.get() is None

        result = await _task_handler(
            action="create",
            title="Test task",
            # created_by intentionally omitted, no partner context
        )

        assert result["error"] == "INVALID_INPUT"
        assert "created_by" in result["message"]

    async def test_superadmin_auto_fill(self):
        from zenos.interface.tools import _task_handler, _current_partner
        from zenos.application.task_service import TaskResult

        t = _make_task(created_by="superadmin")
        create_result = TaskResult(task=t, cascade_updates=[])

        token = _current_partner.set({"displayName": "superadmin", "email": "admin"})
        try:
            with patch("zenos.interface.tools.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)

                result = await _task_handler(
                    action="create",
                    title="Admin task",
                )

                assert "error" not in result
                call_data = mock_ts.create_task.call_args[0][0]
                assert call_data["created_by"] == "superadmin"
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
            body={"email": "new@test.com"},
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
                         "authorizedEntityIds": ["e-1", "e-2"],
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
            assert body["sharedPartnerId"] == "p1"

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

    async def test_invite_duplicate_email(self):
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

    async def test_update_role_success(self):
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

            assert resp.status_code == 200
            mock_repo.update_fields.assert_called_once()

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

    async def test_delete_active_partner_forbidden(self):
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

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await delete_partner(request)

            assert resp.status_code == 403
            import json
            body = json.loads(resp.body)
            assert "invited" in body["message"]

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

    async def test_delete_suspended_partner_forbidden(self):
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

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True, "sharedPartnerId": "p1"})), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await delete_partner(request)

            assert resp.status_code == 403


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
