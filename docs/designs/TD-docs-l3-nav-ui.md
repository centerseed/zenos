---
type: TD
id: TD-docs-l3-nav-ui
status: ready
spec: SPEC-docs-l3-nav-ui.md
created: 2026-04-27
updated: 2026-04-27
---

# 技術設計：文件 UI — L3 Entity 導航展開

## 調查報告

### 已讀文件（附具體發現）
- `docs/specs/SPEC-docs-l3-nav-ui.md` — 9 條 AC，2 個 P0 surface（專案文件分頁 + /docs sidebar），1 個 P1（source count badge）
- `ADR-022-document-bundle-architecture.md` — D1: `doc_role: single | index` 雙模式；single 限 1 source，index 可 1..N；D2: source 必有 `source_id` UUID
- `dashboard/src/app/(protected)/docs/page.tsx` — `listDocs` + `getAllEntities` 後丟 `DocListSidebar`；click doc → `getDocumentDelivery` + `getDocumentContent` 載入編輯器
- `dashboard/src/features/docs/DocListSidebar.tsx:81-115` — `buildDocGroups` 用 `parentId` chain label 分組；`indexItems` 優先顯示但點下去走 `onSelect`，沒有展開 sources 能力
- `dashboard/src/app/(protected)/projects/page.tsx:902-905` — `descendants.filter(c => c.type==="document")` 攤平；1478–1522 渲染 2 欄 card grid，無展開無 preview
- `dashboard/src/features/docs/DocSourceList.tsx:11-21` — `DocSource` 型別無 `snapshot_summary`
- `dashboard/src/types/index.ts:81-95` — `Source` 型別無 `snapshot_summary`
- `src/zenos/interface/dashboard_api.py:901-937` — `_entity_to_dict` 用 `filter_sources_for_partner` pass-through raw dict → **`snapshot_summary` 已回傳至 frontend JSON response**，只缺 TypeScript type 宣告

### 搜尋但未找到
- `tests/spec_compliance/test_docnav*` → 無，本 TD 建立

### 我不確定的事
- 無（所有技術點已查明）

---

## AC Compliance Matrix

| AC ID | AC 描述（摘要） | 實作位置 | Test Function | 狀態 |
|-------|---------------|---------|---------------|------|
| AC-DOCNAV-01 | 文件分頁顯示可展開 L3 列表，不是扁平 grid | `projects/page.tsx` tab=docs section | `test_ac_docnav_01_list_not_grid` | STUB |
| AC-DOCNAV-02 | 點 L3 row → 展開 sources 子列表 | `DocL3AccordionList` expand handler | `test_ac_docnav_02_expand_shows_sources` | STUB |
| AC-DOCNAV-03 | 點 source → inline preview（metadata + snapshot） | `DocL3AccordionList` preview panel | `test_ac_docnav_03_source_click_inline_preview` | STUB |
| AC-DOCNAV-04 | 0 sources → 「尚無來源」空狀態 | `DocL3AccordionList` empty state | `test_ac_docnav_04_empty_sources_state` | STUB |
| AC-DOCNAV-05 | /docs sidebar L3 展開 sources 子列表 | `DocListSidebar` expandedDocIds state | `test_ac_docnav_05_sidebar_expand_sources` | STUB |
| AC-DOCNAV-06 | sidebar source click → editor 載入 | `DocListSidebar` onSelect(doc.id) | `test_ac_docnav_06_sidebar_source_loads_editor` | STUB |
| AC-DOCNAV-07 | single doc 點名稱 → 直接載入 | `DocListSidebar` doc_role branch | `test_ac_docnav_07_single_direct_load` | STUB |
| AC-DOCNAV-08 | index doc 點名稱 → 展開列表 | `DocListSidebar` doc_role branch | `test_ac_docnav_08_index_expand_on_name_click` | STUB |
| AC-DOCNAV-09 | L3 row 顯示 N sources badge | `DocL3AccordionList` + sidebar item | `test_ac_docnav_09_source_count_badge` | STUB |

---

## 變更範圍（純前端，無 backend 改動）

### 新增
- `dashboard/src/features/docs/DocL3AccordionList.tsx` — 可展開 L3 列表元件（給專案文件分頁用）

### 修改
| 檔案 | 變更說明 |
|------|---------|
| `dashboard/src/types/index.ts` | `Source` 介面補 `snapshot_summary?: string \| null` |
| `dashboard/src/features/docs/DocSourceList.tsx` | `DocSource` 介面補 `snapshot_summary?: string \| null` |
| `dashboard/src/app/(protected)/projects/page.tsx` | tab=docs section：用 `DocL3AccordionList` 取代 2 欄 card grid |
| `dashboard/src/features/docs/DocListSidebar.tsx` | L3 item 加展開能力（見介面設計） |

---

## Component 架構

### 新元件：`DocL3AccordionList`（專案文件分頁用）

