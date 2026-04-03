"""Tests for PermissionRiskService.

All tests use mock repositories — no external service dependencies.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from zenos.application.permission_risk_service import PermissionRiskService
from zenos.domain.models import Entity, Tags, Task, TaskStatus, TaskPriority


# ── Helpers ──────────────────────────────────────────────────────────────────


def _entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-default",
        name="Default Entity",
        type="module",
        summary="",
        tags=Tags(what=["x"], why="y", how="z", who=["all"]),
        status="active",
        visibility="public",
        visible_to_roles=[],
        visible_to_members=[],
        visible_to_departments=[],
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _task(**overrides) -> Task:
    defaults = dict(
        id="task-default",
        title="Default Task",
        status=TaskStatus.TODO.value,
        priority=TaskPriority.MEDIUM.value,
        created_by="user-1",
        linked_entities=[],
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_service(entities: list[Entity], tasks: list[Task]) -> PermissionRiskService:
    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=entities)
    task_repo = AsyncMock()
    task_repo.list_all = AsyncMock(return_value=tasks)
    return PermissionRiskService(entity_repo=entity_repo, task_repo=task_repo)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_member_isolation_detected():
    """Restricted entity visible to exactly one member → single_member_isolation warning."""
    isolated_entity = _entity(
        id="ent-isolated",
        name="Private Doc",
        visibility="restricted",
        visible_to_members=["member-1"],
        visible_to_roles=[],
        visible_to_departments=[],
    )
    svc = _make_service(entities=[isolated_entity], tasks=[])

    result = await svc.analyze_risk()

    warning_types = [w["type"] for w in result["warnings"]]
    assert "single_member_isolation" in warning_types

    isolation_warning = next(w for w in result["warnings"] if w["type"] == "single_member_isolation")
    assert isolation_warning["severity"] == "yellow"
    assert isolation_warning["entity_id"] == "ent-isolated"
    assert result["isolation_score"] > 0.0


@pytest.mark.asyncio
async def test_high_confidential_ratio_detected():
    """4 out of 10 entities confidential (40% > 30%) → high_confidential_ratio red warning."""
    entities = (
        [_entity(id=f"conf-{i}", name=f"Conf {i}", visibility="confidential") for i in range(4)]
        + [_entity(id=f"pub-{i}", name=f"Pub {i}", visibility="public") for i in range(6)]
    )
    svc = _make_service(entities=entities, tasks=[])

    result = await svc.analyze_risk()

    warning_types = [w["type"] for w in result["warnings"]]
    assert "high_confidential_ratio" in warning_types

    ratio_warning = next(w for w in result["warnings"] if w["type"] == "high_confidential_ratio")
    assert ratio_warning["severity"] == "red"
    assert ratio_warning["ratio"] == pytest.approx(0.4, abs=0.001)
    assert result["isolation_score"] > 0.0


@pytest.mark.asyncio
async def test_sensitive_entity_overexposed():
    """Entity with '薪資' in name and visibility=public → sensitive_entity_overexposed warning."""
    sensitive = _entity(
        id="ent-salary",
        name="薪資結構表",
        summary="全公司薪資分級說明",
        visibility="public",
    )
    svc = _make_service(entities=[sensitive], tasks=[])

    result = await svc.analyze_risk()

    warning_types = [w["type"] for w in result["warnings"]]
    assert "sensitive_entity_overexposed" in warning_types

    exp_warning = next(w for w in result["warnings"] if w["type"] == "sensitive_entity_overexposed")
    assert exp_warning["severity"] == "red"
    assert exp_warning["entity_id"] == "ent-salary"
    assert result["overexposure_score"] > 0.0


@pytest.mark.asyncio
async def test_tasks_hidden_by_entity_visibility():
    """6 tasks all linked to restricted entities → tasks_hidden_by_entity_visibility yellow warning."""
    restricted_entity = _entity(
        id="ent-restricted",
        name="Internal Process",
        visibility="restricted",
    )
    tasks = [
        _task(id=f"task-{i}", title=f"Task {i}", linked_entities=["ent-restricted"])
        for i in range(6)
    ]
    svc = _make_service(entities=[restricted_entity], tasks=tasks)

    result = await svc.analyze_risk()

    warning_types = [w["type"] for w in result["warnings"]]
    assert "tasks_hidden_by_entity_visibility" in warning_types

    hidden_warning = next(w for w in result["warnings"] if w["type"] == "tasks_hidden_by_entity_visibility")
    assert hidden_warning["severity"] == "yellow"
    assert hidden_warning["affected_task_count"] == 6
    assert result["isolation_score"] > 0.0


@pytest.mark.asyncio
async def test_no_risk_clean_state():
    """All entities public, no sensitive keywords → zero warnings and zero scores."""
    entities = [
        _entity(id="ent-1", name="ZenOS Core", summary="Core ontology module", visibility="public"),
        _entity(id="ent-2", name="Action Layer", summary="Task management layer", visibility="public"),
        _entity(id="ent-3", name="Dashboard UI", summary="Frontend interface", visibility="public"),
    ]
    tasks = [
        _task(id="t-1", linked_entities=["ent-1"]),
        _task(id="t-2", linked_entities=["ent-2"]),
    ]
    svc = _make_service(entities=entities, tasks=tasks)

    result = await svc.analyze_risk()

    assert result["warnings"] == []
    assert result["isolation_score"] == 0.0
    assert result["overexposure_score"] == 0.0
    assert "isolation_score" in result
    assert "overexposure_score" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_tasks_hidden_threshold_not_triggered_at_five():
    """Exactly 5 tasks hidden (not > 5) → no tasks_hidden warning."""
    restricted_entity = _entity(
        id="ent-r",
        name="Restricted",
        visibility="restricted",
    )
    tasks = [
        _task(id=f"task-{i}", linked_entities=["ent-r"])
        for i in range(5)
    ]
    svc = _make_service(entities=[restricted_entity], tasks=tasks)

    result = await svc.analyze_risk()

    warning_types = [w["type"] for w in result["warnings"]]
    assert "tasks_hidden_by_entity_visibility" not in warning_types


@pytest.mark.asyncio
async def test_overexposure_score_capped_at_one():
    """overexposure_score never exceeds 1.0 even with all entities overexposed."""
    entities = [
        _entity(id=f"ent-{i}", name="薪資表", summary="", visibility="public")
        for i in range(20)
    ]
    svc = _make_service(entities=entities, tasks=[])

    result = await svc.analyze_risk()

    assert result["overexposure_score"] <= 1.0


@pytest.mark.asyncio
async def test_confidential_entity_with_single_member_both_warnings():
    """Confidential entity with single member triggers both isolation rules."""
    confidential_isolated = _entity(
        id="ent-ci",
        name="Secret Plan",
        visibility="confidential",
        visible_to_members=["ceo"],
        visible_to_roles=[],
        visible_to_departments=[],
    )
    # Add 9 more entities to avoid triggering high_confidential_ratio (10% < 30%)
    other_entities = [
        _entity(id=f"pub-{i}", name=f"Public {i}", visibility="public")
        for i in range(9)
    ]
    svc = _make_service(entities=[confidential_isolated] + other_entities, tasks=[])

    result = await svc.analyze_risk()

    warning_types = [w["type"] for w in result["warnings"]]
    assert "single_member_isolation" in warning_types
    assert "high_confidential_ratio" not in warning_types
