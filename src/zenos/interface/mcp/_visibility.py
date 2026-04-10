"""MCP interface — server-side visibility checks.

Contains:
- _is_entity_visible
- _guest_allowed_entity_ids
- _is_document_like_entity_visible_for_guest
- _is_task_visible
- _is_protocol_visible
- _is_blindspot_visible
- _check_write_visibility
- _guest_write_rejection
"""

from __future__ import annotations

import logging

from zenos.infrastructure.context import current_partner_department
from zenos.domain.partner_access import describe_partner_access, is_guest, is_unassigned_partner
from zenos.application.knowledge.ontology_service import _collect_subtree_ids

logger = logging.getLogger(__name__)


def _is_entity_visible(entity: object) -> bool:
    """Centralized server-side visibility check for read paths.

    Visibility rules (S04 query slicing):
    - owner/admin: sees everything
    - unassigned: sees nothing
    - guest: only public entities (L1 scope check done at list level)
    - member: only public entities; restricted and confidential are owner-only.
              If a public entity has visible_to_departments set, the partner's
              department must be in that list.
    """
    from zenos.interface.mcp._auth import _current_partner

    partner = _current_partner.get()
    if not partner:
        return True
    access = describe_partner_access(partner)
    if access["is_admin"]:
        return True
    if access["is_unassigned_partner"]:
        return False

    visibility = str(getattr(entity, "visibility", "public") or "public").strip().lower()
    if visibility == "role-restricted":
        visibility = "restricted"

    if access["is_guest"]:
        # Guest: L1 scope check is done at search/list level.
        return visibility == "public"

    # Member: can see public + restricted, but not confidential.
    if visibility == "confidential":
        return False

    # Apply department filter: if entity restricts to specific departments,
    # the partner's department must match (non-"all" partners only).
    visible_to_depts = getattr(entity, "visible_to_departments", None) or []
    if visible_to_depts:
        partner_dept = str(current_partner_department.get() or "all")
        if partner_dept not in visible_to_depts:
            return False

    return True


async def _guest_allowed_entity_ids() -> set[str]:
    """Resolve the guest's authorized subtree IDs.

    Returns an empty set when the caller is not a guest or when scope
    resolution fails. Guest access should fail closed.
    """
    from zenos.interface.mcp._auth import _current_partner
    from zenos.interface.mcp import entity_repo

    partner = _current_partner.get()
    if not partner or not is_guest(partner):
        return set()

    try:
        access = describe_partner_access(partner)
        authorized_ids = access["authorized_l1_ids"]
        if not authorized_ids:
            return set()

        all_entities_list = await entity_repo.list_all()
        entity_map = {e.id: e for e in (all_entities_list or []) if e.id}
        allowed: set[str] = set()
        for l1_id in authorized_ids:
            allowed |= _collect_subtree_ids(l1_id, entity_map)
        return allowed
    except Exception:
        logger.warning("_guest_allowed_entity_ids failed, denying guest access", exc_info=True)
        return set()


def _is_document_like_entity_visible_for_guest(item: object, allowed_ids: set[str]) -> bool:
    """Check guest subtree membership for entity/document-like items."""
    item_id = str(getattr(item, "id", "") or "").strip()
    if item_id and item_id in allowed_ids:
        return True

    linked_entity_ids = getattr(item, "linked_entity_ids", None) or []
    for linked_id in linked_entity_ids:
        if str(linked_id).strip() in allowed_ids:
            return True

    parent_id = str(getattr(item, "parent_id", "") or "").strip()
    return bool(parent_id and parent_id in allowed_ids)


async def _is_task_visible(task: object) -> bool:
    """Task visibility check.

    - Admin: always visible.
    - Guest: requires at least one linked entity in their authorized L1 subtree.
      Entity visibility (public/restricted) is NOT checked — any entity in scope
      makes the task visible. Tasks with no linked entities are NOT visible.
    - Member: task hidden if ANY linked entity is invisible.
      Tasks with no linked entities are always visible (fail-open).
    """
    from zenos.interface.mcp._auth import _current_partner
    from zenos.interface.mcp import entity_repo

    try:
        linked = getattr(task, "linked_entities", None) or []
        partner = _current_partner.get() or {}
        if not partner:
            return True
        if partner.get("isAdmin", False):
            return True
        if is_unassigned_partner(partner):
            return False

        if is_guest(partner):
            # Guest: visible if at least one linked entity is in allowed_ids.
            # Entity visibility is NOT applied here — scope membership is sufficient.
            if not linked:
                return False
            authorized_ids = describe_partner_access(partner)["authorized_l1_ids"]
            all_entities_list = await entity_repo.list_all()
            entity_map = {e.id: e for e in (all_entities_list or []) if e.id}
            allowed: set[str] = set()
            for l1_id in authorized_ids:
                allowed |= _collect_subtree_ids(l1_id, entity_map)
            for eid in linked:
                if isinstance(eid, dict):
                    eid = eid.get("id", "")
                if eid and eid in allowed:
                    return True
            return False

        # Internal non-admin: all linked entities must be visible
        if not linked:
            return True
        for eid in linked:
            if isinstance(eid, dict):
                eid = eid.get("id", "")
            if not eid:
                continue
            entity = await entity_repo.get_by_id(eid)
            if entity and not _is_entity_visible(entity):
                return False
        return True
    except Exception:
        logger.warning("_is_task_visible check failed, defaulting to visible", exc_info=True)
        return True


