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
    pool.release = AsyncMock()
    return pool, conn


from tests.conftest import AsyncContextManager as _AsyncContextManager


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
            "visible_to_roles": ["engineering"],
            "visible_to_members": ["p-admin"],
            "visible_to_departments": ["engineering"],
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
        assert entity.visible_to_roles == ["engineering"]
        assert entity.visible_to_members == ["p-admin"]
        assert entity.visible_to_departments == ["engineering"]
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

    def test_list_all_confirmed_only_none_fetches_all(self):
        """list_all(confirmed_only=None) queries without confirmed_by_user filter."""
        from zenos.infrastructure.sql_repo import SqlProtocolRepository
        import asyncio

        row = _make_row(**self._proto_row("proto1"))
        pool, conn = _make_pool(fetch=[row])
        repo = SqlProtocolRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(repo.list_all(confirmed_only=None))

        assert len(result) == 1
        assert result[0].id == "proto1"
        sql = conn.fetch.call_args[0][0]
        assert "partner_id" in sql
        assert "confirmed_by_user" not in sql
        assert conn.fetch.call_args[0][1] == PARTNER_ID

    def test_list_all_confirmed_only_true_filters_confirmed(self):
        """list_all(confirmed_only=True) adds confirmed_by_user = true filter."""
        from zenos.infrastructure.sql_repo import SqlProtocolRepository
        import asyncio

        confirmed_row = {**self._proto_row("proto-confirmed"), "confirmed_by_user": True}
        pool, conn = _make_pool(fetch=[_make_row(**confirmed_row)])
        repo = SqlProtocolRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(repo.list_all(confirmed_only=True))

        assert len(result) == 1
        sql = conn.fetch.call_args[0][0]
        assert "confirmed_by_user" in sql
        args = conn.fetch.call_args[0]
        assert PARTNER_ID in args
        assert True in args

    def test_list_all_confirmed_only_false_filters_unconfirmed(self):
        """list_all(confirmed_only=False) adds confirmed_by_user = false filter."""
        from zenos.infrastructure.sql_repo import SqlProtocolRepository
        import asyncio

        pool, conn = _make_pool(fetch=[_make_row(**self._proto_row("proto-unconfirmed"))])
        repo = SqlProtocolRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(repo.list_all(confirmed_only=False))

        assert len(result) == 1
        sql = conn.fetch.call_args[0][0]
        assert "confirmed_by_user" in sql
        args = conn.fetch.call_args[0]
        assert PARTNER_ID in args
        assert False in args


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

    def test_list_all_with_offset_uses_sql_offset(self):
        """list_all(offset=10) includes OFFSET in the SQL query."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.list_all(offset=10))

        main_sql = conn.fetch.call_args_list[0][0][0]
        assert "OFFSET" in main_sql.upper()

    def test_list_all_with_explicit_status_uses_offset(self):
        """list_all with explicit status filter uses OFFSET in SQL."""
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        import asyncio

        pool, conn = _make_pool(fetch=[])
        repo = SqlTaskRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.list_all(status=["todo"], offset=5)
        )

        main_sql = conn.fetch.call_args_list[0][0][0]
        assert "OFFSET" in main_sql.upper()

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

    def test_upsert_insert_params_have_no_none_in_not_null_columns(self):
        """INSERT params must not pass None for NOT NULL columns.

        This is a dry-run test that verifies the SQL parameter list passed to
        asyncpg.execute() does not contain None for columns constrained NOT NULL
        in the tasks table schema. Previously, description and project could be
        None (from dashboard API passing body.get() results), causing a NOT NULL
        constraint violation on INSERT.
        """
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        from zenos.domain.models import Task, TaskStatus, TaskPriority
        import asyncio

        pool, conn = _make_pool()
        repo = SqlTaskRepository(pool)

        # Create a minimal task with only required fields (simulating
        # the dashboard POST /api/data/tasks with {"title": "test task"})
        task = Task(
            title="test task",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            created_by=PARTNER_ID,
            updated_by=PARTNER_ID,
            description="",   # must never be None
            project="",        # must never be None
            source_type="",    # must never be None
            priority_reason="",
        )

        asyncio.get_event_loop().run_until_complete(repo.upsert(task))

        # The first execute call is the INSERT statement.
        # asyncpg receives args as individual positional params:
        # call.args[0] = SQL string, call.args[1..32] = the 32 parameter values.
        all_args = conn.execute.call_args_list[0].args
        insert_sql = all_args[0]
        # params are 1-indexed in SQL ($1..$32), 1-indexed in all_args[1..32]
        assert "INSERT INTO" in insert_sql

        # NOT NULL columns and their $N positions (1-indexed in SQL)
        not_null_positions = {
            "id": 1,
            "partner_id": 2,
            "title": 3,
            "description": 4,
            "status": 5,
            "priority": 6,
            "priority_reason": 7,
            "created_by": 10,
            "source_type": 17,
            "context_summary": 19,
            "project": 27,
        }
        for col_name, sql_pos in not_null_positions.items():
            arg_val = all_args[sql_pos]  # all_args[1] = $1, all_args[2] = $2 ...
            assert arg_val is not None, (
                f"Column '{col_name}' (${sql_pos}) is None — "
                f"would violate NOT NULL constraint in PostgreSQL"
            )

    def test_upsert_passes_through_none_description_to_asyncpg(self):
        """sql_repo passes None description straight to asyncpg (no guard at repo layer).

        Documents the architecture contract: sql_repo does NOT coerce None values —
        the caller (task_service.create_task) is responsible for ensuring NOT NULL
        columns are never None before calling upsert.
        """
        from zenos.infrastructure.sql_repo import SqlTaskRepository
        from zenos.domain.models import Task, TaskStatus, TaskPriority
        import asyncio

        pool, conn = _make_pool()
        repo = SqlTaskRepository(pool)

        # Simulate the broken state (pre-fix): description=None
        task = Task(
            title="test task",
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            created_by=PARTNER_ID,
            description=None,  # type: ignore[arg-type]  — intentionally wrong
        )
        asyncio.get_event_loop().run_until_complete(repo.upsert(task))

        all_args = conn.execute.call_args_list[0].args
        # The description is at $4 (all_args[4] in the positional args list).
        # This test documents that passing None would reach asyncpg —
        # the guard must be upstream in task_service.create_task.
        description_arg = all_args[4]
        # We assert this: if it's None, asyncpg would raise with PostgreSQL.
        # The task_service fix must ensure this is NEVER None.
        assert description_arg is None, (
            "If this assertion fails, sql_repo itself now guards against None — "
            "which is also acceptable."
        )

    def test_task_service_create_task_never_passes_none_description(self):
        """create_task() with no description in data produces task.description=''.

        This is the end-to-end fix verification: TaskService.create_task must
        coerce None to '' for description and project (NOT NULL columns).
        """
        from zenos.application.task_service import TaskService
        from zenos.domain.models import Task
        from unittest.mock import AsyncMock
        import asyncio

        captured: list[Task] = []

        async def fake_upsert(task: Task) -> Task:
            captured.append(task)
            return task

        task_repo_mock = AsyncMock()
        task_repo_mock.upsert = AsyncMock(side_effect=fake_upsert)

        entity_repo_mock = AsyncMock()
        entity_repo_mock.list_all = AsyncMock(return_value=[])
        entity_repo_mock.get_by_id = AsyncMock(return_value=None)

        blindspot_repo_mock = AsyncMock()
        blindspot_repo_mock.get_by_id = AsyncMock(return_value=None)

        svc = TaskService(
            task_repo=task_repo_mock,
            entity_repo=entity_repo_mock,
            blindspot_repo=blindspot_repo_mock,
        )

        # Simulate dashboard API: description key is present but value is None
        data = {
            "title": "test task",
            "description": None,   # body.get("description") when not in JSON
            "project": None,        # body.get("project") when not in JSON
            "created_by": PARTNER_ID,
        }
        asyncio.get_event_loop().run_until_complete(svc.create_task(data))

        assert len(captured) == 1
        task = captured[0]
        assert task.description == "", (
            f"description should be '' but got {task.description!r} — "
            "None would cause NOT NULL violation in PostgreSQL"
        )
        assert task.project == "", (
            f"project should be '' but got {task.project!r} — "
            "None would cause NOT NULL violation in PostgreSQL"
        )


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
            status="active", is_admin=False, shared_partner_id=None, access_mode="internal",
            default_project="zenos",
        )

        async def mock_refresh(self_inner):
            self_inner._cache = {
                "secret_key": {
                    "id": "p1", "email": "a@b.com", "displayName": "Alice",
                    "apiKey": "secret_key", "authorizedEntityIds": [],  # pragma: allowlist secret
                    "status": "active", "isAdmin": False, "accessMode": "internal",
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


# ─────────────────────────────────────────────────────────────────────────────
# SqlUsageLogRepository
# ─────────────────────────────────────────────────────────────────────────────


class TestSqlUsageLogRepository:
    """Unit tests for SqlUsageLogRepository.write_usage_log."""

    def test_writes_usage_log_row(self):
        """write_usage_log executes INSERT with correct column mapping."""
        from zenos.infrastructure.sql_repo import SqlUsageLogRepository
        import asyncio

        pool, conn = _make_pool(execute="INSERT 0 1")
        repo = SqlUsageLogRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.write_usage_log(
                partner_id="p1",
                feature="governance.infer_all",
                tokens_in=500,
                tokens_out=120,
                model="gpt-4o",
            )
        )

        conn.execute.assert_called_once()
        sql, *args = conn.execute.call_args[0]
        assert "INSERT" in sql
        assert "usage_logs" in sql
        assert args[0] == "p1"        # partner_id
        assert args[1] == "governance.infer_all"  # feature
        assert args[2] == "gpt-4o"   # model
        assert args[3] == 500         # tokens_in
        assert args[4] == 120         # tokens_out

    def test_skips_insert_for_empty_partner_id(self):
        """write_usage_log silently returns without querying when partner_id is empty."""
        from zenos.infrastructure.sql_repo import SqlUsageLogRepository
        import asyncio

        pool, conn = _make_pool()
        repo = SqlUsageLogRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.write_usage_log(
                partner_id="",
                feature="governance.infer_all",
                tokens_in=100,
                tokens_out=20,
                model="gpt-4o",
            )
        )

        conn.execute.assert_not_called()

    def test_skips_insert_for_none_partner_id(self):
        """write_usage_log treats None as empty and skips the INSERT."""
        from zenos.infrastructure.sql_repo import SqlUsageLogRepository
        import asyncio

        pool, conn = _make_pool()
        repo = SqlUsageLogRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.write_usage_log(
                partner_id=None,
                feature="governance.infer_all",
                tokens_in=100,
                tokens_out=20,
                model="gpt-4o",
            )
        )

        conn.execute.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# SqlPartnerRepository
# ─────────────────────────────────────────────────────────────────────────────


def _make_partner_row(**overrides) -> MagicMock:
    """Build a mock asyncpg.Record for a partners table row."""
    defaults = {
        "id": "p1",
        "email": "user@test.com",
        "display_name": "Test User",
        "api_key": "key-abc",  # pragma: allowlist secret
        "authorized_entity_ids": [],
        "status": "active",
        "is_admin": False,
        "shared_partner_id": None,
        "access_mode": "internal",
        "default_project": None,
        "roles": [],
        "department": "all",
        "invited_by": "",
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    return _make_row(**defaults)


class TestSqlPartnerRepository:
    """Unit tests for SqlPartnerRepository."""

    def test_get_by_email_returns_partner_dict(self):
        """get_by_email fetches by email and maps row to standardized dict."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        row = _make_partner_row(email="alice@test.com", id="p-alice")
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlPartnerRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(
            repo.get_by_email("alice@test.com")
        )

        assert result is not None
        assert result["email"] == "alice@test.com"
        assert result["id"] == "p-alice"
        sql = conn.fetchrow.call_args[0][0]
        assert "partners" in sql
        assert "email" in sql
        assert "btrim(lower(email))" in sql

    def test_get_by_email_normalizes_case_and_whitespace(self):
        """get_by_email uses normalized comparison instead of exact raw equality."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        row = _make_partner_row(email="alice@test.com", id="p-alice")
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlPartnerRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(
            repo.get_by_email(" Alice@Test.com ")
        )

        assert result is not None
        assert result["email"] == "alice@test.com"
        _, passed_email = conn.fetchrow.call_args[0]
        assert passed_email == " Alice@Test.com "

    def test_get_by_email_returns_none_when_missing(self):
        """get_by_email returns None when no partner matches."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, conn = _make_pool(fetchrow=None)
        repo = SqlPartnerRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(
            repo.get_by_email("nobody@test.com")
        )

        assert result is None

    def test_get_by_id_returns_partner_dict(self):
        """get_by_id fetches by ID and maps row to standardized dict."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        row = _make_partner_row(id="p2", email="bob@test.com", is_admin=True)
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlPartnerRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(repo.get_by_id("p2"))

        assert result is not None
        assert result["id"] == "p2"
        assert result["isAdmin"] is True
        assert result["accessMode"] == "internal"
        sql = conn.fetchrow.call_args[0][0]
        assert "partners" in sql

    def test_get_by_id_returns_none_when_missing(self):
        """get_by_id returns None when partner not found."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, _ = _make_pool(fetchrow=None)
        repo = SqlPartnerRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(repo.get_by_id("nope"))
        assert result is None

    def test_list_all_in_tenant_filters_by_tenant_key(self):
        """list_all_in_tenant returns only partners whose tenant key matches."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        # p1 is the admin (no shared_partner_id → tenant key == id == "p1")
        row_admin = _make_partner_row(id="p1", shared_partner_id=None, is_admin=True)
        # p2 shares tenant "p1"
        row_member = _make_partner_row(id="p2", shared_partner_id="p1")
        # p3 belongs to a different tenant
        row_other = _make_partner_row(id="p3", shared_partner_id="other-tenant")
        pool, conn = _make_pool(fetch=[row_admin, row_member, row_other])
        repo = SqlPartnerRepository(pool)

        results = asyncio.get_event_loop().run_until_complete(
            repo.list_all_in_tenant("p1")
        )

        ids = {r["id"] for r in results}
        assert ids == {"p1", "p2"}
        assert "p3" not in ids

    def test_create_inserts_partner_row(self):
        """create executes INSERT with all required fields."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, conn = _make_pool(execute="INSERT 0 1")
        repo = SqlPartnerRepository(pool)
        data = {
            "id": "p-new",
            "email": "new@test.com",
            "displayName": "New User",
            "apiKey": "key-new",  # pragma: allowlist secret
            "authorizedEntityIds": [],
            "status": "invited",
            "isAdmin": False,
            "sharedPartnerId": "p1",
            "accessMode": "unassigned",
            "invitedBy": "admin@test.com",
            "createdAt": NOW,
            "updatedAt": NOW,
        }
        asyncio.get_event_loop().run_until_complete(repo.create(data))

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT" in sql
        assert "partners" in sql

    def test_update_fields_builds_correct_set_clause(self):
        """update_fields generates SET clause only for provided keys."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, conn = _make_pool(execute="UPDATE 1")
        repo = SqlPartnerRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.update_fields("p1", {"status": "suspended", "updatedAt": NOW})
        )

        conn.execute.assert_called_once()
        sql, *params = conn.execute.call_args[0]
        assert "UPDATE" in sql
        assert "partners" in sql
        assert "status" in sql
        assert "suspended" in params

    def test_update_fields_skips_empty_dict(self):
        """update_fields is a no-op when fields dict is empty."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, conn = _make_pool()
        repo = SqlPartnerRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.update_fields("p1", {}))
        conn.execute.assert_not_called()

    def test_delete_executes_delete_sql(self):
        """delete removes partner by ID via a 6-step transaction:
        1. NULL out task assignees
        2. Delete task_comments
        3. Delete tool_events
        4. Delete crm.activities recorded_by this partner
        5. Delete crm.deals owned by this partner (cascades remaining activities)
        6. Delete the partner row
        All steps execute inside a single transaction via conn.execute.
        """
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, conn = _make_pool(execute="DELETE 1")
        repo = SqlPartnerRepository(pool)
        asyncio.get_event_loop().run_until_complete(repo.delete("p1"))

        assert conn.execute.call_count == 6, (
            f"Expected 6 execute calls (NULL assignees, delete task_comments, "
            f"delete tool_events, delete crm.activities, delete crm.deals, delete partner), "
            f"got {conn.execute.call_count}"
        )
        # The final call must delete from partners table
        final_sql = conn.execute.call_args_list[-1][0][0]
        assert "DELETE" in final_sql
        assert "partners" in final_sql
        # CRM cleanup steps must be present
        all_sqls = [call[0][0] for call in conn.execute.call_args_list]
        assert any("crm.activities" in sql for sql in all_sqls), "Missing crm.activities cleanup"
        assert any("crm.deals" in sql for sql in all_sqls), "Missing crm.deals cleanup"

    def test_get_entity_tenant_returns_partner_info(self):
        """get_entity_tenant JOINs entities+partners and returns tenant data."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        row = _make_row(partner_id="p1", shared_partner_id=None)
        pool, conn = _make_pool(fetchrow=row)
        repo = SqlPartnerRepository(pool)

        result = asyncio.get_event_loop().run_until_complete(
            repo.get_entity_tenant("entity-1")
        )

        assert result == {"partner_id": "p1", "shared_partner_id": None}
        sql = conn.fetchrow.call_args[0][0]
        assert "entities" in sql
        assert "partners" in sql
        assert "JOIN" in sql

    def test_get_entity_tenant_returns_none_when_not_found(self):
        """get_entity_tenant returns None when entity does not exist."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, _ = _make_pool(fetchrow=None)
        repo = SqlPartnerRepository(pool)
        result = asyncio.get_event_loop().run_until_complete(
            repo.get_entity_tenant("missing")
        )
        assert result is None

    def test_update_entity_visibility_executes_update(self):
        """update_entity_visibility issues UPDATE on entities table."""
        from zenos.infrastructure.sql_repo import SqlPartnerRepository
        import asyncio

        pool, conn = _make_pool(execute="UPDATE 1")
        repo = SqlPartnerRepository(pool)
        asyncio.get_event_loop().run_until_complete(
            repo.update_entity_visibility(
                entity_id="e1",
                visibility="restricted",
                visible_to_roles=["admin"],
                visible_to_members=["alice@test.com"],
                visible_to_departments=["eng"],
            )
        )

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "UPDATE" in sql
        assert "entities" in sql
        assert "visibility" in sql


