---
type: ADR
id: ADR-022-document-bundle-architecture
status: Superseded
ontology_entity: l3-document
created: 2026-04-09
updated: 2026-04-23
accepted_at: 2026-04-20
superseded_by: ADR-048-grand-ontology-refactor
supersede_reason: Document bundle 決策已完整併入 SPEC-doc-governance §3（2026-04-23 吸收舊 SPEC-document-bundle）+ 主 SPEC v2 §8.1 DDL
---

> **2026-04-23 Supersede note**：本 ADR 記錄的 document bundle（doc_role / sources / bundle_highlights）決策已落地為 `SPEC-doc-governance §3` canonical + 主 SPEC v2 §8.1 schema。

# ADR-022: Document Bundle 架構

## Context

`SPEC-document-bundle` 將 L3 document entity 從「單一文件代理」擴展為「同一語意主題下的文件索引」。架構上要解決四個核心問題：

1. 同一主題的 SPEC、決策、設計、測試被拆成多個 L3 entity，知識地圖退化為文件清單。
2. 既有文件類別偏軟體開發，無法穩定覆蓋非技術文件治理。
3. `read_source`、`batch_update_sources`、`source_status` 都假設每個文件只有一個 source。
4. ZenOS 需要支援多平台 URI 與治理，但不能把「可掛 source」誤解成「今天就可讀原文」。

現有基礎條件如下：

- `documents.sources_json` 已經是 JSONB array，但 runtime 仍以 `sources[0]` 為唯一來源。
- `read_source` 目前只支援 `doc_id`，不支援指定來源。
- `source_uri_validator` 已具備 GitHub / Google Drive / Notion / Wiki 的基礎驗證能力。
- 現有文件與 agent skill 仍大量使用 `ADR`、`TD`、`TC` 等 legacy 類別，不能做破壞性切換。

因此，本 ADR 要鎖定的是「Document Bundle 的正式資料模型、MCP 契約、相容策略與 rollout 邊界」，而不是重述完整產品需求。

## Decision Drivers

- 對既有 `documents` collection 與 MCP 介面保持向後相容
- 明確區分語意索引層與內容讀取能力
- 讓 single / index 共享同一套治理與查詢入口，避免模型分叉
- 支援泛用文件類別，但不破壞既有文件與 skill
- 讓 source 可被精準識別、更新、驗證與讀取

## Decision

### D1. L3 document entity 採用 `doc_role` 雙模式，不新增第二種 collection

`Document` 保持單一 collection，新增 `doc_role`：

- `single`：單一正式文件的語意代理，為預設值
- `index`：同一語意主題下的多文件索引

原因：

- 既有 `sources_json` 已是陣列，沿用單一 collection 成本最低。
- `single` 與 `index` 共用大部分 metadata、搜尋、治理、權限與讀取路徑。
- 若另開 `document_index` collection，會讓 `search/get/write/read_source` 全部出現雙軌邏輯，屬於過度設計。

約束：

- `single` 只能有一個 source。
- `index` 可有 1..N 個 source。
- 既有未標註 `doc_role` 的文件一律視為 `single`。

### D2. Source 改為可獨立治理的正式子結構

每個 source 都必須有穩定的 `source_id`，並具備以下欄位：

- `uri`
- `type`
- `label`
- `doc_type`
- `doc_status`
- `source_status`
- `note`
- `is_primary`

`source_id` 由 server 生成 UUID，caller 不可指定。

原因：

- 沒有 `source_id` 就無法安全支援 per-source update / remove / read。
- `source_status` 與 `doc_status` 必須下沉到 source 層，否則 multi-source file set 無法治理。
- `is_primary` 提供 `read_source(doc_id)` 的向後相容預設行為。

### D3. `write(collection="documents")` 擴展 mutation 語意，不新增 MCP tool

Document source mutation 統一留在既有 `write` tool：

- `sources: [...]`：建立文件時寫入完整 sources
- `add_source: {...}`：新增 source
- `update_source: {source_id, ...}`：更新指定 source
- `remove_source: {source_id}`：移除指定 source

原因：

- 遵循既有 tool consolidation 原則。
- Agent 已熟悉 `write(collection="documents")`，只需學新的 payload key，不必增加 API surface。
- `single` / `index` 的規則差異可在同一 handler 內驗證，不需要拆成多個外部工具。

配套規則：

- `single` 新增第 2 個 source 時必須拒絕，並提示改為 `index`。
- `index` 不可移除最後一個 source。

### D4. `read_source` 升級為 `read_source(doc_id, source_id?)`

讀取規則：

- 有 `source_id`：讀指定來源
- 無 `source_id`：優先讀 `is_primary=true` 的 source
- 若沒有 primary：讀第一個 `source_status=valid` 的 source

失敗規則：

- 若 reader adapter 尚未落地，回傳結構化 `unavailable`
- response 附帶 `setup_hint`
- 若同 bundle 還有其他可讀來源，回傳 `alternative_sources`

原因：

- 這是 multi-source 模型下唯一可維持向後相容且可精準定位的介面。
- `setup_hint` 是建議性資訊，不應變成新的狀態值，避免污染 `source_status` 狀態機。

### D5. 平台能力採「穩定殼層 + 可插拔 source adapter」模型

`doc entity` 是穩定的語意殼層；平台能力由 source contract 決定。每個 source platform 至少定義：

- URI validation
- type normalization
- dead-link policy
- reader adapter
- setup hint

