"""TaskService — orchestrates Action Layer use cases.

Handles task CRUD, state validation, priority recommendation,
context assembly, and cascade unblocking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from zenos.domain.models import Blindspot, EntityType, Task, TaskPriority, TaskStatus
from zenos.domain.repositories import (
    BlindspotRepository,
    EntityRepository,
    TaskRepository,
)
from zenos.domain.task_rules import (
    is_valid_initial_status,
    is_valid_transition,
    is_valid_update_target,
    recommend_priority,
)


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


class TaskService:
    """Application-layer service for Action Layer tasks."""

    def __init__(
        self,
        task_repo: TaskRepository,
        entity_repo: EntityRepository,
        blindspot_repo: BlindspotRepository,
        document_repo: object | None = None,  # deprecated, kept for backward compat
        governance_ai: object | None = None,
    ) -> None:
        self._tasks = task_repo
        self._entities = entity_repo
        self._blindspots = blindspot_repo
        self._governance_ai = governance_ai

    # ──────────────────────────────────────────
    # Create
    # ──────────────────────────────────────────

    async def create_task(self, data: dict) -> TaskResult:
        """Create a new task with priority recommendation and context assembly."""
        # Priority enum validation
        priority_val = data.get("priority")
        if priority_val:
            valid_priorities = [p.value for p in TaskPriority]
            if priority_val not in valid_priorities:
                raise ValueError(
                    f"Invalid priority '{priority_val}'. "
                    f"Must be one of: {', '.join(valid_priorities)}"
                )

        status = data.get("status", TaskStatus.BACKLOG)
        if not is_valid_initial_status(status):
            raise ValueError(
                f"Invalid initial status '{status}'. Must be 'backlog' or 'todo'."
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
        for eid in linked_entity_ids:
            entity = await self._entities.get_by_id(eid)
            if entity:
                linked_entities.append(entity)

        linked_blindspot_id = data.get("linked_blindspot")
        linked_blindspot = None
        if linked_blindspot_id:
            linked_blindspot = await self._blindspots.get_by_id(linked_blindspot_id)

        blocked_by = data.get("blocked_by", [])

        # Auto-set to blocked if has blockers and not backlog
        if blocked_by and status != TaskStatus.BACKLOG:
            status = TaskStatus.BLOCKED

        # Priority recommendation
        due_date = data.get("due_date")
        rec_priority, priority_reason = recommend_priority(
            linked_entities=linked_entities,
            linked_blindspot=linked_blindspot,
            due_date=due_date,
            blocked_by_count=len(blocked_by),
            blocking_others_count=0,
        )

        # Caller-provided priority overrides recommendation
        priority = data.get("priority") or rec_priority

        # Context summary assembly
        context_summary = await self._assemble_context(
            linked_entities, linked_blindspot
        )

        task = Task(
            title=data["title"],
            description=data.get("description", ""),
            status=status,
            priority=priority,
            priority_reason=priority_reason,
            assignee=data.get("assignee"),
            created_by=data["created_by"],
            linked_entities=linked_entity_ids,
            linked_protocol=data.get("linked_protocol"),
            linked_blindspot=linked_blindspot_id,
            source_type=data.get("source_type", ""),
            context_summary=context_summary,
            due_date=due_date,
            blocked_by=blocked_by,
            acceptance_criteria=data.get("acceptance_criteria", []),
        )

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

        new_status = updates.get("status")
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
            if new_status == TaskStatus.BLOCKED and not updates.get("blocked_reason"):
                raise ValueError("blocked_reason is required when status is 'blocked'")

            task.status = new_status

            # Cascade unblocking when done or cancelled
            if new_status in (TaskStatus.DONE, TaskStatus.CANCELLED):
                cascades = await self._cascade_unblock(task_id)
                if new_status == TaskStatus.DONE:
                    task.completed_at = datetime.utcnow()

        # Apply other field updates
        for field in (
            "assignee", "priority", "description", "blocked_reason",
            "due_date", "result", "acceptance_criteria", "blocked_by",
        ):
            if field in updates:
                setattr(task, field, updates[field])

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
    ) -> TaskResult:
        """Accept or reject a task in review status."""
        task = await self._tasks.get_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found")
        if task.status != TaskStatus.REVIEW:
            raise ValueError(
                f"Can only confirm tasks in 'review' status. "
                f"Current status: '{task.status}'"
            )

        cascades: list[CascadeUpdate] = []

        if accepted:
            task.status = TaskStatus.DONE
            task.confirmed_by_creator = True
            task.completed_at = datetime.utcnow()
            cascades = await self._cascade_unblock(task_id)

            # Resolve linked blindspot if present
            if task.linked_blindspot:
                bs = await self._blindspots.get_by_id(task.linked_blindspot)
                if bs and bs.status != "resolved":
                    bs.status = "resolved"
                    await self._blindspots.add(bs)  # re-add to persist

            # Mark related document entities as stale when entities are outdated
            if mark_stale_entity_ids:
                for eid in mark_stale_entity_ids:
                    child_entities = await self._entities.list_by_parent(eid)
                    for child in child_entities:
                        if child.type == EntityType.DOCUMENT and child.status != "stale":
                            child.status = "stale"
                            await self._entities.upsert(child)

            # Create new blindspot discovered during task completion
            if new_blindspot:
                bs_obj = Blindspot(
                    description=new_blindspot.get("description", ""),
                    severity=new_blindspot.get("severity", "yellow"),
                    related_entity_ids=new_blindspot.get("related_entity_ids", []),
                    suggested_action=new_blindspot.get("suggested_action", ""),
                    confirmed_by_user=False,
                )
                await self._blindspots.add(bs_obj)
        else:
            if not rejection_reason:
                raise ValueError("rejection_reason is required when rejecting")
            task.status = TaskStatus.IN_PROGRESS
            task.confirmed_by_creator = False
            task.rejection_reason = rejection_reason

        task.updated_at = datetime.utcnow()
        saved = await self._tasks.upsert(task)
        return TaskResult(task=saved, cascade_updates=cascades)

    # ──────────────────────────────────────────
    # List
    # ──────────────────────────────────────────

    async def list_tasks(self, **filters) -> list[Task]:
        """List tasks with filters. Delegates to repository."""
        return await self._tasks.list_all(**filters)

    async def list_pending_review(self) -> list[Task]:
        """List tasks awaiting creator confirmation."""
        return await self._tasks.list_pending_review()

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    async def _cascade_unblock(self, completed_task_id: str) -> list[CascadeUpdate]:
        """When a task completes, unblock tasks that were waiting for it."""
        blocked_tasks = await self._tasks.list_blocked_by(completed_task_id)
        cascades: list[CascadeUpdate] = []

        for bt in blocked_tasks:
            bt.blocked_by = [
                tid for tid in bt.blocked_by if tid != completed_task_id
            ]
            if not bt.blocked_by and bt.status == TaskStatus.BLOCKED:
                bt.status = TaskStatus.TODO
                bt.blocked_reason = None
                bt.updated_at = datetime.utcnow()
                await self._tasks.upsert(bt)
                cascades.append(CascadeUpdate(
                    task_id=bt.id or "",
                    change="blocked → todo",
                    reason=f"blockedBy {completed_task_id} 已完成",
                ))
            else:
                # Still blocked by other tasks, just remove the completed one
                bt.updated_at = datetime.utcnow()
                await self._tasks.upsert(bt)

        return cascades

    async def _assemble_context(self, linked_entities, linked_blindspot) -> str:
        """Build a concise context summary from ontology references."""
        parts: list[str] = []

        if linked_entities:
            entity_names = [
                f"{e.name}（{e.status}）" for e in linked_entities[:3]
            ]
            parts.append(f"相關實體：{'、'.join(entity_names)}")

        if linked_blindspot:
            parts.append(
                f"觸發盲點：{linked_blindspot.description[:50]}"
            )

        # Enrich with related document entity names for richer context
        if linked_entities:
            doc_titles: list[str] = []
            for entity in linked_entities:
                if entity.id and len(doc_titles) < 3:
                    children = await self._entities.list_by_parent(entity.id)
                    for child in children:
                        if child.type == EntityType.DOCUMENT and len(doc_titles) < 3:
                            doc_titles.append(child.name)
            if doc_titles:
                parts.append(f"相關文件：{'、'.join(doc_titles)}")

        return "。".join(parts) if parts else ""
