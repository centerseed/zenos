"""Dashboard permission helpers should fail closed on internal errors."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from zenos.domain.action import Task
from zenos.domain.knowledge import Blindspot


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Test task",
        status="todo",
        priority="high",
        created_by="architect",
        description="A test task",
        linked_entities=["ent-1"],
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_blindspot(**overrides) -> Blindspot:
    defaults = dict(
        id="bs-1",
        description="Missing docs",
        severity="yellow",
        related_entity_ids=["ent-1"],
        suggested_action="Add docs",
        status="open",
        confirmed_by_user=False,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Blindspot(**defaults)


@pytest.mark.asyncio
async def test_dashboard_task_visibility_exception_denies_access():
    from zenos.interface.dashboard_api import _is_task_visible_for_partner

    partner = {"id": "p1", "isAdmin": False, "authorizedEntityIds": [], "status": "active"}
    task = _make_task()

    with patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(side_effect=RuntimeError("db down"))):
        assert await _is_task_visible_for_partner(task, partner, effective_id="ws-1") is False


@pytest.mark.asyncio
async def test_dashboard_blindspot_visibility_exception_denies_access():
    from zenos.interface.dashboard_api import _is_blindspot_visible_for_partner

    partner = {"id": "p1", "isAdmin": False, "authorizedEntityIds": [], "status": "active"}
    bs = _make_blindspot()

    with patch("zenos.interface.dashboard_api._get_entity_by_id_with_context", new=AsyncMock(side_effect=RuntimeError("db down"))):
        assert await _is_blindspot_visible_for_partner(bs, partner, effective_id="ws-1") is False
