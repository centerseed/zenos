"""MCP tool: get — retrieve one specific item by name or ID."""

from __future__ import annotations

import logging

from zenos.domain.partner_access import is_guest

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import _serialize, _inject_workspace_context, _enrich_task_result
from zenos.interface.mcp._visibility import (
    _is_entity_visible,
    _is_protocol_visible,
    _is_blindspot_visible,
    _is_task_visible,
    _guest_allowed_entity_ids,
    _is_document_like_entity_visible_for_guest,
)
from zenos.interface.mcp._audit import _schedule_tool_event

logger = logging.getLogger(__name__)


async def get(
    collection: str,
    name: str | None = None,
    id: str | None = None,
    workspace_id: str | None = None,
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
        workspace_id: 選填。切換到指定 workspace 執行查詢（必須在你的可用列表內）。
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    await _ensure_services()
    if not name and not id:
        return {"error": "INVALID_INPUT", "message": "Must provide either name or id"}

    partner = _current_partner.get() or {}

    if collection == "entities":
        if name:
            result = await _mcp.ontology_service.get_entity(name)
        elif id:
            entity = await _mcp.entity_repo.get_by_id(id)
            if entity is None:
                return {"error": "NOT_FOUND", "message": f"Entity '{id}' not found"}
            rels = await _mcp.relationship_repo.list_by_entity(id)
            from zenos.application.knowledge.ontology_service import EntityWithRelationships
            result = EntityWithRelationships(entity=entity, relationships=rels)
        else:
            result = None
        if result is None:
            return {"error": "NOT_FOUND", "message": f"Entity not found"}
        if partner and is_guest(partner):
            allowed_ids = await _guest_allowed_entity_ids()
            if not allowed_ids or not _is_document_like_entity_visible_for_guest(result.entity, allowed_ids):
                return {"error": "NOT_FOUND", "message": "Entity not found"}
            if not _is_entity_visible(result.entity):
                return {"error": "NOT_FOUND", "message": "Entity not found"}
        elif not _is_entity_visible(result.entity):
            return {"error": "NOT_FOUND", "message": "Entity not found"}
        response = _serialize(result)
        # Split relationships into outgoing/incoming for clearer graph navigation
        eid = result.entity.id
        if result.relationships:
            allowed_ids = await _guest_allowed_entity_ids() if partner and is_guest(partner) else set()
            visible_relationships = []
            for rel in result.relationships:
                other_id = rel.target_id if rel.source_entity_id == eid else rel.source_entity_id
                other_entity = await _mcp.entity_repo.get_by_id(other_id)
                if other_entity is None:
                    continue
                if partner and is_guest(partner):
                    if not allowed_ids or not _is_document_like_entity_visible_for_guest(other_entity, allowed_ids):
                        continue
                    if not _is_entity_visible(other_entity):
                        continue
                elif not _is_entity_visible(other_entity):
                    continue
                visible_relationships.append(rel)
            response["outgoing_relationships"] = [
                _serialize(r) for r in visible_relationships
                if r.source_entity_id == eid
            ]
            response["incoming_relationships"] = [
                _serialize(r) for r in visible_relationships
                if r.source_entity_id != eid
            ]
            # Remove flat list to avoid payload duplication
            response.pop("relationships", None)
        # Attach active entries so callers see the entity as a knowledge container
        active_entries = await _mcp.entry_repo.list_by_entity(eid) if eid else []
        response["active_entries"] = [_serialize(e) for e in active_entries]
        if eid:
            response["impact_chain"] = await _mcp.ontology_service.compute_impact_chain(eid, direction="forward")
            response["reverse_impact_chain"] = await _mcp.ontology_service.compute_impact_chain(eid, direction="reverse")
        _schedule_tool_event("get", eid, None, None)
        return _inject_workspace_context(response)

    elif collection == "protocols":
        if name:
            result = await _mcp.ontology_service.get_protocol(name)
        elif id:
            # Backward compatibility: first treat id as protocol doc id,
            # fallback to legacy behavior where id is entity_id.
            result = await _mcp.protocol_repo.get_by_id(id)
            if result is None:
                result = await _mcp.protocol_repo.get_by_entity(id)
        else:
            result = None
        if result is None:
            return {"error": "NOT_FOUND", "message": "Protocol not found"}
        if not await _is_protocol_visible(result):
            return {"error": "NOT_FOUND", "message": "Protocol not found"}
        return _inject_workspace_context(_serialize(result))

    elif collection == "documents":
        doc_id = id or name
        if not doc_id:
            return {"error": "INVALID_INPUT", "message": "Provide id for documents"}
        # Try entity(type=document) first, then legacy documents
        result = await _mcp.ontology_service.get_document(doc_id)
        if result is None:
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
        if partner and is_guest(partner):
            allowed_ids = await _guest_allowed_entity_ids()
            if not allowed_ids or not _is_document_like_entity_visible_for_guest(result, allowed_ids):
                return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
            if hasattr(result, "visibility") and not _is_entity_visible(result):
                return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
        elif not _is_entity_visible(result):
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}
        serialized = _serialize(result)
        # ADR-022: enrich sources with canonical_type
        from zenos.domain.doc_types import canonical_type as compute_canonical_type
        for src in (serialized.get("sources") or []):
            if src.get("doc_type"):
                src["canonical_type"] = compute_canonical_type(src["doc_type"])
        return _inject_workspace_context(serialized)

    elif collection == "blindspots":
        if not id:
            return {"error": "INVALID_INPUT", "message": "Provide id for blindspots"}
        result = await _mcp.blindspot_repo.get_by_id(id)
        if result is None:
            return {"error": "NOT_FOUND", "message": f"Blindspot '{id}' not found"}
        if not await _is_blindspot_visible(result):
            return {"error": "NOT_FOUND", "message": f"Blindspot '{id}' not found"}
        return _inject_workspace_context(_serialize(result))

    elif collection == "tasks":
        if not id:
            return {"error": "INVALID_INPUT", "message": "Provide id for tasks"}
        enriched = await _mcp.task_service.get_task_enriched(id)
        if enriched is None:
            return {"error": "NOT_FOUND", "message": f"Task '{id}' not found"}
        task_obj, _ = enriched
        if not await _is_task_visible(task_obj):
            return {"error": "NOT_FOUND", "message": f"Task '{id}' not found"}
        return _inject_workspace_context(await _enrich_task_result(task_obj))

    else:
        return {
            "error": "INVALID_INPUT",
            "message": f"Unknown collection '{collection}'. "
            f"Use: entities, documents, protocols, blindspots, tasks",
        }
