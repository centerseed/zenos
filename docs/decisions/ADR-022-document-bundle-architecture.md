---
doc_id: ADR-022-document-bundle-architecture
title: 架構決策：Document Bundle — L3 文件節點升級為語意文件索引
type: ADR
ontology_entity: L3 文件治理
status: Draft
version: "1.1"
date: 2026-04-09
supersedes: null
---

# ADR-022: Document Bundle — L3 文件節點升級為語意文件索引

## Context

### 問題

ZenOS 的 L3 document entity 目前是「一份外部文件的語意代理」——每個 entity 持有一個 `Source` 物件（type + uri + adapter），儲存為 `sources_json` JSONB 陣列（已是陣列結構，但 runtime 只使用 `sources[0]`）。

這個一對一模型在實際治理中暴露兩個根本問題：

1. **碎片化**：同一語意主題（如「訂閱管理」）的 SPEC、ADR、TD 被迫建成 3 個獨立 L3 entity，L2 底下掛滿碎片節點，知識地圖退化為文件清單。
2. **文件類別偏軟體**：現有 `doc_type`（SPEC / ADR / TD / TC / REF / PB / SC）圍繞軟體開發設計，非技術用戶（行銷、業務、客服）的文件無法被語意分類。

此外，`source_status`（valid / stale / unresolvable）目前掛在 entity 層級（`update_source_status` 更新 `sources[0].status`），當 entity 升級為多 source 時，必須下沉到每個 source 獨立追蹤。

SPEC-document-bundle 已完成 PM 四輪討論和 code review，定義了完整需求。本 ADR 記錄架構層面的關鍵決策。

### 現有基礎設施

| 元件 | 位置 | 現狀 |
|------|------|------|
| `Document` dataclass | `domain/models.py:254` | `source: Source`（單一物件） |
| `Source` dataclass | `domain/models.py:233` | `type + uri + adapter`，無 `source_id` |
| `sources_json` JSONB | `infrastructure/sql_repo.py` | 已是陣列，但 runtime 只讀 `[0]` |
| `update_source_status()` | `sql_repo.py:310` | hardcoded `sources_json[0].status` |
| `batch_update_source_uris()` | `sql_repo.py:327` | hardcoded `sources[0].uri` |
| `validate_source_uri()` | `domain/source_uri_validator.py` | GitHub / Notion / GDrive / Wiki 格式驗證，已存在 |
| `read_source` | `application/source_service.py` | 只讀第一個 source，無 `source_id` 參數 |
| `DocumentStatus` enum | `domain/models.py:56` | entity 層級狀態 |

### 與既有 Spec / ADR 的關係

| 文件 | 關係 |
|------|------|
| **SPEC-doc-governance (Approved)** | 定義每份正式文件的分類/識別/生命週期。本 ADR 不修改該 spec，但新增 index 子類型使 L3 語意從「一份文件」擴展為「一組文件的索引」。需補 amendment。 |
| **SPEC-doc-source-governance (Draft)** | 定義 source_uri 格式驗證和 source_status。本 ADR 將 source_status 下沉到 per-source 層級，需更新該 spec。 |
| **SPEC-document-bundle (Draft)** | 本 ADR 的需求來源。定義了 9 個 P0 + 3 個 P1 + 3 個 P2 需求。 |
| **ADR-013 分散治理** | Document Bundle 的驗證（URI reject、doc_type 映射）遵循 ADR-013 的 server-side 執法原則。 |

---

## Options Considered

### 決策 1：如何表達「一個語意主題聚合多份文件」

**Option A：L3 entity 引入 doc_role（single / index）**

在 Document entity 新增 `doc_role` 欄位。`single` = 現有行為（一個 source），`index` = 聚合多個 source。每個 source 帶獨立 `source_id`（UUID），支援 per-source CRUD。

- 優點：DB schema 變更最小（`sources_json` 已是 JSONB array），向後相容（未指定預設 single），語意清晰
- 缺點：同一張表承載兩種語意角色，需要在業務邏輯中分叉處理（single 拒絕加第 2 個 source）

**Option B：新增 L3-index entity type，與現有 L3-document 並存**

建立新的 entity type `document_index`，與 `document` 是不同的 collection。

