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
        outcome: str = "success",
    ) -> None:
        """Insert a usage log row. Silently ignores empty partner_id."""
        if not partner_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.usage_logs
                    (partner_id, feature, model, tokens_in, tokens_out, outcome)
                    VALUES ($1, $2, $3, $4, $5, $6)""",
                partner_id,
                feature,
                model,
                tokens_in,
                tokens_out,
                outcome,
            )

    async def summarize_provider_health(
        self,
        partner_id: str,
        *,
        days: int = 7,
        hours: int = 1,
    ) -> list[dict]:
        """Aggregate recent provider-level LLM outcomes from usage_logs."""
        if not partner_id:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                WITH recent AS (
                    SELECT
                        CASE
                            WHEN model ILIKE 'gemini/%' OR model ILIKE 'gemini%%' THEN 'gemini'
                            WHEN model ILIKE 'openai/%' OR model ILIKE 'gpt-%%' THEN 'openai'
                            ELSE split_part(model, '/', 1)
                        END AS provider,
                        model,
                        outcome,
                        created_at
                    FROM {SCHEMA}.usage_logs
                    WHERE partner_id = $1
                      AND created_at >= now() - make_interval(days => $2)
                )
                SELECT
                    provider,
                    max(model) AS model,
                    count(*) FILTER (WHERE outcome = 'success') AS success_count_7d,
                    count(*) FILTER (WHERE outcome = 'fallback') AS fallback_count_7d,
                    count(*) FILTER (WHERE outcome = 'exception') AS exception_count_7d,
                    max(created_at) FILTER (WHERE outcome = 'success') AS last_success_at,
                    count(*) FILTER (
                        WHERE outcome = 'success'
                          AND created_at >= now() - make_interval(hours => $3)
                    ) AS success_count_1h,
                    count(*) FILTER (
                        WHERE outcome = 'fallback'
                          AND created_at >= now() - make_interval(hours => $3)
                    ) AS fallback_count_1h,
                    count(*) FILTER (
                        WHERE outcome = 'exception'
                          AND created_at >= now() - make_interval(hours => $3)
                    ) AS exception_count_1h
                FROM recent
                GROUP BY provider
                ORDER BY provider
                """,
                partner_id,
                days,
                hours,
            )
        return [dict(row) for row in rows]
