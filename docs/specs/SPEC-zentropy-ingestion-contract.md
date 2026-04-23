---
type: SPEC
id: SPEC-zentropy-ingestion-contract
status: Approved
ontology_entity: mcp-interface
created: 2026-04-11
updated: 2026-04-23
depends_on: SPEC-zenos-core, SPEC-zenos-external-integration, SPEC-task-governance, SPEC-ontology-architecture v2 §7, SPEC-zenos-auth-federation
---

# Feature Spec: Zentropy Signal Ingestion Contract (v1)

> Layering note: 本文件是「Zentropy 輸入訊號接入 ZenOS」的對外合約與治理邊界定義。核心語意仍以 `SPEC-zenos-core`、`SPEC-zenos-external-integration`、`SPEC-task-governance`、`SPEC-ontology-architecture v2 §7`（L2 canonical，舊 `SPEC-l2-entity-redefinition` 已併入）、`SPEC-zenos-auth-federation` 為準。
>
> Decision binding: ZenOS 側內部治理實作決策由 `ADR-031` 鎖定；本文件是能力邊界的規格層 SSOT。

## 1. 目的（Spec 層強制邊界）

定義 Zentropy 如何在不繞過 ZenOS 核心治理的前提下，持續沉澱 end-user 輸入（task/idea/reflection）到 ZenOS knowledge/action runtime。

本文件的核心目標不是描述 UX，而是嚴格定義：

1. 哪些 API 是 ingestion facade，哪些是 ZenOS 核心治理 API。
2. 每個 ingestion API 可以改什麼、禁止改什麼。
3. ZenOS server 內部治理 pipeline 的強制 gate。
4. Zentropy 小模型與 ZenOS server 的分治邊界。

## 2. 設計原則

1. **分治而不分裂**：Zentropy 負責高頻輸入收斂；ZenOS 負責最終治理執法。
2. **小模型前置，Server 決策後置**：小模型只能產生候選，不得直接寫核心知識。
3. **Raw 優先，延遲蒸餾**：先保留 raw signal，再批次蒸餾，降低即時誤判污染。
4. **唯一 mutation 通道**：所有最終 mutation 必須收斂到 ZenOS 既有 Core contract（`task`、`write(entries)`、`confirm`）。

## 3. 範圍與非範圍

### 3.1 In Scope

- Zentropy -> ZenOS 的 ingestion facade API 合約
- signals -> candidates -> core mutation 的治理流程
- L2 entries 沉澱與 L2 更新候選的升級路徑
- scope / workspace / state machine 的 server-side hard gate

### 3.2 Out of Scope

- Zentropy 端完整 UX（輸入框、時間軸、看板）
- ZenOS 內部模型權重、prompt 細節與 provider 選型
- 直接改寫既有 `/zenos-capture`、`/zenos-sync` workflow 行為

## 4. 分治邊界（強制）

### 4.1 Zentropy 責任

1. 蒐集 end-user raw input（task/idea/reflection）。
2. 以小模型做場景內初步路由與去噪（非最終治理）。
3. 以 delegated credential 呼叫 ZenOS ingestion facade API。
4. 呈現 ZenOS 回傳的 candidate/review queue，不自行宣告「已生效」。

### 4.2 ZenOS 責任

1. delegated credential、workspace、scope 的最終授權判定。
2. 對 signals/candidates 的最終治理決策與拒絕。
3. 將候選寫入 Core mutation 通道（`task` / `write(entries)`）。
4. 透過 `confirm` / `analyze` 維持長期治理閉環。

### 4.3 禁止事項（Hard Ban）

1. Zentropy 不得直接寫入 ZenOS L2 summary、impacts、relationships。
2. Zentropy 不得跳過 ZenOS 授權模型做任何 mutation。
3. Zentropy 不得用 app-specific subtask 取代 ZenOS task review/confirm 語意。
4. `/api/ext/*` 不得成為平行治理後門。

## 5. 治理 API 能力邊界（Spec 層硬規範）

> 認證：所有 `/api/ext/*` endpoint 均需 delegated credential（federation exchange 後取得）。
>
> scope 模型沿用 `SPEC-zenos-external-integration` 與 `SPEC-zenos-auth-federation`：`read`、`write`、`task`。

### 5.1 Endpoint Capability Matrix（強制）

| Endpoint | 必要 scope | 允許能力（Allowed） | 禁止能力（Forbidden） |
|---|---|---|---|
| `POST /api/ext/signals/ingest` | `write` | 只允許 append raw signal（不可逆事件紀錄） | 建立/更新 task、entries、entities、relationships、documents |
| `POST /api/ext/signals/distill` | `write` | 產生 candidate snapshot（task/entry/L2-update candidate） | 任何 Core mutation |
| `POST /api/ext/candidates/commit` | `task`（task candidates）、`write`（entry candidates）；mixed payload 需同時具備兩者 | 僅可透過 ZenOS Core contract 建立 `task(todo)` 與 `entries` | 直接寫 `entities`、`relationships`、`documents`、`protocols`、`blindspots`；不得呼叫 `confirm` |
| `GET /api/ext/review-queue` | `read` | 讀取待審候選與待確認項目 | 任意 mutation |

