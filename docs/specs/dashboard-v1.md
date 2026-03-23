# Dashboard v1 — 完整規格

**日期**：2026-03-23
**狀態**：設計中
**前身**：合併 dashboard-v0.md、dashboard-redesign-panorama.md、company-pulse-dashboard.md

---

## 問題陳述

老闆打開 Dashboard，應該三秒內感受到「AI 懂我的公司」，而不是「又一個 Trello」。

Dashboard v0 解決了夥伴入口問題（登入、MCP 設定、ontology 瀏覽），但視覺上就是一個 generic project card grid。v1 要讓 Dashboard 成為 ZenOS 的差異化展示入口。

## 核心設計原則

1. **Ontology 是底層，每個分頁是同一份 ontology 的不同 view**
2. **每個 view 是讀寫介面**——用戶在專案 view 建模組 = 底層建 entity
3. **不出現 entity / ontology 用語**——用專案、模組、知識地圖、關聯

### 用語對照

| 技術概念 | UI 顯示 |
|---------|--------|
| Entity | 不出現；依 type 顯示為「專案」「模組」等 |
| Ontology | 不出現 |
| Product entity | 專案 |
| Module entity | 模組 |
| Relationship | 關聯 |
| Knowledge Graph view | 知識地圖 |
| Blindspot | AI 發現 或 待確認風險 |
| confirmedByUser | 已確認 / 草稿 |

---

## 分頁架構

```
┌──────────────────────────────────────────┐
│  ZenOS    [專案]  [知識地圖]  [任務]       │
├──────────────────────────────────────────┤
│  同一份 ontology，不同的投影方式            │
└──────────────────────────────────────────┘
```

| 分頁 | 主要用途 | 目標用戶 | 資料來源 |
|------|---------|---------|---------|
| 專案 | Product 為中心，底下模組/任務/owner | 老闆/PM 日常 | entities (type=product) + children |
| 知識地圖 | Entity 關係圖，跨專案連結 | 探索用 | all entities + relationships |
| 任務 | Kanban + Pulse 視角 | 執行者 | tasks + linked entities |

未來分頁（Phase 2）：
- 團隊（Who/Owner 為中心）
- 文件（Documents linked to entities）

---

## Tab 1：專案 View

**定位**：老闆日常用的入口。看起來像專案管理，底層是 ontology。

**Phase 0**：Product entity 直接當專案入口，加 owner 欄位。
**Phase 1**：當有客戶需要多條工作線，加 projects collection。

### 頁面元素

- **專案列表**：Product entities (status=active)，每個顯示：
  - 名稱、摘要
  - Owner（entity.owner，Phase 0 需要加此欄位）
  - 模組數量 + 確認率
  - 盲點數量（紅/黃 badge）
  - 相關任務統計（完成/進行中/待辦）
- **點擊專案**：展開子模組列表、相關任務、盲點
- **新增專案**：建立 product entity（底層）

---

## Tab 2：知識地圖 View

**定位**：ZenOS 的差異化展示。跨專案的知識關聯，kanban 永遠看不到的東西。

**使用場景**：
- Demo 給客戶看的 hero section
- 老闆被 AI 洞察驚艷後，想理解「為什麼 AI 知道」時探索
- 類比：Google Maps 的衛星圖（大部分人用導航就好，但好奇的人會切衛星圖）

### 三欄佈局（Palantir Foundry 啟發）

```
┌─────────┬──────────────────────┬──────────┐
│ 左側邊欄 │    中央關係圖          │ 右側詳情  │
│ 230px   │    Force-directed     │ 350px    │
│         │    Graph              │          │
│ 產品選擇 │                      │ 點擊節點  │
│ 盲點清單 │                      │ 展開      │
│ 任務統計 │                      │          │
└─────────┴──────────────────────┴──────────┘
```

### 左側邊欄

- **產品選擇**：點擊產品名稱 → 圖聚焦到該產品及其模組
- **盲點清單**：紅色優先，點擊跳到相關節點
- **任務統計**：完成/進行中/待辦 breakdown

### 中央關係圖

- **技術**：react-force-graph-2d（已選定，見 ADR-005）
- **節點編碼**：
  - 大小 = type（product 最大）
  - 顏色 = type（blue=product, purple=module, green=goal, amber=role）
  - 亮度 = 活躍度（最近更新越亮）
  - 虛線圈 = 草稿（confirmedByUser=false）
  - 紅色光暈 = 有盲點
  - 藍色 badge = 相關任務數量
