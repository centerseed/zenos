---
type: PLAN
id: PLAN-ontology-grand-refactor-wave9-migration
status: Draft
owner: architect
project: zenos
created: 2026-04-23
updated: 2026-04-23
depends_on:
  - ADR-048-grand-ontology-refactor
  - SPEC-ontology-architecture v2
  - SPEC-task-governance
  - SPEC-doc-governance
related_plans:
  - PLAN-data-model-consolidation  # Document → Entity + Protocol 收斂，互補但不重疊
---

# PLAN: Ontology Grand Refactor — Wave 9 Code + Migration

## Goal

把 Wave 1-8 收斂的 canonical SPEC（主 SPEC v2 §9 + `SPEC-task-governance`）從「spec-level target」真正落地到 runtime，讓 `zenos.tasks` / `zenos.plans` / `task_entities` 等遺留結構收掉，L3-Action 進入 MTI subclass table 體系。

落地後可以把這批 ADR 正式關掉：
- ADR-028（Plan primitive）
- ADR-044（Task ownership SSOT → product_id）
- ADR-047（L1 level SSOT）

## Scope

**In scope**（本 PLAN 處理）：
- L3-Action MTI 結構（`entities_base` + `entity_l3_milestone / plan / task / subtask` 五張 subclass table）
- Ownership tree 統一（`product_id` + `plan_id` + `parent_task_id` 三欄 → `parent_id` 單一樹 per 主 SPEC v2 §9）
- `task_entities` junction 收掉（改走 `relationships` 表）
- `task_blockers` junction 的去留決定（依 Phase A 調查結果）
- Wave 9 後的 SPEC / ADR / REF 後續標記（§7 Phase G）

**Out of scope**（由 `PLAN-data-model-consolidation` 承擔，不要動）：
- `Document` → `Entity` 收斂（ADR-046；該 Plan 的 S03–S07）
- `DocumentTags` / `Tags` 合併（S05）
- `zenos.documents` / `document_entities` drop（S07）
- Protocol collection 收斂（ADR-045；S01–S02）
- Dead Identity dataclass 清理（S08）
- 歷史 doc entity primary_parent TD（S09）

**不重疊原則**：兩份 PLAN 可並行，但不得同時改同一張 migration file 或同一份 repo file。Phase 交界由 Architect 協調，見 §8 Coordination。

## Entry Criteria

| # | 條件 | 驗證 |
|---|------|------|
| E1 | `ADR-048-grand-ontology-refactor` status = Approved | ADR 前頁 frontmatter |
| E2 | 主 SPEC v2 §9 schema（entity_l3_*）已通過 architect review 無進一步修訂 | 無 pending review comment |
| E3 | `PLAN-data-model-consolidation` 為 **ACTIVE**（refactor-index.md 已於 2026-04-23 修正；該 Plan 不是 OBSOLETE）且其 S03（preflight + `EntityStatus.archived` + migration stub）為 **done** — 本 PLAN Phase A02 的 `entities_base` table 依賴該上游落地 | S03 task 的 MCP entity status=done；若該 Plan 尚未啟動，Architect 需先 claim S03 或把其內容搬進本 PLAN 的 A0x（見 §Coordination） |
| E4 | Staging 環境 DB backup + restore drill 完成 | 運維文件記錄 |
| E5 | 本 PLAN 的 Resume Point 已由 Architect claim | `mcp__zenos__task` 下此 PLAN 有 L3 task 處於 in_progress |

## Exit Criteria

