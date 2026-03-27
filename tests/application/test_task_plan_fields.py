from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zenos.application.task_service import TaskService
from zenos.domain.models import Task


@pytest.mark.asyncio
async def test_create_rejects_plan_order_without_plan_id():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    with pytest.raises(ValueError, match="plan_id is required"):
        await svc.create_task(
            {
                "title": "Implement X",
                "created_by": "pm",
                "plan_order": 1,
            }
        )


@pytest.mark.asyncio
async def test_create_accepts_plan_fields_when_valid():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Implement X",
            "created_by": "pm",
            "plan_id": "plan-review-v1",
            "plan_order": 2,
            "depends_on_task_ids": ["task-1"],
        }
    )

    assert result.task.plan_id == "plan-review-v1"
    assert result.task.plan_order == 2
    assert result.task.depends_on_task_ids == ["task-1"]


@pytest.mark.asyncio
async def test_update_rejects_plan_order_without_plan_id():
    existing = Task(
        id="task-1",
        title="T",
        status="todo",
        priority="medium",
        created_by="pm",
    )
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    with pytest.raises(ValueError, match="plan_id is required"):
        await svc.update_task("task-1", {"plan_order": 3})


@pytest.mark.asyncio
async def test_update_accepts_plan_fields_when_valid():
    existing = Task(
        id="task-1",
        title="T",
        status="todo",
        priority="medium",
        created_by="pm",
        plan_id="plan-a",
    )
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.update_task(
        "task-1",
        {"plan_id": "plan-a", "plan_order": 3, "depends_on_task_ids": ["task-0"]},
    )

    assert result.task.plan_order == 3
    assert result.task.depends_on_task_ids == ["task-0"]
