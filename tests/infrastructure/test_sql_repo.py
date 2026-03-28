"""Tests for sql_repo.py — SQL repository implementations.

All tests use mock asyncpg pool/connection objects to avoid a real database.
Each test validates:
  - SQL contains expected WHERE clauses (partner_id scoping)
  - row → domain model mapping correctness
  - join table sync logic
  - upsert (new vs existing) path

NOTE: These are mock-based tests (⚠️ mock tests). They verify branch logic and
SQL construction but do NOT hit a real PostgreSQL instance. Integration tests
against a real DB are tracked separately.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────

PARTNER_ID = "partner_abc"
NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _set_partner(monkeypatch):
    """Patch current_partner_id to return PARTNER_ID."""
    monkeypatch.setattr(
        "zenos.infrastructure.sql_repo.current_partner_id",
        MagicMock(get=MagicMock(return_value=PARTNER_ID)),
    )


def _make_row(**kwargs) -> MagicMock:
    """Build a mock asyncpg.Record dict-like object."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: kwargs[key]
    row.__contains__ = lambda self, key: key in kwargs
    return row


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


def _make_pool(fetchrow=None, fetch=None, execute=None, executemany=None):
    """Build a mock asyncpg pool whose acquire() context manager returns a conn."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock(return_value=execute)
    conn.executemany = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=_FakeTransaction())

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncContextManager(conn))
    return pool, conn


class _AsyncContextManager:
    """Minimal async context manager wrapping a value."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        pass


# ─────────────────────────────────────────────────────────────────────────────
# SqlEntityRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlEntityRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _entity_row(self, eid: str = "ent1") -> dict:
        return {
            "id": eid,
            "name": "Test Entity",
            "type": "module",
            "level": 2,
            "parent_id": None,
            "status": "active",
            "summary": "A test entity",
            "tags_json": json.dumps({"what": ["x"], "why": "because", "how": "do it", "who": ["Alice"]}),
            "details_json": None,
            "confirmed_by_user": False,
            "owner": "Alice",
            "sources_json": json.dumps([{"uri": "https://example.com", "label": "link", "type": "github"}]),
            "visibility": "public",
            "last_reviewed_at": None,
            "created_at": NOW,
            "updated_at": NOW,
        }

    def test_get_by_id_returns_entity_when_found(self, monkeypatch):
        """get_by_id maps row columns to Entity domain model correctly."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository

        row = _make_row(**self._entity_row("ent1"))
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlEntityRepository(pool)

        import asyncio
        entity = asyncio.get_event_loop().run_until_complete(repo.get_by_id("ent1"))

        assert entity is not None
        assert entity.id == "ent1"
        assert entity.name == "Test Entity"
        assert entity.type == "module"
        assert entity.tags.what == ["x"]
        assert entity.tags.why == "because"
        assert entity.owner == "Alice"
        assert entity.confirmed_by_user is False
        # Verify partner_id scoping in SQL
        call_sql = conn.fetchrow.call_args[0][0]
        assert "partner_id" in call_sql
        assert conn.fetchrow.call_args[0][2] == PARTNER_ID

    def test_get_by_id_returns_none_when_missing(self):
        """get_by_id returns None when row not found."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        import asyncio

        pool, _ = _make_pool(fetchrow=None)
        repo = SqlEntityRepository(pool)
        entity = asyncio.get_event_loop().run_until_complete(repo.get_by_id("missing"))
        assert entity is None

    def test_list_all_with_type_filter_includes_type_in_sql(self):
        """list_all passes type filter via SQL AND clause."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        import asyncio

        row = _make_row(**self._entity_row("ent1"))
        pool, conn = _make_pool(fetch=[row])
        repo = SqlEntityRepository(pool)

        asyncio.get_event_loop().run_until_complete(repo.list_all(type_filter="module"))

        sql = conn.fetch.call_args[0][0]
        assert "type" in sql
        assert PARTNER_ID == conn.fetch.call_args[0][1]

    def test_list_all_without_type_filter(self):
        """list_all without filter only scopes by partner_id."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlEntityRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(repo.list_all())

        assert result == []
        sql = conn.fetch.call_args[0][0]
        assert "partner_id" in sql

    def test_upsert_new_entity_generates_id(self):
        """upsert with id=None generates a new ID."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        from zenos.domain.models import Entity, Tags
        import asyncio

        pool, conn = _make_pool()
        repo = SqlEntityRepository(pool)
        entity = Entity(
            name="New Entity", type="module", summary="s",
            tags=Tags(what=[], why="", how="", who=[]),
        )
        assert entity.id is None

        result = asyncio.get_event_loop().run_until_complete(repo.upsert(entity))

        assert result.id is not None
        assert len(result.id) == 32  # uuid4().hex

    def test_upsert_existing_entity_keeps_id(self):
        """upsert with existing id preserves the ID."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        from zenos.domain.models import Entity, Tags
        import asyncio

        pool, _ = _make_pool()
        repo = SqlEntityRepository(pool)
        entity = Entity(
            id="existing_id", name="Existing", type="module", summary="s",
            tags=Tags(what=[], why="", how="", who=[]),
        )

        result = asyncio.get_event_loop().run_until_complete(repo.upsert(entity))
        assert result.id == "existing_id"

    def test_list_unconfirmed_queries_confirmed_false(self):
        """list_unconfirmed filters on confirmed_by_user = false."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlEntityRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_unconfirmed())

        sql = conn.fetch.call_args[0][0]
        assert "confirmed_by_user" in sql
        assert "false" in sql.lower()
        assert PARTNER_ID == conn.fetch.call_args[0][1]

    def test_list_by_parent_scopes_to_partner(self):
        """list_by_parent passes both parent_id and partner_id."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlEntityRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_by_parent("parent1"))

        args = conn.fetch.call_args[0]
        assert "parent_id" in args[0]
        assert "parent1" in args
        assert PARTNER_ID in args


