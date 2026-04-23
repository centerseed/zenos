---
type: SPEC
id: SPEC-doc-governance
status: Under Review
ontology_entity: l3-document
created: 2026-03-26
updated: 2026-04-23
depends_on: SPEC-ontology-architecture v2 §8.1, SPEC-identity-and-access, SPEC-governance-framework
canonical_schema_from: SPEC-ontology-architecture v2 §8.1
absorbs:
  - SPEC-document-bundle (doc_role, sources[], bundle_highlights, change_summary, source platform contract, rollout matrix)
  - SPEC-doc-source-governance (已為 redirect stub)
---

# Feature Spec: ZenOS L3-Document Governance

> **Layering note**：本 SPEC 只管 L3-Document subclass 的**治理規則**。
> schema（`entity_l3_document` DDL、Python dataclass、CHECK constraint）canonical 在 `SPEC-ontology-architecture v2 §8.1`。
> 權限 / visibility canonical 在 `SPEC-identity-and-access`。六維治理表 canonical 在 `SPEC-governance-framework`。
>
> **SSOT 傳遞（ADR-038）**：Agent runtime 透過 `governance_guide(topic="document", level=2)` 取得治理規則。本 SPEC 是人讀權威；`skills/governance/document-governance.md` 為 reference-only。SPEC 修訂必須同步 `src/zenos/interface/governance_rules.py["document"]`，否則不得轉 `Approved`。

## 1. 定位與範圍

L3-Document 是**文件的語意代理**（不是檔案本體），一張 `entity_l3_document` row = 一個 bundle of sources。

**本 SPEC 適用於**：
- 專案內以 Markdown / 外部平台維護、需要被 ZenOS 納入知識治理的正式文件
- 具有審核流程、版本邊界、跨團隊或跨角色約束力的文件

**不自動適用於**：
- 程式碼註解 / docstring / README
- 一次性輸出 / demo 素材 / 純工具層設定
- 應用層自己的內部 checklist

## 2. 核心原則

1. 每份正式文件必須可被分類（`doc_type`）。
2. 每份正式文件必須可被唯一識別（`entity_id` + `source_id`）。
3. 每份正式文件必須有明確生命週期狀態（bundle 層 + source 層雙軌）。
4. 每份正式文件必須對應到 ontology 主題或明確標 `TBD`。
5. 文件穩定性 > 協作便利性；保留歷史寧可開新文件，不覆寫既有決策。
6. 專案特例必須明文記錄為 local convention，不靠口頭共識。
7. 任何影響分類 / 狀態 / 命名 / supersede / ontology 對應的修改，必須同步更新 ontology，否則視為未完成。
8. 文件治理的完成定義包含「**可被找到**」：使用者與 agent 能從對應 L2 快速找到文件入口，不是只把 metadata 寫進 ontology。

## 3. Bundle-first Document Entity

### 3.1 doc_role 語意

| doc_role | 語意 | source 數量 | 用途 |
|----------|------|------------|------|
| `index` | 某語意主題的文件索引（**預設**）| 1..N | 聚合同主題多份文件，作為 L2 的穩定文件入口 |
| `single` | 單一文件的語意代理（例外）| 1 | 文件本身是獨立治理單位，不需要聚合 |

**新建預設為 `index`**。CHECK constraint（主 SPEC §8.1）：
```sql
CHECK (doc_role = 'single' OR bundle_highlights_json != '[]')
```
→ `index` 必須有 `bundle_highlights`。

**選 `single` 的前提**（三選一）：
1. 文件有獨立生命週期，不希望與同主題文件聚合
2. 產品明確要求單獨分享 / 授權 / supersede
3. 文件不是任何 L2 的主文件入口

`single` entity 禁止新增第 2 個 source（reject with `SINGLE_CANNOT_HAVE_MULTIPLE_SOURCES`）。

### 3.2 Source 結構

每個 source 是 typed object（存在 `sources_json`）：

| 欄位 | 必填 | 說明 |
|------|------|------|
| `source_id` | 系統生成 | 穩定識別碼，per-source CRUD 用 |
| `uri` | 是 | 完整 URL |
| `type` | 系統推斷 | `github / gdrive / notion / wiki / url` |
| `label` | 是 | 人類可讀檔名 |
| `doc_type` | 建議 | 見 §5 泛用類別 |
| `doc_status` | index 建議 | `draft / approved / superseded / archived`（per-source lifecycle） |
| `source_status` | 系統管理 | `valid / stale / unresolvable`（URI 可達性） |
| `note` | 選填 | 用途說明 |
| `is_primary` | 預設 false | primary source（`read_source` 未帶 source_id 時預設讀這份）|

