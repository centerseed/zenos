# Dashboard v1 — Architect 交接文件

**日期**：2026-03-23
**來源**：PM 與老闆討論後整理
**前置**：foundation-p0-architect-handoff.md（Entity Schema 擴展，**必須先完成**）、dashboard-v1.md（完整規格）、ADR-005（graph library）、ADR-006（entity/project 分離）

---

## 任務摘要

將 preview/mockup-c 的三欄知識地圖佈局，從 hardcoded 靜態資料改為讀 Firestore 即時資料，並整合進 Dashboard 的多分頁架構。

---

## 現有 Mockup 位置

`dashboard/src/app/preview/mockup-c/page.tsx`（719 行）

**已實作的功能（可直接搬用）：**

| 元件 | 說明 | 程式碼位置 |
|------|------|-----------|
| `Sidebar` | 左 230px：公司 header、產品選擇（可聚焦圖）、盲點清單、任務統計 | L75-174 |
| `GraphCanvas` | 中央 force-directed 圖：react-force-graph-2d、節點自訂繪製、hover/click 互動 | L178-484 |
| `DetailSheet` | 右 350px：entity 基本資訊、tags、關聯（parent/children/depends）、盲點、已知問題、文件、任務 | L489-654 |
| `EntityChip` | 可點擊的 entity 引用元件（色點 + 名稱） | L60-71 |

**節點繪製規則（nodeCanvasObject, L300-398）：**
- 大小 = type（product: val=20, goal: 12, document: 6, 其餘: 8），半徑 = sqrt(val) * 2.8
- 顏色 = type（blue=#3B82F6 product, purple=#8B5CF6 module, green=#10B981 goal, amber=#F59E0B role, cyan=#06B6D4 document, rose=#F43F5E project）
- 亮度 = 活躍度（≤1d: 1.0, ≤3d: 0.7, ≤7d: 0.45, >7d: 0.2）
- 虛線圈 = 草稿（confirmedByUser=false），amber 色
- 紅色光暈 = 有 open blindspot（shadowBlur=25, shadowColor=#EF4444）
- 藍色 badge = 任務數量 > 0 時顯示
- Hover = dim 非連接節點（globalAlpha=0.12），高亮連結路徑
- 選中 = 白色描邊 + glow

**力學參數（L217-219）：**
```
charge.strength(-500).distanceMax(400)
link.distance(100)
center.strength(0.03)
cooldownTicks=120, warmupTicks=60, d3AlphaDecay=0.02, d3VelocityDecay=0.3
```

---

## 需要改的部分

### 1. 從 hardcoded → Firestore 即時資料

Mockup 用 `realData.ts` 的 hardcoded 陣列。正式版改為：

```typescript
// 已有的 Firestore helpers（dashboard/src/lib/firestore.ts）
getAllEntities()        // 所有 entity
getAllRelationships()   // 所有 relationship（目前是 N+1 subcollection query，需優化）
getAllBlindspots()      // 所有 blindspot
getTasks()             // 所有 task
```

**注意：** `getAllRelationships()` 目前是先取所有 entity ID 再逐一讀 subcollection，entity 數量多時會慢。考慮：
- Firestore 加一個 top-level `relationships` collection（去正規化）
- 或用 `collectionGroup` query

### 2. 整合進多分頁架構

目前 Dashboard 路由：
```
/           → 首頁（目前是 project card grid）
/projects   → 專案詳情
/tasks      → 任務看板
/setup      → MCP 設定
/login      → 登入
```

目標路由（知識地圖作為首頁）：
```
/                → redirect to /knowledge-map（或直接是知識地圖）
/knowledge-map   → 三欄知識地圖（mockup-c 搬過來）
/projects        → 專案 view（P1，本次不做）
/tasks           → 任務 view（已有，需升級為 Pulse + Kanban）
/setup           → 保留
/login           → 保留
```

Header nav 改為：
```
ZenOS    [知識地圖]  [專案]  [任務]    [設定]  [用戶名]
```

### 3. 分層展開互動（新需求）

知識地圖的 Entity 有三層（L1 product → L2 module → L3 document/goal/role/project），UI 需要反映這個層級結構。

**預設狀態：**
- 圖只顯示 L1（product）+ L2（module）
- Sidebar 顯示樹狀結構，L2 以下收合

**展開操作：**
- **Sidebar**：點擊 module 的展開箭頭 → 彈出 type 篩選 checkboxes（document / goal / role / project）
- **圖上**：雙擊 module 節點 → 同樣彈出 type 篩選
- 勾選的 type 才展開到圖上，L3 節點從 module 位置「長出來」（動畫）
- 取消勾選 → L3 節點縮回 module

