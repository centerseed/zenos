"""MCP interface — common serialization and response helpers.

Contains:
- _serialize, _convert_datetimes
- _unified_response, _inject_workspace_context
- _new_id, _parse_entity_level
- _enrich_task_result, _build_context_bundle, _build_governance_hints
- _validate_id_format, _format_not_found (ID ergonomics helpers)
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from datetime import datetime

logger_name = __name__
import logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ID format validation helpers (SPEC-mcp-id-ergonomics AC-MIDE-01/02)
# ---------------------------------------------------------------------------

_VALID_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _validate_id_format(id_value: str | None) -> str | None:
    """Check ID format. Returns an error message string, or None if valid.

    A valid ID is exactly 32 lowercase hex characters (uuid4().hex format).
    Accepts None or empty string and returns "id is required" for both.
    """
    if id_value is None or id_value == "":
        return "id is required"
    if len(id_value) != 32:
        return (
            f"id length mismatch (expected 32, got {len(id_value)}). "
            "ID 必須為 32 字元 hex。若只記得前綴，請用 search(id_prefix=...) 或 "
            "get(id_prefix=...) 取完整 ID。"
        )
    if not _VALID_ID_RE.match(id_value.lower()):
        return (
            "id 含非 hex 字元。ID 必須為 32 字元 lowercase hex。"
            "請用 search(id_prefix=...) 確認。"
        )
    return None


_VALID_PREFIX_RE = re.compile(r"^[0-9a-f]{4,}$")


def _validate_id_prefix(prefix: str) -> str | None:
    """Validate an id_prefix value for prefix-match queries.

    Returns an error message if invalid, or None if the prefix is acceptable.
    Minimum 4 hex characters (16^4 = 65536 namespace, collision-safe for typical
    partner data volumes per SPEC-mcp-id-ergonomics §Risk).
    """
    if not prefix:
        return "id_prefix is required"
    if not _VALID_PREFIX_RE.match(prefix.lower()):
        if len(prefix) < 4:
            return (
                f"id_prefix 必須為 4+ 字元 hex（傳入長度 {len(prefix)}）。"
                "最少 4 字元以避免過多碰撞。"
            )
        return (
            f"id_prefix 含非 hex 字元。id_prefix 必須為純 lowercase hex（0-9, a-f）。"
        )
    return None


def _format_not_found(resource: str, id_value: str) -> str:
    """Build a unified not-found error message with ID format diagnostics.

    If the id_value has a format problem (wrong length or non-hex),
    the diagnostic hint is prepended so the caller knows immediately
    why the lookup failed.
    """
    hint = _validate_id_format(id_value)
    if hint:
        return f"{resource} '{id_value}' not found — {hint}"
    return (
        f"{resource} '{id_value}' not found. "
        f"請用 search(query=...) 或 search(id_prefix=...) 確認 ID 正確。"
    )


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
            "blocked": "todo",
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
    data: object,
    warnings: list[str] | None = None,
    suggestions: list[dict] | None = None,
    similar_items: list[dict] | None = None,
    context_bundle: dict | None = None,
    governance_hints: dict | None = None,
    rejection_reason: str | None = None,
    applied_filters: dict | None = None,
    completeness: str | None = None,
) -> dict:
    """Phase 1 unified response format for all MCP tool responses.

    applied_filters / completeness are additive behavior-contract fields
    (SPEC-mcp-tool-contract §5 INV3/INV4):

    - applied_filters: dict echoing server-side filters the caller should
      know excluded items (e.g. {"entity_level": {"input": "L1",
      "effective_max_level": 1, "included_types": ["product", "project",
      "goal", "role"]}, "visibility_applied": true}).
    - completeness: "partial" when result is ranked/threshold-trimmed and
      may omit existing items; "exhaustive" when result is guaranteed
      complete within the declared applied_filters (pagination still ok).
    """
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
    if applied_filters is not None:
        resp["applied_filters"] = applied_filters
    if completeness is not None:
        if completeness not in ("partial", "exhaustive"):
            raise ValueError(
                f"completeness must be 'partial' or 'exhaustive', got {completeness!r}"
            )
        resp["completeness"] = completeness

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


def _error_response(
    *,
    error_code: str,
    message: str,
    status: str = "error",
    warnings: list[str] | None = None,
    suggestions: list[dict] | None = None,
    similar_items: list[dict] | None = None,
    context_bundle: dict | None = None,
    governance_hints: dict | None = None,
    extra_data: dict | None = None,
) -> dict:
    """Build a unified non-ok response with machine-readable error fields."""
    data = {
        "error": error_code,
        "message": message,
        **(extra_data or {}),
    }
    return _unified_response(
        status=status,
        data=data,
        warnings=warnings,
        suggestions=suggestions,
        similar_items=similar_items,
        context_bundle=context_bundle,
        governance_hints=governance_hints,
        rejection_reason=message if status == "rejected" else None,
    )


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
