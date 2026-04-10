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
)
from zenos.interface.mcp._visibility import (
    _is_entity_visible,
    _is_task_visible,
    _guest_allowed_entity_ids,
    _is_document_like_entity_visible_for_guest,
)
from zenos.interface.mcp._audit import _schedule_tool_event

logger = logging.getLogger(__name__)


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
        workspace_id: 選填。切換到指定 workspace 執行搜尋（必須在你的可用列表內）。
    """
    from zenos.interface.mcp import (
        _ensure_services,
        ontology_service,
        task_service,
        entity_repo,
        entry_repo,
    )

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
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

        return _inject_workspace_context(results)

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
            # Apply L1 scope filter for guests
            _partner_ctx = _current_partner.get() or {}
            _access = describe_partner_access(_partner_ctx) if _partner_ctx else None
            if _access and _access["is_guest"]:
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
            from zenos.interface.mcp._visibility import _is_protocol_visible
            if confirmed_only is False:
                protos = await ontology_service._protocols.list_unconfirmed()
            else:
                protos = await ontology_service._protocols.list_all(confirmed_only=confirmed_only)
            visible_protos = [p for p in protos if await _is_protocol_visible(p)]
            results["protocols"] = [_serialize(p) for p in visible_protos[offset:offset + limit]]

        elif col == "blindspots":
            from zenos.interface.mcp._visibility import _is_blindspot_visible
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

    return _inject_workspace_context(results)
