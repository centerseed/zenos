"""ZenOS MCP Server — 8 consolidated tools for ontology + action layer.

Consolidated from 17 tools to 7, plus governance_guide:
  1. search         — find and list across all collections
  2. get            — retrieve one specific item by name or ID
  3. read_source    — read raw file content via adapter
  4. write          — create/update ontology entries
  5. confirm        — approve knowledge drafts or accept/reject tasks
  6. task           — create, update, and list action items
  7. analyze        — run governance health checks
  8. governance_guide — retrieve governance rules by topic/level (no auth required)

Design principles (from MCP tool description research):
  - Each tool answers ONE agent question ("I want to find...", "I want to write...")
  - Descriptions include Purpose, When to use, When NOT to use, Limitations
  - Cross-references between tools to prevent wrong-tool selection
  - Flat parameters preferred over nested dicts where possible
  - readOnlyHint / idempotentHint annotations for client optimization

Usage:
  MCP_TRANSPORT=stdio  python -m zenos.interface.tools   # default
  MCP_TRANSPORT=sse PORT=8080  python -m zenos.interface.tools
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import json
import uuid
import inspect
from contextvars import ContextVar
from dataclasses import asdict
from datetime import datetime, timezone
from urllib.parse import parse_qs

from dotenv import load_dotenv
from starlette.responses import JSONResponse

try:
    from fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - test fallback when fastmcp is absent
    class FastMCP:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def tool(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

load_dotenv()

logger = logging.getLogger(__name__)

from zenos.application.governance_ai import GovernanceAI
from zenos.domain.governance import (
    compute_search_unused_signals,
    detect_invalid_document_titles,
    score_summary_quality,
)
from zenos.domain.models import EntityEntry
from zenos.application.governance_service import GovernanceService
from zenos.application.ontology_service import OntologyService, _collect_subtree_ids
from zenos.application.source_service import SourceService
from zenos.application.task_service import TaskService
from zenos.infrastructure.llm_client import create_llm_client
from zenos.infrastructure.unit_of_work import UnitOfWork
from zenos.infrastructure.sql_repo import (
    SqlBlindspotRepository,
    SqlDocumentRepository,
    SqlEntityEntryRepository,
    SqlEntityRepository,
    SqlPartnerKeyValidator,
    SqlProtocolRepository,
    SqlRelationshipRepository,
    SqlTaskRepository,
    SqlToolEventRepository,
    SqlUsageLogRepository,
    SqlWorkJournalRepository,
    get_pool,
)
from zenos.infrastructure.github_adapter import GitHubAdapter
from zenos.infrastructure.context import (
    current_partner_department,
    current_partner_id as _current_partner_id,
    current_partner_is_admin,
    current_partner_roles,
)
from zenos.interface.governance_rules import GOVERNANCE_RULES
from zenos.domain.partner_access import describe_partner_access, is_scoped_partner, is_unassigned_partner

# ──────────────────────────────────────────────
# Agent Identity — ContextVar for partner data
# ──────────────────────────────────────────────

_current_partner: ContextVar[dict | None] = ContextVar("current_partner", default=None)

# ──────────────────────────────────────────────
# API Key authentication middleware
# ──────────────────────────────────────────────

# PartnerKeyValidator is now provided by sql_repo.SqlPartnerKeyValidator
PartnerKeyValidator = SqlPartnerKeyValidator


_partner_validator = PartnerKeyValidator()


class ApiKeyMiddleware:
    """Pure ASGI middleware — compatible with SSE streaming.

    Authentication:
    - Validate key against active partners in SQL (partners table).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        key = self._extract_key(scope)
        path = scope.get("path", "")

        # Partner key (SQL)
        if key:
            partner = await _partner_validator.validate(key)
            if partner is not None:
                from zenos.infrastructure.context import (
                    current_partner_id,
                    current_partner_authorized_entity_ids,
                )
                token = _current_partner.set(partner)
                token_pid = current_partner_id.set(partner.get("sharedPartnerId") or partner.get("id", ""))
                token_roles = current_partner_roles.set(list(partner.get("roles") or []))
                token_department = current_partner_department.set(str(partner.get("department") or "all"))
                token_admin = current_partner_is_admin.set(bool(partner.get("isAdmin", False)))
                token_auth_ids = current_partner_authorized_entity_ids.set(
                    list(partner.get("authorizedEntityIds") or [])
                )
                try:
                    return await self.app(scope, receive, send)
                finally:
                    _current_partner.reset(token)
                    current_partner_id.reset(token_pid)
                    current_partner_roles.reset(token_roles)
                    current_partner_department.reset(token_department)
                    current_partner_is_admin.reset(token_admin)
                    current_partner_authorized_entity_ids.reset(token_auth_ids)
            logger.warning(
                "Auth rejected: key=%.8s... path=%s cache_size=%d",
                key, path, len(_partner_validator._cache),
            )
        else:
            logger.debug("Auth rejected: no key provided, path=%s", path)

        response = JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
        return await response(scope, receive, send)

    @staticmethod
    def _extract_key(scope) -> str | None:
        """Extract API key from headers or query param."""
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        x_api_key = headers.get(b"x-api-key", b"").decode()
        if x_api_key:
            return x_api_key

        qs = parse_qs(scope.get("query_string", b"").decode())
        keys = qs.get("api_key", [])
        return keys[0] if keys else None


class SseApiKeyPropagator:
    """Inject api_key into the SSE endpoint event so clients preserve auth.

    FastMCP SSE sends: data: /messages/?session_id=<uuid>
    We patch it to:   data: /messages/?session_id=<uuid>&api_key=<key>

    Only activates when api_key is present in the original query string.
    Header-based auth clients are unaffected (pass-through).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        qs = parse_qs(scope.get("query_string", b"").decode())
        api_key = qs.get("api_key", [None])[0]

        if not api_key:
            return await self.app(scope, receive, send)

        async def patched_send(event):
            if event["type"] == "http.response.body":
                body = event.get("body", b"")
                if body:
                    text = body.decode("utf-8", errors="replace")
                    text = re.sub(
                        r"(data: /messages/\?session_id=[^\s&]+)",
                        lambda m: m.group(0) + f"&api_key={api_key}",
                        text,
                    )
                    event = {**event, "body": text.encode("utf-8")}
            await send(event)

        await self.app(scope, receive, patched_send)


# ──────────────────────────────────────────────
# MCP server instance
# ──────────────────────────────────────────────

mcp = FastMCP("ZenOS Ontology")

# ──────────────────────────────────────────────
# Dependency injection — repositories & services
# ──────────────────────────────────────────────

# Repositories are initialised lazily with the shared asyncpg pool.
# We use a sentinel so module-level code stays sync; actual pool wiring
# happens inside _ensure_repos(), called from each tool handler.
_repos_ready: bool = False
entity_repo: SqlEntityRepository | None = None
relationship_repo: SqlRelationshipRepository | None = None
document_repo: SqlDocumentRepository | None = None
protocol_repo: SqlProtocolRepository | None = None
blindspot_repo: SqlBlindspotRepository | None = None
task_repo: SqlTaskRepository | None = None
entry_repo: SqlEntityEntryRepository | None = None


async def _ensure_repos() -> None:
    """Lazily initialise all SQL repositories on first tool invocation."""
    global _repos_ready, entity_repo, relationship_repo, document_repo
    global protocol_repo, blindspot_repo, task_repo, entry_repo
    if _repos_ready:
        return
    pool = await get_pool()
    entity_repo = SqlEntityRepository(pool)
    relationship_repo = SqlRelationshipRepository(pool)
    document_repo = SqlDocumentRepository(pool)
    protocol_repo = SqlProtocolRepository(pool)
    blindspot_repo = SqlBlindspotRepository(pool)
    task_repo = SqlTaskRepository(pool)
    entry_repo = SqlEntityEntryRepository(pool)
    _repos_ready = True

source_adapter = GitHubAdapter()

# GovernanceAI: LLM-based auto-inference (optional, depends on env config)
_governance_ai: GovernanceAI | None = None
_usage_log_repo: SqlUsageLogRepository | None = None
_tool_event_repo: SqlToolEventRepository | None = None
_audit_repo: "SqlAuditEventRepository | None" = None
_journal_repo: SqlWorkJournalRepository | None = None


async def _ensure_governance_ai() -> None:
    """Wire GovernanceAI with SqlUsageLogRepository after pool is available."""
    global _governance_ai, _usage_log_repo, _tool_event_repo
    if _governance_ai is not None:
        return
    try:
        pool = await get_pool()
        _usage_log_repo = SqlUsageLogRepository(pool)
        _tool_event_repo = SqlToolEventRepository(pool)
        llm_client = create_llm_client()
        from zenos.infrastructure.context import current_partner_id as _ctx_partner_id
        _governance_ai = GovernanceAI(
            llm_client,
            usage_log_repo=_usage_log_repo,
            get_partner_id=_ctx_partner_id.get,
        )
        logger.info("GovernanceAI initialized with model: %s", llm_client.model)
    except Exception:
        logger.warning("GovernanceAI disabled: LLM client initialization failed", exc_info=True)


async def _ensure_journal_repo() -> None:
    """Lazily initialise SqlWorkJournalRepository after pool is available."""
    global _journal_repo
    if _journal_repo is not None:
        return
    pool = await get_pool()
    _journal_repo = SqlWorkJournalRepository(pool)


async def _compress_journal(partner_id: str) -> None:
    """Compress old non-summary journal entries into a single summary row.

    Keeps the most recent 9 originals intact; compresses any older originals
    via LLM into a single is_summary=TRUE entry then deletes the originals.
    On any failure, logs a warning and returns without raising.
    """
    try:
        await _ensure_journal_repo()
        assert _journal_repo is not None
        async with _journal_repo._pool.acquire() as _conn:
            total_originals: int = await _conn.fetchval(
                "SELECT COUNT(*) FROM zenos.work_journal"
                " WHERE partner_id = $1 AND is_summary = FALSE",
                partner_id,
            )
        to_compress = total_originals - 9
        if to_compress <= 0:
            return
        entries = await _journal_repo.list_oldest_originals(
            partner_id=partner_id, limit=to_compress
        )
        if not entries:
            return

        formatted = "\n\n".join(
            f"[{e['created_at']}] project={e['project']} flow={e['flow_type']}\n{e['summary']}"
            for e in entries
        )
        prompt = (
            f"以下是 {len(entries)} 則工作日誌，請壓縮成一則不超過 300 字的摘要。\n"
            "保留：完成的功能、遺留問題、重要決策、涉及的專案與技術。\n"
            "直接輸出摘要，無需前言。\n\n"
            f"{formatted}"
        )

        from pydantic import BaseModel as _BaseModel

        class _SummaryOut(_BaseModel):
            summary: str

        llm = create_llm_client()
        result = llm.chat_structured(
            messages=[{"role": "user", "content": prompt}],
            response_schema=_SummaryOut,
        )

        as_of = datetime.now(tz=timezone.utc)

        # Collect metadata from compressed entries
        projects = list({e["project"] for e in entries if e["project"]})
        flow_types = list({e["flow_type"] for e in entries if e["flow_type"]})
        all_tags: list[str] = []
        for e in entries:
            all_tags.extend(e.get("tags") or [])
        unique_tags = list(dict.fromkeys(all_tags))

        ids = [str(e["id"]) for e in entries]
        await _journal_repo.create_summary(
            partner_id=partner_id,
            summary=result.summary,
            project=projects[0] if len(projects) == 1 else None,
            flow_type=flow_types[0] if len(flow_types) == 1 else None,
            tags=unique_tags,
            as_of=as_of,
        )
        await _journal_repo.delete_by_ids(partner_id=partner_id, ids=ids)
    except Exception:
        logger.warning("_compress_journal failed, skipping compression", exc_info=True)


# Services are wired lazily after _ensure_repos() runs.
ontology_service: OntologyService | None = None
governance_service: GovernanceService | None = None
source_service: SourceService | None = None
task_service: TaskService | None = None


async def _ensure_services() -> None:
    """Wire services once repos are ready."""
    global ontology_service, governance_service, source_service, task_service
    await _ensure_repos()
    await _ensure_governance_ai()
    if ontology_service is None:
        ontology_service = OntologyService(
            entity_repo=entity_repo,
            relationship_repo=relationship_repo,
            document_repo=document_repo,
            protocol_repo=protocol_repo,
            blindspot_repo=blindspot_repo,
            governance_ai=_governance_ai,
            source_adapter=source_adapter,
        )
    if governance_service is None:
        governance_service = GovernanceService(
            entity_repo=entity_repo,
            relationship_repo=relationship_repo,
            protocol_repo=protocol_repo,
            blindspot_repo=blindspot_repo,
            task_repo=task_repo,
            governance_ai=_governance_ai,
        )
    if source_service is None:
        source_service = SourceService(
            entity_repo=entity_repo,
            source_adapter=source_adapter,
        )
    if task_service is None:
        task_service = TaskService(
            task_repo=task_repo,
            entity_repo=entity_repo,
            blindspot_repo=blindspot_repo,
            governance_ai=_governance_ai,
            relationship_repo=relationship_repo,
            uow_factory=lambda: UnitOfWork(task_repo._pool),
        )


# ──────────────────────────────────────────────
# Serialization helpers
# ──────────────────────────────────────────────


def _serialize(obj: object) -> dict:
    """Convert a dataclass instance to a JSON-safe dict.

    Handles nested dataclasses via ``dataclasses.asdict`` and converts
    ``datetime`` objects to ISO-8601 strings so the result is
    JSON-serializable.
    """
    raw = asdict(obj)  # type: ignore[arg-type]
    data = _convert_datetimes(raw)
    # Backward-compatible task status normalization
    if "created_by" in data and "priority_reason" in data and "status" in data:
        data["status"] = {
            "backlog": "todo",
            "blocked": "in_progress",
            "archived": "done",
        }.get(data["status"], data["status"])
        # Add proxy_url to attachments that have gcs_path
        if "attachments" in data and data["attachments"]:
            data["attachments"] = _add_proxy_urls(data["attachments"])
    return data


def _convert_datetimes(data: dict) -> dict:
    """Recursively convert datetime values to ISO-8601 strings."""
    out: dict = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, dict):
            out[key] = _convert_datetimes(value)
        elif isinstance(value, list):
            out[key] = [
                _convert_datetimes(v) if isinstance(v, dict)
                else v.isoformat() if isinstance(v, datetime)
                else v
                for v in value
            ]
        else:
            out[key] = value
    return out


async def _enrich_task_result(task_obj) -> dict:
    """Serialize a task and apply enrichment (expanded entities/role/blindspot)."""
    task_dict = _serialize(task_obj)
    enr = await task_service.enrich_task(task_obj)
    task_dict["linked_entities"] = enr["expanded_entities"]
    if "assignee_role" in enr:
        task_dict["assignee_role"] = enr["assignee_role"]
    if "blindspot_detail" in enr:
        task_dict["blindspot_detail"] = enr["blindspot_detail"]
    return task_dict


async def _build_context_bundle(
    *,
    linked_entity_ids: list[str] | None = None,
    protocol_id: str | None = None,
    blindspot_id: str | None = None,
    limit: int = 5,
) -> dict:
    """Build a compact context bundle for write/confirm/search responses."""
    bundle: dict = {
        "entities": [],
        "protocol": None,
        "blindspot": None,
    }

    seen: set[str] = set()
    for eid in linked_entity_ids or []:
        if not eid or eid in seen:
            continue
        seen.add(eid)
        if entity_repo is None:
            continue
        entity = await entity_repo.get_by_id(eid)
        if entity is None or not _is_entity_visible(entity):
            continue
        bundle["entities"].append(
            {
                "id": entity.id,
                "name": entity.name,
                "summary": entity.summary,
                "status": entity.status,
                "type": entity.type,
            }
        )
        if len(bundle["entities"]) >= limit:
            break

    if protocol_id:
        if protocol_repo is None:
            return bundle
        proto = await protocol_repo.get_by_id(protocol_id)
        if proto and await _is_protocol_visible(proto):
            bundle["protocol"] = {
                "id": proto.id,
                "entity_id": proto.entity_id,
                "entity_name": proto.entity_name,
            }

    if blindspot_id:
        if blindspot_repo is None:
            return bundle
        bs = await blindspot_repo.get_by_id(blindspot_id)
        if bs and await _is_blindspot_visible(bs):
            bundle["blindspot"] = {
                "id": bs.id,
                "severity": bs.severity,
                "description": bs.description,
            }

    return bundle


def _build_governance_hints(
    *,
    warnings: list[str] | None = None,
    suggested_follow_up_tasks: list[dict] | None = None,
    similar_items: list[dict] | None = None,
    stale_candidates: list[dict] | None = None,
    suggested_entity_updates: list[dict] | None = None,
) -> dict:
    """Return additive governance hints for caller guidance."""
    warnings = warnings or []
    lowered = " ".join(warnings).lower()
    duplicate_signals = []
    if "duplicate" in lowered or "重複" in lowered:
        duplicate_signals.append("possible_duplicate")

    return {
        "duplicate_signals": duplicate_signals,
        "stale_candidates": stale_candidates or [],
        "suggested_follow_up_tasks": suggested_follow_up_tasks or [],
        "similar_items": similar_items or [],
        "suggested_entity_updates": suggested_entity_updates or [],
    }


def _unified_response(
    *,
    status: str = "ok",
    data: dict,
    warnings: list[str] | None = None,
    suggestions: list[dict] | None = None,
    similar_items: list[dict] | None = None,
    context_bundle: dict | None = None,
    governance_hints: dict | None = None,
    rejection_reason: str | None = None,
) -> dict:
    """Phase 1 unified response format for all MCP tool responses."""
    return {
        "status": status,
        "data": data,
        "warnings": warnings or [],
        "suggestions": suggestions or [],
        "similar_items": similar_items or [],
        "context_bundle": context_bundle or {},
        "governance_hints": governance_hints or {},
        **({"rejection_reason": rejection_reason} if rejection_reason else {}),
    }


def _new_id() -> str:
    """Generate a short unique ID (32-char hex UUID4)."""
    return uuid.uuid4().hex


def _parse_entity_level(entity_level: str | None) -> int | None:
    """Convert entity_level string to max_level int for domain layer.

    Returns:
        None  — no filtering (caller explicitly asked for "all" or "L1,L2,L3")
        1     — L1 only
        2     — L1+L2 (default when entity_level is not provided)
    """
    if entity_level is None:
        # Default: L1+L2 only
        return 2

    normalized = entity_level.strip().lower()
    if normalized in ("all", "l1,l2,l3", "l3"):
        return None
    if normalized == "l1":
        return 1
    if normalized in ("l2", "l1,l2"):
        return 2
    # Unrecognized → fall back to default L1+L2
    return 2


def _is_entity_visible(entity: object) -> bool:
    """Centralized server-side visibility check for read paths."""
    partner = _current_partner.get() or {}
    access = describe_partner_access(partner)
    if access["is_admin"]:
        return True
    if access["is_unassigned_partner"]:
        return False

    visibility = str(getattr(entity, "visibility", "public") or "public")

    if access["is_scoped_partner"]:
        # Scoped partner: L1 scope check is done at search/list level.
        # At per-entity level, just check visibility.
        return visibility == "public"

    # Internal non-admin
    # Department-based filter
    visible_to_departments = set(getattr(entity, "visible_to_departments", []) or [])
    partner_department = str(current_partner_department.get() or "all")
    if (
        visible_to_departments
        and partner_department not in visible_to_departments
        and "all" not in visible_to_departments
    ):
        return False

    if visibility in {"confidential", "restricted"}:
        return False
    if visibility == "role-restricted":
        partner_roles = set(current_partner_roles.get() or [])
        visible_to_roles = set(getattr(entity, "visible_to_roles", []) or [])
        return bool(partner_roles & visible_to_roles) if visible_to_roles else False
    return True


async def _is_task_visible(task: object) -> bool:
    """Task visibility check.

    - Admin: always visible.
    - Scoped partner: requires at least one linked entity in their L1 subtree.
      Entity visibility (public/restricted) is NOT checked — any entity in scope
      makes the task visible. Tasks with no linked entities are NOT visible.
    - Internal non-admin: task hidden if ANY linked entity is invisible.
      Tasks with no linked entities are always visible (fail-open).
    """
    try:
        linked = getattr(task, "linked_entities", None) or []
        partner = _current_partner.get() or {}
        if partner.get("isAdmin", False):
            return True
        if is_unassigned_partner(partner):
            return False

        if is_scoped_partner(partner):
            # Scoped partner: visible if at least one linked entity is in allowed_ids.
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
    try:
        entity_id = getattr(protocol, "entity_id", None)
        if not entity_id:
            return True  # orphan protocol = visible
        partner = _current_partner.get() or {}
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
    Scoped partners (clients) never see blindspots.
    """
    try:
        partner = _current_partner.get() or {}
        if partner.get("isAdmin", False):
            return True
        # Scoped partners cannot see blindspots
        if is_unassigned_partner(partner):
            return False
        if is_scoped_partner(partner):
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


