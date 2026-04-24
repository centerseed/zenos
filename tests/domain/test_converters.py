"""Tests for Wave 9 Phase B — Task ↔ L3TaskEntity bidirectional converters.

Round-trip invariants and edge cases around parent_id affiliation mapping,
partner_id propagation, depends_on union, and created_by passthrough.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from zenos.domain.action.converters import (
    l3_entity_to_task,
    l3_plan_entity_to_plan,
    plan_to_l3_entity,
    task_to_l3_entity,
)
from zenos.domain.action.models import (
    HandoffEvent,
    L3TaskEntity,
    Plan,
    Task,
)
from zenos.domain.action.enums import TaskPriority, TaskStatus


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

_NOW = datetime(2026, 4, 23, 12, 0, 0)

_PARTNER_ID = "partner-tenant-1"


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Fix the bug",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        created_by="user-1",
        description="Reproduce and fix crash",
        assignee="user-2",
        dispatcher="agent:developer",
        acceptance_criteria=["no crash", "test passes"],
        result=None,
        plan_id="plan-1",
        product_id="product-1",
        parent_task_id=None,
        plan_order=3,
        depends_on_task_ids=["task-0"],
        blocked_by=[],
        blocked_reason=None,
        due_date=_NOW,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_plan(**overrides) -> Plan:
    defaults = dict(
        id="plan-1",
        goal="Ship Wave 9",
        status="active",
        created_by="user-1",
        owner="user-1",
        entry_criteria="Phase A done",
        exit_criteria="All tests pass",
        product_id="product-1",
        result=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return Plan(**defaults)


def _make_l3_task(**overrides) -> L3TaskEntity:
    """Build a minimal L3TaskEntity for reverse-direction tests."""
    defaults = dict(
        id="task-1",
        partner_id=_PARTNER_ID,
        name="Fix the bug",
        type_label="task",
        level=3,
        parent_id="plan-1",
        status="active",
        created_at=_NOW,
        updated_at=_NOW,
        description="Reproduce and fix crash",
        task_status="todo",
        assignee="user-2",
        dispatcher="human",
        priority="high",
        depends_on=[],
    )
    defaults.update(overrides)
    return L3TaskEntity(**defaults)


# ──────────────────────────────────────────────
# task_to_l3_entity — basic conversion
# ──────────────────────────────────────────────

class TestTaskToL3Entity:
    def test_basic_fields_mapped(self):
        task = _make_task()
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)

        assert entity.id == "task-1"
        assert entity.name == "Fix the bug"
        assert entity.type_label == "task"
        assert entity.level == 3
        assert entity.task_status == "todo"
        assert entity.assignee == "user-2"
        assert entity.dispatcher == "agent:developer"
        assert entity.acceptance_criteria == ["no crash", "test passes"]
        assert entity.description == "Reproduce and fix crash"
        assert entity.priority == "high"
        assert entity.plan_order == 3
        assert entity.depends_on == ["task-0"]
        assert entity.created_at == _NOW
        assert entity.updated_at == _NOW

    def test_partner_id_from_kwarg_not_product_id(self):
        """partner_id must come from the kwarg, never from task.product_id."""
        task = _make_task(product_id="some-l1-entity-id")
        entity = task_to_l3_entity(task, partner_id="real-tenant-id")
        assert entity.partner_id == "real-tenant-id"
        assert entity.partner_id != "some-l1-entity-id"

    def test_partner_id_set_correctly(self):
        task = _make_task()
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.partner_id == _PARTNER_ID

    def test_due_date_becomes_date(self):
        task = _make_task(due_date=datetime(2026, 5, 1, 0, 0, 0))
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.due_date == date(2026, 5, 1)

    def test_due_date_none_stays_none(self):
        task = _make_task(due_date=None)
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.due_date is None

    def test_result_propagated(self):
        task = _make_task(result="All done")
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.result == "All done"

    def test_handoff_events_copied(self):
        he = HandoffEvent(at=_NOW, from_dispatcher=None, to_dispatcher="agent:qa", reason="review")
        task = _make_task(handoff_events=[he])
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert len(entity.handoff_events) == 1
        assert entity.handoff_events[0].to_dispatcher == "agent:qa"


# ──────────────────────────────────────────────
# parent_id resolution — edge cases
# ──────────────────────────────────────────────

class TestParentIdResolution:
    def test_parent_task_id_takes_priority(self):
        """When parent_task_id is set it dominates over plan_id and product_id."""
        task = _make_task(parent_task_id="task-parent", plan_id="plan-1", product_id="prod-1")
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.parent_id == "task-parent"

    def test_plan_id_when_no_parent_task_id(self):
        """plan_id is used when parent_task_id is None."""
        task = _make_task(parent_task_id=None, plan_id="plan-42", product_id="prod-1")
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.parent_id == "plan-42"

    def test_product_id_when_only_product(self):
        """product_id is used when both parent_task_id and plan_id are None."""
        task = _make_task(parent_task_id=None, plan_id=None, product_id="prod-99")
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.parent_id == "prod-99"

    def test_free_floating_task_has_none_parent(self):
        """All three affiliation fields None → parent_id is None."""
        task = _make_task(parent_task_id=None, plan_id=None, product_id=None)
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.parent_id is None

    def test_plan_id_and_parent_task_id_both_set_uses_parent_task(self):
        """Explicit subtask scenario: parent_task_id wins."""
        task = _make_task(parent_task_id="task-x", plan_id="plan-x")
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.parent_id == "task-x"


# ──────────────────────────────────────────────
# depends_on union (fix-4)
# ──────────────────────────────────────────────

class TestDependsOnUnion:
    def test_depends_on_is_union_of_both_lists(self):
        """depends_on merges depends_on_task_ids + blocked_by."""
        task = _make_task(
            depends_on_task_ids=["task-a", "task-b"],
            blocked_by=["task-c"],
        )
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert set(entity.depends_on) == {"task-a", "task-b", "task-c"}

    def test_depends_on_deduplicates_overlapping_entries(self):
        """Entries present in both lists appear only once in depends_on."""
        task = _make_task(
            depends_on_task_ids=["task-a", "task-b"],
            blocked_by=["task-b", "task-c"],
        )
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.depends_on == ["task-a", "task-b", "task-c"]

    def test_depends_on_preserves_order_first_list_then_second(self):
        """Order: depends_on_task_ids entries first, then new blocked_by entries."""
        task = _make_task(
            depends_on_task_ids=["task-1", "task-2"],
            blocked_by=["task-3", "task-4"],
        )
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.depends_on == ["task-1", "task-2", "task-3", "task-4"]

    def test_depends_on_only_depends_on_task_ids(self):
        """blocked_by empty: depends_on = depends_on_task_ids."""
        task = _make_task(depends_on_task_ids=["task-x"], blocked_by=[])
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.depends_on == ["task-x"]

    def test_depends_on_only_blocked_by(self):
        """depends_on_task_ids empty: depends_on = blocked_by."""
        task = _make_task(depends_on_task_ids=[], blocked_by=["task-y"])
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.depends_on == ["task-y"]

    def test_depends_on_both_empty(self):
        """Both lists empty → depends_on empty."""
        task = _make_task(depends_on_task_ids=[], blocked_by=[])
        entity = task_to_l3_entity(task, partner_id=_PARTNER_ID)
        assert entity.depends_on == []

    def test_reverse_depends_on_restores_depends_on_task_ids_only(self):
        """fix-9: l3_entity_to_task restores depends_on_task_ids but leaves blocked_by empty.

        L3.depends_on is the prerequisite chain, not the blocked-by semantic.
        The reverse path cannot reconstruct the distinction, so blocked_by is
        left as an empty list to avoid marking runnable tasks as blocked.
        """
        entity = _make_l3_task(depends_on=["task-a", "task-b"])
        restored = l3_entity_to_task(entity)
        assert restored.depends_on_task_ids == ["task-a", "task-b"]
        assert restored.blocked_by == []   # fix-9: not mirrored from L3.depends_on

    def test_reverse_depends_on_empty_sets_both_empty(self):
        """Empty depends_on → both legacy lists empty."""
        entity = _make_l3_task(depends_on=[])
        restored = l3_entity_to_task(entity)
        assert restored.depends_on_task_ids == []
        assert restored.blocked_by == []


# ──────────────────────────────────────────────
# l3_entity_to_task — created_by kwarg (fix-2)
# ──────────────────────────────────────────────

class TestCreatedByKwarg:
    def test_created_by_from_kwarg(self):
        entity = _make_l3_task()
        restored = l3_entity_to_task(entity, created_by="user-42")
        assert restored.created_by == "user-42"

    def test_created_by_defaults_to_empty_string(self):
        """Without kwarg, created_by falls back to empty string (legacy behaviour)."""
        entity = _make_l3_task()
        restored = l3_entity_to_task(entity)
        assert restored.created_by == ""

    def test_created_by_empty_string_kwarg(self):
        entity = _make_l3_task()
        restored = l3_entity_to_task(entity, created_by="")
        assert restored.created_by == ""


# ──────────────────────────────────────────────
# Round-trip: Task → L3TaskEntity → Task (5 shapes)
# ──────────────────────────────────────────────

class TestTaskRoundTrip:
    def test_core_fields_survive_round_trip(self):
        original = _make_task()
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity, created_by=original.created_by, original=original)

        assert restored.title == original.title
        assert restored.status == original.status
        assert restored.priority == original.priority
        assert restored.description == original.description
        assert restored.assignee == original.assignee
        assert restored.acceptance_criteria == original.acceptance_criteria
        assert restored.result == original.result
        assert restored.plan_order == original.plan_order
        assert restored.blocked_reason == original.blocked_reason
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at

    # ── Shape 1: subtask (parent_task_id set) ──

    def test_shape_subtask_parent_task_id_restored(self):
        """Subtask: parent_task_id non-null → restored to parent_task_id after round-trip."""
        original = _make_task(
            parent_task_id="task-parent",
            plan_id=None,
            product_id=None,
        )
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        assert entity.parent_id == "task-parent"

        restored = l3_entity_to_task(entity, original=original)
        assert restored.parent_task_id == "task-parent"
        assert restored.plan_id is None
        assert restored.product_id is None

    def test_shape_subtask_partner_id_preserved(self):
        original = _make_task(parent_task_id="task-parent", plan_id=None, product_id=None)
        entity = task_to_l3_entity(original, partner_id="P1")
        assert entity.partner_id == "P1"

    def test_agent_dispatcher_plan_task_without_original_goes_to_plan_id(self):
        """agent:* dispatcher is valid for plan-level tasks; without original hint,
        heuristic must NOT misclassify as subtask. Falls through to plan_id."""
        entity = _make_l3_task(
            parent_id="plan-x",
            type_label="task",
            dispatcher="agent:developer",
        )
        restored = l3_entity_to_task(entity)
        assert restored.plan_id == "plan-x"
        assert restored.parent_task_id is None

    def test_shape_subtask_type_label_heuristic(self):
        """type_label='subtask' → heuristic routes parent_id to parent_task_id."""
        entity = _make_l3_task(
            parent_id="task-parent",
            type_label="subtask",
            dispatcher="human",
        )
        restored = l3_entity_to_task(entity)
        assert restored.parent_task_id == "task-parent"
        assert restored.plan_id is None

    # ── Shape 2: plan_task (plan_id set) ──

    def test_shape_plan_task_plan_id_restored(self):
        """plan_task: plan_id non-null, parent_task_id null → plan_id restored."""
        original = _make_task(
            parent_task_id=None,
            plan_id="plan-99",
            product_id=None,
        )
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        assert entity.parent_id == "plan-99"

        restored = l3_entity_to_task(entity, original=original)
        assert restored.plan_id == "plan-99"
        assert restored.parent_task_id is None
        assert restored.product_id is None

    def test_plan_id_restored_for_regular_task(self):
        """Task with plan_id (no parent_task_id) → parent_id maps back to plan_id."""
        original = _make_task(parent_task_id=None, plan_id="plan-1", product_id="prod-1")
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity, original=original)
        assert restored.plan_id == "plan-1"

    def test_shape_plan_task_heuristic_without_original(self):
        """Without original, non-agent dispatcher + non-subtask type → plan_id."""
        entity = _make_l3_task(
            parent_id="plan-42",
            type_label="task",
            dispatcher="human",
        )
        restored = l3_entity_to_task(entity)
        assert restored.plan_id == "plan-42"
        assert restored.parent_task_id is None

    # ── Shape 3: product_root_task (product_id set, no plan/parent_task) ──

    def test_shape_product_root_task_product_id_restored(self):
        """product_root_task: product_id set, plan_id null, parent_task_id null → product_id restored."""
        original = _make_task(
            parent_task_id=None,
            plan_id=None,
            product_id="product-root",
        )
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        assert entity.parent_id == "product-root"

        restored = l3_entity_to_task(entity, original=original)
        assert restored.product_id == "product-root"
        assert restored.plan_id is None
        assert restored.parent_task_id is None

    # ── Shape 4: blocked_task (blocked_by + depends_on_task_ids both set) ──

    def test_shape_blocked_task_depends_on_union(self):
        """blocked_task: both blocked_by and depends_on_task_ids → union in L3."""
        original = _make_task(
            depends_on_task_ids=["task-a"],
            blocked_by=["task-b"],
        )
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        assert set(entity.depends_on) == {"task-a", "task-b"}

    def test_shape_blocked_task_reverse_depends_on_task_ids_and_blocked_by_empty(self):
        """fix-9: After round-trip depends_on_task_ids == L3.depends_on; blocked_by == [].

        The forward direction merges both lists into L3.depends_on (union).
        The reverse direction only restores depends_on_task_ids; blocked_by is
        left empty because the prerequisite-chain vs blocked-state semantic is
        irrecoverably lost in the L3 layer.
        """
        original = _make_task(
            depends_on_task_ids=["task-a"],
            blocked_by=["task-b"],
        )
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity, original=original)
        assert restored.depends_on_task_ids == list(entity.depends_on)
        assert restored.blocked_by == []   # fix-9: not mirrored

    def test_shape_blocked_task_partner_id(self):
        original = _make_task(depends_on_task_ids=["t-1"], blocked_by=["t-2"])
        entity = task_to_l3_entity(original, partner_id="P1")
        assert entity.partner_id == "P1"

    # ── Shape 5: no_parent (all affiliation fields null) ──

    def test_shape_no_parent_all_affiliation_null(self):
        """Free-floating task: all affiliation fields null → parent_id None, restored null."""
        original = _make_task(
            parent_task_id=None,
            plan_id=None,
            product_id=None,
        )
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        assert entity.parent_id is None

        restored = l3_entity_to_task(entity, original=original)
        assert restored.plan_id is None
        assert restored.parent_task_id is None
        assert restored.product_id is None

    def test_shape_no_parent_without_original_hint(self):
        """No parent_id on entity → all legacy affiliation fields remain null."""
        entity = _make_l3_task(parent_id=None)
        restored = l3_entity_to_task(entity)
        assert restored.plan_id is None
        assert restored.parent_task_id is None
        assert restored.product_id is None

    def test_handoff_events_survive_round_trip(self):
        he = HandoffEvent(at=_NOW, from_dispatcher="human", to_dispatcher="agent:developer", reason="start")
        original = _make_task(handoff_events=[he])
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity)
        assert len(restored.handoff_events) == 1
        assert restored.handoff_events[0].reason == "start"

    def test_due_date_survives_round_trip(self):
        original = _make_task(due_date=datetime(2026, 6, 15))
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity)
        assert restored.due_date is not None
        assert restored.due_date.date() == date(2026, 6, 15)

    def test_due_date_none_survives_round_trip(self):
        original = _make_task(due_date=None)
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity)
        assert restored.due_date is None

    def test_dispatcher_none_in_task_becomes_human(self):
        """Task.dispatcher=None → L3 entity.dispatcher='human' → restored as None."""
        original = _make_task(dispatcher=None)
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        assert entity.dispatcher == "human"
        restored = l3_entity_to_task(entity)
        assert restored.dispatcher is None

    def test_created_by_restored_via_kwarg(self):
        """created_by hint survives round-trip when provided as kwarg."""
        original = _make_task(created_by="U1")
        entity = task_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_entity_to_task(entity, created_by="U1")
        assert restored.created_by == "U1"


# ──────────────────────────────────────────────
# plan_to_l3_entity — partner_id kwarg (fix-2)
# ──────────────────────────────────────────────

class TestPlanToL3Entity:
    def test_partner_id_from_kwarg_not_product_id(self):
        """partner_id must come from kwarg, never from plan.product_id."""
        plan = _make_plan(product_id="some-l1-entity-id")
        entity = plan_to_l3_entity(plan, partner_id="real-tenant-id")
        assert entity.partner_id == "real-tenant-id"
        assert entity.partner_id != "some-l1-entity-id"

    def test_partner_id_set_correctly(self):
        plan = _make_plan()
        entity = plan_to_l3_entity(plan, partner_id=_PARTNER_ID)
        assert entity.partner_id == _PARTNER_ID

    def test_product_id_preserved_as_parent_id(self):
        """plan.product_id still flows to entity.parent_id (L1 → parent of plan)."""
        plan = _make_plan(product_id="product-root")
        entity = plan_to_l3_entity(plan, partner_id=_PARTNER_ID)
        assert entity.parent_id == "product-root"


# ──────────────────────────────────────────────
# Plan ↔ L3PlanEntity round-trip
# ──────────────────────────────────────────────

class TestPlanRoundTrip:
    def test_basic_conversion(self):
        plan = _make_plan()
        entity = plan_to_l3_entity(plan, partner_id=_PARTNER_ID)

        assert entity.id == "plan-1"
        assert entity.type_label == "plan"
        assert entity.level == 3
        assert entity.task_status == "active"
        assert entity.goal_statement == "Ship Wave 9"
        assert entity.entry_criteria == "Phase A done"
        assert entity.exit_criteria == "All tests pass"
        assert entity.parent_id == "product-1"

    def test_core_fields_survive_round_trip(self):
        original = _make_plan()
        entity = plan_to_l3_entity(original, partner_id=_PARTNER_ID)
        restored = l3_plan_entity_to_plan(entity, created_by=original.created_by)

        assert restored.id == original.id
        assert restored.goal == original.goal
        assert restored.status == original.status
        assert restored.entry_criteria == original.entry_criteria
        assert restored.exit_criteria == original.exit_criteria
        assert restored.product_id == original.product_id
        assert restored.result == original.result
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at

    def test_plan_with_no_entry_exit_criteria(self):
        plan = _make_plan(entry_criteria=None, exit_criteria=None)
        entity = plan_to_l3_entity(plan, partner_id=_PARTNER_ID)
        assert entity.entry_criteria == ""
        assert entity.exit_criteria == ""
        restored = l3_plan_entity_to_plan(entity)
        assert restored.entry_criteria is None
        assert restored.exit_criteria is None

    def test_plan_created_by_kwarg(self):
        """l3_plan_entity_to_plan accepts created_by kwarg."""
        plan = _make_plan()
        entity = plan_to_l3_entity(plan, partner_id=_PARTNER_ID)
        restored = l3_plan_entity_to_plan(entity, created_by="user-99")
        assert restored.created_by == "user-99"

    def test_plan_created_by_defaults_to_empty_string(self):
        plan = _make_plan()
        entity = plan_to_l3_entity(plan, partner_id=_PARTNER_ID)
        restored = l3_plan_entity_to_plan(entity)
        assert restored.created_by == ""

    def test_plan_partner_id_round_trip_does_not_bleed(self):
        """Plan.product_id ≠ partner_id: ensure product_id is preserved correctly."""
        plan = _make_plan(product_id="prod-xyz")
        entity = plan_to_l3_entity(plan, partner_id="tenant-abc")
        # entity.partner_id == tenant_id; entity.parent_id == product_id
        assert entity.partner_id == "tenant-abc"
        assert entity.parent_id == "prod-xyz"
        restored = l3_plan_entity_to_plan(entity)
        assert restored.product_id == "prod-xyz"
