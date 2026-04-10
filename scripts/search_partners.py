#!/usr/bin/env python3
"""Search partner records by email/display name substring."""

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


async def main(term: str) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(database_url)
    try:
        rows = await conn.fetch(
            f"""SELECT id, email, display_name, status, is_admin, shared_partner_id, access_mode
                FROM {SCHEMA}.partners
                WHERE lower(email) LIKE lower($1)
                   OR lower(coalesce(display_name, '')) LIKE lower($1)
                ORDER BY email""",
            f"%{term}%",
        )
        if not rows:
            print(f"NO_MATCH: {term}")
            return
        for row in rows:
            print(
                f"id={row['id']} email={row['email']} display_name={row['display_name']} "
                f"status={row['status']} is_admin={row['is_admin']} "
                f"shared_partner_id={row['shared_partner_id']} access_mode={row['access_mode']}"
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: search_partners.py <term>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
