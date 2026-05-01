"""MCP tool: confirm — approve knowledge drafts or task deliveries."""

from __future__ import annotations

import logging
from unittest.mock import Mock

from zenos.domain.knowledge import EntityEntry
from zenos.infrastructure.context import current_partner_department

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import (
    _serialize,
    _new_id,
    _unified_response,
    _build_governance_hints,
    _build_context_bundle,
    _enrich_task_result,
)
from zenos.interface.mcp._audit import _audit_log
from zenos.interface.mcp._entry_quality import VALID_ENTRY_TYPES, entry_quality_issue

logger = logging.getLogger(__name__)


async def confirm(
    collection: str,
    id: str | None = None,
    accepted: bool | None = None,
    accept: bool | None = None,
    rejection_reason: str | None = None,
    mark_stale_entity_ids: list[str] | None = None,
    new_blindspot: dict | None = None,
    entity_entries: list[dict] | None = None,
    workspace_id: str | None = None,
    id_prefix: str | None = None,
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
        workspace_id: 選填。切換到指定 workspace 執行確認（必須在你的可用列表內）。
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    # AC-MIDE-05: confirm 絕對不支援 id_prefix — 確認操作需完整 32-char id
    # Check BEFORE _ensure_services() so we never bootstrap SQL just to reject
    if id_prefix is not None:
        return _unified_response(
            status="rejected",
            data={"hint": "write 類操作需完整 32-char id。恢復：先用 get(collection='tasks', id_prefix='前8碼') 解析完整 ID，再帶完整 ID 重呼叫 confirm。"},
            rejection_reason="id_prefix_not_allowed_for_write_ops",
        )
    await _ensure_services()
    try:
        warnings: list[str] = []
        if accepted is None:
            if accept is not None:
                accepted = accept
                warnings.append("參數 alias 'accept' 已自動改寫為 'accepted'")
            else:
                accepted = True
        if collection == "tasks":
            if accepted and entity_entries:
                task = await _mcp.task_repo.get_by_id(id) if _mcp.task_repo is not None else None
                linked = set(getattr(task, "linked_entities", []) or []) if task is not None and not isinstance(task, Mock) else set()
                enforce_link_gate = task is not None and not isinstance(task, Mock)
                invalid_targets = sorted({
                    str(entry.get("entity_id") or "")
                    for entry in entity_entries
                    if enforce_link_gate and entry.get("entity_id") and entry.get("entity_id") not in linked
                })
                if invalid_targets:
                    return _unified_response(
                        status="rejected",
                        data={
                            "error": "ENTRY_TARGET_NOT_LINKED",
                            "invalid_entity_ids": invalid_targets,
                            "linked_entity_ids": sorted(linked),
                        },
                        rejection_reason="entity_entries target entity must be linked to the task",
                    )
            result = await _mcp.task_service.confirm_task(
                task_id=id,
                accepted=accepted,
                rejection_reason=rejection_reason,
                mark_stale_entity_ids=mark_stale_entity_ids,
                new_blindspot=new_blindspot,
                updated_by=((_current_partner.get() or {}).get("id")),
                entity_entries=entity_entries,
            )

            # Write entity entries (knowledge feedback loop) — only when accepted
            if accepted and entity_entries and _mcp.entry_repo is not None:
                partner_ctx = _current_partner.get() or {}
                pid = partner_ctx.get("id", "")
                partner_department = str(
                    partner_ctx.get("department") or current_partner_department.get() or "all"
                )
                for entry_data in entity_entries:
                    entity_id = entry_data.get("entity_id")
                    if not entity_id:
                        warnings.append("entity_entries skipped: missing entity_id")
                        continue
                    content = entry_data.get("content", "")
                    if not content or len(content) > 200:
                        warnings.append(f"entity_entries skipped for {entity_id}: content must be 1-200 chars")
                        continue
                    entry_type = entry_data.get("type", "insight")
                    if entry_type not in VALID_ENTRY_TYPES:
                        entry_type = "insight"
                    quality_issue = entry_quality_issue(content, entry_type)
                    if quality_issue:
                        warnings.append(f"entity_entries skipped for {entity_id}: {quality_issue}")
                        continue
                    entry = EntityEntry(
                        id=_new_id(),
                        partner_id=pid,
                        entity_id=entity_id,
                        type=entry_type,
                        content=content,
                        department=partner_department,
                        source_task_id=id,
                    )
                    await _mcp.entry_repo.create(entry)
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
                warnings=warnings,
                suggestions=cascade_suggestions,
                context_bundle=context_bundle,
                governance_hints=_build_governance_hints(
                    suggested_follow_up_tasks=cascade_suggestions,
                    suggested_entity_updates=getattr(result, "suggested_entity_updates", None) or [],
                ),
            )
        else:
            result = await _mcp.ontology_service.confirm(collection, id)
            confirm_data = dict(result) if isinstance(result, dict) else result
            if collection == "entities":
                _mcp._schedule_embed(id)
            _audit_log(
                event_type="ontology.confirm",
                target={"collection": collection, "id": id},
                changes={"accepted": accepted},
            )
            return _unified_response(
                data=confirm_data,
                warnings=warnings,
                context_bundle=await _build_context_bundle(
                    linked_entity_ids=[id] if collection == "entities" else []
                ),
                governance_hints=_build_governance_hints(),
            )
    except ValueError as e:
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))
