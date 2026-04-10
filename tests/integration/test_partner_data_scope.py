"""Integration tests for partner data scope (single-tenant shared partition).

These tests verify that when a non-admin partner has ``sharedPartnerId = admin.id``,
both the agent and admin see the same data.

The mechanism under test
------------------------
  tools.py line 114:
      current_partner_id.set(partner.get("sharedPartnerId") or partner.get("id", ""))

  dashboard_api.py line 125:
      effective_id = partner.get("sharedPartnerId") or partner["id"]

Both the MCP server (tools.py) and the Dashboard API compute ``effective_id`` before
setting ``current_partner_id``.  When the non-admin partner's ``sharedPartnerId``
equals the admin's id, they share the same partition.

What these tests verify
-----------------------
1. Agent context (current_partner_id = admin.id) uses admin's partition for writes.
2. Admin context (current_partner_id = admin.id) reads from the same partition.
3. An entity written in agent context is visible in admin context.
4. An entity written under an isolated (unshared) partner is NOT visible in admin
   context — confirming that the scoping is by partition_id and not global.

Test infrastructure
-------------------
Uses a stateful in-memory store (dict keyed by partner_id) instead of a real
PostgreSQL instance.  The mock pool captures every ``partner_id`` argument passed
to ``conn.execute`` and ``conn.fetch``, and routes reads to the same store.

⚠️  Mock test note: SQL writes are validated against an in-memory dict, not a real
PostgreSQL instance.  The test verifies ContextVar routing logic but does NOT
exercise the full SQL INSERT/SELECT path.  Real E2E coverage requires a live DB
(see tests/integration/test_sql_repo_integration.py).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Partners under test
# ---------------------------------------------------------------------------

ADMIN_ID = "admin-partner-001"
AGENT_ID = "agent-partner-002"        # sharedPartnerId = ADMIN_ID
ISOLATED_ID = "isolated-partner-003"  # no sharedPartnerId (wrong partition)

# ---------------------------------------------------------------------------
# Helpers: partner fixtures mirroring what tools.py / dashboard_api.py build
# ---------------------------------------------------------------------------


def _admin_partner() -> dict:
    """Admin partner: sharedPartnerId is absent/null — uses own id as partition."""
    return {"id": ADMIN_ID, "email": "admin@example.com", "isAdmin": True}


def _agent_partner() -> dict:
    """Non-admin agent partner: sharedPartnerId = ADMIN_ID → same partition as admin."""
    return {"id": AGENT_ID, "email": "agent@example.com", "isAdmin": False, "sharedPartnerId": ADMIN_ID}


def _effective_id(partner: dict) -> str:
    """Replicate the effective_id logic from tools.py line 114 and dashboard_api.py line 125."""
    return partner.get("sharedPartnerId") or partner["id"]


# ---------------------------------------------------------------------------
# In-memory store + mock pool factory
# ---------------------------------------------------------------------------


def _make_stateful_pool() -> tuple[MagicMock, dict[str, list[dict]]]:
    """Return (pool, store) where store maps partner_id → list of entity rows.

    The mock pool simulates:
      - conn.execute(INSERT ...): stores the entity in store[partner_id]
      - conn.fetch(SELECT ...):   reads from store[partner_id]
    """
    store: dict[str, list[dict]] = {}

    def _extract_partner_id_from_execute_args(sql: str, *args: Any) -> str | None:
        """Parse partner_id positional arg from INSERT args (position 2, 0-indexed)."""
        # In SqlEntityRepository.upsert:
        #   args: entity.id ($1), pid ($2), entity.name ($3), ...
        # So args[1] is the partner_id.
        if len(args) >= 2:
            return str(args[1])
        return None

    def _extract_partner_id_from_fetch_args(sql: str, *args: Any) -> str | None:
        """Parse partner_id positional arg from SELECT args.

        In SqlEntityRepository.list_all without filter:
            args[0] = pid
        """
        if args:
            return str(args[0])
        return None

    async def _execute(sql: str, *args: Any) -> str:
        if "INSERT INTO" in sql and "entities" in sql:
            pid = _extract_partner_id_from_execute_args(sql, *args)
            if pid:
                entity_id = str(args[0])
                entity_name = str(args[2]) if len(args) > 2 else "unknown"
                store.setdefault(pid, []).append({"id": entity_id, "name": entity_name, "_partner_id": pid})
        return "INSERT 0 1"

    async def _fetch(sql: str, *args: Any) -> list[dict]:
        if "SELECT" in sql and "entities" in sql:
            pid = _extract_partner_id_from_fetch_args(sql, *args)
            if pid:
                return [_make_entity_row(r) for r in store.get(pid, [])]
        return []

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=_execute)
    conn.fetch = AsyncMock(side_effect=_fetch)
    conn.fetchrow = AsyncMock(return_value=None)

    class _AsyncCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *a):
            pass

        def __await__(self):
            async def _r():
                return conn
            return _r().__await__()

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx())
    pool.release = AsyncMock()
    return pool, store


def _make_entity_row(raw: dict) -> MagicMock:
    """Build a mock asyncpg.Record from a stored entity dict."""
    defaults = {
        "id": raw.get("id", "ent-x"),
        "name": raw.get("name", "test"),
        "type": "product",
        "level": 1,
        "parent_id": None,
        "status": "active",
        "summary": "test summary",
        "tags_json": json.dumps({"what": ["testing"], "why": "test", "how": "pytest", "who": ["dev"]}),
        "details_json": None,
        "confirmed_by_user": False,
        "owner": None,
        "sources_json": json.dumps([]),
        "visibility": "public",
        "visible_to_roles": [],
        "visible_to_members": [],
        "visible_to_departments": [],
        "last_reviewed_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    row = MagicMock()
    row.__getitem__ = lambda self, key: defaults[key]
    row.__contains__ = lambda self, key: key in defaults
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPartnerDataScope:
    """Verify that agent and admin share the same partition via sharedPartnerId."""

    def test_effective_id_for_admin_is_own_id(self):
        """Admin partner's effective_id equals its own id (sharedPartnerId is absent)."""
        admin = _admin_partner()
        assert _effective_id(admin) == ADMIN_ID

    def test_effective_id_for_agent_is_admin_id(self):
        """Agent partner's effective_id equals admin_id (sharedPartnerId = admin.id)."""
        agent = _agent_partner()
        assert _effective_id(agent) == ADMIN_ID

    def test_effective_id_for_isolated_partner_is_own_id(self):
        """Partner without sharedPartnerId uses its own id as partition key."""
        isolated = {"id": ISOLATED_ID, "email": "x@example.com", "isAdmin": False}
        assert _effective_id(isolated) == ISOLATED_ID

    @pytest.mark.asyncio
    async def test_agent_write_visible_to_admin(self):
        """Entity written in agent context is visible when reading in admin context.

        Simulates:
          1. Agent computes effective_id = admin.id (via sharedPartnerId)
          2. Agent sets current_partner_id = admin.id
          3. Agent writes entity → stored under admin.id partition
          4. Admin sets current_partner_id = admin.id
          5. Admin reads list_all() → entity is found
        """
        from zenos.domain.knowledge import Entity, Tags
        from zenos.infrastructure.context import current_partner_id
        from zenos.infrastructure.knowledge import SqlEntityRepository

        pool, store = _make_stateful_pool()
        repo = SqlEntityRepository(pool)

        agent = _agent_partner()
        admin = _admin_partner()

        # Step 1-3: Agent writes using effective_id = admin.id
        agent_effective_id = _effective_id(agent)  # == ADMIN_ID
        token = current_partner_id.set(agent_effective_id)
        try:
            entity = Entity(
                name="agent-written-entity",
                type="product",
                summary="Written by agent, should be visible to admin",
                tags=Tags(what=["test"], why="scope test", how="pytest", who=["agent"]),
                level=1,
                status="active",
            )
            saved = await repo.upsert(entity)
        finally:
            current_partner_id.reset(token)

        assert saved.id is not None

        # Verify the entity was stored under admin's partition
        assert ADMIN_ID in store, "Entity should be stored under admin_id partition"
        stored_ids = [r["id"] for r in store[ADMIN_ID]]
        assert saved.id in stored_ids

        # Step 4-5: Admin reads using own id
        admin_effective_id = _effective_id(admin)  # == ADMIN_ID
        token = current_partner_id.set(admin_effective_id)
        try:
            entities = await repo.list_all()
        finally:
            current_partner_id.reset(token)

        entity_ids = {e.id for e in entities}
        assert saved.id in entity_ids, (
            f"Admin should see agent-written entity {saved.id!r} in list_all(). "
            f"Found: {entity_ids}"
        )

    @pytest.mark.asyncio
    async def test_isolated_partner_write_not_visible_to_admin(self):
        """Entity written by an isolated (unshared) partner is NOT visible to admin.

        This confirms scoping works correctly: data written under ISOLATED_ID
        does not appear in admin's list_all().
        """
        from zenos.domain.knowledge import Entity, Tags
        from zenos.infrastructure.context import current_partner_id
        from zenos.infrastructure.knowledge import SqlEntityRepository

        pool, store = _make_stateful_pool()
        repo = SqlEntityRepository(pool)

        # Isolated partner writes under its own partition
        token = current_partner_id.set(ISOLATED_ID)
        try:
            entity = Entity(
                name="isolated-partner-entity",
                type="product",
                summary="Written by isolated partner",
                tags=Tags(what=["test"], why="isolation test", how="pytest", who=["isolated"]),
                level=1,
                status="active",
            )
            saved = await repo.upsert(entity)
        finally:
            current_partner_id.reset(token)

        # Admin reads — should NOT see isolated partner's entity
        admin_effective_id = _effective_id(_admin_partner())
        token = current_partner_id.set(admin_effective_id)
        try:
            entities = await repo.list_all()
        finally:
            current_partner_id.reset(token)

        entity_ids = {e.id for e in entities}
        assert saved.id not in entity_ids, (
            f"Admin should NOT see isolated partner's entity {saved.id!r}. "
            f"Partition isolation failed."
        )

    @pytest.mark.asyncio
    async def test_context_var_routes_to_correct_partition(self):
        """current_partner_id ContextVar value is passed as partner_id to SQL queries.

        Verifies that SqlEntityRepository.upsert passes whatever value is in
        current_partner_id directly to the SQL INSERT as the partner_id column.
        """
        from zenos.domain.knowledge import Entity, Tags
        from zenos.infrastructure.context import current_partner_id
        from zenos.infrastructure.knowledge import SqlEntityRepository

        pool, store = _make_stateful_pool()
        repo = SqlEntityRepository(pool)

        token = current_partner_id.set(ADMIN_ID)
        try:
            entity = Entity(
                name="contextvar-routing-entity",
                type="product",
                summary="ContextVar routing test",
                tags=Tags(what=["test"], why="routing", how="pytest", who=["dev"]),
                level=1,
                status="active",
            )
            saved = await repo.upsert(entity)
        finally:
            current_partner_id.reset(token)

        # Confirm entity stored under ADMIN_ID
        assert ADMIN_ID in store
        stored_ids = [r["id"] for r in store[ADMIN_ID]]
        assert saved.id in stored_ids

        # Confirm nothing stored under AGENT_ID (different partition)
        assert AGENT_ID not in store or saved.id not in [r["id"] for r in store.get(AGENT_ID, [])]

    @pytest.mark.asyncio
    async def test_upsert_uses_context_partner_id_in_sql(self):
        """SqlEntityRepository.upsert passes current_partner_id to SQL execute call.

        Directly inspects the mock conn.execute call arguments to confirm
        the partner_id positional parameter equals what was set in the ContextVar.
        """
        from zenos.domain.knowledge import Entity, Tags
        from zenos.infrastructure.context import current_partner_id
        from zenos.infrastructure.knowledge import SqlEntityRepository

        pool, store = _make_stateful_pool()

        # Capture the raw execute calls to inspect partner_id arg
        execute_calls: list[tuple] = []

        original_side_effect = pool.acquire.return_value.__class__

        # Re-build pool with call recorder
        conn_spy = AsyncMock()

        async def _spy_execute(sql: str, *args: Any) -> str:
            execute_calls.append((sql, args))
            return "INSERT 0 1"

        conn_spy.execute = AsyncMock(side_effect=_spy_execute)
        conn_spy.fetch = AsyncMock(return_value=[])
        conn_spy.fetchrow = AsyncMock(return_value=None)

        class _AsyncCtx:
            async def __aenter__(self):
                return conn_spy

            async def __aexit__(self, *a):
                pass

            def __await__(self):
                async def _r():
                    return conn_spy
                return _r().__await__()

        pool_spy = MagicMock()
        pool_spy.acquire = MagicMock(return_value=_AsyncCtx())
        pool_spy.release = AsyncMock()

        repo = SqlEntityRepository(pool_spy)

        token = current_partner_id.set(ADMIN_ID)
        try:
            entity = Entity(
                name="sql-param-check-entity",
                type="product",
                summary="SQL parameter check",
                tags=Tags(what=["test"], why="sql check", how="pytest", who=["dev"]),
                level=1,
                status="active",
            )
            await repo.upsert(entity)
        finally:
            current_partner_id.reset(token)

        assert execute_calls, "conn.execute should have been called"
        # args[1] in the INSERT is the partner_id (position $2 in SQL)
        insert_call = next(
            (c for c in execute_calls if "INSERT INTO" in c[0] and "entities" in c[0]),
            None,
        )
        assert insert_call is not None, "No INSERT call found"
        positional_args = insert_call[1]
        # positional_args[1] = pid (second bind param after entity.id)
        assert len(positional_args) >= 2
        assert positional_args[1] == ADMIN_ID, (
            f"partner_id in SQL should be {ADMIN_ID!r}, got {positional_args[1]!r}"
        )