| # | 條件 | 驗證方式 |
|---|------|---------|
| X1 | 5 張 subclass table（`entities_base` / `entity_l3_milestone` / `entity_l3_plan` / `entity_l3_task` / `entity_l3_subtask`）存在且符合主 SPEC v2 §9 DDL | `psql` describe + CHECK constraint 測試 |
| X2 | Runtime task / plan 的 primary read/write path 走 subclass table，不再走 `zenos.tasks` / `zenos.plans` | `grep -r "zenos.tasks\|zenos.plans"` 於 `src/zenos/infrastructure/` 0 hit（除了 migration / archive tag） |
| X3 | `task_entities` table 已 drop | migration 確認；`sql_task_repo.py` 無 `task_entities` reference |
| X4 | Task `product_id` / `plan_id` / `parent_task_id` 三欄在 DB 層刪除；歸屬由 `parent_id` 表達 | migration 確認；主 SPEC v2 §9.4 DDL 完全落地 |
| X5 | Server 強制 `parent_id` 鏈終止於 L1（level=1, parent_id=null）；違反 reject `INVALID_PARENT_CHAIN` | `governance_rules.py` 更新 + test 通過 |
| X6 | MCP `task` / `plan` / `confirm` / `search(collection="tasks")` 外部 contract（`SPEC-mcp-tool-contract §8.5-§8.9`）行為不變 | partner key e2e 測試通過；dashboard 顯示一致；迴歸 test 零失敗 |
| X7 | Compliance test 全綠——以下 AC 必須從 red → green：`AC-TASK-01..09`、`AC-MCP-01..35`（除 Gap-note 標記為非 runtime 強制的條目；見下）；`AC-TASK-10` 不列入本 PLAN 退場標準——SPEC-task-governance §17 明載其 `SUBTASK_NESTING_DISALLOWED` 為 governance target 而非 runtime 強制（Wave 9 不新加 validation，若之後要做走 §9.1 stretch task） | `pytest tests/spec_compliance/ -v` |
| X7b | SPEC-mcp-tool-contract §13 標為「governance target」的 AC（AC-MCP-20 / AC-MCP-21 / AC-MCP-31 find_gaps / AC-MCP-32 analyze 中的非強制分支）維持現狀；本 PLAN 不 implement 也不阻擋 | 該些 AC 在 test suite 維持 skipped / 標註為 target-state | |
| X8 | ADR-028 / ADR-044 / ADR-047 frontmatter status → Superseded，`superseded_by: ADR-048` | grep ADR frontmatter |
| X9 | 主 SPEC v2 §9 intro 的「當前 runtime 狀態」block 改寫為「已落地」；`REF-ontology-current-state` 的 Wave 9 warning 清除 | grep 文件 |
| X10 | Stable 運行 ≥ 2 週、partner 零資料不一致 incident | 運維報告 + error log |

## 關鍵 Runtime 參考（實作前必讀）

### Domain layer
- `src/zenos/domain/action/models.py` — `Task` / `Plan` / `Subtask` / `Milestone` 現行 dataclass
- `src/zenos/domain/action/repositories.py` — repo protocol
- `src/zenos/domain/task_rules.py` — state machine `_VALID_TRANSITIONS`（Wave 9 後仍 canonical，邏輯不動）
- `src/zenos/domain/knowledge/models.py` — `Entity` / `BaseEntity`（L3-Action 將要繼承的 base）
- `src/zenos/domain/knowledge/enums.py` — `EntityStatus` / `TaskStatus`
- `src/zenos/domain/governance.py` — 跨實體治理邏輯，可能需要改寫 L3-Action 辨識方式

### Infrastructure layer
- `src/zenos/infrastructure/action/sql_task_repo.py`（~400 行；lines 82,101,117,220,253,270,275,280,326,356-358,394 都是 Wave 9 改動熱區）
- `src/zenos/infrastructure/action/sql_plan_repo.py`
- `src/zenos/infrastructure/firestore_repo.py` — 舊 Firestore fallback（已 deprecated 但仍需確認不會被叫到）
- `src/zenos/infrastructure/knowledge/sql_entity_repo.py` — 主 SPEC 的 `entities_base` 實作起點

### Interface layer（主要作為黑盒 contract 驗證，避免 regression）
- `src/zenos/interface/mcp/task.py:577-708`（`task` handler）
- `src/zenos/interface/mcp/plan.py:198-275`
- `src/zenos/interface/mcp/confirm.py:24` — `entity_entries` feedback loop
- `src/zenos/interface/mcp/search.py:145`
- `src/zenos/interface/mcp/get.py:139`
- `src/zenos/interface/governance_rules.py`（error code canonical）

