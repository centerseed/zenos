"""ZenOS MCP Server — 7 consolidated tools for ontology + action layer.

Consolidated from 17 tools to 7, optimized for agent comprehension:
  1. search   — find and list across all collections
  2. get      — retrieve one specific item by name or ID
  3. read_source — read raw file content via adapter
  4. write    — create/update ontology entries
  5. confirm  — approve knowledge drafts or accept/reject tasks
  6. task     — create, update, and list action items
  7. analyze  — run governance health checks

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
import time
from contextvars import ContextVar
from dataclasses import asdict
from datetime import datetime

from dotenv import load_dotenv
from starlette.responses import JSONResponse

from fastmcp import FastMCP

load_dotenv()

logger = logging.getLogger(__name__)

from zenos.application.governance_ai import GovernanceAI
from zenos.application.governance_service import GovernanceService
from zenos.application.ontology_service import OntologyService
from zenos.application.source_service import SourceService
from zenos.application.task_service import TaskService
from zenos.infrastructure.llm_client import create_llm_client
from zenos.infrastructure.firestore_repo import (
    FirestoreBlindspotRepository,
    FirestoreDocumentRepository,  # kept for legacy backward compat
    FirestoreEntityRepository,
    FirestoreProtocolRepository,
    FirestoreRelationshipRepository,
    FirestoreTaskRepository,
)
from zenos.infrastructure.github_adapter import GitHubAdapter

# ──────────────────────────────────────────────
# Agent Identity — ContextVar for partner data
# ──────────────────────────────────────────────

_current_partner: ContextVar[dict | None] = ContextVar("current_partner", default=None)

# ──────────────────────────────────────────────
# API Key authentication middleware
# ──────────────────────────────────────────────

ZENOS_API_KEY = os.environ.get("ZENOS_API_KEY", "")
ZENOS_DEFAULT_PARTNER_ID = os.environ.get("ZENOS_DEFAULT_PARTNER_ID", "")


class PartnerKeyValidator:
    """Validates API keys against Firestore partners collection.

    Caches active partner keys in memory with a configurable TTL
    to avoid a Firestore read on every request.
    """

    def __init__(self, ttl: int = 300):
        self._cache: dict[str, dict] = {}
        self._cache_ts: float = 0
        self._ttl = ttl

    async def validate(self, key: str) -> dict | None:
        """Return partner data if *key* belongs to an active partner."""
        now = time.time()
        if now - self._cache_ts > self._ttl:
            await self._refresh_cache()
        return self._cache.get(key)

    async def _refresh_cache(self) -> None:
        from zenos.infrastructure.firestore_repo import get_db

        try:
            db = get_db()
            docs = db.collection("partners").where("status", "==", "active").stream()
            new_cache: dict[str, dict] = {}
            async for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id  # expose document ID for partner routing
                api_key = data.get("apiKey", "")
                if api_key:
                    new_cache[api_key] = data
            self._cache = new_cache
            self._cache_ts = time.time()
            logger.info("Partner cache refreshed: %d active keys", len(new_cache))
        except Exception:
            logger.exception("Failed to refresh partner cache from Firestore")
            # Don't update _cache_ts so next request retries
            # But if cache is empty and keeps failing, we need a fallback
            if not self._cache:
                self._cache_ts = time.time()  # avoid hammering Firestore


_partner_validator = PartnerKeyValidator()


class ApiKeyMiddleware:
    """Pure ASGI middleware — compatible with SSE streaming.

    Authentication order:
    1. If ZENOS_API_KEY env var is empty → skip auth (local dev / stdio).
    2. Check against ZENOS_API_KEY (superadmin, backward-compatible).
    3. Check against Firestore partners collection (multi-key).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Skip auth if no key configured (local dev / stdio)
        if not ZENOS_API_KEY:
            return await self.app(scope, receive, send)

        key = self._extract_key(scope)
        path = scope.get("path", "")

        # 1. Superadmin key (env var)
        if key and key == ZENOS_API_KEY:
            from zenos.infrastructure.context import current_partner_id
            token = _current_partner.set({
                "displayName": "superadmin",
                "email": "admin",
                "id": ZENOS_DEFAULT_PARTNER_ID,
            })
            token_pid = current_partner_id.set(ZENOS_DEFAULT_PARTNER_ID)
            try:
                return await self.app(scope, receive, send)
            finally:
                _current_partner.reset(token)
                current_partner_id.reset(token_pid)

        # 2. Partner key (Firestore)
        if key:
            partner = await _partner_validator.validate(key)
            if partner is not None:
                from zenos.infrastructure.context import current_partner_id
                token = _current_partner.set(partner)
                token_pid = current_partner_id.set(partner.get("id", ""))
                try:
                    return await self.app(scope, receive, send)
                finally:
                    _current_partner.reset(token)
                    current_partner_id.reset(token_pid)
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
        """Extract API key from Authorization header or query param."""
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        from urllib.parse import parse_qs

        qs = parse_qs(scope.get("query_string", b"").decode())
        keys = qs.get("api_key", [])
        return keys[0] if keys else None