- **互動**：
  - Hover = dim 不相關節點，高亮連結路徑
  - Click = 右側展開詳情面板
  - Zoom/Pan = 標準

### 右側詳情面板

點擊任何節點滑出，顯示：

1. **基本資訊**：名稱、類型、摘要、Owner、更新時間、草稿/已確認
2. **關聯實體**：可點擊的 Entity Chip（帶類型色點），依方向分組（隸屬/子模組/依賴）
3. **盲點**：紅/黃分色，含建議行動
4. **已知問題**：如 entity 有 details.knownIssues
5. **文件**：連結的 documents（目前 0，因為文件連結到舊 entity ID）
6. **相關任務**：任務列表，含狀態點 + assignee badge

四維標籤（What/Why/How/Who）是 AI metadata，收在「進階」或默認隱藏。

---

## Tab 3：任務 View

**定位**：執行者的工作追蹤介面。

### 雙模式切換

- **Pulse**（預設）：公司作戰室
- **Kanban**：傳統看板

### Pulse 模式（四區塊）

1. **指標列**：Active / Moving / Blocked / Overdue / Review 五張卡片
2. **專案進度條**：每個 product 的任務完成率
3. **角色 × 專案 矩陣**：行=assignee，列=product，格子=任務數+狀態分佈
4. **活動時間線**：最近的任務事件 + blindspot 發現

### Kanban 模式

- 六欄：Backlog | Todo | In Progress | Review | Done | Blocked
- 可依 assignee / product / priority 篩選

---

## 跨分頁共用

### Entity Chip（Palantir 的 inline reference 模式）

在任何 view 中，每個 entity 引用都是可點擊的 chip：

```
[● 藍點] Paceriz [→]
```

點擊跳到該 entity 的詳情面板。這讓 ontology 在每個 view 裡都是活的。

### 確認佇列

所有 view 共用的確認機制。待確認項目（confirmedByUser=false）在任何 view 被看到時都標記為「草稿」，點擊可以直接確認。

---

## 技術基礎（v0 延續）

- **框架**：Next.js 15 (App Router) + Tailwind + shadcn/ui
- **部署**：Firebase Hosting（zenos-naruvia.web.app）
- **Auth**：Firebase Auth (Google) + partner document validation
- **資料**：直接讀 Firestore（不經 MCP server）
- **主題**：Deep dark（#09090B 背景），shadcn/ui dark mode

---

## 資料模型缺口（需要 Architect 處理）

| 缺口 | 影響 | 優先級 | 解法 |
|------|------|--------|------|
| Entity 缺 `owner` 欄位 | 專案 view 無法顯示負責人 | P0 | Entity schema 加 owner: string |
| Entity 缺 `sources` 欄位 | 詳情面板看不到相關文件 | P0 | Entity schema 加 sources: [{uri, label, type}]，取代 document entry 作為文件索引 |
| Tasks 的 `linkedEntities` 全空 | 任務和知識沒有連結 | P0 | MCP task tool 建任務時自動推斷 linkedEntities |
| Documents collection 空 | — | P2 | 改用 entity.sources 做文件索引，document collection 保留給高價值 semantic proxy |

---

## 實作優先級

| 優先級 | 功能 | 前置條件 |
|--------|------|---------|
| P0 | 知識地圖 tab（三欄佈局）| 已有 mockup，react-force-graph-2d 已安裝 |
| P0 | Entity schema 加 owner | Architect |
| P1 | 專案 tab | Owner 欄位就緒後 |
| P1 | 任務 tab Pulse 模式 | linkedEntities 修復後 |
| P2 | 確認佇列 | |
| P2 | 團隊 tab | |

---

## Mockup 參考

Preview 頁面位置：`dashboard/src/app/preview/mockup-c/page.tsx`
使用真實 Firestore 資料（21 entities, 13 blindspots, 22 tasks, 152 documents）。

---

## 本文件合併自

| 原文件 | 保留狀態 |
|--------|---------|
| dashboard-v0.md | → archive（基礎需求已併入本文件） |
| dashboard-v0-technical-design.md | → archive（技術決策已併入本文件） |
| dashboard-redesign-panorama.md | → archive（知識地圖設計已併入本文件） |
| dashboard-redesign-tech-design.md | → archive（元件設計已併入本文件） |
| company-pulse-dashboard.md | → archive（Pulse 設計已併入本文件） |