### Migration infrastructure
- `migrations/20260325_0001_sql_cutover_init.sql:293` — task_entities 建立位置
- 新 migration 的檔名前綴可用 `20260501_*`（Wave 9 landing 預期時程，實際 merge 日取目前日期）
- 現有 migration runner：`scripts/run_sql_migrations.py`

### Spec 導引（實作對照權威）
- 主 SPEC v2 §9（L3-Action DDL canonical）
- 主 SPEC v2 §10（Relationships 取代 task_entities junction）
- 主 SPEC v2 §11.2（status state machine，state machine 已在 runtime 正確）
- `SPEC-task-governance §1.1 + §1.2`（歸屬語意 + ownership SSOT）
- `SPEC-task-governance §3` + `task_rules.py:19-33`（state machine，Wave 9 不改）
- `SPEC-mcp-tool-contract §8.5 / §8.9`（task / plan tool contract，外部不動）

## Phase 劃分（dependency chain）

```
Phase A (schema preflight, additive)
    │
    ▼
Phase B (domain dataclass duality)
    │
    ▼
Phase B' (application + interface contract-preserving adapter)
    │    ↑ 保證 MCP contract 行為不變；Phase C 之前必完
    ▼
Phase C (infra dual-write / dual-read with feature flag)
    │
    ▼
Phase D (parent_id backfill + INVALID_PARENT_CHAIN validator)
    │
    ▼
Phase E (cutover: feature flag ramp)
    │
    │ (穩定 2 週)
    ▼
Phase F (legacy drop: 舊欄位 / task_entities / Task dataclass)
    │
    ▼
Phase G (SPEC / ADR / REF / index 後處理)

（本 PLAN 與 PLAN-data-model-consolidation 的 coordination 見 §8）
```

## Tasks

### Phase A — Schema preflight（additive，零 runtime 行為變化）

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **A01** | Preflight 調查：task_entities / task_blockers 目前行數、NULL 率、cross-partner 分佈 | query 寫入 runbook；不改 code | 統計表進 migration runbook；發現任何 outlier（cross-partner / 孤兒 row）先進 `findings` log |
| **A02** | 新 migration：建 `entities_base` + `entity_l3_milestone / plan / task / subtask` 五張 table（空；不加 FK 到 `zenos.tasks`）| `migrations/20260xxx_l3_action_preflight.sql` | `psql \d entity_l3_task` 可見；DDL 對齊主 SPEC v2 §9.4 line 456-471 |
| **A03** | 確認 `entities_base` 與 `PLAN-data-model-consolidation` 的使用方式相容：兩份 PLAN 不得各自建一張語意衝突的 `entities_base` | Architect 檢查 + 兩份 PLAN 的 Architect 同步會議紀錄 | 兩份 PLAN 所需 schema 描述一致；若有衝突先收斂再執行 A02 |
| **A04** | 加 `entities_base.parent_id` 欄位 nullable（之後 Phase D backfill）| 同 A02 migration 或續寫 | column 存在 |
| **A05** | CHECK constraint 預寫 stub：`task_status != 'review' OR result IS NOT NULL` 等主 SPEC §9 的 CHECK，先設 `NOT VALID`（之後 Phase E 驗證再 enable）| migration | CHECK 存在但未 enforce |

### Phase B — Domain dataclass duality

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **B01** | 建 `L3TaskBaseEntity` 抽象 dataclass（description / task_status / assignee / dispatcher / acceptance_criteria / priority / result / handoff_events）| `src/zenos/domain/action/models.py` 新增（**不刪** `Task`）| `pytest tests/domain/test_models.py` 通過 |
| **B02** | 建 `L3TaskEntity` / `L3PlanEntity` / `L3SubtaskEntity` / `L3MilestoneEntity` dataclass，對齊主 SPEC v2 §9.2-§9.5 | 同 | import 無 circular dep |
| **B03** | 加 domain-level converter `Task ↔ L3TaskEntity`，確保新舊雙向可轉換（避免 Phase C 讀寫不一致時炸掉）| 同；test 加 | round-trip equal 測試通過 |
| **B04** | `governance.py:223-230` 雙路徑邏輯擴充：同時支援舊 `Task` 與 `L3TaskEntity`（現在已同時支援 `Document` vs `Entity`；把 Task 納入）| `src/zenos/domain/governance.py` | 既有 test 不動；新增 Task-as-entity test 通過 |