# ──────────────────────────────────────────────
# MCP server instance
# ──────────────────────────────────────────────

mcp = FastMCP("ZenOS Ontology")

# ──────────────────────────────────────────────
# Dependency injection — repositories & services
# ──────────────────────────────────────────────

entity_repo = FirestoreEntityRepository()
relationship_repo = FirestoreRelationshipRepository()
document_repo = FirestoreDocumentRepository()
protocol_repo = FirestoreProtocolRepository()
blindspot_repo = FirestoreBlindspotRepository()
task_repo = FirestoreTaskRepository()

source_adapter = GitHubAdapter()

# GovernanceAI: LLM-based auto-inference (optional, depends on env config)
_governance_ai: GovernanceAI | None = None
try:
    _llm_client = create_llm_client()
    _governance_ai = GovernanceAI(_llm_client)
    logger.info("GovernanceAI initialized with model: %s", _llm_client.model)
except Exception:
    logger.warning("GovernanceAI disabled: LLM client initialization failed", exc_info=True)

ontology_service = OntologyService(
    entity_repo=entity_repo,
    relationship_repo=relationship_repo,
    document_repo=document_repo,
    protocol_repo=protocol_repo,
    blindspot_repo=blindspot_repo,
    governance_ai=_governance_ai,
)

governance_service = GovernanceService(
    entity_repo=entity_repo,
    relationship_repo=relationship_repo,
    protocol_repo=protocol_repo,
    blindspot_repo=blindspot_repo,
)

