---
type: PLAN
id: PLAN-ontology-grand-refactor-wave9-migration
status: done
owner: architect
project: zenos
plan_id: 4f4a591ec45143d9b2d3d4528a4e1c3e
product_id: Gr54tjmnXK0ZAtZia6Pj
created: 2026-04-23
updated: 2026-04-24
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

> **Pre-entry investigation exception（2026-04-23 Architect 決策，用戶核可）**：
> A01 為 pre-entry investigation，性質是 read-only query + 決策收集，可在 E1-E5 全數達成前先行啟動。
> A01 不動 schema、不動 runtime、不寫 code（只寫 runbook + decision record），不與 `PLAN-data-model-consolidation` 產生 shared-file 衝突。
> A02 起（會建 `entities_base` 等 schema 的 task）必須等 E3 正式解除、三項待定決策拍板後才能啟動。

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
| X10 | Stable 運行 ≥ 2 週、partner 零資料不一致 incident | **Owner waiver 2026-04-24**：prod-only / single-user deployment，經 dry-run、partner-key e2e、post-drop smoke 通過後直接進 Phase F |

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
| **A01** | **Pre-entry investigation（解鎖 3 項待定決策 + 重估依賴）**；四件交付物缺一不可：<br>**(a) Junction table 現況**：`task_entities` / `task_blockers` 目前行數、NULL 率、cross-partner 分佈；outlier（孤兒 row / cross-partner）進 `findings` log，含 task_id 與 reason<br>**(b) Milestone / `goal` entity 現況盤點**：現有 row 數、被哪些 L2 module / L3 task 引用、與主 SPEC v2 §9 L3-Milestone 語意差異；給出 C04 決策建議（in-place upgrade `goal` vs 獨立 `entity_l3_milestone` subclass），含 data migration blast radius 評估<br>**(c) `handoff_events` 存儲位置評估**：目前 JSONB 欄位分佈（per-task 平均長度、最大值）、append 頻率、audit 查詢模式；對照方案 A=subclass JSONB / B=獨立 `task_handoff_events` 表的 (read/write cost, audit queryability, migration cost)，給出推薦<br>**(d) 依賴重估**：**明確判定** `PLAN-task-ownership-ssot`（plan_id `c646d3c91374466baa92c6e03d6a4b37`）是否為本 PLAN Phase D 上游。分析 D01/D02 backfill 對 `tasks.product_id` 的實際依賴（欄位還是 SSOT？是否已 NOT NULL？），回答「Phase D 可否在 ownership plan 未完成前啟動」。若判定為上游，就在回報中指名要把它補進本 PLAN Entry Criteria | `docs/runbooks/wave9-preflight-findings.md`（新建）+ `docs/runbooks/wave9-preflight-findings.findings.csv`（outlier log） | 四段各自有證據數據與推薦結論；Architect 依此拍板 A02 `entities_base` DDL + handoff_events 位置、C04 milestone 策略、C06 task_blockers 去留、Phase D 上游依賴；拍板後更新本 PLAN §Decisions 與 Entry Criteria |
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

### Phase C gate（2026-04-23 追加）

**Phase C 啟動前必須完成的 infra 前置**（Architect 獨立 triage，非 Wave 9 scope 內 task）：
1. ✅ `scripts/migrate.sh` secret source 修正：`database-url`（空 neondb）→ `zenos-database-url`（真 zenos DB），並新增 `--target prod|staging`
2. ✅ staging DB 環境建立：同一 Cloud SQL instance `zentropy-db` 內新增獨立 database `zenos_staging` + secret `zenos-staging-database-url`
3. ✅ `migrations/20260423_0004_wave9_l3_action_preflight.sql` 正式 apply：已透過 migration runner 先 staging 後 prod；prod schema 原已存在，runner 已補記 `zenos.schema_migrations`

**I02 結論（2026-04-24）**：Phase C gate 已解除。Staging 是同 instance 的獨立 database，不是獨立 Cloud SQL instance；在目前「只有一台 DB instance」約束下，這是 Wave 9 後續 dual-write / cutover smoke 的正式 target。

Phase C 的 Developer dispatch prompt 必須在開工前確認以上三項已 green。

### Phase C — Infrastructure dual-write / dual-read

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **C01** ✅ | `sql_task_repo.py` 寫入：transaction 內同時寫 `zenos.tasks` 與 `entity_l3_task` + `entities_base`（冪等：二者欄位不一致 raise）| `sql_task_repo.py` dual-write；不刪舊；`parent_id` 先留 NULL，Phase D backfill | `tests/infrastructure/test_sql_repo.py::TestSqlTaskRepository` + repo suite pass |
| **C02** ✅ | `sql_task_repo.py` 讀取：預設仍讀 `zenos.tasks`（避免行為改變）；新增 `feature_flag="l3_read_new_path"` 切到讀 `entity_l3_task`，預設 off | env flag `ZENOS_L3_READ_NEW_PATH`; get/list/prefix/review/blocker read path 支援 L3 | flag off behavior 0 變化；flag on mock coverage pass |
| **C03** ✅ | 同 C01/C02 套用 `sql_plan_repo.py` / `entity_l3_plan` | `sql_plan_repo.py` dual-write；讀取共用 `ZENOS_L3_READ_NEW_PATH`，預設 off；`parent_id` 先留 NULL，Phase D backfill | `tests/infrastructure/test_sql_repo.py::TestSqlPlanRepository` + plan tool/service parity pass |
| **C04** ✅ | Subtask / Milestone 的 dual-write：subtask 寫 `entity_l3_subtask`；milestone 採 A01 已拍板的獨立 subclass strategy 寫 `entity_l3_milestone` | `sql_task_repo.py` subtask dual-write；`sql_entity_repo.py` goal→milestone dual-write | `tests/infrastructure/test_sql_repo.py::TestSqlTaskRepository` + `::TestSqlEntityRepository` pass |
| **C05** ✅ | `task_entities` 行為：dual-write 改為同時寫 `relationships`；讀取仍走 `task_entities`（不動行為）| `sql_task_repo.py` task mutation 後同步 `relationships(type='related_to')`；目前 legacy FK schema 下用 savepoint guard，避免過渡期 FK mismatch 中斷 task 寫入 | relationships SQL coverage pass；完整 row parity 待 Phase D/E schema cutover 後驗證 |
| **C06** ✅ | `task_blockers` 的收斂決策：依 A01 調查 0 row，採 direct drop | 不改 runtime read path；drop 合併到 Phase F03 legacy cleanup | 決策記錄於 §Decisions；Phase C 不提前破壞 legacy shadow read |

### Phase D — parent_id backfill + validation

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **D01** ✅ | backfill script：對每個 task 計算 `parent_id = plan_id OR product_id`（按主 SPEC §9 語意）；subtask 的 `parent_id = parent_task_id` | `scripts/backfill_l3_action_parent_id.py` 新檔；同時更新 runtime dual-write 新 row 不再寫 NULL parent_id | dry-run/apply script tests pass；實際 staging/prod apply 進 D04 |
| **D02** ✅ | backfill script：plan 的 `parent_id = product_id`；milestone 的 `parent_id` 採 legacy goal.parent_id（A01/C04 milestone 獨立 subclass 決策） | 同 | script 覆蓋 plan/milestone rows；實際 staging/prod apply 進 D04 |
| **D03** ✅ | `INVALID_PARENT_CHAIN` validator：new task / plan 的 parent_id 必須可走回 level=1 / parent_id=null 的 L1 entity | Phase D script DB validator + warning capture；runtime wiring：task/plan mutation 遇到既有 parent 缺 `product_id` 時回 `INVALID_PARENT_CHAIN`，plan MCP handler 支援帶 `error_code` 的標準 error envelope | script validator tests pass；runtime error-code tests pass |
| **D03a** ✅ | 定義「既有孤兒 / 斷鏈 task」落腳載體（decision + migration）。兩張表載體需在同一 migration 建立，避免 Phase D 落地時隱性引入 schema：<br>**table 1: `zenos.legacy_orphan_tasks`**（D01 backfill 過不去的 row，column：`task_id / partner_id / reason / detected_at / resolved_at / resolver_partner_id / manual_parent_id`；Wave 9 完成後 2 週若 rows 仍 >0 升 incident）<br>**table 2: `zenos.legacy_parent_chain_warnings`**（D03 validator 觸發但 allowlist 過渡的 row；column：`task_id / chain_snapshot_json / detected_at / triaged_at`；migration drop 時間點見 Phase F）| `migrations/20260424_0001_wave9_legacy_action_shadow_tables.sql` | static migration tests pass |
| **D04** ✅ | D01/D02 執行。2026-04-24 用戶決策：只有 prod，跳過 staging；prod 先 dry-run clean 再 apply | `scripts/backfill_l3_action_parent_id.py` + prod report `/tmp/wave9_l3_parent_backfill_apply_after_schema_fix.json` | prod apply success；0 orphan；0 parent chain warning；action parent_id NULL=0 |
| **D05** ✅ | Phase A 設的 CHECK constraint 從 NOT VALID 改 VALID（啟用強制）| `migrations/20260424_0003_wave9_validate_l3_action_checks.sql` | prod `entity_l3_task_review_needs_result.convalidated = true` |

### Phase E — Cutover

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **E01** ✅ | Feature flag `l3_read_new_path` 由 off → on（用戶決策：prod-only；先 smoke，再 prod ramp）| `scripts/smoke_l3_read_new_path.py`；Cloud Run revision `zenos-mcp-00209-9qd`（flag on） | prod traffic 100% flag-on；25 tasks + 25 plans smoke 0 mismatch；Cloud Run ERROR log = `[]` |
| **E02** ✅ | 停止 dual-write 的舊路徑：`zenos.tasks` / `zenos.plans` / `task_entities` 改為 **read-only shadow**（仍有資料，但不再寫新 row）| `sql_task_repo.py` / `sql_plan_repo.py` / `migrations/20260424_0004_wave9_l3_action_write_cutover_metadata.sql` | Cloud Run `zenos-mcp-00214-puc` 100% traffic；official `/mcp` partner-key full flow OK；new task storage `legacy_tasks=0` / `legacy_task_entities=0` / `entities_base=1` / `entity_l3_task=1` |
| **E03** ✅ | AC compliance test 全綠：`AC-TASK-01..09` + `AC-MCP` 中標為「runtime enforcement」的條目 + 主 SPEC §9 CHECK test（見 §Exit Criteria X7/X7b 排除清單）| `tests/spec_compliance/` | `302 passed, 19 skipped`；修正 stale test 對 frontmatter updated date 的硬編碼，改驗 updated >= review date |
| **E03b** ✅ | 新增 `tests/spec_compliance/test_wave9_ac_status_map.py`：每條 AC 標記 `runtime_enforced | governance_target | pending_wave`；CI 失敗若清單與本 PLAN 不一致 | `tests/spec_compliance/test_wave9_ac_status_map.py` | `tests/spec_compliance` → `304 passed, 19 skipped` |
| **E04** ✅ | Partner key e2e 驗證（create task → handoff → confirm → entity_entries 回饋 → cleanup）| `scripts/smoke_partner_key_e2e.py` | 正式 `/mcp` + real partner API key；create/update/handoff/confirm + entity_entries OK；cleanup 後測試 rows = 0 |

### Phase F — Legacy cleanup（Owner waiver 後直接執行）

**Stable window start（2026-04-24T04:03:34Z）**：Cloud Run `zenos-mcp-00214-puc` route ready 且 E02 write-cutover 100% traffic。Phase F drop 前需以 `scripts/smoke_wave9_legacy_shadow.py --since 2026-04-24T04:03:34Z` 持續確認 legacy shadow 無新增 mutation。

**Owner waiver（2026-04-24）**：使用者確認 ZenOS 目前為 single-user prod-only deployment，允許跳過 2 週等待窗。Phase F 仍需滿足：prod dry-run clean、正式 MCP 先切到 L3-only revision、post-drop partner-key e2e 通過。

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **F01** ✅ | Drop `zenos.tasks.product_id` / `plan_id` / `parent_task_id` 欄位（歸屬已進 parent_id）| `migrations/20260424_0005_wave9_drop_legacy_action_tables.sql` | `zenos.tasks` 已整表 drop；欄位不存在 |
| **F02** ✅ | Drop `task_entities` table | 同 | `to_regclass('zenos.task_entities') IS NULL` |
| **F03** ✅ | `task_blockers` 依 C06 決策執行：drop | 同 | `to_regclass('zenos.task_blockers') IS NULL` |
| **F04** ⚠️ | 刪除 legacy `Task` / `Plan` dataclass（保留 `L3TaskEntity` 等新 class）；刪 Phase B 的 converter | **部分延後**：`Task` / `Plan` 目前仍是 MCP/API DTO contract，不能在 DB cleanup 中硬刪；legacy storage path 已移除 | 另開 API-shape cleanup follow-up；不阻擋 Wave 9 storage 收口 |
| **F05** ✅ | 刪除 `sql_task_repo.py` / `sql_plan_repo.py` 裡對舊 table 的查詢 / dual-write code | infra repo + smoke scripts | runtime repo 不再查 `zenos.tasks` / `zenos.plans`；post-drop MCP e2e OK |
| **F06** ✅ | Drop `zenos.tasks` / `zenos.plans` 本體 table | `migrations/20260424_0005_wave9_drop_legacy_action_tables.sql` | `to_regclass('zenos.tasks') IS NULL`；`to_regclass('zenos.plans') IS NULL` |
| **F07** ✅ | Drop `zenos.legacy_orphan_tasks` 與 `zenos.legacy_parent_chain_warnings` | 同 | `to_regclass(...) IS NULL`；preflight row count 0 |

### Phase G — Post-landing SPEC / ADR / REF 同步

| ID | Title | Files | Verify |
|----|-------|-------|--------|
| **G01** ✅ | 主 SPEC v2 §9 intro block 改寫：刪「當前 runtime 狀態」段落，改為「已於 Wave 9 migration 落地」| `docs/specs/SPEC-ontology-architecture.md` | §9 標記 2026-04-24 已落地 |
| **G02** ✅ | `SPEC-task-governance §1.1` Transitional note 刪除（或改「Wave 9 已完成」歷史註記）| `docs/specs/SPEC-task-governance.md` | status 升 Approved；§1.1 改 L3 subclass runtime |
| **G03** ✅ | `REF-ontology-current-state.md` 清掉所有 runtime-vs-target 警告；§1 axioms 改為事實敘述 | `docs/reference/REF-ontology-current-state.md` | L3-Action 改為 runtime canonical |
| **G04** ✅ | ADR-028 status → Superseded；frontmatter `superseded_by: ADR-048` | `docs/decisions/ADR-028-plan-primitive.md` | status 更新 |
| **G05** ✅ | ADR-044 status → Superseded；frontmatter `superseded_by: ADR-048` | `docs/decisions/ADR-044-task-ownership-ssot-convergence.md` | status 更新 |
| **G06** ✅ | ADR-047 的「partial」部分升為完全 Superseded | `docs/decisions/ADR-047-l1-level-ssot.md` | status 更新 |
| **G07** ✅ | ADR-046 / ADR-032 / ADR-041 同步檢查：若其 runtime 層也已落地（由 `PLAN-data-model-consolidation` 或其他 PLAN 收口），一併改 Superseded | 各 ADR 前頁 | 未改：仍由 `PLAN-data-model-consolidation` / sidecar retrieval canonical 承擔 |
| **G08** ✅ | ADR-048 `supersedes:` 前頁 list 擴充，納入 028 / 044 / 047 等新完成 supersede 的 ADR | `docs/decisions/ADR-048-grand-ontology-refactor.md` | frontmatter list 一致 |
| **G09** ✅ | `refactor-index.md` Wave 9 欄標記 ✅ + 實際 migration 日期 | `docs/refactor-index.md` | 索引更新 |
| **G10** ✅ | 寫 journal：Wave 9 完成摘要（commit SHA + 關鍵決策 + next step）| `mcp__zenos__journal_write` | journal id `53dc3510-cf89-4ad4-983a-f1c57d204343` |

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
- 2026-04-23：A01 升為 **pre-entry investigation**（可在 E3 達標前先行），交付物擴充為 4 件事（Junction 現況 / Milestone 盤點 / handoff_events 位置 / Phase D 上游依賴判定）。A02+ 仍卡 E3 不變。理由：E3 只卡 schema-changing task（需要 entities_base 語意收斂），不卡 read-only 調查；先拿真數據才能拍三項待定決策。
- 2026-04-23：legacy 孤兒 / 斷鏈 task 的載體採 **DB table**（`zenos.legacy_orphan_tasks` + `zenos.legacy_parent_chain_warnings`），不採 journal / runbook-only。理由：
  - DB table 可查詢、可 join、可跨 session 持久；journal / runbook-only 會失去 structured triage state
  - Row count / TTL 可當 ops 指標；Phase F07 drop 條件可量化（row=0 連續 2 週）
  - 建立成本極低（migration 兩張表 ≤20 行 SQL），不值得為省這點成本採非結構化載體
- 2026-04-23（Phase B 完成後拍板的 Phase C pre-decision）：
  - **loss-1 收斂（用戶核可）**：
    - `linked_entities` → 收斂到 `relationships` 表（SPEC §10 canonical, `docs/specs/SPEC-ontology-architecture.md:549`），**不算 loss**
    - 其餘 5 欄位（`created_by / priority_reason / source_type / source_metadata / context_summary`）→ 維持 legacy shadow，Phase B'/C 不搬去 audit_events，不發明新 canonical storage。Phase F 舊表 drop 前再由單獨 architect decision 判定搬 or 放棄
    - **原則**：Phase B' 任務是保 MCP contract byte-equal，不順手發明新 canonical
  - **loss-2 拍板 (b) truncate to date（用戶核可）**：
    - 採 date-only（SPEC §9.4 `due_date date` 與 `L3TaskEntity.due_date: date, "calendar date, not datetime"` 一致）
    - 不改 SPEC 為 timestamptz（會推翻 Wave 9 目標態）
    - Phase C dual-write: L3 path 存 date；legacy Task.due_date 繼續存 datetime；Phase E cutover 切到 date-only 為 SSOT
