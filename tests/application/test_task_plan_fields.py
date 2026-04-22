from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from zenos.application.action.task_service import TaskService, _parse_due_date
from zenos.domain.action import Task
from zenos.domain.knowledge import Entity, Tags


def _make_entity(entity_id: str, name: str, entity_type: str) -> Entity:
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
        level=1 if entity_type in {"product", "company"} else 2,
        parent_id=None,
        status="active",
        summary="summary",
        tags=Tags(what=[], why="", how="", who=[]),
        details=None,
        confirmed_by_user=True,
        owner="owner",
        sources=[],
        visibility="public",
        last_reviewed_at=None,
    )


@pytest.mark.asyncio
async def test_create_rejects_plan_order_without_plan_id():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    with pytest.raises(ValueError, match="plan_id is required"):
        await svc.create_task(
            {
                "title": "Implement X",
                "created_by": "pm",
                "product_id": "prod-1",
                "plan_order": 1,
            }
        )


@pytest.mark.asyncio
async def test_create_accepts_plan_fields_when_valid():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Implement X",
            "created_by": "pm",
            "product_id": "prod-1",
            "plan_id": "plan-review-v1",
            "plan_order": 2,
            "depends_on_task_ids": ["task-1"],
        }
    )

    assert result.task.plan_id == "plan-review-v1"
    assert result.task.plan_order == 2
    assert result.task.depends_on_task_ids == ["task-1"]


@pytest.mark.asyncio
async def test_create_accepts_product_id_when_provided():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Implement ownership SSOT",
            "created_by": "pm",
            "product_id": "prod-1",
        }
    )

    assert result.task.product_id == "prod-1"
    assert result.task.product_id == "prod-1"


@pytest.mark.asyncio
async def test_create_accepts_company_root_as_product_scope():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("company-1", "原心生技", "company"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Prepare client collaboration space",
            "created_by": "pm",
            "product_id": "company-1",
        }
    )

    assert result.task.product_id == "company-1"
    assert result.task.project == "原心生技"


@pytest.mark.asyncio
async def test_create_rejects_missing_product_id_when_unresolved():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.get_by_name = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    with pytest.raises(ValueError, match="MISSING_PRODUCT_ID|product_id is required"):
        await svc.create_task(
            {
                "title": "Implement ownership SSOT",
                "created_by": "pm",
            }
        )


@pytest.mark.asyncio
async def test_create_resolves_product_id_from_project_name():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_name = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
    entity_repo.get_by_id = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Implement ownership SSOT",
            "created_by": "pm",
            "project": "ZenOS",
        }
    )

    assert result.task.product_id == "prod-1"
    assert result.task.project == "ZenOS"


@pytest.mark.asyncio
async def test_create_rejects_invalid_product_id():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("goal-1", "Goal", "goal"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    with pytest.raises(ValueError, match="invalid or not a collaboration root entity"):
        await svc.create_task(
            {
                "title": "Implement ownership SSOT",
                "created_by": "pm",
                "product_id": "goal-1",
            }
        )


@pytest.mark.asyncio
async def test_create_strips_collaboration_root_entities_from_linked_entities():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    product = _make_entity("prod-1", "ZenOS", "product")
    company = _make_entity("company-1", "原心生技", "company")
    module = _make_entity("mod-1", "Auth", "module")
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(
        side_effect=lambda entity_id: {"prod-1": product, "company-1": company, "mod-1": module}.get(entity_id)
    )
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Implement ownership SSOT",
            "created_by": "pm",
            "product_id": "prod-1",
            "linked_entities": ["prod-1", "company-1", "mod-1"],
        }
    )

    assert result.task.linked_entities == ["mod-1"]


@pytest.mark.asyncio
async def test_create_accepts_due_date_string_without_datetime_timezone_error():
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.create_task(
        {
            "title": "Implement analytics tracking",
            "created_by": "pm",
            "product_id": "prod-1",
            "due_date": "2026-05-15",
        }
    )

    assert result.task.due_date is not None
    assert result.task.due_date.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_update_rejects_plan_order_without_plan_id():
    existing = Task(
        id="task-1",
        title="T",
        status="todo",
        priority="medium",
        created_by="pm",
        product_id="prod-1",
    )
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
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
        product_id="prod-1",
    )
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=existing)
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-1", "ZenOS", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.update_task(
        "task-1",
        {"plan_id": "plan-a", "plan_order": 3, "depends_on_task_ids": ["task-0"]},
    )

    assert result.task.plan_order == 3
    assert result.task.depends_on_task_ids == ["task-0"]


@pytest.mark.asyncio
async def test_update_accepts_product_id_when_valid():
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
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-2", "Paceriz", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    result = await svc.update_task("task-1", {"product_id": "prod-2"})

    assert result.task.product_id == "prod-2"
    assert result.task.product_id == "prod-2"


@pytest.mark.asyncio
async def test_create_rejects_cross_product_subtask():
    parent = Task(
        id="task-parent",
        title="Parent",
        status="todo",
        priority="medium",
        created_by="pm",
        product_id="prod-1",
    )
    task_repo = AsyncMock()
    task_repo.get_by_id = AsyncMock(return_value=parent)
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-2", "Paceriz", "product"))
    blindspot_repo = AsyncMock()

    svc = TaskService(task_repo, entity_repo, blindspot_repo)

    with pytest.raises(ValueError, match="parent task product_id"):
        await svc.create_task(
            {
                "title": "Implement child",
                "created_by": "pm",
                "product_id": "prod-2",
                "parent_task_id": "task-parent",
            }
        )


@pytest.mark.asyncio
async def test_create_rejects_cross_product_plan_task():
    plan = AsyncMock()
    plan.product_id = "prod-1"
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t: t)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=_make_entity("prod-2", "Paceriz", "product"))
    blindspot_repo = AsyncMock()
    plan_repo = AsyncMock()
    plan_repo.get_by_id = AsyncMock(return_value=plan)

    svc = TaskService(task_repo, entity_repo, blindspot_repo, plan_repo=plan_repo)

    with pytest.raises(ValueError, match="plan.product_id"):
        await svc.create_task(
            {
                "title": "Implement planned work",
                "created_by": "pm",
                "product_id": "prod-2",
                "plan_id": "plan-1",
            }
        )


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