def _audit_log(
    event_type: str,
    target: dict,
    changes: dict | None = None,
    governance: dict | None = None,
) -> None:
    """Emit structured governance audit logs to stdout/Cloud Logging + SQL."""
    partner = _current_partner.get() or {}
    payload = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "partner_id": partner.get("id", ""),
        "actor": {
            "id": partner.get("id", ""),
            "name": partner.get("displayName", "system"),
            "email": partner.get("email", ""),
        },
        "target": target,
        "changes": changes or {},
        "governance": governance or {},
    }
    logger.info("AUDIT_LOG %s", json.dumps(payload, ensure_ascii=False, default=str))

    # Async SQL write (non-blocking, graceful degradation)
    _schedule_audit_sql_write(payload)


def _schedule_audit_sql_write(payload: dict) -> None:
    """Schedule non-blocking SQL write. Never raises."""
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running():
            return
        loop.create_task(_write_audit_event(payload))
    except Exception:
        pass  # Audit write scheduling must never crash the caller


async def _write_audit_event(payload: dict) -> None:
    """Write audit event to SQL. Failure only logs warning."""
    global _audit_repo  # noqa: PLW0603
    try:
        if _audit_repo is None:
            from zenos.infrastructure.sql_repo import SqlAuditEventRepository
            pool = await get_pool()
            _audit_repo = SqlAuditEventRepository(pool)
        event = {
            "partner_id": payload.get("partner_id", ""),
            "actor_id": payload.get("actor", {}).get("id", ""),
            "actor_type": "partner",
            "operation": payload.get("event_type", ""),
            "resource_type": payload.get("target", {}).get("collection", ""),
            "resource_id": payload.get("target", {}).get("id"),
            "changes_json": payload.get("changes"),
        }
        await _audit_repo.create(event)
    except Exception:
        logger.warning("Audit SQL write failed", exc_info=True)


# ===================================================================
# Tool event logging helper
# ===================================================================


async def _log_tool_event(
    partner_id: str,
    tool_name: str,
    entity_id: str | None,
    query: str | None,
    result_count: int | None,
) -> None:
    """Write a single tool event row. Errors are logged as warnings only."""
    if _tool_event_repo is None:
        return
    try:
        await _tool_event_repo.log_tool_event(
            partner_id=partner_id,
            tool_name=tool_name,
            entity_id=entity_id,
            query=query,
            result_count=result_count,
        )
    except Exception:
        logger.warning("tool_event logging failed", exc_info=True)


def _schedule_tool_event(
    tool_name: str,
    entity_id: str | None,
    query: str | None,
    result_count: int | None,
) -> None:
    """Schedule a non-blocking tool event insert via asyncio.create_task."""
    partner_id = _current_partner_id.get()
    if not partner_id:
        return
    try:
        asyncio.create_task(
            _log_tool_event(
                partner_id=partner_id,
                tool_name=tool_name,
                entity_id=entity_id,
                query=query,
                result_count=result_count,
            )
        )
    except RuntimeError:
        # No running event loop (e.g. tests not using asyncio)
        pass


# ===================================================================
# Tool 1: search — find and list across all collections
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def search(
    query: str = "",
    collection: str = "all",
    status: str | None = None,
    severity: str | None = None,
    entity_name: str | None = None,
    assignee: str | None = None,
    created_by: str | None = None,
    confirmed_only: bool | None = None,
    limit: int = 200,
    offset: int = 0,
    project: str | None = None,
    plan_id: str | None = None,
    product_id: str | None = None,
    product: str | None = None,
    entity_level: str | None = None,
) -> dict:
    """搜尋和列出 ontology 及任務中的所有內容。

    這是你探索 ZenOS 知識庫的主要入口。當你需要「找東西」時用這個。
    支援關鍵字搜尋（跨所有集合）或按集合過濾列出。

    使用時機：
    - 不確定要找什麼 → query="關鍵字"，collection="all"
    - 列出某類東西 → collection="entities"，可加 status 過濾
    - 看待確認項目 → confirmed_only=False
    - 查任務 → collection="tasks"，可加 assignee/created_by 過濾
    - 查同一 plan 的所有任務 → collection="tasks"，plan_id="my-plan-id"
    - 按產品過濾 → product="Paceriz"（by name）或 product_id="product-xxx"（by ID）
    - 控制搜尋層級 → entity_level="L1,L2"（預設只搜 L1+L2，排除 L3 細節）

    不要用這個工具的情境：
    - 已知確切名稱要看完整資料 → 用 get
    - 要讀原始文件內容 → 用 read_source
    - 要搜尋任務 → collection="tasks"（在這裡，不需要用 task 工具）

    限制：關鍵字搜尋，非語意搜尋。query 最長 200 字。

    Args:
        query: 搜尋關鍵字（空字串 = 列出全部）
        collection: 搜尋範圍。all/entities/documents/protocols/blindspots/tasks/entries
        status: 按狀態過濾（如 active/open/todo/in_progress，逗號分隔多值）
        severity: 按嚴重度過濾 blindspots（red/yellow/green）
        entity_name: 按實體名稱過濾（blindspots 和 documents 用）
        assignee: 按被指派者過濾 tasks（Inbox 視角）
        created_by: 按建立者過濾 tasks（Outbox 視角）
        confirmed_only: true=只看已確認 / false=只看未確認 / 不傳=全部
        limit: 回傳上限，預設 200（無硬性 cap，可依需求調大）
        offset: 分頁偏移量，預設 0。搭配 limit 做分頁。
        project: 按專案過濾 tasks（如 "zenos"、"paceriz"）。
            未傳時自動使用 partner 的 default_project，確保跨專案隔離。
        plan_id: 按 plan 過濾 tasks（精確找同一 plan 的所有票）。
        product_id: 按產品 ID 過濾。只回傳該產品及其子樹內的 entity/task。
        product: 按產品名稱過濾（case-insensitive）。找不到時回傳錯誤提示。
            與 product_id 並存，product 優先。
        entity_level: 控制搜尋的 entity 層級。
            "L1" = 只搜 L1（product, project, goal, role）
            "L2" = 只搜 L2（module, strategy, knowledge 等）
            "L1,L2" = 搜 L1+L2（預設行為）
            "L1,L2,L3" 或 "all" = 搜所有層級（含 L3 文件/細節）
            不傳時預設只搜 L1+L2，排除 L3 細節節點。
    """
    await _ensure_services()
    results: dict = {}

    # Resolve product name → product_id (product takes priority over product_id)
    if product is not None:
        resolved = await entity_repo.get_by_name(product)
        if resolved is None:
            return {
                "error": f"找不到名為 '{product}' 的產品。請確認名稱是否正確。",
                "hint": "用 search(collection='entities', status='product') 查看所有產品。",
            }
        product_id = resolved.id

    # Parse entity_level → max_level int for domain layer
    max_level = _parse_entity_level(entity_level)

    # Keyword search mode (cross-collection)
    if query.strip() and collection == "all":
        search_results = await ontology_service.search(
            query, max_level=max_level, product_id=product_id,
        )
        visible_results = [r for r in search_results if (r.type != "entity" or _is_entity_visible(r))]
        paginated = visible_results[offset:offset + limit]
        results["results"] = [_serialize(r) for r in paginated]
        results["count"] = len(results["results"])
        results["total"] = len(visible_results)

        # Also search tasks by title/description keyword
        # Auto-fill project from partner context if caller omits it
        _partner_ctx = _current_partner.get()
        effective_project_kw = project or (_partner_ctx.get("defaultProject", "") if _partner_ctx else "")
        all_tasks = await task_service.list_tasks(limit=200, project=effective_project_kw or None)
        query_lower = query.lower()
        matched_tasks = [
            t for t in all_tasks
            if query_lower in t.title.lower()
            or query_lower in t.description.lower()
        ]
        # Filter tasks by linked entity visibility
        visible_tasks = []
        for t in matched_tasks:
            if await _is_task_visible(t):
                visible_tasks.append(t)
                if len(visible_tasks) >= limit:
                    break
        if visible_tasks:
            results["tasks"] = [await _enrich_task_result(t) for t in visible_tasks]

        # Also search entity entries content (filter by parent entity visibility)
        partner_department = str(current_partner_department.get() or "all")
        entry_hits = await entry_repo.search_content(query, limit=limit, department=partner_department)
        if entry_hits:
            visible_entries = []
            for hit in entry_hits:
                entry_obj = hit["entry"]
                parent_eid = getattr(entry_obj, "entity_id", None)
                if parent_eid:
                    parent_entity = await entity_repo.get_by_id(parent_eid)
                    if parent_entity and not _is_entity_visible(parent_entity):
                        continue
                visible_entries.append(
                    {**_serialize(entry_obj), "entity_name": hit["entity_name"]}
                )
            if visible_entries:
                results["entries"] = visible_entries

        # Log a tool event for each exposed entity
        exposed_count = results.get("count", 0)
        for r in visible_results[:limit]:
            eid = getattr(r, "id", None)
            if eid:
                _schedule_tool_event("search", eid, query, exposed_count)

        return results

    # Collection-specific listing
    collections = (
        [collection] if collection != "all"
        else ["entities", "documents", "protocols", "blindspots", "tasks"]
    )

    for col in collections:
        if col == "entities":
            type_filter = status if status in (
                "product", "module", "goal", "role", "project"
            ) else None
            entities = await ontology_service.list_entities(type_filter=type_filter)
            entities = [e for e in entities if _is_entity_visible(e)]
            # Apply L1 scope filter for scoped partners
            _partner_ctx = _current_partner.get() or {}
            _access = describe_partner_access(_partner_ctx)
            if _access["is_scoped_partner"]:
                all_entities_for_map = await ontology_service._entities.list_all()
                _entity_map = {e.id: e for e in all_entities_for_map if e.id}
                _allowed: set[str] = set()
                for _l1_id in _access["authorized_l1_ids"]:
                    _allowed |= _collect_subtree_ids(_l1_id, _entity_map)
                entities = [e for e in entities if e.id in _allowed]
            # Apply level filter
            if max_level is not None:
                entities = [e for e in entities if (e.level or 1) <= max_level]
            # Apply product_id filter
            if product_id is not None:
                entity_map = {e.id: e for e in entities if e.id}
                subtree_ids = _collect_subtree_ids(product_id, entity_map)
                entities = [e for e in entities if e.id in subtree_ids]
            if confirmed_only is not None:
                entities = [
                    e for e in entities
                    if e.confirmed_by_user == confirmed_only
                ]
            paginated_entities = entities[offset:offset + limit]
            items = [_serialize(e) for e in paginated_entities]
            results["entities"] = items

        elif col == "documents":
            # Query document entities (type="document") from entities collection
            doc_entities = await ontology_service._entities.list_all(type_filter="document")
            doc_entities = [d for d in doc_entities if _is_entity_visible(d)]
            # Exclude archived document entities (dead links confirmed unresolvable)
            doc_entities = [d for d in doc_entities if d.status != "archived"]
            # Apply product_id filter for documents via parent_id chain
            if product_id is not None:
                all_entities = await ontology_service._entities.list_all()
                entity_map = {e.id: e for e in all_entities if e.id}
                subtree_ids = _collect_subtree_ids(product_id, entity_map)
                doc_entities = [d for d in doc_entities if d.parent_id in subtree_ids]
            if query.strip():
                q = query.lower().strip()
                filtered = []
                for d in doc_entities:
                    source_uris = " ".join(str(s.get("uri", "")) for s in (d.sources or []))
                    source_labels = " ".join(str(s.get("label", "")) for s in (d.sources or []))
                    haystack = f"{d.name} {d.summary} {source_uris} {source_labels}".lower()
                    if q in haystack:
                        filtered.append(d)
                doc_entities = filtered
            if entity_name:
                entity = await ontology_service._entities.get_by_name(entity_name)
                if entity and entity.id:
                    doc_entities = [
                        d for d in doc_entities if d.parent_id == entity.id
                    ]
            if confirmed_only is not None:
                doc_entities = [d for d in doc_entities if d.confirmed_by_user == confirmed_only]
            results["documents"] = [_serialize(d) for d in doc_entities[offset:offset + limit]]

        elif col == "protocols":
            if confirmed_only is False:
                protos = await ontology_service._protocols.list_unconfirmed()
            else:
                protos = await ontology_service._protocols.list_all(confirmed_only=confirmed_only)
            visible_protos = [p for p in protos if await _is_protocol_visible(p)]
            results["protocols"] = [_serialize(p) for p in visible_protos[offset:offset + limit]]

        elif col == "blindspots":
            blindspots = await ontology_service.list_blindspots(
                entity_name=entity_name, severity=severity
            )
            if confirmed_only is not None:
                blindspots = [
                    b for b in blindspots
                    if b.confirmed_by_user == confirmed_only
                ]
            visible_bs = [b for b in blindspots if await _is_blindspot_visible(b)]
            results["blindspots"] = [_serialize(b) for b in visible_bs[offset:offset + limit]]

        elif col == "tasks":
            status_list = status.split(",") if status else None
            # Auto-fill project from partner context if caller omits it
            _partner = _current_partner.get()
            effective_project = project or (_partner.get("defaultProject", "") if _partner else "")
            tasks = await task_service.list_tasks(
                assignee=assignee,
                created_by=created_by,
                status=status_list,
                limit=limit,
                offset=offset,
                project=effective_project or None,
                plan_id=plan_id,
            )
            # Filter tasks by linked entity visibility
            visible_tasks = [t for t in tasks if await _is_task_visible(t)]
            # Apply keyword filter if query provided
            if query.strip():
                q = query.lower()
                visible_tasks = [
                    t for t in visible_tasks
                    if q in t.title.lower() or q in (t.description or "").lower()
                ]
            results["tasks"] = [await _enrich_task_result(t) for t in visible_tasks]

        elif col == "entries":
            if not query.strip():
                return {
                    "error": "INVALID_INPUT",
                    "message": "search(collection='entries') 目前需要提供 query 關鍵字",
                }
            partner_department = str(current_partner_department.get() or "all")
            entry_hits = await entry_repo.search_content(
                query,
                limit=limit,
                department=partner_department,
            )
            results["entries"] = [
                {**_serialize(hit["entry"]), "entity_name": hit["entity_name"]}
                for hit in entry_hits
            ]

    # Log a tool event for each entity exposed in collection-specific results
    entity_items = results.get("entities", [])
    total_count = sum(len(v) for v in results.values() if isinstance(v, list))
    for item in entity_items:
        eid = item.get("id") if isinstance(item, dict) else None
        if eid:
            _schedule_tool_event("search", eid, query or None, total_count)

    return results


