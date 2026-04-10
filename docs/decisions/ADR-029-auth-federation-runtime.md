---
doc_id: ADR-029-auth-federation-runtime
title: 決策紀錄：Auth Federation Runtime — Delegated Credential 實作模型
type: DECISION
ontology_entity: zenos-auth-federation
status: Draft
version: "1.2"
date: 2026-04-10
supersedes: null
---

# ADR-029: Auth Federation Runtime — Delegated Credential 實作模型

## Context

SPEC-zenos-auth-federation 定義了 ZenOS 作為多 application 共用底層時的 auth federation contract：上層 app 自己管 authentication，ZenOS 管 authorization，跨服務呼叫必須經過 delegated credential。ADR-025 將 Identity & Access Layer 列為五層之一，ADR-026 規劃了 `domain/identity/`、`application/identity/`、`infrastructure/identity/` 的 code 結構。

但到目前為止，ZenOS 有兩條主要 auth path（加上 admin API 實際上是三條），都是直接信任模型：

1. **MCP：API key**（`SqlPartnerKeyValidator`，`interface/tools.py` 的 `ApiKeyMiddleware`）。每個 partner 有一把 `api_key`，middleware 從 `Authorization: Bearer <key>` / `X-API-Key` / `?api_key=` 取出，查 SQL `partners` 表驗證，然後把 partner context 寫入 `ContextVar`。
2. **Dashboard REST API：Firebase ID token**（`dashboard_api._auth_and_scope`）。Firebase `verify_id_token()` 解 email，查 `partners` 表找到對應 partner，建立 workspace context。用於 entity/task/relationship 等資料端點。
3. **Admin API：Firebase ID token**（`admin_api._verify_firebase_token`）。與 Dashboard 相同的 Firebase 驗證，但額外檢查 `isAdmin` flag。用於 partner 管理、邀請、部門管理等管理端點。

路徑 2 和 3 共用相同的 Firebase 驗證機制，但 scope 判定方式不同——Dashboard 用 workspace_context 的 `is_guest` / `is_unassigned_partner` 做 per-endpoint filtering，Admin 用 `isAdmin` flag 做 admin gate。

這些路徑有以下問題：

- **無法接入外部 app。** 上層 app 如果用自己的 Firebase project 或其他 IdP，其 end-user token 無法被 ZenOS 信任。目前唯一的替代方案是讓 app facade 持有一把 ZenOS API key，但這意味著所有 end-user 共用同一把 key，權限無法區分。
- **API key 是永久憑證。** 沒有 expiry、沒有 scope 限制、沒有 rotation 機制。任何拿到 key 的 agent 都有該 partner 的完整權限。
- **沒有 scope enforcement。** 所有 MCP tool 的權限判斷散落在各 tool handler 裡（visibility check、write guard、guest subtree filtering），沒有統一的 scope 層。

本 ADR 要決定：如何在現有架構上加入 federation exchange + delegated credential，讓外部 app 能安全接入 ZenOS，同時與現有 API key 模型共存。

## Decision Drivers

- 必須「實作到真實可用」，不只是架構文件
- 現有 API key + Firebase Auth 兩條路徑不能斷，federation 是新增路徑
- Phase 0 團隊規模小（2-5 人），不做過度設計
- 用戶已確認：粗粒度 scope（read/write/task），不做細粒度
- 用戶已確認：直接改 import path，不保留相容 shim（配合 ADR-026 遷移）

## Decision

### D1. Identity Link DB schema

新增 `zenos.identity_links` 表，映射外部 app 的 user 到 ZenOS principal：

```sql
CREATE TABLE zenos.identity_links (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id        UUID NOT NULL REFERENCES zenos.trusted_apps(app_id),
    issuer        TEXT NOT NULL,           -- e.g. "firebase:my-app-project", "auth0:tenant-xyz"
    external_user_id TEXT NOT NULL,        -- IdP 發出的 user identifier
    email         TEXT,                    -- 輔助比對，不作為唯一鍵
    zenos_principal_id UUID NOT NULL,      -- 指向 zenos.partners.id
    status        TEXT NOT NULL DEFAULT 'active',  -- active | suspended | revoked
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (app_id, issuer, external_user_id)
);
```

