---
type: SPEC
id: SPEC-google-workspace-per-user-retrieval
status: Draft
ontology_entity: ingestion-adapter
created: 2026-04-21
updated: 2026-04-23
depends_on: SPEC-doc-governance, SPEC-identity-and-access, SPEC-zenos-auth-federation
---

# Feature Spec: Google Workspace Connector v0 — Per-User Live Retrieval

## 1. 背景

ZenOS 現有外部文件路線只有兩種：

1. `helper ingest`：把外部文件壓成 `snapshot_summary`
2. `zenos_native`：把 markdown snapshot 存進 ZenOS delivery

這足夠支撐 dogfood，但還不夠支撐企業資料治理。缺口有兩個：

- **connector scope 沒有 runtime。** `SPEC-identity-and-access` 已要求 workspace 必須先定義 allowed containers，但目前沒有正式資料模型與 enforcement。
- **per-user live retrieval 沒有 contract。** 使用者若要沿用自己 Google Workspace 的原生 ACL，ZenOS 必須支援「只在當前使用者要求時，用該使用者自己的外部身份 live 取全文」，而不是先把全文同步成 workspace 共享副本。

本 spec 定義最小可落地版本：

- Google Workspace 先走 `per-user live retrieval`
- ZenOS 只共享 metadata / summary
- 全文必須走 live reader，不得偷落成共享 cache
- live reader 先走 **internal-first sidecar**：ZenOS server 呼叫客戶環境內的 Google Workspace connector sidecar；每位使用者仍以自己的公司帳號在 sidecar 內完成綁定

## 2. 目標

1. 讓 ZenOS 可以表達「這份 gdrive source 是 per-user live retrieval，不是共享全文」
2. 讓 workspace owner 能限制 connector 只允許某些 Shared Drive / Folder / container
3. 讓 `read_source`、Dashboard docs metadata、MCP `get(document)` 對 out-of-scope source fail closed
4. 讓 delegated credential / current principal 成為 live retrieval 的正式身份來源
5. 讓 Settings 頁能配置 Google Workspace sidecar 與 container allowlist，並提供健康檢查與操作步驟

## 3. 非目標

- 不在 ZenOS 內實作 Google OAuth consent screen
- 不做 webhook / 自動 sync
- 不做 workspace-shared full ingest
- 不做 source-level ACL editor；P0 只做 workspace connector scope + per-user live retrieval
- 不在本 repo 內交付真正的 Google sidecar 服務本體；本 spec 只定 ZenOS 與 sidecar 的 contract

## 4. 核心模型

### 4.1 Workspace Connector Scope

workspace 的 connector allowlist 先存於 `partner.preferences.connectorScopes`。

格式：

```json
{
  "connectorScopes": {
    "gdrive": {
      "containers": ["drive:finance", "folder:roadmap"]
    }
  }
}
```

規則：

- config 不存在：維持 legacy 行為，不額外阻擋
- config 存在但 `containers=[]`：代表此 connector 已接入但目前不允許任何 container
- source 若沒有 `container_id` / `container_ids`，而 workspace 對該 connector 已定義 allowlist，則 fail closed

### 4.2 Source Contract

外部 source 新增兩個正式欄位：

| 欄位 | 型別 | 說明 |
|------|------|------|
| `container_id` / `container_ids` | string / string[] | 此 source 所屬的 connector container |
| `retrieval_mode` | `direct \| snapshot \| per_user_live` | `per_user_live` 代表全文只能走 user-scoped live fetch |

補充：

- `content_access=summary`：只允許摘要
- `content_access=full` + `retrieval_mode=per_user_live`：允許全文，但必須走 live reader
- `snapshot_summary` 仍可存在，但只是 discover/summary 層，不代表 workspace 共享全文

### 4.3 Live Retrieval Boundary

當 source 設為 `retrieval_mode=per_user_live` 時：

- ZenOS 不得回退到共享全文副本
- `read_source` 必須使用「當前 caller 的 delegated credential / principal」觸發 live reader
- 若 live reader 或 user-scoped credential 不存在，回 `LIVE_RETRIEVAL_REQUIRED`

### 4.4 Google Workspace Sidecar 設定

ZenOS 以 `partner.preferences.googleWorkspace` 保存 sidecar 連線資訊：

```json
{
  "googleWorkspace": {
    "sidecar_base_url": "http://google-workspace-sidecar.internal:8787",
    "sidecar_token": "gwsc-...",
    "principal_mode": "partner_email"
  }
}
```

規則：

- `sidecar_base_url`：ZenOS server 可連到的 sidecar URL
- `sidecar_token`：ZenOS 呼叫 sidecar 的 shared secret；若為空代表不啟用
- `principal_mode`：P0 固定為 `partner_email`
- Settings 頁必須允許 owner 保存上述設定，並同頁保存 `connectorScopes.gdrive.containers`

### 4.5 Sidecar Contract

P0 sidecar contract：

- `GET {sidecar_base_url}/health`
  - request header: `X-Zenos-Connector-Token: {sidecar_token}`
  - response: `{status, message?, capability?}`
- `POST {sidecar_base_url}/read-source`
  - request header: `X-Zenos-Connector-Token: {sidecar_token}`
  - request body:

