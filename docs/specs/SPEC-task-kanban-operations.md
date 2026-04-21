---
type: SPEC
id: SPEC-task-kanban-operations
status: Under Review
l2_entity: action-layer
created: 2026-03-31
updated: 2026-04-19
---

# Feature Spec: Task Kanban 操作能力

## 背景與動機

目前 `/tasks` 畫面幾乎是唯讀面板——使用者可以看任務、篩選、查看詳情，但無法在 UI 上執行任何操作。要改狀態、編輯欄位、建任務、做 review，都必須回到 MCP 或 API。這讓 Dashboard 無法作為日常工作面板使用，降低了任務治理的效率與體驗。

## 目標用戶

- 每日使用 Dashboard 管理任務的 PM / owner
- 需要在 UI 上直接推進任務狀態的執行者
- 負責 review 任務交付的 reviewer

## 需求

### P0（必須有）

#### R1：狀態轉換 — 拖曳

- **描述**：使用者可以在 Kanban 視圖中，透過拖曳卡片到不同欄位來變更任務狀態。
- **Acceptance Criteria**：
  - Given 一張狀態為 `todo` 的任務卡片，When 使用者將其拖曳到 `in_progress` 欄位，Then 任務狀態更新為 `in_progress`，卡片停留在新欄位。
  - Given 拖曳過程中，When 卡片懸停在目標欄位上方，Then 目標欄位必須有視覺提示（高亮/虛線框）表示可放置。
  - Given 狀態更新 API 失敗，When 拖曳完成，Then 卡片回到原始欄位，並顯示錯誤提示。

#### R2：狀態轉換 — Detail Drawer 按鈕

- **描述**：使用者在任務詳情 Drawer 中，可以透過按鈕或下拉選單變更任務狀態。
- **Acceptance Criteria**：
  - Given 開啟任一任務的 Detail Drawer，When 使用者查看狀態區域，Then 必須有狀態切換控制項（下拉選單或按鈕組）。
  - Given 使用者選擇新狀態，When 確認變更，Then 任務狀態即時更新，Drawer 與 Kanban 同步反映。

#### R3：Cancel Task

- **描述**：任務的 owner 或 creator 可以取消任務。非 owner/creator 不可見取消操作。
- **Acceptance Criteria**：
  - Given 使用者是該任務的 owner 或 creator，When 在 Detail Drawer 查看任務，Then 必須可見「取消任務」操作入口。
  - Given 使用者不是 owner 也不是 creator，When 在 Detail Drawer 查看任務，Then 不可見「取消任務」操作。
  - Given 使用者點擊取消，When 確認操作（需二次確認），Then 任務狀態變為 `cancelled`。

#### R4：建立任務

- **描述**：使用者可以從 Kanban UI 新增任務，透過完整表單填寫欄位。表單分為「基本欄位」與「進階欄位」兩層；僅標題必填，但 richer task 欄位不得只能靠 MCP 才能輸入。
- **Acceptance Criteria**：
  - Given 使用者在 `/tasks` 頁面，When 點擊「新增任務」按鈕，Then 開啟任務建立表單。
  - Given 表單開啟，When 使用者查看欄位，Then 必須包含：標題（必填）、描述、優先級、指派人、到期日、專案。
  - Given 使用者只填寫標題，When 提交表單，Then 任務成功建立，其餘欄位為空/預設值。
  - Given 任務建立成功，When 表單關閉，Then 新任務立即出現在 Kanban 對應欄位中（預設 `todo`）。
  - Given 使用者展開進階欄位，When 查看表單，Then 至少可輸入或選擇：`linked_entities`, `assignee_role_id`, `dispatcher`, `plan_id`, `plan_order`, `parent_task_id`, `depends_on_task_ids`, `blocked_by`, `blocked_reason`, `linked_protocol`, `linked_blindspot`, `acceptance_criteria`, `source_metadata`。
  - Given dashboard 尚無專屬 read model 的欄位（如 `plan_id`, `linked_protocol`），When 使用者操作表單，Then 仍可透過穩定 ID 或 structured text 輸入，不得靜默省略該欄位。

#### R5：編輯任務欄位

- **描述**：使用者可以在 Detail Drawer 中編輯任務的標題、描述、優先級、指派人、到期日，以及 richer task orchestration/context 欄位。
- **Acceptance Criteria**：
  - Given 開啟任務 Detail Drawer，When 使用者點擊任一可編輯欄位，Then 該欄位進入編輯模式（inline edit）。
  - Given 使用者修改欄位值，When 儲存變更，Then 變更即時反映在 Drawer 與 Kanban 卡片上。
  - Given 使用者修改描述欄位，When 進入編輯模式，Then 提供 Markdown 編輯器（至少支援純文字輸入，儲存後渲染為 Markdown）。
  - Given 開啟任務 Detail Drawer，When 查看進階欄位區，Then 至少可讀寫：`assignee_role_id`, `dispatcher`, `plan_id`, `plan_order`, `parent_task_id`, `depends_on_task_ids`, `blocked_by`, `blocked_reason`, `linked_protocol`, `linked_blindspot`, `acceptance_criteria`, `source_metadata`。
  - Given 任務已有 `attachments`, `handoff_events`, `result`
    When 開啟 Detail Drawer
    Then 這三類資訊必須可直接查看；其中 `attachments` 必須可管理、`handoff_events` 必須可追蹤，但 `handoff_events` 不可被直接編輯覆寫。

