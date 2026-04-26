---
type: PLAN
id: PLAN-zenos-dogfooding-loop
status: Active
created: 2026-04-19
related:
  - docs/decisions/ADR-010-entity-entries.md
  - docs/decisions/ADR-042-entry-source-tiering.md
  - docs/plans/HANDOFF-2026-04-19-entry-governance-findings.md
  - skills/release/governance/
  - skills/release/zenos-governance/SKILL.md
---

# PLAN: ZenOS Dogfooding Loop — 自我治理與改進閉環

## 目標

建立一個 agent 自驅的治理/改進閉環，讓 MCP + skill 能透過「真實使用→偵測缺口→修補→驗證」持續迭代，逐步逼近三大目標：

1. Agent 更快、更少 token 拿到有用 context
2. 主動治理讓知識圖譜越來越完整（支持 #1）
3. 跨用戶/跨 agent 同一套 context 可用（CRM/marketing 已達標，繼續守住）

## 硬約束（不可動）

- **Capture/治理入口必須保留人為觸發**（`/zenos-capture`、`/zenos-governance`）
- **毀滅性操作不得暴露為 MCP tool**
- **部署後必須端到端驗證**
- 本 loop 的「producer agent」也必須走 human-trigger 路徑（由 orchestrator 當人）

## 四種被治理的 entity 類型

（假設四種 = L2 entity + L3 document + L3 task + L3 blindspot。如需調整請更新此節。）

### Type 1: L2 entity（module，含 entries）

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| summary 準確度 | 反映當前實作，不超過 300 字 | 漂移偵測 → review task |
| 四維 tags 完整 | domain/role/time/impact 各至少 1 | 缺欄位 → review task |
| relationships | ≥ 2 條（通常 impacts / depends_on） | 孤兒節點 → propose 關聯 |
| entries per partner+dept | ≤ 20 active | saturation → consolidate（ADR-010） |
| entries 品質 | 無 9 類 anti-pattern（capture-governance） | 手動稽核 protocol |
| entity 粒度 | 主題數 ≤ 3 | entries ≥ 30 或主題 ≥ 5 → 拆分建議 |

**產生路徑**：L2 三問通過 → `write(entity)` → `confirm`
**更新路徑**：summary 或 tag 漂移 → architect review
**消亡路徑**：merged into another entity（status=archived + merge_target）

### Type 2: L3 document

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| source.uri | 真實可達 | 定期驗證 → stale |
| linked_entity_ids | ≥ 1 個合法 L2 | 孤兒 document → propose 關聯或 archive |
| 新鮮度 | source 檔案 last-modified 無巨幅落差 | sync 偵測 → mark stale |
| 去重 | 同 URI 無多筆 | write 時 query by uri 先 |

**產生路徑**：capture 發現值得建語意代理 → `write(document, confirmed_by_user=false)` → user confirm
**更新路徑**：source 變更 → sync mark stale → 重 capture
**消亡路徑**：source 刪除 或 linked_entity 全 archived → archived

### Type 3: L3 task

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| owner / assignee | 至少一方有值 | 缺 → reject 建立 |
| AC | 2-5 條可觀察 | 不符 → reject |
| 狀態流動 | todo → in_progress → review → done 不卡 | 7 天無進展 → stale flag |
| linked_entities | 1-3 個合法 L2 | 缺 → `[Ontology Gap]` 標記 |
| review→done | 走 `confirm(accepted=True)` | 直接 update 到 done → reject |

**產生路徑**：8 題 checklist → `write(task, status=todo)`
**更新路徑**：`task(action=update)` 改狀態；`confirm` 驗收
**消亡路徑**：done（confirm accepted）或 cancelled（帶 reason）

### Type 4: L3 blindspot

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| severity | red/yellow/green 合理 | LLM / 手動判斷 |
| related_entity_ids | ≥ 1 | 缺 → 不得建立 |
| suggested_action | 可執行（非抽象口號） | 太抽象 → review |
| 狀態流動 | open → acknowledged → resolved | resolved 後存查，不刪 |

**產生路徑**：capture / analyze(blindspot) 推斷 → `write(blindspot, status=open)`
**更新路徑**：ack / resolve 時附 linked_task_id 或 resolution_note
**消亡路徑**：resolved；或 stale（30 天未動且 severity=green）

## Dogfooding Loop 架構

三個角色 + 閉環機制：

```
┌─────────────────────────────────────────────────────────────────┐
│  Orchestrator (main Claude session) — 監控閉環、決定停/修/續      │
│                                                                 │
│   ┌───────────────────┐             ┌───────────────────┐      │
│   │ Producer subagent │  → writes → │  ZenOS Ontology   │      │
│   │  扮演用戶觸發      │             │  (MCP server)     │      │
│   │  capture/task     │             └───────────────────┘      │
│   └───────────────────┘                      ↑                 │
│            ↑                                 │                 │
│            │ 任務場景                        │ reads            │
│            │ (從 journal log                 │                 │
│            │  + git log 抽)                  │                 │
│            │                         ┌───────────────────┐    │
│            └─────────────────────────│ Monitor subagent  │    │
│                                      │ 跑 per-type 健康  │    │
│                                      │ 檢查 + diff       │    │
│                                      └───────────────────┘    │
│                                              ↓                 │
│                                      health report            │
│                                              ↓                 │
│            ┌──────────────────────────────────────────┐        │
│            │ Orchestrator 決策：                       │        │
│            │ - 健康 → 進下一 iteration                 │        │
│            │ - 缺口 → 定位 MCP/skill，修、部署、重測   │        │
│            │ - 改動寫回 ADR/journal                    │        │
│            └──────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### Producer subagent

**職責**：模擬真實用戶觸發 capture / task confirm。不得直接 write ontology（必須走 skill 入口，維持 human-trigger 約束）。

**輸入**：
- 場景（orchestrator 指定，例如「CRM agent 剛完成一通客戶電話的摘要」）
- 來自 journal log 的真實 capture 歷史（抽樣重放）
- 來自 git log 的真實 commit 主題（不直接產 entry，但提供場景素材）

**輸出**：
- 觸發 `/zenos-capture` 或 `confirm(task, entity_entries=...)` 的 session
- Session log（tools called、tokens、timeouts）

**關鍵紀律**：必須用 release skills 同一份 SSOT，不自寫內部規則。

### Monitor subagent

**職責**：對四種 entity 類型跑健康檢查，產出 diff report。

**檢查項（per iteration 全跑）**：

| 檢查 | 實作 |
|---|---|
| L2 entries saturation | `search(collection=entries, entity_id=X)` 逐 entity（需 MCP 支援，iteration 1 要補） |
| L2 孤兒 | `analyze(check_type=quality)` 或自定 SQL |
| L3 document staleness | `analyze(check_type=staleness)` |
| Task stuck | `search(collection=tasks, status=todo)` + age filter |
| Blindspot 過期 | `search(collection=blindspots, severity=green)` + 30d filter |
| Anti-pattern entries | 遍歷 entries + 9 類判準 matcher |

**輸出**：結構化 diff report（JSON），對照 producer 這一輪的輸入預期與實際產出。

### Orchestrator（我）

**職責**：
1. 啟動 producer（指定場景）
2. 讓 producer 跑完
3. 啟動 monitor
4. 讀 monitor report，比對「預期」與「實際」
5. 若缺口：
   - 定位缺口在 MCP（tool 缺 / 參數缺 / 行為錯）還是 skill（prompt 不對 / 判斷規則過時）
   - 最小改動 + 本地測試 + deploy（走 `./scripts/deploy_mcp.sh` 或 `./scripts/deploy.sh`）
   - 端到端驗證：同場景重跑 producer → monitor 應通過
   - 寫 ADR（結構決策）或 journal（戰術調整）
6. 若健康：紀錄 baseline，進下一 iteration

**停機條件**：
- 連續 3 個 iteration 同一缺口修不好 → 升級為人工介入 task
- 部署失敗 → 停，通知用戶
- 改動觸到硬約束（改 capture 觸發模型、毀滅性 tool）→ 停，require 確認

## 基線：過去一個月 capture 紀錄

**收集方式**：
```
journal_read(flow_type="capture", since="2026-03-19")
→ 統計：總次數、平均 tokens、每次產出 entries/documents/blindspots 數
→ 分類主題（CRM / marketing / zenos-core / paceriz / 其他）
```

**用途**：
1. Producer 的「場景庫」來源（重放真實場景）
2. 測量 loop 改進後，同場景 token/call 降多少
3. 找出過去 1 個月反覆踩的 friction（例如今天發現的 `get(entries) 5 條上限`）

## Iteration 協議

```
每個 iteration 有唯一 ID：DF-{YYYYMMDD}-{N}

Step 1. Orchestrator 選場景（from 基線庫）
Step 2. Producer 執行，log to /tmp/zenos-dogfood/{DF-ID}/producer.jsonl
Step 3. Monitor 執行，log to /tmp/zenos-dogfood/{DF-ID}/monitor.json
Step 4. Orchestrator 產 decision：
   {
     "df_id": "DF-20260419-1",
     "gap": "search(entries) 無 entity_id filter",
     "fix": "src/zenos/interface/mcp/search.py 加 entity_id 參數",
     "deploy": "scripts/deploy_mcp.sh",
     "verify_scenario": "重跑 audit 訓練計畫系統 entries",
     "outcome": "keep|revert"
   }
Step 5. 若 keep，寫 entry via `confirm(task, entity_entries=[...])` 走 Tier 1
         若 revert，寫 journal(flow_type=governance, summary="tried X, reverted because Y")
