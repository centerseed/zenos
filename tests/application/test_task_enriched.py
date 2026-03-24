"""Tests for TaskService.get_task_enriched and enriched create_task behaviour.

Unit tests mock all repositories — no Firestore dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.task_service import TaskService
from zenos.domain.models import Blindspot, Entity, Tags, Task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_repo(task: Task | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=task)
    repo.upsert = AsyncMock(side_effect=lambda t: t)
    repo.list_all = AsyncMock(return_value=[])
    repo.list_blocked_by = AsyncMock(return_value=[])
    repo.list_pending_review = AsyncMock(return_value=[])
    return repo


def _make_entity_repo(entity: Entity | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=entity)
    repo.list_all = AsyncMock(return_value=[])
    repo.list_by_parent = AsyncMock(return_value=[])
    return repo


def _make_blindspot_repo(blindspot: Blindspot | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=blindspot)
    return repo


def _make_service(
    task: Task | None = None,
    entity: Entity | None = None,
    blindspot: Blindspot | None = None,
    entity_side_effect=None,
) -> TaskService:
    task_repo = _make_task_repo(task)
    entity_repo = _make_entity_repo(entity)
    if entity_side_effect is not None:
        entity_repo.get_by_id = AsyncMock(side_effect=entity_side_effect)
    blindspot_repo = _make_blindspot_repo(blindspot)
    return TaskService(
        task_repo=task_repo,
        entity_repo=entity_repo,
        blindspot_repo=blindspot_repo,
    )


def _entity(id: str = "ent-1", name: str = "Paceriz", summary: str = "A running coach") -> Entity:
    return Entity(
        id=id,
        name=name,
        type="product",
        summary=summary,
        tags=Tags(what="app", why="coaching", how="AI", who="runners"),
        status="active",
    )


def _task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Fix bug",
        status="todo",
        priority="high",
        created_by="architect",
        linked_entities=[],
        assignee_role_id=None,
        linked_blindspot=None,
    )
    defaults.update(overrides)
    return Task(**defaults)


# ---------------------------------------------------------------------------
# T1: Expand linked_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_expands_entities():
    entity = _entity()
    task = _task(linked_entities=["ent-1"])
    svc = _make_service(task=task, entity=entity)

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    got_task, enrichments = result
    assert len(enrichments["expanded_entities"]) == 1
    exp = enrichments["expanded_entities"][0]
    assert exp["id"] == "ent-1"
    assert exp["name"] == "Paceriz"
    assert exp["summary"] == "A running coach"
    assert "tags" in exp
    assert exp["tags"]["what"] == "app"
    assert exp["status"] == "active"


# ---------------------------------------------------------------------------
# T2: Empty linked_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_empty_entities():
    task = _task(linked_entities=[])
    svc = _make_service(task=task)

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    _, enrichments = result
    assert enrichments["expanded_entities"] == []


# ---------------------------------------------------------------------------
# T3: Missing entity — graceful fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_missing_entity():
    task = _task(linked_entities=["missing-id"])
    svc = _make_service(task=task, entity=None)  # entity_repo returns None

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    _, enrichments = result
    assert enrichments["expanded_entities"] == [{"id": "missing-id", "not_found": True}]


# ---------------------------------------------------------------------------
# T4: Task not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_not_found():
    svc = _make_service(task=None)

    result = await svc.get_task_enriched("ghost")

    assert result is None


# ---------------------------------------------------------------------------
# T5: Expand assignee_role (P1a)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_expands_assignee_role():
    role = _entity(id="role-1", name="Product Manager", summary="Owns the roadmap")
    task = _task(assignee_role_id="role-1")

    def entity_side_effect(eid: str):
        if eid == "role-1":
            return role
        return None

    svc = _make_service(task=task, entity_side_effect=entity_side_effect)

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    _, enrichments = result
    assert "assignee_role" in enrichments
    ar = enrichments["assignee_role"]
    assert ar is not None
    assert ar["id"] == "role-1"
    assert ar["name"] == "Product Manager"
    assert ar["summary"] == "Owns the roadmap"


# ---------------------------------------------------------------------------
# T6: No assignee_role_id — key absent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_no_assignee_role_key_absent():
    task = _task(assignee_role_id=None)
    svc = _make_service(task=task)

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    _, enrichments = result
    assert "assignee_role" not in enrichments


# ---------------------------------------------------------------------------
# T7: assignee_role_id points to non-existent entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_missing_role_returns_none():
    task = _task(assignee_role_id="ghost")
    svc = _make_service(task=task, entity=None)  # all get_by_id return None

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    _, enrichments = result
    assert "assignee_role" in enrichments
    assert enrichments["assignee_role"] is None


# ---------------------------------------------------------------------------
# T8: Expand blindspot_detail (P1b)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_enriched_expands_blindspot():
    bs = Blindspot(
        id="bs-1",
        description="No monitoring on prod",
        severity="red",
        related_entity_ids=["ent-1"],
        suggested_action="Add Datadog",
    )
    task = _task(linked_blindspot="bs-1")
    svc = _make_service(task=task, blindspot=bs)

    result = await svc.get_task_enriched("task-1")

    assert result is not None
    _, enrichments = result
    assert "blindspot_detail" in enrichments
    bd = enrichments["blindspot_detail"]
    assert bd["description"] == "No monitoring on prod"
    assert bd["severity"] == "red"
    assert bd["suggested_action"] == "Add Datadog"


# ---------------------------------------------------------------------------
# T9: Auto context_summary from linked_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_auto_context_summary():
    entity = _entity(id="ent-1", name="Paceriz", summary="A running coach for athletes")
    entity_repo = _make_entity_repo(entity)
    task_repo = _make_task_repo()
    blindspot_repo = _make_blindspot_repo()
    svc = TaskService(
        task_repo=task_repo,
        entity_repo=entity_repo,
        blindspot_repo=blindspot_repo,
    )

    data = {
        "title": "Fix login",
        "created_by": "architect",
        "linked_entities": ["ent-1"],
    }
    task_result = await svc.create_task(data)
    assert "Paceriz" in task_result.task.context_summary
    assert "任務關聯節點" in task_result.task.context_summary


# ---------------------------------------------------------------------------
# T10: Manual context_summary is preserved
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_manual_context_summary_preserved():
    entity = _entity(id="ent-1", name="Paceriz", summary="A running coach")
    entity_repo = _make_entity_repo(entity)
    task_repo = _make_task_repo()
    blindspot_repo = _make_blindspot_repo()
    svc = TaskService(
        task_repo=task_repo,
        entity_repo=entity_repo,
        blindspot_repo=blindspot_repo,
    )

    data = {
        "title": "Fix login",
        "created_by": "architect",
        "linked_entities": ["ent-1"],
        "context_summary": "手動填的",
    }
    task_result = await svc.create_task(data)
    assert task_result.task.context_summary == "手動填的"


# ---------------------------------------------------------------------------
# T11: No linked_entities → context_summary empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_no_linked_no_context():
    entity_repo = _make_entity_repo(None)
    task_repo = _make_task_repo()
    blindspot_repo = _make_blindspot_repo()
    svc = TaskService(
        task_repo=task_repo,
        entity_repo=entity_repo,
        blindspot_repo=blindspot_repo,
    )

    data = {
        "title": "Fix login",
        "created_by": "architect",
    }
    task_result = await svc.create_task(data)
    assert task_result.task.context_summary == ""
