#!/usr/bin/env python3
"""Verify Wave 9 legacy action tables stayed read-only or were removed.

Read-only check:
- Count legacy task/plan/task_entities inserts or updates at/after --since.
- Exit non-zero if any legacy shadow table changed after the cutover timestamp.
- After Phase F cleanup, missing legacy tables are treated as a successful final state.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

import asyncpg


DEFAULT_CUTOVER_SINCE = "2026-04-24T04:03:34Z"


def _database_url() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    proxy_port = os.environ.get("DB_PROXY_PORT")
    if proxy_port:
        database_url = re.sub(
            r"@(localhost|127\.0\.0\.1)(:\d+)?/",
            f"@127.0.0.1:{proxy_port}/",
            database_url,
            count=1,
        )
    return database_url


def _parse_since(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    cutoff = datetime.fromisoformat(normalized)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return cutoff


async def _counts(
    conn: asyncpg.Connection,
    *,
    since: datetime,
    partner_id: str | None,
) -> dict[str, Any]:
    partner_filter = "AND partner_id = $2" if partner_id else ""
    params: list[Any] = [since]
    if partner_id:
        params.append(partner_id)

    tables = {
        "tasks": bool((await conn.fetchrow("SELECT to_regclass('zenos.tasks') IS NOT NULL AS exists"))["exists"]),
        "plans": bool((await conn.fetchrow("SELECT to_regclass('zenos.plans') IS NOT NULL AS exists"))["exists"]),
        "task_entities": bool((await conn.fetchrow("SELECT to_regclass('zenos.task_entities') IS NOT NULL AS exists"))["exists"]),
    }
    if not any(tables.values()):
        return {
            "legacy_tasks_created": 0,
            "legacy_tasks_updated": 0,
            "legacy_plans_created": 0,
            "legacy_plans_updated": 0,
            "legacy_task_entities_created": 0,
            "entities_base_created": 0,
            "entities_base_updated": 0,
            "legacy_tables_present": tables,
            "phase_f_cleanup_complete": True,
        }

    tasks_created_sql = (
        f"(SELECT COUNT(*) FROM zenos.tasks WHERE created_at >= $1 {partner_filter})"
        if tables["tasks"]
        else "0"
    )
    tasks_updated_sql = (
        f"(SELECT COUNT(*) FROM zenos.tasks WHERE updated_at >= $1 {partner_filter})"
        if tables["tasks"]
        else "0"
    )
    plans_created_sql = (
        f"(SELECT COUNT(*) FROM zenos.plans WHERE created_at >= $1 {partner_filter})"
        if tables["plans"]
        else "0"
    )
    plans_updated_sql = (
        f"(SELECT COUNT(*) FROM zenos.plans WHERE updated_at >= $1 {partner_filter})"
        if tables["plans"]
        else "0"
    )
    task_entities_created_sql = (
        f"(SELECT COUNT(*) FROM zenos.task_entities WHERE created_at >= $1 {partner_filter})"
        if tables["task_entities"]
        else "0"
    )

    row = await conn.fetchrow(
        f"""
        SELECT
          {tasks_created_sql} AS legacy_tasks_created,
          {tasks_updated_sql} AS legacy_tasks_updated,
          {plans_created_sql} AS legacy_plans_created,
          {plans_updated_sql} AS legacy_plans_updated,
          {task_entities_created_sql} AS legacy_task_entities_created,
          (SELECT COUNT(*) FROM zenos.entities_base WHERE created_at >= $1 {partner_filter}) AS entities_base_created,
          (SELECT COUNT(*) FROM zenos.entities_base WHERE updated_at >= $1 {partner_filter}) AS entities_base_updated
        """,
        *params,
    )
    if row is None:
        raise RuntimeError("shadow stability query returned no row")
    counts = {key: int(row[key]) for key in row.keys()}
    counts["legacy_tables_present"] = tables
    counts["phase_f_cleanup_complete"] = False
    return counts


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default=DEFAULT_CUTOVER_SINCE)
    parser.add_argument("--partner-id")
    args = parser.parse_args()

    since = _parse_since(args.since)
    conn = await asyncpg.connect(_database_url())
    try:
        counts = await _counts(conn, since=since, partner_id=args.partner_id)
    finally:
        await conn.close()

    legacy_keys = (
        "legacy_tasks_created",
        "legacy_tasks_updated",
        "legacy_plans_created",
        "legacy_plans_updated",
        "legacy_task_entities_created",
    )
    legacy_mutations = {key: counts[key] for key in legacy_keys}
    status = "ok" if all(value == 0 for value in legacy_mutations.values()) else "failed"
    report = {
        "status": status,
        "since": since.isoformat(),
        "partner_id": args.partner_id,
        "legacy_mutations": legacy_mutations,
        "legacy_tables_present": counts["legacy_tables_present"],
        "phase_f_cleanup_complete": counts["phase_f_cleanup_complete"],
        "new_path_activity": {
            key: value
            for key, value in counts.items()
            if key not in legacy_keys and key not in {"legacy_tables_present", "phase_f_cleanup_complete"}
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