### Phase B' — Application / Interface contract-preserving adapter（在 C 之前、B 之後）

> **目的**：`B` 只動 domain dataclass，`C` 才碰 DB。中間需要 application + interface 層把新 dataclass 接上去，**同時保證 `SPEC-mcp-tool-contract §8.5-§8.9` 的 MCP contract 零行為變化**。沒有這些 task，repo 改完會發現 MCP response shape / error code / warning 漂掉。

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **BP01** | `task_service.py` 擴充：同時可以處理 `Task` 與 `L3TaskEntity` 型別輸入／輸出；validation logic（`CROSS_PLAN_SUBTASK` / `CROSS_PRODUCT_SUBTASK` / `MISSING_PRODUCT_ID` / `HANDOFF_EVENTS_READONLY` 等）搬到新 class 仍會被觸發 | `src/zenos/application/action/task_service.py:180-224,340-480,660-700` | 現有 `tests/application/test_validation.py` 全綠；新加 `test_task_service_l3_entity_path.py` 確認新類型走過同一套 validation；每個 error code（見 `governance_rules.py:930-948`）仍能觸發 |
| **BP02** | `plan_service.py` 同上：同時接受 legacy `Plan` 與 `L3PlanEntity`；`PLAN_HAS_UNFINISHED_TASKS` 的 ValueError 字串輸出維持（Shape B rejection reason）| `src/zenos/application/action/plan_service.py:148-196` | integration test：plan completed 時訊息含前 5 個 task id，字串完全等同 legacy path |
| **BP03** | `mcp/task.py` 輸出 normalization：確保 `data.linked_entities` 仍為 expanded objects（per `SPEC-mcp-tool-contract §8.5` + dogfood Issue 7 已修）；dual-path 期間兩條路徑的 response shape byte-equal | `src/zenos/interface/mcp/task.py:577-708` + `_common._enrich_task_result` | 新增 `tests/interface/test_task_response_parity.py`：legacy 與 new-entity 路徑對同一 input 的 response dict 深度等同 |
| **BP04** | `mcp/plan.py` 輸出 normalization：`action="get"` 回 `tasks_summary`；`action="list"` 回 collection-keyed；`PLAN_HAS_UNFINISHED_TASKS` shape 不變（Shape B） | `src/zenos/interface/mcp/plan.py:198-275` + `_plan_handler` | parity test 對 create/update/get/list 四 action 的 response；rejection_reason 字串等同 |
| **BP05** | `mcp/confirm.py` parity：`collection="tasks"` 的 `accepted=True/False` 走 new-entity path 與 legacy path 行為等同；`entity_entries` writeback 仍命中 L2 sidecar；`accept` alias warning 字串不變 | `src/zenos/interface/mcp/confirm.py:24-140` + `_enrich_task_result` | parity test：accept 與 reject 兩 branch；HandoffEvent append 內容 byte-equal；entry write 結果一致 |
| **BP06** | `mcp/search.py` — `collection="tasks"` 走新 repo path 時 response shape 不變；legacy status normalize（`backlog` / `blocked` / `archived`）仍 warning；filter 欄位（`plan_id` / `parent_task_id` / `dispatcher` / `linked_entity`）全部能走 | `src/zenos/interface/mcp/search.py:145-260` | parity test：對同一 query legacy 與 new path 回傳完全一致；legacy status alias warning 字串一致 |
| **BP07** | `mcp/get.py` — `collection="tasks"`、`id` / `id_prefix` / `include` 三類 path 在 new-entity path 下仍保持 `SPEC-mcp-tool-contract §8.2` 行為；`AMBIGUOUS_PREFIX` reject 字串不變 | `src/zenos/interface/mcp/get.py:139-200` | parity test |
| **BP08** | `governance_rules.py` 的所有 task-related error code（`CROSS_PLAN_SUBTASK / CROSS_PRODUCT_SUBTASK / CROSS_PRODUCT_PLAN_TASK / MISSING_PRODUCT_ID / INVALID_PRODUCT_ID / LINKED_ENTITIES_PRODUCT_STRIPPED / HANDOFF_EVENTS_READONLY / PARENT_NOT_FOUND / INVALID_DISPATCHER`）在新 entity path 下皆 wired，且 envelope shape（Shape A flat `data.error: str`）一致 | `src/zenos/interface/governance_rules.py:930-948` + 相關 caller | AC-MCP-06/07/08/09/10/11 全綠 |