**雙向連動：**
- Sidebar 展開 = 圖上展開（反之亦然）
- 點擊任何節點（不管哪層）→ 右側 Detail Sheet 顯示詳情

**多選：**
- 可以同時展開多個 module，各自獨立的 type 篩選

### 4. 任務連結方式改善

Mockup 的 `inferTasksForEntity()` 用**文字比對**推斷任務歸屬（L25-31）：
```typescript
// 目前：模糊比對 entity name / tags.what 和 task title
return tasks.filter(t => title.includes(name) || keywords.some(kw => title.includes(kw)));
```

正式版應該用 `task.linkedEntities` 欄位（目前全空）。但在 `linkedEntities` 修復前，這個 fallback 可以保留。

### 5. 文件連結（重要變更）

Document 現在是 entity(type="document")，不是獨立 collection。知識地圖上會出現 document 節點。

**知識地圖上**：document entity 顯示為 cyan 色小節點，連到所屬的 module/product。
**詳情面板**：
- 「文件」區塊顯示兩種來源：
  1. 子 document entity（`parent_id` 指向此 entity 的 document type 節點）
  2. `entity.sources` 欄位裡的參考連結
- Document entity 可點擊（跳到該節點的詳情）
- Sources 連結可點擊（跳到外部 URL — GitHub/Drive/Notion）

**資料來源**：`/zenos-capture` 掃目錄後自動建立 document entity 和填入 sources。

---

## Schema 變更需求

### Entity 加 `owner` 欄位

```
entities/{id}
  + owner: string | null     // Phase 0: 簡單的名字字串
                               // Phase 1: 改為 reference to who collection
```

MCP Server 的 `write(collection="entities")` 需支援 `owner` 欄位。

### Entity 加 `sources` 欄位 + `visibility` 欄位

```
entities/{id}
  + sources: [                // 非 entity 級文件的參考連結
      {
        uri: string,          // "github://owner/repo/path" 或 "gdrive://fileId" 或 URL
        label: string,        // 顯示名稱
        type: "github" | "gdrive" | "notion" | "url"
      }
    ]
  + visibility: "public" | "restricted"   // 預設 public
```

文件索引的雙軌模型：
- **高價值文件**（spec, 架構, PRD）→ entity(type="document")，出現在知識地圖上
- **低價值文件**（筆記, 草稿）→ entity.sources，只在詳情面板列出

### Entity type 加 `document`

MCP Server 需允許 `type: "document"`。Document entity 出現在知識地圖上。

### MCP Server 更新

**全部 schema 改動的詳細規格見 `foundation-p0-architect-handoff.md`。** Dashboard 實作依賴那份文件的任務 1 先完成。

---

## 不做的事（明確排除）

- ❌ 專案 tab（P1，等 owner 欄位和更多客戶資料）
- ❌ 任務 tab Pulse 模式升級（P1，等 linkedEntities 修復）
- ❌ 確認佇列互動（P2）
- ❌ 圖上的即時編輯（P2）
- ❌ Document collection（已廢棄，改用 entity type="document" + entity.sources）

---

## 驗收條件

1. `/knowledge-map` 頁面載入後 3 秒內顯示 force-directed 關係圖
2. 圖使用 Firestore 即時資料（不是 hardcoded）
3. 預設只顯示 L1（product）+ L2（module），不顯示 L3
4. 雙擊 module 節點或 sidebar 展開 → 彈出 type 篩選，勾選後展開 L3 節點
5. Sidebar 樹狀結構與圖雙向連動
6. 點擊節點右側滑出詳情面板，顯示 entity 資訊 + 關聯 + 盲點 + sources + 任務
7. Header 有三個分頁 tab（知識地圖 active，專案和任務可點擊切換）
8. AuthGuard 保護（需登入）
9. 部署到 Firebase Hosting 並可用

---

## 參考文件

- **`docs/specs/foundation-p0-architect-handoff.md`** — 基礎層 P0（**先做這個**）
- `docs/specs/dashboard-v1.md` — 完整規格
- `docs/spec.md` Part 7.2 — Entity 架構（分層、邊界、用語）
- `docs/decisions/ADR-005-dashboard-graph-library.md` — Graph library 選型
- `docs/decisions/ADR-006-entity-project-separation.md` — Entity/Project 分離
- `dashboard/src/app/preview/mockup-c/page.tsx` — 可直接搬用的元件程式碼
