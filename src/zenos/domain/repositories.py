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

    async def get_by_name(self, name: str) -> Entity | None:
        """Look up an entity by name (case-insensitive exact match)."""
        ...

    async def list_all(self, type_filter: str | None = None) -> list[Entity]: ...

    async def upsert(self, entity: Entity) -> Entity: ...

    async def list_unconfirmed(self) -> list[Entity]: ...

    async def list_by_ids(self, entity_ids: list[str]) -> list[Entity]: ...

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


class ToolEventRepository(TypingProtocol):
    """Persistence interface for agent tool event tracking."""

    async def log_tool_event(
        self,
        partner_id: str,
        tool_name: str,
        entity_id: str | None,
        query: str | None,
        result_count: int | None,
    ) -> None: ...

    async def get_entity_usage_stats(
        self,
        partner_id: str,
        days: int = 30,
    ) -> list[dict]: ...


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


class UsageLogRepository(TypingProtocol):
    """Persistence interface for LLM usage logging."""

    async def write_usage_log(
        self,
        partner_id: str,
        feature: str,
        tokens_in: int,
        tokens_out: int,
        model: str,
    ) -> None: ...


class PartnerRepository(TypingProtocol):
    """Persistence interface for partner lookups."""

    async def get_by_email(self, email: str) -> dict | None: ...

    async def get_by_id(self, partner_id: str) -> dict | None: ...

    async def list_all_in_tenant(self, tenant_id: str) -> list[dict]: ...

    async def create(self, data: dict) -> None: ...

    async def update_fields(self, partner_id: str, fields: dict) -> None: ...

    async def delete(self, partner_id: str) -> None: ...

    async def get_entity_tenant(self, entity_id: str) -> dict | None:
        """Return entity tenant info: {partner_id, shared_partner_id}."""
        ...

    async def update_entity_visibility(
        self,
        entity_id: str,
        visibility: str,
        visible_to_roles: list[str],
        visible_to_members: list[str],
        visible_to_departments: list[str],
    ) -> None: ...

    async def list_departments(self, tenant_id: str) -> list[str]: ...

    async def create_department(self, tenant_id: str, name: str) -> None: ...

    async def rename_department(self, tenant_id: str, old_name: str, new_name: str) -> None: ...

    async def delete_department(self, tenant_id: str, name: str, fallback_department: str = "all") -> None: ...


class CrmRepository(TypingProtocol):
    """Persistence interface for CRM operations."""

    async def create_company(self, company: object) -> object: ...

    async def update_company(self, company: object) -> object: ...

    async def get_company(self, partner_id: str, company_id: str) -> object | None: ...

    async def list_companies(self, partner_id: str) -> list: ...

    async def create_contact(self, contact: object) -> object: ...

    async def update_contact(self, contact: object) -> object: ...

    async def get_contact(self, partner_id: str, contact_id: str) -> object | None: ...

    async def list_contacts(
        self, partner_id: str, company_id: str | None = None
    ) -> list: ...

    async def create_deal(self, deal: object) -> object: ...

    async def update_deal(self, deal: object) -> object: ...

    async def get_deal(self, partner_id: str, deal_id: str) -> object | None: ...

    async def list_deals(
        self, partner_id: str, include_inactive: bool = False
    ) -> list: ...

    async def create_activity(self, activity: object) -> object: ...

    async def list_activities(self, partner_id: str, deal_id: str) -> list: ...
