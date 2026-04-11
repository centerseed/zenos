"""PostgreSQL-backed EntityEntryRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.knowledge import EntityEntry
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire_with_tx,
    _get_partner_id,
    _now,
    _to_dt,
)


def _row_to_entry(row: asyncpg.Record) -> EntityEntry:
    return EntityEntry(
        id=row["id"],
        partner_id=row["partner_id"],
        entity_id=row["entity_id"],
        type=row["type"],
        content=row["content"],
        context=row["context"],
        author=row["author"],
        department=row["department"] if "department" in row else None,
        source_task_id=row["source_task_id"],
        status=row["status"],
        superseded_by=row["superseded_by"],
        archive_reason=row["archive_reason"],
        created_at=_to_dt(row["created_at"]) or _now(),
    )


class SqlEntityEntryRepository:
    """PostgreSQL-backed repository for entity knowledge entries.

    All queries are scoped by partner_id to enforce multi-tenant isolation.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, entry: EntityEntry, *, conn: asyncpg.Connection | None = None) -> EntityEntry:
        """Insert a new entry and return it."""
        pid = _get_partner_id()
        async with _acquire_with_tx(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entity_entries (
                    id, partner_id, entity_id, type, content,
                    context, author, department, source_task_id, status,
                    superseded_by, created_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                entry.id, pid, entry.entity_id, entry.type, entry.content,
                entry.context, entry.author, entry.department, entry.source_task_id, entry.status,
                entry.superseded_by, entry.created_at,
            )
        return entry

    async def get_by_id(self, entry_id: str) -> EntityEntry | None:
        """Fetch a single entry by ID, scoped to the current partner."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.entity_entries WHERE id = $1 AND partner_id = $2",
                entry_id, pid,
            )
        return _row_to_entry(row) if row else None

    async def list_by_entity(
        self, entity_id: str, status: str | None = "active", department: str | None = None
    ) -> list[EntityEntry]:
        """List entries for an entity. Defaults to active only; pass None for all."""
        pid = _get_partner_id()
        conditions = ["partner_id = $1", "entity_id = $2"]
        params: list[object] = [pid, entity_id]
        idx = 3
        if status is not None:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if department and department != "all":
            conditions.append(f"(department = ${idx} OR department = 'all' OR department IS NULL)")
            params.append(department)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {SCHEMA}.entity_entries
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at DESC""",
                *params,
            )
        return [_row_to_entry(r) for r in rows]

    async def update_status(
        self, entry_id: str, status: str, superseded_by: str | None = None,
        archive_reason: str | None = None,
    ) -> EntityEntry | None:
        """Update entry status, superseded_by, and archive_reason. Returns updated entry or None."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""UPDATE {SCHEMA}.entity_entries
                    SET status = $1, superseded_by = $2, archive_reason = $3
                    WHERE id = $4 AND partner_id = $5
                    RETURNING *""",
                status, superseded_by, archive_reason, entry_id, pid,
            )
        return _row_to_entry(row) if row else None

    async def list_saturated_entities(self, threshold: int = 20) -> list[dict]:
        """Return (entity, department) groups that have >= threshold active entries.

        Returns list of dicts: {entity_id, entity_name, department, active_count}.
        department may be None (treated as its own group).
        """
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT ee.entity_id, e.name AS entity_name,
                           ee.department, COUNT(*) AS active_count
                    FROM {SCHEMA}.entity_entries ee
                    JOIN {SCHEMA}.entities e
                      ON e.id = ee.entity_id AND e.partner_id = ee.partner_id
                    WHERE ee.partner_id = $1 AND ee.status = 'active'
                    GROUP BY ee.entity_id, e.name, ee.department
                    HAVING COUNT(*) >= $2
                    ORDER BY active_count DESC""",
                pid, threshold,
            )
        return [
            {
                "entity_id": r["entity_id"],
                "entity_name": r["entity_name"],
                "department": r["department"],
                "active_count": int(r["active_count"]),
            }
            for r in rows
        ]

    async def count_active_by_entity(self, entity_id: str, department: str | None = None) -> int:
        """Count active entries for an entity. Used for saturation check."""
        pid = _get_partner_id()
        conditions = ["partner_id = $1", "entity_id = $2", "status = 'active'"]
        params: list[object] = [pid, entity_id]
        if department and department != "all":
            conditions.append("(department = $3 OR department = 'all' OR department IS NULL)")
            params.append(department)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT COUNT(*) as cnt FROM {SCHEMA}.entity_entries
                    WHERE {' AND '.join(conditions)}""",
                *params,
            )
        return int(row["cnt"]) if row else 0

    async def search_content(self, query: str, limit: int = 20, department: str | None = None) -> list[dict]:
        """Search entries by content keyword, returning entries with entity context.

        Returns a list of dicts: {entry: EntityEntry, entity_id: str}.
        The caller can enrich with entity names via entity_repo.
        """
        pid = _get_partner_id()
        query_lower = f"%{query.lower()}%"
        conditions = ["ee.partner_id = $1", "LOWER(ee.content) LIKE $2"]
        params: list[object] = [pid, query_lower]
        idx = 3
        if department and department != "all":
            conditions.append(f"(ee.department = ${idx} OR ee.department = 'all' OR ee.department IS NULL)")
            params.append(department)
            idx += 1
        params.append(limit)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT ee.*, e.name AS entity_name
                    FROM {SCHEMA}.entity_entries ee
                    JOIN {SCHEMA}.entities e
                      ON e.id = ee.entity_id AND e.partner_id = ee.partner_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY ee.created_at DESC
                    LIMIT ${idx}""",
                *params,
            )
        results = []
        for row in rows:
            entry = _row_to_entry(row)
            results.append({
                "entry": entry,
                "entity_name": row["entity_name"],
            })
        return results
