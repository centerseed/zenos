"""Partner access helpers.

Separates tenant routing from data visibility. `sharedPartnerId` routes to the
tenant partition; legacy `accessMode` is kept as a storage/detail layer, while
runtime authorization resolves the spec-facing workspace role:
Owner / Member / Guest.
"""

from __future__ import annotations

from typing import TypedDict


VALID_ACCESS_MODES = {"internal", "scoped", "unassigned"}
VALID_WORKSPACE_ROLES = {"owner", "member", "guest"}


class PartnerAccess(TypedDict):
    is_admin: bool
    access_mode: str
    workspace_role: str
    authorized_l1_ids: list[str]
    is_owner: bool
    is_member: bool
    is_guest: bool
    is_internal_member: bool
    is_scoped_partner: bool
    is_unassigned_partner: bool


def _authorized_l1_ids(partner: dict | None) -> list[str]:
    if not partner:
        return []
    raw = partner.get("authorizedEntityIds")
    if raw is None:
        raw = partner.get("authorized_entity_ids")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def resolve_access_mode(partner: dict | None) -> str:
    """Resolve access mode with backward-compatible fallback.

    Fallback policy is transitional and intentionally conservative:
    - explicit workspaceRole wins when present
    - explicit `accessMode`/`access_mode` wins
    - any non-empty authorized scope => scoped
    - existing active non-admins without explicit mode => internal
    - everyone else => unassigned
    """
    if not partner:
        return "unassigned"

    raw_role = partner.get("workspaceRole")
    if raw_role is None:
        raw_role = partner.get("workspace_role")
    if isinstance(raw_role, str):
        normalized = raw_role.strip().lower()
        if normalized in VALID_WORKSPACE_ROLES:
            if normalized == "guest":
                return "scoped"
            return "internal"

    raw_mode = partner.get("accessMode")
    if raw_mode is None:
        raw_mode = partner.get("access_mode")
    if isinstance(raw_mode, str):
        normalized = raw_mode.strip().lower()
        if normalized in VALID_ACCESS_MODES:
            return normalized

    authorized_ids = _authorized_l1_ids(partner)
    if authorized_ids:
        return "scoped"

    status = str(partner.get("status") or "").strip().lower()
    if status == "active" or not status:
        return "internal"
    return "unassigned"


def resolve_workspace_role(partner: dict | None) -> str:
    """Resolve spec-facing workspace role from partner record.

    Backward compatibility:
    - isAdmin => owner
    - explicit workspaceRole/workspace_role wins
    - scoped => guest
    - active non-admin => member
    - fallback => guest
    """
    if not partner:
        return "guest"

    if bool(partner.get("isAdmin", False)):
        return "owner"

    raw_role = partner.get("workspaceRole")
    if raw_role is None:
        raw_role = partner.get("workspace_role")
    if isinstance(raw_role, str):
        normalized = raw_role.strip().lower()
        if normalized in VALID_WORKSPACE_ROLES:
            return normalized

    access_mode = resolve_access_mode(partner)
    if access_mode == "scoped":
        return "guest"
    if access_mode == "internal":
        return "member"
    return "guest"


def describe_partner_access(partner: dict | None) -> PartnerAccess:
    is_admin = bool((partner or {}).get("isAdmin", False))
    access_mode = "internal" if is_admin else resolve_access_mode(partner)
    workspace_role = resolve_workspace_role(partner)
    authorized_l1_ids = _authorized_l1_ids(partner)
    return {
        "is_admin": is_admin,
        "access_mode": access_mode,
        "workspace_role": workspace_role,
        "authorized_l1_ids": authorized_l1_ids,
        "is_owner": workspace_role == "owner",
        "is_member": workspace_role == "member",
        "is_guest": workspace_role == "guest",
        "is_internal_member": is_admin or access_mode == "internal",
        "is_scoped_partner": (not is_admin) and access_mode == "scoped",
        "is_unassigned_partner": (not is_admin) and access_mode == "unassigned",
    }


def is_scoped_partner(partner: dict | None) -> bool:
    return describe_partner_access(partner)["is_scoped_partner"]


def is_unassigned_partner(partner: dict | None) -> bool:
    return describe_partner_access(partner)["is_unassigned_partner"]


def is_internal_member(partner: dict | None) -> bool:
    return describe_partner_access(partner)["is_internal_member"]


def is_owner(partner: dict | None) -> bool:
    return describe_partner_access(partner)["is_owner"]


def is_member(partner: dict | None) -> bool:
    return describe_partner_access(partner)["is_member"]


def is_guest(partner: dict | None) -> bool:
    return describe_partner_access(partner)["is_guest"]