# ===================================================================
# Tool 2: get — retrieve one specific item
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def get(
    collection: str,
    name: str | None = None,
    id: str | None = None,
) -> dict:
    """取得一個特定項目的完整資訊。

    當你已經知道要找的東西的名稱或 ID 時用這個。
    回傳該項目的所有欄位，包括四維標籤、關係、gaps 等完整資訊。

    使用時機：
    - 知道實體名稱 → get(collection="entities", name="Paceriz")
    - 知道 Protocol → get(collection="protocols", name="Paceriz")
    - 知道文件 ID → get(collection="documents", id="doc-abc")
    - 知道任務 ID → get(collection="tasks", id="task-001")

    不要用這個工具的情境：
    - 不確定名稱 → 用 search
    - 要讀文件原始內容 → 先用這個拿 metadata，再用 read_source

    Args:
        collection: entities/documents/protocols/blindspots/tasks
        name: 項目名稱（entities 和 protocols 支援按名稱查詢）
        id: 項目 ID（所有集合都支援）
    """
    await _ensure_services()
    if not name and not id:
        return {"error": "INVALID_INPUT", "message": "Must provide either name or id"}

    if collection == "entities":
        if name:
            result = await ontology_service.get_entity(name)
        elif id:
            entity = await entity_repo.get_by_id(id)
            if entity is None:
                return {"error": "NOT_FOUND", "message": f"Entity '{id}' not found"}
            rels = await relationship_repo.list_by_entity(id)
            from zenos.application.ontology_service import EntityWithRelationships
            result = EntityWithRelationships(entity=entity, relationships=rels)
        else:
            result = None
        if result is None:
            return {"error": "NOT_FOUND", "message": f"Entity not found"}
        if not _is_entity_visible(result.entity):
            return {"error": "NOT_FOUND", "message": "Entity not found"}
        response = _serialize(result)
        # Split relationships into outgoing/incoming for clearer graph navigation
        eid = result.entity.id
        if result.relationships:
            response["outgoing_relationships"] = [
                _serialize(r) for r in result.relationships
                if r.source_entity_id == eid
            ]
            response["incoming_relationships"] = [
                _serialize(r) for r in result.relationships
                if r.source_entity_id != eid
            ]
            # Remove flat list to avoid payload duplication
            response.pop("relationships", None)
        # Attach active entries so callers see the entity as a knowledge container
        active_entries = await entry_repo.list_by_entity(eid) if eid else []
        response["active_entries"] = [_serialize(e) for e in active_entries]
        if eid:
            response["impact_chain"] = await ontology_service.compute_impact_chain(eid, direction="forward")
            response["reverse_impact_chain"] = await ontology_service.compute_impact_chain(eid, direction="reverse")
        _schedule_tool_event("get", eid, None, None)
        return response

    elif collection == "protocols":
        if name:
            result = await ontology_service.get_protocol(name)
        elif id:
            # Backward compatibility: first treat id as protocol doc id,
            # fallback to legacy behavior where id is entity_id.
            result = await protocol_repo.get_by_id(id)
            if result is None:
                result = await protocol_repo.get_by_entity(id)
        else:
            result = None
        if result is None:
            return {"error": "NOT_FOUND", "message": "Protocol not found"}
        if not await _is_protocol_visible(result):
            return {"error": "NOT_FOUND", "message": "Protocol not found"}
        return _serialize(result)

    elif collection == "documents":
        doc_id = id or name
        if not doc_id:
            return {"error": "INVALID_INPUT", "message": "Provide id for documents"}
        # Try entity(type=document) first, then legacy documents
        result = await ontology_service.get_document(doc_id)
        if result is None:
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
        if not _is_entity_visible(result):
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
        return _serialize(result)

    elif collection == "blindspots":
        if not id:
            return {"error": "INVALID_INPUT", "message": "Provide id for blindspots"}
        result = await blindspot_repo.get_by_id(id)
        if result is None:
            return {"error": "NOT_FOUND", "message": f"Blindspot '{id}' not found"}
        if not await _is_blindspot_visible(result):
            return {"error": "NOT_FOUND", "message": f"Blindspot '{id}' not found"}
        return _serialize(result)

    elif collection == "tasks":
        if not id:
            return {"error": "INVALID_INPUT", "message": "Provide id for tasks"}
        enriched = await task_service.get_task_enriched(id)
        if enriched is None:
            return {"error": "NOT_FOUND", "message": f"Task '{id}' not found"}
        task_obj, _ = enriched
        if not await _is_task_visible(task_obj):
            return {"error": "NOT_FOUND", "message": f"Task '{id}' not found"}
        return await _enrich_task_result(task_obj)

    else:
        return {
            "error": "INVALID_INPUT",
            "message": f"Unknown collection '{collection}'. "
            f"Use: entities, documents, protocols, blindspots, tasks",
        }


# ===================================================================
# Tool 3: read_source — read raw file content
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def read_source(doc_id: str) -> dict:
    """讀取文件的原始內容（透過 adapter 從 GitHub 等來源取得）。

    這個工具讀取的是實際的文件內容，不是 ontology metadata。
    請先用 get(collection="documents", id=...) 確認文件存在，
    再用這個工具讀取原始內容。

    使用時機：
    - 需要文件的實際文字內容（程式碼、文件正文）
    - 先用 get 看過 metadata，確認相關後再讀原文

    限制：目前只支援 GitHub adapter。檔案 > 1MB 需要特殊處理。

    Args:
        doc_id: 文件的 ID（從 search 或 get 取得）
    """
    await _ensure_services()
    try:
        doc_entity = await entity_repo.get_by_id(doc_id)
        if doc_entity and not _is_entity_visible(doc_entity):
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
        result = None
        reader = getattr(source_service, "read_source_with_recovery", None)
        if reader is not None:
            maybe = reader(doc_id)
            if inspect.isawaitable(maybe):
                result = await maybe
        if result is None:
            result = await source_service.read_source(doc_id)
        if isinstance(result, str):
            return {"doc_id": doc_id, "content": result}
        if "content" in result:
            return {"doc_id": doc_id, "content": result["content"]}
        return result
    except (ValueError, FileNotFoundError):
        return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
    except PermissionError:
        return {"error": "ADAPTER_ERROR", "message": "Permission denied while reading source"}
    except RuntimeError as e:
        return {"error": "ADAPTER_ERROR", "message": str(e)}


# ===================================================================
# Tool 4: write — create/update ontology entries
# ===================================================================


