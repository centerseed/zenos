---
type: TD
id: TD-zentropy-ingestion-governance-implementation
status: Approved
linked_spec: SPEC-zentropy-ingestion-contract
created: 2026-04-11
updated: 2026-04-11
---

# 技術設計：Zentropy Ingestion Governance Implementation

## 調查報告

### 已讀文件（附具體發現）
- `docs/specs/SPEC-zentropy-ingestion-contract.md`
  - 發現：已把 `/api/ext/*` 邊界寫成硬規範，明確要求 commit 僅能落到 `task`/`write(entries)`，且禁止直寫 L2/relationship/document。
- `docs/decisions/ADR-031-zentropy-ingestion-governance-boundary.md`
  - 發現：已鎖定雙層 API（Ingestion Facade + Core Governance）與 scope-by-candidate-type 模型，並要求 8 段 server gate。
- `docs/specs/SPEC-zenos-external-integration.md`
  - 發現：外部 app 接入正式路徑是 federation + delegated credential，scope 為 `read/write/task`。
- `docs/specs/SPEC-zenos-auth-federation.md`
  - 發現：delegated credential 必帶 `workspace_ids` 與 scopes，ZenOS 是最終 authorization authority。
- `docs/specs/SPEC-task-governance.md`
  - 發現：Task 正式狀態機與 confirm gate 已固定，`done` 不可由 update 直接設。
- `docs/specs/SPEC-l2-entity-redefinition.md`
  - 發現：L2 升級必須經過三問 + impacts gate；injection 不可直接改 L2。
- `docs/decisions/ADR-029-auth-federation-runtime.md`
  - 發現：`POST /api/federation/exchange` + JWT delegated credential + scope enforcement 是既定技術路徑。
- `docs/decisions/ADR-030-mcp-authorization-hardening.md`
  - 發現：JWT path 必須與 API key path 有同級授權保護，且要做整合測試。
- `docs/designs/TD-distributed-governance.md`
  - 發現：Server 端結構執法可增量擴充，方向與本案一致，不需重建治理基礎。
- `src/zenos/interface/federation_api.py`
  - 發現：只有 `/api/federation/exchange` 對外 endpoint 已實作，且回傳 delegated token 結構。
- `src/zenos/interface/mcp/_auth.py`
  - 發現：JWT path 已驗證 `workspace_ids`，可重用同一授權語意到 ext API。
- `src/zenos/interface/mcp/_scope.py` + `src/zenos/interface/mcp/__init__.py`
  - 發現：`read/write/task` scope 已成形且透過 decorator 落在 tool handler，不需新定義 scope 族群。
- `src/zenos/interface/mcp/task.py`、`write.py`、`confirm.py`
  - 發現：Task/Entry/Confirm 的 canonical mutation/gate 已存在，commit 可直接複用。

### 搜尋但未找到
- `src/zenos` 搜尋 `/api/ext/signals/ingest|signals/distill|candidates/commit|review-queue`
  - 無結果：ext ingestion facade 尚未實作。
- `docs/designs` 搜尋 `TD-*zentropy*ingestion*`
  - 無結果：本案尚無專屬 TD。

### 我不確定的事（明確標記）
- [未確認] `signals`/`candidates` 最終是否採單表多型或分表設計（需在 implementation 時依查詢模式決定）。
- [未確認] `candidates/commit` 對 mixed payload 的 transaction 策略（全有全無 vs 部分成功）最終產品偏好。

### 結論
可以開始設計並開工。既有授權與治理基礎足夠，本案是新增 ingestion facade 與資料模型，再把 commit 收斂到既有 core mutation 路徑。

## Spec Compliance Matrix（每個 P0 需求一行，全部填完）