**為什麼 `zenos_principal_id` 指向 `partners.id`：**

現有系統的 principal 就是 partner。UserPrincipal dataclass 的 `partner_id` 對應 `partners.id`，所有 ContextVar（`current_partner_id`、`current_partner_authorized_entity_ids`）都以 partner 為單位。新建一套獨立的 principal 表在 Phase 0 沒有必要——identity link 只是多了一條「外部 identity -> 哪個 partner」的映射，不改變 partner 作為 principal 的語意。

**考慮過的替代方案：**

新建獨立 `principals` 表，partner 和 identity link 都指向它。問題：現有 codebase 有 ~20 處硬編碼 `partners.id` 作為 principal key，改動範圍太大，收益不明顯（Phase 0 只有一種 principal 類型）。等未來出現 service account、org admin 等新 principal 類型時再抽象。

### D2. Trusted App Registry DB schema

新增 `zenos.trusted_apps` 表，記錄被信任的上層 app：

```sql
CREATE TABLE zenos.trusted_apps (
    app_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_name        TEXT NOT NULL UNIQUE,
    app_secret_hash TEXT NOT NULL,         -- bcrypt hash of app secret
    allowed_issuers TEXT[] NOT NULL DEFAULT '{}',  -- 該 app 可代理哪些 issuer
    allowed_scopes  TEXT[] NOT NULL DEFAULT '{read}',  -- 該 app 可申請的最大 scope 集合
    status          TEXT NOT NULL DEFAULT 'active',  -- active | suspended | revoked
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**為什麼 `app_secret_hash` 用 bcrypt：**

app secret 是長期憑證，不能明文存。bcrypt 的 work factor 提供了足夠的暴力破解防護。Phase 0 不需要 argon2——bcrypt 在 Python 生態（`passlib`/`bcrypt`）更成熟，且 app secret 驗證不在 hot path（只在 federation exchange 時用，不是每個 MCP request）。

**`allowed_issuers` 的用途：**

防止 app A 拿著 app B 的 issuer 發出的 token 來做 exchange。每個 trusted app 註冊時必須宣告它會用哪些 issuer（e.g. `["firebase:my-app-project"]`），exchange 時 server 驗證 issuer 在允許清單內。

### D3. Federation Exchange Endpoint

新增 `POST /api/federation/exchange`：

**Request：**

```json
{
    "app_id": "uuid",
    "app_secret": "plain-text-secret", // pragma: allowlist secret
    "external_token": "eyJ...",
    "issuer": "firebase:my-app-project",
    "requested_scopes": ["read", "write"]
}
```

**Server 驗證流程：**

1. 查 `trusted_apps` 確認 `app_id` 存在且 `status = active`
2. 驗證 `app_secret` 與 `app_secret_hash` 匹配
3. 驗證 `issuer` 在該 app 的 `allowed_issuers` 內
4. 驗證 `external_token`（Phase 0 只支援 Firebase ID token：呼叫 `firebase_admin.auth.verify_id_token()` 並比對 issuer project）
5. 從 token 取得 `external_user_id`（Firebase 的 `uid`）和 `email`
6. 查 `identity_links` 找到對應的 `zenos_principal_id`；找不到則返回 403
7. 計算 `granted_scopes = requested_scopes ∩ app.allowed_scopes`
8. 查 partner 取得 `workspace_ids`（partner 自己的 id + shared_partner_id）
9. 簽發 delegated credential（JWT），返回

**Response（成功）：**

```json
{
    "delegated_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "principal_id": "uuid",
    "granted_scopes": ["read", "write"],
    "workspace_ids": ["uuid-1", "uuid-2"]
}
```

**Response（失敗）：**

```json
{
    "error": "IDENTITY_NOT_LINKED",
    "message": "No identity link found for this external user"
}
```

錯誤碼：`INVALID_APP`、`INVALID_SECRET`、`ISSUER_NOT_ALLOWED`、`INVALID_EXTERNAL_TOKEN`、`IDENTITY_NOT_LINKED`、`APP_SUSPENDED`。

**為什麼 exchange 放在 REST endpoint 而不是 MCP tool：**

federation exchange 是 server-to-server 呼叫，上層 app 的 backend 呼叫 ZenOS backend。MCP tool 是給 agent 用的，有 partner context 前提。exchange 發生在 partner context 建立之前，邏輯上不屬於 MCP 層。放在 `dashboard_api.py` 同層（或獨立 `federation_api.py`）的 HTTP endpoint 更合理。

### D4. Delegated Credential 格式

選擇 JWT（HS256），payload：

```json
{
    "sub": "zenos-principal-uuid",
    "app_id": "trusted-app-uuid",
    "workspace_ids": ["uuid-1", "uuid-2"],
    "scopes": ["read", "write"],
    "iat": 1712678400,
    "exp": 1712682000,
    "iss": "zenos",
    "jti": "unique-token-id"
}
```

**為什麼 JWT 而非 opaque token：**

| 維度 | JWT | Opaque token |
|------|-----|-------------|
| 驗證方式 | 本地簽名驗證，不查 DB | 每次都要查 DB |
| MCP hot path 影響 | 零 DB round-trip | 每個 request 多一次 query |
| Revocation | 只能等過期（或維護 blocklist） | 可即時撤銷 |
| Payload 自帶 context | scopes、workspace_ids 都在 token 裡 | 需要額外 DB query 取 context |

選 JWT 的理由：MCP 是 ZenOS 的 hot path，每個 tool call 都要過 auth。API key 現在是純 memory cache lookup（~0ms），JWT 是純 CPU 簽名驗證（~0.1ms），兩者都不需要 DB。如果用 opaque token，每個 MCP request 多一次 DB query，降級太大。

Revocation 的風險用短效 token（1 小時 TTL）緩解。最壞情況：app 被 revoke 後，已簽發的 token 最多再活 1 小時。Phase 0 可接受。未來若需即時撤銷，加 `jti` blocklist（Redis 或 in-memory set），不改架構。

**為什麼 HS256 而非 RS256：**

Phase 0 只有 ZenOS 自己簽發和驗證 delegated credential，不需要 public key 分發。HS256 用單一 shared secret，簽發和驗證都更快，配置更簡單（一個環境變數 vs RSA key pair 管理）。未來如果有第三方需要離線驗證 ZenOS token（不太可能——delegated credential 只在 ZenOS 自己的 MCP/API 內驗證），再切 RS256。

### D5. 與現有 API key 共存——MCP middleware 雙路徑

修改 `ApiKeyMiddleware`，加入 JWT 驗證路徑：

```
收到 request
    ↓
