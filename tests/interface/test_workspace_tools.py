"""Tests for ADR-024 workspace_id parameter and _apply_workspace_override in tools.py."""

from __future__ import annotations

from contextvars import copy_context
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from zenos.domain.knowledge import Entity, Tags


# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap — prevent SQL repos from being instantiated in unit tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    with (
        patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)),
        patch("zenos.interface.mcp.ontology_service", new=AsyncMock()),
        patch("zenos.interface.mcp.task_service", new=AsyncMock()),
        patch("zenos.interface.mcp.entity_repo", new=AsyncMock()),
        patch("zenos.interface.mcp.entry_repo", new=AsyncMock()),
    ):
        yield


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-1",
        name="Paceriz",
        type="product",
        summary="Running coach",
        tags=Tags(what="app", why="coach", how="AI", who="runners"),
        status="active",
        parent_id=None,
        confirmed_by_user=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_partner(partner_id="home-1", shared_id=None) -> dict:
    return {
        "id": partner_id,
        "email": "alice@example.com",
        "sharedPartnerId": shared_id,
        "isAdmin": False,
        "status": "active",
        "authorizedEntityIds": [],
        "roles": [],
        "department": "all",
    }


# ──────────────────────────────────────────────────────────────────────────────
# _apply_workspace_override unit tests
# ──────────────────────────────────────────────────────────────────────────────


class TestApplyWorkspaceOverride:

    def test_returns_none_when_no_partner(self):
        """Without an authenticated partner, override is silently skipped."""
        from zenos.interface.mcp import _apply_workspace_override, _current_partner

        token = _current_partner.set(None)
        try:
            result = _apply_workspace_override("some-ws")
        finally:
            _current_partner.reset(token)

        assert result is None

    def test_valid_home_workspace_returns_none(self):
        """Valid home workspace ID should succeed (return None)."""
        from zenos.interface.mcp import _apply_workspace_override, _current_partner

        partner = _make_partner("home-1")
        token = _current_partner.set(partner)
        try:
            result = _apply_workspace_override("home-1")
        finally:
            _current_partner.reset(token)

        assert result is None

    def test_valid_shared_workspace_returns_none(self):
        """Valid shared workspace ID should succeed (return None)."""
        from zenos.interface.mcp import _apply_workspace_override, _current_partner

        partner = _make_partner("home-1", shared_id="shared-99")
        token = _current_partner.set(partner)
        try:
            result = _apply_workspace_override("shared-99")
        finally:
            _current_partner.reset(token)

        assert result is None

    def test_invalid_workspace_returns_error_dict(self):
        """Invalid workspace ID should return FORBIDDEN_WORKSPACE error response."""
        from zenos.interface.mcp import _apply_workspace_override, _current_partner

        partner = _make_partner("home-1", shared_id="shared-99")
        token = _current_partner.set(partner)
        try:
            result = _apply_workspace_override("evil-workspace")
        finally:
            _current_partner.reset(token)

        assert result is not None
        assert result["status"] == "error"
        assert result["data"]["error"] == "FORBIDDEN_WORKSPACE"

    def test_invalid_workspace_error_mentions_available_workspaces(self):
        """FORBIDDEN_WORKSPACE error should hint at available workspace IDs."""
        from zenos.interface.mcp import _apply_workspace_override, _current_partner

        partner = _make_partner("home-1", shared_id="shared-99")
        token = _current_partner.set(partner)
        try:
            result = _apply_workspace_override("not-allowed")
        finally:
            _current_partner.reset(token)

        warnings_text = " ".join(result["warnings"])
        assert "home-1" in warnings_text or "shared-99" in warnings_text

    def test_invalid_workspace_on_home_only_partner(self):
        """Partner without shared workspace rejects any non-home workspace."""
        from zenos.interface.mcp import _apply_workspace_override, _current_partner

        partner = _make_partner("home-1", shared_id=None)
        token = _current_partner.set(partner)
        try:
            result = _apply_workspace_override("shared-99")
        finally:
            _current_partner.reset(token)

        assert result is not None
        assert result["data"]["error"] == "FORBIDDEN_WORKSPACE"

    def test_switch_from_home_projection_to_shared_updates_effective_workspace(self):
        """Regression: home-view projection must still be able to switch to shared workspace."""
        from zenos.interface.mcp import _apply_workspace_override
        from zenos.interface.mcp._auth import (
            _current_partner,
            _original_shared_partner_id,
            _raw_authenticated_partner,
        )
        from zenos.application.identity.workspace_context import active_partner_view
        from zenos.infrastructure.context import current_partner_id

        raw_partner = _make_partner("home-1", shared_id="shared-99")
        raw_partner.update({
            "workspaceRole": "guest",
            "accessMode": "scoped",
            "authorizedEntityIds": ["l1-a"],
        })
        # Simulate middleware default behavior: request starts in home workspace.
        home_projected, _ = active_partner_view(raw_partner, "home-1")
        assert home_projected["sharedPartnerId"] is None
        assert home_projected["workspaceRole"] == "owner"

        token_partner = _current_partner.set(home_projected)
        token_pid = current_partner_id.set("home-1")
        token_orig_shared = _original_shared_partner_id.set("shared-99")
        token_raw = _raw_authenticated_partner.set(raw_partner)
        try:
            result = _apply_workspace_override("shared-99")
            assert result is None
            assert current_partner_id.get() == "shared-99"
            switched = _current_partner.get()
            assert switched is not None
            assert switched.get("workspaceRole") == "guest"
            assert switched.get("sharedPartnerId") == "shared-99"
        finally:
            _current_partner.reset(token_partner)
            current_partner_id.reset(token_pid)
            _original_shared_partner_id.reset(token_orig_shared)
            _raw_authenticated_partner.reset(token_raw)

    def test_switch_back_to_home_restores_owner_projection(self):
        """Shared workspace context can switch back to home and regain owner projection."""
        from zenos.interface.mcp import _apply_workspace_override
        from zenos.interface.mcp._auth import (
            _current_partner,
            _original_shared_partner_id,
            _raw_authenticated_partner,
        )
        from zenos.application.identity.workspace_context import active_partner_view
        from zenos.infrastructure.context import current_partner_id

        raw_partner = _make_partner("home-1", shared_id="shared-99")
        raw_partner.update({
            "workspaceRole": "guest",
            "accessMode": "scoped",
            "authorizedEntityIds": ["l1-a"],
        })
        shared_projected, _ = active_partner_view(raw_partner, "shared-99")
        assert shared_projected.get("workspaceRole") == "guest"

        token_partner = _current_partner.set(shared_projected)
        token_pid = current_partner_id.set("shared-99")
        token_orig_shared = _original_shared_partner_id.set("shared-99")
        token_raw = _raw_authenticated_partner.set(raw_partner)
        try:
            result = _apply_workspace_override("home-1")
            assert result is None
            assert current_partner_id.get() == "home-1"
            switched = _current_partner.get()
            assert switched is not None
            assert switched.get("workspaceRole") == "owner"
            assert switched.get("sharedPartnerId") is None
        finally:
            _current_partner.reset(token_partner)
            current_partner_id.reset(token_pid)
            _original_shared_partner_id.reset(token_orig_shared)
            _raw_authenticated_partner.reset(token_raw)


