"""MCP interface — partner auth context and API key middleware.

Contains:
- _current_partner ContextVar
- ApiKeyMiddleware (ASGI)
- SseApiKeyPropagator (ASGI)
- _apply_workspace_override()
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from urllib.parse import parse_qs

from starlette.responses import JSONResponse

from zenos.infrastructure.identity import SqlPartnerKeyValidator
from zenos.infrastructure.context import (
    current_partner_authorized_entity_ids as _ctx_authorized_entity_ids,
    current_partner_department,
    current_partner_id as _current_partner_id,
    current_partner_is_admin,
    current_partner_roles,
)
from zenos.application.identity.workspace_context import (
    resolve_active_workspace_id,
    active_partner_view,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Agent Identity — ContextVar for partner data
# ──────────────────────────────────────────────

_current_partner: ContextVar[dict | None] = ContextVar("current_partner", default=None)

# ──────────────────────────────────────────────
# API Key authentication middleware
# ──────────────────────────────────────────────

PartnerKeyValidator = SqlPartnerKeyValidator
_partner_validator = PartnerKeyValidator()


class ApiKeyMiddleware:
    """Pure ASGI middleware — compatible with SSE streaming.

    Authentication:
    - Validate key against active partners in SQL (partners table).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        key = self._extract_key(scope)
        path = scope.get("path", "")

        # Partner key (SQL)
        if key:
            partner = await _partner_validator.validate(key)
            if partner is not None:
                from zenos.infrastructure.context import (
                    current_partner_id,
                    current_partner_authorized_entity_ids,
                )
                # Resolve active workspace: honour X-Active-Workspace-Id header if valid
                ws_header = self._extract_workspace_id(scope)
                resolved_ws = resolve_active_workspace_id(partner, ws_header)
                adjusted, effective_id = active_partner_view(partner, resolved_ws)

                token = _current_partner.set(adjusted)
                token_pid = current_partner_id.set(effective_id)
                token_roles = current_partner_roles.set(list(partner.get("roles") or []))
                token_department = current_partner_department.set(str(partner.get("department") or "all"))
                token_admin = current_partner_is_admin.set(bool(adjusted.get("isAdmin", False)))
                token_auth_ids = current_partner_authorized_entity_ids.set(
                    list(adjusted.get("authorizedEntityIds") or [])
                )
                try:
                    return await self.app(scope, receive, send)
                finally:
                    _current_partner.reset(token)
                    current_partner_id.reset(token_pid)
                    current_partner_roles.reset(token_roles)
                    current_partner_department.reset(token_department)
                    current_partner_is_admin.reset(token_admin)
                    current_partner_authorized_entity_ids.reset(token_auth_ids)
            logger.warning(
                "Auth rejected: key=%.8s... path=%s cache_size=%d",
                key, path, len(_partner_validator._cache),
            )
        else:
            logger.debug("Auth rejected: no key provided, path=%s", path)

        response = JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
        return await response(scope, receive, send)

    @staticmethod
    def _extract_key(scope) -> str | None:
        """Extract API key from headers or query param."""
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        x_api_key = headers.get(b"x-api-key", b"").decode()
        if x_api_key:
            return x_api_key

        qs = parse_qs(scope.get("query_string", b"").decode())
        keys = qs.get("api_key", [])
        return keys[0] if keys else None

    @staticmethod
    def _extract_workspace_id(scope) -> str | None:
        """Extract X-Active-Workspace-Id header value, or None if absent."""
        headers = dict(scope.get("headers", []))
        ws = headers.get(b"x-active-workspace-id", b"").decode().strip()
        return ws or None


class SseApiKeyPropagator:
    """Inject api_key into the SSE endpoint event so clients preserve auth.

    FastMCP SSE sends: data: /messages/?session_id=<uuid>
    We patch it to:   data: /messages/?session_id=<uuid>&api_key=<key>

    Only activates when api_key is present in the original query string.
    Header-based auth clients are unaffected (pass-through).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        qs = parse_qs(scope.get("query_string", b"").decode())
        api_key = qs.get("api_key", [None])[0]

        if not api_key:
            return await self.app(scope, receive, send)

        async def patched_send(event):
            if event["type"] == "http.response.body":
                body = event.get("body", b"")
                if body:
                    text = body.decode("utf-8", errors="replace")
                    text = re.sub(
                        r"(data: /messages/\?session_id=[^\s&]+)",
                        lambda m: m.group(0) + f"&api_key={api_key}",
                        text,
                    )
                    event = {**event, "body": text.encode("utf-8")}
            await send(event)

        await self.app(scope, receive, patched_send)


def _apply_workspace_override(workspace_id: str) -> dict | None:
    """Attempt to switch the active workspace for the current request.

    Validates *workspace_id* against the authenticated partner's allowed
    workspaces, then mutates the ContextVars for the remainder of the
    request if valid.

    Returns:
        None when the switch succeeded (caller should continue normally).
        An error response dict when *workspace_id* is not in the allowed
        set (caller should return this dict immediately).
    """
    # Import here to avoid circular import (_common imports _auth)
    from zenos.interface.mcp._common import _unified_response

    partner = _current_partner.get()
    if not partner:
        return None  # No partner context — silently skip (middleware will block auth anyway)

    resolved = resolve_active_workspace_id(partner, workspace_id)
    if resolved != workspace_id:
        # workspace_id was not in the partner's valid set; resolve fell back to home
        home_id = str(partner["id"])
        shared_partner_id = partner.get("sharedPartnerId")
        available = [home_id]
        if shared_partner_id:
            available.append(str(shared_partner_id))
        return _unified_response(
            status="error",
            data={"error": "FORBIDDEN_WORKSPACE"},
            warnings=[
                f"workspace_id '{workspace_id}' 不在你的可用 workspace 列表中。"
                f" 可用：{available}"
            ],
        )

    adjusted, effective_id = active_partner_view(partner, resolved)
    _current_partner.set(adjusted)
    _current_partner_id.set(effective_id)
    current_partner_is_admin.set(bool(adjusted.get("isAdmin", False)))
    _ctx_authorized_entity_ids.set(list(adjusted.get("authorizedEntityIds") or []))
    return None
