# Feature Spec: 派工系統 UI 改版

## 狀態
Draft

## 日期
2026-03-26

## 背景與問題確認

目前派工系統已經有任務資料模型、狀態機與基本 dashboard，但 PM dogfooding 後確認一個核心問題：

**UI 讓人看到「有任務」，但看不到「實際狀態」。**

這不是單純視覺設計問題，而是資訊架構錯位。當前版本有四個結構性缺陷：

1. `Pulse` 與 `Kanban` 共用同一份 `tasks` state，切到 `My Inbox` / `Review` 後再回 `Pulse`，看到的是局部資料，不是全局
2. `Kanban` 主畫面只顯示 `backlog / todo / in_progress / review / blocked`，`done / cancelled / archived` 會在畫面上消失
3. `People x Projects` 把一格內所有任務壓成一個最高狀態，PM 無法理解真實工作分布
4. `Project Progress` 只看完成率，無法區分「健康推進中」與「大量卡在 review / blocked」

結果是 PM 難以回答最基本的管理問題：

- 現在整體工作量在哪裡？
- 哪些任務在前進，哪些其實卡住？
- 哪些案子看起來有進度，但其實只是堆在 review？
- 誰手上 overloaded？誰手上的 blocker 最多？
- 哪些任務逾期、哪些等待驗收太久？

## 目標

- 讓 PM 在 10 秒內判斷全局真實狀態
- 讓執行者在 Kanban 快速找到自己要處理的任務
- 讓所有任務狀態在 UI 上都有可見出口，不被隱藏
- 區分「全域營運視角」與「個人執行視角」
- 支援從 summary drill-down 到具體 task

## 非目標

- 不在本次加入拖拉改 status
- 不做通知系統
- 不做完整 audit log viewer
- 不重做 task data model
- 不做跨公司跨 workspace 聚合

## 使用者故事

- 身為 PM，我想先看到全局阻塞、待驗收、逾期，而不是先看卡片清單
- 身為 PM，我想知道某個產品進度差，是因為 backlog 太多、review 堆積，還是 blocked
- 身為執行者，我想切到 `My Inbox` 只看自己待做，但不影響 PM 的全域 view
- 身為老闆，我想知道哪些任務已完成、被取消、被封存，而不是它們直接從畫面消失

## 設計原則

1. **全域資料與局部視圖分離**
2. **真實狀態不得消失**
3. **Review 是獨立狀態，不等於進行中**
4. **Blocked 要有原因與 blocker 入口**
5. **Summary 必須可 drill-down**
6. **收合態先服務決策，展開態再服務閱讀**

---

## 資訊架構

### 頁面層級

`/tasks` 保留雙模式：

- `Pulse`：PM / 老闆的全局決策畫面
- `Kanban`：執行者的任務操作畫面

### 狀態定義

畫面必須支援所有既有 task status：

- `backlog`
- `todo`
- `in_progress`
- `review`
- `blocked`
- `done`
- `cancelled`
- `archived`

其中：

- `done`：預設顯示於 Kanban 主欄
- `cancelled` / `archived`：可收進次欄、摺疊區或 filter 預設關閉，但不可消失

---

## Pulse 改版規格

### 1. 全域指標列

顯示六張卡：

- `Active`：`backlog + todo + in_progress + review + blocked`
- `Moving`：僅 `in_progress`
- `Blocked`：`blocked`
- `Overdue`：所有未完成且 `due_date < now`
- `Review Queue`：`review && !confirmedByCreator`
- `Done 7d`：近 7 天完成數

每張卡都要可點擊，點擊後在同頁打開對應 task list drawer / panel。

### 2. 風險清單

新增單獨區塊，顯示最多 10 筆高優先任務：

- 先列 `blocked`
- 再列 `overdue`
- 再列 `review` 且等待超過 SLA（Phase 0 先用 48 小時）

每列顯示：

- 標題
- 狀態 badge
- assignee
- product / module
- 逾期或等待天數
- blocked reason 或 waiting review 標記

### 3. 專案健康表

取代現在只顯示 `% done` 的 progress bar。

每個 product 一列，顯示：

- `done`
- `in_progress`
- `review`
- `blocked`
- `todo + backlog`
- `overdue`

視覺表現：

- 橫向堆疊條 + 數字
- hover / click 可展開該 product 的 task list

排序方式：

1. `blocked + overdue` 多者優先
2. `review` 多者次之
3. 其餘依 active task 數量排序

### 4. 人員負載表

取代現在的 `People x Projects` 壓縮矩陣。