### Phase C — Infrastructure dual-write / dual-read

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **C01** | `sql_task_repo.py` 寫入：transaction 內同時寫 `zenos.tasks` 與 `entity_l3_task` + `entities_base`（冪等：二者欄位不一致 raise）| `sql_task_repo.py:220-270` 增 dual write；不刪舊 | 寫完的 row 兩邊都存在；migration test；pytest integration |
| **C02** | `sql_task_repo.py` 讀取：預設仍讀 `zenos.tasks`（避免行為改變）；新增 `feature_flag="l3_read_new_path"` 切到讀 `entity_l3_task`，預設 off | `sql_task_repo.py` + config | flag off 時 behavior 0 變化；flag on integration test 通過 |
| **C03** | 同 C01/C02 套用 `sql_plan_repo.py` / `entity_l3_plan` | `sql_plan_repo.py` | 同 |
| **C04** | Subtask / Milestone 的 dual-write：subtask 寫 `entity_l3_subtask`；milestone 因現有 `goal` entity type，需確認是否 in-place upgrade 還是獨立寫 | A01 調查 + 決策；改 repo | 決策有 ADR 或 decision record；migration 後行為等價 |
| **C05** | `task_entities` 行為：dual-write 改為同時寫 `relationships`；讀取仍走 `task_entities`（不動行為）| `sql_task_repo.py:275-280` 增寫 relationships | 每次 task mutation 後 relationships 與 task_entities 行數差距 = 0 |
| **C06** | `task_blockers` 的收斂決策：依 A01 調查決定留或改走 relationships 的 `blocks` type。Architect 決策後落入 subtask | sql_task_repo.py:104-109 | 決策記錄於本 PLAN Decisions 章節；執行後 blocked_by 查詢行為等價 |

### Phase D — parent_id backfill + validation

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **D01** | backfill script：對每個 task 計算 `parent_id = plan_id OR product_id`（按主 SPEC §9 語意）；subtask 的 `parent_id = parent_task_id` | `scripts/backfill_l3_action_parent_id.py` 新檔 | dry-run 無 cross-partner 洩漏；所有 row 有 parent_id |
| **D02** | backfill script：plan 的 `parent_id = product_id`；milestone 的 `parent_id` 視 A01 / C04 決策 | 同 | 同 |
| **D03** | 寫 `INVALID_PARENT_CHAIN` validator：new task / plan 的 parent_id 必須可走回 level=1 / parent_id=null 的 L1 entity | `governance_rules.py` + `task_service.py` | test 驗證 rejection；既有 task 若 parent chain 壞進入 §D03a 定義的 legacy table |
| **D03a** | 定義「既有孤兒 / 斷鏈 task」落腳載體（decision + migration）。兩張表載體需在同一 migration 建立，避免 Phase D 落地時隱性引入 schema：<br>**table 1: `zenos.legacy_orphan_tasks`**（D01 backfill 過不去的 row，column：`task_id / partner_id / reason / detected_at / resolved_at / resolver_partner_id / manual_parent_id`；Wave 9 完成後 2 週若 rows 仍 >0 升 incident）<br>**table 2: `zenos.legacy_parent_chain_warnings`**（D03 validator 觸發但 allowlist 過渡的 row；column：`task_id / chain_snapshot_json / detected_at / triaged_at`；migration drop 時間點見 Phase F）| 新 migration：`migrations/20260xxx_wave9_legacy_shadow_tables.sql`；admin runbook：`docs/runbooks/wave9-legacy-task-triage.md`（新建） | 兩張 table 存在且有 DDL；runbook 描述 SLA（orphan row TTL 7 天人工處理）；本 PLAN §Decisions 記錄「採 DB table 而非 journal / runbook-only」理由 |
| **D04** | D01/D02 執行 on staging → staging regression → production（small batch first）| 同 | staging 通過 + 監控指標不變 |
| **D05** | Phase A 設的 CHECK constraint 從 NOT VALID 改 VALID（啟用強制）| migration | CHECK violation count = 0 on production |

