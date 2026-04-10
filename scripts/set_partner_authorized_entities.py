#!/usr/bin/env python3
"""Set a partner's authorized_entity_ids and access_mode."""

from __future__ import annotations

import asyncio
import os
import sys

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed.", file=sys.stderr)
    sys.exit(1)

SCHEMA = "zenos"


async def main(email: str, entity_ids: list[str]) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(database_url)
    try:
        row = await conn.fetchrow(
            f"""UPDATE {SCHEMA}.partners
                SET authorized_entity_ids = $2::text[],
                    access_mode = CASE WHEN cardinality($2::text[]) > 0 THEN 'scoped' ELSE 'unassigned' END,
                    updated_at = now()
                WHERE lower(email) = lower($1)
                RETURNING id, email, access_mode, authorized_entity_ids""",
            email,
            entity_ids,
        )
        if not row:
            print(f"NOT_FOUND: {email}")
            return
        print(
            f"id={row['id']} email={row['email']} "
            f"access_mode={row['access_mode']} authorized_entity_ids={list(row['authorized_entity_ids'] or [])}"
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: set_partner_authorized_entities.py <email> <entity_id> [<entity_id> ...]", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
