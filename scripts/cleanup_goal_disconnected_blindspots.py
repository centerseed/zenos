#!/usr/bin/env python3
"""Remove stale 'goal_disconnected' blindspots from the database.

Background
----------
A bug in analyze_graph_topology() generated goal_disconnected blindspots for
every MODULE entity even when no GOAL entities existed in the ontology.  The
bug has been fixed (early-return when goal_ids is empty), but the already-
persisted blindspots need to be cleaned up.

Usage
-----
    DATABASE_URL=postgresql://user:pass@host/db \  # pragma: allowlist secret
        python scripts/cleanup_goal_disconnected_blindspots.py [--dry-run | --live]
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
PATTERN = "%無法追溯到任何目標節點%"


async def run(dry_run: bool) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(dsn)
    try:
        # Find matching blindspots
        rows = await conn.fetch(
            f"SELECT id, description FROM {SCHEMA}.blindspots WHERE description LIKE $1",
            PATTERN,
        )
        print(f"Found {len(rows)} goal_disconnected blindspot(s).")
        for r in rows:
            print(f"  [{r['id']}] {r['description']}")

        if not rows:
            print("Nothing to clean up.")
            return

        if dry_run:
            print("\n[DRY RUN] No changes made. Use --live to delete.")
            return

        ids = [r["id"] for r in rows]
        async with conn.transaction():
            # Delete join table entries first
            deleted_links = await conn.execute(
                f"DELETE FROM {SCHEMA}.blindspot_entities WHERE blindspot_id = ANY($1::text[])",
                ids,
            )
            # Delete blindspots
            deleted_bs = await conn.execute(
                f"DELETE FROM {SCHEMA}.blindspots WHERE id = ANY($1::text[])",
                ids,
            )
            print(f"\nDeleted {deleted_bs} blindspot(s), {deleted_links} link(s).")
    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    group.add_argument("--live", action="store_true", help="Actually delete")
    args = parser.parse_args()
    asyncio.run(run(dry_run=not args.live))


if __name__ == "__main__":
    main()
