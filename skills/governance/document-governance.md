# L3 文件治理規則 v2.0（含完整範例）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是task（文件沒有 owner 和 AC）。

## 情境 → 文件對應（泛用版）

| 情境 | 文件類別 | 說明 |
|------|---------|------|
| 新功能需求 / 產品規格 | SPEC | 定義 what / why，含 Acceptance Criteria |
| 重大決策（架構、策略、供應商選型） | DECISION | 記錄為什麼選這個方案，可被 supersede |
| 實作設計 / 流程設計 | DESIGN | 定義 how，component 架構、DB schema、流程圖 |
| 計畫排程 / 企劃 | PLAN | Sprint Plan、行銷企劃、專案時程 |
| 報告 / 分析 | REPORT | 效能報告、市場調研、月報、回顧 |
| 合約 / 協議 / SLA | CONTRACT | 有約束力的文件、API contract、NDA |
| 操作手冊 / SOP / 指南 | GUIDE | Playbook、新人手冊、品管手冊 |
| 會議紀錄 | MEETING | 決議、行動項目、討論要點 |
| 外部參考、競品研究、法規 | REFERENCE | 無嚴格生命週期，ontology_entity 可為 null |
| QA 驗收場景 / 品質檢驗 | TEST | Given/When/Then 格式，P0/P1 分級 |
| 其他 | OTHER | 不屬於以上類別 |

### Legacy 別名（自動轉換）
舊類別 → 新類別：ADR→DECISION, TD→DESIGN, TC→TEST, PB→GUIDE, REF→REFERENCE。
搜尋時會自動展開（搜 ADR 也會找到 DECISION，反之亦然）。

> **原則：** 新功能開發必須同時建 SPEC + TEST。DESIGN 視複雜度決定。DECISION 只在重大不可逆的決策時建立。

## 各文件類別完整範例 Frontmatter

SPEC 範例：
```yaml
---
doc_id: SPEC-governance-framework
title: 功能規格：治理框架
type: SPEC
ontology_entity: 知識治理框架
status: approved
version: "1.0"
date: 2026-02-15
supersedes: null
---
```

DECISION 範例（取代原 ADR）：
```yaml
---
doc_id: DECISION-entity-architecture
title: 決策紀錄：Entity 三層模型
type: DECISION
ontology_entity: 知識節點架構
status: approved
version: "1.0"
date: 2026-01-20
supersedes: DECISION-entity-flat-model
---
```

DESIGN 範例（取代原 TD）：
```yaml
---
doc_id: DESIGN-three-layer-arch
title: 技術設計：三層架構實作
type: DESIGN
ontology_entity: 服務分層架構
status: under_review
version: "0.3"
date: 2026-03-01
supersedes: null
---
```

TEST 範例（取代原 TC）：
```yaml
---
doc_id: TEST-governance-framework
title: 測試場景：治理框架
type: TEST
ontology_entity: 知識治理框架
status: approved
version: "1.0"
date: 2026-02-15
supersedes: null
---
```

PLAN 範例（非軟體）：
```yaml
---
doc_id: PLAN-q2-launch
title: Q2 產品上市企劃
type: PLAN
ontology_entity: 產品上市策略
status: approved
version: "1.0"
date: 2026-03-15
---
```

CONTRACT 範例：
```yaml
---
doc_id: CONTRACT-vendor-sla
title: 供應商服務水準協議
type: CONTRACT
ontology_entity: 供應商管理
status: approved
version: "2.0"
date: 2026-02-01
supersedes: CONTRACT-vendor-sla-v1
---
```

REFERENCE 範例：frontmatter 同上，`ontology_entity` 可為 `null`（REFERENCE 是唯一例外）。

TEST 內容格式（Given/When/Then，標明 P0/P1）：
```markdown
## P0 場景（必須全部通過）
### S1: {場景名稱}
Given: {前提狀態}
When: {操作}
Then: {預期結果}

## P1 場景（應通過）
### S2: {場景名稱}
...
```

