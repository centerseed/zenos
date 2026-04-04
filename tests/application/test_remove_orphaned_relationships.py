"""Tests for OntologyService.remove_orphaned_relationships().

Verifies:
- Orphaned relationships (source or target missing from entities) are detected and removed
- Non-orphaned relationships are preserved
- Returns correct count and removed list
- Gracefully handles repos without list_all
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from zenos.domain.models import Entity, EntityType, Relationship, Tags


def _make_entity(entity_id: str, name: str = "Test") -> Entity:
    return Entity(
        id=entity_id,
        name=name,
        type=EntityType.MODULE,
        summary="",
        tags=Tags(what=[], why="", how="", who=[]),
    )


def _make_rel(source_id: str, target_id: str, rel_type: str = "related_to") -> Relationship:
    return Relationship(
        id=f"{source_id}->{target_id}",
        source_entity_id=source_id,
        target_id=target_id,
        type=rel_type,
        description="",
    )


class FakeRelationshipRepo:
    def __init__(self, relationships: list[Relationship]):
        self._rels = relationships
        self._removed: list[tuple[str, str, str]] = []

    async def list_all(self) -> list[Relationship]:
        return list(self._rels)

    async def list_by_entity(self, entity_id: str) -> list[Relationship]:
        return [r for r in self._rels if r.source_entity_id == entity_id]

    async def find_duplicate(self, source_id: str, target_id: str, rel_type: str):
        return None

    async def add(self, rel: Relationship) -> Relationship:
        return rel

    async def remove(self, source_id: str, target_id: str, rel_type: str) -> bool:
        self._removed.append((source_id, target_id, rel_type))
        return True


class FakeEntityRepo:
    def __init__(self, entities: list[Entity]):
        self._entities = entities

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        if type_filter:
            return [e for e in self._entities if e.type == type_filter]
        return list(self._entities)


def _make_service(entities: list[Entity], relationships: list[Relationship]):
    """Create a minimal OntologyService with fake repos."""
    from zenos.application.ontology_service import OntologyService

    service = object.__new__(OntologyService)
    service._entities = FakeEntityRepo(entities)
    service._relationships = FakeRelationshipRepo(relationships)
    return service


class TestRemoveOrphanedRelationships:

    @pytest.mark.asyncio
    async def test_no_orphans_returns_empty(self):
        """When all relationship endpoints exist, returns count=0."""
        ent_a = _make_entity("ent-A")
        ent_b = _make_entity("ent-B")
        rel = _make_rel("ent-A", "ent-B")

        service = _make_service([ent_a, ent_b], [rel])
        result = await service.remove_orphaned_relationships()

        assert result["count"] == 0
        assert result["removed"] == []

    @pytest.mark.asyncio
    async def test_orphaned_target_is_removed(self):
        """Relationship pointing to a non-existent target is removed."""
        ent_a = _make_entity("ent-A")
        rel = _make_rel("ent-A", "non-existent")

        service = _make_service([ent_a], [rel])
        result = await service.remove_orphaned_relationships()

        assert result["count"] == 1
        assert result["removed"][0]["target_id"] == "non-existent"
        assert result["removed"][0]["reason"] == "target_missing"

    @pytest.mark.asyncio
    async def test_orphaned_source_is_removed(self):
        """Relationship with a non-existent source is removed."""
        ent_b = _make_entity("ent-B")
        rel = _make_rel("non-existent", "ent-B")

        service = _make_service([ent_b], [rel])
        result = await service.remove_orphaned_relationships()

        assert result["count"] == 1
        assert result["removed"][0]["source_entity_id"] == "non-existent"
        assert result["removed"][0]["reason"] == "source_missing"

    @pytest.mark.asyncio
    async def test_mixed_orphan_and_valid(self):
        """Only orphaned relationships are removed; valid ones are preserved."""
        ent_a = _make_entity("ent-A")
        ent_b = _make_entity("ent-B")
        valid_rel = _make_rel("ent-A", "ent-B")
        orphan_rel = _make_rel("ent-A", "ghost")

        service = _make_service([ent_a, ent_b], [valid_rel, orphan_rel])
        result = await service.remove_orphaned_relationships()

        assert result["count"] == 1
        assert result["removed"][0]["target_id"] == "ghost"

    @pytest.mark.asyncio
    async def test_no_list_all_returns_empty(self):
        """When relationship repo lacks list_all, returns empty result gracefully."""
        from zenos.application.ontology_service import OntologyService

        ent_a = _make_entity("ent-A")
        service = object.__new__(OntologyService)
        service._entities = FakeEntityRepo([ent_a])

        # repo without list_all
        minimal_repo = MagicMock()
        del minimal_repo.list_all
        service._relationships = minimal_repo

        result = await service.remove_orphaned_relationships()

        assert result == {"removed": [], "count": 0}