# ──────────────────────────────────────────────────────────────────────────────
# workspace_context injected in _unified_response
# ──────────────────────────────────────────────────────────────────────────────


class TestUnifiedResponseWorkspaceContext:

    def test_no_partner_context_no_workspace_context(self):
        """Without authenticated partner, workspace_context should not appear."""
        from zenos.interface.mcp import _unified_response, _current_partner

        token = _current_partner.set(None)
        try:
            result = _unified_response(data={"x": 1})
        finally:
            _current_partner.reset(token)

        assert "workspace_context" not in result

    def test_partner_context_injects_workspace_context(self):
        """Authenticated partner causes workspace_context to be injected."""
        from zenos.interface.mcp import _unified_response, _current_partner
        from zenos.infrastructure.context import current_partner_id

        partner = _make_partner("home-1")
        token_p = _current_partner.set(partner)
        token_id = current_partner_id.set("home-1")
        try:
            result = _unified_response(data={})
        finally:
            _current_partner.reset(token_p)
            current_partner_id.reset(token_id)

        assert "workspace_context" in result
        ws_ctx = result["workspace_context"]
        assert ws_ctx["workspace_id"] == "home-1"
        assert ws_ctx["is_home_workspace"] is True
        assert "available_workspaces" in ws_ctx

    def test_workspace_context_includes_required_keys(self):
        """workspace_context must have workspace_id, workspace_name, is_home_workspace, available_workspaces."""
        from zenos.interface.mcp import _unified_response, _current_partner
        from zenos.infrastructure.context import current_partner_id

        partner = _make_partner("home-1", shared_id="shared-99")
        token_p = _current_partner.set(partner)
        token_id = current_partner_id.set("shared-99")
        try:
            result = _unified_response(data={})
        finally:
            _current_partner.reset(token_p)
            current_partner_id.reset(token_id)

        ws = result["workspace_context"]
        for key in ("workspace_id", "workspace_name", "is_home_workspace", "available_workspaces"):
            assert key in ws, f"Missing workspace_context key: {key}"

    def test_non_home_workspace_reflected_correctly(self):
        """When active workspace is shared, is_home_workspace must be False."""
        from zenos.interface.mcp import _unified_response, _current_partner
        from zenos.infrastructure.context import current_partner_id

        partner = _make_partner("home-1", shared_id="shared-99")
        token_p = _current_partner.set(partner)
        token_id = current_partner_id.set("shared-99")
        try:
            result = _unified_response(data={})
        finally:
            _current_partner.reset(token_p)
            current_partner_id.reset(token_id)

        assert result["workspace_context"]["is_home_workspace"] is False
        assert result["workspace_context"]["workspace_id"] == "shared-99"


