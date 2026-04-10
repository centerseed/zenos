#!/usr/bin/env python3
"""Inspect partner access/workspace fields for a given email."""

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


async def main(email: str) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(database_url)
    try:
        row = await conn.fetchrow(
            f"""SELECT id, email, display_name, status, is_admin, shared_partner_id,
                       access_mode, authorized_entity_ids, roles, department
                FROM {SCHEMA}.partners
                WHERE lower(email) = lower($1)
                LIMIT 1""",
            email,
        )
        if not row:
            print(f"NOT_FOUND: {email}")
            return
        for key in row.keys():
            print(f"{key}={row[key]}")
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: inspect_partner_access.py <email>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