# ─────────────────────────────────────────────────────────────────────────────
# SqlRelationshipRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlRelationshipRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _rel_row(self, rid: str = "rel1") -> dict:
        return {
            "id": rid,
            "source_entity_id": "src1",
            "target_entity_id": "tgt1",  # SQL column name
            "type": "depends_on",
            "description": "A depends on B",
            "confirmed_by_user": False,
        }

    def test_row_maps_target_entity_id_to_target_id(self):
        """Row's target_entity_id column maps to Relationship.target_id domain field."""
        from zenos.infrastructure.sql_repo import _row_to_relationship

        row = _make_row(**self._rel_row())
        rel = _row_to_relationship(row)

        assert rel.target_id == "tgt1"  # domain field
        assert rel.source_entity_id == "src1"

    def test_list_by_entity_queries_both_directions(self):
        """list_by_entity includes both source and target entity_id in WHERE."""
        from zenos.infrastructure.sql_repo import SqlRelationshipRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlRelationshipRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_by_entity("ent1"))

        sql = conn.fetch.call_args[0][0]
        assert "source_entity_id" in sql
        assert "target_entity_id" in sql
        assert PARTNER_ID == conn.fetch.call_args[0][2]

    def test_find_duplicate_passes_all_three_params(self):
        """find_duplicate queries source, target, type, and partner_id."""
        from zenos.infrastructure.sql_repo import SqlRelationshipRepository
        import asyncio

        pool, conn = _make_pool(fetchrow=None)
        repo = SqlRelationshipRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.find_duplicate("src1", "tgt1", "depends_on")
        )

        args = conn.fetchrow.call_args[0]
        assert "source_entity_id" in args[0]
        assert "target_entity_id" in args[0]
        assert "type" in args[0]
        assert PARTNER_ID in args

    def test_add_generates_id_for_new_relationship(self):
        """add() with rel.id=None generates a new id."""
        from zenos.infrastructure.sql_repo import SqlRelationshipRepository
        from zenos.domain.models import Relationship
        import asyncio

        pool, _ = _make_pool()
        repo = SqlRelationshipRepository(pool)
        rel = Relationship(source_entity_id="src", target_id="tgt", type="depends_on", description="d")
        assert rel.id is None

        result = asyncio.get_event_loop().run_until_complete(repo.add(rel))
        assert result.id is not None

    def test_add_maps_target_id_to_target_entity_id_in_sql(self):
        """add() stores rel.target_id as target_entity_id in SQL."""
        from zenos.infrastructure.sql_repo import SqlRelationshipRepository
        from zenos.domain.models import Relationship
        import asyncio

        pool, conn = _make_pool()
        repo = SqlRelationshipRepository(pool)
        rel = Relationship(
            id="rel1", source_entity_id="src", target_id="tgt99",
            type="depends_on", description="d",
        )
        asyncio.get_event_loop().run_until_complete(repo.add(rel))

        # target_entity_id should be "tgt99" in INSERT call
        exec_args = conn.execute.call_args[0]
        assert "tgt99" in exec_args

    def test_list_all_scopes_by_partner_id(self):
        """list_all queries relationships filtered by partner_id."""
        from zenos.infrastructure.sql_repo import SqlRelationshipRepository
        import asyncio

        row = _make_row(**self._rel_row("rel1"))
        pool, conn = _make_pool(fetch=[row])
        repo = SqlRelationshipRepository(pool)

        results = asyncio.get_event_loop().run_until_complete(repo.list_all())

        assert len(results) == 1
        assert results[0].id == "rel1"
        assert results[0].target_id == "tgt1"
        sql = conn.fetch.call_args[0][0]
        assert "partner_id" in sql
        assert conn.fetch.call_args[0][1] == PARTNER_ID

    def test_list_all_returns_empty_when_no_rows(self):
        """list_all returns an empty list when no relationships exist."""
        from zenos.infrastructure.sql_repo import SqlRelationshipRepository
        import asyncio

        pool, _ = _make_pool(fetch=[])
        repo = SqlRelationshipRepository(pool)
        results = asyncio.get_event_loop().run_until_complete(repo.list_all())
        assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# SqlDocumentRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlDocumentRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _doc_row(self, did: str = "doc1") -> dict:
        return {
            "id": did,
            "title": "A Doc",
            "source_json": json.dumps({"type": "github", "uri": "https://g.com/f", "adapter": "github"}),
            "tags_json": json.dumps({"what": ["spec"], "why": "reasoning", "how": "usage", "who": ["dev"]}),
            "summary": "Summary here",
            "status": "current",
            "confirmed_by_user": False,
            "last_reviewed_at": None,
            "created_at": NOW,
            "updated_at": NOW,
        }

    def test_row_to_document_maps_source_correctly(self):
        """_row_to_document maps source_json to Source domain model."""
        from zenos.infrastructure.sql_repo import _row_to_document

        row = _make_row(**self._doc_row())
        doc = _row_to_document(row, ["ent1", "ent2"])

        assert doc.source.type == "github"
        assert doc.source.uri == "https://g.com/f"
        assert doc.source.adapter == "github"
        assert doc.linked_entity_ids == ["ent1", "ent2"]

    def test_upsert_syncs_document_entities_join_table(self):
        """upsert() deletes old rows and inserts new rows in document_entities."""
        from zenos.infrastructure.sql_repo import SqlDocumentRepository
        from zenos.domain.models import Document, DocumentTags, Source
        import asyncio

        pool, conn = _make_pool()
        repo = SqlDocumentRepository(pool)

        doc = Document(
            title="T", source=Source(type="github", uri="u", adapter="a"),
            tags=DocumentTags(what=[], why="", how="", who=[]),
            summary="s", linked_entity_ids=["e1", "e2"],
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(doc))

        # DELETE and INSERT into document_entities should both be called
        execute_calls = [c[0][0] for c in conn.execute.call_args_list]
        assert any("document_entities" in sql and "DELETE" in sql for sql in execute_calls)
        assert conn.executemany.called

    def test_update_linked_entities_replaces_rows(self):
        """update_linked_entities() deletes then inserts in document_entities."""
        from zenos.infrastructure.sql_repo import SqlDocumentRepository
        import asyncio

        pool, conn = _make_pool()
        repo = SqlDocumentRepository(pool)

        asyncio.get_event_loop().run_until_complete(
            repo.update_linked_entities("doc1", ["e1"])
        )

        execute_calls = [c[0][0] for c in conn.execute.call_args_list]
        assert any("document_entities" in sql and "DELETE" in sql for sql in execute_calls)
        assert conn.executemany.called

    def test_list_by_entity_joins_document_entities(self):
        """list_by_entity uses JOIN document_entities in SQL."""
        from zenos.infrastructure.sql_repo import SqlDocumentRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlDocumentRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_by_entity("ent1"))

        sql = conn.fetch.call_args[0][0]
        assert "document_entities" in sql
        assert "JOIN" in sql.upper()


