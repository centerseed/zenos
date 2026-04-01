"""Dashboard REST API — Firebase ID token auth for data access endpoints.

Endpoints:
  GET    /api/partner/me                                  — current partner info
  GET    /api/data/entities                               — list entities
  GET    /api/data/entities/{id}                          — get single entity
  GET    /api/data/entities/{id}/children                 — get child entities
  GET    /api/data/entities/{id}/relationships            — get entity relationships
  GET    /api/data/relationships                          — list all relationships
  GET    /api/data/blindspots                             — list blindspots
  GET    /api/data/tasks                                  — list tasks
  POST   /api/data/tasks                                  — create task
  GET    /api/data/tasks/by-entity/{entityId}             — tasks by entity
  PATCH  /api/data/tasks/{taskId}                         — update task fields
  POST   /api/data/tasks/{taskId}/confirm                 — approve or reject task
  POST   /api/data/tasks/{taskId}/attachments             — upload attachment (returns signed URL)
  DELETE /api/data/tasks/{taskId}/attachments/{attachmentId} — delete attachment
  GET    /attachments/{attachment_id}                     — proxy-stream attachment file

Auth: Firebase ID token → email → SQL partners table → partner scope.
CORS: allows requests from the Dashboard origin.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from zenos.application.ontology_service import OntologyService
from zenos.application.task_service import TaskService
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
    status = {
        "backlog": "todo",
        "blocked": "in_progress",
        "archived": "done",
    }.get(t.status, t.status)
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": status,
        "priority": t.priority,
        "priorityReason": t.priority_reason,
        "assignee": t.assignee,
        "assigneeName": t.assignee_name,
        "assigneeRoleId": t.assignee_role_id,
        "planId": t.plan_id,
        "planOrder": t.plan_order,
        "dependsOnTaskIds": t.depends_on_task_ids,
        "createdBy": t.created_by,
        "updatedBy": t.updated_by,
        "creatorName": t.creator_name,
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
        "attachments": _attachments_with_proxy_url(t.attachments),
        "createdAt": t.created_at,
        "updatedAt": t.updated_at,
        "completedAt": t.completed_at,
    }


def _attachments_with_proxy_url(attachments: list[dict]) -> list[dict]:
    """Add proxy_url to attachment items that have a gcs_path."""
    result = []
    for att in attachments:
        att_copy = dict(att)
        if att_copy.get("gcs_path"):
            att_copy["proxy_url"] = f"/attachments/{att_copy['id']}"
        result.append(att_copy)
    return result


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
        tasks = await _task_repo.list_all(status=status_list, assignee=assignee, created_by=created_by, limit=500)
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
# Endpoint: GET /attachments/{attachment_id}
# ──────────────────────────────────────────────


async def get_attachment(request: Request) -> Response:
    """Proxy-stream an attachment file from GCS with auth verification."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    attachment_id = request.path_params.get("attachment_id")
    if not attachment_id:
        return _error_response("INVALID_INPUT", "attachment_id required", 400, request=request)

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_obj = await _task_repo.find_task_by_attachment_id(attachment_id)
    finally:
        current_partner_id.reset(token)

    if not task_obj:
        return _error_response("NOT_FOUND", "Attachment not found", 404, request=request)

    # Find the specific attachment metadata
    att_meta = None
    for att in task_obj.attachments:
        if att.get("id") == attachment_id:
            att_meta = att
            break

    if not att_meta or not att_meta.get("gcs_path"):
        return _error_response("NOT_FOUND", "Attachment has no file data", 404, request=request)

    try:
        from google.cloud.exceptions import NotFound as GcsNotFound  # type: ignore[import-untyped]
        from zenos.infrastructure.gcs_client import download_blob, get_default_bucket
        data, file_content_type = download_blob(get_default_bucket(), att_meta["gcs_path"])
    except GcsNotFound:
        logger.warning("GCS object not found for attachment %s", attachment_id)
        return _error_response("NOT_FOUND", "Attachment file not found", 404, request=request)
    except Exception:
        logger.exception("Failed to download attachment %s from GCS", attachment_id)
        return _error_response("INTERNAL_ERROR", "Failed to retrieve attachment", 500, request=request)

    # Determine Content-Disposition
    filename = att_meta.get("filename", "attachment")
    is_image = file_content_type.startswith("image/")
    disposition = "inline" if is_image else f'attachment; filename="{filename}"'

    headers = {
        **_cors_headers(request),
        "Content-Disposition": disposition,
        "Cache-Control": "private, max-age=3600",
    }

    return Response(content=data, media_type=file_content_type, headers=headers)


