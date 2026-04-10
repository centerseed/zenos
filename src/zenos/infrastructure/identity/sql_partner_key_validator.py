"""PostgreSQL-backed SqlPartnerKeyValidator."""

from __future__ import annotations

import time

from zenos.infrastructure.sql_common import SCHEMA, get_pool


class SqlPartnerKeyValidator:
    """Validates API keys against the SQL partners table.

    Caches active partner keys in memory with a configurable TTL to avoid
    a database round-trip on every request.
    """

    def __init__(self, ttl: int = 300) -> None:
        self._cache: dict[str, dict] = {}
        self._cache_ts: float = 0.0
        self._ttl = ttl

    async def validate(self, key: str) -> dict | None:
        """Return partner data dict if *key* belongs to an active partner."""
        now = time.time()
        if now - self._cache_ts > self._ttl:
            await self._refresh_cache()
        return self._cache.get(key)

    async def _refresh_cache(self) -> None:
        import logging
        logger = logging.getLogger(__name__)
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""SELECT id, email, display_name, api_key,
                               authorized_entity_ids, status, is_admin,
                               shared_partner_id, access_mode, default_project, roles, department
                        FROM {SCHEMA}.partners WHERE status = 'active'"""
                )
            new_cache: dict[str, dict] = {}
            for row in rows:
                api_key = row["api_key"]
                if api_key:
                    new_cache[api_key] = {
                        "id": row["id"],
                        "email": row["email"],
                        "displayName": row["display_name"],
                        "apiKey": row["api_key"],
                        "authorizedEntityIds": list(row["authorized_entity_ids"] or []),
                        "status": row["status"],
                        "isAdmin": row["is_admin"],
                        "sharedPartnerId": row["shared_partner_id"],
                        "accessMode": row["access_mode"] if "access_mode" in row else None,
                        "defaultProject": row["default_project"] or "",
                        "roles": list(row["roles"] or []) if "roles" in row else [],
                        "department": (row["department"] or "all") if "department" in row else "all",
                    }
            self._cache = new_cache
            self._cache_ts = time.time()
            logger.info("Partner cache refreshed from SQL: %d active keys", len(new_cache))
        except Exception:
            logger.exception("Failed to refresh partner cache from SQL")
            if not self._cache:
                self._cache_ts = time.time()
