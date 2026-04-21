---
type: TD
id: TD-project-progress-console-implementation
status: Draft
linked_spec: SPEC-project-progress-console
created: 2026-04-21
updated: 2026-04-21
---

# 技術設計：Project Progress Console 實作

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-project-progress-console.md`
  - 發現：Spec 已帶 15 條 `AC-PPC-*`，屬於 executable SPEC。P0 核心是 `/projects/[id]` 的 active plans、grouped open work、AI recap、copy prompt，而不是補 task 欄位。
- `docs/decisions/ADR-008-dashboard-multi-view.md`
  - 發現：Dashboard 的 `專案` view 本來就定位給老闆 / PM 日常使用；`任務` view 才是執行層。
- `docs/specs/SPEC-task-view-clarity.md`
  - 發現：`/tasks` 已承接跨專案 task 狀態清晰化與 richer task visibility；本次不應再把 `/projects/[id]` 做成第二個 task board。
- `docs/specs/SPEC-task-kanban-operations.md`
  - 發現：task create / edit / review / handoff 的主操作面仍應留在 `/tasks`。
- `docs/specs/SPEC-task-governance.md`
  - 發現：`milestone = goal entity`、`subtask = parent_task_id != null`、`plan` 是獨立 primitive；產品頁應沿用語義，不可重新發明 kind。
- `docs/specs/SPEC-dashboard-ai-rail.md`
  - 發現：shared AI rail、`CopilotEntryConfig`、`scope_label`、`build_prompt()` 已是正式協議，可直接承接本輪的 AI recap。
- `docs/designs/TD-dashboard-ai-rail-implementation.md`
  - 發現：shared rail shell 與 preset/adapters 分層已定，產品頁應掛 project-specific preset，而不是另做 AI UI。
- `dashboard/src/app/(protected)/projects/page.tsx`
  - 發現：產品 detail 現在直接拼 `getEntityContext + getTasksByEntity + getChildEntities + getAllBlindspots`，且 `tasks` tab 直接 render `TaskBoard`；頂部「Agent 建議」只是切 `timeline` tab，不是 AI recap。
- `dashboard/src/components/TaskBoard.tsx`
  - 發現：看板雖按 `planId` 群組，但 plan 標題缺 read model 時只顯示 UUID 尾碼，證明目前只有 task-centric fallback。
- `dashboard/src/components/TaskDetailDrawer.tsx`
  - 發現：Drawer 可編 `plan_id/plan_order`，但沒有正式 plan 名稱來源。
- `dashboard/src/lib/api.ts`
  - 發現：client 目前沒有 project-progress 或 plan-summary API。
- `src/zenos/interface/dashboard_api.py`
  - 發現：dashboard surface 沒有 `/api/data/plans` 或 project progress aggregate endpoint。
- `src/zenos/application/action/plan_service.py`
  - 發現：server 端其實已有 `get_plan()` 與 `list_plans()`，且 `get_plan()` 會回 `tasks_summary`；缺口在 dashboard API 沒接出來。
- `dashboard/src/components/ai/CopilotRailShell.tsx`
  - 發現：shared shell 已可直接複用，適合作為 AI recap / prompt rail。
- `dashboard/src/lib/copilot/types.ts`
  - 發現：`CopilotEntryConfig` 已支援 `artifact/apply/chat`、`scope_label`、`build_prompt()`，足夠承接產品頁 preset。

### 搜尋但未找到

- `src/zenos/interface/dashboard_api.py` 中搜尋 `/api/data/plans` → 無結果
- `dashboard/src/app/(protected)/projects/page.tsx` 中搜尋 `CopilotRailShell` / `AI recap` / `copy prompt` → 無結果
- `docs/designs/TD-*project-progress*` → 無既有 TD

### 我不確定的事（明確標記）

- [未確認] Phase 0 的 AI recap 是否要把最近一次摘要快取到 server；本 TD 先採 on-demand、前端持有。
- [未確認] list 頁 `/projects` 的卡片 KPI 是否要同步 plan-aware；本輪先把 `/projects/[id]` 做正，list 頁只做最小必要調整。

### 結論

可以開始設計。

本輪不是補 task 欄位，而是補三個缺口：

1. project-level aggregate read model
2. `/projects/[id]` 的 plan-centric console IA
3. 掛在 shared AI rail 上的 recap / copy prompt preset

## Spec 衝突檢查

- `SPEC-project-progress-console` vs `SPEC-task-view-clarity`：無衝突。前者定義管理層產品頁，後者定義 `/tasks` 的執行層可讀性。
- `SPEC-project-progress-console` vs `SPEC-task-kanban-operations`：無衝突。前者不接手 task 操作面，後者仍維持 task 操作主場。
- `SPEC-project-progress-console` vs `SPEC-task-governance`：無衝突。前者沿用 `plan / goal / subtask` 語義，不重定義 core model。
- `SPEC-project-progress-console` vs `SPEC-dashboard-ai-rail`：無衝突。前者新增 project preset，後者提供 shared AI rail 協議。

結論：**Spec 衝突檢查：無衝突。**

## 實作結論

本次實作統一為：

1. **新增 project progress aggregate endpoint**
   Dashboard API 提供一個 product-centric read model，避免前端自行從 tasks/entities 雜湊推導不同口徑。
2. **重構 `/projects/[id]` detail view**
   頁面第一層改成 plan-centric console：Current Plans、Open Work、AI Recap、Copy Prompt。
3. **沿用 shared AI rail**
   不另起新 AI UI。產品頁提供 `CopilotEntryConfig` preset 與本地 prompt generator。

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-PPC-01 | 進產品頁第一層直接顯示 active plans | `src/zenos/interface/dashboard_api.py`, `dashboard/src/app/(protected)/projects/page.tsx` | `acPpc01ActivePlansFirstFold` | STUB |
| AC-PPC-02 | plan 卡顯示 goal / open / blocked / review / updated | `dashboard/src/features/projects/ProjectPlansOverview.tsx` | `acPpc02PlanCardMetrics` | STUB |
| AC-PPC-03 | 無 active plan 時有明確空態 | `dashboard/src/features/projects/ProjectPlansOverview.tsx` | `acPpc03NoActivePlanEmptyState` | STUB |
| AC-PPC-04 | open work 依 plan 分組 | `src/zenos/interface/dashboard_api.py`, `dashboard/src/features/projects/ProjectOpenWorkPanel.tsx` | `acPpc04OpenWorkGroupedByPlan` | STUB |
| AC-PPC-05 | subtask 收在 parent task 底下 | `dashboard/src/features/projects/ProjectOpenWorkPanel.tsx` | `acPpc05SubtasksNestedUnderParent` | STUB |
| AC-PPC-06 | blocked / review / overdue 直接可辨識 | `dashboard/src/features/projects/ProjectOpenWorkPanel.tsx` | `acPpc06RiskSignalsVisible` | STUB |
| AC-PPC-07 | AI recap 涵蓋進度 / plans / blockers / 下一步 / 待決策 | `dashboard/src/features/projects/projectCopilot.ts`, `dashboard/src/features/projects/ProjectRecapRail.tsx` | `acPpc07AiRecapContract` | STUB |
| AC-PPC-08 | 資料少時 AI recap 仍可產生下一步建議 | `dashboard/src/features/projects/projectCopilot.ts` | `acPpc08AiRecapHandlesSparseState` | STUB |
| AC-PPC-09 | copy prompt 含 product context / plans / blockers / recap / next step | `dashboard/src/features/projects/projectPrompt.ts` | `acPpc09CopyPromptContainsContinuationContext` | STUB |
| AC-PPC-10 | 不進 task 詳情也能直接 copy prompt | `dashboard/src/app/(protected)/projects/page.tsx` | `acPpc10CopyPromptAvailableFromProjectPage` | STUB |
| AC-PPC-11 | `/projects/[id]` 第一層不是完整 task board | `dashboard/src/app/(protected)/projects/page.tsx` | `acPpc11ProjectPageNotTaskBoardFirstView` | STUB |
| AC-PPC-12 | 可 drill down 到 task，但不取代主視角 | `dashboard/src/app/(protected)/projects/page.tsx`, `dashboard/src/components/TaskBoard.tsx` | `acPpc12TaskDrillDownWithoutReplacingConsole` | STUB |
| AC-PPC-13 | milestone / phase 可被辨識 | `src/zenos/interface/dashboard_api.py`, `dashboard/src/features/projects/ProjectMilestoneStrip.tsx` | `acPpc13MilestoneStageVisible` | STUB |
| AC-PPC-14 | 顯示近期推進摘要 | `src/zenos/interface/dashboard_api.py`, `dashboard/src/features/projects/ProjectRecentProgress.tsx` | `acPpc14RecentProgressSummaryVisible` | STUB |
| AC-PPC-15 | prompt preset 可按目標 agent 切換 | `dashboard/src/features/projects/projectPrompt.ts`, `dashboard/src/features/projects/ProjectRecapRail.tsx` | `acPpc15PromptPresetSwitching` | STUB |

## Component 架構

### 1. Backend Aggregate Layer

新增 dashboard aggregate endpoint：

- `GET /api/data/projects/{id}/progress`

責任：

- 讀 product entity
- 取得 linked 到該 product 的 tasks
- 反查涉及的 `plan_id`
- 讀 plan 資料與 `tasks_summary`
- 計算 open work、blocked/review/overdue count、next tasks、recent progress、milestone summary
- 回傳單一、口徑一致的 project progress payload

### 2. Frontend Feature Layer

新增：

```text
dashboard/src/features/projects/
  types.ts
  ProjectProgressConsole.tsx
  ProjectPlansOverview.tsx
  ProjectOpenWorkPanel.tsx
  ProjectMilestoneStrip.tsx
  ProjectRecentProgress.tsx
  ProjectRecapRail.tsx
  projectCopilot.ts
  projectPrompt.ts
