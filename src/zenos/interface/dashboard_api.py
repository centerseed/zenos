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
  POST   /api/docs/{docId}/publish                        — publish latest source as snapshot revision
  GET    /api/docs/{docId}                                — document delivery metadata
  GET    /api/docs/{docId}/content                        — read latest published markdown snapshot
  PATCH  /api/docs/{docId}/access                         — update document visibility
  POST   /api/docs/{docId}/share-links                    — create revocable share token
  DELETE /api/docs/share-links/{tokenId}                  — revoke share token
  GET    /s/{token}                                       — public read via share token

Auth: Firebase ID token → email → SQL partners table → partner scope.
CORS: allows requests from the Dashboard origin.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from zenos.application.knowledge.governance_service import GovernanceService
from zenos.application.knowledge.ontology_service import OntologyService, _collect_subtree_ids
from zenos.application.knowledge.source_service import SourceService
from zenos.application.action.task_service import TaskService
from zenos.domain.governance import compute_search_unused_signals, score_summary_quality
from zenos.domain.action import Task
from zenos.domain.knowledge import Blindspot, Entity, EntityType, Relationship, SourceType
from zenos.application.identity.workspace_context import (
    active_partner_view,
    build_available_workspaces,
    resolve_active_workspace_id,
)
from zenos.domain.partner_access import (
    describe_partner_access,
    is_guest,
    is_unassigned_partner,
)
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.unit_of_work import UnitOfWork
from zenos.infrastructure.action import PostgresTaskCommentRepository, SqlTaskRepository
from zenos.infrastructure.agent import SqlToolEventRepository
from zenos.infrastructure.identity import SqlPartnerRepository
from zenos.infrastructure.github_adapter import GitHubAdapter
from zenos.infrastructure.knowledge import SqlBlindspotRepository, SqlEntityRepository, SqlProtocolRepository, SqlRelationshipRepository
from zenos.infrastructure.sql_common import SCHEMA, get_cached_health, get_pool, upsert_health_cache
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
_tool_event_repo: SqlToolEventRepository | None = None
_comment_repo: PostgresTaskCommentRepository | None = None


async def _ensure_repos() -> None:
    global _repos_ready, _entity_repo, _relationship_repo, _blindspot_repo, _task_repo, _partner_repo, _tool_event_repo, _comment_repo
    if _repos_ready:
        return
    pool = await get_pool()
    _entity_repo = SqlEntityRepository(pool)
    _relationship_repo = SqlRelationshipRepository(pool)
    _blindspot_repo = SqlBlindspotRepository(pool)
    _task_repo = SqlTaskRepository(pool)
    _partner_repo = SqlPartnerRepository(pool)
    _tool_event_repo = SqlToolEventRepository(pool)
    _comment_repo = PostgresTaskCommentRepository(pool)
    _repos_ready = True


# ──────────────────────────────────────────────
# Partner lookup from SQL
# ──────────────────────────────────────────────


async def _get_partner_by_email_sql(email: str) -> dict | None:
    """Query SQL partners table by email. Returns partner dict or None."""
    await _ensure_repos()
    return await _partner_repo.get_by_email(email)


def _requested_active_workspace_id(request: Request) -> str | None:
    raw = request.headers.get("x-active-workspace-id", "").strip()
    return raw or None


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
    active_workspace_id = resolve_active_workspace_id(
        partner,
        _requested_active_workspace_id(request),
    )
    adjusted_partner, effective_id = active_partner_view(partner, active_workspace_id)
    adjusted_partner["activeWorkspaceId"] = active_workspace_id
    adjusted_partner["homeWorkspaceId"] = partner["id"]
    adjusted_partner["isHomeWorkspace"] = active_workspace_id == str(partner["id"])
    return adjusted_partner, effective_id


async def _list_all_entities_with_context(
    effective_id: str,
    *,
    type_filter: str | None = None,
) -> list[Entity]:
    """Load entities while the partner context is active."""
    token = current_partner_id.set(effective_id)
    try:
        return await _entity_repo.list_all(type_filter=type_filter)
    finally:
        current_partner_id.reset(token)


async def _get_entity_by_id_with_context(
    effective_id: str,
    entity_id: str,
) -> Entity | None:
    """Load a single entity while the partner context is active."""
    token = current_partner_id.set(effective_id)
    try:
        return await _entity_repo.get_by_id(entity_id)
    finally:
        current_partner_id.reset(token)


async def _compute_impact_chains_with_context(
    effective_id: str,
    entity_id: str,
) -> tuple[list[dict], list[dict]]:
    """Compute impact chains under the active partner context."""
    if _relationship_repo is None:
        return [], []
    ontology_service = OntologyService(
        _entity_repo,
        _relationship_repo,
        None,
        None,
        None,
    )
    token = current_partner_id.set(effective_id)
    try:
        return await asyncio.gather(
            ontology_service.compute_impact_chain(entity_id, direction="forward"),
            ontology_service.compute_impact_chain(entity_id, direction="reverse"),
        )
    finally:
        current_partner_id.reset(token)


# ──────────────────────────────────────────────
# Document Delivery helpers
# ──────────────────────────────────────────────


def _effective_source_status(source: dict) -> str:
    return str(source.get("source_status") or source.get("status") or "valid")


def _select_publish_source(sources: list[dict]) -> dict | None:
    if not sources:
        return None
    primary_valid = next(
        (s for s in sources if s.get("is_primary") and _effective_source_status(s) == "valid"),
        None,
    )
    if primary_valid:
        return primary_valid
    first_valid = next((s for s in sources if _effective_source_status(s) == "valid"), None)
    if first_valid:
        return first_valid
    primary_any = next((s for s in sources if s.get("is_primary")), None)
    return primary_any or sources[0]


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def _is_document_visible_for_partner(doc: Entity, partner: dict, effective_id: str) -> bool:
    if partner.get("isAdmin"):
        return True
    if is_unassigned_partner(partner):
        return False
    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
        if not doc.id or doc.id not in allowed_ids:
            return False
        return doc.visibility == "public"
    return OntologyService.is_entity_visible_for_partner(doc, partner)


