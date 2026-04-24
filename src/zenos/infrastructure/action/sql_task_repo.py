"""PostgreSQL-backed TaskRepository and PostgresTaskCommentRepository."""

from __future__ import annotations

import json
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.action import HandoffEvent, Task
from zenos.domain.action.converters import task_to_l3_entity
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire_with_tx,
    _dumps,
    _get_partner_id,
    _json_loads_safe,
    _new_id,
    _now,
    _to_dt,
)


def _deserialize_handoff_events(raw: object) -> list[HandoffEvent]:
    """Deserialize JSONB handoff_events column into HandoffEvent objects."""
    if not raw:
        return []
    records: list[dict] = raw if isinstance(raw, list) else (_json_loads_safe(raw) or [])
    events: list[HandoffEvent] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        events.append(HandoffEvent(
            at=_to_dt(rec.get("at")) or _now(),
            from_dispatcher=rec.get("from_dispatcher"),
            to_dispatcher=rec.get("to_dispatcher", ""),
            reason=rec.get("reason", ""),
            output_ref=rec.get("output_ref"),
            notes=rec.get("notes"),
        ))
    return events


def _row_to_task(row: asyncpg.Record, linked_entities: list[str], blocked_by: list[str]) -> Task:
    plan_id = row["plan_id"] if "plan_id" in row else None
    plan_order = row["plan_order"] if "plan_order" in row else None
    depends_json = row["depends_on_task_ids_json"] if "depends_on_task_ids_json" in row else None
    source_metadata_json = row["source_metadata_json"] if "source_metadata_json" in row else None
    handoff_events_raw = row["handoff_events"] if "handoff_events" in row else None
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        priority_reason=row["priority_reason"],
        assignee=row["assignee"],
        assignee_role_id=row["assignee_role_id"],
        plan_id=plan_id,
        plan_order=plan_order,
        depends_on_task_ids=_json_loads_safe(depends_json) or [],
        created_by=row["created_by"],
        updated_by=row["updated_by"] if "updated_by" in row else None,
        linked_entities=linked_entities,
        linked_protocol=row["linked_protocol"],
        linked_blindspot=row["linked_blindspot"],
        source_type=row["source_type"],
        source_metadata=_json_loads_safe(source_metadata_json) or {},
        context_summary=row["context_summary"],
        due_date=_to_dt(row["due_date"]),
        blocked_by=blocked_by,
        blocked_reason=row["blocked_reason"],
        acceptance_criteria=_json_loads_safe(row["acceptance_criteria_json"]) or [],
        completed_by=row["completed_by"],
        creator_name=row["creator_name"] if "creator_name" in row else None,
        assignee_name=row["assignee_name"] if "assignee_name" in row else None,
        confirmed_by_creator=row["confirmed_by_creator"],
        rejection_reason=row["rejection_reason"],
        result=row["result"],
        project=row["project"],
        product_id=row["product_id"],
        attachments=_json_loads_safe(row["attachments"] if "attachments" in row else None) or [],
        parent_task_id=row["parent_task_id"] if "parent_task_id" in row else None,
        dispatcher=row["dispatcher"] if "dispatcher" in row else None,
        handoff_events=_deserialize_handoff_events(handoff_events_raw),
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
        completed_at=_to_dt(row["completed_at"]),
    )


