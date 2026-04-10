"""Tests for SqlAuditEventRepository.

Verifies SQL insert and query logic using a mock asyncpg pool.
All tests are pure unit tests — no real DB connection required.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(conn_mock: AsyncMock) -> MagicMock:
    """Return a mock pool whose acquire() context manager yields conn_mock."""
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    return conn


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestSqlAuditEventRepositoryCreate:
    """Verify create() writes the correct SQL and parameters."""

    async def test_create_calls_insert_with_required_fields(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        event = {
            "partner_id": "partner-1",
            "actor_id": "actor-1",
            "actor_type": "partner",
            "operation": "task.create",
            "resource_type": "tasks",
            "resource_id": "task-abc",
            "changes_json": {"title": "New task"},
        }
        await repo.create(event)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        sql = call_args.args[0]
        params = call_args.args[1:]

        assert "INSERT INTO zenos.audit_events" in sql
        assert params[0] == "partner-1"   # partner_id
        assert params[1] == "actor-1"     # actor_id
        assert params[2] == "partner"     # actor_type
        assert params[3] == "task.create" # operation
        assert params[4] == "tasks"       # resource_type
        assert params[5] == "task-abc"    # resource_id
        # changes_json serialized as JSON string
        parsed = json.loads(params[6])
        assert parsed["title"] == "New task"

    async def test_create_defaults_actor_type_to_partner(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        event = {
            "partner_id": "partner-1",
            "actor_id": "actor-1",
            # actor_type omitted
            "operation": "ontology.entity.upsert",
            "resource_type": "entities",
        }
        await repo.create(event)

        call_args = conn.execute.call_args
        params = call_args.args[1:]
        assert params[2] == "partner"  # default actor_type

    async def test_create_handles_null_resource_id(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        event = {
            "partner_id": "partner-1",
            "actor_id": "actor-1",
            "operation": "task.create",
            "resource_type": "tasks",
            # resource_id omitted
        }
        await repo.create(event)

        call_args = conn.execute.call_args
        params = call_args.args[1:]
        assert params[5] is None  # resource_id is None

    async def test_create_serializes_empty_changes_json(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        event = {
            "partner_id": "partner-1",
            "actor_id": "actor-1",
            "operation": "task.create",
            "resource_type": "tasks",
            # changes_json omitted
        }
        await repo.create(event)

        call_args = conn.execute.call_args
        params = call_args.args[1:]
        assert params[6] == "{}"  # empty dict serialized


# ---------------------------------------------------------------------------
# list_events()
# ---------------------------------------------------------------------------


class TestSqlAuditEventRepositoryListEvents:
    """Verify list_events() builds WHERE clause correctly."""

    async def test_partner_id_filter_always_present(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        await repo.list_events(partner_id="partner-1")

        conn.fetch.assert_called_once()
        sql = conn.fetch.call_args.args[0]
        assert "partner_id = $1" in sql

    async def test_since_filter_appended(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        await repo.list_events(partner_id="partner-1", since=since)

        sql = conn.fetch.call_args.args[0]
        params = conn.fetch.call_args.args[1:]
        assert "timestamp >= $2" in sql
        assert since in params

    async def test_until_filter_appended(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        until = datetime(2026, 12, 31, tzinfo=timezone.utc)
        await repo.list_events(partner_id="partner-1", until=until)

        sql = conn.fetch.call_args.args[0]
        params = conn.fetch.call_args.args[1:]
        assert "timestamp <= $2" in sql
        assert until in params

    async def test_operation_filter_appended(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        await repo.list_events(partner_id="partner-1", operation="task.create")

        sql = conn.fetch.call_args.args[0]
        params = conn.fetch.call_args.args[1:]
        assert "operation = $2" in sql
        assert "task.create" in params

    async def test_actor_id_filter_appended(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        await repo.list_events(partner_id="partner-1", actor_id="actor-99")

        sql = conn.fetch.call_args.args[0]
        params = conn.fetch.call_args.args[1:]
        assert "actor_id = $2" in sql
        assert "actor-99" in params

    async def test_multiple_filters_use_incremental_params(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        until = datetime(2026, 12, 31, tzinfo=timezone.utc)
        await repo.list_events(
            partner_id="partner-1",
            since=since,
            until=until,
            operation="task.create",
            actor_id="actor-99",
        )

        sql = conn.fetch.call_args.args[0]
        params = conn.fetch.call_args.args[1:]
        assert "partner_id = $1" in sql
        assert "timestamp >= $2" in sql
        assert "timestamp <= $3" in sql
        assert "operation = $4" in sql
        assert "actor_id = $5" in sql
        assert len(params) == 5

    async def test_returns_list_of_dicts(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        # asyncpg Record mock
        mock_row = {"event_id": "uuid-1", "operation": "task.create", "partner_id": "partner-1"}
        conn.fetch = AsyncMock(return_value=[mock_row])
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        result = await repo.list_events(partner_id="partner-1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["operation"] == "task.create"

    async def test_limit_applied_in_query(self):
        from zenos.infrastructure.agent import SqlAuditEventRepository

        conn = _make_conn()
        pool = _make_pool(conn)
        repo = SqlAuditEventRepository(pool)

        await repo.list_events(partner_id="partner-1", limit=42)

        sql = conn.fetch.call_args.args[0]
        assert "LIMIT 42" in sql