> **Phase 1 統一回傳格式：** 所有回傳改為 `{status, data, warnings, suggestions, similar_items, ...}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

> **重複文件檢查：** `write` 回傳 `similar_items` 列出相近的既有文件。建立前應檢查避免重複。

> **原子取代：** 建立新版文件時，可在 `write` 的 data 中同時填入 `supersedes` 欄位，Server 會原子性地將舊文件標為 superseded。

## doc_role: single vs index（ADR-022 Document Bundle）

### 概念
- **single**（預設）：文件有一個主要 source，可能有輔助 source
- **index**：文件本身是多個 source 的索引/集合
  - 軟體範例：「產品文件集」包含 SPEC + DESIGN + TEST 三類文件
  - 非軟體範例：「合規文件包」包含 CONTRACT + REFERENCE + GUIDE

### 建立 index 文件範例
```
write(
  collection="documents",
  data={
    "doc_id": "INDEX-product-docs",
    "title": "產品文件集",
    "type": "REFERENCE",
    "doc_role": "index",
    "ontology_entity": "產品知識",
    "source": [
      {"uri": "docs/specs/SPEC-pricing.md", "type": "github", "doc_type": "SPEC"},
      {"uri": "docs/design/DESIGN-pricing-impl.md", "type": "github", "doc_type": "DESIGN"},
      {"uri": "https://docs.google.com/...", "type": "google_drive", "doc_type": "REPORT"}
    ]
  }
)
```

### single → index 升級流程
觸發條件：single 文件累積 3+ sources 且涵蓋 2+ 不同 doc_type
```
write(collection="documents", data={
    "doc_id": "existing-doc-id",
    "doc_role": "index"
})
```

### Dashboard 顯示
- single 文件：平面 source 列表，每個 source 顯示平台圖標 + 狀態
- index 文件：按 doc_type 分組顯示 sources（SPEC 區、DESIGN 區、TEST 區...）

## Capture/Sync 路由決策樹

```
收到一份文件
    ↓
1. search(collection="documents", query="文件主題") 查重
    ↓
2a. 找到既有 document entity
    → 加為新 source：write(data={"doc_id": "...", "source": {"uri": "...", "type": "github"}})
    → 檢查：sources 3+ && doc_types 2+ → 建議升級 doc_role 為 index
    ↓
2b. 無既有 entity
    → 判斷類別（11 類 + legacy 別名自動轉換）
    → write(collection="documents", data={...}) 建新 entity
    ↓
3. 檔案已刪除/改名？
    → stale：暫時不可達
    → unresolvable：確認已永久刪除
    → 唯一 source 且 unresolvable → 文件 status 改為 archived
```

## Supersede 操作步驟（完整流程）

情境：DECISION-007 取代了 DECISION-003

Step 1：在文件系統建立新文件，frontmatter 加 supersedes
Step 2：在 ZenOS 建 document entity（原子取代）：
```
write(
  collection="documents",
  data={
    "doc_id": "DECISION-entity-architecture",
    "title": "決策紀錄：Entity 三層模型",
    "type": "DECISION",
    "ontology_entity": "知識節點架構",
    "status": "approved",
    "source": {"uri": "docs/decisions/DECISION-entity-architecture.md"},
    "supersedes": "DECISION-entity-flat-model"
  }
)
```
Server 自動將舊文件 status 標為 superseded。

Step 3：（可選）手動更新舊文件 entity：
```
write(
  collection="documents",
  data={
    "doc_id": "DECISION-entity-flat-model",
    "status": "superseded",
    "superseded_by": "DECISION-entity-architecture"
  }
)
```
Step 4：建立 relationship：
```
write(
  collection="relationships",
  data={
    "source_entity_id": "{新文件 entity ID}",
    "target_entity_id": "{舊文件 entity ID}",
    "type": "supersedes"
  }
)
```

## 從 git log 同步 document 狀態的流程

```
1. git log --name-only --since="30 days ago" -- "docs/**/*.md"
   → 找出最近 30 天修改的文件

