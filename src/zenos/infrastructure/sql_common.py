"""Shared helpers for all SQL repository implementations.

Centralises the connection pool singleton, partner-ID context lookup,
connection helpers, and general data-conversion utilities so that each
sub-package repository can import them without circular dependencies.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.context import current_partner_id

# ---------------------------------------------------------------------------
# Schema constant
# ---------------------------------------------------------------------------

SCHEMA = "zenos"

# ---------------------------------------------------------------------------
# Connection pool singleton
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return a shared asyncpg connection pool, creating it on first call.

    Supports Cloud SQL socket URLs (``?host=/cloudsql/...``) by extracting
    the Unix socket path from the query string and passing it to asyncpg
    as the ``host`` parameter.
    """
    global _pool  # noqa: PLW0603
    if _pool is None:
        from urllib.parse import urlparse, parse_qs

        database_url = os.environ["DATABASE_URL"]
        parsed = urlparse(database_url)
        socket_host = parse_qs(parsed.query).get("host", [None])[0]

        if socket_host:
            _pool = await asyncpg.create_pool(
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip("/"),
                host=socket_host,
                min_size=2,
                max_size=10,
            )
        else:
            _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    return _pool


# ---------------------------------------------------------------------------
# Partner-ID helper
# ---------------------------------------------------------------------------


def _get_partner_id() -> str:
    pid = current_partner_id.get()
    if not pid:
        raise RuntimeError("No partner_id in context")
    return pid


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _acquire(pool: asyncpg.Pool, conn: asyncpg.Connection | None):
    """Yield an existing connection or acquire one from the pool."""
    if conn is not None:
        yield conn
        return
    c = await pool.acquire()
    try:
        yield c
    finally:
        await pool.release(c)


@asynccontextmanager
async def _acquire_with_tx(pool: asyncpg.Pool, conn: asyncpg.Connection | None):
    """Like _acquire, but also starts a transaction when using a pool connection."""
    if conn is not None:
        yield conn
        return
    c = await pool.acquire()
    try:
        async with c.transaction():
            yield c
    finally:
        await pool.release(c)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    """Generate a short unique ID (32-char hex UUID4)."""
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    return None


def _json_loads_safe(raw: Any) -> Any:
    """Return parsed JSON or the value as-is (asyncpg may auto-decode JSONB)."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _dumps(obj: Any) -> str:
    return json.dumps(obj)


# ---------------------------------------------------------------------------
# Governance Health Cache — standalone helpers (no class needed)
# ---------------------------------------------------------------------------


async def get_cached_health(pool: asyncpg.Pool, partner_id: str) -> dict | None:
    """Return cached health signal or None if no cache exists.

    Returns: {"overall_level": str, "computed_at": datetime} or None.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT overall_level, computed_at FROM {SCHEMA}.governance_health_cache "
            "WHERE partner_id = $1",
            partner_id,
        )
    if row is None:
        return None
    return {
        "overall_level": row["overall_level"],
        "computed_at": row["computed_at"],
    }


async def upsert_health_cache(
    pool: asyncpg.Pool, partner_id: str, overall_level: str
) -> None:
    """UPSERT governance health cache for a partner."""
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.governance_health_cache (partner_id, overall_level, computed_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (partner_id) DO UPDATE SET
                overall_level = EXCLUDED.overall_level,
                computed_at = EXCLUDED.computed_at
            """,
            partner_id,
            overall_level,
        )