@mcp.tool(
    tags={"write"},
    annotations={"idempotentHint": True},
)
async def write(
    collection: str,
    data: dict,
    id: str | None = None,
) -> dict:
    """建立或更新 ontology 中的知識條目。

    當你需要記錄、更新或修改公司知識庫時用這個。
    根據 collection 參數決定寫入哪個集合，data 的格式因集合而異。

    使用時機：
    - 記錄新實體 → collection="entities"
    - 註冊文件 → collection="documents"
    - 建立 Protocol → collection="protocols"
    - 記錄盲點 → collection="blindspots"
    - 建立關係 → collection="relationships"
    - 記錄 entity 知識條目 → collection="entries"

    不要用這個工具的情境：
    - 管理任務（建立/更新） → 用 task
    - 確認 draft → 用 confirm
    - 分析 ontology 健康度 → 用 analyze

    各集合必填欄位：

    entities: name, type(product/module/goal/role/project/document), summary,
              tags({what, why, how, who})
              選填：parent_id（module 必須設為所屬 product 的 entity ID）
              選填：owner（負責人名稱，如 "Barry"）
              選填：sources([{uri, label, type}]) 或 append_sources（追加不覆蓋）
              選填：visibility（"public" | "restricted"，預設 public）
              選填：force（true 時可覆寫已確認 entity 的非空欄位）
              選填：consolidation_mode（"global" | "incremental"，標記 L2 建立時的統合模式）
              選填：layer_decision({q1_persistent, q2_cross_role, q3_company_consensus, impacts_draft})
                    — 新建 L2（type=module）時必填，除非 force=True
                    — 型別必須是 object（dict），不可傳 JSON 字串
                    — 三問（boolean）：
                      q1_persistent: bool — 持久性：是否為公司核心持久知識？（非臨時性、不隨 sprint 消失）
                      q2_cross_role: bool — 跨角色：是否跨角色共識？（不是某個人的個人筆記）
                      q3_company_consensus: bool — 全司共識：是否為經確認的公司知識？（在不同情境指向同一件事）
                    — impacts 門檻（string，三問全 true 後獨立驗證）：
                      impacts_draft: str — 具體影響描述，格式「A 改了什麼 → B 的什麼要跟著看」（至少 1 條）
                    — 正確：
                      layer_decision={
                        "q1_persistent": true,
                        "q2_cross_role": true,
                        "q3_company_consensus": true,
                        "impacts_draft": "A 改了什麼→B 的什麼要跟著看"
                      }
                    — 錯誤（不要這樣傳）：
                      layer_decision="{\"q1_persistent\":true,...}"
    documents: title, source({type, uri, adapter}), tags({what[], why, how, who[]}),
               summary。更新語意為 merge update（未提供欄位不清空）。
               linked_entity_ids canonical 格式為 list[str]，也接受 JSON array 字串（會正規化）。
               可用 sync_mode 做文件治理批次同步：
                 - rename: 文件改名
                 - reclassify: 重新分類（改 tags/type）
                 - archive: 歸檔（標記為不再使用）
                 - supersede: 被新版取代
                 - sync_repair: 修復同步問題
               搭配 dry_run=true 可先預覽變更。
    protocols: entity_id, entity_name, content({what, why, how, who})
    blindspots: description, severity(red/yellow/green), suggested_action
    relationships: source_entity_id, target_entity_id, type(depends_on/serves/
                   owned_by/part_of/blocks/related_to/impacts/enables), description
    entries: entity_id（必填）, type（必填）, content（必填：1-200 字元）
             選填：context（額外脈絡，最多 200 字元）, author, source_task_id
             type（必填）各類型區別：
               - decision: 團隊做出的決定（如「選用 PostgreSQL」）
               - insight: 發現的洞察（如「用戶主要在週末使用」）
               - limitation: 已知限制（如「API 不支援批量操作」）
               - change: 變更記錄（如「v2.0 移除了舊認證」）
               - context: 背景脈絡（如「此模組由外部團隊維護」）

             supersede 流程：
             1. 先建立新 entry（write collection="entries", data={entity_id, type, content, ...}）
             2. 拿到新 entry id 後，更新舊 entry 狀態：
                write collection="entries", id=<舊 entry id>,
                data={status="superseded", superseded_by=<新 entry id>}

    Args:
        collection: entities/documents/protocols/blindspots/relationships/entries
        data: 集合對應的欄位（見上方說明）
        id: entries 更新 status 時提供既有 entry ID；其他集合新增時不提供
    """
    await _ensure_services()
    try:
        if id:
            data["id"] = id

        if collection == "entities":
            # --- Permission check: existing entity must be visible to caller ---
            existing_id = data.get("id")
            existing_name = data.get("name")
            existing_entity = None
            if existing_id:
                existing_entity = await entity_repo.get_by_id(existing_id)
            elif existing_name:
                existing_entity = await entity_repo.get_by_name(existing_name)
            if existing_entity:
                auth_error = _check_write_visibility(existing_entity, data)
                if auth_error:
                    return auth_error
                # Capture before-state for audit diff
                _before_visibility = {
                    "visibility": getattr(existing_entity, "visibility", "public"),
                    "visible_to_roles": list(getattr(existing_entity, "visible_to_roles", []) or []),
                    "visible_to_members": list(getattr(existing_entity, "visible_to_members", []) or []),
                    "visible_to_departments": list(getattr(existing_entity, "visible_to_departments", []) or []),
                }
            else:
                _before_visibility = None

            result = await ontology_service.upsert_entity(data)
            serialized = _serialize(result)
            entity_id = serialized.get("entity", {}).get("id")
            _audit_log(
                event_type="ontology.entity.upsert",
                target={"collection": collection, "id": entity_id},
                changes={"input": data},
                governance={"warnings": result.warnings or []},
            )
            context_bundle = await _build_context_bundle(
                linked_entity_ids=[entity_id] if entity_id else []
            )
            governance_hints = _build_governance_hints(
                warnings=result.warnings or [],
                similar_items=result.similar_items,
            )
            # --- Visibility change audit ---
            if _before_visibility is not None:
                result_entity = result.entity if hasattr(result, "entity") else None
                _after_visibility = {
                    "visibility": getattr(result_entity, "visibility", "public") if result_entity else data.get("visibility", "public"),
                    "visible_to_roles": list(getattr(result_entity, "visible_to_roles", []) or []) if result_entity else data.get("visible_to_roles", []),
                    "visible_to_members": list(getattr(result_entity, "visible_to_members", []) or []) if result_entity else data.get("visible_to_members", []),
                    "visible_to_departments": list(getattr(result_entity, "visible_to_departments", []) or []) if result_entity else data.get("visible_to_departments", []),
                }
                if _before_visibility != _after_visibility:
                    _audit_log(
                        event_type="governance.visibility.change",
                        target={"collection": collection, "id": entity_id},
                        changes={"before": _before_visibility, "after": _after_visibility},
                    )
            # Auto policy suggestion when visibility not specified
            policy_suggestion = None
            if "visibility" not in data:
                try:
                    from zenos.application.policy_suggestion_service import PolicySuggestionService
                    _policy_svc = PolicySuggestionService(entity_repo=ontology_service._entities)
                    policy_suggestion = await _policy_svc.suggest(entity_id)
                except Exception:
                    pass  # never block write
            if policy_suggestion is not None:
                serialized["policy_suggestion"] = policy_suggestion
            return _unified_response(
                data=serialized,
                warnings=result.warnings or [],
                similar_items=result.similar_items or [],
                context_bundle=context_bundle,
                governance_hints=governance_hints,
            )

        elif collection == "documents":
            # Backward compat: collection="documents" now creates entity(type="document")
            if data.get("sync_mode"):
                result = await ontology_service.sync_document_governance(data)
                serialized = _serialize(result)
                _audit_log(
                    event_type="ontology.document.sync",
                    target={"collection": collection, "id": serialized.get("document_id")},
                    changes={"input": data},
                )
                return _unified_response(data=serialized)
            result = await ontology_service.upsert_document(data)
            serialized = _serialize(result)
            _audit_log(
                event_type="ontology.document.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            linked_ids = serialized.get("linked_entity_ids") or data.get("linked_entity_ids") or []
            return _unified_response(
                data=serialized,
                context_bundle=await _build_context_bundle(linked_entity_ids=linked_ids),
                governance_hints=_build_governance_hints(),
            )

        elif collection == "protocols":
            result = await ontology_service.upsert_protocol(data)
            serialized = _serialize(result)
            _audit_log(
                event_type="ontology.protocol.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            return _unified_response(
                data=serialized,
                context_bundle=await _build_context_bundle(
                    linked_entity_ids=[serialized.get("entity_id")] if serialized.get("entity_id") else [],
                    protocol_id=serialized.get("id"),
                ),
                governance_hints=_build_governance_hints(),
            )

        elif collection == "blindspots":
            result = await ontology_service.add_blindspot(data)
            serialized = _serialize(result)

            # Red blindspots auto-create a draft task for immediate attention
            if result.severity == "red":
                # Idempotency: avoid creating duplicate open tasks for same blindspot.
                _partner_ctx = _current_partner.get()
                effective_project = (
                    _partner_ctx.get("defaultProject", "") if _partner_ctx else ""
                )
                existing_tasks = await task_service.list_tasks(
                    limit=200,
                    project=effective_project or None,
                )
                duplicate_open = next(
                    (
                        t
                        for t in existing_tasks
                        if t.linked_blindspot == result.id
                        and t.source_type == "blindspot"
                        and t.status not in {"done", "archived", "cancelled"}
                    ),
                    None,
                )
                if duplicate_open is not None:
                    _audit_log(
                        event_type="ontology.blindspot.upsert",
                        target={"collection": collection, "id": serialized.get("id")},
                        changes={"input": data},
                        governance={"auto_task": "skipped_existing_open"},
                    )
                    return _unified_response(
                        data={
                            **serialized,
                            "auto_created_task": _serialize(duplicate_open),
                            "auto_task_skipped": "EXISTING_OPEN_TASK",
                        },
                        suggestions=[{
                            "id": duplicate_open.id,
                            "title": duplicate_open.title,
                            "reason": "existing_open_task_for_blindspot",
                        }],
                        context_bundle=await _build_context_bundle(
                            linked_entity_ids=result.related_entity_ids,
                            blindspot_id=result.id,
                        ),
                        governance_hints=_build_governance_hints(
                            suggested_follow_up_tasks=[{
                                "id": duplicate_open.id,
                                "title": duplicate_open.title,
                                "reason": "existing_open_task_for_blindspot",
                            }]
                        ),
                    )

                # Infer assignee from related entities' who tag
                assignee = None
                for eid in (result.related_entity_ids or []):
                    entity = await entity_repo.get_by_id(eid)
                    if entity and entity.tags.who:
                        who = entity.tags.who
                        if isinstance(who, list):
                            assignee = who[0] if who else None
                        else:
                            assignee = who
                        break

                creator_id = (_partner_ctx or {}).get("id") or "system"
                auto_task_data = {
                    "title": f"處理盲點：{result.description[:30]}",
                    "source_type": "blindspot",
                    "source_metadata": {
                        "created_via_agent": True,
                        "agent_name": "system-auto",
                        "actor_partner_id": creator_id,
                    },
                    "linked_blindspot": result.id,
                    "linked_entities": result.related_entity_ids or [],
                    "status": "todo",
                    "created_by": creator_id,
                    "updated_by": creator_id,
                    "assignee": assignee,
                }
                auto_task_result = await task_service.create_task(auto_task_data)
                serialized["auto_created_task"] = _serialize(auto_task_result.task)

            _audit_log(
                event_type="ontology.blindspot.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            context_bundle = await _build_context_bundle(
                linked_entity_ids=result.related_entity_ids,
                blindspot_id=result.id,
            )
            follow_ups = []
            auto_created = serialized.get("auto_created_task")
            if isinstance(auto_created, dict):
                follow_ups.append({
                    "id": auto_created.get("id"),
                    "title": auto_created.get("title"),
                    "reason": "blindspot_requires_action",
                })
            return _unified_response(
                data=serialized,
                suggestions=follow_ups,
                context_bundle=context_bundle,
                governance_hints=_build_governance_hints(suggested_follow_up_tasks=follow_ups),
            )

        elif collection == "relationships":
            result = await ontology_service.add_relationship(
                source_id=data["source_entity_id"],
                target_id=data["target_entity_id"],
                rel_type=data["type"],
                description=data["description"],
                verb=data.get("verb"),
            )
            serialized = _serialize(result)
            _audit_log(
                event_type="ontology.relationship.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            # Suggest verbs when caller did not provide one
            if result.verb is None and governance_service is not None:
                src_entity = await entity_repo.get_by_id(data["source_entity_id"])
                tgt_entity = await entity_repo.get_by_id(data["target_entity_id"])
                if src_entity is not None and tgt_entity is not None:
                    suggested_verbs = await governance_service.suggest_relationship_verb(
                        src_entity, tgt_entity
                    )
                    serialized["suggested_verbs"] = suggested_verbs
                else:
                    serialized["suggested_verbs"] = []
            else:
                serialized["suggested_verbs"] = []
            return _unified_response(
                data=serialized,
                context_bundle=await _build_context_bundle(
                    linked_entity_ids=[data["source_entity_id"], data["target_entity_id"]],
                ),
                governance_hints=_build_governance_hints(),
            )

        elif collection == "entries":
            # Update status flow (e.g. supersede)
            if id:
                new_status = data.get("status")
                superseded_by = data.get("superseded_by")
                if not new_status:
                    return _unified_response(status="rejected", data={}, rejection_reason="entries 更新時 data 需提供 status")
                valid_statuses = {"active", "superseded", "archived"}
                if new_status not in valid_statuses:
                    return _unified_response(status="rejected", data={}, rejection_reason=f"status 必須是 {valid_statuses} 之一")
                if new_status == "superseded" and not superseded_by:
                    return _unified_response(status="rejected", data={}, rejection_reason="status=superseded 時必填 superseded_by")
                archive_reason = data.get("archive_reason")
                if new_status == "archived":
                    if not archive_reason:
                        return _unified_response(status="rejected", data={}, rejection_reason="status=archived 時必填 archive_reason")
                    if archive_reason not in ("merged", "manual"):
                        return _unified_response(status="rejected", data={}, rejection_reason="archive_reason 必須是 merged 或 manual")
                updated = await entry_repo.update_status(id, new_status, superseded_by, archive_reason)
                if updated is None:
                    return _unified_response(
                        status="rejected",
                        data={},
                        rejection_reason=f"Entry '{id}' not found",
                    )
                serialized = _serialize(updated)
                return _unified_response(
                    data=serialized,
                    context_bundle=await _build_context_bundle(
                        linked_entity_ids=[serialized.get("entity_id")] if serialized.get("entity_id") else []
                    ),
                    governance_hints=_build_governance_hints(),
                )

            # Create new entry
            entity_id = data.get("entity_id")
            entry_type = data.get("type")
            content = data.get("content")
            if not entity_id or not entry_type or not content:
                return _unified_response(status="rejected", data={}, rejection_reason="entries 必填：entity_id, type, content")
            if not (1 <= len(content) <= 200):
                return _unified_response(status="rejected", data={}, rejection_reason="content 必須 1-200 字元")
            valid_types = {"decision", "insight", "limitation", "change", "context"}
            if entry_type not in valid_types:
                return _unified_response(status="rejected", data={}, rejection_reason=f"type 必須是 {valid_types} 之一")
            context = data.get("context")
            if context and len(context) > 200:
                return _unified_response(status="rejected", data={}, rejection_reason="context 最多 200 字元")

            partner_ctx = _current_partner.get() or {}
            pid = partner_ctx.get("id", "")
            partner_department = str(partner_ctx.get("department") or current_partner_department.get() or "all")
            entry = EntityEntry(
                id=_new_id(),
                partner_id=pid,
                entity_id=entity_id,
                type=entry_type,
                content=content,
                context=context,
                author=data.get("author"),
                department=partner_department,
                source_task_id=data.get("source_task_id"),
            )
            result = await entry_repo.create(entry)
            _audit_log(
                event_type="ontology.entry.create",
                target={"collection": collection, "id": result.id},
                changes={"input": data},
            )
            serialized = _serialize(result)
            active_count = await entry_repo.count_active_by_entity(entity_id, department=partner_department)
            entry_warnings: list[str] = []
            if active_count >= 20:
                entry_warnings.append(
                    "此 entity 已達 20 條 active entries 上限，"
                    "建議執行 analyze(check_type='quality') 觸發歸納"
                )
            return _unified_response(
                data=serialized,
                warnings=entry_warnings,
                context_bundle=await _build_context_bundle(linked_entity_ids=[entity_id]),
                governance_hints=_build_governance_hints(warnings=entry_warnings),
            )

        else:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason=(
                    f"Unknown collection '{collection}'. "
                    f"Use: entities, documents, protocols, blindspots, relationships, entries"
                ),
            )
    except (ValueError, KeyError, TypeError) as e:
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))


# ===================================================================
# Tool 5: confirm — approve knowledge drafts or task deliveries
# ===================================================================


