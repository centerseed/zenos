"""MCP interface — common serialization and response helpers.

Contains:
- _serialize, _convert_datetimes
- _unified_response, _inject_workspace_context
- _new_id, _parse_entity_level
- _enrich_task_result, _build_context_bundle, _build_governance_hints
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime

logger_name = __name__
import logging
logger = logging.getLogger(__name__)


def _serialize(obj: object) -> dict:
    """Convert a dataclass instance to a JSON-safe dict.

    Handles nested dataclasses via ``dataclasses.asdict`` and converts
    ``datetime`` objects to ISO-8601 strings so the result is
    JSON-serializable.
    """
    raw = asdict(obj)  # type: ignore[arg-type]
    data = _convert_datetimes(raw)
    # Backward-compatible task status normalization
    if "created_by" in data and "priority_reason" in data and "status" in data:
        data["status"] = {
            "backlog": "todo",
            "blocked": "in_progress",
            "archived": "done",
        }.get(data["status"], data["status"])
        # Add proxy_url to attachments that have gcs_path
        if "attachments" in data and data["attachments"]:
            data["attachments"] = _add_proxy_urls(data["attachments"])
    return data


def _convert_datetimes(data: dict) -> dict:
    """Recursively convert datetime values to ISO-8601 strings."""
    out: dict = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, dict):
            out[key] = _convert_datetimes(value)
        elif isinstance(value, list):
            out[key] = [
                _convert_datetimes(v) if isinstance(v, dict)
                else v.isoformat() if isinstance(v, datetime)
                else v
                for v in value
            ]
        else:
            out[key] = value
    return out


def _add_proxy_urls(attachments: list[dict]) -> list[dict]:
    """Add proxy_url to attachment items that have a gcs_path."""
    result = []
    for att in attachments:
        att_copy = dict(att)
        if att_copy.get("gcs_path"):
            att_copy["proxy_url"] = f"/attachments/{att_copy['id']}"
        result.append(att_copy)
    return result


def _unified_response(
    *,
    status: str = "ok",
    data: dict,
    warnings: list[str] | None = None,
    suggestions: list[dict] | None = None,
    similar_items: list[dict] | None = None,
    context_bundle: dict | None = None,
    governance_hints: dict | None = None,
    rejection_reason: str | None = None,
) -> dict:
    """Phase 1 unified response format for all MCP tool responses."""
    from zenos.interface.mcp._auth import _current_partner
    from zenos.infrastructure.context import current_partner_id as _current_partner_id
    from zenos.application.identity.workspace_context import build_workspace_context_sync

    resp: dict = {
        "status": status,
        "data": data,
        "warnings": warnings or [],
        "suggestions": suggestions or [],
        "similar_items": similar_items or [],
        "context_bundle": context_bundle or {},
        "governance_hints": governance_hints or {},
    }
    if rejection_reason is not None:
        resp["rejection_reason"] = rejection_reason

    # Inject workspace_context when a partner is authenticated
    partner = _current_partner.get()
    if partner:
        active_ws = _current_partner_id.get() or str(partner["id"])
        from zenos.interface.mcp._auth import _original_shared_partner_id
        resp["workspace_context"] = build_workspace_context_sync(
            partner, active_ws,
            original_shared_id=_original_shared_partner_id.get(),
        )

    return resp


def _inject_workspace_context(result: dict) -> dict:
    """Inject workspace_context into any dict response that doesn't go through _unified_response."""
    from zenos.interface.mcp._auth import _current_partner
    from zenos.infrastructure.context import current_partner_id as _current_partner_id
    from zenos.application.identity.workspace_context import build_workspace_context_sync

    partner = _current_partner.get()
    if partner:
        active_ws = _current_partner_id.get() or str(partner["id"])
        from zenos.interface.mcp._auth import _original_shared_partner_id
        result["workspace_context"] = build_workspace_context_sync(
            partner, active_ws,
            original_shared_id=_original_shared_partner_id.get(),
        )
    return result


def _new_id() -> str:
    """Generate a short unique ID (32-char hex UUID4)."""
    return uuid.uuid4().hex