### Phase E — Cutover

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **E01** | Feature flag `l3_read_new_path` 由 off → on（分階段：staging 100% → prod 10% → prod 100%）| config + monitoring | 每階段 48h 無 regression |
| **E02** | 停止 dual-write 的舊路徑：`zenos.tasks` / `zenos.plans` / `task_entities` 改為 **read-only shadow**（仍有資料，但不再寫新 row）| `sql_task_repo.py` | 所有 mutation 只走 `entity_l3_*` + `relationships`；舊表行數不再增長 |
| **E03** | AC compliance test 全綠：`AC-TASK-01..09` + `AC-MCP` 中標為「runtime enforcement」的條目 + 主 SPEC §9 CHECK test（見 §Exit Criteria X7/X7b 排除清單）| `tests/spec_compliance/` | `pytest` 綠；skipped 清單以 reviewer-accepted gap 為限 |
| **E03b** | 新增 `tests/spec_compliance/test_wave9_ac_status_map.py`：每條 AC 標記 `runtime_enforced | governance_target | pending_wave`；CI 失敗若清單與本 PLAN 不一致 | 新 test file | CI 綠 |
| **E04** | Partner key e2e 驗證（create task → handoff → confirm → entity_entries 回饋 → delete）| `tests/integration/test_e2e_*` | 全部綠 |

### Phase F — Legacy cleanup（E 穩定 ≥ 2 週後）

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **F01** | Drop `zenos.tasks.product_id` / `plan_id` / `parent_task_id` 欄位（歸屬已進 parent_id）| migration | column 不存在；既有查詢 0 regression |
| **F02** | Drop `task_entities` table | migration | `psql \d task_entities` 不存在 |
| **F03** | `task_blockers` 依 C06 決策執行：drop 或重命名 | migration | 同 |
| **F04** | 刪除 legacy `Task` / `Plan` dataclass（保留 `L3TaskEntity` 等新 class）；刪 Phase B 的 converter | `src/zenos/domain/action/models.py`；`governance.py:223-230` 去 Document-like 雙路徑 | grep `class Task(` 0 hit；test suite 綠 |
| **F05** | 刪除 `sql_task_repo.py` / `sql_plan_repo.py` 裡對舊 table 的查詢 / dual-write code | infra repo | grep 確認無 `zenos.tasks` 殘留 |
| **F06** | Drop `zenos.tasks` / `zenos.plans` 本體 table（最後步驟；保留 2 週 read-only shadow 期滿後）| migration | table 不存在 |
| **F07** | Drop `zenos.legacy_orphan_tasks` 與 `zenos.legacy_parent_chain_warnings`（D03a 定義的 shadow tables）。前提：兩表 row count = 0 持續 ≥ 2 週，且 runbook triage 全部結案 | migration | table 不存在；runbook 封存至 `docs/runbooks/archive/` |