Step 6. 回 Step 1
```

**每 iteration 預算**：
- Producer：≤ 5 tool calls
- Monitor：≤ 10 tool calls
- Orchestrator 修補：≤ 15 min 或跨 session

## 成功指標

### 短期（iteration 1-10）

- 每 iteration 至少解一個 friction 或驗證一個假設
- 今天列出的三大 friction（A/B/C）全部解掉
- 基線庫建好

### 中期（iteration 10-30）

- 重放過去 1 個月任一 capture 場景 → token 降 30%+
- Monitor 可偵測 4 種 entity 的全部健康維度
- 至少一次「發現 ADR 規則過時 → 更新 ADR」

### 長期（iteration 30+）

- 新用戶接 ZenOS 後，第一週 agent 自動完成 5 次以上治理閉環（不需人工 debug）
- 跨用戶 Tier 1 entry 共享機制啟用（ADR-042 延伸議題）

## 與現有 skill 的邊界

- `zenos-capture` / `zenos-governance`：保留人觸發，producer 透過 subagent spawn 當作「人」
- `zenos-sync`：不在 loop 內直接用（entries 已退出其路徑）
- 新 MCP tool：如果 iteration 發現需要，走 ADR → implement → deploy → 回 loop

## 啟動前缺的東西

本 loop 跑起來前要先補：

1. **Per-entity-type 健康檢查 API**（Monitor 用）
   - `search(collection=entries, entity_id=X, limit=200)` ← 今天發現缺
   - `analyze(check_type="entity_audit", entity_id=X, dry_run=True)` 單 entity 模式
2. **session log hook**（producer / monitor 都要）
3. **Baseline 庫建構**（journal_read 抽過去 1 個月）

這三項是 iteration 1-3 的工作。

## Open Questions

1. Monitor 偵測到缺口時，orchestrator 自動修 vs 先 escalate？目前設計是「明顯缺陷自動修，結構性改動 escalate」——但邊界需要實跑幾次才能畫清
2. 四種 entity 是否涵蓋完整？relationships / protocols / project 要不要也納入？
3. Producer 需要多真實？完全重放歷史 vs 合成場景 vs 混合？
4. Orchestrator 跨 session 記憶：每次 iteration 重開 session 還是長跑？長跑有 context bleed，短跑缺連續性

## Iteration Log

### DF-20260424-1

- Scenario: 在 `Dogfood Test Product` 下建立 L2 `Dogfood MCP Friction Log`，再建立修復 task，模擬新用戶在測試 L1 內治理 MCP/skill 摩擦。
- Findings:
  - `write(collection="entities")` 的 module fuzzy duplicate guard 跨 product 比對，導致 Dogfood L1 被 ZenOS 正式 L2 `MCP 介面設計` 誤擋。
  - `task(action="create")` 未傳 `linked_entities` 或傳 `[]` 時，GovernanceAI auto-infer 出不存在 ID 會被當成 caller 錯誤 reject。
  - `scripts/deploy_mcp.sh` 建出 revision 後沒有把 traffic 切到新 revision；需另行檢查 traffic split。
  - `write` 成功後 response 對 agent 不直覺：直接讀 `data.id` 得到 null，需後續檢查 machine-readable shape。
- Fix:
  - `src/zenos/application/knowledge/ontology_service.py`：module fuzzy candidates 限定同 `parent_id`。
  - `src/zenos/application/action/task_service.py`：auto-inferred missing linked entity IDs 改為 warning，不 reject；caller 顯式提供的 missing ID 仍 reject。
  - `src/zenos/interface/mcp/task.py`：service warnings 串回 MCP response。
- QA:
  - Developer focused tests: `118 passed` + `52 passed`。
  - QA verdict: PASS，無 Critical/Major。
- Deploy:
  - `./scripts/deploy_mcp.sh` 建出 `zenos-mcp-00213-pcm`，但 traffic 仍在舊 revision。
  - 手動 `gcloud run services update-traffic ... --to-revisions=zenos-mcp-00213-pcm=100` 後正式 `/mcp` 驗證通過。
- Production verification:
  - Partner-key smoke: search + full task flow + cleanup OK，`tool_count=19`。
  - Exact `write` retry: `status=ok`，建立 `Dogfood MCP Friction Log` (`1b07c1679c08490db2b688ba82347afe`)。
  - Exact `task` retry: `status=ok`，建立並 confirm task `c14f2797e4a24a999f9e424a0278fcf0`。
- Resume Point:
  - 下一輪優先處理 deploy script traffic verification，或修 `write` response shape 讓 agent 可直接取得 created entity id。

### DF-20260424-2 / DF-20260424-3

- Scenario: 延續 DF-20260424-1 的部署後摩擦，修補 MCP deploy gate 與 `write(collection="entities")` 成功 response shape。
- Findings:
  - `scripts/deploy_mcp.sh` 第一版 traffic gate 使用 `latestReadyRevisionName`，無法保證指向剛建出的 revision。
  - 修成 `latestCreatedRevisionName` 後，第二個 bug 浮現：`gcloud --format='csv[no-heading](status.traffic...)'` 對 repeated traffic fields 會壓成單列，導致已成功切流量仍被誤判失敗。
  - `write(collection="entities")` 成功 response 原本把 entity id 放在 `data.entity.id`，agent 直覺讀 `data.id` 會得到 null。
  - 同 product 下相似 L2 被 duplicate guard 擋住是正確行為；後續 smoke 應使用 update existing entity 或唯一名稱。
- Fix:
  - `scripts/deploy_mcp.sh`：target revision 優先用 `status.latestCreatedRevisionName`，fallback 才用 `latestReadyRevisionName`。
  - `scripts/deploy_mcp.sh`：traffic parser 改用 `--format='json(status.traffic)'` + Python stdlib JSON parsing；驗證 target revision `percent=100`。
  - `src/zenos/interface/mcp/write.py`：entity write response 保留 `data.entity`，並 mirror `id/name/type/level/status/parent_id/entity_id/entity_name` 到 `data` top-level。
- QA:
  - DF-20260424-2 QA PASS：deploy target revision contract + write response mirror。
  - DF-20260424-3 QA PASS：JSON traffic parser + latestCreated target preserved。
- Deploy:
  - `./scripts/deploy_mcp.sh` 第二次實跑成功，target `zenos-mcp-00215-sj2`，traffic 100%，script 自身 validation PASS。
- Production verification:
  - Deployed `/mcp` update existing `Dogfood MCP Friction Log` returned `data.id = data.entity_id = data.entity.id = 1b07c1679c08490db2b688ba82347afe`.
- Resume Point:
  - 下一輪可處理 `journal_write` latency（本輪上次曾 160 秒）與 smoke naming ergonomics，或繼續測 `confirm(entity)` 將 Dogfood L2 從 draft 升 active 的流程。

### DF-20260424-4

- Scenario: 嘗試把 `Dogfood MCP Friction Log` 從 draft confirm 成 active，驗證 L2 lifecycle、impacts 關聯與錯誤引導是否順。
- Findings:
  - `confirm(collection="entities")` 正確拒絕沒有 concrete impacts 的 L2，錯誤訊息有指示 `write(collection="relationships")` 補 impacts。
  - 按指示用 `write(collection="relationships")` 建立 `Dogfood MCP Friction Log -> MCP 介面設計` impacts 時，MCP 直接回 raw DB FK error：`source_entity_id` 不存在於 `entities_base`。
  - 根因初判：`SqlEntityRepository.upsert()` 只寫 `entities`，目前只有 `goal` 透過 `_upsert_l3_milestone()` 額外寫 `entities_base`；但 `relationships` FK 已指向 `entities_base`，導致新建 L2 module 無法建 edge。
- Fix:
  - `src/zenos/infrastructure/knowledge/sql_entity_repo.py`：Developer 修 `SqlEntityRepository.upsert()` 對非-goal Entity 維護 `entities_base` row；goal 繼續走 milestone subclass path。
  - `migrations/20260424_0006_entities_base_legacy_entity_backfill.sql`：補 production 舊資料 backfill，避免既有 L1/L2/L3 legacy rows 缺 `entities_base`。
  - `src/zenos/application/knowledge/ontology_service.py`：`impacts` relationship description 必須是 concrete 格式（`A 改了什麼 → B 的什麼要跟著看`）；同 source/target/type 重寫 description 時更新 existing edge，不新增 duplicate。
- QA:
  - FK/base-row 修復 QA PASS，Critical/Major 無。
  - impacts validation + duplicate update + migration static test QA PASS，Critical/Major 無。
- Deploy:
  - Migration dry-run：只 pending `20260424_0006_entities_base_legacy_entity_backfill`。
  - Migration apply：成功套用 `20260424_0006_entities_base_legacy_entity_backfill.sql`。
  - MCP deploy：`zenos-mcp-00216-snl` 上線 FK/base-row 修復；`zenos-mcp-00217-jw4` 上線 impacts validation/dedup update，traffic gate 100% PASS。
- Production verification:
  - `write(collection="relationships")` 建立/更新 `Dogfood MCP Friction Log -> MCP 介面設計` impacts edge 成功。
  - `confirm(collection="entities", id_prefix="1b07c167")` 成功，Dogfood L2 變 `active` 且 `confirmed_by_user=true`。
- Resume Point:
  - 下一輪繼續測 `analyze(check_type="health", entity_id=Dogfood)` scope 行為、journal latency，或走一輪 task -> entry -> stale/impact propagation。

### DF-20260424-5

- Scenario: 對 `Dogfood Test Product` 執行 `analyze(check_type="health", entity_id=...)`，驗證 scoped health 是否能給測試 L1 可用治理訊號。
- Findings:
  - 原 production 回傳整個 workspace health，沒有 scope echo；Dogfood L1 被 global `llm_health=red` 與 workspace KPI 汙染，對 dogfood 不可用。
  - 第一版修復被 QA 擋下：scoped relationships 收進 cross-scope impacts edge，但沒有把外部 target entity 帶進 item 13 validity context，會把合法 external active target 誤判 `target_missing`。
- Fix:
  - `GovernanceService.compute_health_signal(entity_id=...)`：支援 root + parent_id subtree scope，scope 內計算 entities/documents/protocols/blindspots/relationships，並回傳 `scope` metadata。
  - Scoped health 排除 global-only `llm_health`，且不寫 dashboard health cache；global health 保留原行為。
  - `run_quality_check(..., impact_target_context_entities=...)` 與 `check_impacts_target_validity(..., target_context_entities=...)`：外部 target 可用於 impacts target validity，但不會被當成 scoped source module。
- QA:
  - 第一輪 QA FAIL：cross-scope target context 缺失。
  - 補修後 QA PASS：`scoped -> external` 合法通過，`external -> ghost` 不污染 scoped health；global check 仍會抓到 external broken edge。
- Deploy:
  - MCP deploy 成功，serving revision `zenos-mcp-00218-h7j`，traffic 100%。
- Production verification:
  - `analyze(check_type="health", entity_id="82f81abf483e49bdbdfba66e51c8e019")` 回傳 Dogfood scope：
    - `overall_level=green`
    - `quality_score=88`
    - `active_l2_missing_impacts=0`
    - `scope.entity_count=7`
    - `scope.relationship_count=10`
    - `scope.global_signals_excluded=["llm_health"]`
  - `analyze(check_type="health")` 全域仍回 workspace red，保留 `llm_health` red。
- Resume Point:
  - 下一輪可測 `analyze(check_type="quality", entity_id=Dogfood)` 是否也需要 scope，或走 task -> entry -> stale/impact propagation。

### DF-20260424-6

- Scenario: 檢查 L3 document entity 是否真的支援一對多 L2 linkage、native md / delivery snapshot，以及 MCP 是否能把文件當穩定知識入口使用。
- Findings:
  - `upsert_document()` 已有一對多雛形：`linked_entity_ids[0] -> parent_id`，其餘 link 會 materialize 成 `related_to` relationships。
  - 但 `search(collection="documents")` 的 `entity_name` / `product_id` filter 仍只看 `parent_id`，所以多 L2 doc 在 MCP 查詢面不可靠。
  - `detect_stale_documents_from_consistency()` 只看 `parent_id` / `part_of`，忽略 `related_to`，document governance 不會把 secondary L2 當一等 linkage。
  - `get(collection="documents")` 與 `write(collection="documents")` 成功 response 沒有穩定回傳 canonical `linked_entity_ids` / primary / related split，agent 需要自行推斷。
  - Native md 方向已由 `SPEC-docs-native-edit-and-helper-ingest` + delivery API 覆蓋，但 production dogfood 發現 `write(documents)` 的 `SourceType` enum 漏收 `zenos_native/local`，導致 validator 支援但 MCP 寫入拒絕。
- Fix:
  - 新增 `src/zenos/domain/document_linkage.py` 作為 L3 document linkage SSOT：`Document.linked_entity_ids`、`Entity.parent_id`、outgoing `part_of`、outgoing `related_to` 會被正規化成同一個 ordered/deduped list。
  - `search(collection="documents")`：`entity_name` 與 `product_id` filter 改用 canonical linked IDs；response 直接回 `linked_entity_ids`、`primary_linked_entity_id`、`related_entity_ids`、`linked_entities`。
  - `get(collection="documents")`：補上 canonical linkage fields 與 linked entity names。
  - `write(collection="documents")`：成功 response 補上 normalized multi-linkage fields，避免 agent 寫完仍不知道 secondary links 是否生效。
  - `detect_stale_documents_from_consistency()`：document consistency grouping 改走 canonical linkage helper，`related_to` 成為一等文件 linkage。
  - `SourceType` enum 補上 `zenos_native` / `local`，讓 MCP `write(documents)` 與 source URI validator contract 一致。
  - `read_source(zenos_native)`：若 doc entity 找得到但尚無 revision，回 `SNAPSHOT_UNAVAILABLE` + Dashboard 儲存提示，不再誤報 document not found。
- QA:
  - Focused regression：13 passed。
  - Interface + governance loop suite：238 passed。
  - Native md / delivery regression：26 passed。
  - QA agent verdict：PASS，Critical/Major 無；指出 service materialization test 與 guest secondary-link visibility 兩個 minor。
  - 補修後 regression：`tests/interface/test_tools.py tests/domain/test_governance_feedback_loop.py tests/application/test_validation.py` → 352 passed。
  - Native source enum 補修後 regression：365 passed。
  - `read_source(zenos_native)` 補修後 regression：381 passed。
- Deploy:
  - MCP deploy `zenos-mcp-00219-6xp`：上線 canonical linkage。
  - MCP deploy `zenos-mcp-00220-nbk`：上線 `zenos_native/local` SourceType enum。
  - MCP deploy `zenos-mcp-00221-zwz`：上線 `read_source(zenos_native)` error semantics。
- Production verification:
  - `write(collection="documents")` 成功建立 `DF-20260424-6 L3 Document Multi-Link Native Smoke` (`09332173558041a4bdca54709e5092a9`)。
  - Created doc source type：`zenos_native`，uri `/docs/DF-20260424-6-l3-doc-linkage`。
  - `write` / `get` / `search(entity_name=Dogfood MCP Friction Log)` / `search(entity_name=訂單履約流程)` / `search(product_id=Dogfood Test Product)` 均回同一份 doc，且 `linked_entity_ids=["1b07...","e3d..."]`、`primary_linked_entity_id="1b07..."`、`related_entity_ids=["e3d..."]`。
  - `read_source(doc_id=0933...)` 在目前 Codex MCP persistent session 仍回舊版 `Document not found`，推斷現有 MCP 連線未重連至 `00221-zwz`；新語意已用本地 regression 覆蓋，需下輪新 MCP session 再做 production smoke。
- Resume Point:
  - 下一輪開新 MCP session 後先重測 `read_source(doc_id=09332173558041a4bdca54709e5092a9)`，應回 `SNAPSHOT_UNAVAILABLE` 而不是 `Document not found`；再補 Dashboard native revision 端到端驗證。

### DF-20260424-7

- Scenario: 重新整理 L3 doc entity 的資料治理，驗證「找到 L2 後，agent 能先讀 L3 summary 判斷有哪些文件可用」是否順暢。
- Findings:
  - 舊 L3 docs 多半是一檔一 entity 或只有薄 summary，agent 找到 L2 後仍要自己猜哪些 source 該讀。
  - `doc_role=index` / `bundle_highlights` 已存在，但治理規則沒有明確要求 `summary` 是文件群 retrieval map。
  - MCP `search(collection="documents")` 沒有明確把 current formal index doc 排在一般 single/draft doc 前面。
  - Dogfood 時誤把 `product_id` 當 `workspace_id` 傳入 write，MCP 有擋下但錯誤顯示暴露 product/workspace 參數容易混淆，後續可改善命名或 hint。
- Fix:
  - 建立並補強 L3 index doc：`L3 文件治理：文件群索引` (`de4ae982add24e79985a6b94993444fc`)。
  - 這份 doc 掛到 `L3 文件治理`，並 related 到 `MCP 介面設計`、`Dashboard 知識地圖`、`知識系統 Adapter 策略`。
  - 補上 8 個 source 與 5 個 `bundle_highlights`，明確指向日常治理、權威 spec、document bundle、native edit/helper ingest、delivery layer。
  - 更新 local/release `document-governance.md`：`L3 index summary = 文件群 retrieval map`，定義 L2 → documents search → summary/highlights → source 的閱讀順序。
  - 更新 MCP `governance_guide(document/bundle)` server-side rules，同步要求 summary、change_summary、bundle_highlights 的用途。
  - 更新 `search(collection="documents")`：文件列表排序優先 current、formal_entry、doc_role=index、有 bundle_highlights、多 sources 的 L3 index。
- QA:
  - `tests/interface/test_tools.py` 新增 document search 排序測試與 governance_guide 規則同步測試。
  - Regression：`177 passed, 6 warnings`。
- Deploy:
  - MCP deploy 成功，serving revision `zenos-mcp-00222-9mn`，traffic 100%。
- Production verification:
  - `governance_guide(topic="document", level=2)` 已回 `L3 index summary = 文件群 retrieval map` 與 `search(collection="documents", entity_name="<L2 name>")` 閱讀順序。
  - `governance_guide(topic="bundle", level=2)` 已回 index summary 最低要求。
  - `search(collection="documents", entity_name="L3 文件治理", limit=5)` 第一筆為 `L3 文件治理：文件群索引`，含完整 summary、change_summary、bundle_highlights、linked_entities。
- Resume Point:
  - 下一輪可補 `analyze(check_type="invalid_documents")` 或新的 governance gap，抓「L2 有 docs 但沒有 current index summary/highlights」的缺口；另可改善 `workspace_id` / `product_id` 混淆提示。

### DF-20260425-1

- Scenario: 接續 L3 doc governance，讓 `analyze(check_type="invalid_documents")` 能自動找出 L3 index summary / highlights / current index 缺口。
- Findings:
  - 原 `invalid_documents` 只抓空標題與 bare-domain title，無法支援新規則「L3 index summary 是文件群 retrieval map」。
  - 第一版 production smoke 回 178 個 bundle issues，response 過大且不利 agent 決策。
  - 第一版也把 draft smoke doc 當 red failure，沒有尊重 document lifecycle。
- Fix:
  - 新增 `detect_document_bundle_governance_issues()`，偵測：
    - `index_missing_bundle_highlights`
    - `index_missing_primary_highlight`
    - `index_summary_not_retrieval_map`
    - `index_missing_change_summary`
    - `l2_missing_current_index_document`
  - `analyze(check_type="invalid_documents")` 新增 `bundle_issues`、`bundle_issue_count`、`bundle_issue_limit`、`bundle_issues_truncated`。
  - bundle issues 依 severity/type 排序，最多回 50 筆，但保留總數。
  - lifecycle 修正：只檢查 `current` / `approved` / `under_review` 文件，draft 不再進 red list。
- QA:
  - 新增 domain tests 覆蓋 valid index、missing highlights、thin summary、missing change_summary、single-only L2、draft 排除。
  - 新增 interface test 覆蓋 `invalid_documents` bundle issue cap。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `197 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00223-rbr`：上線初版 bundle issue detection。
  - MCP deploy `zenos-mcp-00224-xbv`：上線 issue cap / truncation metadata。
  - MCP deploy `zenos-mcp-00225-bt4`：上線 lifecycle filter。
- Production verification:
  - 初版：`bundle_issue_count=178`，response 太大，且 draft smoke doc 被誤報。
  - cap 版：只回 50 筆，`bundle_issues_truncated=true`。
  - lifecycle 版：`bundle_issue_count=98`，draft smoke doc 不再出現在 red issue 第一筆；response 仍保留前 50 筆高優先問題。
- Resume Point:
  - 下一輪可做 scoped `analyze(check_type="invalid_documents", entity_id=...)`，讓 L1/L2 範圍治理不要被全 workspace 問題淹沒。

### DF-20260425-2

- Scenario: 補 scoped `analyze(check_type="invalid_documents", entity_id=...)`，避免 L3 doc 治理被全 workspace 問題淹沒。
- Findings:
  - 全域 `invalid_documents` 即使已 cap，仍是 workspace 層級 backlog，不適合作為單一 L1/L2 的立即治理入口。
  - Agent 真正在 dogfood 時需要「只看這個 L2/L1 的 L3 doc 問題」。
- Fix:
  - `invalid_documents` 分支支援 `entity_id` subtree scope。
  - Scope filter 使用 canonical document linkage：`parent_id` + outgoing `part_of` / `related_to`。
  - 回傳新增 `scope` metadata：`entity_id/entity_name/entity_type/mode/entity_count/document_count`。
  - scope entity 不存在時回 `status=rejected`, `error=NOT_FOUND`。
- QA:
  - 新增 interface tests：
    - scoped invalid_documents 只回 scope 內 document issue。
    - missing scope entity 回 rejected / NOT_FOUND。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `199 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00226-jfj`，traffic 100%。
- Production verification:
  - `analyze(check_type="invalid_documents", entity_id="9b894d4b44cb4e4c9cb2e7c7ab98e8b6")`（L3 文件治理）：
    - `scope.document_count=8`
    - `bundle_issue_count=4`
    - `bundle_issues_truncated=false`
  - `analyze(check_type="invalid_documents", entity_id="82f81abf483e49bdbdfba66e51c8e019")`（Dogfood Test Product）：
    - `scope.document_count=1`
    - `bundle_issue_count=0`
- Resume Point:
  - 下一輪可以直接修 `L3 文件治理` scope 內 4 個薄 summary document，或把 scoped invalid_documents 接到 governance loop / dashboard 顯示。

### DF-20260425-3

- Scenario: 直接修復 `L3 文件治理` scope 內 4 個 `index_summary_not_retrieval_map` 問題，驗證 scoped analyzer 能導向可完成的治理動作。
- Target docs:
  - `ZenOS Active Spec Surface` (`1cf651f1bd864e7e9e3fc293d3d8358a`)
  - `ZenOS 現行文件分類盤點` (`d11b87b499ce45e7a634aba7c84b27b4`)
  - `ZenOS-Enabled 專案文件治理規則` (`c3aae173920f4375990f2c62b023ed32`)
  - `document-governance：L3 文件治理合規操作` (`d020858dfc0e469483ae430c90ce8ba3`)
- Fix:
  - 逐份補強 `summary`：從短標籤改成文件群 / source routing retrieval map。
  - 補 `change_summary`：說明 2026-04-25 dogfood 將 summary 改為 L3 retrieval map。
  - 保留並強化原本 `bundle_highlights`，每份均指向 primary source 與 reason_to_read。
  - MCP `write(documents)` 額外對 current formal-entry 文件自動補 delivery snapshot。
- Production verification:
  - `analyze(check_type="invalid_documents", entity_id="9b894d4b44cb4e4c9cb2e7c7ab98e8b6")` 回：
    - `scope.document_count=8`
    - `bundle_issue_count=0`
    - `bundle_issues=[]`
- Outcome:
  - `L3 文件治理` 這個核心 L2 已可作為 L3 doc governance 的 reference-quality 範例：L2 → scoped analyze → 修 summary/highlights → analyzer 歸零。
- Resume Point:
  - 下一輪可把這個修復模式產品化：讓 `analyze(invalid_documents, entity_id=...)` 回 `repair_payload` 或 `suggested_write_patch`，降低 agent 手寫 summary/highlight payload 的成本。

### DF-20260425-4

- Scenario: 將 scoped `invalid_documents` 的 L3 doc 修復流程產品化，讓 analyzer 直接回 `suggested_write_patch`。
- Findings:
  - 上一輪修 `L3 文件治理` scope 時，agent 仍需手寫大段 `write(documents)` payload，容易慢、容易漏欄位。
  - Production smoke 顯示 patch 初版可用，但 `reason_to_read` 太通用，需帶入 doc title 才比較像可接受的治理內容。
- Fix:
  - `analyze(check_type="invalid_documents")` 對以下 issue 回 `suggested_write_patch`：
    - `index_missing_bundle_highlights`
    - `index_missing_primary_highlight`
    - `index_summary_not_retrieval_map`
    - `index_missing_change_summary`
  - Patch 格式可直接餵給 `write(collection="documents")`：
    - `tool="write"`
    - `collection="documents"`
    - `data={id,title,status,doc_role,linked_entity_ids,...}`
    - `needs_agent_review=true`
  - Highlight patch 會從既有 primary/first source 產生 `priority=primary` highlight。
  - Summary patch 會產生 deterministic retrieval-map template。
  - `reason_to_read` template 改為帶入 doc title，避免大量機械化通用句。
- QA:
  - 新增 interface test：確認 bundle issue 回 `suggested_write_patch`，且 patch 內有可執行的 `write/documents/data` 與 primary highlight。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `200 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00227-j2b`：上線 `suggested_write_patch`。
  - MCP deploy `zenos-mcp-00228-7cz`：上線 doc-title-aware `reason_to_read`。
- Production verification:
  - `analyze(check_type="invalid_documents", entity_id="8fc76949228b40af817220c6cef9530f")`（行銷內容自動化系統）回 6 個 issue，每個都有 `suggested_write_patch`。
  - 直接採用 6 個 suggested patches 執行 `write(collection="documents")`，全部成功。
  - 再跑同 scope analyze：
    - `scope.document_count=6`
    - `bundle_issue_count=0`
    - `bundle_issues=[]`
- Outcome:
  - L3 doc governance 修復閉環已可由 MCP 主導：analyze 產 patch → agent review → write 套用 → analyze 歸零。
- Resume Point:
  - 下一輪可補「批次套用 suggested_write_patch」的工具/工作流，或先把 patch quality 再提高：根據 source label/doc_type 產更具體的 `reason_to_read` 與 `summary`。

### DF-20260425-5

- Scenario: 補批次套用 `suggested_write_patch` 的 MCP 工作流，避免 agent 逐筆手動 copy/paste 文件修復 payload。
- Findings:
  - `analyze(invalid_documents)` 已能產單筆 `write(documents)` patch，但沒有安全批次入口。
  - 若直接開任意 batch write，會讓 relationship/entity 等高風險 mutation 也被批次執行，不適合 dogfood 修復流。
- Fix:
  - `write(collection="patches")` 新增文件修復 patch batch workflow。
  - 只接受 `tool="write"`、`collection="documents"`、`needs_agent_review=true` 的 patch。
  - patch data 採欄位白名單，允許 `id/title/status/doc_role/linked_entity_ids/bundle_highlights/summary/change_summary/tags/details/formal_entry`。
  - 支援 `dry_run=true` 只驗證不寫入；正式套用時逐筆轉呼叫既有 `write(collection="documents")` merge update 路徑。
- QA:
  - 新增 interface tests 覆蓋 dry-run、拒絕非文件 patch、拒絕高風險欄位、合法 patch 逐筆套用。
  - 新增 analyzer patch quality test：無 source 時不回不可執行的空 `suggested_write_patch`。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `205 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00229-l42`：上線 `write(collection="patches")` batch apply workflow。
  - MCP deploy `zenos-mcp-00230-snn`：上線 analyzer 不回空 patch 的修正。
- Production verification:
  - `Dashboard 知識地圖` scope 初始 `bundle_issue_count=6`，6 個 issue 均可 dry-run validate。
  - `write(collection="patches", dry_run=true)` 回 `validated_count=6`，未寫入。
  - `write(collection="patches")` 回 `applied_count=6`、`rejected_count=0`。
  - rerun `analyze(check_type="invalid_documents", entity_id="jN076EgEmQcUrOLrtAwd")` 後 `bundle_issue_count=1`。
  - 剩餘 issue 為無 source 的 `index_missing_bundle_highlights`，新版 analyzer 不再提供不可執行的 `suggested_write_patch`。
- Resume Point:
  - 下一輪可補「無 source 的 current index doc」修復策略：先補 source / zenos_native snapshot，再產 bundle_highlights patch。

### DF-20260425-6

- Scenario: 補「無 source 的 current L3 index doc」修復策略，完成 sourceless index → source → highlight 的兩階段治理閉環。
- Findings:
  - `Dashboard 知識地圖` scope 剩 1 個 red issue：`SPEC: L2 節點展開——Graph 內聯展開 Refs & Tasks` 是 `current doc_role=index`，但沒有 sources。
  - 前一版 analyzer 已避免產空 highlight patch，但 agent 仍只能看到問題，不能進入可套用修復。
  - 第一版 source patch dogfood 時失敗：`retrieval_mode="full"` 不符合 service contract，dry-run validator 沒擋住。
- Fix:
  - `detect_document_bundle_governance_issues()` 新增 `index_missing_sources` issue；source_count=0 時先要求補 source，不再直接報 missing highlights。
  - `analyze(invalid_documents)` 對 `index_missing_sources` 產 `suggested_write_patch`，補 `add_source`：
    - `type="zenos_native"`
    - `uri="/docs/{doc_id}"`
    - `is_primary=true`
    - `retrieval_mode="snapshot"`
    - `content_access="full"`
  - `write(collection="patches")` 允許受限 `add_source` patch，但只接受 zenos_native、uri 必須等於 `/docs/{doc_id}`、primary 必須 true，並驗證 retrieval/content access enum。
- QA:
  - 新增 domain test：sourceless index 回 `index_missing_sources`。
  - 新增 interface tests：analyzer 產 native source patch、patch validator 拒絕 unsafe source / invalid retrieval_mode。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `209 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00231-9mb`：上線 missing source analyzer/source patch 初版。
  - MCP deploy `zenos-mcp-00232-fgv`：修正 retrieval_mode/content_access contract 與 validator。
- Production verification:
  - `analyze(check_type="invalid_documents", entity_id="jN076EgEmQcUrOLrtAwd")` 回 `index_missing_sources` + native source patch。
  - `write(collection="patches", dry_run=true)` accepted source patch。
  - 第一版 apply 因 `retrieval_mode="full"` 被 service reject；修正部署後 apply source patch 成功。
  - rerun analyze 後同 doc 轉為 `index_missing_bundle_highlights`，並產出帶真實 `source_id` 的 highlight patch。
  - dry-run + apply highlight patch 成功。
  - 最終 rerun analyze：`Dashboard 知識地圖` scope `bundle_issue_count=0`。
- Outcome:
  - L3 doc governance 現在可處理三段式缺口：thin summary / missing highlights / missing sources。
  - `Dashboard 知識地圖` 成為第二個實際歸零的 L2 scope，驗證批次 patch workflow 對真資料有效。
- Resume Point:
  - 下一輪可改進 patch 內容品質：source patch 的 doc_type 目前固定 `GUIDE`，應根據文件 title/source label 推斷 SPEC/DESIGN/DECISION/TEST。

### DF-20260425-7

- Scenario: 改進 L3 doc patch 內容品質，讓 analyzer 產出的 summary/highlight 更像可用的 retrieval map，而不是通用模板。
- Findings:
  - `ERP 系統整合研究報告` 的 sourceless source patch 初版被固定成 `GUIDE`，但實際應是 `REPORT`。
  - `Action Layer` scope 內多份 ADR/TD/PRD/governance 文件仍可被 analyzer 找到，但 patch 內容若沒有 doc_type 判斷，agent 讀到 summary 時仍要二次猜文件用途。
  - 批次 patch workflow 已能安全套用多份文件修復，因此下一個瓶頸是 patch quality，而不是套用流程。
- Fix:
  - `analyze(invalid_documents)` 新增 deterministic doc_type inference，從 title/source label/summary 推斷 `SPEC/DESIGN/DECISION/TEST/PLAN/REPORT/CONTRACT/GUIDE/MEETING/REFERENCE/OTHER`。
  - 支援常見 prefix/keyword：
    - `ADR` → `DECISION`
    - `TD` → `DESIGN`
    - `PRD/FRD/SPEC` → `SPEC`
    - `PB/PLAYBOOK/治理/規範/SOP` → `GUIDE`
    - `研究/報告/分析/回顧` → `REPORT`
  - Summary patch 會明確寫入 `Primary source 類型判定為 {doc_type}`。
  - Highlight patch 的 `reason_to_read` 依 doc_type 產生更具體用途，例如 SPEC 看需求/驗收邊界、DECISION 看決策背景、REPORT 看研究結論。
  - Native source patch 的 source label 改為使用 inferred doc_type，例如 `REPORT: ERP 系統整合研究報告 ZenOS native delivery`。
- QA:
  - 新增 tests 覆蓋：
    - native source patch 使用 inferred doc_type。
    - ADR/TD/PRD/governance guide prefix/keyword 推斷。
    - SPEC highlight reason 使用需求/驗收語意。
    - summary patch 包含 primary source type。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `211 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00233-fb7`：上線 doc_type inference 初版。
  - MCP deploy `zenos-mcp-00234-6bk`：上線 doc_type-aware summary/highlight。
  - MCP deploy `zenos-mcp-00235-wpn`：補 PRD/FRD/Playbook/governance guide 推斷。
- Production verification:
  - `ERP Adapter 策略` scope：
    - `ERP 系統整合研究報告` source patch 被推斷為 `REPORT`。
    - dry-run + apply source patch 成功。
    - rerun analyze 後產生帶真實 `source_id` 的 highlight patch。
    - dry-run + apply highlight patch 成功。
    - 最終 `bundle_issue_count=0`。
  - `Action Layer` scope：
    - 初始 `bundle_issue_count=11`，全部為 `index_summary_not_retrieval_map`。
    - analyzer 對 ADR/TD/PRD/governance guide 產生較準的 doc_type-aware summary patches。
    - `write(collection="patches", dry_run=true)` 回 `validated_count=11`。
    - `write(collection="patches")` 回 `applied_count=11`、`rejected_count=0`。
    - 最終 rerun analyze：`bundle_issue_count=0`。
- Outcome:
  - L3 doc governance 目前能完成：scoped discovery → suggested patch → dry-run → batch apply → rerun verify。
  - L3 summary 已開始承擔「找到 L2 後快速知道有哪些文件、各自用途是什麼」的 retrieval-map 角色。
- Resume Point:
  - 下一輪仍可補 `l2_missing_current_index_document` 的 executable patch：目前 analyzer 能指出 L2 缺 current index，但還不能自動建立 L3 index doc。
  - 可再提高 summary quality：若 source 可讀，應從 source 摘更具體的文件內容，而不是只靠 title/metadata/template。

### DF-20260425-8

- Scenario: 補 `l2_missing_current_index_document` 的 executable patch，讓 L2 缺 current L3 index doc 時也能走 analyze → dry-run → batch apply → rerun verify。
- Findings:
  - 前一版 analyzer 只能指出 L2 缺 current index doc，但沒有 `entity_id` 對應既有 doc，因此無法用既有 update-only patch workflow 修復。
  - `write(collection="patches")` 原本強制 `data.id` 必須指向既有文件，不支援安全建立 L3 index doc。
  - Production dogfood 時，我第一次把 batch metadata 傳成 top-level `source`，MCP schema 拒絕；正確位置是 `data.source`。這是小摩擦，後續可在 tool description 補清楚。
- Fix:
  - `analyze(invalid_documents)` 對 `l2_missing_current_index_document` 產 `create_index_document` patch：
    - 預先生成 stable doc id。
    - 建立 `current` + `doc_role=index` + `formal_entry=true` 的 L3 document。
    - 補 `summary` 作為 L2 文件群 retrieval map。
    - 補 `zenos_native` primary source，uri 對齊 `/docs/{doc_id}`。
    - 補 primary `bundle_highlights`，讓新 index 建立後不需要再跑第二段 highlight patch。
  - `write(collection="patches")` 支援受限 create-index patch：
    - 只允許 `create_index_document=true` 時帶 `sources`。
    - 驗證 source 必須是 `zenos_native`、uri 必須等於 `/docs/{doc_id}`、必須只有一個 primary source。
    - 驗證 `bundle_highlights` source_id 必須對應 patch 內 source。
  - `upsert_document()` / `upsert_entity()` 支援 internal `allow_create_with_id`，只由 patch apply path 注入，讓 analyzer 生成的 `/docs/{doc_id}` 可以和新 document id 穩定對齊。
  - plural `sources` create path 保留 `source_id`、`retrieval_mode`、`content_access`、`is_primary` 等 metadata。
  - `write()` 補 optional top-level `source` 參數；仍支援 `data.source`，避免 agent 傳 audit metadata 時被 schema 擋。
- QA:
  - 新增 tests 覆蓋：
    - analyzer 對 L2 缺 current index 產 create-index patch。
    - batch dry-run 接受 create-index patch。
    - batch validator 拒絕 source uri 不等於 `/docs/{doc_id}`。
    - batch apply 會把 `create_index_document` 轉成 internal `allow_create_with_id`。
    - application layer 可用 stable id 建立 index doc 並保留 source metadata / highlight source_id。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `330 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00236-xtn`，traffic 100%。
- Production verification:
  - Global `analyze(check_type="invalid_documents")` 回 `l2_missing_current_index_document` for `Naruvia官網部落格`，並附 create-index patch。
  - `write(collection="patches", data={dry_run=true, patches=[...]})` 回 `validated_count=1`。
  - `write(collection="patches", data={patches=[...]})` 回 `applied_count=1`、`rejected_count=0`，新 doc id `be1550287549422da8a7ae2c72ac40a0`。
  - `analyze(check_type="invalid_documents", entity_id="ea983dae7b2c42fe8b2aed3a35500745")` 回 `bundle_issue_count=0`。
- Outcome:
  - L3 doc governance 的主要 red-loop 現在完整：missing index / missing sources / missing highlights / thin summary 都能產可審查 patch 並批次套用。
- Resume Point:
  - 可把 create-index patch 的 summary 從 metadata/template 升級成 source-aware 摘要：若既有 docs 可讀，應提取更具體的 source routing，而不是只列 title。

### DF-20260425-9

- Scenario: 補 source-aware L3 summary，並確認 MCP tool / skill / governance guide 三者一致。
- Findings:
  - DF-8 後 create-index patch 可用，但 summary 仍偏 title/template；agent 可以看出「有哪些文件」，但較難看出各 source 的實際語意用途。
  - 直接讓 `analyze` live 讀 GitHub/GCS/外部 source 會讓治理掃描變慢，且可能被外部權限或網路問題拖垮。
  - Skill / server-side `governance_guide` 存在多份規則字串；只改 local skill 不夠，production guide 仍可能回舊規則。
- Fix:
  - `analyze(invalid_documents)` 的 L3 summary patch 改為 source-aware：
    - 有 `snapshot_summary` 時納入 source 實際語意摘要。
    - 沒有 snapshot 時至少列出 `label/uri/doc_type/doc_status/is_primary` 與 status。
    - create-index patch 會把既有 docs 的 summary/source metadata 摘進新 index summary。
  - 保持 analyzer 不 live 讀外部全文；需要原文時仍由 agent 額外呼叫 `read_source`。
  - `write()` 支援 optional top-level `source`，和 `data.source` 都可作為 patch batch audit metadata。
  - 更新治理規則：
    - `skills/governance/document-governance.md`
    - `skills/release/governance/document-governance.md`
    - `skills/workflows/governance-loop.md`
    - `skills/release/zenos-governance/SKILL.md`
    - `src/zenos/interface/governance_rules.py`
  - 規則明確化：文件治理預設用 scoped `analyze(check_type="invalid_documents", entity_id="<L2 id>")`，有 `suggested_write_patch` 先 dry-run 再 batch apply。
- QA:
  - 新增 tests 覆蓋：
    - summary patch 會使用 `snapshot_summary`。
    - create-index patch summary 會吸收既有 doc/source 線索。
    - top-level `source` 會進 patch batch audit metadata。
  - Regression：`tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `331 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00238-whg`：source-aware summary / top-level source 初版。
  - MCP deploy `zenos-mcp-00239-5b7`：補齊 server-side `governance_guide` 規則字串。
