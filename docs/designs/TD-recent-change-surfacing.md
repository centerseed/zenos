---
type: DESIGN
id: TD-recent-change-surfacing
status: Draft
ontology_entity: MCP 介面設計
created: 2026-04-20
updated: 2026-04-20
---

# 技術設計：Recent Change Surfacing

## 調查報告

### 已讀文件（附具體發現）
- `docs/specs/SPEC-recent-change-surfacing.md` — 已有可執行 AC：`AC-RCS-01` ~ `AC-RCS-13`，可直接轉 test stubs 與任務拆分。
- `docs/specs/SPEC-document-bundle.md` — `change_summary` 已是正式欄位，server 只做 timestamp 與 suggestion，不會自動生成內容。
- `docs/specs/SPEC-governance-feedback-loop.md` — 已明確指出 capture/sync 缺少分層與回饋閉環，但尚未定義 recent changes query。
- `skills/workflows/knowledge-capture.md` — capture 會產出 documents / entries，但沒有「實質變更必寫 change_summary」硬規則。
- `skills/workflows/knowledge-sync.md` — sync 會掃 git 變更，但沒有「影響 L2 必寫 entry(type=change)」硬規則。
- `src/zenos/application/knowledge/ontology_service.py` — document write path 已支援 `change_summary` 與 `summary_updated_at`；bundle mutation 只回 suggestion。
- `src/zenos/interface/mcp/search.py` — 無 recent changes mode/tool；documents 搜尋不使用 `change_summary` 作為 primary signal。
- `src/zenos/interface/mcp/get.py` — 只支援單一 entity entries，不支援跨 product/topic recent change 彙整。
- `src/zenos/interface/mcp/journal.py` — journal 是工作日誌，不是 recent changes 聚合層。

### 搜尋但未找到
- `docs/designs/TD-*recent-change*`
- `docs/specs/SPEC-*recent-update*`
- `src/zenos/interface/mcp/*recent*`
- `src/zenos/**` 中的 `recent_updates`

### 我不確定的事
- [未確認] recent changes 最後落在新 tool 還是 `search(mode="recent_changes")`；本 TD 先選新 tool，避免污染既有 search semantics。
- [未確認] `entry(type="change")` 的 enum/validator 是否已全域允許；若未全域允許，S02 需一併補齊。
- [未確認] dashboard product feed 是否本輪一起做；本 TD 先不含 dashboard。

### 結論
可以開始設計並派工。這次不需要新 ontology layer，主要是補 workflow 規則、MCP tool contract、以及 deterministic aggregation query。

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-RCS-01 | sync 實質文件變更後 document.change_summary 非空且更新 summary_updated_at | `skills/workflows/knowledge-sync.md`, `tests/spec_compliance/test_recent_change_surfacing_ac.py` | `test_ac_rcs_01_sync_material_change_writes_change_summary` | STUB |
| AC-RCS-02 | typo / formatting change 不強制覆寫 change_summary | `skills/workflows/knowledge-sync.md`, `tests/spec_compliance/test_recent_change_surfacing_ac.py` | `test_ac_rcs_02_non_material_change_does_not_overwrite_change_summary` | STUB |
| AC-RCS-03 | bundle operation 實質變更但缺 change_summary 時 workflow 不算完成 | `skills/workflows/knowledge-sync.md`, `skills/workflows/knowledge-capture.md` | `test_ac_rcs_03_material_bundle_operation_requires_change_summary` | STUB |
| AC-RCS-04 | 影響既有 L2 的文件變更必新增 entry(type=change) | `skills/workflows/knowledge-sync.md`, `skills/workflows/knowledge-capture.md` | `test_ac_rcs_04_l2_impact_creates_change_entry` | STUB |
| AC-RCS-05 | 純 L3 敘述更新不得硬建 change entry | `skills/workflows/knowledge-sync.md`, `skills/workflows/knowledge-capture.md` | `test_ac_rcs_05_l3_only_change_does_not_create_change_entry` | STUB |
| AC-RCS-06 | change entry 不能只是複製 change_summary | `skills/workflows/knowledge-sync.md`, `skills/workflows/knowledge-capture.md` | `test_ac_rcs_06_change_entry_must_explain_impacted_concept` | STUB |
| AC-RCS-07 | recent changes 以 product + since 回傳 documents 與 change entries | `src/zenos/interface/mcp/recent_updates.py`, `src/zenos/interface/mcp/__init__.py` | `test_ac_rcs_07_recent_updates_by_product_and_since` | STUB |
| AC-RCS-08 | topic filter 後按時間排序，不是只按 semantic score | `src/zenos/interface/mcp/recent_updates.py` | `test_ac_rcs_08_recent_updates_filters_by_topic_then_sorts_by_time` | STUB |
| AC-RCS-09 | 有 recent changes 時不需先讀 journal 才能找到主要變更 | `src/zenos/interface/mcp/recent_updates.py` | `test_ac_rcs_09_recent_updates_does_not_depend_on_journal_primary` | STUB |
| AC-RCS-10 | response 每筆結果都帶 why_it_matters | `src/zenos/interface/mcp/recent_updates.py` | `test_ac_rcs_10_recent_updates_response_includes_why_it_matters` | STUB |
| AC-RCS-11 | document change 與 entity change 可同組呈現但不得重複 | `src/zenos/interface/mcp/recent_updates.py` | `test_ac_rcs_11_recent_updates_groups_document_and_entity_change` | STUB |
| AC-RCS-12 | 有 change_summary / change entry 時不得讓 journal 蓋過知識層 | `src/zenos/interface/mcp/recent_updates.py` | `test_ac_rcs_12_recent_updates_prefers_knowledge_layer_over_journal` | STUB |
| AC-RCS-13 | 只有 journal 時只能作 fallback 並標記治理缺口 | `src/zenos/interface/mcp/recent_updates.py` | `test_ac_rcs_13_journal_only_result_marked_as_governance_gap` | STUB |