async def _get_latest_revision(partner_id: str, doc_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT id, doc_id, source_id, source_version_ref, snapshot_bucket,
                   snapshot_object_path, content_hash, render_format, content_type, created_at
            FROM {SCHEMA}.document_revisions
            WHERE partner_id = $1 AND doc_id = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            partner_id,
            doc_id,
        )
    return dict(row) if row else None


async def _get_revision_by_id(partner_id: str, revision_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT id, doc_id, source_id, source_version_ref, snapshot_bucket,
                   snapshot_object_path, content_hash, render_format, content_type, created_at
            FROM {SCHEMA}.document_revisions
            WHERE partner_id = $1 AND id = $2
            LIMIT 1
            """,
            partner_id,
            revision_id,
        )
    return dict(row) if row else None


async def _create_revision_and_mark_ready(
    *,
    partner_id: str,
    doc_id: str,
    source_id: str | None,
    source_version_ref: str | None,
    snapshot_bucket: str,
    snapshot_object_path: str,
    content_hash: str,
    content_type: str,
    created_by: str,
) -> str:
    revision_id = uuid.uuid4().hex
    canonical_path = f"/docs/{doc_id}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.document_revisions (
                    id, partner_id, doc_id, source_id, source_version_ref,
                    snapshot_bucket, snapshot_object_path, content_hash, render_format,
                    content_type, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'markdown',$9,$10)
                """,
                revision_id,
                partner_id,
                doc_id,
                source_id,
                source_version_ref,
                snapshot_bucket,
                snapshot_object_path,
                content_hash,
                content_type,
                created_by,
            )
            await conn.execute(
                f"""
                UPDATE {SCHEMA}.entities
                SET canonical_path = $1,
                    primary_snapshot_revision_id = $2,
                    last_published_at = now(),
                    delivery_status = 'ready',
                    updated_at = now()
                WHERE partner_id = $3 AND id = $4
                """,
                canonical_path,
                revision_id,
                partner_id,
                doc_id,
            )
    return revision_id


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _lookup_doc_for_share_token(token: str) -> dict | None:
    token_digest = _token_hash(token)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT
                st.id AS token_id,
                st.partner_id,
                st.doc_id,
                st.expires_at,
                st.max_access_count,
                st.used_count,
                st.revoked_at,
                e.name AS doc_name,
                e.primary_snapshot_revision_id
            FROM {SCHEMA}.document_share_tokens st
            JOIN {SCHEMA}.entities e
              ON e.partner_id = st.partner_id AND e.id = st.doc_id
            WHERE st.token_hash = $1
            LIMIT 1
            """,
            token_digest,
        )
    return dict(row) if row else None


async def _increment_share_token_usage(token_id: str, partner_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE {SCHEMA}.document_share_tokens
            SET used_count = used_count + 1
            WHERE id = $1 AND partner_id = $2
            """,
            token_id,
            partner_id,
        )


# ──────────────────────────────────────────────
# Visibility helpers (permission governance Phase 0)
# ──────────────────────────────────────────────


def _build_allowed_entity_ids(partner: dict, entity_map: dict[str, Entity]) -> set[str]:
    """Return the set of entity IDs allowed for a guest."""
    authorized_ids = describe_partner_access(partner)["authorized_l1_ids"]
    allowed: set[str] = set()
    for l1_id in authorized_ids:
        allowed |= _collect_subtree_ids(l1_id, entity_map)
    return allowed


async def _is_task_visible_for_partner(
    task: Task,
    partner: dict,
    effective_id: str,
    allowed_ids: set[str] | None = None,
) -> bool:
    """Task visibility rules:

    - Admin: always visible.
    - Guest: task must have at least one linked entity in allowed_ids.
      Tasks with no linked entities are NOT visible to guests.
    - Member: task is visible only if ALL linked entities are visible.
      Tasks with no linked entities are always visible (fail-open).
    """
    try:
        linked = task.linked_entities or []
        if partner.get("isAdmin"):
            return True
        if is_unassigned_partner(partner):
            return False

        if is_guest(partner):
            # Guest: requires at least one linked entity in scope.
            if not linked:
                return False
            if allowed_ids is None:
                return False
            for eid in linked:
                if isinstance(eid, dict):
                    eid = eid.get("id", "")
                if eid and eid in allowed_ids:
                    return True
            return False

        # Member: all linked entities must be visible.
        if not linked:
            return True
        for eid in linked:
            if isinstance(eid, dict):
                eid = eid.get("id", "")
            if not eid:
                continue
            entity = await _get_entity_by_id_with_context(effective_id, eid)
            if entity and not OntologyService.is_entity_visible_for_partner(entity, partner):
                return False
        return True
    except Exception:
        logger.warning("_is_task_visible_for_partner failed, defaulting to visible", exc_info=True)
        return True


async def _is_blindspot_visible_for_partner(
    bs: Blindspot,
    partner: dict,
    effective_id: str,
) -> bool:
    """Blindspot is visible if ANY related entity is visible.

    Guests never see blindspots.
    Blindspots with no related entities are always visible (fail-open for members).
    """
    try:
        if partner.get("isAdmin"):
            return True
        if is_unassigned_partner(partner):
            return False
        if is_guest(partner):
            return False
        related = bs.related_entity_ids or []
        if not related:
            return True
        for eid in related:
            entity = await _get_entity_by_id_with_context(effective_id, eid)
            if entity and OntologyService.is_entity_visible_for_partner(entity, partner):
                return True
        return False
    except Exception:
        logger.warning("_is_blindspot_visible_for_partner failed, defaulting to visible", exc_info=True)
        return True


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
        # ADR-022 Document Bundle fields
        "docRole": e.doc_role,
        "changeSummary": e.change_summary,
        "summaryUpdatedAt": e.summary_updated_at,
    }