- Production verification:
  - `governance_guide(topic="document", level=2)` 已回 source-aware / scoped-first 規則。
  - `analyze(check_type="invalid_documents", entity_id="2D8B9wxvasBONntACcxu")` 的 summary patch 現在包含 `目前 source routing：...（doc_type, valid）`。
  - `write(collection="patches", source="dogfood.source_aware_summary", data={dry_run=true,...})` 成功，驗證 top-level `source` 已被 tool schema 接受。
  - apply 單筆 source-aware summary patch 成功；rerun scoped analyze 後 `bundle_issue_count` 由 15 降為 14。
- Outcome:
  - MCP tool、skill、production governance guide 已對齊同一個 L3 doc governance 流程。
  - L3 summary 不再只是 title list；在有 source metadata / snapshot_summary 時會提供更可用的 source routing。
- Resume Point:
  - 下一輪可批次套用 `語意治理 Pipeline` scope 內剩餘 14 個 source-aware summary patches，並觀察是否還有 false positive。
  - 下一個品質提升點：讓 helper ingest 更常填 `snapshot_summary`，否則 analyzer 只能做到 metadata-aware，不能做到 content-aware。

### DF-20260425-10

- Scenario: 讓 helper / connector ingest 的 `snapshot_summary` 從 skill 規則到 production MCP create path 都能保留，並用 production dogfood 驗證 analyzer 真的能做 content-aware source routing。
- Findings:
  - plural `sources: [...]` create path 原本只保留部分 source metadata；helper 送來的 `snapshot_summary`、`external_updated_at`、`last_synced_at` 可能在新建 bundle 時被丟掉。
  - local workflow skill 已補 snapshot 規則後，release `zenos-capture` / `zenos-sync` 仍會漏；使用者更新 skills 後可能拿到不一致指引。
  - 第一次 production 驗證發現 `governance_guide(topic="capture")` 沒有同步 snapshot 規則；只改 skill 不夠。
  - `write(collection="documents", id=..., data={summary: ...})` 仍要求 `linked_entity_ids` / `tags`，單欄位更新 summary 摩擦偏高。