# ──────────────────────────────────────────────
# Endpoint: POST /api/data/tasks/{taskId}/attachments
# ──────────────────────────────────────────────


async def upload_task_attachment(request: Request) -> Response:
    """Request a signed PUT URL for uploading an attachment to a task."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    task_id = request.path_params.get("taskId")
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    attachment_type = body.get("type", "file")

    # Handle link attachment (no GCS upload required)
    if attachment_type == "link":
        url = body.get("url", "").strip()
        if not url:
            return _error_response("INVALID_INPUT", "url required for link attachments", 400, request=request)

        await _ensure_repos()
        token = current_partner_id.set(effective_id)
        try:
            task_obj = await _task_repo.get_by_id(task_id)
            if not task_obj:
                return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

            attachment_id = uuid.uuid4().hex
            attachment = {
                "id": attachment_id,
                "type": "link",
                "url": url,
                "filename": body.get("filename", url),
                "description": body.get("description", ""),
                "uploaded_by": effective_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            task_obj.attachments.append(attachment)
            await _task_repo.upsert(task_obj)

            logger.info("Created link attachment %s for task %s", attachment_id, task_id)
            return _json_response({"attachment_id": attachment_id}, request=request)
        finally:
            current_partner_id.reset(token)

    # Handle file attachment (GCS signed URL upload)
    filename = body.get("filename")
    content_type = body.get("content_type")
    if not filename or not content_type:
        return _error_response("INVALID_INPUT", "filename and content_type required", 400, request=request)

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_obj = await _task_repo.get_by_id(task_id)
        if not task_obj:
            return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

        try:
            from zenos.infrastructure.gcs_client import generate_signed_put_url, get_default_bucket
            attachment_id = uuid.uuid4().hex
            bucket_name = get_default_bucket()
            gcs_path = f"tasks/{task_id}/attachments/{attachment_id}/{filename}"
            signed_put_url = generate_signed_put_url(bucket_name, gcs_path, content_type)
        except Exception:
            logger.exception("Failed to generate signed URL for task %s", task_id)
            return _error_response("GCS_ERROR", "Failed to generate upload URL", 500, request=request)

        attachment = {
            "id": attachment_id,
            "filename": filename,
            "content_type": content_type,
            "gcs_path": gcs_path,
            "uploaded_by": effective_id,
            "uploaded": False,
            "description": body.get("description", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        task_obj.attachments.append(attachment)
        await _task_repo.upsert(task_obj)

        logger.info("Created attachment %s for task %s", attachment_id, task_id)
        return _json_response({
            "attachment_id": attachment_id,
            "proxy_url": f"/attachments/{attachment_id}",
            "signed_put_url": signed_put_url,
        }, request=request)
    finally:
        current_partner_id.reset(token)


# ──────────────────────────────────────────────
# Endpoint: DELETE /api/data/tasks/{taskId}/attachments/{attachmentId}
# ──────────────────────────────────────────────


async def delete_task_attachment(request: Request) -> Response:
    """Remove an attachment from a task and best-effort delete the GCS blob."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    task_id = request.path_params.get("taskId")
    attachment_id = request.path_params.get("attachmentId")

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_obj = await _task_repo.get_by_id(task_id)
        if not task_obj:
            return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

        att_to_remove = None
        for att in task_obj.attachments:
            if att.get("id") == attachment_id:
                att_to_remove = att
                break

        if not att_to_remove:
            return _error_response("NOT_FOUND", "Attachment not found", 404, request=request)

        task_obj.attachments.remove(att_to_remove)
        await _task_repo.upsert(task_obj)

        # Best-effort GCS cleanup
        gcs_path = att_to_remove.get("gcs_path")
        if gcs_path:
            try:
                from zenos.infrastructure.gcs_client import delete_blob, get_default_bucket
                delete_blob(get_default_bucket(), gcs_path)
            except Exception:
                logger.warning("Failed to delete GCS blob %s", gcs_path)

        logger.info("Deleted attachment %s from task %s", attachment_id, task_id)
        return _json_response({"ok": True}, request=request)
    finally:
        current_partner_id.reset(token)


