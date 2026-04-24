"""ZenOS Domain — Action Layer Models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

# Dispatcher namespace pattern — single source of truth (used by write and handoff validators)
DISPATCHER_PATTERN = re.compile(r"^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$")


@dataclass
class HandoffEvent:
    """A single dispatcher-handoff record appended to Task.handoff_events.

    Append-only. Created by task(action="handoff") and confirm(), never by
    direct write(). Server generates ``at`` and ``from_dispatcher``.
    """
    at: datetime
    from_dispatcher: str | None
    to_dispatcher: str
    reason: str
    output_ref: str | None = None
    notes: str | None = None


@dataclass
class Plan:
    """Action Layer plan: a grouping, sequencing, and completion boundary for tasks.

    Plans are owned by a partner and group related tasks under a shared goal.
    A plan defines entry/exit criteria and tracks its own lifecycle independently
    from its constituent tasks.
    """
    goal: str
    status: str  # PlanStatus value
    created_by: str
    id: str | None = None
    owner: str | None = None
    entry_criteria: str | None = None
    exit_criteria: str | None = None
    project: str = ""
    product_id: str | None = None
    updated_by: str | None = None
    result: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def project_id(self) -> str | None:
        """Deprecated alias kept for backward-compatible reads."""
        return self.product_id

    @project_id.setter
    def project_id(self, value: str | None) -> None:
        self.product_id = value


@dataclass
class Task:
    """Action Layer task: a knowledge-driven action item.

    Tasks live above the ontology layer. They reference ontology entries
    via linked_entities / linked_protocol / linked_blindspot, but have
    their own lifecycle (status, priority, assignee, due date).
    """
    title: str
    status: str  # TaskStatus value
    priority: str  # TaskPriority value
    created_by: str
    updated_by: str | None = None
    id: str | None = None
    description: str = ""
    priority_reason: str = ""
    assignee: str | None = None
    linked_entities: list[str] = field(default_factory=list)
    linked_protocol: str | None = None
    linked_blindspot: str | None = None
    source_type: str = ""
    source_metadata: dict[str, object] = field(default_factory=dict)
    context_summary: str = ""
    due_date: datetime | None = None
    assignee_role_id: str | None = None
    plan_id: str | None = None
    plan_order: int | None = None
    depends_on_task_ids: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    acceptance_criteria: list[str] = field(default_factory=list)
    completed_by: str | None = None
    creator_name: str | None = None
    assignee_name: str | None = None
    confirmed_by_creator: bool = False
    rejection_reason: str | None = None
    result: str | None = None
    project: str = ""  # Partner-level project grouping (e.g. "zenos", "paceriz")
    product_id: str | None = None
    attachments: list[dict] = field(default_factory=list)  # [{id, filename, content_type, gcs_path, ...}]
    # Action-Layer upgrade fields (2026-04-19)
    parent_task_id: str | None = None
    dispatcher: str | None = None
    handoff_events: list[HandoffEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def project_id(self) -> str | None:
        """Deprecated alias kept for backward-compatible reads."""
        return self.product_id

    @project_id.setter
    def project_id(self, value: str | None) -> None:
        self.product_id = value


# ──────────────────────────────────────────────────────────────
# Wave 9 L3-Action Entity dataclasses (Phase B — domain only)
#
# These coexist with the legacy Task / Plan dataclasses.
# Repo / MCP / application layers still use Task / Plan.
# Converters (see converters.py) bridge old ↔ new shapes.
# ──────────────────────────────────────────────────────────────


@dataclass(kw_only=True)
class L3TaskBaseEntity:
    """Wave 9 L3-Action entity base (abstract; do not instantiate directly).

    Subclass of entities_base + adds action-layer fields common to all
    L3-Action subclasses (milestone / plan / task / subtask).

    Notes:
        - L3-Action does NOT carry SemanticMixin (no tags / confirmed_by_user).
        - ``status`` here is the BaseEntity lifecycle status ("active" for tasks).
        - ``task_status`` carries the business-level status enum.
        - ``parent_id`` encodes all affiliation (replaces product_id / plan_id tree).
        - ``handoff_events`` is kept in-memory in Phase B; Phase C repo will
          persist to the dedicated ``task_handoff_events`` table.
    """

    # entities_base fields
    id: str
    partner_id: str
    name: str
    type_label: str          # 'task' | 'plan' | 'subtask' | 'milestone'
    level: int               # always 3 for L3-Action entities
    parent_id: str | None
    status: str              # EntityStatus lifecycle ("active" for all live tasks)
    created_at: datetime
    updated_at: datetime

    # L3-Action shared fields (SPEC §9.1)
    description: str
    task_status: str         # business-level status; values depend on subclass
    assignee: str | None
    dispatcher: str          # agent:xxx | human[:id] — matches DISPATCHER_PATTERN
    acceptance_criteria: list[str] = field(default_factory=list)
    priority: str = "medium"    # critical | high | medium | low
    result: str | None = None
    handoff_events: list[HandoffEvent] = field(default_factory=list)


@dataclass(kw_only=True)
class L3MilestoneEntity(L3TaskBaseEntity):
    """Wave 9 L3-Action Milestone — merges old Goal concept (SPEC §9.2).

    task_status enum: planned | active | completed | cancelled
    """

    target_date: date | None = None
    completion_criteria: str | None = None


@dataclass(kw_only=True)
class L3PlanEntity(L3TaskBaseEntity):
    """Wave 9 L3-Action Plan — task grouping boundary (SPEC §9.3).

    task_status enum: draft | active | completed | cancelled
    """

    goal_statement: str = ""
    entry_criteria: str = ""
    exit_criteria: str = ""


@dataclass(kw_only=True)
class L3TaskEntity(L3TaskBaseEntity):
    """Wave 9 L3-Action Task — executable work item (SPEC §9.4).

    task_status enum: todo | in_progress | review | done | cancelled

    Notes:
        - ``depends_on`` holds task entity IDs that block this task
          (replaces the legacy ``depends_on_task_ids`` / ``blocked_by`` lists).
        - ``due_date`` is a calendar date, not a datetime.
    """

    plan_order: int | None = None
    depends_on: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    due_date: date | None = None


@dataclass(kw_only=True)
class L3SubtaskEntity(L3TaskEntity):
    """Wave 9 L3-Action Subtask — agent-dispatched sub-unit (SPEC §9.5).

    Subtask is a specialisation of L3TaskEntity:
    - parent_id MUST point to an L3TaskEntity
    - typically created automatically by an agent (auto_created=True)
    """

    dispatched_by_agent: str = ""
    auto_created: bool = True
