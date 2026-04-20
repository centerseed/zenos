"""PostgreSQL-backed BlindspotRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.knowledge import Blindspot
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire_with_tx,
    _get_partner_id,
    _new_id,
    _now,
    _to_dt,
)


def _row_to_blindspot(row: asyncpg.Record, related_entity_ids: list[str]) -> Blindspot:
    return Blindspot(
        id=row["id"],
        description=row["description"],
        severity=row["severity"],
        related_entity_ids=related_entity_ids,
        suggested_action=row["suggested_action"],
        status=row["status"],
        confirmed_by_user=row["confirmed_by_user"],
        created_at=_to_dt(row["created_at"]) or _now(),
    )


class SqlBlindspotRepository:
    """PostgreSQL-backed BlindspotRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_related_entity_ids(self, conn: asyncpg.Connection, blindspot_id: str, pid: str) -> list[str]:
        rows = await conn.fetch(
            f"SELECT entity_id FROM {SCHEMA}.blindspot_entities WHERE blindspot_id = $1 AND partner_id = $2",
            blindspot_id, pid,
        )
        return [r["entity_id"] for r in rows]

    async def list_all(
        self,
        entity_id: str | None = None,
        severity: str | None = None,
    ) -> list[Blindspot]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if entity_id is not None and severity is not None:
                rows = await conn.fetch(
                    f"""SELECT DISTINCT b.* FROM {SCHEMA}.blindspots b
                        JOIN {SCHEMA}.blindspot_entities be ON b.id = be.blindspot_id
                        WHERE be.entity_id = $1 AND b.severity = $2 AND b.partner_id = $3""",
                    entity_id, severity, pid,
                )
            elif entity_id is not None:
                rows = await conn.fetch(
                    f"""SELECT DISTINCT b.* FROM {SCHEMA}.blindspots b
                        JOIN {SCHEMA}.blindspot_entities be ON b.id = be.blindspot_id
                        WHERE be.entity_id = $1 AND b.partner_id = $2""",
                    entity_id, pid,
                )
            elif severity is not None:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.blindspots WHERE severity = $1 AND partner_id = $2",
                    severity, pid,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.blindspots WHERE partner_id = $1",
                    pid,
                )
            if not rows:
                return []
            bs_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT blindspot_id, entity_id FROM {SCHEMA}.blindspot_entities"
                f" WHERE partner_id = $1 AND blindspot_id = ANY($2::text[])",
                pid, bs_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["blindspot_id"], []).append(lr["entity_id"])
        return [_row_to_blindspot(r, links.get(r["id"], [])) for r in rows]

    async def find_by_id_prefix(
        self, prefix: str, partner_id: str, limit: int = 11
    ) -> list[Blindspot]:
        """Return blindspots whose id starts with prefix, scoped to partner_id.

        limit=11 lets the caller distinguish "exactly 10" from "more than 10"
        (SPEC-mcp-id-ergonomics AC-MIDE-03/04).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.blindspots"
                f" WHERE id LIKE $1 || '%' AND partner_id = $2"
                f" ORDER BY id LIMIT $3",
                prefix, partner_id, limit,
            )
            if not rows:
                return []
            bs_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT blindspot_id, entity_id FROM {SCHEMA}.blindspot_entities"
                f" WHERE partner_id = $1 AND blindspot_id = ANY($2::text[])",
                partner_id, bs_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["blindspot_id"], []).append(lr["entity_id"])
        return [_row_to_blindspot(r, links.get(r["id"], [])) for r in rows]

    async def add(self, blindspot: Blindspot, *, conn: asyncpg.Connection | None = None) -> Blindspot:
        pid = _get_partner_id()
        now = _now()
        if blindspot.created_at is None:  # type: ignore[comparison-overlap]
            blindspot.created_at = now
        if blindspot.id is None:
            blindspot.id = _new_id()

        async with _acquire_with_tx(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.blindspots (
                    id, partner_id, description, severity, suggested_action,
                    status, confirmed_by_user, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO UPDATE SET
                    description=EXCLUDED.description, severity=EXCLUDED.severity,
                    suggested_action=EXCLUDED.suggested_action, status=EXCLUDED.status,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at
                WHERE blindspots.partner_id = EXCLUDED.partner_id
                """,
                blindspot.id, pid, blindspot.description, blindspot.severity,
                blindspot.suggested_action, blindspot.status,
                blindspot.confirmed_by_user, blindspot.created_at, now,
            )
            # Sync blindspot_entities join table
            await _conn.execute(
                f"DELETE FROM {SCHEMA}.blindspot_entities WHERE blindspot_id = $1 AND partner_id = $2",
                blindspot.id, pid,
            )
            if blindspot.related_entity_ids:
                await _conn.executemany(
                    f"INSERT INTO {SCHEMA}.blindspot_entities (blindspot_id, entity_id, partner_id)"
                    f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    [(blindspot.id, eid, pid) for eid in blindspot.related_entity_ids],
                )
        return blindspot

    async def list_unconfirmed(self) -> list[Blindspot]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.blindspots WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
            if not rows:
                return []
            bs_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT blindspot_id, entity_id FROM {SCHEMA}.blindspot_entities"
                f" WHERE partner_id = $1 AND blindspot_id = ANY($2::text[])",
                pid, bs_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["blindspot_id"], []).append(lr["entity_id"])
        return [_row_to_blindspot(r, links.get(r["id"], [])) for r in rows]

    async def get_by_id(self, blindspot_id: str) -> Blindspot | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.blindspots WHERE id = $1 AND partner_id = $2",
                blindspot_id, pid,
            )
            if not row:
                return None
            related = await self._fetch_related_entity_ids(conn, blindspot_id, pid)
        return _row_to_blindspot(row, related)
