---
type: SPEC
id: SPEC-zenos-auth-federation
status: Draft
ontology_entity: zenos-auth-federation
created: 2026-04-09
updated: 2026-04-10
---

# Feature Spec: ZenOS Auth Federation

## 背景與動機

ZenOS 要作為底層 platform，被多個 application layer 消費，而不是要求所有上層產品共用同一個 Firebase project。

目前存在的架構限制：

1. Dashboard 主要依賴 ZenOS 自有 Firebase Auth
2. MCP 主要依賴 API key 與 partner context
3. 若上層 app 使用不同的 Firebase project，則其 end-user token 無法被 ZenOS 直接信任
4. 若 app facade 直接代用 ZenOS API key，則用戶在 app 中看到的權限，與實際 MCP 權限可能脫鉤

因此 ZenOS 需要一個正式的 federation contract：

- 上層 app 自己管理 end-user authentication
- ZenOS 自己管理 ontology / workspace authorization
- 跨服務呼叫必須經過 delegated credential，而不是直接共用 session

## 目標

1. 讓上層 app 的用戶權限與 MCP 權限一致。
2. 讓 ZenOS 能作為多 application 共用的底層，而不綁死在 ZenOS 自有 Firebase Auth。
3. 保留 ZenOS 作為最終 authorization authority。
4. 允許不同上層 app 使用不同 identity provider，只要能與 ZenOS 做 federation。

## 非目標

- 不要求所有 application layer 共用同一個 Firebase project。
- 不要求 ZenOS 接受任意 external token 直接作為內部 access token。
- 不在本 spec 內定義特定第三方 IdP 的 SDK 細節。

## 分層原則

### Authentication 與 Authorization 分離

- `authentication`：由上層 app 驗證 end user 身份
- `authorization`：由 ZenOS 根據自己的 workspace / role / visibility / entity scope 決定

### ZenOS 不直接信任外部 end-user token

外部 app 的 Firebase ID token、Auth0 token、Supabase token 等，都不是 ZenOS MCP 的直接存取憑證。

ZenOS 只接受以下兩種 credential：

1. ZenOS 自己簽發的 access credential
2. ZenOS 明確信任的 federation exchange 流程所產生的 delegated credential

### 上層 app 不得自行決定 ZenOS 權限

上層 app 可以提出「這個 user 想做什麼」，但不能單方面決定：

- 該 user 對哪個 workspace 有權限
- 可見哪些 entity / task / doc
- 可使用哪些 MCP mutation

這些判斷必須由 ZenOS server 完成。

## 核心模型

### External App Identity

上層 app 的身份模型，最少包含：

- `app_id`
- `issuer`
- `external_user_id`
- `email`（如可用）

### ZenOS Principal

ZenOS 內部權限判斷的主體，最少包含：

- `principal_id`
- `principal_type`
- `home_workspace_id`
- `workspace_memberships`

### Identity Link

ZenOS 需維護 external identity 到 ZenOS principal 的映射。

最少欄位：

- `app_id`
- `issuer`
- `external_user_id`
- `zenos_principal_id`
- `status`

沒有 identity link 的 external user，不得直接操作 ZenOS ontology。

### Delegated Credential

當上層 app 代表 user 呼叫 ZenOS 時，必須先向 ZenOS 交換 delegated credential。

delegated credential 最少應帶：

- `zenos_principal_id`
- `app_id`
- `issued_at`
- `expires_at`
- `workspace_ids`
- `granted_scopes`

它是 ZenOS MCP / API 的正式 access credential，而不是上層 app 的原始 token。

## 標準流程

### Flow A: 上層 app 呼叫 ZenOS MCP

1. user 在上層 app 完成登入
2. 上層 app server 驗證自己的 end-user token
3. 上層 app server 呼叫 ZenOS federation exchange endpoint
4. ZenOS 驗證：
   - app 是否受信任
   - external identity 是否存在 identity link
   - user 對哪些 workspace 有權限
5. ZenOS 簽發短效 delegated credential
6. 上層 app / app-facing MCP 使用該 credential 呼叫 ZenOS MCP
7. ZenOS MCP 依 delegated credential + active workspace context 做最終授權

### Flow B: ZenOS 第一方產品

ZenOS 自己的第一方 app 仍可使用自有 Firebase Auth。

但其驗證流程在架構上被視為：

- 一個特殊的 first-party identity provider
- 最終仍需映射成 ZenOS principal 與 authorization context

因此 ZenOS Firebase Auth 可以存在，但不應是 platform 層唯一可接受的 identity source。

## MCP 與上層 App 的責任切分

### ZenOS MCP

負責：

- 驗證 delegated credential 或 ZenOS credential
- 解析 principal
- 建立 active workspace context
- 執行 workspace / visibility / scope 授權
- 執行 ontology / task / document mutation

### App MCP / Facade

負責：

- 驗證自己的 end-user
- 觸發 federation exchange
- 將 app-specific workflow 映射到 ZenOS MCP calls
- 聚合多次 ZenOS MCP 操作

app facade 不得：

- 直接偽造 ZenOS principal
- 跳過 ZenOS authorization
- 保存永久高權限 ZenOS master credential 供每個 user 共用

## 與 API Key 模型的關係

目前的 API key 模型可暫時保留，作為：

- CLI / local agent 的直接存取方式
- 第一方或早期內部使用的 bootstrap 方式

但它不應被視為長期唯一模型。

正式方向是：

- API key = 過渡或 direct-client 模式
- delegated credential = platform federation 模式

## 與既有 Spec 的關係

- `SPEC-identity-and-access`：定義 workspace / role / visibility / active workspace context；本 spec 定義 external app 如何進入同一套 authorization runtime。
- `SPEC-agent-integration-contract`：需補充 delegated credential / app facade 路徑，不再假設所有 agent 都直接持有 ZenOS API key。
- `SPEC-zenos-core`：本 spec 屬於 `ZenOS Core Identity & Access Layer` 的外部接入 contract。

## rollout 規劃

### Phase 1

- 保留 API key 模型
- 文件上明確標示 API key 是現行 direct-client 模式
- 定義 federation contract，但未必立即完成實作

### Phase 2

- 建立 identity link 與 trusted app registry
- 實作 federation exchange endpoint
- 支援 delegated credential 呼叫 ZenOS MCP / API

### Phase 3

- 上層 app 全面改用 delegated auth
- API key 收斂為特定 use case（CLI / internal ops / break-glass）

## 明確要求

1. ZenOS 不得要求所有 application layer 共用 ZenOS Firebase project。
2. ZenOS MCP 必須有自己的驗證邏輯，不可無條件信任外部 app session。
3. 用戶在上層 app 看到的 workspace / role / scope，必須與其可執行的 ZenOS MCP 權限一致。
4. 權限一致性的最終 authority 必須在 ZenOS，不在上層 app。
