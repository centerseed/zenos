"""ZenOS Domain — Action Layer Repository Interfaces."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .models import Task


class TaskRepository(TypingProtocol):
    """Persistence interface for Action Layer tasks."""

    async def get_by_id(self, task_id: str) -> Task | None: ...

    async def upsert(self, task: Task) -> Task: ...

    async def list_all(
        self,
        *,
        assignee: str | None = None,
        created_by: str | None = None,
        status: list[str] | None = None,
        priority: str | None = None,
        linked_entity: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
        project: str | None = None,
        plan_id: str | None = None,
    ) -> list[Task]: ...

    async def list_blocked_by(self, task_id: str) -> list[Task]:
        """Find all tasks whose blockedBy contains task_id."""
        ...

    async def list_pending_review(self) -> list[Task]:
        """Tasks in review status with confirmedByCreator=false."""
        ...
