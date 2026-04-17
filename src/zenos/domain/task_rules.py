"""Task state machine and priority recommendation engine.

Pure functions, zero external dependencies. Encodes the Action Layer
business rules from spec.md Part 7.1.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .action import Task, TaskPriority, TaskStatus
from .knowledge import Blindspot, Entity, EntityStatus, Severity

# ──────────────────────────────────────────────
# State machine
# ──────────────────────────────────────────────

# Adjacency set: (from_status, to_status) pairs that are legal.
_VALID_TRANSITIONS: set[tuple[str, str]] = {
    # from todo
    (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
    (TaskStatus.TODO, TaskStatus.CANCELLED),
    # from in_progress
    (TaskStatus.IN_PROGRESS, TaskStatus.TODO),
    (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW),
    (TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED),
    # from review (done only via confirm_task, not update_task)
    (TaskStatus.REVIEW, TaskStatus.IN_PROGRESS),
    (TaskStatus.REVIEW, TaskStatus.DONE),
    (TaskStatus.REVIEW, TaskStatus.CANCELLED),
    # from done (allow reopen)
    (TaskStatus.DONE, TaskStatus.TODO),
}

# Statuses that can be set by update_task (review→done must go via confirm_task)
_UPDATE_FORBIDDEN_TARGETS = {TaskStatus.DONE}

# Valid initial statuses for create_task
_INITIAL_STATUSES = {TaskStatus.TODO}


def normalize_task_status(status: str) -> str:
    """Map deprecated statuses into canonical statuses."""
    return {
        "backlog": TaskStatus.TODO,
        "blocked": TaskStatus.TODO,
        "archived": TaskStatus.DONE,
    }.get(status, status)


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Check if a status transition is legal."""
    return (from_status, to_status) in _VALID_TRANSITIONS


def is_valid_update_target(to_status: str) -> bool:
    """Check if update_task can set this status (done is forbidden)."""
    return to_status not in _UPDATE_FORBIDDEN_TARGETS


def is_valid_initial_status(status: str) -> bool:
    """Check if create_task can use this status."""
    return status in _INITIAL_STATUSES


# ──────────────────────────────────────────────
# Priority recommendation engine (rule-based)
# ──────────────────────────────────────────────

def recommend_priority(
    linked_entities: list[Entity],
    linked_blindspot: Blindspot | None,
    due_date: datetime | None,
    blocked_by_count: int,
    blocking_others_count: int,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Recommend priority based on ontology context.

    Returns (priority, reason_text).
    The caller can override the priority; the reason is always stored.
    """
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = _ensure_utc(now)

    score = 0
    reasons: list[str] = []

    # Rule 1: linked to blindspot
    if linked_blindspot:
        if linked_blindspot.severity == Severity.RED:
            score += 2
            reasons.append(
                f"連結到 severity=red 盲點：{linked_blindspot.description[:40]}"
            )
        elif linked_blindspot.severity == Severity.YELLOW:
            score += 1
            reasons.append("連結到 severity=yellow 盲點")

    # Rule 2: linked to active entity (+1, only count once)
    active_entity = next(
        (e for e in linked_entities if e.status == EntityStatus.ACTIVE), None
    )
    if active_entity:
        score += 1
        reasons.append(f"連結到 active 實體：{active_entity.name}")

    # Rule 3: linked to paused entity (-1, only count once)
    paused_entity = next(
        (e for e in linked_entities if e.status == EntityStatus.PAUSED), None
    )
    if paused_entity:
        score -= 1
        reasons.append(f"連結到 paused 實體：{paused_entity.name}")

    # Rule 4: due date < 3 days
    if due_date:
        due_date = _ensure_utc(due_date)
        days_left = (due_date - now).days
        if days_left < 3:
            score += 3
            reasons.append(f"距離到期日只剩 {max(days_left, 0)} 天")

    # Rule 5: blocked by others
    if blocked_by_count > 0:
        score -= 1
        reasons.append("被其他任務阻塞中")

    # Rule 6: blocking others (they're waiting for this)
    if blocking_others_count > 0:
        score += 1
        reasons.append(f"有 {blocking_others_count} 個任務在等這個完成")

    # Rule 7: cross-entity impact
    if len(linked_entities) >= 3:
        score += 1
        reasons.append("跨多個實體，影響範圍大")

    # Score → Priority
    if score >= 3:
        priority = TaskPriority.CRITICAL
    elif score >= 2:
        priority = TaskPriority.HIGH
    elif score >= 0:
        priority = TaskPriority.MEDIUM
    else:
        priority = TaskPriority.LOW

    reason_text = "；".join(reasons) if reasons else "無特殊訊號，預設 medium"
    return priority, reason_text
