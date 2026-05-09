from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from zenos.domain.knowledge import Entity, Relationship, Tags
from zenos.interface.mcp.search import search


def _entity(
    eid: str,
    *,
    name: str = "Training Plan",
    entity_type: str = "module",
    level: int = 2,
    parent_id: str | None = None,
    summary: str = "Training plan module",
    status: str = "active",
    sources: list[dict] | None = None,
    doc_role: str | None = None,
    bundle_highlights: list[dict] | None = None,
) -> Entity:
    return Entity(
        id=eid,
        name=name,
        type=entity_type,
        level=level,
        parent_id=parent_id,
        status=status,
        summary=summary,
        tags=Tags(what=["training"], why="retrieval", how="graph", who=["agent"]),
        confirmed_by_user=True,
        owner="Barry",
        sources=sources or [],
        visibility="public",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        doc_role=doc_role,
        bundle_highlights=bundle_highlights or [],
    )


class _EntityRepo:
    def __init__(self, entities: dict[str, Entity]) -> None:
        self.entities = entities

    async def list_by_parent(self, parent_id: str) -> list[Entity]:
        return [entity for entity in self.entities.values() if entity.parent_id == parent_id]

    async def get_by_id(self, entity_id: str) -> Entity | None:
        return self.entities.get(entity_id)


class _RelationshipRepo:
    def __init__(self, relationships: list[Relationship]) -> None:
        self.relationships = relationships

    async def list_by_entity(self, entity_id: str) -> list[Relationship]:
        return [
            rel for rel in self.relationships
            if rel.source_entity_id == entity_id or rel.target_id == entity_id
        ]


@pytest.mark.asyncio
async def test_search_entities_documents_include_returns_primary_and_related_l3_docs():
    module = _entity("mod-training")
    primary_doc = _entity(
        "doc-primary",
        name="Beginner Plan Index",
        entity_type="document",
        level=3,
        parent_id=module.id,
        summary="Routes beginner 5K and 10K schedule questions.",
        status="current",
        doc_role="index",
        sources=[{
            "source_id": "src-primary",
            "uri": "/docs/doc-primary",
            "label": "Beginner plan snapshot",
            "type": "zenos_native",
            "is_primary": True,
            "source_status": "valid",
        }],
        bundle_highlights=[{
            "source_id": "src-primary",
            "headline": "Beginner 5K/10K routing",
            "priority": "primary",
        }],
    )
    related_doc = _entity(
        "doc-related",
        name="Training API Guide",
        entity_type="document",
        level=3,
        parent_id="mod-api",
        summary="Explains target_type=beginner and methodology_id=complete_10k.",
        status="current",
        doc_role="index",
        sources=[{
            "source_id": "src-api",
            "uri": "https://github.com/example/repo/blob/main/TRAINING_V2_API_INTEGRATION_GUIDE.md",
            "label": "TRAINING_V2_API_INTEGRATION_GUIDE.md",
            "type": "github",
            "is_primary": True,
            "source_status": "valid",
        }],
        bundle_highlights=[{
            "source_id": "src-api",
            "headline": "API contract for beginner plans",
            "priority": "primary",
        }],
    )
    entities = {
        module.id: module,
        primary_doc.id: primary_doc,
        related_doc.id: related_doc,
    }
    related_edge = Relationship(
        id="rel-related",
        source_entity_id=related_doc.id,
        target_id=module.id,
        type="related_to",
        description="document linked to entity",
    )
    entity_repo = _EntityRepo(entities)
    relationship_repo = _RelationshipRepo([related_edge])
    ontology_service = AsyncMock()
    ontology_service.list_entities = AsyncMock(return_value=[module])
    ontology_service._entities = entity_repo
    ontology_service._relationships = relationship_repo

    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.search_service", new=None), \
         patch("zenos.interface.mcp.ontology_service", new=ontology_service), \
         patch("zenos.interface.mcp.search._load_document_delivery_states", new=AsyncMock(return_value={})):
        result = await search(
            collection="entities",
            query="training",
            entity_level="L2",
            include=["summary", "documents"],
        )

    assert result["status"] == "ok"
    item = result["data"]["entities"][0]
    assert item["id"] == module.id
    assert "documents" in item
    assert [doc["id"] for doc in item["documents"]] == ["doc-primary", "doc-related"]
    assert item["documents"][0]["bundle_highlights"][0]["headline"] == "Beginner 5K/10K routing"
    assert item["documents"][1]["primary_source"]["label"] == "TRAINING_V2_API_INTEGRATION_GUIDE.md"