# ─────────────────────────────────────────────────────────────────────────────
# SqlProtocolRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlProtocolRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _proto_row(self, pid: str = "proto1") -> dict:
        return {
            "id": pid,
            "entity_id": "ent1",
            "entity_name": "MyEntity",
            "content_json": json.dumps({"what": {}, "why": {}, "how": {}, "who": {}}),
            "gaps_json": json.dumps([{"description": "gap A", "priority": "red"}]),
            "version": "1.0",
            "confirmed_by_user": False,
            "generated_at": NOW,
            "updated_at": NOW,
        }

    def test_row_to_protocol_parses_gaps(self):
        """_row_to_protocol parses gaps_json into list[Gap]."""
        from zenos.infrastructure.sql_repo import _row_to_protocol

        row = _make_row(**self._proto_row())
        proto = _row_to_protocol(row)

        assert len(proto.gaps) == 1
        assert proto.gaps[0].description == "gap A"
        assert proto.gaps[0].priority == "red"

    def test_get_by_entity_scopes_to_partner(self):
        """get_by_entity includes partner_id in query."""
        from zenos.infrastructure.sql_repo import SqlProtocolRepository
        import asyncio

        pool, conn = _make_pool(fetchrow=None)
        repo = SqlProtocolRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.get_by_entity("ent1"))

        args = conn.fetchrow.call_args[0]
        assert "partner_id" in args[0]
        assert PARTNER_ID in args

    def test_upsert_generates_id_for_new_protocol(self):
        """upsert() with id=None generates a new id."""
        from zenos.infrastructure.sql_repo import SqlProtocolRepository
        from zenos.domain.models import Protocol
        import asyncio

        pool, _ = _make_pool()
        repo = SqlProtocolRepository(pool)
        proto = Protocol(entity_id="ent1", entity_name="Ent", content={})
        assert proto.id is None

        result = asyncio.get_event_loop().run_until_complete(repo.upsert(proto))
        assert result.id is not None