### 3.3 Mutation 操作

| 操作 | 語意 |
|------|------|
| `write(collection="documents", data={..., sources: [...]})` | 建立時帶完整 sources |
| `write(..., data={doc_id, add_source: {...}})` | 追加 source |
| `write(..., data={doc_id, update_source: {source_id, ...}})` | 更新特定 source |
| `write(..., data={doc_id, remove_source: {source_id}})` | 移除 source（最後一份不可移除）|
| `batch_update_sources(...)` | 批次更新 per source_id |

### 3.4 bundle_highlights & change_summary

**`bundle_highlights`**（index 必填，1..5 筆）：
```
[{source_id, headline, reason_to_read, priority: primary|important|supporting}]
```
- 必須至少一筆 `priority=primary`
- 必須引用屬於該 bundle 的 `source_id`（不得游離）

**`change_summary`**（選填，string）：一段人話，描述最近重要變化。

**`highlights_updated_at` / `summary_updated_at`**：系統管理，write 時自動覆寫。

## 4. Source Platform Contract

### 4.1 分層能力

| 層次 | 問題 |
|------|------|
| `type normalization` | 這是什麼平台？由 URI pattern 推斷 |
| `URI validation` | URI 格式合不合法？server-side 驗證 |
| `status governance` | 這個 source 現在有效嗎？由 `source_status` + dead-link policy 表達 |
| `reader adapter` | ZenOS 今天能不能真的讀到？由 `read_source(doc_id, source_id?)` 決定 |

### 4.2 Rollout 能力矩陣

| source_type | URI contract | 可掛 doc entity | status 治理 | 內容讀取 | Rollout |
|------------|-------------|---------------|-----------|---------|--------|
| `github` | `https://github.com/{owner}/{repo}/blob/{branch}/{path}` | 是 | 正式 | 正式 | Phase 1 |
| `gdrive` | `https://drive.google.com/file/d/{id}/...` 或 `https://docs.google.com/...`，含 file ID | 是 | 正式 | adapter 待補 | Phase 1.5 |
| `notion` | `https://www.notion.so/...` 含 UUID | 是 | 基本 | adapter 待補 | Later |
| `wiki` | 完整 `https://...`，禁 `/edit` | 是 | 基本 | adapter 待補 | Later |
| `url` | 完整 `https://...` | 是 | 基本 | 預設 metadata only | Later |

**規則**：
1. multi-source contract 先定案，不必等所有 adapter 完成
2. 未落地 adapter 的 `read_source` 必須回傳結構化 `unavailable` + `setup_hint`，不得偽造內容
3. `source.type` 由 server 從 URI pattern 推斷，caller 不信任

### 4.3 URI 嚴格驗證

| Type | 拒絕範例 |
|------|---------|
| `github` | 相對路徑 / tree URL / raw URL（reject 400） |
| `gdrive` | 資料夾連結 / 不含 file ID（reject 400） |
| `notion` | 不含 UUID 段（reject 400） |
| `wiki` | `/edit` 結尾（reject 400） |
| `url` | 裸字串 / 相對路徑（reject 400） |

### 4.4 read_source 合約

```
read_source(doc_id, source_id?) → {content, source_status, setup_hint?, alternative_sources?}
```

- 帶 `source_id` → 讀指定 source
- 不帶 → 讀 `is_primary=true`；無 primary → 讀第一個 `source_status=valid`
- 失敗時附 `setup_hint`（如 `"Google Drive MCP"`）+ `alternative_sources`（同 bundle 可用的其他 source）

## 5. 泛用文件類別系統（`doc_type`）

| 類別 | 名稱 | 範例 |
|------|------|------|
| `SPEC` | 規格 | 產品規格、功能需求、服務規格 |
| `DECISION` | 決策 | ADR、策略決策、採購決策 |
| `DESIGN` | 設計 | TD、視覺設計、流程設計 |
| `PLAN` | 計畫 | 行銷企劃、專案計畫 |
| `REPORT` | 報告 | 月報、事後檢討、競品分析 |
| `CONTRACT` | 合約 | 客戶合約、SLA、合作協議 |
| `GUIDE` | 指南 | Playbook、SOP、onboarding |
| `MEETING` | 會議紀錄 | 週會、kickoff |
| `REFERENCE` | 參考 | 術語表、市場研究 |
| `TEST` | 測試 | TC、QA checklist |
| `OTHER` | 其他 | 無法歸類 |

