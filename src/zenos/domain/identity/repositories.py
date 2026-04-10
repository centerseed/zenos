"""ZenOS Domain — Identity Layer Repository Interfaces."""

from __future__ import annotations

from typing import Protocol as TypingProtocol

from .federation import TrustedApp, IdentityLink


class TrustedAppRepository(TypingProtocol):
    """Persistence interface for trusted app lookups."""

    async def get_by_id(self, app_id: str) -> TrustedApp | None: ...

    async def get_by_name(self, app_name: str) -> TrustedApp | None: ...

    async def create(self, app_name: str, app_secret_hash: str, allowed_issuers: list[str], allowed_scopes: list[str]) -> TrustedApp: ...

    async def update_status(self, app_id: str, status: str) -> None: ...


class IdentityLinkRepository(TypingProtocol):
    """Persistence interface for identity link lookups."""

    async def get(self, app_id: str, issuer: str, external_user_id: str) -> IdentityLink | None: ...

    async def create(self, app_id: str, issuer: str, external_user_id: str, zenos_principal_id: str, email: str | None = None) -> IdentityLink: ...

    async def list_by_principal(self, zenos_principal_id: str) -> list[IdentityLink]: ...


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