def _row_to_task_from_l3(
    row: asyncpg.Record,
    linked_entities: list[str],
    blocked_by: list[str],
) -> Task:
    due_date = row["due_date"] if "due_date" in row else None
    due_datetime = None
    if due_date is not None:
        due_datetime = _to_dt(due_date)
        if due_datetime is None and hasattr(due_date, "year"):
            from datetime import datetime, time, timezone

            due_datetime = datetime.combine(due_date, time.min, tzinfo=timezone.utc)

    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        priority_reason=row["priority_reason"] if "priority_reason" in row else "",
        assignee=row["assignee"],
        assignee_role_id=row["assignee_role_id"] if "assignee_role_id" in row else None,
        plan_id=row["plan_id"] if "plan_id" in row else None,
        plan_order=row["plan_order"] if "plan_order" in row else None,
        depends_on_task_ids=_json_loads_safe(row["depends_on_task_ids_json"] if "depends_on_task_ids_json" in row else None) or [],
        created_by=(row["created_by"] if "created_by" in row else "") or "",
        updated_by=row["updated_by"] if "updated_by" in row else None,
        linked_entities=linked_entities,
        linked_protocol=row["linked_protocol"] if "linked_protocol" in row else None,
        linked_blindspot=row["linked_blindspot"] if "linked_blindspot" in row else None,
        source_type=row["source_type"] if "source_type" in row else "",
        source_metadata=_json_loads_safe(row["source_metadata_json"] if "source_metadata_json" in row else None) or {},
        context_summary=row["context_summary"] if "context_summary" in row else "",
        due_date=due_datetime,
        blocked_by=blocked_by,
        blocked_reason=row["blocked_reason"],
        acceptance_criteria=_json_loads_safe(row["acceptance_criteria_json"]) or [],
        completed_by=row["completed_by"] if "completed_by" in row else None,
        creator_name=row["creator_name"] if "creator_name" in row else None,
        assignee_name=row["assignee_name"] if "assignee_name" in row else None,
        confirmed_by_creator=row["confirmed_by_creator"] if "confirmed_by_creator" in row else False,
        rejection_reason=row["rejection_reason"] if "rejection_reason" in row else None,
        result=row["result"],
        project=row["project"] if "project" in row else "",
        product_id=row["product_id"] if "product_id" in row else None,
        attachments=_json_loads_safe(row["attachments"] if "attachments" in row else None) or [],
        parent_task_id=row["parent_task_id"] if "parent_task_id" in row else None,
        dispatcher=row["dispatcher"],
        handoff_events=_deserialize_handoff_events(row["handoff_events"] if "handoff_events" in row else None),
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
        completed_at=_to_dt(row["completed_at"] if "completed_at" in row else None),
    )


