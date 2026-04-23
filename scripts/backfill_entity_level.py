#!/usr/bin/env python3
"""Backfill entity.level for rows where level IS NULL.

Background
----------
ADR-047 makes ``level == 1 AND parent_id IS NULL`` the sole L1 gating condition
and removes the ``level is None`` fallback from ``is_collaboration_root_entity``.
Before deploying that strict check (S02-code), every entity in production must
have an explicit level.  This script is the one-off data remediation tool.

Modes
-----
dry-run (default)
    Read-only scan of ``zenos.entities WHERE level IS NULL``.  Prints a JSON
    report to stdout (or --output path) showing what *would* be updated.
    No data is written.

apply
    Requires ``--snapshot-path``.  Writes a JSONL rollback snapshot, then
    executes individual UPDATE statements for all resolvable rows.
    Rows whose type is not in DEFAULT_TYPE_LEVELS are left untouched and
    listed under ``skipped_unresolvable`` in the report.

Usage
-----
    # Step 1: review impact
    python scripts/backfill_entity_level.py --dry-run [--output report.json]

    # Step 2 (after Architect review): commit
    python scripts/backfill_entity_level.py --apply --snapshot-path backfill_snapshot.jsonl [--output report.json]

    # Rollback (if needed)
    # The snapshot contains {"id": "<uuid>", "level": null} per line.
    # Re-run a custom script (or psql) to SET level = NULL for those ids.

Environment
-----------
DATABASE_URL   PostgreSQL DSN (required at runtime, not at import time)

"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed.  Run: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

# Absolute path so tests can do sys.path.insert and import this module.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from zenos.domain.knowledge.entity_levels import DEFAULT_TYPE_LEVELS  # noqa: E402

SCHEMA = "zenos"


# ---------------------------------------------------------------------------
# Core logic — pure functions so tests can call them without DB
# ---------------------------------------------------------------------------

def classify_rows(
    rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split rows into (resolvable, unresolvable) based on DEFAULT_TYPE_LEVELS.

    Args:
        rows: Each row must have keys ``id``, ``name``, ``type``, ``level``,
              ``parent_id``.

    Returns:
        A 2-tuple ``(resolvable, unresolvable)``.
        - ``resolvable`` items have a ``new_level`` key added.
        - ``unresolvable`` items carry ``id``, ``name``, ``type`` only.
    """
    resolvable: list[dict] = []
    unresolvable: list[dict] = []

    for row in rows:
        entity_type = row["type"]
        inferred = DEFAULT_TYPE_LEVELS.get(entity_type)
        if inferred is not None:
            resolvable.append({
                "id": row["id"],
                "type": entity_type,
                "new_level": inferred,
            })
        else:
            unresolvable.append({
                "id": row["id"],
                "name": row["name"],
                "type": entity_type,
            })

    return resolvable, unresolvable