# ─────────────────────────────────────────────────────────────────────────────
# SqlBlindspotRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlBlindspotRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _bs_row(self, bid: str = "bs1") -> dict:
        return {
            "id": bid,
            "description": "Missing ownership",
            "severity": "red",
            "suggested_action": "Add owner",
            "status": "open",
            "confirmed_by_user": False,
            "created_at": NOW,
        }

    def test_row_to_blindspot_maps_fields(self):
        """_row_to_blindspot correctly maps all row fields."""
        from zenos.infrastructure.sql_repo import _row_to_blindspot

        row = _make_row(**self._bs_row())
        bs = _row_to_blindspot(row, ["ent1"])

        assert bs.id == "bs1"
        assert bs.severity == "red"
        assert bs.related_entity_ids == ["ent1"]
        assert bs.status == "open"

    def test_add_syncs_blindspot_entities_join_table(self):
        """add() syncs blindspot_entities join table (DELETE + INSERT)."""
        from zenos.infrastructure.sql_repo import SqlBlindspotRepository
        from zenos.domain.models import Blindspot
        import asyncio

        pool, conn = _make_pool()
        repo = SqlBlindspotRepository(pool)
        bs = Blindspot(
            description="d", severity="red", related_entity_ids=["e1"],
            suggested_action="Fix it",
        )
        asyncio.get_event_loop().run_until_complete(repo.add(bs))

        execute_calls = [c[0][0] for c in conn.execute.call_args_list]
        assert any("blindspot_entities" in sql and "DELETE" in sql for sql in execute_calls)
        assert conn.executemany.called

    def test_list_all_with_entity_filter_uses_join(self):
        """list_all(entity_id=...) uses JOIN blindspot_entities."""
        from zenos.infrastructure.sql_repo import SqlBlindspotRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlBlindspotRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_all(entity_id="ent1"))

        sql = conn.fetch.call_args[0][0]
        assert "blindspot_entities" in sql
        assert "JOIN" in sql.upper()

    def test_list_all_with_severity_filter(self):
        """list_all(severity=...) includes severity in WHERE."""
        from zenos.infrastructure.sql_repo import SqlBlindspotRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlBlindspotRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_all(severity="red"))

        sql = conn.fetch.call_args[0][0]
        assert "severity" in sql

    def test_add_generates_id(self):
        """add() with id=None generates a new id."""
        from zenos.infrastructure.sql_repo import SqlBlindspotRepository
        from zenos.domain.models import Blindspot
        import asyncio

        pool, _ = _make_pool()
        repo = SqlBlindspotRepository(pool)
        bs = Blindspot(
            description="d", severity="green", related_entity_ids=[],
            suggested_action="s",
        )
        assert bs.id is None

        result = asyncio.get_event_loop().run_until_complete(repo.add(bs))
        assert result.id is not None