| Spec 需求 ID | 需求描述 | 實作方式 | 預計 File:Line | 測試覆蓋 |
|-------------|---------|---------|---------------|---------|
| S1 | delegated credential 可呼叫 `signals/ingest` | 新增 ext API + JWT middleware path 重用 + G0/G1 gate | `src/zenos/interface/ext_ingestion_api.py` | `tests/interface/test_ext_ingestion_api.py::test_ingest_with_delegated_token` |
| S2 | `signals/distill` 產生 task/entry/L2-update candidates，且不 mutation | Distill 實作在 ingestion service，僅生成 candidate + batch | `src/zenos/application/ingestion/service.py` | `tests/application/test_ingestion_service.py::test_distill_produces_candidates_without_core_mutation` |
| S3 | `candidates/commit` 僅落到 `task`/`write(entries)` | Commit adapter 僅允許 task/entry canonical path | `src/zenos/interface/ext_ingestion_api.py` | `tests/application/test_ingestion_service.py::test_commit_uses_canonical_adapters_for_task_and_entry` |
| S4 | mixed payload scope 正確（task+write） | commit 前按 candidate type 做 scope gate | `src/zenos/interface/ext_ingestion_api.py` | `tests/interface/test_ext_ingestion_api.py::test_commit_mixed_payload_requires_task_and_write_scopes` |
| S5 | 禁止直接改 L2/relationship/document | commit payload forbidden target reject + whitelist filter | `src/zenos/application/ingestion/service.py` | `tests/application/test_ingestion_service.py::test_commit_rejects_forbidden_mutation_target` |
| S6 | e2e：raw -> candidate -> task/entry -> review | 建立最小端到端測試流程（含 review queue） | `src/zenos/interface/ext_ingestion_api.py` | `tests/interface/test_ext_ingestion_api.py::test_raw_to_distill_to_commit_to_review_queue` |
| S7 | spec 文件同時掛 ZenOS+Zentropy 兩個 L2 | 已完成（既有 document entity + relationship） | ontology 文檔 `c27c11...` | `mcp__zenos__get(collection=\"documents\", id=\"c27c11...\")` |

## Spec 衝突檢查（Phase 1.2）

- `SPEC-zentropy-ingestion-contract` vs `SPEC-zenos-external-integration`：無衝突。沿用相同 delegated credential + scope 模型。
- `SPEC-zentropy-ingestion-contract` vs `SPEC-task-governance`：無衝突。commit 僅 create task(todo)，驗收仍走 confirm。
- `SPEC-zentropy-ingestion-contract` vs `SPEC-l2-entity-redefinition`：無衝突。L2 只走 candidate->review/confirm，不開直寫通道。
- `SPEC-zentropy-ingestion-contract` vs `SPEC-zenos-auth-federation`：無衝突。ext API 僅消費既有 federation token。

結論：Spec 衝突檢查結果為 **無衝突**。

## Component 架構

```text
Zentropy Backend
  -> POST /api/federation/exchange
  -> POST /api/ext/signals/ingest
  -> POST /api/ext/signals/distill
  -> POST /api/ext/candidates/commit
  -> GET  /api/ext/review-queue

Interface Layer
  ext_ingestion_api.py
    - auth/scope/workspace gate
    - request/response normalization

Application Layer
  ingestion/service.py
  ingestion/repository.py
    - commit adapter -> TaskService / Ontology entry path

Infrastructure Layer
  ingestion repositories (SQL)
    - external_signals
    - ingestion_batches
    - ingestion_candidates
    - ingestion_review_queue
```

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `POST /api/ext/signals/ingest` | `workspace_id, product_id, external_user_id, external_signal_id, event_type, raw_ref, summary, intent, confidence, occurred_at` | JSON | 是 | append raw signal，具 idempotency |
| `POST /api/ext/signals/distill` | `workspace_id, product_id, window{from,to}, max_items` | JSON | 是 | 產生 `batch_id` 與 candidates |
| `POST /api/ext/candidates/commit` | `workspace_id, product_id, batch_id, task_candidates[], entry_candidates[], atomic` | JSON | 是 | 只走 canonical mutation adapter |
| `GET /api/ext/review-queue` | `workspace_id, product_id, status?, limit?, offset?` | Query | 是（workspace/product） | read-only review queue |
| `IngestService.ingest()` | ingest payload | dataclass/dict | 是 | 寫 external_signals，處理 replay |
| `DistillService.distill()` | workspace/product/window/max_items | dataclass/dict | 是 | 產生 ingestion_batches + ingestion_candidates |
| `CommitService.commit()` | batch + candidates + actor scope | dataclass/dict | 是 | type-based scope gate + canonical service calls |
| `ReviewQueueService.list_queue()` | workspace/product/filter | dataclass/dict | 是 | 讀取 queue items |

