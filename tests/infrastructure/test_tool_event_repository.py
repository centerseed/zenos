"""Tests for SqlToolEventRepository — tool event logging.

All tests use mock asyncpg pool/connection objects to avoid a real database.
Tests verify:
  - SQL INSERT is called with correct partner_id and parameters
  - Empty partner_id causes silent no-op (not an error)
  - get_entity_usage_stats returns correct per-entity counts
  - _schedule_tool_event helper creates asyncio tasks correctly

NOTE: These are mock-based tests (⚠️ mock tests).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from zenos.infrastructure.sql_repo import SqlToolEventRepository


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────

PARTNER_ID = "partner_test_123"


from tests.conftest import AsyncContextManager as _AsyncContextManager


def _make_pool(fetch=None, execute=None):
    """Build a mock asyncpg pool whose acquire() context manager returns a conn."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock(return_value=execute)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncContextManager(conn))
    return pool, conn


def _make_stat_row(entity_id: str, search_count: int, get_count: int) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "entity_id": entity_id,
        "search_count": search_count,
        "get_count": get_count,
    }[k]
    return row


# ─────────────────────────────────────────────────────────────────────────────
# SqlToolEventRepository.log_tool_event
# ─────────────────────────────────────────────────────────────────────────────


class TestLogToolEvent:

    @pytest.mark.asyncio
    async def test_inserts_row_with_correct_params(self):
        """log_tool_event executes INSERT with all provided parameters."""
        pool, conn = _make_pool()
        repo = SqlToolEventRepository(pool)

        await repo.log_tool_event(
            partner_id=PARTNER_ID,
            tool_name="search",
            entity_id="ent_abc",
            query="some query",
            result_count=5,
        )

        conn.execute.assert_called_once()
        sql, *args = conn.execute.call_args[0]
        assert "INSERT INTO" in sql
        assert "tool_events" in sql
        assert args == [PARTNER_ID, "search", "ent_abc", "some query", 5]

    @pytest.mark.asyncio
    async def test_silently_returns_on_empty_partner_id(self):
        """log_tool_event does nothing when partner_id is empty string."""
        pool, conn = _make_pool()
        repo = SqlToolEventRepository(pool)

        await repo.log_tool_event(
            partner_id="",
            tool_name="get",
            entity_id="ent_xyz",
            query=None,
            result_count=None,
        )

        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_accepts_none_optional_fields(self):
        """log_tool_event passes None for optional entity_id, query, result_count."""
        pool, conn = _make_pool()
        repo = SqlToolEventRepository(pool)

        await repo.log_tool_event(
            partner_id=PARTNER_ID,
            tool_name="get",
            entity_id=None,
            query=None,
            result_count=None,
        )

        conn.execute.assert_called_once()
        _, *args = conn.execute.call_args[0]
        assert args == [PARTNER_ID, "get", None, None, None]


# ─────────────────────────────────────────────────────────────────────────────
# SqlToolEventRepository.get_entity_usage_stats
# ─────────────────────────────────────────────────────────────────────────────


class TestGetEntityUsageStats:

    @pytest.mark.asyncio
    async def test_returns_per_entity_counts(self):
        """get_entity_usage_stats maps DB rows to expected dict structure."""
        rows = [
            _make_stat_row("ent_1", search_count=10, get_count=3),
            _make_stat_row("ent_2", search_count=0, get_count=7),
        ]
        pool, conn = _make_pool(fetch=rows)
        repo = SqlToolEventRepository(pool)

        stats = await repo.get_entity_usage_stats(PARTNER_ID, days=30)

        assert len(stats) == 2
        assert stats[0] == {"entity_id": "ent_1", "search_count": 10, "get_count": 3}
        assert stats[1] == {"entity_id": "ent_2", "search_count": 0, "get_count": 7}

    @pytest.mark.asyncio
    async def test_sql_contains_partner_id_filter(self):
        """get_entity_usage_stats passes partner_id as parameterized query arg."""
        pool, conn = _make_pool(fetch=[])
        repo = SqlToolEventRepository(pool)

        await repo.get_entity_usage_stats(PARTNER_ID, days=7)

        conn.fetch.assert_called_once()
        sql, *args = conn.fetch.call_args[0]
        assert "$1" in sql
        assert PARTNER_ID in args

    @pytest.mark.asyncio
    async def test_sql_uses_parameterized_interval_not_string_interpolation(self):
        """get_entity_usage_stats passes days as a parameter, not via f-string into SQL."""
        pool, conn = _make_pool(fetch=[])
        repo = SqlToolEventRepository(pool)

        await repo.get_entity_usage_stats(PARTNER_ID, days=14)

        conn.fetch.assert_called_once()
        sql, *args = conn.fetch.call_args[0]
        # days value must be passed as a bind arg, not hardcoded in SQL
        assert "14" not in sql
        assert "14" in [str(a) for a in args]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_events(self):
        """get_entity_usage_stats returns empty list when no events exist."""
        pool, conn = _make_pool(fetch=[])
        repo = SqlToolEventRepository(pool)

        stats = await repo.get_entity_usage_stats(PARTNER_ID)

        assert stats == []


# ─────────────────────────────────────────────────────────────────────────────
# _schedule_tool_event helper in tools.py
# ─────────────────────────────────────────────────────────────────────────────


class TestScheduleToolEvent:

    @pytest.mark.asyncio
    async def test_schedule_tool_event_calls_create_task_with_partner_id(self):
        """_schedule_tool_event creates an asyncio task when partner_id is set."""
        from zenos.interface import tools as tools_mod

        fake_repo = AsyncMock()
        fake_repo.log_tool_event = AsyncMock()

        original_repo = tools_mod._tool_event_repo
        original_partner_id = tools_mod._current_partner_id

        try:
            tools_mod._tool_event_repo = fake_repo
            # Patch _current_partner_id.get to return a partner_id
            mock_ctx = MagicMock()
            mock_ctx.get = MagicMock(return_value=PARTNER_ID)
            tools_mod._current_partner_id = mock_ctx

            created_tasks = []
            original_create_task = asyncio.create_task

            def capture_create_task(coro, **kwargs):
                task = original_create_task(coro, **kwargs)
                created_tasks.append(task)
                return task

            with patch("asyncio.create_task", side_effect=capture_create_task):
                tools_mod._schedule_tool_event("search", "ent_abc", "my query", 3)

            # Allow any pending coroutines to complete
            await asyncio.gather(*created_tasks, return_exceptions=True)

            fake_repo.log_tool_event.assert_called_once_with(
                partner_id=PARTNER_ID,
                tool_name="search",
                entity_id="ent_abc",
                query="my query",
                result_count=3,
            )
        finally:
            tools_mod._tool_event_repo = original_repo
            tools_mod._current_partner_id = original_partner_id

    @pytest.mark.asyncio
    async def test_schedule_tool_event_no_op_when_no_partner(self):
        """_schedule_tool_event does nothing when no partner_id in context."""
        from zenos.interface import tools as tools_mod

        original_partner_id = tools_mod._current_partner_id
        try:
            mock_ctx = MagicMock()
            mock_ctx.get = MagicMock(return_value="")
            tools_mod._current_partner_id = mock_ctx

            with patch("asyncio.create_task") as mock_create_task:
                tools_mod._schedule_tool_event("get", "ent_xyz", None, None)
                mock_create_task.assert_not_called()
        finally:
            tools_mod._current_partner_id = original_partner_id
