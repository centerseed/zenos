from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from zenos.application.knowledge.ontology_service import OntologyService
from zenos.domain.knowledge import Entity, Tags


def _make_entity(
    *,
    entity_id: str,
    name: str,
    entity_type: str,
    parent_id: str | None = None,
) -> Entity:
    now = datetime.now(timezone.utc)
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
        summary=f"{name} summary",
        tags=Tags(what=["x"], why="y", how="z", who=["pm"]),
        status="active",
        parent_id=parent_id,
        confirmed_by_user=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_find_gaps_scope_product_uses_parent_chain_not_entity_product():
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()

    product = _make_entity(entity_id="prod-1", name="ZenOS", entity_type="product")
    module = _make_entity(entity_id="mod-1", name="Action Layer", entity_type="module", parent_id="prod-1")
    other_product = _make_entity(entity_id="prod-2", name="Other", entity_type="product")
    other_module = _make_entity(entity_id="mod-2", name="Other Module", entity_type="module", parent_id="prod-2")

    entity_repo.list_all = AsyncMock(return_value=[product, module, other_product, other_module])
    relationship_repo.find_orphan_entities = AsyncMock(return_value=[
        {"id": "mod-1", "name": "Action Layer", "type": "module", "level": 2},
        {"id": "mod-2", "name": "Other Module", "type": "module", "level": 2},
    ])
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

    service = OntologyService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        document_repo=AsyncMock(),
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    result = await service.find_gaps("orphan_entities", scope_product="ZenOS")

    assert result["total"] == 1
    assert result["gaps"][0]["entity_id"] == "mod-1"


@pytest.mark.asyncio
async def test_find_gaps_without_scope_still_returns_results():
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()

    module = _make_entity(entity_id="mod-1", name="Action Layer", entity_type="module")
    entity_repo.list_all = AsyncMock(return_value=[module])
    relationship_repo.find_orphan_entities = AsyncMock(return_value=[
        {"id": "mod-1", "name": "Action Layer", "type": "module", "level": 2},
    ])
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

    service = OntologyService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        document_repo=AsyncMock(),
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    result = await service.find_gaps("orphan_entities")

    assert result["total"] == 1
    assert result["gaps"][0]["entity_id"] == "mod-1"
