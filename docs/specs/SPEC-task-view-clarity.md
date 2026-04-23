---
type: SPEC
id: SPEC-task-view-clarity
status: Under Review
ontology_entity: l3-action
created: 2026-03-27
updated: 2026-04-23
depends_on: SPEC-task-governance, SPEC-mcp-tool-contract, SPEC-task-surface-reset
runtime_canonical:
  - dashboard/src/types/index.ts:191 (TaskStatus = "todo" | "in_progress" | "review" | "done" | "cancelled")
  - dashboard/src/lib/task-risk.ts (overdue / upcoming / idle 判定)
  - SPEC-mcp-tool-contract §9 (legacy status normalization backlog|blocked → todo, archived → done)
---

# Feature Spec: Task 畫面可讀性與跨專案狀態清晰化

> **Layering note（2026-04-23 revision）**：本 SPEC 僅定義 `/tasks` 畫面可讀性規則。Canonical task status 以 `SPEC-task-governance §3.1` + runtime `dashboard/src/types/index.ts:191` 為準，**只有 5 個值**：`todo / in_progress / review / done / cancelled`。舊 legacy 值 `backlog / blocked / archived` 已於 MCP 層由 server normalize（`SPEC-mcp-tool-contract §9.2`），UI 不再處理。

## 背景與動機

目前 `/tasks` 畫面雖有 Pulse 與 Kanban 兩種視圖，但使用者無法快速回答兩個核心問題：

1. 現在有哪些 task 還沒完成、卡在哪個狀態。
2. 不同專案（`task.project`）各自的任務狀態分布與風險。

這會造成 Action Layer 難以作為「可營運的工作面板」，使用者只能回到 MCP 查詢或手動比對，降低任務治理效率。

## 目標

1. 讓使用者在 30 秒內看懂「未完成任務全貌」。
2. 讓使用者可直接比較不同專案的任務狀態，不需離開 `/tasks`。
3. 讓每一個數字都可追溯到同一批資料，避免各區塊定義不一致。
4. 保持 Task 治理語義一致：`done / cancelled`（closed）與「待處理」（open）必須明確分離。

## 非目標

- 不在本 spec 定義新的 task schema 或狀態機。
- 不在本 spec 定義 backend API 重構細節。
- 不在本 spec 定義 drag-and-drop 或任務編輯流程。
- 不把 Pulse/Kanban 擴大成全新 IA（資訊架構）重做。

## 目標使用者

- 每日查看任務盤點的 PM / owner
- 需要跨專案協作的執行者與 reviewer
- 需要快速判斷風險（overdue / idle_todo / review 堵塞）的管理者

## 現況問題定義（As-Is）

1. `Pulse` 與 `Kanban` 切換缺少明確預設意圖，首次進入不易理解下一步操作。
2. `Kanban` 欄位歷史上只呈現「進行中」狀態集，看板視角看不到終態（`done / cancelled`）的規模。
3. 畫面缺少 `project` 維度的一級摘要，使用者看不到「同狀態在不同專案的差異」。
4. 各區塊（Pulse 指標、ProjectProgress、PeopleMatrix、ActivityTimeline）對「活躍 task」與「完成 task」的口徑雖接近，但未被明文化為同一規則。

## 名詞與判斷定義

Canonical `TaskStatus` 5 值（`SPEC-task-governance §3.1` / runtime `dashboard/src/types/index.ts:191`）：`todo / in_progress / review / done / cancelled`。

- `待處理（open）`：`todo, in_progress, review`
- `完成/結束（closed）`：`done, cancelled`
  - 對應 runtime `dashboard/src/lib/task-risk.ts:5` 的 `CLOSED_STATUSES`（程式碼端因歷史兼容仍接受 `archived`，server 端已於 `SPEC-mcp-tool-contract §9.2` 將 `archived → done` normalize；UI 判定時 `archived` 與 `done` 同視）
- `overdue`：task 的 `dueDate` 存在，且時間早於當前時間，且狀態不屬於 `closed`（`task-risk.ts:13-18`）
- `upcoming`：task 的 `dueDate` 在未來 3 天內，狀態不屬於 `closed`（`task-risk.ts:20-26`）
- `idle_todo`：`status=todo` + 有 assignee + `updatedAt` 超過 48h（`task-risk.ts:28-33`）
- `專案未指定`：`task.project=""`，必須顯示為固定 bucket `unscoped`

## 需求（含優先級與對應驗收）

