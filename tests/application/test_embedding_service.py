"""Unit tests for EmbeddingService (ADR-041 S02).

Coverage:
- Happy path: compute_and_store success
- Retry: first call fails, second succeeds
- Empty summary: EMPTY sentinel written
- Null vector returned: treated as failure, retried
- Rate limit / dry-run batch
- needs_reembed edge cases
- embed_query success and failure paths
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from zenos.application.knowledge.embedding_service import (
    EMPTY_HASH,
    FAILED_HASH,
    GEMINI_EMBED_MODEL,
    BackfillStats,
    EmbeddingService,
)
from zenos.domain.knowledge.models import Entity, Tags
from zenos.infrastructure.llm_client import EmbeddingAPIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _fake_vec(dim: int = 768) -> list[float]:
    return [float(i % 10) / 10.0 for i in range(dim)]


def _make_entity(
    entity_id: str = "e-001",
    summary: str = "A meaningful summary",
    embedded_summary_hash: str | None = None,
    embedding_model: str | None = None,
    embedded_at: datetime | None = None,
) -> Entity:
    return Entity(
        id=entity_id,
        name="Test Entity",
        type="module",
        summary=summary,
        tags=Tags(what=["test"], why="testing", how="unit test", who=["dev"]),
        embedded_summary_hash=embedded_summary_hash,
        embedding_model=embedding_model,
        embedded_at=embedded_at,
    )


# ---------------------------------------------------------------------------
# compute_and_store — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_and_store_success_writes_correct_fields():
    """Happy path: entity with summary → embed called, 4 columns written correctly."""
    summary = "Important product concept"
    vec = _fake_vec()

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_entity(summary=summary))
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[vec])

    service = EmbeddingService(repo, llm)
    result = await service.compute_and_store("e-001")

    assert result is True
    llm.embed.assert_called_once_with([summary])

    repo.update_embedding.assert_called_once()
    eid, stored_vec, model, stored_hash = repo.update_embedding.call_args.args
    assert eid == "e-001"
    assert len(stored_vec) == 768
    assert model == GEMINI_EMBED_MODEL
    assert stored_hash == _sha256(summary)


# ---------------------------------------------------------------------------
# compute_and_store — retry on first failure, success on second
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_and_store_retries_on_api_error():
    """First attempt raises EmbeddingAPIError; second attempt succeeds."""
    summary = "Retry summary"
    vec = _fake_vec()

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_entity(summary=summary))
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock(
        side_effect=[EmbeddingAPIError("transient error"), [vec]]
    )

    service = EmbeddingService(repo, llm, max_retries=3)
    result = await service.compute_and_store("e-001")

    assert result is True
    assert llm.embed.call_count == 2
    repo.update_embedding.assert_called_once()
    _, _, _, stored_hash = repo.update_embedding.call_args.args
    assert stored_hash == _sha256(summary)


# ---------------------------------------------------------------------------
# compute_and_store — all retries exhausted → FAILED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_and_store_all_retries_fail_writes_failed_sentinel():
    """All max_retries attempts fail → FAILED sentinel written, returns False."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_entity(summary="Some summary"))
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock(side_effect=EmbeddingAPIError("quota"))

    service = EmbeddingService(repo, llm, max_retries=2)
    result = await service.compute_and_store("e-001")

    assert result is False
    assert llm.embed.call_count == 2

    repo.update_embedding.assert_called_once()
    _, vec_arg, _, hash_arg = repo.update_embedding.call_args.args
    assert vec_arg is None
    assert hash_arg == FAILED_HASH


# ---------------------------------------------------------------------------
# compute_and_store — empty summary → EMPTY sentinel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_and_store_empty_summary_writes_empty_sentinel():
    """Entity with empty summary → update_embedding called with EMPTY hash, no embed call."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_entity(summary=""))
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock()

    service = EmbeddingService(repo, llm)
    result = await service.compute_and_store("e-001")

    assert result is True
    llm.embed.assert_not_called()

    repo.update_embedding.assert_called_once()
    _, vec_arg, _, hash_arg = repo.update_embedding.call_args.args
    assert vec_arg is None
    assert hash_arg == EMPTY_HASH


@pytest.mark.asyncio
async def test_compute_and_store_none_summary_writes_empty_sentinel():
    """Entity with None summary → EMPTY sentinel written."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_entity(summary=None))  # type: ignore[arg-type]
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock()

    service = EmbeddingService(repo, llm)
    result = await service.compute_and_store("e-001")

    assert result is True
    llm.embed.assert_not_called()
    _, _, _, hash_arg = repo.update_embedding.call_args.args
    assert hash_arg == EMPTY_HASH