@mcp.tool(
    tags={"write"},
)
async def confirm(
    collection: str,
    id: str,
    accepted: bool = True,
    rejection_reason: str | None = None,
    mark_stale_entity_ids: list[str] | None = None,
    new_blindspot: dict | None = None,
    entity_entries: list[dict] | None = None,
) -> dict:
    """確認（批准）一個 AI 產出的 draft 或驗收一個已完成的任務。

    ZenOS 核心原則：AI 產出 = draft，人確認 = 生效。
    這個工具統一處理兩種確認：
    1. 知識確認：把 ontology entry 從 draft 標記為「已確認」
    2. 任務驗收：接受或打回一個 status=review 的任務

    使用時機：
    - 確認 ontology 條目 → confirm(collection="entities", id="...")
    - 接受任務交付 → confirm(collection="tasks", id="...", accepted=True)
    - 打回任務重做 → confirm(collection="tasks", id="...", accepted=False,
                             rejection_reason="...")

    不要用這個工具的情境：
    - 更新任務狀態（非驗收） → 用 task(action="update")
    - 修改 ontology 內容 → 用 write

    Args:
        collection: entities/documents/protocols/blindspots/tasks
        id: 項目 ID
        accepted: 任務驗收用。true=通過，false=打回。知識確認忽略此參數。
        rejection_reason: accepted=false 時必填，打回原因
        mark_stale_entity_ids: 任務完成時，標記這些 entity 的相關文件為 stale（僅 tasks 集合生效）
        new_blindspot: 任務完成時發現的新盲點（{description, severity, related_entity_ids, suggested_action}）
        entity_entries: 任務完成時回寫的知識條目 list。
            每個 entry 格式：{entity_id: str, type: "decision"|"insight"|"limitation"|"change"|"context", content: str(1-200字)}
            僅 tasks 集合 + accepted=True 時生效。
    """
    await _ensure_services()
    try:
        if collection == "tasks":
            result = await task_service.confirm_task(
                task_id=id,
                accepted=accepted,
                rejection_reason=rejection_reason,
                mark_stale_entity_ids=mark_stale_entity_ids,
                new_blindspot=new_blindspot,
                updated_by=((_current_partner.get() or {}).get("id")),
                entity_entries=entity_entries,
            )

            # Write entity entries (knowledge feedback loop) — only when accepted
            if accepted and entity_entries and entry_repo is not None:
                partner_ctx = _current_partner.get() or {}
                pid = partner_ctx.get("id", "")
                partner_department = str(
                    partner_ctx.get("department") or current_partner_department.get() or "all"
                )
                valid_entry_types = {"decision", "insight", "limitation", "change", "context"}
                for entry_data in entity_entries:
                    entity_id = entry_data.get("entity_id")
                    if not entity_id:
                        continue
                    content = entry_data.get("content", "")
                    if not content or len(content) > 200:
                        continue
                    entry_type = entry_data.get("type", "insight")
                    if entry_type not in valid_entry_types:
                        entry_type = "insight"
                    entry = EntityEntry(
                        id=_new_id(),
                        partner_id=pid,
                        entity_id=entity_id,
                        type=entry_type,
                        content=content,
                        department=partner_department,
                        source_task_id=id,
                    )
                    await entry_repo.create(entry)
            task_data = await _enrich_task_result(result.task)
            if result.cascade_updates:
                task_data["cascadeUpdates"] = [
                    {"taskId": c.task_id, "change": c.change, "reason": c.reason}
                    for c in result.cascade_updates
                ]
            cascade_suggestions = [
                {
                    "id": c.task_id,
                    "title": "follow-up task updated by cascade",
                    "reason": c.reason,
                }
                for c in (result.cascade_updates or [])
            ]
            context_bundle = await _build_context_bundle(
                linked_entity_ids=[e.get("id") for e in task_data.get("linked_entities", []) if isinstance(e, dict)]
                or [e for e in getattr(result.task, "linked_entities", []) if isinstance(e, str)],
                blindspot_id=getattr(result.task, "linked_blindspot", None),
            )
            _audit_log(
                event_type="task.confirm",
                target={"collection": collection, "id": id},
                changes={
                    "accepted": accepted,
                    "rejection_reason": rejection_reason,
                    "mark_stale_entity_ids": mark_stale_entity_ids or [],
                    "new_blindspot": new_blindspot or {},
                    "entity_entries": entity_entries or [],
                },
            )
            return _unified_response(
                data=task_data,
                suggestions=cascade_suggestions,
                context_bundle=context_bundle,
                governance_hints=_build_governance_hints(
                    suggested_follow_up_tasks=cascade_suggestions,
                    suggested_entity_updates=getattr(result, "suggested_entity_updates", None) or [],
                ),
            )
        else:
            result = await ontology_service.confirm(collection, id)
            confirm_data = dict(result) if isinstance(result, dict) else result
            _audit_log(
                event_type="ontology.confirm",
                target={"collection": collection, "id": id},
                changes={"accepted": accepted},
            )
            return _unified_response(
                data=confirm_data,
                context_bundle=await _build_context_bundle(
                    linked_entity_ids=[id] if collection == "entities" else []
                ),
                governance_hints=_build_governance_hints(),
            )
    except ValueError as e:
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))


# ===================================================================
# Attachment helpers
# ===================================================================

_VALID_ATTACHMENT_TYPES = {"image", "file", "link"}


def _validate_attachments(
    attachments: list[dict],
    partner_id: str | None,
    existing_attachments: list[dict] | None = None,
) -> list[dict] | dict:
    """Validate and normalize attachment items.

    Args:
        attachments: Attachment items from caller.
        partner_id: Authenticated partner ID for uploaded_by.
        existing_attachments: Current attachments from DB; server-side fields
            (gcs_path, content_type, uploaded, created_at) are merged back so
            callers don't need to round-trip them.

    Returns:
        A list of validated attachments, or an error dict.
    """
    validated = []
    for att in attachments:
        att_type = att.get("type", "file")
        if att_type not in _VALID_ATTACHMENT_TYPES:
            return {
                "error": "INVALID_INPUT",
                "message": f"Invalid attachment type '{att_type}'. Must be one of: {', '.join(_VALID_ATTACHMENT_TYPES)}",
            }
        if att_type == "link":
            if not att.get("url"):
                return {"error": "INVALID_INPUT", "message": "Link attachment requires 'url' field"}
            item = {
                "id": att.get("id") or uuid.uuid4().hex,
                "type": "link",
                "url": att["url"],
                "filename": att.get("filename", att["url"]),
                "description": att.get("description", ""),
                "uploaded_by": partner_id or "",
                "created_at": att.get("created_at") or datetime.now(timezone.utc).isoformat(),
            }
        else:
            # image or file: must have attachment_id from prior upload
            if not att.get("attachment_id") and not att.get("id"):
                return {
                    "error": "INVALID_INPUT",
                    "message": f"'{att_type}' attachment requires 'attachment_id' (from upload_attachment)",
                }
            # Start from caller's data
            item = dict(att)
            if "attachment_id" in item and "id" not in item:
                item["id"] = item.pop("attachment_id")

            # Merge back server-side fields from existing attachment
            if existing_attachments:
                existing = next(
                    (a for a in existing_attachments if a.get("id") == item.get("id")), None
                )
                if existing:
                    for key in ("gcs_path", "content_type", "uploaded", "created_at"):
                        if key not in item and key in existing:
                            item[key] = existing[key]

            # Normalize: accept mime_type as alias for content_type
            if "mime_type" in item and "content_type" not in item:
                item["content_type"] = item.pop("mime_type")

            item["uploaded_by"] = partner_id or item.get("uploaded_by", "")
        validated.append(item)
    return validated


def _cleanup_removed_attachments(
    old_attachments: list[dict], new_attachments: list[dict],
) -> None:
    """Delete GCS blobs for attachments removed during update (best-effort)."""
    new_ids = {a.get("id") for a in new_attachments}
    for old in old_attachments:
        if old.get("id") not in new_ids and old.get("gcs_path"):
            try:
                from zenos.infrastructure.gcs_client import delete_blob, get_default_bucket
                delete_blob(get_default_bucket(), old["gcs_path"])
            except Exception:
                logger.warning("Failed to cleanup attachment %s", old.get("id"), exc_info=True)


def _add_proxy_urls(attachments: list[dict]) -> list[dict]:
    """Add proxy_url to attachment items that have a gcs_path."""
    result = []
    for att in attachments:
        att_copy = dict(att)
        if att_copy.get("gcs_path"):
            att_copy["proxy_url"] = f"/attachments/{att_copy['id']}"
        result.append(att_copy)
    return result


# ===================================================================
# Tool 6: task — create, update, and list action items
# ===================================================================


async def _task_handler(
    action: str,
    title: str | None = None,
    created_by: str | None = None,
    id: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    linked_entities: list[str] | None = None,
    linked_protocol: str | None = None,
    linked_blindspot: str | None = None,
    source_type: str | None = None,
    source_metadata: dict | None = None,
    created_via_agent: bool | None = None,
    agent_name: str | None = None,
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    acceptance_criteria: list[str] | None = None,
    result: str | None = None,
    project: str | None = None,
    assignee_role_id: str | None = None,
    plan_id: str | None = None,
    plan_order: int | None = None,
    depends_on_task_ids: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    """Core task handler logic — extracted for testability.

    Called by the ``task`` MCP tool wrapper. Tests import this function
    directly to avoid calling a ``FunctionTool`` object.
    """
    def _looks_like_markdown(text: str) -> bool:
        markers = ("# ", "## ", "- ", "* ", "1. ", "|", "```", "**", "[", "](")
        return any(m in text for m in markers)

    def _normalize_description_to_markdown(raw: str | None) -> str:
        text = (raw or "").strip()
        if not text:
            return ""
        if _looks_like_markdown(text):
            return text

        lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
        if not lines:
            return ""

        title = lines[0]
        details = lines[1:]
        if not details and len(title) > 24:
            chunks = [seg.strip() for seg in re.split(r"[。；;]\s*", title) if seg.strip()]
            if len(chunks) > 1:
                title = chunks[0]
                details = chunks[1:]

        md_lines = [f"**需求摘要**：{title}"]
        if details:
            md_lines.append("")
            md_lines.append("**補充資訊**")
            md_lines.extend(f"- {d}" for d in details)
        return "\n".join(md_lines)

    def _merge_actor_metadata(meta: dict | None, partner_ctx: dict | None) -> dict:
        merged = dict(meta or {})
        via_agent = True if created_via_agent is None else bool(created_via_agent)
        merged["created_via_agent"] = via_agent
        if agent_name:
            merged["agent_name"] = agent_name
        elif via_agent and "agent_name" not in merged:
            merged["agent_name"] = "agent"
        if partner_ctx and partner_ctx.get("id"):
            merged["actor_partner_id"] = partner_ctx["id"]
        return merged

    def _normalize_str_list(value: list[str] | str | None, field: str) -> list[str] | dict:  # dict = _unified_response(status="rejected")
        if value is None:
            return []
        if isinstance(value, list):
            if not all(isinstance(v, str) for v in value):
                return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str]")
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            # Accept JSON array string for backward compatibility.
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str] or JSON array string")
                if not isinstance(parsed, list) or not all(isinstance(v, str) for v in parsed):
                    return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str]")
                return parsed
            return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str], not plain string")
        return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str]")

    try:
        # Resolve partner context once — used for auto-filling created_by and project
        partner = _current_partner.get()
        partner_default_project = partner.get("defaultProject", "") if partner else ""

        if action == "create":
            if not title:
                return _unified_response(status="rejected", data={}, rejection_reason="title is required for create")
            # In MCP context, creator identity must follow the authenticated
            # partner bound to the API key, not arbitrary caller input.
            if partner and partner.get("id"):
                created_by = partner.get("id")
            elif not created_by:
                # Backward-compat fallback for non-MCP/internal callers.
                created_by = None
            if not created_by:
                return _unified_response(status="rejected", data={}, rejection_reason="created_by is required for create")

            # Auto-fill project from partner's default_project if caller omits it
            effective_project = project or partner_default_project

            # Parse due_date string to datetime
            parsed_due = None
            if due_date:
                try:
                    parsed_due = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return _unified_response(status="rejected", data={}, rejection_reason=f"Invalid due_date format: {due_date}")

            normalized_description = _normalize_description_to_markdown(description)
            normalized_linked_entities = _normalize_str_list(linked_entities, "linked_entities")
            if isinstance(normalized_linked_entities, dict):
                return normalized_linked_entities
            normalized_blocked_by = _normalize_str_list(blocked_by, "blocked_by")
            if isinstance(normalized_blocked_by, dict):
                return normalized_blocked_by
            normalized_acceptance_criteria = _normalize_str_list(acceptance_criteria, "acceptance_criteria")
            if isinstance(normalized_acceptance_criteria, dict):
                return normalized_acceptance_criteria
            normalized_depends_on = _normalize_str_list(depends_on_task_ids, "depends_on_task_ids")
            if isinstance(normalized_depends_on, dict):
                return normalized_depends_on

            data = {
                "title": title,
                "created_by": created_by,
                "updated_by": created_by,
                "description": normalized_description,
                "assignee": assignee,
                "priority": priority,
                "status": status or "todo",
                "linked_entities": normalized_linked_entities,
                "linked_protocol": linked_protocol,
                "linked_blindspot": linked_blindspot,
                "source_type": source_type or "",
                "source_metadata": _merge_actor_metadata(source_metadata, partner),
                "due_date": parsed_due,
                "blocked_by": normalized_blocked_by,
                "blocked_reason": blocked_reason,
                "acceptance_criteria": normalized_acceptance_criteria,
                "project": effective_project,
                "assignee_role_id": assignee_role_id,
                "plan_id": plan_id,
                "plan_order": plan_order,
                "depends_on_task_ids": normalized_depends_on,
            }

            # Validate and process attachments
            if attachments:
                validated = _validate_attachments(attachments, (partner or {}).get("id"))
                if isinstance(validated, dict) and "error" in validated:
                    return validated
                data["attachments"] = validated

            if task_service is None:
                await _ensure_services()
            task_result = await task_service.create_task(data)
            task_data = await _enrich_task_result(task_result.task)
            _audit_log(
                event_type="task.create",
                target={"collection": "tasks", "id": task_data.get("id")},
                changes={"input": data},
            )
            create_warnings: list[str] = []
            if not task_result.task.linked_entities:
                create_warnings.append(
                    "linked_entities 為空：任務缺少 ontology context，governance_hints 將無法產生有效建議"
                )
            if not effective_project:
                create_warnings.append(
                    "未指定 project：票已建立但無法被 search(project=...) 過濾找到，建議傳入 project 參數（如 'zenos'）"
                )
            return _unified_response(data=task_data, warnings=create_warnings)

        elif action == "update":
            if not id:
                return _unified_response(status="rejected", data={}, rejection_reason="id is required for update")

            updates: dict = {}
            if status is not None:
                updates["status"] = status
            actor_id = (partner or {}).get("id")
            if actor_id:
                updates["updated_by"] = actor_id
            if assignee is not None:
                updates["assignee"] = assignee
            if priority is not None:
                updates["priority"] = priority
            if description is not None:
                updates["description"] = description
            if blocked_reason is not None:
                updates["blocked_reason"] = blocked_reason
            if result is not None:
                updates["result"] = result
            if blocked_by is not None:
                normalized_blocked_by = _normalize_str_list(blocked_by, "blocked_by")
                if isinstance(normalized_blocked_by, dict):
                    return normalized_blocked_by
                updates["blocked_by"] = normalized_blocked_by
            if source_metadata is not None:
                updates["source_metadata"] = source_metadata
            if acceptance_criteria is not None:
                normalized_acceptance_criteria = _normalize_str_list(
                    acceptance_criteria, "acceptance_criteria"
                )
                if isinstance(normalized_acceptance_criteria, dict):
                    return normalized_acceptance_criteria
                updates["acceptance_criteria"] = normalized_acceptance_criteria
            if due_date is not None:
                try:
                    updates["due_date"] = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return _unified_response(status="rejected", data={}, rejection_reason=f"Invalid due_date: {due_date}")
            if plan_id is not None:
                updates["plan_id"] = plan_id
            if plan_order is not None:
                updates["plan_order"] = plan_order
            if depends_on_task_ids is not None:
                normalized_depends_on = _normalize_str_list(
                    depends_on_task_ids, "depends_on_task_ids"
                )
                if isinstance(normalized_depends_on, dict):
                    return normalized_depends_on
                updates["depends_on_task_ids"] = normalized_depends_on

            # Attachments: full replacement with GCS cleanup for removed items
            if attachments is not None:
                # Fetch existing task first so we can merge server-side fields
                if task_service is None:
                    await _ensure_services()
                old_task = await task_service._tasks.get_by_id(id)
                existing_atts = old_task.attachments if old_task else None

                validated = _validate_attachments(
                    attachments, (partner or {}).get("id"), existing_attachments=existing_atts
                )
                if isinstance(validated, dict) and "error" in validated:
                    return validated
                updates["attachments"] = validated

                # Best-effort cleanup of removed GCS blobs
                if old_task:
                    _cleanup_removed_attachments(old_task.attachments, validated)

            if task_service is None:
                await _ensure_services()
            task_result = await task_service.update_task(id, updates)
            task_data = await _enrich_task_result(task_result.task)
            if task_result.cascade_updates:
                task_data["cascadeUpdates"] = [
                    {"taskId": c.task_id, "change": c.change, "reason": c.reason}
                    for c in task_result.cascade_updates
                ]
            cascade_suggestions = [
                {
                    "id": c.task_id,
                    "title": "follow-up task updated by cascade",
                    "reason": c.reason,
                }
                for c in (task_result.cascade_updates or [])
            ]
            _audit_log(
                event_type="task.update",
                target={"collection": "tasks", "id": id},
                changes={"updates": updates},
            )
            return _unified_response(
                data=task_data,
                suggestions=cascade_suggestions,
                governance_hints=_build_governance_hints(
                    suggested_follow_up_tasks=cascade_suggestions,
                ),
            )

        else:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason=f"Unknown action '{action}'. Use: create, update",
            )
    except ValueError as e:
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))


