"""MCP tool: get — retrieve one specific item by name or ID."""

from __future__ import annotations

import logging

from zenos.domain.partner_access import is_guest
from zenos.application.identity.source_access_policy import filter_sources_for_partner

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import (
    _serialize,
    _document_linkage_fields,
    _load_document_relationships,
    _inject_workspace_context,
    _enrich_task_result,
    _unified_response,
    _error_response,
    _format_not_found,
    _validate_id_prefix,
)
from zenos.interface.mcp._include import (
    VALID_ENTITY_INCLUDES,
    validate_include,
    log_deprecation_warning,
    build_entity_response,
)
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


def _sanitize_entity_sources(payload: dict, partner: dict | None) -> dict:
    if "sources" in payload and isinstance(payload.get("sources"), list):
        payload["sources"] = filter_sources_for_partner(payload["sources"], partner)
    return payload

async def _resolve_id_prefix_for_get(
    prefix: str, collection: str, partner_id: str,
) -> str | dict:
    """Resolve an id_prefix to either a single full id or a rejection response.

    Returns:
        str — the single matched full id (caller should proceed with exact match)
        dict — a _unified_response rejection (0, 2-10, or 11+ matches)
    """
    import zenos.interface.mcp as mcp

    # Normalize prefix to lowercase so uppercase input matches lowercase stored IDs
    prefix = prefix.lower()

    # Dispatch to per-collection repo
    if collection == "entities":
        if mcp.entity_repo is None:
            return _error_response(
                status="rejected", error_code="SERVICE_UNAVAILABLE",
                message="entity_repo not initialized",
            )
        items = await mcp.entity_repo.find_by_id_prefix(prefix, partner_id)
        candidates = [{"id": e.id, "name": e.name, "type": e.type} for e in items]
    elif collection == "documents":
        if mcp.entity_repo is None:
            return _error_response(
                status="rejected", error_code="SERVICE_UNAVAILABLE",
                message="entity_repo not initialized",
            )
        items = await mcp.entity_repo.find_by_id_prefix(prefix, partner_id)
        items = [e for e in items if e.type == "document"]
        candidates = [{"id": e.id, "name": e.name, "type": "document"} for e in items]
    elif collection == "blindspots":
        if mcp.blindspot_repo is None:
            return _error_response(
                status="rejected", error_code="SERVICE_UNAVAILABLE",
                message="blindspot_repo not initialized",
            )
        items = await mcp.blindspot_repo.find_by_id_prefix(prefix, partner_id)
        candidates = [{"id": b.id, "name": b.description[:60] if b.description else b.id, "type": "blindspot"} for b in items]
    elif collection == "tasks":
        if mcp.task_repo is None:
            return _error_response(
                status="rejected", error_code="SERVICE_UNAVAILABLE",
                message="task_repo not initialized",
            )
        items = await mcp.task_repo.find_by_id_prefix(prefix, partner_id)
        candidates = [{"id": t.id, "name": t.title, "type": "task"} for t in items]
    elif collection == "entries":
        if mcp.entry_repo is None:
            return _error_response(
                status="rejected", error_code="SERVICE_UNAVAILABLE",
                message="entry_repo not initialized",
            )
        items = await mcp.entry_repo.find_by_id_prefix(prefix, partner_id)
        candidates = [{"id": e.id, "name": e.content[:60] if e.content else e.id, "type": e.type} for e in items]
    else:
        # Unknown collection — will be handled by the main get() dispatch below
        return _error_response(
            status="rejected",
            error_code="INVALID_INPUT",
            message=(
                f"id_prefix 不支援 collection '{collection}'。"
                f"支援：entities, documents, blindspots, tasks, entries"
            ),
        )

    count = len(items)

    if count == 0:
        return _unified_response(
            status="rejected",
            data={},
            rejection_reason=f"id_prefix '{prefix}' matches 0 {collection}",
        )

    if count == 1:
        # Unique match — return the resolved full id
        return candidates[0]["id"]

    if count >= 11:
        return _unified_response(
            status="rejected",
            data={"hint": "超過 10 筆，請增加 prefix 長度"},
            rejection_reason="AMBIGUOUS_PREFIX",
        )

    # 2–10 matches
    return _unified_response(
        status="rejected",
        data={"candidates": candidates[:10]},
        rejection_reason="AMBIGUOUS_PREFIX",
    )


