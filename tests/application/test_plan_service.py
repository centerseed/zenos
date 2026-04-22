"""Tests for PlanService — CRUD, lifecycle, and completion validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.action.plan_service import PlanService
from zenos.domain.action import Plan, PlanStatus, Task
from zenos.domain.knowledge import Entity, Tags


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_plan(**kwargs) -> Plan:
    defaults = {
        "goal": "Ship feature",
        "status": PlanStatus.DRAFT,
        "created_by": "pm",
        "id": "plan-1",
        "project": "ZenOS",
        "product_id": "prod-1",
    }
    defaults.update(kwargs)
    return Plan(**defaults)


def _make_task(status: str, id: str = "task-1") -> Task:
    return Task(id=id, title="T", status=status, priority="medium", created_by="pm")


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


def _make_service(plan=None, tasks=None, entity=None) -> PlanService:
    plan_repo = AsyncMock()
    plan_repo.get_by_id = AsyncMock(return_value=plan)
    plan_repo.upsert = AsyncMock(side_effect=lambda p: p)
    plan_repo.list_all = AsyncMock(return_value=[])

    task_repo = AsyncMock()
    task_repo.list_all = AsyncMock(return_value=tasks or [])
    resolved_entity = entity if entity is not None else _make_entity("prod-1", "ZenOS", "product")
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=resolved_entity)
    entity_repo.get_by_name = AsyncMock(return_value=resolved_entity)

    return PlanService(plan_repo=plan_repo, task_repo=task_repo, entity_repo=entity_repo)


# ─────────────────────────────────────────────────────────────────────────────
# create_plan
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_plan_requires_goal():
    svc = _make_service()
    with pytest.raises(ValueError, match="goal is required"):
        await svc.create_plan({"created_by": "pm"})


@pytest.mark.asyncio
async def test_create_plan_requires_created_by():
    svc = _make_service()
    with pytest.raises(ValueError, match="created_by is required"):
        await svc.create_plan({"goal": "Some goal"})


@pytest.mark.asyncio
async def test_create_plan_requires_product_id():
    svc = _make_service(entity=None)
    with pytest.raises(ValueError, match="product_id is required"):
        await svc.create_plan({"goal": "Deploy v1", "created_by": "pm"})


@pytest.mark.asyncio
async def test_create_plan_defaults_to_draft():
    svc = _make_service(entity=_make_entity("prod-1", "ZenOS", "product"))
    plan = await svc.create_plan({"goal": "Deploy v1", "created_by": "pm", "product_id": "prod-1"})
    assert plan.status == PlanStatus.DRAFT


@pytest.mark.asyncio
async def test_create_plan_stores_optional_fields():
    svc = _make_service(entity=_make_entity("prod-1", "ZenOS", "product"))
    plan = await svc.create_plan({
        "goal": "Ship X",
        "created_by": "pm",
        "owner": "tech-lead",
        "entry_criteria": "ADR approved",
        "exit_criteria": "QA passed",
        "project": "zenos",
        "product_id": "prod-1",
    })
    assert plan.owner == "tech-lead"
    assert plan.entry_criteria == "ADR approved"
    assert plan.exit_criteria == "QA passed"
    assert plan.project == "ZenOS"


@pytest.mark.asyncio
async def test_create_plan_accepts_valid_product_id_and_derives_project_name():
    svc = _make_service(entity=_make_entity("prod-1", "ZenOS", "product"))

    plan = await svc.create_plan({"goal": "Deploy v1", "created_by": "pm", "product_id": "prod-1"})

    assert plan.product_id == "prod-1"
    assert plan.project == "ZenOS"


@pytest.mark.asyncio
async def test_create_plan_accepts_company_root_as_collaboration_scope():
    svc = _make_service(entity=_make_entity("company-1", "原心生技", "company"))

    plan = await svc.create_plan({"goal": "Kick off client workspace", "created_by": "pm", "product_id": "company-1"})

    assert plan.product_id == "company-1"
    assert plan.project == "原心生技"


@pytest.mark.asyncio
async def test_create_plan_rejects_non_collaboration_root_entity_as_product_id():
    svc = _make_service(entity=_make_entity("goal-1", "Goal", "goal"))

    with pytest.raises(ValueError, match="invalid or not a collaboration root entity"):
        await svc.create_plan({"goal": "Deploy v1", "created_by": "pm", "product_id": "goal-1"})


# ─────────────────────────────────────────────────────────────────────────────
# update_plan — lifecycle transitions
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_plan_draft_to_active():
    plan = _make_plan(status=PlanStatus.DRAFT)
    svc = _make_service(plan=plan)
    updated = await svc.update_plan("plan-1", {"status": "active"})
    assert updated.status == PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_update_plan_draft_to_cancelled():
    plan = _make_plan(status=PlanStatus.DRAFT)
    svc = _make_service(plan=plan)
    updated = await svc.update_plan("plan-1", {"status": "cancelled"})
    assert updated.status == PlanStatus.CANCELLED


@pytest.mark.asyncio
async def test_update_plan_rejects_draft_to_completed():
    plan = _make_plan(status=PlanStatus.DRAFT)
    svc = _make_service(plan=plan)
    with pytest.raises(ValueError, match="Invalid plan status transition"):
        await svc.update_plan("plan-1", {"status": "completed"})


@pytest.mark.asyncio
async def test_update_plan_active_to_completed_requires_result():
    plan = _make_plan(status=PlanStatus.ACTIVE)
    # All tasks terminal
    tasks = [_make_task("done"), _make_task("cancelled", id="task-2")]
    svc = _make_service(plan=plan, tasks=tasks)
    with pytest.raises(ValueError, match="result is required"):
        await svc.update_plan("plan-1", {"status": "completed"})


@pytest.mark.asyncio
async def test_update_plan_active_to_completed_requires_all_tasks_terminal():
    plan = _make_plan(status=PlanStatus.ACTIVE)
    # One task still in progress
    tasks = [_make_task("done"), _make_task("in_progress", id="task-2")]
    svc = _make_service(plan=plan, tasks=tasks)
    with pytest.raises(ValueError, match="Cannot complete plan"):
        await svc.update_plan("plan-1", {"status": "completed", "result": "Done!"})


@pytest.mark.asyncio
async def test_update_plan_active_to_completed_succeeds_when_all_tasks_done():
    plan = _make_plan(status=PlanStatus.ACTIVE)
    tasks = [_make_task("done"), _make_task("cancelled", id="task-2")]
    svc = _make_service(plan=plan, tasks=tasks)
    updated = await svc.update_plan("plan-1", {"status": "completed", "result": "All shipped!"})
    assert updated.status == PlanStatus.COMPLETED


@pytest.mark.asyncio
async def test_update_plan_completed_is_immutable():
    plan = _make_plan(status=PlanStatus.COMPLETED)
    svc = _make_service(plan=plan)
    with pytest.raises(ValueError, match="terminal status"):
        await svc.update_plan("plan-1", {"status": "active"})


@pytest.mark.asyncio
async def test_update_plan_cancelled_is_immutable():
    plan = _make_plan(status=PlanStatus.CANCELLED)
    svc = _make_service(plan=plan)
    with pytest.raises(ValueError, match="terminal status"):
        await svc.update_plan("plan-1", {"goal": "new goal"})


@pytest.mark.asyncio
async def test_update_plan_not_found():
    svc = _make_service(plan=None)
    with pytest.raises(ValueError, match="not found"):
        await svc.update_plan("nonexistent", {"status": "active"})


@pytest.mark.asyncio
async def test_update_plan_rejects_non_collaboration_root_entity_as_product_id():
    plan = _make_plan(product_id="prod-1", project="ZenOS")
    svc = _make_service(plan=plan, entity=_make_entity("goal-1", "Goal", "goal"))

    with pytest.raises(ValueError, match="invalid or not a collaboration root entity"):
        await svc.update_plan("plan-1", {"product_id": "goal-1"})


# ─────────────────────────────────────────────────────────────────────────────
# get_plan
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_plan_includes_tasks_summary():
    plan = _make_plan()
    tasks = [
        _make_task("done", "t1"),
        _make_task("done", "t2"),
        _make_task("in_progress", "t3"),
    ]
    svc = _make_service(plan=plan, tasks=tasks)
    result = await svc.get_plan("plan-1")
    assert result["tasks_summary"]["total"] == 3
    assert result["tasks_summary"]["by_status"]["done"] == 2
    assert result["tasks_summary"]["by_status"]["in_progress"] == 1


@pytest.mark.asyncio
async def test_get_plan_not_found():
    svc = _make_service(plan=None)
    with pytest.raises(ValueError, match="not found"):
        await svc.get_plan("missing")


# ─────────────────────────────────────────────────────────────────────────────
# list_plans
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_plans_delegates_to_repo():
    plan_repo = AsyncMock()
    plans = [_make_plan(), _make_plan(id="plan-2", goal="Another plan")]
    plan_repo.list_all = AsyncMock(return_value=plans)
    plan_repo.upsert = AsyncMock(side_effect=lambda p: p)
    task_repo = AsyncMock()

    svc = PlanService(plan_repo=plan_repo, task_repo=task_repo)
    result = await svc.list_plans(status=["draft"], project="zenos", product_id="prod-1")

    plan_repo.list_all.assert_awaited_once_with(
        status=["draft"], project="zenos", product_id="prod-1", limit=50, offset=0
    )
    assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────────────
# advance_plan_to_active
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_advance_plan_to_active_from_draft():
    plan = _make_plan(status=PlanStatus.DRAFT)
    plan_repo = AsyncMock()
    plan_repo.get_by_id = AsyncMock(return_value=plan)
    plan_repo.upsert = AsyncMock(side_effect=lambda p: p)
    task_repo = AsyncMock()

    svc = PlanService(plan_repo=plan_repo, task_repo=task_repo)
    await svc.advance_plan_to_active("plan-1")

    plan_repo.upsert.assert_awaited_once()
    assert plan.status == PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_advance_plan_to_active_no_op_when_already_active():
    plan = _make_plan(status=PlanStatus.ACTIVE)
    plan_repo = AsyncMock()
    plan_repo.get_by_id = AsyncMock(return_value=plan)
    plan_repo.upsert = AsyncMock(side_effect=lambda p: p)
    task_repo = AsyncMock()

    svc = PlanService(plan_repo=plan_repo, task_repo=task_repo)
    await svc.advance_plan_to_active("plan-1")

    plan_repo.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_advance_plan_to_active_no_op_when_plan_not_found():
    plan_repo = AsyncMock()
    plan_repo.get_by_id = AsyncMock(return_value=None)
    plan_repo.upsert = AsyncMock()
    task_repo = AsyncMock()

    svc = PlanService(plan_repo=plan_repo, task_repo=task_repo)
    # Should not raise
    await svc.advance_plan_to_active("nonexistent")
    plan_repo.upsert.assert_not_awaited()