## DB Schema 變更（無則寫「無」）

新增 migration：`migrations/20260411_0021_ext_ingestion_tables.sql`

1. `zenos.external_signals`
   - `id`, `workspace_id`, `product_id`, `external_user_id`, `external_signal_id`, `event_type`, `raw_ref`, `summary`, `intent`, `confidence`, `occurred_at`, `created_at`
   - unique index: `(workspace_id, external_signal_id)`

2. `zenos.ingestion_batches`
   - `id`, `workspace_id`, `product_id`, `window_from`, `window_to`, `status`, `created_at`, `created_by`

3. `zenos.ingestion_candidates`
   - `id`, `batch_id`, `candidate_type(task|entry|l2_update)`, `payload_json`, `reason`, `confidence`, `status(draft|queued|committed|rejected)`, `created_at`, `updated_at`

4. `zenos.ingestion_review_queue`
   - `id`, `workspace_id`, `product_id`, `candidate_id`, `review_type`, `status(pending|approved|rejected)`, `reviewed_by`, `reviewed_at`, `note`, `created_at`

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 建 ext ingestion API 路由與 request schema | Developer | 4 個 endpoint 可被路由並完成基本驗證（含 workspace/scope gate） |
| S02 | 建 ingestion application services + repositories | Developer | ingest/distill/commit/review queue 四服務可獨立測試，無直接 core bypass |
| S03 | commit adapter 收斂到 canonical mutation | Developer | task candidates 只能走 TaskService；entry candidates 只能走 entry path |
| S04 | DB migration + repository 實作 | Developer | 4 張新表可建置、查詢、寫入，idempotency index 生效 |
| S05 | 單元/整合測試（scope + forbidden mutation + e2e） | QA | 覆蓋 spec matrix S1-S6，全部 PASS |
| S06 | 文件與 ontology 同步（TD 註冊 + relationship） | Architect | TD 文件入庫，掛到 ZenOS + Zentropy L2 |

## Risk Assessment（四小節全部必填，不可留空）

### 1. 不確定的技術點
- [未確認] 批次 commit 的交易語意（部分成功或全有全無）對 UX 的最終偏好。
- [未確認] distill 候選生成是否需要同步寫 review queue，或由 commit 後再建 queue。

### 2. 替代方案與選擇理由
- 方案 A：`/api/ext/*` 直接寫 core 表。
  - 不選：會形成平行治理通道，與 spec/ADR 衝突。
- 方案 B：commit 只當轉發，不做 type-based scope gate。
  - 不選：mixed payload 會放大權限錯配風險。
- 方案 C（採用）：ext facade + canonical adapter + scope-by-candidate-type。
  - 選擇理由：最貼合現有授權與治理基礎，且可增量落地。

### 3. 需要用戶確認的決策
- `atomic` 預設值是否固定 `false`（允許部分成功），或改為 `true`（全有全無）。
- `l2_update_candidate` 是否永遠只進 review queue，或可選擇直接自動開 follow-up task。

### 4. 最壞情況與修正成本
- 最壞情況：commit path 漏洞導致非白名單 mutation 被寫入。
  - 修正成本：中等（需回補資料與補測試）。
  - 緩解：先上 forbidden mutation 測試與 production audit log。
- 最壞情況：scope gate 錯誤導致低權限 token 可提交 mixed payload。
  - 修正成本：中等偏高（權限事故）。
  - 緩解：在 interface 層與 service 層雙重檢查 + JWT integration test。