- 優點：模型乾淨，不需要 doc_role 分叉
- 缺點：搜尋需要跨 collection 合併；已有的 `write` / `search` / `get` / `read_source` 全部要適配新 collection；migration 複雜度高；index 和 single 本質上共享 90% 的行為（相同的 metadata、相同的治理流程），分成兩個 type 是過度設計

**Option C：用 L2 entity 的 sources[] 聚合文件，不動 L3**

利用 L2 entity 已有的 `sources` 欄位來聚合文件連結。

- 優點：不需要 schema 變更
- 缺點：L2 sources 是「輕量參考連結」，不具備 per-source 生命週期追蹤（draft/approved/superseded）、不具備 doc_type 分類、不具備 source_status 追蹤。這等於把需要治理的正式文件降級成附件。

### 決策 2：doc_type 擴展策略

**Option A：新增 11 種泛用類別 + 舊類別向後相容映射**

Server-side 維護映射表（ADR→DECISION、TD→DESIGN 等）。搜尋時透明展開。寫入時新舊都接受。

- 優點：向後相容零斷裂，非技術用戶可用 PLAN/CONTRACT/MEETING 等直覺類別
- 缺點：server 需維護映射邏輯；SC 的映射需要 agent 判斷（依用途可映射為 REFERENCE/TEST/SPEC）

**Option B：強制遷移到新類別，不做向後相容**

一次性 migration 把所有舊 doc_type 改成新類別。

- 優點：程式碼不需要映射層
- 缺點：breaking change。已部署的 agent skill、現有 governance guide、所有 document frontmatter 需要一次性更新。風險高。

**Option C：只新增類別，不做映射**

ADR、TD 等舊類別和 DECISION、DESIGN 新類別並存，不做映射。

- 優點：實作最簡單
- 缺點：搜 DECISION 找不到 ADR，搜 ADR 找不到 DECISION。用戶困惑，語意斷裂。

### 決策 3：change_summary 的更新責任

**Option A：Agent 手動更新，server 在 mutation 時 suggestion 提醒**

`add_source` / `update_source` / `remove_source` 操作完成後，response 的 `suggestions` 欄位提醒 agent 更新 `change_summary`。

- 優點：agent 寫的摘要品質遠高於自動生成；server 不需要 LLM 依賴；suggestion 機制已存在（治理 hints）
- 缺點：agent 可能忽略 suggestion，導致 change_summary 過時

**Option B：Server 自動生成 change_summary**

每次 source 變更時，server 根據操作類型自動更新。

- 優點：永遠保持最新
- 缺點：自動生成的摘要品質低（只能寫「新增了一個 source」）；若要高品質需引入 LLM 依賴，增加 server 複雜度和成本；違反 ZenOS「server 不做 AI 推論」的原則

### 決策 4：Source 結構中 source_id 的生成策略

**Option A：Server-side UUID 生成**

寫入時 server 自動生成 `source_id`（UUID v4），caller 不可指定。

- 優點：保證唯一性、格式一致、caller 不需要關心 ID 生成
- 缺點：caller 在同一次操作中不知道新 source 的 ID（需要從 response 取回）

**Option B：Caller 指定 source_id**

允許 caller 傳入自訂 source_id。

- 優點：caller 可以預先知道 ID
- 缺點：需要處理衝突、格式不一致、空值等邊界情況

### 決策 5：write mutation 操作語意

**Option A：在現有 write tool 上擴展 add_source / update_source / remove_source 語意**

通過 `data` 物件中的不同 key 區分操作意圖。

- 優點：不增加 MCP tool 數量，agent 不需要學新 tool
- 缺點：write 的 data schema 變複雜，需要在同一個 handler 中分流多種操作

**Option B：新增獨立的 MCP tools（add_doc_source / update_doc_source / remove_doc_source）**

每個操作一個 tool。

- 優點：每個 tool 介面乾淨
- 缺點：違反 ADR-005 的 tool consolidation 原則（減少 tool 數量）；agent 需要多記 3 個 tool

---

## Decision

### D1：採用 doc_role（single / index）擴展 L3 entity（Option 1A）

在 `Document` model 新增 `doc_role` 欄位（enum: `single` | `index`，預設 `single`）。