### Phase G — Post-landing SPEC / ADR / REF 同步

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **G01** | 主 SPEC v2 §9 intro block 改寫：刪「當前 runtime 狀態」段落，改為「已於 Wave 9 migration 落地」| `docs/specs/SPEC-ontology-architecture.md` | grep 無 `runtime 今日` 殘留於 §9 |
| **G02** | `SPEC-task-governance §1.1` Transitional note 刪除（或改「Wave 9 已完成」歷史註記）| `docs/specs/SPEC-task-governance.md` | 無 post-MTI / Transitional 字眼 |
| **G03** | `REF-ontology-current-state.md` 清掉所有 runtime-vs-target 警告；§1 axioms 改為事實敘述 | `docs/reference/REF-ontology-current-state.md` | 無 target-state warning |
| **G04** | ADR-028 status → Superseded；frontmatter `superseded_by: ADR-048` | `docs/decisions/ADR-028-plan-primitive.md` | status 更新 |
| **G05** | ADR-044 status → Superseded；frontmatter `superseded_by: ADR-048` | `docs/decisions/ADR-044-task-ownership-ssot-convergence.md` | status 更新 |
| **G06** | ADR-047 的「partial」部分升為完全 Superseded | `docs/decisions/ADR-047-l1-level-ssot.md` | 同 |
| **G07** | ADR-046 / ADR-032 / ADR-041 同步檢查：若其 runtime 層也已落地（由 `PLAN-data-model-consolidation` 或其他 PLAN 收口），一併改 Superseded | 各 ADR 前頁 | 按落地實況更新 |
| **G08** | ADR-048 `supersedes:` 前頁 list 擴充，納入 028 / 044 / 047 等新完成 supersede 的 ADR | `docs/decisions/ADR-048-grand-ontology-refactor.md` | frontmatter list 一致 |
| **G09** | `refactor-index.md` Wave 9 欄標記 ✅ + 實際 migration 日期 | `docs/refactor-index.md` | 索引更新 |
| **G10** | 寫 journal：Wave 9 完成摘要（commit SHA + 關鍵決策 + next step）| `mcp__zenos__journal_write` | journal 已寫 |

## Risks & Mitigation

| Risk | 影響 | Mitigation |
|------|------|-----------|
| **task / plan 資料在 dual-write 階段出現不一致** | partner 看到錯誤狀態 | C01 transaction wrap；每次 mutation 有 invariant check；staging 跑 1 週後才 prod |
| **`parent_id` backfill 對既有孤兒 task 失效** | task 無法歸屬 L1 | D01 先做 dry-run；孤兒 row 寫入 **D03a 定義的 `zenos.legacy_orphan_tasks` DB table**（非 journal / 非 runbook-only）；每筆在 Wave 9 完成後 2 週內須人工 triage，reason / resolver_partner_id 記錄；不 silent 吞 |
| **Cutover 當下 MCP 行為意外變化** | 所有 partner 受影響 | feature flag 分階段 rollout（E01）；每階段 48h 觀察；有 rollback 步驟 |
| **Phase F drop table 之後才發現還有 caller** | 服務 500 | F01-F06 前必做 `grep -r "zenos.tasks"` 全 repo 確認 0 caller；灰度期 2 週 |
| **`PLAN-data-model-consolidation` 與本 PLAN 同時改 `entities_base` 語意** | schema 衝突 | §8 Coordination 強制 Architect 同步；Phase A03 明確檢查相容性 |
| **既有 `task_rules.py` state machine 邏輯漏移到新 entity class** | reopen / confirm 等行為 regression | B03 converter 的 round-trip test；E03 AC compliance test 包含全部狀態轉換 |
| **Handoff events JSONB 欄位在 subclass table 位置不對**（主 SPEC §9.6 是獨立 log，可能需要新表 `task_handoff_events`）| audit trail 斷裂 | A02 / A03 階段先拍板 handoff_events 存儲位置；若改獨立表需另建 migration subtask |

## Coordination with `PLAN-data-model-consolidation`

兩份 PLAN 重疊區：**`entities_base` 表**與 **`Entity` dataclass**。

| 檔案 / 結構 | PLAN-data-model-consolidation | 本 PLAN | 協調原則 |
|------------|------------------------------|---------|---------|
| `entities_base` table DDL | 負責 document-type row 寫入 | 負責 L3-action row 寫入 | Phase A02 migration 由先動工的 PLAN 建表；另一 PLAN 只新增 column / constraint，不重建 |
| `EntityStatus` enum | S03 新增 `archived` | L3-Action 用 `active` 不會動 enum | 無衝突 |
| `governance.py:223-230` 雙路徑 | S06 從 Document 移除 | B04 加入 Task 支援 | 兩邊改不同分支，不衝突 |
| `Tags` dataclass | S05 合併 DocumentTags 進 Tags | 不動 | 本 PLAN 讀 Tags，不改 schema |
| `relationships` 表 | S04 backfill document_entities | C05 backfill task_entities | 同表，migration 可並行但 dry-run 須同時驗 |

**衝突解決機制**：Architect 每週同步兩份 PLAN 的 Resume Point；任何 shared file 改動需在 PR description 標 `@plan-data-model` 與 `@plan-wave9-migration` 讓兩邊 architect 都 review。

