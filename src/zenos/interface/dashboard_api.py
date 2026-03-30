"""Dashboard REST API — Firebase ID token auth for data access endpoints.

Endpoints:
  GET /api/partner/me                     — current partner info
  GET /api/data/entities                  — list entities
  GET /api/data/entities/{id}             — get single entity
  GET /api/data/entities/{id}/children    — get child entities
  GET /api/data/entities/{id}/relationships — get entity relationships
  GET /api/data/relationships             — list all relationships
  GET /api/data/blindspots               — list blindspots
  GET /api/data/tasks                     — list tasks
  GET /api/data/tasks/by-entity/{entityId} — tasks by entity

Auth: Firebase ID token → email → SQL partners table → partner scope.
CORS: allows requests from the Dashboard origin.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from zenos.application.ontology_service import OntologyService
from zenos.domain.models import Blindspot, Entity, Relationship, Task
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.sql_repo import (  # composition root
    SqlBlindspotRepository,
    SqlEntityRepository,
    SqlPartnerRepository,
    SqlRelationshipRepository,
    SqlTaskRepository,
    get_pool,
)
from zenos.interface.admin_api import (
    _cors_headers,
    _error_response,
    _handle_options,
    _json_response,
    _verify_firebase_token,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Repository cache (lazy-init with shared pool)
# ──────────────────────────────────────────────

_repos_ready = False
_entity_repo: SqlEntityRepository | None = None
_relationship_repo: SqlRelationshipRepository | None = None
_blindspot_repo: SqlBlindspotRepository | None = None
_task_repo: SqlTaskRepository | None = None
_partner_repo: SqlPartnerRepository | None = None


async def _ensure_repos() -> None:
    global _repos_ready, _entity_repo, _relationship_repo, _blindspot_repo, _task_repo, _partner_repo
    if _repos_ready:
        return
    pool = await get_pool()
    _entity_repo = SqlEntityRepository(pool)
    _relationship_repo = SqlRelationshipRepository(pool)
    _blindspot_repo = SqlBlindspotRepository(pool)
    _task_repo = SqlTaskRepository(pool)
    _partner_repo = SqlPartnerRepository(pool)
    _repos_ready = True


# ──────────────────────────────────────────────
# Partner lookup from SQL
# ──────────────────────────────────────────────


async def _get_partner_by_email_sql(email: str) -> dict | None:
    """Query SQL partners table by email. Returns partner dict or None."""
    await _ensure_repos()
    return await _partner_repo.get_by_email(email)


# ──────────────────────────────────────────────
# Auth helper — Firebase token → partner scope
# ──────────────────────────────────────────────


async def _auth_and_scope(request: Request) -> tuple[dict | None, str | None]:
    """Verify token, look up partner, set current_partner_id ContextVar.

    Returns (partner_dict, effective_partner_id) on success, or (None, None).
    Does NOT reset the ContextVar — caller must do so after the request.
    """
    decoded = await _verify_firebase_token(request)
    if not decoded:
        return None, None
    email = decoded.get("email")
    if not email:
        return None, None
    partner = await _get_partner_by_email_sql(email)
    if not partner:
        return None, None
    # Use sharedPartnerId for data scoping (same as Dashboard frontend logic)
    effective_id = partner.get("sharedPartnerId") or partner["id"]
    return partner, effective_id


# ──────────────────────────────────────────────
# Serialization helpers
# ──────────────────────────────────────────────


def _entity_to_dict(e: Entity) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "type": e.type,
        "level": e.level,
        "parentId": e.parent_id,
        "status": e.status,
        "summary": e.summary,
        "tags": {"what": e.tags.what, "why": e.tags.why, "how": e.tags.how, "who": e.tags.who},
        "details": e.details,
        "confirmedByUser": e.confirmed_by_user,
        "owner": e.owner,
        "sources": e.sources,
        "visibility": e.visibility,
        "visibleToRoles": e.visible_to_roles,
        "visibleToMembers": e.visible_to_members,
        "visibleToDepartments": e.visible_to_departments,
        "lastReviewedAt": e.last_reviewed_at,
        "createdAt": e.created_at,
        "updatedAt": e.updated_at,
    }


def _relationship_to_dict(r: Relationship) -> dict:
    return {
        "id": r.id,
        "sourceEntityId": r.source_entity_id,
        "targetId": r.target_id,
        "type": r.type,
        "description": r.description,
        "confirmedByUser": r.confirmed_by_user,
    }


def _blindspot_to_dict(b: Blindspot) -> dict:
    return {
        "id": b.id,
        "description": b.description,
        "severity": b.severity,
        "relatedEntityIds": b.related_entity_ids,
        "suggestedAction": b.suggested_action,
        "status": b.status,
        "confirmedByUser": b.confirmed_by_user,
        "createdAt": b.created_at,
    }


def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "priorityReason": t.priority_reason,
        "assignee": t.assignee,
        "assigneeRoleId": t.assignee_role_id,
        "planId": t.plan_id,
        "planOrder": t.plan_order,
        "dependsOnTaskIds": t.depends_on_task_ids,
        "createdBy": t.created_by,
        "linkedEntities": t.linked_entities,
        "linkedProtocol": t.linked_protocol,
        "linkedBlindspot": t.linked_blindspot,
        "sourceType": t.source_type,
        "sourceMetadata": t.source_metadata,
        "contextSummary": t.context_summary,
        "dueDate": t.due_date,
        "blockedBy": t.blocked_by,
        "blockedReason": t.blocked_reason,
        "acceptanceCriteria": t.acceptance_criteria,
        "completedBy": t.completed_by,
        "confirmedByCreator": t.confirmed_by_creator,
        "rejectionReason": t.rejection_reason,
        "result": t.result,
        "project": t.project,
        "createdAt": t.created_at,
        "updatedAt": t.updated_at,
        "completedAt": t.completed_at,
    }


# ──────────────────────────────────────────────
# Endpoint: GET /api/partner/me
# ──────────────────────────────────────────────


async def get_partner_me(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    email = decoded.get("email")
    if not email:
        return _error_response("INVALID_INPUT", "Email not found in token", 400, request=request)

    partner = await _get_partner_by_email_sql(email)
    if not partner:
        return _error_response("NOT_FOUND", f"No partner found for email {email}", 404, request=request)

    return _json_response({"partner": partner}, request=request)


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/entities
# ──────────────────────────────────────────────


async def list_entities(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    await _ensure_repos()
    type_filter = request.query_params.get("type")
    token = current_partner_id.set(effective_id)
    try:
        entities = await _entity_repo.list_all(type_filter=type_filter)
    finally:
        current_partner_id.reset(token)
    entities = [e for e in entities if OntologyService.is_entity_visible_for_partner(e, partner)]

    return _json_response({"entities": [_entity_to_dict(e) for e in entities]}, request=request)


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/entities/{id}
# ──────────────────────────────────────────────


async def get_entity(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    entity_id = request.path_params.get("id")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        entity = await _entity_repo.get_by_id(entity_id)
    finally:
        current_partner_id.reset(token)

    if not entity:
        return _error_response("NOT_FOUND", f"Entity {entity_id} not found", 404, request=request)
    if not OntologyService.is_entity_visible_for_partner(entity, partner):
        return _error_response("NOT_FOUND", f"Entity {entity_id} not found", 404, request=request)

    return _json_response({"entity": _entity_to_dict(entity)}, request=request)


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/entities/{id}/children
# ──────────────────────────────────────────────


async def get_entity_children(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    entity_id = request.path_params.get("id")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        children = await _entity_repo.list_by_parent(entity_id)
    finally:
        current_partner_id.reset(token)
    children = [e for e in children if OntologyService.is_entity_visible_for_partner(e, partner)]

    return _json_response(
        {"entities": [_entity_to_dict(e) for e in children], "count": len(children)},
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/entities/{id}/relationships
# ──────────────────────────────────────────────


async def get_entity_relationships(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    entity_id = request.path_params.get("id")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        relationships = await _relationship_repo.list_by_entity(entity_id)
    finally:
        current_partner_id.reset(token)

    return _json_response(
        {"relationships": [_relationship_to_dict(r) for r in relationships]},
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/relationships
# ──────────────────────────────────────────────


async def list_relationships(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        relationships = await _relationship_repo.list_all()
    finally:
        current_partner_id.reset(token)

    return _json_response(
        {"relationships": [_relationship_to_dict(r) for r in relationships]},
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/blindspots
# ──────────────────────────────────────────────


async def list_blindspots(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    entity_id = request.query_params.get("entity_id")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        blindspots = await _blindspot_repo.list_all(entity_id=entity_id)
    finally:
        current_partner_id.reset(token)

    return _json_response(
        {"blindspots": [_blindspot_to_dict(b) for b in blindspots]},
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/tasks
# ──────────────────────────────────────────────


async def list_tasks(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    status_param = request.query_params.get("status")
    status_list = [s.strip() for s in status_param.split(",")] if status_param else None
    assignee = request.query_params.get("assignee") or None
    created_by = request.query_params.get("created_by") or None

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        tasks = await _task_repo.list_all(status=status_list, assignee=assignee, created_by=created_by)
    finally:
        current_partner_id.reset(token)

    return _json_response({"tasks": [_task_to_dict(t) for t in tasks]}, request=request)


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/tasks/by-entity/{entityId}
# ──────────────────────────────────────────────


async def list_tasks_by_entity(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    entity_id = request.path_params.get("entityId")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        tasks = await _task_repo.list_all(linked_entity=entity_id)
    finally:
        current_partner_id.reset(token)

    return _json_response({"tasks": [_task_to_dict(t) for t in tasks]}, request=request)


# ──────────────────────────────────────────────
# Route table
# ──────────────────────────────────────────────

dashboard_routes = [
    Route("/api/partner/me", get_partner_me, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities", list_entities, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}/children", get_entity_children, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}/relationships", get_entity_relationships, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}", get_entity, methods=["GET", "OPTIONS"]),
    Route("/api/data/relationships", list_relationships, methods=["GET", "OPTIONS"]),
    Route("/api/data/blindspots", list_blindspots, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/by-entity/{entityId}", list_tasks_by_entity, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks", list_tasks, methods=["GET", "OPTIONS"]),
]
