"""Wave 9 Phase B — bidirectional converters between legacy Task/Plan and L3 entity dataclasses.

These converters allow the domain layer to speak both the old (Task/Plan) and new
(L3TaskEntity / L3PlanEntity) languages simultaneously.  Repo / MCP / application layers
still use Task/Plan; converters are the bridge until Phase C completes dual-write.

Parent-id mapping contract
--------------------------
The legacy ``Task`` carries up to four affiliation fields:
  - ``product_id``   — L1 product owner
  - ``plan_id``      — L3PlanEntity (task group)
  - ``parent_task_id`` — L3TaskEntity parent (subtask relationship)
  - ``project``      — partner-level project label (string, not a FK)

In the L3 world, ``parent_id`` is the single edge that encodes affiliation.
Priority for ``task_to_l3_entity``:
  1. ``parent_task_id`` if set  → subtask relationship dominates
  2. ``plan_id`` if set          → task inside a plan
  3. ``product_id`` if set       → task under a product (root task)
  4. None                        → free-floating task

For the reverse direction (``l3_entity_to_task``), if an ``original`` Task is
provided the function restores ``parent_id`` into whichever legacy field was
originally non-null.  Without ``original``, a heuristic based on ``type_label``
and ``dispatcher`` is applied.

depends_on / blocked_by merge contract
---------------------------------------
Forward direction (``task_to_l3_entity``):
  ``L3TaskEntity.depends_on`` is the union of ``Task.depends_on_task_ids`` and
  ``Task.blocked_by`` (per SPEC §9.4 — "replaces the legacy depends_on_task_ids /
  blocked_by lists").

Reverse direction (``l3_entity_to_task``) — fix-9:
  Only ``depends_on_task_ids`` is restored from ``L3TaskEntity.depends_on``.
  ``blocked_by`` is left as an empty list because ``L3TaskEntity.depends_on``
  encodes normal prerequisite chains (not the "blocked" semantic).  Callers
  that need to restore the ``blocked_by`` state must supply the original Task
  hint and apply their own logic — the converter cannot losslessly reconstruct
  the distinction.
"""

from __future__ import annotations

from datetime import date, datetime

