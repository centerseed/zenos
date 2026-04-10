"""PostgreSQL-backed TaskRepository and PostgresTaskCommentRepository."""

from __future__ import annotations

import json
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.action import Task
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


def _row_to_task(row: asyncpg.Record, linked_entities: list[str], blocked_by: list[str]) -> Task:
    plan_id = row["plan_id"] if "plan_id" in row else None
    plan_order = row["plan_order"] if "plan_order" in row else None
    depends_json = row["depends_on_task_ids_json"] if "depends_on_task_ids_json" in row else None
    source_metadata_json = row["source_metadata_json"] if "source_metadata_json" in row else None
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
        project_id=row["project_id"] if "project_id" in row else None,
        attachments=_json_loads_safe(row["attachments"] if "attachments" in row else None) or [],
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
        completed_at=_to_dt(row["completed_at"]),
    )


class SqlTaskRepository:
    """PostgreSQL-backed TaskRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_task_relations(
        self, conn: asyncpg.Connection, task_id: str, pid: str,
    ) -> tuple[list[str], list[str]]:
        entity_rows = await conn.fetch(
            f"SELECT entity_id FROM {SCHEMA}.task_entities WHERE task_id = $1 AND partner_id = $2",
            task_id, pid,
        )
        blocker_rows = await conn.fetch(
            f"SELECT blocker_task_id FROM {SCHEMA}.task_blockers WHERE task_id = $1 AND partner_id = $2",
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
            f"SELECT task_id, entity_id FROM {SCHEMA}.task_entities"
            f" WHERE partner_id = $1 AND task_id = ANY($2::text[])",
            pid, task_ids,
        )
        blocker_rows = await conn.fetch(
            f"SELECT task_id, blocker_task_id FROM {SCHEMA}.task_blockers"
            f" WHERE partner_id = $1 AND task_id = ANY($2::text[])",
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

    async def get_by_id(self, task_id: str) -> Task | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT t.*,
                           COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, t.created_by) as creator_name,
                           COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, t.assignee) as assignee_name
                    FROM {SCHEMA}.tasks t
                    LEFT JOIN {SCHEMA}.partners p1 ON t.created_by = p1.id
                    LEFT JOIN {SCHEMA}.partners p2 ON t.assignee = p2.id
                    WHERE t.id = $1 AND t.partner_id = $2""",
                task_id, pid,
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, task_id, pid)
        return _row_to_task(row, linked_entities, blocked_by)

    async def upsert(self, task: Task, *, conn: asyncpg.Connection | None = None) -> Task:
        pid = _get_partner_id()
        now = _now()
        task.updated_at = now
        if task.id is None:
            task.id = _new_id()
            task.created_at = now

        async with _acquire_with_tx(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.tasks (
                    id, partner_id, title, description, status, priority,
                    priority_reason, assignee, assignee_role_id, created_by, updated_by,
                    plan_id, plan_order, depends_on_task_ids_json,
                    linked_protocol, linked_blindspot, source_type, source_metadata_json, context_summary,
                    due_date, blocked_reason, acceptance_criteria_json, completed_by,
                    confirmed_by_creator, rejection_reason, result, project, project_id,
                    attachments,
                    created_at, updated_at, completed_at
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
                    $12,$13,$14::jsonb,$15,$16,$17,$18::jsonb,$19,$20,$21,$22::jsonb,$23,$24,$25,$26,$27,$28,
                    $29::jsonb,
                    $30,$31,$32
                )
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title, description=EXCLUDED.description,
                    status=EXCLUDED.status, priority=EXCLUDED.priority,
                    priority_reason=EXCLUDED.priority_reason,
                    assignee=EXCLUDED.assignee,
                    assignee_role_id=EXCLUDED.assignee_role_id,
                    updated_by=EXCLUDED.updated_by,
                    plan_id=EXCLUDED.plan_id,
                    plan_order=EXCLUDED.plan_order,
                    depends_on_task_ids_json=EXCLUDED.depends_on_task_ids_json,
                    linked_protocol=EXCLUDED.linked_protocol,
                    linked_blindspot=EXCLUDED.linked_blindspot,
                    source_type=EXCLUDED.source_type,
                    source_metadata_json=EXCLUDED.source_metadata_json,
                    context_summary=EXCLUDED.context_summary,
                    due_date=EXCLUDED.due_date,
                    blocked_reason=EXCLUDED.blocked_reason,
                    acceptance_criteria_json=EXCLUDED.acceptance_criteria_json,
                    completed_by=EXCLUDED.completed_by,
                    confirmed_by_creator=EXCLUDED.confirmed_by_creator,
                    rejection_reason=EXCLUDED.rejection_reason,
                    result=EXCLUDED.result, project=EXCLUDED.project,
                    project_id=EXCLUDED.project_id,
                    attachments=EXCLUDED.attachments,
                    updated_at=EXCLUDED.updated_at,
                    completed_at=EXCLUDED.completed_at
                WHERE tasks.partner_id = EXCLUDED.partner_id
                """,
                task.id, pid, task.title, task.description, task.status,
                task.priority, task.priority_reason, task.assignee,
                task.assignee_role_id, task.created_by, task.updated_by,
                task.plan_id, task.plan_order, _dumps(task.depends_on_task_ids),
                task.linked_protocol, task.linked_blindspot,
                task.source_type, _dumps(task.source_metadata), task.context_summary, task.due_date,
                task.blocked_reason, _dumps(task.acceptance_criteria),
                task.completed_by, task.confirmed_by_creator,
                task.rejection_reason, task.result, task.project, task.project_id,
                _dumps(task.attachments),
                task.created_at, task.updated_at, task.completed_at,
            )
            # Sync task_entities join table
            await _conn.execute(
                f"DELETE FROM {SCHEMA}.task_entities WHERE task_id = $1 AND partner_id = $2",
                task.id, pid,
            )
            if task.linked_entities:
                await _conn.executemany(
                    f"INSERT INTO {SCHEMA}.task_entities (task_id, entity_id, partner_id)"
                    f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    [(task.id, eid, pid) for eid in task.linked_entities],
                )
            # Sync task_blockers join table
            await _conn.execute(
                f"DELETE FROM {SCHEMA}.task_blockers WHERE task_id = $1 AND partner_id = $2",
                task.id, pid,
            )
            if task.blocked_by:
                await _conn.executemany(
                    f"INSERT INTO {SCHEMA}.task_blockers (task_id, blocker_task_id, partner_id)"
                    f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    [(task.id, bid, pid) for bid in task.blocked_by],
                )
        return task

    async def find_task_by_attachment_id(self, attachment_id: str) -> Task | None:
        """Find a task containing an attachment with the given ID."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT t.*,
                           COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, t.created_by) as creator_name,
                           COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, t.assignee) as assignee_name
                    FROM {SCHEMA}.tasks t
                    LEFT JOIN {SCHEMA}.partners p1 ON t.created_by = p1.id
                    LEFT JOIN {SCHEMA}.partners p2 ON t.assignee = p2.id
                    WHERE t.partner_id = $1
                      AND t.attachments @> $2::jsonb""",
                pid, json.dumps([{"id": attachment_id}]),
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, row["id"], pid)
        return _row_to_task(row, linked_entities, blocked_by)

    async def list_all(
        self,
        *,
        assignee: str | None = None,
        created_by: str | None = None,
        status: list[str] | None = None,
        priority: str | None = None,
        linked_entity: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
        project: str | None = None,
        plan_id: str | None = None,
    ) -> list[Task]:
        pid = _get_partner_id()

        conditions = ["t.partner_id = $1"]
        params: list[Any] = [pid]
        idx = 2

        if assignee is not None:
            conditions.append(f"t.assignee = ${idx}")
            params.append(assignee)
            idx += 1
        if created_by is not None:
            conditions.append(f"t.created_by = ${idx}")
            params.append(created_by)
            idx += 1
        if priority is not None:
            conditions.append(f"t.priority = ${idx}")
            params.append(priority)
            idx += 1
        if project is not None:
            conditions.append(f"t.project = ${idx}")
            params.append(project)
            idx += 1
        if plan_id is not None:
            conditions.append(f"t.plan_id = ${idx}")
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
            conditions.append(f"t.status IN ({placeholders})")
            params.extend(status)
            idx += len(status)
        elif not include_archived:
            conditions.append("t.status <> 'archived'")

        where_clause = " AND ".join(conditions)

        if linked_entity is not None:
            join_clause = f"JOIN {SCHEMA}.task_entities te ON t.id = te.task_id AND te.entity_id = ${idx}"
            params.append(linked_entity)
            idx += 1
        else:
            join_clause = ""

        select_cols = (
            f"DISTINCT t.*, "
            f"COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, t.created_by) as creator_name, "
            f"COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, t.assignee) as assignee_name"
        )
        from_clause = (
            f"{SCHEMA}.tasks t "
            f"{join_clause} "
            f"LEFT JOIN {SCHEMA}.partners p1 ON t.created_by = p1.id "
            f"LEFT JOIN {SCHEMA}.partners p2 ON t.assignee = p2.id"
        )

        # Build LIMIT/OFFSET clause
        limit_idx = idx
        params.append(limit)
        idx += 1
        offset_idx = idx
        params.append(offset)
        idx += 1

        if not explicit_status_filter:
            # Split query: active tickets unlimited (up to limit), done/cancelled capped at 5 each
            active_where = f"{where_clause} AND t.status NOT IN ('done', 'cancelled')"
            done_where = f"{where_clause} AND t.status = 'done'"
            cancelled_where = f"{where_clause} AND t.status = 'cancelled'"
            sql = (
                f"SELECT * FROM ("
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {active_where} ORDER BY t.created_at DESC LIMIT ${limit_idx} OFFSET ${offset_idx})"
                f"  UNION ALL"
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {done_where} ORDER BY t.updated_at DESC LIMIT 5)"
                f"  UNION ALL"
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {cancelled_where} ORDER BY t.updated_at DESC LIMIT 5)"
                f") combined ORDER BY created_at DESC"
            )
        else:
            sql = (
                f"SELECT {select_cols} "
                f"FROM {from_clause} "
                f"WHERE {where_clause} ORDER BY t.created_at DESC LIMIT ${limit_idx} OFFSET ${offset_idx}"
            )

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks(rows, linked_map, blocker_map)

    async def list_blocked_by(self, task_id: str) -> list[Task]:
        """Return all tasks that are blocked by the given task_id."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT DISTINCT t.* FROM {SCHEMA}.tasks t
                    JOIN {SCHEMA}.task_blockers tb ON t.id = tb.task_id
                    WHERE tb.blocker_task_id = $1 AND t.partner_id = $2""",
                task_id, pid,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks(rows, linked_map, blocker_map)

    async def list_pending_review(self) -> list[Task]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {SCHEMA}.tasks
                    WHERE status = 'review' AND confirmed_by_creator = false
                    AND partner_id = $1""",
                pid,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks(rows, linked_map, blocker_map)


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
