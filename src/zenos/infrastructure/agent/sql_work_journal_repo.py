"""PostgreSQL-backed WorkJournalRepository."""

from __future__ import annotations

import uuid
from datetime import datetime

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA

_MAX_SUMMARY_LENGTH = 500
_EMPTY_SUMMARY_FALLBACK = "Journal summary unavailable."


def _normalize_summary(summary: str) -> str:
    """Match zenos.work_journal.summary DB constraints before insert."""
    normalized = (summary or "").strip()
    if not normalized:
        return _EMPTY_SUMMARY_FALLBACK
    return normalized[:_MAX_SUMMARY_LENGTH]


class SqlWorkJournalRepository:
    """PostgreSQL-backed repository for agent work journal entries.

    The work_journal table stores operational session/flow summaries for agents.
    It is independent of the ontology layers (not L2/L3 entity).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(
        self,
        *,
        partner_id: str,
        summary: str,
        project: str | None = None,
        flow_type: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Insert a new journal entry and return its UUID string."""
        entry_id = str(uuid.uuid4())
        normalized_summary = _normalize_summary(summary)
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.work_journal
                    (id, partner_id, summary, project, flow_type, tags)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                entry_id,
                partner_id,
                normalized_summary,
                project,
                flow_type,
                tags or [],
            )
        return entry_id

    async def count(self, *, partner_id: str) -> int:
        """Return total number of journal entries for a partner."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                f"SELECT COUNT(*) FROM {SCHEMA}.work_journal WHERE partner_id = $1",
                partner_id,
            )

    async def list_recent(
        self,
        *,
        partner_id: str,
        limit: int,
        project: str | None = None,
        flow_type: str | None = None,
    ) -> tuple[list[dict], int]:
        """Return (entries, total) for a partner, newest first.

        Optionally filtered by project or flow_type.
        Returns at most `limit` entries; total reflects the unfiltered count.
        """
        conditions = ["partner_id = $1"]
        params: list = [partner_id]
        i = 2
        if project is not None:
            conditions.append(f"project = ${i}")
            params.append(project)
            i += 1
        if flow_type is not None:
            conditions.append(f"flow_type = ${i}")
            params.append(flow_type)
            i += 1
        where = " AND ".join(conditions)
        async with self._pool.acquire() as conn:
            total: int = await conn.fetchval(
                f"SELECT COUNT(*) FROM {SCHEMA}.work_journal WHERE {where}",
                *params,
            )
            rows = await conn.fetch(
                f"SELECT id, created_at, project, flow_type, summary, tags, is_summary"
                f" FROM {SCHEMA}.work_journal WHERE {where}"
                f" ORDER BY created_at DESC LIMIT {limit}",
                *params,
            )
        return [dict(r) for r in rows], total

    async def list_oldest_originals(
        self,
        *,
        partner_id: str,
        limit: int,
    ) -> list[dict]:
        """Return oldest non-summary entries (is_summary=FALSE), oldest first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT id, created_at, project, flow_type, summary, tags, is_summary"
                f" FROM {SCHEMA}.work_journal"
                f" WHERE partner_id = $1 AND is_summary = FALSE"
                f" ORDER BY created_at ASC LIMIT {limit}",
                partner_id,
            )
        return [dict(r) for r in rows]

    async def delete_by_ids(self, *, partner_id: str, ids: list[str]) -> None:
        """Delete journal entries by IDs, scoped to partner_id."""
        if not ids:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {SCHEMA}.work_journal"
                f" WHERE partner_id = $1 AND id = ANY($2::uuid[])",
                partner_id,
                ids,
            )

    async def create_summary(
        self,
        *,
        partner_id: str,
        summary: str,
        project: str | None = None,
        flow_type: str | None = None,
        tags: list[str] | None = None,
        as_of: datetime,
    ) -> str:
        """Insert a compressed summary entry (is_summary=TRUE) and return its UUID."""
        entry_id = str(uuid.uuid4())
        normalized_summary = _normalize_summary(summary)
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.work_journal
                    (id, partner_id, created_at, summary, project, flow_type, tags, is_summary)
                VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
                """,
                entry_id,
                partner_id,
                as_of,
                normalized_summary,
                project,
                flow_type,
                tags or [],
            )
        return entry_id