from .models import (
    L3PlanEntity,
    L3TaskEntity,
    Plan,
    Task,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _dt_to_date(dt: datetime | date | None) -> date | None:
    """Coerce a datetime to a date (date-only field on L3 entities)."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.date()
    return dt


def _resolve_parent_id(task: Task) -> str | None:
    """Pick the single ``parent_id`` value from the legacy four-field affiliation."""
    if task.parent_task_id:
        return task.parent_task_id
    if task.plan_id:
        return task.plan_id
    if task.product_id:
        return task.product_id
    return None


# ──────────────────────────────────────────────
# Task ↔ L3TaskEntity
# ──────────────────────────────────────────────

def task_to_l3_entity(task: Task, *, partner_id: str) -> L3TaskEntity:
    """Convert a legacy Task to a Wave 9 L3TaskEntity.

    Args:
        task: The legacy Task to convert.
        partner_id: The tenant FK for entities_base.partner_id.  Callers must
            supply this explicitly — it is NOT derived from ``task.product_id``
            (which is an L1 entity id, not a partner/tenant id).

    Lossy fields (not round-trippable without metadata):
    - ``title`` → ``name``  (no information loss, just rename)
    - ``priority_reason``, ``source_type``, ``source_metadata``,
      ``context_summary``, ``creator_name``, ``assignee_name``,
      ``confirmed_by_creator``, ``rejection_reason`` — dropped; these are
      application/infra concerns, not domain entity fields.
    - ``linked_entities``, ``linked_protocol``, ``linked_blindspot`` — handled
      via ``relationships`` table in Phase C; not stored on L3 entity directly.
    - ``attachments`` — likewise infra concern.
    - ``completed_by``, ``completed_at`` — not part of L3TaskBaseEntity;
      completion is inferred from task_status == "done".
    - ``depends_on_task_ids`` + ``blocked_by`` → merged into ``depends_on``
      (union, order-preserving, deduplicated).
    """
    task_id = task.id or ""
    depends_on = list(
        dict.fromkeys((task.depends_on_task_ids or []) + (task.blocked_by or []))
    )

    return L3TaskEntity(
        # entities_base fields
        id=task_id,
        partner_id=partner_id,
        name=task.title,
        type_label="task",
        level=3,
        parent_id=_resolve_parent_id(task),
        status="active",          # lifecycle always "active" for non-done tasks; simplified
        created_at=task.created_at,
        updated_at=task.updated_at,
        # L3-Action shared fields
        description=task.description,
        task_status=task.status,  # maps 1:1: todo/in_progress/review/done/cancelled
        assignee=task.assignee,
        dispatcher=task.dispatcher or "human",
        acceptance_criteria=list(task.acceptance_criteria),
        priority=task.priority,
        result=task.result,
        handoff_events=list(task.handoff_events),
        # L3TaskEntity-specific fields
        plan_order=task.plan_order,
        depends_on=depends_on,
        blocked_reason=task.blocked_reason,
        due_date=_dt_to_date(task.due_date),
    )


def l3_entity_to_task(
    entity: L3TaskEntity,
    *,
    created_by: str = "",
    original: Task | None = None,
) -> Task:
    """Convert a Wave 9 L3TaskEntity back to a legacy Task.

    Args:
        entity: The L3TaskEntity to convert.
        created_by: Optional hint for the legacy ``created_by`` field.  When
            not provided, defaults to empty string (maintains prior behaviour).
        original: Optional original Task used as a hint for restoring
            ``parent_id`` to the correct legacy affiliation field.  When
            provided, the field that was originally non-null is used.  When
            not provided, a heuristic based on ``type_label`` and
            ``dispatcher`` is applied.

    Round-trip guarantee:
    - ``name`` → ``title``
    - ``task_status`` → ``status``
    - ``parent_id`` → restored to the correct legacy field based on
      ``original`` hint (if given) or heuristic.

    Lossy fields after round-trip (fix-9):
    - ``depends_on_task_ids`` is restored from the L3 ``depends_on`` field.
    - ``blocked_by`` is left as an empty list: ``L3TaskEntity.depends_on``
      encodes normal prerequisite chains; the "blocked by" semantic cannot
      be reconstructed without additional metadata from the original Task.
      Callers that need to restore ``blocked_by`` must supply ``original``
      and apply their own post-processing.

    Fields that cannot be fully round-tripped are left at their zero-values.
    """
    # Restore legacy affiliation fields from parent_id.
    plan_id: str | None = None
    parent_task_id: str | None = None
    product_id: str | None = None

    if original is not None:
        # fix: preserve ALL original affiliation fields so round-trip does not
        # drop product ownership. A normal plan task has both plan_id AND
        # product_id non-null; entity.parent_id only holds the "primary" edge
        # (parent_task_id > plan_id > product_id, per task_to_l3_entity order),
        # but the other non-null legacy fields must survive the round-trip.
        parent_task_id = original.parent_task_id or None
        plan_id = original.plan_id or None
        product_id = original.product_id or None
    elif entity.parent_id:
        # Heuristic: only type_label='subtask' identifies a subtask.
        # dispatcher='agent:*' is a valid value for normal plan-level tasks
        # (e.g. agent:pm / agent:developer dispatching a plan task), so
        # dispatcher MUST NOT be used as a subtask signal. Caller should
        # pass original= when precise restoration is needed — in particular
        # to preserve product_id on plan tasks.
        if entity.type_label == "subtask":
            parent_task_id = entity.parent_id
        else:
            plan_id = entity.parent_id

    # fix-9: reverse direction restores depends_on_task_ids from L3.depends_on.
    # blocked_by is left empty — L3.depends_on encodes prerequisite chains, not
    # the "blocked by" semantic.  The distinction is irrecoverably lossy at this
    # layer; callers needing to restore blocked_by must apply their own logic.
    depends_on_list = list(entity.depends_on)

    return Task(
        id=entity.id or None,
        title=entity.name,
        status=entity.task_status,
        priority=entity.priority,
        created_by=created_by,
        description=entity.description,
        assignee=entity.assignee,
        dispatcher=entity.dispatcher if entity.dispatcher != "human" else None,
        acceptance_criteria=list(entity.acceptance_criteria),
        result=entity.result,
        handoff_events=list(entity.handoff_events),
        plan_id=plan_id,
        parent_task_id=parent_task_id,
        product_id=product_id,
        plan_order=entity.plan_order,
        depends_on_task_ids=depends_on_list,
        blocked_by=[],              # fix-9: not restored from L3.depends_on
        blocked_reason=entity.blocked_reason,
        due_date=datetime.combine(entity.due_date, datetime.min.time()) if entity.due_date else None,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


# ──────────────────────────────────────────────
# Plan ↔ L3PlanEntity
# ──────────────────────────────────────────────

def plan_to_l3_entity(plan: Plan, *, partner_id: str) -> L3PlanEntity:
    """Convert a legacy Plan to a Wave 9 L3PlanEntity.

    Args:
        plan: The legacy Plan to convert.
        partner_id: The tenant FK for entities_base.partner_id.  Callers must
            supply this explicitly — it is NOT derived from ``plan.product_id``
            (which is an L1 entity id, not a partner/tenant id).
    """
    plan_id = plan.id or ""

    return L3PlanEntity(
        id=plan_id,
        partner_id=partner_id,
        name=plan.goal,           # goal text becomes the plan's name
        type_label="plan",
        level=3,
        parent_id=plan.product_id,
        status="active",
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        description=plan.goal,    # no separate description on legacy Plan
        task_status=plan.status,  # draft/active/completed/cancelled
        assignee=plan.owner,
        dispatcher="human",
        result=plan.result,
        goal_statement=plan.goal,
        entry_criteria=plan.entry_criteria or "",
        exit_criteria=plan.exit_criteria or "",
    )


def l3_plan_entity_to_plan(entity: L3PlanEntity, *, created_by: str = "") -> Plan:
    """Convert a Wave 9 L3PlanEntity back to a legacy Plan.

    Args:
        entity: The L3PlanEntity to convert.
        created_by: Optional hint for the legacy ``created_by`` field.  When
            not provided, defaults to empty string (maintains prior behaviour).

    Notes:
        ``parent_id`` on a Plan L3 entity always maps to ``product_id`` —
        a Plan's sole affiliation is its owning product (L1 entity).
    """
    return Plan(
        id=entity.id or None,
        goal=entity.goal_statement or entity.name,
        status=entity.task_status,
        created_by=created_by,
        owner=entity.assignee,
        entry_criteria=entity.entry_criteria or None,
        exit_criteria=entity.exit_criteria or None,
        product_id=entity.parent_id,
        result=entity.result,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )
