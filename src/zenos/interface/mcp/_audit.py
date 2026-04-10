"""MCP interface — audit logging helpers.

Contains:
- _audit_log
- _schedule_audit_sql_write
- _write_audit_event
- _log_tool_event
- _schedule_tool_event
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Lazily initialized audit repo (populated on first use)
_audit_repo = None


def _audit_log(
    event_type: str,
    target: dict,
    changes: dict | None = None,
    governance: dict | None = None,
) -> None:
    """Emit structured governance audit logs to stdout/Cloud Logging + SQL."""
    from zenos.interface.mcp._auth import _current_partner

    partner = _current_partner.get() or {}
    payload = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "partner_id": partner.get("id", ""),
        "actor": {
            "id": partner.get("id", ""),
            "name": partner.get("displayName", "system"),
            "email": partner.get("email", ""),
        },
        "target": target,
        "changes": changes or {},
        "governance": governance or {},
    }
    logger.info("AUDIT_LOG %s", json.dumps(payload, ensure_ascii=False, default=str))

    # Async SQL write (non-blocking, graceful degradation)
    _schedule_audit_sql_write(payload)


def _schedule_audit_sql_write(payload: dict) -> None:
    """Schedule non-blocking SQL write. Never raises."""
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running():
            return
        loop.create_task(_write_audit_event(payload))
    except Exception:
        pass  # Audit write scheduling must never crash the caller


async def _write_audit_event(payload: dict) -> None:
    """Write audit event to SQL. Failure only logs warning."""
    global _audit_repo  # noqa: PLW0603
    try:
        if _audit_repo is None:
            from zenos.infrastructure.agent import SqlAuditEventRepository
            from zenos.infrastructure.sql_common import get_pool
            pool = await get_pool()
            _audit_repo = SqlAuditEventRepository(pool)
        event = {
            "partner_id": payload.get("partner_id", ""),
            "actor_id": payload.get("actor", {}).get("id", ""),
            "actor_type": "partner",
            "operation": payload.get("event_type", ""),
            "resource_type": payload.get("target", {}).get("collection", ""),
            "resource_id": payload.get("target", {}).get("id"),
            "changes_json": payload.get("changes"),
        }
        await _audit_repo.create(event)
    except Exception:
        logger.warning("Audit SQL write failed", exc_info=True)


async def _log_tool_event(
    partner_id: str,
    tool_name: str,
    entity_id: str | None,
    query: str | None,
    result_count: int | None,
) -> None:
    """Write a single tool event row. Errors are logged as warnings only."""
    import zenos.interface.mcp as _mcp

    if _mcp._tool_event_repo is None:
        return
    try:
        await _mcp._tool_event_repo.log_tool_event(
            partner_id=partner_id,
            tool_name=tool_name,
            entity_id=entity_id,
            query=query,
            result_count=result_count,
        )
    except Exception:
        logger.warning("tool_event logging failed", exc_info=True)


def _schedule_tool_event(
    tool_name: str,
    entity_id: str | None,
    query: str | None,
    result_count: int | None,
) -> None:
    """Schedule a non-blocking tool event insert via asyncio.create_task."""
    from zenos.infrastructure.context import current_partner_id as _current_partner_id

    partner_id = _current_partner_id.get()
    if not partner_id:
        return
    try:
        asyncio.create_task(
            _log_tool_event(
                partner_id=partner_id,
                tool_name=tool_name,
                entity_id=entity_id,
                query=query,
                result_count=result_count,
            )
        )
    except RuntimeError:
        # No running event loop (e.g. tests not using asyncio)
        pass
