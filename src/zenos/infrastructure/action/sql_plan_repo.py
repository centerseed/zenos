"""PostgreSQL-backed PlanRepository."""

from __future__ import annotations

from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.action import Plan
from zenos.infrastructure.sql_common import (
    SCHEMA,
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
        product_id=row["product_id"] if "product_id" in row else (row["project_id"] if "project_id" in row else None),
        updated_by=row["updated_by"] if "updated_by" in row else None,
        result=row["result"] if "result" in row else None,
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


class SqlPlanRepository:
    """PostgreSQL-backed PlanRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, plan_id: str) -> Plan | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.plans WHERE id = $1 AND partner_id = $2",
                plan_id, pid,
            )
        if not row:
            return None
        return _row_to_plan(row)

    async def upsert(self, plan: Plan) -> Plan:
        pid = _get_partner_id()
        now = _now()
        plan.updated_at = now
        if plan.id is None:
            plan.id = _new_id()
            plan.created_at = now

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.plans (
                    id, partner_id, goal, owner, status,
                    entry_criteria, exit_criteria, project, product_id,
                    created_by, updated_by, result,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12,
                    $13, $14
                )
                ON CONFLICT (partner_id, id) DO UPDATE SET
                    goal=EXCLUDED.goal,
                    owner=EXCLUDED.owner,
                    status=EXCLUDED.status,
                    entry_criteria=EXCLUDED.entry_criteria,
                    exit_criteria=EXCLUDED.exit_criteria,
                    project=EXCLUDED.project,
                    product_id=EXCLUDED.product_id,
                    updated_by=EXCLUDED.updated_by,
                    result=EXCLUDED.result,
                    updated_at=EXCLUDED.updated_at
                WHERE plans.partner_id = EXCLUDED.partner_id
                """,
                plan.id, pid, plan.goal, plan.owner, plan.status,
                plan.entry_criteria, plan.exit_criteria, plan.project, plan.product_id,
                plan.created_by, plan.updated_by, plan.result,
                plan.created_at, plan.updated_at,
            )
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

        conditions = ["partner_id = $1"]
        params: list[Any] = [pid]
        idx = 2

        if status is not None:
            placeholders = ", ".join(f"${i}" for i in range(idx, idx + len(status)))
            conditions.append(f"status IN ({placeholders})")
            params.extend(status)
            idx += len(status)

        if project is not None:
            conditions.append(f"project = ${idx}")
            params.append(project)
            idx += 1

        if product_id is not None:
            conditions.append(f"product_id = ${idx}")
            params.append(product_id)
            idx += 1

        where_clause = " AND ".join(conditions)
        params.append(limit)
        limit_idx = idx
        idx += 1
        params.append(offset)
        offset_idx = idx

        sql = (
            f"SELECT * FROM {SCHEMA}.plans"
            f" WHERE {where_clause}"
            f" ORDER BY created_at DESC"
            f" LIMIT ${limit_idx} OFFSET ${offset_idx}"
        )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [_row_to_plan(r) for r in rows]
