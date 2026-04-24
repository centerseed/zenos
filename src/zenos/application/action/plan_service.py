"""PlanService — orchestrates Plan primitive use cases.

Handles plan CRUD, lifecycle transitions, and completion validation.
Plans group and sequence tasks under a shared goal with explicit entry/exit criteria.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from zenos.domain.action import Plan, PlanStatus
from zenos.domain.action.models import L3PlanEntity
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


class PlanValidationError(ValueError):
    """Validation error with a machine-readable error_code."""

    def __init__(self, message: str, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


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
            product_id=data.get("product_id"),
            project_hint=data.get("project"),
        )
        if product_entity is None:
            raise ValueError("product_id is required for plan creation")
        product_name = getattr(product_entity, "name", None) or (data.get("project") or "")
        canonical_product_id = getattr(product_entity, "id", None) or data.get("product_id")

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
        # project_id alias removed (ADR-047 D3). Callers must use product_id.

        product_entity = await self._resolve_product_entity(
            product_id=normalized_updates.get("product_id") or plan.product_id,
            project_hint=normalized_updates.get("project") or plan.project,
        )
        if product_entity is None:
            if plan.product_id is None and "product_id" not in normalized_updates:
                raise PlanValidationError(
                    f"Plan '{plan_id}' has no product_id; parent chain cannot terminate at an L1 collaboration root.",
                    error_code="INVALID_PARENT_CHAIN",
                )
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

    # ──────────────────────────────────────────
    # Wave 9 Phase B prime — L3 path adapters
    # ──────────────────────────────────────────

    async def create_plan_via_l3_entity(
        self,
        entity: L3PlanEntity,
        *,
        created_by: str,
        product_id: str | None = None,
    ) -> Plan:
        """Create a plan from an L3PlanEntity (dual-path adapter, Phase B prime).

        Normalizes the L3PlanEntity to the legacy dict format, then delegates
        to create_plan so that all validation and response shapes are byte-equal
        with the legacy path.

        fix-12: product_id kwarg takes precedence over entity.parent_id, allowing
        callers (e.g. the MCP plan handler) to supply a resolved product_id even
        when entity.parent_id is absent or unresolved.
        """
        data = {
            "goal": entity.goal_statement or entity.name,
            "created_by": created_by,
            "owner": entity.assignee,
            "entry_criteria": entity.entry_criteria or None,
            "exit_criteria": entity.exit_criteria or None,
            "product_id": product_id if product_id is not None else entity.parent_id,
            "project": None,
            "updated_by": created_by,
        }
        return await self.create_plan(data)

    async def update_plan_via_l3_entity(
        self,
        plan_id: str,
        entity: L3PlanEntity,
        *,
        product_id: str | None = None,
    ) -> Plan:
        """Update a plan from an L3PlanEntity (dual-path adapter, Phase B prime).

        Extracts mutable fields from the L3PlanEntity and delegates to
        update_plan so that all validation and response shapes are byte-equal.

        fix-17: entry_criteria and exit_criteria use always-pass semantics so
        that an empty string can explicitly clear existing values. The legacy
        update_plan accepts "" and stores it as-is.

        fix-16: product_id kwarg (partial-update semantic). If the caller
        provides an explicit product_id (already resolved from project/
        defaultProject by the MCP handler), it takes precedence over
        entity.parent_id. This allows re-homing a plan to a different product
        via the L3 update path.
        """
        updates: dict = {
            # Always-pass semantics for goal so that callers can change it.
            # goal_statement takes priority over name (L3 entity shape).
            "goal": entity.goal_statement or entity.name or "",
            # always-pass for entry/exit criteria (fix-17): empty string = explicit clear.
            "entry_criteria": entity.entry_criteria,
            "exit_criteria": entity.exit_criteria,
        }
        # status: only include when entity carries a value
        if entity.task_status:
            updates["status"] = entity.task_status
        if entity.assignee is not None:
            updates["owner"] = entity.assignee
        if entity.result is not None:
            updates["result"] = entity.result

        # product_id resolution (fix-16): caller-supplied kwarg takes precedence
        # over entity.parent_id so that MCP callers can re-home a plan after
        # running _resolve_plan_product_id.
        resolved_product_id = product_id if product_id is not None else entity.parent_id
        if resolved_product_id is not None:
            updates["product_id"] = resolved_product_id

        return await self.update_plan(plan_id, updates)

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
        "created_by": plan.created_by,
        "updated_by": plan.updated_by,
        "result": plan.result,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }
