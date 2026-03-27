---
type: SPEC
id: SPEC-task-view-clarity
status: Approved
l2_entity: action-layer
created: 2026-03-27
updated: 2026-03-27
---

# Feature Spec: Task 畫面可讀性與跨專案狀態清晰化

## 背景與動機

目前 `/tasks` 畫面雖有 Pulse 與 Kanban 兩種視圖，但使用者無法快速回答兩個核心問題：

1. 現在有哪些 task 還沒完成、卡在哪個狀態。
2. 不同專案（`task.project`）各自的任務狀態分布與風險。

這會造成 Action Layer 難以作為「可營運的工作面板」，使用者只能回到 MCP 查詢或手動比對，降低任務治理效率。

## 目標

1. 讓使用者在 30 秒內看懂「未完成任務全貌」。
2. 讓使用者可直接比較不同專案的任務狀態，不需離開 `/tasks`。
3. 讓每一個數字都可追溯到同一批資料，避免各區塊定義不一致。
4. 保持 Task 治理語義一致：`done/archived/cancelled` 與「待處理」必須明確分離。

## 非目標

- 不在本 spec 定義新的 task schema 或狀態機。
- 不在本 spec 定義 backend API 重構細節。
- 不在本 spec 定義 drag-and-drop 或任務編輯流程。
- 不把 Pulse/Kanban 擴大成全新 IA（資訊架構）重做。

## 目標使用者

- 每日查看任務盤點的 PM / owner
- 需要跨專案協作的執行者與 reviewer
- 需要快速判斷風險（blocked/overdue/review 堵塞）的管理者

## 現況問題定義（As-Is）

1. `Pulse` 與 `Kanban` 切換缺少明確預設意圖，首次進入不易理解下一步操作。
2. `Kanban` 欄位目前只呈現 `todo/in_progress/review/blocked/backlog`，看板視角看不到 `done/cancelled/archived` 的規模。
3. 畫面缺少 `project` 維度的一級摘要，使用者看不到「同狀態在不同專案的差異」。
4. 各區塊（Pulse 指標、ProjectProgress、PeopleMatrix、ActivityTimeline）對「活躍 task」與「完成 task」的口徑雖接近，但未被明文化為同一規則。

## 名詞與判斷定義

- `待處理`：`backlog,todo,in_progress,review,blocked`
- `完成/結束`：`done,cancelled,archived`
- `overdue`：task 的 `dueDate` 存在，且時間早於當前時間，且 task 狀態不屬於 `done,cancelled,archived`。
- `專案未指定`：`task.project=""`，必須顯示為固定 bucket `unscoped`。

## 需求（含優先級與對應驗收）

### P0-1（R1）任務狀態口徑統一

- 畫面中所有 task 統計必須使用同一套狀態集合定義，不得混用隱含口徑。
- 若某區塊採不同分母，必須在畫面上標示分母定義。

AC-R1:
1. Given 同一批 task 資料  
   When 同時檢查摘要總數與看板欄位  
   Then `待處理總數` 必須等於 `backlog+todo+in_progress+review+blocked` 欄位總和。
2. Given 任一統計卡片與任務列表  
   When 套用同一篩選條件  
   Then 卡片數字與列表數字必須一致。

### P0-2（R2）跨專案狀態摘要

- `/tasks` 畫面必須提供「專案 x 狀態」摘要區，至少顯示每個 `task.project` 在 `backlog,todo,in_progress,review,blocked,done` 的數量。
- 摘要區必須以可見欄位直接呈現風險：每個專案顯示 `blocked` 與 `overdue` 計數；不得只靠顏色暗示。
- `task.project=""` 必須歸入 `unscoped` 並顯示計數。

AC-R2:
1. Given 至少兩個不同 `task.project`  
   When 進入 `/tasks`  
   Then 摘要區必須同時顯示兩個專案的狀態分布。
2. Given 某專案有 blocked 與 overdue 任務  
   When 查看摘要區  
   Then 該專案列必須同時顯示 blocked 與 overdue 的具體數字。
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
- 待處理視圖只顯示 `backlog,todo,in_progress,review,blocked`。
- 全狀態視圖額外顯示 `done,cancelled,archived`。
- 任一狀態被隱藏時，必須有可見提示，不得讓使用者誤判資料不存在。

AC-R4:
1. Given Kanban 在待處理視圖  
   When 檢查欄位  
   Then 不得顯示 `done,cancelled,archived` 欄位，且須看到「已隱藏已完成狀態」等同級提示。
2. Given 切換為全狀態視圖  
   When 檢查欄位  
   Then 必須顯示 `done,cancelled,archived`。

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

## 技術約束（給 Architect）

- 本 spec 不新增 task 狀態值，僅使用既有狀態集合。
- 本 spec 不改動 task schema，只能使用既有欄位（含 `project`, `status`, `priority`, `dueDate`）。
- 畫面篩選條件必須可在 Pulse/Kanban 間共享，同一套條件不得各自維護獨立語義。
- 若既有 API 無法一次回傳專案摘要所需資料，必須在 implementation task 中明確拆分增量交付，不得以「前端自行推測」替代正式口徑。

## 邊界與治理規則

- 本 spec 只定義 task 畫面「看得懂與可追蹤」的產品規則，不定義實作技術。
- 若需求同時包含「資訊架構大改」與「即時可交付可驗收改善」，必須拆成兩張 task：
  - 一張處理畫面可讀性與狀態口徑一致。
  - 一張處理結構重設或新導航。

## 與既有規格關係

- `SPEC-task-governance`：沿用 task 狀態語義與驗收治理，不重定義生命周期。
- `SPEC-partner-context-fix`：沿用 partner/project scope 前提，不重定義租戶隔離策略。

## Open Questions

1. `review` 是否需要進一步拆分「待審核」與「被退回」顯示（目前以 `rejectionReason` 偵測）？此項列為 P2 後續討論，不阻塞本 spec。
