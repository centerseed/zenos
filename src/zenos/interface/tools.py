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

from fastmcp import FastMCP

load_dotenv()

logger = logging.getLogger(__name__)

from zenos.application.governance_ai import GovernanceAI
from zenos.domain.models import EntityEntry
from zenos.application.governance_service import GovernanceService
from zenos.application.ontology_service import OntologyService
from zenos.application.source_service import SourceService
from zenos.application.task_service import TaskService
from zenos.infrastructure.llm_client import create_llm_client
from zenos.infrastructure.sql_repo import (
    SqlBlindspotRepository,
    SqlDocumentRepository,
    SqlEntityEntryRepository,
    SqlEntityRepository,
    SqlPartnerKeyValidator,
    SqlProtocolRepository,
    SqlRelationshipRepository,
    SqlTaskRepository,
    SqlUsageLogRepository,
    get_pool,
)
from zenos.infrastructure.github_adapter import GitHubAdapter
from zenos.infrastructure.context import (
    current_partner_department,
    current_partner_is_admin,
    current_partner_roles,
)
from zenos.interface.governance_rules import GOVERNANCE_RULES

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
                from zenos.infrastructure.context import current_partner_id
                token = _current_partner.set(partner)
                token_pid = current_partner_id.set(partner.get("sharedPartnerId") or partner.get("id", ""))
                token_roles = current_partner_roles.set(list(partner.get("roles") or []))
                token_department = current_partner_department.set(str(partner.get("department") or "all"))
                token_admin = current_partner_is_admin.set(bool(partner.get("isAdmin", False)))
                try:
                    return await self.app(scope, receive, send)
                finally:
                    _current_partner.reset(token)
                    current_partner_id.reset(token_pid)
                    current_partner_roles.reset(token_roles)
                    current_partner_department.reset(token_department)
                    current_partner_is_admin.reset(token_admin)
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


