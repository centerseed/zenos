"""PostgreSQL-backed ProtocolRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.knowledge import Gap
from zenos.domain.knowledge import Protocol as OntologyProtocol
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _dumps,
    _get_partner_id,
    _json_loads_safe,
    _new_id,
    _now,
    _to_dt,
)


def _row_to_protocol(row: asyncpg.Record) -> OntologyProtocol:
    gaps_raw = _json_loads_safe(row["gaps_json"]) or []
    gaps = [
        Gap(description=g.get("description", ""), priority=g.get("priority", "green"))
        for g in gaps_raw
    ]
    return OntologyProtocol(
        id=row["id"],
        entity_id=row["entity_id"],
        entity_name=row["entity_name"],
        content=_json_loads_safe(row["content_json"]) or {},
        gaps=gaps,
        version=row["version"],
        confirmed_by_user=row["confirmed_by_user"],
        generated_at=_to_dt(row["generated_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


class SqlProtocolRepository:
    """PostgreSQL-backed ProtocolRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, protocol_id: str) -> OntologyProtocol | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.protocols WHERE id = $1 AND partner_id = $2",
                protocol_id, pid,
            )
        return _row_to_protocol(row) if row else None

    async def get_by_entity(self, entity_id: str) -> OntologyProtocol | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.protocols WHERE entity_id = $1 AND partner_id = $2 LIMIT 1",
                entity_id, pid,
            )
        return _row_to_protocol(row) if row else None

    async def get_by_entity_name(self, name: str) -> OntologyProtocol | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.protocols WHERE entity_name = $1 AND partner_id = $2 LIMIT 1",
                name, pid,
            )
        return _row_to_protocol(row) if row else None

    async def upsert(self, protocol: OntologyProtocol) -> OntologyProtocol:
        pid = _get_partner_id()
        now = _now()
        protocol.updated_at = now
        if protocol.id is None:
            protocol.id = _new_id()
            protocol.generated_at = now

        gaps_list = [{"description": g.description, "priority": g.priority} for g in protocol.gaps]

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.protocols (
                    id, partner_id, entity_id, entity_name, content_json,
                    gaps_json, version, confirmed_by_user, generated_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8,$9,$10)
                ON CONFLICT (id) DO UPDATE SET
                    entity_id=EXCLUDED.entity_id, entity_name=EXCLUDED.entity_name,
                    content_json=EXCLUDED.content_json, gaps_json=EXCLUDED.gaps_json,
                    version=EXCLUDED.version, confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at
                WHERE protocols.partner_id = EXCLUDED.partner_id
                """,
                protocol.id, pid, protocol.entity_id, protocol.entity_name,
                _dumps(protocol.content), _dumps(gaps_list),
                protocol.version, protocol.confirmed_by_user,
                protocol.generated_at, protocol.updated_at,
            )
        return protocol

    async def list_unconfirmed(self) -> list[OntologyProtocol]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.protocols WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
        return [_row_to_protocol(r) for r in rows]

    async def list_all(self, confirmed_only: bool | None = None) -> list[OntologyProtocol]:
        """Fetch all protocols for the current partner in a single query.

        Args:
            confirmed_only: If True, return only confirmed protocols.
                            If False, return only unconfirmed protocols.
                            If None, return all protocols.
        """
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if confirmed_only is None:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.protocols WHERE partner_id = $1",
                    pid,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.protocols WHERE partner_id = $1 AND confirmed_by_user = $2",
                    pid, confirmed_only,
                )
        return [_row_to_protocol(r) for r in rows]