- 2026-04-23（A01 完成後拍板）：
  - **C06 task_blockers 去留 → DROP**。依據：A01 發現 `zenos.task_blockers` 為 0 row（表存在但完全未使用）；blocked 關係實際走 task.blocked_by 欄位。Phase F03 直接 drop table，無 migration burden。
  - **C04 Milestone 策略 → 獨立 subclass（`entity_l3_milestone`）**。依據：A01 §B — 4 rows goal 現況；SPEC v2 §9.2 多 5 個 milestone-only 欄位（task_status / dispatcher / acceptance_criteria_json / target_date / completion_criteria）；in-place 會讓 entities table 加 sparse NULL 欄位違反 MTI 原則；4 rows migration blast radius 極小。Phase C04 task 改寫為 migration + caller sweep。
  - **handoff_events 存儲 → 方案 B（獨立 `task_handoff_events` 表）**。依據：A01 §C — 17 events total，migration 成本極低；SPEC v2 §9.6 已定義獨立表 DDL；audit queryability 顯著優於 JSONB；MCP contract 可透過 JOIN 填充 `task.handoff_events` 欄位保持外部不變。Phase A02 建 schema 時一併建立此表與 index。
  - **Phase D 上游依賴 → 不卡 ownership plan 整體**，但有條件：
    - `tasks.product_id NOT NULL` 已在 live DB 落地（migration 0003 applied，44/44 tasks 100% 覆蓋）→ D01/D02 backfill 讀取前提已就緒
    - D01/D02 backfill script **走純 SQL**，不走 domain / repo layer，繞過 PLAN-task-ownership-ssot S04/S05 的未完成狀態
    - **若** D01/D02 改走 repo layer，則 S04（domain model 改名）+ S05（repo 純走 product_id）需先完成；在 Phase D 啟動前再決
- 2026-04-23：發現 **cross-plan 任務追蹤落後**（不屬於 Wave 9 scope 但需獨立 triage）：PLAN-task-ownership-ssot 的 S02/S03 MCP task 狀態仍為 todo，但對應 migration `20260422_0002` / `20260422_0003` 已實際 apply 到 live DB。Architect 須提給用戶決定由 ownership plan 的 owner 或 QA 清理。Wave 9 不獨立處理。

## Resume Point

**目前狀態**：done（2026-04-24）。Wave 9 L3-Action migration 已落地到 prod，runtime primary read/write path 為 `entities_base` + L3-Action subclass tables。

**Sign-off verification**：
- Production MCP serving revision：`zenos-mcp-00212-rkb`，100% traffic，URL `https://zenos-mcp-s5oifosv3a-de.a.run.app`。
- DB cleanup：`zenos.tasks` / `zenos.plans` / `task_entities` / `task_blockers` / legacy warning tables 已 drop；`task_handoff_events=235` migrated.
- Smoke：official `/mcp` partner-key full task flow OK after legacy tables were dropped；L3 read smoke 25 tasks + 25 plans，0 mismatch。
- Test suite：full suite green after mock transaction fix for `test_agent_write_visible_to_admin`。

**Follow-ups**：
- F04 is intentionally deferred from Wave 9 storage cleanup: legacy `Task` / `Plan` dataclasses now act as MCP/API DTOs, not legacy DB storage.
- Follow-up task `F04 dataclass/API DTO cleanup` is tracked under this plan: `b44ebc5969864ae486b25b9b6f8f9292`.

**Historical execution log below is kept for provenance.**

**歷史起點**：Active（2026-04-23）。用戶 Gate 決策採 Option A + C：A01 先行，做完再決定是否切 B。

**已完成的 Architect 動作**：
- Wave 9 MCP plan entity 已建立（見下方 `plan_id`）
- A01 L3 task 已建立並 dispatch 給 Developer

**已完成**：
- A01 四段調查 done（2026-04-23；runbook: `docs/runbooks/wave9-preflight-findings.md` + `.findings.csv`）
- 四項待定決策已拍板（見 §Decisions）
- Phase D 上游依賴判定：不卡整體 ownership plan，走純 SQL backfill