**向後相容映射**（舊 → 新）：`ADR→DECISION`、`TD→DESIGN`、`TC→TEST`、`REF→REFERENCE`、`PB→GUIDE`、`SC→依用途`。Agent 兩種都可寫，搜尋時新舊都匹配。

**治理原則**：
- `doc_type` 只表達文件性質，**不表達部門歸屬**。跨部門區隔靠 `ontology_entity` / linked L2 / product，不靠 `doc_type` 分叉
- 禁止建 `MARKETING_REPORT` / `CS_REPORT` 這類型別
- Agent 不得因 `doc_type` 相同就自動追加到同一 index；必須先確認語意主題一致

## 6. Lifecycle State Machine

> **Canonical**：`entity_l3_document` 的合法 status enum 為 `draft / current / stale / archived / conflict`（見主 SPEC v2 §11.2 + runtime `ontology_service._DOCUMENT_STATUSES`）。本節描述轉換語意。

### 6.1 Bundle 層（`entities_base.status`，L3-Document 合法值）

```
draft ──► current ──► stale ──► archived
           │            ▲          ▲
           ├── conflict ──┘        │
           └────── supersede ──────┘
```

| Status | 語意 |
|--------|------|
| `draft` | 剛建立、尚未通過品質閘（frontmatter 或 ontology 對應仍缺）|
| `current` | 現行有效的 SSOT；任何該主題的查詢應先命中這個 bundle |
| `stale` | 與 upstream 脫節（impacts 斷鏈 / 久未 review / sources 大量失效）；待 re-review 或降級 |
| `conflict` | 同主題存在多個 current，待人工裁決 |
| `archived` | 不再維護；靠 supersede 指向繼任者（terminal）|

**合法轉換**：
- `draft → current`：通過 §6.3 Approved 品質閘
- `current ↔ stale`：re-review 復活 / impacts 斷鏈降級
- `current → conflict`：同主題出現第二份 current → server 標 conflict，兩邊都進裁決待辦
- `conflict → current`：人工裁決後留一份
- `current | stale | conflict → archived`：supersede 或手動封存

**禁止**：`archived → 任何狀態`（terminal）。

> **Frontmatter status ↔ entity status 映射**：文件 frontmatter 用 `Draft / Under Review / Approved / Superseded / Archived`（§7）描述**文件審核狀態**；entity status 用 `draft / current / stale / archived / conflict` 描述**知識圖譜上的 bundle 狀態**。兩者語意不同——frontmatter 關心審核流程，entity status 關心知識可信度。映射關係：`Approved` frontmatter → `current` entity；`Superseded` → `archived`；`Draft` / `Under Review` → `draft`。

### 6.2 Source 層（per-source `doc_status`，僅 index 使用）

```
draft ──► approved ──► superseded ──► archived
```

| 轉換 | 前提 |
|------|------|
| `draft → approved` | frontmatter 齊備 + ontology_entity 非 TBD + quality gate 通過 |
| `approved → superseded` | 指向繼任 source（本 bundle 內或跨 bundle） |
| `superseded → archived` | 保存歷史；不再顯示於主入口 |

**禁止**：`approved → draft`、`archived → 任何狀態`（terminal）。

### 6.3 Approved 品質閘（source frontmatter `status=Approved` + entity status `current` 前必過）

- Frontmatter 必填欄位齊全（見 §7）
- **`ontology_entity` 必須為 ontology 存在的 slug**，禁 `TBD`
- 內容跨角色可讀（summary 通過 LLM 評分 ≥ threshold，軟規則）

### 6.4 `ontology_entity: TBD` 治理

`TBD` 僅合法於 frontmatter `status ∈ {Draft, Under Review}`；對應 entity status 停留於 `draft`。
- `status=Approved` + `ontology_entity=TBD` → reject `ONTOLOGY_ENTITY_REQUIRED_ON_APPROVED`
- entity status=`current` 需要 `ontology_entity` 為真實 slug；caller 將 draft entity 升 current 前必須先補 ontology 掛載
- TBD 文件應同步建立 backlog task（dispatch `agent:architect`）以在限期內補 ontology 掛載

## 7. Frontmatter 規格

每份 Markdown 文件 header 必填：