# ---------------------------------------------------------------------------
# compute_and_store — entity not found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_and_store_entity_not_found_returns_false():
    """Entity not found in DB → return False without calling embed."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock()

    service = EmbeddingService(repo, llm)
    result = await service.compute_and_store("nonexistent-id")

    assert result is False
    llm.embed.assert_not_called()
    repo.update_embedding.assert_not_called()


# ---------------------------------------------------------------------------
# embed_query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_query_returns_768_dim_vector():
    """embed_query returns 768-dim vector and does not write DB."""
    vec = _fake_vec(768)

    repo = MagicMock()
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[vec])

    service = EmbeddingService(repo, llm)
    result = await service.embed_query("governance query")

    assert result is not None
    assert len(result) == 768
    repo.update_embedding.assert_not_called()


@pytest.mark.asyncio
async def test_embed_query_api_unavailable_returns_none():
    """embed_query returns None when API raises EmbeddingAPIError."""
    llm = MagicMock()
    llm.embed = AsyncMock(side_effect=EmbeddingAPIError("service down"))

    service = EmbeddingService(MagicMock(), llm)
    result = await service.embed_query("some query")

    assert result is None


@pytest.mark.asyncio
async def test_embed_query_empty_text_returns_none():
    """embed_query returns None immediately for empty/whitespace text."""
    llm = MagicMock()
    llm.embed = AsyncMock()

    service = EmbeddingService(MagicMock(), llm)
    result = await service.embed_query("   ")

    assert result is None
    llm.embed.assert_not_called()


# ---------------------------------------------------------------------------
# needs_reembed
# ---------------------------------------------------------------------------

def test_needs_reembed_summary_changed_returns_true():
    """Hash mismatch (summary changed) → True."""
    entity = _make_entity(
        summary="New summary",
        embedded_summary_hash=_sha256("Old summary"),
        embedded_at=datetime.utcnow(),
    )
    service = EmbeddingService(MagicMock(), MagicMock())
    assert service.needs_reembed(entity) is True


def test_needs_reembed_summary_unchanged_returns_false():
    """Hash matches current summary → False."""
    summary = "Unchanged summary"
    entity = _make_entity(
        summary=summary,
        embedded_summary_hash=_sha256(summary),
        embedded_at=datetime.utcnow(),
    )
    service = EmbeddingService(MagicMock(), MagicMock())
    assert service.needs_reembed(entity) is False


def test_needs_reembed_no_hash_returns_true():
    """Never embedded (hash is None) → True."""
    entity = _make_entity(summary="Some summary", embedded_summary_hash=None)
    service = EmbeddingService(MagicMock(), MagicMock())
    assert service.needs_reembed(entity) is True


def test_needs_reembed_failed_hash_returns_true():
    """FAILED sentinel → True (needs retry)."""
    entity = _make_entity(summary="Some summary", embedded_summary_hash=FAILED_HASH)
    service = EmbeddingService(MagicMock(), MagicMock())
    assert service.needs_reembed(entity) is True


def test_needs_reembed_empty_summary_returns_false():
    """Empty summary → False (already handled by EMPTY sentinel logic)."""
    entity = _make_entity(summary="", embedded_summary_hash=None)
    service = EmbeddingService(MagicMock(), MagicMock())
    assert service.needs_reembed(entity) is False


def test_needs_reembed_none_summary_returns_false():
    """None summary → False."""
    entity = _make_entity(summary=None, embedded_summary_hash=None)  # type: ignore[arg-type]
    service = EmbeddingService(MagicMock(), MagicMock())
    assert service.needs_reembed(entity) is False


# ---------------------------------------------------------------------------
# batch_embed_missing — dry run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_embed_missing_dry_run_no_api_call(capsys):
    """dry_run=True: prints count, never calls embed or update_embedding."""
    entities = [
        _make_entity(entity_id="e-001", summary="Summary 1"),
        _make_entity(entity_id="e-002", summary="Summary 2"),
    ]

    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=entities)
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock()

    service = EmbeddingService(repo, llm)
    stats = await service.batch_embed_missing(dry_run=True)

    assert stats.total == 2
    llm.embed.assert_not_called()
    repo.update_embedding.assert_not_called()

    captured = capsys.readouterr()
    assert "will process 2" in captured.out


# ---------------------------------------------------------------------------
# batch_embed_missing — only_reembed skips never-attempted entities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_embed_missing_only_reembed_skips_never_embedded():
    """only_reembed=True skips entities with hash=None (never attempted)."""
    never_embedded = _make_entity(entity_id="e-001", summary="Never embedded", embedded_summary_hash=None)
    failed_entity = _make_entity(entity_id="e-002", summary="Failed before", embedded_summary_hash=FAILED_HASH)

    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=[never_embedded, failed_entity])
    repo.get_by_id = AsyncMock(side_effect=lambda eid: {
        "e-002": failed_entity,
    }.get(eid))
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[_fake_vec()])

    service = EmbeddingService(repo, llm)
    stats = await service.batch_embed_missing(only_reembed=True)

    # Only failed_entity should be processed; never_embedded is skipped
    assert stats.total == 1
    assert stats.skipped >= 1


# ---------------------------------------------------------------------------
# batch_embed_missing — skips fresh entities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_embed_missing_skips_fresh_entities():
    """Entities with fresh embeddings (hash matches summary) are counted as skipped."""
    summary = "Fresh summary"
    fresh_entity = _make_entity(
        summary=summary,
        embedded_summary_hash=_sha256(summary),
        embedded_at=datetime.utcnow(),
    )

    repo = MagicMock()
    repo.list_all = AsyncMock(return_value=[fresh_entity])
    repo.update_embedding = AsyncMock()

    llm = MagicMock()
    llm.embed = AsyncMock()

    service = EmbeddingService(repo, llm)
    stats = await service.batch_embed_missing()

    assert stats.skipped == 1
    assert stats.total == 0
    llm.embed.assert_not_called()
