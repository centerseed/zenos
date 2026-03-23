# Dashboard 全景圖重新設計 — 技術設計

**作者**：Architect
**日期**：2026-03-22
**依據**：`docs/specs/dashboard-redesign-panorama.md`（PM spec）
**ADR**：`docs/decisions/ADR-005-dashboard-graph-library.md`

---

## 概覽

把 Dashboard 首頁從 project card grid 改成「公司知識全景圖」，用 graph visualization 展示 entities + relationships，深色主題 + shadcn/ui 統一視覺風格。

**不改的東西**：
- Firestore schema 不動
- 後端 MCP server 不動
- 現有 Firestore query functions 保留，只新增需要的

---

## Component 架構

```
app/page.tsx（首頁，重寫）
├── components/ui/          ← shadcn/ui 基礎元件
├── components/HealthBar.tsx ← 新：頂部健康指標列
├── components/KnowledgeGraph.tsx ← 新：Hero 知識關係圖
├── components/BlindspotPanel.tsx ← 新：盲點警示面板
├── components/NodeDetailSheet.tsx ← 新：點擊節點的側欄
└── components/ProjectCard.tsx ← 保留，降級到快速導航區
```

### 新增 Components

#### 1. KnowledgeGraph.tsx（Hero）

**技術**：`react-force-graph-2d`
**Props**：
```typescript
interface KnowledgeGraphProps {
  entities: Entity[];
  relationships: Relationship[];
  blindspotsByEntity: Map<string, Blindspot[]>;
  onNodeClick: (entity: Entity) => void;
  onNodeHover: (entity: Entity | null) => void;
}
```

**節點設計**：
- 大小：依子節點數量（`childCount`），product > module > goal/role
- 顏色：依 entity type
  - product = `#3B82F6`（藍）
  - module = `#8B5CF6`（紫）
  - goal = `#10B981`（綠）
  - role = `#F59E0B`（橙）
  - project = `#6366F1`（靛藍）
- 有 blindspot 的節點：外圈紅色光暈（`#EF4444` glow）
- paused entity：降低 opacity 到 0.4
- 節點 label：entity.name，白色文字

**邊設計**：
- 顏色：半透明白 `rgba(255,255,255,0.15)`
- hover 時高亮相關邊：`rgba(255,255,255,0.6)`
- 有方向箭頭（depends_on、serves 等有語意方向）

**互動**：
- Hover：節點放大 + 高亮連接邊 + tooltip 顯示 summary
- Click：觸發 `onNodeClick` → 開 NodeDetailSheet
- Zoom/Pan：內建支援
- 初始載入：nodes 從中心擴散動畫（force simulation warm-up）

**Canvas 自定義繪製**：
使用 `nodeCanvasObject` callback 自定義節點外觀（圓形 + glow + label）。

#### 2. HealthBar.tsx

頂部一行，5 個指標：

```typescript
interface HealthBarProps {
  entityCount: number;
  confirmRate: number;      // confirmedByUser 的比例 0-100
  activeBlindspots: number; // status=open 的 blindspot 數
  docCoverage: number;      // 有文件的 entity 比例 0-100
  lastUpdated: Date | null; // 最新 entity.updatedAt
}
```

顏色規則：
- confirmRate > 80% → 綠 | 50-80% → 黃 | < 50% → 紅
- activeBlindspots == 0 → 綠 | 1-3 → 黃 | > 3 → 紅
- docCoverage > 70% → 綠 | 40-70% → 黃 | < 40% → 紅

#### 3. BlindspotPanel.tsx

右側或下方面板，可收合：

```typescript
interface BlindspotPanelProps {
  blindspots: Blindspot[];
  onBlindspotClick: (blindspot: Blindspot) => void;
}
```

- severity=red 的排最上面，紅色卡片
- severity=yellow 的排下面，黃色卡片
- 每張卡片：description + related entity 名稱 + suggestedAction
- 沒有 blindspot 時自動收起

#### 4. NodeDetailSheet.tsx

點擊節點後從右側滑入的 sheet/drawer：

```typescript
interface NodeDetailSheetProps {
  entity: Entity | null;
  relationships: Relationship[];
  blindspots: Blindspot[];
  onClose: () => void;
}
```

內容：
- Entity name + type badge + status badge
- Summary
- 四維標籤（What/Why/How/Who）
- 關聯的 relationships 列表
- 關聯的 blindspots（如有，紅色高亮）
- 「View Project」 連結（如果是 product type）

---

## 資料流

```
page.tsx（首頁）
  useEffect:
    1. getProjectEntities() → products
    2. 對每個 product: getChildEntities(id) → modules/goals/roles
    3. 對每個 entity: getRelationships(id) → edges
    4. getAllBlindspots() → blindspots（新增 query）
    5. countDocuments(id) → docCoverage 計算

  組裝:
    - entities: 扁平化的所有 entity 列表
    - relationships: 所有 edges 的扁平列表（去重）
    - blindspotsByEntity: Map<entityId, Blindspot[]>
    - healthMetrics: 聚合計算

  渲染:
    <HealthBar metrics={healthMetrics} />
    <KnowledgeGraph entities={...} relationships={...} />
    <BlindspotPanel blindspots={...} />
    <NodeDetailSheet entity={selectedEntity} />
```