# ──────────────────────────────────────────────────────────────────────────────
# workspace_id parameter wiring — write tool
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestWriteToolWorkspaceId:

    async def test_invalid_workspace_id_rejected_before_write(self):
        """write() with invalid workspace_id returns FORBIDDEN_WORKSPACE without writing."""
        from zenos.interface.mcp import write, _current_partner

        partner = _make_partner("home-1")
        token = _current_partner.set(partner)
        try:
            result = await write(
                collection="entities",
                data={"name": "Test", "type": "product", "summary": "x",
                      "tags": {"what": "a", "why": "b", "how": "c", "who": "d"}},
                workspace_id="evil-ws",
            )
        finally:
            _current_partner.reset(token)

        assert result["status"] == "error"
        assert result["data"]["error"] == "FORBIDDEN_WORKSPACE"

    async def test_valid_workspace_id_proceeds_to_write(self):
        """write() with valid workspace_id should proceed — NOT return FORBIDDEN_WORKSPACE."""
        from zenos.interface.mcp import write, _current_partner
        from zenos.application.knowledge.ontology_service import UpsertEntityResult
        from zenos.domain.shared import TagConfidence

        entity = _make_entity()
        upsert_result = UpsertEntityResult(
            entity=entity,
            tag_confidence=TagConfidence(confirmed_fields=[], draft_fields=[]),
            split_recommendation=None,
            warnings=None,
        )

        partner = _make_partner("home-1")
        token = _current_partner.set(partner)
        try:
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.upsert_entity = AsyncMock(return_value=upsert_result)
                result = await write(
                    collection="entities",
                    data={"name": "Paceriz", "type": "product", "summary": "Test",
                          "tags": {"what": "app", "why": "x", "how": "y", "who": "z"}},
                    workspace_id="home-1",
                )
        finally:
            _current_partner.reset(token)

        # The write proceeded past workspace validation — ensure no FORBIDDEN error
        assert result.get("data", {}).get("error") != "FORBIDDEN_WORKSPACE"
        assert result.get("status") != "error"


# ──────────────────────────────────────────────────────────────────────────────
# workspace_id parameter wiring — search tool
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestSearchToolWorkspaceId:

    async def test_invalid_workspace_id_rejected(self):
        """search() with invalid workspace_id returns FORBIDDEN_WORKSPACE."""
        from zenos.interface.mcp import search, _current_partner

        partner = _make_partner("home-1")
        token = _current_partner.set(partner)
        try:
            result = await search(collection="entities", workspace_id="bad-ws")
        finally:
            _current_partner.reset(token)

        assert result["status"] == "error"
        assert result["data"]["error"] == "FORBIDDEN_WORKSPACE"


# ──────────────────────────────────────────────────────────────────────────────
# ApiKeyMiddleware workspace header extraction
# ──────────────────────────────────────────────────────────────────────────────


class TestApiKeyMiddlewareWorkspaceExtraction:

    def test_extract_workspace_id_from_header(self):
        from zenos.interface.mcp import ApiKeyMiddleware

        scope = {
            "headers": [(b"x-active-workspace-id", b"shared-99")],
        }
        result = ApiKeyMiddleware._extract_workspace_id(scope)
        assert result == "shared-99"

    def test_extract_workspace_id_missing_returns_none(self):
        from zenos.interface.mcp import ApiKeyMiddleware

        scope = {"headers": []}
        result = ApiKeyMiddleware._extract_workspace_id(scope)
        assert result is None

    def test_extract_workspace_id_empty_header_returns_none(self):
        from zenos.interface.mcp import ApiKeyMiddleware

        scope = {
            "headers": [(b"x-active-workspace-id", b"   ")],
        }
        result = ApiKeyMiddleware._extract_workspace_id(scope)
        assert result is None
