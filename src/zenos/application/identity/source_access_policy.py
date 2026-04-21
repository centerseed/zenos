"""Source access policy helpers shared by MCP and Dashboard surfaces.

This module centralizes two governed-access concerns:
1. connector scope allowlists (workspace-boundary for external sources)
2. retrieval mode semantics (shared snapshot vs per-user live retrieval)
"""

from __future__ import annotations

from typing import Iterable


EXTERNAL_CONNECTOR_TYPES = frozenset({"github", "gdrive", "notion", "wiki"})
VALID_RETRIEVAL_MODES = frozenset({"direct", "snapshot", "per_user_live"})


def _partner_preferences(partner: dict | None) -> dict:
    if not partner:
        return {}
    prefs = partner.get("preferences")
    return prefs if isinstance(prefs, dict) else {}


def _connector_scopes(partner: dict | None) -> dict:
    prefs = _partner_preferences(partner)
    raw = prefs.get("connectorScopes")
    if isinstance(raw, dict):
        return raw
    raw = partner.get("connectorScopes") if partner else None
    return raw if isinstance(raw, dict) else {}


def _normalize_ids(raw: object) -> list[str]:
    if isinstance(raw, str):
        value = raw.strip()
        return [value] if value else []
    if isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray, dict)):
        values: list[str] = []
        for item in raw:
            value = str(item or "").strip()
            if value:
                values.append(value)
        return values
    return []


def source_container_ids(source: dict) -> list[str]:
    """Return normalized container identifiers for a source."""
    for key in ("container_ids", "containers", "container_id", "container"):
        ids = _normalize_ids(source.get(key))
        if ids:
            return ids
    return []


def source_scope_config(partner: dict | None, source_type: str) -> dict | None:
    scopes = _connector_scopes(partner)
    config = scopes.get(str(source_type or "").strip().lower())
    return config if isinstance(config, dict) else None


def is_source_in_connector_scope(source: dict, partner: dict | None) -> bool:
    """Check whether an external source is within the active workspace allowlist.

    Semantics:
    - no connector scope config for this source type -> allow (legacy compatibility)
    - config present with empty containers -> deny all for that connector
    - config present and source has no container_id(s) -> deny (cannot prove scope)
    - otherwise any intersection with allowlist -> allow
    """
    source_type = str(source.get("type", "") or "").strip().lower()
    if source_type not in EXTERNAL_CONNECTOR_TYPES:
        return True

    config = source_scope_config(partner, source_type)
    if config is None:
        return True

    allowed = _normalize_ids(
        config.get("containers", config.get("allowed_containers"))
    )
    if not allowed:
        return False

    containers = source_container_ids(source)
    if not containers:
        return False
    return any(container in set(allowed) for container in containers)


def filter_sources_for_partner(sources: list[dict] | None, partner: dict | None) -> list[dict]:
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict) and is_source_in_connector_scope(source, partner)]


def entity_has_visible_source(entity: object, partner: dict | None) -> bool:
    sources = getattr(entity, "sources", None)
    if not isinstance(sources, list) or not sources:
        return True
    return bool(filter_sources_for_partner(sources, partner))


def normalized_retrieval_mode(source: dict) -> str:
    raw = str(
        source.get("retrieval_mode")
        or source.get("read_mode")
        or ""
    ).strip().lower()
    if raw:
        return raw if raw in VALID_RETRIEVAL_MODES else "snapshot"

    source_type = str(source.get("type", "") or "").strip().lower()
    if source_type in {"github", "zenos_native"}:
        return "direct"
    return "snapshot"
