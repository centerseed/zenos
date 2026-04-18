"""PostgreSQL-backed RelationshipRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.knowledge import Relationship
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire,
    _get_partner_id,
    _new_id,
    _now,
)


def _row_to_relationship(row: asyncpg.Record) -> Relationship:
    return Relationship(
        id=row["id"],
        source_entity_id=row["source_entity_id"],
        target_id=row["target_entity_id"],  # SQL col → domain field
        type=row["type"],
        description=row["description"],
        confirmed_by_user=row["confirmed_by_user"],
        # verb column exists in DB schema but is no longer read (fill rate 8.8%, removed 2026-04-18)
    )


class SqlRelationshipRepository:
    """PostgreSQL-backed RelationshipRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_entity(self, entity_id: str) -> list[Relationship]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {SCHEMA}.relationships
                    WHERE (source_entity_id = $1 OR target_entity_id = $1)
                    AND partner_id = $2""",
                entity_id, pid,
            )
        return [_row_to_relationship(r) for r in rows]

    async def list_all(self) -> list[Relationship]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.relationships WHERE partner_id = $1",
                pid,
            )
        return [_row_to_relationship(r) for r in rows]

    async def find_duplicate(
        self, source_entity_id: str, target_id: str, rel_type: str,
    ) -> Relationship | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT * FROM {SCHEMA}.relationships
                    WHERE source_entity_id = $1 AND target_entity_id = $2
                    AND type = $3 AND partner_id = $4 LIMIT 1""",
                source_entity_id, target_id, rel_type, pid,
            )
        return _row_to_relationship(row) if row else None

    async def add(self, rel: Relationship, *, conn: asyncpg.Connection | None = None) -> Relationship:
        pid = _get_partner_id()
        now = _now()
        if rel.id is None:
            rel.id = _new_id()

        async with _acquire(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.relationships (
                    id, partner_id, source_entity_id, target_entity_id,
                    type, description, confirmed_by_user, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO UPDATE SET
                    source_entity_id=EXCLUDED.source_entity_id,
                    target_entity_id=EXCLUDED.target_entity_id,
                    type=EXCLUDED.type, description=EXCLUDED.description,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at
                WHERE relationships.partner_id = EXCLUDED.partner_id
                """,
                rel.id, pid, rel.source_entity_id, rel.target_id,
                rel.type, rel.description, rel.confirmed_by_user, now, now,
            )
        return rel

    async def find_orphan_entities(self) -> list[dict]:
        """Find entities with zero relationships (excluding product/project roots)."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT e.id, e.name, e.type, e.level
                    FROM {SCHEMA}.entities e
                    LEFT JOIN {SCHEMA}.relationships r
                        ON (r.source_entity_id = e.id OR r.target_entity_id = e.id)
                        AND r.partner_id = e.partner_id
                    WHERE e.partner_id = $1
                        AND e.type NOT IN ('product', 'project')
                        AND e.status != 'archived'
                        AND r.id IS NULL""",
                pid,
            )
        return [dict(r) for r in rows]

    async def find_common_neighbors(
        self, entity_a_id: str, entity_b_id: str
    ) -> list[dict]:
        """Find entities that are directly connected to both A and B."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""WITH neighbors_a AS (
                        SELECT CASE WHEN source_entity_id = $1 THEN target_entity_id
                                    ELSE source_entity_id END AS neighbor_id,
                               type AS edge_type_a
                        FROM {SCHEMA}.relationships
                        WHERE (source_entity_id = $1 OR target_entity_id = $1)
                            AND partner_id = $3
                    ),
                    neighbors_b AS (
                        SELECT CASE WHEN source_entity_id = $2 THEN target_entity_id
                                    ELSE source_entity_id END AS neighbor_id,
                               type AS edge_type_b
                        FROM {SCHEMA}.relationships
                        WHERE (source_entity_id = $2 OR target_entity_id = $2)
                            AND partner_id = $3
                    )
                    SELECT a.neighbor_id, e.name AS neighbor_name,
                           a.edge_type_a, b.edge_type_b
                    FROM neighbors_a a
                    JOIN neighbors_b b ON a.neighbor_id = b.neighbor_id
                    JOIN {SCHEMA}.entities e ON e.id = a.neighbor_id AND e.partner_id = $3
                    WHERE a.neighbor_id != $1 AND a.neighbor_id != $2""",
                entity_a_id, entity_b_id, pid,
            )
        return [dict(r) for r in rows]

    async def remove(self, source_entity_id: str, target_id: str, rel_type: str) -> int:
        """Delete a relationship edge by source/target/type. Returns rowcount."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""DELETE FROM {SCHEMA}.relationships
                    WHERE source_entity_id = $1 AND target_entity_id = $2
                    AND type = $3 AND partner_id = $4""",
                source_entity_id, target_id, rel_type, pid,
            )
        return int(result.split()[-1])