```yaml
---
type: SPEC | DECISION | DESIGN | PLAN | REPORT | CONTRACT | GUIDE | MEETING | REFERENCE | TEST | OTHER
id: <stable-id>          # e.g. SPEC-doc-governance / ADR-048
status: Draft | Under Review | Approved | Superseded | Archived
ontology_entity: <slug>  # 或 TBD
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

選填：`depends_on / supersedes / superseded_by / amended / owner`。

Server 端 frontmatter validator 拒絕：缺必填欄位、非法 enum 值、`status=Approved` 但 `ontology_entity=TBD`。

## 8. 命名與編號規則

| Type | 檔名格式 |
|------|---------|
| SPEC | `SPEC-{slug}.md` |
| DECISION (ADR) | `ADR-{NNN}-{slug}.md` |
| DESIGN (TD) | `TD-{slug}.md` |
| PLAN | `PLAN-{slug}.md` |
| REPORT | `REPORT-{YYYYMMDD}-{slug}.md` |
| GUIDE (PB) | `PB-{slug}.md` |
| REFERENCE (REF) | `REF-{slug}.md` |
| TEST (TC) | `TC-{slug}.md` |
| SKILL | `SKILL-{slug}.md` |

- `{slug}` = kebab-case，不含空格 / 全形
- ADR 編號遞增，不得重用
- 重大更動開新版本或 amendment；不覆寫既有 Approved 決策正文

## 9. 何時開新 vs 更新既有

### 9.1 開新文件
- 新功能 / 新決策 / 新子主題
- 需要獨立審核流程
- 需要獨立 supersede chain

### 9.2 可直接更新
- Typo / 格式 / 補充細節，不改變 AC 或決策
- Frontmatter `updated` 要跟著改

### 9.3 必須開新版或 amendment
- 推翻既有 AC / 決策結論
- 擴充新 P0 需求
- 任何影響外部依賴的 contract 改動

### 9.4 不可直接改寫正文
- `status=Approved` 文件的核心章節
- 任何被其他文件 `depends_on` 引用的結論

## 10. Capture / Sync 路由決策

```
新文件
  │
  ├─ Step 1：search(collection="documents", query=<主題關鍵字>)
  │
  ├─ 找到 index entity？ → add_source 到該 index
  │
  ├─ 找到 single entity 且新文件高度相關？
  │    → 提議升級 single → index（需 confirm）
  │
  ├─ 無相關 doc entity？
  │    ├─ 屬 L2 正式產出？ → 建新 doc entity（預設 index）
  │    └─ L2 輕量參考？ → 掛到 L2 的 sources[]（不建 L3）
  │
  └─ 不確定 → 停止，回報用戶