# ─────────────────────────────────────────────────────────────────────────────
# Governance Health Cache helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestGovernanceHealthCache:

    def test_get_cached_health_returns_none_when_no_row(self):
        """get_cached_health returns None when cache miss."""
        from zenos.infrastructure.sql_repo import get_cached_health

        pool, _conn = _make_pool(fetchrow=None)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            get_cached_health(pool, "partner_abc")
        )
        assert result is None

    def test_get_cached_health_returns_dict_when_row_exists(self):
        """get_cached_health returns {overall_level, computed_at} on hit."""
        from zenos.infrastructure.sql_repo import get_cached_health

        row = _make_row(overall_level="yellow", computed_at=NOW)
        pool, conn = _make_pool(fetchrow=row)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            get_cached_health(pool, "partner_abc")
        )
        assert result == {"overall_level": "yellow", "computed_at": NOW}
        conn.fetchrow.assert_called_once()
        sql = conn.fetchrow.call_args[0][0]
        assert "governance_health_cache" in sql
        assert "partner_abc" == conn.fetchrow.call_args[0][1]

    def test_upsert_health_cache_executes_upsert_sql(self):
        """upsert_health_cache runs INSERT ... ON CONFLICT DO UPDATE."""
        from zenos.infrastructure.sql_repo import upsert_health_cache

        pool, conn = _make_pool()
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            upsert_health_cache(pool, "partner_abc", "red")
        )
        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "governance_health_cache" in sql
        assert "ON CONFLICT" in sql
        assert conn.execute.call_args[0][1] == "partner_abc"
        assert conn.execute.call_args[0][2] == "red"

    def test_upsert_health_cache_overwrites_existing(self):
        """Calling upsert twice uses same SQL (ON CONFLICT handles update)."""
        from zenos.infrastructure.sql_repo import upsert_health_cache

        pool, conn = _make_pool()
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            upsert_health_cache(pool, "partner_abc", "green")
        )
        asyncio.get_event_loop().run_until_complete(
            upsert_health_cache(pool, "partner_abc", "yellow")
        )
        assert conn.execute.call_count == 2
        # Second call should have "yellow"
        assert conn.execute.call_args_list[1][0][2] == "yellow"
