"""Home workspace bootstrap service.

Copies selected shared `product(L1)` subtrees into the caller's home workspace
as owned copies. P0 scope only handles public entities + relationships.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from zenos.domain.knowledge import Entity, Relationship
from zenos.infrastructure.context import current_partner_id


@dataclass
class HomeWorkspaceBootstrapResult:
    applied_source_entity_ids: list[str]
    copied_root_entity_ids: list[str]
    copied_entity_count: int
    copied_relationship_count: int
    skipped_source_entity_ids: list[str]


def _collect_subtree_ids(root_id: str, entity_map: dict[str, Entity]) -> set[str]:
    seen: set[str] = set()
    stack = [root_id]
    while stack:
        current_id = stack.pop()
        if current_id in seen:
            continue
        seen.add(current_id)
        for entity in entity_map.values():
            if entity.parent_id == current_id and entity.id:
                stack.append(entity.id)
    return seen


def _is_public_path(entity_id: str, entity_map: dict[str, Entity], allowed_ids: set[str]) -> bool:
    current_id = entity_id
    visited: set[str] = set()
    while current_id and current_id in allowed_ids:
        if current_id in visited:
            return False
        visited.add(current_id)
        entity = entity_map.get(current_id)
        if entity is None or entity.visibility != "public":
            return False
        current_id = entity.parent_id or ""
    return True


def _entity_depth(entity: Entity, entity_map: dict[str, Entity]) -> int:
    depth = 0
    current_id = entity.parent_id
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        current = entity_map.get(current_id)
        if current is None:
            break
        depth += 1
        current_id = current.parent_id
    return depth


class HomeWorkspaceBootstrapService:
    def __init__(self, entity_repo, relationship_repo) -> None:
        self._entity_repo = entity_repo
        self._relationship_repo = relationship_repo

    async def _list_entities(self, workspace_id: str) -> list[Entity]:
        token = current_partner_id.set(workspace_id)
        try:
            return await self._entity_repo.list_all()
        finally:
            current_partner_id.reset(token)

    async def _list_relationships(self, workspace_id: str) -> list[Relationship]:
        token = current_partner_id.set(workspace_id)
        try:
            return await self._relationship_repo.list_all()
        finally:
            current_partner_id.reset(token)

    async def _upsert_entity(self, workspace_id: str, entity: Entity) -> Entity:
        token = current_partner_id.set(workspace_id)
        try:
            return await self._entity_repo.upsert(entity)
        finally:
            current_partner_id.reset(token)

    async def _find_duplicate_relationship(
        self,
        workspace_id: str,
        source_entity_id: str,
        target_entity_id: str,
        rel_type: str,
    ) -> Relationship | None:
        token = current_partner_id.set(workspace_id)
        try:
            return await self._relationship_repo.find_duplicate(source_entity_id, target_entity_id, rel_type)
        finally:
            current_partner_id.reset(token)

    async def _add_relationship(self, workspace_id: str, rel: Relationship) -> Relationship:
        token = current_partner_id.set(workspace_id)
        try:
            return await self._relationship_repo.add(rel)
        finally:
            current_partner_id.reset(token)

    async def apply(
        self,
        *,
        source_workspace_id: str,
        target_workspace_id: str,
        source_root_entity_ids: list[str],
    ) -> HomeWorkspaceBootstrapResult:
        source_entities = await self._list_entities(source_workspace_id)
        source_relationships = await self._list_relationships(source_workspace_id)
        target_entities = await self._list_entities(target_workspace_id)

        source_entity_map = {entity.id: entity for entity in source_entities if entity.id}
        target_by_origin = {}
        for entity in target_entities:
            if not entity.id:
                continue
            details = entity.details or {}
            origin = details.get("bootstrap_origin") if isinstance(details, dict) else None
            if not isinstance(origin, dict):
                continue
            source_entity_id = str(origin.get("source_entity_id") or "").strip()
            source_workspace = str(origin.get("source_workspace_id") or "").strip()
            if source_entity_id and source_workspace:
                target_by_origin[(source_workspace, source_entity_id)] = entity

        now_iso = datetime.now(timezone.utc).isoformat()
        source_ids_to_copy: set[str] = set()
        source_root_by_entity_id: dict[str, str] = {}
        valid_root_ids: list[str] = []
        skipped_source_ids: list[str] = []

        for root_id in source_root_entity_ids:
            root = source_entity_map.get(root_id)
            if root is None or root.type != "product" or not root.id:
                skipped_source_ids.append(root_id)
                continue
            subtree_ids = _collect_subtree_ids(root.id, source_entity_map)
            copyable_ids = {
                entity_id
                for entity_id in subtree_ids
                if _is_public_path(entity_id, source_entity_map, subtree_ids)
            }
            if root.id not in copyable_ids:
                skipped_source_ids.append(root_id)
                continue
            valid_root_ids.append(root.id)
            source_ids_to_copy |= copyable_ids
            for entity_id in copyable_ids:
                source_root_by_entity_id.setdefault(entity_id, root.id)

        sorted_entities = sorted(
            (source_entity_map[entity_id] for entity_id in source_ids_to_copy if entity_id in source_entity_map),
            key=lambda entity: _entity_depth(entity, source_entity_map),
        )

        source_to_target_id: dict[str, str] = {}
        copied_entity_count = 0
        copied_root_entity_ids: list[str] = []
        applied_source_entity_ids: list[str] = []

        for source_entity in sorted_entities:
            if not source_entity.id:
                continue
            existing = target_by_origin.get((source_workspace_id, source_entity.id))
            parent_id = (
                source_to_target_id.get(source_entity.parent_id)
                if source_entity.parent_id and source_entity.parent_id in source_ids_to_copy
                else None
            )
            source_root_entity_id = source_root_by_entity_id.get(source_entity.id, source_entity.id)
            if existing and existing.id:
                source_to_target_id[source_entity.id] = existing.id
                if source_entity.id in valid_root_ids:
                    copied_root_entity_ids.append(existing.id)
                    applied_source_entity_ids.append(source_entity.id)
                continue

            details = dict(source_entity.details or {})
            details["bootstrap_origin"] = {
                "source_workspace_id": source_workspace_id,
                "source_entity_id": source_entity.id,
                "source_root_entity_id": source_root_entity_id,
                "bootstrap_applied_at": now_iso,
            }
            entity_to_save = existing or Entity(
                name=source_entity.name,
                type=source_entity.type,
                summary=source_entity.summary,
                tags=source_entity.tags,
                level=source_entity.level,
                status=source_entity.status,
                parent_id=parent_id,
                details=details,
                confirmed_by_user=False,
                owner=source_entity.owner,
                sources=list(source_entity.sources),
                visibility=source_entity.visibility,
                visible_to_roles=list(source_entity.visible_to_roles),
                visible_to_members=list(source_entity.visible_to_members),
                visible_to_departments=list(source_entity.visible_to_departments),
                doc_role=source_entity.doc_role,
                bundle_highlights=list(source_entity.bundle_highlights),
                highlights_updated_at=source_entity.highlights_updated_at,
                change_summary=source_entity.change_summary,
                summary_updated_at=source_entity.summary_updated_at,
            )
            entity_to_save.name = source_entity.name
            entity_to_save.type = source_entity.type
            entity_to_save.summary = source_entity.summary
            entity_to_save.tags = source_entity.tags
            entity_to_save.level = source_entity.level
            entity_to_save.status = source_entity.status
            entity_to_save.parent_id = parent_id
            entity_to_save.details = details
            entity_to_save.confirmed_by_user = False
            entity_to_save.owner = source_entity.owner
            entity_to_save.sources = list(source_entity.sources)
            entity_to_save.visibility = source_entity.visibility
            entity_to_save.visible_to_roles = list(source_entity.visible_to_roles)
            entity_to_save.visible_to_members = list(source_entity.visible_to_members)
            entity_to_save.visible_to_departments = list(source_entity.visible_to_departments)
            entity_to_save.doc_role = source_entity.doc_role
            entity_to_save.bundle_highlights = list(source_entity.bundle_highlights)
            entity_to_save.highlights_updated_at = source_entity.highlights_updated_at
            entity_to_save.change_summary = source_entity.change_summary
            entity_to_save.summary_updated_at = source_entity.summary_updated_at

            saved = await self._upsert_entity(target_workspace_id, entity_to_save)
            if not saved.id:
                continue
            source_to_target_id[source_entity.id] = saved.id
            copied_entity_count += 1
            if source_entity.id in valid_root_ids:
                copied_root_entity_ids.append(saved.id)
                applied_source_entity_ids.append(source_entity.id)

        copied_relationship_count = 0
        for rel in source_relationships:
            if rel.source_entity_id not in source_ids_to_copy or rel.target_id not in source_ids_to_copy:
                continue
            mapped_source = source_to_target_id.get(rel.source_entity_id)
            mapped_target = source_to_target_id.get(rel.target_id)
            if not mapped_source or not mapped_target:
                continue
            existing = await self._find_duplicate_relationship(
                target_workspace_id,
                mapped_source,
                mapped_target,
                rel.type,
            )
            if existing:
                continue
            rel_to_save = Relationship(
                id=None,
                source_entity_id=mapped_source,
                target_id=mapped_target,
                type=rel.type,
                description=rel.description,
                confirmed_by_user=False,
            )
            await self._add_relationship(target_workspace_id, rel_to_save)
            copied_relationship_count += 1

        return HomeWorkspaceBootstrapResult(
            applied_source_entity_ids=applied_source_entity_ids,
            copied_root_entity_ids=copied_root_entity_ids,
            copied_entity_count=copied_entity_count,
            copied_relationship_count=copied_relationship_count,
            skipped_source_entity_ids=skipped_source_ids,
        )
