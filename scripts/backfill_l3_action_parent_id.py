#!/usr/bin/env python3
"""Backfill Wave 9 L3-Action entities_base.parent_id.

Phase D is intentionally pure SQL.  It does not call repository/domain layers,
because PLAN-task-ownership-ssot is not a blocker when the existing
``product_id`` values are already present and trusted.

Modes:
  --dry-run  Print a JSON report; no data is written.
  --apply    Insert missing L3 action base/subclass rows and set parent_id.

The apply path is additive/idempotent.  It records rows that still cannot be
assigned a parent in ``zenos.legacy_orphan_tasks`` instead of guessing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover - import guard for operator machines
    print("ERROR: asyncpg not installed. Run: pip install asyncpg", file=sys.stderr)
    sys.exit(1)


SCHEMA = "zenos"


def _status_to_task_status(status: str | None) -> str:
    return {
        "backlog": "todo",
        "blocked": "todo",
        "archived": "done",
    }.get(status or "todo", status or "todo")


def _status_to_plan_status(status: str | None) -> str:
    return status or "draft"


def _status_to_milestone_status(status: str | None) -> str:
    return {
        "active": "active",
        "completed": "completed",
        "done": "completed",
        "cancelled": "cancelled",
        "archived": "cancelled",
        "planned": "planned",
    }.get(status or "planned", "planned")


def compute_task_parent_id(row: dict[str, Any]) -> str | None:
    """D01 parent rule: subtask > plan > product."""
    return row.get("parent_task_id") or row.get("plan_id") or row.get("product_id")


def classify_task_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolvable: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []
    for row in rows:
        parent_id = compute_task_parent_id(row)
        item = dict(row)
        item["computed_parent_id"] = parent_id
        if parent_id:
            resolvable.append(item)
        else:
            item["reason"] = "NO_PARENT_SOURCE"
            orphaned.append(item)
    return resolvable, orphaned


def build_report(
    *,
    mode: str,
    task_rows: list[dict[str, Any]],
    plan_rows: list[dict[str, Any]],
    milestone_rows: list[dict[str, Any]],
    orphaned_tasks: list[dict[str, Any]],
    updated: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "tasks": {
            "scanned": len(task_rows),
            "resolvable": len(task_rows) - len(orphaned_tasks),
            "orphaned": orphaned_tasks,
        },
        "plans": {"scanned": len(plan_rows)},
        "milestones": {"scanned": len(milestone_rows)},
        "updated": updated or {},
    }


async def fetch_task_candidates(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        f"""
        SELECT id, partner_id, title, description, status, priority, assignee,
               dispatcher, created_by, parent_task_id, plan_id, product_id,
               plan_order, depends_on_task_ids_json, blocked_reason, due_date,
               acceptance_criteria_json, result, created_at, updated_at
        FROM {SCHEMA}.tasks
        ORDER BY partner_id, id
        """
    )
    return [dict(r) for r in rows]


async def fetch_plan_candidates(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        f"""
        SELECT id, partner_id, goal, owner, status, entry_criteria,
               exit_criteria, product_id, created_by, result, created_at, updated_at
        FROM {SCHEMA}.plans
        ORDER BY partner_id, id
        """
    )
    return [dict(r) for r in rows]


async def fetch_milestone_candidates(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        f"""
        SELECT id, partner_id, name, summary, status, parent_id, owner,
               visibility, visible_to_roles, visible_to_members,
               visible_to_departments, created_at, updated_at
        FROM {SCHEMA}.entities
        WHERE type = 'goal'
        ORDER BY partner_id, id
        """
    )
    return [dict(r) for r in rows]


async def ensure_legacy_entity_base(conn: asyncpg.Connection) -> int:
    """Mirror legacy entities into entities_base as parent targets."""
    tag = await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entities_base (
            id, partner_id, name, type_label, level, parent_id, status,
            visibility, visible_to_roles, visible_to_members,
            visible_to_departments, owner, created_at, updated_at
        )
        SELECT e.id, e.partner_id, e.name, e.type, COALESCE(e.level, 3), e.parent_id,
               e.status, e.visibility, '{{}}'::text[], '{{}}'::text[], '{{}}'::text[],
               e.owner, e.created_at, e.updated_at
        FROM {SCHEMA}.entities e
        ON CONFLICT (partner_id, id) DO UPDATE SET
            name=EXCLUDED.name,
            status=EXCLUDED.status,
            visibility=EXCLUDED.visibility,
            owner=EXCLUDED.owner,
            updated_at=EXCLUDED.updated_at
        """
    )
    return _tag_count(tag)