- Fix:
  - `upsert_document` plural `sources` create path 保留：
    - `snapshot_summary`
    - `external_updated_at`
    - `last_synced_at`
    - `retrieval_mode`
    - `content_access`
  - 對 plural source 的 `snapshot_summary` 套用 10KB guard，避免把全文 mirror 塞進 ontology。
  - 更新 workflow / release skills：
    - `skills/workflows/knowledge-capture.md`
    - `skills/workflows/knowledge-sync.md`
    - `skills/release/zenos-capture/SKILL.md`
    - `skills/release/zenos-sync/SKILL.md`
  - 更新 server-side `governance_guide(topic="capture")` level 1/2/3，明確要求 helper source 帶 `snapshot_summary`。
  - 修正既有 document sparse update：只更新 `summary` / `change_summary` 等欄位時，若 document 已有 parent / linkage，就沿用既有 linkage，不再要求 agent 重送 `linked_entity_ids` / `tags`。
- QA:
  - 更新 `test_plural_sources_payload_persisted`，確認新建 document bundle 時會保留 snapshot / external sync metadata。
  - 新增 sparse document update regression，確認既有 document 單欄位更新可沿用 existing linkage。
  - Regression：`tests/application/test_adr022_review_fixes.py tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `357 passed`。
- Deploy:
  - MCP deploy `zenos-mcp-00240-ztl`：plural source snapshot preservation + release skill update。
  - MCP deploy `zenos-mcp-00241-hgm`：補 production `governance_guide(topic="capture")` snapshot 規則。
  - MCP deploy `zenos-mcp-00242-qdx`：降低 document sparse update 摩擦。
- Production verification:
  - `governance_guide(topic="capture", level=1/2/3)` 已回 helper source / `snapshot_summary` 規則。
  - 建立 dogfood L3 index doc（id_prefix `fba350bb`），source `df-20260425-10-local-helper` 的 `snapshot_summary`、`external_updated_at`、`last_synced_at` 均有保存。
  - 將該 doc summary 暫時降成 `Thin.` 後，scoped `analyze(check_type="invalid_documents")` 產出 `index_summary_not_retrieval_map` patch，summary 內包含 helper snapshot 摘要。
  - `write(collection="patches", dry_run=true)` 成功；`dry_run=false` apply 成功；rerun scoped analyze 回 `bundle_issue_count=0`。
  - `write(collection="documents", id_prefix="fba350bb", data={summary: ...})` 不帶 `tags` / `linked_entity_ids` 成功，且 response 保留既有 tags/linkage。
- Outcome:
  - L3 doc governance 現在不只 metadata-aware；helper source 有 snapshot 時，production analyzer 可產 content-aware routing patch。
  - Agent 修 L3 summary 的常見路徑少一次重試，不需要查回完整 tags/linkage 再寫。
- Resume Point:
  - 下一個可修點：`write(collection="patches")` 的 patch format 對 `needs_agent_review` 很嚴格；可以在 rejection suggestion 裡直接提示「請保留 analyzer 回傳的 needs_agent_review=true」。

### DF-20260425-11

- Scenario: 繼續 dogfood batch patch workflow，修正 patch validation rejection 的錯誤提示。
- Findings:
  - DF-10 production dogfood 時，agent 手動重組 analyzer patch 後漏掉 `needs_agent_review=true`。
  - MCP 只回 `patch_must_be_analyzer_reviewable`，雖然安全但不夠可操作；agent 需要猜下一步。
- Fix:
  - `write(collection="patches")` 在 patch batch validation error 時會根據 reason 產生 suggestions。
  - 對 `patch_must_be_analyzer_reviewable` 明確提示：請保留 analyze 回傳 patch 的 `needs_agent_review=true`。
  - 對 patch 結構錯、非 document patch、disallowed fields、empty patch list、create-index patch 被改壞、add-source patch 不安全，都補最小可操作 suggestion。
- QA:
  - 新增 interface test：缺 `needs_agent_review` 時 response suggestions 包含 `needs_agent_review=true`。
  - 擴充 tests 覆蓋 non-document patch、disallowed fields、unsafe add_source patch 的 suggestions。
  - Regression：
    - `tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `217 passed`
    - `tests/application/test_adr022_review_fixes.py tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `358 passed`
- Deploy:
  - MCP deploy `zenos-mcp-00243-rxr`，traffic 100%。
  - MCP deploy `zenos-mcp-00244-fr7`，補齊分類式 rejection suggestions。
- Production verification:
  - 故意送缺 `needs_agent_review` 的 `write(collection="patches", dry_run=true)`，response 回：
    - `reason="patch_must_be_analyzer_reviewable"`
    - suggestion：「請保留 analyze 回傳 patch 的 needs_agent_review=true；不要手動重組時漏掉這個欄位。」
  - 補上 `needs_agent_review=true` 後 dry-run 成功，`validated_count=1`。
  - 故意送 `collection="relationships"` patch，response suggestion 明確要求直接傳 analyzer 的 `suggested_write_patch`，且必須 `tool=write` / `collection=documents` / `data.id` 必填。
  - 故意送外部 GitHub `add_source` repair patch，response suggestion 明確說 add_source repair 目前只允許 analyzer 產生的 `zenos_native` primary source，外部 source 要走 `write(collection="documents")` 人工更新路徑。
- Outcome:
  - Batch patch 安全 gate 沒放寬，但 agent 下一步更明確，少一次推測與重試。
- Resume Point:
  - 下一輪可回到真實 scoped `invalid_documents` backlog，批次套用一組 analyzer patch，觀察是否還有 false positive 或 apply-time failure。

### DF-20260425-12

- Scenario: 回到真實 `invalid_documents` backlog，對 `語意治理 Pipeline` scope 批次套用 analyzer patch，驗證完整 analyze → dry-run → apply → rerun 閉環。
- Findings:
  - scoped `analyze(check_type="invalid_documents", entity_id="2D8B9wxvasBONntACcxu")` 起始回 `bundle_issue_count=14`。
  - 14 筆都是 L3 index summary / change_summary governance patch，沒有 structural reject。
  - 同一 document 同時有 `index_missing_change_summary` 和 `index_summary_not_retrieval_map` 時，可以在同一 batch 內順序 apply，沒有覆寫衝突。
- Execution:
  - 第一批 5 筆：
    - dry-run `validated_count=5`
    - apply `applied_count=5` / `rejected_count=0`
    - rerun 後 `bundle_issue_count=9`
  - 第二批 9 筆：
    - dry-run `validated_count=9`
    - apply `applied_count=9` / `rejected_count=0`
    - rerun 後 `bundle_issue_count=0`
- Outcome:
  - `語意治理 Pipeline` scope 的 L3 doc bundle governance 已清到 0。
  - 這次真實 backlog 沒看到 false positive、dry-run false reject、或 apply-time failure。
  - Batch patch workflow 對 agent 已經足夠順：scoped analyze 回 patch → dry-run → apply → rerun 能穩定閉環。
- Resume Point:
  - 下一輪可挑另一個 L2/L1 scope 做同樣清理，或開始檢查 Dashboard / search / get 是否能把整理後的 L3 summary 以 agent 友善方式呈現。

### DF-20260425-13

- Scenario: 測整理後的 L3 summary 是否真的讓 `search/get` 更好用，而不是只有 analyzer 指標變乾淨。
- Findings:
  - `search(collection="documents", entity_name="語意治理 Pipeline")` 能找到 L3 index docs，且 summary / highlights 能幫 agent 判斷先讀哪份 source。
  - 但預設回完整 document payload，18 筆結果 token 過大，不利於 agent 掃描。
  - 長 query `Agent 端語意判斷 Server 端結構執法` 初次回空；原因是 document query 只做 substring，title 中間有 `vs` 就不命中。
  - `get(collection="documents", id=...)` 對單份 L3 doc 可讀性良好；適合 search 後看單 doc 詳情。
- Fix:
  - document search query 改成：
    - 先做原 substring match。
    - 若沒命中，拆 token 後全部 token 命中 haystack 也算 match。
    - haystack 納入 title / summary / source uri / source label / source doc_type / tags。
  - `search(collection="documents")` 多結果且 caller 未指定 include 時，自動降級成 compact document payload：
    - `summary_short`
    - `doc_role`
    - `change_summary`
    - `bundle_highlights`
    - `source_count`
    - `primary_source`
    - linkage fields
  - 顯式 `include=["summary"]` 保留完整 L3 summary；顯式 `include=["full"]` 回完整 payload。
- QA:
  - 新增 tests：
    - document long query token match 可找到 ADR-013。
    - entity_name 多 docs 自動 compact summary payload。
  - Regression：
    - `tests/interface/test_tools.py` → `199 passed`
    - `tests/application/test_adr022_review_fixes.py tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `360 passed`
