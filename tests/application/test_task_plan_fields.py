from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from zenos.application.task_service import TaskService, _parse_due_date
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


# ─────────────────────────────────────────────────────────────────────────────
# _parse_due_date — string-to-datetime conversion used for dashboard API dates
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_due_date_returns_none_for_none():
    assert _parse_due_date(None) is None


def test_parse_due_date_returns_none_for_empty_string():
    assert _parse_due_date("") is None


def test_parse_due_date_parses_iso_date_string():
    result = _parse_due_date("2026-04-15")
    assert isinstance(result, datetime)
    assert result.year == 2026
    assert result.month == 4
    assert result.day == 15
    assert result.tzinfo == timezone.utc


def test_parse_due_date_parses_iso_datetime_with_z():
    result = _parse_due_date("2026-04-15T12:00:00Z")
    assert isinstance(result, datetime)
    assert result.tzinfo is not None


def test_parse_due_date_passthrough_for_datetime():
    dt = datetime(2026, 4, 15, tzinfo=timezone.utc)
    result = _parse_due_date(dt)
    assert result is dt


def test_parse_due_date_adds_utc_to_naive_datetime():
    dt = datetime(2026, 4, 15)
    result = _parse_due_date(dt)
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_due_date_returns_none_for_invalid_string():
    assert _parse_due_date("not-a-date") is None