實作要點：
- DB：`documents` 表新增三個欄位，需要 DDL migration：
  - `doc_role` enum（`single` | `index`），預設 `single`
  - `change_summary` text，選填
  - `summary_updated_at` timestamp，系統管理
- Domain：`Source` dataclass 擴展為帶 `source_id`（UUID）、`label`、`doc_type`、`doc_status`、`source_status`、`note`、`is_primary` 的結構。
- Application：`write` handler 在 `doc_role=single` 時拒絕新增第 2 個 source。`doc_role=index` 時允許 1..N 個 source。
- 向後相容：`doc_role` 未指定時預設 `single`。現有 `sources_json` 中只有一個 source 的 entity 自動視為 single。

選擇理由：DB 已是 JSONB array，改動最小。L3 document 的核心行為（metadata、治理流程、搜尋、read_source）在 single 和 index 之間共享度 >90%，拆成兩個 entity type 是 YAGNI。doc_role、change_summary、summary_updated_at 作為正式欄位放在 documents 表（而非塞進 JSONB），確保可索引、可查詢、與 SPEC 對齊。

### D2：11 種泛用類別 + 向後相容映射（Option 2A）

Server-side 維護映射表：

```python
DOC_TYPE_ALIASES = {
    "ADR": "DECISION",
    "TD": "DESIGN",
    "TC": "TEST",
    "PB": "GUIDE",
    "REF": "REFERENCE",
}
```

規則：
- **寫入**：新舊類別都接受。server 原樣存儲（寫什麼存什麼）。不做寫入時的自動轉換。
- **搜尋**：query 為 `ADR` 時，server 透明展開為同時匹配 `ADR` 和 `DECISION`，反之亦然。映射表用於搜尋展開，不用於存儲轉換。
- **讀取**：回傳 original type（寫什麼回什麼），避免與檔案 frontmatter 產生假差異。額外提供 `canonical_type` computed field，供需要統一分類的場景使用（如 Dashboard 分組、統計報表）。
- **SC 處理**：SC 作為 legacy type 被接受，server 原樣存儲（不自動轉換）。Agent 根據 governance skill 的指引，在寫入時自行選擇正確的新類別（依用途判斷：場景描述→REFERENCE、驗收場景→TEST、需求場景→SPEC）。搜尋時 SC 不做自動展開（因為沒有固定映射目標）。
- **未知類別**：寫入時回傳 warning 建議使用 `OTHER`，但不拒絕。

映射表放在 `domain/` 層（純資料，無 IO），供 `search` handler 做搜尋展開，以及 `canonical_type` 計算使用。

**canonical_type 規則：**
- 有映射的舊類別（ADR→DECISION 等）：`canonical_type` = 映射後的新類別
- 新類別或無映射的類別：`canonical_type` = 原始 type
- SC：`canonical_type` = 原始值 `SC`（因為沒有固定映射目標）
- `canonical_type` 是 read-only computed field，不可寫入

### D3：Agent 手動更新 change_summary，server suggestion 提醒（Option 3A）

- `change_summary`（string, optional）和 `summary_updated_at`（datetime, 系統管理）已在 D1 的 DDL migration 中新增到 `documents` 表。Domain model 對應新增這兩個欄位。
- `write` handler 在執行 `add_source` / `update_source` / `remove_source` 後，response 的 `suggestions` 欄位附帶 `"change_summary 可能需要更新"`。
- `analyze` tool 在 `summary_updated_at` 超過 90 天且 entity 有近期 source 變動時，回傳 warning。

選擇理由：Agent 寫的摘要品質遠高於模板字串。Server 不引入 LLM 依賴，符合「智慧邏輯只放 server 端」但「server 不做 AI 推論」的平衡。

### D4：Server-side UUID 生成 source_id（Option 4A）

- `source_id` = UUID v4，server 在 `write` 時自動生成。
- Caller 不可指定 `source_id`（傳入則忽略）。
- `write` response 回傳完整的 sources 陣列（含新生成的 source_id），caller 從 response 取得。

選擇理由：保證唯一性和格式一致。Source ID 只在後續的 update/remove/read_source 操作中使用，不需要 caller 預知。