每位 assignee 一列，顯示：

- active tasks
- in progress
- review
- blocked
- overdue
- done 7d

另提供可展開的次層：

- 展開後才看各 product 分布

原因：

- PM 先要知道「誰 overloaded」
- 再看「他 overload 在哪個 product」

### 5. 活動時間線

調整為「事件流」而不是「狀態推論」。

Phase 0 如果後端沒有 event log，前端只允許顯示這些事件：

- created
- moved to in_progress
- submitted review
- blocked
- completed
- rejected

若無法判斷事件類型，就顯示 `updated task`，但不得用當前狀態假裝成事件。

---

## Kanban 改版規格

### 1. 資料範圍

需要區分兩份資料：

- `globalTasks`：Pulse 永遠使用的全量任務
- `scopedTasks`：Kanban tab/filter 後的局部任務

任一 Kanban tab/filter 切換都不得覆蓋 `globalTasks`。

### 2. Tab 定義

- `All Tasks`
- `My Inbox`
- `My Outbox`
- `Review Queue`

語意：

- `All Tasks`：全量任務
- `My Inbox`：`assignee = current user`
- `My Outbox`：`created_by = current user`
- `Review Queue`：待我確認或待 review 的任務

### 3. 欄位定義

主欄：

- `Backlog`
- `Todo`
- `In Progress`
- `Review`
- `Blocked`
- `Done`

次欄：

- `Cancelled`
- `Archived`

次欄可用「Show closed tasks」切換，不預設展開。

### 4. 卡片收合態

收合態必須顯示：

- title
- priority
- status cue
- assignee
- linked product / module 名稱
- overdue badge
- blocked badge / blocker count
- last updated

禁止只顯示：

- title
- priority
- assignee

因為那不足以支撐派工判斷。

### 5. 卡片展開態

展開後顯示：

- description
- context summary
- acceptance criteria
- blocked by
- blocked reason
- result
- rejection reason

### 6. Filter

新增或補齊：

- status
- priority
- assignee
- linked product
- overdue only
- blocked only
- no linked entity

---

## 互動與 drill-down

以下 summary 元件都必須能 drill-down 到 task list：

- Pulse 指標卡
- 專案健康表列
- 人員負載表列
- 風險清單項目

drill-down 打開的 task list 需保留來源上下文，例如：

- `Blocked tasks`
- `Review queue for Paceriz`
- `Tasks owned by architect`

---

## 資料需求

前端已可取得的欄位：

- `status`
- `priority`
- `assignee`
- `createdBy`
- `linkedEntities`
- `dueDate`
- `blockedBy`
- `blockedReason`
- `confirmedByCreator`
- `updatedAt`
- `completedAt`

本次 Phase 0 不強制新增 API 欄位，但前端需要重新組裝與使用。

建議後續 API 擴充：

- `linkedEntityNames`
- `waitingReviewHours`
- `isOverdue`
- `doneInLast7d`

---

## 驗收條件

### P0

1. 切到 `Kanban > My Inbox` 再切回 `Pulse`，Pulse 指標仍顯示全量任務統計
2. Kanban 主畫面可看見 `Done` 欄
3. `Cancelled` / `Archived` 不會從 UI 消失，至少能透過 `Show closed tasks` 顯示
4. Pulse 有獨立 `Blocked`、`Overdue`、`Review Queue` 可點擊入口
5. 專案健康表不再只顯示單一完成率，而是至少顯示 `done / in_progress / review / blocked / pending`
6. 人員負載表能同時看見一個人手上的多種狀態分布，不再只顯示最高狀態

### P1

1. 風險清單按嚴重度正確排序
2. 所有 summary 區塊都可 drill-down
3. 活動時間線不再用當前狀態假裝事件
4. Kanban 卡片收合態即可完成派工判讀，不必逐張展開

## 實作建議

### Phase 0

- 先修正 task state 分離：`globalTasks` vs `scopedTasks`
- 補齊 Kanban 欄位：至少顯示 `done`
- 重做 Pulse 的 `ProjectProgress` 與 `PeopleMatrix`

### Phase 1

- 新增風險清單與 drill-down side panel
- 重做 Activity Timeline 的事件定義
- 補齊 filter 與收合卡片資訊架構

## 相關文件

- `docs/archive/specs/deferred-2026-03/SPEC-dashboard-v1.md`
- `docs/archive/specs/SPEC-enriched-task-dispatch.md`
- `docs/designs/TD-dashboard-v1-implementation.md`
