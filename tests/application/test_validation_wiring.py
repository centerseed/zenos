"""Tests for validation wiring into task_service and ontology_service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.action.task_service import TaskService
from zenos.application.knowledge.ontology_service import OntologyService, UpsertEntityResult
from zenos.domain.action import Task
from zenos.domain.knowledge import Entity, EntityType, Tags


# ──────────────────────────────────────────────
# TaskService.create_task — title validation
# ──────────────────────────────────────────────

def _make_task_service() -> TaskService:
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.list_all = AsyncMock(return_value=[])
    blindspot_repo = AsyncMock()
    return TaskService(task_repo, entity_repo, blindspot_repo)


@pytest.mark.asyncio
async def test_create_task_rejects_title_too_short():
    svc = _make_task_service()
    with pytest.raises(ValueError, match="Task title 驗證失敗"):
        await svc.create_task({"title": "Fix", "created_by": "u1"})


@pytest.mark.asyncio
async def test_create_task_rejects_title_starting_with_stopword():
    svc = _make_task_service()
    with pytest.raises(ValueError, match="Task title 驗證失敗"):
        await svc.create_task({"title": "Task to fix login bug", "created_by": "u1"})


@pytest.mark.asyncio
async def test_create_task_accepts_valid_title():
    svc = _make_task_service()
    result = await svc.create_task({"title": "Implement OAuth login flow", "created_by": "u1"})
    assert result.task.title == "Implement OAuth login flow"


@pytest.mark.asyncio
async def test_create_task_rejects_empty_title():
    svc = _make_task_service()
    with pytest.raises(ValueError, match="Task title 驗證失敗"):
        await svc.create_task({"title": "", "created_by": "u1"})


# ──────────────────────────────────────────────
# OntologyService.upsert_entity — similar_items
# ──────────────────────────────────────────────

def _make_entity(id: str, name: str) -> Entity:
    return Entity(
        id=id,
        name=name,
        type=EntityType.PRODUCT,
        summary="test",
        tags=Tags(what=[], why="", how="", who=[]),
        status="active",
    )


def _make_ontology_service(existing_entities: list[Entity]) -> OntologyService:
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.get_by_name = AsyncMock(return_value=None)

    async def _list_all(type_filter=None, **kwargs):
        if type_filter:
            return [e for e in existing_entities if e.type == type_filter]
        return existing_entities

    entity_repo.list_all = _list_all
    entity_repo.list_by_parent = AsyncMock(return_value=[])
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)

    rel_repo = AsyncMock()
    rel_repo.list_by_entity = AsyncMock(return_value=[])
    rel_repo.list_all = AsyncMock(return_value=[])
    rel_repo.upsert = AsyncMock(side_effect=lambda r: r)
    rel_repo.get_by_source_target_type = AsyncMock(return_value=None)

    doc_repo = AsyncMock()
    doc_repo.list_all = AsyncMock(return_value=[])

    protocol_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = OntologyService(
        entity_repo=entity_repo,
        relationship_repo=rel_repo,
        document_repo=doc_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )
    return svc


@pytest.mark.asyncio
async def test_upsert_entity_similar_items_returned_when_similar_exists():
    # "Payment Auth Service" and "Payment Auth Services" share 3/4 words → Jaccard ≥ 0.4
    existing = [_make_entity("e1", "Payment Auth Service")]
    svc = _make_ontology_service(existing)

    # force=True bypasses the duplicate guard; similar_items should still be populated
    data = {
        "name": "Payment Auth Services",
        "type": EntityType.PRODUCT,
        "summary": "handles payments",
        "tags": {"what": "payments", "why": "revenue", "how": "api", "who": "finance"},
        "force": True,
    }
    result = await svc.upsert_entity(data)
    assert isinstance(result, UpsertEntityResult)
    assert result.similar_items is not None
    names = [s["name"] for s in result.similar_items]
    assert "Payment Auth Service" in names


@pytest.mark.asyncio
async def test_upsert_entity_similar_items_none_when_no_match():
    existing = [_make_entity("e1", "Completely Unrelated Thing")]
    svc = _make_ontology_service(existing)

    data = {
        "name": "OAuth Login Flow",
        "type": EntityType.PRODUCT,
        "summary": "handles login",
        "tags": {"what": "payments", "why": "revenue", "how": "api", "who": "finance"},
    }
    result = await svc.upsert_entity(data)
    # similar_items should be None or empty when nothing crosses threshold
    assert result.similar_items is None or result.similar_items == []


@pytest.mark.asyncio
async def test_upsert_entity_similar_items_excludes_self_on_update():
    """When updating an entity, it should not appear in its own similar_items."""
    entity = _make_entity("e1", "Payment Service")
    existing = [entity, _make_entity("e2", "Billing Service")]

    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=entity)
    entity_repo.list_all = AsyncMock(return_value=existing)
    entity_repo.list_by_parent = AsyncMock(return_value=[])
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)

    rel_repo = AsyncMock()
    rel_repo.list_by_entity = AsyncMock(return_value=[])
    rel_repo.list_all = AsyncMock(return_value=[])
    rel_repo.upsert = AsyncMock(side_effect=lambda r: r)
    rel_repo.get_by_source_target_type = AsyncMock(return_value=None)

    doc_repo = AsyncMock()
    doc_repo.list_all = AsyncMock(return_value=[])

    svc = OntologyService(
        entity_repo=entity_repo,
        relationship_repo=rel_repo,
        document_repo=doc_repo,
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    data = {
        "id": "e1",
        "name": "Payment Service",
        "type": EntityType.PRODUCT,
        "summary": "updated summary",
        "tags": {"what": "payments", "why": "revenue", "how": "api", "who": "finance"},
    }
    result = await svc.upsert_entity(data)
    if result.similar_items:
        ids = [s["id"] for s in result.similar_items]
        assert "e1" not in ids
