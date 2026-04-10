"""ZenOS Domain — Identity Layer Repository Interfaces."""

from __future__ import annotations

from typing import Protocol as TypingProtocol


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