async def _ensure_governance_ai() -> None:
    """Wire GovernanceAI with SqlUsageLogRepository after pool is available."""
    global _governance_ai, _usage_log_repo
    if _governance_ai is not None:
        return
    try:
        pool = await get_pool()
        _usage_log_repo = SqlUsageLogRepository(pool)
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
        )
    if governance_service is None:
        governance_service = GovernanceService(
            entity_repo=entity_repo,
            relationship_repo=relationship_repo,
            protocol_repo=protocol_repo,
            blindspot_repo=blindspot_repo,
            task_repo=task_repo,
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
    return _convert_datetimes(raw)


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


def _new_id() -> str:
    """Generate a short unique ID (32-char hex UUID4)."""
    return uuid.uuid4().hex


def _is_entity_visible(entity: object) -> bool:
    """Centralized server-side visibility check for read paths."""
    partner = _current_partner.get() or {}
    partner_id = str(partner.get("id") or "")
    is_admin = bool(partner.get("isAdmin", False))
    if is_admin:
        return True

    visibility = str(getattr(entity, "visibility", "public") or "public")
    visible_to_roles = set(getattr(entity, "visible_to_roles", []) or [])
    visible_to_members = set(getattr(entity, "visible_to_members", []) or [])
    visible_to_departments = set(getattr(entity, "visible_to_departments", []) or [])
    partner_roles = set(current_partner_roles.get() or [])
    partner_department = str(current_partner_department.get() or "all")

    if visible_to_departments and partner_department not in visible_to_departments and "all" not in visible_to_departments:
        return False

    if visibility == "confidential":
        return partner_id in visible_to_members

    if visibility in {"restricted", "role-restricted"}:
        if partner_id in visible_to_members:
            return True
        if visible_to_roles:
            return bool(partner_roles & visible_to_roles)
        return False

    return True


def _audit_log(
    event_type: str,
    target: dict,
    changes: dict | None = None,
    governance: dict | None = None,
) -> None:
    """Emit structured governance audit logs to stdout/Cloud Logging."""
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
    limit: int = 50,
    project: str | None = None,
) -> dict:
    """搜尋和列出 ontology 及任務中的所有內容。

    這是你探索 ZenOS 知識庫的主要入口。當你需要「找東西」時用這個。
    支援關鍵字搜尋（跨所有集合）或按集合過濾列出。

    使用時機：
    - 不確定要找什麼 → query="關鍵字"，collection="all"
    - 列出某類東西 → collection="entities"，可加 status 過濾
    - 看待確認項目 → confirmed_only=False
    - 查任務 → collection="tasks"，可加 assignee/created_by 過濾

    不要用這個工具的情境：
    - 已知確切名稱要看完整資料 → 用 get
    - 要讀原始文件內容 → 用 read_source
    - 要搜尋任務 → collection="tasks"（在這裡，不需要用 task 工具）

    限制：關鍵字搜尋，非語意搜尋。query 最長 200 字。

    Args:
        query: 搜尋關鍵字（空字串 = 列出全部）
        collection: 搜尋範圍。all/entities/documents/protocols/blindspots/tasks
        status: 按狀態過濾（如 active/open/todo/in_progress，逗號分隔多值）
        severity: 按嚴重度過濾 blindspots（red/yellow/green）
        entity_name: 按實體名稱過濾（blindspots 和 documents 用）
        assignee: 按被指派者過濾 tasks（Inbox 視角）
        created_by: 按建立者過濾 tasks（Outbox 視角）
        confirmed_only: true=只看已確認 / false=只看未確認 / 不傳=全部
        limit: 回傳上限，預設 50
        project: 按專案過濾 tasks（如 "zenos"、"paceriz"）。
            未傳時自動使用 partner 的 default_project，確保跨專案隔離。
    """
    await _ensure_services()
    results: dict = {}

    # Keyword search mode (cross-collection)
    if query.strip() and collection == "all":
        search_results = await ontology_service.search(query)
        visible_results = [r for r in search_results if (r.type != "entity" or _is_entity_visible(r))]
        results["results"] = [_serialize(r) for r in visible_results[:limit]]
        results["count"] = len(results["results"])

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
        ][:limit]
        if matched_tasks:
            results["tasks"] = [_serialize(t) for t in matched_tasks]

        # Also search entity entries content
        entry_hits = await entry_repo.search_content(query, limit=limit)
        if entry_hits:
            results["entries"] = [
                {**_serialize(hit["entry"]), "entity_name": hit["entity_name"]}
                for hit in entry_hits
            ]

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
            if confirmed_only is not None:
                entities = [
                    e for e in entities
                    if e.confirmed_by_user == confirmed_only
                ]
            items = [_serialize(e) for e in entities[:limit]]
            results["entities"] = items

        elif col == "documents":
            # Query document entities (type="document") from entities collection
            doc_entities = await ontology_service._entities.list_all(type_filter="document")
            doc_entities = [d for d in doc_entities if _is_entity_visible(d)]
            # Exclude archived document entities (dead links confirmed unresolvable)
            doc_entities = [d for d in doc_entities if d.status != "archived"]
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
            results["documents"] = [_serialize(d) for d in doc_entities[:limit]]

        elif col == "protocols":
            if confirmed_only is False:
                protos = await ontology_service._protocols.list_unconfirmed()
            else:
                protos = await ontology_service._protocols.list_all(confirmed_only=confirmed_only)
            results["protocols"] = [_serialize(p) for p in protos[:limit]]

        elif col == "blindspots":
            blindspots = await ontology_service.list_blindspots(
                entity_name=entity_name, severity=severity
            )
            if confirmed_only is not None:
                blindspots = [
                    b for b in blindspots
                    if b.confirmed_by_user == confirmed_only
                ]
            results["blindspots"] = [_serialize(b) for b in blindspots[:limit]]

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
                project=effective_project or None,
            )
            results["tasks"] = [_serialize(t) for t in tasks]

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
        # Attach active entries so callers see the entity as a knowledge container
        eid = result.entity.id
        active_entries = await entry_repo.list_by_entity(eid) if eid else []
        response["active_entries"] = [_serialize(e) for e in active_entries]
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
        return _serialize(result)

    elif collection == "tasks":
        if not id:
            return {"error": "INVALID_INPUT", "message": "Provide id for tasks"}
        enriched = await task_service.get_task_enriched(id)
        if enriched is None:
            return {"error": "NOT_FOUND", "message": f"Task '{id}' not found"}
        task_obj, enrichments = enriched
        result = _serialize(task_obj)
        result["linked_entities"] = enrichments["expanded_entities"]
        if "assignee_role" in enrichments:
            result["assignee_role"] = enrichments["assignee_role"]
        if "blindspot_detail" in enrichments:
            result["blindspot_detail"] = enrichments["blindspot_detail"]
        return result

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
              選填：layer_decision({q1_persistent, q2_cross_role, q3_company_consensus, impacts_draft})
                    — 新建 L2（type=module）時必填，除非 force=True
                    — 型別必須是 object（dict），不可傳 JSON 字串
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
               可用 sync_mode(rename/reclassify/archive/supersede/sync_repair)
               + dry_run=true 做文件治理批次同步預覽。
    protocols: entity_id, entity_name, content({what, why, how, who})
    blindspots: description, severity(red/yellow/green), suggested_action
    relationships: source_entity_id, target_entity_id, type(depends_on/serves/
                   owned_by/part_of/blocks/related_to/impacts/enables), description
    entries: entity_id（必填）, type（必填：decision/insight/limitation/change/context）,
             content（必填：1-200 字元）
             選填：context（額外脈絡，最多 200 字元）, author, source_task_id

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
            result = await ontology_service.upsert_entity(data)
            response = _serialize(result)
            if result.warnings:
                response["warnings"] = result.warnings
            _audit_log(
                event_type="ontology.entity.upsert",
                target={"collection": collection, "id": response.get("entity", {}).get("id")},
                changes={"input": data},
                governance={"warnings": result.warnings or []},
            )
            return response

        elif collection == "documents":
            # Backward compat: collection="documents" now creates entity(type="document")
            if data.get("sync_mode"):
                result = await ontology_service.sync_document_governance(data)
                response = _serialize(result)
                _audit_log(
                    event_type="ontology.document.sync",
                    target={"collection": collection, "id": response.get("document_id")},
                    changes={"input": data},
                )
                return response
            result = await ontology_service.upsert_document(data)
            response = _serialize(result)
            _audit_log(
                event_type="ontology.document.upsert",
                target={"collection": collection, "id": response.get("id")},
                changes={"input": data},
            )
            return response

        elif collection == "protocols":
            result = await ontology_service.upsert_protocol(data)
            response = _serialize(result)
            _audit_log(
                event_type="ontology.protocol.upsert",
                target={"collection": collection, "id": response.get("id")},
                changes={"input": data},
            )
            return response

        elif collection == "blindspots":
            result = await ontology_service.add_blindspot(data)
            response = _serialize(result)

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
                    response["auto_created_task"] = _serialize(duplicate_open)
                    response["auto_task_skipped"] = "EXISTING_OPEN_TASK"
                    _audit_log(
                        event_type="ontology.blindspot.upsert",
                        target={"collection": collection, "id": response.get("id")},
                        changes={"input": data},
                        governance={"auto_task": "skipped_existing_open"},
                    )
                    return response

                # Infer assignee from related entities' who tag
                assignee = None
                for eid in (result.related_entity_ids or []):
                    entity = await entity_repo.get_by_id(eid)
                    if entity and entity.tags.who:
                        assignee = entity.tags.who
                        break

                auto_task_data = {
                    "title": f"處理盲點：{result.description[:30]}",
                    "source_type": "blindspot",
                    "linked_blindspot": result.id,
                    "linked_entities": result.related_entity_ids or [],
                    "status": "backlog",
                    "created_by": "system",
                    "assignee": assignee,
                }
                auto_task_result = await task_service.create_task(auto_task_data)
                response["auto_created_task"] = _serialize(auto_task_result.task)

            _audit_log(
                event_type="ontology.blindspot.upsert",
                target={"collection": collection, "id": response.get("id")},
                changes={"input": data},
            )
            return response

        elif collection == "relationships":
            result = await ontology_service.add_relationship(
                source_id=data["source_entity_id"],
                target_id=data["target_entity_id"],
                rel_type=data["type"],
                description=data["description"],
            )
            response = _serialize(result)
            _audit_log(
                event_type="ontology.relationship.upsert",
                target={"collection": collection, "id": response.get("id")},
                changes={"input": data},
            )
            return response

        elif collection == "entries":
            # Update status flow (e.g. supersede)
            if id:
                new_status = data.get("status")
                superseded_by = data.get("superseded_by")
                if not new_status:
                    return {"error": "INVALID_INPUT", "message": "entries 更新時 data 需提供 status"}
                valid_statuses = {"active", "superseded", "archived"}
                if new_status not in valid_statuses:
                    return {"error": "INVALID_INPUT", "message": f"status 必須是 {valid_statuses} 之一"}
                if new_status == "superseded" and not superseded_by:
                    return {"error": "INVALID_INPUT", "message": "status=superseded 時必填 superseded_by"}
                archive_reason = data.get("archive_reason")
                if new_status == "archived":
                    if not archive_reason:
                        return {"error": "INVALID_INPUT", "message": "status=archived 時必填 archive_reason"}
                    if archive_reason not in ("merged", "manual"):
                        return {"error": "INVALID_INPUT", "message": "archive_reason 必須是 merged 或 manual"}
                updated = await entry_repo.update_status(id, new_status, superseded_by, archive_reason)
                if updated is None:
                    return {"error": "NOT_FOUND", "message": f"Entry '{id}' not found"}
                return _serialize(updated)

            # Create new entry
            entity_id = data.get("entity_id")
            entry_type = data.get("type")
            content = data.get("content")
            if not entity_id or not entry_type or not content:
                return {"error": "INVALID_INPUT", "message": "entries 必填：entity_id, type, content"}
            if not (1 <= len(content) <= 200):
                return {"error": "INVALID_INPUT", "message": "content 必須 1-200 字元"}
            valid_types = {"decision", "insight", "limitation", "change", "context"}
            if entry_type not in valid_types:
                return {"error": "INVALID_INPUT", "message": f"type 必須是 {valid_types} 之一"}
            context = data.get("context")
            if context and len(context) > 200:
                return {"error": "INVALID_INPUT", "message": "context 最多 200 字元"}

            pid = (_current_partner.get() or {}).get("id", "")
            entry = EntityEntry(
                id=_new_id(),
                partner_id=pid,
                entity_id=entity_id,
                type=entry_type,
                content=content,
                context=context,
                author=data.get("author"),
                source_task_id=data.get("source_task_id"),
            )
            result = await entry_repo.create(entry)
            _audit_log(
                event_type="ontology.entry.create",
                target={"collection": collection, "id": result.id},
                changes={"input": data},
            )
            response = _serialize(result)
            active_count = await entry_repo.count_active_by_entity(entity_id)
            if active_count >= 20:
                response["warning"] = (
                    "此 entity 已達 20 條 active entries 上限，"
                    "建議執行 analyze(check_type='quality') 觸發歸納"
                )
            return response

        else:
            return {
                "error": "INVALID_INPUT",
                "message": f"Unknown collection '{collection}'. "
                f"Use: entities, documents, protocols, blindspots, relationships, entries",
            }
    except (ValueError, KeyError, TypeError) as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


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
            )
            response = _serialize(result.task)
            if result.cascade_updates:
                response["cascadeUpdates"] = [
                    {"taskId": c.task_id, "change": c.change, "reason": c.reason}
                    for c in result.cascade_updates
                ]
            _audit_log(
                event_type="task.confirm",
                target={"collection": collection, "id": id},
                changes={
                    "accepted": accepted,
                    "rejection_reason": rejection_reason,
                    "mark_stale_entity_ids": mark_stale_entity_ids or [],
                    "new_blindspot": new_blindspot or {},
                },
            )
            return response
        else:
            result = await ontology_service.confirm(collection, id)
            _audit_log(
                event_type="ontology.confirm",
                target={"collection": collection, "id": id},
                changes={"accepted": accepted},
            )
            return result
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return {"error": "NOT_FOUND", "message": error_msg}
        return {"error": "INVALID_INPUT", "message": error_msg}


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

    try:
        # Resolve partner context once — used for auto-filling created_by and project
        partner = _current_partner.get()
        partner_default_project = partner.get("defaultProject", "") if partner else ""

        if action == "create":
            if not title:
                return {"error": "INVALID_INPUT", "message": "title is required for create"}
            # Auto-fill created_by from partner identity if not provided
            if not created_by:
                if partner:
                    created_by = partner.get("displayName", "unknown")
            if not created_by:
                return {"error": "INVALID_INPUT", "message": "created_by is required for create"}

            # Auto-fill project from partner's default_project if caller omits it
            effective_project = project or partner_default_project

            # Parse due_date string to datetime
            parsed_due = None
            if due_date:
                try:
                    parsed_due = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return {"error": "INVALID_INPUT", "message": f"Invalid due_date format: {due_date}"}

            normalized_description = _normalize_description_to_markdown(description)

            data = {
                "title": title,
                "created_by": created_by,
                "description": normalized_description,
                "assignee": assignee,
                "priority": priority,
                "status": status or "backlog",
                "linked_entities": linked_entities or [],
                "linked_protocol": linked_protocol,
                "linked_blindspot": linked_blindspot,
                "source_type": source_type or "",
                "source_metadata": source_metadata or {},
                "due_date": parsed_due,
                "blocked_by": blocked_by or [],
                "blocked_reason": blocked_reason,
                "acceptance_criteria": acceptance_criteria or [],
                "project": effective_project,
                "assignee_role_id": assignee_role_id,
                "plan_id": plan_id,
                "plan_order": plan_order,
                "depends_on_task_ids": depends_on_task_ids or [],
            }
            if task_service is None:
                await _ensure_services()
            task_result = await task_service.create_task(data)
            response = _serialize(task_result.task)
            _audit_log(
                event_type="task.create",
                target={"collection": "tasks", "id": response.get("id")},
                changes={"input": data},
            )
            return response

        elif action == "update":
            if not id:
                return {"error": "INVALID_INPUT", "message": "id is required for update"}

            updates: dict = {}
            if status is not None:
                updates["status"] = status
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
                updates["blocked_by"] = blocked_by
            if source_metadata is not None:
                updates["source_metadata"] = source_metadata
            if acceptance_criteria is not None:
                updates["acceptance_criteria"] = acceptance_criteria
            if due_date is not None:
                try:
                    updates["due_date"] = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return {"error": "INVALID_INPUT", "message": f"Invalid due_date: {due_date}"}
            if plan_id is not None:
                updates["plan_id"] = plan_id
            if plan_order is not None:
                updates["plan_order"] = plan_order
            if depends_on_task_ids is not None:
                updates["depends_on_task_ids"] = depends_on_task_ids

            if task_service is None:
                await _ensure_services()
            task_result = await task_service.update_task(id, updates)
            response = _serialize(task_result.task)
            if task_result.cascade_updates:
                response["cascadeUpdates"] = [
                    {"taskId": c.task_id, "change": c.change, "reason": c.reason}
                    for c in task_result.cascade_updates
                ]
            _audit_log(
                event_type="task.update",
                target={"collection": "tasks", "id": id},
                changes={"updates": updates},
            )
            return response

        else:
            return {
                "error": "INVALID_INPUT",
                "message": f"Unknown action '{action}'. Use: create, update",
            }
    except ValueError as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