- Deploy:
  - MCP deploy `zenos-mcp-00245-97x`：document token query match + summary payload 初版。
  - MCP deploy `zenos-mcp-00246-vpb`：多結果 auto compact summary。
- Production verification:
  - `search(collection="documents", query="Agent 端語意判斷 Server 端結構執法")` 現在找到 `ADR-013: 分散治理模型——Agent 端語意判斷 vs Server 端結構執法`。
  - `search(collection="documents", entity_name="語意治理 Pipeline", limit=20)` 回 18 筆 compact document payload，warning 明確說明自動 compact，並提示要完整 summary 用 `include=["summary"]`、完整 payload 用 `include=["full"]`。
  - `search(collection="documents", entity_name="語意治理 Pipeline", include=["summary"], limit=5)` 仍可拿完整 summary，用於 agent 已縮小候選後的精讀。
- Outcome:
  - L3 doc 整理後現在能被 search/get 實際消費：先用 compact list 掃描候選，再用 get 或 include summary 精讀。
  - 目前仍有品質改善空間：部分 analyzer 產生的 summary / change_summary 太模板化；下一輪可改善 summary 文字品質，而不是只修 retrieval mechanics。
- Resume Point:
  - 下一輪可針對 L3 summary 內容品質做 dogfood：挑 3-5 個模板化 summary，改 analyzer patch 生成策略，讓 summary 更像「這份文件回答什麼問題」而不是固定句型。

