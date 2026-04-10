"""PostgreSQL-backed PartnerRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import (
    SCHEMA,
    _now,
)

_PARTNER_SELECT_COLS = """id, email, display_name, api_key, authorized_entity_ids,
                       status, is_admin, shared_partner_id, access_mode, default_project, invited_by,
                       roles, department, created_at, updated_at, invite_expires_at, preferences"""


def _row_to_partner_dict(row: asyncpg.Record) -> dict:
    """Convert a partners table row to a standardized partner dict."""
    return {
        "id": row["id"],
        "email": row["email"],
        "displayName": row["display_name"],
        "apiKey": row["api_key"],
        "authorizedEntityIds": list(row["authorized_entity_ids"] or []),
        "status": row["status"],
        "isAdmin": row["is_admin"],
        "sharedPartnerId": row["shared_partner_id"],
        "accessMode": row["access_mode"] if "access_mode" in row else None,
        "defaultProject": row["default_project"],
        "roles": list(row["roles"] or []) if "roles" in row else [],
        "department": (row["department"] or "all") if "department" in row else "all",
        "invitedBy": row["invited_by"],
        "createdAt": row["created_at"] if "created_at" in row else None,
        "updatedAt": row["updated_at"] if "updated_at" in row else None,
        "inviteExpiresAt": row["invite_expires_at"] if "invite_expires_at" in row else None,
        "preferences": row["preferences"] if "preferences" in row and row["preferences"] else {},
    }


def _deep_merge_prefs(base: dict, patch: dict) -> dict:
    """Recursively merge *patch* into *base* (new dict, no mutation).

    When both the base value and patch value for a key are dicts, they are
    merged recursively.  Otherwise the patch value wins.
    """
    result = dict(base)
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_prefs(result[key], value)
        else:
            result[key] = value
    return result


class SqlPartnerRepository:
    """PostgreSQL-backed PartnerRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_email(self, email: str) -> dict | None:
        """Fetch partner by email. Returns standardized dict or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT {_PARTNER_SELECT_COLS}
                FROM {SCHEMA}.partners
                WHERE btrim(lower(email)) = btrim(lower($1))
                LIMIT 1
                """,
                email,
            )
        return _row_to_partner_dict(row) if row else None

    async def get_by_id(self, partner_id: str) -> dict | None:
        """Fetch partner by ID. Returns standardized dict or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_PARTNER_SELECT_COLS} FROM {SCHEMA}.partners WHERE id = $1 LIMIT 1",
                partner_id,
            )
        return _row_to_partner_dict(row) if row else None

    async def list_all_in_tenant(self, tenant_id: str) -> list[dict]:
        """Fetch all partners whose tenant key matches tenant_id.

        Tenant key = shared_partner_id if set, else id.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_PARTNER_SELECT_COLS} FROM {SCHEMA}.partners"
            )
        results = []
        for row in rows:
            d = _row_to_partner_dict(row)
            row_tenant = d.get("sharedPartnerId") or d["id"]
            if row_tenant == tenant_id:
                results.append(d)
        return results

    async def create(self, data: dict) -> None:
        """Insert a new partner row."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.partners (
                        id, email, display_name, api_key, authorized_entity_ids,
                        status, is_admin, shared_partner_id, access_mode, invited_by,
                        roles, department, created_at, updated_at, invite_expires_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                data["id"],
                data["email"],
                data["displayName"],
                data.get("apiKey", ""),
                data.get("authorizedEntityIds", []),
                data.get("status", "invited"),
                data.get("isAdmin", False),
                data.get("sharedPartnerId"),
                data.get("accessMode", "unassigned"),
                data.get("invitedBy", ""),
                data.get("roles", []),
                data.get("department", "all"),
                data["createdAt"],
                data["updatedAt"],
                data.get("inviteExpiresAt"),
            )

    async def get_preferences(self, partner_id: str) -> dict:
        """Fetch preferences JSONB for a partner. Returns empty dict if unset."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT preferences FROM {SCHEMA}.partners WHERE id = $1 LIMIT 1",
                partner_id,
            )
        if not row or not row["preferences"]:
            return {}
        return row["preferences"]

    async def update_preferences(self, partner_id: str, patch: dict) -> dict:
        """Deep-merge patch into existing preferences JSONB. Returns updated preferences.

        Top-level keys that map to dicts are merged recursively so that e.g.
        ``{"onboarding": {"platform_type": "technical"}}`` does not overwrite
        existing ``onboarding.step1_done`` or ``onboarding.dismissed``.
        """
        import json as _json

        async with self._pool.acquire() as conn:
            # Read current preferences first, deep-merge in Python, write back.
            cur_row = await conn.fetchrow(
                f"SELECT preferences FROM {SCHEMA}.partners WHERE id = $1 LIMIT 1",
                partner_id,
            )
            existing = (cur_row["preferences"] if cur_row and cur_row["preferences"] else {})
            merged = _deep_merge_prefs(existing, patch)
            row = await conn.fetchrow(
                f"""UPDATE {SCHEMA}.partners
                    SET preferences = $2::jsonb,
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING preferences""",
                partner_id,
                _json.dumps(merged),
            )
        if not row or not row["preferences"]:
            return {}
        return row["preferences"]

    async def list_departments(self, tenant_id: str) -> list[str]:
        """Return stored departments plus any in-use partner departments."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT name FROM {SCHEMA}.partner_departments
                    WHERE tenant_id = $1
                    ORDER BY CASE WHEN name = 'all' THEN 0 ELSE 1 END, lower(name)""",
                tenant_id,
            )
            partner_rows = await conn.fetch(
                f"""SELECT department, shared_partner_id, id
                    FROM {SCHEMA}.partners"""
            )
        departments = {str(row["name"]) for row in rows if row["name"]}
        for row in partner_rows:
            row_tenant = row["shared_partner_id"] or row["id"]
            if row_tenant == tenant_id and row["department"]:
                departments.add(str(row["department"]))
        departments.add("all")
        return sorted(departments, key=lambda value: (value != "all", value.lower()))

    async def create_department(self, tenant_id: str, name: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.partner_departments (tenant_id, name)
                    VALUES ($1, $2)
                    ON CONFLICT (tenant_id, name) DO NOTHING""",
                tenant_id,
                name,
            )

    async def rename_department(self, tenant_id: str, old_name: str, new_name: str) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""DELETE FROM {SCHEMA}.partner_departments
                        WHERE tenant_id = $1 AND name = $2""",
                    tenant_id,
                    old_name,
                )
                await conn.execute(
                    f"""INSERT INTO {SCHEMA}.partner_departments (tenant_id, name)
                        VALUES ($1, $2)
                        ON CONFLICT (tenant_id, name) DO NOTHING""",
                    tenant_id,
                    new_name,
                )
                await conn.execute(
                    f"""UPDATE {SCHEMA}.partners
                        SET department = $1
                        WHERE COALESCE(shared_partner_id, id) = $2
                          AND department = $3""",
                    new_name,
                    tenant_id,
                    old_name,
                )

    async def delete_department(self, tenant_id: str, name: str, fallback_department: str = "all") -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""DELETE FROM {SCHEMA}.partner_departments
                        WHERE tenant_id = $1 AND name = $2""",
                    tenant_id,
                    name,
                )
                await conn.execute(
                    f"""UPDATE {SCHEMA}.partners
                        SET department = $1
                        WHERE COALESCE(shared_partner_id, id) = $2
                          AND department = $3""",
                    fallback_department,
                    tenant_id,
                    name,
                )

    async def update_fields(self, partner_id: str, fields: dict) -> None:
        """Update arbitrary partner fields by building a SET clause.

        Only keys present in ``fields`` are updated. ``updated_at`` is always
        refreshed to ``fields['updatedAt']`` if provided, else kept unchanged.
        """
        if not fields:
            return
        # Build parameterized SET clause
        col_map = {
            "status": "status",
            "isAdmin": "is_admin",
            "apiKey": "api_key",  # pragma: allowlist secret
            "displayName": "display_name",
            "accessMode": "access_mode",
            "roles": "roles",
            "department": "department",
            "authorizedEntityIds": "authorized_entity_ids",
            "sharedPartnerId": "shared_partner_id",
            "updatedAt": "updated_at",
            "inviteExpiresAt": "invite_expires_at",
        }
        sets = []
        params: list = []
        idx = 1
        for key, col in col_map.items():
            if key in fields:
                sets.append(f"{col} = ${idx}")
                params.append(fields[key])
                idx += 1
        if not sets:
            return
        params.append(partner_id)
        sql = f"UPDATE {SCHEMA}.partners SET {', '.join(sets)} WHERE id = ${idx}"
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *params)

    async def delete(self, partner_id: str) -> None:
        """Delete partner by ID."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Nullify tasks assigned to this partner
                await conn.execute(
                    f"UPDATE {SCHEMA}.tasks SET assignee = NULL WHERE assignee = $1",
                    partner_id,
                )
                # Delete task_comments by this partner
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.task_comments WHERE partner_id = $1",
                    partner_id,
                )
                # Delete tool_events by this partner (prevent FK constraint error)
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.tool_events WHERE partner_id = $1",
                    partner_id,
                )
                # CRM cleanup: recorded_by and owner_partner_id are NOT NULL FKs
                # without ON DELETE action, so they must be cleaned up before
                # deleting the partner to avoid FK constraint errors.
                # Delete activities recorded by this partner on other partners' deals.
                await conn.execute(
                    "DELETE FROM crm.activities WHERE recorded_by = $1",
                    partner_id,
                )
                # Delete deals owned by this partner (cascades remaining activities).
                await conn.execute(
                    "DELETE FROM crm.deals WHERE owner_partner_id = $1",
                    partner_id,
                )
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.partners WHERE id = $1",
                    partner_id,
                )

    async def get_entity_tenant(self, entity_id: str) -> dict | None:
        """Return {partner_id, shared_partner_id} for the entity's owner partner."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT e.partner_id, p.shared_partner_id
                    FROM {SCHEMA}.entities e
                    JOIN {SCHEMA}.partners p ON p.id = e.partner_id
                    WHERE e.id = $1
                    LIMIT 1""",
                entity_id,
            )
        if not row:
            return None
        return {
            "partner_id": row["partner_id"],
            "shared_partner_id": row["shared_partner_id"],
        }

    async def update_entity_visibility(
        self,
        entity_id: str,
        visibility: str,
        visible_to_roles: list[str],
        visible_to_members: list[str],
        visible_to_departments: list[str],
    ) -> None:
        """Update entity visibility fields."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""UPDATE {SCHEMA}.entities
                    SET visibility = $1,
                        visible_to_roles = $2,
                        visible_to_members = $3,
                        visible_to_departments = $4,
                        updated_at = $5
                    WHERE id = $6""",
                visibility,
                visible_to_roles,
                visible_to_members,
                visible_to_departments,
                _now(),
                entity_id,
            )
