"""ZenOS Domain — Knowledge Layer Repository Interfaces."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .models import Blindspot, Document, Entity, Protocol, Relationship


class EntityRepository(TypingProtocol):
    """Persistence interface for skeleton-layer entities."""

    async def get_by_id(self, entity_id: str) -> Entity | None: ...

    async def get_by_name(self, name: str) -> Entity | None:
        """Look up an entity by name (case-insensitive exact match)."""
        ...

    async def list_all(self, type_filter: str | None = None) -> list[Entity]: ...

    async def upsert(self, entity: Entity) -> Entity: ...

    async def list_unconfirmed(self) -> list[Entity]: ...

    async def list_by_ids(self, entity_ids: list[str]) -> list[Entity]: ...

    async def list_by_parent(self, parent_id: str) -> list[Entity]: ...

    async def update_source_status(self, entity_id: str, new_status: str, source_id: str | None = None) -> None: ...

    async def archive_entity(self, entity_id: str) -> None: ...

    async def batch_update_source_uris(
        self, updates: list[dict], *, atomic: bool = False,
    ) -> dict: ...


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

    async def list_all(self, confirmed_only: bool | None = None) -> list[Protocol]: ...


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


class SourceAdapter(TypingProtocol):
    """Read-only access to external document content."""

    async def read_content(self, uri: str) -> str: ...

    async def search_by_filename(
        self, owner: str, repo: str, ref: str, filename: str
    ) -> list[str]:
        """Search for files with matching filename. Returns list of URIs."""
        ...

    async def search_alternatives_for_uri(self, uri: str) -> list[str]:
        """Given a source URI, attempt to find alternative file locations.

        Returns a list of candidate URIs in the same repository.
        Returns an empty list if the adapter does not support this or encounters an error.
        """
        ...