**已完成（2026-04-23）**：
- A01 pre-entry investigation done（runbook: `docs/runbooks/wave9-preflight-findings.md`）
- 四項待定決策全部拍板（見 §Decisions）
- **A03 cross-plan check done**：data-model-consolidation S03 只做 `EntityStatus.archived` + preflight dry-run，**不建** `entities_base`——A02 建立 `entities_base` 為該 plan 鋪路，無 schema 衝突
- **Cross-plan triage**（`PLAN-task-ownership-ssot`）完成：S01 QA CONDITIONAL PASS confirmed done；S02/S03 cancelled with covered-by reason；任務追蹤已對齊 runtime
- **Phase B done**：domain dataclass duality 落地。5 new L3 class + converter + governance 三分支
- **Phase B fix done**（review 發現 4 bug 重派修完）：migration 移除 BEGIN/COMMIT；converter partner_id kwarg；parent_id 透過 original hint/heuristic restore；depends_on union with blocked_by。496 pytest PASS
- **Phase B prime done**（BP01-BP08 合併）：application + interface dual-path adapter，採 normalize-to-legacy 策略
- **Phase B prime fix done**（review 發現 4 adapter bug 重派修完）：adapter signature 改 explicit kwargs；移除 dispatcher heuristic；update adapter 翻譯 parent_id + full-replace entity fields
- **Phase B prime third-round fix done**（review 又發現 5 bug 重派修完）：blocked_by 不自動填；MCP ontology links/provenance/attachments 透過 kwargs forward；L3 task/plan create 走 defaultProject product resolution；entity_l3_subtask 補 task_status/priority enum CHECK
- **Phase B prime fourth-round fix done**（review 又發現 4 bug + Architect 自抓 1 hidden bug）：update path 7 MCP mutable kwargs forward；entities_base + 4 subclass + handoff_events composite FK partner-scoped；L3 plan update product/project override；L3 plan update full-replace entry/exit criteria；hardcoded `blocked_by=[]` 在 update path 移除
- **Doc integrity fix done**（外部 review 3 finding 全修，Architect 推翻 reviewer「忽略」標記）：SPEC §8.1 line 285 改 target/runtime 區分語氣；SPEC line 651 DRAFT enum + §15 rule 5 跟 §7.2 L2 lifecycle 對齊；ADR-048 「六份」→「八份」+ 註 task-gov/doc-gov frontmatter 待升 Approved
- **P1-D converter heuristic 殘留 fix done**（外部 review）：`converters.py:l3_entity_to_task` 無 original hint fallback 移除 dispatcher heuristic，agent:* dispatcher 不再被誤分類為 subtask
- **P1-E composite FK delete action fix done**（外部 review）：Cloud SQL PG 16.13 確認，migration 改 `ON DELETE SET NULL (parent_id)` PG 15+ syntax；runbook §E 記錄 PG 版本與決策。smoke test 實跑 production DB zenos_smoke schema 驗證。2513 full suite PASS
- **Infra I01 done**：`scripts/migrate.sh` default 改 prod secret（zentropy-4f7a5 + zenos-database-url）；neondb 確認為 empty legacy；header docstring 明確標記。Phase C 剩 I02（staging DB 建立）
- **A02+A04+A05 done**：`migrations/20260423_0004_wave9_l3_action_preflight.sql`（162 lines, 6 table + 1 index, DDL 對齊 SPEC v2 §9）。Production DB gate 實測 task_entities=578 rows (A01 proxy 推算 133 低估 4.3×)、tasks=634 rows、孤兒 row=0、task_blockers=0。Runbook §E 新增
- **Infra I02 done（2026-04-24）**：
  - 同一 Cloud SQL instance `zentropy-db` 內建立獨立 database `zenos_staging`
  - 建立 Secret Manager secret `zenos-staging-database-url`
  - `scripts/migrate.sh` 新增 `--target prod|staging`
  - `scripts/run_sql_migrations.py` 新增 `--only` / `--exclude`，避免 prod 仍 pending 的 unrelated `20260423_0003_drop_legacy_document_tables` 被誤套
  - staging baseline 已套到 prod 已套用水位（排除 `0003/0004`），再正式 apply `20260423_0004_wave9_l3_action_preflight`
  - prod 已透過正式 runner path 單獨 apply/mark `20260423_0004_wave9_l3_action_preflight`，schema_migrations 記錄存在
  - staging/prod schema 驗證：`entities_base`、`entity_l3_milestone`、`entity_l3_plan`、`entity_l3_task`、`entity_l3_subtask`、`task_handoff_events` 均存在
- **Phase C01/C02 done（2026-04-24）**：
  - `SqlTaskRepository.upsert` 在既有 transaction 內 dual-write legacy `zenos.tasks` + new `entities_base/entity_l3_task`
  - L3 base row `parent_id` 暫留 `NULL`，避免 Phase D 前因 product/plan 尚未進 `entities_base` 而觸發 FK；D01/D02 負責正式 backfill
  - 新增 `ZENOS_L3_READ_NEW_PATH`，預設 off；開啟後 `get_by_id` / `find_by_id_prefix` / `list_all` / `list_blocked_by` / `list_pending_review` 從 L3 task path 讀，並 left join legacy task 補齊過渡期欄位
- **Phase C03 done（2026-04-24）**：
  - `SqlPlanRepository.upsert` 改為 transaction-wrapped dual-write legacy `zenos.plans` + new `entities_base/entity_l3_plan`
  - Plan read path 共用 `ZENOS_L3_READ_NEW_PATH`，預設 off；開啟後 `get_by_id` / `list_all` 從 L3 plan path 讀，並 left join legacy plan 補齊過渡期欄位
