"""MCP tool: search — find and list across all collections."""

from __future__ import annotations

import logging

from zenos.application.knowledge.ontology_service import _collect_subtree_ids
from zenos.domain.partner_access import describe_partner_access, is_guest
from zenos.infrastructure.context import (
    current_partner_department,
)

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import (
    _serialize,
    _parse_entity_level,
    _inject_workspace_context,
    _enrich_task_result,
    _unified_response,
    _error_response,
)
from zenos.interface.mcp._visibility import (
    _is_entity_visible,
    _is_task_visible,
    _guest_allowed_entity_ids,
    _is_document_like_entity_visible_for_guest,
)
from zenos.interface.mcp._audit import _schedule_tool_event
from zenos.interface.mcp._include import (
    VALID_SEARCH_INCLUDES,
    validate_include,
    log_deprecation_warning,
    build_search_result,
)
from zenos.domain.task_rules import normalize_task_status

logger = logging.getLogger(__name__)


def _normalize_project_scope(value: object) -> str:
    """Normalize partner project scope input for stable task filtering."""
    if value is None:
        return ""
    return str(value).strip().lower()


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
    workspace_id: str | None = None,
    include: list[str] | None = None,
    mode: str = "hybrid",
    entity_id: str | None = None,
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
    - 列出單一 entity 的所有 entries → collection="entries"，entity_id="..."（可選 query 做二次過濾）
    - 按產品過濾 → product="Paceriz"（by name）或 product_id="product-xxx"（by ID）
    - 控制搜尋層級 → entity_level="L1,L2"（預設只搜 L1+L2，排除 L3 細節）

    不要用這個工具的情境：
    - 已知確切名稱要看完整資料 → 用 get
    - 要讀原始文件內容 → 用 read_source
    - 要搜尋任務 → collection="tasks"（在這裡，不需要用 task 工具）

    query 最長 200 字。

    mode 參數：
    - mode="keyword"  → 純關鍵字 substring（backward compat）
    - mode="semantic" → 語意相似度（query embed + cosine），適合口語化 query
    - mode="hybrid"（預設）→ 0.7 semantic + 0.3 keyword，綜合召回與精確
    範例：search(collection="entities", query="治理怎麼做", mode="semantic")

    include 參數（僅對 collection="entities" 有效）：
    - include=["summary"]  → 快速識別 / capture：每筆回傳 {id, name, type, level, summary_short, score}，token 用量最小
    - include=["tags"]     → 快速分類：在 summary 基礎上加回 tags
    - include=["full"]     → 完整 payload：等同不傳 include 的 eager dump，但不 log warning

    可以組合多個值，例如 include=["summary", "tags"]。
    不傳 include（預設）等同 include=["full"]，但會 log deprecation warning。
    ADR-040 Phase B 將把預設改為 include=["summary"]。

    範例：
    - search(collection="entities", include=["summary"]) → 快速列出所有 entity（低 token）
    - search(collection="entities", include=["full"]) → 完整 payload（等同不傳 include）

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
        entity_level: 控制搜尋的 entity 層級（按 entity.level 欄位過濾）。
            實際 type→level 映射（current codebase）：
              level=1: product
              level=2: module
              level=3: document, goal, role, project
            "L1"      = max_level=1（只含 level=1 的 type：product）
            "L2"      = max_level=2（含 level 1+2：product, module）
            "L1,L2"   = 等同 "L2"（預設行為）
            "L3" / "L1,L2,L3" / "all" = 不過濾 level（含 level=3：project / goal / role / document）
            不傳時預設 max_level=2（排除 L3）。
            ⚠️ project / goal / role 屬 level=3，需要 entity_level="all" 才看得到。
            回傳 response 的 `applied_filters.entity_level` 會 echo 實際套用的 max_level。
        workspace_id: 選填。切換到指定 workspace 執行搜尋（必須在你的可用列表內）。
        include: 選填。控制每筆 entity result 的欄位集合（僅 entities 有效）。
            支援值：summary / tags / full
            範例：include=["summary"]、include=["full"]
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    await _ensure_services()

    # Validate include early — only applies to entities collection, but we reject
    # unknown values regardless so callers get fast feedback.
    include_set, include_err = validate_include(include, VALID_SEARCH_INCLUDES)
    if include_err is not None:
        return include_err

    results: dict = {}
    warnings: list[str] = []

    # DF-20260419-8 F2 fix: empty-query list-all on entities collection
    # previously eager-dumped every entity (129K+ chars for mid-size
    # workspaces, exceeding MCP token limit). When caller passes no query
    # and no explicit include, defer the decision: apply auto-degrade
    # after we know the result count, below, only if large. This keeps
    # ADR-040 Phase A eager-dump behavior intact for small workspaces.
    _list_all_auto_degrade = not query.strip() and collection in ("all", "entities") and include is None

    # Resolve product name → product_id (product takes priority over product_id)
    if product is not None:
        resolved = await _mcp.entity_repo.get_by_name(product)
        if resolved is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=f"找不到名為 '{product}' 的產品。請確認名稱是否正確。",
                extra_data={
                    "hint": "用 search(collection='entities', status='product') 查看所有產品。",
                },
            )
        product_id = resolved.id

    # Parse entity_level → max_level int for domain layer
    max_level = _parse_entity_level(entity_level)

    # Build applied_filters echo (INV3: server-side filters must be transparent).
    # This tells the agent exactly what was excluded, so empty results can be
    # correctly interpreted as "nothing matched" vs "filter excluded candidates".
    _TYPES_AT_OR_BELOW_LEVEL = {
        1: ["product"],
        2: ["product", "module"],
        3: ["product", "module", "document", "goal", "role", "project"],
    }
    applied_filters: dict = {
        "collection": collection,
        "entity_level": {
            "input": entity_level,
            "effective_max_level": max_level,
            "included_types": (
                _TYPES_AT_OR_BELOW_LEVEL.get(max_level) if max_level is not None else None
            ),
            "excluded_types": (
                [
                    t for t in _TYPES_AT_OR_BELOW_LEVEL[3]
                    if t not in _TYPES_AT_OR_BELOW_LEVEL.get(max_level, [])
                ] if max_level is not None else []
            ),
        },
        "visibility_applied": True,
    }
    if product_id is not None:
        applied_filters["product_id"] = product_id
    if confirmed_only is not None:
        applied_filters["confirmed_only"] = confirmed_only
    if status is not None:
        applied_filters["status"] = status

    # Keyword search mode (cross-collection)
    if query.strip() and collection == "all":
        search_results = await _mcp.ontology_service.search(
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
        effective_project_kw = _normalize_project_scope(project) or _normalize_project_scope(
            _partner_ctx.get("defaultProject", "") if _partner_ctx else ""
        )
        all_tasks = await _mcp.task_service.list_tasks(limit=200, project=effective_project_kw or None)
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
        entry_hits = await _mcp.entry_repo.search_content(query, limit=limit, department=partner_department)
        if entry_hits:
            visible_entries = []
            for hit in entry_hits:
                entry_obj = hit["entry"]
                parent_eid = getattr(entry_obj, "entity_id", None)
                if parent_eid:
                    parent_entity = await _mcp.entity_repo.get_by_id(parent_eid)
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

        return _unified_response(
            data=_inject_workspace_context(results),
            warnings=warnings,
            applied_filters=applied_filters,
            completeness="partial",  # keyword search is ranked; may omit matches
        )

    # Collection-specific listing
    collections = (
        [collection] if collection != "all"
        else ["entities", "documents", "protocols", "blindspots", "tasks"]
    )

    for col in collections:
        if col == "entities":
            # mode parameter is only relevant for collection="entities".
            # For all other collections, mode is silently ignored.
            if _mcp.search_service is not None:
                # S05: use SearchService for keyword / semantic / hybrid modes
                raw_results = await _mcp.search_service.search_entities(
                    query,
                    mode=mode,
                    limit=limit + offset + 500,  # fetch extra to allow for visibility filtering
                    filters=None,
                )
                # Extract entities from result dicts and apply visibility + other filters
                entities_with_scores: list[tuple] = []
                for r in raw_results:
                    e = r["_entity"]
                    if not _is_entity_visible(e):
                        continue
                    entities_with_scores.append((e, r["score"], r["score_breakdown"]))

                # Apply L1 scope filter for guests
                _partner_ctx = _current_partner.get() or {}
                _access = describe_partner_access(_partner_ctx) if _partner_ctx else None
                if _access and _access["is_guest"]:
                    all_entities_for_map = await _mcp.ontology_service._entities.list_all()
                    _entity_map = {e.id: e for e in all_entities_for_map if e.id}
                    _allowed: set[str] = set()
                    for _l1_id in _access["authorized_l1_ids"]:
                        _allowed |= _collect_subtree_ids(_l1_id, _entity_map)
                    entities_with_scores = [(e, sc, bd) for e, sc, bd in entities_with_scores if e.id in _allowed]

                # Apply type filter (status used as type for entities)
                type_filter = status if status in (
                    "product", "module", "goal", "role", "project"
                ) else None
                if type_filter is not None:
                    entities_with_scores = [(e, sc, bd) for e, sc, bd in entities_with_scores if e.type == type_filter]

                # Apply level filter
                if max_level is not None:
                    entities_with_scores = [(e, sc, bd) for e, sc, bd in entities_with_scores if (e.level or 1) <= max_level]

                # Apply product_id filter
                if product_id is not None:
                    all_e = await _mcp.ontology_service._entities.list_all()
                    entity_map = {e.id: e for e in all_e if e.id}
                    subtree_ids = _collect_subtree_ids(product_id, entity_map)
                    entities_with_scores = [(e, sc, bd) for e, sc, bd in entities_with_scores if e.id in subtree_ids]

                # DF-20260419-L2d: exclude archived entities from default search
                # unless caller explicitly asks for status="archived" (the same
                # pattern documents collection already uses at line 424).
                # Archived L2 should not pollute discovery / listing flows but
                # stays retrievable via get(id=X).
                if status != "archived":
                    entities_with_scores = [
                        (e, sc, bd) for e, sc, bd in entities_with_scores
                        if e.status != "archived"
                    ]

                if confirmed_only is not None:
                    entities_with_scores = [
                        (e, sc, bd) for e, sc, bd in entities_with_scores
                        if e.confirmed_by_user == confirmed_only
                    ]

                paginated = entities_with_scores[offset:offset + limit]

                # DF-20260419-8 F2: auto-degrade eager dump when list-all
                # response is too large (>20 results). Keeps small workspaces
                # at Phase A eager-dump; protects large ones from token blow-up.
                _effective_include_set = include_set
                if include_set is None and _list_all_auto_degrade and len(paginated) > 20:
                    _effective_include_set = {"summary"}
                    warnings.append(
                        f"search(query=\"\") 回 {len(paginated)} 筆，自動套用 "
                        "include=[\"summary\"] 避免 token 超限；要完整 payload 請傳 include=[\"full\"]"
                    )

                if _effective_include_set is None:
                    # Default legacy path: eager dump + deprecation warning (once per call)
                    _partner_ctx_for_warn = _current_partner.get()
                    _caller_id = str(_partner_ctx_for_warn.get("id")) if _partner_ctx_for_warn else None
                    log_deprecation_warning("search", "entities", _caller_id)
                    items = []
                    for e, score, score_breakdown in paginated:
                        item = _serialize(e)
                        item["score"] = score
                        item["score_breakdown"] = score_breakdown
                        items.append(item)
                else:
                    items = []
                    for e, score, score_breakdown in paginated:
                        item = build_search_result(_serialize(e), score=score, include_set=_effective_include_set)
                        item["score_breakdown"] = score_breakdown
                        items.append(item)
            else:
                # Fallback path when search_service is not yet wired (should not happen in production)
                type_filter = status if status in (
                    "product", "module", "goal", "role", "project"
                ) else None
                entities = await _mcp.ontology_service.list_entities(type_filter=type_filter)
                entities = [e for e in entities if _is_entity_visible(e)]
                _partner_ctx = _current_partner.get() or {}
                _access = describe_partner_access(_partner_ctx) if _partner_ctx else None
                if _access and _access["is_guest"]:
                    all_entities_for_map = await _mcp.ontology_service._entities.list_all()
                    _entity_map = {e.id: e for e in all_entities_for_map if e.id}
                    _allowed: set[str] = set()
                    for _l1_id in _access["authorized_l1_ids"]:
                        _allowed |= _collect_subtree_ids(_l1_id, _entity_map)
                    entities = [e for e in entities if e.id in _allowed]
                if max_level is not None:
                    entities = [e for e in entities if (e.level or 1) <= max_level]
                if product_id is not None:
                    entity_map = {e.id: e for e in entities if e.id}
                    subtree_ids = _collect_subtree_ids(product_id, entity_map)
                    entities = [e for e in entities if e.id in subtree_ids]
                if confirmed_only is not None:
                    entities = [e for e in entities if e.confirmed_by_user == confirmed_only]
                paginated_entities = entities[offset:offset + limit]
                if include_set is None:
                    _partner_ctx_for_warn = _current_partner.get()
                    _caller_id = str(_partner_ctx_for_warn.get("id")) if _partner_ctx_for_warn else None
                    log_deprecation_warning("search", "entities", _caller_id)
                    items = [_serialize(e) for e in paginated_entities]
                else:
                    items = [
                        build_search_result(_serialize(e), score=0.0, include_set=include_set)
                        for e in paginated_entities
                    ]
            results["entities"] = items

        elif col == "documents":
            # Query document entities (type="document") from entities collection
            doc_entities = await _mcp.ontology_service._entities.list_all(type_filter="document")
            doc_entities = [d for d in doc_entities if _is_entity_visible(d)]
            partner_ctx = _current_partner.get()
            if partner_ctx and is_guest(partner_ctx):
                allowed_ids = await _guest_allowed_entity_ids()
                doc_entities = [
                    d for d in doc_entities
                    if allowed_ids and _is_document_like_entity_visible_for_guest(d, allowed_ids)
                ]
            # Exclude archived document entities (dead links confirmed unresolvable)
            doc_entities = [d for d in doc_entities if d.status != "archived"]
            # Apply product_id filter for documents via parent_id chain
            if product_id is not None:
                all_entities = await _mcp.ontology_service._entities.list_all()
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
                entity = await _mcp.ontology_service._entities.get_by_name(entity_name)
                if entity and entity.id:
                    doc_entities = [
                        d for d in doc_entities if d.parent_id == entity.id
                    ]
            if confirmed_only is not None:
                doc_entities = [d for d in doc_entities if d.confirmed_by_user == confirmed_only]
            results["documents"] = [_serialize(d) for d in doc_entities[offset:offset + limit]]

        elif col == "protocols":
            from zenos.interface.mcp._visibility import _is_protocol_visible
            if confirmed_only is False:
                protos = await _mcp.ontology_service._protocols.list_unconfirmed()
            else:
                protos = await _mcp.ontology_service._protocols.list_all(confirmed_only=confirmed_only)
            visible_protos = [p for p in protos if await _is_protocol_visible(p)]
            results["protocols"] = [_serialize(p) for p in visible_protos[offset:offset + limit]]

        elif col == "blindspots":
            from zenos.interface.mcp._visibility import _is_blindspot_visible
            blindspots = await _mcp.ontology_service.list_blindspots(
                entity_name=entity_name, severity=severity
            )
            if confirmed_only is not None:
                blindspots = [
                    b for b in blindspots
                    if b.confirmed_by_user == confirmed_only
                ]
            # DF-20260419-7 F11 fix: apply product_id subtree filter.
            # Previously product_id was silently ignored for blindspots, which
            # meant Monitor audit saw every workspace blindspot regardless of
            # scope. Now: keep blindspot if any related_entity is in the
            # subtree. Strict mode (all related in subtree) may be added later.
            if product_id is not None:
                all_e = await _mcp.ontology_service._entities.list_all()
                entity_map = {e.id: e for e in all_e if e.id}
                subtree_ids = _collect_subtree_ids(product_id, entity_map)
                blindspots = [
                    b for b in blindspots
                    if any(eid in subtree_ids for eid in (b.related_entity_ids or []))
                ]
            visible_bs = [b for b in blindspots if await _is_blindspot_visible(b)]
            results["blindspots"] = [_serialize(b) for b in visible_bs[offset:offset + limit]]

        elif col == "tasks":
            status_list = None
            if status:
                raw_statuses = [s.strip() for s in status.split(",") if s.strip()]
                normalized_statuses = [normalize_task_status(s) for s in raw_statuses]
                legacy_used = [
                    raw for raw, normalized in zip(raw_statuses, normalized_statuses, strict=False)
                    if raw != normalized
                ]
                if legacy_used:
                    warnings.append(
                        "legacy task status alias 已自動改寫："
                        + ", ".join(f"{raw}->{normalize_task_status(raw)}" for raw in legacy_used)
                    )
                status_list = normalized_statuses
            # Auto-fill project from partner context if caller omits it
            _partner = _current_partner.get()
            effective_project = _normalize_project_scope(project) or _normalize_project_scope(
                _partner.get("defaultProject", "") if _partner else ""
            )
            tasks = await _mcp.task_service.list_tasks(
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
            # DF-20260419-7 F12 fix: apply product_id subtree filter.
            # Previously product_id was silently ignored for tasks — Monitor
            # audit saw every workspace task. Now: keep task if any linked
            # entity is in the product subtree.
            if product_id is not None:
                all_e = await _mcp.ontology_service._entities.list_all()
                entity_map = {e.id: e for e in all_e if e.id}
                subtree_ids = _collect_subtree_ids(product_id, entity_map)
                visible_tasks = [
                    t for t in visible_tasks
                    if any(eid in subtree_ids for eid in (t.linked_entities or []))
                ]
            results["tasks"] = [await _enrich_task_result(t) for t in visible_tasks]

        elif col == "entries":
            # DF-20260419-5 F5 fix: support entity_id filter to enumerate all entries
            # under a single entity (no keyword required). When entity_id is set,
            # query is optional; when entity_id is None, query is still required.
            if entity_id:
                partner_department = str(current_partner_department.get() or "all")
                # status filter: accept comma-separated statuses (e.g. "active,superseded")
                # default to active only for backward compat
                status_filter: str | None = "active"
                if status is not None:
                    status_filter = status if status.lower() != "all" else None
                entries_list = await _mcp.entry_repo.list_by_entity(
                    entity_id,
                    status=status_filter,
                    department=partner_department,
                )
                # Apply keyword post-filter if query provided (narrow within entity)
                if query.strip():
                    q = query.lower()
                    entries_list = [
                        e for e in entries_list
                        if q in (e.content or "").lower()
                        or q in (e.context or "").lower()
                    ]
                # Look up entity name once for display
                entity_obj = await _mcp.entity_repo.get_by_id(entity_id)
                entity_name_resolved = entity_obj.name if entity_obj else None
                results["entries"] = [
                    {**_serialize(e), "entity_name": entity_name_resolved}
                    for e in entries_list[:limit]
                ]
            else:
                if not query.strip():
                    return _error_response(
                        status="rejected",
                        error_code="INVALID_INPUT",
                        message=(
                            "search(collection='entries') 需要 query 關鍵字，"
                            "或改用 entity_id= 列出單一 entity 的所有 entries"
                        ),
                    )
                partner_department = str(current_partner_department.get() or "all")
                entry_hits = await _mcp.entry_repo.search_content(
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

    # Collection listing is exhaustive within the declared applied_filters
    # (pagination via limit/offset is ok; the filter scope is fully materialized).
    return _unified_response(
        data=_inject_workspace_context(results),
        warnings=warnings,
        applied_filters=applied_filters,
        completeness="exhaustive",
    )