def build_by_type(rows: list[dict]) -> dict[str, int]:
    """Count rows grouped by entity type."""
    counts: dict[str, int] = {}
    for row in rows:
        t = row["type"]
        counts[t] = counts.get(t, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def fetch_null_level_rows(conn: asyncpg.Connection) -> list[dict]:
    """SELECT rows where level IS NULL."""
    sql = f"""
        SELECT id, name, type, level, parent_id
        FROM {SCHEMA}.entities
        WHERE level IS NULL
    """
    records = await conn.fetch(sql)
    return [dict(r) for r in records]


async def apply_updates(
    conn: asyncpg.Connection,
    resolvable: list[dict],
    snapshot_path: Path,
) -> int:
    """Write snapshot then UPDATE each resolvable row.

    Args:
        conn: Open asyncpg connection.
        resolvable: List of ``{"id": ..., "type": ..., "new_level": ...}`` dicts.
        snapshot_path: File path to write JSONL rollback snapshot.

    Returns:
        Number of rows actually updated.
    """
    # Write snapshot *before* any mutation.
    with open(snapshot_path, "w", encoding="utf-8") as fh:
        for row in resolvable:
            fh.write(json.dumps({"id": row["id"], "level": None}) + "\n")
    logger.info("Snapshot written to %s (%d rows)", snapshot_path, len(resolvable))

    updated = 0
    for row in resolvable:
        result = await conn.execute(
            f"UPDATE {SCHEMA}.entities SET level = $1 WHERE id = $2",
            row["new_level"],
            row["id"],
        )
        # asyncpg returns a tag like "UPDATE 1"
        n = _parse_command_tag_count(result)
        updated += n
        logger.debug("Updated entity %s → level=%d (tag=%s)", row["id"], row["new_level"], result)

    return updated


def _parse_command_tag_count(tag: str) -> int:
    try:
        return int(tag.split()[-1])
    except (IndexError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def build_dry_run_report(
    rows: list[dict],
    resolvable: list[dict],
    unresolvable: list[dict],
) -> dict:
    return {
        "mode": "dry-run",
        "total": len(rows),
        "by_type": build_by_type(rows),
        "unresolvable": unresolvable,
        "would_update": resolvable,
        "snapshot_path": None,
    }


def build_apply_report(
    rows: list[dict],
    resolvable: list[dict],
    unresolvable: list[dict],
    updated: int,
    snapshot_path: str,
) -> dict:
    return {
        "mode": "apply",
        "total": len(rows),
        "by_type": build_by_type(rows),
        "updated": updated,
        "skipped_unresolvable": unresolvable,
        "snapshot_path": str(snapshot_path),
    }


def emit_report(report: dict, output_path: str | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        print(f"Report written to {output_path}", file=sys.stderr)
    else:
        print(text)


# ---------------------------------------------------------------------------
# Main async entrypoint
# ---------------------------------------------------------------------------

async def run_dry_run(conn: asyncpg.Connection, output_path: str | None) -> None:
    rows = await fetch_null_level_rows(conn)
    resolvable, unresolvable = classify_rows(rows)

    print(
        f"\n[DRY RUN] Found {len(rows)} entities with level IS NULL. "
        f"Would update {len(resolvable)}, skipping {len(unresolvable)} unresolvable.",
        file=sys.stderr,
    )
    if unresolvable:
        print(
            f"WARNING: {len(unresolvable)} entity/entities have unresolvable type(s) "
            "and will NOT be updated.  Inspect 'unresolvable' in the report.",
            file=sys.stderr,
        )

    report = build_dry_run_report(rows, resolvable, unresolvable)
    emit_report(report, output_path)


async def run_apply(
    conn: asyncpg.Connection,
    snapshot_path: str,
    output_path: str | None,
) -> int:
    """Apply backfill updates.

    Returns the process exit code:
      0 — all NULL levels resolved, GATE A exit criteria satisfied
      3 — partial success: some rows had unresolvable types and remain NULL;
          GATE A exit criteria NOT satisfied; operator must manually resolve
          before deploying strict-level code.
    """
    rows = await fetch_null_level_rows(conn)
    resolvable, unresolvable = classify_rows(rows)

    print(
        f"\n[APPLY] About to update {len(resolvable)} rows. "
        f"Skipping {len(unresolvable)} unresolvable.  Snapshot → {snapshot_path}",
        file=sys.stderr,
    )
    if unresolvable:
        print(
            f"WARNING: {len(unresolvable)} entity/entities cannot be resolved and will be skipped. "
            "Manual review required.",
            file=sys.stderr,
        )

    snap = Path(snapshot_path)
    updated = await apply_updates(conn, resolvable, snap)

    report = build_apply_report(rows, resolvable, unresolvable, updated, snapshot_path)
    emit_report(report, output_path)

    if unresolvable:
        print(
            f"\n[APPLY] INCOMPLETE: Updated {updated} rows but {len(unresolvable)} entity/entities "
            "still have level IS NULL (unresolvable types).  GATE A exit criteria NOT satisfied — "
            "strict-level code MUST NOT be deployed until these are manually resolved.  "
            f"Snapshot at {snapshot_path}.",
            file=sys.stderr,
        )
        return 3

    print(
        f"\n[APPLY] Done. Updated {updated} rows. All NULL levels resolved. "
        f"Snapshot at {snapshot_path}.",
        file=sys.stderr,
    )
    return 0


async def main(args: argparse.Namespace) -> int:
    """Returns process exit code.

    0 — success
    1 — missing DATABASE_URL
    3 — apply completed but unresolvable rows remain (GATE A not satisfied)
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "ERROR: DATABASE_URL environment variable is not set.\n"
            "Example: DATABASE_URL=postgresql://user:pass@host/db",  # pragma: allowlist secret
            file=sys.stderr,
        )
        return 1

    conn: asyncpg.Connection = await asyncpg.connect(database_url)
    try:
        if args.dry_run:
            await run_dry_run(conn, args.output)
            return 0
        else:
            # apply mode — snapshot_path is validated before we get here
            return await run_apply(conn, args.snapshot_path, args.output)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill entity.level for rows where level IS NULL.  "
            "Run --dry-run first, then --apply --snapshot-path <path>."
        )
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report without writing any data.",
    )
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="Write snapshot and apply UPDATEs.  Requires --snapshot-path.",
    )

    parser.add_argument(
        "--snapshot-path",
        metavar="PATH",
        help="JSONL file path to write rollback snapshot (required with --apply).",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write JSON report to this file instead of stdout.",
    )

    ns = parser.parse_args(argv)

    if ns.apply and not ns.snapshot_path:
        parser.error(
            "--snapshot-path is required when using --apply.  "
            "Example: --apply --snapshot-path backfill_snapshot.jsonl"
        )

    return ns


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    sys.exit(asyncio.run(main(args)))