# ──────────────────────────────────────────────
# TaskService helper
# ──────────────────────────────────────────────


def _make_task_service() -> TaskService:
    """Construct a TaskService from the initialized repositories."""
    return TaskService(
        task_repo=_task_repo,
        entity_repo=_entity_repo,
        blindspot_repo=_blindspot_repo,
    )


# ──────────────────────────────────────────────
# Endpoint: POST /api/data/tasks
# ──────────────────────────────────────────────


async def create_task(request: Request) -> Response:
    """Create a new task. title is required; all other fields are optional."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    title = body.get("title", "").strip()
    if not title:
        return _error_response("INVALID_INPUT", "title is required", 400, request=request)

    data: dict = {"title": title, "created_by": effective_id}
    for _field in ("description", "priority", "assignee", "due_date", "project"):
        _val = body.get(_field)
        if _val is not None:
            data[_field] = _val

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_service = _make_task_service()
        result = await task_service.create_task(data)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), 400, request=request)
    except Exception:
        logger.exception("Failed to create task")
        return _error_response("INTERNAL_ERROR", "Failed to create task", 500, request=request)
    finally:
        current_partner_id.reset(token)

    logger.info("Created task %s by partner %s", result.task.id, effective_id)
    return _json_response({"task": _task_to_dict(result.task)}, status_code=201, request=request)


# ──────────────────────────────────────────────
# Endpoint: PATCH /api/data/tasks/{taskId}
# ──────────────────────────────────────────────


async def update_task(request: Request) -> Response:
    """Update a task's fields. All fields are optional."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    task_id = request.path_params.get("taskId")
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    allowed_fields = {"status", "title", "description", "priority", "assignee", "due_date", "result"}
    updates: dict = {k: v for k, v in body.items() if k in allowed_fields and v is not None}

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_service = _make_task_service()
        result = await task_service.update_task(task_id, updates)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return _error_response("NOT_FOUND", msg, 404, request=request)
        return _error_response("INVALID_INPUT", msg, 400, request=request)
    except Exception:
        logger.exception("Failed to update task %s", task_id)
        return _error_response("INTERNAL_ERROR", "Failed to update task", 500, request=request)
    finally:
        current_partner_id.reset(token)

    logger.info("Updated task %s by partner %s", task_id, effective_id)
    return _json_response({"task": _task_to_dict(result.task)}, request=request)


# ──────────────────────────────────────────────
# Endpoint: POST /api/data/tasks/{taskId}/confirm
# ──────────────────────────────────────────────


async def confirm_task(request: Request) -> Response:
    """Approve or reject a task in review status."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    task_id = request.path_params.get("taskId")
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    action = body.get("action")
    if action not in ("approve", "reject"):
        return _error_response("INVALID_INPUT", "action must be 'approve' or 'reject'", 400, request=request)

    rejection_reason = body.get("rejection_reason")

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_service = _make_task_service()
        result = await task_service.confirm_task(
            task_id,
            accepted=(action == "approve"),
            rejection_reason=rejection_reason,
            updated_by=effective_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return _error_response("NOT_FOUND", msg, 404, request=request)
        return _error_response("INVALID_INPUT", msg, 400, request=request)
    except Exception:
        logger.exception("Failed to confirm task %s", task_id)
        return _error_response("INTERNAL_ERROR", "Failed to confirm task", 500, request=request)
    finally:
        current_partner_id.reset(token)

    logger.info("Confirmed task %s action=%s by partner %s", task_id, action, effective_id)
    return _json_response({"task": _task_to_dict(result.task)}, request=request)


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
    Route("/api/data/tasks/{taskId}/confirm", confirm_task, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/attachments/{attachmentId}", delete_task_attachment, methods=["DELETE", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/attachments", upload_task_attachment, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}", update_task, methods=["PATCH", "OPTIONS"]),
    Route("/api/data/tasks", list_tasks, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks", create_task, methods=["POST", "OPTIONS"]),
    Route("/attachments/{attachment_id}", get_attachment, methods=["GET", "OPTIONS"]),
]