class SqlTaskRepository:
    """PostgreSQL-backed TaskRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_task_relations(
        self, conn: asyncpg.Connection, task_id: str, pid: str,
    ) -> tuple[list[str], list[str]]:
        entity_rows = await conn.fetch(
            f"""SELECT target_entity_id AS entity_id
                FROM {SCHEMA}.relationships
                WHERE source_entity_id = $1 AND partner_id = $2
                  AND type = 'related_to'""",
            task_id, pid,
        )
        blocker_rows = await conn.fetch(
            f"""SELECT jsonb_array_elements_text(depends_on_json) AS blocker_task_id
                FROM {SCHEMA}.entity_l3_task
                WHERE entity_id = $1 AND partner_id = $2
                UNION ALL
                SELECT jsonb_array_elements_text(depends_on_json) AS blocker_task_id
                FROM {SCHEMA}.entity_l3_subtask
                WHERE entity_id = $1 AND partner_id = $2""",
            task_id, pid,
        )
        linked_entities = [r["entity_id"] for r in entity_rows]
        blocked_by = [r["blocker_task_id"] for r in blocker_rows]
        return linked_entities, blocked_by

    async def _batch_fetch_task_relations(
        self, conn: asyncpg.Connection, task_ids: list[str], pid: str,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Batch-fetch linked_entities and blocked_by for a list of task IDs."""
        entity_rows = await conn.fetch(
            f"""SELECT source_entity_id AS task_id, target_entity_id AS entity_id
                FROM {SCHEMA}.relationships
                WHERE partner_id = $1
                  AND source_entity_id = ANY($2::text[])
                  AND type = 'related_to'""",
            pid, task_ids,
        )
        blocker_rows = await conn.fetch(
            f"""SELECT entity_id AS task_id, jsonb_array_elements_text(depends_on_json) AS blocker_task_id
                FROM {SCHEMA}.entity_l3_task
                WHERE partner_id = $1 AND entity_id = ANY($2::text[])
                UNION ALL
                SELECT entity_id AS task_id, jsonb_array_elements_text(depends_on_json) AS blocker_task_id
                FROM {SCHEMA}.entity_l3_subtask
                WHERE partner_id = $1 AND entity_id = ANY($2::text[])""",
            pid, task_ids,
        )
        linked_map: dict[str, list[str]] = {}
        for er in entity_rows:
            linked_map.setdefault(er["task_id"], []).append(er["entity_id"])
        blocker_map: dict[str, list[str]] = {}
        for br in blocker_rows:
            blocker_map.setdefault(br["task_id"], []).append(br["blocker_task_id"])
        return linked_map, blocker_map

    def _rows_to_tasks(
        self,
        rows: list[asyncpg.Record],
        linked_map: dict[str, list[str]],
        blocker_map: dict[str, list[str]],
    ) -> list[Task]:
        return [
            _row_to_task(r, linked_map.get(r["id"], []), blocker_map.get(r["id"], []))
            for r in rows
        ]

    def _rows_to_tasks_from_l3(
        self,
        rows: list[asyncpg.Record],
        linked_map: dict[str, list[str]],
        blocker_map: dict[str, list[str]],
    ) -> list[Task]:
        return [
            _row_to_task_from_l3(r, linked_map.get(r["id"], []), blocker_map.get(r["id"], []))
            for r in rows
        ]

    async def _upsert_l3_task(self, conn: asyncpg.Connection, task: Task, pid: str) -> None:
        l3_task = task_to_l3_entity(task, partner_id=pid)
        is_subtask = bool(task.parent_task_id)
        type_label = "subtask" if is_subtask else "task"
        existing = await conn.fetchrow(
            f"SELECT type_label FROM {SCHEMA}.entities_base WHERE id = $1 AND partner_id = $2",
            task.id,
            pid,
        )
        if existing and existing["type_label"] not in {"task", "subtask"}:
            raise ValueError(
                f"L3 entity type mismatch for task {task.id}: {existing['type_label']}"
            )

        parent_id = task.parent_task_id or task.plan_id or task.product_id
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.entities_base (
                id, partner_id, name, type_label, level, parent_id, status,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, 3, $5, $6, $7, $8
            )
            ON CONFLICT (partner_id, id) DO UPDATE SET
                name=EXCLUDED.name,
                type_label=EXCLUDED.type_label,
                level=EXCLUDED.level,
                parent_id=EXCLUDED.parent_id,
                status=EXCLUDED.status,
                updated_at=EXCLUDED.updated_at
            """,
            l3_task.id,
            pid,
            l3_task.name,
            type_label,
            parent_id,
            l3_task.status,
            l3_task.created_at,
            l3_task.updated_at,
        )
        if is_subtask:
            await conn.execute(
                f"DELETE FROM {SCHEMA}.entity_l3_task WHERE partner_id = $1 AND entity_id = $2",
                pid,
                l3_task.id,
            )
            dispatched_by_agent = (
                task.dispatcher
                if task.dispatcher and task.dispatcher.startswith("agent:")
                else task.created_by
                if task.created_by.startswith("agent:")
                else "agent:architect"
            )
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entity_l3_subtask (
                    partner_id, entity_id, description, task_status, assignee,
                    dispatcher, acceptance_criteria_json, priority, result,
                    plan_order, depends_on_json, blocked_reason, due_date,
                    dispatched_by_agent, auto_created,
                    priority_reason, assignee_role_id, created_by, updated_by,
                    linked_protocol, linked_blindspot, source_type, source_metadata_json,
                    context_summary, completed_by, confirmed_by_creator, rejection_reason,
                    project, product_id, attachments, completed_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7::jsonb, $8, $9,
                    $10, $11::jsonb, $12, $13,
                    $14, true,
                    $15, $16, $17, $18,
                    $19, $20, $21, $22::jsonb,
                    $23, $24, $25, $26,
                    $27, $28, $29::jsonb, $30
                )
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
                    auto_created=EXCLUDED.auto_created,
                    priority_reason=EXCLUDED.priority_reason,
                    assignee_role_id=EXCLUDED.assignee_role_id,
                    created_by=EXCLUDED.created_by,
                    updated_by=EXCLUDED.updated_by,
                    linked_protocol=EXCLUDED.linked_protocol,
                    linked_blindspot=EXCLUDED.linked_blindspot,
                    source_type=EXCLUDED.source_type,
                    source_metadata_json=EXCLUDED.source_metadata_json,
                    context_summary=EXCLUDED.context_summary,
                    completed_by=EXCLUDED.completed_by,
                    confirmed_by_creator=EXCLUDED.confirmed_by_creator,
                    rejection_reason=EXCLUDED.rejection_reason,
                    project=EXCLUDED.project,
                    product_id=EXCLUDED.product_id,
                    attachments=EXCLUDED.attachments,
                    completed_at=EXCLUDED.completed_at
                """,
                pid,
                l3_task.id,
                l3_task.description,
                l3_task.task_status,
                l3_task.assignee,
                l3_task.dispatcher,
                _dumps(l3_task.acceptance_criteria),
                l3_task.priority,
                l3_task.result,
                l3_task.plan_order,
                _dumps(l3_task.depends_on),
                l3_task.blocked_reason,
                l3_task.due_date,
                dispatched_by_agent,
                task.priority_reason,
                task.assignee_role_id,
                task.created_by,
                task.updated_by,
                task.linked_protocol,
                task.linked_blindspot,
                task.source_type,
                _dumps(task.source_metadata),
                task.context_summary,
                task.completed_by,
                task.confirmed_by_creator,
                task.rejection_reason,
                task.project,
                task.product_id,
                _dumps(task.attachments),
                task.completed_at,
            )
        else:
            await conn.execute(
                f"DELETE FROM {SCHEMA}.entity_l3_subtask WHERE partner_id = $1 AND entity_id = $2",
                pid,
                l3_task.id,
            )
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entity_l3_task (
                    partner_id, entity_id, description, task_status, assignee,
                    dispatcher, acceptance_criteria_json, priority, result,
                    plan_order, depends_on_json, blocked_reason, due_date,
                    priority_reason, assignee_role_id, created_by, updated_by,
                    linked_protocol, linked_blindspot, source_type, source_metadata_json,
                    context_summary, completed_by, confirmed_by_creator, rejection_reason,
                    project, product_id, attachments, completed_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7::jsonb, $8, $9,
                    $10, $11::jsonb, $12, $13,
                    $14, $15, $16, $17,
                    $18, $19, $20, $21::jsonb,
                    $22, $23, $24, $25,
                    $26, $27, $28::jsonb, $29
                )
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
                    priority_reason=EXCLUDED.priority_reason,
                    assignee_role_id=EXCLUDED.assignee_role_id,
                    created_by=EXCLUDED.created_by,
                    updated_by=EXCLUDED.updated_by,
                    linked_protocol=EXCLUDED.linked_protocol,
                    linked_blindspot=EXCLUDED.linked_blindspot,
                    source_type=EXCLUDED.source_type,
                    source_metadata_json=EXCLUDED.source_metadata_json,
                    context_summary=EXCLUDED.context_summary,
                    completed_by=EXCLUDED.completed_by,
                    confirmed_by_creator=EXCLUDED.confirmed_by_creator,
                    rejection_reason=EXCLUDED.rejection_reason,
                    project=EXCLUDED.project,
                    product_id=EXCLUDED.product_id,
                    attachments=EXCLUDED.attachments,
                    completed_at=EXCLUDED.completed_at
                """,
                pid,
                l3_task.id,
                l3_task.description,
                l3_task.task_status,
                l3_task.assignee,
                l3_task.dispatcher,
                _dumps(l3_task.acceptance_criteria),
                l3_task.priority,
                l3_task.result,
                l3_task.plan_order,
                _dumps(l3_task.depends_on),
                l3_task.blocked_reason,
                l3_task.due_date,
                task.priority_reason,
                task.assignee_role_id,
                task.created_by,
                task.updated_by,
                task.linked_protocol,
                task.linked_blindspot,
                task.source_type,
                _dumps(task.source_metadata),
                task.context_summary,
                task.completed_by,
                task.confirmed_by_creator,
                task.rejection_reason,
                task.project,
                task.product_id,
                _dumps(task.attachments),
                task.completed_at,
            )

    async def _sync_task_relationships(
        self, conn: asyncpg.Connection, task: Task, pid: str
    ) -> None:
        try:
            async with conn.transaction():
                await conn.execute(
                    f"""DELETE FROM {SCHEMA}.relationships
                        WHERE source_entity_id = $1 AND partner_id = $2
                        AND type = 'related_to'""",
                    task.id,
                    pid,
                )
                if task.linked_entities:
                    await conn.executemany(
                        f"""INSERT INTO {SCHEMA}.relationships (
                            id, partner_id, source_entity_id, target_entity_id,
                            type, description, confirmed_by_user, created_at, updated_at
                        ) VALUES ($1,$2,$3,$4,'related_to',$5,false,$6,$6)
                        ON CONFLICT (partner_id, source_entity_id, target_entity_id, type)
                        DO UPDATE SET description=EXCLUDED.description,
                                      updated_at=EXCLUDED.updated_at""",
                        [
                            (
                                _new_id(),
                                pid,
                                task.id,
                                eid,
                                f"Task '{task.title}' linked to entity '{eid}'",
                                task.updated_at,
                            )
                            for eid in task.linked_entities
                        ],
                    )
        except asyncpg.ForeignKeyViolationError:
            raise

    async def _sync_handoff_events(
        self, conn: asyncpg.Connection, task: Task, pid: str
    ) -> None:
        await conn.execute(
            f"DELETE FROM {SCHEMA}.task_handoff_events WHERE partner_id = $1 AND task_entity_id = $2",
            pid,
            task.id,
        )
        if not task.handoff_events:
            return
        await conn.executemany(
            f"""INSERT INTO {SCHEMA}.task_handoff_events (
                    partner_id, task_entity_id, from_dispatcher, to_dispatcher,
                    reason, notes, output_ref, created_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            [
                (
                    pid,
                    task.id,
                    event.from_dispatcher,
                    event.to_dispatcher,
                    event.reason,
                    event.notes,
                    event.output_ref,
                    event.at,
                )
                for event in task.handoff_events
            ],
        )

    def _l3_select(self) -> str:
        return f"""
            SELECT eb.id,
                   eb.partner_id,
                   eb.name AS title,
                   l3.description,
                   l3.task_status AS status,
                   l3.priority,
                   l3.assignee,
                   NULLIF(l3.dispatcher, 'human') AS dispatcher,
                   l3.acceptance_criteria_json,
                   l3.result,
                   l3.plan_order,
                   l3.depends_on_json AS depends_on_task_ids_json,
                   l3.blocked_reason,
                   l3.due_date,
                   eb.created_at,
                   eb.updated_at,
                   l3.priority_reason,
                   l3.assignee_role_id,
                   l3.created_by,
                   l3.updated_by,
                   CASE WHEN eb.type_label = 'task' AND parent.type_label = 'plan' THEN eb.parent_id ELSE NULL END AS plan_id,
                   l3.linked_protocol,
                   l3.linked_blindspot,
                   l3.source_type,
                   l3.source_metadata_json,
                   l3.context_summary,
                   l3.completed_by,
                   COALESCE(l3.confirmed_by_creator, false) AS confirmed_by_creator,
                   l3.rejection_reason,
                   l3.project,
                   l3.product_id,
                   l3.attachments,
                   CASE WHEN eb.type_label = 'subtask' THEN eb.parent_id ELSE NULL END AS parent_task_id,
                   COALESCE(handoff.events, '[]'::jsonb) AS handoff_events,
                   l3.completed_at,
                   COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, l3.created_by) as creator_name,
                   COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, l3.assignee) as assignee_name
            FROM {SCHEMA}.entities_base eb
            JOIN (
                SELECT partner_id, entity_id, description, task_status, assignee,
                       dispatcher, acceptance_criteria_json, priority, result,
                       plan_order, depends_on_json, blocked_reason, due_date,
                       priority_reason, assignee_role_id, created_by, updated_by,
                       linked_protocol, linked_blindspot, source_type, source_metadata_json,
                       context_summary, completed_by, confirmed_by_creator, rejection_reason,
                       project, product_id, attachments, completed_at
                FROM {SCHEMA}.entity_l3_task
                UNION ALL
                SELECT partner_id, entity_id, description, task_status, assignee,
                       dispatcher, acceptance_criteria_json, priority, result,
                       plan_order, depends_on_json, blocked_reason, due_date,
                       priority_reason, assignee_role_id, created_by, updated_by,
                       linked_protocol, linked_blindspot, source_type, source_metadata_json,
                       context_summary, completed_by, confirmed_by_creator, rejection_reason,
                       project, product_id, attachments, completed_at
                FROM {SCHEMA}.entity_l3_subtask
            ) l3
              ON eb.partner_id = l3.partner_id AND eb.id = l3.entity_id
            LEFT JOIN {SCHEMA}.entities_base parent
              ON eb.partner_id = parent.partner_id AND eb.parent_id = parent.id
            LEFT JOIN LATERAL (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'at', e.created_at,
                        'from_dispatcher', e.from_dispatcher,
                        'to_dispatcher', e.to_dispatcher,
                        'reason', e.reason,
                        'notes', e.notes,
                        'output_ref', e.output_ref
                    )
                    ORDER BY e.created_at
                ) AS events
                FROM {SCHEMA}.task_handoff_events e
                WHERE e.partner_id = eb.partner_id AND e.task_entity_id = eb.id
            ) handoff ON true
            LEFT JOIN {SCHEMA}.partners p1 ON l3.created_by = p1.id
            LEFT JOIN {SCHEMA}.partners p2 ON l3.assignee = p2.id
        """

    async def get_by_id(self, task_id: str) -> Task | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"{self._l3_select()} WHERE eb.id = $1 AND eb.partner_id = $2",
                task_id,
                pid,
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, task_id, pid)
        return _row_to_task_from_l3(row, linked_entities, blocked_by)

    async def find_by_id_prefix(
        self, prefix: str, partner_id: str, limit: int = 11
    ) -> list[Task]:
        """Return tasks whose id starts with prefix, scoped to partner_id.

        limit=11 lets the caller distinguish "exactly 10" from "more than 10"
        (SPEC-mcp-id-ergonomics AC-MIDE-03/04).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"{self._l3_select()}"
                f" WHERE eb.id LIKE $1 || '%' AND eb.partner_id = $2"
                f" ORDER BY eb.id LIMIT $3",
                prefix,
                partner_id,
                limit,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, partner_id)
        return self._rows_to_tasks_from_l3(rows, linked_map, blocker_map)

    async def upsert(self, task: Task, *, conn: asyncpg.Connection | None = None) -> Task:
        pid = _get_partner_id()
        now = _now()
        task.updated_at = now
        if task.id is None:
            task.id = _new_id()
            task.created_at = now

        async with _acquire_with_tx(self._pool, conn) as _conn:
            await self._upsert_l3_task(_conn, task, pid)
            await self._sync_handoff_events(_conn, task, pid)
            await self._sync_task_relationships(_conn, task, pid)
        return task

    async def find_task_by_attachment_id(self, attachment_id: str) -> Task | None:
        """Find a task containing an attachment with the given ID."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT *
                    FROM ({self._l3_select()}) l3_rows
                    WHERE l3_rows.partner_id = $1
                      AND l3_rows.attachments @> $2::jsonb""",
                pid, json.dumps([{"id": attachment_id}]),
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, row["id"], pid)
        return _row_to_task_from_l3(row, linked_entities, blocked_by)

    async def list_all(
        self,
        *,
        assignee: str | None = None,
        created_by: str | None = None,
        status: list[str] | None = None,
        priority: str | None = None,
        linked_entity: str | None = None,
        dispatcher: str | None = None,
        parent_task_id: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
        project: str | None = None,
        product_id: str | None = None,
        plan_id: str | None = None,
    ) -> list[Task]:
        pid = _get_partner_id()

        status_expr = "l3_rows.status"
        priority_expr = "l3_rows.priority"
        assignee_expr = "l3_rows.assignee"
        dispatcher_expr = "l3_rows.dispatcher"
        created_by_expr = "l3_rows.created_by"
        parent_task_expr = "l3_rows.parent_task_id"
        project_expr = "l3_rows.project"
        product_expr = "l3_rows.product_id"
        plan_expr = "l3_rows.plan_id"
        created_at_expr = "l3_rows.created_at"
        updated_at_expr = "l3_rows.updated_at"

        conditions = ["l3_rows.partner_id = $1"]
        params: list[Any] = [pid]
        idx = 2

        if assignee is not None:
            conditions.append(f"{assignee_expr} = ${idx}")
            params.append(assignee)
            idx += 1
        if created_by is not None:
            conditions.append(f"{created_by_expr} = ${idx}")
            params.append(created_by)
            idx += 1
        if priority is not None:
            conditions.append(f"{priority_expr} = ${idx}")
            params.append(priority)
            idx += 1
        if dispatcher is not None:
            conditions.append(f"{dispatcher_expr} = ${idx}")
            params.append(dispatcher)
            idx += 1
        if parent_task_id is not None:
            conditions.append(f"{parent_task_expr} = ${idx}")
            params.append(parent_task_id)
            idx += 1
        if project is not None:
            conditions.append(
                f"(LOWER(BTRIM(COALESCE({project_expr}, ''))) = LOWER(BTRIM(${idx})) OR {product_expr} = ${idx})"
            )
            params.append(str(project).strip())
            idx += 1
        if product_id is not None:
            conditions.append(f"{product_expr} = ${idx}")
            params.append(product_id)
            idx += 1
        if plan_id is not None:
            conditions.append(f"{plan_expr} = ${idx}")
            params.append(plan_id)
            idx += 1
        # Track whether caller explicitly filtered by status
        explicit_status_filter = status is not None

        if status is not None:
            normalized = []
            for s in status:
                mapped = {"backlog": "todo", "blocked": "todo", "archived": "done"}.get(s, s)
                if mapped not in normalized:
                    normalized.append(mapped)
            status = normalized
            placeholders = ", ".join(f"${i}" for i in range(idx, idx + len(status)))
            conditions.append(f"{status_expr} IN ({placeholders})")
            params.extend(status)
            idx += len(status)
        elif not include_archived:
            conditions.append(f"{status_expr} <> 'archived'")

        where_clause = " AND ".join(conditions)

        if linked_entity is not None:
            join_clause = (
                f"JOIN {SCHEMA}.relationships rel "
                f"ON l3_rows.id = rel.source_entity_id "
                f"AND rel.target_entity_id = ${idx} "
                f"AND rel.type = 'related_to'"
            )
            params.append(linked_entity)
            idx += 1
        else:
            join_clause = ""

        select_cols = "DISTINCT l3_rows.*"
        from_clause = f"({self._l3_select()}) l3_rows {join_clause}"

        # Build LIMIT/OFFSET clause
        limit_idx = idx
        params.append(limit)
        idx += 1
        offset_idx = idx
        params.append(offset)
        idx += 1

        if not explicit_status_filter:
            # Split query: active tickets unlimited (up to limit), done/cancelled capped at 5 each
            active_where = f"{where_clause} AND l3_rows.status NOT IN ('done', 'cancelled')"
            done_where = f"{where_clause} AND l3_rows.status = 'done'"
            cancelled_where = f"{where_clause} AND l3_rows.status = 'cancelled'"
            sql = (
                f"SELECT * FROM ("
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {active_where} ORDER BY {created_at_expr} DESC LIMIT ${limit_idx} OFFSET ${offset_idx})"
                f"  UNION ALL"
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {done_where} ORDER BY {updated_at_expr} DESC LIMIT 5)"
                f"  UNION ALL"
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {cancelled_where} ORDER BY {updated_at_expr} DESC LIMIT 5)"
                f") combined ORDER BY created_at DESC"
            )
        else:
            sql = (
                f"SELECT {select_cols} "
                f"FROM {from_clause} "
                f"WHERE {where_clause} ORDER BY {created_at_expr} DESC LIMIT ${limit_idx} OFFSET ${offset_idx}"
            )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks_from_l3(rows, linked_map, blocker_map)

    async def list_blocked_by(self, task_id: str) -> list[Task]:
        """Return all tasks that are blocked by the given task_id."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT DISTINCT l3_rows.*
                    FROM ({self._l3_select()}) l3_rows
                    WHERE l3_rows.partner_id = $2
                      AND l3_rows.depends_on_task_ids_json ? $1""",
                task_id, pid,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks_from_l3(rows, linked_map, blocker_map)

    async def list_pending_review(self) -> list[Task]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM ({self._l3_select()}) l3_rows
                    WHERE status = 'review' AND confirmed_by_creator = false
                    AND partner_id = $1""",
                pid,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks_from_l3(rows, linked_map, blocker_map)


