"""MCP tool: plan — create, update, get, and list plans (Action Layer grouping primitive)."""

from __future__ import annotations

import logging

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import _unified_response
from zenos.interface.mcp._audit import _audit_log
from zenos.application.action.plan_service import _plan_to_dict

logger = logging.getLogger(__name__)


async def _plan_handler(
    action: str,
    goal: str | None = None,
    owner: str | None = None,
    entry_criteria: str | None = None,
    exit_criteria: str | None = None,
    project: str | None = None,
    project_id: str | None = None,
    id: str | None = None,
    status: str | None = None,
    result: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Core plan handler — extracted for testability."""
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    try:
        partner = _current_partner.get()
        partner_default_project = partner.get("defaultProject", "") if partner else ""
        actor_id = (partner or {}).get("id")

        if action == "create":
            if not goal:
                return _unified_response(
                    status="rejected", data={},
                    rejection_reason="goal is required for plan create",
                )
            created_by = actor_id
            if not created_by:
                return _unified_response(
                    status="rejected", data={},
                    rejection_reason="created_by cannot be determined — no authenticated partner",
                )

            effective_project = project or partner_default_project

            if _mcp.plan_service is None:
                await _ensure_services()
            plan = await _mcp.plan_service.create_plan({
                "goal": goal,
                "created_by": created_by,
                "owner": owner,
                "entry_criteria": entry_criteria,
                "exit_criteria": exit_criteria,
                "project": effective_project,
                "project_id": project_id,
                "updated_by": created_by,
            })
            _audit_log(
                event_type="plan.create",
                target={"collection": "plans", "id": plan.id},
                changes={"goal": goal},
            )
            return _unified_response(data=_plan_to_dict(plan))

        elif action == "update":
            if not id:
                return _unified_response(
                    status="rejected", data={},
                    rejection_reason="id is required for plan update",
                )

            updates: dict = {}
            if status is not None:
                updates["status"] = status
            if result is not None:
                updates["result"] = result
            if goal is not None:
                updates["goal"] = goal
            if owner is not None:
                updates["owner"] = owner
            if entry_criteria is not None:
                updates["entry_criteria"] = entry_criteria
            if exit_criteria is not None:
                updates["exit_criteria"] = exit_criteria
            if project is not None:
                updates["project"] = project
            if project_id is not None:
                updates["project_id"] = project_id
            if actor_id:
                updates["updated_by"] = actor_id

            if _mcp.plan_service is None:
                await _ensure_services()
            plan = await _mcp.plan_service.update_plan(id, updates)
            _audit_log(
                event_type="plan.update",
                target={"collection": "plans", "id": id},
                changes={"updates": updates},
            )
            return _unified_response(data=_plan_to_dict(plan))

        elif action == "get":
            if not id:
                return _unified_response(
                    status="rejected", data={},
                    rejection_reason="id is required for plan get",
                )
            if _mcp.plan_service is None:
                await _ensure_services()
            plan_dict = await _mcp.plan_service.get_plan(id)
            return _unified_response(data=plan_dict)

        elif action == "list":
            status_filter: list[str] | None = None
            if status:
                status_filter = [s.strip() for s in status.split(",") if s.strip()]

            if _mcp.plan_service is None:
                await _ensure_services()
            plans = await _mcp.plan_service.list_plans(
                status=status_filter,
                project=project or None,
                limit=limit,
                offset=offset,
            )
            return _unified_response(data={"plans": [_plan_to_dict(p) for p in plans]})

        else:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason=f"Unknown action '{action}'. Use: create, update, get, list",
            )

    except ValueError as e:
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))


async def plan(
    action: str,  # "create" | "update" | "get" | "list"
    goal: str | None = None,
    owner: str | None = None,
    entry_criteria: str | None = None,
    exit_criteria: str | None = None,
    project: str | None = None,
    project_id: str | None = None,
    id: str | None = None,
    status: str | None = None,
    result: str | None = None,
    limit: int = 50,
    offset: int = 0,
    workspace_id: str | None = None,
) -> dict:
    """管理 Action Layer 的 Plan primitive（任務群組 + 排序 + 所有權 + 完成邊界）。

    Plan 是 Task 的上層容器，定義了一組任務的共同目標、進入條件、完成條件。
    Plan 不能被刪除，只能 cancel。

    使用時機：
    - 建 Plan → action="create"（必填：goal）
    - 改狀態/欄位 → action="update"（必填：id）
    - 取單一 Plan（含 tasks_summary） → action="get"（必填：id）
    - 列出 Plans → action="list"

    狀態流：
    - draft → active（任一下轄 task 進入 in_progress 時自動推進）
    - draft → cancelled（直接取消）
    - active → completed（需所有 task 在 terminal state + result 非空）
    - active → cancelled
    - completed / cancelled → 不可再轉

    Args:
        action: "create" | "update" | "get" | "list"
        goal: Plan 目標描述（create 必填）
        owner: 負責人識別（user ID 或名稱）
        entry_criteria: 進入條件（何時算 Plan 可以開始）
        exit_criteria: 完成條件（何時算 Plan 達成目標）
        project: 所屬專案識別碼（如 "zenos"），未傳時使用 partner 預設
        project_id: 連結到 product/project entity ID（選填）
        id: Plan ID（update/get 必填）
        status: 目標狀態（update 時使用）
        result: 完成產出描述（完成 Plan 時必填）
        limit: list 時的分頁大小（預設 50）
        offset: list 時的分頁偏移（預設 0）
        workspace_id: 切換到指定 workspace 執行（選填）
    """
    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    return await _plan_handler(
        action=action,
        goal=goal,
        owner=owner,
        entry_criteria=entry_criteria,
        exit_criteria=exit_criteria,
        project=project,
        project_id=project_id,
        id=id,
        status=status,
        result=result,
        limit=limit,
        offset=offset,
    )
