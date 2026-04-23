#!/usr/bin/env python3
"""Run SQL migrations in order and record applied versions."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import asyncpg
from asyncpg import exceptions as pg_exceptions


KNOWN_CHECKSUM_ALIASES: dict[str, set[str]] = {
    # 2026-04-22: migration was applied in production before a follow-up commit
    # added the deterministic placeholder-product fallback. Treat the original
    # applied checksum as equivalent so later migrations are not blocked.
    "20260422_0002_task_product_id_backfill": {
        "32d6052aeea27b96e4053d5bab32c3fa6b2adc6fdbb21b31e0660fb05a89d118",  # pragma: allowlist secret
    },
}


@dataclass(frozen=True)
class Migration:
    version: str
    filename: str
    path: Path
    checksum: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZenOS SQL migration runner")
    parser.add_argument(
        "--migrations-dir",
        default=str(Path(__file__).resolve().parent.parent / "migrations"),
        help="Directory containing .sql migration files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without applying",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show applied/pending migration status and exit",
    )
    return parser.parse_args()


def load_migrations(migrations_dir: Path) -> list[Migration]:
    files = sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())
    migrations: list[Migration] = []
    for path in files:
        content = path.read_bytes()
        migrations.append(
            Migration(
                version=path.stem,
                filename=path.name,
                path=path,
                checksum=hashlib.sha256(content).hexdigest(),
            )
        )
    return migrations


def checksum_matches_applied(version: str, applied_checksum: str, current_checksum: str) -> bool:
    if applied_checksum == current_checksum:
        return True
    aliases = KNOWN_CHECKSUM_ALIASES.get(version, set())
    return applied_checksum in aliases


async def ensure_migration_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zenos.schema_migrations (
          version text PRIMARY KEY,
          filename text NOT NULL,
          checksum text NOT NULL,
          applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


async def fetch_applied(conn: asyncpg.Connection) -> dict[str, asyncpg.Record]:
    rows = await conn.fetch(
        """
        SELECT version, filename, checksum, applied_at
        FROM zenos.schema_migrations
        ORDER BY version
        """
    )
    return {r["version"]: r for r in rows}


async def apply_migration(conn: asyncpg.Connection, migration: Migration) -> None:
    sql = migration.path.read_text(encoding="utf-8")
    async with conn.transaction():
        await conn.execute("SET LOCAL search_path TO zenos, public")
        await conn.execute(sql)
        await conn.execute(
            """
            INSERT INTO zenos.schema_migrations(version, filename, checksum)
            VALUES($1, $2, $3)
            """,
            migration.version,
            migration.filename,
            migration.checksum,
        )


async def mark_migration_applied(conn: asyncpg.Connection, migration: Migration) -> None:
    await conn.execute(
        """
        INSERT INTO zenos.schema_migrations(version, filename, checksum)
        VALUES($1, $2, $3)
        ON CONFLICT (version) DO NOTHING
        """,
        migration.version,
        migration.filename,
        migration.checksum,
    )


async def main() -> int:
    args = parse_args()
    migrations_dir = Path(args.migrations_dir).resolve()
    if not migrations_dir.exists():
        print(f"ERROR: migrations dir not found: {migrations_dir}")
        return 1

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is required")
        return 1

    migrations = load_migrations(migrations_dir)
    if not migrations:
        print(f"No migration files found in {migrations_dir}")
        return 0

    conn = await asyncpg.connect(database_url)
    try:
        await ensure_migration_table(conn)
        applied = await fetch_applied(conn)

        pending: list[Migration] = []
        for migration in migrations:
            if migration.version in applied:
                old_checksum = applied[migration.version]["checksum"]
                if not checksum_matches_applied(migration.version, old_checksum, migration.checksum):
                    print(
                        "ERROR: checksum mismatch for applied migration "
                        f"{migration.filename}"
                    )
                    return 2
            else:
                pending.append(migration)

        print(f"Applied: {len(applied)}")
        print(f"Pending: {len(pending)}")

        if args.status:
            for migration in migrations:
                state = "APPLIED" if migration.version in applied else "PENDING"
                print(f"{state:8} {migration.filename}")
            return 0

        if args.dry_run:
            for migration in pending:
                print(f"DRY RUN apply: {migration.filename}")
            return 0

        for migration in pending:
            print(f"Applying: {migration.filename}")
            try:
                await apply_migration(conn, migration)
                print(f"Applied: {migration.filename}")
            except (
                pg_exceptions.DuplicateObjectError,
                pg_exceptions.DuplicateTableError,
                pg_exceptions.DuplicateColumnError,
            ) as e:
                # Existing environments may have changes applied manually without
                # schema_migrations records. Mark these as applied to bootstrap tracking.
                print(f"Already present, marking applied: {migration.filename} ({e})")
                await mark_migration_applied(conn, migration)

        print("Done")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