```tsx
// Props
interface DocL3AccordionListProps {
  documents: Entity[];         // type=document entities
  t: ReturnType<typeof useInk>;
}

// State
expandedDocId: string | null   // 目前展開的 doc
previewSourceId: string | null // 目前 inline preview 的 source
```

**渲染邏輯：**
1. 每個 `doc` → 一個 accordion row
   - 顯示：`doc.name`、`doc.docRole`（"INDEX" badge / "SINGLE" badge）、source count badge（`doc.sources.length` sources）
   - 點 row → toggle `expandedDocId`
2. 展開後：`doc.sources.map(source => ...)` 子列表
   - 每項：type badge（ZenOS/GitHub/…）+ `source.label || source.uri`
   - 點 source → set `previewSourceId`，render inline preview panel
   - 0 sources → 「尚無來源」
3. Inline preview panel（selected source）：
   - `source.label`、`source.type`、`source.source_status`、`source.doc_type`
   - `source.snapshot_summary || doc.summary || "—"`（fallback chain）

### 修改：`DocListSidebar` 展開行為

新增 state：`expandedDocIds: Set<string>`

改變每個 doc item 的 render 邏輯：

```
if doc_role === "index":
  - 左側顯示 chevron（rotate 90° when expanded）
  - 點 entity 名稱 → toggleExpandedDoc(doc.id)，不呼叫 onSelect
  - 展開後顯示 sources 子列表（縮排）
  - 點 source → onSelect(doc.id)  ← 載入該 doc 到編輯器
  - source count badge 顯示在右側

if doc_role === "single" or null:
  - 維持現有行為：點名稱 → onSelect(doc.id)
  - 不顯示 chevron
```

---

## 介面合約清單

| 介面 | 參數/欄位 | 型別 | 必填 | 說明 |
|------|---------|------|------|------|
| `Source.snapshot_summary` | — | `string \| null` | 否 | Helper ingest 萃取的語意摘要（10KB 內）；`zenos_native` / `github` 通常無此欄位 |
| `DocSource.snapshot_summary` | — | `string \| null` | 否 | 同上，DocSourceList 用 |
| `DocL3AccordionList.documents` | — | `Entity[]` | 是 | type=document entities，sources 陣列必須存在（listDocs 已回傳）|
| `DocL3AccordionList.t` | — | `ReturnType<typeof useInk>` | 是 | Design token |
| inline preview fallback chain | `snapshot_summary > entity.summary > "—"` | — | — | 決策：snapshot 優先，entity summary 為 fallback，不呼叫額外 API |
| source click（/docs sidebar） | `onSelect(doc.id)` | `(id: string) => void` | 是 | 點 source 仍傳 doc.id；編輯器載入 doc 的 canonical revision |

---

## 不需要改的東西（明確標記）

- **Backend**：`_entity_to_dict` 已回傳完整 sources（含 `snapshot_summary`）
- **API**：`listDocs` 已回傳 `Entity.sources[]`，不需要 lazy-load 設計
- **`getDocumentDelivery` / `getDocumentContent`**：不改，source click 仍用 doc.id 載入
- **`DocSourceList.tsx` 渲染邏輯**：只補型別，不改 UI

---

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | Type 補欄位 + DocL3AccordionList 元件 | Developer | `Source` / `DocSource` 加 `snapshot_summary`；`DocL3AccordionList` 實作完；AC-DOCNAV-01/02/03/04/09 test 全 PASS |
| S02 | DocListSidebar 展開邏輯 | Developer（同 S01，可一起） | `DocListSidebar` 加 `expandedDocIds` state 與 doc_role 分流；AC-DOCNAV-05/06/07/08 test 全 PASS |
| S03 | QA 驗收 | QA | AC-DOCNAV-01~09 全部 PASS；瀏覽器端 smoke test 通過 |

---

## Risk Assessment

### 1. 不確定的技術點
- `snapshot_summary` 對 `zenos_native` / `github` sources 通常為空 → inline preview 必須有 fallback（已設計：用 `entity.summary`）
- 原心生技有 248 份 doc，accordion list 全展開效能 → 不應預展開，default collapsed 即可

### 2. 替代方案與選擇理由
- **LazyLoad sources**：每次 expand 才呼叫 API → 被排除，listDocs 已回傳完整 sources，不需要額外 API call
- **三層（L2→L3→sources）**：PM spec 明確選 B（兩層），不顯示 L2 → 不做

### 3. 需要用戶確認的決策
- **無**：所有設計點已確認

### 4. 最壞情況與修正成本
- `DocL3AccordionList` 展開效能問題（248 doc 全展開）→ 風險低，只有主動點擊才展開；若有效能問題加 React.memo 或 virtual scroll，修正成本 < 0.5 day

---

## Spec Compliance Matrix（Test File）

Test file：`dashboard/src/__tests__/docs_l3_nav_ui_ac.test.tsx`