### P0-1（R1）任務狀態口徑統一

- 畫面中所有 task 統計必須使用同一套狀態集合定義，不得混用隱含口徑。
- 若某區塊採不同分母，必須在畫面上標示分母定義。

AC-R1:
1. Given 同一批 task 資料
   When 同時檢查摘要總數與看板欄位
   Then `待處理總數` 必須等於 `todo + in_progress + review` 欄位總和（canonical 5-status，不含 closed）。
2. Given 任一統計卡片與任務列表
   When 套用同一篩選條件
   Then 卡片數字與列表數字必須一致。

### P0-2（R2）跨專案狀態摘要

- `/tasks` 畫面必須提供「專案 x 狀態」摘要區，至少顯示每個 `task.project` 在 canonical 5 狀態（`todo / in_progress / review / done / cancelled`）的數量。
- 摘要區必須以可見欄位直接呈現風險：每個專案顯示 `overdue`（§名詞定義）與 `idle_todo` 計數；不得只靠顏色暗示。
- `task.project=""` 必須歸入 `unscoped` 並顯示計數。

AC-R2:
1. Given 至少兩個不同 `task.project`
   When 進入 `/tasks`
   Then 摘要區必須同時顯示兩個專案的 canonical 5 狀態分布。
2. Given 某專案有 `overdue` 與 `idle_todo` 任務
   When 查看摘要區
   Then 該專案列必須同時顯示兩者的具體數字。
3. Given 有 `task.project=""` 的任務
   When 查看摘要區
   Then 必須出現 `unscoped` 列，且數量可對回任務列表。

### P0-3（R3）主視圖預設與導覽

- `/tasks` 首次進入必須預設顯示「全域摘要 + 跨專案摘要」區塊在第一屏，不得先進入單張 task 詳情導向畫面。
- Pulse 與 Kanban 切換必須保留既有篩選條件（tab/status/priority/完成狀態顯示模式），不得遺失上下文。

AC-R3:
1. Given 使用者首次進入 `/tasks`  
   When 畫面載入完成  
   Then 第一屏可見區域必須含全域摘要與跨專案摘要。
2. Given 使用者已設定 tab/status/priority  
   When 在 Pulse 與 Kanban 之間切換  
   Then 篩選條件必須保持不變。

### P1-1（R4）Kanban 可觀測性補齊

- Kanban 必須支援「待處理視圖」與「全狀態視圖」切換。
- 待處理視圖只顯示 `todo, in_progress, review`（§名詞的 `open`）。
- 全狀態視圖額外顯示 `done, cancelled`（`closed`）。
- 任一狀態被隱藏時，必須有可見提示，不得讓使用者誤判資料不存在。

AC-R4:
1. Given Kanban 在待處理視圖
   When 檢查欄位
   Then 不得顯示 `done / cancelled` 欄位，且須看到「已隱藏已完成狀態」等同級提示。
2. Given 切換為全狀態視圖
   When 檢查欄位
   Then 必須顯示全部 5 個 canonical 欄位（`todo / in_progress / review / done / cancelled`）。

### P1-2（R5）篩選與計數一致性

- 任一篩選生效後，摘要卡、專案摘要、看板欄位、任務列表必須同步更新。
- 畫面必須顯示「目前篩選快照」：tab、status、priority、完成狀態顯示模式。

AC-R5:
1. Given 使用者連續調整 tab/status/priority  
   When 查看摘要卡、專案摘要、看板與列表  
   Then 四者數字必須同時更新且互相一致。
2. Given 任一篩選已套用  
   When 查看篩選快照  
   Then 必須可見 tab/status/priority/顯示模式四項當前值。

### P2-1（R6）空狀態與錯誤狀態文案

- 畫面應區分三種情境文案：無任務、被篩選排除、載入失敗。
- 載入失敗時應提供重試入口。

AC-R6:
1. Given API 成功但結果為空  
   When 載入 `/tasks`  
   Then 顯示「無任務」文案。
2. Given API 成功但被篩選成空  
   When 套用篩選  
   Then 顯示「目前篩選無結果」文案。
3. Given API 失敗  
   When 載入 `/tasks`  
   Then 顯示錯誤文案與重試入口；重試成功後回復正常顯示。

### P0-4（R7）Kanban 卡片資訊乘載力擴充 (Rich Kanban Card)

