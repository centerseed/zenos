# TD1 — 派工系統 UI 改版

> 指派：Architect + Developer + QA | 預估：2.5 天
> 依賴：現有 `/tasks` 頁面、`SPEC-task-dispatch-ui-redesign.md`
> 相關文件：`docs/archive/specs/deferred-2026-03/SPEC-dashboard-v1.md`

---

## 目標

修正目前任務頁「看得到任務、看不到實際狀態」的問題，讓 PM 能在單一頁面判斷全局狀態，同時保留執行者的 Kanban 操作視角。

---

## 拆解任務

### TD1-1 資料範圍重構

> 指派：Developer | 預估：0.5 天 | 優先級：P0

#### 目標

把 `/tasks` 頁面的資料拆成：

- `globalTasks`：Pulse 使用
- `scopedTasks`：Kanban 使用

#### 交付

- `dashboard/src/app/tasks/page.tsx`
- 如需要，抽出共用 selector / aggregation helper

#### Acceptance Criteria

- 切換 `Kanban` tab 不會污染 `Pulse` 的統計結果
- 切回 `Pulse` 不需要重新整理頁面即可看到全量正確數字

---

### TD1-2 Kanban 欄位補齊

> 指派：Developer | 預估：0.5 天 | 優先級：P0

#### 目標

補齊主欄與 closed task 顯示機制，避免真實狀態消失。

#### 交付

- `dashboard/src/components/TaskBoard.tsx`
- `dashboard/src/components/TaskFilters.tsx`
- 如需要，新增 closed tasks toggle 元件

#### Acceptance Criteria

- 主欄可見 `Done`
- `Cancelled` / `Archived` 至少可透過 toggle 或 filter 顯示
- `No tasks` 僅在該欄真的沒有任務時顯示

---

### TD1-3 Pulse 指標與專案健康表重做

> 指派：Developer | 預估：0.5 天 | 優先級：P0

#### 目標

把單純完成率改成可判讀結構狀態的健康視圖。

#### 交付

- `dashboard/src/components/PulseBar.tsx`
- `dashboard/src/components/ProjectProgress.tsx`

#### Acceptance Criteria

- `PulseBar` 至少顯示 `Active / Moving / Blocked / Overdue / Review Queue / Done 7d`
- `ProjectProgress` 改為多狀態分布，不再只有 `% done`
- 每個 product 至少顯示 `done / in_progress / review / blocked / pending`

---

### TD1-4 人員負載表重做

> 指派：Developer | 預估：0.5 天 | 優先級：P0

#### 目標

用「每人負載摘要 + 可展開產品分布」取代最高狀態壓縮矩陣。

#### 交付

- `dashboard/src/components/PeopleMatrix.tsx`

#### Acceptance Criteria

- 同一位 assignee 的多種狀態能同時被看見
- PM 可以直接看出誰有 `blocked`、誰有 `overdue`
- 不再只用單一 `highestStatus` 表示一整格任務

---

### TD1-5 Kanban 卡片資訊架構調整

> 指派：Developer | 預估：0.25 天 | 優先級：P1

#### 目標

讓卡片在收合態就足夠支撐派工判讀。

#### 交付

- `dashboard/src/components/TaskCard.tsx`

#### Acceptance Criteria

- 收合態可看見 assignee、linked product/module、overdue、blocked、updatedAt
- 展開態保留 description / context / acceptance criteria / result 等長文

---

### TD1-6 風險清單與 drill-down

> 指派：Architect + Developer | 預估：0.5 天 | 優先級：P1

#### 目標

新增 risk-first 區塊，並讓 summary 元件可 drill-down。

#### 交付

- 新增 Pulse risk list 元件
- 新增 task list drawer / panel
- 定義 summary → task list 的互動契約

#### Acceptance Criteria

- 可從 `Blocked`、`Overdue`、`Review Queue` 點進對應清單
- risk list 依嚴重度排序

---

### TD1-7 QA 驗證

> 指派：QA | 預估：0.25 天 | 優先級：P0

#### 驗證案例

1. 切 `Kanban > My Inbox` 再回 `Pulse`，確認數字未縮水
2. 確認 `Done` 任務在 Kanban 可見
3. 開啟 closed tasks 後可看到 `Cancelled` / `Archived`
4. 找一位同時有 `review + blocked + in_progress` 的 assignee，確認 UI 能同時辨識
5. 找一個完成率低但 `review` 高的 product，確認不再被簡化成單一低進度條

#### 驗收產出

- 截圖證據
- 回歸風險註記
- 若有時間，補前端測試

---

## 建議執行順序

1. TD1-1 資料範圍重構
2. TD1-2 Kanban 欄位補齊
3. TD1-3 Pulse 指標與專案健康表重做
4. TD1-4 人員負載表重做
5. TD1-5 卡片資訊架構調整
6. TD1-6 風險清單與 drill-down
7. TD1-7 QA 驗證

---

## Done Criteria

- [ ] `Pulse` 與 `Kanban` 的資料範圍完全分離
- [ ] `Done`、`Cancelled`、`Archived` 在 UI 上都有明確出口
- [ ] PM 可在 `Pulse` 判斷 blocked / overdue / review queue
- [ ] PM 可在 `Pulse` 判斷每個 product 的狀態分布，而不是只有完成率
- [ ] PM 可在 `Pulse` 判斷每位 assignee 的真實負載
- [ ] QA 完成關鍵路徑驗證
