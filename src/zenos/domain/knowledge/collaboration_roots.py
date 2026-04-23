from __future__ import annotations


def is_collaboration_root_entity(entity: object | None) -> bool:
    """Return True iff the entity is a collaboration root (L1).

    An entity is L1 when level == 1 AND parent_id is absent or empty.
    Type is irrelevant — any EntityType label is valid for L1 (ADR-047 D2).

    Args:
        entity: Any object with optional ``level`` and ``parent_id``/``parentId``
                attributes, or None.

    Returns:
        True if the entity is a valid L1 collaboration root.
    """
    if entity is None:
        return False
    level = getattr(entity, "level", None)
    parent_id = getattr(entity, "parent_id", getattr(entity, "parentId", None))
    return level == 1 and not parent_id