### DF-20260425-14

- Scenario: 改善 `analyze(invalid_documents)` 產生的 L3 index summary patch 品質，避免只產出模板化 retrieval map。
- Findings:
  - 前一輪 search/get 已變順，但 analyzer 產出的 summary 偏固定句型。
  - 對 agent 來說，L3 summary 最有用的資訊是「這份文件群主要回答什麼問題、誰在什麼任務先讀、primary source/type/source routing」。
- Fix:
  - `src/zenos/interface/mcp/analyze.py`：
    - summary patch 會從 `tags.what/why/how/who`、`doc_type`、source label、snapshot summary 推導用途。
    - 產出文字新增「主要回答...」與「適合 ... 在處理 ... 任務時先讀」。
    - `change_summary` patch 改為說明哪份 doc、多少 sources/highlights 被補齊，而不是泛稱補 metadata。
- QA:
  - `tests/interface/test_tools.py::TestAnalyzeTool::test_analyze_invalid_documents_returns_suggested_write_patch tests/interface/test_tools.py::TestAnalyzeTool::test_analyze_invalid_documents_suggests_native_source_patch` → `2 passed`
  - `tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py` → `219 passed`
  - `tests/application/test_adr022_review_fixes.py tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `360 passed`
- Deploy:
  - MCP deploy `zenos-mcp-00247-xj4`，traffic 100%。
- Production verification:
  - 將 `DF-20260425-10 Helper Snapshot Summary Preservation` summary 故意改成 `Thin.`。
  - scoped `analyze(check_type="invalid_documents", entity_id="1b07c1679c08490db2b688ba82347afe")` 產出 summary patch，內容包含：
    - 「主要回答「Dogfood MCP Friction Log、L3 document governance、helper ingest」的操作流程、治理規則與日常執行方式」
    - 「適合 architect 在處理 dogfood test 任務時先讀」
    - primary source、GUIDE 類型、snapshot summary source routing。
  - `write(collection="patches", dry_run=true)` 驗證成功。
  - `write(collection="patches", dry_run=false)` 套用成功，`applied_count=1` / `rejected_count=0`。
  - 重跑 scoped analyzer 後 `bundle_issue_count=0`。
- Outcome:
  - L3 doc governance 現在形成比較完整閉環：L2 找 docs → compact search 掃描 → get 精讀 → analyzer 可補高品質 L3 summary → batch patch 套用 → scoped analyzer 清零。
  - 目前主流程已可用；下一輪若要再提高品質，應改進大量舊 L3 docs 的實際內容與 source snapshot，而不是只修 MCP mechanics。
- Resume Point:
  - 下一輪可挑另一個真實 L2 scope 做 end-to-end dogfood，檢查舊文件的 source snapshot 是否足夠支撐 summary；若不足，再補 capture/sync 對 snapshot_summary 的生成品質。

### DF-20260426-1

- Scenario: 直接重整 ZenOS L1 目前舊 L3 docs 的 source snapshot / summary 內容品質，而不是只修 MCP mechanics。
- Findings:
  - `analyze(check_type="invalid_documents", entity_id="Gr54tjmnXK0ZAtZia6Pj")` 起始 scope：
    - `entity_count=113`
    - `document_count=94`
    - `bundle_issue_count=24`
  - 第一輪 24 筆都是舊 L3 index summary 不像 retrieval map；可用 analyzer patch 批次修。
  - 批次套用第一批 12 筆時，1 筆因手動貼錯 document id 被 reject；batch patch 正確回 `status=partial`、指出 `index=11` 與 not found document id，方便 agent 補救。
  - 套用 24 筆後 scoped analyzer 一度回 `bundle_issue_count=0`，但 search/get 抽查發現漏網：部分 summary 是人寫內容摘要，長度足夠、有 highlight，卻沒有 primary/source routing/閱讀邊界。
- Fix:
  - Production data remediation：
    - 第一批 11 筆成功、1 筆補正 id 後重套。
    - 第二批 13 筆成功。
    - 新 detector 上線後新增 16 筆漏網 summary patch，dry-run 16 成功，apply 16 成功。
  - MCP analyzer detector 補強：
    - `index_summary_not_retrieval_map` 不再只看長度或多 source。
    - summary 必須同時具備回答範圍、primary/source 指向、source routing 或 bundle_highlights、閱讀/治理邊界。
    - 補測試：一般內容摘要（例如 Auth ADR 摘要）不能被當成 retrieval map。
- QA:
  - `tests/interface/test_analyze_invalid_documents.py tests/interface/test_tools.py::TestAnalyzeTool::test_analyze_invalid_documents_returns_suggested_write_patch` → `22 passed`
  - `tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `335 passed`
