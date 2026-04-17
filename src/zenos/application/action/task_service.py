"""TaskService — orchestrates Action Layer use cases.

Handles task CRUD, state validation, priority recommendation,
context assembly, and cascade unblocking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from zenos.domain.action import Task, TaskPriority, TaskStatus
from zenos.domain.knowledge import Blindspot, EntityType
from zenos.domain.action import TaskRepository
from zenos.domain.action.repositories import PlanRepository
from zenos.domain.knowledge import BlindspotRepository, EntityRepository
from zenos.domain.validation import validate_task_title
from zenos.domain.task_rules import (
    is_valid_initial_status,
    is_valid_transition,
    is_valid_update_target,
    normalize_task_status,
    recommend_priority,
)


def _normalize_project_scope(value: object) -> str:
    """Normalize partner-level project scope strings for stable storage/filtering."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _parse_due_date(value: object) -> datetime | None:
    """Convert a due_date value to a timezone-aware datetime or None.

    Accepts:
    - None / empty string → None
    - datetime (already correct) → unchanged
    - ISO date string "YYYY-MM-DD" → midnight UTC datetime
    - ISO datetime string → parsed and made UTC-aware
    """
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Date-only "YYYY-MM-DD"
        if len(raw) == 10 and raw[4] == "-":
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Try full ISO format (may include T and Z/offset)
        raw_normalized = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw_normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


@dataclass
class CascadeUpdate:
    """Record of a cascade status change triggered by unblocking."""
    task_id: str
    change: str
    reason: str


@dataclass
class TaskResult:
    """Result of a task mutation, including any cascade side-effects."""
    task: Task
    cascade_updates: list[CascadeUpdate]
    suggested_entity_updates: list[dict] | None = None


