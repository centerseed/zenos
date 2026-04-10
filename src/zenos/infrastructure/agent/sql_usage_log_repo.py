"""PostgreSQL-backed UsageLogRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA


class SqlUsageLogRepository:
    """PostgreSQL-backed UsageLogRepository.

    Writes LLM usage records to the usage_logs table.
    This class has no partner_id context dependency; the partner_id is
    passed explicitly so it can be called from background tasks.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_usage_log(
        self,
        partner_id: str,
        feature: str,
        tokens_in: int,
        tokens_out: int,
        model: str,
    ) -> None:
        """Insert a usage log row. Silently ignores empty partner_id."""
        if not partner_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.usage_logs (partner_id, feature, model, tokens_in, tokens_out)
                    VALUES ($1, $2, $3, $4, $5)""",
                partner_id,
                feature,
                model,
                tokens_in,
                tokens_out,
            )