- **Phase C04/C05/C06 done（2026-04-24）**：
  - Subtask dual-write 落地：`Task.parent_task_id` 存在時寫 `entities_base(type_label='subtask')` + `entity_l3_subtask`，並清 stale `entity_l3_task`
  - Milestone dual-write 落地：legacy `Entity(type='goal')` 仍寫 `zenos.entities`，同 transaction 內鏡像到 `entities_base(type_label='milestone')` + `entity_l3_milestone`
  - `task_entities` 過渡 dual-write 落地：task mutation 會以 savepoint guard 同步 `relationships(type='related_to')`；目前 legacy `relationships` FK 仍可能指向 `zenos.entities`，完整 row parity 留到 Phase D/E schema cutover 後驗證
  - `task_blockers` 決策完成：A01 確認 0 row，Phase C 不改 runtime read；direct drop 併入 Phase F03 legacy cleanup
- **Phase D01/D02/D03/D03a implementation done（2026-04-24）**：
  - 新增 `scripts/backfill_l3_action_parent_id.py`：純 SQL dry-run/apply；會鏡像 legacy entities/plans/tasks/goals 到 `entities_base` + L3 subclass tables，並設定 task/plan/milestone parent_id
  - parent rule：subtask → `parent_task_id`；task → `plan_id` else `product_id`；plan → `product_id`；milestone → legacy `goal.parent_id`
  - 新增 `migrations/20260424_0001_wave9_legacy_action_shadow_tables.sql`：`legacy_orphan_tasks` + `legacy_parent_chain_warnings`
  - Runtime dual-write 更新：task/plan/milestone 新寫入開始帶 parent_id，不再新增 NULL parent_id
  - D03 runtime wiring：task create/update 會對 parent task / plan 的 parent chain 終點做 `product_id` guard；壞鏈回 `INVALID_PARENT_CHAIN`；plan update 與 MCP plan handler 也會保留 machine-readable error code
- **Phase D04/D05 prod apply done（2026-04-24）**：
  - 用戶決策：只有 prod，直接 prod dry-run clean 後 apply；不走 staging
  - 先 apply `20260424_0001_wave9_legacy_action_shadow_tables.sql`
  - prod 實際 schema 發現 `entity_l3_*` subclass tables 仍是舊 single-column shape（0 rows）；補 `20260424_0002_wave9_l3_action_composite_schema_upgrade.sql`，guard 確認 L3 tables 全空後 drop/recreate composite schema
  - backfill dry-run：tasks 646 scanned / 646 resolvable / 0 orphan；plans 77；milestones 4
  - backfill apply：`entities_base=1059`、`entity_l3_plan=77`、`entity_l3_task=610`、`entity_l3_subtask=36`、`entity_l3_milestone=4`、`legacy_orphan_tasks=0`、`legacy_parent_chain_warnings=0`
  - post-apply verify：Action rows with `parent_id IS NULL` = 0；`task_status='review' AND result IS NULL` = 0
  - D05 apply `20260424_0003_wave9_validate_l3_action_checks.sql`；prod constraint `entity_l3_task_review_needs_result.convalidated = true`
- **Phase D03 runtime wiring done（2026-04-24）**：
  - task create/update 對 parent task / plan 缺 `product_id` 的壞鏈回 `INVALID_PARENT_CHAIN`
  - plan update 新增 `PlanValidationError(error_code=INVALID_PARENT_CHAIN)`；plan MCP handler 支援帶 `error_code` 的標準 error envelope
  - governance guide task rules 補 `INVALID_PARENT_CHAIN`
  - regression：`tests/infrastructure/test_sql_repo.py tests/application/test_task_plan_fields.py tests/application/test_plan_service.py tests/interface/test_task_response_parity.py tests/spec_compliance/test_task_ownership_ssot_ac.py` → 195 passed
- **Phase E01 prod-only smoke + 10% ramp（2026-04-24）**：
  - 新增只讀 smoke：`scripts/smoke_l3_read_new_path.py`，比對同一批 task/plan 在 legacy read path 與 `ZENOS_L3_READ_NEW_PATH=1` 的 stable fields
  - 首次 prod smoke 失敗：`status/result/dispatcher` drift；re-run `backfill_l3_action_parent_id.py --dry-run` clean（646/646 resolvable, 0 orphan）後 apply 重同步，`status/result` drift 收斂
  - 修正 transitional L3 read：`dispatcher` 由 `COALESCE(t.dispatcher, NULLIF(l3.dispatcher, 'human'))` 補 legacy explicit `"human"`，避免 `human → None` 外部行為差異
  - 部署 Phase C/D runtime 到 prod：Cloud Run `zenos-mcp-00206-q22` 100% serving；final backfill dry-run clean（647/647 resolvable, 0 orphan）後 apply
  - 重跑 prod smoke：25 tasks + 25 plans，0 mismatch
  - 建立 no-traffic flag-on revision `zenos-mcp-00207-6h4`（同 image，`ZENOS_L3_READ_NEW_PATH=1`），確認 env/secrets preserved
  - Traffic split：`zenos-mcp-00207-6h4=10%`、`zenos-mcp-00206-q22=90%`
  - Immediate dogfood：MCP `search(tasks)` / `search(entities)` OK；Cloud Run ERROR log（20m）= `[]`
