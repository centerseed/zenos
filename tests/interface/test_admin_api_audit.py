"""Audit log tests for Admin REST API.

Verifies that each partner management endpoint emits a structured audit log
via logger.info("audit", extra={...}) after a successful operation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers (duplicated from test_admin_api.py to keep tests self-contained)
# ---------------------------------------------------------------------------

def _mock_request(
    method: str = "POST",
    headers: dict | None = None,
    body: dict | None = None,
    path_params: dict | None = None,
) -> MagicMock:
    """Create a minimal mock Starlette Request."""
    req = MagicMock()
    req.method = method
    req.headers = headers or {}
    req.path_params = path_params or {}

    async def json_coro():
        return body or {}

    req.json = json_coro
    return req


def _firebase_token(email: str = "admin@test.com", name: str = "Admin") -> dict:
    return {"email": email, "name": name, "uid": "uid-123"}


def _assert_audit_log(mock_logger_info, *, action: str, result: str = "success") -> dict:
    """Assert logger.info was called with 'audit' and return the extra dict."""
    audit_calls = [c for c in mock_logger_info.call_args_list if c.args and c.args[0] == "audit"]
    assert audit_calls, f"Expected audit log for action={action!r} but logger.info('audit', ...) was never called"
    extra = audit_calls[-1].kwargs.get("extra", {})
    assert extra.get("action") == action, f"Expected action={action!r}, got {extra.get('action')!r}"
    assert extra.get("result") == result, f"Expected result={result!r}, got {extra.get('result')!r}"
    return extra


# ===========================================================================
# Audit log tests
# ===========================================================================

class TestInvitePartnerAudit:
    """Audit log: POST /api/partners/invite"""

    async def test_audit_log_emitted_on_success(self):
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "new@test.com"},
        )

        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await invite_partner(request)

            assert resp.status_code == 201
            extra = _assert_audit_log(mock_logger.info, action="partner_invite")
            assert extra["caller_email"] == "admin@test.com"
            assert extra["target_email"] == "new@test.com"
            assert "apiKey" not in extra["detail"]

    async def test_no_audit_log_on_duplicate_email(self):
        """Audit log must NOT be emitted on error paths."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "existing@test.com"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p2", {"email": "existing@test.com", "status": "active"})), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await invite_partner(request)

            assert resp.status_code == 409
            audit_calls = [c for c in mock_logger.info.call_args_list if c.args and c.args[0] == "audit"]
            assert not audit_calls, "Audit log must not be emitted on error"


class TestActivatePartnerAudit:
    """Audit log: POST /api/partners/activate"""

    async def test_audit_log_emitted_on_success(self):
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="new@test.com", name="New User")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p-new", {"email": "new@test.com", "status": "invited"})), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await activate_partner(request)

            assert resp.status_code == 200
            extra = _assert_audit_log(mock_logger.info, action="partner_activate")
            assert extra["caller_email"] == "new@test.com"
            assert extra["target_email"] == "new@test.com"
            assert extra["target_partner_id"] == "p-new"
            assert extra["detail"] == "status=active"

    async def test_no_audit_log_on_suspended_partner(self):
        """Audit log must NOT be emitted when activation is forbidden."""
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="suspended@test.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p1", {"email": "suspended@test.com", "status": "suspended"})), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await activate_partner(request)

            assert resp.status_code == 403
            audit_calls = [c for c in mock_logger.info.call_args_list if c.args and c.args[0] == "audit"]
            assert not audit_calls, "Audit log must not be emitted on error"


class TestUpdatePartnerRoleAudit:
    """Audit log: PUT /api/partners/{id}/role"""

    async def test_audit_log_emitted_on_success(self):
        from zenos.interface.admin_api import update_partner_role
        from datetime import datetime, timezone

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"isAdmin": True},
            path_params={"id": "partner-2"},
        )

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "id": "partner-2", "email": "user@test.com", "display_name": "User",
            "is_admin": False, "status": "active", "shared_partner_id": "p1",
            "invited_by": None, "created_at": datetime(2026,1,1,tzinfo=timezone.utc),
            "updated_at": datetime(2026,1,1,tzinfo=timezone.utc),
        }[k]
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await update_partner_role(request)

            assert resp.status_code == 200
            extra = _assert_audit_log(mock_logger.info, action="partner_role_change")
            assert extra["caller_email"] == "admin@test.com"
            assert extra["target_email"] == "user@test.com"
            assert extra["target_partner_id"] == "partner-2"
            assert extra["detail"] == "is_admin=True"

    async def test_no_audit_log_when_partner_not_found(self):
        from zenos.interface.admin_api import update_partner_role

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"isAdmin": True},
            path_params={"id": "nonexistent"},
        )

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await update_partner_role(request)

            assert resp.status_code == 404
            audit_calls = [c for c in mock_logger.info.call_args_list if c.args and c.args[0] == "audit"]
            assert not audit_calls, "Audit log must not be emitted on error"


class TestUpdatePartnerStatusAudit:
    """Audit log: PUT /api/partners/{id}/status"""

    async def test_audit_log_emitted_on_success(self):
        from zenos.interface.admin_api import update_partner_status
        from datetime import datetime, timezone

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"status": "suspended"},
            path_params={"id": "partner-2"},
        )

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "id": "partner-2", "email": "user@test.com", "display_name": "User",
            "is_admin": False, "status": "active", "shared_partner_id": "p1",
            "invited_by": None, "created_at": datetime(2026,1,1,tzinfo=timezone.utc),
            "updated_at": datetime(2026,1,1,tzinfo=timezone.utc),
        }[k]
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await update_partner_status(request)

            assert resp.status_code == 200
            extra = _assert_audit_log(mock_logger.info, action="partner_status_change")
            assert extra["caller_email"] == "admin@test.com"
            assert extra["target_email"] == "user@test.com"
            assert extra["target_partner_id"] == "partner-2"
            assert extra["detail"] == "status=suspended"

    async def test_no_audit_log_when_partner_not_found(self):
        from zenos.interface.admin_api import update_partner_status

        request = _mock_request(
            method="PUT",
            headers={"authorization": "Bearer fake-token"},
            body={"status": "active"},
            path_params={"id": "nonexistent"},
        )

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p1", {"email": "admin@test.com", "isAdmin": True})), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            resp = await update_partner_status(request)

            assert resp.status_code == 404
            audit_calls = [c for c in mock_logger.info.call_args_list if c.args and c.args[0] == "audit"]
            assert not audit_calls, "Audit log must not be emitted on error"


class TestAuditLogNoPii:
    """Ensure audit log detail never contains API key."""

    async def test_activate_detail_has_no_api_key(self):
        """The apiKey UUID generated during activation must not appear in audit detail."""
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        class _ACM:
            async def __aenter__(self): return mock_conn
            async def __aexit__(self, *a): pass

        mock_pool.acquire = MagicMock(return_value=_ACM())

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="user@test.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p1", {"email": "user@test.com", "status": "invited"})), \
             patch("zenos.infrastructure.sql_repo.get_pool", new_callable=AsyncMock, return_value=mock_pool), \
             patch("zenos.interface.admin_api.logger") as mock_logger:

            await activate_partner(request)

            audit_calls = [c for c in mock_logger.info.call_args_list if c.args and c.args[0] == "audit"]
            assert audit_calls
            extra = audit_calls[0].kwargs.get("extra", {})
            # detail must not contain any UUID-like string (the api_key)
            assert "apiKey" not in str(extra)
            assert len(extra.get("detail", "")) < 50  # "status=active" is short