Rollout 邊界：

- `github`：Phase 1 正式支援治理與原文讀取
- `gdrive`：Phase 1.5 先支援 URI contract、治理、setup_hint，reader 後補
- `notion` / `wiki` / `url`：先支援 contract 與治理，不宣稱 today readable

原因：

- 避免把「可掛 URI」與「可讀內容」混在一起。
- 新平台擴充時不必重做 `doc entity` 模型，只需要補 source adapter contract。

### D6. 文件類別採泛用 canonical type，保留 legacy alias 相容

正式 canonical 類別為：

- `SPEC`
- `DECISION`
- `DESIGN`
- `PLAN`
- `REPORT`
- `CONTRACT`
- `GUIDE`
- `MEETING`
- `REFERENCE`
- `TEST`
- `OTHER`

Legacy alias 持續接受：

- `ADR -> DECISION`
- `TD -> DESIGN`
- `TC -> TEST`
- `PB -> GUIDE`
- `REF -> REFERENCE`

決策：

- 搜尋時做 alias 展開
- 讀取時保留原始 type，另提供 computed `canonical_type`
- 寫入時接受新舊類別，不做破壞性強轉

原因：

- 一次性硬切到新類別風險過高。
- 不做 alias 又會讓搜尋與治理語意斷裂。

### D7. `change_summary` 採 agent 維護，server 只做提醒與稽核

`documents` 表新增：

- `change_summary`
- `summary_updated_at`

責任分工：

- agent 在 capture / sync / source mutation 後更新摘要
- server 在 response `suggestions` 中提醒摘要可能需要更新
- analyze 對長期未更新但近期有 source 變動的文件提出 warning

原因：

- server 不應引入 LLM 自動摘要依賴
- 真正有價值的 bundle 摘要需要語境理解，應由 agent 撰寫

**2026-04-17 強化（see ADR-039）**：D7 的範圍擴及整個 bundle 主路徑，不只是 change_summary：

- `bundle_highlights` 的 `reason_to_read` 同樣由 agent 端 LLM 產生；server 的 `bundle_highlights_suggestion` 僅以 deterministic 規則（doc_type 分級 + is_primary）產出
- Server 端 write / add_source / update_source 路徑**禁止任何 LLM call**
- 任一 LLM provider（含 Gemini）故障時，document/bundle 寫入必須仍可成功
- Gemini 修復後**不對歷史 document 做 backfill**；依 D8 自然演進

### D8. 遷移採自然演進，不做一次性主動合併

既有 `single` 文件不做批次自動合併為 `index`。升級路徑如下：

1. agent 在 capture / sync 中發現第二份高度相關正式文件
2. 提議把既有 `single` 升級為 `index`
3. 保留原 source 為第一個 source，再追加新 source

原因：

- 無法可靠自動判斷哪些舊文件屬於同一 bundle
- 自然演進能避免錯誤合併與大規模 migration 風險

## Consequences

### Positive

- L3 文件不再只能表達單一檔案，知識地圖可回到「主題索引」而不是「附件清單」。
- 文件治理從軟體文件擴展為泛用商業文件治理。
- `read_source`、`batch_update_sources`、`sync`、Dashboard 都能以 `source_id` 精準處理來源。
- Source platform 能分階段 rollout，不需要等待所有 adapter 完成才能落地資料模型。

### Negative

- `write(collection="documents")` 的 payload 會變更複雜，需要明確驗證與錯誤訊息。
- single / index 共用同一模型，application layer 必須承擔更多規則分叉。
- 舊文件與舊 skill 將長期處於 alias 相容模式，短期內系統會同時看到 legacy 與 canonical 類別。

### Risks

- 若不嚴格驗證 `single` / `index` 規則，容易出現非法狀態。
- 若 Dashboard 與 API 沒有同步改為 source-aware，會出現資料模型升級但 UI/操作仍只看第一個 source 的錯誤。
- 若 governance skill 不同步更新，agent 仍會沿用單文件假設，導致 bundle 設計失效。

## Implementation Notes

本 ADR 對應的實作切片應至少包含：

1. DB migration：新增 `doc_role`、`change_summary`、`summary_updated_at`
2. Domain model：`Document` / `Source` 結構升級與 canonical type alias 定義
3. Application/service：`write`、`read_source`、`batch_update_sources` 改為 source-aware
4. Validator：GitHub / GDrive / Notion / Wiki / Generic URL contract 與錯誤訊息
5. Governance：`document-governance.md` 與 `governance_guide("document")` 同步更新
6. Dashboard：source 列表、doc_type 分組、source_status 呈現與外鏈打開行為

## Rollout

### Phase 1

- `doc_role`
- source-aware schema
- `read_source(doc_id, source_id?)`
- `batch_update_sources` 支援 `source_id`
- `github` 正式 reader
- canonical doc type alias

### Phase 1.5

- `gdrive` contract + setup_hint
- Dashboard bundle 顯示
- governance skill 更新完成

### Later

- `notion` / `wiki` / `url` reader adapter
- 進一步的 bundle 去重與可視化優化

## Follow-up

- `SPEC-doc-governance` 需補 amendment，說明 L3 新增 `index` 子類型
- `SPEC-doc-source-governance` 的有效內容由 `SPEC-document-bundle` 吸收後應降為導向文件或明確標示被吸收
- `document-governance.md` 必須改用 canonical 類別與 bundle routing 規則