@mcp.tool(
    tags={"write"},
)
async def task(
    action: str,  # "create" | "update"
    title: str | None = None,
    created_by: str | None = None,
    id: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    linked_entities: list[str] | None = None,
    linked_protocol: str | None = None,
    linked_blindspot: str | None = None,
    source_type: str | None = None,
    source_metadata: dict | None = None,
    created_via_agent: bool | None = None,
    agent_name: str | None = None,
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    acceptance_criteria: list[str] | None = None,
    result: str | None = None,
    project: str | None = None,
    assignee_role_id: str | None = None,
    plan_id: str | None = None,
    plan_order: int | None = None,
    depends_on_task_ids: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    """管理知識驅動的行動項目（Action Layer）。

    任務是 ontology 的 output 路徑——從知識洞察產生的具體行動。
    每個任務透過 linked_entities/linked_blindspot 連結回 ontology，
    讓收到任務的人/agent 自動獲得相關 context。

    使用時機：
    - 建任務 → action="create"（必填：title；created_by 由 server 依 API key context 寫入）
    - 改狀態 → action="update"（必填：id。改 status/assignee/priority 等）
    - 列任務 → 不要用這個，用 search(collection="tasks") 更靈活

    狀態流：todo → in_progress → review → done
            任何活躍狀態可 → cancelled。
    注意：不能用 update 把 status 改成 done（必須走 confirm 驗收流程）。
    補充限制：
    - create 時初始 status 只能是 todo
    - update 到 review 時，result 為必填（SQL schema 強制）
    - blocked_by 可記錄依賴，但不再使用 blocked 狀態欄
    - linked_protocol / linked_blindspot / assignee_role_id / linked_entities 會受資料庫外鍵限制，ID 必須存在於同租戶資料中
    - task 屬於某個 plan 時，建議帶 plan_id 與 plan_order，讓 agent 能按順序執行

    不要用這個工具的情境：
    - 查任務列表 → 用 search(collection="tasks")
    - 驗收任務 → 用 confirm(collection="tasks")

    Args:
        action: "create" 或 "update"
        title: 任務標題，動詞開頭（create 必填）
        created_by: 建立者 partner ID（create 時由 server 依 API key context 覆寫）
        id: 任務 ID（update 必填）
        description: 任務描述
        assignee: 被指派者 UID（具體的人或 agent）
        priority: critical/high/medium/low（不傳時 AI 自動推薦）
        status: create 時只能 todo；update 時需通過合法性驗證
        linked_entities: 關聯的 entity IDs，型別必須是 list[str]（不可傳單一字串）
        linked_protocol: 關聯的 Protocol ID
        linked_blindspot: 觸發的 blindspot ID
        source_type: 來源類型（如 "chat"、"doc"、"repo"、"spec"、"review"）
        source_metadata: 來源追溯與外部同步資訊（可選，dict）。
            ⚠️ 這是「來源追溯」用途，不是放附件的地方。附件請用 attachments 參數。
            推薦結構：
            {
              "provenance": [
                {
                  "type": "chat|doc|repo",
                  "label": "來源標題",
                  "snippet": "對話或代碼原文片段"
                }
              ]
            }
        created_via_agent: 是否由 agent 建立。預設 true（MCP 路徑）。
                           ⚠️ 此欄位與 agent_name 會合併寫入 source_metadata.agent_info。
        agent_name: agent 名稱（如 "architect-agent"）。created_via_agent=true 時建議帶入。
                    ⚠️ 此值不會獨立存為 task 欄位，而是合併寫入 source_metadata.agent_info。
        due_date: 到期日 ISO-8601（如 "2026-03-29"）
        blocked_by: 阻塞此任務的 task IDs，型別必須是 list[str]
        blocked_reason: 可選的依賴/阻塞說明（不再綁定 blocked 狀態）
        acceptance_criteria: 驗收條件列表，型別必須是 list[str]
        result: 完成產出描述（status=review 時必填）
        project: 所屬專案識別碼（如 "zenos"、"paceriz"），用於任務隔離。
            未傳時自動使用 partner 的 default_project，確保任務不會跨專案污染。
        assignee_role_id: 指向 role entity 的 ID（可選），表達「這個任務需要什麼角色」而非「指派給誰」。
                          get 時會展開為角色的 name/summary context。
        plan_id: 任務群組 ID（PLAN 層識別）
        plan_order: 任務在 plan 內順序（>=1）
        depends_on_task_ids: 前置依賴 task IDs（可選，型別必須是 list[str]）
        attachments: 附件陣列（可選）。create 時傳入初始附件；update 時為全量覆寫。
            ⚠️ 附件必須用此參數，不能放在 source_metadata 裡。
            每個項目需有 type ("image"/"file"/"link")。
            - link 類型：需有 url 和 title。範例：{"type": "link", "url": "https://...", "title": "蝦皮旗艦館"}
            - image/file 類型：先呼叫 upload_attachment 取得 signed_put_url，用 curl PUT 上傳檔案後，再帶 attachment_id。
              範例：{"type": "image", "id": "<attachment_id>", "filename": "photo.jpg", "content_type": "image/jpeg"}
            update 時為全量覆寫——傳入的陣列會取代所有既有附件。

    系統欄位：
        updated_by: 不接受 caller 直接傳入；由 server 依當次 actor context 自動寫入
    """
    return await _task_handler(
        action=action,
        title=title,
        created_by=created_by,
        id=id,
        description=description,
        assignee=assignee,
        priority=priority,
        status=status,
        linked_entities=linked_entities,
        linked_protocol=linked_protocol,
        linked_blindspot=linked_blindspot,
        source_type=source_type,
        source_metadata=source_metadata,
        created_via_agent=created_via_agent,
        agent_name=agent_name,
        due_date=due_date,
        blocked_by=blocked_by,
        blocked_reason=blocked_reason,
        acceptance_criteria=acceptance_criteria,
        result=result,
        project=project,
        assignee_role_id=assignee_role_id,
        plan_id=plan_id,
        plan_order=plan_order,
        depends_on_task_ids=depends_on_task_ids,
        attachments=attachments,
    )


# ===================================================================
# Tool 6b: upload_attachment — upload file to task
# ===================================================================


@mcp.tool(
    tags={"write"},
)
async def upload_attachment(
    task_id: str,
    filename: str,
    content_type: str,
    description: str | None = None,
) -> dict:
    """上傳附件到任務（signed URL 模式）。

    流程：
    1. 呼叫此工具 → 取得 signed_put_url（15 分鐘有效）
    2. 用 Bash 執行 curl 上傳檔案到 signed URL：
       curl -X PUT -H "Content-Type: <content_type>" --data-binary @/path/to/file "<signed_put_url>"
    3. 上傳完成後，附件自動關聯到任務，可在 Dashboard 查看

    回傳 attachment_id、proxy_url、signed_put_url。

    Args:
        task_id: 目標任務 ID
        filename: 原始檔名
        content_type: MIME type（如 "image/png", "application/pdf"）
        description: 附件描述（可選）
    """
    try:
        partner = _current_partner.get()
        if not partner or not partner.get("id"):
            return {"error": "UNAUTHORIZED", "message": "Authentication required"}

        await _ensure_services()

        # Validate task exists and belongs to current partner
        task_obj = await task_service._tasks.get_by_id(task_id)
        if task_obj is None:
            return {"error": "NOT_FOUND", "message": f"Task '{task_id}' not found"}

        from zenos.infrastructure.gcs_client import (
            get_default_bucket,
            generate_signed_put_url,
        )

        attachment_id = uuid.uuid4().hex
        gcs_path = f"tasks/{task_id}/attachments/{attachment_id}/{filename}"
        bucket_name = get_default_bucket()

        signed_put_url = generate_signed_put_url(bucket_name, gcs_path, content_type)

        attachment = {
            "id": attachment_id,
            "filename": filename,
            "content_type": content_type,
            "gcs_path": gcs_path,
            "uploaded_by": partner["id"],
            "uploaded": False,
            "description": description or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Append to task's attachments
        task_obj.attachments.append(attachment)
        await task_service._tasks.upsert(task_obj)

        result = {
            "attachment_id": attachment_id,
            "proxy_url": f"/attachments/{attachment_id}",
            "signed_put_url": signed_put_url,
        }

        _audit_log(
            event_type="attachment.upload",
            target={"task_id": task_id, "attachment_id": attachment_id},
            changes={"filename": filename, "content_type": content_type, "mode": "signed_url"},
        )
        return result

    except ValueError as e:
        return {"error": "INVALID_INPUT", "message": str(e)}
    except Exception as e:
        logger.exception("upload_attachment failed")
        return {"error": "INTERNAL_ERROR", "message": str(e)}


# ===================================================================
# Tool 7: analyze — governance health checks
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def analyze(
    check_type: str = "all",
) -> dict:
    """執行 ontology 治理健康檢查。

    分析整個知識庫的品質、新鮮度和潛在盲點。
    結果可用來發現問題、建立改善任務。

    使用時機：
    - 定期健檢 → analyze(check_type="all")
    - 只看品質分數 → analyze(check_type="quality")
    - 找過時內容 → analyze(check_type="staleness")
    - 推斷盲點 → analyze(check_type="blindspot")
    - 只看 impacts 斷鏈 → analyze(check_type="impacts")
    - 只看文件一致性 → analyze(check_type="document_consistency")
    - 分析能見度風險 → analyze(check_type="permission_risk")
    - 找無效文件條目 → analyze(check_type="invalid_documents")
    - 清理孤立關聯 → analyze(check_type="orphaned_relationships")

    不要用這個工具的情境：
    - 搜尋或列出條目 → 用 search
    - 更新 ontology 內容 → 用 write

    Args:
        check_type: "all" / "quality" / "staleness" / "blindspot" / "impacts" /
                    "document_consistency" / "permission_risk" / "invalid_documents" /
                    "orphaned_relationships"

    Returns:
        dict — 各 check_type 對應的子結構：
        - quality: {score, total_entities, issues[{entity_id, entity_name, defect}], ...}
                   含 L2 治理補充欄位（l2_impacts_repairs, l2_backfill_proposals, 等）
        - staleness: {warnings[{...}], count, document_consistency_warnings, document_consistency_count}
        - blindspots: {blindspots[{...}], count, task_signal_suggestions[{...}], task_signal_count}
        - permission_risk: {isolation_score, overexposure_score, warnings[{...}], summary}
        - impacts: quality.l2_impacts_validity（掛在 quality 子結構下）
        - document_consistency: {document_consistency_warnings[{...}], document_consistency_count}
        - invalid_documents: {items[{entity_id, current_title, source_uri, linked_entity_ids,
                             proposed_title, action}], count}
        - kpis: {total_items, unconfirmed_items, unconfirmed_ratio, blindspot_total,
                 duplicate_blindspots, duplicate_blindspot_rate, median_confirm_latency_days,
                 active_l2_missing_impacts, weekly_review_required}（check_type="all" 時包含）
    """
    await _ensure_services()
    results: dict = {}
    l2_repairs: list[dict] = []

    def _is_concrete_impacts_description(description: str) -> bool:
        desc = (description or "").strip()
        if not desc:
            return False
        if "→" in desc:
            left, right = desc.split("→", 1)
            return bool(left.strip()) and bool(right.strip())
        if "->" in desc:
            left, right = desc.split("->", 1)
            return bool(left.strip()) and bool(right.strip())
        return False

    async def _infer_l2_repairs() -> list[dict]:
        all_entities = await ontology_service._entities.list_all()
        active_modules = [
            e for e in all_entities
            if e.type == "module" and e.status == "active" and e.id
        ]
        draft_modules = [
            e for e in all_entities
            if e.type == "module" and e.status == "draft" and e.id
        ]
        if not active_modules and not draft_modules:
            return []

        impact_entity_ids: set[str] = set()
        seen_rel_ids: set[str | None] = set()
        for ent in all_entities:
            if not ent.id:
                continue
            rels = await ontology_service._relationships.list_by_entity(ent.id)
            for rel in rels:
                if rel.id in seen_rel_ids:
                    continue
                seen_rel_ids.add(rel.id)
                if rel.type != "impacts":
                    continue
                if not _is_concrete_impacts_description(rel.description):
                    continue
                impact_entity_ids.add(rel.source_entity_id)
                impact_entity_ids.add(rel.target_id)

        repairs = []
        for mod in active_modules:
            if mod.id in impact_entity_ids:
                continue
            repairs.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "severity": "red",
                "defect": "active_l2_missing_concrete_impacts",
                "repair_options": [
                    "補 impacts（A 改了什麼→B 的什麼要跟著看）",
                    "降級為 L3",
                    "重新切粒度",
                ],
            })
        for mod in draft_modules:
            override = (
                mod.details.get("manual_override_reason")
                if mod.details and isinstance(mod.details, dict)
                else None
            )
            repairs.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "severity": "yellow",
                "defect": "draft_l2_pending_confirmation",
                "manual_override_reason": override,
                "repair_options": [
                    "補 impacts 後 confirm",
                    "降級為 L3",
                ],
            })
        return repairs

    async def _check_entry_saturation() -> list[dict]:
        """Detect saturated entities (>= 20 active entries) and produce consolidation proposals."""
        if entry_repo is None or _governance_ai is None:
            return []
        saturated = await entry_repo.list_saturated_entities(threshold=20)
        if not saturated:
            return []

        proposals = []
        for item in saturated:
            entity_id = item["entity_id"]
            entity_name = item["entity_name"]
            active_count = item["active_count"]
            entries = await entry_repo.list_by_entity(entity_id, status="active")
            entry_dicts = [
                {"id": e.id, "type": e.type, "content": e.content}
                for e in entries
            ]
            proposal = _governance_ai.consolidate_entries(entity_id, entity_name, entry_dicts)
            proposals.append({
                "entity_id": entity_id,
                "entity_name": entity_name,
                "active_count": active_count,
                "consolidation_proposal": proposal.model_dump() if proposal else None,
            })
        return proposals

    if check_type in ("all", "quality"):
        # Gather entry counts per entity for sparsity check
        _entries_by_entity: dict[str, int] | None = None
        if entry_repo is not None:
            try:
                all_entities_for_sparsity = await ontology_service._entities.list_all()
                active_module_ids = [
                    e.id for e in all_entities_for_sparsity
                    if e.type == "module" and e.status == "active" and e.id
                ]
                _entries_by_entity = {}
                for eid in active_module_ids:
                    try:
                        cnt = await entry_repo.count_active_by_entity(eid)
                        _entries_by_entity[eid] = cnt
                    except Exception:
                        _entries_by_entity[eid] = 0
            except Exception:
                logger.warning("Entry sparsity data collection failed", exc_info=True)

        report = await governance_service.run_quality_check(entries_by_entity=_entries_by_entity)
        results["quality"] = _serialize(report)
        try:
            l2_repairs = await _infer_l2_repairs()
            active_repairs = [r for r in l2_repairs if r.get("defect") == "active_l2_missing_concrete_impacts"]
            draft_repairs = [r for r in l2_repairs if r.get("defect") == "draft_l2_pending_confirmation"]
            results["quality"]["active_l2_missing_impacts"] = len(active_repairs)
            results["quality"]["draft_l2_pending_confirmation"] = len(draft_repairs)
            if l2_repairs:
                results["quality"]["l2_impacts_repairs"] = l2_repairs
        except Exception:
            # Repair suggestion is additive and should not break quality report.
            logger.warning("L2 repairs inference failed", exc_info=True)
        try:
            backfill = await governance_service.infer_l2_backfill_proposals()
            results["quality"]["l2_backfill_proposals"] = backfill
            results["quality"]["l2_backfill_count"] = len(backfill)
        except Exception:
            logger.warning("L2 backfill proposals failed", exc_info=True)

        # L2 governance: impacts target validity
        try:
            validity_report = await governance_service.check_impacts_target_validity()
            results["quality"]["l2_impacts_validity"] = validity_report
        except Exception:
            logger.warning("L2 impacts target validity check failed", exc_info=True)

        # P0-2: quality correction priority
        try:
            priority_report = await governance_service.run_quality_correction_priority()
            results["quality"]["quality_correction_priority"] = priority_report
        except Exception:
            logger.warning("Quality correction priority failed", exc_info=True)

        # L2 governance: stale L2 downstream (entity part from domain; task part here)
        try:
            downstream_entities = await governance_service.find_stale_l2_downstream_entities()
            # Enrich with open tasks at interface layer (task_repo available here)
            _open_statuses = {"todo", "in_progress", "review"}
            all_tasks = await task_service.list_tasks(limit=500)
            for entry in downstream_entities:
                mod_id = entry["stale_module_id"]
                affected_tasks = [
                    {"id": t.id, "title": t.title, "status": t.status}
                    for t in all_tasks
                    if mod_id in (t.linked_entities or [])
                    and t.status in _open_statuses
                ]
                entry["affected_tasks"] = affected_tasks
                entry["suggested_actions"] = [
                    "重新掛載到 active L2",
                    "更新引用",
                    "降級為 sources",
                ]
            results["quality"]["l2_stale_downstream"] = downstream_entities
        except Exception:
            logger.warning("L2 stale downstream check failed", exc_info=True)

        # L2 governance: reverse impacts check
        try:
            reverse_impacts = await governance_service.check_reverse_impacts()
            results["quality"]["l2_reverse_impacts"] = reverse_impacts
        except Exception:
            logger.warning("L2 reverse impacts check failed", exc_info=True)

        # L2 governance: review overdue check
        try:
            overdue = await governance_service.check_governance_review_overdue()
            results["quality"]["l2_governance_review_overdue"] = overdue
            results["quality"]["l2_review_overdue_count"] = len(overdue)
        except Exception:
            logger.warning("L2 governance review overdue check failed", exc_info=True)

        # Entry saturation detection
        try:
            entry_saturation = await _check_entry_saturation()
            results["quality"]["entry_saturation"] = entry_saturation
            results["quality"]["entry_saturation_count"] = len(entry_saturation)
        except Exception:
            logger.warning("Entry saturation check failed", exc_info=True)

        # Search-unused signals
        try:
            if _tool_event_repo is not None:
                partner_id = _current_partner_id.get() or ""
                all_entities_for_signals = await ontology_service._entities.list_all()
                usage_stats = await _tool_event_repo.get_entity_usage_stats(partner_id, days=30)
                search_unused = compute_search_unused_signals(usage_stats, all_entities_for_signals)
                if search_unused:
                    results["quality"]["search_unused_signals"] = search_unused
        except Exception:
            logger.warning("Search unused signals check failed", exc_info=True)

        # Summary quality flags
        try:
            all_entities_for_quality = await ontology_service._entities.list_all()
            l2_entities = [
                e for e in all_entities_for_quality
                if e.type == "module" and e.status in ("active", "draft") and e.id
            ]
            summary_flags = []
            for e in l2_entities:
                quality = score_summary_quality(e.summary or "", e.type)
                if quality["quality_score"] != "good":
                    summary_flags.append({
                        "entity_id": e.id,
                        "entity_name": e.name,
                        **quality,
                    })
            if summary_flags:
                results["quality"]["summary_quality_flags"] = summary_flags
        except Exception:
            logger.warning("Summary quality flags check failed", exc_info=True)

    if check_type in ("all", "staleness", "document_consistency"):
        staleness_result = await governance_service.run_staleness_check()
        staleness_warnings = staleness_result["warnings"]
        doc_consistency_warnings = staleness_result["document_consistency_warnings"]
        if check_type != "document_consistency":
            results["staleness"] = {
                "warnings": [_serialize(w) for w in staleness_warnings],
                "count": len(staleness_warnings),
                "document_consistency_warnings": doc_consistency_warnings,
                "document_consistency_count": len(doc_consistency_warnings),
            }
        if check_type == "document_consistency":
            results["document_consistency"] = {
                "document_consistency_warnings": doc_consistency_warnings,
                "document_consistency_count": len(doc_consistency_warnings),
            }

    if check_type in ("all", "blindspot"):
        blindspots = await governance_service.run_blindspot_analysis()
        results["blindspots"] = {
            "blindspots": [_serialize(b) for b in blindspots],
            "count": len(blindspots),
        }
        try:
            task_signal_suggestions = await governance_service.infer_blindspots_from_tasks()
            results["blindspots"]["task_signal_suggestions"] = task_signal_suggestions
            results["blindspots"]["task_signal_count"] = len(task_signal_suggestions)
        except Exception:
            logger.warning("Task signal blindspot inference failed", exc_info=True)
            results["blindspots"]["task_signal_suggestions"] = []
            results["blindspots"]["task_signal_count"] = 0

    if check_type == "impacts":
        try:
            validity_report = await governance_service.check_impacts_target_validity()
            results.setdefault("quality", {})["l2_impacts_validity"] = validity_report
        except Exception:
            logger.warning("Impacts target validity check failed (impacts check_type)", exc_info=True)

    if check_type in ("all", "permission_risk"):
        from zenos.application.permission_risk_service import PermissionRiskService
        risk_svc = PermissionRiskService(
            entity_repo=ontology_service._entities,
            task_repo=task_service._tasks,
        )
        results["permission_risk"] = await risk_svc.analyze_risk()

    if check_type in ("all", "invalid_documents"):
        all_doc_entities = await ontology_service._entities.list_all(type_filter="document")
        invalid_docs = detect_invalid_document_titles(all_doc_entities)
        # Task 40: enrich each item with proposed_title and action
        from zenos.domain.source_uri_validator import GITHUB_BLOB_PATTERN
        for doc in invalid_docs:
            source_uri = doc["source_uri"]
            if source_uri and GITHUB_BLOB_PATTERN.match(source_uri):
                try:
                    from zenos.infrastructure.github_adapter import parse_github_url
                    _, _, path, _ = parse_github_url(source_uri)
                    proposed_title = path.rsplit("/", 1)[-1]
                except Exception:
                    proposed_title = None
                doc["proposed_title"] = proposed_title
                doc["action"] = "propose_title"
            elif not source_uri or not source_uri.startswith("http"):
                doc["proposed_title"] = None
                doc["action"] = "auto_archive"
            else:
                doc["proposed_title"] = None
                doc["action"] = "manual_review"
        results["invalid_documents"] = {
            "items": invalid_docs,
            "count": len(invalid_docs),
        }

    if check_type in ("all", "orphaned_relationships"):
        try:
            orphan_result = await ontology_service.remove_orphaned_relationships()
            results["orphaned_relationships"] = orphan_result
        except Exception:
            logger.warning("Orphaned relationships check failed", exc_info=True)

    if not results:
        return {
            "error": "INVALID_INPUT",
            "message": (
                f"Unknown check_type '{check_type}'. "
                "Use: all, quality, staleness, blindspot, impacts, "
                "document_consistency, permission_risk, invalid_documents, "
                "orphaned_relationships"
            ),
        }

    if check_type == "all":
        try:
            # Minimal governance KPI snapshot for ongoing quality tracking.
            all_entities = await ontology_service._entities.list_all()
            non_doc_entities = [e for e in all_entities if e.type != "document"]
            doc_entities = [e for e in all_entities if e.type == "document"]
            legacy_docs = await ontology_service._documents.list_all()
            all_blindspots = await blindspot_repo.list_all()

            protocols = []
            for entity in non_doc_entities:
                if entity.id:
                    proto = await ontology_service._protocols.get_by_entity(entity.id)
                    if proto:
                        protocols.append(proto)

            total_items = (
                len(non_doc_entities)
                + len(doc_entities)
                + len(legacy_docs)
                + len(protocols)
                + len(all_blindspots)
            )
            unconfirmed_items = (
                sum(1 for e in non_doc_entities if not e.confirmed_by_user)
                + sum(1 for d in doc_entities if not d.confirmed_by_user)
                + sum(1 for d in legacy_docs if not d.confirmed_by_user)
                + sum(1 for p in protocols if not p.confirmed_by_user)
                + sum(1 for b in all_blindspots if not b.confirmed_by_user)
            )
            unconfirmed_ratio = (unconfirmed_items / total_items) if total_items else 0.0

            # Duplicate blindspots use semantic signature (description + severity + related + action).
            signature_count: dict[tuple[str, str, tuple[str, ...], str], int] = {}
            for bs in all_blindspots:
                sig = (
                    " ".join(bs.description.strip().lower().split()),
                    bs.severity,
                    tuple(sorted(bs.related_entity_ids)),
                    " ".join(bs.suggested_action.strip().lower().split()),
                )
                signature_count[sig] = signature_count.get(sig, 0) + 1
            duplicate_blindspots = sum(max(0, cnt - 1) for cnt in signature_count.values())
            duplicate_blindspot_rate = (
                duplicate_blindspots / len(all_blindspots) if all_blindspots else 0.0
            )

            # Approximate confirm latency from created_at -> updated_at on confirmed items.
            latencies: list[float] = []
            for item in [*non_doc_entities, *doc_entities, *legacy_docs, *protocols, *all_blindspots]:
                if not getattr(item, "confirmed_by_user", False):
                    continue
                created_at = getattr(item, "created_at", None) or getattr(item, "generated_at", None)
                updated_at = getattr(item, "updated_at", None)
                if created_at and updated_at and updated_at >= created_at:
                    latencies.append((updated_at - created_at).total_seconds() / 86400)
            median_confirm_latency_days = 0.0
            if latencies:
                sorted_days = sorted(latencies)
                mid = len(sorted_days) // 2
                if len(sorted_days) % 2 == 1:
                    median_confirm_latency_days = sorted_days[mid]
                else:
                    median_confirm_latency_days = (sorted_days[mid - 1] + sorted_days[mid]) / 2

            results["kpis"] = {
                "total_items": total_items,
                "unconfirmed_items": unconfirmed_items,
                "unconfirmed_ratio": round(unconfirmed_ratio, 4),
                "blindspot_total": len(all_blindspots),
                "duplicate_blindspots": duplicate_blindspots,
                "duplicate_blindspot_rate": round(duplicate_blindspot_rate, 4),
                "median_confirm_latency_days": round(median_confirm_latency_days, 2),
                "active_l2_missing_impacts": len(l2_repairs),
                "weekly_review_required": (
                    results.get("quality", {}).get("score", 0) < 70
                    or len(l2_repairs) > 0
                ),
            }
            if l2_repairs:
                results["governance_repairs"] = l2_repairs
        except Exception:
            # KPI should be additive; never break main governance checks.
            pass

    return results