### 新增 Firestore Query

```typescript
// lib/firestore.ts — 新增

/** Fetch ALL entities (not just products) */
export async function getAllEntities(): Promise<Entity[]>;

/** Fetch ALL blindspots (not filtered by entity) */
export async function getAllBlindspots(): Promise<Blindspot[]>;

/** Fetch ALL relationships across all entities */
export async function getAllRelationships(): Promise<{ entityId: string; relationships: Relationship[] }[]>;
```

注意：`getAllRelationships()` 需要對每個 entity 查 subcollection。
SMB 場景 < 50 entities，parallel fetch 可接受。
未來若效能成問題，考慮 denormalize 到 top-level collection。

---

## 深色主題

### 全局 CSS

```css
/* app/globals.css */
:root {
  --background: #0A0A0B;
  --foreground: #FAFAFA;
  --card: #111113;
  --card-border: #1F1F23;
  --muted: #71717A;
  --accent-blue: #3B82F6;
  --accent-purple: #8B5CF6;
  --accent-green: #10B981;
  --accent-orange: #F59E0B;
  --accent-red: #EF4444;
}
```

### shadcn/ui 安裝

1. `npx shadcn@latest init` — 選 New York style + dark theme
2. 需要的 components：`card`, `badge`, `sheet`, `tooltip`, `separator`
3. 不需要全裝，用什麼裝什麼

### Header 升級

從白底灰字改為：
- 背景：`var(--background)`
- Logo：白色
- Nav：`var(--muted)` 未選中 / 白色選中
- 細線分隔：`var(--card-border)`

---

## 頁面改動範圍

| 頁面 | 改動 |
|------|------|
| `/`（首頁）| **完全重寫**：project grid → 全景圖 |
| `/projects`（detail）| 視覺升級：深色主題 + shadcn card |
| `/tasks` | 視覺升級：深色主題（Pulse + Kanban 邏輯不動）|
| `/login` | 視覺升級：深色主題 |
| `/setup` | 視覺升級：深色主題 |
| `layout.tsx` | 全局 CSS 改為深色 |

---

## 實作順序（3 個 Developer 任務）

### Task 1：基礎設施 — shadcn/ui + 深色主題 + 全局視覺升級
- 安裝 shadcn/ui（Tailwind v4 模式）
- 改 globals.css 為深色主題 CSS variables
- 升級 layout.tsx（深色 body）
- 升級所有頁面的 header 為深色
- 升級 `/login`、`/setup`、`/projects`、`/tasks` 的視覺（深色背景 + shadcn card）
- **不動邏輯，只改視覺**

Done Criteria：
- [ ] shadcn/ui 安裝成功（至少 card, badge, sheet, tooltip）
- [ ] 所有頁面背景為深色 (#0A0A0B)
- [ ] Header 為深色統一風格
- [ ] 現有功能不受影響（Pulse/Kanban/Login 都正常）
- [ ] `npm run build` 成功

### Task 2：KnowledgeGraph 核心 — 全景圖 component
- 安裝 `react-force-graph-2d`
- 新增 `getAllEntities()`、`getAllBlindspots()`、`getAllRelationships()` Firestore queries
- 實作 `KnowledgeGraph.tsx`（force-directed graph + 自定義節點繪製）
- 實作 `NodeDetailSheet.tsx`（點擊節點的側欄）
- 節點依 type 上色、有 blindspot 加紅色光暈、paused 降 opacity

Done Criteria：
- [ ] Graph 顯示所有 entities 和 relationships
- [ ] 節點依 type 上色（product 藍/module 紫/goal 綠/role 橙）
- [ ] 有 blindspot 的節點有紅色光暈
- [ ] Hover 節點：放大 + tooltip 顯示 name + summary
- [ ] Click 節點：開 NodeDetailSheet 顯示完整資訊
- [ ] Graph 有動態感（force simulation 浮動）
- [ ] 深色背景上節點發光

### Task 3：首頁組裝 — HealthBar + BlindspotPanel + 導航
- 實作 `HealthBar.tsx`（5 個健康指標）
- 實作 `BlindspotPanel.tsx`（盲點警示卡片）
- 重寫 `app/page.tsx`：組裝 HealthBar + KnowledgeGraph + BlindspotPanel
- 首頁底部加快速導航（小型 project 卡片列表，連結到 /projects?id=）
- 更新頂部導航：首頁 → 「Panorama」或保持 Projects

Done Criteria：
- [ ] 首頁打開 3 秒內看到知識關係圖
- [ ] 頂部 HealthBar 顯示 5 個指標（實體數/確認率/盲點數/文件覆蓋率/最後更新）
- [ ] 有 blindspot 時面板自動展開，沒有時收起
- [ ] 快速導航列出所有 products
- [ ] 整體視覺科技感、統一深色風格
