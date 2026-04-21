---
type: SPEC
id: SPEC-zenos-external-integration
status: Draft
ontology_entity: agent-integration
created: 2026-04-10
updated: 2026-04-21
---

# Feature Spec: ZenOS External Integration Contract (v1)

> Layering note: 本文件是「對外接入說明層」；核心語意仍以 `SPEC-zenos-core`、`SPEC-identity-and-access`、`SPEC-task-governance`、`SPEC-zenos-auth-federation` 為準。

## 1. 目的

定義外部 application（以 Zentropy 為首例）如何安全接入 ZenOS Core，使用統一的 knowledge/action/access runtime，而不改寫 ZenOS 核心語意。

---

## 2. 接入模式

### 2.1 模式 A：Direct ZenOS MCP（現行）

- 呼叫端直接持有 ZenOS API key
- 適用：CLI、內部 agent、早期整合 PoC
- 優點：接入快
- 限制：不適合多 end-user 權限分流

### 2.2 模式 B：App-facing Federation（推薦）

- 外部 app 先完成自身 end-user authentication
- app server 呼叫 `/api/federation/exchange` 交換 delegated credential
- 後續用 delegated token 呼叫 ZenOS MCP / API
- 適用：Zentropy、CRM facade、多租戶 app

---

## 3. 權責邊界（強制）

### 3.1 外部 app 必須負責

1. end-user authentication（自己的 IdP / Firebase project）
2. app workflow 與 UI（milestone、execution step、subtask）
3. 將 app 行為映射到 ZenOS 的 `entity/task/plan` contract

### 3.2 ZenOS 必須負責

1. workspace / role / visibility 最終授權
2. task lifecycle 與 confirm gate
3. ontology 治理（draft/confirm、analyze、document contract）
4. delegated credential 驗證與 scope enforcement

### 3.3 外部 app 不得

1. 偽造 ZenOS principal 或 workspace scope
2. 跳過 ZenOS authorization 直接做 mutation
3. 用 app-specific subtask 取代 ZenOS Task 驗收邊界

---

## 4. Zentropy 接入規格（v1）

### 4.1 最小能力矩陣

| Zentropy 能力 | ZenOS 對應 | 必填/規則 |
|---|---|---|
| 查 context | `search` / `get` / `read_source` | `read` scope |
| 建立行動項 | `task(action="create")` | `title` 動詞開頭、`status=todo` |
| 更新執行進度 | `task(action="update")` | `review` 前必須有 `result` |
| 驗收結案 | `confirm(collection="tasks")` | 只能驗收 `review` 狀態 |
| 多任務編排 | `plan(action=create/update/get/list)` | `goal/owner/status/entry/exit` |
| 治理巡檢 | `analyze` | 回傳 warning/suggestions 後需跟進 |

### 4.2 Zentropy 到 ZenOS 的映射規則

1. Zentropy 的 milestone/sprint 群組 -> ZenOS `Plan`
2. 需要跨人協作/驗收/知識回饋的工作 -> ZenOS `Task`
3. 僅 app 內部執行步驟 -> 保留在 Zentropy，不進 ZenOS Core
4. 重要產出文件 -> 以 ZenOS document contract 註冊（single/index）

### 4.3 認證與授權流程（推薦）

1. Zentropy user 在 Zentropy 完成登入
2. Zentropy backend 呼叫 ZenOS `/api/federation/exchange`
3. 取得 delegated token（含 `scopes`、`workspace_ids`）
4. Zentropy backend 使用 delegated token 呼叫 ZenOS MCP/API
5. ZenOS server 依 active workspace context 做最終授權裁切

---

## 5. 對外 API / Tool Contract（v1）

### 5.1 Federation Exchange

- Endpoint: `POST /api/federation/exchange`
- Request 最小欄位：`app_id`, `app_secret`, `external_token`, `issuer`, `scopes[]`
- Response 最小欄位：`access_token`, `token_type`, `expires_in`, `scopes`, `principal_id`

### 5.2 Scope 規則

- `read`: 只讀查詢（search/get/read_source/analyze 等）
- `write`: 知識與治理寫入（write/confirm/journal_write 等）
- `task`: task/plan mutation