1. 從 Authorization header / X-API-Key / query param 取出 credential
    ↓
2. credential 是 JWT 格式？（以 "eyJ" 開頭 + 包含兩個 "."）
   ├── 是 → JWT path：verify_jwt() → 從 payload 建立 partner context
   └── 否 → API key path：SqlPartnerKeyValidator.validate() → 現有邏輯
    ↓
3. 驗證成功 → 設定 ContextVar（current_partner_id, scopes, workspace_ids）
4. 驗證失敗 → 401
```

**JWT path 的 partner context 建立：**

JWT payload 帶 `sub`（principal_id）和 `workspace_ids`，但不帶完整 partner data（roles、authorized_entity_ids 等）。驗證 JWT 後，仍需用 `sub` 查一次 `partners` 表取完整 partner data，然後走現有的 `active_partner_view()` 邏輯。

這不違反 D4 選 JWT 的理由嗎？不違反——差別在於：

- API key path 也要查 partners 表（透過 cache），JWT path 同樣走 cache
- JWT 的價值不在於「完全不查 DB」，而在於「不需要額外的 token 表」和「payload 自帶 scopes 做前置過濾」

**為什麼不把完整 partner data 塞進 JWT：**

partner data 會變（authorized_entity_ids 被 owner 修改、role 被調整），JWT 一旦簽發就是 frozen snapshot。如果 JWT 帶完整 data，token 有效期間內的權限變更不生效。用 `sub` 查最新 partner data 確保權限即時。

### D6. Scope enforcement——粗粒度，MCP tool 層面檢查

定義三個 scope：

| Scope | 允許的操作 |
|-------|-----------|
| `read` | `search`、`get`、`read_source`、`common_neighbors`、`find_gaps`、`governance_guide`、`journal_read` |
| `write` | `read` 的全部 + `write`、`confirm`、`analyze`、`batch_update_sources`、`upload_attachment`、`journal_write`、`setup`、`suggest_policy` |
| `task` | `read` 的全部 + `task`（CRUD + lifecycle） |

規則：

- `write` 包含 `read`（向上兼容）
- `task` 包含 `read` 但不包含 `write`（task 是獨立 scope，不隱含 entity mutation）
- 典型 app facade 申請 `["read", "task"]`（查知識 + 管任務），不需要 `write`
- API key path 隱含 `["read", "write", "task"]`——即現行行為不變

**Enforcement 位置：**

在每個 MCP tool handler 的開頭加 scope check。不在 middleware 做——因為 MCP tool name 在 middleware 層不可知（MCP protocol 的 tool dispatch 發生在 FastMCP 內部，middleware 只看到 HTTP path `/messages/`）。

實作方式：decorator。

```python
TOOL_SCOPE_MAP: dict[str, str] = {
    "search": "read",
    "get": "read",
    "write": "write",
    "confirm": "write",
    "task": "task",
    # ...
}