async def upsert_plan_rows(conn: asyncpg.Connection) -> int:
    tag = await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entities_base (
            id, partner_id, name, type_label, level, parent_id, status,
            created_at, updated_at
        )
        SELECT p.id, p.partner_id, p.goal, 'plan', 3, p.product_id,
               'active', p.created_at, p.updated_at
        FROM {SCHEMA}.plans p
        WHERE p.product_id IS NOT NULL
        ON CONFLICT (partner_id, id) DO UPDATE SET
            name=EXCLUDED.name,
            parent_id=EXCLUDED.parent_id,
            status=EXCLUDED.status,
            updated_at=EXCLUDED.updated_at
        """
    )
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entity_l3_plan (
            partner_id, entity_id, description, task_status, assignee,
            dispatcher, acceptance_criteria_json, priority, result,
            goal_statement, entry_criteria, exit_criteria
        )
        SELECT p.partner_id, p.id, COALESCE(p.goal, ''), p.status, p.owner,
               COALESCE(NULLIF(p.created_by, ''), 'human'), '[]'::jsonb,
               'medium', p.result, p.goal,
               COALESCE(p.entry_criteria, ''), COALESCE(p.exit_criteria, '')
        FROM {SCHEMA}.plans p
        WHERE p.product_id IS NOT NULL
        ON CONFLICT (partner_id, entity_id) DO UPDATE SET
            description=EXCLUDED.description,
            task_status=EXCLUDED.task_status,
            assignee=EXCLUDED.assignee,
            result=EXCLUDED.result,
            goal_statement=EXCLUDED.goal_statement,
            entry_criteria=EXCLUDED.entry_criteria,
            exit_criteria=EXCLUDED.exit_criteria
        """
    )
    return _tag_count(tag)