def _relationship_to_dict(r: Relationship) -> dict:
    return {
        "id": r.id,
        "sourceEntityId": r.source_entity_id,
        "targetId": r.target_id,
        "type": r.type,
        "description": r.description,
        "confirmedByUser": r.confirmed_by_user,
        "verb": r.verb,
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
        "blocked": "todo",
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

    raw_partner = await _get_partner_by_email_sql(email)
    if not raw_partner:
        return _error_response("NOT_FOUND", f"No partner found for email {email}", 404, request=request)

    active_workspace_id = resolve_active_workspace_id(
        raw_partner,
        _requested_active_workspace_id(request),
    )
    partner, _ = active_partner_view(raw_partner, active_workspace_id)
    partner["activeWorkspaceId"] = active_workspace_id
    partner["homeWorkspaceId"] = raw_partner["id"]
    partner["isHomeWorkspace"] = active_workspace_id == str(raw_partner["id"])

    async def _lookup_partner(pid: str) -> dict | None:
        await _ensure_repos()
        return await _partner_repo.get_by_id(pid)

    partner["availableWorkspaces"] = await build_available_workspaces(raw_partner, _lookup_partner)
    return _json_response({"partner": partner}, request=request)


# ──────────────────────────────────────────────
# Endpoint: GET /api/partner/preferences
# Endpoint: PATCH /api/partner/preferences
# ──────────────────────────────────────────────


async def get_partner_preferences(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    email = decoded.get("email")
    if not email:
        return _error_response("INVALID_INPUT", "Email not found in token", 400, request=request)

    raw_partner = await _get_partner_by_email_sql(email)
    if not raw_partner:
        return _error_response("NOT_FOUND", f"No partner found for email {email}", 404, request=request)

    await _ensure_repos()
    preferences = await _partner_repo.get_preferences(str(raw_partner["id"]))
    return _json_response({"preferences": preferences}, request=request)


async def update_partner_preferences(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    email = decoded.get("email")
    if not email:
        return _error_response("INVALID_INPUT", "Email not found in token", 400, request=request)

    raw_partner = await _get_partner_by_email_sql(email)
    if not raw_partner:
        return _error_response("NOT_FOUND", f"No partner found for email {email}", 404, request=request)

    import json as _json

    body = await request.body()
    try:
        patch = _json.loads(body)
    except (ValueError, TypeError):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    if not isinstance(patch, dict):
        return _error_response("INVALID_INPUT", "Body must be a JSON object", 400, request=request)

    await _ensure_repos()
    updated = await _partner_repo.update_preferences(str(raw_partner["id"]), patch)
    return _json_response({"preferences": updated}, request=request)


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
    if is_unassigned_partner(partner):
        return _json_response({"entities": []}, request=request)
    entities = await _list_all_entities_with_context(effective_id, type_filter=type_filter)

    if is_guest(partner):
        # Need full entity tree (not just type-filtered subset) to compute subtrees correctly.
        all_entities = await _list_all_entities_with_context(effective_id) if type_filter else entities
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
        entities = [
            e for e in entities
            if e.id in allowed_ids and e.visibility == "public"
        ]
    else:
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
    if is_unassigned_partner(partner):
        return _error_response("NOT_FOUND", f"Entity {request.path_params.get('id')} not found", 404, request=request)

    entity_id = request.path_params.get("id")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        entity = await _entity_repo.get_by_id(entity_id)
    finally:
        current_partner_id.reset(token)

    if not entity:
        return _error_response("NOT_FOUND", f"Entity {entity_id} not found", 404, request=request)

    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
        if entity_id not in allowed_ids or entity.visibility != "public":
            return _error_response("NOT_FOUND", f"Entity {entity_id} not found", 404, request=request)
    elif not OntologyService.is_entity_visible_for_partner(entity, partner):
        return _error_response("NOT_FOUND", f"Entity {entity_id} not found", 404, request=request)

    impact_chain, reverse_impact_chain = await _compute_impact_chains_with_context(effective_id, entity_id)

    return _json_response(
        {
            "entity": _entity_to_dict(entity),
            "impact_chain": impact_chain,
            "reverse_impact_chain": reverse_impact_chain,
        },
        request=request,
    )


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
    if is_unassigned_partner(partner):
        return _json_response({"entities": [], "count": 0}, request=request)
    token = current_partner_id.set(effective_id)
    try:
        children = await _entity_repo.list_by_parent(entity_id)
    finally:
        current_partner_id.reset(token)

    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in (all_entities or []) if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
        # If the parent entity itself is not in scope, return empty (no info leak)
        if entity_id not in allowed_ids:
            return _json_response({"entities": [], "count": 0}, request=request)
        # Filter children to L1 scope + public visibility
        children = [
            e for e in children
            if e.id in allowed_ids and e.visibility == "public"
        ]
    else:
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
    if is_unassigned_partner(partner):
        return _json_response({"relationships": []}, request=request)
    token = current_partner_id.set(effective_id)
    try:
        entity = await _entity_repo.get_by_id(entity_id)
        if not entity or not OntologyService.is_entity_visible_for_partner(entity, partner):
            return _json_response({"relationships": []}, request=request)
        relationships = await _relationship_repo.list_by_entity(entity_id)
    finally:
        current_partner_id.reset(token)

    allowed_ids: set[str] | None = None
    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
        if not allowed_ids or entity_id not in allowed_ids or entity.visibility != "public":
            return _json_response({"relationships": []}, request=request)

    visible_relationships: list[Relationship] = []
    for rel in relationships:
        src = await _get_entity_by_id_with_context(effective_id, rel.source_entity_id)
        tgt = await _get_entity_by_id_with_context(effective_id, rel.target_id)
        if not src or not tgt:
            continue
        if is_guest(partner):
            if not allowed_ids:
                continue
            if src.id not in allowed_ids or tgt.id not in allowed_ids:
                continue
            if src.visibility != "public" or tgt.visibility != "public":
                continue
        elif not (
            OntologyService.is_entity_visible_for_partner(src, partner)
            and OntologyService.is_entity_visible_for_partner(tgt, partner)
        ):
            continue
        visible_relationships.append(rel)

    return _json_response(
        {"relationships": [_relationship_to_dict(r) for r in visible_relationships]},
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
    if is_unassigned_partner(partner):
        return _json_response({"relationships": []}, request=request)
    token = current_partner_id.set(effective_id)
    try:
        relationships = await _relationship_repo.list_all()
    finally:
        current_partner_id.reset(token)

    visible_relationships: list[Relationship] = []
    allowed_ids: set[str] | None = None
    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
    for rel in relationships:
        src = await _get_entity_by_id_with_context(effective_id, rel.source_entity_id)
        tgt = await _get_entity_by_id_with_context(effective_id, rel.target_id)
        if not src or not tgt:
            continue
        if is_guest(partner):
            if not allowed_ids:
                continue
            if src.id not in allowed_ids or tgt.id not in allowed_ids:
                continue
            if src.visibility != "public" or tgt.visibility != "public":
                continue
        elif not (
            OntologyService.is_entity_visible_for_partner(src, partner)
            and OntologyService.is_entity_visible_for_partner(tgt, partner)
        ):
            continue
        visible_relationships.append(rel)

    return _json_response(
        {"relationships": [_relationship_to_dict(r) for r in visible_relationships]},
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
    if is_unassigned_partner(partner):
        return _json_response({"blindspots": []}, request=request)
    token = current_partner_id.set(effective_id)
    try:
        blindspots = await _blindspot_repo.list_all(entity_id=entity_id)
    finally:
        current_partner_id.reset(token)

    # Filter blindspots by related entity visibility
    visible_blindspots = []
    for bs in blindspots:
        if await _is_blindspot_visible_for_partner(bs, partner, effective_id):
            visible_blindspots.append(bs)

    return _json_response(
        {"blindspots": [_blindspot_to_dict(b) for b in visible_blindspots]},
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
    if is_unassigned_partner(partner):
        return _json_response({"tasks": []}, request=request)
    token = current_partner_id.set(effective_id)
    try:
        tasks = await _task_repo.list_all(status=status_list, assignee=assignee, created_by=created_by, limit=500)
    finally:
        current_partner_id.reset(token)

    # Build allowed_ids for guests (needed for task filtering)
    allowed_ids: set[str] | None = None
    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)

    # Filter tasks by linked entity visibility
    visible_tasks = []
    for t in tasks:
        if await _is_task_visible_for_partner(t, partner, effective_id, allowed_ids=allowed_ids):
            visible_tasks.append(t)

    return _json_response({"tasks": [_task_to_dict(t) for t in visible_tasks]}, request=request)


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
    if is_unassigned_partner(partner):
        return _json_response({"tasks": []}, request=request)

    # Build allowed_ids for guests BEFORE the entity check so we can reject
    # out-of-scope entity IDs even if they happen to be public.
    allowed_ids: set[str] | None = None
    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_map = {e.id: e for e in all_entities if e.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_map)
        if entity_id not in allowed_ids:
            return _json_response({"tasks": []}, request=request)

    token = current_partner_id.set(effective_id)
    try:
        # Check if the requested entity itself is visible
        entity = await _entity_repo.get_by_id(entity_id)
        if entity and not OntologyService.is_entity_visible_for_partner(entity, partner):
            return _json_response({"tasks": []}, request=request)
        tasks = await _task_repo.list_all(linked_entity=entity_id)
    finally:
        current_partner_id.reset(token)

    # Filter tasks by linked entity visibility
    visible_tasks = [
        t for t in tasks
        if await _is_task_visible_for_partner(t, partner, effective_id, allowed_ids=allowed_ids)
    ]

    return _json_response({"tasks": [_task_to_dict(t) for t in visible_tasks]}, request=request)


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
        relationship_repo=_relationship_repo,
        uow_factory=lambda: UnitOfWork(_task_repo._pool),
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
# Helper: build allowed_ids for guest
# ──────────────────────────────────────────────


async def _get_allowed_ids_for_guest(
    partner: dict,
    effective_id: str,
) -> set[str] | None:
    """Return the set of allowed entity IDs for a guest, or None otherwise."""
    if not is_guest(partner):
        return None
    all_entities = await _list_all_entities_with_context(effective_id)
    entity_map = {e.id: e for e in all_entities if e.id}
    return _build_allowed_entity_ids(partner, entity_map)


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/tasks/{taskId}/comments
# ──────────────────────────────────────────────


async def list_comments(request: Request) -> Response:
    """List all comments for a task."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    task_id = request.path_params.get("taskId")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_obj = await _task_repo.get_by_id(task_id)
    finally:
        current_partner_id.reset(token)

    if not task_obj:
        return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

    allowed_ids = await _get_allowed_ids_for_guest(partner, effective_id)
    if not await _is_task_visible_for_partner(task_obj, partner, effective_id, allowed_ids=allowed_ids):
        return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

    comments = await _comment_repo.list_by_task(task_id)
    return _json_response({"comments": comments}, request=request)


async def _notify_task_owner_of_comment(task_obj: object, commenter_partner: dict, commenter_id: str, content: str) -> None:
    """Fire-and-forget: notify the task owner when a comment is added.

    Handles both dataclass Task and dict representations of task_obj.
    Silently exits if owner cannot be found, is the commenter, or email fails.
    """
    from zenos.infrastructure.email_client import EmailService

    try:
        # Extract created_by — supports dataclass and dict
        if isinstance(task_obj, dict):
            task_creator_id = task_obj.get("created_by")
            task_title = task_obj.get("title", "")
        else:
            task_creator_id = getattr(task_obj, "created_by", None)
            task_title = getattr(task_obj, "title", "")

        if not task_creator_id or task_creator_id == commenter_id:
            return  # Don't notify self

        await _ensure_repos()
        owner = await _partner_repo.get_by_id(task_creator_id)
        if not owner or not owner.get("email"):
            return

        commenter_name = commenter_partner.get("displayName") or commenter_partner.get("email", "")
        email_service = EmailService()
        await email_service.send_comment_notification(
            to_email=owner["email"],
            commenter_name=commenter_name,
            task_title=task_title,
            content=content,
        )
    except Exception:
        logger.warning("Failed to send comment notification", exc_info=True)


# ──────────────────────────────────────────────
# Endpoint: POST /api/data/tasks/{taskId}/comments
# ──────────────────────────────────────────────


async def create_comment(request: Request) -> Response:
    """Add a comment to a task."""
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

    content = (body.get("content") or "").strip()
    if not content:
        return _error_response("INVALID_INPUT", "content is required and cannot be empty", 400, request=request)

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_obj = await _task_repo.get_by_id(task_id)
    finally:
        current_partner_id.reset(token)

    if not task_obj:
        return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

    allowed_ids = await _get_allowed_ids_for_guest(partner, effective_id)
    if not await _is_task_visible_for_partner(task_obj, partner, effective_id, allowed_ids=allowed_ids):
        return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

    comment = await _comment_repo.create(task_id=task_id, partner_id=effective_id, content=content)
    logger.info("Created comment %s on task %s by partner %s", comment["id"], task_id, effective_id)

    asyncio.ensure_future(_notify_task_owner_of_comment(task_obj, partner, effective_id, content))

    return _json_response({"comment": comment}, status_code=201, request=request)


# ──────────────────────────────────────────────
# Endpoint: DELETE /api/data/tasks/{taskId}/comments/{commentId}
# ──────────────────────────────────────────────


async def delete_comment(request: Request) -> Response:
    """Delete a comment. Only the author or an admin may delete."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    task_id = request.path_params.get("taskId")
    comment_id = request.path_params.get("commentId")

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_obj = await _task_repo.get_by_id(task_id)
    finally:
        current_partner_id.reset(token)

    if not task_obj:
        return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

    allowed_ids = await _get_allowed_ids_for_guest(partner, effective_id)
    if not await _is_task_visible_for_partner(task_obj, partner, effective_id, allowed_ids=allowed_ids):
        return _error_response("NOT_FOUND", f"Task '{task_id}' not found", 404, request=request)

    comment = await _comment_repo.get_by_id(comment_id)
    if not comment:
        return _error_response("NOT_FOUND", f"Comment '{comment_id}' not found", 404, request=request)

    # Prevent lateral access: comment must belong to this task
    if comment["task_id"] != task_id:
        return _error_response("NOT_FOUND", f"Comment '{comment_id}' not found", 404, request=request)

    is_author = comment["partner_id"] == effective_id
    if not is_author and not partner.get("isAdmin"):
        return _error_response("FORBIDDEN", "You do not have permission to delete this comment", 403, request=request)

    await _comment_repo.delete(comment_id)
    logger.info("Deleted comment %s from task %s by partner %s", comment_id, task_id, effective_id)
    return Response(status_code=204, headers=dict(_cors_headers(request)))


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
# Endpoint: GET /api/data/quality-signals
# ──────────────────────────────────────────────


async def get_quality_signals(request: Request) -> Response:
    """Return quality signal flags for all entities.

    Response:
        {
          "search_unused": [{ "entity_id": str, "entity_name": str, ... }],
          "summary_poor":  [{ "entity_id": str, "entity_name": str, "quality_score": str, ... }]
        }
    """
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        all_entities = await _entity_repo.list_all()
    finally:
        current_partner_id.reset(token)

    # Search-unused signals
    search_unused: list[dict] = []
    try:
        if _tool_event_repo is not None:
            usage_stats = await _tool_event_repo.get_entity_usage_stats(effective_id, days=30)
            non_doc_entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
            search_unused = compute_search_unused_signals(usage_stats, non_doc_entities)
    except Exception:
        logger.warning("Quality signals: search_unused computation failed", exc_info=True)

    # Summary quality flags (poor only, for L2 active/draft modules)
    summary_poor: list[dict] = []
    try:
        l2_entities = [
            e for e in all_entities
            if e.type == EntityType.MODULE and e.status in ("active", "draft") and e.id
        ]
        for e in l2_entities:
            quality = score_summary_quality(e.summary or "", e.type)
            if quality["quality_score"] == "poor":
                summary_poor.append({
                    "entity_id": e.id,
                    "entity_name": e.name,
                    **quality,
                })
    except Exception:
        logger.warning("Quality signals: summary_poor computation failed", exc_info=True)

    return _json_response(
        {"search_unused": search_unused, "summary_poor": summary_poor},
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/governance-health
# ──────────────────────────────────────────────

_HEALTH_CACHE_MAX_AGE_SECONDS = 24 * 3600  # 24 hours


async def get_governance_health(request: Request) -> Response:
    """Return governance health level for the current partner.

    Response:
        {
          "overall_level": "green" | "yellow" | "red",
          "cached_at": "ISO datetime" | null,
          "stale": false | true
        }

    Safe degradation: any failure returns green + stale=true.
    """
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    await _ensure_repos()
    pool = await get_pool()

    # 1. Try cache (table may not exist yet — tolerate errors)
    cached = None
    try:
        cached = await get_cached_health(pool, effective_id)
    except Exception:
        logger.debug("governance-health: cache read failed (table may not exist)")

    if cached is not None:
        computed_at = cached["computed_at"]
        age_seconds = (datetime.now(timezone.utc) - computed_at).total_seconds()
        if age_seconds < _HEALTH_CACHE_MAX_AGE_SECONDS:
            return _json_response({
                "overall_level": cached["overall_level"],
                "cached_at": computed_at.isoformat(),
                "stale": False,
            }, request=request)

    # 2. Cache miss or stale — recompute
    try:
        token = current_partner_id.set(effective_id)
        try:
            governance_service = GovernanceService(
                entity_repo=_entity_repo,
                relationship_repo=_relationship_repo,
                protocol_repo=SqlProtocolRepository(pool),
                blindspot_repo=_blindspot_repo,
            )
            health_signal = await governance_service.compute_health_signal()
        finally:
            current_partner_id.reset(token)

        overall_level = health_signal.get("overall_level", "green")
        try:
            await upsert_health_cache(pool, effective_id, overall_level)
        except Exception:
            logger.debug("governance-health: cache write failed (table may not exist)")
        return _json_response({
            "overall_level": overall_level,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "stale": False,
        }, request=request)
    except Exception:
        logger.warning("governance-health: compute failed, returning degraded response", exc_info=True)
        # Return stale cache if available, otherwise safe green
        if cached is not None:
            return _json_response({
                "overall_level": cached["overall_level"],
                "cached_at": cached["computed_at"].isoformat(),
                "stale": True,
            }, request=request)
        return _json_response({
            "overall_level": "green",
            "cached_at": None,
            "stale": True,
        }, request=request)


# ──────────────────────────────────────────────
# Document Delivery Endpoints
# ──────────────────────────────────────────────


async def publish_document_snapshot(request: Request) -> Response:
    """Publish a document source into a private snapshot revision."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("FORBIDDEN", "Current workspace cannot publish documents", 403, request=request)
    if is_guest(partner):
        return _error_response("FORBIDDEN", "Guest cannot publish document snapshots", 403, request=request)

    doc_id = request.path_params.get("docId")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        doc_entity = await _entity_repo.get_by_id(doc_id)
    finally:
        current_partner_id.reset(token)

    if not doc_entity or doc_entity.type != EntityType.DOCUMENT:
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)
    if not await _is_document_visible_for_partner(doc_entity, partner, effective_id):
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)

    source = _select_publish_source(doc_entity.sources or [])
    if not source:
        return _error_response("INVALID_INPUT", "Document has no source to publish", 400, request=request)

    source_uri = str(source.get("uri", "")).strip()
    source_type = str(source.get("type", "")).strip()
    source_id = source.get("source_id")
    if not source_uri:
        return _error_response("INVALID_INPUT", "Selected source has empty URI", 400, request=request)
    if source_type != SourceType.GITHUB:
        return _error_response(
            "SOURCE_UNAVAILABLE",
            f"Source type '{source_type}' is not yet publishable in Phase 1",
            409,
            request=request,
        )

    source_service = SourceService(entity_repo=_entity_repo, source_adapter=GitHubAdapter())
    token = current_partner_id.set(effective_id)
    try:
        content = await source_service.read_source(doc_id, source_uri=source_uri)
    except FileNotFoundError:
        return _error_response("SOURCE_NOT_FOUND", "Source file not found", 404, request=request)
    except PermissionError:
        return _error_response("SOURCE_FORBIDDEN", "Permission denied while reading source", 403, request=request)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), 400, request=request)
    except RuntimeError as exc:
        return _error_response("SOURCE_ERROR", str(exc), 409, request=request)
    finally:
        current_partner_id.reset(token)

    try:
        from zenos.infrastructure.gcs_client import get_documents_bucket, upload_blob

        revision_id = uuid.uuid4().hex
        snapshot_path = f"docs/{doc_id}/revisions/{revision_id}.md"
        bucket = get_documents_bucket()
        payload = content.encode("utf-8")
        upload_blob(bucket, snapshot_path, payload, "text/markdown; charset=utf-8")
        content_hash = hashlib.sha256(payload).hexdigest()
    except Exception:
        logger.exception("Failed to write document snapshot for %s", doc_id)
        return _error_response("GCS_ERROR", "Failed to write document snapshot", 500, request=request)

    try:
        stored_revision_id = await _create_revision_and_mark_ready(
            partner_id=effective_id,
            doc_id=doc_id,
            source_id=source_id,
            source_version_ref=source_uri,
            snapshot_bucket=bucket,
            snapshot_object_path=snapshot_path,
            content_hash=content_hash,
            content_type="text/markdown; charset=utf-8",
            created_by=effective_id,
        )
    except Exception:
        logger.exception("Failed to persist revision metadata for %s", doc_id)
        return _error_response("INTERNAL_ERROR", "Failed to persist snapshot revision", 500, request=request)

    return _json_response(
        {
            "doc_id": doc_id,
            "canonical_path": f"/docs/{doc_id}",
            "revision_id": stored_revision_id,
            "delivery_status": "ready",
            "source_id": source_id,
            "source_uri": source_uri,
        },
        request=request,
    )


async def get_document_delivery(request: Request) -> Response:
    """Return document delivery metadata for Reader page."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("NOT_FOUND", f"Document '{request.path_params.get('docId')}' not found", 404, request=request)

    doc_id = request.path_params.get("docId")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        doc_entity = await _entity_repo.get_by_id(doc_id)
    finally:
        current_partner_id.reset(token)

    if not doc_entity or doc_entity.type != EntityType.DOCUMENT:
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)
    if not await _is_document_visible_for_partner(doc_entity, partner, effective_id):
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT canonical_path, primary_snapshot_revision_id, last_published_at, delivery_status
            FROM {SCHEMA}.entities
            WHERE partner_id = $1 AND id = $2
            """,
            effective_id,
            doc_id,
        )
    latest_revision = await _get_latest_revision(effective_id, doc_id)

    return _json_response(
        {
            "document": {
                "id": doc_entity.id,
                "name": doc_entity.name,
                "summary": doc_entity.summary,
                "visibility": doc_entity.visibility,
                "sources": doc_entity.sources or [],
                "doc_role": doc_entity.doc_role or "single",
                "canonical_path": row["canonical_path"] if row else None,
                "primary_snapshot_revision_id": row["primary_snapshot_revision_id"] if row else None,
                "last_published_at": row["last_published_at"] if row else None,
                "delivery_status": row["delivery_status"] if row else None,
                "latest_revision": latest_revision,
            }
        },
        request=request,
    )


async def get_document_content(request: Request) -> Response:
    """Return latest published markdown snapshot content after ACL check."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("NOT_FOUND", f"Document '{request.path_params.get('docId')}' not found", 404, request=request)

    doc_id = request.path_params.get("docId")
    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        doc_entity = await _entity_repo.get_by_id(doc_id)
    finally:
        current_partner_id.reset(token)

    if not doc_entity or doc_entity.type != EntityType.DOCUMENT:
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)
    if not await _is_document_visible_for_partner(doc_entity, partner, effective_id):
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT primary_snapshot_revision_id, canonical_path, delivery_status
            FROM {SCHEMA}.entities
            WHERE partner_id = $1 AND id = $2
            """,
            effective_id,
            doc_id,
        )

    primary_revision_id = row["primary_snapshot_revision_id"] if row else None
    revision = (
        await _get_revision_by_id(effective_id, primary_revision_id)
        if primary_revision_id
        else None
    )
    if revision is None:
        revision = await _get_latest_revision(effective_id, doc_id)
    if revision is None:
        return _error_response("NOT_FOUND", "No published snapshot for this document", 404, request=request)

    try:
        from google.cloud.exceptions import NotFound as GcsNotFound  # type: ignore[import-untyped]
        from zenos.infrastructure.gcs_client import download_blob

        raw, content_type = download_blob(
            revision["snapshot_bucket"],
            revision["snapshot_object_path"],
        )
        content = raw.decode("utf-8")
    except GcsNotFound:
        return _error_response("NOT_FOUND", "Snapshot object not found", 404, request=request)
    except Exception:
        logger.exception("Failed to load snapshot content for %s", doc_id)
        return _error_response("INTERNAL_ERROR", "Failed to read snapshot content", 500, request=request)

    return _json_response(
        {
            "doc_id": doc_id,
            "canonical_path": row["canonical_path"] if row else f"/docs/{doc_id}",
            "delivery_status": row["delivery_status"] if row else None,
            "revision": revision,
            "content_type": content_type,
            "content": content,
        },
        request=request,
    )


async def update_document_access(request: Request) -> Response:
    """Update document visibility (grants are reserved for next iteration)."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("FORBIDDEN", "Current workspace cannot update document access", 403, request=request)
    if is_guest(partner):
        return _error_response("FORBIDDEN", "Guest cannot update document access", 403, request=request)

    doc_id = request.path_params.get("docId")
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    visibility = str(body.get("visibility", "")).strip()
    if visibility not in {"public", "restricted", "confidential"}:
        return _error_response(
            "INVALID_INPUT",
            "visibility must be one of: public, restricted, confidential",
            400,
            request=request,
        )

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        doc_entity = await _entity_repo.get_by_id(doc_id)
    finally:
        current_partner_id.reset(token)

    if not doc_entity or doc_entity.type != EntityType.DOCUMENT:
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)
    if not await _is_document_visible_for_partner(doc_entity, partner, effective_id):
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE {SCHEMA}.entities
            SET visibility = $1,
                updated_at = now()
            WHERE partner_id = $2 AND id = $3
            """,
            visibility,
            effective_id,
            doc_id,
        )

    warnings: list[str] = []
    if "grants" in body:
        warnings.append("grants payload is reserved for Phase 1.5 and was not persisted")

    return _json_response(
        {"doc_id": doc_id, "visibility": visibility, "warnings": warnings},
        request=request,
    )


async def create_document_share_link(request: Request) -> Response:
    """Create revocable external share token for a document."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("FORBIDDEN", "Current workspace cannot create share links", 403, request=request)
    if is_guest(partner):
        return _error_response("FORBIDDEN", "Guest cannot create share links", 403, request=request)

    doc_id = request.path_params.get("docId")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if body is None:
        body = {}

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        doc_entity = await _entity_repo.get_by_id(doc_id)
    finally:
        current_partner_id.reset(token)

    if not doc_entity or doc_entity.type != EntityType.DOCUMENT:
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)
    if not await _is_document_visible_for_partner(doc_entity, partner, effective_id):
        return _error_response("NOT_FOUND", f"Document '{doc_id}' not found", 404, request=request)

    expires_at = _parse_iso_datetime(body.get("expires_at"))
    if expires_at is None:
        expires_in_hours = body.get("expires_in_hours", 24 * 7)
        try:
            expires_in_hours = int(expires_in_hours)
        except Exception:
            return _error_response("INVALID_INPUT", "expires_in_hours must be an integer", 400, request=request)
        if expires_in_hours <= 0:
            return _error_response("INVALID_INPUT", "expires_in_hours must be > 0", 400, request=request)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

    max_access_count = body.get("max_access_count")
    if max_access_count is not None:
        try:
            max_access_count = int(max_access_count)
        except Exception:
            return _error_response("INVALID_INPUT", "max_access_count must be an integer", 400, request=request)
        if max_access_count <= 0:
            return _error_response("INVALID_INPUT", "max_access_count must be > 0", 400, request=request)

    token_id = uuid.uuid4().hex
    raw_token = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    digest = _token_hash(raw_token)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {SCHEMA}.document_share_tokens (
                id, partner_id, doc_id, token_hash, scope,
                expires_at, max_access_count, used_count, revoked_at, created_by
            ) VALUES ($1,$2,$3,$4,'read',$5,$6,0,NULL,$7)
            """,
            token_id,
            effective_id,
            doc_id,
            digest,
            expires_at,
            max_access_count,
            effective_id,
        )

    return _json_response(
        {
            "token_id": token_id,
            "doc_id": doc_id,
            "share_url": f"/s?token={raw_token}",
            "expires_at": expires_at,
            "max_access_count": max_access_count,
        },
        request=request,
    )


async def revoke_document_share_link(request: Request) -> Response:
    """Revoke a previously created share token."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("FORBIDDEN", "Current workspace cannot revoke share links", 403, request=request)
    if is_guest(partner):
        return _error_response("FORBIDDEN", "Guest cannot revoke share links", 403, request=request)

    token_id = request.path_params.get("tokenId")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE {SCHEMA}.document_share_tokens
            SET revoked_at = now()
            WHERE id = $1 AND partner_id = $2
            RETURNING id, doc_id, revoked_at
            """,
            token_id,
            effective_id,
        )
    if row is None:
        return _error_response("NOT_FOUND", f"Share token '{token_id}' not found", 404, request=request)
    return _json_response(
        {"token_id": row["id"], "doc_id": row["doc_id"], "revoked_at": row["revoked_at"]},
        request=request,
    )


async def access_document_share_link(request: Request) -> Response:
    """Public endpoint: resolve token and return shared markdown snapshot."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    token = request.path_params.get("token")
    token_row = await _lookup_doc_for_share_token(token)
    if token_row is None:
        return _error_response("NOT_FOUND", "Share link not found", 404, request=request)
    if token_row.get("revoked_at") is not None:
        return _error_response("UNAUTHORIZED", "Share link is revoked", 401, request=request)

    now = datetime.now(timezone.utc)
    expires_at = token_row.get("expires_at")
    if expires_at is not None and expires_at <= now:
        return _error_response("EXPIRED", "Share link expired", 410, request=request)

    max_access = token_row.get("max_access_count")
    used_count = int(token_row.get("used_count") or 0)
    if max_access is not None and used_count >= int(max_access):
        return _error_response("EXPIRED", "Share link exhausted", 410, request=request)

    partner_id = token_row["partner_id"]
    doc_id = token_row["doc_id"]
    revision_id = token_row.get("primary_snapshot_revision_id")
    revision = await _get_revision_by_id(partner_id, revision_id) if revision_id else None
    if revision is None:
        revision = await _get_latest_revision(partner_id, doc_id)
    if revision is None:
        return _error_response("NOT_FOUND", "No published snapshot for this document", 404, request=request)

    try:
        from google.cloud.exceptions import NotFound as GcsNotFound  # type: ignore[import-untyped]
        from zenos.infrastructure.gcs_client import download_blob

        raw, content_type = download_blob(
            revision["snapshot_bucket"],
            revision["snapshot_object_path"],
        )
        content = raw.decode("utf-8")
    except GcsNotFound:
        return _error_response("NOT_FOUND", "Snapshot object not found", 404, request=request)
    except Exception:
        logger.exception("Failed to read shared snapshot for doc %s", doc_id)
        return _error_response("INTERNAL_ERROR", "Failed to load shared document", 500, request=request)

    await _increment_share_token_usage(token_row["token_id"], partner_id)

    return _json_response(
        {
            "doc": {
                "id": doc_id,
                "name": token_row.get("doc_name") or doc_id,
            },
            "revision_id": revision["id"],
            "content_type": content_type,
            "content": content,
        },
        request=request,
    )


# ──────────────────────────────────────────────
# Route table
# ──────────────────────────────────────────────

dashboard_routes = [
    Route("/api/partner/me", get_partner_me, methods=["GET", "OPTIONS"]),
    Route("/api/partner/preferences", get_partner_preferences, methods=["GET", "OPTIONS"]),
    Route("/api/partner/preferences", update_partner_preferences, methods=["PATCH", "OPTIONS"]),
    Route("/api/data/entities", list_entities, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}/children", get_entity_children, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}/relationships", get_entity_relationships, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}", get_entity, methods=["GET", "OPTIONS"]),
    Route("/api/data/relationships", list_relationships, methods=["GET", "OPTIONS"]),
    Route("/api/data/blindspots", list_blindspots, methods=["GET", "OPTIONS"]),
    Route("/api/data/quality-signals", get_quality_signals, methods=["GET", "OPTIONS"]),
    Route("/api/data/governance-health", get_governance_health, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/by-entity/{entityId}", list_tasks_by_entity, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/comments/{commentId}", delete_comment, methods=["DELETE", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/comments", create_comment, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/comments", list_comments, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/confirm", confirm_task, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/attachments/{attachmentId}", delete_task_attachment, methods=["DELETE", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/attachments", upload_task_attachment, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}", update_task, methods=["PATCH", "OPTIONS"]),
    Route("/api/data/tasks", list_tasks, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks", create_task, methods=["POST", "OPTIONS"]),
    Route("/attachments/{attachment_id}", get_attachment, methods=["GET", "OPTIONS"]),
    Route("/api/docs/{docId}/publish", publish_document_snapshot, methods=["POST", "OPTIONS"]),
    Route("/api/docs/{docId}", get_document_delivery, methods=["GET", "OPTIONS"]),
    Route("/api/docs/{docId}/content", get_document_content, methods=["GET", "OPTIONS"]),
    Route("/api/docs/{docId}/access", update_document_access, methods=["PATCH", "OPTIONS"]),
    Route("/api/docs/{docId}/share-links", create_document_share_link, methods=["POST", "OPTIONS"]),
    Route("/api/docs/share-links/{tokenId}", revoke_document_share_link, methods=["DELETE", "OPTIONS"]),
    Route("/s/{token}", access_document_share_link, methods=["GET", "OPTIONS"]),
]