async def _is_protocol_visible(protocol: object) -> bool:
    """Protocol inherits visibility from its linked entity."""
    from zenos.interface.mcp._auth import _current_partner
    from zenos.interface.mcp import entity_repo

    try:
        entity_id = getattr(protocol, "entity_id", None)
        if not entity_id:
            return True  # orphan protocol = visible
        partner = _current_partner.get() or {}
        if not partner:
            return True
        if partner.get("isAdmin", False):
            return True
        if is_unassigned_partner(partner):
            return False
        entity = await entity_repo.get_by_id(entity_id)
        if entity is None:
            return True  # entity deleted = show protocol
        return _is_entity_visible(entity)
    except Exception:
        logger.warning("_is_protocol_visible check failed, defaulting to visible", exc_info=True)
        return True


async def _is_blindspot_visible(blindspot: object) -> bool:
    """Blindspot is visible if ANY related entity is visible.

    If ALL related entities are invisible, the blindspot is hidden.
    Blindspots with no related entities are always visible.
    Guests never see blindspots.
    """
    from zenos.interface.mcp._auth import _current_partner
    from zenos.interface.mcp import entity_repo

    try:
        partner = _current_partner.get() or {}
        if not partner:
            return True
        if partner.get("isAdmin", False):
            return True
        # Guests cannot see blindspots.
        if is_unassigned_partner(partner):
            return False
        if is_guest(partner):
            return False
        related = getattr(blindspot, "related_entity_ids", None) or []
        if not related:
            return True
        for eid in related:
            entity = await entity_repo.get_by_id(eid)
            if entity and _is_entity_visible(entity):
                return True  # at least one visible
        return False
    except Exception:
        logger.warning("_is_blindspot_visible check failed, defaulting to visible", exc_info=True)
        return True


def _check_write_visibility(existing_entity: object, data: dict) -> dict | None:
    """Check if caller is authorized to write to an existing entity.

    Returns an error dict if unauthorized, None if OK.
    Fail-open: exceptions default to allowing the write.
    """
    from zenos.interface.mcp._auth import _current_partner

    try:
        if not _is_entity_visible(existing_entity):
            return {
                "error": "FORBIDDEN",
                "message": "You do not have permission to modify this entity.",
            }
        # Non-admin cannot change visibility on confidential entities
        partner = _current_partner.get() or {}
        is_admin = bool(partner.get("isAdmin", False))
        visibility_fields = {"visibility", "visible_to_roles", "visible_to_members", "visible_to_departments"}
        if not is_admin and getattr(existing_entity, "visibility", "public") == "confidential":
            if any(f in data for f in visibility_fields):
                return {
                    "error": "FORBIDDEN",
                    "message": "Only admin can modify visibility settings on confidential entities.",
                }
        return None
    except Exception:
        logger.warning("_check_write_visibility failed, allowing write", exc_info=True)
        return None


def _guest_write_rejection(collection: str) -> dict | None:
    """Reject ontology writes from guests while keeping task/comment paths open.

    Entity writes are intentionally excluded from this blanket rejection:
    guests may create L3 entities under their authorized scope. The
    application-layer write guard (OntologyService._enforce_guest_write_guard)
    enforces the L1/L2/L3 rules with proper scope checks.
    """
    from zenos.interface.mcp._auth import _current_partner

    partner = _current_partner.get()
    if not partner or not is_guest(partner):
        return None

    # Non-entity ontology collections remain fully restricted for guests.
    # Note: "documents" is intentionally excluded — write(collection="documents") is
    # the backward-compatible path for entity(type="document"), an L3 type that guests
    # are allowed to create under an authorized parent. The application-layer write guard
    # in OntologyService.upsert_document enforces the scope check.
    if collection in {"protocols", "blindspots", "relationships", "entries"}:
        return {
            "status": "rejected",
            "data": {},
            "rejection_reason": "Guests cannot create or modify ontology content.",
        }
    return None
