"""ZenOS MCP Server — exposes ontology operations as MCP tools.

Provides 17 tools across three categories:
  - Consumer tools (7): read-only queries for AI agents consuming context
  - Governance tools (7): read-write operations for ontology maintenance
  - Governance engine tools (3): ontology-wide analysis and health checks

Usage:
  MCP_TRANSPORT=stdio  python -m zenos.interface.tools   # default
  MCP_TRANSPORT=sse PORT=8080  python -m zenos.interface.tools
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime

from starlette.responses import JSONResponse

from fastmcp import FastMCP

from zenos.application.governance_service import GovernanceService
from zenos.application.ontology_service import OntologyService
from zenos.application.source_service import SourceService
from zenos.infrastructure.firestore_repo import (
    FirestoreBlindspotRepository,
    FirestoreDocumentRepository,
    FirestoreEntityRepository,
    FirestoreProtocolRepository,
    FirestoreRelationshipRepository,
)
from zenos.infrastructure.github_adapter import GitHubAdapter

# ──────────────────────────────────────────────
# API Key authentication middleware
# ──────────────────────────────────────────────

ZENOS_API_KEY = os.environ.get("ZENOS_API_KEY", "")


class ApiKeyMiddleware:
    """Pure ASGI middleware — compatible with SSE streaming."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Skip auth if no key configured (local dev / stdio)
        if not ZENOS_API_KEY:
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()

        # Check Authorization header
        if auth.startswith("Bearer ") and auth[7:] == ZENOS_API_KEY:
            return await self.app(scope, receive, send)

        # Check query param fallback
        from urllib.parse import parse_qs
        qs = parse_qs(scope.get("query_string", b"").decode())
        if qs.get("api_key", [None])[0] == ZENOS_API_KEY:
            return await self.app(scope, receive, send)

        response = JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
        return await response(scope, receive, send)


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

source_adapter = GitHubAdapter()

ontology_service = OntologyService(
    entity_repo=entity_repo,
    relationship_repo=relationship_repo,
    document_repo=document_repo,
    protocol_repo=protocol_repo,
    blindspot_repo=blindspot_repo,
)

governance_service = GovernanceService(
    entity_repo=entity_repo,
    document_repo=document_repo,
    relationship_repo=relationship_repo,
    protocol_repo=protocol_repo,
    blindspot_repo=blindspot_repo,
)

