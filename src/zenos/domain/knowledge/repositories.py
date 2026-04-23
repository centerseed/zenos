"""ZenOS Domain — Knowledge Layer Repository Interfaces."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .models import Blindspot, Entity, EntityEntry, Protocol, Relationship


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

    async def find_by_id_prefix(self, prefix: str, partner_id: str, limit: int = 11) -> list[Entity]:
        """Return entities whose id starts with prefix, scoped to partner_id."""
        ...

    async def update_source_status(self, entity_id: str, new_status: str, source_id: str | None = None) -> None: ...

    async def archive_entity(self, entity_id: str) -> None: ...

    async def batch_update_source_uris(
        self, updates: list[dict], *, atomic: bool = False,
    ) -> dict: ...


class RelationshipRepository(TypingProtocol):
    """Persistence interface for skeleton-layer relationships."""

    async def list_by_entity(self, entity_id: str) -> list[Relationship]: ...

    async def list_all(self) -> list[Relationship]: ...

    async def find_duplicate(
        self, source_entity_id: str, target_id: str, rel_type: str,
    ) -> Relationship | None:
        """Find an existing relationship with the same source, target, and type."""
        ...

    async def add(self, rel: Relationship) -> Relationship: ...

    async def remove(self, source_entity_id: str, target_id: str, rel_type: str) -> int: ...

    async def remove_by_id(self, rel_id: str) -> int: ...


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

    async def find_by_id_prefix(self, prefix: str, partner_id: str, limit: int = 11) -> list[Blindspot]:
        """Return blindspots whose id starts with prefix, scoped to partner_id."""
        ...


class EntityEntryRepository(TypingProtocol):
    """Persistence interface for entity knowledge entries."""

    async def create(self, entry: EntityEntry, *, conn: object | None = None) -> EntityEntry: ...

    async def get_by_id(self, entry_id: str) -> EntityEntry | None: ...

    async def list_by_entity(
        self, entity_id: str, status: str | None = "active", department: str | None = None
    ) -> list[EntityEntry]: ...

    async def update_status(
        self,
        entry_id: str,
        status: str,
        superseded_by: str | None = None,
        archive_reason: str | None = None,
    ) -> EntityEntry | None: ...

    async def list_saturated_entities(self, threshold: int = 20) -> list[dict]: ...

    async def count_active_by_entity(self, entity_id: str, department: str | None = None) -> int: ...

    async def find_by_id_prefix(self, prefix: str, partner_id: str, limit: int = 11) -> list[EntityEntry]:
        """Return entries whose id starts with prefix, scoped to partner_id."""
        ...

    async def search_content(self, query: str, limit: int = 20, department: str | None = None) -> list[dict]: ...


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