def require_scope(scope: str):
    """Decorator: check current request has the required scope."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            granted = _current_scopes.get()
            if scope not in granted:
                return _unified_response(
                    status="rejected",
                    data={},
                    rejection_reason=f"Insufficient scope: requires '{scope}', granted {granted}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

新增 ContextVar `_current_scopes: ContextVar[set[str]]`，在 middleware 設定。API key path 設為 `{"read", "write", "task"}`，JWT path 從 token payload 的 `scopes` 讀取。

**考慮過的替代方案：**

**細粒度 scope（per-tool 或 per-entity-type）。** 例如 `entity:read`、`task:create`、`task:confirm`。問題：Phase 0 只有 ~15 個 MCP tool，tool 數量會持續增加。每新增一個 tool 就要定義新 scope、更新 trusted app 的 `allowed_scopes`、更新所有 app 的 `requested_scopes`。對 2-5 人團隊來說管理成本過高。粗粒度的三個 scope 足以區分「只讀」、「可改 ontology」、「可管 task」三種典型 app 角色。用戶已確認此決策。

### D7. JWT signing key 管理

Phase 0：單一 HMAC key，存在環境變數 `ZENOS_JWT_SECRET`。

```python
JWT_SECRET = os.environ.get("ZENOS_JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = 3600  # 1 hour
```

**Rotation 預留：**

- JWT payload 加 `kid`（key ID），Phase 0 固定為 `"v1"`
- 未來 rotation 時，新 key 簽發 `kid: "v2"`，驗證時按 `kid` 選 key，舊 key 保留到所有 v1 token 過期
- 不在 Phase 0 實作 rotation 機制——YAGNI

**為什麼不用 Google Cloud KMS 或 Secret Manager 做 signing：**

KMS signing 每次呼叫有 ~50ms 延遲和 per-call cost。exchange endpoint 一次性用可以，但如果把 KMS 用在 verification（不需要——HS256 verification 是本地操作）就過度設計了。Secret Manager 存 key 是合理的（比環境變數更安全），但那是部署層面的改進，不影響 runtime 架構。Phase 0 先用環境變數，部署腳本確保 key 設定。

### D8. Dashboard auth 收斂策略——Phase 0 三路徑共存是刻意決策

**決策：** Phase 0 維持三條 auth path 共存（API key、Firebase ID token、delegated JWT），不在本階段強制收斂 Dashboard auth 到 federation exchange。

**現狀描述：**

ZenOS 實際有三條獨立的 auth path，各服務不同場景：

| Path | 進入點 | 驗證方式 | 使用者 |
|------|--------|---------|--------|
| API key | MCP middleware (`ApiKeyMiddleware`) | `SqlPartnerKeyValidator` 查 partners 表 | Agent / CLI |
| Firebase ID token | Dashboard REST API (`dashboard_api._auth_and_scope`, `admin_api._verify_firebase_token`) | `firebase_admin.auth.verify_id_token()` → email → partners 表 | Dashboard 使用者 |
| Delegated JWT | MCP middleware (JWT path, 本 ADR 新增) | HS256 signature verify → `sub` → partners 表 | 外部 app 代理的 end-user |

三條路徑最終都收斂到同一個 partner-based authorization runtime（`workspace_context.py` 的 `resolve_active_workspace_id` + `active_partner_view`）。差異在前置驗證，不在授權邏輯。

**為什麼不在 Phase 0 收斂：**

1. Dashboard 的 Firebase Auth 是前端直接調用的——瀏覽器裡的 Firebase SDK `signInWithEmailLink()` → 拿到 ID token → 直接打 REST API。要改成 federation exchange，需要先讓 Dashboard 變成一個 trusted app、走 server-to-server exchange、再拿 delegated JWT 打 REST API。這增加了一次 network round-trip 和整個 Dashboard 的 auth 重構，Phase 0 收益不明顯。
2. Dashboard REST endpoints 的 scope enforcement 目前由 `is_guest` / `is_unassigned_partner` / `isAdmin` 等 per-endpoint check 實現，不依賴 D6 的三 scope 模型。強行統一會讓 Dashboard 的細粒度 admin check 退化成粗粒度 scope。

**收斂時機：** 當 Dashboard 需要支援非 ZenOS Firebase 的 identity provider 時（例如 SSO），Dashboard auth 必須改走 federation exchange。屆時建新 ADR。

### D9. 外部 user workspace_context 處理——identity_link 的 partner 必須有完整 workspace config

**決策：** Federation exchange 在步驟 8（查 partner 取得 `workspace_ids`）時，如果 `identity_link` 映射到的 partner 沒有 `sharedPartnerId`，exchange 仍然成功，但 `workspace_ids` 只包含該 partner 自己的 home workspace。

**Edge case 分析：**

identity_link 映射到的 partner 有三種可能狀態：

| Partner 狀態 | sharedPartnerId | workspace_ids 結果 | 說明 |
|-------------|----------------|-------------------|------|
| 正常（owner / member） | 有 | [home_id, shared_id] | 可切換兩個 workspace |
| 正常（無共享關係） | 無 | [home_id] | 只能存取自己的 workspace |
| Unassigned（invited but not activated） | 可能有 | exchange reject → 403 | 未啟用的 partner 不應被外部 app 存取 |

**命名收斂說明：**

- `workspace_ids` 是 runtime payload 與 API response 的正式欄位名
- 它表示 delegated credential 目前允許使用的 workspace 集合
- `SPEC-zenos-auth-federation` 已同步使用相同命名；不再保留 `allowed_workspace_ids` 這個舊稱呼，避免實作層與 spec 層 drift

**為什麼 unassigned partner reject：**

`workspace_context.py` 的 `active_partner_view` 對 unassigned partner 會設定 `accessMode = "unassigned"`，下游所有 MCP tool 和 Dashboard endpoint 都會回傳空結果。讓 exchange 成功但實際什麼都做不了只會讓外部 app 困惑。直接在 exchange 階段 reject 並回傳 `PARTNER_NOT_ACTIVATED` 錯誤碼更清楚。

**新增驗證步驟（插入 D3 步驟 6 之後）：**

6.5. 查 partner 的 `status`，如果是 `invited`（未啟用）或 `suspended`，回傳 403 `PARTNER_NOT_ACTIVATED` / `PARTNER_SUSPENDED`

### D10. Auto-provisioning 明確立場——Phase 0 手動建立，記錄未來方向

**決策：** Phase 0 不實作 auto-provisioning。外部 user 首次透過 federation exchange 存取 ZenOS 時，如果沒有 identity_link，exchange 回傳 `IDENTITY_NOT_LINKED`。Admin 必須預先透過 admin script 建立 identity_link。

**為什麼不在 Phase 0 做 auto-provisioning：**

1. **Auto-provisioning 是產品決策，不是技術決策。** 「外部 user 第一次來就自動建 partner」意味著 workspace owner 無法控制誰能進入自己的 workspace。中小企業場景下，這等於開放大門——任何拿到 app 存取權的人都自動獲得 ZenOS ontology 存取權。
2. **Email match 不夠可靠。** auto-provisioning 的典型實作是「email 相同就 link」，但不同 IdP 的 email 驗證強度不同。某些 IdP 允許未驗證 email 註冊，靠 email match 做 auto-link 有冒充風險。
3. **Phase 0 的 partner 數量極少。** 手動建立 identity_link 的操作量可控（admin script 一行指令）。

**未來方向（記錄，不承諾時程）：**

- **Phase 2 方向 A（Owner approve flow）：** exchange 時如果沒有 link 但 email 在 partner 中存在，回傳 `IDENTITY_LINK_PENDING`，同時通知 workspace owner 審批。owner approve 後自動建立 link。
- **Phase 2 方向 B（Domain-based auto-link）：** workspace owner 可設定「允許 @company.com 的 email 自動 link」，exchange 時自動建立 link。需要 email 驗證標記（只信任 `email_verified = true` 的 token）。
- **不做的方向：** 完全開放的 auto-provisioning（無 owner 控制）——違反中小企業場景的安全預期。

## Tradeoffs 總覽

| 決策點 | 選擇 | 替代方案 | 取捨 |
|--------|------|---------|------|
| Token 格式 | JWT（HS256） | Opaque token + DB lookup | JWT 省 DB query，但無法即時撤銷。用 1hr TTL 緩解。 |
| Signing 演算法 | HS256 | RS256 | HS256 更簡單，但 ZenOS 必須同時是 signer 和 verifier。Phase 0 沒有第三方驗證需求。 |
| Scope 粒度 | 粗粒度（read/write/task） | Per-tool / per-entity-type | 粗粒度管理成本低，但無法限制「只能讀 entity 不能讀 task」。Phase 0 可接受。 |
| Principal 表 | 複用 partners.id | 新建 principals 表 | 避免大範圍重構，但 partner 和 principal 語意耦合。等新 principal 類型出現再解。 |
| 為什麼不直接信任外部 token | — | 直接 verify 外部 Firebase/Auth0 token | ZenOS 不能依賴對所有 IdP 的 SDK 支援。federation exchange 讓 ZenOS 只需要信任自己簽發的 credential，external token 驗證邏輯集中在 exchange endpoint，未來新增 issuer 只改 exchange，不改 MCP middleware。 |
| Dashboard auth 收斂 | Phase 0 三路徑共存 | 立即收斂 Dashboard 到 federation | 收斂需重構 Dashboard auth 架構，Phase 0 收益不明顯。等 SSO 需求出現時再做。 |
| Auto-provisioning | Phase 0 手動建立 | exchange 時自動建 link | 自動建立繞過 owner 控制，中小企業場景不適合。Phase 2 加 owner approve flow。 |
| Unassigned partner exchange | Reject (403) | 成功但下游回空 | 成功但什麼都做不了只會讓外部 app 困惑。直接 reject 更清楚。 |

## Implementation Impact

### 新增檔案（按 ADR-026 module boundary）

| 路徑 | 內容 |
|------|------|
| `src/zenos/domain/identity/federation.py` | `IdentityLink`、`TrustedApp` dataclass；`FederationScope` enum |
| `src/zenos/application/identity/federation_service.py` | `exchange_token()`、`create_identity_link()`、`register_trusted_app()` |
| `src/zenos/infrastructure/identity/sql_identity_link_repo.py` | `SqlIdentityLinkRepository` |
| `src/zenos/infrastructure/identity/sql_trusted_app_repo.py` | `SqlTrustedAppRepository` |
| `src/zenos/infrastructure/identity/jwt_service.py` | `sign_delegated_credential()`、`verify_delegated_credential()` |
| `src/zenos/interface/federation_api.py` | `POST /api/federation/exchange` HTTP endpoint |
| `migrations/20260409_xxxx_identity_links.sql` | `identity_links` + `trusted_apps` DDL |

### 修改檔案

| 路徑 | 變更 |
|------|------|
| `src/zenos/interface/tools.py`（或遷移後的 `interface/mcp/__init__.py`） | `ApiKeyMiddleware` 加 JWT path；新增 `_current_scopes` ContextVar |
| 各 MCP tool handler | 加 `@require_scope` decorator |
| `src/zenos/domain/identity/models.py`（遷移後） | 新增 `FederationScope` enum（或放在 `federation.py`） |
| `src/zenos/application/identity/federation_service.py` | `exchange_token()` 步驟 6.5 加 partner status check（D9） |

### DB migration

```sql
-- 順序：先建 trusted_apps（因為 identity_links 有 FK）
CREATE TABLE zenos.trusted_apps ( ... );
CREATE TABLE zenos.identity_links ( ... );
CREATE INDEX idx_identity_links_lookup 
    ON zenos.identity_links (app_id, issuer, external_user_id);
```

### 對 deploy 的影響

- Cloud Run 需新增環境變數 `ZENOS_JWT_SECRET`
- `deploy_mcp.sh` 不需改動——新檔案自動被 Python package 打包
- Dashboard deploy 不受影響——federation exchange 是 backend-to-backend

## Risks

### 最大風險：JWT secret 洩漏等於全面失守

如果 `ZENOS_JWT_SECRET` 洩漏，攻擊者可以偽造任意 principal 的 delegated credential。

**機率：** 低。環境變數在 Cloud Run 的 Secret 設定中，不進 git。

**緩解：**
1. 部署時用 Google Secret Manager 注入，不 hardcode
2. `kid` 欄位預留了 rotation 能力，發現洩漏時可立即 rotate
3. JWT TTL 1 小時，洩漏後的 exposure window 有限

### 中等風險：exchange endpoint 成為 DDoS 目標

bcrypt 驗證 app_secret 有計算成本（~100ms），如果被大量無效 request 打，會消耗 CPU。

**緩解：**
1. 先檢查 `app_id` 是否存在（DB lookup，快），不存在直接 reject，不做 bcrypt
2. 未來加 rate limiting（per app_id）
3. exchange 不在 MCP hot path，被打不影響正常 MCP 操作

### 低風險：identity_link 管理缺乏 self-service UI

Phase 0 的 identity link 建立靠 admin script 或直接 SQL。沒有 dashboard UI 讓 owner 管理「哪些外部 user 映射到我的 workspace」。

**緩解：** Phase 0 只有內部使用，admin script 足夠。Phase 2 再建 UI。

## Consequences

### Positive

- **外部 app 可安全接入 ZenOS。** 不再需要共用 API key——每個 end-user 透過 identity link 映射到自己的 partner，權限精確。
- **Scope enforcement 首次落地。** 即使只有三個 scope，也比現在「API key = 全部權限」好得多。
- **與現有系統零破壞共存。** API key path 完全不變，federation 是純新增路徑。
- **架構上已為 multi-IdP 預留。** `issuer` + `allowed_issuers` 機制讓未來接 Auth0、Supabase、Google Workspace 只需在 exchange 加 token verification adapter，不改 MCP middleware。

### Negative

- **多了一套 credential 管理。** 現在有 API key + Firebase token + delegated JWT 三種 credential，middleware 邏輯更複雜。Phase 0 三路徑共存是刻意決策（D8），收斂時機待 SSO 需求出現。
- **JWT 無法即時撤銷。** 1 小時 TTL 內的 revocation gap 是已知限制。
- **identity_link 需要人工建立。** Phase 0 沒有 auto-provisioning（D10），外部 user 首次存取時必須先由 admin 建 link。這限制了 onboarding 體驗，但保護了 workspace owner 的控制權。
- **bcrypt dependency。** 需要新增 `bcrypt` 或 `passlib` 到 Python dependencies。
- **Scope enforcement 不涵蓋 Dashboard REST endpoints。** D6 的三 scope 模型（read/write/task）只 enforce MCP tool handler。Dashboard REST endpoints 繼續使用 per-endpoint 的 `isAdmin` / `is_guest` / `is_unassigned_partner` check。兩套機制並行增加認知成本，但 Dashboard 的細粒度 admin check 無法用粗粒度 scope 取代（D8）。

### 後續工作（不在本 ADR scope 內）

1. Admin script：`register_trusted_app.py`、`create_identity_link.py`
2. Dashboard UI：workspace owner 管理 identity links
3. Auto-provisioning（D10 記錄方向）：owner approve flow 或 domain-based auto-link，待 Phase 2
4. Token blocklist：如果 1hr TTL 不夠，加 `jti` blocklist 支援即時撤銷
5. RS256 migration：如果出現第三方離線驗證需求
6. Dashboard auth 收斂（D8）：當 Dashboard 需要 SSO 時，改走 federation exchange
7. Scope enforcement 擴展到 Dashboard REST endpoints：當 Dashboard 和 MCP 的 visibility 邏輯需要共用時統一
