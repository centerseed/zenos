from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.action.task_service import TaskService
from zenos.domain.action import Task


def _make_uow_factory():
    """Create a mock UoW factory for testing."""
    uow = MagicMock()
    uow.conn = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return lambda: uow


def _make_review_task(**overrides) -> Task:
    defaults = dict(
        id="task-review",
        title="Deliver feature X",
        status="review",
        priority="medium",
        created_by="dev-1",
        updated_by="dev-1",
    )
    defaults.update(overrides)
    return Task(**defaults)


@pytest.mark.asyncio
async def test_create_sets_updated_by_from_input_or_created_by():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    explicit = await svc.create_task(
        {
            "title": "Implement X",
            "created_by": "owner-1",
            "updated_by": "actor-2",
        }
    )
    assert explicit.task.created_by == "owner-1"
    assert explicit.task.updated_by == "actor-2"

    implicit = await svc.create_task(
        {
            "title": "Implement Y",
            "created_by": "owner-3",
        }
    )
    assert implicit.task.created_by == "owner-3"
    assert implicit.task.updated_by == "owner-3"


@pytest.mark.asyncio
async def test_update_and_confirm_set_updated_by():
    existing = Task(
        id="task-1",
        title="T",
        status="review",
        priority="medium",
        created_by="owner-1",
        updated_by="owner-1",
    )
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t, **kw: t)
    task_repo.list_blocked_by = AsyncMock(return_value=[])
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo, uow_factory=_make_uow_factory())

    updated = await svc.update_task("task-1", {"description": "x", "updated_by": "actor-2"})
    assert updated.task.updated_by == "actor-2"

    confirmed = await svc.confirm_task("task-1", accepted=True, updated_by="actor-3")
    assert confirmed.task.updated_by == "actor-3"


@pytest.mark.asyncio
async def test_confirm_task_accepts_entity_entries_param_without_error():
    """entity_entries param is accepted; service-layer ignores it (writing handled in tools layer)."""
    existing = _make_review_task()
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t, **kw: t)
    task_repo.list_blocked_by = AsyncMock(return_value=[])
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo, uow_factory=_make_uow_factory())

    entries = [
        {"entity_id": "ent-1", "type": "insight", "content": "Some valuable insight"},
        {"entity_id": "ent-2", "type": "decision", "content": "Key architectural decision"},
    ]
    result = await svc.confirm_task(
        "task-review",
        accepted=True,
        entity_entries=entries,
        updated_by="reviewer-1",
    )

    assert result.task.status == "done"
    assert result.task.updated_by == "reviewer-1"


@pytest.mark.asyncio
async def test_confirm_task_entity_entries_ignored_when_rejected():
    """entity_entries are not processed when task is rejected."""
    existing = _make_review_task()
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    entries = [{"entity_id": "ent-1", "type": "insight", "content": "should be ignored"}]
    result = await svc.confirm_task(
        "task-review",
        accepted=False,
        rejection_reason="Not meeting acceptance criteria",
        entity_entries=entries,
    )

    assert result.task.status == "in_progress"


@pytest.mark.asyncio
async def test_confirm_task_entity_entries_none_is_backward_compatible():
    """Not providing entity_entries (default None) preserves existing behavior."""
    existing = _make_review_task()
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t, **kw: t)
    task_repo.list_blocked_by = AsyncMock(return_value=[])
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo, uow_factory=_make_uow_factory())

    result = await svc.confirm_task("task-review", accepted=True, updated_by="reviewer-1")

    assert result.task.status == "done"
