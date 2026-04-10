"""Workspace context resolution — shared between dashboard_api and MCP tools.

Provides pure functions for:
  - resolving which workspace is active for a given partner
  - projecting a raw partner row into the selected active-workspace view
  - building the list of available workspaces (with optional DB lookup)
  - assembling the workspace_context dict injected into MCP tool responses
"""

from __future__ import annotations

from typing import Awaitable, Callable

from zenos.domain.partner_access import describe_partner_access


def resolve_active_workspace_id(partner: dict, requested_id: str | None) -> str:
    """Resolve which workspace is active for a partner.

    Priority:
      1. If *requested_id* is in the partner's valid workspace set, honour it.
      2. Otherwise fall back to the partner's home workspace (partner["id"]).

    Args:
        partner: Raw partner row dict (must have "id", may have "sharedPartnerId").
        requested_id: Workspace ID requested by the caller (may be None).

    Returns:
        The resolved active workspace ID string.
    """
    home_id = str(partner["id"])
    shared_id = str(partner["sharedPartnerId"]) if partner.get("sharedPartnerId") else None
    if requested_id and requested_id in {home_id, shared_id}:
        return requested_id
    return home_id


def active_partner_view(partner: dict, active_workspace_id: str) -> tuple[dict, str]:
    """Project a raw partner row into the selected active-workspace context.

    When the active workspace is the partner's *home* workspace and the partner
    has a sharedPartnerId (i.e. they are viewing their own space, not the shared
    tenant), the projection strips the shared link and grants owner privileges.

    Otherwise the partner is projected into the shared workspace perspective:
    access mode and workspace role are derived from ``describe_partner_access``.

    Args:
        partner: Raw partner row dict.
        active_workspace_id: The resolved active workspace ID.

    Returns:
        A (projected_partner, effective_partner_id) tuple where
        effective_partner_id is the tenant routing key used by repositories.
    """
    shared_partner_id = str(partner["sharedPartnerId"]) if partner.get("sharedPartnerId") else None

    if shared_partner_id and active_workspace_id == str(partner["id"]):
        # Viewing home workspace — strip shared link, grant owner privileges
        projected = dict(partner)
        projected["sharedPartnerId"] = None
        projected["isAdmin"] = True
        projected["accessMode"] = "internal"
        projected["workspaceRole"] = "owner"
        projected["authorizedEntityIds"] = []
        return projected, str(partner["id"])

    projected = dict(partner)
    access = describe_partner_access(projected)
    projected["accessMode"] = access["access_mode"]
    # Only set workspaceRole when partner is NOT unassigned.
    # Setting workspaceRole="guest" on an unassigned partner causes
    # resolve_access_mode to reclassify them as "scoped" (since it
    # prioritises workspaceRole over accessMode), breaking the
    # unassigned → empty-result fast-path.
    if access["access_mode"] != "unassigned":
        projected["workspaceRole"] = access["workspace_role"]
    return projected, shared_partner_id or str(partner["id"])


async def build_available_workspaces(
    partner: dict,
    lookup_partner_fn: Callable[[str], Awaitable[dict | None]],
) -> list[dict]:
    """Build the list of workspaces available to a partner.

    Performs a DB lookup for the shared workspace display name via the
    injected *lookup_partner_fn* callback, keeping this module free from
    direct infrastructure imports.

    Args:
        partner: Raw partner row dict.
        lookup_partner_fn: Async callable ``(partner_id: str) -> dict | None``
            used to look up the shared workspace owner's display info.

    Returns:
        List of workspace dicts: [{"id", "name", "hasUpdate"}, ...]
    """
    workspaces = [{"id": partner["id"], "name": "我的工作區", "hasUpdate": False}]
    shared_partner_id = partner.get("sharedPartnerId")
    if not shared_partner_id:
        return workspaces

    owner = await lookup_partner_fn(str(shared_partner_id))
    owner_name = (
        (owner or {}).get("displayName")
        or (owner or {}).get("email")
        or "共享工作區"
    )
    workspaces.append({
        "id": str(shared_partner_id),
        "name": f"{owner_name} 的工作區",
        "hasUpdate": False,
    })
    return workspaces


def build_workspace_context_sync(partner: dict, active_workspace_id: str) -> dict:
    """Assemble the workspace_context dict injected into MCP tool responses.

    This is the sync variant — it does NOT perform DB lookups for display names.
    The shared workspace name falls back to "共享工作區" when the display name
    is not already present in the partner dict.  The dashboard can enrich names
    separately via its own DB access.

    Args:
        partner: Raw partner row dict.
        active_workspace_id: The currently active workspace ID.

    Returns:
        workspace_context dict suitable for embedding in MCP responses.
    """
    home_id = str(partner["id"])
    shared_partner_id = partner.get("sharedPartnerId")
    shared_id = str(shared_partner_id) if shared_partner_id else None

    is_home = active_workspace_id == home_id

    available: list[dict] = [{"id": home_id, "name": "我的工作區", "hasUpdate": False}]
    if shared_id:
        available.append({
            "id": shared_id,
            "name": "共享工作區",
            "hasUpdate": False,
        })

    return {
        "workspace_id": active_workspace_id,
        "workspace_name": "我的工作區" if is_home else "共享工作區",
        "is_home_workspace": is_home,
        "available_workspaces": available,
    }
