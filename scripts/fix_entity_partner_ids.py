#!/usr/bin/env python3
"""Admin script: migrate all non-admin entities to the admin partner_id.

Background
----------
ZenOS is a single-tenant system, but entities have been written under multiple
partner_ids (e.g. via different MCP API keys).  The Dashboard only queries the
admin partner's data, so non-admin entities are invisible.

This script finds the admin partner (is_admin = true), then reassigns every
row that belongs to a different partner_id to the admin partner_id.

Tables updated (all partner_id columns):
  audit_events, entities, governance_health_cache, relationships,
  documents, document_entities, protocols, blindspots, blindspot_entities,
  tasks, task_entities, task_blockers, tool_events, work_journal

The partners table itself is NOT modified.

Usage
-----
    DATABASE_URL=postgresql://user:pass@host/db python scripts/fix_entity_partner_ids.py  # pragma: allowlist secret [--dry-run]

Flags
-----
--dry-run   Print what would change without writing anything.

Notes
-----
- All UPDATEs are wrapped in a single transaction; any failure triggers a full
  rollback.
- The entities table has composite self-referencing FKs on (partner_id, parent_id)
  and (partner_id, project_id).  PostgreSQL evaluates non-deferred immediate
  constraints at statement-end (not row-by-row), so the bulk UPDATE is safe:
  once the statement completes all entities share the same admin partner_id,
  satisfying all cross-entity FK references.
- Requires asyncpg.  DATABASE_URL must be a valid PostgreSQL DSN.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Run: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

SCHEMA = "zenos"

# Tables whose partner_id column references partners(id) directly.
# Order matters for FK satisfaction: join/leaf tables before their parents
# is fine here because we defer all constraints.
PARTNER_ID_TABLES: list[str] = [
    "audit_events",
    "entities",
    "governance_health_cache",
    "relationships",
    "documents",
    "document_entities",
    "protocols",
    "blindspots",
    "blindspot_entities",
    "tasks",
    "task_entities",
    "task_blockers",
    "tool_events",
    "work_journal",
]


@dataclass
class UpdateSummary:
    """Track how many rows were updated per table."""
    counts: dict[str, int] = field(default_factory=dict)

    def record(self, table: str, count: int) -> None:
        self.counts[table] = self.counts.get(table, 0) + count

    def print_report(self, dry_run: bool) -> None:
        mode = "[DRY RUN] " if dry_run else ""
        print(f"\n=== {mode}Update Summary ===")
        total = 0
        for table in PARTNER_ID_TABLES:
            count = self.counts.get(table, 0)
            total += count
            print(f"  {table:<25} : {count} rows")
        print(f"  {'TOTAL':<25} : {total} rows")


async def fetch_admin_partner_id(conn: asyncpg.Connection) -> str:
    """Return the id of the single admin partner (is_admin = true).

    Raises RuntimeError if none or more than one admin partner is found.
    """
    rows = await conn.fetch(f"SELECT id FROM {SCHEMA}.partners WHERE is_admin = true")
    if not rows:
        raise RuntimeError("No admin partner found (is_admin = true). Cannot proceed.")
    if len(rows) > 1:
        ids = [r["id"] for r in rows]
        raise RuntimeError(f"Multiple admin partners found: {ids}. Expected exactly one.")
    return rows[0]["id"]


async def fetch_affected_counts(
    conn: asyncpg.Connection,
    admin_id: str,
) -> dict[str, int]:
    """Return the number of rows in each table that have a non-admin partner_id."""
    counts: dict[str, int] = {}
    for table in PARTNER_ID_TABLES:
        row = await conn.fetchrow(
            f"SELECT COUNT(*) AS n FROM {SCHEMA}.{table} WHERE partner_id <> $1",
            admin_id,
        )
        counts[table] = row["n"]
    return counts


async def run_fix(
    conn: asyncpg.Connection,
    admin_id: str,
    dry_run: bool,
) -> UpdateSummary:
    """Execute (or simulate) the partner_id migration.

    In dry-run mode no data is modified; the function queries affected row
    counts and prints them, then returns a summary.

    In live mode all UPDATEs run inside a single transaction.  Constraints are
    deferred so the composite self-referencing FKs on the entities table do not
    block the bulk UPDATE.
    """
    summary = UpdateSummary()

    affected = await fetch_affected_counts(conn, admin_id)
    total_affected = sum(affected.values())

    print(f"\nAdmin partner_id : {admin_id}")
    print(f"Total rows to migrate : {total_affected}")

    if total_affected == 0:
        print("Nothing to do — all rows already use the admin partner_id.")
        for table, count in affected.items():
            summary.record(table, count)
        return summary

    print("\nAffected rows per table:")
    for table in PARTNER_ID_TABLES:
        n = affected.get(table, 0)
        print(f"  {table:<25} : {n}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
        for table, count in affected.items():
            summary.record(table, count)
        return summary

    # Live execution — single transaction.
    # Cross-table FKs (e.g. relationships → entities) are IMMEDIATE, so updating
    # entities first causes a FK violation from the still-old relationships rows.
    # Fix: drop inter-entity FK constraints within the transaction, update all
    # tables, then re-add the constraints (which validates the final state).
    fk_constraints = [
        # → entities
        ("relationships",      "fk_relationships_source",
         "FOREIGN KEY (partner_id, source_entity_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE CASCADE"),
        ("relationships",      "fk_relationships_target",
         "FOREIGN KEY (partner_id, target_entity_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE CASCADE"),
        ("document_entities",  "fk_document_entities_entity",
         "FOREIGN KEY (partner_id, entity_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE CASCADE"),
        ("protocols",          "fk_protocols_entity",
         "FOREIGN KEY (partner_id, entity_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE CASCADE"),
        ("blindspot_entities", "fk_blindspot_entities_entity",
         "FOREIGN KEY (partner_id, entity_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE CASCADE"),
        ("tasks",              "fk_tasks_assignee_role",
         "FOREIGN KEY (partner_id, assignee_role_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE SET NULL"),
        ("tasks",              "fk_tasks_project",
         "FOREIGN KEY (partner_id, project_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE SET NULL"),
        ("task_entities",      "fk_task_entities_entity",
         "FOREIGN KEY (partner_id, entity_id) REFERENCES {schema}.entities(partner_id, id) ON DELETE CASCADE"),
        # → documents
        ("document_entities",  "fk_document_entities_document",
         "FOREIGN KEY (partner_id, document_id) REFERENCES {schema}.documents(partner_id, id) ON DELETE CASCADE"),
        # → protocols
        ("tasks",              "fk_tasks_linked_protocol",
         "FOREIGN KEY (partner_id, linked_protocol) REFERENCES {schema}.protocols(partner_id, id) ON DELETE SET NULL"),
        # → blindspots
        ("blindspot_entities", "fk_blindspot_entities_blindspot",
         "FOREIGN KEY (partner_id, blindspot_id) REFERENCES {schema}.blindspots(partner_id, id) ON DELETE CASCADE"),
        ("tasks",              "fk_tasks_linked_blindspot",
         "FOREIGN KEY (partner_id, linked_blindspot) REFERENCES {schema}.blindspots(partner_id, id) ON DELETE SET NULL"),
        # → tasks
        ("task_blockers",      "fk_task_blockers_task",
         "FOREIGN KEY (partner_id, task_id) REFERENCES {schema}.tasks(partner_id, id) ON DELETE CASCADE"),
        ("task_blockers",      "fk_task_blockers_blocker",
         "FOREIGN KEY (partner_id, blocker_task_id) REFERENCES {schema}.tasks(partner_id, id) ON DELETE CASCADE"),
        ("task_entities",      "fk_task_entities_task",
         "FOREIGN KEY (partner_id, task_id) REFERENCES {schema}.tasks(partner_id, id) ON DELETE CASCADE"),
    ]

    async with conn.transaction():
        # Step 1: drop cross-entity FKs to unblock the bulk UPDATE
        for table, constraint, _ in fk_constraints:
            await conn.execute(
                f"ALTER TABLE {SCHEMA}.{table} DROP CONSTRAINT IF EXISTS {constraint}"
            )

        # Step 2: migrate all tables
        for table in PARTNER_ID_TABLES:
            if table == "governance_health_cache":
                # Cache rows are recomputable and keyed only by partner_id.
                # If the admin row already exists, rewriting orphan rows to the
                # admin id would violate the PK. Keep the admin cache row and
                # drop stale non-admin cache rows instead.
                result = await conn.execute(
                    f"DELETE FROM {SCHEMA}.{table} WHERE partner_id <> $1",
                    admin_id,
                )
            else:
                result = await conn.execute(
                    f"UPDATE {SCHEMA}.{table} SET partner_id = $1 WHERE partner_id <> $1",
                    admin_id,
                )
            count = _parse_command_tag_count(result)
            summary.record(table, count)
            logger.info("Updated %d rows in %s", count, table)

        # Step 3: re-add FK constraints (validates final data state)
        for table, constraint, fk_def in fk_constraints:
            await conn.execute(
                f"ALTER TABLE {SCHEMA}.{table} ADD CONSTRAINT {constraint} "
                + fk_def.format(schema=SCHEMA)
            )

    return summary


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
        admin_id = await fetch_admin_partner_id(conn)
        summary = await run_fix(conn, admin_id, dry_run=dry_run)
        summary.print_report(dry_run=dry_run)
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate non-admin entity partner_ids to the admin partner_id."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print affected row counts without modifying any data.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    asyncio.run(main(dry_run=args.dry_run))
