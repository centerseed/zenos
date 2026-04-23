"""Entity level defaults — SSOT for type-to-level mapping.

This module is intentionally zero-dependency: it imports nothing from the
domain model or any infrastructure layer.  It exists solely to define the
constant ``DEFAULT_TYPE_LEVELS`` that all layers can safely import without
creating circular dependencies.

Usage
-----
- ``backfill_entity_level.py``: infer level from type for NULL-level rows.
- ``application/crm/crm_service.py``: default level when CRM bridge creates an entity.
- ``application/knowledge/ontology_service.py``: canonical level lookup (ADR-047 S03).

Do **not** import ``EntityType``, domain models, or infrastructure here.
"""
from __future__ import annotations

DEFAULT_TYPE_LEVELS: dict[str, int] = {
    "product": 1,
    "company": 1,
    "person": 1,
    "deal": 1,
    "module": 2,
    "document": 3,
    "goal": 3,
    "role": 3,
    "project": 3,
}


def default_level_for_type(entity_type: str) -> int | None:
    """Return the default level for a given entity type string, or None if unknown.

    This is a pure lookup — it never raises, never defaults to an arbitrary
    integer for unknown types.  Callers that receive None must treat the entity
    as unresolvable and escalate to human review rather than guessing.

    Args:
        entity_type: The entity type string (e.g. ``"company"``, ``"module"``).

    Returns:
        The default level integer, or ``None`` if the type is not in
        ``DEFAULT_TYPE_LEVELS``.
    """
    return DEFAULT_TYPE_LEVELS.get(entity_type)