### 5.2 Commit 欄位白名單（強制）

1. `task_candidate` 只允許映射到：`title`、`description`、`acceptance_criteria`、`linked_entities`、`priority`、`assignee`、`assignee_role_id`、`plan_id`、`plan_order`、`due_date`、`source_metadata`。
2. `entry_candidate` 只允許映射到：`entity_id`、`type(decision|insight|limitation|change|context)`、`content`、`context`。
3. 任何超出白名單欄位一律忽略並回傳 `warnings`；若影響安全/授權，回傳 `status="rejected"`。
4. `status`、`created_by`、`updated_by`、`workspace_id` 由 server 決定，caller 不可強制覆寫。

## 6. ZenOS Server 內部治理 Pipeline（必做）

### 6.1 Pipeline Stages

1. **G0 Credential Gate**：驗 delegated credential，有效期、issuer、principal。
2. **G1 Scope + Workspace Gate**：驗 scope 與 active workspace 是否在 token `workspace_ids`。
3. **G2 Schema Gate**：驗 payload 結構、欄位上限、枚舉值、時間窗。
4. **G3 Distill Gate（語意層）**：小模型/規則只產生 candidates，不可直接 mutation。
5. **G4 Structural Gate（結構層）**：套用 Task/Entry 既有 server-side 驗證規則。
6. **G5 Commit Gate**：僅透過 Core contract 寫入（`task` / `write(entries)`）。
7. **G6 Human Gate**：高風險候選進 review queue，最終生效需 `confirm` 或等價人工驗收。
8. **G7 Feedback Gate**：`analyze` 與治理任務回寫，形成長期品質閉環。

### 6.2 Gate 不可下放原則

1. G0/G1/G4/G5 必須在 ZenOS server 端執行。
2. Zentropy 可優化 G3 的前置路由，但不得跳過 server gate。
3. 任一 gate 失敗需回傳統一格式：`status/data/warnings/suggestions/governance_hints/rejection_reason`。

## 7. API Contract（v1）

### 7.1 `POST /api/ext/signals/ingest`

用途：接收 Zentropy 標準化訊號，僅 append raw signal，不做 core mutation。

最小 request payload：

```json
{
  "workspace_id": "string",
  "product_id": "423e9df420cb47adba7d514a3211aa4d",
  "external_user_id": "string",
  "external_signal_id": "string",
  "event_type": "task_input|idea_input|reflection_input",
  "raw_ref": "app://zentropy/signals/{id}",
  "summary": "string<=280",
  "intent": "todo|explore|decide|reflect",
  "confidence": 0.0,
  "occurred_at": "2026-04-11T00:00:00Z"
}
```

response：

```json
{
  "status": "ok",
  "data": {
    "signal_id": "string",
    "queued": true,
    "idempotent_replay": false
  },
  "warnings": [],
  "suggestions": [],
  "governance_hints": []
}
```

規則：

1. `external_signal_id` 在同 workspace 需具 idempotency。
2. `ingest` 不得直接改任何 ontology 或 task 狀態。

### 7.2 `POST /api/ext/signals/distill`

用途：批次蒸餾 `signals -> candidates`（task/entry/l2_update），不做 core mutation。

最小 request payload：

```json
{
  "workspace_id": "string",
  "product_id": "423e9df420cb47adba7d514a3211aa4d",
  "window": {
    "from": "2026-04-10T00:00:00Z",
    "to": "2026-04-11T00:00:00Z"
  },
  "max_items": 50
}
```

response（節錄）：

```json
{
  "status": "ok",
  "data": {
    "batch_id": "string",
    "task_candidates": [],
    "entry_candidates": [],
    "l2_update_candidates": [],
    "dropped_signals": []
  },
  "warnings": [],
  "suggestions": [],
  "governance_hints": []
}
```

規則：

1. `distill` 只能產生候選，不得 commit。
2. 每個 candidate 必須帶 `reason` 與 `confidence`（0.0~1.0）。
3. `l2_update_candidates` 只進 review queue，不可直接改 L2 entity。

### 7.3 `POST /api/ext/candidates/commit`

用途：將 candidates 提交到 ZenOS Core mutation，並套用治理 gate。

最小 request payload：

```json
{
  "workspace_id": "string",
  "product_id": "423e9df420cb47adba7d514a3211aa4d",
  "batch_id": "string",
  "task_candidates": [],
  "entry_candidates": [],
  "atomic": false
}
```

行為（強制）：

1. task candidate -> `task(action="create")`（預設 `status=todo`）
2. entry candidate -> `write(collection="entries")`
3. `l2_update_candidate` 不可在此 endpoint 直接落 L2 mutation，僅可建立 review queue item 或 follow-up task
4. 低信心或規則不足 -> `status=rejected` + 修正建議
5. mixed candidates 需同時具備 `task` + `write` scope