## Decisions（build 期間追加）

- 2026-04-23：PLAN 初稿建立。scope 與 `PLAN-data-model-consolidation` 明確切開（document / protocol 不碰）。
- 2026-04-23：`PLAN-data-model-consolidation` 的 OBSOLETE 判斷於 refactor-index.md:239 撤回 — 兩份 PLAN 並行、scope 正交（見 §Coordination）。
- 2026-04-23：legacy 孤兒 / 斷鏈 task 的載體採 **DB table**（`zenos.legacy_orphan_tasks` + `zenos.legacy_parent_chain_warnings`），不採 journal / runbook-only。理由：
  - DB table 可查詢、可 join、可跨 session 持久；journal / runbook-only 會失去 structured triage state
  - Row count / TTL 可當 ops 指標；Phase F07 drop 條件可量化（row=0 連續 2 週）
  - 建立成本極低（migration 兩張表 ≤20 行 SQL），不值得為省這點成本採非結構化載體
- 〔待定〕`task_blockers` 的去留（A01 調查後由 Architect 拍板）
- 〔待定〕Milestone 是否 in-place upgrade 現有 `goal` entity（C04 決策）
- 〔待定〕`handoff_events` 存儲位置：subclass JSONB 或獨立 `task_handoff_events` 表（A02 決策）

## Resume Point

**目前狀態**：Draft，尚未建立 MCP plan entity。

**下一步**：
1. 用戶 review 本 PLAN（特別是 §Scope 邊界、§Risks、§Coordination）
2. 通過後 Architect 用 `mcp__zenos__plan(action="create", ...)` 建立 plan entity 並取得 `plan_id`
3. 將本檔 frontmatter 的 `plan_id` 從 missing 補成真實 UUID
4. Architect 依 Phase A dependency 建立 A01-A05 共 5 張 L3 task，`plan_id` = 本 Plan UUID
5. A01 完成後再開 B / C / D / E / F / G 的 task

**斷點對話脈絡**：Wave 0-8 spec-level refactor 已完成並 commit 到 `main`（最新 commit `773a64ccd`）。ADR-048 master 正式把「spec 目標態 vs runtime 現況」的分裂寫明。本 PLAN 是 Wave 9 的 runtime 實作計畫，**不包含** code，只定義 phase / subtask / 依賴 / risk。

## 相關文件

**Canonical SPEC（實作對照權威）**
- `docs/specs/SPEC-ontology-architecture.md`（v2 §9 DDL、§10 Relationships、§11.2 state machine）
- `docs/specs/SPEC-task-governance.md`（§1 歸屬、§3 state machine、§4 handoff、§8 linked_entities、§11 entity_entries、§17 AC-TASK-01..10）
- `docs/specs/SPEC-mcp-tool-contract.md`（§6 envelope、§8.5-§8.9 task/plan/confirm contract、§13 AC-MCP-01..35）

**Runtime canonical（實作時的主要 touch points）**
- `src/zenos/domain/action/models.py`
- `src/zenos/domain/action/repositories.py`
- `src/zenos/domain/task_rules.py`（Wave 9 **不改** state machine 邏輯）
- `src/zenos/infrastructure/action/sql_task_repo.py`
- `src/zenos/infrastructure/action/sql_plan_repo.py`
- `src/zenos/interface/mcp/task.py` / `plan.py` / `confirm.py`
- `src/zenos/interface/governance_rules.py`

**決策權威**
- `docs/decisions/ADR-048-grand-ontology-refactor.md`（master）
- `docs/decisions/ADR-028-plan-primitive.md`（將於 G04 Superseded）
- `docs/decisions/ADR-044-task-ownership-ssot-convergence.md`（將於 G05 Superseded）
- `docs/decisions/ADR-047-l1-level-ssot.md`（將於 G06 完全 Superseded）

**並行 PLAN（coordination required）**
- `docs/plans/PLAN-data-model-consolidation.md`（Document / Protocol / Tags）

**索引**
- `docs/refactor-index.md`（Wave 9 狀態最終回寫位置）
