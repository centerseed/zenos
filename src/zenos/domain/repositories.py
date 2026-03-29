"""Abstract repository interfaces — pure typing.Protocol, zero external deps."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .models import (
    Blindspot,
    Document,
    Entity,
    Protocol,
    Relationship,
    Task,
)


class EntityRepository(TypingProtocol):
    """Persistence interface for skeleton-layer entities."""

    async def get_by_id(self, entity_id: str) -> Entity | None: ...

    async def get_by_name(self, name: str) -> Entity | None: ...

    async def list_all(self, type_filter: str | None = None) -> list[Entity]: ...

    async def upsert(self, entity: Entity) -> Entity: ...

    async def list_unconfirmed(self) -> list[Entity]: ...

    async def list_by_parent(self, parent_id: str) -> list[Entity]: ...

    async def update_source_status(self, entity_id: str, new_status: str) -> None: ...

    async def archive_entity(self, entity_id: str) -> None: ...


class RelationshipRepository(TypingProtocol):
    """Persistence interface for skeleton-layer relationships."""

    async def list_by_entity(self, entity_id: str) -> list[Relationship]: ...

    async def find_duplicate(
        self, source_entity_id: str, target_id: str, rel_type: str,
    ) -> Relationship | None:
        """Find an existing relationship with the same source, target, and type."""
        ...

    async def add(self, rel: Relationship) -> Relationship: ...


class DocumentRepository(TypingProtocol):
    """Persistence interface for neural-layer documents."""

    async def get_by_id(self, doc_id: str) -> Document | None: ...

    async def list_all(self) -> list[Document]: ...

    async def upsert(self, doc: Document) -> Document: ...

    async def list_by_entity(self, entity_id: str) -> list[Document]: ...

    async def list_unconfirmed(self) -> list[Document]: ...


class ProtocolRepository(TypingProtocol):
    """Persistence interface for context protocols."""

    async def get_by_id(self, protocol_id: str) -> Protocol | None: ...

    async def get_by_entity(self, entity_id: str) -> Protocol | None: ...

    async def get_by_entity_name(self, name: str) -> Protocol | None: ...

    async def upsert(self, protocol: Protocol) -> Protocol: ...

    async def list_unconfirmed(self) -> list[Protocol]: ...


class BlindspotRepository(TypingProtocol):
    """Persistence interface for governance blindspot findings."""

    async def get_by_id(self, blindspot_id: str) -> Blindspot | None: ...

    async def list_all(
        self,
        entity_id: str | None = None,
        severity: str | None = None,
    ) -> list[Blindspot]: ...

    async def add(self, blindspot: Blindspot) -> Blindspot: ...

    async def list_unconfirmed(self) -> list[Blindspot]: ...


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
        limit: int = 50,
        project: str | None = None,
    ) -> list[Task]: ...

    async def list_blocked_by(self, task_id: str) -> list[Task]:
        """Find all tasks whose blockedBy contains task_id."""
        ...

    async def list_pending_review(self) -> list[Task]:
        """Tasks in review status with confirmedByCreator=false."""
        ...


class SourceAdapter(TypingProtocol):
    """Read-only access to external document content."""

    async def read_content(self, uri: str) -> str: ...
