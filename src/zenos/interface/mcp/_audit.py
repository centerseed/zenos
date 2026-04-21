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
import hashlib
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Lazily initialized audit repo (populated on first use)
_audit_repo = None

_SENSITIVE_KEYS = frozenset({
    "content",
    "query",
    "prompt",
    "body",
    "markdown",
    "snapshot_summary",
    "raw_content",
    "raw_query",
    "raw_prompt",
})


def _redacted_marker(value: object) -> dict:
    """Return a stable redaction marker that preserves debug value without content."""
    if isinstance(value, str):
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return {
            "redacted": True,
            "type": "str",
            "len": len(value),
            "sha256_12": digest,
        }
    if isinstance(value, list):
        return {"redacted": True, "type": "list", "len": len(value)}
    if isinstance(value, dict):
        return {"redacted": True, "type": "dict", "keys": sorted(value.keys())[:10]}
    return {"redacted": True, "type": type(value).__name__}


def _sanitize_payload(value: object, *, key: str | None = None) -> object:
    """Recursively sanitize audit payloads before logging or SQL persistence."""
    if key and key.lower() in _SENSITIVE_KEYS:
        return _redacted_marker(value)
    if isinstance(value, dict):
        return {
            str(k): _sanitize_payload(v, key=str(k))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_payload(item, key=key) for item in value]
    return value


def _redact_query(query: str | None) -> str | None:
    """Store query fingerprint instead of raw text in tool-event telemetry."""
    if not query:
        return query
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
    return f"[redacted len={len(query)} sha256_12={digest}]"


def _audit_log(
    event_type: str,
    target: dict,
    changes: dict | None = None,
    governance: dict | None = None,
) -> None:
    """Emit structured governance audit logs to stdout/Cloud Logging + SQL."""
    from zenos.interface.mcp._auth import _current_partner

    partner = _current_partner.get() or {}
    sanitized_changes = _sanitize_payload(changes or {})
    sanitized_governance = _sanitize_payload(governance or {})
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
        "changes": sanitized_changes,
        "governance": sanitized_governance,
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
            query=_redact_query(query),
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