async def get(
    collection: str,
    name: str | None = None,
    id: str | None = None,
    id_prefix: str | None = None,
    workspace_id: str | None = None,
    include: list[str] | None = None,
    intent: str | None = None,
    top_k_per_hop: int | None = None,
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

    include 參數（僅對 collection="entities" 有效）：
    - include=["summary"]        → 快速辨識 / capture：只回傳 entity 本體 + source_count，token 用量最小
    - include=["relationships"]  → 沿圖找鄰居：加回 outgoing/incoming relationships 陣列
    - include=["impact_chain"]   → 影響範圍分析：加回 impact_chain + reverse_impact_chain
    - include=["sources"]        → 找 L3 關聯文件：加回完整 sources 陣列（取代 source_count）
    - include=["entries"]        → 最近 decision / insight：加回最新 5 條 active_entries
    - include=["all"]            → 完整 payload：等同不傳 include 的 eager dump，但不 log warning

    可以組合多個值，例如：
    - include=["summary", "relationships"] → entity 本體 + outgoing/incoming
    - include=["summary", "impact_chain"]  → entity 本體 + 影響鏈

    不傳 include（預設）行為等同 include=["all"]，但會 log deprecation warning。
    ADR-040 Phase B 將把預設改為 include=["summary"]。

    額外參數（僅對 include=["impact_chain"] 或 include=["all"] 有效，其他情況忽略）：
    - intent: str | None — 要找什麼？用它的語意 embedding 排序 neighbor。
      範例：get(name="MCP 介面設計", include=["impact_chain"], intent="治理 audit")
    - top_k_per_hop: int | None — 每層 BFS 只保留相關度前 K 名，省 token。
      範例：get(..., include=["impact_chain"], top_k_per_hop=3)

    Args:
        collection: entities/documents/protocols/blindspots/tasks
        name: 項目名稱（entities 和 protocols 支援按名稱查詢）
        id: 項目 ID（所有集合都支援，32-char hex）
        id_prefix: 選填。ID 前綴查詢（至少 4 字元 hex）。與 id 互斥。
            唯一匹配 → 回傳完整 payload；多筆 → rejected + AMBIGUOUS_PREFIX + candidates。
            此參數對讀取操作有效；write/confirm/handoff 不接受 id_prefix。
        workspace_id: 選填。切換到指定 workspace 執行查詢（必須在你的可用列表內）。
        include: 選填。控制回傳欄位集合（僅 entities 有效）。
            支援值：summary / relationships / entries / impact_chain / sources / all
            範例：include=["summary"]、include=["all"]
        intent: 選填。語意排序意圖（僅對 include=[impact_chain] 或 include=[all] 有效）。
            傳入自然語言描述，用來對 impact_chain neighbor 按語意相關度排序。
        top_k_per_hop: 選填。每層 BFS 最多保留幾名 neighbor（僅對 include=[impact_chain] 或 include=[all] 有效）。
            用來限制 impact_chain 的大小，搭配 intent 使用可大幅降低 payload。
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    await _ensure_services()
    # id and id_prefix are mutually exclusive
    if id and id_prefix:
        return _error_response(
            status="rejected",
            error_code="INVALID_INPUT",
            message="id 與 id_prefix 互斥，只能傳其中一個",
        )
    if not name and not id and not id_prefix:
        return _error_response(
            status="rejected",
            error_code="INVALID_INPUT",
            message="Must provide either name, id, or id_prefix",
        )

    # Handle id_prefix routing: resolve prefix to a single id or reject
    if id_prefix is not None:
        prefix_err = _validate_id_prefix(id_prefix)
        if prefix_err:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message=f"id_prefix 必須為 4+ 字元 hex：{prefix_err}",
            )
        # Look up prefix against the appropriate repo
        partner_ctx = _current_partner.get() or {}
        pid = str(partner_ctx.get("id") or "")
        prefix_result = await _resolve_id_prefix_for_get(
            id_prefix, collection, pid,
        )
        if isinstance(prefix_result, dict):
            # Already a response (0, 2+, or 11+ matches)
            return prefix_result
        # prefix_result is the resolved full ID — proceed as exact match
        id = prefix_result

    partner = _current_partner.get() or {}

    if collection == "entities":
        # Validate include before doing any DB work — fail fast on bad input
        include_set, include_err = validate_include(include, VALID_ENTITY_INCLUDES)
        if include_err is not None:
            return include_err

        if name:
            result = await _mcp.ontology_service.get_entity(name)
        elif id:
            entity = await _mcp.entity_repo.get_by_id(id)
            if entity is None:
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=_format_not_found("Entity", id),
                )
            rels = await _mcp.relationship_repo.list_by_entity(id)
            from zenos.application.knowledge.ontology_service import EntityWithRelationships
            result = EntityWithRelationships(entity=entity, relationships=rels)
        else:
            result = None
        if result is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message="Entity not found",
            )
        if partner and is_guest(partner):
            allowed_ids = await _guest_allowed_entity_ids()
            if not allowed_ids or not _is_document_like_entity_visible_for_guest(result.entity, allowed_ids):
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=_format_not_found("Entity", result.entity.id) if id else "Entity not found",
                )
            if not _is_entity_visible(result.entity):
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=_format_not_found("Entity", result.entity.id) if id else "Entity not found",
                )
        elif not _is_entity_visible(result.entity):
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Entity", result.entity.id) if id else "Entity not found",
            )

        eid = result.entity.id

        # Resolve visible relationships (needed for both paths). Also keep the
        # peer Entity object so we can enrich each rel dict with peer_parent_id
        # / peer_l1_id (DF-20260419-9 F9 — saves governance audit an extra
        # get() per peer just to check subtree membership).
        visible_rel_pairs: list[tuple] = []  # list of (Relationship, peer Entity)
        if result.relationships:
            allowed_ids = await _guest_allowed_entity_ids() if partner and is_guest(partner) else set()
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
                visible_rel_pairs.append((rel, other_entity))
        visible_relationships = [r for r, _ in visible_rel_pairs]

        # Compute L1 root for each peer once. Builds entity map lazily only
        # when we have at least one visible peer.
        peer_l1_map: dict[str, str | None] = {}
        if visible_rel_pairs:
            _all_entities = await _mcp.entity_repo.list_all()
            _emap_for_root = {e.id: e for e in _all_entities if e.id}
            from zenos.application.knowledge.ontology_service import _find_product_root
            for _, peer in visible_rel_pairs:
                if peer.id and peer.id not in peer_l1_map:
                    peer_l1_map[peer.id] = _find_product_root(peer.id, _emap_for_root)

        def _enrich_rel_dict(rel, peer_entity) -> dict:
            d = _serialize(rel)
            d["peer_parent_id"] = peer_entity.parent_id
            d["peer_l1_id"] = peer_l1_map.get(peer_entity.id) if peer_entity.id else None
            return d

        if include_set is None or "all" in include_set:
            # Eager-dump path.
            # include=None  → deprecation warning (caller bypassing include)
            # include=["all"] → explicit full payload, no warning
            if include_set is None:
                caller_id = partner.get("id") if partner else None
                log_deprecation_warning("get", "entities", str(caller_id) if caller_id else None)

            response = _sanitize_entity_sources(_serialize(result), partner)
            if visible_rel_pairs:
                response["outgoing_relationships"] = [
                    _enrich_rel_dict(r, peer) for r, peer in visible_rel_pairs
                    if r.source_entity_id == eid
                ]
                response["incoming_relationships"] = [
                    _enrich_rel_dict(r, peer) for r, peer in visible_rel_pairs
                    if r.source_entity_id != eid
                ]
                response.pop("relationships", None)
            active_entries = await _mcp.entry_repo.list_by_entity(eid) if eid else []
            response["active_entries"] = [_serialize(e) for e in active_entries]
            if eid:
                response["impact_chain"] = await _mcp.ontology_service.compute_impact_chain(
                    eid, direction="forward", intent=intent, top_k_per_hop=top_k_per_hop,
                )
                response["reverse_impact_chain"] = await _mcp.ontology_service.compute_impact_chain(
                    eid, direction="reverse", intent=intent, top_k_per_hop=top_k_per_hop,
                )
            _schedule_tool_event("get", eid, None, None)
            return _unified_response(data=_inject_workspace_context(response))

        # Selective include path: only fetch what is requested
        entity_dict = _sanitize_entity_sources(_serialize(result.entity), partner)

        # Fetch data only for requested sections
        rel_dicts: list[dict] | None = None
        if "relationships" in include_set:
            rel_dicts = []
            for r, peer in visible_rel_pairs:
                d = _enrich_rel_dict(r, peer)
                d["_direction"] = "outgoing" if r.source_entity_id == eid else "incoming"
                rel_dicts.append(d)

        entries_dicts: list[dict] | None = None
        if "entries" in include_set:
            raw_entries = await _mcp.entry_repo.list_by_entity(eid) if eid else []
            # Sort by updated_at DESC (newest first)
            raw_entries_sorted = sorted(
                raw_entries,
                key=lambda e: getattr(e, "updated_at", None) or getattr(e, "created_at", None),
                reverse=True,
            )
            entries_dicts = [_serialize(e) for e in raw_entries_sorted]

        fwd_impact: list[dict] | None = None
        rev_impact: list[dict] | None = None
        if "impact_chain" in include_set:
            if eid:
                fwd_impact = await _mcp.ontology_service.compute_impact_chain(
                    eid, direction="forward", intent=intent, top_k_per_hop=top_k_per_hop,
                )
                rev_impact = await _mcp.ontology_service.compute_impact_chain(
                    eid, direction="reverse", intent=intent, top_k_per_hop=top_k_per_hop,
                )

        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=rel_dicts,
            entries=entries_dicts,
            forward_impact=fwd_impact,
            reverse_impact=rev_impact,
            include_set=include_set,
        )
        _schedule_tool_event("get", eid, None, None)
        return _unified_response(data=_inject_workspace_context(response))

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
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message="Protocol not found",
            )
        if not await _is_protocol_visible(result):
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message="Protocol not found",
            )
        return _unified_response(data=_inject_workspace_context(_serialize(result)))

    elif collection == "documents":
        doc_id = id or name
        if not doc_id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="Provide id for documents",
            )
        # Try entity(type=document) first, then legacy documents
        result = await _mcp.ontology_service.get_document(doc_id)
        if result is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Document", doc_id),
            )
        relationships = await _load_document_relationships(result.id)
        if partner and is_guest(partner):
            allowed_ids = await _guest_allowed_entity_ids()
            if not allowed_ids or not _is_document_like_entity_visible_for_guest(result, allowed_ids, relationships):
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=_format_not_found("Document", doc_id),
                )
            if hasattr(result, "visibility") and not _is_entity_visible(result):
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=_format_not_found("Document", doc_id),
                )
        elif not _is_entity_visible(result):
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Document", doc_id),
            )
        serialized = _sanitize_entity_sources(_serialize(result), partner)
        entity_map = None
        try:
            all_entities = await _mcp.ontology_service._entities.list_all()
            entity_map = {e.id: e for e in all_entities if e.id}
        except Exception:
            entity_map = None
        serialized.update(_document_linkage_fields(result, relationships, entity_map=entity_map))
        # ADR-022: enrich sources with canonical_type
        from zenos.domain.doc_types import canonical_type as compute_canonical_type
        for src in (serialized.get("sources") or []):
            if src.get("doc_type"):
                src["canonical_type"] = compute_canonical_type(src["doc_type"])
        return _unified_response(data=_inject_workspace_context(serialized))

    elif collection == "blindspots":
        if not id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="Provide id for blindspots",
            )
        result = await _mcp.blindspot_repo.get_by_id(id)
        if result is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Blindspot", id),
            )
        if not await _is_blindspot_visible(result):
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Blindspot", id),
            )
        return _unified_response(data=_inject_workspace_context(_serialize(result)))

    elif collection == "tasks":
        if not id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="Provide id for tasks",
            )
        enriched = await _mcp.task_service.get_task_enriched(id)
        if enriched is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Task", id),
            )
        task_obj, _ = enriched
        if not await _is_task_visible(task_obj):
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Task", id),
            )
        return _unified_response(data=_inject_workspace_context(await _enrich_task_result(task_obj)))

    else:
        return _error_response(
            status="rejected",
            error_code="INVALID_INPUT",
            message=(
                f"Unknown collection '{collection}'. "
                f"Use: entities, documents, protocols, blindspots, tasks"
            ),
        )
