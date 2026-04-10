"""Unit tests for workspace_context application module (ADR-024)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from zenos.application.identity.workspace_context import (
    resolve_active_workspace_id,
    active_partner_view,
    build_available_workspaces,
    build_workspace_context_sync,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _partner_home_only(partner_id="home-1") -> dict:
    """Partner with no shared workspace."""
    return {
        "id": partner_id,
        "email": "alice@example.com",
        "sharedPartnerId": None,
        "isAdmin": False,
        "status": "active",
        "authorizedEntityIds": [],
    }


def _partner_with_shared(partner_id="home-1", shared_id="shared-99") -> dict:
    """Partner linked to a shared workspace."""
    return {
        "id": partner_id,
        "email": "alice@example.com",
        "sharedPartnerId": shared_id,
        "isAdmin": False,
        "status": "active",
        "authorizedEntityIds": [],
    }


# ──────────────────────────────────────────────────────────────────────────────
# resolve_active_workspace_id
# ──────────────────────────────────────────────────────────────────────────────

class TestResolveActiveWorkspaceId:

    def test_no_requested_id_returns_home(self):
        partner = _partner_home_only("home-1")
        result = resolve_active_workspace_id(partner, None)
        assert result == "home-1"

    def test_no_requested_id_with_shared_partner_still_returns_home(self):
        """ADR-024/SPEC: missing workspace_id must default to home, not shared."""
        partner = _partner_with_shared("home-1", "shared-99")
        result = resolve_active_workspace_id(partner, None)
        assert result == "home-1"

    def test_requested_home_id_is_accepted(self):
        partner = _partner_with_shared("home-1", "shared-99")
        result = resolve_active_workspace_id(partner, "home-1")
        assert result == "home-1"

    def test_requested_shared_id_is_accepted(self):
        partner = _partner_with_shared("home-1", "shared-99")
        result = resolve_active_workspace_id(partner, "shared-99")
        assert result == "shared-99"

    def test_invalid_requested_id_falls_back_to_home(self):
        partner = _partner_with_shared("home-1", "shared-99")
        result = resolve_active_workspace_id(partner, "unknown-workspace")
        assert result == "home-1"

    def test_empty_string_requested_id_falls_back_to_home(self):
        partner = _partner_home_only("home-1")
        result = resolve_active_workspace_id(partner, "")
        assert result == "home-1"

    def test_partner_without_shared_only_accepts_home(self):
        partner = _partner_home_only("home-1")
        result = resolve_active_workspace_id(partner, "home-1")
        assert result == "home-1"

    def test_partner_without_shared_rejects_foreign_id(self):
        partner = _partner_home_only("home-1")
        result = resolve_active_workspace_id(partner, "some-other-id")
        assert result == "home-1"


# ──────────────────────────────────────────────────────────────────────────────
# active_partner_view
# ──────────────────────────────────────────────────────────────────────────────

class TestActivePartnerView:

    def test_home_workspace_view_strips_shared_link_and_grants_owner(self):
        """When active workspace == home, partner is projected as owner with no shared link."""
        partner = _partner_with_shared("home-1", "shared-99")
        projected, effective_id = active_partner_view(partner, "home-1")

        assert projected["sharedPartnerId"] is None
        assert projected["isAdmin"] is True
        assert projected["accessMode"] == "internal"
        assert projected["workspaceRole"] == "owner"
        assert projected["authorizedEntityIds"] == []
        assert effective_id == "home-1"

    def test_shared_workspace_view_uses_shared_id_as_effective(self):
        """When active workspace == shared, effective_id points to shared tenant."""
        partner = _partner_with_shared("home-1", "shared-99")
        _, effective_id = active_partner_view(partner, "shared-99")
        assert effective_id == "shared-99"

    def test_no_shared_partner_returns_home_as_effective(self):
        """Partner without sharedPartnerId: effective_id is always home."""
        partner = _partner_home_only("home-1")
        projected, effective_id = active_partner_view(partner, "home-1")
        assert effective_id == "home-1"

    def test_home_workspace_does_not_mutate_original_partner(self):
        """active_partner_view returns a copy, not a mutation of the input."""
        partner = _partner_with_shared("home-1", "shared-99")
        active_partner_view(partner, "home-1")
        # Original must still have sharedPartnerId
        assert partner["sharedPartnerId"] == "shared-99"

    def test_shared_workspace_view_sets_access_mode(self):
        """Shared workspace projection derives access_mode via describe_partner_access."""
        partner = _partner_with_shared("home-1", "shared-99")
        projected, _ = active_partner_view(partner, "shared-99")
        assert "accessMode" in projected

    def test_unassigned_partner_does_not_get_workspace_role(self):
        """Unassigned partners must NOT get workspaceRole set (breaks fast-path filtering)."""
        partner = {
            "id": "home-1",
            "sharedPartnerId": "shared-99",
            "isAdmin": False,
            "status": "inactive",  # => unassigned
            "authorizedEntityIds": [],
        }
        projected, _ = active_partner_view(partner, "shared-99")
        assert projected.get("accessMode") == "unassigned"
        assert "workspaceRole" not in projected


# ──────────────────────────────────────────────────────────────────────────────
# build_available_workspaces (async)
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildAvailableWorkspaces:

    @pytest.mark.asyncio
    async def test_partner_without_shared_returns_one_workspace(self):
        partner = _partner_home_only("home-1")
        lookup = AsyncMock(return_value=None)
        result = await build_available_workspaces(partner, lookup)
        assert len(result) == 1
        assert result[0]["id"] == "home-1"
        assert result[0]["name"] == "我的工作區"
        lookup.assert_not_called()

    @pytest.mark.asyncio
    async def test_partner_with_shared_returns_two_workspaces(self):
        partner = _partner_with_shared("home-1", "shared-99")
        owner_dict = {"displayName": "Barry", "email": "barry@example.com"}
        lookup = AsyncMock(return_value=owner_dict)
        result = await build_available_workspaces(partner, lookup)
        assert len(result) == 2
        lookup.assert_called_once_with("shared-99")

    @pytest.mark.asyncio
    async def test_shared_workspace_name_uses_display_name(self):
        partner = _partner_with_shared("home-1", "shared-99")
        lookup = AsyncMock(return_value={"displayName": "Barry Inc"})
        result = await build_available_workspaces(partner, lookup)
        shared = next(w for w in result if w["id"] == "shared-99")
        assert "Barry Inc" in shared["name"]

    @pytest.mark.asyncio
    async def test_shared_workspace_name_falls_back_to_email(self):
        partner = _partner_with_shared("home-1", "shared-99")
        lookup = AsyncMock(return_value={"email": "barry@example.com"})
        result = await build_available_workspaces(partner, lookup)
        shared = next(w for w in result if w["id"] == "shared-99")
        assert "barry@example.com" in shared["name"]

    @pytest.mark.asyncio
    async def test_shared_workspace_name_falls_back_to_default_when_no_owner(self):
        partner = _partner_with_shared("home-1", "shared-99")
        lookup = AsyncMock(return_value=None)
        result = await build_available_workspaces(partner, lookup)
        shared = next(w for w in result if w["id"] == "shared-99")
        # Fallback is "共享工作區 的工作區" (using the hardcoded fallback owner_name)
        assert "共享工作區" in shared["name"]


# ──────────────────────────────────────────────────────────────────────────────
# build_workspace_context_sync
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildWorkspaceContextSync:

    def test_home_workspace_context_is_home(self):
        partner = _partner_home_only("home-1")
        ctx = build_workspace_context_sync(partner, "home-1")
        assert ctx["workspace_id"] == "home-1"
        assert ctx["is_home_workspace"] is True
        assert ctx["workspace_name"] == "我的工作區"

    def test_shared_workspace_context_is_not_home(self):
        partner = _partner_with_shared("home-1", "shared-99")
        ctx = build_workspace_context_sync(partner, "shared-99")
        assert ctx["workspace_id"] == "shared-99"
        assert ctx["is_home_workspace"] is False

    def test_available_workspaces_listed(self):
        partner = _partner_with_shared("home-1", "shared-99")
        ctx = build_workspace_context_sync(partner, "home-1")
        ids = [w["id"] for w in ctx["available_workspaces"]]
        assert "home-1" in ids
        assert "shared-99" in ids

    def test_partner_without_shared_has_one_available(self):
        partner = _partner_home_only("home-1")
        ctx = build_workspace_context_sync(partner, "home-1")
        assert len(ctx["available_workspaces"]) == 1

    def test_all_required_keys_present(self):
        partner = _partner_home_only("home-1")
        ctx = build_workspace_context_sync(partner, "home-1")
        for key in ("workspace_id", "workspace_name", "is_home_workspace", "available_workspaces"):
            assert key in ctx, f"Missing key: {key}"

    def test_adjusted_home_view_still_lists_shared_workspace(self):
        """BUG REPRO: shared member viewing home workspace.

        Runtime path: active_partner_view() strips sharedPartnerId when
        projecting to home workspace. build_workspace_context_sync then
        receives the adjusted partner (sharedPartnerId=None).
        Fix: pass original_shared_id to preserve the shared workspace.
        """
        partner = _partner_with_shared("home-1", "shared-99")

        # Simulate runtime: active_partner_view adjusts partner for home view
        adjusted, _ = active_partner_view(partner, "home-1")
        assert adjusted["sharedPartnerId"] is None  # confirms the strip

        # Without original_shared_id → bug: only 1 workspace
        ctx_broken = build_workspace_context_sync(adjusted, "home-1")
        assert len(ctx_broken["available_workspaces"]) == 1  # confirms the bug path

        # With original_shared_id → fix: 2 workspaces
        ctx_fixed = build_workspace_context_sync(
            adjusted, "home-1", original_shared_id="shared-99"
        )
        ids = [w["id"] for w in ctx_fixed["available_workspaces"]]
        assert "shared-99" in ids, (
            f"Shared workspace missing from available_workspaces. Got: {ids}"
        )
        assert "home-1" in ids