# ─────────────────────────────────────────────────────────────────────────────
# SqlTaskRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlTaskRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _task_row(self, tid: str = "task1") -> dict:
        return {
            "id": tid,
            "title": "Fix bug",
            "description": "A bug exists",
            "status": "todo",
            "priority": "high",
            "priority_reason": "urgent",
            "assignee": "Bob",
            "assignee_role_id": None,
            "created_by": "Alice",
            "linked_protocol": None,
            "linked_blindspot": None,
            "source_type": "manual",
            "context_summary": "",
            "due_date": None,
            "blocked_reason": None,
            "acceptance_criteria_json": json.dumps(["criterion 1"]),
            "completed_by": None,
            "confirmed_by_creator": False,
            "rejection_reason": None,
            "result": None,
            "project": "zenos",
            "created_at": NOW,
            "updated_at": NOW,
            "completed_at": None,
        }

    def test_row_to_task_maps_linked_and_blocked(self):
        """_row_to_task maps linked_entities and blocked_by from parameters."""
        from zenos.infrastructure.sql_repo import _row_to_task

        row = _make_row(**self._task_row())
        task = _row_to_task(row, ["e1", "e2"], ["task2"])

        assert task.linked_entities == ["e1", "e2"]
        assert task.blocked_by == ["task2"]
        assert task.acceptance_criteria == ["criterion 1"]

    def test_row_to_task_maps_assignee_role_id(self):
        """_row_to_task reads assignee_role_id from the row."""
        from zenos.infrastructure.sql_repo import _row_to_task

        row_data = self._task_row()
        row_data["assignee_role_id"] = "role-42"
        row = _make_row(**row_data)
        task = _row_to_task(row, [], [])

        assert task.assignee_role_id == "role-42"

    def test_upsert_includes_assignee_role_id_in_sql(self):
        """upsert() INSERT SQL contains assignee_role_id column."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        from zenos.domain.models import Task
        import asyncio

        pool, conn = _make_pool()
        repo = SqlTaskRepository(pool)
        task = Task(
            title="T", status="todo", priority="medium", created_by="Alice",
            assignee_role_id="role-99",
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(task))

        execute_sql = conn.execute.call_args_list[0][0][0]
        assert "assignee_role_id" in execute_sql
        # Verify the value was passed in the binding arguments
        execute_args = conn.execute.call_args_list[0][0]
        assert "role-99" in execute_args

    def test_get_by_id_fetches_join_tables(self):
        """get_by_id fetches task_entities and task_blockers for the task."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        task_row = _make_row(**self._task_row("task1"))
        pool, conn = _make_pool(fetchrow=task_row, fetch=[])
        repo = SqlTaskRepository(pool)

        asyncio.get_event_loop().run_until_complete(repo.get_by_id("task1"))

        all_fetch_calls = [c[0][0] for c in conn.fetch.call_args_list]
        assert any("task_entities" in sql for sql in all_fetch_calls)
        assert any("task_blockers" in sql for sql in all_fetch_calls)

    def test_upsert_syncs_task_entities_and_task_blockers(self):
        """upsert() syncs both task_entities and task_blockers join tables."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        from zenos.domain.models import Task
        import asyncio

        pool, conn = _make_pool()
        repo = SqlTaskRepository(pool)
        task = Task(
            title="T", status="todo", priority="medium", created_by="Alice",
            linked_entities=["e1"], blocked_by=["task2"],
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(task))

        execute_calls = [c[0][0] for c in conn.execute.call_args_list]
        assert any("task_entities" in sql and "DELETE" in sql for sql in execute_calls)
        assert any("task_blockers" in sql and "DELETE" in sql for sql in execute_calls)
        assert conn.executemany.call_count >= 2

    def test_list_all_with_status_uses_sql_in(self):
        """list_all(status=[...]) uses SQL IN clause instead of client filter."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.list_all(status=["todo", "in_progress"])
        )

        # fetch is called for the main query first
        main_sql = conn.fetch.call_args_list[0][0][0]
        assert "IN" in main_sql.upper()
        assert "partner_id" in main_sql

    def test_list_all_with_linked_entity_uses_join(self):
        """list_all(linked_entity=...) joins task_entities."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.list_all(linked_entity="ent1")
        )

        main_sql = conn.fetch.call_args_list[0][0][0]
        assert "task_entities" in main_sql
        assert "JOIN" in main_sql.upper()

    def test_list_all_excludes_archived_by_default(self):
        """list_all without include_archived excludes archived tasks in SQL."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_all())

        main_sql = conn.fetch.call_args_list[0][0][0]
        assert "archived" in main_sql

    def test_list_blocked_by_queries_blocker_task_id(self):
        """list_blocked_by queries task_blockers by blocker_task_id."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_blocked_by("task1"))

        sql = conn.fetch.call_args_list[0][0][0]
        assert "blocker_task_id" in sql
        assert "task_blockers" in sql

    def test_list_pending_review_filters_review_status(self):
        """list_pending_review filters on status='review' and confirmed_by_creator=false."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_pending_review())

        sql = conn.fetch.call_args_list[0][0][0]
        assert "review" in sql
        assert "confirmed_by_creator" in sql
        assert PARTNER_ID == conn.fetch.call_args_list[0][0][1]

    def test_upsert_new_task_generates_id(self):
        """upsert() with id=None generates a new id."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        from zenos.domain.models import Task
        import asyncio

        pool, _ = _make_pool()
        repo = SqlTaskRepository(pool)
        task = Task(title="T", status="backlog", priority="low", created_by="X")
        assert task.id is None

        result = asyncio.get_event_loop().run_until_complete(repo.upsert(task))
        assert result.id is not None


# ─────────────────────────────────────────────────────────────────────────────
# SqlPartnerKeyValidator
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlPartnerKeyValidator:

    @pytest.mark.asyncio
    async def test_validate_returns_partner_data_for_known_key(self, monkeypatch):
        """validate() returns partner dict for a known API key."""
        from zenos.infrastructure.sql_repo import SqlPartnerKeyValidator

        row = _make_row(
            id="p1", email="a@b.com", display_name="Alice",
            api_key="secret_key", authorized_entity_ids=[],  # pragma: allowlist secret
            status="active", is_admin=False, shared_partner_id=None,
            default_project="zenos",
        )

        async def mock_refresh(self_inner):
            self_inner._cache = {
                "secret_key": {
                    "id": "p1", "email": "a@b.com", "displayName": "Alice",
                    "apiKey": "secret_key", "authorizedEntityIds": [],  # pragma: allowlist secret
                    "status": "active", "isAdmin": False,
                    "sharedPartnerId": None, "defaultProject": "zenos",
                }
            }
            self_inner._cache_ts = 9999999999.0  # far future

        with patch.object(SqlPartnerKeyValidator, "_refresh_cache", mock_refresh):
            validator = SqlPartnerKeyValidator(ttl=300)
            result = await validator.validate("secret_key")

        assert result is not None
        assert result["id"] == "p1"
        assert result["displayName"] == "Alice"

    @pytest.mark.asyncio
    async def test_validate_returns_none_for_unknown_key(self, monkeypatch):
        """validate() returns None for an unrecognised key."""
        from zenos.infrastructure.sql_repo import SqlPartnerKeyValidator

        async def mock_refresh(self_inner):
            self_inner._cache = {}
            self_inner._cache_ts = 9999999999.0

        with patch.object(SqlPartnerKeyValidator, "_refresh_cache", mock_refresh):
            validator = SqlPartnerKeyValidator(ttl=300)
            result = await validator.validate("bad_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_cache_queries_active_partners(self, monkeypatch):
        """_refresh_cache queries partners WHERE status = 'active'."""
        from zenos.infrastructure.sql_repo import SqlPartnerKeyValidator

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool_mock = MagicMock()
        pool_mock.acquire = MagicMock(return_value=_AsyncContextManager(conn))

        with patch("zenos.infrastructure.sql_repo.get_pool", AsyncMock(return_value=pool_mock)):
            validator = SqlPartnerKeyValidator(ttl=300)
            await validator._refresh_cache()

        sql = conn.fetch.call_args[0][0]
        assert "active" in sql
        assert "partners" in sql


# ─────────────────────────────────────────────────────────────────────────────
# Cross-tenant / Transaction tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossTenantAndTransaction:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def test_entity_upsert_cross_partner_blocked(self):
        """Entity upsert SQL contains WHERE partner_id = EXCLUDED.partner_id guard."""
        from zenos.infrastructure.sql_repo import SqlEntityRepository
        from zenos.domain.models import Entity, Tags
        import asyncio

        pool, conn = _make_pool()
        repo = SqlEntityRepository(pool)
        entity = Entity(
            id="shared_id", name="Entity", type="module", summary="s",
            tags=Tags(what=[], why="", how="", who=[]),
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(entity))

        execute_sql = conn.execute.call_args[0][0]
        assert "partner_id = EXCLUDED.partner_id" in execute_sql

    def test_document_upsert_uses_transaction(self):
        """Document upsert acquires a transaction wrapping main table + join sync."""
        from zenos.infrastructure.sql_repo import SqlDocumentRepository
        from zenos.domain.models import Document, DocumentTags, Source
        import asyncio

        pool, conn = _make_pool()
        conn.transaction = MagicMock(return_value=_FakeTransaction())
        repo = SqlDocumentRepository(pool)

        doc = Document(
            title="T", source=Source(type="github", uri="u", adapter="a"),
            tags=DocumentTags(what=[], why="", how="", who=[]),
            summary="s", linked_entity_ids=["e1"],
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(doc))

        conn.transaction.assert_called_once()

    def test_task_upsert_uses_transaction(self):
        """Task upsert acquires a transaction wrapping main table + join syncs."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        from zenos.domain.models import Task
        import asyncio

        pool, conn = _make_pool()
        conn.transaction = MagicMock(return_value=_FakeTransaction())
        repo = SqlTaskRepository(pool)

        task = Task(
            title="T", status="todo", priority="medium", created_by="Alice",
            linked_entities=["e1"], blocked_by=["task2"],
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(task))

        conn.transaction.assert_called_once()

    def test_blindspot_add_uses_transaction(self):
        """Blindspot add acquires a transaction wrapping main table + join sync."""
        from zenos.infrastructure.sql_repo import SqlBlindspotRepository
        from zenos.domain.models import Blindspot
        import asyncio

        pool, conn = _make_pool()
        conn.transaction = MagicMock(return_value=_FakeTransaction())
        repo = SqlBlindspotRepository(pool)

        bs = Blindspot(
            description="d", severity="red", related_entity_ids=["e1"],
            suggested_action="Fix it",
        )
        asyncio.get_event_loop().run_until_complete(repo.add(bs))

        conn.transaction.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# SqlEntityEntryRepository
