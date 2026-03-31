from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zenos.application.task_service import TaskService
from zenos.domain.models import Task


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
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    task_repo.list_blocked_by = AsyncMock(return_value=[])
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    updated = await svc.update_task("task-1", {"description": "x", "updated_by": "actor-2"})
    assert updated.task.updated_by == "actor-2"

    confirmed = await svc.confirm_task("task-1", accepted=True, updated_by="actor-3")
    assert confirmed.task.updated_by == "actor-3"
