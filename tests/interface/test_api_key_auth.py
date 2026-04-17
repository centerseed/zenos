"""ST-1 security tests: API key authentication boundary.

Verifies that ApiKeyMiddleware correctly rejects all invalid/missing
API key scenarios with HTTP 401 before any tool logic is reached.

Strategy: mock _partner_validator.validate (the actual validator is the
boundary; we control what keys are "valid"). ApiKeyMiddleware itself
is NOT mocked — it is the subject under test.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from zenos.interface.mcp import ApiKeyMiddleware
from zenos.interface.mcp._auth import _current_partner


# ---------------------------------------------------------------------------
# Helper: build a minimal ASGI app wrapped by ApiKeyMiddleware
# ---------------------------------------------------------------------------

ACTIVE_PARTNER = {
    "id": "p-active",
    "email": "active@test.com",
    "displayName": "Active User",
    "apiKey": "valid-key-abc123",  # pragma: allowlist secret
    "status": "active",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}


def _make_test_app() -> Starlette:
    """Build a Starlette app with ApiKeyMiddleware guarding a /ping route."""

    async def ping(request):
        partner = _current_partner.get() or {}
        return JSONResponse({"ok": True, "defaultProject": partner.get("defaultProject")})

    inner = Starlette(routes=[Route("/ping", ping)])
    return ApiKeyMiddleware(inner)


# Partner cache used by validate mock: only "valid-key-abc123" resolves
async def _mock_validate(key: str) -> dict | None:
    return ACTIVE_PARTNER if key == ACTIVE_PARTNER["apiKey"] else None  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient for the middleware-wrapped app with mocked validator."""
    app = _make_test_app()
    with patch("zenos.interface.mcp._auth._partner_validator") as mock_validator:
        mock_validator.validate = AsyncMock(side_effect=_mock_validate)
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


class TestApiKeyAuth:
    """ST-1: invalid / missing credentials must always get 401."""

    def test_no_auth_header_returns_401(self, client):
        """No auth at all → 401."""
        resp = client.get("/ping")
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
        assert "UNAUTHORIZED" in body["error"]

    def test_bearer_nonexistent_key_returns_401(self, client):
        """Bearer header with a key that is not in the system → 401."""
        resp = client.get("/ping", headers={"Authorization": "Bearer totally-unknown-key"})
        assert resp.status_code == 401

    def test_x_api_key_nonexistent_key_returns_401(self, client):
        """X-Api-Key header with an unknown key → 401."""
        resp = client.get("/ping", headers={"X-Api-Key": "does-not-exist"})
        assert resp.status_code == 401

    def test_suspended_partner_key_returns_401(self, client):
        """A key belonging to a suspended partner is not in the active cache → 401.

        SqlPartnerKeyValidator only caches status='active' rows.
        A suspended partner's key is absent from cache, so validate() returns None.
        """
        # "suspended-key" is not in active cache (validate returns None)
        resp = client.get("/ping", headers={"X-Api-Key": "suspended-key-xyz"})
        assert resp.status_code == 401

    def test_inactive_partner_key_returns_401(self, client):
        """A key belonging to an inactive partner → 401 (not in active cache)."""
        resp = client.get("/ping", headers={"Authorization": "Bearer inactive-partner-key"})
        assert resp.status_code == 401

    def test_valid_key_passes_through(self, client):
        """Positive: a valid active key should NOT get 401."""
        resp = client.get("/ping", headers={"Authorization": f"Bearer {ACTIVE_PARTNER['apiKey']}"})
        # Should reach the inner app (200 OK)
        assert resp.status_code == 200

    def test_query_project_overrides_default_project_for_request(self, client):
        """project query param should become request-local defaultProject."""
        resp = client.get(
            "/ping?project=  Paceriz  ",
            headers={"Authorization": f"Bearer {ACTIVE_PARTNER['apiKey']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["defaultProject"] == "paceriz"

    def test_response_body_does_not_leak_internals(self, client):
        """401 response must not contain stack trace or internal details."""
        resp = client.get("/ping", headers={"Authorization": "Bearer bad-key"})
        assert resp.status_code == 401
        text = resp.text
        assert "Traceback" not in text
        assert "Exception" not in text
        assert "sql" not in text.lower()