class TaskService:
    """Application-layer service for Action Layer tasks."""

    def __init__(
        self,
        task_repo: TaskRepository,
        entity_repo: EntityRepository,
        blindspot_repo: BlindspotRepository,
        document_repo: object | None = None,  # deprecated, kept for backward compat
        governance_ai: object | None = None,
        relationship_repo: object | None = None,
        uow_factory: Any | None = None,
        plan_repo: PlanRepository | None = None,
    ) -> None:
        self._tasks = task_repo
        self._entities = entity_repo
        self._blindspots = blindspot_repo
        self._governance_ai = governance_ai
        self._relationships = relationship_repo
        self._uow_factory = uow_factory
        self._plans = plan_repo

    # ──────────────────────────────────────────
    # Create
    # ──────────────────────────────────────────

    async def create_task(self, data: dict, *, conn: Any | None = None) -> TaskResult:
        """Create a new task with priority recommendation and context assembly."""
        # Governance validation: task title
        title_errors, _ = validate_task_title(data.get("title", ""))
        if title_errors:
            raise ValueError("Task title 驗證失敗: " + "; ".join(title_errors))

        # Priority enum validation
        priority_val = data.get("priority")
        if priority_val:
            valid_priorities = [p.value for p in TaskPriority]
            if priority_val not in valid_priorities:
                raise ValueError(
                    f"Invalid priority '{priority_val}'. "
                    f"Must be one of: {', '.join(valid_priorities)}"
                )

        status = normalize_task_status(data.get("status", TaskStatus.TODO))
        if not is_valid_initial_status(status):
            raise ValueError(
                f"Invalid initial status '{status}'. Must be 'todo'."
            )

        # Build linked context for priority recommendation
        linked_entity_ids = data.get("linked_entities", [])

        # GovernanceAI: auto-infer entity links if none provided
        if not linked_entity_ids and self._governance_ai:
            all_entities = await self._entities.list_all()
            if all_entities:
                entity_dicts = [
                    {
                        "id": e.id, "name": e.name, "type": e.type,
                    }
                    for e in all_entities
                ]
                linked_entity_ids = self._governance_ai.infer_task_links(
                    title=data.get("title", ""),
                    description=data.get("description", ""),
                    existing_entities=entity_dicts,
                )

        linked_entities = []
        missing_ids = []
        for eid in linked_entity_ids:
            entity = await self._entities.get_by_id(eid)
            if entity:
                linked_entities.append(entity)
            else:
                missing_ids.append(eid)
        if missing_ids:
            raise ValueError(
                f"linked_entities 包含不存在的 entity ID: {', '.join(missing_ids)}。"
                f"請先建立這些 entity 或移除無效 ID。"
            )

        linked_blindspot_id = data.get("linked_blindspot")
        linked_blindspot = None
        if linked_blindspot_id:
            linked_blindspot = await self._blindspots.get_by_id(linked_blindspot_id)

        blocked_by = data.get("blocked_by", [])
        blocked_reason = data.get("blocked_reason")
        if blocked_by and not blocked_reason:
            raise ValueError("blocked_reason is required when blocked_by is set")
        plan_id = data.get("plan_id")
        plan_order = data.get("plan_order")
        depends_on_task_ids = data.get("depends_on_task_ids", [])

        if plan_order is not None and not plan_id:
            raise ValueError("plan_id is required when plan_order is provided")
        if plan_order is not None and int(plan_order) < 1:
            raise ValueError("plan_order must be >= 1")
        if plan_id and self._plans is not None:
            existing_plan = await self._plans.get_by_id(plan_id)
            if existing_plan is None:
                raise ValueError(
                    f"plan_id '{plan_id}' does not exist. Create the plan first."
                )

        # Priority recommendation
        due_date = _parse_due_date(data.get("due_date"))
        rec_priority, priority_reason = recommend_priority(
            linked_entities=linked_entities,
            linked_blindspot=linked_blindspot,
            due_date=due_date,
            blocked_by_count=len(blocked_by),
            blocking_others_count=0,
        )

        # Caller-provided priority overrides recommendation
        priority = data.get("priority") or rec_priority

        # Context summary assembly — preserve manual value if provided
        manual_context = data.get("context_summary", "")
        if manual_context:
            context_summary = manual_context
        else:
            context_summary = await self._assemble_context(
                linked_entities, linked_blindspot
            )

        task = Task(
            title=data["title"],
            description=data.get("description") or "",
            status=status,
            priority=priority,
            priority_reason=priority_reason,
            assignee=data.get("assignee") or None,
            assignee_role_id=data.get("assignee_role_id") or None,
            plan_id=plan_id,
            plan_order=int(plan_order) if plan_order is not None else None,
            depends_on_task_ids=depends_on_task_ids,
            created_by=data["created_by"],
            updated_by=data.get("updated_by") or data["created_by"],
            linked_entities=linked_entity_ids,
            linked_protocol=data.get("linked_protocol") or None,
            linked_blindspot=linked_blindspot_id,
            source_type=data.get("source_type") or "",
            source_metadata=data.get("source_metadata") or {},
            context_summary=context_summary,
            due_date=due_date,
            blocked_by=blocked_by,
            blocked_reason=blocked_reason,
            acceptance_criteria=data.get("acceptance_criteria") or [],
            project=_normalize_project_scope(data.get("project")),
            attachments=data.get("attachments") or [],
        )

        if conn is None:
            saved = await self._tasks.upsert(task)
        else:
            # SQL repositories support conn-scoped writes for cross-repo atomicity.
            try:
                saved = await self._tasks.upsert(task, conn=conn)
            except TypeError:
                saved = await self._tasks.upsert(task)
        return TaskResult(task=saved, cascade_updates=[])

    # ──────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────

    async def update_task(self, task_id: str, updates: dict) -> TaskResult:
        """Update a task with state validation and cascade unblocking."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        task.status = normalize_task_status(task.status)

        new_status = normalize_task_status(updates.get("status")) if updates.get("status") else None
        cascades: list[CascadeUpdate] = []

        # Status transition validation
        if new_status and new_status != task.status:
            if not is_valid_update_target(new_status):
                raise ValueError(
                    f"Cannot set status to '{new_status}' via update. "
                    f"Use confirm to accept/reject tasks in review."
                )
            if not is_valid_transition(task.status, new_status):
                raise ValueError(
                    f"Invalid transition: {task.status} → {new_status}"
                )
            if new_status == TaskStatus.REVIEW and not (
                updates.get("result") or task.result
            ):
                raise ValueError("result is required when status is 'review'")

            task.status = new_status

            # Auto-advance plan draft → active when a task becomes in_progress
            if new_status == TaskStatus.IN_PROGRESS and task.plan_id and self._plans is not None:
                plan = await self._plans.get_by_id(task.plan_id)
                if plan is not None and plan.status == "draft":
                    plan.status = "active"
                    plan.updated_at = datetime.utcnow()
                    await self._plans.upsert(plan)

            # Cascade unblocking when done or cancelled
            if new_status in (TaskStatus.DONE, TaskStatus.CANCELLED):
                cascades = await self._cascade_unblock(task_id)
                if new_status == TaskStatus.DONE:
                    task.completed_at = datetime.utcnow()

        # Apply other field updates
        for field in (
            "assignee", "priority", "description", "blocked_reason",
            "result", "acceptance_criteria", "blocked_by",
            "plan_id", "plan_order", "depends_on_task_ids", "source_metadata",
            "updated_by", "project", "linked_entities", "attachments",
        ):
            if field in updates:
                setattr(task, field, updates[field])
        if "due_date" in updates:
            task.due_date = _parse_due_date(updates["due_date"])

        if task.plan_order is not None and not task.plan_id:
            raise ValueError("plan_id is required when plan_order is provided")
        if task.plan_order is not None and int(task.plan_order) < 1:
            raise ValueError("plan_order must be >= 1")

        task.updated_at = datetime.utcnow()
        saved = await self._tasks.upsert(task)
        return TaskResult(task=saved, cascade_updates=cascades)

    # ──────────────────────────────────────────
    # Confirm (accept / reject)
    # ──────────────────────────────────────────

    async def confirm_task(
        self,
        task_id: str,
        accepted: bool,
        rejection_reason: str | None = None,
        mark_stale_entity_ids: list[str] | None = None,
        new_blindspot: dict | None = None,
        updated_by: str | None = None,
        entity_entries: list[dict] | None = None,
    ) -> TaskResult:
        """Accept or reject a task in review status."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        task.status = normalize_task_status(task.status)
        if task.status != TaskStatus.REVIEW:
            raise ValueError(
                f"Can only confirm tasks in 'review' status. "
                f"Current status: '{task.status}'"
            )

        cascades: list[CascadeUpdate] = []

        if accepted:
            async with self._uow_factory() as uow:
                task.status = TaskStatus.DONE
                task.confirmed_by_creator = True
                task.completed_at = datetime.utcnow()
                cascades = await self._cascade_unblock(task_id, conn=uow.conn)

                # Phase 1: feedback engine (batch to avoid N+1)
                suggested_entity_updates: list[dict] = []
                if task.linked_entities and self._relationships:
                    all_rels = await asyncio.gather(
                        *[self._relationships.list_by_entity(eid) for eid in task.linked_entities]
                    )
                    target_ids = list({
                        rel.target_id
                        for rels in all_rels for rel in rels
                        if rel.type in ("impacts", "depends_on")
                    })
                    if target_ids:
                        targets = await self._entities.list_by_ids(target_ids)
                        for t in targets:
                            suggested_entity_updates.append({
                                "entity_id": t.id,
                                "entity_name": t.name,
                                "reason": f"任務 '{task.title}' 完成後，相關 entity '{t.name}' 可能需要更新",
                            })

                # Resolve linked blindspot if present
                if task.linked_blindspot:
                    bs = await self._blindspots.get_by_id(task.linked_blindspot)
                    if bs and bs.status != "resolved":
                        bs.status = "resolved"
                        await self._blindspots.add(bs, conn=uow.conn)

                # Mark related document entities as stale when entities are outdated
                if mark_stale_entity_ids:
                    for eid in mark_stale_entity_ids:
                        child_entities = await self._entities.list_by_parent(eid)
                        for child in child_entities:
                            if child.type == EntityType.DOCUMENT and child.status != "stale":
                                child.status = "stale"
                                await self._entities.upsert(child, conn=uow.conn)

                # Create new blindspot discovered during task completion
                if new_blindspot:
                    bs_obj = Blindspot(
                        description=new_blindspot.get("description", ""),
                        severity=new_blindspot.get("severity", "yellow"),
                        related_entity_ids=new_blindspot.get("related_entity_ids", []),
                        suggested_action=new_blindspot.get("suggested_action", ""),
                        confirmed_by_user=False,
                    )
                    await self._blindspots.add(bs_obj, conn=uow.conn)

                task.updated_at = datetime.utcnow()
                if updated_by:
                    task.updated_by = updated_by
                saved = await self._tasks.upsert(task, conn=uow.conn)
            return TaskResult(task=saved, cascade_updates=cascades, suggested_entity_updates=suggested_entity_updates)
        else:
            if not rejection_reason:
                raise ValueError("rejection_reason is required when rejecting")
            task.status = TaskStatus.IN_PROGRESS
            task.confirmed_by_creator = False
            task.rejection_reason = rejection_reason

            task.updated_at = datetime.utcnow()
            if updated_by:
                task.updated_by = updated_by
            saved = await self._tasks.upsert(task)
            return TaskResult(task=saved, cascade_updates=cascades, suggested_entity_updates=[])

    # ──────────────────────────────────────────
    # List
    # ──────────────────────────────────────────

    async def list_tasks(
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
        """List tasks with filters. Delegates to repository."""
        return await self._tasks.list_all(
            assignee=assignee,
            created_by=created_by,
            status=status,
            priority=priority,
            linked_entity=linked_entity,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
            project=project,
            plan_id=plan_id,
        )

    async def list_pending_review(self) -> list[Task]:
        """List tasks awaiting creator confirmation."""
        return await self._tasks.list_pending_review()

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    async def _cascade_unblock(
        self,
        completed_task_id: str,
        *,
        conn: object | None = None,
    ) -> list[CascadeUpdate]:
        """When a task completes, unblock tasks that were waiting for it."""
        blocked_tasks = await self._tasks.list_blocked_by(completed_task_id)
        cascades: list[CascadeUpdate] = []

        for bt in blocked_tasks:
            bt.status = normalize_task_status(bt.status)
            bt.blocked_by = [
                tid for tid in bt.blocked_by if tid != completed_task_id
            ]
            if not bt.blocked_by and bt.status == TaskStatus.IN_PROGRESS:
                bt.blocked_reason = None
                bt.updated_at = datetime.utcnow()
                await self._tasks.upsert(bt, conn=conn)
                cascades.append(CascadeUpdate(
                    task_id=bt.id or "",
                    change="in_progress (unblocked)",
                    reason=f"blockedBy {completed_task_id} 已完成",
                ))
            else:
                # Still blocked by other tasks, just remove the completed one
                bt.updated_at = datetime.utcnow()
                await self._tasks.upsert(bt, conn=conn)

        return cascades

    async def _assemble_context(self, linked_entities, linked_blindspot) -> str:
        """Build a concise context summary from ontology references."""
        parts: list[str] = []

        if linked_entities:
            node_summaries = [
                f"{e.name} — {e.summary[:60]}" for e in linked_entities[:3]
            ]
            parts.append(f"任務關聯節點：{'；'.join(node_summaries)}")

        if linked_blindspot:
            parts.append(
                f"觸發盲點：{linked_blindspot.description[:50]}"
            )

        return "。".join(parts) if parts else ""

    async def enrich_task(self, task: Task) -> dict:
        """Enrich a single task with expanded linked_entities/assignee_role/blindspot_detail.

        Returns enrichments dict:
          - expanded_entities: list of entity objects (id/name/summary/tags/status)
          - assignee_role: entity object or None (only present if assignee_role_id set)
          - blindspot_detail: blindspot detail dict (only present if linked_blindspot set)
        """
        enrichments: dict = {}

        # Expand linked_entities from IDs to objects
        expanded: list[dict] = []
        for eid in task.linked_entities:
            entity = await self._entities.get_by_id(eid)
            if entity:
                tags = entity.tags
                expanded.append({
                    "id": entity.id,
                    "name": entity.name,
                    "summary": entity.summary,
                    "tags": {
                        "what": tags.what,
                        "who": tags.who,
                        "why": tags.why,
                        "how": tags.how,
                    },
                    "status": entity.status,
                })
            else:
                expanded.append({"id": eid, "not_found": True})
        enrichments["expanded_entities"] = expanded

        # Expand assignee_role
        if task.assignee_role_id:
            role = await self._entities.get_by_id(task.assignee_role_id)
            enrichments["assignee_role"] = (
                {"id": role.id, "name": role.name, "summary": role.summary}
                if role else None
            )

        # Expand blindspot_detail
        if task.linked_blindspot:
            bs = await self._blindspots.get_by_id(task.linked_blindspot)
            if bs:
                enrichments["blindspot_detail"] = {
                    "description": bs.description,
                    "severity": bs.severity,
                    "suggested_action": bs.suggested_action,
                }

        return enrichments

    async def get_task_enriched(self, task_id: str) -> tuple[Task, dict] | None:
        """Get task with linked_entities/assignee_role/blindspot expanded.

        Returns (task, enrichments) where enrichments is a plain dict:
          - expanded_entities: list of entity objects (id/name/summary/tags/status)
          - assignee_role: entity object or None (only present if assignee_role_id set)
          - blindspot_detail: blindspot detail dict (only present if linked_blindspot set)
        """
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            return None
        enrichments = await self.enrich_task(task)
        return task, enrichments