```

### 10.1 L2 sources[] vs L3 doc entity 邊界

| 層級 | 標準 | 正例 | 反例 |
|------|------|------|------|
| **L2 sources[]** | 輕量參考；移除不影響 L2 語意 | 原始碼路徑、外部 API doc、設定檔 | 客戶合約、產品規格 |
| **L3 single** | 一份正式文件語意代理；獨立生命週期 | 單份 SPEC / ADR / 合約 | README |
| **L3 index** | 多份正式文件的語意索引；聚合展示 | 「訂閱管理文件集」、「客戶 X 交付文件集」 | 只有一份且短期不會增加（應用 single）|

### 10.2 正式產出定義

具以下任一特徵：
1. 走審核流程（Draft → Under Review → Approved）
2. 有版本邊界（v1 → v2）
3. 有法律 / 商業 / 跨團隊約束力
4. 被其他文件 / 任務引用為依據

## 11. Supersede 規則

```
write(collection="documents", data={
  id: <new-doc-id>,
  supersedes: <old-doc-id>,        # bundle-level supersede
  supersedes_reason: "..."
})
```

Server 原子操作：
1. 新 doc entity 建立
2. 舊 doc entity status → `archived`
3. 舊 entity 寫入 `superseded_by = <new-id>`
4. 圖上建立 `relationships.type = "supersede"` edge

Per-source supersede 則透過 `update_source` 設定 `doc_status=superseded` + `supersedes_source_id`。

## 12. Archive 與刪除

### 12.1 應 archive 到 `archive/`
- `status=Superseded` 文件，等 supersede chain 穩定 ≥ 30 天
- 專案方向轉變後的舊計畫
- 歷史 decision（仍有回溯價值）

### 12.2 可直接刪除
- 暫存分析結果（未轉 Approved）
- handoff 摘要 / 備份 / 一次性輸出
- 從未掛 ontology 的 draft

### 12.3 封存前必須滿足
- `status = Superseded` 或 `Archived`
- supersede chain 明確（如有繼任者）
- ontology 同步完成（`superseded_by` 寫回、`archived_at` timestamp）

## 13. Agent 合規流程

### 13.1 強制動作序列

1. **capture 前 search**：
   ```
   search(collection="documents", query=<主題>, status="current")
   ```
2. **有 bundle → `add_source`**；無 bundle → 建 `index`（預設）
3. **寫 frontmatter**：`type / id / status / ontology_entity / created / updated`
4. **掛 ontology**：L2 or L3 `linked_entities`，不確定就標 `TBD` + 建 backlog task
5. **寫 bundle_highlights**（若 doc_role=index）
6. **sync journal**：`journal_write` 一行描述動作

### 13.2 禁止

- 不做 search 直接建新 entity（導致重複）
- `doc_role=single` 未說明例外理由
- `status=Approved` 但 `ontology_entity=TBD`
- 寫 frontmatter 但檔名與 `id` 不一致

## 14. 合規違規偵測

| Signal | Detector（runtime canonical） |
|--------|---------|
| `index` 無 highlights | `analyze(check_type="health")` → `kpis.bundle_highlights_coverage`（`analyze.py:717`）|
| primary source = stale / unresolvable | `analyze(check_type="document_consistency")` → `document_consistency_warnings`（`analyze.py:606-620`）+ `read_source` dead-link |
| `change_summary` 超過 90 天未更新且 sources 有變動 | `analyze(check_type="staleness")` |
| 孤立 doc entity（無 relationships / 無 parent 掛載）| `find_gaps(gap_type="orphan_entities")`（`governance.py:116`）|
| doc entity 關聯薄弱（全是 `related_to`）| `find_gaps(gap_type="weak_semantics")`（`governance.py:118`）|
| Frontmatter 欄位缺漏 / `status=Approved` + `ontology_entity=TBD` | write-time validator reject（`ONTOLOGY_ENTITY_REQUIRED_ON_APPROVED`）|

> 合法 `check_type`：`all / health / quality / staleness / blindspot / impacts / document_consistency / permission_risk / invalid_documents / orphaned_relationships / llm_health / consolidate`（`analyze.py:44-48`）。
> 合法 `gap_type`：`all / orphan_entities / weak_semantics / underconnected`（`governance.py:129`）。
> 「同主題拆多個 single entity」目前無 dedicated gap_type；沿用 `find_gaps(gap_type="weak_semantics")` + 人工 routing 判斷（§10 capture/sync 路由決策樹）。

## 15. 反饋路徑 (Feedback Triggers)

Agent 偵測到以下情境必須建立 governance task（不得靜默）：

- `index` 缺 `bundle_highlights` → 建 task dispatch 到對應 owner
- `source_status=unresolvable` 持續 14+ 天 → 建 task（修 URI 或 archive）
- `doc_type=OTHER` 且被引用 3+ 次 → 建 task（分類升級）
- 同一 L2 下出現 2+ 份 SPEC single entity → 建 task（評估升 index）

反饋完整性規則：若偵測到問題但無人員認領，必須 escalate 到 L1 workspace owner。

## 16. 衝突仲裁

| 衝突類型 | 仲裁 |
|---------|------|
| 兩份文件宣稱同一 SSOT | 先到者為主；後到者必須 supersede 或合併為 source |
| frontmatter 與檔名不一致 | frontmatter 勝；更新檔名 |
| `doc_type` 與實際內容不符 | 內容勝；update `doc_type` |
| L2 sources[] 與 L3 index 都掛同一 URI | L3 勝；從 L2 移除 |
| 同 bundle 下兩份 source 都 `is_primary=true` | reject with `MULTIPLE_PRIMARY_SOURCES` |

## 17. 專案層可覆寫

- 命名前綴（如 `ADR-{NNN}-{slug}` 改為 `ADR-{slug}-{NNN}`）
- Archive 目錄結構
- `doc_type` 擴充（僅限用途互斥的新類別；不得新增部門變體）
- Lifecycle 中的 `Under Review` 子階段（如 `Under Review → Peer Review → Approved`）

**不可覆寫**：
- `doc_role` enum、CHECK constraint
- Frontmatter 必填清單
- Supersede 原子語意
- Source platform 合約

## 18. 驗收 Criteria

**Bundle & Role**：
- `AC-DOC-01` Given 建立新 doc entity 未傳 `doc_role`，When write，Then 建為 `index`
- `AC-DOC-02` Given `doc_role=index` 只傳 1 個 source，When write，Then 成功
- `AC-DOC-03` Given `doc_role=single` 未傳 reason，When write，Then warning / reject 引導改 `index`
- `AC-DOC-04` Given `single` entity 加第 2 個 source，When write，Then reject with `SINGLE_CANNOT_HAVE_MULTIPLE_SOURCES`

**Source CRUD**：
- `AC-DOC-05` Given 追加 source 到 index，When write，Then 系統生成 source_id，其他 source 不動
- `AC-DOC-06` Given 移除 index 的最後一個 source，When write，Then reject
- `AC-DOC-07` Given 兩筆 source 同時 `is_primary=true`，When write，Then reject with `MULTIPLE_PRIMARY_SOURCES`

**Bundle Highlights**：
- `AC-DOC-08` Given `doc_role=index` 無 `bundle_highlights`，When write，Then reject（對應 §8.1 CHECK）
- `AC-DOC-09` Given bundle_highlights 無 `priority=primary` 項，When write，Then reject
- `AC-DOC-10` Given bundle_highlights 引用不屬於本 bundle 的 source_id，When write，Then reject
- `AC-DOC-11` Given update bundle_highlights，When write，Then `highlights_updated_at` 自動覆寫

**URI Validation**：
- `AC-DOC-12` Given GitHub tree URL，When write，Then reject 400 提示「請提供檔案連結而非目錄」
- `AC-DOC-13` Given Google Drive 資料夾 URL，When write，Then reject 400
- `AC-DOC-14` Given Notion URL 不含 UUID，When write，Then reject 400

**read_source**：
- `AC-DOC-15` Given `read_source(doc_id)` 且有 primary，When 執行，Then 讀 primary 內容
- `AC-DOC-16` Given `read_source(doc_id)` 無 primary 有 3 個 source，When 執行，Then 讀第一個 valid
- `AC-DOC-17` Given gdrive reader adapter 未落地，When `read_source`，Then 回傳 `unavailable` + `setup_hint: "Google Drive MCP"` + `alternative_sources`

**Lifecycle & Supersede**：
- `AC-DOC-18` Given frontmatter `status=Approved` 但 `ontology_entity=TBD`，When write，Then reject with `ONTOLOGY_ENTITY_REQUIRED_ON_APPROVED`
- `AC-DOC-18b` Given entity status 由 `draft` 嘗試升 `current` 但 `ontology_entity=TBD`，When write，Then reject（同 error code）
- `AC-DOC-19` Given supersede 新建 doc，When write，Then 舊 entity status → `archived` + `superseded_by` 寫回 + relationships 建 `supersede` edge
- `AC-DOC-20` Given entity status=`archived`，When try update status → 任何值，Then reject (terminal)
- `AC-DOC-20b` Given 同主題已存在 status=`current` 的 bundle，且新 bundle 設 status=`current`，When write，Then 兩者 status → `conflict` + 自動建 backlog task 交人工裁決

**Routing & UX**：
- `AC-DOC-21` Given agent capture 新文件且已有同主題 index，When 路由判斷，Then 選 `add_source` 而非建新 entity
- `AC-DOC-22` Given L2 detail，When 顯示，Then 直接看到 bundle title + highlights + primary source
- `AC-DOC-23` Given L2 掛 2 個 doc bundles，When detail 顯示，Then 分開呈現不合併
- `AC-DOC-24` Given 知識地圖，When 顯示，Then L2 → doc bundle 有穩定 edge

**Governance Guide**：
- `AC-DOC-25` Given `governance_guide(topic="document", level=2)`，When 執行，Then 回傳包含 §3 bundle-first、§5 類別表、§10 路由決策樹

## 19. 明確不包含

- 文件版本 diff 顯示 / 編輯器 UX（屬 `SPEC-document-delivery-layer`）
- Revision snapshot 儲存（屬 `SPEC-document-delivery-layer`）
- 批次治理流程細節（屬 `SPEC-batch-doc-governance`）
- semantic retrieval / embedding（屬 `SPEC-semantic-retrieval`）
- application-specific 內部 checklist

## 20. 相關文件

- `SPEC-ontology-architecture v2 §8.1` — L3-Document schema（canonical）
- `SPEC-identity-and-access` — visibility / permission
- `SPEC-governance-framework` — 六維治理表
- `SPEC-mcp-tool-contract` — `write(documents) / read_source / batch_update_sources`
- `SPEC-document-delivery-layer` — revision / share token sidecar
- `SPEC-batch-doc-governance` — 批次治理（引用本 SPEC 為 canonical）
- `SPEC-governance-guide-contract` — `governance_guide("document")` 契約