- 任務的 `description` 與 `result` 欄位必須完整支援 **Markdown 渲染**，包含表格、清單與超連結，做為跨部門（如業務與行銷）溝通的資訊載體。
- 若 `description` 中包含圖片連結（例如 `![Image](URL)`），Kanban 卡片（Card）與抽屜式詳情（Drawer）必須直接渲染圖片縮圖，不須點開即可預覽（如設計物、截圖）。
- 卡面必須借鑒 Jira/Kanban 的資訊密度，直覺呈現：`linked_entities`（以 Tag 顯示）、`priority`（Icon）、`assignee`（Avatar）。

AC-R7:
1. Given task description 包含 Markdown 表格與圖片  
   When 在 UI 開啟 task 詳情  
   Then 必須正確渲染出表格結構與實體圖片。
2. Given task 包含圖片連結  
   When 查看 Kanban 視圖  
   Then 該卡片上方或內部必須顯示該圖片的縮圖 (Cover/Thumbnail)。
3. Given task 具備 linked_entities 與 assignee  
   When 查看 Kanban 視圖  
   Then 必須在卡面上直接看到對應的 L2 Tag 與人員頭像。

### P1-3（R8）自動化建票行為與 UI 連動 (Conversational Intake / Rich Creation)

- 為減少反覆輸入，Agent 在接收需求建票時，必須將非結構化的對話/文字，自動結構化為 Markdown 格式寫入 `description`。
- Agent 建票時，若發現缺少關鍵資訊（基於掛載的 L2 Protocol），應在前端介面/對話中引導補完，並於建票後直接顯示 Kanban 卡片預覽。

AC-R8:
1. Given 業務提供未格式化的需求文字  
   When Agent 執行 `mcp_zenos_task`  
   Then 寫入的 description 必須是排版整齊的 Markdown（含重點清單與粗體）。

## 技術約束（給 Architect）

- 本 spec 不新增 task 狀態值，僅使用既有狀態集合。
- 本 spec 不改動 task schema，只能使用既有 Task Core 欄位；除 `project`, `status`, `priority`, `dueDate` 外，也必須能承接已存在的 richer 欄位，如 `assignee_role_id`, `plan_id`, `plan_order`, `depends_on_task_ids`, `blocked_by`, `blocked_reason`, `linked_protocol`, `linked_blindspot`, `dispatcher`, `parent_task_id`。
- 畫面篩選條件必須可在 Pulse/Kanban 間共享，同一套條件不得各自維護獨立語義。
- 若既有 API 無法一次回傳專案摘要所需資料，必須在 implementation task 中明確拆分增量交付，不得以「前端自行推測」替代正式口徑。
- 對於目前尚無專屬 read model 的 richer 欄位（例如 `plan_id`, `linked_protocol`），UI 可暫以穩定 ID 呈現或編輯，但不得靜默忽略。

## 邊界與治理規則

- 本 spec 只定義 task 畫面「看得懂與可追蹤」的產品規則，不定義實作技術。
- 若需求同時包含「資訊架構大改」與「即時可交付可驗收改善」，必須拆成兩張 task：
  - 一張處理畫面可讀性與狀態口徑一致。
  - 一張處理結構重設或新導航。

## 與既有規格關係

- `SPEC-task-governance`：沿用 task 狀態語義與驗收治理，不重定義生命周期。
- `SPEC-partner-context-fix`：沿用 partner/project scope 前提，不重定義租戶隔離策略。

### P0-5（R9）晨報（Morning Report）

每位使用者進入 `/tasks` 時，第一屏頂部顯示個人化晨報區塊，只呈現與當前使用者相關的風險任務。

顯示三個 bucket（對齊 `task-risk.ts` 判定）：
- **即將到期**：assigned to me，due_date 在未來 3 天內，狀態 ∈ `open`（即非 `closed`）
- **已逾期**：assigned to me，due_date < now，狀態 ∈ `open`
- **建的任務—無人動**：created by me，assignee 已指定，status 仍為 `todo`，updated_at 超過 48h（對齊 `task-risk.ts:28-33` 的 `getIdleTodoHours`）

AC-R9:
1. Given 使用者登入，When 進入 `/tasks`，Then 晨報區塊顯示在第一屏，內容僅包含當前使用者相關任務。
2. Given 晨報區塊，When 點擊任一任務，Then 開啟 TaskDetailDrawer。
3. Given 使用者無任何到期、逾期、或停滯任務，When 進入 `/tasks`，Then 晨報顯示「今日無待處理風險」空態。
4. Given 晨報中「建的任務—無人動」bucket，When 計算，Then 僅以 `updated_at > 48h 前` 且 `status = todo` 且 `assignee != null` 為條件，不包含無 assignee 的任務。