### D5：在 write tool 上擴展操作語意（Option 5A）

操作語意通過 `data` 物件中的 key 區分：

| data key | 操作 | 適用 doc_role |
|----------|------|--------------|
| `sources: [...]` | 建立時傳入完整 sources | single / index |
| `add_source: {...}` | 追加 source | index only |
| `update_source: {source_id, ...}` | 更新特定 source | single / index |
| `remove_source: {source_id}` | 移除 source | index only（且不可移除最後一個） |

選擇理由：遵循 ADR-005 tool consolidation 原則。Agent 已熟悉 `write(collection="documents", data={...})` 的介面，只是 data schema 新增操作 key。

### D5.1：batch_update_sources 升級為 per-source 操作

現有 `batch_update_sources` 假設每個 doc entity 只有一個 source（by doc_id + new_uri）。升級為支援 `source_id` 定位。

**新 payload schema：**

```python
# 新格式：by source_id（推薦）
batch_update_sources([
    {"doc_id": "xxx", "source_id": "yyy", "new_uri": "https://..."},
    {"doc_id": "xxx", "source_id": "zzz", "new_uri": "https://..."},
])

# 舊格式：by doc_id（向後相容）
batch_update_sources([
    {"doc_id": "xxx", "new_uri": "https://..."},
])
```

**向後相容策略：**
- 舊 payload（`doc_id` + `new_uri`，無 `source_id`）仍然有效：自動更新 `is_primary=true` 的 source；若無 primary 則更新第一個 source。這等同於現有行為。
- 新 payload（`doc_id` + `source_id` + `new_uri`）精確定位到指定 source。
- 兩種格式可以在同一批次中混用。
- `source_id` 不存在時回傳 404 錯誤，該筆操作跳過，其餘繼續。

**遷移路徑：**
1. Phase 1：infrastructure 層 `batch_update_source_uris()` 支援新舊兩種 payload。
2. Phase 2：governance skill 和 sync 工具優先切換到新格式（by source_id）。
3. 舊格式長期保留，不設 deprecation 期限（single doc entity 使用舊格式完全合理）。

### D6：read_source 新增可選 source_id 參數

- 簽名：`read_source(doc_id, source_id?)`
- 無 source_id：讀取 `is_primary=true` 的 source；無 primary 則讀取第一個 `source_status=valid` 的 source。
- 失敗時：response 附帶 `setup_hint`（MCP server 名稱建議）和 `alternative_sources`（同 bundle 內其他可用 source 的 source_id + label）。
- 不引入新的 source_status 值，沿用 valid / stale / unresolvable。

**邊界規則：**

| 情境 | 行為 |
|------|------|
| `source_id` 不存在（傳入的 ID 在該 entity 中找不到） | 回傳 404，錯誤訊息：`"source_id not found in this document"`。附帶該 entity 所有 source 的 `source_id` + `label` 清單供 caller 選擇。 |
| entity 沒有任何 `source_status=valid` 的 source | 回傳最後一個 stale source 的資訊（uri、type、source_status）+ `setup_hint` + 所有 source 的 status 清單。不回傳空結果——即使全部 stale，caller 仍需要知道有哪些 source 以及如何修復。 |
| `doc_role=single` 且未傳 `source_id` | 正常行為：讀取唯一的 source（等同 primary）。source_id 可省略。 |
| `doc_role=single` 且傳了 `source_id` | 接受：若 match 唯一 source 則正常讀取；若不 match 則回傳 404（同上述「source_id 不存在」規則）。single 模式不存在「非 primary」的問題，因為只有一個 source。 |

### D7：URI 嚴格驗證擴展

現有 `validate_source_uri()` 已覆蓋 GitHub / Notion / GDrive / Wiki。本次強化：
- GitHub：reject tree URL 和 raw URL（現有只檢查 blob 格式）。
- GDrive：reject 純資料夾連結（folder URL）。
- 全部為 server-side reject（遵循 ADR-013 分散治理的 server 執法原則）。

---

## Implementation Plan

### Phase 1：Domain + Infrastructure（向後相容，需 DDL migration）

1. **DDL Migration**：`documents` 表新增三個欄位：
   - `doc_role` enum（`single` | `index`），預設 `single`
   - `change_summary` text，nullable
   - `summary_updated_at` timestamp，nullable
