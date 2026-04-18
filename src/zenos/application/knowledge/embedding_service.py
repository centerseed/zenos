"""EmbeddingService — Application layer for entity embedding pipeline.

Responsibilities:
- compute_and_store: embed a single entity summary and write result to the repo
- embed_query: pure in-memory embed for query vectors (no DB write)
- needs_reembed: determine whether an entity's embedding is stale
- batch_embed_missing: backfill driver for scripts/backfill_embeddings.py

Design constraints (ADR-041 S02):
- EmbeddingService never calls litellm directly; all embedding goes through llm_client.embed()
- Retry up to max_retries; on exhaustion write FAILED sentinel
- summary=None/empty skips embed and writes EMPTY sentinel
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from zenos.infrastructure.llm_client import EmbeddingAPIError

if TYPE_CHECKING:
    from zenos.domain.knowledge.models import Entity

logger = logging.getLogger(__name__)

GEMINI_EMBED_MODEL = "gemini/gemini-embedding-001"
EMPTY_HASH = "EMPTY"
FAILED_HASH = "FAILED"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class BackfillStats:
    total: int = 0
    embedded: int = 0
    skipped: int = 0
    failed: int = 0
    duration_seconds: float = 0.0


class EmbeddingService:
    """Application service that owns the entity embedding lifecycle."""

    def __init__(
        self,
        entity_repo: Any,
        llm_client: Any,
        *,
        max_retries: int = 3,
    ) -> None:
        self._repo = entity_repo
        self._llm = llm_client
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute_and_store(self, entity_id: str) -> bool:
        """Embed entity.summary and persist the four embedding columns.

        Returns:
            True if embedding was stored (or entity has empty summary — EMPTY sentinel).
            False if all retries exhausted — FAILED sentinel written.
        """
        entity = await self._repo.get_by_id(entity_id)
        if entity is None:
            logger.warning("compute_and_store: entity %s not found", entity_id)
            return False

        summary = (entity.summary or "").strip()
        if not summary:
            await self._repo.update_embedding(entity_id, None, GEMINI_EMBED_MODEL, EMPTY_HASH)
            logger.debug("compute_and_store: entity %s has empty summary — marked EMPTY", entity_id)
            return True

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                vectors = await self._llm.embed([summary])
                vec = vectors[0] if vectors else None
                if vec is not None:
                    summary_hash = _sha256(summary)
                    await self._repo.update_embedding(entity_id, vec, GEMINI_EMBED_MODEL, summary_hash)
                    logger.debug(
                        "compute_and_store: entity %s embedded on attempt %d", entity_id, attempt
                    )
                    return True
                # vec is None means the API returned no data for this text
                logger.warning(
                    "compute_and_store: entity %s got None vector on attempt %d", entity_id, attempt
                )
                last_exc = ValueError("embed returned None for the text")
            except EmbeddingAPIError as exc:
                logger.warning(
                    "compute_and_store: entity %s API error on attempt %d: %s",
                    entity_id, attempt, exc,
                )
                last_exc = exc

        # All retries exhausted
        logger.warning(
            "compute_and_store: entity %s failed after %d attempts: %s",
            entity_id, self._max_retries, last_exc,
        )
        await self._repo.update_embedding(entity_id, None, GEMINI_EMBED_MODEL, FAILED_HASH)
        return False

    async def embed_query(self, text: str) -> list[float] | None:
        """Return a single 768-dim embedding for a query string.

        Pure in-memory — does NOT write to DB.

        Returns:
            Vector on success, None when API is unavailable.
        """
        if not text.strip():
            return None
        try:
            vectors = await self._llm.embed([text])
            return vectors[0] if vectors else None
        except EmbeddingAPIError as exc:
            logger.warning("embed_query: API unavailable — %s", exc)
            return None

    def needs_reembed(self, entity: Entity) -> bool:
        """Determine whether entity.summary needs (re-)embedding.

        Rules (Architect decision OQ-3):
        - summary is empty/None → False (will be / already marked EMPTY; no embed needed)
        - embedded_summary_hash is None or FAILED → True (never successfully embedded)
        - sha256(summary) != embedded_summary_hash → True (summary changed)
        - else → False
        """
        summary = (entity.summary or "").strip()
        if not summary:
            return False

        stored_hash = entity.embedded_summary_hash
        if stored_hash is None or stored_hash == FAILED_HASH:
            return True

        return _sha256(summary) != stored_hash

    async def batch_embed_missing(
        self,
        *,
        dry_run: bool = False,
        only_reembed: bool = False,
        rate_limit_per_min: int = 1500,
    ) -> BackfillStats:
        """Backfill embedding for entities that need it.

        Args:
            dry_run: Print count only; do not call API or write DB.
            only_reembed: If True, skip entities with summary_embedding=null that have
                never been attempted (embedded_summary_hash=None) — only process
                needs_reembed=True entities (hash mismatch or FAILED retry).
            rate_limit_per_min: Maximum API calls per minute.  Enforced via asyncio
                semaphore + time-window throttle.

        Returns:
            BackfillStats with totals.
        """
        start = time.monotonic()
        stats = BackfillStats()

        all_entities = await self._repo.list_all()

        candidates: list[Entity] = []
        for entity in all_entities:
            summary_empty = not (entity.summary or "").strip()
            already_embedded_fresh = (
                entity.embedded_summary_hash is not None
                and entity.embedded_summary_hash not in (FAILED_HASH, EMPTY_HASH)
                and not self.needs_reembed(entity)
            )
            if already_embedded_fresh:
                stats.skipped += 1
                continue

            if summary_empty:
                # Will be marked EMPTY — counts as "to process"
                candidates.append(entity)
                continue

            if only_reembed:
                # --only-reembed: skip entities that were NEVER attempted (hash=None).
                # Only process entities that previously had a failed attempt (FAILED sentinel)
                # or whose summary changed since the last successful embed (hash mismatch).
                hash_val = entity.embedded_summary_hash
                if hash_val is None:
                    # Never attempted — skip
                    stats.skipped += 1
                elif self.needs_reembed(entity):
                    candidates.append(entity)
                else:
                    stats.skipped += 1
            else:
                candidates.append(entity)

        stats.total = len(candidates)

        if dry_run:
            print(f"will process {stats.total} entities")
            stats.duration_seconds = time.monotonic() - start
            return stats

        # Rate-limit: allow at most rate_limit_per_min calls per 60 seconds using
        # a token-bucket approximation via asyncio.Semaphore.
        # We process sequentially here; callers can parallelise further if desired.
        # For S07 the batch script will layer additional concurrency on top.
        interval_per_call = 60.0 / rate_limit_per_min  # minimum seconds between calls

        semaphore = asyncio.Semaphore(1)  # one at a time; script can override

        async def _process(entity: Entity) -> None:
            nonlocal semaphore
            async with semaphore:
                success = await self.compute_and_store(entity.id)  # type: ignore[arg-type]
                if success:
                    summary = (entity.summary or "").strip()
                    if not summary:
                        stats.skipped += 1
                    else:
                        stats.embedded += 1
                else:
                    stats.failed += 1
                await asyncio.sleep(interval_per_call)

        tasks = [_process(e) for e in candidates]
        await asyncio.gather(*tasks)

        stats.duration_seconds = time.monotonic() - start
        return stats
