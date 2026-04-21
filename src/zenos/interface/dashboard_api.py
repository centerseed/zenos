"""Dashboard REST API — Firebase ID token auth for data access endpoints.

Endpoints:
  GET    /api/partner/me                                  — current partner info
  GET    /api/data/entities                               — list entities
  GET    /api/data/entities/{id}                          — get single entity
  GET    /api/data/entities/{id}/children                 — get child entities
  GET    /api/data/entities/{id}/relationships            — get entity relationships
  GET    /api/data/relationships                          — list all relationships
  GET    /api/data/blindspots                             — list blindspots
  GET    /api/data/plans                                  — list plans / plan details
  GET    /api/data/tasks                                  — list tasks
  POST   /api/data/tasks                                  — create task
  GET    /api/data/tasks/by-entity/{entityId}             — tasks by entity
  GET    /api/data/projects/{id}/progress                 — project progress aggregate
  PATCH  /api/data/tasks/{taskId}                         — update task fields
  POST   /api/data/tasks/{taskId}/confirm                 — approve or reject task
  POST   /api/data/tasks/{taskId}/attachments             — upload attachment (returns signed URL)
  DELETE /api/data/tasks/{taskId}/attachments/{attachmentId} — delete attachment
  GET    /attachments/{attachment_id}                     — proxy-stream attachment file
  POST   /api/docs/{docId}/publish                        — publish latest source as snapshot revision
  POST   /api/docs/{docId}/content                        — write markdown directly as snapshot revision
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
import json
import hashlib
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from zenos.application.action.plan_service import PlanService
from zenos.application.action.task_service import TaskService
from zenos.application.knowledge.governance_service import GovernanceService
from zenos.application.knowledge.ontology_service import OntologyService, _collect_subtree_ids
from zenos.application.knowledge.source_service import SourceService
from zenos.domain.governance import compute_search_unused_signals, score_summary_quality
from zenos.domain.action import Task
from zenos.domain.knowledge import Blindspot, Entity, EntityType, Relationship, SourceType, Tags
from zenos.application.identity.workspace_context import (
    active_partner_view,
    build_available_workspaces,
    resolve_active_workspace_id,
)
from zenos.application.identity.source_access_policy import (
    filter_sources_for_partner,
)
from zenos.domain.partner_access import (
    describe_partner_access,
    is_guest,
    is_unassigned_partner,
)
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.unit_of_work import UnitOfWork
from zenos.infrastructure.action import PostgresTaskCommentRepository, SqlPlanRepository, SqlTaskRepository
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

_GRAPH_CONTEXT_ALLOWED_STATUSES = {"active", "approved", "current"}
_GRAPH_CONTEXT_DEFAULT_BUDGET = 1500
_GRAPH_CONTEXT_MAX_L2 = 10
_GRAPH_CONTEXT_MAX_DOCS_PER_L2 = 3
_GRAPH_CONTEXT_MAX_DOCS_TOTAL = 20
_GRAPH_CONTEXT_MAX_DOC_SUMMARY = 500
_GRAPH_CONTEXT_REDUCED_DOC_SUMMARY = 180
_GRAPH_CONTEXT_REDUCED_ENTITY_SUMMARY = 180
_GRAPH_CONTEXT_MIN_ENTITY_SUMMARY = 48
_PROJECT_PROGRESS_RECENT_LIMIT = 8


class RevisionConflictError(RuntimeError):
    """Raised when a direct document write is based on a stale revision."""

    def __init__(
        self,
        *,
        current_revision_id: str | None,
        canonical_path: str | None,
        last_published_at: datetime | None,
    ) -> None:
        super().__init__("Document revision conflict")
        self.current_revision_id = current_revision_id
        self.canonical_path = canonical_path
        self.last_published_at = last_published_at


# ──────────────────────────────────────────────
# Repository cache (lazy-init with shared pool)
# ──────────────────────────────────────────────

_repos_ready = False
_entity_repo: SqlEntityRepository | None = None
_relationship_repo: SqlRelationshipRepository | None = None
_blindspot_repo: SqlBlindspotRepository | None = None
_task_repo: SqlTaskRepository | None = None
_plan_repo: SqlPlanRepository | None = None
_partner_repo: SqlPartnerRepository | None = None
_tool_event_repo: SqlToolEventRepository | None = None
_comment_repo: PostgresTaskCommentRepository | None = None


async def _ensure_repos() -> None:
    global _repos_ready, _entity_repo, _relationship_repo, _blindspot_repo, _task_repo, _plan_repo, _partner_repo, _tool_event_repo, _comment_repo
    if _repos_ready:
        return
    pool = await get_pool()
    _entity_repo = SqlEntityRepository(pool)
    _relationship_repo = SqlRelationshipRepository(pool)
    _blindspot_repo = SqlBlindspotRepository(pool)
    _task_repo = SqlTaskRepository(pool)
    _plan_repo = SqlPlanRepository(pool)
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


async def _list_children_with_context(
    effective_id: str,
    entity_id: str,
) -> list[Entity]:
    token = current_partner_id.set(effective_id)
    try:
        return await _entity_repo.list_by_parent(entity_id)
    finally:
        current_partner_id.reset(token)


async def _list_relationships_with_context(
    effective_id: str,
    entity_id: str,
) -> list[Relationship]:
    token = current_partner_id.set(effective_id)
    try:
        return await _relationship_repo.list_by_entity(entity_id)
    finally:
        current_partner_id.reset(token)


def _graph_context_status_ok(entity: Entity | None) -> bool:
    return bool(entity and str(entity.status or "").lower() in _GRAPH_CONTEXT_ALLOWED_STATUSES)


def _graph_context_is_visible(entity: Entity, partner: dict) -> bool:
    if is_guest(partner):
        return entity.visibility == "public"
    return OntologyService.is_entity_visible_for_partner(entity, partner)


def _graph_context_tags(entity: Entity) -> dict:
    what = entity.tags.what if isinstance(entity.tags.what, list) else [entity.tags.what] if entity.tags.what else []
    who = entity.tags.who if isinstance(entity.tags.who, list) else [entity.tags.who] if entity.tags.who else []
    return {
        "what": [str(item).strip() for item in what if str(item).strip()],
        "why": str(entity.tags.why or "").strip(),
        "how": str(entity.tags.how or "").strip(),
        "who": [str(item).strip() for item in who if str(item).strip()],
    }


def _truncate_graph_context_summary(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 1)].rstrip()}…"


def _estimate_graph_context_tokens(payload: dict) -> int:
    return max(1, math.ceil(len(json.dumps(payload, ensure_ascii=False)) / 4))


def _graph_context_entity_payload(entity: Entity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "type": entity.type,
        "level": entity.level,
        "status": entity.status,
        "summary": entity.summary or "",
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "tags": _graph_context_tags(entity),
    }


def _graph_context_doc_payload(entity: Entity) -> dict:
    details = entity.details if isinstance(entity.details, dict) else {}
    doc_type = (
        details.get("type")
        or details.get("doc_type")
        or details.get("document_type")
        or entity.type
    )
    return {
        "id": entity.id,
        "doc_id": entity.id,
        "title": entity.name,
        "type": str(doc_type or "document"),
        "status": entity.status,
        "summary": _truncate_graph_context_summary(entity.summary or "", _GRAPH_CONTEXT_MAX_DOC_SUMMARY),
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


def _apply_graph_context_budget(response: dict, budget_tokens: int) -> dict:
    if budget_tokens <= 0:
        budget_tokens = _GRAPH_CONTEXT_DEFAULT_BUDGET

    working = json.loads(json.dumps(response))
    truncation_details = {
        "dropped_l2": 0,
        "dropped_l3": 0,
        "summary_truncated": 0,
    }

    def _refresh() -> int:
        estimate = _estimate_graph_context_tokens(working)
        working["estimated_tokens"] = estimate
        return estimate

    estimated = _refresh()
    if estimated <= budget_tokens:
        working["truncated"] = False
        working["truncation_details"] = truncation_details
        return working

    seed_summary = str(working.get("seed", {}).get("summary") or "")
    reduced_seed_summary = _truncate_graph_context_summary(seed_summary, _GRAPH_CONTEXT_REDUCED_ENTITY_SUMMARY)
    if reduced_seed_summary != seed_summary:
        working["seed"]["summary"] = reduced_seed_summary
        truncation_details["summary_truncated"] += 1

    for neighbor in working.get("neighbors", []):
        summary = str(neighbor.get("summary") or "")
        reduced = _truncate_graph_context_summary(summary, _GRAPH_CONTEXT_REDUCED_ENTITY_SUMMARY)
        if reduced != summary:
            neighbor["summary"] = reduced
            truncation_details["summary_truncated"] += 1

    for neighbor in working.get("neighbors", []):
        for doc in neighbor.get("documents", []):
            summary = str(doc.get("summary") or "")
            reduced = _truncate_graph_context_summary(summary, _GRAPH_CONTEXT_REDUCED_DOC_SUMMARY)
            if reduced != summary:
                doc["summary"] = reduced
                truncation_details["summary_truncated"] += 1
    estimated = _refresh()

    if estimated > budget_tokens:
        for neighbor in working.get("neighbors", []):
            for doc in neighbor.get("documents", []):
                if doc.get("summary"):
                    doc["summary"] = ""
                    truncation_details["summary_truncated"] += 1
        estimated = _refresh()

    if estimated > budget_tokens:
        for neighbor in reversed(working.get("neighbors", [])):
            while neighbor.get("documents") and estimated > budget_tokens:
                neighbor["documents"].pop()
                truncation_details["dropped_l3"] += 1
                estimated = _refresh()
            if estimated <= budget_tokens:
                break

    if estimated > budget_tokens:
        for neighbor in working.get("neighbors", []):
            summary = str(neighbor.get("summary") or "")
            reduced = _truncate_graph_context_summary(summary, _GRAPH_CONTEXT_MIN_ENTITY_SUMMARY)
            if reduced != summary:
                neighbor["summary"] = reduced
                truncation_details["summary_truncated"] += 1
        estimated = _refresh()

    if estimated > budget_tokens:
        while working.get("neighbors") and estimated > budget_tokens:
            removed = working["neighbors"].pop()
            truncation_details["dropped_l2"] += 1
            truncation_details["dropped_l3"] += len(removed.get("documents", []))
            estimated = _refresh()

    if estimated > budget_tokens:
        summary = str(working.get("seed", {}).get("summary") or "")
        reduced = _truncate_graph_context_summary(summary, _GRAPH_CONTEXT_MIN_ENTITY_SUMMARY)
        if reduced != summary:
            working["seed"]["summary"] = reduced
            truncation_details["summary_truncated"] += 1
            estimated = _refresh()

    if estimated > budget_tokens and working.get("seed", {}).get("summary"):
        working["seed"]["summary"] = ""
        truncation_details["summary_truncated"] += 1
        estimated = _refresh()

    working["truncated"] = any(truncation_details.values())
    working["truncation_details"] = truncation_details
    working["estimated_tokens"] = min(estimated, budget_tokens)
    return working


async def _resolve_graph_context_neighbors(
    partner: dict,
    effective_id: str,
    seed: Entity,
) -> tuple[list[Entity], list[str]]:
    errors: list[str] = []
    neighbors: list[Entity] = []
    seen_ids: set[str] = set()

    try:
        direct_children = await _list_children_with_context(effective_id, seed.id)
    except Exception as exc:
        errors.append(f"list children failed: {exc}")
        direct_children = []

    for child in direct_children:
        if (
            child.id
            and child.type != "document"
            and child.level == 2
            and _graph_context_status_ok(child)
            and _graph_context_is_visible(child, partner)
            and child.id not in seen_ids
        ):
            seen_ids.add(child.id)
            neighbors.append(child)

    try:
        relationships = await _list_relationships_with_context(effective_id, seed.id)
    except Exception as exc:
        errors.append(f"list relationships failed: {exc}")
        relationships = []

    for rel in relationships:
        other_id = rel.target_id if rel.source_entity_id == seed.id else rel.source_entity_id
        if not other_id or other_id in seen_ids:
            continue
        candidate = await _get_entity_by_id_with_context(effective_id, other_id)
        if not candidate or not _graph_context_is_visible(candidate, partner):
            continue
        if candidate.level == 2 and candidate.type != "document" and _graph_context_status_ok(candidate):
            seen_ids.add(candidate.id)
            neighbors.append(candidate)
            continue
        if candidate.level == 1 and _graph_context_status_ok(candidate):
            try:
                grand_children = await _list_children_with_context(effective_id, candidate.id)
            except Exception as exc:
                errors.append(f"list related children failed: {exc}")
                continue
            for grand_child in grand_children:
                if (
                    grand_child.id
                    and grand_child.type != "document"
                    and grand_child.level == 2
                    and _graph_context_status_ok(grand_child)
                    and _graph_context_is_visible(grand_child, partner)
                    and grand_child.id not in seen_ids
                ):
                    seen_ids.add(grand_child.id)
                    neighbors.append(grand_child)

    neighbors.sort(key=lambda item: item.updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return neighbors[:_GRAPH_CONTEXT_MAX_L2], errors


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


async def _publish_document_snapshot_internal(
    *,
    effective_id: str,
    doc_id: str,
    doc_entity: Entity | None = None,
) -> dict:
    """Publish a GitHub-backed document into a private snapshot revision."""
    await _ensure_repos()
    if doc_entity is None:
        token = current_partner_id.set(effective_id)
        try:
            doc_entity = await _entity_repo.get_by_id(doc_id)
        finally:
            current_partner_id.reset(token)

    if not doc_entity or doc_entity.type != EntityType.DOCUMENT:
        raise ValueError(f"Document '{doc_id}' not found")

    source = _select_publish_source(doc_entity.sources or [])
    if not source:
        raise ValueError("Document has no source to publish")

    source_uri = str(source.get("uri", "")).strip()
    source_type = str(source.get("type", "")).strip()
    source_id = source.get("source_id")
    if not source_uri:
        raise ValueError("Selected source has empty URI")
    if source_type != SourceType.GITHUB:
        raise RuntimeError(f"Source type '{source_type}' is not yet publishable in Phase 1")

    source_service = SourceService(entity_repo=_entity_repo, source_adapter=GitHubAdapter())
    token = current_partner_id.set(effective_id)
    try:
        content = await source_service.read_source(doc_id, source_uri=source_uri)
    finally:
        current_partner_id.reset(token)

    from zenos.infrastructure.gcs_client import get_documents_bucket, upload_blob

    revision_id = uuid.uuid4().hex
    snapshot_path = f"docs/{doc_id}/revisions/{revision_id}.md"
    bucket = get_documents_bucket()
    payload = content.encode("utf-8")
    upload_blob(bucket, snapshot_path, payload, "text/markdown; charset=utf-8")
    content_hash = hashlib.sha256(payload).hexdigest()

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
    return {
        "doc_id": doc_id,
        "canonical_path": f"/docs/{doc_id}",
        "revision_id": stored_revision_id,
        "delivery_status": "ready",
        "source_id": source_id,
        "source_uri": source_uri,
    }


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
    expected_base_revision_id: str | None = None,
) -> str:
    revision_id = uuid.uuid4().hex
    canonical_path = f"/docs/{doc_id}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if expected_base_revision_id is not None:
                row = await conn.fetchrow(
                    f"""
                    SELECT primary_snapshot_revision_id, canonical_path, last_published_at
                    FROM {SCHEMA}.entities
                    WHERE partner_id = $1 AND id = $2
                    FOR UPDATE
                    """,
                    partner_id,
                    doc_id,
                )
                current_primary = row["primary_snapshot_revision_id"] if row else None
                if current_primary != expected_base_revision_id:
                    raise RevisionConflictError(
                        current_revision_id=current_primary,
                        canonical_path=row["canonical_path"] if row else canonical_path,
                        last_published_at=row["last_published_at"] if row else None,
                    )
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
    - Guest: task must have at least one linked entity in allowed_ids and that
      linked entity must itself be visible to the guest.
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
            # Guest: requires at least one linked entity in scope and visible.
            if not linked:
                return False
            if allowed_ids is None:
                return False
            for eid in linked:
                if isinstance(eid, dict):
                    eid = eid.get("id", "")
                if not eid or eid not in allowed_ids:
                    continue
                entity = await _get_entity_by_id_with_context(effective_id, eid)
                if entity and OntologyService.is_entity_visible_for_partner(entity, partner):
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
        logger.warning("_is_task_visible_for_partner failed, denying access", exc_info=True)
        return False


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
        logger.warning("_is_blindspot_visible_for_partner failed, denying access", exc_info=True)
        return False


# ──────────────────────────────────────────────
# Serialization helpers
# ──────────────────────────────────────────────


def _entity_to_dict(e: Entity, partner: dict | None = None) -> dict:
    visible_sources = filter_sources_for_partner(e.sources, partner)
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
        "sources": visible_sources,
        "visibility": e.visibility,
        "visibleToRoles": e.visible_to_roles,
        "visibleToMembers": e.visible_to_members,
        "visibleToDepartments": e.visible_to_departments,
        "lastReviewedAt": e.last_reviewed_at,
        "createdAt": e.created_at,
        "updatedAt": e.updated_at,
        # ADR-022 Document Bundle fields
        "docRole": e.doc_role,
        "bundleHighlights": e.bundle_highlights,
        "highlightsUpdatedAt": e.highlights_updated_at,
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
        "dispatcher": t.dispatcher,
        "parentTaskId": t.parent_task_id,
        "handoffEvents": [
            {
                "at": h.at,
                "fromDispatcher": h.from_dispatcher,
                "toDispatcher": h.to_dispatcher,
                "reason": h.reason,
                "outputRef": h.output_ref,
                "notes": h.notes,
            }
            for h in (t.handoff_events or [])
        ],
        "attachments": _attachments_with_proxy_url(t.attachments),
        "createdAt": t.created_at,
        "updatedAt": t.updated_at,
        "completedAt": t.completed_at,
    }


def _progress_task_status(status: str | None) -> str:
    return {
        "backlog": "todo",
        "archived": "done",
    }.get(status or "", status or "")


def _progress_task_is_open(status: str | None) -> bool:
    return _progress_task_status(status) in {"todo", "blocked", "in_progress", "review"}


def _progress_task_is_blocked(task: Task) -> bool:
    status = _progress_task_status(task.status)
    return status == "blocked" or bool(task.blocked_by)


def _progress_task_is_review(task: Task) -> bool:
    return _progress_task_status(task.status) == "review"


def _progress_task_is_overdue(task: Task, now: datetime) -> bool:
    if not task.due_date or not _progress_task_is_open(task.status):
        return False
    due_date = task.due_date
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
    return due_date < now


def _progress_task_sort_key(task: Task, now: datetime) -> tuple[int, float, float]:
    rank = 4
    if _progress_task_is_blocked(task):
        rank = 0
    elif _progress_task_is_review(task):
        rank = 1
    elif _progress_task_is_overdue(task, now):
        rank = 2
    elif _progress_task_status(task.status) == "in_progress":
        rank = 3
    updated_ts = task.updated_at.timestamp() if task.updated_at else 0.0
    created_ts = task.created_at.timestamp() if task.created_at else 0.0
    return (rank, -updated_ts, -created_ts)


def _build_progress_task_summary(
    task: Task,
    now: datetime,
    subtasks: list[dict] | None = None,
) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "status": _progress_task_status(task.status),
        "priority": task.priority,
        "assignee_name": task.assignee_name,
        "due_date": task.due_date,
        "overdue": _progress_task_is_overdue(task, now),
        "blocked": _progress_task_is_blocked(task),
        "blocked_reason": task.blocked_reason,
        "parent_task_id": task.parent_task_id,
        "updated_at": task.updated_at,
        "subtasks": subtasks or [],
    }


def _build_progress_task_tree(tasks: list[Task], now: datetime) -> list[dict]:
    subtasks_by_parent: dict[str, list[Task]] = {}
    top_level: list[Task] = []
    task_ids = {task.id for task in tasks if task.id}
    for task in tasks:
        if task.parent_task_id and task.parent_task_id in task_ids:
            subtasks_by_parent.setdefault(task.parent_task_id, []).append(task)
        else:
            top_level.append(task)

    def render(task: Task) -> dict:
        children = sorted(
            subtasks_by_parent.get(task.id or "", []),
            key=lambda item: _progress_task_sort_key(item, now),
        )
        return _build_progress_task_summary(
            task,
            now,
            subtasks=[render(child) for child in children],
        )

    ordered_top_level = sorted(top_level, key=lambda item: _progress_task_sort_key(item, now))
    return [render(task) for task in ordered_top_level]


def _count_progress_tasks(tasks: list[Task], now: datetime) -> dict[str, int]:
    return {
        "open_count": sum(1 for task in tasks if _progress_task_is_open(task.status)),
        "blocked_count": sum(1 for task in tasks if _progress_task_is_blocked(task)),
        "review_count": sum(1 for task in tasks if _progress_task_is_review(task)),
        "overdue_count": sum(1 for task in tasks if _progress_task_is_overdue(task, now)),
    }


def _recent_progress_item_sort_key(item: dict) -> float:
    updated_at = item.get("updated_at")
    if isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            updated_at = None
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return updated_at.timestamp()
    return float("-inf")


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


async def google_workspace_connector_health(request: Request) -> Response:
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
    override: dict = {}
    if body:
        try:
            parsed = _json.loads(body)
        except (ValueError, TypeError):
            return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
        if not isinstance(parsed, dict):
            return _error_response("INVALID_INPUT", "Body must be a JSON object", 400, request=request)
        override = parsed

    active_workspace_id = resolve_active_workspace_id(
        raw_partner,
        _requested_active_workspace_id(request),
    )
    partner, _ = active_partner_view(raw_partner, active_workspace_id)
    partner["activeWorkspaceId"] = active_workspace_id
    partner["homeWorkspaceId"] = raw_partner["id"]
    partner["isHomeWorkspace"] = active_workspace_id == str(raw_partner["id"])

    source_service = SourceService(entity_repo=_entity_repo, source_adapter=None)
    result = await source_service.check_google_workspace_connector_health(partner, override_config=override)
    return _json_response(result, request=request)


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

    return _json_response({"entities": [_entity_to_dict(e, partner) for e in entities]}, request=request)


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
            "entity": _entity_to_dict(entity, partner),
            "impact_chain": impact_chain,
            "reverse_impact_chain": reverse_impact_chain,
        },
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: GET /api/cowork/graph-context
# ──────────────────────────────────────────────


async def get_cowork_graph_context(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("NOT_FOUND", "seed entity not found", 404, request=request)

    seed_id = str(request.query_params.get("seed_id") or "").strip()
    if not seed_id:
        return _error_response("INVALID_INPUT", "seed_id is required", 400, request=request)

    try:
        budget_tokens = int(request.query_params.get("budget_tokens") or _GRAPH_CONTEXT_DEFAULT_BUDGET)
    except ValueError:
        return _error_response("INVALID_INPUT", "budget_tokens must be an integer", 400, request=request)
    include_docs = str(request.query_params.get("include_docs") or "true").strip().lower() != "false"

    await _ensure_repos()
    seed = await _get_entity_by_id_with_context(effective_id, seed_id)
    if not seed or not _graph_context_is_visible(seed, partner):
        return _error_response("NOT_FOUND", f"Entity {seed_id} not found", 404, request=request)

    neighbors, errors = await _resolve_graph_context_neighbors(partner, effective_id, seed)
    l3_total = 0
    neighbor_payloads: list[dict] = []

    for neighbor in neighbors:
        documents: list[dict] = []
        if include_docs and l3_total < _GRAPH_CONTEXT_MAX_DOCS_TOTAL:
            try:
                children = await _list_children_with_context(effective_id, neighbor.id)
            except Exception as exc:
                errors.append(f"list documents failed for {neighbor.id}: {exc}")
                children = []

            docs = [
                child for child in children
                if child.type == "document"
                and _graph_context_status_ok(child)
                and _graph_context_is_visible(child, partner)
            ]
            docs.sort(key=lambda item: item.updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            remaining = max(0, _GRAPH_CONTEXT_MAX_DOCS_TOTAL - l3_total)
            selected_docs = docs[: min(_GRAPH_CONTEXT_MAX_DOCS_PER_L2, remaining)]
            documents = [_graph_context_doc_payload(doc) for doc in selected_docs]
            l3_total += len(documents)

        payload = _graph_context_entity_payload(neighbor)
        payload["distance"] = 1
        payload["documents"] = documents
        neighbor_payloads.append(payload)

    fallback_mode = "normal"
    if seed.level == 1 and (len(neighbor_payloads) <= 1 or (include_docs and bool(errors))):
        fallback_mode = "l1_tags_only"

    response = {
        "seed": _graph_context_entity_payload(seed),
        "fallback_mode": fallback_mode,
        "neighbors": neighbor_payloads,
        "partial": bool(errors),
        "errors": errors,
        "truncated": False,
        "truncation_details": {
            "dropped_l2": 0,
            "dropped_l3": 0,
            "summary_truncated": 0,
        },
        "estimated_tokens": 0,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    if response["fallback_mode"] == "l1_tags_only":
        response["neighbors"] = neighbor_payloads[:1]

    response = _apply_graph_context_budget(response, budget_tokens)
    return _json_response(response, request=request)


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
        {"entities": [_entity_to_dict(e, partner) for e in children], "count": len(children)},
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
# Endpoint: GET /api/data/plans
# ──────────────────────────────────────────────


def _plan_payload_to_dict(plan: object) -> dict[str, object]:
    created_at = getattr(plan, "created_at", None)
    updated_at = getattr(plan, "updated_at", None)
    return {
        "id": getattr(plan, "id", None),
        "goal": getattr(plan, "goal", None),
        "status": getattr(plan, "status", None),
        "owner": getattr(plan, "owner", None),
        "entry_criteria": getattr(plan, "entry_criteria", None),
        "exit_criteria": getattr(plan, "exit_criteria", None),
        "project": getattr(plan, "project", None),
        "project_id": getattr(plan, "project_id", None),
        "created_by": getattr(plan, "created_by", None),
        "updated_by": getattr(plan, "updated_by", None),
        "result": getattr(plan, "result", None),
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


async def list_plans(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    await _ensure_repos()
    if is_unassigned_partner(partner):
        return _json_response({"plans": []}, request=request)

    ids = [plan_id.strip() for plan_id in request.query_params.getlist("id") if plan_id.strip()]
    deduped_ids = list(dict.fromkeys(ids))

    token = current_partner_id.set(effective_id)
    try:
        plan_service = PlanService(_plan_repo, _task_repo)
        if deduped_ids:
            plans: list[dict[str, object]] = []
            for plan_id in deduped_ids:
                try:
                    plans.append(await plan_service.get_plan(plan_id))
                except ValueError:
                    continue
        else:
            listed = await plan_service.list_plans(limit=200)
            plans = [_plan_payload_to_dict(plan) for plan in listed]
    finally:
        current_partner_id.reset(token)

    return _json_response({"plans": plans}, request=request)


# ──────────────────────────────────────────────
# Endpoint: GET /api/data/projects/{id}/progress
# ──────────────────────────────────────────────


async def get_project_progress(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    project_id = request.path_params.get("id")
    if not project_id:
        return _error_response("INVALID_INPUT", "Project id is required", 400, request=request)

    await _ensure_repos()
    if is_unassigned_partner(partner):
        return _error_response("NOT_FOUND", "Project not found", 404, request=request)

    allowed_ids: set[str] | None = None
    entity_cache: dict[str, Entity] = {}
    if is_guest(partner):
        all_entities = await _list_all_entities_with_context(effective_id)
        entity_cache = {entity.id: entity for entity in all_entities if entity.id}
        allowed_ids = _build_allowed_entity_ids(partner, entity_cache)
        if project_id not in allowed_ids:
            return _error_response("NOT_FOUND", "Project not found", 404, request=request)

    project = entity_cache.get(project_id) or await _get_entity_by_id_with_context(effective_id, project_id)
    if not project or not OntologyService.is_entity_visible_for_partner(project, partner):
        return _error_response("NOT_FOUND", "Project not found", 404, request=request)

    token = current_partner_id.set(effective_id)
    try:
        linked_tasks = await _task_repo.list_all(linked_entity=project_id, limit=500)
        plan_service = PlanService(_plan_repo, _task_repo)
        plan_ids = sorted({task.plan_id for task in linked_tasks if task.plan_id})
        plan_payloads: dict[str, dict] = {}
        for plan_id in plan_ids:
            try:
                plan_payloads[plan_id] = await plan_service.get_plan(plan_id)
            except ValueError:
                continue
    finally:
        current_partner_id.reset(token)

    visible_tasks = [
        task
        for task in linked_tasks
        if await _is_task_visible_for_partner(task, partner, effective_id, allowed_ids=allowed_ids)
    ]

    now = datetime.now(timezone.utc)
    tasks_by_plan: dict[str | None, list[Task]] = {}
    visible_linked_entity_ids = {
        entity_id
        for task in visible_tasks
        for entity_id in (task.linked_entities or [])
        if entity_id and isinstance(entity_id, str)
    }
    for entity_id in visible_linked_entity_ids:
        if entity_id in entity_cache:
            continue
        entity = await _get_entity_by_id_with_context(effective_id, entity_id)
        if entity:
            entity_cache[entity_id] = entity

    for task in visible_tasks:
        tasks_by_plan.setdefault(task.plan_id, []).append(task)

    active_plans: list[dict] = []
    open_work_groups: list[dict] = []
    for plan_id, plan_tasks in tasks_by_plan.items():
        plan_payload = plan_payloads.get(plan_id or "")
        plan_goal = plan_payload["goal"] if plan_payload else None
        plan_status = plan_payload["status"] if plan_payload else None
        open_tasks = [task for task in plan_tasks if _progress_task_is_open(task.status)]
        counts = _count_progress_tasks(open_tasks, now)
        if counts["open_count"] > 0:
            task_tree = _build_progress_task_tree(open_tasks, now)
            open_work_groups.append({
                "plan_id": plan_id,
                "plan_goal": plan_goal,
                "plan_status": plan_status,
                **counts,
                "tasks": task_tree,
            })

        if plan_payload and plan_status == "active":
            top_level_tasks = [
                task for task in open_tasks
                if not task.parent_task_id or task.parent_task_id not in {candidate.id for candidate in open_tasks if candidate.id}
            ]
            next_tasks = [
                _build_progress_task_summary(task, now)
                for task in sorted(top_level_tasks, key=lambda item: _progress_task_sort_key(item, now))[:3]
            ]
            active_plans.append({
                "id": plan_payload["id"],
                "goal": plan_payload["goal"],
                "status": plan_payload["status"],
                "owner": plan_payload["owner"],
                "tasks_summary": plan_payload.get("tasks_summary", {}),
                **counts,
                "updated_at": plan_payload["updated_at"],
                "next_tasks": next_tasks,
            })

    active_plans.sort(
        key=lambda item: (
            0 if item["blocked_count"] > 0 else 1,
            -_recent_progress_item_sort_key({"updated_at": item["updated_at"]}),
            item["goal"] or "",
        )
    )
    open_work_groups.sort(
        key=lambda item: (
            0 if item["blocked_count"] > 0 else 1,
            -item["open_count"],
            item["plan_goal"] or "",
        )
    )

    milestone_counts: dict[str, dict] = {}
    for task in visible_tasks:
        if not _progress_task_is_open(task.status):
            continue
        for entity_id in task.linked_entities or []:
            if not isinstance(entity_id, str) or entity_id == project_id:
                continue
            if is_guest(partner) and allowed_ids is not None and entity_id not in allowed_ids:
                continue
            entity = entity_cache.get(entity_id)
            if not entity or entity.type != EntityType.GOAL.value:
                continue
            if not OntologyService.is_entity_visible_for_partner(entity, partner):
                continue
            current = milestone_counts.setdefault(entity_id, {
                "id": entity.id,
                "name": entity.name,
                "open_count": 0,
            })
            current["open_count"] += 1

    recent_progress: list[dict] = []
    for task in sorted(visible_tasks, key=lambda item: _recent_progress_item_sort_key({"updated_at": item.updated_at}), reverse=True):
        recent_progress.append({
            "id": task.id,
            "kind": "task",
            "title": task.title,
            "subtitle": f"Task · {_progress_task_status(task.status)}",
            "updated_at": task.updated_at,
        })
    for plan_payload in plan_payloads.values():
        recent_progress.append({
            "id": plan_payload["id"],
            "kind": "plan",
            "title": plan_payload["goal"],
            "subtitle": f"Plan · {plan_payload['status']}",
            "updated_at": plan_payload["updated_at"],
        })
    recent_progress.sort(key=_recent_progress_item_sort_key, reverse=True)

    return _json_response(
        {
            "project": _entity_to_dict(project, partner),
            "active_plans": active_plans,
            "open_work_groups": open_work_groups,
            "milestones": sorted(
                milestone_counts.values(),
                key=lambda item: (-item["open_count"], item["name"]),
            ),
            "recent_progress": recent_progress[:_PROJECT_PROGRESS_RECENT_LIMIT],
        },
        request=request,
    )


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
    for _field in (
        "description",
        "priority",
        "assignee",
        "due_date",
        "project",
        "linked_entities",
        "acceptance_criteria",
        "assignee_role_id",
        "linked_protocol",
        "linked_blindspot",
        "blocked_by",
        "blocked_reason",
        "plan_id",
        "plan_order",
        "depends_on_task_ids",
        "parent_task_id",
        "dispatcher",
        "source_metadata",
    ):
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

    allowed_fields = {
        "status",
        "title",
        "description",
        "priority",
        "assignee",
        "due_date",
        "result",
        "acceptance_criteria",
        "assignee_role_id",
        "linked_entities",
        "linked_protocol",
        "linked_blindspot",
        "blocked_by",
        "blocked_reason",
        "plan_id",
        "plan_order",
        "depends_on_task_ids",
        "parent_task_id",
        "dispatcher",
        "source_metadata",
    }
    updates: dict = {k: body[k] for k in body.keys() if k in allowed_fields}

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
# Endpoint: POST /api/data/tasks/{taskId}/handoff
# ──────────────────────────────────────────────


async def handoff_task(request: Request) -> Response:
    """Append a handoff event and move the task's dispatcher.

    Body: { to_dispatcher, reason, output_ref?, notes? }
    """
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

    to_dispatcher = (body.get("to_dispatcher") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not to_dispatcher:
        return _error_response("INVALID_INPUT", "to_dispatcher is required", 400, request=request)
    if not reason:
        return _error_response("INVALID_INPUT", "reason is required", 400, request=request)

    output_ref = body.get("output_ref")
    notes = body.get("notes")

    await _ensure_repos()
    token = current_partner_id.set(effective_id)
    try:
        task_service = _make_task_service()
        result = await task_service.handoff_task(
            task_id,
            to_dispatcher=to_dispatcher,
            reason=reason,
            output_ref=output_ref,
            notes=notes,
            updated_by=effective_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return _error_response("NOT_FOUND", msg, 404, request=request)
        return _error_response("INVALID_INPUT", msg, 400, request=request)
    except Exception:
        logger.exception("Failed to handoff task %s", task_id)
        return _error_response("INTERNAL_ERROR", "Failed to handoff task", 500, request=request)
    finally:
        current_partner_id.reset(token)

    logger.info("Handoff task %s → %s by partner %s", task_id, to_dispatcher, effective_id)
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
# Document Creation Endpoint
# ──────────────────────────────────────────────


async def create_doc(request: Request) -> Response:
    """Create a new native document entity.

    POST /api/docs
    Body: {name: str, doc_role?: "index"|"single", status?: str, product_id?: str}
    Returns: {doc_id, base_revision_id: null, entity}

    Creates a type=document level=3 entity with a primary zenos_native source.
    No document_revisions row is created — the first POST /content with
    base_revision_id=null will create rev-1.
    """
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("FORBIDDEN", "Current workspace cannot create documents", 403, request=request)
    if is_guest(partner):
        return _error_response("FORBIDDEN", "Guest cannot create documents", 403, request=request)

    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Request body must be a JSON object", 400, request=request)

    name = body.get("name")
    if not isinstance(name, str) or not name.strip():
        return _error_response("INVALID_INPUT", "name is required", 400, request=request)
    name = name.strip()

    doc_role = body.get("doc_role", "index")
    if doc_role not in ("index", "single"):
        return _error_response("INVALID_INPUT", "doc_role must be 'index' or 'single'", 400, request=request)

    status = body.get("status", "draft")
    if not isinstance(status, str) or not status.strip():
        status = "draft"
    else:
        status = status.strip()

    product_id = body.get("product_id")
    if product_id is not None:
        product_id = str(product_id).strip() or None

    doc_id = uuid.uuid4().hex
    canonical_path = f"/docs/{doc_id}"
    source_id = uuid.uuid4().hex
    primary_source = {
        "source_id": source_id,
        "type": "zenos_native",
        "uri": canonical_path,
        "is_primary": True,
        "source_status": "valid",
        "label": name,
    }

    entity = Entity(
        id=doc_id,
        name=name,
        type="document",
        level=3,
        status=status,
        summary="",
        tags=Tags(what=[], why="", how="", who=[]),
        sources=[primary_source],
        doc_role=doc_role,
        parent_id=product_id,
        visibility="public",
    )

    await _ensure_repos()
    ctx_token = current_partner_id.set(effective_id)
    try:
        saved_entity = await _entity_repo.upsert(entity)
    finally:
        current_partner_id.reset(ctx_token)

    # Set canonical_path on the entity row (not managed by entity_repo.upsert).
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE {SCHEMA}.entities
            SET canonical_path = $1, updated_at = now()
            WHERE partner_id = $2 AND id = $3
            """,
            canonical_path,
            effective_id,
            doc_id,
        )

    logger.info("Created document entity %s for partner %s", doc_id, effective_id)
    return _json_response(
        {
            "doc_id": doc_id,
            "base_revision_id": None,
            "entity": _entity_to_dict(saved_entity, partner),
        },
        request=request,
    )


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

    try:
        payload = await _publish_document_snapshot_internal(
            effective_id=effective_id,
            doc_id=doc_id,
            doc_entity=doc_entity,
        )
    except FileNotFoundError:
        return _error_response("SOURCE_NOT_FOUND", "Source file not found", 404, request=request)
    except PermissionError:
        return _error_response("SOURCE_FORBIDDEN", "Permission denied while reading source", 403, request=request)
    except ValueError as exc:
        return _error_response("INVALID_INPUT", str(exc), 400, request=request)
    except RuntimeError as exc:
        return _error_response("SOURCE_ERROR", str(exc), 409, request=request)
    except Exception:
        logger.exception("Failed to write document snapshot for %s", doc_id)
        return _error_response("GCS_ERROR", "Failed to write document snapshot", 500, request=request)
    return _json_response(payload, request=request)