2. 擴展 `Source` dataclass：新增 `source_id`、`label`、`doc_type`、`doc_status`、`source_status`、`note`、`is_primary` 欄位
3. 新增 `doc_role`、`change_summary`、`summary_updated_at` 到 Document domain model
4. 新增 `DOC_TYPE_ALIASES` 映射表到 `domain/`（用於搜尋展開和 `canonical_type` 計算，不用於存儲轉換）
5. 擴展 `validate_source_uri()`：tree URL / raw URL / folder URL reject
6. 擴展 `sql_repo.py`：`update_source_status` 和 `batch_update_source_uris` 改為 per-source（by source_id），`batch_update_source_uris` 支援新舊兩種 payload 格式（見 D5.1）

### Phase 2：Application Layer

1. `write` handler 擴展：add_source / update_source / remove_source 操作
2. `write` handler 加入 doc_role 守衛（single 不可加第 2 個 source）
3. `write` handler 加入 doc_type 映射邏輯
4. `read_source` 加入 source_id 參數、primary fallback、setup_hint
5. `search` handler 加入 doc_type 透明展開
6. `analyze` 加入 change_summary 過時偵測

### Phase 3：Interface + Dashboard

1. MCP tool schema 更新（read_source 新增 source_id 參數）
2. governance_guide("document") 回傳更新（泛用類別 + 路由決策樹）
3. Dashboard doc entity 詳情頁：source 列表、平台圖標、status 標記

### Phase 4：Governance Skill + Spec 同步

1. 更新 document-governance skill（泛用類別 + 路由決策樹）
2. SPEC-doc-governance 補 amendment（L3 新增 index 子類型）
3. SPEC-doc-source-governance 更新（source_status 移到 per-source）

---

## Consequences

### 正面

- **知識地圖品質提升**：同主題文件聚合為一個 entity，L2 底下的 L3 節點數量大幅減少，知識地圖從「文件清單」恢復為「語意索引」
- **非技術用戶可用**：行銷企劃用 PLAN、客戶合約用 CONTRACT、會議紀錄用 MEETING，文件類別終於涵蓋非軟體場景
- **per-source 治理**：每個 source 獨立追蹤 status 和 doc_type，一個 source 掛了不影響整個 entity 的可用性
- **向後相容**：未指定 doc_role 預設 single，舊 doc_type 繼續被接受且原樣存儲（不自動轉換），read_source 不帶 source_id 仍可用，batch_update_sources 舊 payload 仍有效。需要 DDL migration（新增三個欄位），但不改變現有資料語意。
- **MCP 聯邦引導**：read_source 失敗時 setup_hint 引導 agent 設定外部 MCP，而非靜默失敗

### 負面

- **write handler 複雜度增加**：同一個 handler 需要分流建立 / add_source / update_source / remove_source 四種操作，需要嚴格的 validation 防止錯誤組合
- **doc_type 映射維護成本**：新舊類別並存的過渡期，搜尋需要處理映射展開邏輯，展示需要計算 canonical_type。但因為存儲保留原始值，不存在 frontmatter 假差異問題。預計 2-3 個 release cycle 後可以開始收斂
- **change_summary 依賴 agent 紀律**：server 只能提醒，不能強制。若 agent 持續忽略 suggestion，change_summary 會過時。mitigation：analyze 會偵測並報 warning
- **Source dataclass 欄位膨脹**：從 3 個欄位（type/uri/adapter）擴展到 10 個欄位。但這反映了 source 從「連結」升級為「可獨立治理的文件代理」的語意轉變，是必要的複雜度

### 風險

- **single→index 升級的原子性**：升級時需要同時修改 doc_role 和 sources，若中間失敗可能留下不一致狀態。mitigation：整個操作在同一個 DB transaction 內。
- **SC 映射的模糊性**：SC 沒有固定映射目標，依賴 agent 在寫入時根據用途自行選擇正確類別。mitigation：governance skill 提供明確的判斷指引（場景描述→REFERENCE、驗收場景→TEST、需求場景→SPEC）；server 原樣存儲 SC，不做自動轉換，避免錯誤映射。