@mcp.tool(
    tags={"write"},
)
async def task(
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
) -> dict:
    """管理知識驅動的行動項目（Action Layer）。

    任務是 ontology 的 output 路徑——從知識洞察產生的具體行動。
    每個任務透過 linked_entities/linked_blindspot 連結回 ontology，
    讓收到任務的人/agent 自動獲得相關 context。

    使用時機：
    - 建任務 → action="create"（必填：title, created_by）
    - 改狀態 → action="update"（必填：id。改 status/assignee/priority 等）
    - 列任務 → 不要用這個，用 search(collection="tasks") 更靈活

    狀態流：backlog → todo → in_progress → review → done → archived
            任何狀態可 → cancelled。blocked 是特殊狀態（需填 blocked_reason）。
    注意：不能用 update 把 status 改成 done（必須走 confirm 驗收流程）。
    補充限制：
    - create 時初始 status 只能是 backlog 或 todo
    - update 到 review 時，result 為必填（SQL schema 強制）
    - create 時若 blocked_by 非空且 status 不是 backlog，會進入 blocked，且 blocked_reason 必填
    - linked_protocol / linked_blindspot / assignee_role_id / linked_entities 會受資料庫外鍵限制，ID 必須存在於同租戶資料中
    - task 屬於某個 plan 時，建議帶 plan_id 與 plan_order，讓 agent 能按順序執行

    不要用這個工具的情境：
    - 查任務列表 → 用 search(collection="tasks")
    - 驗收任務 → 用 confirm(collection="tasks")

    Args:
        action: "create" 或 "update"
        title: 任務標題，動詞開頭（create 必填）
        created_by: 建立者 UID（create 必填）
        id: 任務 ID（update 必填）
        description: 任務描述
        assignee: 被指派者 UID
        priority: critical/high/medium/low（不傳時 AI 自動推薦）
        status: create 時只能 backlog/todo；update 時需通過合法性驗證
        linked_entities: 關聯的 entity IDs
        linked_protocol: 關聯的 Protocol ID
        linked_blindspot: 觸發的 blindspot ID
        source_metadata: 來源追溯與外部同步資訊（可選，dict）。
            推薦結構：
            {
              "provenance": [
                {
                  "type": "chat|doc|repo",
                  "label": "來源標題",
                  "snippet": "對話或代碼原文片段",
                  "url": "外部連結 (可選)",
                  "imageUrl": "圖片連結 (可選)",
                  "sheetRef": "Sheet 座標 (可選)"
                }
              ],
              "syncSources": ["github", "linear", "slack"]
            }
        due_date: 到期日 ISO-8601（如 "2026-03-29"）
        blocked_by: 阻塞此任務的 task IDs
        blocked_reason: status=blocked 時必填；create 若 blocked_by 讓任務進入 blocked 也必填
        acceptance_criteria: 驗收條件列表
        result: 完成產出描述（status=review 時必填）
        project: 所屬專案識別碼（如 "zenos"、"paceriz"），用於任務隔離。
            未傳時自動使用 partner 的 default_project，確保任務不會跨專案污染。
        assignee_role_id: 指向 role entity 的 ID（可選），用於展開角色 context
        plan_id: 任務群組 ID（PLAN 層識別）
        plan_order: 任務在 plan 內順序（>=1）
        depends_on_task_ids: 前置依賴 task IDs（可選）
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
    )


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

    不要用這個工具的情境：
    - 搜尋或列出條目 → 用 search
    - 更新 ontology 內容 → 用 write

    Args:
        check_type: "all" / "quality" / "staleness" / "blindspot" / "impacts" / "document_consistency"
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
        report = await governance_service.run_quality_check()
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
            _open_statuses = {"backlog", "todo", "in_progress", "review", "blocked"}
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

    if not results:
        return {
            "error": "INVALID_INPUT",
            "message": (
                f"Unknown check_type '{check_type}'. "
                "Use: all, quality, staleness, blindspot, impacts, document_consistency"
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

    return {
        "topic": topic,
        "level": level,
        "version": "1.0",
        "content": GOVERNANCE_RULES[topic][level],
    }



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
    """自助安裝 ZenOS 治理能力到你的 AI agent 平台。

    已完成 MCP 連線的用戶呼叫此 tool，即可取得 ZenOS skill 安裝指引。
    支援：Claude Code、Claude Web UI、OpenAI Codex。
    不需要 DB 連線，不需要 partner key。

    使用時機：
    - 首次設定 ZenOS 治理能力 → setup()（不帶參數，取得平台清單）
    - 指定平台安裝 → setup(platform='claude_code')
    - 更新 skill 到最新版 → setup(platform='claude_code', skip_overview=True)
    - 只需要 Task 治理 → setup(platform='claude_code', skill_selection='task_only')

    不需要用這個工具的情境：
    - MCP 連線設定（取得 API key、填入 MCP server URL）→ 這是前置條件，不在 setup 範圍
    - 查詢 ontology → 用 search 或 get
    - 治理規則查詢 → 用 governance_guide

    Args:
        platform: 目標平台。claude_code / claude_web / codex。
                  不傳時回傳平台清單，讓 agent 詢問用戶後帶正確值再次呼叫。
        skill_selection: 治理能力組合。
                         full=完整（L2+L3+Task），doc_task=文件+Task，task_only=僅Task。
        skip_overview: 跳過治理概要說明，適合更新操作（已熟悉 ZenOS 的用戶）。

    Returns:
        platform=None → {"action": "ask_platform", "bundle_version": "...", "options": [...]}
        platform valid → {"action": "install", "platform": "...", "payload": {...}}
        platform invalid → {"error": "unsupported_platform", "supported_platforms": [...]}
        skill_selection invalid → {"error": "invalid_skill_selection", "message": "..."}
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
