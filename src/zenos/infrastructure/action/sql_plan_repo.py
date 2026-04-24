"""PostgreSQL-backed PlanRepository."""

from __future__ import annotations
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.action import Plan
from zenos.domain.action.converters import plan_to_l3_entity
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire_with_tx,
    _dumps,
    _get_partner_id,
    _new_id,
    _now,
    _to_dt,
)


def _row_to_plan(row: asyncpg.Record) -> Plan:
    return Plan(
        id=row["id"],
        goal=row["goal"],
        status=row["status"],
        created_by=row["created_by"],
        owner=row["owner"],
        entry_criteria=row["entry_criteria"],
        exit_criteria=row["exit_criteria"],
        project=row["project"],
        product_id=row["product_id"],
        updated_by=row["updated_by"] if "updated_by" in row else None,
        result=row["result"] if "result" in row else None,
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


def _row_to_plan_from_l3(row: asyncpg.Record) -> Plan:
    return Plan(
        id=row["id"],
        goal=row["goal"],
        status=row["status"],
        created_by=(row["created_by"] if "created_by" in row else "") or "",
        owner=row["owner"],
        entry_criteria=row["entry_criteria"],
        exit_criteria=row["exit_criteria"],
        project=row["project"] if "project" in row else "",
        product_id=row["product_id"] if "product_id" in row else None,
        updated_by=row["updated_by"] if "updated_by" in row else None,
        result=row["result"] if "result" in row else None,
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


class SqlPlanRepository:
    """PostgreSQL-backed PlanRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _upsert_l3_plan(self, conn: asyncpg.Connection, plan: Plan, pid: str) -> None:
        l3_plan = plan_to_l3_entity(plan, partner_id=pid)
        existing = await conn.fetchrow(
            f"SELECT type_label FROM {SCHEMA}.entities_base WHERE id = $1 AND partner_id = $2",
            plan.id,
            pid,
        )
        if existing and existing["type_label"] != "plan":
            raise ValueError(
                f"L3 entity type mismatch for plan {plan.id}: {existing['type_label']}"
            )

        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.entities_base (
                id, partner_id, name, type_label, level, parent_id, status,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, 'plan', 3, $4, $5, $6, $7
            )
            ON CONFLICT (partner_id, id) DO UPDATE SET
                name=EXCLUDED.name,
                type_label=EXCLUDED.type_label,
                level=EXCLUDED.level,
                parent_id=EXCLUDED.parent_id,
                status=EXCLUDED.status,
                updated_at=EXCLUDED.updated_at
            """,
            l3_plan.id,
            pid,
            l3_plan.name,
            l3_plan.parent_id,
            l3_plan.status,
            l3_plan.created_at,
            l3_plan.updated_at,
        )
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.entity_l3_plan (
                partner_id, entity_id, description, task_status, assignee,
                dispatcher, acceptance_criteria_json, priority, result,
                goal_statement, entry_criteria, exit_criteria,
                created_by, updated_by, project, product_id
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7::jsonb, $8, $9,
                $10, $11, $12,
                $13, $14, $15, $16
            )
            ON CONFLICT (partner_id, entity_id) DO UPDATE SET
                description=EXCLUDED.description,
                task_status=EXCLUDED.task_status,
                assignee=EXCLUDED.assignee,
                dispatcher=EXCLUDED.dispatcher,
                acceptance_criteria_json=EXCLUDED.acceptance_criteria_json,
                priority=EXCLUDED.priority,
                result=EXCLUDED.result,
                goal_statement=EXCLUDED.goal_statement,
                entry_criteria=EXCLUDED.entry_criteria,
                exit_criteria=EXCLUDED.exit_criteria,
                created_by=EXCLUDED.created_by,
                updated_by=EXCLUDED.updated_by,
                project=EXCLUDED.project,
                product_id=EXCLUDED.product_id
            """,
            pid,
            l3_plan.id,
            l3_plan.description,
            l3_plan.task_status,
            l3_plan.assignee,
            l3_plan.dispatcher,
            _dumps(l3_plan.acceptance_criteria),
            l3_plan.priority,
            l3_plan.result,
            l3_plan.goal_statement,
            l3_plan.entry_criteria,
            l3_plan.exit_criteria,
            plan.created_by,
            plan.updated_by,
            plan.project,
            plan.product_id,
        )

    def _l3_select(self) -> str:
        return f"""
            SELECT eb.id,
                   eb.partner_id,
                   l3.goal_statement AS goal,
                   l3.task_status AS status,
                   l3.assignee AS owner,
                   NULLIF(l3.entry_criteria, '') AS entry_criteria,
                   NULLIF(l3.exit_criteria, '') AS exit_criteria,
                   l3.result,
                   eb.created_at,
                   eb.updated_at,
                   l3.created_by,
                   l3.updated_by,
                   l3.project,
                   l3.product_id
            FROM {SCHEMA}.entities_base eb
            JOIN {SCHEMA}.entity_l3_plan l3
              ON eb.partner_id = l3.partner_id AND eb.id = l3.entity_id
        """

    async def get_by_id(self, plan_id: str) -> Plan | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"{self._l3_select()} WHERE eb.id = $1 AND eb.partner_id = $2",
                plan_id,
                pid,
            )
        if not row:
            return None
        return _row_to_plan_from_l3(row)

    async def upsert(self, plan: Plan) -> Plan:
        pid = _get_partner_id()
        now = _now()
        plan.updated_at = now
        if plan.id is None:
            plan.id = _new_id()
            plan.created_at = now

        async with _acquire_with_tx(self._pool, None) as conn:
            await self._upsert_l3_plan(conn, plan, pid)
        return plan

    async def list_all(
        self,
        *,
        status: list[str] | None = None,
        project: str | None = None,
        product_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Plan]:
        pid = _get_partner_id()

        status_expr = "l3_rows.status"
        project_expr = "l3_rows.project"
        product_expr = "l3_rows.product_id"

        conditions = ["l3_rows.partner_id = $1"]
        params: list[Any] = [pid]
        idx = 2

        if status is not None:
            placeholders = ", ".join(f"${i}" for i in range(idx, idx + len(status)))
            conditions.append(f"{status_expr} IN ({placeholders})")
            params.extend(status)
            idx += len(status)

        if project is not None:
            conditions.append(f"{project_expr} = ${idx}")
            params.append(project)
            idx += 1

        if product_id is not None:
            conditions.append(f"{product_expr} = ${idx}")
            params.append(product_id)
            idx += 1

        where_clause = " AND ".join(conditions)
        params.append(limit)
        limit_idx = idx
        idx += 1
        params.append(offset)
        offset_idx = idx

        sql = (
            f"SELECT * FROM ({self._l3_select()}) l3_rows"
            f" WHERE {where_clause}"
            f" ORDER BY created_at DESC"
            f" LIMIT ${limit_idx} OFFSET ${offset_idx}"
        )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [_row_to_plan_from_l3(r) for r in rows]