- **Phase E01 100% cutover + E04 partner-key e2e done（2026-04-24）**：
  - 修正 observation 期間發現的非 L3 runtime error：`work_journal_summary_check`。`SqlWorkJournalRepository` 在 insert 前 trim + clamp summary 到 DB constraint，空白摘要改 fallback；journal repo/tool tests 26 passed
  - 部署新版 runtime image `sha256:bf4a9fc2183fbe3a09fa9c48e99b59e494ac69a5fd1ac714c85580bf14e66f77`
  - 重新建立 flag-on revision `zenos-mcp-00209-9qd`，traffic ramp 到 100%
  - 100% 後 L3 smoke：25 tasks + 25 plans，0 mismatch；Cloud Run ERROR log = `[]`
  - 新增 `scripts/smoke_partner_key_e2e.py`：用 real partner API key 連正式 `/mcp`，不輸出 key
  - E04 full flow：`search` OK；`journal_write` OK；task create → update in_progress → handoff `agent:qa` → confirm accepted + `entity_entries` OK；direct DB cleanup 後 `tasks/entities_base/entity_l3_task/entity_entries/task_entities/task_handoff_events` 測試 rows 全為 0
- **Phase E03 AC compliance done（2026-04-24）**：
  - `tests/spec_compliance` → `302 passed, 19 skipped`
  - `test_ac_task_upg_09_related_spec_review_passed` 修正：frontmatter `updated` 應允許晚於 2026-04-19 的合法後續修訂，仍要求 changelog review note 存在
- **Phase E02 write cutover done（2026-04-24）**：
  - 補 migration `20260424_0004_wave9_l3_action_write_cutover_metadata.sql`：把 MCP contract metadata 搬進 `entity_l3_task` / `entity_l3_subtask` / `entity_l3_plan`，並把 `relationships` FK 從 legacy `entities` 改指 `entities_base`
  - `SqlTaskRepository` / `SqlPlanRepository` 新增 `ZENOS_L3_WRITE_NEW_PATH`；flag on 時停止寫 legacy `zenos.tasks` / `zenos.plans` / `task_entities`，legacy tables 進入 read-only shadow
  - prod migration dry-run clean 後 apply；post-apply verify：metadata backfill missing=0，`relationships` base FK=2、legacy FK=0
  - 部署 image `sha256:39d03d1d351d42157981178aa89b265b2a10a0299fe3ee1dacf5c4b737e12443`；Cloud Run `zenos-mcp-00214-puc` 設 `ZENOS_L3_READ_NEW_PATH=1` + `ZENOS_L3_WRITE_NEW_PATH=1`，traffic 100%
  - 官方 `/mcp` partner-key full flow OK；storage 檢查：`legacy_tasks=0`、`legacy_task_entities=0`、`entities_base=1`、`entity_l3_task=1`；cleanup=true
  - 100% 後 L3 smoke：25 tasks + 25 plans，0 mismatch；Cloud Run ERROR log since route ready = `[]`
- **Phase E03b AC status map done（2026-04-24）**：
  - 新增 `tests/spec_compliance/test_wave9_ac_status_map.py`
  - 固定分類：runtime-enforced ACs、governance-target ACs（`AC-TASK-10`、`AC-MCP-20/21/31`）、pending_wave 空集合
  - regression：`tests/spec_compliance` → `304 passed, 19 skipped`
- **Phase F gate monitor ready（2026-04-24）**：
  - 新增 `scripts/smoke_wave9_legacy_shadow.py`，用 E02 route-ready timestamp 檢查 legacy `zenos.tasks` / `zenos.plans` / `task_entities` 是否仍 read-only
  - 首跑結果：`legacy_tasks_created=0`、`legacy_tasks_updated=0`、`legacy_plans_created=0`、`legacy_plans_updated=0`、`legacy_task_entities_created=0`

**歷史下一步（已完成）**：
1. Phase F / G 已由 owner waiver 解除 2 週等待窗後完成；本段保留為 E02 當時斷點記錄。

**跳過的 task**：Phase F03 的 `task_blockers` 改為 direct drop（C06 決策合併進 Phase F）。

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