async def upsert_task_rows(conn: asyncpg.Connection) -> int:
    tag = await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entities_base (
            id, partner_id, name, type_label, level, parent_id, status,
            created_at, updated_at
        )
        SELECT t.id, t.partner_id, t.title,
               CASE WHEN t.parent_task_id IS NOT NULL THEN 'subtask' ELSE 'task' END,
               3,
               COALESCE(t.parent_task_id, t.plan_id, t.product_id),
               'active', t.created_at, t.updated_at
        FROM {SCHEMA}.tasks t
        WHERE COALESCE(t.parent_task_id, t.plan_id, t.product_id) IS NOT NULL
        ON CONFLICT (partner_id, id) DO UPDATE SET
            name=EXCLUDED.name,
            type_label=EXCLUDED.type_label,
            parent_id=EXCLUDED.parent_id,
            status=EXCLUDED.status,
            updated_at=EXCLUDED.updated_at
        """
    )
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entity_l3_task (
            partner_id, entity_id, description, task_status, assignee,
            dispatcher, acceptance_criteria_json, priority, result,
            plan_order, depends_on_json, blocked_reason, due_date
        )
        SELECT t.partner_id, t.id, COALESCE(t.description, ''),
               CASE t.status
                    WHEN 'backlog' THEN 'todo'
                    WHEN 'blocked' THEN 'todo'
                    WHEN 'archived' THEN 'done'
                    ELSE t.status
               END,
               t.assignee,
               COALESCE(NULLIF(t.dispatcher, ''), 'human'),
               t.acceptance_criteria_json, t.priority, t.result,
               t.plan_order, t.depends_on_task_ids_json, t.blocked_reason,
               t.due_date::date
        FROM {SCHEMA}.tasks t
        WHERE t.parent_task_id IS NULL
          AND COALESCE(t.parent_task_id, t.plan_id, t.product_id) IS NOT NULL
        ON CONFLICT (partner_id, entity_id) DO UPDATE SET
            description=EXCLUDED.description,
            task_status=EXCLUDED.task_status,
            assignee=EXCLUDED.assignee,
            dispatcher=EXCLUDED.dispatcher,
            acceptance_criteria_json=EXCLUDED.acceptance_criteria_json,
            priority=EXCLUDED.priority,
            result=EXCLUDED.result,
            plan_order=EXCLUDED.plan_order,
            depends_on_json=EXCLUDED.depends_on_json,
            blocked_reason=EXCLUDED.blocked_reason,
            due_date=EXCLUDED.due_date
        """
    )
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entity_l3_subtask (
            partner_id, entity_id, description, task_status, assignee,
            dispatcher, acceptance_criteria_json, priority, result,
            plan_order, depends_on_json, blocked_reason, due_date,
            dispatched_by_agent, auto_created
        )
        SELECT t.partner_id, t.id, COALESCE(t.description, ''),
               CASE t.status
                    WHEN 'backlog' THEN 'todo'
                    WHEN 'blocked' THEN 'todo'
                    WHEN 'archived' THEN 'done'
                    ELSE t.status
               END,
               t.assignee,
               COALESCE(NULLIF(t.dispatcher, ''), 'human'),
               t.acceptance_criteria_json, t.priority, t.result,
               t.plan_order, t.depends_on_task_ids_json, t.blocked_reason,
               t.due_date::date,
               CASE
                    WHEN t.dispatcher LIKE 'agent:%' THEN t.dispatcher
                    WHEN t.created_by LIKE 'agent:%' THEN t.created_by
                    ELSE 'agent:architect'
               END,
               true
        FROM {SCHEMA}.tasks t
        WHERE t.parent_task_id IS NOT NULL
        ON CONFLICT (partner_id, entity_id) DO UPDATE SET
            description=EXCLUDED.description,
            task_status=EXCLUDED.task_status,
            assignee=EXCLUDED.assignee,
            dispatcher=EXCLUDED.dispatcher,
            acceptance_criteria_json=EXCLUDED.acceptance_criteria_json,
            priority=EXCLUDED.priority,
            result=EXCLUDED.result,
            plan_order=EXCLUDED.plan_order,
            depends_on_json=EXCLUDED.depends_on_json,
            blocked_reason=EXCLUDED.blocked_reason,
            due_date=EXCLUDED.due_date,
            dispatched_by_agent=EXCLUDED.dispatched_by_agent,
            auto_created=EXCLUDED.auto_created
        """
    )
    return _tag_count(tag)


async def upsert_milestone_rows(conn: asyncpg.Connection) -> int:
    tag = await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entities_base (
            id, partner_id, name, type_label, level, parent_id, status,
            visibility, visible_to_roles, visible_to_members,
            visible_to_departments, owner, created_at, updated_at
        )
        SELECT e.id, e.partner_id, e.name, 'milestone', 3, e.parent_id,
               e.status, e.visibility, '{{}}'::text[], '{{}}'::text[], '{{}}'::text[],
               e.owner, e.created_at, e.updated_at
        FROM {SCHEMA}.entities e
        WHERE e.type = 'goal'
        ON CONFLICT (partner_id, id) DO UPDATE SET
            name=EXCLUDED.name,
            type_label=EXCLUDED.type_label,
            parent_id=EXCLUDED.parent_id,
            status=EXCLUDED.status,
            visibility=EXCLUDED.visibility,
            owner=EXCLUDED.owner,
            updated_at=EXCLUDED.updated_at
        """
    )
    await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.entity_l3_milestone (
            partner_id, entity_id, description, task_status, assignee,
            dispatcher, acceptance_criteria_json, priority, result,
            target_date, completion_criteria
        )
        SELECT e.partner_id, e.id, e.summary,
               CASE e.status
                    WHEN 'archived' THEN 'cancelled'
                    WHEN 'done' THEN 'completed'
                    WHEN 'completed' THEN 'completed'
                    WHEN 'cancelled' THEN 'cancelled'
                    WHEN 'active' THEN 'active'
                    ELSE 'planned'
               END,
               e.owner,
               CASE
                    WHEN e.owner LIKE 'agent:%' OR e.owner LIKE 'human%' THEN e.owner
                    ELSE 'human'
               END,
               '[]'::jsonb, 'medium', NULL, NULL, NULL
        FROM {SCHEMA}.entities e
        WHERE e.type = 'goal'
        ON CONFLICT (partner_id, entity_id) DO UPDATE SET
            description=EXCLUDED.description,
            task_status=EXCLUDED.task_status,
            assignee=EXCLUDED.assignee,
            dispatcher=EXCLUDED.dispatcher
        """
    )
    return _tag_count(tag)


async def record_orphan_tasks(conn: asyncpg.Connection) -> int:
    tag = await conn.execute(
        f"""
        INSERT INTO {SCHEMA}.legacy_orphan_tasks (
            task_id, partner_id, reason, detected_at
        )
        SELECT t.id, t.partner_id, 'NO_PARENT_SOURCE', now()
        FROM {SCHEMA}.tasks t
        WHERE COALESCE(t.parent_task_id, t.plan_id, t.product_id) IS NULL
        ON CONFLICT (partner_id, task_id) DO UPDATE SET
            reason=EXCLUDED.reason,
            detected_at=EXCLUDED.detected_at,
            resolved_at=NULL,
            resolver_partner_id=NULL,
            manual_parent_id=NULL
        """
    )
    return _tag_count(tag)


async def validate_parent_chains(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        f"""
        WITH RECURSIVE chain AS (
            SELECT child.partner_id, child.id AS child_id, child.parent_id,
                   parent.id AS current_id, parent.parent_id AS next_parent_id,
                   parent.level, 1 AS depth, ARRAY[child.id, parent.id] AS path
            FROM {SCHEMA}.entities_base child
            LEFT JOIN {SCHEMA}.entities_base parent
              ON parent.partner_id = child.partner_id
             AND parent.id = child.parent_id
            WHERE child.type_label IN ('milestone', 'plan', 'task', 'subtask')
              AND child.parent_id IS NOT NULL
            UNION ALL
            SELECT chain.partner_id, chain.child_id, chain.parent_id,
                   parent.id AS current_id, parent.parent_id AS next_parent_id,
                   parent.level, chain.depth + 1, chain.path || parent.id
            FROM chain
            JOIN {SCHEMA}.entities_base parent
              ON parent.partner_id = chain.partner_id
             AND parent.id = chain.next_parent_id
            WHERE chain.next_parent_id IS NOT NULL
              AND NOT parent.id = ANY(chain.path)
              AND chain.depth < 16
        ),
        terminal AS (
            SELECT DISTINCT ON (partner_id, child_id)
                   partner_id, child_id, current_id, next_parent_id, level, depth
            FROM chain
            ORDER BY partner_id, child_id, depth DESC
        )
        SELECT eb.partner_id, eb.id AS entity_id, eb.type_label, eb.parent_id,
               CASE
                    WHEN eb.parent_id IS NULL THEN 'MISSING_PARENT_ID'
                    WHEN t.current_id IS NULL THEN 'MISSING_PARENT_ROW'
                    WHEN t.level != 1 OR t.next_parent_id IS NOT NULL THEN 'INVALID_PARENT_CHAIN'
                    ELSE NULL
               END AS reason
        FROM {SCHEMA}.entities_base eb
        LEFT JOIN terminal t
          ON t.partner_id = eb.partner_id AND t.child_id = eb.id
        WHERE eb.type_label IN ('milestone', 'plan', 'task', 'subtask')
          AND (
              eb.parent_id IS NULL
              OR t.current_id IS NULL
              OR t.level != 1
              OR t.next_parent_id IS NOT NULL
          )
        ORDER BY eb.partner_id, eb.id
        """
    )
    return [dict(r) for r in rows]


async def record_parent_chain_warnings(
    conn: asyncpg.Connection,
    warnings: list[dict[str, Any]],
) -> int:
    if not warnings:
        return 0
    await conn.executemany(
        f"""
        INSERT INTO {SCHEMA}.legacy_parent_chain_warnings (
            task_id, partner_id, chain_snapshot_json, detected_at
        )
        VALUES ($1, $2, $3::jsonb, now())
        ON CONFLICT (partner_id, task_id) DO UPDATE SET
            chain_snapshot_json=EXCLUDED.chain_snapshot_json,
            detected_at=EXCLUDED.detected_at
        """,
        [
            (
                item["entity_id"],
                item["partner_id"],
                json.dumps(item, sort_keys=True),
            )
            for item in warnings
        ],
    )
    return len(warnings)


async def run_dry_run(conn: asyncpg.Connection, output_path: str | None) -> int:
    tasks = await fetch_task_candidates(conn)
    plans = await fetch_plan_candidates(conn)
    milestones = await fetch_milestone_candidates(conn)
    _, orphaned_tasks = classify_task_rows(tasks)
    report = build_report(
        mode="dry-run",
        task_rows=tasks,
        plan_rows=plans,
        milestone_rows=milestones,
        orphaned_tasks=orphaned_tasks,
    )
    emit_report(report, output_path)
    return 0 if not orphaned_tasks else 3


async def run_apply(conn: asyncpg.Connection, output_path: str | None) -> int:
    tasks = await fetch_task_candidates(conn)
    plans = await fetch_plan_candidates(conn)
    milestones = await fetch_milestone_candidates(conn)
    _, orphaned_tasks = classify_task_rows(tasks)
    async with conn.transaction():
        updated = {
            "legacy_entity_base": await ensure_legacy_entity_base(conn),
            "plans": await upsert_plan_rows(conn),
            "tasks": await upsert_task_rows(conn),
            "milestones": await upsert_milestone_rows(conn),
            "orphan_tasks": await record_orphan_tasks(conn),
        }
        warnings = await validate_parent_chains(conn)
        updated["parent_chain_warnings"] = await record_parent_chain_warnings(conn, warnings)
    report = build_report(
        mode="apply",
        task_rows=tasks,
        plan_rows=plans,
        milestone_rows=milestones,
        orphaned_tasks=orphaned_tasks,
        updated=updated,
    )
    report["parent_chain_warnings"] = warnings
    emit_report(report, output_path)
    return 0 if not orphaned_tasks and not warnings else 3


def emit_report(report: dict[str, Any], output_path: str | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        print(f"Report written to {output_path}", file=sys.stderr)
    else:
        print(text)


def _tag_count(tag: str) -> int:
    try:
        return int(tag.split()[-1])
    except (IndexError, ValueError):
        return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Wave 9 L3-Action parent_id")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--output", metavar="PATH", help="Write JSON report to PATH")
    return parser.parse_args(argv)


async def main(args: argparse.Namespace) -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is required", file=sys.stderr)
        return 1
    conn = await asyncpg.connect(database_url)
    try:
        if args.dry_run:
            return await run_dry_run(conn, args.output)
        return await run_apply(conn, args.output)
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(parse_args())))
