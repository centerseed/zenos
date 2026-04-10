#!/usr/bin/env python3
"""List product entities for a tenant partner."""

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


async def main(partner_id: str) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(database_url)
    try:
        rows = await conn.fetch(
            f"""SELECT id, name, visibility, parent_id
                FROM {SCHEMA}.entities
                WHERE partner_id = $1
                  AND type = 'product'
                ORDER BY lower(name)""",
            partner_id,
        )
        for row in rows:
            print(f"id={row['id']} name={row['name']} visibility={row['visibility']} parent_id={row['parent_id']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: list_product_entities.py <partner_id>", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1]))