# ===================================================================
# Tool: suggest_policy — suggest entity visibility policy
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def suggest_policy(
    entity_id: str,
) -> dict:
    """根據 entity 的內容和位置，建議合適的 visibility。

    使用時機：
    - 在 capture 新 entity 時，不確定要設什麼 visibility
    - 審查現有 entity 的權限是否合適

    Args:
        entity_id: 要建議 policy 的 entity ID

    Returns:
        dict — {entity_id, suggested_visibility, reason, risk_score}
    """
    await _ensure_services()
    from zenos.application.policy_suggestion_service import PolicySuggestionService
    svc = PolicySuggestionService(entity_repo=ontology_service._entities)
    return await svc.suggest(entity_id)


# ===================================================================
# Work Journal tools: journal_write / journal_read
# ===================================================================


@mcp.tool(
    tags={"write"},
)
async def journal_write(
    summary: str,
    project: str | None = None,
    flow_type: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """記錄工作日誌條目。

    使用時機：
    - session 或 flow 結束時呼叫，記錄本次完成的工作、遺留問題、重要決策。
    - 讓下次 session 開始時能快速恢復 context，減少用戶重新補充資訊的需要。

    summary 會自動截斷至 100 字。超過 20 則日誌時，會自動觸發壓縮（舊條目合併為摘要）。

    Args:
        summary: 工作摘要（自動截斷至 100 字）
        project: 相關專案名稱（選填）
        flow_type: 工作類型，例如 feature/bugfix/review/research（選填）
        tags: 標籤列表（選填）

    Returns:
        dict — {id, created_at, compressed: bool}
    """
    import json as _json
    # Coerce tags: agent 有時會傳 JSON 字串而非 list
    if isinstance(tags, str):
        try:
            tags = _json.loads(tags)
        except (_json.JSONDecodeError, ValueError):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

    await _ensure_journal_repo()
    assert _journal_repo is not None
    partner_id = _current_partner_id.get()
    if not partner_id:
        return _unified_response(status="rejected", data={}, rejection_reason="No authenticated partner context")

    # Truncate summary to 100 chars without rejecting
    summary = summary[:100]

    # Auto-fill project from partner context if caller omits it
    _partner = _current_partner.get()
    effective_project = project or (_partner.get("defaultProject", "") if _partner else "") or None

    entry_id = await _journal_repo.create(
        partner_id=partner_id,
        summary=summary,
        project=effective_project,
        flow_type=flow_type,
        tags=tags or [],
    )
    count = await _journal_repo.count(partner_id=partner_id)
    compressed = False
    if count > 20:
        await _compress_journal(partner_id)
        compressed = True

    return _unified_response(
        data={"id": entry_id, "created_at": datetime.now(timezone.utc).isoformat(), "compressed": compressed}
    )


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def journal_read(
    limit: int = 10,
    project: str | None = None,
    flow_type: str | None = None,
) -> dict:
    """讀取近期工作日誌。

    使用時機：
    - session 開始時呼叫，快速回顧近期工作脈絡，取代讓用戶重新補充 context。
    - 了解上次 session 完成了什麼、遺留哪些問題、有哪些重要決策。

    Args:
        limit: 回傳筆數上限（預設 10，最大 50）
        project: 篩選特定專案（選填）
        flow_type: 篩選特定工作類型（選填）

    Returns:
        dict — {entries: [...], count: int, total: int}
        每個 entry 包含：id, created_at, project, flow_type, summary, tags, is_summary
    """
    await _ensure_journal_repo()
    assert _journal_repo is not None
    partner_id = _current_partner_id.get()
    if not partner_id:
        return _unified_response(status="rejected", data={}, rejection_reason="No authenticated partner context")

    limit = max(1, min(limit, 50))

    # Auto-fill project from partner context if caller omits it
    _partner = _current_partner.get()
    effective_project = project or (_partner.get("defaultProject", "") if _partner else "") or None

    entries, total = await _journal_repo.list_recent(
        partner_id=partner_id,
        limit=limit,
        project=effective_project,
        flow_type=flow_type,
    )
    # Convert datetime fields to ISO strings for JSON serialization
    serialized = [
        {**e, "created_at": e["created_at"].isoformat() if hasattr(e["created_at"], "isoformat") else e["created_at"]}
        for e in entries
    ]
    return _unified_response(
        data={"entries": serialized, "count": len(serialized), "total": total}
    )


# ===================================================================
# Tool 8: governance_guide — retrieve governance rules by topic/level
# ===================================================================

_VALID_TOPICS = frozenset(GOVERNANCE_RULES.keys())
_VALID_LEVELS = frozenset({1, 2, 3})


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def governance_guide(
    topic: str,
    level: int = 1,
) -> dict:
    """取得 ZenOS 治理規則指南。

    讓任何 MCP client 按需載入 ZenOS 治理規則，取代 local skill 文件。
    規則分四個主題，三個深度層級。不需要 DB 連線，不需要 partner key。

    使用時機：
    - 開始 capture/write 操作前想確認規則 → governance_guide(topic="entity", level=1)
    - 需要完整建票規則 → governance_guide(topic="task", level=2)
    - 需要含範例的 capture 指南 → governance_guide(topic="capture", level=3)

    Args:
        topic: 規則主題。entity=L2知識節點治理, document=L3文件治理,
               task=任務建票與驗收, capture=知識捕獲分層路由
        level: 深度層級。1=核心摘要(~1k tokens), 2=完整規則(~2-3k),
               3=含範例(~3-5k)。預設 1。

    Returns:
        dict with keys: topic, level, version, content
        On invalid input: {"error": "INVALID_INPUT", "message": "..."}
    """
    if topic not in _VALID_TOPICS:
        return {
            "error": "INVALID_INPUT",
            "message": f"topic 必須是 {sorted(_VALID_TOPICS)} 之一，收到：'{topic}'",
        }
    if level not in _VALID_LEVELS:
        return {
            "error": "INVALID_INPUT",
            "message": f"level 必須是 1/2/3，收到：{level}",
        }

    _topic_versions = {
        "entity": "1.1",
        "document": "1.1",
        "task": "2.0",
        "capture": "1.0",
    }
    return {
        "topic": topic,
        "level": level,
        "version": _topic_versions.get(topic, "1.0"),
        "content": GOVERNANCE_RULES[topic][level],
    }



# ===================================================================
# Batch update sources tool
# ===================================================================


@mcp.tool(
    tags={"write"},
    annotations={"idempotentHint": True},
)
async def batch_update_sources(
    updates: list[dict],
    atomic: bool = False,
) -> dict:
    """批次更新多個 document 的 source URI。

    大範圍文件重構（目錄搬移、rename）後，一次更新所有受影響的 document source URI，
    不需要逐一呼叫 write。

    使用時機：
    - 目錄搬移後修復 broken URI → batch_update_sources(updates=[...])
    - /zenos-sync 偵測到 rename 後套用修正 → batch_update_sources(updates=proposed_fixes, atomic=True)

    不要用這個工具的情境：
    - 更新單一 document 的其他欄位 → 用 write(collection="documents")
    - 建立新 document → 用 write(collection="documents")

    Args:
        updates: 更新清單，每個元素為 {"document_id": "entity-id", "new_uri": "新的 source URI"}。
                 上限 100 筆。
        atomic: false（預設）= 逐筆獨立，partial failure 不阻斷其他更新。
                true = PostgreSQL transaction 包住整批，任一失敗全部回滾。
                用 sync rename 修正時建議 atomic=true。

    Returns:
        {status, data: {updated: [...], not_found: [...], errors: [...]}}
    """
    await _ensure_services()
    try:
        result = await ontology_service.batch_update_document_sources(
            updates, atomic=atomic
        )

        _audit_log(
            event_type="ontology.documents.batch_update_sources",
            target={"collection": "documents", "count": len(updates)},
            changes={"input": updates, "result": result},
        )

        return _unified_response(
            data=result,
            warnings=[],
        )
    except ValueError as exc:
        return _unified_response(
            status="rejected",
            data={},
            rejection_reason=str(exc),
        )
    except Exception as exc:
        return _unified_response(
            status="error",
            data={},
            rejection_reason=f"Unexpected error: {exc}",
        )


# ===================================================================
# Setup tool
# ===================================================================

_VALID_PLATFORMS = frozenset({"claude_code", "claude_web", "codex"})
_VALID_SKILL_SELECTIONS = frozenset({"full", "doc_task", "task_only"})


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def setup(
    platform: str | None = None,
    skill_selection: str = "full",
    skip_overview: bool = False,
) -> dict:
    """安裝或更新 ZenOS setup skill 到用戶的 AI agent 平台。

    用戶完成 MCP 連線後呼叫此 tool，取得安裝 setup skill 的 curl 指令。
    Claude 執行該指令後，再告知用戶執行 /zenos-setup 完成完整安裝。
    支援：Claude Code、Claude Web UI、OpenAI Codex / ChatGPT。

    使用時機：
    - 用戶說「安裝 ZenOS」「設定 ZenOS」「更新 ZenOS」→ setup(platform='claude_code')
    - tool 回傳 curl 指令 → Claude 執行 → 告知用戶執行 /zenos-setup

    不需要用這個工具的情境：
    - MCP 連線設定（取得 API key、填入 MCP server URL）→ 這是前置條件，不在 setup 範圍
    - 查詢 ontology → 用 search 或 get
    - 治理規則查詢 → 用 governance_guide

    Args:
        platform: 目標平台。claude_code / claude_web / codex（含 ChatGPT）。
                  不傳時回傳平台清單，讓 agent 詢問用戶後帶正確值再次呼叫。
        skill_selection: 治理能力組合（claude_code 平台已無作用，保留供其他平台使用）。
        skip_overview: 跳過治理概要說明，適合更新操作（已熟悉 ZenOS 的用戶）。

    Returns:
        platform=None → {"action": "ask_platform", "options": [...]}
        claude_code → {"action": "install_setup_skill", "command": "curl ...", "next_step": "/zenos-setup"}
        claude_web/codex → {"action": "install", "payload": {...}}
        platform invalid → {"error": "unsupported_platform"}
    """
    from zenos.interface.setup_content import get_bundle_version
    from zenos.interface.setup_adapters import (
        build_claude_code_payload,
        build_claude_web_payload,
        build_codex_payload,
    )

    # Step 1：無 platform → 回傳平台清單
    if platform is None:
        bundle_version = get_bundle_version()
        return {
            "action": "ask_platform",
            "bundle_version": bundle_version,
            "question": "你使用哪個 AI agent 平台？",
            "options": [
                {"id": "claude_code", "label": "Claude Code（CLI 或 IDE 擴充套件）"},
                {"id": "claude_web", "label": "Claude Web UI（claude.ai 網頁版）"},
                {"id": "codex", "label": "OpenAI Codex / ChatGPT"},
                {"id": "other", "label": "其他"},
            ],
            "next_step": "呼叫 setup(platform='<id>') 繼續安裝",
        }

    # Step 2：驗證 skill_selection
    if skill_selection not in _VALID_SKILL_SELECTIONS:
        return {
            "error": "invalid_skill_selection",
            "message": "skill_selection 必須是 full / doc_task / task_only",
        }

    # Step 3：依 platform 委派 adapter
    if platform == "claude_code":
        return build_claude_code_payload(skill_selection, skip_overview)
    if platform == "claude_web":
        return build_claude_web_payload(skill_selection, skip_overview)
    if platform == "codex":
        return build_codex_payload(skill_selection, skip_overview)

    # Step 4：不支援的平台
    bundle_version = get_bundle_version()
    return {
        "error": "unsupported_platform",
        "message": "目前不支援此平台，請聯繫 ZenOS 管理員或到 https://github.com/centerseed/zenos 查看最新文件",
        "supported_platforms": sorted(_VALID_PLATFORMS),
        "bundle_version": bundle_version,
    }


# ===================================================================
# Tool: find_gaps — structural gap detection in ontology graph
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def find_gaps(
    gap_type: str = "all",
    scope_product: str | None = None,
) -> dict:
    """找出 ontology 中的結構性缺口——孤立節點、缺少關聯的節點。

    這是 search/get 做不到的「負面查詢」：找出圖譜中「不存在的東西」。
    用於定期健檢、發現 ontology 品質問題。

    使用時機：
    - 找孤立節點（沒有任何 relationship）→ find_gaps(gap_type="orphan_entities")
    - 找只被引用但無主動關聯的節點 → find_gaps(gap_type="underconnected")
    - 找語意品質差的節點（全是 related_to） → find_gaps(gap_type="weak_semantics")
    - 全面掃描 → find_gaps()
    - 限定在某產品下 → find_gaps(scope_product="ZenOS")

    不要用這個工具的情境：
    - 搜尋特定節點 → 用 search
    - 查看特定節點的關係 → 用 get（會顯示 outgoing/incoming 分類）
    - 品質分數和治理問題 → 用 analyze
    - 查詢某個節點缺什麼 → 用 get 看它的 relationships，不是 find_gaps

    Args:
        gap_type: "all" / "orphan_entities" / "weak_semantics" / "underconnected"
            - orphan_entities: 沒有任何 relationship 的非根節點
            - weak_semantics: 所有關聯都是 related_to，缺少 impacts/depends_on 等語意明確的關係
            - underconnected: 只有 incoming 沒有 outgoing 的節點
        scope_product: 限定在某產品名稱下（例如 "ZenOS"）

    Returns:
        {gaps: [{type, entity_id, entity_name, severity, suggestion}], total, by_type}
    """
    await _ensure_services()
    result = await ontology_service.find_gaps(gap_type, scope_product)
    return _unified_response(data=result)


# ===================================================================
# Tool: common_neighbors — find shared connections between two entities
# ===================================================================


@mcp.tool(
    tags={"read"},
    annotations={"readOnlyHint": True},
)
async def common_neighbors(
    entity_a: str,
    entity_b: str,
) -> dict:
    """找出兩個節點的共同鄰居——同時與 A 和 B 有直接關聯的節點。

    用於發現隱藏的關聯、找出交集、理解兩個概念之間的間接連結。
    這是 search 做不到的「集合交集查詢」。

    使用時機：
    - 「A 和 B 有什麼共同關聯？」→ common_neighbors(entity_a="A", entity_b="B")
    - 找兩個模組共同影響的下游 → common_neighbors(entity_a="模組A", entity_b="模組B")

    不要用這個工具的情境：
    - 只看單一節點的關係 → 用 get
    - 看 A 到 B 的影響鏈 → 用 get 看 impact_chain

    Args:
        entity_a: 第一個節點的名稱或 ID
        entity_b: 第二個節點的名稱或 ID

    Returns:
        {entity_a, entity_b, common_neighbors: [{neighbor_id, neighbor_name, edge_type_a, edge_type_b}], count}
    """
    await _ensure_services()
    try:
        result = await ontology_service.find_common_neighbors(entity_a, entity_b)
    except ValueError as e:
        return _unified_response(
            status="rejected", data={}, rejection_reason=str(e)
        )
    return _unified_response(data=result)


# ===================================================================
# Entrypoint
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    transport = os.environ.get("MCP_TRANSPORT", "dual")
    if transport in ("dual", "sse", "http", "streamable-http"):
        port = int(os.environ.get("PORT", "8080"))

        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        from zenos.interface.admin_api import admin_routes
        from zenos.interface.crm_dashboard_api import crm_dashboard_routes
        from zenos.interface.dashboard_api import dashboard_routes

        if transport == "dual":
            stream_http_app = mcp.http_app(
                transport="streamable-http",
                path="/mcp",
                stateless_http=True,
            )
            sse_http_app = SseApiKeyPropagator(mcp.http_app(transport="sse", path="/sse"))

            class _PathTransportRouter:
                def __init__(self, stream_app, sse_app):
                    self.stream_app = stream_app
                    self.sse_app = sse_app

                async def __call__(self, scope, receive, send):
                    path = scope.get("path", "")
                    if path.startswith("/sse") or path.startswith("/messages/"):
                        return await self.sse_app(scope, receive, send)
                    if path.startswith("/mcp"):
                        return await self.stream_app(scope, receive, send)
                    response = JSONResponse({"error": "NOT_FOUND"}, status_code=404)
                    return await response(scope, receive, send)

            routed_mcp_app = _PathTransportRouter(stream_http_app, sse_http_app)
            mcp_routes = [Mount("/", app=ApiKeyMiddleware(routed_mcp_app))]
            lifespan_app = stream_http_app
        elif transport == "sse":
            http_app = SseApiKeyPropagator(mcp.http_app(transport="sse", path="/sse"))
            mcp_routes = [Mount("/", app=ApiKeyMiddleware(http_app))]
            lifespan_app = http_app
        else:
            http_app = mcp.http_app(
                transport="streamable-http",
                path="/mcp",
                stateless_http=True,
            )
            mcp_routes = [Mount("/", app=ApiKeyMiddleware(http_app))]
            lifespan_app = http_app

        app = Starlette(
            routes=[
                *[Route(r.path, r.endpoint, methods=r.methods) for r in admin_routes],
                *[Route(r.path, r.endpoint, methods=r.methods) for r in dashboard_routes],
                *[Route(r.path, r.endpoint, methods=r.methods) for r in crm_dashboard_routes],
                *mcp_routes,
            ],
            lifespan=lifespan_app.lifespan,
        )

        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        mcp.run(transport="stdio")
