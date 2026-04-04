"""Tests for SqlWorkJournalRepository.

All tests use a mock asyncpg pool — no real DB connection required.
Coverage includes: create, count, list_recent, list_oldest_originals,
delete_by_ids, create_summary, and filtering logic.

Note: These are mock-only unit tests (no real DB). Marked accordingly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(conn_mock: AsyncMock) -> MagicMock:
    """Return a mock pool whose acquire() yields conn_mock."""
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetch = AsyncMock(return_value=[])
    return conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_create_returns_uuid_string():
    """create() inserts a row and returns a non-empty UUID string."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    repo = SqlWorkJournalRepository(_make_pool(conn))

    result = await repo.create(
        partner_id="p1",
        summary="finished the feature",
        project="ZenOS",
        flow_type="feature",
        tags=["backend"],
    )

    assert isinstance(result, str)
    assert len(result) == 36  # UUID format
    conn.execute.assert_awaited_once()
    # Verify partner_id and summary are passed
    call_args = conn.execute.call_args[0]
    assert "p1" in call_args
    assert "finished the feature" in call_args


async def test_create_uses_empty_list_when_tags_is_none():
    """create() defaults tags to [] when not provided."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    repo = SqlWorkJournalRepository(_make_pool(conn))

    await repo.create(partner_id="p1", summary="no tags here")

    call_args = conn.execute.call_args[0]
    # The last positional arg to execute is the tags list
    assert [] in call_args


async def test_count_returns_integer():
    """count() returns the fetchval result as an integer."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    conn.fetchval = AsyncMock(return_value=7)
    repo = SqlWorkJournalRepository(_make_pool(conn))

    result = await repo.count(partner_id="p1")

    assert result == 7
    conn.fetchval.assert_awaited_once()
    assert "p1" in conn.fetchval.call_args[0]


async def test_list_recent_returns_entries_and_total():
    """list_recent() returns (list[dict], total) tuple."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    _ts = datetime(2026, 4, 4, tzinfo=timezone.utc)
    row = {
        "id": "abc",
        "created_at": _ts,
        "project": "ZenOS",
        "flow_type": "feature",
        "summary": "done",
        "tags": ["x"],
        "is_summary": False,
    }
    conn = _make_conn()
    conn.fetchval = AsyncMock(return_value=3)
    conn.fetch = AsyncMock(return_value=[row])
    repo = SqlWorkJournalRepository(_make_pool(conn))

    entries, total = await repo.list_recent(partner_id="p1", limit=10)

    assert total == 3
    assert len(entries) == 1
    assert entries[0]["summary"] == "done"


async def test_list_recent_applies_project_filter():
    """list_recent() adds project to SQL when specified."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    conn.fetchval = AsyncMock(return_value=0)
    repo = SqlWorkJournalRepository(_make_pool(conn))

    await repo.list_recent(partner_id="p1", limit=5, project="ZenOS")

    # The SQL for fetchval should include project filter
    fetchval_call = conn.fetchval.call_args[0]
    assert "ZenOS" in fetchval_call


async def test_list_oldest_originals_returns_list():
    """list_oldest_originals() returns oldest non-summary entries."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    conn.fetch = AsyncMock(return_value=[])
    repo = SqlWorkJournalRepository(_make_pool(conn))

    result = await repo.list_oldest_originals(partner_id="p1", limit=5)

    assert result == []
    fetch_call = conn.fetch.call_args[0]
    sql = fetch_call[0]
    assert "is_summary = FALSE" in sql
    assert "ASC" in sql


async def test_delete_by_ids_skips_empty_list():
    """delete_by_ids() does not execute SQL when ids is empty."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    repo = SqlWorkJournalRepository(_make_pool(conn))

    await repo.delete_by_ids(partner_id="p1", ids=[])

    conn.execute.assert_not_awaited()


async def test_delete_by_ids_passes_ids():
    """delete_by_ids() executes DELETE with partner_id and ids."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    repo = SqlWorkJournalRepository(_make_pool(conn))

    await repo.delete_by_ids(partner_id="p1", ids=["id1", "id2"])

    conn.execute.assert_awaited_once()
    call_args = conn.execute.call_args[0]
    assert "p1" in call_args
    assert ["id1", "id2"] in call_args


async def test_create_summary_sets_is_summary_true():
    """create_summary() inserts row with is_summary=TRUE in SQL."""
    from zenos.infrastructure.sql_repo import SqlWorkJournalRepository

    conn = _make_conn()
    repo = SqlWorkJournalRepository(_make_pool(conn))
    as_of = datetime(2026, 4, 4, tzinfo=timezone.utc)

    result = await repo.create_summary(
        partner_id="p1",
        summary="compressed summary",
        project="ZenOS",
        flow_type="feature",
        tags=["tag1"],
        as_of=as_of,
    )

    assert isinstance(result, str)
    assert len(result) == 36
    conn.execute.assert_awaited_once()
    # SQL should reference TRUE
    sql = conn.execute.call_args[0][0]
    assert "TRUE" in sql
    call_args = conn.execute.call_args[0]
    assert "compressed summary" in call_args
    assert as_of in call_args
