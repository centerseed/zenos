"""PlanService — orchestrates Plan primitive use cases.

Handles plan CRUD, lifecycle transitions, and completion validation.
Plans group and sequence tasks under a shared goal with explicit entry/exit criteria.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from zenos.domain.action import Plan, PlanStatus
from zenos.domain.action.repositories import PlanRepository, TaskRepository
from zenos.domain.knowledge import EntityRepository
from zenos.domain.knowledge.collaboration_roots import is_collaboration_root_entity
from zenos.infrastructure.sql_common import _new_id, _now

# Terminal task statuses — a plan can only complete when all tasks reach these states.
_TASK_TERMINAL_STATUSES = {"done", "cancelled"}

# Valid plan status transitions
_PLAN_TRANSITIONS: dict[str, set[str]] = {
    PlanStatus.DRAFT: {PlanStatus.ACTIVE, PlanStatus.CANCELLED},
    PlanStatus.ACTIVE: {PlanStatus.COMPLETED, PlanStatus.CANCELLED},
    PlanStatus.COMPLETED: set(),
    PlanStatus.CANCELLED: set(),
}


class PlanService:
    """Application-layer service for Plan lifecycle and task grouping."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        task_repo: TaskRepository,
        entity_repo: EntityRepository | None = None,
    ) -> None:
        self._plans = plan_repo
        self._tasks = task_repo
        self._entities = entity_repo

    # ──────────────────────────────────────────
    # Create
    # ──────────────────────────────────────────

    async def create_plan(self, data: dict) -> Plan:
        """Create a new plan. Status defaults to draft."""
        goal = data.get("goal", "").strip()
        if not goal:
            raise ValueError("goal is required for plan creation")
        created_by = data.get("created_by", "").strip()
        if not created_by:
            raise ValueError("created_by is required for plan creation")

        product_entity = await self._resolve_product_entity(
            product_id=data.get("product_id") or data.get("project_id"),
            project_hint=data.get("project"),
        )
        if product_entity is None:
            raise ValueError("product_id is required for plan creation")
        product_name = getattr(product_entity, "name", None) or (data.get("project") or "")
        canonical_product_id = getattr(product_entity, "id", None) or data.get("product_id") or data.get("project_id")

        plan = Plan(
            goal=goal,
            status=PlanStatus.DRAFT,
            created_by=created_by,
            owner=data.get("owner") or None,
            entry_criteria=data.get("entry_criteria") or None,
            exit_criteria=data.get("exit_criteria") or None,
            project=product_name,
            product_id=canonical_product_id,
            updated_by=data.get("updated_by") or created_by,
        )
        return await self._plans.upsert(plan)

    # ──────────────────────────────────────────
    # Update / lifecycle
    # ──────────────────────────────────────────

    async def update_plan(self, plan_id: str, updates: dict) -> Plan:
        """Update plan fields and/or advance lifecycle status.

        Completion requires all tasks in terminal state and result non-empty.
        completed/cancelled plans are immutable.
        """
        plan = await self._plans.get_by_id(plan_id)
        if plan is None:
            raise ValueError(f"Plan '{plan_id}' not found")

        # Terminal plans are fully immutable
        if plan.status in (PlanStatus.COMPLETED, PlanStatus.CANCELLED):
            raise ValueError(
                f"Plan '{plan_id}' is in terminal status '{plan.status}' and cannot be updated"
            )

        new_status = updates.get("status")

        if new_status and new_status != plan.status:
            allowed = _PLAN_TRANSITIONS.get(plan.status, set())
            if new_status not in allowed:
                raise ValueError(
                    f"Invalid plan status transition: {plan.status} → {new_status}"
                )
            if new_status == PlanStatus.COMPLETED:
                await self._validate_completion(plan_id, updates, current_plan=plan)
            plan.status = new_status

        normalized_updates = dict(updates)
        if "project_id" in normalized_updates and "product_id" not in normalized_updates:
            normalized_updates["product_id"] = normalized_updates["project_id"]

        product_entity = await self._resolve_product_entity(
            product_id=normalized_updates.get("product_id") or plan.product_id,
            project_hint=normalized_updates.get("project") or plan.project,
        )
        if product_entity is None:
            raise ValueError("product_id is required for plan update")
        product_name = getattr(product_entity, "name", None) or normalized_updates.get("project") or plan.project
        canonical_product_id = (
            getattr(product_entity, "id", None)
            or normalized_updates.get("product_id")
            or plan.product_id
        )

        # Apply scalar field updates (non-status)
        for field_name in ("goal", "owner", "entry_criteria", "exit_criteria",
                           "result", "updated_by"):
            if field_name in normalized_updates and field_name != "status":
                setattr(plan, field_name, normalized_updates[field_name])
        plan.project = product_name
        plan.product_id = canonical_product_id

        plan.updated_at = _now()
        return await self._plans.upsert(plan)

    async def _validate_completion(self, plan_id: str, updates: dict, current_plan: Plan | None = None) -> None:
        """Raise ValueError if completion preconditions are not met.

        Preconditions:
        - result must be non-empty (from updates or existing plan)
        - all tasks under this plan must be in terminal state
        """
        result = updates.get("result") or (current_plan.result if current_plan else None)
        if not result or not result.strip():
            raise ValueError(
                "result is required when completing a plan"
            )

        tasks = await self._tasks.list_all(plan_id=plan_id)
        non_terminal = [
            t for t in tasks
            if t.status not in _TASK_TERMINAL_STATUSES
        ]
        if non_terminal:
            ids = ", ".join(t.id or "?" for t in non_terminal[:5])
            raise ValueError(
                f"Cannot complete plan: {len(non_terminal)} task(s) not in terminal state. "
                f"Pending task IDs (first 5): {ids}"
            )

    # ──────────────────────────────────────────
    # Get
    # ──────────────────────────────────────────

    async def get_plan(self, plan_id: str) -> dict:
        """Return plan dict enriched with a tasks_summary."""
        plan = await self._plans.get_by_id(plan_id)
        if plan is None:
            raise ValueError(f"Plan '{plan_id}' not found")

        tasks = await self._tasks.list_all(plan_id=plan_id)
        status_counts: dict[str, int] = {}
        for t in tasks:
            status_counts[t.status] = status_counts.get(t.status, 0) + 1

        plan_dict = _plan_to_dict(plan)
        plan_dict["tasks_summary"] = {
            "total": len(tasks),
            "by_status": status_counts,
        }
        return plan_dict

    # ──────────────────────────────────────────
    # List
    # ──────────────────────────────────────────

    async def list_plans(
        self,
        *,
        status: list[str] | None = None,
        project: str | None = None,
        product_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Plan]:
        """List plans with optional filters."""
        return await self._plans.list_all(
            status=status,
            project=project,
            product_id=product_id,
            limit=limit,
            offset=offset,
        )

    # ──────────────────────────────────────────
    # Auto-advance (called by TaskService)
    # ──────────────────────────────────────────

    async def advance_plan_to_active(self, plan_id: str) -> None:
        """Advance a draft plan to active when a task starts. No-op if not in draft."""
        plan = await self._plans.get_by_id(plan_id)
        if plan is None or plan.status != PlanStatus.DRAFT:
            return
        plan.status = PlanStatus.ACTIVE
        plan.updated_at = _now()
        await self._plans.upsert(plan)

    async def _resolve_product_entity(
        self,
        *,
        product_id: str | None,
        project_hint: str | None,
    ) -> Any | None:
        """Resolve the canonical product entity for a plan mutation."""
        if self._entities is None:
            if product_id:
                return {"id": product_id, "name": project_hint or ""}
            return None

        if product_id:
            entity = await self._entities.get_by_id(product_id)
            if not is_collaboration_root_entity(entity):
                raise ValueError(f"product_id '{product_id}' is invalid or not a collaboration root entity")
            return entity

        if project_hint:
            entity = await self._entities.get_by_name(str(project_hint).strip())
            if entity is None:
                return None
            if not is_collaboration_root_entity(entity):
                raise ValueError(f"project '{project_hint}' resolved to non-collaboration-root entity '{entity.id}'")
            return entity
        return None


def _plan_to_dict(plan: Plan) -> dict[str, Any]:
    """Convert a Plan dataclass to a JSON-safe dict."""
    return {
        "id": plan.id,
        "goal": plan.goal,
        "status": plan.status,
        "owner": plan.owner,
        "entry_criteria": plan.entry_criteria,
        "exit_criteria": plan.exit_criteria,
        "project": plan.project,
        "product_id": plan.product_id,
        "project_id": plan.product_id,
        "created_by": plan.created_by,
        "updated_by": plan.updated_by,
        "result": plan.result,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }
