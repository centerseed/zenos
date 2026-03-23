# Company Pulse Dashboard

> 把 Tasks 頁面從「看板工具」升級為「公司作戰室」，讓老闆 3 秒內掌握全局。

## 問題陳述

目前 `/tasks` 頁面是標準 Kanban board，功能完整但：
- 視覺上是死的，沒有動態感
- 只展示「任務清單」，看不到人、案子、進度之間的關係
- 對老闆來說跟 Trello 沒有差異化
- ZenOS 的核心價值（AI 驅動的知識→行動閉環）完全沒有體現

## 目標

老闆打開這個頁面，3 秒內回答三個問題：
1. **公司現在整體健不健康？** → Pulse Bar
2. **誰在忙什麼？有沒有人卡住？** → People × Projects 矩陣
3. **哪些案子在推進、哪些有風險？** → 專案進度條 + Activity Timeline

## 非目標

- 不做虛擬辦公室 / 3D 空間
- 不做即時協作（real-time cursor、聊天）
- 不取代 Kanban — Kanban 降級為第二層 Detail View
- 不需要新增 Firestore 欄位（P0/P1 全部用現有資料）

## 使用者故事

- 身為老闆，我打開 Dashboard 就想看到公司整體的健康狀況，不想一個一個任務點開
- 身為老闆，我想知道每個人手上有幾件事、分布在哪些案子、誰被卡住了
- 身為老闆，我想看到每個案子做到幾成了，不是看一堆卡片自己數

---

## 設計規格

### 頁面結構（上到下四個區塊）

```
┌─ Pulse Bar ─────────────────────────────────────────────────┐
│  8 Active    3 Moving    2 Blocked    1 Overdue    2 Review │
└─────────────────────────────────────────────────────────────┘

┌─ Projects Progress ─────────────────────────────────────────┐
│  Paceriz     ████████████░░░░ 64%    7/11                   │
│  ZenOS       ██████░░░░░░░░░░ 30%    3/10                   │
│  Naruvia     ████░░░░░░░░░░░░ 25%    2/8                    │
└─────────────────────────────────────────────────────────────┘

┌─ People × Projects 矩陣 ───────────────────────────────────┐
│              Paceriz          ZenOS          Naruvia         │
│ Architect    ●● WORKING      ● REVIEW ⏳                    │
│ Developer    ● DONE ✓        ●● WORKING     ● BLOCKED 🔴   │
│ QA                           ● TODO                         │
└─────────────────────────────────────────────────────────────┘

┌─ Activity Timeline ─────────────────────────────────────────┐
│ 今天                                                        │
│ ├─ 14:30  Developer 完成「Firestore Rules」→ Paceriz    ✅  │
│ ├─ 11:20  Architect 開始「MCP 介面設計」→ Paceriz       🔄  │
│ 昨天                                                        │
│ ├─ 18:40  Developer 被阻塞「Agent 修復」→ Naruvia       🔴  │
│ └─ 16:00  QA 提交 Review「E2E 測試」→ ZenOS             📋  │
└─────────────────────────────────────────────────────────────┘
```

### 區塊一：Pulse Bar（指標列）

橫排 5 個指標卡片：

| 指標 | 計算方式 | 顏色規則 |
|------|----------|----------|
| Active | `status in [todo, in_progress, review, blocked]` 的 count | 白底藍字 |
| Moving | `status == in_progress` 的 count | 綠色 |
| Blocked | `status == blocked` 的 count | **紅色**（>0 時強調） |
| Overdue | `dueDate < now && status not in [done, cancelled]` 的 count | **橙色**（>0 時強調） |
| Review | `status == review && !confirmedByCreator` 的 count | 紫色 |

**交互**：點擊任一指標卡片 → 過濾下方矩陣只顯示對應任務。

### 區塊二：Projects Progress（專案進度條）

每個 Entity（type=product）一行：

```
[專案名稱]  [進度條 ████░░░░]  [百分比]  [done/total]
```

- 進度 = `tasks where linkedEntities contains entityId && status == "done"` / `total tasks linked`
- 進度條顏色：< 30% 紅色、30-70% 黃色、> 70% 綠色
- 排序：按完成百分比降序（進度最高的在最上面）

**交互**：點擊專案名稱 → 展開該專案的任務列表（複用現有 TaskCard）。

### 區塊三：People × Projects 矩陣（核心區）

**行** = 所有有任務的 assignee（從 tasks 聚合 distinct assignees）
**列** = 所有 active 的 Entity（type=product）

每個格子顯示：
- **圓點數量** = 該人在該專案的 active 任務數
- **最高優先狀態標籤**：BLOCKED（紅底）> IN PROGRESS（黃底）> REVIEW（紫底）> TODO（藍底）> DONE（灰底）
- 空格子 = 該人不參與該專案

**格子顏色規則**：
- 有 BLOCKED 任務 → 紅色底 + 脈衝動畫（CSS animation）
- 有 Overdue 任務 → 橙色邊框
- 全部 DONE → 綠色淡底
- 其他 → 白底

**交互**：
- Hover → tooltip 顯示該人在該專案的任務標題列表
- Click → 展開該格子的完整任務卡片（複用 TaskCard）

**人員行尾統計**：
```
Architect  ██████░░░░ 完成 3 / 剩 5
```

### 區塊四：Activity Timeline（動態流）

從所有 Task 的 `updatedAt` 排序，取最近 20 筆：

每條動態格式：
```
[時間]  [assignee] [動作] [任務標題] → [專案名稱]  [狀態 icon]
```

動作推斷邏輯（從 task 欄位推導）：
- `status == done && completedAt 在近期` → 「完成」 ✅
- `status == in_progress && updatedAt 在近期` → 「進行中」 🔄
- `status == blocked` → 「被阻塞」 🔴 + 顯示 blockedReason
- `status == review` → 「提交 Review」 📋
- `rejectionReason != null` → 「被退回」 ❌

**Blindspot 混入**（如果有）：
- 從 `blindspots` collection 拿 severity=red 的，混入 timeline
- 格式：`⚠️ AI 偵測盲點：[description] → [related entity]`

---

## 資料需求

### 新增 Firestore Query（firestore.ts）

```typescript
// 取所有 active partners
async function getAllPartners(): Promise<Partner[]>

// 取所有 active entities（type=product）— 已有 getProjectEntities()

// 取所有任務（不帶 filter，dashboard 全局視角）
async function getAllActiveTasks(): Promise<Task[]>

// 取最近的 blindspots（severity=red, status=open）
async function getRecentBlindspots(limit: number): Promise<Blindspot[]>
```

### 不需要改的（現有已足夠）

- Task 資料結構：所有欄位都已存在
- Entity 資料結構：不需改
- Blindspot 資料結構：不需改

---

## 導航變更

- `/tasks` → 預設顯示 Company Pulse Dashboard
- 在 Pulse Dashboard 內加 tab 切換：`Pulse | Kanban`
- Kanban 保留現有所有功能（filters、tabs）
- Header nav 改名：`Tasks` → `Command Center`（可選）

---

## 需求優先級

**P0（必須有，Demo 核心）**
- [ ] Pulse Bar 指標列（5 個指標卡）
- [ ] Projects Progress 進度條
- [ ] People × Projects 矩陣（含格子顏色規則）
- [ ] Pulse / Kanban tab 切換

**P1（重要，但 v1 可先 hardcode 或簡化）**
- [ ] Activity Timeline（需要推導動態）
- [ ] 矩陣格子 hover tooltip
- [ ] 矩陣格子 click 展開任務
- [ ] Pulse Bar 點擊過濾
- [ ] 人員行尾進度條

**P2（未來再說）**
- [ ] Blindspot 混入 timeline
- [ ] 進度條動畫（count-up、bar animation）
- [ ] Blocked 格子脈衝動畫
- [ ] 任務級進度條（需改 acceptanceCriteria schema）
- [ ] Timeline / Gantt 第三視圖

---

## 成功指標

- 短期：老闆打開頁面 3 秒內能說出「誰被卡住了」
- 長期：Demo 給外部企業老闆時，對方問「這個我的公司也能用嗎？」

## 開放問題

- ⚠️ 待 Architect 確認：矩陣在任務量大時（>50）的效能策略
- ⚠️ 待 Architect 確認：Activity Timeline 是否需要獨立的 activity log collection，還是純從 task updatedAt 推導
- ❓ 待 Barry 決策：Header 要不要從 `Tasks` 改名為 `Command Center`

---

## 技術筆記（給 Architect）

- 現有 `TaskBoard.tsx`、`TaskCard.tsx` 保留，降級為 Kanban tab 的 component
- 新增 component 建議：`PulseBar.tsx`、`ProjectProgress.tsx`、`PeopleMatrix.tsx`、`ActivityTimeline.tsx`
- 所有計算（指標、矩陣聚合）在 client 端做，不需要 Cloud Functions
- 矩陣的「專案」維度需要 resolve `task.linkedEntities` → Entity name，建議在 page 層一次性 batch fetch
