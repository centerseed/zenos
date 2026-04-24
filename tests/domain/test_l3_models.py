"""Tests for Wave 9 L3-Action entity dataclasses.

Verifies:
- SPEC §9.1-§9.5 field compliance for all 5 new classes
- Inheritance chain
- Default values
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from zenos.domain.action.models import (
    HandoffEvent,
    L3MilestoneEntity,
    L3PlanEntity,
    L3SubtaskEntity,
    L3TaskBaseEntity,
    L3TaskEntity,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

_NOW = datetime(2026, 4, 23, 12, 0, 0)
_HANDOFF = HandoffEvent(
    at=_NOW,
    from_dispatcher=None,
    to_dispatcher="agent:developer",
    reason="initial dispatch",
)


def _base_kwargs(**overrides) -> dict:
    """Minimal valid kwargs for L3TaskBaseEntity (and subclasses)."""
    base = dict(
        id="entity-1",
        partner_id="partner-abc",
        name="Test Task",
        type_label="task",
        level=3,
        parent_id="plan-1",
        status="active",
        created_at=_NOW,
        updated_at=_NOW,
        description="Do the thing",
        task_status="todo",
        assignee=None,
        dispatcher="agent:developer",
    )
    base.update(overrides)
    return base


# ──────────────────────────────────────────────
# L3TaskBaseEntity — SPEC §9.1
# ──────────────────────────────────────────────

class TestL3TaskBaseEntityDataclassFields:
    """SPEC §9.1 compliance: entities_base + L3-Action shared fields."""

    def test_required_entities_base_fields_present(self):
        entity = L3TaskBaseEntity(**_base_kwargs())
        assert entity.id == "entity-1"
        assert entity.partner_id == "partner-abc"
        assert entity.name == "Test Task"
        assert entity.type_label == "task"
        assert entity.level == 3
        assert entity.parent_id == "plan-1"
        assert entity.status == "active"
        assert entity.created_at == _NOW
        assert entity.updated_at == _NOW

    def test_required_l3_action_shared_fields_present(self):
        entity = L3TaskBaseEntity(**_base_kwargs())
        assert entity.description == "Do the thing"
        assert entity.task_status == "todo"
        assert entity.assignee is None
        assert entity.dispatcher == "agent:developer"

    def test_default_optional_fields(self):
        entity = L3TaskBaseEntity(**_base_kwargs())
        assert entity.acceptance_criteria == []
        assert entity.priority == "medium"
        assert entity.result is None
        assert entity.handoff_events == []

    def test_parent_id_can_be_none(self):
        entity = L3TaskBaseEntity(**_base_kwargs(parent_id=None))
        assert entity.parent_id is None

    def test_with_handoff_events(self):
        entity = L3TaskBaseEntity(**_base_kwargs(handoff_events=[_HANDOFF]))
        assert len(entity.handoff_events) == 1
        assert entity.handoff_events[0].to_dispatcher == "agent:developer"

    def test_with_acceptance_criteria(self):
        criteria = ["tests pass", "review approved"]
        entity = L3TaskBaseEntity(**_base_kwargs(acceptance_criteria=criteria))
        assert entity.acceptance_criteria == criteria

    def test_level_is_always_3(self):
        entity = L3TaskBaseEntity(**_base_kwargs())
        assert entity.level == 3

    def test_kw_only_instantiation(self):
        """L3TaskBaseEntity uses kw_only=True; positional args must fail."""
        with pytest.raises(TypeError):
            L3TaskBaseEntity(  # type: ignore[call-arg]
                "entity-1", "partner-abc", "name", "task", 3, None, "active",
                _NOW, _NOW, "desc", "todo", None, "human",
            )


# ──────────────────────────────────────────────
# L3MilestoneEntity — SPEC §9.2
# ──────────────────────────────────────────────

class TestL3MilestoneEntityDataclassFields:
    """SPEC §9.2 compliance: L3TaskBaseEntity + target_date + completion_criteria."""

    def _make(self, **overrides) -> L3MilestoneEntity:
        return L3MilestoneEntity(**_base_kwargs(type_label="milestone", **overrides))

    def test_inherits_base_fields(self):
        m = self._make()
        assert m.id == "entity-1"
        assert m.type_label == "milestone"

    def test_target_date_defaults_none(self):
        m = self._make()
        assert m.target_date is None

    def test_completion_criteria_defaults_none(self):
        m = self._make()
        assert m.completion_criteria is None

    def test_target_date_set(self):
        td = date(2026, 6, 30)
        m = self._make(target_date=td)
        assert m.target_date == td

    def test_completion_criteria_set(self):
        cc = "All acceptance criteria met and signed off"
        m = self._make(completion_criteria=cc)
        assert m.completion_criteria == cc

    def test_is_subclass_of_base(self):
        m = self._make()
        assert isinstance(m, L3TaskBaseEntity)

    def test_task_status_values(self):
        """task_status for milestones: planned|active|completed|cancelled."""
        for ts in ("planned", "active", "completed", "cancelled"):
            m = self._make(task_status=ts)
            assert m.task_status == ts


# ──────────────────────────────────────────────
# L3PlanEntity — SPEC §9.3
# ──────────────────────────────────────────────

class TestL3PlanEntityDataclassFields:
    """SPEC §9.3 compliance: L3TaskBaseEntity + goal/entry/exit criteria."""

    def _make(self, **overrides) -> L3PlanEntity:
        return L3PlanEntity(**_base_kwargs(type_label="plan", **overrides))

    def test_inherits_base_fields(self):
        p = self._make()
        assert p.type_label == "plan"

    def test_goal_statement_defaults_empty(self):
        p = self._make()
        assert p.goal_statement == ""

    def test_entry_criteria_defaults_empty(self):
        p = self._make()
        assert p.entry_criteria == ""

    def test_exit_criteria_defaults_empty(self):
        p = self._make()
        assert p.exit_criteria == ""

    def test_fields_set(self):
        p = self._make(
            goal_statement="Ship Wave 9",
            entry_criteria="Phase A done",
            exit_criteria="All tests pass + QA sign-off",
        )
        assert p.goal_statement == "Ship Wave 9"
        assert p.entry_criteria == "Phase A done"
        assert p.exit_criteria == "All tests pass + QA sign-off"

    def test_is_subclass_of_base(self):
        p = self._make()
        assert isinstance(p, L3TaskBaseEntity)

    def test_task_status_values(self):
        """task_status for plans: draft|active|completed|cancelled."""
        for ts in ("draft", "active", "completed", "cancelled"):
            p = self._make(task_status=ts)
            assert p.task_status == ts


# ──────────────────────────────────────────────
# L3TaskEntity — SPEC §9.4
# ──────────────────────────────────────────────

class TestL3TaskEntityDataclassFields:
    """SPEC §9.4 compliance: L3TaskBaseEntity + plan_order/depends_on/blocked_reason/due_date."""

    def _make(self, **overrides) -> L3TaskEntity:
        return L3TaskEntity(**_base_kwargs(type_label="task", **overrides))

    def test_inherits_base_fields(self):
        t = self._make()
        assert t.type_label == "task"

    def test_plan_order_defaults_none(self):
        t = self._make()
        assert t.plan_order is None

    def test_depends_on_defaults_empty(self):
        t = self._make()
        assert t.depends_on == []

    def test_blocked_reason_defaults_none(self):
        t = self._make()
        assert t.blocked_reason is None

    def test_due_date_defaults_none(self):
        t = self._make()
        assert t.due_date is None

    def test_all_specific_fields_set(self):
        dd = date(2026, 5, 1)
        t = self._make(
            plan_order=2,
            depends_on=["task-a", "task-b"],
            blocked_reason="waiting on external API",
            due_date=dd,
        )
        assert t.plan_order == 2
        assert t.depends_on == ["task-a", "task-b"]
        assert t.blocked_reason == "waiting on external API"
        assert t.due_date == dd

    def test_is_subclass_of_base(self):
        t = self._make()
        assert isinstance(t, L3TaskBaseEntity)

    def test_task_status_values(self):
        """task_status for tasks: todo|in_progress|review|done|cancelled."""
        for ts in ("todo", "in_progress", "review", "done", "cancelled"):
            t = self._make(task_status=ts)
            assert t.task_status == ts


# ──────────────────────────────────────────────
# L3SubtaskEntity — SPEC §9.5
# ──────────────────────────────────────────────

class TestL3SubtaskEntityDataclassFields:
    """SPEC §9.5 compliance: L3TaskEntity + dispatched_by_agent + auto_created."""

    def _make(self, **overrides) -> L3SubtaskEntity:
        return L3SubtaskEntity(**_base_kwargs(type_label="subtask", **overrides))

    def test_inherits_l3_task_entity(self):
        s = self._make()
        assert isinstance(s, L3TaskEntity)
        assert isinstance(s, L3TaskBaseEntity)

    def test_dispatched_by_agent_defaults_empty(self):
        s = self._make()
        assert s.dispatched_by_agent == ""

    def test_auto_created_defaults_true(self):
        s = self._make()
        assert s.auto_created is True

    def test_fields_set(self):
        s = self._make(dispatched_by_agent="agent:developer", auto_created=False)
        assert s.dispatched_by_agent == "agent:developer"
        assert s.auto_created is False

    def test_inherits_task_entity_specific_fields(self):
        s = self._make(plan_order=1, depends_on=["task-x"])
        assert s.plan_order == 1
        assert s.depends_on == ["task-x"]

    def test_type_label(self):
        s = self._make()
        assert s.type_label == "subtask"


# ──────────────────────────────────────────────
# Cross-class invariants
# ──────────────────────────────────────────────

class TestL3ClassInheritanceChain:
    def test_subtask_is_task_is_base(self):
        s = L3SubtaskEntity(**_base_kwargs(type_label="subtask"))
        assert isinstance(s, L3SubtaskEntity)
        assert isinstance(s, L3TaskEntity)
        assert isinstance(s, L3TaskBaseEntity)

    def test_milestone_is_base_not_task(self):
        m = L3MilestoneEntity(**_base_kwargs(type_label="milestone"))
        assert isinstance(m, L3TaskBaseEntity)
        assert not isinstance(m, L3TaskEntity)

    def test_plan_is_base_not_task(self):
        p = L3PlanEntity(**_base_kwargs(type_label="plan"))
        assert isinstance(p, L3TaskBaseEntity)
        assert not isinstance(p, L3TaskEntity)

    def test_all_level_3(self):
        for cls, label in [
            (L3MilestoneEntity, "milestone"),
            (L3PlanEntity, "plan"),
            (L3TaskEntity, "task"),
            (L3SubtaskEntity, "subtask"),
        ]:
            entity = cls(**_base_kwargs(type_label=label))
            assert entity.level == 3
