"""ZenOS Domain — Action Layer Repository Interfaces."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .models import Plan, Task


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
        dispatcher: str | None = None,
        parent_task_id: str | None = None,
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

    async def find_by_id_prefix(self, prefix: str, partner_id: str, limit: int = 11) -> list[Task]:
        """Return tasks whose id starts with prefix, scoped to partner_id."""
        ...


class PlanRepository(TypingProtocol):
    """Persistence interface for Action Layer plans."""

    async def get_by_id(self, plan_id: str) -> Plan | None: ...

    async def upsert(self, plan: Plan) -> Plan: ...

    async def list_all(
        self,
        *,
        status: list[str] | None = None,
        project: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Plan]: ...
