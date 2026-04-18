"""MCP interface — include parameter helpers for opt-in field projection.

ADR-040 Phase A: get/search support opt-in include parameter.
All include-related logic is centralised here; get.py and search.py must not
independently duplicate include resolution.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Valid include value sets
# ──────────────────────────────────────────────

VALID_ENTITY_INCLUDES: set[str] = {
    "summary",
    "relationships",
    "entries",
    "impact_chain",
    "sources",
    "all",
}

VALID_SEARCH_INCLUDES: set[str] = {
    "summary",
    "tags",
    "full",
}

# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────


def validate_include(
    include: list[str] | None,
    valid_set: set[str],
) -> tuple[set[str] | None, dict | None]:
    """Validate and normalise an include list.

    Returns:
        (None, None)                 — include is None → default / legacy path
        (set[str], None)             — all values valid → normalised include set
        (None, error_response_dict)  — at least one unknown value → error dict
    """
    from zenos.interface.mcp._common import _error_response

    if include is None:
        return None, None

    include_set = set(include)
    unknown = include_set - valid_set
    if unknown:
        sorted_supported = sorted(valid_set)
        return None, _error_response(
            status="rejected",
            error_code="INVALID_INCLUDE",
            message=(
                f"Unknown include value(s): {sorted(unknown)}. "
                f"Supported values: {sorted_supported}"
            ),
        )
    return include_set, None


# ──────────────────────────────────────────────
# Deprecation warning (structured log)
# ──────────────────────────────────────────────


def log_deprecation_warning(
    tool: str,
    collection: str,
    caller_id: str | None,
) -> None:
    """Emit a structured JSON deprecation warning to the server log.

    Format matches the TD structured-log spec so Cloud Run log explorer can
    aggregate by tool/collection/caller_id.
    """
    entry = {
        "event": "mcp_include_deprecation",
        "tool": tool,
        "collection": collection,
        "caller_id": caller_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": (
            "caller not using include, defaulting to full payload "
            "— this will change in ADR-040 Phase B"
        ),
    }
    logger.warning(json.dumps(entry))


# ──────────────────────────────────────────────
# Build helpers
# ──────────────────────────────────────────────


def build_entity_response(
    entity_dict: dict,
    relationships: list[dict] | None,
    entries: list[dict] | None,
    forward_impact: list[dict] | None,
    reverse_impact: list[dict] | None,
    include_set: set[str],
) -> dict:
    """Build a conditional entity response dict based on include_set.

    This function handles the selective include path only.  The "all" case
    (full eager dump) is handled directly in get.py and search.py to avoid
    duplicating the legacy serialisation logic.

    Args:
        entity_dict:    Already-serialised entity dict (output of _serialize on Entity).
        relationships:  Flat list of serialised Relationship dicts with an extra
                        "_direction" key ("outgoing" | "incoming") injected by caller.
        entries:        Serialised active entries sorted by updated_at DESC;
                        this function applies the limit=5 cap for "entries" mode.
        forward_impact: Serialised forward impact chain list.
        reverse_impact: Serialised reverse impact chain list.
        include_set:    Validated set of include values (must not contain "all").

    Returns a new dict with only the requested fields.
    """
    # Base: entity core fields + source_count (summary-only baseline)
    sources = entity_dict.get("sources") or []
    response: dict = {
        "id": entity_dict.get("id"),
        "name": entity_dict.get("name"),
        "type": entity_dict.get("type"),
        "level": entity_dict.get("level"),
        "status": entity_dict.get("status"),
        "summary": entity_dict.get("summary"),
        "tags": entity_dict.get("tags"),
        "owner": entity_dict.get("owner"),
        "confirmed_by_user": entity_dict.get("confirmed_by_user"),
        "parent_id": entity_dict.get("parent_id"),
        "source_count": len(sources),
    }

    if "relationships" in include_set and relationships is not None:
        response["outgoing_relationships"] = [
            r for r in relationships if r.get("_direction") == "outgoing"
        ]
        response["incoming_relationships"] = [
            r for r in relationships if r.get("_direction") == "incoming"
        ]

    if "entries" in include_set:
        # limit=5, entries should already be sorted DESC by caller
        response["active_entries"] = (entries or [])[:5]

    if "impact_chain" in include_set:
        response["impact_chain"] = forward_impact or []
        response["reverse_impact_chain"] = reverse_impact or []

    if "sources" in include_set:
        # Full sources array replaces source_count
        response.pop("source_count", None)
        response["sources"] = sources

    return response


def _summary_short(text: str | None) -> str:
    """Return the first 120 codepoints of text, with '…' suffix if truncated.

    Truncation is by codepoint (Python len()) per SPEC Architect ruling.
    """
    if not text:
        return ""
    if len(text) <= 120:
        return text
    return text[:120] + "…"


def build_search_result(
    entity_dict: dict,
    score: float,
    include_set: set[str] | None,
) -> dict:
    """Build a single search result dict based on include_set.

    Args:
        entity_dict: Already-serialised entity dict.
        score:       Search relevance score.
        include_set: Validated include set, or None for default legacy path.

    Returns a dict with only the fields permitted by include_set.
    """
    if include_set is None or "full" in include_set:
        # Default legacy path or explicit full: return full serialised entity + score
        result = dict(entity_dict)
        result["score"] = score
        return result

    # Summary baseline shape: {id, name, type, level, summary_short, score}
    result: dict = {
        "id": entity_dict.get("id"),
        "name": entity_dict.get("name"),
        "type": entity_dict.get("type"),
        "level": entity_dict.get("level"),
        "summary_short": _summary_short(entity_dict.get("summary")),
        "score": score,
    }

    if "tags" in include_set:
        result["tags"] = entity_dict.get("tags")

    return result
