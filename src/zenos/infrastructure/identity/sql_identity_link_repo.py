"""ZenOS Infrastructure — SQL-backed IdentityLink repository."""

from __future__ import annotations

import logging
import uuid

from zenos.domain.identity.federation import IdentityLink

logger = logging.getLogger(__name__)


class SqlIdentityLinkRepository:
    """PostgreSQL-backed repository for identity links."""

    def __init__(self, pool) -> None:
        self._pool = pool

    def _row_to_model(self, row: dict) -> IdentityLink:
        return IdentityLink(
            id=str(row["id"]),
            app_id=str(row["app_id"]),
            issuer=row["issuer"],
            external_user_id=row["external_user_id"],
            zenos_principal_id=row["zenos_principal_id"],
            email=row.get("email"),
            status=row["status"],
        )

    async def get(self, app_id: str, issuer: str, external_user_id: str) -> IdentityLink | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM zenos.identity_links
                WHERE app_id = $1 AND issuer = $2 AND external_user_id = $3
                """,
                uuid.UUID(app_id),
                issuer,
                external_user_id,
            )
        if row is None:
            return None
        return self._row_to_model(dict(row))

    async def create(
        self,
        app_id: str,
        issuer: str,
        external_user_id: str,
        zenos_principal_id: str,
        email: str | None = None,
    ) -> IdentityLink:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO zenos.identity_links (app_id, issuer, external_user_id, zenos_principal_id, email)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                uuid.UUID(app_id),
                issuer,
                external_user_id,
                zenos_principal_id,
                email,
            )
        return self._row_to_model(dict(row))

    async def list_by_principal(self, zenos_principal_id: str) -> list[IdentityLink]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM zenos.identity_links WHERE zenos_principal_id = $1",
                zenos_principal_id,
            )
        return [self._row_to_model(dict(r)) for r in rows]
