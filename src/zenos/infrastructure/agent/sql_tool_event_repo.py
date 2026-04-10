"""PostgreSQL-backed ToolEventRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA


class SqlToolEventRepository:
    """PostgreSQL-backed ToolEventRepository.

    Tracks agent tool usage (search/get) per entity for feedback loop analysis.
    The partner_id is passed explicitly so it can be called from background tasks.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def log_tool_event(
        self,
        partner_id: str,
        tool_name: str,
        entity_id: str | None,
        query: str | None,
        result_count: int | None,
    ) -> None:
        """Insert a tool event row. Silently ignores empty partner_id."""
        if not partner_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.tool_events
                    (partner_id, tool_name, entity_id, query, result_count)
                    VALUES ($1, $2, $3, $4, $5)""",
                partner_id,
                tool_name,
                entity_id,
                query,
                result_count,
            )

    async def get_entity_usage_stats(
        self,
        partner_id: str,
        days: int = 30,
    ) -> list[dict]:
        """Return per-entity search/get counts for the past N days.

        Uses a parameterized interval to avoid SQL injection.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT entity_id,
                           SUM(CASE WHEN tool_name = 'search' THEN 1 ELSE 0 END) AS search_count,
                           SUM(CASE WHEN tool_name = 'get' THEN 1 ELSE 0 END) AS get_count
                    FROM {SCHEMA}.tool_events
                    WHERE partner_id = $1
                      AND entity_id IS NOT NULL
                      AND created_at > now() - ($2 || ' days')::interval
                    GROUP BY entity_id""",
                partner_id,
                str(days),
            )
        return [
            {
                "entity_id": row["entity_id"],
                "search_count": int(row["search_count"]),
                "get_count": int(row["get_count"]),
            }
            for row in rows
        ]