### P1（應該有）

#### R6：Review 流程 — Approve / Reject

- **描述**：當任務狀態為 `review` 時，reviewer 可以在 Detail Drawer 中執行 approve 或 reject 操作。
- **Acceptance Criteria**：
  - Given 任務狀態為 `review`，When 在 Detail Drawer 查看，Then 必須可見「Approve」與「Reject」按鈕。
  - Given 使用者點擊 Approve，When 確認，Then 任務狀態變為 `done`。
  - Given 使用者點擊 Reject，When 操作，Then 顯示 rejection reason 輸入框（選填），提交後任務狀態回到 `in_progress`。
  - Given 任務狀態不是 `review`，When 在 Detail Drawer 查看，Then 不顯示 Approve / Reject 按鈕。

#### R7：Handoff 補齊 output_ref

- **描述**：當使用者在 UI 中 handoff 任務時，除了 `to_dispatcher`、`reason`、`notes` 外，也必須能補 `output_ref`，讓履歷與 spec/commit/file path 對得上。
- **Acceptance Criteria**：
  - Given 使用者在 Detail Drawer 執行 handoff
    When 查看 handoff 表單
    Then 表單必須可輸入 `output_ref`。
  - Given 使用者送出 handoff
    When Hand off 成功
    Then 新增的 `handoff_event` 必須包含 `output_ref`（若有填）。

#### R8：狀態轉換規則提示

- **描述**：當使用者嘗試不合理的狀態轉換時（如 `todo` 直接跳到 `done`），UI 應給予提示或阻擋。
- **Acceptance Criteria**：
  - Given 使用者嘗試將 `todo` 拖曳到 `done`，When 放置卡片，Then 顯示提示「建議先經過 in_progress 和 review」，使用者可選擇強制執行或取消。
  - Given 拖曳到 `review` 狀態，When 任務沒有填寫 result，Then 顯示警告「建議填寫任務成果後再送審」，使用者可選擇繼續或取消。

### P2（可以有）

#### R9：批次操作

- **描述**：使用者可以多選任務卡片，批次變更狀態或指派人。
- **Acceptance Criteria**：
  - Given 使用者在 Kanban 視圖，When 使用 Ctrl/Cmd + Click 選取多張卡片，Then 顯示批次操作工具列。
  - Given 選取多張卡片並選擇批次狀態變更，When 確認，Then 所有選中任務的狀態同時更新。

## 明確不包含

- Plan 管理（建立 plan、加入/移出 plan、排序）
- 任務刪除（只有 cancel，不做硬刪除）
- 任務模板功能
- 任務評論/留言功能
- 通知系統整合
- Protocol / blindspot / role / plan 本身的 CRUD

## 技術約束（給 Architect 參考）

- 狀態轉換必須透過既有 MCP task API 執行，不另建 REST endpoint。
- Cancel 權限判斷需比對當前登入用戶與 task 的 `owner` / `created_by` 欄位。
- 拖曳功能需考慮行動裝置的觸控體驗。
- 編輯操作應採用 optimistic update 以提升體驗，失敗時 rollback 並提示。
- 需與 `SPEC-task-view-clarity` 的篩選機制共存，操作後不能破壞篩選狀態。
- Dashboard contract 必須把 richer task 欄位透傳到既有 TaskService；這次不新增 core schema。
- 對尚無 dashboard read model 的 richer 欄位，可先採穩定 ID / structured text 輸入，但不可完全缺席於 UI。

## 與既有規格關係

- `SPEC-task-view-clarity`（Approved）：本 spec 在其「唯讀」基礎上增加操作能力，不改動其定義的顯示規則。
- `SPEC-task-governance`：沿用 task 狀態語義與生命周期，不重定義。

## 開放問題

1. 拖曳在行動裝置上的體驗是否需要備用方案（如長按選單）？列為 Architect 決策。
2. 編輯描述時是否需要即時預覽 Markdown？列為 P2 後續討論。

## Changelog

- 2026-04-19: reviewed against SPEC-task-governance dispatcher / handoff / subtask semantics; kanban operations keep existing UI actions and do not redefine dispatcher lifecycle.
- 2026-04-21: expanded create/edit/handoff UI contract to cover richer task fields and handoff output_ref.