source_service = SourceService(
    document_repo=document_repo,
    source_adapter=source_adapter,
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
# Consumer Tools (7) — read-only queries
# ===================================================================


@mcp.tool()
async def get_protocol(entity_name: str) -> dict:
    """取得某個產品或實體的 Context Protocol。

    當 AI agent 需要了解一個產品/模組/專案的完整 context 時使用。
    例如：行銷 agent 在撰寫素材前先讀取產品 context，開發 agent
    在實作前先了解模組的設計意圖與限制。

    Args:
        entity_name: 實體名稱（如 "Paceriz"、"ZenOS"）
    """
    result = await ontology_service.get_protocol(entity_name)
    if result is None:
        return {"error": "NOT_FOUND", "message": f"No protocol found for '{entity_name}'"}
    return _serialize(result)


@mcp.tool()
async def list_entities(type_filter: str | None = None) -> dict:
    """列出 ontology 中的所有實體（產品、模組、目標、角色、專案）。

    當 AI agent 需要瀏覽公司的骨架層結構時使用。可選擇按類型篩選。
    用於建立全景圖、查看公司有哪些產品/模組等。

    Args:
        type_filter: 可選，按實體類型篩選（product/module/goal/role/project）
    """
    entities = await ontology_service.list_entities(type_filter=type_filter)
    return {
        "entities": [_serialize(e) for e in entities],
        "count": len(entities),
    }


@mcp.tool()
async def get_entity(entity_name: str) -> dict:
    """取得單一實體的完整資訊，包含其所有關係。

    當 AI agent 需要深入了解某個實體及其與其他實體的關聯時使用。
    回傳實體的四維標籤（What/Why/How/Who）、狀態、以及所有
    上下游依賴關係。

    Args:
        entity_name: 實體名稱
    """
    result = await ontology_service.get_entity(entity_name)
    if result is None:
        return {"error": "NOT_FOUND", "message": f"Entity '{entity_name}' not found"}
    return _serialize(result)


@mcp.tool()
async def list_blindspots(
    entity_name: str | None = None,
    severity: str | None = None,
) -> dict:
    """列出 ontology 中的盲點（AI 推斷出的知識缺口）。

    當 AI agent 需要了解公司知識體系中缺少什麼、哪些地方有風險時使用。
    盲點是 ZenOS 的核心差異化：從跨產品關係圖中推斷老闆沒注意到的問題。

    Args:
        entity_name: 可選，按實體名稱篩選
        severity: 可選，按嚴重程度篩選（red/yellow/green）
    """
    blindspots = await ontology_service.list_blindspots(
        entity_name=entity_name,
        severity=severity,
    )
    return {
        "blindspots": [_serialize(b) for b in blindspots],
        "count": len(blindspots),
    }


@mcp.tool()
async def get_document(doc_id: str) -> dict:
    """取得單一文件的 ontology entry（語意代理）。

    當 AI agent 需要了解某份文件的 metadata（標題、標籤、摘要、
    來源、連結的實體）時使用。這是神經層的 entry，不是文件內容本身。
    若需要讀取文件原始內容，請使用 read_source。

    Args:
        doc_id: 文件的 Firestore document ID
    """
    result = await ontology_service.get_document(doc_id)
    if result is None:
        return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
    return _serialize(result)


@mcp.tool()
async def read_source(doc_id: str) -> dict:
    """讀取文件的原始內容（透過 source adapter 從 GitHub 等來源取得）。

    當 AI agent 需要讀取實際的文件內容（而非僅 metadata）時使用。
    先用 get_document 確認文件存在，再用此 tool 讀取原始內容。

    Args:
        doc_id: 文件的 Firestore document ID
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


@mcp.tool()
async def search_ontology(query: str) -> dict:
    """在整個 ontology 中搜尋（跨實體、文件、Protocol）。

    當 AI agent 不確定要找的東西在哪裡時使用。輸入關鍵字，
    回傳所有匹配的實體、文件、Protocol，按相關度排序。
    適合用於探索性查詢、找出相關 context。

    Args:
        query: 搜尋關鍵字（支援多個詞，用空格分隔）
    """
    if not query or not query.strip():
        return {"error": "INVALID_INPUT", "message": "Query must not be empty"}
    results = await ontology_service.search(query)
    return {
        "results": [_serialize(r) for r in results],
        "count": len(results),
    }


# ===================================================================
# Governance Tools (7) — read-write operations
# ===================================================================


@mcp.tool()
async def upsert_entity(
    name: str,
    type: str,
    summary: str,
    tags: dict,
    status: str = "active",
    id: str | None = None,
    parent_id: str | None = None,
    details: dict | None = None,
    confirmed_by_user: bool = False,
) -> dict:
    """建立或更新一個骨架層實體。

    當 AI agent 需要在 ontology 中新增或修改產品、模組、目標、角色、
    專案時使用。會自動執行治理邏輯：標籤信心度分類和拆分建議。
    新建時不需要提供 id，系統會自動生成。

    Args:
        name: 實體名稱
        type: 實體類型（product/module/goal/role/project）
        summary: 一句話摘要
        tags: 四維標籤，格式 {"what": "...", "why": "...", "how": "...", "who": "..."}
        status: 狀態（active/paused/completed/planned），預設 active
        id: 可選，更新時提供既有 ID
        parent_id: 可選，父實體 ID
        details: 可選，額外結構化資訊
        confirmed_by_user: 是否已經由人確認，預設 false
    """
    data = {
        "name": name,
        "type": type,
        "summary": summary,
        "tags": tags,
        "status": status,
        "id": id,
        "parent_id": parent_id,
        "details": details,
        "confirmed_by_user": confirmed_by_user,
    }
    try:
        result = await ontology_service.upsert_entity(data)
        return _serialize(result)
    except (ValueError, KeyError, TypeError) as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


@mcp.tool()
async def add_relationship(
    source_entity_id: str,
    target_entity_id: str,
    type: str,
    description: str,
) -> dict:
    """在兩個實體之間建立有向關係。

    當 AI agent 發現兩個實體之間有依賴、服務、歸屬等關係時使用。
    關係類型包括：depends_on、serves、owned_by、part_of、blocks、related_to。

    Args:
        source_entity_id: 來源實體 ID
        target_entity_id: 目標實體 ID
        type: 關係類型（depends_on/serves/owned_by/part_of/blocks/related_to）
        description: 關係描述
    """
    try:
        result = await ontology_service.add_relationship(
            source_id=source_entity_id,
            target_id=target_entity_id,
            rel_type=type,
            description=description,
        )
        return _serialize(result)
    except (ValueError, TypeError) as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


@mcp.tool()
async def upsert_document(
    title: str,
    source: dict,
    tags: dict,
    summary: str,
    linked_entity_ids: list[str] | None = None,
    status: str = "current",
    id: str | None = None,
    confirmed_by_user: bool = False,
) -> dict:
    """建立或更新一個神經層文件 entry（語意代理）。

    當 AI agent 需要在 ontology 中註冊一份新文件或更新既有文件的
    metadata 時使用。這不是上傳文件內容，而是建立文件的語意代理，
    包含標題、來源、標籤、摘要等 metadata。

    Args:
        title: 文件標題
        source: 來源資訊，格式 {"type": "github", "uri": "...", "adapter": "github"}
        tags: 四維標籤，格式 {"what": [...], "why": "...", "how": "...", "who": [...]}
        summary: 文件摘要
        linked_entity_ids: 可選，關聯的實體 ID 列表
        status: 文件狀態（current/stale/archived/draft/conflict），預設 current
        id: 可選，更新時提供既有 ID
        confirmed_by_user: 是否已經由人確認，預設 false
    """
    data = {
        "title": title,
        "source": source,
        "tags": tags,
        "summary": summary,
        "linked_entity_ids": linked_entity_ids or [],
        "status": status,
        "id": id,
        "confirmed_by_user": confirmed_by_user,
    }
    try:
        result = await ontology_service.upsert_document(data)
        return _serialize(result)
    except (ValueError, KeyError, TypeError) as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


@mcp.tool()
async def upsert_protocol(
    entity_id: str,
    entity_name: str,
    content: dict,
    gaps: list[dict] | None = None,
    version: str = "1.0",
    id: str | None = None,
    confirmed_by_user: bool = False,
) -> dict:
    """建立或更新一個 Context Protocol。

    Context Protocol 是 ontology 的 view——從 ontology 自動生成，
    人微調確認。當 AI agent 需要為某個實體建立或更新其 Protocol 時使用。

    Args:
        entity_id: 對應的實體 ID
        entity_name: 對應的實體名稱
        content: Protocol 內容，格式 {"what": {...}, "why": {...}, "how": {...}, "who": {...}}
        gaps: 可選，已知缺口列表，格式 [{"description": "...", "priority": "red/yellow/green"}]
        version: 版本號，預設 "1.0"
        id: 可選，更新時提供既有 ID
        confirmed_by_user: 是否已經由人確認，預設 false
    """
    data = {
        "entity_id": entity_id,
        "entity_name": entity_name,
        "content": content,
        "gaps": gaps or [],
        "version": version,
        "id": id,
        "confirmed_by_user": confirmed_by_user,
    }
    try:
        result = await ontology_service.upsert_protocol(data)
        return _serialize(result)
    except (ValueError, KeyError, TypeError) as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


@mcp.tool()
async def add_blindspot(
    description: str,
    severity: str,
    suggested_action: str,
    related_entity_ids: list[str] | None = None,
    status: str = "open",
    id: str | None = None,
    confirmed_by_user: bool = False,
) -> dict:
    """記錄一個新發現的盲點。

    當 AI agent 在分析 ontology 時發現知識缺口、風險或矛盾時使用。
    盲點是 ZenOS 的核心差異化功能：從跨產品關係圖中推斷問題。

    Args:
        description: 盲點描述
        severity: 嚴重程度（red/yellow/green）
        suggested_action: 建議的處理方式
        related_entity_ids: 可選，相關的實體 ID 列表
        status: 狀態（open/acknowledged/resolved），預設 open
        id: 可選，更新時提供既有 ID
        confirmed_by_user: 是否已經由人確認，預設 false
    """
    data = {
        "description": description,
        "severity": severity,
        "suggested_action": suggested_action,
        "related_entity_ids": related_entity_ids or [],
        "status": status,
        "id": id,
        "confirmed_by_user": confirmed_by_user,
    }
    try:
        result = await ontology_service.add_blindspot(data)
        return _serialize(result)
    except (ValueError, KeyError, TypeError) as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


@mcp.tool()
async def confirm(collection: str, id: str) -> dict:
    """將一個 AI 產出的 draft 標記為「人已確認」。

    ZenOS 的核心原則：AI 產出 = draft，人確認 = 生效。
    當使用者審閱過某個實體/文件/Protocol/盲點後，用此 tool 確認。

    Args:
        collection: 集合名稱（entities/documents/protocols/blindspots）
        id: 該項目的 ID
    """
    try:
        result = await ontology_service.confirm(collection, id)
        return result
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return {"error": "NOT_FOUND", "message": error_msg}
        return {"error": "INVALID_INPUT", "message": error_msg}


@mcp.tool()
async def list_unconfirmed(collection: str | None = None) -> dict:
    """列出所有尚未經人確認的項目。

    用於治理流程：查看哪些 AI 產出還需要人工審閱確認。
    可按集合篩選，或一次列出所有集合的未確認項目。

    Args:
        collection: 可選，按集合篩選（entities/documents/protocols/blindspots）
    """
    try:
        result = await ontology_service.list_unconfirmed(collection)
        # Serialize each item in each collection
        serialized: dict = {}
        for col_name, items in result.items():
            serialized[col_name] = [_serialize(item) for item in items]
        return serialized
    except ValueError as e:
        return {"error": "INVALID_INPUT", "message": str(e)}


# ===================================================================
# Governance Engine Tools (3) — ontology-wide analysis
# ===================================================================


@mcp.tool()
async def run_quality_check() -> dict:
    """執行 ontology 品質檢查（9 項檢查清單）。

    對整個 ontology 進行全面品質評估，包括：實體完整性、
    標籤品質、關係覆蓋率、Protocol 涵蓋度等。
    回傳總分（0-100）和每項檢查的通過/失敗/警告狀態。
    適合在每次大幅修改後或定期健檢時使用。
    """
    report = await governance_service.run_quality_check()
    return _serialize(report)


@mcp.tool()
async def run_staleness_check() -> dict:
    """偵測 ontology 中的陳舊模式（staleness patterns）。

    掃描所有實體和文件，找出長時間未更新、可能已過時的項目。
    回傳每個陳舊警告的模式、描述、影響範圍和建議處理方式。
    適合定期執行，確保 ontology 保持新鮮。
    """
    warnings = await governance_service.run_staleness_check()
    return {
        "warnings": [_serialize(w) for w in warnings],
        "count": len(warnings),
    }


@mcp.tool()
async def run_blindspot_analysis() -> dict:
    """執行跨實體的盲點推斷分析。

    透過交叉比對 ontology 各層（實體、文件、關係），自動推斷
    出可能存在但尚未被記錄的知識盲點。這是 ZenOS 最核心的
    差異化功能——從跨產品關係圖中推斷老闆沒注意到的問題。
    分析結果會產生新的 Blindspot entries。
    """
    blindspots = await governance_service.run_blindspot_analysis()
    return {
        "blindspots": [_serialize(b) for b in blindspots],
        "count": len(blindspots),
    }


# ===================================================================
# Entrypoint
# ===================================================================

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("sse", "http"):
        port = int(os.environ.get("PORT", "8080"))
        app = ApiKeyMiddleware(mcp.http_app(transport="streamable-http"))
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