### P0-6（R10）TaskCard 風險標記

TaskCard 上直接顯示到期與停滯的視覺警示 badge，不需點開詳情即可判斷風險。

- **逾期**：due_date < now，狀態 ∈ `open` → 紅色「逾期 N 天」（runtime `task-risk.ts:41-53`）
- **即將到期**：due_date 在未來 3 天內，狀態 ∈ `open` → 橘色「N 天後到期」（runtime `task-risk.ts:54-60`）
- **未開始**：status = `todo`，assignee 存在，updated_at > 48h → 灰色「未開始 Nh」（runtime `task-risk.ts:62-68`）

AC-R10:
1. Given task 的 due_date 在 2 天後，status = `in_progress`，When 在 Kanban 檢視，Then 卡片顯示橘色「2 天後到期」badge。
2. Given task 的 due_date 在昨天，status = `todo`，When 在 Kanban 檢視，Then 卡片顯示紅色「逾期 1 天」badge。
3. Given task status = `todo`，assignee 存在，updated_at = 72h 前，When 在 Kanban 檢視，Then 卡片顯示灰色「未開始 72h」badge。
4. Given task 狀態 ∈ `closed`（`done / cancelled`，server 已將 legacy `archived` normalize 為 `done`），When 在 Kanban 檢視，Then 不顯示任何風險 badge，無論 due_date 為何。

### P0-7（R11）Richer Task Context 可見性

- `/tasks` 的卡片與詳情面板必須能承接新版 task 架構中的核心 orchestration/context 欄位，至少包含：`dispatcher`, `parent_task_id`, `plan_id`, `plan_order`, `assignee_role_id`, `blocked_by`, `blocked_reason`, `linked_protocol`, `linked_blindspot`。
- 有現成名稱 read model 時應顯示名稱；沒有時至少顯示穩定 ID，不得讓欄位消失。
- `blocked_by` / `blocked_reason` 屬於風險資訊，必須在不打開 raw JSON 的情況下被看見。

AC-R11:
1. Given task 帶有 `dispatcher`, `parent_task_id`, `plan_id`, `plan_order`
   When 使用者查看 TaskCard 或 Detail Drawer
   Then 至少一個主要 UI 區塊必須直接顯示這些欄位的語意化資訊，而非只存在 API payload。
2. Given task 帶有 `assignee_role_id`, `linked_protocol`, `linked_blindspot`
   When 使用者開啟 Detail Drawer
   Then 必須看到對應欄位值；若 UI 無名稱 read model，至少顯示穩定 ID。
3. Given task 帶有 `blocked_by` 或 `blocked_reason`
   When 使用者查看 TaskCard 或 Detail Drawer
   Then 必須可直接辨識該 task 為 blocked/有阻塞資訊，且可看到 blocker count 或阻塞原因。

### P1-4（R12）Richer Task Filter / Grouping

- `/tasks` 必須在既有 `status/priority/project/dispatcher` 之外，補足至少一種 richer task filter（例如 `assignee_role_id` 或 `blocked`），避免新版 task 只能看不能篩。
- Kanban 內屬於同一 `plan_id` 的 task 應保留群組顯示；若沒有 plan 名稱 read model，可先用穩定 ID fallback。

AC-R12:
1. Given 多張 task 分屬不同 `assignee_role_id` 或 blocked 狀態
   When 使用者套用 richer filter
   Then 看板、摘要與列表必須同步只顯示符合條件的 task。
2. Given 多張 task 共享同一 `plan_id`
   When 查看 Kanban
   Then 必須維持同 plan 群組顯示，而不是退回無群組平鋪。

## Open Questions

## Changelog

- 2026-04-19: reviewed against SPEC-task-governance dispatcher / handoff / subtask semantics; added reference note only, no conflicting state-machine text in this view spec.
- 2026-04-21: expanded view contract to cover richer task context visibility and richer filters; UI may use stable IDs as fallback for fields without dedicated read model.

1. `review` 是否需要進一步拆分「待審核」與「被退回」顯示（目前以 `rejectionReason` 偵測）？此項列為 P2 後續討論，不阻塞本 spec。
2. 晨報的「無人動 48h」門檻是否應可由用戶設定（例如 24h / 72h）？Phase 0 先固定 48h，後續討論。