最小 response（節錄）：

```json
{
  "status": "ok",
  "data": {
    "committed": [],
    "rejected": [],
    "queued_for_review": []
  },
  "warnings": [],
  "suggestions": [],
  "governance_hints": []
}
```

### 7.4 `GET /api/ext/review-queue`

用途：給 Zentropy 顯示待人確認項目（task review、entry/L2 update candidates）。

規則：

1. 此 endpoint 為 read-only，不得產生任何 mutation。
2. 只回傳 caller 在 active workspace 可見的 queue items。
3. queue item 若需最終生效，必須回到 `confirm` 或等價人工驗收路徑。

## 8. 訊號沉澱到 L2 Entries 的標準流程

1. Zentropy 收到 raw input，寫入 app 內 raw log。
2. Zentropy 小模型做場景路由，送 `signals/ingest`。
3. ZenOS 以時間窗批次執行 `signals/distill`：
   - task-like -> task candidate
   - knowledge-like -> entry candidate（decision/insight/limitation/change/context）
4. commit 後，entry 寫入 canonical entries，必要時同步放入 review queue。
5. 週期性聚合同一 L2 的 entries，產生 L2 update candidate（含 impacts draft）。
6. 最終升級仍需走 ZenOS confirm / task 驗收，不自動升 active L2。

## 9. L2 升級邊界（強制）

1. ingestion API 不得直接改 `entities.summary`、`entities.tags`、`impacts relationships`。
2. L2 更新必須以 `l2_update_candidate -> review -> confirm` 路徑執行。
3. 若需要正式改 L2，必須走既有 L2 治理規範（`SPEC-ontology-architecture v2 §7`；舊 `SPEC-l2-entity-redefinition` 已併入）。

## 10. 治理執行模型

### 10.1 ZenOS Server（必做）

1. Hard gate：auth/scope/狀態機/欄位完整性
2. Soft gate：小模型語意檢查（accept/draft/reject）
3. 回傳統一格式：`status/data/warnings/suggestions/governance_hints`

### 10.2 Zentropy Adapter（可演進）

1. 場景收斂分類（高頻低風險）
2. 噪音抑制與訊號去重（同一 session）
3. 不做最終知識治理決策

## 11. Spec 衝突檢查

本文件與以下規範無衝突，且採「不覆寫」原則：

1. `SPEC-zenos-core`：沿用 Core/App 分層與 Action/Identity 邊界。
2. `SPEC-zenos-external-integration`：沿用 delegated credential + scope 合約。
3. `SPEC-task-governance`：沿用 task lifecycle 與 review/confirm gate。
4. `SPEC-ontology-architecture v2 §7`：沿用 L2 升級條件與 impacts gate（2026-04-23 起 canonical）。
5. `SPEC-zenos-auth-federation`：沿用 federation exchange 與 delegated token 模型。

## 12. Ontology 連結（本 spec 強制綁定）

本文件必須同時連到以下兩個產品的 L2：

1. **ZenOS / MCP 介面設計**  
   entity_id: `GAWPNrvdToJGHTtYC2W2`
2. **Zentropy / Brain Dump 輸入處理**  
   entity_id: `f1d6088c85074cbb868e448e4c93cd09`

連結目的：

1. ZenOS 端 API 契約變更可追溯到 MCP 介面治理
2. Zentropy 端輸入策略變更可追溯到 Brain Dump 核心模組

## 13. 與既有 Spec / ADR 關係

- `SPEC-zenos-core`：沿用 Core 與 Application 分層邊界
- `SPEC-zenos-external-integration`：沿用 federation 與外部接入原則
- `SPEC-task-governance`：task lifecycle 與 confirm gate 不重定義
- `SPEC-ontology-architecture v2 §7`：L2 升降級與 impacts gate 不重定義（canonical；舊 `SPEC-l2-entity-redefinition` 已併入）
- `SPEC-agent-integration-contract`：日常寫入仍屬 MCP + server governance
- `ADR-031`：鎖定 ZenOS 內部治理實作策略與 rollout

## 14. Done Criteria

1. Zentropy 可用 delegated credential 呼叫 `signals/ingest`
2. `signals/distill` 可產生 task/entry/L2-update candidates，且不做 mutation
3. `candidates/commit` 僅能落到既有 `task`/`write(entries)` 契約，不新增平行寫入通道
4. `candidates/commit` 對 mixed payload 正確執行 scope 檢查（`task`+`write`）
5. 任一 API 嘗試直接改 L2/relationship/document 時，必須被拒絕
6. 至少一條端到端證據：raw input -> candidate -> task/entry -> review queue -> confirm
7. 本文件在 ontology 中同時掛載 ZenOS + Zentropy 兩個 L2（見第 12 節）
