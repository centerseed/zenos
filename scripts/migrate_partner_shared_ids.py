#!/usr/bin/env python3
"""Admin script: set shared_partner_id on all non-admin partners.

Background
----------
ZenOS uses a single canonical partition key per tenant: the admin partner's id.
Non-admin partners (MCP API keys, invited members) must have their
``shared_partner_id`` set to the admin partner's id so that all read/write
operations route to the same data partition.

This script finds all non-admin partners whose ``shared_partner_id`` is NULL
and sets it to the admin partner's id.

The partners table itself is the only table modified.

Usage
-----
    DATABASE_URL=postgresql://user:pass@host/db \\  # pragma: allowlist secret
        python scripts/migrate_partner_shared_ids.py [--dry-run | --live]

Flags
-----
--dry-run   (default) Print what would change without writing anything.
--live      Execute the UPDATE in a transaction.

Notes
-----
- All UPDATEs are wrapped in a single transaction; any failure triggers a
  full rollback.
- Requires asyncpg.  DATABASE_URL must be a valid PostgreSQL DSN.
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


async def fetch_admin_partner(conn: asyncpg.Connection) -> asyncpg.Record:
    """Return the single admin partner record (id, email).

    Raises RuntimeError if none or more than one admin partner is found.
    """
    rows = await conn.fetch(
        f"SELECT id, email FROM {SCHEMA}.partners WHERE is_admin = true"
    )
    if not rows:
        raise RuntimeError("No admin partner found (is_admin = true). Cannot proceed.")
    if len(rows) > 1:
        ids = [r["id"] for r in rows]
        raise RuntimeError(f"Multiple admin partners found: {ids}. Expected exactly one.")
    return rows[0]


async def fetch_partners_missing_shared_id(
    conn: asyncpg.Connection,
    admin_id: str,
) -> list[asyncpg.Record]:
    """Return all non-admin partners with shared_partner_id IS NULL."""
    return await conn.fetch(
        f"""SELECT id, email
            FROM {SCHEMA}.partners
            WHERE is_admin = false
              AND shared_partner_id IS NULL
              AND id <> $1""",
        admin_id,
    )


async def run_migration(
    conn: asyncpg.Connection,
    dry_run: bool,
) -> None:
    """Execute (or simulate) the shared_partner_id migration.

    In dry-run mode no data is modified; the function prints what would change.
    In live mode all UPDATEs run inside a single transaction.
    """
    admin = await fetch_admin_partner(conn)
    admin_id: str = admin["id"]

    print(f"\nAdmin partner    : {admin_id}  ({admin['email']})")

    affected = await fetch_partners_missing_shared_id(conn, admin_id)

    if not affected:
        print("Nothing to do — all non-admin partners already have shared_partner_id set.")
        return

    print(f"\nPartners to update ({len(affected)}):")
    for row in affected:
        print(f"  {row['id']}  ({row['email']})")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
        _print_summary(affected, dry_run=True)
        return

    # Live execution — single transaction.
    partner_ids = [row["id"] for row in affected]
    async with conn.transaction():
        result = await conn.execute(
            f"""UPDATE {SCHEMA}.partners
                SET shared_partner_id = $1, updated_at = now()
                WHERE id = ANY($2::text[])""",
            admin_id,
            partner_ids,
        )
        count = _parse_command_tag_count(result)
        logger.info("Updated %d partner rows with shared_partner_id = %s", count, admin_id)

    _print_summary(affected, dry_run=False)


def _print_summary(affected: list[asyncpg.Record], *, dry_run: bool) -> None:
    mode = "[DRY RUN] " if dry_run else ""
    print(f"\n=== {mode}Migration Summary ===")
    print(f"  Partners updated : {len(affected)}")
    for row in affected:
        print(f"    - {row['email']}  (id: {row['id']})")


def _parse_command_tag_count(tag: str) -> int:
    """Parse the row count from an asyncpg command tag string (e.g. 'UPDATE 42')."""
    try:
        return int(tag.split()[-1])
    except (IndexError, ValueError):
        return 0


async def main(dry_run: bool) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL environment variable is not set.\n"
            "Example: DATABASE_URL=postgresql://user:pass@host/db",  # pragma: allowlist secret
            file=sys.stderr,
        )
        sys.exit(1)

    conn: asyncpg.Connection = await asyncpg.connect(database_url)
    try:
        await run_migration(conn, dry_run=dry_run)
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set shared_partner_id on non-admin partners missing it."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(default) Print affected partners without modifying any data.",
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
    # --live overrides the default dry-run
    dry_run = not args.live
    asyncio.run(main(dry_run=dry_run))