class PostgresTaskCommentRepository:
    """CRUD operations for task comments."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, task_id: str, partner_id: str, content: str) -> dict:
        """Create a comment and return its dict representation, including author_name."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""INSERT INTO {SCHEMA}.task_comments (task_id, partner_id, content)
                    VALUES ($1, $2, $3)
                    RETURNING id, task_id, partner_id, content, created_at""",
                task_id, partner_id, content,
            )
            author_row = await conn.fetchrow(
                f"SELECT display_name FROM {SCHEMA}.partners WHERE id = $1",
                partner_id,
            )
        return {
            "id": str(row["id"]),
            "task_id": str(row["task_id"]),
            "partner_id": row["partner_id"],
            "content": row["content"],
            "created_at": row["created_at"].isoformat(),
            "author_name": author_row["display_name"] if author_row else partner_id,
        }

    async def list_by_task(self, task_id: str) -> list[dict]:
        """Return all comments for a task, joined with partner display name, oldest-first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT c.id, c.task_id, c.partner_id, c.content, c.created_at,
                           COALESCE(NULLIF(p.display_name, ''), p.email, c.partner_id) AS author_name
                    FROM {SCHEMA}.task_comments c
                    LEFT JOIN {SCHEMA}.partners p ON c.partner_id = p.id
                    WHERE c.task_id = $1
                    ORDER BY c.created_at ASC""",
                task_id,
            )
        return [
            {
                "id": str(r["id"]),
                "task_id": str(r["task_id"]),
                "partner_id": r["partner_id"],
                "content": r["content"],
                "author_name": r["author_name"] or r["partner_id"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def get_by_id(self, comment_id: str) -> dict | None:
        """Return a single comment dict (includes partner_id for auth checks), or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT id, task_id, partner_id, content, created_at
                    FROM {SCHEMA}.task_comments
                    WHERE id = $1""",
                comment_id,
            )
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "task_id": str(row["task_id"]),
            "partner_id": row["partner_id"],
            "content": row["content"],
            "created_at": row["created_at"].isoformat(),
        }

    async def delete(self, comment_id: str) -> bool:
        """Delete a comment. Returns True if a row was deleted."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {SCHEMA}.task_comments WHERE id = $1",
                comment_id,
            )
        # asyncpg execute returns "DELETE N" where N is row count
        return result == "DELETE 1"