- Deploy:
  - 初次 MCP deploy 因 sandbox DNS 無法解析 `oauth2.googleapis.com` 失敗。
  - 外部網路重跑 `./scripts/deploy_mcp.sh` 成功。
  - MCP deploy `zenos-mcp-00248-kwl`，traffic 100%。
- Production verification:
  - 新 detector 部署後，ZenOS L1 scoped analyzer 抓出 16 筆舊 summary 漏網。
  - `write(collection="patches", dry_run=true)` 驗證 `validated_count=16`。
  - `write(collection="patches", dry_run=false)` 套用 `applied_count=16` / `rejected_count=0`。
  - 最終 `analyze(check_type="invalid_documents", entity_id="Gr54tjmnXK0ZAtZia6Pj")`：
    - `document_count=94`
    - `bundle_issue_count=0`
    - `bundle_issues_truncated=false`
- Outcome:
  - ZenOS L1 目前 current/approved/under_review L3 index docs 已整理到 analyzer 規則下 0 issue。
  - Analyzer 現在能抓「有摘要但不是 retrieval map」的舊 L3 docs，這是本輪真正補上的品質缺口。
  - Batch patch workflow 對大量 L3 remediation 可用；partial failure 也能讓 agent 明確補救。
- Resume Point:
  - 下一輪可抽查 `search(collection="documents", entity_name="<核心 L2>", include=["summary"])` 對 3-5 個核心 L2 的可用性；若仍有語意薄弱，問題多半在 source snapshot 不夠，而不是 summary detector。

### DF-20260426-2

- Scenario: 抽查 L3 doc search 實際可用性，確認 agent 從 L2 找文件時是否會先拿到正確且具體的文件入口。
- Findings:
  - `search(collection="documents", entity_name="MCP 介面設計", include=["summary"])` 會把 secondary-linked 的 `L3 文件治理：文件群索引` 排在主 L2 文件前面。
  - `Dashboard 知識地圖` 也有同類風險；agent 容易先讀到相關治理文件，而不是 Dashboard 自己的 spec/design/ADR。
  - 收緊後又發現 30 筆舊 summary 雖然形式上像 retrieval map，但內容是「此主題有哪些正式文件、哪份 source 應先讀」這種泛化模板，對 agent 幫助有限。
- Fix:
  - `src/zenos/interface/mcp/search.py`：
    - `entity_name` 文件搜尋排序新增 primary-linked 優先權。
    - 同一 L2 下仍保留原本 current/formal/index/highlight/source/updated 排序。
  - `src/zenos/domain/governance.py`：
    - `_summary_looks_like_retrieval_map` 新增 generic template negative check。
    - 看到「此主題有哪些正式文件」「哪份 source 應先讀」等泛化句型時，判為 `index_summary_not_retrieval_map`。
  - Production data remediation：
    - 正式 analyzer 抓出 30 筆 generic summary。
    - 以 `write(collection="patches")` 分三批 dry-run/apply，每批 10 筆，全部成功。
- QA:
  - `tests/interface/test_tools.py::TestSearchTool` → `18 passed`
  - `tests/interface/test_tools.py tests/interface/test_analyze_invalid_documents.py tests/application/test_validation.py` → `337 passed`
- Deploy:
  - MCP deploy `zenos-mcp-00249-pt7`：search primary-linked ranking 上線。
  - MCP deploy `zenos-mcp-00250-pwt`：generic summary detector 上線。
- Production verification:
  - `MCP 介面設計` 搜尋現在先回主 L2 文件，如 `TD-zentropy-ingestion-governance-implementation`、`SPEC-ingestion-governance-v2`，不再先回 L3 governance secondary doc。
  - `Dashboard 知識地圖` 搜尋現在先回 Dashboard spec/design/ADR，且 summary 已改為具體問題域。
  - `語意治理 Pipeline` / `Action Layer` 抽查可看到具體 answer scope、primary source、source routing 與閱讀邊界。
  - 最終 `analyze(check_type="invalid_documents", entity_id="Gr54tjmnXK0ZAtZia6Pj")`：
    - `document_count=94`
    - `bundle_issue_count=0`
    - `bundle_issues_truncated=false`
