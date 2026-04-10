"""Tests for list_workspaces MCP tool."""

from __future__ import annotations

import json
from contextvars import copy_context
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_bootstrap():
    with (
        patch("zenos.interface.mcp._ensure_services", new=AsyncMock()),
        patch("zenos.interface.mcp._ensure_repos", new=AsyncMock()),
    ):
        yield


def _run_in_context(coro, partner, original_shared=None):
    """Run coroutine with _current_partner and _original_shared_partner_id set."""
    from zenos.interface.mcp._auth import _current_partner, _original_shared_partner_id
    from zenos.infrastructure.context import current_partner_id

    ctx = copy_context()

    async def _inner():
        _current_partner.set(partner)
        _original_shared_partner_id.set(original_shared)
        current_partner_id.set(str(partner["id"]))
        return await coro

    return ctx.run(lambda: _inner())


class TestListWorkspaces:

    async def test_home_only_partner_sees_one_workspace(self):
        from zenos.interface.mcp.workspace import list_workspaces

        partner = {
            "id": "home-1",
            "email": "alice@test.com",
            "displayName": "Alice",
            "sharedPartnerId": None,
            "isAdmin": False,
            "status": "active",
        }

        result = await _run_in_context(list_workspaces(), partner)

        data = result["data"]
        assert len(data["workspaces"]) == 1
        assert data["workspaces"][0]["id"] == "home-1"
        assert data["workspaces"][0]["is_active"] is True
        assert "switch_hint" not in data

    async def test_shared_member_sees_two_workspaces(self):
        from zenos.interface.mcp.workspace import list_workspaces

        partner = {
            "id": "member-1",
            "email": "sue@test.com",
            "displayName": "Sue",
            "sharedPartnerId": None,  # stripped by active_partner_view
            "isAdmin": False,
            "status": "active",
        }

        mock_workspaces = [
            {"id": "member-1", "name": "我的工作區", "hasUpdate": False},
            {"id": "owner-1", "name": "Barry 的工作區", "hasUpdate": False},
        ]
        with patch(
            "zenos.application.identity.workspace_context.build_available_workspaces",
            new=AsyncMock(return_value=mock_workspaces),
        ):
            result = await _run_in_context(
                list_workspaces(),
                partner,
                original_shared="owner-1",
            )

        data = result["data"]
        assert len(data["workspaces"]) == 2
        ids = [w["id"] for w in data["workspaces"]]
        assert "member-1" in ids
        assert "owner-1" in ids
        assert "switch_hint" in data
        assert "owner-1" in data["switch_hint"]

    async def test_no_partner_returns_error(self):
        from zenos.interface.mcp.workspace import list_workspaces
        from zenos.interface.mcp._auth import _current_partner

        _current_partner.set(None)
        result = await list_workspaces()
        assert result["status"] == "error"
