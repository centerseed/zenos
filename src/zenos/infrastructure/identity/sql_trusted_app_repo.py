"""ZenOS Infrastructure — SQL-backed TrustedApp repository."""

from __future__ import annotations

import logging
import uuid

from zenos.domain.identity.federation import TrustedApp

logger = logging.getLogger(__name__)


class SqlTrustedAppRepository:
    """PostgreSQL-backed repository for trusted apps."""

    def __init__(self, pool) -> None:
        self._pool = pool

    def _row_to_model(self, row: dict) -> TrustedApp:
        return TrustedApp(
            app_id=str(row["app_id"]),
            app_name=row["app_name"],
            app_secret_hash=row["app_secret_hash"],
            allowed_issuers=list(row["allowed_issuers"] or []),
            allowed_scopes=list(row["allowed_scopes"] or ["read"]),
            status=row["status"],
        )

    async def get_by_id(self, app_id: str) -> TrustedApp | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM zenos.trusted_apps WHERE app_id = $1",
                uuid.UUID(app_id),
            )
        if row is None:
            return None
        return self._row_to_model(dict(row))

    async def get_by_name(self, app_name: str) -> TrustedApp | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM zenos.trusted_apps WHERE app_name = $1",
                app_name,
            )
        if row is None:
            return None
        return self._row_to_model(dict(row))

    async def create(
        self,
        app_name: str,
        app_secret_hash: str,
        allowed_issuers: list[str],
        allowed_scopes: list[str],
    ) -> TrustedApp:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO zenos.trusted_apps (app_name, app_secret_hash, allowed_issuers, allowed_scopes)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                app_name,
                app_secret_hash,
                allowed_issuers,
                allowed_scopes,
            )
        return self._row_to_model(dict(row))

    async def update_status(self, app_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE zenos.trusted_apps SET status = $1, updated_at = now() WHERE app_id = $2",
                status,
                uuid.UUID(app_id),
            )