- Outcome:
  - L3 doc entity 現在對 agent 更像可用的「L2 → 文件入口」：主掛文件優先、secondary link 保留但不搶位、summary 不再允許泛化模板過關。
  - Batch patch workflow 已被真實 30 筆資料驗證，dry-run/apply/re-analyze 閉環順。
- Resume Point:
  - 下一輪可把 `bundle_highlights` 也收緊：目前不少 headline 還是「這個主題目前最直接的文件入口」，可要求 headline / reason_to_read 必須包含具體用途或決策點。

### DF-20260426-3

- Scenario: 檢查 journal 與 entries 的實際資料品質；驗證「journal 是否被 agent 過度使用」與「entries 是否真的寫到重點」。
- Findings:
  - `journal_read(limit=20)` 回來的資料混雜多個 project，且有大量 session/flow closeout；對 agent 恢復任務脈絡的精準度不如 `recent_updates`、tasks、PLAN Resume Point。
  - journal summary 曾在 MCP tool 層被截斷到 100 字，但 DB repository 可收 500 字；這會讓本來就偏流水帳的 journal 更難讀。
  - ZenOS L1 entries 有少數有價值的 decision/limitation，但近期待辦/完成型 entries 偏像 task completion report，例如 AC 通過、pytest passed、元件改了什麼；這些應留在 `task.result`，不該固化為 L2 知識。
  - `confirm(collection="tasks", entity_entries=...)` 與 `write(collection="entries")` 原本只檢查 type/length，沒有檢查 entry 是否是 durable knowledge。
- Fix:
  - 新增 `src/zenos/interface/mcp/_entry_quality.py`：
    - 擋 completion report、AC pass、pytest/QA PASS、code trace 類 entry。
    - 允許含決策、原因、限制、取捨、約束、風險、後續等 durable marker 的內容。
  - `write(collection="entries")`：
    - 低價值內容回 `LOW_VALUE_ENTRY`，提示「QA PASS / pytest / AC 通過 / 部署完成」留在 task result / journal / plan log。
  - `confirm(collection="tasks", entity_entries=...)`：
    - accepted 時遇到低價值 entity_entries 會 skip 並回 warning，不再靜默寫入。
  - `journal_write`：
    - summary 截斷從 100 字放寬到 500 字，超長時回 warning。
    - tool docstring 明確：journal 只記重大 flow 結束，不要每個 task/handoff/小修復都寫；任務結果放 task.result，長期知識放 entries。
  - Skills：
    - `architect` / `developer` / `pm` / `qa` 啟動流程改成優先 `recent_updates`、tasks、entities/documents、PLAN Resume Point。
    - journal 降級為 fallback：上述來源都不足時才讀 `journal_read(limit=5)`。
    - brainstorm/debug workflow 的 journal_write 從「必做」改為「重大結論/重大修復才寫」。
- QA:
  - Focused：`tests/interface/test_journal_tools.py` + confirm entries + write entries → `39 passed`
  - Broader：`tests/interface/test_tools.py tests/interface/test_journal_tools.py tests/interface/test_review_bugs.py tests/application/test_validation.py` → `336 passed`
- Deploy:
  - MCP deploy `zenos-mcp-00251-f5j`，traffic 100%。
- Production verification:
  - `write(collection="entries", type="change", content="Implementation complete；pytest 337 passed；QA PASS")` 回：
    - `status="rejected"`
    - `data.error="LOW_VALUE_ENTRY"`
    - `data.reason="entry_is_completion_report"`
  - rejection suggestions 指向正確分層：completion report 留 task result / journal / plan log；entries 改寫成原因、約束或決策邊界。
- Outcome:
  - Journal 已從主要 context source 降級為 fallback/重大 flow 記錄。
  - Entries 入口已加第一層 server 品質閘門，防止 completion-report 型內容繼續污染 L2 knowledge。
- Resume Point:
  - 下一輪可補 `analyze(check_type="quality")` 的 entry anti-pattern repair patch：掃出既有低價值 active entries，產生 archive/supersede 建議，清掉歷史污染。

### DF-20260426-4

- Scenario: 驗證 MCP tool 已修後，release skills / workflow skills 是否也跟上 journal 與 entries 的新分層規則。
- Findings:
  - MCP 已能阻擋 completion-report 型 entry，但多個 skill 還殘留舊行為：`journal_read(limit=20)` 當啟動主來源、capture 完成後「每次都寫 journal」、dogfood 觀察直接寫 journal。
  - `tests/test_release_agent_context_constraints.py` 還把「必須讀 journal」當成 release role 的合格條件，與 `recent_updates` 優先的新方向衝突。
- Fix:
  - Role skills：architect / developer / pm / qa / designer / marketing / debugger / challenger / coach 啟動脈絡統一改成優先 `recent_updates`、tasks、entities、documents；journal 只作 fallback，最多 `limit=5`。
  - Capture / governance skills：Work Journal 從「每次捕獲都寫」改為「只有實際新增/更新知識，或留下 TBD / blindspot 時才寫」；純掃描無變更不要寫。
  - Dogfood workflow：問題先記到 plan / task result；只有跨 session 且不適合 task/result 時才寫 journal。
  - PM / Developer ALWAYS 條款移除「啟動時讀 journal」舊紅線。
  - Release sync：執行 `python3 scripts/sync_skills_from_release.py`，同步到 `~/.claude/skills` 與 `~/.codex/skills`。
  - Sync script：補 legacy workflow aliases（`debug` / `feature` / `brainstorm` / `triage`）與 governance directory sync，避免全域 root skills 繼續保留舊版 workflow。
  - Sync script：補 platform agent overwrite（`zenos-capture` / `zenos-sync` / `zenos-setup` / `zenos-governance`），清掉 `~/.claude/agents` 舊版 capture agent 的 journal-first 文案。
  - MCP governance guide：`governance_guide(topic="capture")` 補 `Work Journal gate`，明確禁止純掃描無變更寫 journal、禁止把 task completion report 寫成 entry。
  - Test guard：`tests/test_release_agent_context_constraints.py` 改為要求 durable ontology context (`recent_updates` / tasks / entries) 與 journal fallback 語義。
- QA:
  - `pytest -q tests/interface/test_tools.py::TestGovernanceGuideTool::test_capture_rules_describe_routing_not_llm_internals tests/test_sync_skills_from_release.py tests/test_release_agent_context_constraints.py` → `4 passed`
  - `rg` 驗證 repo skills、repo agents/roles、`~/.codex/skills`、`~/.claude/skills`、`~/.codex/agents`、`~/.claude/agents` 不再含 `journal_read(limit=20)`、`每次捕獲完都寫`、`模式 A/B/C 完成後都要做`、`啟動時讀 journal` 等舊指令。
- Deploy:
  - MCP deploy `zenos-mcp-00252-7kc`，traffic 100%。
- Production verification:
  - `governance_guide(topic="capture", level=2)` 已回傳 `Work Journal gate`。
  - Production guide 明確包含：「純掃描無變更不要寫 journal」、「task 完成狀態寫在 task.result；durable knowledge 才寫 entries」。
- Outcome:
  - Skill 層已追上 MCP 的 journal/entries 分層：agent 的入口提示不再鼓勵流水帳 journal，也不再把 task completion 當 durable entry。
- Resume Point:
  - 下一輪可把 `governance_guide(topic="sync")` 也補上同等 journal gate，避免 sync status 過度依賴 journal；目前 sync 已限制「有實質變更才寫」，但 server guide 可再更明確。

### DF-20260426-5

- Scenario: 收斂 skill 同步鏈，並讓查 context 的 happy path 更少靠 agent 猜。
- Findings:
  - 只靠手動 `rg` 抓 stale skill 不夠；同步腳本應在發布後自我驗證，否則舊的 journal-first 指令可能留在全域 root skill / agent alias。
  - role skills 雖然已降級 journal，但「先查 recent_updates、再查 task、再找 L2/L3」仍分散在各檔，agent 需要自己拼順序。
- Fix:
  - `scripts/sync_skills_from_release.py`：
    - 新增 stale instruction gate，發布後若仍含 `journal_read(limit=20)`、`每次捕獲完都寫`、`模式 A/B/C 完成後都要做`、`啟動時讀 journal` 等舊指令，直接 fail。
    - stale check 只掃本次發布的 skill / agent 檔案，保留 `LOCAL.md` 不阻斷同步。
  - `skills/governance/bootstrap-protocol.md` 與 release mirror：
    - 新增 **Context Happy Path**：`recent_updates → tasks → L2 entity → L3 documents → read_source → journal fallback`。
  - Core role skills / agent aliases：
    - architect / developer / pm / qa 明確引用 Context Happy Path。
    - legacy role files與 `skills/agents/architect.md` 同步補上同一條路徑，避免 global agent alias 漏掉。
  - `tests/test_sync_skills_from_release.py`：
    - 覆蓋 stale instruction gate、LOCAL.md skip、platform agent overwrite、Context Happy Path 發布。
- QA:
  - `pytest -q tests/test_sync_skills_from_release.py tests/test_release_agent_context_constraints.py` → `6 passed`
  - `python3 scripts/sync_skills_from_release.py` → synced 22 skills + 12 agents。
  - `rg` 驗證 `~/.claude/skills`、`~/.codex/skills`、`~/.claude/agents`、`~/.codex/agents` 沒有舊 journal-first 指令。
  - `rg` 驗證 `~/.codex/skills/{architect,developer,pm,qa}`、`~/.codex/skills/governance/bootstrap-protocol.md`、`~/.claude/agents/architect.md` 都含 Context Happy Path。
- Outcome:
  - Skill 同步鏈現在有發布後 gate，未來不容易再出現「repo 修了但全域 skill 還舊」。
  - Agent 查 context 的預設路徑變成固定流程，不再需要憑經驗猜要先讀 journal、tasks 還是 L3 docs。
- Resume Point:
  - 下一輪可考慮把 Context Happy Path 做成 MCP tool response suggestion，例如 search/get 回傳 `next_context_steps`，讓不讀 skill 的 agent 也能走對路徑。
