#!/usr/bin/env python3
"""Smoke-test Wave 9 L3 read path against a live database.

Read-only check:
- Select a partner with existing L3 tasks unless --partner-id is provided.
- Read sample tasks/plans through repositories.
- Verify externally visible stable fields can be materialized from L3 storage.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

import asyncpg

from zenos.infrastructure.action.sql_plan_repo import SqlPlanRepository
from zenos.infrastructure.action.sql_task_repo import SqlTaskRepository
from zenos.infrastructure.context import current_partner_id


TASK_FIELDS = (
    "id",
    "title",
    "description",
    "status",
    "priority",
    "assignee",
    "assignee_role_id",
    "plan_id",
    "plan_order",
    "depends_on_task_ids",
    "linked_entities",
    "linked_protocol",
    "linked_blindspot",
    "blocked_by",
    "blocked_reason",
    "acceptance_criteria",
    "confirmed_by_creator",
    "rejection_reason",
    "result",
    "project",
    "product_id",
    "attachments",
    "parent_task_id",
    "dispatcher",
)

PLAN_FIELDS = (
    "id",
    "goal",
    "status",
    "owner",
    "entry_criteria",
    "exit_criteria",
    "project",
    "product_id",
    "result",
)


def _stable(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    data = asdict(obj) if is_dataclass(obj) else dict(obj)
    return {field: data.get(field) for field in fields}


async def _pick_partner(conn: asyncpg.Connection) -> str:
    row = await conn.fetchrow(
        """
        SELECT partner_id
        FROM zenos.entity_l3_task
        GROUP BY partner_id
        ORDER BY count(*) DESC
        LIMIT 1
        """
    )
    if row is None:
        raise RuntimeError("No tasks found; cannot smoke-test L3 read path")
    return str(row["partner_id"])


async def _sample_task_ids(conn: asyncpg.Connection, *, partner_id: str, limit: int) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT entity_id AS id
        FROM zenos.entity_l3_task
        WHERE partner_id = $1
        ORDER BY entity_id
        LIMIT $2
        """,
        partner_id,
        limit,
    )
    return [str(row["id"]) for row in rows]


async def _sample_plan_ids(conn: asyncpg.Connection, *, partner_id: str, limit: int) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT entity_id AS id
        FROM zenos.entity_l3_plan
        WHERE partner_id = $1
        ORDER BY entity_id
        LIMIT $2
        """,
        partner_id,
        limit,
    )
    return [str(row["id"]) for row in rows]


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partner-id")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

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

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            partner_id = args.partner_id or await _pick_partner(conn)
            task_ids = await _sample_task_ids(conn, partner_id=partner_id, limit=args.limit)
            plan_ids = await _sample_plan_ids(conn, partner_id=partner_id, limit=args.limit)

        token = current_partner_id.set(partner_id)
        try:
            task_repo = SqlTaskRepository(pool)
            plan_repo = SqlPlanRepository(pool)
            mismatches: list[dict[str, Any]] = []

            for task_id in task_ids:
                task = await task_repo.get_by_id(task_id)
                if task is None:
                    mismatches.append({"kind": "task", "id": task_id, "reason": "missing"})
                    continue
                stable = _stable(task, TASK_FIELDS)
                if stable["id"] != task_id:
                    mismatches.append({"kind": "task", "id": task_id, "task": stable})

            for plan_id in plan_ids:
                plan = await plan_repo.get_by_id(plan_id)
                if plan is None:
                    mismatches.append({"kind": "plan", "id": plan_id, "reason": "missing"})
                    continue
                stable = _stable(plan, PLAN_FIELDS)
                if stable["id"] != plan_id:
                    mismatches.append({"kind": "plan", "id": plan_id, "plan": stable})
        finally:
            current_partner_id.reset(token)

        report = {
            "status": "ok" if not mismatches else "failed",
            "partner_id": partner_id,
            "sampled": {"tasks": len(task_ids), "plans": len(plan_ids)},
            "mismatches": mismatches,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return 0 if not mismatches else 1
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
