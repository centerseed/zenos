#!/usr/bin/env python3
"""Clear stale shared_partner_id values on admin partners.

Background
----------
After the workspace/permission model changes, an admin partner must represent
their own home workspace. If an admin row still carries a non-null
``shared_partner_id`` from an older shared-workspace membership, the Dashboard
misclassifies that partner as a shared-workspace user and hides owner-only
surfaces such as CRM, Team, and Setup.

This script finds all rows where:
  - is_admin = true
  - shared_partner_id IS NOT NULL

and clears ``shared_partner_id`` back to NULL.

Usage
-----
    DATABASE_URL=postgresql://user:pass@host/db \\  # pragma: allowlist secret
        python scripts/fix_admin_shared_partner_ids.py [--dry-run | --live]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logger = logging.getLogger(__name__)

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

SCHEMA = "zenos"


async def fetch_affected_admins(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""SELECT id, email, shared_partner_id
            FROM {SCHEMA}.partners
            WHERE is_admin = true
              AND shared_partner_id IS NOT NULL
            ORDER BY email"""
    )


def _parse_command_tag_count(tag: str) -> int:
    try:
        return int(tag.split()[-1])
    except (IndexError, ValueError):
        return 0


async def run_fix(conn: asyncpg.Connection, *, dry_run: bool) -> None:
    affected = await fetch_affected_admins(conn)

    if not affected:
        print("Nothing to do — all admin partners already have shared_partner_id = NULL.")
        return

    print(f"Admin partners to fix ({len(affected)}):")
    for row in affected:
        print(f"  {row['id']}  ({row['email']}) shared_partner_id={row['shared_partner_id']}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    partner_ids = [row["id"] for row in affected]
    async with conn.transaction():
        result = await conn.execute(
            f"""UPDATE {SCHEMA}.partners
                SET shared_partner_id = NULL,
                    updated_at = now()
                WHERE id = ANY($1::text[])""",
            partner_ids,
        )
    print(f"\nUpdated {_parse_command_tag_count(result)} admin partners.")


async def main(*, dry_run: bool) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL environment variable is not set.\n"
            "Example: DATABASE_URL=postgresql://user:pass@host/db",  # pragma: allowlist secret
            file=sys.stderr,
        )
        sys.exit(1)

    conn = await asyncpg.connect(database_url)
    try:
        await run_fix(conn, dry_run=dry_run)
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear stale shared_partner_id values on admin partners."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(default) Print affected rows without modifying data.",
    )
    group.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Execute the UPDATE. Without this flag, dry-run is the default.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    asyncio.run(main(dry_run=not args.live))
