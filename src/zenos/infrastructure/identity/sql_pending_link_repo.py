"""ZenOS Infrastructure — SQL-backed PendingIdentityLink repository."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from zenos.domain.identity.pending_link import PendingIdentityLink

logger = logging.getLogger(__name__)


class SqlPendingIdentityLinkRepository:
    """PostgreSQL-backed repository for pending identity link requests."""

    def __init__(self, pool) -> None:
        self._pool = pool

    def _row_to_model(self, row: dict) -> PendingIdentityLink:
        return PendingIdentityLink(
            id=str(row["id"]),
            app_id=str(row["app_id"]),
            issuer=row["issuer"],
            external_user_id=row["external_user_id"],
            workspace_id=str(row["workspace_id"]),
            status=row["status"],
            email=row.get("email"),
            reviewed_by=row.get("reviewed_by"),
            reviewed_at=row.get("reviewed_at"),
            created_at=row.get("created_at"),
            expires_at=row.get("expires_at"),
        )

    async def get_most_recent(
        self, app_id: str, issuer: str, external_user_id: str
    ) -> PendingIdentityLink | None:
        """Return the most recent pending link for this user (any status), or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM zenos.pending_identity_links
                WHERE app_id = $1
                  AND issuer = $2
                  AND external_user_id = $3
                ORDER BY created_at DESC
                LIMIT 1
                """,
                uuid.UUID(app_id),
                issuer,
                external_user_id,
            )
        if row is None:
            return None
        return self._row_to_model(dict(row))

    async def get_active(
        self, app_id: str, issuer: str, external_user_id: str
    ) -> PendingIdentityLink | None:
        """Return the active (status=pending, not expired) pending link, or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM zenos.pending_identity_links
                WHERE app_id = $1
                  AND issuer = $2
                  AND external_user_id = $3
                  AND status = 'pending'
                  AND expires_at > now()
                """,
                uuid.UUID(app_id),
                issuer,
                external_user_id,
            )
        if row is None:
            return None
        return self._row_to_model(dict(row))

    async def get_by_id(self, pending_link_id: str) -> PendingIdentityLink | None:
        """Fetch a pending link by its UUID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM zenos.pending_identity_links WHERE id = $1",
                uuid.UUID(pending_link_id),
            )
        if row is None:
            return None
        return self._row_to_model(dict(row))

    async def create(
        self,
        app_id: str,
        issuer: str,
        external_user_id: str,
        workspace_id: str,
        email: str | None = None,
    ) -> PendingIdentityLink:
        """Insert a new pending link (status=pending, expires in 7 days)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO zenos.pending_identity_links
                    (app_id, issuer, external_user_id, workspace_id, email)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                uuid.UUID(app_id),
                issuer,
                external_user_id,
                workspace_id,
                email,
            )
        return self._row_to_model(dict(row))

    async def expire_pending(
        self, app_id: str, issuer: str, external_user_id: str
    ) -> None:
        """Mark all pending (but expired) links for this user as 'expired'."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE zenos.pending_identity_links
                SET status = 'expired'
                WHERE app_id = $1
                  AND issuer = $2
                  AND external_user_id = $3
                  AND status = 'pending'
                  AND expires_at <= now()
                """,
                uuid.UUID(app_id),
                issuer,
                external_user_id,
            )

    async def update_status(
        self,
        pending_link_id: str,
        status: str,
        reviewed_by: str | None = None,
    ) -> None:
        """Update the status of a pending link (approved/rejected)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE zenos.pending_identity_links
                SET status = $2, reviewed_by = $3, reviewed_at = now()
                WHERE id = $1
                """,
                uuid.UUID(pending_link_id),
                status,
                reviewed_by,
            )

    async def list_by_workspace(
        self, workspace_id: str, status: str | None = None
    ) -> list[PendingIdentityLink]:
        """List pending links for a workspace, optionally filtered by status."""
        async with self._pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM zenos.pending_identity_links
                    WHERE workspace_id = $1 AND status = $2
                    ORDER BY created_at DESC
                    """,
                    workspace_id,
                    status,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM zenos.pending_identity_links
                    WHERE workspace_id = $1
                    ORDER BY created_at DESC
                    """,
                    workspace_id,
                )
        return [self._row_to_model(dict(r)) for r in rows]