```

責任切分：

- `ProjectProgressConsole.tsx`
  - 組裝 detail 頁第一層 layout
  - 管理 AI rail open/close、selected next step、selected prompt preset
- `ProjectPlansOverview.tsx`
  - 顯示 active / blocked plans 與 plan metrics
- `ProjectOpenWorkPanel.tsx`
  - 顯示 grouped open work
  - 處理 parent/subtask nesting
- `ProjectMilestoneStrip.tsx`
  - 顯示目前工作落在哪個 milestone / 階段
- `ProjectRecentProgress.tsx`
  - 顯示近期推進摘要
- `ProjectRecapRail.tsx`
  - 掛 shared `CopilotRailShell`
  - 顯示 AI recap 與 copy prompt CTA
- `projectCopilot.ts`
  - 建 `CopilotEntryConfig`
  - 把 aggregate payload 轉成 AI recap prompt context
- `projectPrompt.ts`
  - 依 preset 生成可複製 continuation prompt

### 3. Existing Page Refactor

- `dashboard/src/app/(protected)/projects/page.tsx`
  - 保留 list 頁容器
  - detail 頁改為使用 `getProjectProgress()` + `ProjectProgressConsole`
  - `TaskBoard` 退為 drill-down 區，不再是第一層主內容

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `GET /api/data/projects/{id}/progress` | `id` | `string` | 是 | 回傳產品頁的單一 aggregate payload |
| `getProjectProgress()` | `token, entityId` | `string, string` | 是 | dashboard client wrapper |
| `buildProjectRecapEntry()` | `progress, options` | `ProjectProgressPayload, {...}` | 是 | 產生 AI recap rail preset |
| `buildProjectContinuationPrompt()` | `progress, recap, nextStep, preset` | structured input | 是 | 產生 Claude/Codex 可複製 prompt |

### `GET /api/data/projects/{id}/progress` 回傳草案

```ts
type ProjectProgressPayload = {
  project: Entity
  active_plans: Array<{
    id: string
    goal: string
    status: string
    owner: string | null
    open_count: number
    blocked_count: number
    review_count: number
    updated_at: string | null
    next_tasks: ProjectTaskSummary[]
  }>
  open_work_groups: Array<{
    plan_id: string | null
    plan_goal: string | null
    tasks: ProjectTaskSummary[]
  }>
  milestones: Array<{
    id: string
    name: string
    open_count: number
  }>
  recent_progress: Array<{
    id: string
    kind: "task" | "plan" | "entity"
    title: string
    subtitle: string
    updated_at: string | null
  }>
}
```

### `ProjectTaskSummary` 草案

```ts
type ProjectTaskSummary = {
  id: string
  title: string
  status: string
  priority: string
  assignee_name: string | null
  due_date: string | null
  overdue: boolean
  blocked: boolean
  blocked_reason: string | null
  parent_task_id: string | null
  subtasks?: ProjectTaskSummary[]
}
```

## DB Schema 變更

無。

本輪只補 dashboard API surface 與 frontend read model，不動 core schema。

## Done Criteria

1. `GET /api/data/projects/{id}/progress` 存在，且回傳 project-level aggregate payload；不要求前端自行從 `getTasksByEntity()` 拼 active plan 與 open work。
2. `/projects/[id]` 第一層改為 plan-centric console；第一屏可直接看到 active plans 與 grouped open work，而不是完整 `TaskBoard`。
3. open work 依 plan 分組，subtask 收在 parent task 底下。
4. 頁面可直接辨識 blocked / review / overdue。
5. 產品頁接 shared `CopilotRailShell`，可產生 AI recap。
6. 頁面可在不進 task 詳情下直接 copy continuation prompt。
7. prompt 支援至少 `claude_code` / `codex` 兩種 preset，若 Phase 0 內容相同也需有切換 UI 與 contract。
8. AC stubs `dashboard/src/__tests__/project_progress_console_ac.test.tsx` 由 FAIL 變 PASS。
9. 至少跑：
   - `cd dashboard && npx vitest run src/__tests__/project_progress_console_ac.test.tsx`
   - `cd dashboard && npm run build`
   - backend 相關最小 scope pytest

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 補 project progress aggregate endpoint 與 client contract | Developer | 新增 `/api/data/projects/{id}/progress`、client wrapper、backend/frontend最小必要型別與測試 |
| S02 | 重構 `/projects/[id]` 為 plan-centric console | Developer | 第一層為 Current Plans + Open Work + Milestone + Recent Progress；`TaskBoard` 退為 drill-down |
| S03 | 接 AI recap rail 與 copy prompt preset | Developer | 使用 shared AI rail；copy prompt 可產出 continuation prompt |
| S04 | 補 AC tests / regression / build gate | Developer | AC stubs 轉 PASS；最小 scope + build 通過 |
| S05 | Spec compliance + scenario audit | QA | 對照 `AC-PPC-*` 驗收；P0 任一 fail 則退回 |

## Risk Assessment

### 1. 不確定的技術點

- [未確認] 現有 `TaskRepo.list_all(linked_entity=...)` 是否足夠支撐 project-level aggregate 效能；若不夠，後續可能需要專門 query。
- [未確認] 產品頁 current entity 與 plan/project string scope 是否總是一致；本輪設計採「以 linked tasks 反查 plan_id」避免依賴 plan.project 字串。

### 2. 替代方案與選擇理由

- 方案 A：前端延續 `getTasksByEntity + getChildEntities` 自行拼出 plans / open work / milestones
  - 不選原因：會把口徑分散在 page local logic，重蹈目前空值與混亂問題。
- 方案 B：新增單一 aggregate endpoint
  - 選擇理由：可把 plan / open work / recent progress 口徑收斂成正式 read model，符合 spec 的「任何進度數字都必須可追溯」。
- 方案 C：另做一套專用 AI widget
  - 不選原因：`SPEC-dashboard-ai-rail` 已有 shared shell，另起一套會造成 AI UX 再次分叉。

### 3. 需要用戶確認的決策

- [未確認] list 頁 `/projects` 的 KPI 是否要在本輪同步升級為 plan-aware；若沒有額外要求，本輪先交付 detail 頁。
- [未確認] Phase 0 的 AI recap 是否接受「不落 server 快取、僅前端保留本次摘要」。

### 4. 最壞情況與修正成本

- 若 aggregate endpoint 的資料口徑不穩，前端即使重做 IA 仍會顯示錯誤數字；修正成本在 backend query / grouping，而不是 UI。
- 若 shared AI rail 掛接失敗，仍可先保留 project console 主體交付，AI recap / copy prompt 切成次批修復；但不得宣稱 P0 全交付。

