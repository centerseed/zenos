"""MCP interface — federation scope enforcement.

ADR-029: scope checking for delegated JWT credentials.
API key callers always have full scopes; JWT callers are constrained to their token's scopes.
"""

from __future__ import annotations

import functools
import logging

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Tool → scope mapping
# ──────────────────────────────────────────────

TOOL_SCOPE_MAP: dict[str, str] = {
    # read scope
    "search": "read",
    "get": "read",
    "read_source": "read",
    "common_neighbors": "read",
    "find_gaps": "read",
    "governance_guide": "read",
    "journal_read": "read",
    "analyze": "read",
    "setup": "read",
    "suggest_policy": "read",
    # write scope
    "write": "write",
    "confirm": "write",
    "batch_update_sources": "write",
    "upload_attachment": "write",
    "upload_document_file": "write",
    "journal_write": "write",
    # task scope
    "task": "task",
    "plan": "task",
}


def require_scope(scope: str):
    """Decorator factory — enforces that the current request has the required scope.

    If _current_scopes is None (API key path), all scopes are considered granted.
    If _current_scopes is set (JWT path), the requested scope must be present.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from zenos.interface.mcp._auth import _current_scopes
            from zenos.interface.mcp._common import _error_response
            current = _current_scopes.get()
            # None means full access (API key path)
            if current is not None and scope not in current:
                logger.warning(
                    "Scope denied: required=%s granted=%s tool=%s",
                    scope, current, func.__name__,
                )
                return _error_response(
                    error_code="FORBIDDEN",
                    message=f"This operation requires '{scope}' scope.",
                    warnings=[
                        f"Your credential only has: {sorted(current)}",
                        f"Required scope: {scope}",
                    ],
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
