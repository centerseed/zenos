"""ZenOS Domain — Action Layer Models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

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
    project_id: str | None = None
    updated_by: str | None = None
    result: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


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
    project_id: str | None = None  # Link to product/project entity ID
    attachments: list[dict] = field(default_factory=list)  # [{id, filename, content_type, gcs_path, ...}]
    # Action-Layer upgrade fields (2026-04-19)
    parent_task_id: str | None = None
    dispatcher: str | None = None
    handoff_events: list[HandoffEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