2. 對每個修改的文件：
   a. 讀取 frontmatter 取得 doc_id 和 type
   b. search(collection="documents", query=doc_id, product_id=PRODUCT_ID) 找對應 entity
   c. 比對：
      - git 有修改 + ZenOS status=draft → 建議 under_review
      - git 有新文件 + ZenOS 無 entity → 建議建立 entity
      - git 文件已刪除 + ZenOS status=approved → 建議 archived

3. batch write 更新
```

## 寫文件前必做：查重

```python
# 必須帶 product_id，避免跨產品誤判
search(collection="documents", query="主題關鍵字", product_id=PRODUCT_ID)
# + glob docs/ 下同前綴同主題的檔案
```

找到既有文件 → 讀 frontmatter 確認 status：
- `Draft / Under Review` → 直接更新
- `Approved` → 判斷變更性質：實作對齊（可直接更新）vs 決策改向（開新文件 + supersede）
- `Superseded / Archived` → 必須開新文件

**禁止未查重就直接建新文件。**

## Archive / Delete 規則

**封存到 `archive/`（保留追溯）：**
- 被新版文件取代的舊文件（標 `status: Superseded`）
- 已驗收完成但需追溯的 handoff 文件

**可直接刪除（無追溯價值）：**
- `*_SUMMARY.md`、`*_FIX_*.md`、`*_REPORT.md` 等 AI 工作產物
- 暫存稿、備份檔、可由其他系統重建的產出物

**封存前必須確認：**
- ZenOS ontology 已持有該文件的知識（未持有 → 先 capture，再 archive）
- 更新 frontmatter `status` + 對應 L3 entity

## 常見陷阱

陷阱 1：把 L2 entity 的 summary 當 document
→ summary 是概念描述，不是文件。文件必須有 source.uri。

陷阱 2：不設 ontology_entity
→ 每份文件都是某個 L2 概念的具體化。找不到 L2？先建 L2 再掛文件。
→ 例外：REFERENCE 的 ontology_entity 可為 null。

陷阱 3：supersede 時刪除舊文件
→ 不刪除，改 status=superseded。歷史決策需要可追溯。

陷阱 4：用舊類別名稱建立文件
→ 可以用（ADR/TD/TC/PB/REF），server 會自動轉換。但建議直接用新類別名稱。

陷阱 5：index 文件不設 doc_type
→ index 文件的每個 source 應設 doc_type，讓 Dashboard 能正確分組顯示。

## Source 稽核規則

### source.label 規範

- **必須是實際檔名**，例如 `SPEC-agent-system.md`、`DECISION-entity-architecture.md`
- **不可只寫 type**：`"github"` 是無意義的 label，Dashboard 顯示時毫無資訊量
- 若 label 為空或等於 type 名稱（如 "github"），視為 `bad_label`，應從 URI 尾段提取正確檔名

提取規則：取 URI 最後一個 `/` 之後的部分作為 label。
- `https://github.com/org/repo/blob/main/docs/SPEC-pricing.md` → `SPEC-pricing.md`
- `github:docs/DECISION-entity-architecture.md` → `DECISION-entity-architecture.md`

### source.uri 規範

- 必須指向**有效的檔案位置**，不可指向已刪除或已改名的路徑
- 對 `type=github` 的 source，可用 `git ls-files` 驗證路徑是否存在
- 若檔案已改名，應更新 URI 為新路徑（可用 `git log --follow --diff-filter=R` 追蹤）
- 若檔案已刪除且無改名記錄，應**標記為 broken 並等用戶確認後才移除**（不同裝置的本地 repo 狀態可能不同，見 ADR-016）；若用戶確認刪除且為文件的唯一 source，將文件 status 改為 `archived`

### source_status 欄位

- **valid**（預設）：source 可正常存取
- **stale**：source 可能過時（偵測到但尚未確認）
- **unresolvable**：source 確認不可達（已刪除、連結失效）

### 稽核觸發時機

每次執行 `/zenos-sync` 時，**Step 0: Source Audit 預設自動執行**，在正式增量同步前先完成 source 連結的清理。

若只想執行稽核而不做增量同步，使用 `/zenos-sync --audit`。