source_service = SourceService(
    entity_repo=entity_repo,
    source_adapter=source_adapter,
)

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
    results: dict = {}

    # Keyword search mode (cross-collection)
    if query.strip() and collection == "all":
        search_results = await ontology_service.search(query)
        results["results"] = [_serialize(r) for r in search_results[:limit]]
        results["count"] = len(results["results"])

        # Also search tasks by title/description keyword
        # Auto-fill project from partner context if caller omits it
        _partner_ctx = _current_partner.get()
        effective_project_kw = project or (_partner_ctx.get("default_project", "") if _partner_ctx else "")
        all_tasks = await task_service.list_tasks(limit=200, project=effective_project_kw or None)
        query_lower = query.lower()
        matched_tasks = [
            t for t in all_tasks
            if query_lower in t.title.lower()
            or query_lower in t.description.lower()
        ][:limit]
        if matched_tasks:
            results["tasks"] = [_serialize(t) for t in matched_tasks]

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
            # Protocols don't have list_all, collect via entities
            if confirmed_only is False:
                protos = await ontology_service._protocols.list_unconfirmed()
            else:
                entities = await ontology_service.list_entities()
                protos = []
                for e in entities:
                    if e.id:
                        p = await ontology_service._protocols.get_by_entity(e.id)
                        if p:
                            if confirmed_only is None or p.confirmed_by_user == confirmed_only:
                                protos.append(p)
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
            effective_project = project or (_partner.get("default_project", "") if _partner else "")
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
        return _serialize(result)

    elif collection == "protocols":
        if name:
            result = await ontology_service.get_protocol(name)
        elif id:
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
    try:
        content = await source_service.read_source(doc_id)
        return {"doc_id": doc_id, "content": content}
    except ValueError as e:
        return {"error": "NOT_FOUND", "message": str(e)}
    except FileNotFoundError as e:
        return {"error": "NOT_FOUND", "message": str(e)}
    except PermissionError as e:
        return {"error": "ADAPTER_ERROR", "message": f"Permission denied: {e}"}
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
    documents: title, source({type, uri, adapter}), tags({what[], why, how, who[]}),
               summary
    protocols: entity_id, entity_name, content({what, why, how, who})
    blindspots: description, severity(red/yellow/green), suggested_action
    relationships: source_entity_id, target_entity_id, type(depends_on/serves/
                   owned_by/part_of/blocks/related_to), description

    Args:
        collection: entities/documents/protocols/blindspots/relationships
        data: 集合對應的欄位（見上方說明）
        id: 更新時提供既有 ID，不提供則新增
    """
    try:
        if id:
            data["id"] = id

        if collection == "entities":
            result = await ontology_service.upsert_entity(data)
            response = _serialize(result)
            if result.warnings:
                response["warnings"] = result.warnings
            return response

        elif collection == "documents":
            # Backward compat: collection="documents" now creates entity(type="document")
            result = await ontology_service.upsert_document(data)
            return _serialize(result)

        elif collection == "protocols":
            result = await ontology_service.upsert_protocol(data)
            return _serialize(result)

        elif collection == "blindspots":
            result = await ontology_service.add_blindspot(data)
            response = _serialize(result)

            # Red blindspots auto-create a draft task for immediate attention
            if result.severity == "red":
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

            return response

        elif collection == "relationships":
            result = await ontology_service.add_relationship(
                source_id=data["source_entity_id"],
                target_id=data["target_entity_id"],
                rel_type=data["type"],
                description=data["description"],
            )
            return _serialize(result)

        else:
            return {
                "error": "INVALID_INPUT",
                "message": f"Unknown collection '{collection}'. "
                f"Use: entities, documents, protocols, blindspots, relationships",
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
            return response
        else:
            result = await ontology_service.confirm(collection, id)
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
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    acceptance_criteria: list[str] | None = None,
    result: str | None = None,
    project: str | None = None,
    assignee_role_id: str | None = None,
) -> dict:
    """Core task handler logic — extracted for testability.

    Called by the ``task`` MCP tool wrapper. Tests import this function
    directly to avoid calling a ``FunctionTool`` object.
    """
    try:
        # Resolve partner context once — used for auto-filling created_by and project
        partner = _current_partner.get()
        partner_default_project = partner.get("default_project", "") if partner else ""

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

            data = {
                "title": title,
                "created_by": created_by,
                "description": description or "",
                "assignee": assignee,
                "priority": priority,
                "status": status or "backlog",
                "linked_entities": linked_entities or [],
                "linked_protocol": linked_protocol,
                "linked_blindspot": linked_blindspot,
                "source_type": source_type or "",
                "due_date": parsed_due,
                "blocked_by": blocked_by or [],
                "acceptance_criteria": acceptance_criteria or [],
                "project": effective_project,
                "assignee_role_id": assignee_role_id,
            }
            task_result = await task_service.create_task(data)
            response = _serialize(task_result.task)
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
            if acceptance_criteria is not None:
                updates["acceptance_criteria"] = acceptance_criteria
            if due_date is not None:
                try:
                    updates["due_date"] = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return {"error": "INVALID_INPUT", "message": f"Invalid due_date: {due_date}"}

            task_result = await task_service.update_task(id, updates)
            response = _serialize(task_result.task)
            if task_result.cascade_updates:
                response["cascadeUpdates"] = [
                    {"taskId": c.task_id, "change": c.change, "reason": c.reason}
                    for c in task_result.cascade_updates
                ]
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
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    acceptance_criteria: list[str] | None = None,
    result: str | None = None,
    project: str | None = None,
    assignee_role_id: str | None = None,
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
        status: 目標狀態（update 用，需通過合法性驗證）
        linked_entities: 關聯的 entity IDs
        linked_protocol: 關聯的 Protocol ID
        linked_blindspot: 觸發的 blindspot ID
        due_date: 到期日 ISO-8601（如 "2026-03-29"）
        blocked_by: 阻塞此任務的 task IDs
        blocked_reason: blocked 狀態時必填
        acceptance_criteria: 驗收條件列表
        result: 完成產出描述（status=review 時填寫）
        project: 所屬專案識別碼（如 "zenos"、"paceriz"），用於任務隔離。
            未傳時自動使用 partner 的 default_project，確保任務不會跨專案污染。
        assignee_role_id: 指向 role entity 的 ID（可選），用於展開角色 context
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
        due_date=due_date,
        blocked_by=blocked_by,
        blocked_reason=blocked_reason,
        acceptance_criteria=acceptance_criteria,
        result=result,
        project=project,
        assignee_role_id=assignee_role_id,
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

    不要用這個工具的情境：
    - 搜尋或列出條目 → 用 search
    - 更新 ontology 內容 → 用 write

    Args:
        check_type: "all" / "quality" / "staleness" / "blindspot"
    """
    results: dict = {}

    if check_type in ("all", "quality"):
        report = await governance_service.run_quality_check()
        results["quality"] = _serialize(report)

    if check_type in ("all", "staleness"):
        warnings = await governance_service.run_staleness_check()
        results["staleness"] = {
            "warnings": [_serialize(w) for w in warnings],
            "count": len(warnings),
        }

    if check_type in ("all", "blindspot"):
        blindspots = await governance_service.run_blindspot_analysis()
        results["blindspots"] = {
            "blindspots": [_serialize(b) for b in blindspots],
            "count": len(blindspots),
        }

    if not results:
        return {
            "error": "INVALID_INPUT",
            "message": f"Unknown check_type '{check_type}'. Use: all, quality, staleness, blindspot",
        }

    return results


# ===================================================================
# Entrypoint
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("sse", "http"):
        port = int(os.environ.get("PORT", "8080"))

        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        from zenos.interface.admin_api import admin_routes

        http_app = mcp.http_app(transport="streamable-http", stateless_http=True)
        mcp_app = ApiKeyMiddleware(http_app)

        app = Starlette(
            routes=[
                *[Route(r.path, r.endpoint, methods=r.methods) for r in admin_routes],
                Mount("/", app=mcp_app),
            ],
            lifespan=http_app.lifespan,
        )

        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        mcp.run(transport="stdio")