## Component 架構

1. Workflow Layer
- `skills/workflows/knowledge-capture.md`
- `skills/workflows/knowledge-sync.md`
- 角色：定義何時必寫 `change_summary`、何時必寫 `entry(type="change")`

2. MCP Interface Layer
- 新增 `src/zenos/interface/mcp/recent_updates.py`
- 在 `src/zenos/interface/mcp/__init__.py` 註冊 tool
- 角色：提供正式的 recent changes query contract

3. Aggregation Logic
- Phase 1 先放在 `recent_updates.py` 內部組裝
- primary source：documents with `change_summary`
- secondary source：entries with `type="change"`
- fallback source：journal

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `recent_updates` | `product` | `str \| None` | 否 | 產品名稱；與 `product_id` 二選一，`product` 優先 |
| `recent_updates` | `product_id` | `str \| None` | 否 | 產品 entity id |
| `recent_updates` | `since_days` | `int \| None` | 否 | 近 N 天；與 `since` 二選一 |
| `recent_updates` | `since` | `str \| None` | 否 | ISO 日期或 datetime |
| `recent_updates` | `topic` | `str \| None` | 否 | 主題縮小，例如 `marketing` |
| `recent_updates` | `limit` | `int` | 否 | 預設 20 |
| `recent_updates` | `workspace_id` | `str \| None` | 否 | 多 workspace 時切換 |

## DB Schema 變更

無。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 補 workflow recent-change 寫入規則 | Developer | `knowledge-capture.md` / `knowledge-sync.md` 明確定義 material change、`change_summary` 必填條件、`entry(type="change")` 觸發規則 |
| S02 | 新增 MCP `recent_updates` tool 與 aggregation contract | Developer | 新 tool 註冊完成，支援 `product/product_id/since/since_days/topic/limit`，AC-RCS-07~13 test 轉 PASS |
| S03 | 補 spec compliance tests 與 validator gaps | Developer | `tests/spec_compliance/test_recent_change_surfacing_ac.py` 全部由 FAIL 變 PASS；若 `entry(type="change")` validator 缺口存在，一併補齊 |

## Spec Compliance Matrix

| AC 群組 | 對應任務 | 驗證 |
|--------|---------|------|
| AC-RCS-01 ~ AC-RCS-06 | S01 | workflow 規則文字 + spec compliance tests |
| AC-RCS-07 ~ AC-RCS-13 | S02, S03 | MCP tool tests + spec compliance tests |

## Done Criteria

1. `recent_updates` MCP tool 已註冊並可查詢 `product + since + topic`
2. `knowledge-capture.md` 與 `knowledge-sync.md` 對 material change / `change_summary` / `entry(type="change")` 有硬規則，不再只是 suggestion
3. `tests/spec_compliance/test_recent_change_surfacing_ac.py` 的 13 條 AC 全部從 FAIL 變 PASS
4. 若 `entry(type="change")` 目前不是全域合法 type，必須一併補齊 validator / serialization
5. 不修改 dashboard UI；本輪只交付 workflow + MCP contract + tests

## Risk Assessment

### 1. 不確定的技術點
- [未確認] `entry(type="change")` 是否需要改 domain enum / repo query filter。
- [未確認] `recent_updates` 的日期解析要不要接受自然語言；本 TD 先不做，只收 ISO / since_days。

### 2. 替代方案與選擇理由
- 方案 A：在 `search` 新增 `mode="recent_changes"`
  - 不選理由：會混進既有 search semantics，增加 backward compat 風險。
- 方案 B：新增獨立 `recent_updates` tool
  - 選擇理由：查詢意圖清楚、回傳 shape 可獨立設計、不污染既有 search contract。

### 3. 需要用戶確認的決策
- 目前無阻塞性決策。依你剛剛的指示，我直接按新 tool 路線拆工。

### 4. 最壞情況與修正成本
- 最壞情況：workflow 規則寫好了，但現有 agent 不遵守，導致只有 MCP tool 上線、資料仍舊稀疏。
- 修正成本：中。需再補 server-side governance rejection，但不影響 `recent_updates` tool 本身的查詢落地。
