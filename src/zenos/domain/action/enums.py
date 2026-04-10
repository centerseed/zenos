"""ZenOS Domain — Action Layer Enums."""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    TODO = "todo"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
