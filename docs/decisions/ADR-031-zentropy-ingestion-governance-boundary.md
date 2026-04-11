---
type: ADR
id: ADR-031
status: Accepted
ontology_entity: MCP 介面設計
created: 2026-04-11
updated: 2026-04-11
---

# ADR-031: Zentropy Ingestion 的 ZenOS 內部治理與 API 能力邊界

## Context

Zentropy 要把高頻 end-user 輸入（task/idea/reflection）沉澱到 ZenOS，但現況有兩個結構風險：

1. `SPEC-zentropy-ingestion-contract` 先前描述了 `/api/ext/signals/*` 流程，但對「可改什麼/不可改什麼」邊界不夠硬，容易變成平行 mutation 通道。
2. 現有 codebase 只有 `POST /api/federation/exchange` 已實作（`src/zenos/interface/federation_api.py`）；`/api/ext/signals/ingest`、`/api/ext/signals/distill`、`/api/ext/candidates/commit`、`/api/ext/review-queue` 尚未落地。

同時，ZenOS 既有治理 runtime 已存在：

- delegated credential + scope/workspace enforcement（`src/zenos/interface/mcp/_auth.py`、`_scope.py`）
- Core mutation gate（`task.py`、`write.py`、`confirm.py`）
- server-side governance intelligence（`governance_ai.py`、`governance_service.py`）

因此關鍵決策不是「要不要治理」，而是「怎麼把 Zentropy 小模型前置能力接進既有 ZenOS server 治理，不產生第二套規則引擎」。

## Decision

### D1. 統一為「雙層 API」模型：Ingestion Facade API + Core Governance API

我們統一為兩層：

1. Ingestion Facade API（`/api/ext/*`）只處理 raw signal、candidate、review queue。
2. Core Governance API（`task`、`write(entries)`、`confirm`、`analyze`）保持唯一治理 authority。

`/api/ext/*` 不得成為平行治理入口；所有最終 mutation 必須收斂回 Core API。

### D2. 限定 `/api/ext/*` 的能力邊界為白名單，禁止黑箱擴權

我們限定：

1. `signals/ingest` 只允許 append raw signal，禁止任何 core mutation。
2. `signals/distill` 只允許產生 candidates，禁止任何 core mutation。
3. `candidates/commit` 只允許經由 canonical adapter 建立 `task(todo)` 與 `entries`。
4. `review-queue` 只讀，不可 mutation。

我們禁止：

1. 直接寫 `entities`、`relationships`、`documents`、`protocols`、`blindspots`。
2. 直接呼叫 `confirm` 使候選生效。
3. 直接改 L2 summary/impacts。

### D3. 改為「scope-by-candidate-type」執法，不使用單一寬鬆 scope

我們要求：

1. `signals/ingest`、`signals/distill` 需要 `write`。
2. `candidates/commit` 對 `task_candidates` 需要 `task`；對 `entry_candidates` 需要 `write`。
3. mixed payload（task + entry）必須同時具備 `task` 與 `write`。
4. `review-queue` 需要 `read`。

這個設計沿用既有 `read/write/task` 粗粒度模型，避免新增大量新 scope。

### D4. 改為「server 八段 gate」實作，不讓小模型結果直接生效

ZenOS server 必須依序執行：

1. G0 Credential Gate（delegated credential 驗證）
2. G1 Scope + Workspace Gate
3. G2 Schema Gate
4. G3 Distill Gate（語意候選）
5. G4 Structural Gate（Task/Entry 驗證）
6. G5 Commit Gate（canonical mutation）
7. G6 Human Gate（review/confirm）
8. G7 Feedback Gate（analyze + follow-up）

小模型可以輔助 G3，但不得越過 G4/G5/G6。

### D5. 限定 L2 升級路徑為「entries 累積 -> L2 candidate -> review/confirm」

我們限定：

1. ingestion pipeline 可以沉澱到 L2 entries。
2. ingestion pipeline 不可直接升級或改寫 L2 entity。
3. L2 變更必須走 `SPEC-l2-entity-redefinition` 的三問 + impacts gate，並通過 review/confirm。

### D6. 改為「Spec 先行、ADR 鎖定、程式再落地」的 rollout

本次先把硬邊界寫進 `SPEC-zentropy-ingestion-contract`（SSOT），再由本 ADR 鎖定 ZenOS 內部實作決策。後續開發不得再以 skill/prompt 約定取代 spec 邊界。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| 把治理主要放在 Zentropy 小模型，ZenOS 只存資料 | 整合速度快 | 規則可被繞過；多 app 一致性失效；難以審計 | 違反 ZenOS 作為最終治理 authority 的定位 |
| 開放 `/api/ext/*` 直接寫 entities/relationships | 實作表面簡單 | 形成平行 mutation 通道；L2 會被高頻輸入污染 | 與 `SPEC-zenos-core`、`SPEC-task-governance`、`SPEC-l2-entity-redefinition` 衝突 |
| 完全沿用 skill 治理，不新增 server ingestion gate | 初期開發成本低 | 無法保證執法一致；外部 app 難以標準化接入 | 違反 ADR-013 的 server 結構執法方向 |

## Consequences

- 正面：
  - Zentropy 可以使用小模型做前置收斂，但最終治理仍由 ZenOS server 強制執行。
  - `/api/ext/*` 不會演化成平行寫入後門，核心語意維持單一權威。
  - ingestion contract 可被測試與審計（scope、workspace、mutation whitelist）。
  - L2 長期品質可透過「entries 累積 + review/confirm」穩定演化。
- 負面：
  - 初期實作成本上升，需要新增 raw signal/candidate/review queue 資料模型與 API。
  - 端點行為較嚴格，Zentropy 端需處理更多 `rejected`/`warnings` 分支。
  - mixed payload scope 驗證會提高整合複雜度。
- 後續處理：
  - [未確認] raw signal 與 candidate 的最終 DB schema（建議另開 TD）。
  - 需要補上 ext ingestion path 的整合測試（JWT scope、workspace、mutation 邊界）。

## Implementation

1. 更新 `docs/specs/SPEC-zentropy-ingestion-contract.md`，加入 endpoint capability matrix、scope-by-candidate-type、server gate pipeline、L2 禁止直寫規則。
2. 新增 `src/zenos/interface/ext_ingestion_api.py`（或等價模組），提供 `/api/ext/signals/ingest`、`/api/ext/signals/distill`、`/api/ext/candidates/commit`、`/api/ext/review-queue`。
3. 新增 `src/zenos/application/ingestion/` 服務層，拆分 raw ingest、distill、commit、review queue orchestration。
4. `candidates/commit` 必須重用既有 core service path：Task 走 `TaskService`，Entry 走 ontology write/entry path，不另建平行 mutation service。
5. 在 ext API 入口加 scope/workspace 驗證，規則對齊 `src/zenos/interface/mcp/_auth.py`、`_scope.py` 的授權語意。
6. 補測試：
   - JWT delegated credential + scope gate（含 mixed payload）
   - workspace_ids claim 驗證
   - forbidden mutation（entities/relationships/documents）拒絕
   - e2e：raw signal -> candidate -> commit -> review queue -> confirm
