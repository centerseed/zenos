"""MCP tools: read_source, batch_update_sources — document source access."""

from __future__ import annotations

import inspect
import logging

from zenos.domain.partner_access import is_guest

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import (
    _serialize,
    _unified_response,
    _build_governance_hints,
    _error_response,
)
from zenos.interface.mcp._visibility import (
    _is_entity_visible,
    _guest_allowed_entity_ids,
    _is_document_like_entity_visible_for_guest,
)
from zenos.interface.mcp._audit import _audit_log

logger = logging.getLogger(__name__)


async def read_source(doc_id: str, source_id: str | None = None) -> dict:
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
        source_id: 可選。指定要讀取的 source（用於 doc_role=index 的多 source 文件）。
                   不指定時讀取 primary source 或第一個 valid source。
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    await _ensure_services()
    # MCP setup_hint mapping for adapter suggestions
    _SETUP_HINTS: dict[str, str] = {
        "github": "GitHub MCP",
        "gdrive": "Google Drive MCP",
        "notion": "Notion MCP",
        "wiki": "Wiki MCP",
    }

    def _source_status(source: dict) -> str:
        return str(source.get("source_status") or source.get("status") or "valid")

    try:
        doc_record = await _mcp.ontology_service.get_document(doc_id)
        if doc_record is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=f"Document '{doc_id}' not found",
            )
        partner = _current_partner.get() or {}
        if partner and is_guest(partner):
            allowed_ids = await _guest_allowed_entity_ids()
            if not allowed_ids or not _is_document_like_entity_visible_for_guest(doc_record, allowed_ids):
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=f"Document '{doc_id}' not found",
                )
            if hasattr(doc_record, "visibility") and not _is_entity_visible(doc_record):
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=f"Document '{doc_id}' not found",
                )
        elif hasattr(doc_record, "visibility") and not _is_entity_visible(doc_record):
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=f"Document '{doc_id}' not found",
            )

        # --- ADR-022: source_id-aware source selection ---
        sources = doc_record.sources or []
        all_source_info = [
            {
                "source_id": s.get("source_id", ""),
                "label": s.get("label", ""),
                "status": _source_status(s),
                "source_status": _source_status(s),
            }
            for s in sources
        ]

        target_source = None
        if source_id:
            # Find specific source by source_id
            target_source = next((s for s in sources if s.get("source_id") == source_id), None)
            if target_source is None:
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=f"source_id '{source_id}' not found in this document",
                    extra_data={"available_sources": all_source_info},
                )
        else:
            # Primary fallback logic (D6) — prefer primary+valid, then any valid
            # 1. is_primary=true AND valid
            target_source = next(
                (s for s in sources if s.get("is_primary") and _source_status(s) == "valid"),
                None,
            )
            # 2. First valid source (regardless of primary flag)
            if target_source is None:
                target_source = next((s for s in sources if _source_status(s) == "valid"), None)
            # 3. Last stale source (if no valid)
            if target_source is None and sources:
                stale_sources = [s for s in sources if _source_status(s) == "stale"]
                target_source = stale_sources[-1] if stale_sources else sources[-1]

        if target_source is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=f"Document '{doc_id}' has no sources",
            )

        uri = target_source.get("uri", "")
        source_type = target_source.get("type", "")
        source_status = _source_status(target_source)

        # Build alternative_sources (other sources in the same bundle)
        current_sid = target_source.get("source_id", "")
        alternative_sources = [
            s for s in all_source_info
            if s.get("source_id") != current_sid and s.get("status") == "valid"
        ]

        # If target source is stale/unresolvable, return info with setup_hint
        if source_status in ("stale", "unresolvable"):
            return _error_response(
                error_code="SOURCE_UNAVAILABLE",
                message=f"Source '{current_sid or uri}' is currently {source_status}",
                extra_data={
                    "doc_id": doc_id,
                    "source_id": current_sid,
                    "source_type": source_type,
                    "source_status": source_status,
                    "uri": uri,
                    "setup_hint": _SETUP_HINTS.get(source_type, ""),
                    "alternative_sources": alternative_sources,
                    "all_sources_status": all_source_info,
                },
            )

        # Read the actual content via adapter — pass selected URI so the
        # service reads the correct source, not always sources[0].
        result = None
        reader = getattr(_mcp.source_service, "read_source_with_recovery", None)
        if reader is not None:
            maybe = reader(doc_id, source_uri=uri)
            if inspect.isawaitable(maybe):
                result = await maybe
        if result is None:
            result = await _mcp.source_service.read_source(doc_id, source_uri=uri)
        if isinstance(result, str):
            resp = {"doc_id": doc_id, "content": result}
            if current_sid:
                resp["source_id"] = current_sid
            if alternative_sources:
                resp["alternative_sources"] = alternative_sources
            return _unified_response(data=resp)
        if "content" in result:
            resp = {"doc_id": doc_id, "content": result["content"]}
            if current_sid:
                resp["source_id"] = current_sid
            if alternative_sources:
                resp["alternative_sources"] = alternative_sources
            return _unified_response(data=resp)
        # Error result from read_source_with_recovery — enrich with setup_hint
        if "error" in result:
            return _error_response(
                error_code=str(result.get("error", "ADAPTER_ERROR")),
                message=str(result.get("message", "Failed to read source")),
                extra_data={
                    **{k: v for k, v in result.items() if k not in {"error", "message"}},
                    "setup_hint": _SETUP_HINTS.get(result.get("source_type", source_type), ""),
                    "alternative_sources": alternative_sources,
                },
            )
        return _unified_response(data=result)
    except (ValueError, FileNotFoundError):
        return _error_response(
            status="rejected",
            error_code="NOT_FOUND",
            message=f"Document '{doc_id}' not found",
        )
    except PermissionError:
        return _error_response(
            error_code="ADAPTER_ERROR",
            message="Permission denied while reading source",
        )
    except RuntimeError as e:
        return _error_response(
            error_code="ADAPTER_ERROR",
            message=str(e),
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
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp
    from zenos.infrastructure.sql_common import get_pool, upsert_health_cache
    from zenos.infrastructure.context import current_partner_id as _current_partner_id

    await _ensure_services()
    try:
        result = await _mcp.ontology_service.batch_update_document_sources(
            updates, atomic=atomic
        )

        _audit_log(
            event_type="ontology.documents.batch_update_sources",
            target={"collection": "documents", "count": len(updates)},
            changes={"input": updates, "result": result},
        )

        # ADR-020: attach health signal after batch sync
        health_signal = None
        try:
            health_signal = await _mcp.governance_service.compute_health_signal()
            # ADR-021: persist to DB cache for Dashboard consumption
            if health_signal:
                try:
                    pool = await get_pool()
                    pid = _current_partner_id.get() or ""
                    if pid:
                        await upsert_health_cache(pool, pid, health_signal.get("overall_level", "green"))
                except Exception:
                    pass  # cache write is additive; never break the main operation
        except Exception:
            pass  # health signal is additive; never break the main operation

        return _unified_response(
            data=result,
            warnings=[],
            governance_hints=_build_governance_hints(health_signal=health_signal),
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