```json
{
  "connector": "gdrive",
  "doc_id": "doc-1",
  "source_id": "src-1",
  "source_uri": "https://drive.google.com/file/d/1abcXYZ/view",
  "requested_access": "full",
  "principal": {
    "partner_id": "partner-1",
    "email": "user@company.com",
    "display_name": "Alice"
  }
}
```

規則：

- ZenOS 必須把當前 caller 的 email 帶給 sidecar，作為 per-user identity binding
- sidecar 失敗時 ZenOS 不得回退到共享全文副本
- Settings 頁必須明確告知：每位公司成員要先在 sidecar / CLI 內完成自己的 Google Workspace 綁定

## 5. P0 需求

### P0-1: Connector Scope Runtime

- source 若位於未授權 container，ZenOS 不得暴露其 metadata / summary / full-content
- document 若所有 source 都 out of scope，文件本身也不可見
- 若 document 是 mixed-source bundle，僅保留 in-scope source metadata

### P0-2: Per-User Live Retrieval

- `gdrive` source 可標為 `retrieval_mode=per_user_live`
- `read_source` 在 `content_access=full` 時只可走 live reader
- `content_access=summary` 時可回 `snapshot_summary`

### P0-3: Cross-Surface Consistency

- MCP `read_source`
- MCP `get(collection="documents")`
- Dashboard `GET /api/data/entities?type=document`
- Dashboard `GET /api/docs/{doc_id}`

以上四條路徑對同一 source 的 connector scope 結果必須一致。

### P0-4: Settings / Onboarding

- Settings 頁必須提供 Google Workspace connector 區塊
- 使用者必須能保存：
  - sidecar base URL
  - sidecar token
  - gdrive allowed containers
- Settings 頁必須提供 health check
- Settings 頁必須用白話列出 setup steps：部署 sidecar、每位使用者綁定自己的 Google Workspace 帳號、填入 allowlist

## 6. Acceptance Criteria

- `AC-GWPR-01` Given workspace 對 `gdrive` 已定義 connector scope 且 `containers=[]`，When caller 讀取只含 gdrive source 的文件，Then MCP 與 Dashboard 都不得暴露該文件或其 source metadata
- `AC-GWPR-02` Given gdrive source 的 `container_id` 不在 workspace allowlist，When caller 執行 `read_source(doc_id, source_id)`，Then server 回 `NOT_FOUND` 或等價 concealment，而不是回 summary/full-content
- `AC-GWPR-03` Given document 同時有一個 in-scope gdrive source 與一個 out-of-scope gdrive source，When caller 讀取文件 metadata，Then 文件仍可見，但 response 只包含 in-scope source
- `AC-GWPR-04` Given gdrive source 設為 `retrieval_mode=per_user_live` 且 `content_access=full`，When `read_source` 執行但 live reader 或 user-scoped credential 未配置，Then server 回 `LIVE_RETRIEVAL_REQUIRED`
- `AC-GWPR-05` Given gdrive source 設為 `retrieval_mode=per_user_live` 且 `content_access=full`，When live reader 可用，Then `read_source` 回傳 live fetched content，且不得回退到共享全文副本
- `AC-GWPR-06` Given gdrive source 設為 `retrieval_mode=per_user_live` 且 `content_access=summary`，When `read_source` 執行，Then server 只回 `snapshot_summary` 或 `SNAPSHOT_UNAVAILABLE`，不可回全文
- `AC-GWPR-07` Given document 的所有 source 都被 connector scope 擋下，When caller 查 `get(collection="documents")` 或 Dashboard docs metadata，Then 文件視同不存在，不得外洩 blocked source metadata
- `AC-GWPR-08` Given source 帶 `container_id`、`retrieval_mode`、`content_access`，When helper 或 write mutation 更新 source，Then 新欄位被保留在 `sources_json`，供後續 runtime 使用
- `AC-GWPR-09` Given 使用者在 Settings 頁填入 Google Workspace sidecar URL、token 與 gdrive containers，When 儲存設定，Then `/api/partner/preferences` 會保存 `preferences.googleWorkspace.*` 與 `preferences.connectorScopes.gdrive.containers`
- `AC-GWPR-10` Given Settings 頁對當前 sidecar 設定執行 health check，When sidecar 回 `status=ok`，Then UI 顯示 connector 已連線且不要求使用者直接看 raw JSON
- `AC-GWPR-11` Given gdrive source 設為 `retrieval_mode=per_user_live` 且 sidecar 已配置，When `read_source` 走 live path，Then ZenOS 對 sidecar 的 request payload 會帶當前 caller 的 email/principal，並只回 sidecar 的 live content

## 7. 與既有 Spec 關係

- `SPEC-identity-and-access`：本 spec 是其 `P0-3 Connector Scope` 與 `P0-4 Progressive Data Exposure` 的具體落地
- `SPEC-zenos-external-integration`：外部 app / agent 消費 ZenOS 時，Google Workspace 路徑以本 spec 的 `per_user_live` contract 為準
- `SPEC-zenos-auth-federation`：live retrieval 的 caller identity 來自 delegated credential，不另開第二套 auth
- `SPEC-docs-native-edit-and-helper-ingest`：helper summary 路徑保留；本 spec 補的是另一條更嚴格的全文讀取路徑

## 8. 明確不包含

- 真正的 OAuth token storage / refresh flow（由 sidecar 自己管理）
- Shared Drive crawler / sync worker
- webhook / push notification