async def save_document_content(request: Request) -> Response:
    """Write markdown directly into GCS and publish as latest snapshot revision."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)
    if is_unassigned_partner(partner):
        return _error_response("FORBIDDEN", "Current workspace cannot write document content", 403, request=request)
    if is_guest(partner):
        return _error_response("FORBIDDEN", "Guest cannot write document content", 403, request=request)

    doc_id = request.path_params.get("docId")
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Request body must be a JSON object", 400, request=request)

    content = body.get("content")
    if not isinstance(content, str):
        return _error_response("INVALID_INPUT", "content must be a string", 400, request=request)

    # base_revision_id must be present in the body (key must exist).
    # Acceptable values:
    #   - null / None  → first save (no prior revision); skips conflict check
    #   - non-empty string → existing revision ID; conflict check is enforced
    _SENTINEL = object()
    _raw_base = body.get("base_revision_id", _SENTINEL)
    if _raw_base is _SENTINEL:
        return _error_response(
            "INVALID_INPUT",
            "base_revision_id is required for direct document writes",
            400,
            request=request,
        )
    if _raw_base is None:
        base_revision_id = None  # first-save sentinel: skip conflict check
    elif isinstance(_raw_base, str) and _raw_base.strip():
        base_revision_id = _raw_base.strip()
    else:
        return _error_response(
            "INVALID_INPUT",
            "base_revision_id must be null (first save) or a non-empty revision ID string",
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

    source_id = body.get("source_id")
    if source_id is not None:
        source_id = str(source_id).strip() or None
    source_version_ref = body.get("source_version_ref")
    if source_version_ref is not None:
        source_version_ref = str(source_version_ref).strip() or None
    if source_version_ref is None:
        source_version_ref = "manual"

    try:
        from zenos.infrastructure.gcs_client import get_documents_bucket, upload_blob

        revision_id = uuid.uuid4().hex
        snapshot_path = f"docs/{doc_id}/revisions/{revision_id}.md"
        bucket = get_documents_bucket()
        payload = content.encode("utf-8")
        upload_blob(bucket, snapshot_path, payload, "text/markdown; charset=utf-8")
        content_hash = hashlib.sha256(payload).hexdigest()
    except Exception:
        logger.exception("Failed to write markdown snapshot for %s", doc_id)
        return _error_response("GCS_ERROR", "Failed to write document snapshot", 500, request=request)

    try:
        stored_revision_id = await _create_revision_and_mark_ready(
            partner_id=effective_id,
            doc_id=doc_id,
            source_id=source_id,
            source_version_ref=source_version_ref,
            snapshot_bucket=bucket,
            snapshot_object_path=snapshot_path,
            content_hash=content_hash,
            content_type="text/markdown; charset=utf-8",
            created_by=effective_id,
            expected_base_revision_id=base_revision_id,
        )
    except RevisionConflictError as exc:
        return _json_response(
            {
                "error": "REVISION_CONFLICT",
                "message": "Document has a newer published revision",
                "current_revision_id": exc.current_revision_id,
                "canonical_path": exc.canonical_path or f"/docs/{doc_id}",
                "last_published_at": exc.last_published_at,
            },
            status_code=409,
            request=request,
        )
    except Exception:
        logger.exception("Failed to persist direct markdown revision metadata for %s", doc_id)
        return _error_response("INTERNAL_ERROR", "Failed to persist snapshot revision", 500, request=request)

    return _json_response(
        {
            "doc_id": doc_id,
            "canonical_path": f"/docs/{doc_id}",
            "revision_id": stored_revision_id,
            "delivery_status": "ready",
            "source_id": source_id,
            "source_version_ref": source_version_ref,
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
                "sources": filter_sources_for_partner(doc_entity.sources, partner),
                "doc_role": doc_entity.doc_role or "single",
                "bundle_highlights": doc_entity.bundle_highlights or [],
                "highlights_updated_at": doc_entity.highlights_updated_at,
                "change_summary": doc_entity.change_summary,
                "summary_updated_at": doc_entity.summary_updated_at,
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
    Route("/api/connectors/google-workspace/health", google_workspace_connector_health, methods=["POST", "OPTIONS"]),
    Route("/api/cowork/graph-context", get_cowork_graph_context, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities", list_entities, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}/children", get_entity_children, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}/relationships", get_entity_relationships, methods=["GET", "OPTIONS"]),
    Route("/api/data/entities/{id}", get_entity, methods=["GET", "OPTIONS"]),
    Route("/api/data/relationships", list_relationships, methods=["GET", "OPTIONS"]),
    Route("/api/data/blindspots", list_blindspots, methods=["GET", "OPTIONS"]),
    Route("/api/data/quality-signals", get_quality_signals, methods=["GET", "OPTIONS"]),
    Route("/api/data/governance-health", get_governance_health, methods=["GET", "OPTIONS"]),
    Route("/api/data/plans", list_plans, methods=["GET", "OPTIONS"]),
    Route("/api/data/projects/{id}/progress", get_project_progress, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/by-entity/{entityId}", list_tasks_by_entity, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/comments/{commentId}", delete_comment, methods=["DELETE", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/comments", create_comment, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/comments", list_comments, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/confirm", confirm_task, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/handoff", handoff_task, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/attachments/{attachmentId}", delete_task_attachment, methods=["DELETE", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}/attachments", upload_task_attachment, methods=["POST", "OPTIONS"]),
    Route("/api/data/tasks/{taskId}", update_task, methods=["PATCH", "OPTIONS"]),
    Route("/api/data/tasks", list_tasks, methods=["GET", "OPTIONS"]),
    Route("/api/data/tasks", create_task, methods=["POST", "OPTIONS"]),
    Route("/attachments/{attachment_id}", get_attachment, methods=["GET", "OPTIONS"]),
    Route("/api/docs", create_doc, methods=["POST", "OPTIONS"]),
    Route("/api/docs/{docId}/publish", publish_document_snapshot, methods=["POST", "OPTIONS"]),
    Route("/api/docs/{docId}/content", save_document_content, methods=["POST", "OPTIONS"]),
    Route("/api/docs/{docId}", get_document_delivery, methods=["GET", "OPTIONS"]),
    Route("/api/docs/{docId}/content", get_document_content, methods=["GET", "OPTIONS"]),
    Route("/api/docs/{docId}/access", update_document_access, methods=["PATCH", "OPTIONS"]),
    Route("/api/docs/{docId}/share-links", create_document_share_link, methods=["POST", "OPTIONS"]),
    Route("/api/docs/share-links/{tokenId}", revoke_document_share_link, methods=["DELETE", "OPTIONS"]),
    Route("/s/{token}", access_document_share_link, methods=["GET", "OPTIONS"]),
]
