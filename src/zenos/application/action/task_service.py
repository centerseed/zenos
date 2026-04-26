"""TaskService — orchestrates Action Layer use cases.

Handles task CRUD, state validation, priority recommendation,
context assembly, and cascade unblocking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from zenos.domain.action import DISPATCHER_PATTERN, HandoffEvent, Task, TaskPriority, TaskStatus
from zenos.domain.action.models import L3TaskEntity
from zenos.domain.knowledge import Blindspot, EntityType
from zenos.domain.knowledge.collaboration_roots import is_collaboration_root_entity
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


class TaskValidationError(ValueError):
    """Validation error with a machine-readable error_code."""

    def __init__(self, message: str, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def _validate_action_parent_product_id(
    *,
    parent_kind: str,
    parent_id: str,
    parent_product_id: str | None,
) -> None:
    """Ensure an Action L3 parent chain can terminate at an L1 product root."""
    if not parent_product_id:
        raise TaskValidationError(
            f"{parent_kind} '{parent_id}' has no product_id; "
            "parent chain cannot terminate at an L1 collaboration root.",
            error_code="INVALID_PARENT_CHAIN",
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


async def _resolve_product_entity(
    entity_repo: EntityRepository,
    *,
    product_id: str | None,
    project_hint: str | None,
) -> Entity | None:
    """Resolve a canonical product entity from explicit product_id or project hint."""
    if product_id:
        entity = await entity_repo.get_by_id(product_id)
        if not is_collaboration_root_entity(entity):
            raise TaskValidationError(
                f"product_id '{product_id}' is invalid or not a collaboration root entity.",
                error_code="INVALID_PRODUCT_ID",
            )
        return entity

    if project_hint:
        entity = await entity_repo.get_by_name(str(project_hint).strip())
        if entity is not None:
            if not is_collaboration_root_entity(entity):
                raise TaskValidationError(
                    f"project '{project_hint}' resolved to non-collaboration-root entity '{entity.id}'.",
                    error_code="INVALID_PRODUCT_ID",
                )
            return entity
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
    warnings: list[str] | None = None


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

    async def _save_task(self, task: Task, *, conn: Any | None = None) -> Task:
        if conn is None:
            return await self._tasks.upsert(task)
        try:
            return await self._tasks.upsert(task, conn=conn)
        except TypeError:
            return await self._tasks.upsert(task)

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

        # Dispatcher namespace validation
        dispatcher = data.get("dispatcher")
        if dispatcher is not None and not DISPATCHER_PATTERN.match(dispatcher):
            raise TaskValidationError(
                f"dispatcher '{dispatcher}' does not match required namespace format "
                f"^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$",
                error_code="INVALID_DISPATCHER",
            )

        # project_id alias removed (ADR-047 D3). Callers must use product_id.
        product_entity = await _resolve_product_entity(
            self._entities,
            product_id=data.get("product_id"),
            project_hint=data.get("project"),
        )
        effective_product_id = product_entity.id if product_entity else None
        effective_project_name = product_entity.name if product_entity else None
        if effective_product_id is None:
            raise TaskValidationError(
                "product_id is required when project/defaultProject cannot be resolved to a product entity.",
                error_code="MISSING_PRODUCT_ID",
            )

        # Cross-plan subtask validation
        parent_task_id = data.get("parent_task_id")
        if parent_task_id is not None:
            parent = await self._tasks.get_by_id(parent_task_id)
            if parent is None:
                raise TaskValidationError(
                    f"parent_task_id '{parent_task_id}' does not exist.",
                    error_code="PARENT_NOT_FOUND",
                )
            if data.get("plan_id") and parent.plan_id != data.get("plan_id"):
                raise TaskValidationError(
                    f"Subtask plan_id '{data.get('plan_id')}' does not match "
                    f"parent task plan_id '{parent.plan_id}'. "
                    f"Subtasks must inherit the parent's plan_id.",
                    error_code="CROSS_PLAN_SUBTASK",
                )
            _validate_action_parent_product_id(
                parent_kind="parent_task_id",
                parent_id=parent_task_id,
                parent_product_id=parent.product_id,
            )
            if effective_product_id and parent.product_id and parent.product_id != effective_product_id:
                raise TaskValidationError(
                    f"Subtask product_id '{effective_product_id}' does not match "
                    f"parent task product_id '{parent.product_id}'.",
                    error_code="CROSS_PRODUCT_SUBTASK",
                )

        # Build linked context for priority recommendation
        linked_entity_ids = data.get("linked_entities", [])
        caller_provided_linked_entity_ids = bool(linked_entity_ids)
        auto_inferred_linked_entity_ids = False
        warnings: list[str] = []

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
                ) or []
                auto_inferred_linked_entity_ids = bool(linked_entity_ids)

        filtered_linked_entity_ids: list[str] = []
        linked_entities = []
        missing_ids = []
        for eid in linked_entity_ids:
            entity = await self._entities.get_by_id(eid)
            if entity:
                if is_collaboration_root_entity(entity):
                    continue
                filtered_linked_entity_ids.append(eid)
                linked_entities.append(entity)
            else:
                missing_ids.append(eid)
        if missing_ids and caller_provided_linked_entity_ids:
            raise ValueError(
                f"linked_entities 包含不存在的 entity ID: {', '.join(missing_ids)}。"
                f"請先建立這些 entity 或移除無效 ID。"
            )
        if missing_ids and auto_inferred_linked_entity_ids:
            warnings.append(
                "auto-inferred linked entity IDs were ignored because they no longer exist: "
                + ", ".join(missing_ids)
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
            _validate_action_parent_product_id(
                parent_kind="plan_id",
                parent_id=plan_id,
                parent_product_id=existing_plan.product_id,
            )
            if effective_product_id and existing_plan.product_id and existing_plan.product_id != effective_product_id:
                raise TaskValidationError(
                    f"task.product_id '{effective_product_id}' does not match "
                    f"plan.product_id '{existing_plan.product_id}'.",
                    error_code="CROSS_PRODUCT_PLAN_TASK",
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
            linked_entities=filtered_linked_entity_ids,
            linked_protocol=data.get("linked_protocol") or None,
            linked_blindspot=linked_blindspot_id,
            source_type=data.get("source_type") or "",
            source_metadata=data.get("source_metadata") or {},
            context_summary=context_summary,
            due_date=due_date,
            blocked_by=blocked_by,
            blocked_reason=blocked_reason,
            acceptance_criteria=data.get("acceptance_criteria") or [],
            project=effective_project_name or _normalize_project_scope(data.get("project")),
            product_id=effective_product_id or data.get("product_id") or None,
            attachments=data.get("attachments") or [],
            parent_task_id=parent_task_id,
            dispatcher=dispatcher,
        )

        saved = await self._save_task(task, conn=conn)
        return TaskResult(task=saved, cascade_updates=[], warnings=warnings)

    # ──────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────

    async def update_task(self, task_id: str, updates: dict) -> TaskResult:
        """Update a task with state validation and cascade unblocking."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        task.status = normalize_task_status(task.status)

        # Dispatcher namespace validation
        if "dispatcher" in updates:
            dispatcher_val = updates["dispatcher"]
            if dispatcher_val is not None and not DISPATCHER_PATTERN.match(dispatcher_val):
                raise TaskValidationError(
                    f"dispatcher '{dispatcher_val}' does not match required namespace format "
                    f"^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$",
                    error_code="INVALID_DISPATCHER",
                )

        # Cross-plan subtask validation
        parent: Task | None = None
        if "parent_task_id" in updates:
            new_parent_id = updates["parent_task_id"]
            if new_parent_id is not None:
                parent = await self._tasks.get_by_id(new_parent_id)
                if parent is None:
                    raise TaskValidationError(
                        f"parent_task_id '{new_parent_id}' does not exist.",
                        error_code="PARENT_NOT_FOUND",
                    )
                effective_plan_id = updates.get("plan_id", task.plan_id)
                if effective_plan_id and parent.plan_id != effective_plan_id:
                    raise TaskValidationError(
                        f"Subtask plan_id '{effective_plan_id}' does not match "
                        f"parent task plan_id '{parent.plan_id}'. "
                        f"Subtasks must inherit the parent's plan_id.",
                        error_code="CROSS_PLAN_SUBTASK",
                    )
                _validate_action_parent_product_id(
                    parent_kind="parent_task_id",
                    parent_id=new_parent_id,
                    parent_product_id=parent.product_id,
                )

        # project_id alias removed (ADR-047 D3). Callers must use product_id.
        product_entity = await _resolve_product_entity(
            self._entities,
            product_id=updates.get("product_id") or task.product_id,
            project_hint=updates.get("project") or task.project,
        )
        effective_product_id = product_entity.id if product_entity else None
        effective_project_name = product_entity.name if product_entity else None
        if effective_product_id is None:
            raise TaskValidationError(
                "product_id is required when project/defaultProject cannot be resolved to a product entity.",
                error_code="MISSING_PRODUCT_ID",
            )

        if parent is None and (updates.get("parent_task_id") or task.parent_task_id):
            parent = await self._tasks.get_by_id(updates.get("parent_task_id") or task.parent_task_id)
            if parent is not None:
                _validate_action_parent_product_id(
                    parent_kind="parent_task_id",
                    parent_id=updates.get("parent_task_id") or task.parent_task_id,
                    parent_product_id=parent.product_id,
                )
        if parent is not None and effective_product_id and parent.product_id and parent.product_id != effective_product_id:
            raise TaskValidationError(
                f"Subtask product_id '{effective_product_id}' does not match "
                f"parent task product_id '{parent.product_id}'.",
                error_code="CROSS_PRODUCT_SUBTASK",
            )

        effective_plan_id = updates.get("plan_id", task.plan_id)
        if effective_plan_id and self._plans is not None:
            existing_plan = await self._plans.get_by_id(effective_plan_id)
            if existing_plan is None:
                raise ValueError(
                    f"plan_id '{effective_plan_id}' does not exist. Create the plan first."
                )
            _validate_action_parent_product_id(
                parent_kind="plan_id",
                parent_id=effective_plan_id,
                parent_product_id=existing_plan.product_id,
            )
            if effective_product_id and existing_plan.product_id and existing_plan.product_id != effective_product_id:
                raise TaskValidationError(
                    f"task.product_id '{effective_product_id}' does not match "
                    f"plan.product_id '{existing_plan.product_id}'.",
                    error_code="CROSS_PRODUCT_PLAN_TASK",
                )

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
            "updated_by", "attachments",
            "parent_task_id", "dispatcher",
        ):
            if field in updates:
                setattr(task, field, updates[field])
        if "project" in updates or effective_project_name:
            task.project = effective_project_name or _normalize_project_scope(updates.get("project"))
        if "linked_entities" in updates:
            filtered_linked_entity_ids: list[str] = []
            for entity_id in updates["linked_entities"]:
                entity = await self._entities.get_by_id(entity_id)
                if entity is None:
                    raise ValueError(
                        f"linked_entities 包含不存在的 entity ID: {entity_id}。"
                        f"請先建立這些 entity 或移除無效 ID。"
                    )
                if is_collaboration_root_entity(entity):
                    continue
                filtered_linked_entity_ids.append(entity_id)
            task.linked_entities = filtered_linked_entity_ids
        # project_id alias removed (ADR-047 D3). Callers must use product_id.
        if "product_id" in updates:
            task.product_id = effective_product_id or updates["product_id"]
        elif effective_product_id:
            task.product_id = effective_product_id
        if "due_date" in updates:
            task.due_date = _parse_due_date(updates["due_date"])

        if task.plan_order is not None and not task.plan_id:
            raise ValueError("plan_id is required when plan_order is provided")
        if task.plan_order is not None and int(task.plan_order) < 1:
            raise ValueError("plan_order must be >= 1")

        task.updated_at = datetime.utcnow()
        saved = await self._save_task(task)
        return TaskResult(task=saved, cascade_updates=cascades)

    async def handoff_task(
        self,
        task_id: str,
        *,
        to_dispatcher: str,
        reason: str,
        output_ref: str | None = None,
        notes: str | None = None,
        updated_by: str | None = None,
    ) -> TaskResult:
        """Append a handoff event and move dispatcher atomically when possible."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        task.status = normalize_task_status(task.status)

        if not to_dispatcher or not DISPATCHER_PATTERN.match(to_dispatcher):
            raise TaskValidationError(
                f"dispatcher '{to_dispatcher}' does not match required namespace format "
                f"^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$",
                error_code="INVALID_DISPATCHER",
            )
        if not reason or not reason.strip():
            raise ValueError("reason is required for handoff")

        now = datetime.now(timezone.utc)
        event = HandoffEvent(
            at=now,
            from_dispatcher=task.dispatcher,
            to_dispatcher=to_dispatcher,
            reason=reason.strip(),
            output_ref=output_ref,
            notes=notes,
        )
        next_status = task.status
        if to_dispatcher == "agent:qa" and task.status == TaskStatus.IN_PROGRESS:
            next_status = TaskStatus.REVIEW

        async def _persist(conn: Any | None = None) -> Task:
            task.handoff_events = [*(task.handoff_events or []), event]
            task.dispatcher = to_dispatcher
            task.status = next_status
            task.updated_at = datetime.utcnow()
            if updated_by:
                task.updated_by = updated_by
            return await self._save_task(task, conn=conn)

        if self._uow_factory is not None:
            async with self._uow_factory() as uow:
                saved = await _persist(getattr(uow, "conn", None))
        else:
            saved = await _persist()
        return TaskResult(task=saved, cascade_updates=[])

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
                accept_ref = None
                if entity_entries:
                    entity_ids = [
                        str(item.get("entity_id"))
                        for item in entity_entries
                        if isinstance(item, dict) and item.get("entity_id")
                    ]
                    if entity_ids:
                        accept_ref = ",".join(entity_ids)
                task.handoff_events = [
                    *(task.handoff_events or []),
                    HandoffEvent(
                        at=datetime.now(timezone.utc),
                        from_dispatcher=task.dispatcher,
                        to_dispatcher="human",
                        reason="accepted",
                        output_ref=accept_ref,
                    ),
                ]
                task.dispatcher = "human"
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
                saved = await self._save_task(task, conn=uow.conn)
            return TaskResult(task=saved, cascade_updates=cascades, suggested_entity_updates=suggested_entity_updates)
        else:
            if not rejection_reason:
                raise ValueError("rejection_reason is required when rejecting")
            task.status = TaskStatus.IN_PROGRESS
            task.confirmed_by_creator = False
            task.rejection_reason = rejection_reason
            task.handoff_events = [
                *(task.handoff_events or []),
                HandoffEvent(
                    at=datetime.now(timezone.utc),
                    from_dispatcher=task.dispatcher,
                    to_dispatcher=task.dispatcher or "human",
                    reason=f"rejected: {rejection_reason}",
                ),
            ]

            task.updated_at = datetime.utcnow()
            if updated_by:
                task.updated_by = updated_by
            saved = await self._save_task(task)
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
        dispatcher: str | None = None,
        parent_task_id: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
        project: str | None = None,
        product_id: str | None = None,
        plan_id: str | None = None,
    ) -> list[Task]:
        """List tasks with filters. Delegates to repository."""
        return await self._tasks.list_all(
            assignee=assignee,
            created_by=created_by,
            status=status,
            priority=priority,
            linked_entity=linked_entity,
            dispatcher=dispatcher,
            parent_task_id=parent_task_id,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
            project=project,
            product_id=product_id,
            plan_id=plan_id,
        )

    async def list_pending_review(self) -> list[Task]:
        """List tasks awaiting creator confirmation."""
        return await self._tasks.list_pending_review()

    # ──────────────────────────────────────────
    # Wave 9 Phase B prime — L3 path adapters
    # ──────────────────────────────────────────
    # Strategy: normalize-to-legacy. Convert L3TaskEntity → dict, then
    # delegate to the existing create_task / update_task logic so all
    # validation, error codes, and response shapes are byte-equal.
    # Runtime callers still use the legacy Task path; these methods only
    # exist to satisfy the parity gate (Phase C will flip the switch).

    @staticmethod
    def _l3_task_entity_to_create_dict(
        entity: L3TaskEntity,
        *,
        created_by: str,
        product_id: str,
        plan_id: str | None = None,
        parent_task_id: str | None = None,
        project: str | None = None,
        linked_entities: list[str] | None = None,
        linked_protocol: str | None = None,
        linked_blindspot: str | None = None,
        source_type: str = "",
        source_metadata: dict | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Convert an L3TaskEntity to the dict shape expected by create_task.

        This is the normalize-to-legacy bridge for the dual-path adapter.
        Fields that don't exist on legacy Task (e.g. type_label, level,
        status/'active') are mapped to their closest legacy equivalents or
        dropped intentionally.

        Hierarchy routing is the caller's responsibility — this method does NOT
        infer plan_id / parent_task_id from entity.parent_id or entity.dispatcher.
        Callers must pass the correct hierarchy kwargs explicitly (fix-5, fix-6).

        Args:
            entity: The L3TaskEntity to convert.
            created_by: Creator identifier for the legacy Task.
            product_id: REQUIRED — product that owns this task. Caller must
                resolve and supply this; adapter does not infer from entity.
            plan_id: Explicit plan affiliation (optional). Pass when task
                belongs to a plan. Mutually exclusive with parent_task_id.
            parent_task_id: Explicit parent task ID for subtasks (optional).
            project: Optional project name hint for product resolution fallback.
        """
        # L3TaskEntity.depends_on is the union of depends_on_task_ids + blocked_by.
        # We split back: put the full list in both (lossy but parity-safe).
        depends_on = list(entity.depends_on)

        # due_date: L3 uses date, legacy uses datetime
        due_date = None
        if entity.due_date is not None:
            from datetime import datetime, date as _date
            if isinstance(entity.due_date, datetime):
                due_date = entity.due_date.isoformat()
            elif isinstance(entity.due_date, _date):
                due_date = entity.due_date.isoformat()

        # dispatcher: L3 stores "human" explicitly; legacy uses None for human
        dispatcher = entity.dispatcher if entity.dispatcher != "human" else None

        return {
            "title": entity.name,
            "created_by": created_by,
            "description": entity.description or "",
            "status": entity.task_status,
            "priority": entity.priority,
            "assignee": entity.assignee,
            "dispatcher": dispatcher,
            "acceptance_criteria": list(entity.acceptance_criteria),
            "result": entity.result,
            "plan_id": plan_id,
            "plan_order": entity.plan_order,
            "parent_task_id": parent_task_id,
            "product_id": product_id,
            "project": project,
            "depends_on_task_ids": depends_on,
            "blocked_by": [],               # fix-9: L3.depends_on is prerequisite chain, not blocked
            "blocked_reason": entity.blocked_reason,
            "due_date": due_date,
            # fix-10: forward caller-provided ontology links and provenance
            "linked_entities": list(linked_entities or []),
            "linked_protocol": linked_protocol,
            "linked_blindspot": linked_blindspot,
            "source_type": source_type,
            "source_metadata": dict(source_metadata or {}),
            "attachments": list(attachments or []),
        }

    async def create_task_via_l3_entity(
        self,
        entity: L3TaskEntity,
        *,
        created_by: str,
        product_id: str,
        plan_id: str | None = None,
        parent_task_id: str | None = None,
        project: str | None = None,
        linked_entities: list[str] | None = None,
        linked_protocol: str | None = None,
        linked_blindspot: str | None = None,
        source_type: str = "",
        source_metadata: dict | None = None,
        attachments: list[dict] | None = None,
        conn: Any | None = None,
    ) -> TaskResult:
        """Create a task from an L3TaskEntity (dual-path adapter, Phase B prime).

        Normalizes the L3TaskEntity to the legacy dict format, then delegates
        to create_task so that all validation and response shapes are byte-equal
        with the legacy path.

        Callers MUST provide product_id explicitly. plan_id / parent_task_id
        are optional and represent the hierarchy position — the adapter does NOT
        infer these from entity.parent_id or entity.dispatcher (fix-5, fix-6).

        fix-10: linked_entities / linked_protocol / linked_blindspot /
        source_type / source_metadata / attachments are forwarded as caller
        kwargs so that MCP callers can pass ontology links and provenance
        without silent drops.

        Args:
            entity: The L3TaskEntity to create.
            created_by: Creator identifier.
            product_id: REQUIRED — product that owns this task.
            plan_id: Optional plan affiliation. Mutually exclusive with
                parent_task_id (subtask routing).
            parent_task_id: Optional parent task ID for subtask creation.
            project: Optional project name hint.
            linked_entities: Optional list of ontology entity IDs to link.
            linked_protocol: Optional protocol entity ID to link.
            linked_blindspot: Optional blindspot entity ID to link.
            source_type: Source type string (e.g. "chat", "doc").
            source_metadata: Source provenance metadata dict.
            attachments: Initial attachments list.
            conn: Optional DB connection for atomic operations.
        """
        data = self._l3_task_entity_to_create_dict(
            entity,
            created_by=created_by,
            product_id=product_id,
            plan_id=plan_id,
            parent_task_id=parent_task_id,
            project=project,
            linked_entities=linked_entities,
            linked_protocol=linked_protocol,
            linked_blindspot=linked_blindspot,
            source_type=source_type,
            source_metadata=source_metadata,
            attachments=attachments,
        )
        return await self.create_task(data, conn=conn)

    async def update_task_via_l3_entity(
        self,
        task_id: str,
        entity: L3TaskEntity,
        *,
        product_id: str | None = None,
        plan_id: str | None = None,
        parent_task_id: str | None = None,
        linked_entities: list[str] | None = None,
        linked_protocol: str | None = None,
        linked_blindspot: str | None = None,
        source_type: str | None = None,
        source_metadata: dict | None = None,
        attachments: list[dict] | None = None,
        blocked_by: list[str] | None = None,
    ) -> TaskResult:
        """Update a task from an L3TaskEntity (dual-path adapter, Phase B prime).

        Entity fields are applied with full-replace semantics — the L3TaskEntity
        represents a complete desired state snapshot, so all mutable fields
        (including empty lists and None values) are forwarded unconditionally
        to update_task (fix-8). This allows explicit clearing of acceptance_criteria,
        depends_on, description, etc.

        Hierarchy kwargs (product_id / plan_id / parent_task_id) are partial-update:
        only included in the update dict when the caller explicitly passes them
        (fix-7). This lets the caller rehome a task without touching entity fields.

        MCP mutable field kwargs (fix-14): linked_entities / linked_protocol /
        linked_blindspot / source_type / source_metadata / attachments / blocked_by
        are forwarded as caller kwargs with partial-update semantics (None = no change).
        This ensures byte-equal parity with the legacy update path for all MCP fields.

        Note: blocked_by is a legacy-only field. fix-9 principle still applies —
        entity.depends_on is NOT automatically promoted to blocked_by. The caller
        must pass blocked_by explicitly when needed.

        Args:
            task_id: ID of the task to update.
            entity: L3TaskEntity representing the full desired state.
            product_id: If provided, update the task's product affiliation.
            plan_id: If provided, rehome the task to this plan.
            parent_task_id: If provided, re-parent the task under this parent.
            linked_entities: If provided, update linked entity IDs (partial-update).
            linked_protocol: If provided, update linked protocol ID (partial-update).
            linked_blindspot: If provided, update linked blindspot ID (partial-update).
            source_type: If provided, update source type (partial-update).
            source_metadata: If provided, update source metadata (partial-update).
            attachments: If provided, full-replace attachments list (partial-update).
            blocked_by: If provided, update blocked_by task IDs (partial-update).
        """
        from datetime import datetime, date as _date

        # Full-replace for all entity-sourced mutable fields (fix-8).
        # L3TaskEntity is a complete state snapshot — always pass, even if empty/None.
        # title (entity.name) is intentionally omitted: update_task does not accept
        # title as an update field (title is immutable after create).
        depends_on = list(entity.depends_on)

        # dispatcher: L3 stores "human" explicitly; legacy uses None for human
        dispatcher = entity.dispatcher if entity.dispatcher != "human" else None

        updates: dict = {
            "status": entity.task_status,
            "priority": entity.priority,
            "assignee": entity.assignee,
            "description": entity.description,
            "blocked_reason": entity.blocked_reason,
            "result": entity.result,
            "acceptance_criteria": list(entity.acceptance_criteria),
            "depends_on_task_ids": depends_on,
            # blocked_by intentionally omitted here: update is partial-update,
            # so blocked_by must only enter updates when caller explicitly passes
            # the kwarg (handled below at line 992-993). Hardcoding [] here would
            # silently clear existing blocked_by on every L3 update call.
            # (fix-9 correctly puts "blocked_by": [] in the CREATE path to prevent
            # depends_on from being misread as blocked state; that is a different
            # code path in create_task_via_l3_entity.)
            "plan_order": entity.plan_order,
            "dispatcher": dispatcher,
        }

        # due_date: always convert (can be None → explicit clear)
        if entity.due_date is not None:
            if isinstance(entity.due_date, datetime):
                updates["due_date"] = entity.due_date.isoformat()
            elif isinstance(entity.due_date, _date):
                updates["due_date"] = entity.due_date.isoformat()
        else:
            updates["due_date"] = None

        # Hierarchy kwargs: partial-update semantics — only include when caller
        # explicitly passes them (fix-7). None kwarg = "don't change this field".
        if product_id is not None:
            updates["product_id"] = product_id
        if plan_id is not None:
            updates["plan_id"] = plan_id
        if parent_task_id is not None:
            updates["parent_task_id"] = parent_task_id

        # MCP mutable field kwargs: partial-update semantics (fix-14).
        # None kwarg = "don't change this field".
        # This ensures the L3 update path has byte-equal parity with the legacy
        # update path for all MCP-exposed mutable fields.
        if linked_entities is not None:
            updates["linked_entities"] = list(linked_entities)
        if linked_protocol is not None:
            updates["linked_protocol"] = linked_protocol
        if linked_blindspot is not None:
            updates["linked_blindspot"] = linked_blindspot
        if source_type is not None:
            updates["source_type"] = source_type
        if source_metadata is not None:
            updates["source_metadata"] = dict(source_metadata)
        if attachments is not None:
            updates["attachments"] = list(attachments)
        if blocked_by is not None:
            updates["blocked_by"] = list(blocked_by)

        return await self.update_task(task_id, updates)

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
