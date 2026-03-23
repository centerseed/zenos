# Dashboard Redesign：全景圖優先

**日期**：2026-03-22
**狀態**：待 Architect 確認
**交付角色**：Architect → Developer

## 問題陳述

現在的 Dashboard 首頁是一個 generic 的 project card grid，Tasks 頁是標準 kanban。
任何人看到都會覺得「這不就是另一個 Trello？」——完全沒有傳達 ZenOS 的核心價值。

ZenOS 的賣點是「AI 懂你的公司」，但畫面上看不到任何「懂」的感覺。

## 目標

老闆打開 Dashboard，三秒內感受到：**「我的公司被 AI 看透了。」**

Demo 時能讓人「哇」，而不是「喔，又一個專案管理工具」。

## 非目標

- 不重寫後端 / Firestore schema（資料結構已足夠）
- 不增加新功能（用現有資料做視覺升級）
- 不做 drag-and-drop、inline editing 等互動功能

---

## 設計方向：全景圖即首頁

### 首頁（`/`）— 公司知識全景圖

進入 Dashboard 第一眼看到的不是 project list，而是 **公司的知識關係網絡**。

**核心元素：**

1. **知識關係圖（Hero 區域，佔據畫面主體）**
   - 以圖（graph）的形式展示公司所有 entities 和它們之間的 relationships
   - 節點 = Entity（product / module / goal / role），大小依子節點數量決定
   - 邊 = Relationship（depends_on / serves / owned_by / part_of / blocks）
   - 顏色語意：active = 亮色，paused = 淡色，有 blindspot 的節點 = 紅色光暈
   - 點擊節點展開詳情側欄（名稱、摘要、四維標籤、關聯 blindspots）
   - 視覺參考：Obsidian graph view、Neo4j Bloom、GitHub 的 dependency graph

2. **盲點警示（固定在畫面右側或下方）**
   - 紅色盲點 = 紅色卡片，搶眼但不擋住全景圖
   - 黃色盲點 = 黃色卡片
   - 每張卡片：描述 + 影響的實體 + 建議行動
   - 有盲點時自動展開，沒有就收起來

3. **健康指標列（頂部，一行搞定）**
   - 實體數量 | 確認率（confirmedByUser 的比例）| 活躍盲點數 | 文件覆蓋率 | 最後更新
   - 用顏色表達健康度（綠/黃/紅）

4. **快速導航**
   - 全景圖下方或側邊：Projects 列表（小卡片，點擊切到 project detail）
   - 頂部導航保留 Tasks（Pulse / Kanban）入口

### Project Detail（`/projects?id={id}`）— 保持但升級

- 保留 EntityTree + Blindspots 的結構
- 視覺升級：用 component library 的卡片和排版
- 加入該 project 的 sub-graph（只顯示相關 entities 的關係圖）

### Tasks（`/tasks`）— 保持但升級

- Pulse view 和 Kanban view 保留
- 視覺升級：用 component library 統一風格

---

## 視覺設計規格

### Component Library

**採用 shadcn/ui** — 理由：
- 與 Next.js + Tailwind 完美整合
- 不是 npm 依賴，是 copy-paste 的 component，完全可控
- 視覺品質高，開箱即用就好看
- 支援 dark mode（demo 加分）

### 圖表 / Graph 視覺化

**關係圖選型（待 Architect 確認）：**
- 選項 A：**React Flow** — 節點可互動、可拖曳、生態系成熟
- 選項 B：**D3.js force-directed graph** — 更自由、動態感更強
- 選項 C：**Sigma.js / Cytoscape.js** — 專門做 graph 的 library

⚠️ 關鍵要求：圖要好看、有動態感（節點會微微浮動）、點擊有回饋。
不要做成靜態的方塊連線圖。

### 配色

- 主色：深灰 / 近黑背景（#0A0A0B 或類似）— 讓圖的節點發光
- 節點顏色：依 entity type 區分（product = 藍、module = 紫、goal = 綠、role = 橙）
- 強調色：盲點紅、健康綠
- 整體感覺：**科技感、沉穩、AI 的感覺**——不是可愛的 SaaS 風格

### 字體

- 保持系統字體或用 Inter — 乾淨、現代
- 數字用 tabular-nums（monospace 數字對齊）

---

## 資料來源（已有，不需新增）

| 視覺元素 | Firestore 來源 | 查詢方法 |
|----------|---------------|----------|
| 全景圖節點 | `entities` collection | `getProjectEntities()` + `getChildEntities()` |
| 全景圖邊 | `entities/{id}/relationships` | `getRelationships()` |
| 盲點警示 | `blindspots` collection | `getBlindspots()` |
| 健康指標 | `entities` + `documents` | 聚合計算 |
| Task 指標 | `tasks` collection | `getTasks()` |

---

## 成功條件

- [ ] 打開首頁，三秒內看到公司知識關係圖，不需要任何點擊
- [ ] 有 blindspot 的實體在圖上明顯標記（紅色光暈或警示圖示）
- [ ] 圖有動態感（節點浮動、hover 有回饋、點擊展開側欄）
- [ ] 整體視覺風格一致（shadcn/ui + 深色主題）
- [ ] 非技術人員看到會說「哇」而不是「這是什麼工程師工具」

## P1（重要但 v1 可以先不做）

- [ ] Dark mode toggle（先做 dark mode only 即可）
- [ ] 圖的佈局可切換（force / tree / radial）
- [ ] 動畫轉場（頁面切換、圖的展開收合）

## P2（未來再說）

- 圖上直接操作（新增 entity、拖曳連線）
- 即時協作（多人同時看）

---

## 開放問題

- ⚠️ **Graph library 選型**：待 Architect 評估 React Flow vs D3 vs 其他
- ⚠️ **效能**：entities 數量大時 graph 的渲染效能
- ⚠️ **shadcn/ui 與 Next.js 16 的相容性**：待 Architect 確認