> `write` 不等於 `task`；外部 app 需按最小權限申請 scope。

### 5.2.1 Governed Access Contract

- `read` 代表可進入 ZenOS 的只讀查詢面，不代表自動取得所有原文
- 外部 app / agent 對資料的預設暴露層級，必須是 `metadata + summary`
- `read_source` 可回傳三種結果：
  - `summary` / `snapshot_summary`
  - `full-content`
  - `FORBIDDEN` / `SNAPSHOT_UNAVAILABLE`
- Google Workspace 的 `full-content` 若走 `per_user_live`，server 必須以當前 caller 的 delegated credential / principal 做 live retrieval；不得回退到 workspace-shared 全文副本
- 是否能拿到 `full-content`，除 `read` scope 外，還必須同時通過：
  - active workspace
  - workspace role / visibility
  - connector scope
  - content policy（該 source 是否允許原文存取）
- 外部 app 不得把 delegated credential 視為「全資料通行證」

### 5.3 Task 狀態契約

- 正式狀態：`todo`, `in_progress`, `review`, `done`, `cancelled`
- `done` 不可由 `task(update)` 直接設置，必須走 `confirm`
- 阻塞資訊用 `blocked_by` / `blocked_reason` 表達，不使用 `blocked` 狀態

---

## 6. 驗收標準（Integration Done Criteria）

外部 app（Zentropy）整合完成必須同時滿足：

1. 能用 delegated credential 成功呼叫 `search/get/task/plan`
2. `read/write/task` scope 拒絕與放行行為可重現且可測
3. Task 流程符合 `todo -> in_progress -> review -> confirm -> done`
4. app 端無繞過 ZenOS 授權的直寫路徑
5. 至少 1 條端到端流程證據（登入 -> exchange -> 建 task -> review -> confirm）

### Acceptance Criteria

- `AC-EIC-01` Given 外部 app 以 delegated credential 呼叫 `search/get/task/plan`，When token 的 `workspace_ids` 與 `scopes` 合法，Then 請求可成功執行，且結果仍受 active workspace / role / visibility 裁切
- `AC-EIC-02` Given token 缺少 `write` scope，When 外部 app 呼叫 `write/confirm/journal_write/upload_attachment`，Then server 回 `FORBIDDEN`
- `AC-EIC-03` Given token 缺少 `task` scope，When 外部 app 呼叫 `task/plan` mutation，Then server 回 `FORBIDDEN`
- `AC-EIC-04` Given 外部 app 擁有 `read` scope 但目標 source 僅允許 summary access，When 呼叫 `read_source`，Then server 只可回傳摘要型結果或拒絕，不可回傳 full-content
- `AC-EIC-05` Given 外部文件位於未被該 workspace 授權的 connector scope 外，When 外部 app 查詢 context 或讀取 source，Then ZenOS 不得暴露該文件的 metadata、summary 或 full-content
- `AC-EIC-06` Given 外部 app 嘗試繞過 delegated credential 直寫 ZenOS Core 資料，When 請求未通過正式 auth/runtime path，Then server 必須拒絕
- `AC-EIC-07` Given 外部 app 完成一條端到端流程（登入 -> exchange -> 建 task -> review -> confirm），When 事後查核 audit / tool event，Then 可看見 actor、resource、action 與 outcome，但預設不得看到原始文件內容或 prompt/query 原文

> Google Workspace `per_user_live` 的 source contract 與 AC，另見 `SPEC-google-workspace-per-user-retrieval`。

---

## 7. Rollout 建議

### Phase 1（現在）
- 允許 Direct API key 與 Federation 並行
- 新 app 預設走 Federation 模式

### Phase 2
- 外部 app 全面改用 delegated credential
- API key 收斂為 CLI/internal ops/break-glass

---

## 8. 與既有 Spec 關係

本 spec 不覆寫以下文件，只定義對外接入視角：

- `SPEC-zenos-core`（Core 分層與邊界）
- `SPEC-identity-and-access`（身份與授權）
- `SPEC-zenos-auth-federation`（federation 契約）
- `SPEC-agent-integration-contract`（MCP 接入哲學）
- `SPEC-task-governance`（task lifecycle 與治理）
