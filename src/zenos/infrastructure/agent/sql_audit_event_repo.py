"""PostgreSQL-backed AuditEventRepository."""

from __future__ import annotations

import json
from datetime import datetime

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA


class SqlAuditEventRepository:
    """PostgreSQL-backed repository for immutable governance audit events."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, event: dict) -> None:
        """Write an audit event row. Failure must not propagate to caller."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.audit_events
                    (partner_id, actor_id, actor_type, operation, resource_type, resource_id, changes_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                event["partner_id"],
                event["actor_id"],
                event.get("actor_type", "partner"),
                event["operation"],
                event["resource_type"],
                event.get("resource_id"),
                json.dumps(event.get("changes_json") or {}, default=str),
            )

    async def list_events(
        self,
        partner_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        operation: str | None = None,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return audit events for a partner, optionally filtered."""
        conditions = ["partner_id = $1"]
        params: list = [partner_id]
        i = 2
        if since:
            conditions.append(f"timestamp >= ${i}")
            params.append(since)
            i += 1
        if until:
            conditions.append(f"timestamp <= ${i}")
            params.append(until)
            i += 1
        if operation:
            conditions.append(f"operation = ${i}")
            params.append(operation)
            i += 1
        if actor_id:
            conditions.append(f"actor_id = ${i}")
            params.append(actor_id)
            i += 1
        where = " AND ".join(conditions)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.audit_events WHERE {where} ORDER BY timestamp DESC LIMIT {limit}",
                *params,
            )
        return [dict(r) for r in rows]
