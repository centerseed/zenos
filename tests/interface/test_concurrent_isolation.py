"""ST-2 security tests: concurrent request ContextVar isolation.

Verifies that when Partner A and Partner B send requests simultaneously,
each request sees only its own ContextVar values and the vars are correctly
reset even when an exception occurs (try-finally path).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zenos.infrastructure.context import (
    current_partner_id,
    current_partner_department,
    current_partner_roles,
    current_partner_is_admin,
    current_partner_authorized_entity_ids,
)
from zenos.interface.tools import ApiKeyMiddleware

# ---------------------------------------------------------------------------
# Test partners
# ---------------------------------------------------------------------------

PARTNER_A = {
    "id": "p-tenant-a",
    "email": "a@tenanta.com",
    "displayName": "Partner A",
    "apiKey": "key-tenant-a",  # pragma: allowlist secret
    "status": "active",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": ["editor"],
    "department": "engineering",
    "authorizedEntityIds": ["ent-a1", "ent-a2"],
}

PARTNER_B = {
    "id": "p-tenant-b",
    "email": "b@tenantb.com",
    "displayName": "Partner B",
    "apiKey": "key-tenant-b",  # pragma: allowlist secret
    "status": "active",
    "isAdmin": True,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": ["admin"],
    "department": "finance",
    "authorizedEntityIds": ["ent-b1"],
}

KEY_MAP = {
    PARTNER_A["apiKey"]: PARTNER_A,
    PARTNER_B["apiKey"]: PARTNER_B,
}


async def _mock_validate(key: str) -> dict | None:
    return KEY_MAP.get(key)


# ---------------------------------------------------------------------------
# Helper ASGI app that captures ContextVar values mid-request
# ---------------------------------------------------------------------------

def _make_capturing_app(capture_list: list[dict]):
    """Inner ASGI app that records current ContextVar state into capture_list."""

    async def inner(scope, receive, send):
        if scope["type"] != "http":
            return
        capture_list.append({
            "partner_id": current_partner_id.get(),
            "department": current_partner_department.get(),
            "roles": list(current_partner_roles.get()),
            "is_admin": current_partner_is_admin.get(),
            "authorized_entity_ids": list(current_partner_authorized_entity_ids.get()),
        })
        # Send a minimal HTTP response
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": b"{}", "more_body": False})

    return inner


def _build_scope(key: str, path: str = "/ping") -> dict:
    """Build a minimal HTTP scope with the given API key as Bearer."""
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [(b"authorization", f"Bearer {key}".encode())],
    }


async def _fake_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _dispatch(middleware: ApiKeyMiddleware, scope: dict, captures: list[dict]):
    """Send one request through the middleware and collect captures."""
    responses: list[dict] = []

    async def send(event):
        responses.append(event)

    await middleware(scope, _fake_receive, send)
    return responses


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConcurrentContextVarIsolation:
    """ST-2: ContextVar values must not bleed between concurrent requests."""

    async def test_concurrent_partners_see_own_context(self):
        """Partner A and B fire concurrently; each sees its own partner_id / department."""
        captures: list[dict] = []
        inner = _make_capturing_app(captures)
        middleware = ApiKeyMiddleware(inner)

        with patch("zenos.interface.tools._partner_validator") as mock_validator:
            mock_validator.validate = AsyncMock(side_effect=_mock_validate)

            scope_a = _build_scope(PARTNER_A["apiKey"])
            scope_b = _build_scope(PARTNER_B["apiKey"])

            await asyncio.gather(
                _dispatch(middleware, scope_a, captures),
                _dispatch(middleware, scope_b, captures),
            )

        assert len(captures) == 2, "Both requests should reach the inner app"

        ids = {c["partner_id"] for c in captures}
        assert "p-tenant-a" in ids
        assert "p-tenant-b" in ids

        for capture in captures:
            if capture["partner_id"] == "p-tenant-a":
                assert capture["department"] == "engineering"
                assert capture["roles"] == ["editor"]
                assert capture["is_admin"] is False
                assert "ent-a1" in capture["authorized_entity_ids"]
            elif capture["partner_id"] == "p-tenant-b":
                assert capture["department"] == "finance"
                assert capture["roles"] == ["admin"]
                assert capture["is_admin"] is True
                assert "ent-b1" in capture["authorized_entity_ids"]

    async def test_context_vars_reset_after_request(self):
        """After a successful request, ContextVars must return to their defaults."""
        captures: list[dict] = []
        inner = _make_capturing_app(captures)
        middleware = ApiKeyMiddleware(inner)

        with patch("zenos.interface.tools._partner_validator") as mock_validator:
            mock_validator.validate = AsyncMock(side_effect=_mock_validate)
            scope_a = _build_scope(PARTNER_A["apiKey"])
            await _dispatch(middleware, scope_a, captures)

        # After request completes, ContextVars should be back to defaults
        assert current_partner_id.get() == ""
        assert current_partner_department.get() == "all"
        assert current_partner_roles.get() == []
        assert current_partner_is_admin.get() is False
        assert current_partner_authorized_entity_ids.get() == []

    async def test_context_vars_reset_after_inner_exception(self):
        """ContextVars are reset via try-finally even if the inner app raises."""

        async def raising_inner(scope, receive, send):
            raise RuntimeError("simulated inner app crash")

        middleware = ApiKeyMiddleware(raising_inner)

        with patch("zenos.interface.tools._partner_validator") as mock_validator:
            mock_validator.validate = AsyncMock(side_effect=_mock_validate)
            scope_a = _build_scope(PARTNER_A["apiKey"])

            with pytest.raises(RuntimeError, match="simulated inner app crash"):
                await _dispatch(middleware, scope_a, [])

        # Must be reset even after exception
        assert current_partner_id.get() == ""
        assert current_partner_department.get() == "all"
        assert current_partner_roles.get() == []
        assert current_partner_is_admin.get() is False
        assert current_partner_authorized_entity_ids.get() == []

    async def test_no_context_leak_between_sequential_requests(self):
        """Partner A request followed by unauthenticated request: no leak."""
        captures: list[dict] = []
        inner = _make_capturing_app(captures)
        middleware = ApiKeyMiddleware(inner)

        with patch("zenos.interface.tools._partner_validator") as mock_validator:
            mock_validator.validate = AsyncMock(side_effect=_mock_validate)

            # First: authenticated request from Partner A
            scope_a = _build_scope(PARTNER_A["apiKey"])
            await _dispatch(middleware, scope_a, captures)

            # Second: unauthenticated request (no key)
            scope_anon = {
                "type": "http",
                "method": "GET",
                "path": "/ping",
                "query_string": b"",
                "headers": [],
            }
            responses_anon: list[dict] = []

            async def send_anon(event):
                responses_anon.append(event)

            await middleware(scope_anon, _fake_receive, send_anon)

        # Anon request must get 401 — partner A's context must not have leaked
        assert any(e.get("status") == 401 for e in responses_anon)
        # ContextVar must be at default after anon request
        assert current_partner_id.get() == ""
