"""Tests for plan MCP tool handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from zenos.domain.action import Plan, PlanStatus
from zenos.interface.mcp.plan import _plan_handler

# Patch targets: plan_service and _ensure_services live in zenos.interface.mcp namespace
# _audit_log lives in zenos.interface.mcp.plan (imported there)
_PLAN_SVC = "zenos.interface.mcp.plan_service"
_ENSURE = "zenos.interface.mcp._ensure_services"
_AUDIT = "zenos.interface.mcp.plan._audit_log"


def _make_plan(**kwargs) -> Plan:
    defaults = {
        "id": "plan-abc",
        "goal": "Ship v1",
        "status": PlanStatus.DRAFT,
        "created_by": "pm",
        "owner": None,
        "entry_criteria": None,
        "exit_criteria": None,
        "project": "zenos",
        "project_id": None,
        "updated_by": "pm",
        "result": None,
    }
    defaults.update(kwargs)
    return Plan(**defaults)


@pytest.fixture(autouse=True)
def _mock_partner():
    """Inject a fake partner context for all tests in this file."""
    with patch("zenos.interface.mcp.plan._current_partner") as mock_cp:
        mock_cp.get.return_value = {
            "id": "partner-1",
            "defaultProject": "zenos",
        }
        yield mock_cp


@pytest.fixture()
def mock_plan_service():
    return AsyncMock()


# ─────────────────────────────────────────────────────────────────────────────
# create action
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_plan_returns_ok(mock_plan_service):
    plan = _make_plan()
    mock_plan_service.create_plan = AsyncMock(return_value=plan)

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()), \
         patch(_AUDIT):
        result = await _plan_handler(action="create", goal="Ship v1", project="zenos")

    assert result["status"] == "ok"
    assert result["data"]["id"] == "plan-abc"
    assert result["data"]["goal"] == "Ship v1"


@pytest.mark.asyncio
async def test_create_plan_rejects_missing_goal():
    # Validation happens before service call — no service needed
    result = await _plan_handler(action="create")

    assert result["status"] == "rejected"
    assert "goal" in result["rejection_reason"]


@pytest.mark.asyncio
async def test_create_plan_uses_default_project_from_partner(mock_plan_service):
    plan = _make_plan(project="zenos")
    mock_plan_service.create_plan = AsyncMock(return_value=plan)

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()), \
         patch(_AUDIT):
        # No project passed — should use defaultProject from partner
        await _plan_handler(action="create", goal="Implicit project")

    call_args = mock_plan_service.create_plan.call_args[0][0]
    assert call_args["project"] == "zenos"


# ─────────────────────────────────────────────────────────────────────────────
# update action
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_plan_returns_ok(mock_plan_service):
    plan = _make_plan(status=PlanStatus.ACTIVE)
    mock_plan_service.update_plan = AsyncMock(return_value=plan)

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()), \
         patch(_AUDIT):
        result = await _plan_handler(action="update", id="plan-abc", status="active")

    assert result["status"] == "ok"
    assert result["data"]["status"] == PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_update_plan_rejects_missing_id():
    result = await _plan_handler(action="update", status="active")

    assert result["status"] == "rejected"
    assert "id" in result["rejection_reason"]


@pytest.mark.asyncio
async def test_update_plan_propagates_service_error(mock_plan_service):
    mock_plan_service.update_plan = AsyncMock(
        side_effect=ValueError("Invalid plan status transition: completed → active")
    )

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()), \
         patch(_AUDIT):
        result = await _plan_handler(action="update", id="plan-abc", status="active")

    assert result["status"] == "rejected"
    assert "Invalid plan status transition" in result["rejection_reason"]


# ─────────────────────────────────────────────────────────────────────────────
# get action
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_plan_returns_plan_with_tasks_summary(mock_plan_service):
    plan_dict = {
        "id": "plan-abc",
        "goal": "Ship v1",
        "status": "draft",
        "tasks_summary": {"total": 3, "by_status": {"done": 2, "in_progress": 1}},
    }
    mock_plan_service.get_plan = AsyncMock(return_value=plan_dict)

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()):
        result = await _plan_handler(action="get", id="plan-abc")

    assert result["status"] == "ok"
    assert result["data"]["tasks_summary"]["total"] == 3


@pytest.mark.asyncio
async def test_get_plan_rejects_missing_id():
    result = await _plan_handler(action="get")

    assert result["status"] == "rejected"
    assert "id" in result["rejection_reason"]


# ─────────────────────────────────────────────────────────────────────────────
# list action
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_plans_returns_list(mock_plan_service):
    plans = [_make_plan(), _make_plan(id="plan-2", goal="Another plan")]
    mock_plan_service.list_plans = AsyncMock(return_value=plans)

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()):
        result = await _plan_handler(action="list")

    assert result["status"] == "ok"
    assert len(result["data"]["plans"]) == 2


@pytest.mark.asyncio
async def test_list_plans_with_status_filter(mock_plan_service):
    mock_plan_service.list_plans = AsyncMock(return_value=[])

    with patch(_PLAN_SVC, mock_plan_service), \
         patch(_ENSURE, new=AsyncMock()):
        await _plan_handler(action="list", status="draft,active")

    call_kwargs = mock_plan_service.list_plans.call_args[1]
    assert call_kwargs["status"] == ["draft", "active"]


# ─────────────────────────────────────────────────────────────────────────────
# unknown action
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_action_returns_rejected():
    result = await _plan_handler(action="delete")

    assert result["status"] == "rejected"
    assert "delete" in result["rejection_reason"]
