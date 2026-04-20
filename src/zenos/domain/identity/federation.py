"""ZenOS Domain — Identity Federation Models.

ADR-029: Auth Federation Runtime — domain models for trusted apps and identity links.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FederationScope(str, Enum):
    """Scopes that can be granted to federated tokens."""

    read = "read"
    write = "write"
    task = "task"


@dataclass
class TrustedApp:
    """A third-party application trusted to exchange tokens via ZenOS federation."""

    app_id: str
    app_name: str
    app_secret_hash: str
    allowed_issuers: list[str] = field(default_factory=list)
    allowed_scopes: list[str] = field(default_factory=lambda: ["read"])
    status: str = "active"
    default_workspace_id: str | None = None
    auto_link_email_domains: list[str] = field(default_factory=list)

    def is_active(self) -> bool:
        return self.status == "active"

    def allows_issuer(self, issuer: str) -> bool:
        return issuer in self.allowed_issuers

    def allows_scopes(self, requested: list[str]) -> list[str]:
        """Return only the subset of requested scopes that this app permits."""
        permitted = set(self.allowed_scopes)
        return [s for s in requested if s in permitted]

    def can_autolink_email(self, email: str, email_verified: bool) -> bool:
        """Return True if this email qualifies for domain auto-link.

        Requires:
        - email_verified is True
        - email domain matches one of auto_link_email_domains
        - default_workspace_id is set (needed to provision a guest partner)
        """
        if not email_verified:
            return False
        if not self.auto_link_email_domains:
            return False
        if not self.default_workspace_id:
            return False
        if "@" not in email:
            return False
        domain = email.split("@", 1)[1].lower()
        return domain in {d.lower() for d in self.auto_link_email_domains}


@dataclass
class IdentityLink:
    """Maps an external identity (app + issuer + user_id) to a ZenOS principal."""

    id: str
    app_id: str
    issuer: str
    external_user_id: str
    zenos_principal_id: str
    email: str | None = None
    status: str = "active"

    def is_active(self) -> bool:
        return self.status == "active"
