"""Abstract repository interfaces — pure typing.Protocol, zero external deps."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .models import (
    Blindspot,
    Document,
    Entity,
    Protocol,
    Relationship,
)


class EntityRepository(TypingProtocol):
    """Persistence interface for skeleton-layer entities."""

    async def get_by_id(self, entity_id: str) -> Entity | None: ...

    async def get_by_name(self, name: str) -> Entity | None: ...

    async def list_all(self, type_filter: str | None = None) -> list[Entity]: ...

    async def upsert(self, entity: Entity) -> Entity: ...

    async def list_unconfirmed(self) -> list[Entity]: ...


class RelationshipRepository(TypingProtocol):
    """Persistence interface for skeleton-layer relationships."""

    async def list_by_entity(self, entity_id: str) -> list[Relationship]: ...

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

    async def get_by_entity(self, entity_id: str) -> Protocol | None: ...

    async def get_by_entity_name(self, name: str) -> Protocol | None: ...

    async def upsert(self, protocol: Protocol) -> Protocol: ...

    async def list_unconfirmed(self) -> list[Protocol]: ...


class BlindspotRepository(TypingProtocol):
    """Persistence interface for governance blindspot findings."""

    async def list_all(
        self,
        entity_id: str | None = None,
        severity: str | None = None,
    ) -> list[Blindspot]: ...

    async def add(self, blindspot: Blindspot) -> Blindspot: ...

    async def list_unconfirmed(self) -> list[Blindspot]: ...


class SourceAdapter(TypingProtocol):
    """Read-only access to external document content."""

    async def read_content(self, uri: str) -> str: ...