# ─────────────────────────────────────────────────────────────────────────────

class TestSqlEntityEntryRepository:

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _entry_row(self, eid: str = "entry1") -> dict:
        return {
            "id": eid,
            "partner_id": PARTNER_ID,
            "entity_id": "ent1",
            "type": "decision",
            "content": "We decided to use PostgreSQL",
            "context": "After evaluating DynamoDB",
            "author": "Alice",
            "source_task_id": None,
            "status": "active",
            "superseded_by": None,
            "archive_reason": None,
            "created_at": NOW,
        }

    def test_create_inserts_and_returns_entry(self, monkeypatch):
        """create() inserts row and returns the entry with partner_id scoping."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        from zenos.domain.models import EntityEntry
        import asyncio

        pool, conn = _make_pool()
        repo = SqlEntityEntryRepository(pool)
        entry = EntityEntry(
            id="entry1",
            partner_id=PARTNER_ID,
            entity_id="ent1",
            type="decision",
            content="We decided to use PostgreSQL",
            created_at=NOW,
        )
        result = asyncio.get_event_loop().run_until_complete(repo.create(entry))

        assert result.id == "entry1"
        assert result.content == "We decided to use PostgreSQL"
        # Verify SQL was called with partner_id as $2
        sql = conn.execute.call_args[0][0]
        assert "entity_entries" in sql
        assert conn.execute.call_args[0][2] == PARTNER_ID

    def test_get_by_id_returns_entry_when_found(self, monkeypatch):
        """get_by_id maps row to EntityEntry domain model with partner_id scoping."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        row = _make_row(**self._entry_row("entry1"))
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlEntityEntryRepository(pool)

        entry = asyncio.get_event_loop().run_until_complete(repo.get_by_id("entry1"))

        assert entry is not None
        assert entry.id == "entry1"
        assert entry.type == "decision"
        assert entry.content == "We decided to use PostgreSQL"
        assert entry.status == "active"
        assert entry.context == "After evaluating DynamoDB"
        sql = conn.fetchrow.call_args[0][0]
        assert "partner_id" in sql
        assert conn.fetchrow.call_args[0][2] == PARTNER_ID

    def test_get_by_id_returns_none_when_missing(self):
        """get_by_id returns None when row not found."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        pool, _ = _make_pool(fetchrow=None)
        repo = SqlEntityEntryRepository(pool)
        entry = asyncio.get_event_loop().run_until_complete(repo.get_by_id("missing"))
        assert entry is None

    def test_list_by_entity_filters_by_active_status_by_default(self, monkeypatch):
        """list_by_entity default status='active' adds status filter to SQL."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        row = _make_row(**self._entry_row("entry1"))
        pool, conn = _make_pool(fetch=[row])
        repo = SqlEntityEntryRepository(pool)

        entries = asyncio.get_event_loop().run_until_complete(repo.list_by_entity("ent1"))

        assert len(entries) == 1
        assert entries[0].entity_id == "ent1"
        sql = conn.fetch.call_args[0][0]
        assert "status" in sql
        assert conn.fetch.call_args[0][3] == "active"

    def test_list_by_entity_with_status_none_omits_status_filter(self, monkeypatch):
        """list_by_entity(status=None) fetches all statuses for an entity."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlEntityEntryRepository(pool)

        asyncio.get_event_loop().run_until_complete(repo.list_by_entity("ent1", status=None))

        sql = conn.fetch.call_args[0][0]
        # status parameter $3 should NOT appear when status=None
        assert "$3" not in sql

    def test_update_status_returns_updated_entry(self, monkeypatch):
        """update_status issues UPDATE...RETURNING and maps result to EntityEntry."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        updated_row_data = self._entry_row("entry1")
        updated_row_data["status"] = "superseded"
        updated_row_data["superseded_by"] = "entry2"
        row = _make_row(**updated_row_data)
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlEntityEntryRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(
            repo.update_status("entry1", "superseded", "entry2")
        )

        assert result is not None
        assert result.status == "superseded"
        assert result.superseded_by == "entry2"
        sql = conn.fetchrow.call_args[0][0]
        assert "UPDATE" in sql
        assert "RETURNING" in sql
        assert "partner_id" in sql

    def test_update_status_returns_none_when_not_found(self):
        """update_status returns None when entry not found."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        pool, _ = _make_pool(fetchrow=None)
        repo = SqlEntityEntryRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.update_status("missing", "archived")
        )
        assert result is None

    def test_search_content_returns_entries_with_entity_name(self, monkeypatch):
        """search_content JOINs entities table and returns entity_name context."""
        from zenos.infrastructure.sql_repo import SqlEntityEntryRepository
        import asyncio

        row_data = self._entry_row("entry1")
        row_data["entity_name"] = "ZenOS Core"
        row = _make_row(**row_data)
        pool, conn = _make_pool(fetch=[row])
        repo = SqlEntityEntryRepository(pool)

        results = asyncio.get_event_loop().run_until_complete(
            repo.search_content("PostgreSQL")
        )

        assert len(results) == 1
        assert results[0]["entity_name"] == "ZenOS Core"
        assert results[0]["entry"].content == "We decided to use PostgreSQL"
        sql = conn.fetch.call_args[0][0]
        assert "JOIN" in sql
        assert "LOWER" in sql
        assert "partner_id" in sql
