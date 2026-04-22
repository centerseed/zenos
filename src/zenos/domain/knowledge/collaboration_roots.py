from __future__ import annotations

from zenos.domain.knowledge.enums import EntityType


COLLABORATION_ROOT_TYPES = {
    EntityType.PRODUCT.value,
    EntityType.COMPANY.value,
}


def is_collaboration_root_entity(entity: object | None) -> bool:
    if entity is None:
        return False
    entity_type = getattr(entity, "type", None)
    parent_id = getattr(entity, "parent_id", getattr(entity, "parentId", None))
    level = getattr(entity, "level", None)
    return entity_type in COLLABORATION_ROOT_TYPES and not parent_id and (level == 1 or level is None)