def _parse_entity_level(entity_level: str | None) -> int | None:
    """Convert entity_level string to max_level int for domain layer.

    Returns:
        None  — no filtering (caller explicitly asked for "all" or "L1,L2,L3")
        1     — L1 only
        2     — L1+L2 (default when entity_level is not provided)
    """
    if entity_level is None:
        # Default: L1+L2 only
        return 2

    normalized = entity_level.strip().lower()
    if normalized in ("all", "l1,l2,l3", "l3"):
        return None
    if normalized == "l1":
        return 1
    if normalized in ("l2", "l1,l2"):
        return 2
    # Unrecognized → fall back to default L1+L2
    return 2


def _build_governance_hints(
    *,
    warnings: list[str] | None = None,
    suggested_follow_up_tasks: list[dict] | None = None,
    similar_items: list[dict] | None = None,
    stale_candidates: list[dict] | None = None,
    suggested_entity_updates: list[dict] | None = None,
    health_signal: dict | None = None,
) -> dict:
    """Return additive governance hints for caller guidance."""
    warnings = warnings or []
    lowered = " ".join(warnings).lower()
    duplicate_signals = []
    if "duplicate" in lowered or "重複" in lowered:
        duplicate_signals.append("possible_duplicate")

    hints: dict = {
        "duplicate_signals": duplicate_signals,
        "stale_candidates": stale_candidates or [],
        "suggested_follow_up_tasks": suggested_follow_up_tasks or [],
        "similar_items": similar_items or [],
        "suggested_entity_updates": suggested_entity_updates or [],
    }
    if health_signal is not None:
        hints["health_signal"] = health_signal
    return hints


async def _enrich_task_result(task_obj) -> dict:
    """Serialize a task and apply enrichment (expanded entities/role/blindspot)."""
    import zenos.interface.mcp as _mcp
    task_dict = _serialize(task_obj)
    enr = await _mcp.task_service.enrich_task(task_obj)
    task_dict["linked_entities"] = enr["expanded_entities"]
    if "assignee_role" in enr:
        task_dict["assignee_role"] = enr["assignee_role"]
    if "blindspot_detail" in enr:
        task_dict["blindspot_detail"] = enr["blindspot_detail"]
    return task_dict


async def _build_context_bundle(
    *,
    linked_entity_ids: list[str] | None = None,
    protocol_id: str | None = None,
    blindspot_id: str | None = None,
    limit: int = 5,
) -> dict:
    """Build a compact context bundle for write/confirm/search responses."""
    import zenos.interface.mcp as _mcp
    from zenos.interface.mcp._visibility import _is_entity_visible, _is_protocol_visible, _is_blindspot_visible

    bundle: dict = {
        "entities": [],
        "protocol": None,
        "blindspot": None,
    }

    seen: set[str] = set()
    for eid in linked_entity_ids or []:
        if not eid or eid in seen:
            continue
        seen.add(eid)
        if _mcp.entity_repo is None:
            continue
        entity = await _mcp.entity_repo.get_by_id(eid)
        if entity is None or not _is_entity_visible(entity):
            continue
        bundle["entities"].append(
            {
                "id": entity.id,
                "name": entity.name,
                "summary": entity.summary,
                "status": entity.status,
                "type": entity.type,
            }
        )
        if len(bundle["entities"]) >= limit:
            break

    if protocol_id:
        if _mcp.protocol_repo is None:
            return bundle
        proto = await _mcp.protocol_repo.get_by_id(protocol_id)
        if proto and await _is_protocol_visible(proto):
            bundle["protocol"] = {
                "id": proto.id,
                "entity_id": proto.entity_id,
                "entity_name": proto.entity_name,
            }

    if blindspot_id:
        if _mcp.blindspot_repo is None:
            return bundle
        bs = await _mcp.blindspot_repo.get_by_id(blindspot_id)
        if bs and await _is_blindspot_visible(bs):
            bundle["blindspot"] = {
                "id": bs.id,
                "severity": bs.severity,
                "description": bs.description,
            }

    return bundle
