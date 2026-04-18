"""Unit tests for SqlEntityRepository embedding methods (ADR-041 Phase 1 / S01).

Tests cover:
- update_embedding: happy path, FAILED sentinel, EMPTY sentinel
- get_embeddings_by_ids: multiple IDs including null embedding
- search_by_vector: basic top-K, visibility filter

All tests use mock asyncpg pool/connection objects (no real DB required).
These are mock-based unit tests (⚠️ mock tests): they verify SQL construction
and branch logic. Integration tests that require pgvector are tracked via
@pytest.mark.integration in tests/spec_compliance/test_semantic_retrieval_ac.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from tests.conftest import AsyncContextManager as _AsyncContextManager

PARTNER_ID = "partner_test"
NOW = datetime(2026, 4, 18, 0, 0, 0, tzinfo=timezone.utc)

EMBEDDING_768 = [0.1] * 768
ENTITY_ID = "entity-abc-123"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _set_partner(monkeypatch):
    monkeypatch.setattr(
        "zenos.infrastructure.sql_common.current_partner_id",
        MagicMock(get=MagicMock(return_value=PARTNER_ID)),
    )


def _make_entity_row(eid: str = ENTITY_ID, **overrides) -> MagicMock:
    base: dict[str, Any] = {
        "id": eid,
        "name": "Test Entity",
        "type": "module",
        "level": 2,
        "parent_id": None,
        "status": "active",
        "summary": "A test entity summary",
        "tags_json": json.dumps({"what": ["x"], "why": "because", "how": "do it", "who": ["Alice"]}),
        "details_json": None,
        "confirmed_by_user": False,
        "owner": "Alice",
        "sources_json": json.dumps([{"uri": "https://example.com", "label": "link", "type": "github"}]),
        "visibility": "public",
        "visible_to_roles": ["engineering"],
        "visible_to_members": [],
        "visible_to_departments": [],
        "last_reviewed_at": None,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_role": None,
        "bundle_highlights_json": None,
        "highlights_updated_at": None,
        "change_summary": None,
        "summary_updated_at": None,
        "cosine_score": 0.9,
    }
    base.update(overrides)
    row = MagicMock()
    row.__getitem__ = lambda self, key: base[key]
    row.__contains__ = lambda self, key: key in base
    return row


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


def _make_pool(fetchrow=None, fetch=None, execute=None):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock(return_value=execute)
    conn.transaction = MagicMock(return_value=_FakeTransaction())

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncContextManager(conn))
    pool.release = AsyncMock()
    return pool, conn


# ─────────────────────────────────────────────────────────────────────────────
# update_embedding tests
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateEmbedding:
    """Tests for SqlEntityRepository.update_embedding."""

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    @pytest.mark.asyncio
    async def test_happy_path_writes_all_four_columns(self):
        """update_embedding with valid vector writes embedding, model, embedded_at, and hash."""
        pool, conn = _make_pool()

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        sha = "abc123def456"  # pragma: allowlist secret
        await repo.update_embedding(
            entity_id=ENTITY_ID,
            embedding=EMBEDDING_768,
            model="gemini/gemini-embedding-001",
            hash=sha,
        )

        conn.execute.assert_awaited_once()
        sql_call = conn.execute.call_args
        sql: str = sql_call.args[0]

        assert "summary_embedding" in sql
        assert "embedding_model" in sql
        assert "embedded_at" in sql
        assert "embedded_summary_hash" in sql
        # The passed embedding and hash must appear in the params. pgvector wants
        # the vector as a stringified literal "[v1,v2,...]" when no codec is
        # registered on the pool.
        params = sql_call.args[1:]
        expected_lit = "[" + ",".join(repr(float(v)) for v in EMBEDDING_768) + "]"
        assert expected_lit in params
        assert "gemini/gemini-embedding-001" in params
        assert sha in params
        assert ENTITY_ID in params
        assert PARTNER_ID in params
        # embedded_at must be a non-None datetime when embed succeeds
        embedded_at_param = params[2]  # positional order: embedding, model, embedded_at, hash, id, pid
        assert embedded_at_param is not None
        assert isinstance(embedded_at_param, datetime)

    @pytest.mark.asyncio
    async def test_failed_sentinel_sets_embedded_at_to_none(self):
        """update_embedding with hash='FAILED' sets embedded_at=None."""
        pool, conn = _make_pool()

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.update_embedding(
            entity_id=ENTITY_ID,
            embedding=None,
            model="FAILED",
            hash="FAILED",
        )

        conn.execute.assert_awaited_once()
        params = conn.execute.call_args.args[1:]
        # embedding should be None
        assert params[0] is None
        # embedded_at should be None for FAILED sentinel
        embedded_at_param = params[2]
        assert embedded_at_param is None

    @pytest.mark.asyncio
    async def test_empty_sentinel_sets_embedded_at_to_none(self):
        """update_embedding with hash='EMPTY' (summary was empty) sets embedded_at=None."""
        pool, conn = _make_pool()

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.update_embedding(
            entity_id=ENTITY_ID,
            embedding=None,
            model="EMPTY",
            hash="EMPTY",
        )

        conn.execute.assert_awaited_once()
        params = conn.execute.call_args.args[1:]
        assert params[0] is None
        embedded_at_param = params[2]
        assert embedded_at_param is None

    @pytest.mark.asyncio
    async def test_scopes_by_partner_id(self):
        """update_embedding SQL includes both entity_id and partner_id in WHERE clause."""
        pool, conn = _make_pool()

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.update_embedding(ENTITY_ID, EMBEDDING_768, "model-x", "hash-x")

        params = conn.execute.call_args.args[1:]
        assert ENTITY_ID in params
        assert PARTNER_ID in params


# ─────────────────────────────────────────────────────────────────────────────
# get_embeddings_by_ids tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetEmbeddingsByIds:
    """Tests for SqlEntityRepository.get_embeddings_by_ids."""

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    def _embedding_row(self, eid: str, embedding: list[float] | None) -> MagicMock:
        data = {"id": eid, "summary_embedding": embedding}
        row = MagicMock()
        row.__getitem__ = lambda self, key: data[key]
        return row

    @pytest.mark.asyncio
    async def test_returns_dict_keyed_by_id(self):
        """get_embeddings_by_ids returns {id: vector} for rows with embeddings."""
        vec_a = [0.1] * 768
        vec_b = [0.2] * 768
        pool, conn = _make_pool(
            fetch=[
                self._embedding_row("e1", vec_a),
                self._embedding_row("e2", vec_b),
            ]
        )

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        result = await repo.get_embeddings_by_ids(["e1", "e2"])

        assert result == {"e1": vec_a, "e2": vec_b}

    @pytest.mark.asyncio
    async def test_null_embedding_returned_as_none(self):
        """get_embeddings_by_ids maps null summary_embedding to None."""
        pool, conn = _make_pool(
            fetch=[
                self._embedding_row("e1", [0.1] * 768),
                self._embedding_row("e_null", None),
            ]
        )

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        result = await repo.get_embeddings_by_ids(["e1", "e_null"])

        assert result["e1"] == [0.1] * 768
        assert result["e_null"] is None

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty_dict_without_db_call(self):
        """get_embeddings_by_ids returns {} for empty ids list without hitting DB."""
        pool, conn = _make_pool()

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        result = await repo.get_embeddings_by_ids([])

        assert result == {}
        conn.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_scopes_by_partner_id(self):
        """get_embeddings_by_ids SQL uses partner_id scoping."""
        pool, conn = _make_pool(fetch=[])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.get_embeddings_by_ids(["e1"])

        conn.fetch.assert_awaited_once()
        params = conn.fetch.call_args.args[1:]
        assert PARTNER_ID in params


# ─────────────────────────────────────────────────────────────────────────────
# search_by_vector tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchByVector:
    """Tests for SqlEntityRepository.search_by_vector."""

    @pytest.fixture(autouse=True)
    def patch_partner(self, monkeypatch):
        _set_partner(monkeypatch)

    @pytest.mark.asyncio
    async def test_returns_entity_score_tuples(self):
        """search_by_vector returns list of (Entity, float) sorted by score desc."""
        row1 = _make_entity_row("e1", cosine_score=0.95)
        row2 = _make_entity_row("e2", cosine_score=0.80)
        pool, conn = _make_pool(fetch=[row1, row2])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        results = await repo.search_by_vector(EMBEDDING_768, limit=10)

        assert len(results) == 2
        entity1, score1 = results[0]
        assert entity1.id == "e1"
        assert abs(score1 - 0.95) < 1e-6

        entity2, score2 = results[1]
        assert entity2.id == "e2"
        assert abs(score2 - 0.80) < 1e-6

    @pytest.mark.asyncio
    async def test_sql_contains_hnsw_cosine_operator(self):
        """search_by_vector SQL uses pgvector <=> operator for cosine distance."""
        pool, conn = _make_pool(fetch=[])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.search_by_vector(EMBEDDING_768, limit=5)

        conn.fetch.assert_awaited_once()
        sql: str = conn.fetch.call_args.args[0]
        assert "<=>" in sql, "SQL must use pgvector cosine distance operator <=>"
        assert "summary_embedding IS NOT NULL" in sql

    @pytest.mark.asyncio
    async def test_visibility_filter_appended_to_where(self):
        """search_by_vector adds visibility = $N clause when filters={'visibility': ...} given."""
        pool, conn = _make_pool(fetch=[])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.search_by_vector(EMBEDDING_768, limit=5, filters={"visibility": "public"})

        conn.fetch.assert_awaited_once()
        sql: str = conn.fetch.call_args.args[0]
        assert "visibility" in sql

        params = conn.fetch.call_args.args[1:]
        assert "public" in params

    @pytest.mark.asyncio
    async def test_no_filters_excludes_visibility_clause(self):
        """search_by_vector without filters does not add visibility to SQL."""
        pool, conn = _make_pool(fetch=[])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.search_by_vector(EMBEDDING_768, limit=5)

        sql: str = conn.fetch.call_args.args[0]
        # visibility must not appear as a filter when no filters are passed
        # (partner_id IS required; we only check no extra visibility filter)
        assert "visibility = " not in sql

    @pytest.mark.asyncio
    async def test_scopes_by_partner_id(self):
        """search_by_vector SQL uses partner_id scoping."""
        pool, conn = _make_pool(fetch=[])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        await repo.search_by_vector(EMBEDDING_768, limit=5)

        params = conn.fetch.call_args.args[1:]
        assert PARTNER_ID in params

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self):
        """search_by_vector returns [] when no rows found."""
        pool, conn = _make_pool(fetch=[])

        from zenos.infrastructure.knowledge.sql_entity_repo import SqlEntityRepository
        repo = SqlEntityRepository(pool)

        result = await repo.search_by_vector(EMBEDDING_768, limit=10)
        assert result == []
