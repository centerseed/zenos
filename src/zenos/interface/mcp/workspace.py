"""MCP tool — list_workspaces: list available workspaces and switch context."""

from __future__ import annotations


async def list_workspaces() -> dict:
    """列出當前用戶可用的工作區。

    回傳所有可存取的 workspace，包含名稱和 ID。
    用戶可用回傳的 workspace ID 傳入其他 tool 的 workspace_id 參數來切換工作區。

    Returns:
        {workspaces: [{id, name, is_active}], active_workspace_id, switch_hint}
    """
    import zenos.interface.mcp as _mcp
    from zenos.interface.mcp._auth import _current_partner, _original_shared_partner_id
    from zenos.interface.mcp._common import _unified_response
    from zenos.infrastructure.context import current_partner_id as _current_partner_id
    from zenos.application.identity.workspace_context import build_available_workspaces

    partner = _current_partner.get()
    if not partner:
        return _unified_response(
            status="error",
            data={"error": "UNAUTHORIZED"},
        )

    # Use async version with DB lookup for proper display names
    async def _lookup_partner(pid: str):
        await _mcp._ensure_repos()
        from zenos.infrastructure.identity import SqlPartnerRepository
        from zenos.infrastructure.sql_common import get_pool
        pool = await get_pool()
        repo = SqlPartnerRepository(pool)
        return await repo.get_by_id(pid)

    # Restore original shared_partner_id for workspace listing
    orig_shared = _original_shared_partner_id.get()
    partner_for_listing = partner
    if orig_shared and not partner.get("sharedPartnerId"):
        partner_for_listing = dict(partner)
        partner_for_listing["sharedPartnerId"] = orig_shared

    workspaces = await build_available_workspaces(partner_for_listing, _lookup_partner)

    active_ws = _current_partner_id.get() or str(partner["id"])

    # Mark which one is active
    for ws in workspaces:
        ws["is_active"] = (str(ws["id"]) == active_ws)

    result = {
        "workspaces": workspaces,
        "active_workspace_id": active_ws,
    }

    if len(workspaces) > 1:
        inactive = [w for w in workspaces if not w["is_active"]]
        if inactive:
            result["switch_hint"] = (
                f"要切換到「{inactive[0]['name']}」，在任何 tool 呼叫中傳入 "
                f"workspace_id=\"{inactive[0]['id']}\""
            )

    return _unified_response(status="success", data=result)
