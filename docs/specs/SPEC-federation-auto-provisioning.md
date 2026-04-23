---
type: SPEC
id: SPEC-federation-auto-provisioning
status: Draft
ontology_entity: zenos-auth-federation
created: 2026-04-19
updated: 2026-04-23
extends: SPEC-zenos-auth-federation
depends_on: SPEC-zenos-auth-federation, SPEC-identity-and-access
---

# Feature Spec: Federation Auto-Provisioning

## 背景與動機

`SPEC-zenos-auth-federation` 與 `ADR-029` 定義了 ZenOS federation exchange 的完整合約，並在 ADR-029 D10 明確標注：Phase 0 不實作 auto-provisioning，外部 user 首次存取必須由 ZenOS admin 手動執行 `create_identity_link.py`。

這個決策在 Phase 0（少量內部使用者）可接受，但 **Zentropy 作為第一個接入 ZenOS core 的 app 時，此限制是 launch blocker**：每個 Zentropy 用戶都要 admin 手動建 identity link，自助 onboarding 完全卡住。

本 Spec 補齊 ADR-029 D10 預留的 Phase 2 方向，讓外部 app 的新用戶可以透過 workspace owner 審批（Direction A）或 domain 配置（Direction B）自動完成 provisioning，不需要 admin 手動介入。

## 目標

1. 消除 Zentropy onboarding 的手動操作瓶頸。
2. 保留 workspace owner 的存取控制權——自動建立 identity link 之前，必須有 owner 的明確授權（審批或 domain 配置）。
3. 與現有 exchange endpoint + trusted_apps + identity_links 零破壞共存。

## 非目標

- 不做完全開放的 auto-provisioning（無 owner 控制）。
- 不在本 Spec 內實作 Admin Dashboard UI（Phase 2 優先實作 API，UI 是後續）。
- 不改變現有 API key path 或 Firebase ID token path 的行為。
- 不實作 email 驗證程度升級（沿用現有 Firebase `email_verified` flag）。

## 核心模型擴充

### Pending Identity Link

當 exchange 請求無法找到 identity link，但滿足 auto-provisioning 前提時，系統建立一筆 `pending_identity_link` 記錄，而非直接 reject。

最少欄位：

- `id`（UUID）
- `app_id`（FK → trusted_apps）
- `issuer`
- `external_user_id`
- `email`（從 external token 取出）
- `workspace_id`（承接審批通知的目標 workspace）
- `status`：`pending` | `approved` | `rejected` | `expired`
- `created_at`
- `expires_at`（7 天）
- `reviewed_by`（審批者 partner_id，nullable）
- `reviewed_at`（nullable）

### Trusted App 擴充欄位

`trusted_apps` 新增兩個欄位：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `default_workspace_id` | UUID NOT NULL | 必填。審批通知與自動 provisioning 的目標 workspace。`register_trusted_app.py` 與 Register API 皆要求此欄位。 |
| `auto_link_email_domains` | TEXT[] | 允許自動 link 的 email domain 白名單（例如 `["zentropy.app"]`）。空陣列 = 不啟用 domain auto-link，所有新用戶走 Owner-Approve 流程。 |

## 標準流程

### Flow P: Owner-Approve Flow（Pending Link）

前提：`trusted_apps.default_workspace_id` 已設定。

1. Zentropy user 在 Zentropy 登入，得到 Firebase ID token。
2. Zentropy backend 呼叫 `POST /api/federation/exchange`，帶 `app_id`, `app_secret`, `external_token`, `issuer`。
3. ZenOS 驗證 app + secret + issuer + token（同現有 D3 步驟 1-5）。
4. 查 `identity_links`，找不到對應 link。
5. 查是否已有相同 `(app_id, issuer, external_user_id)` 的 `pending` 狀態 pending_link：
   - 有 → 直接回傳 `IDENTITY_LINK_PENDING`，不重複建立。
   - 無 → 建立新 pending_identity_link（status=pending, expires=7天後）→ 回傳 `IDENTITY_LINK_PENDING`。
6. Workspace owner 透過 API 查看 pending 清單 → 審批或拒絕。
7. Owner 批准：
   - 系統在 `default_workspace_id` 自動建立 partner（role=guest）。
   - 建立 `identity_link`，`zenos_principal_id` 指向新建的 partner。
   - 更新 pending_link status=approved。
8. Zentropy backend 重新呼叫 exchange → 成功，取得 delegated JWT。
9. Owner 拒絕：更新 pending_link status=rejected → 下次 exchange 回傳 `IDENTITY_NOT_LINKED`（不是 IDENTITY_LINK_PENDING）。

### Flow D: Domain Auto-Link

前提：`trusted_apps.auto_link_email_domains` 包含用戶 email domain，且 token 的 `email_verified=true`。

1. Exchange 步驟 1-5 同 Flow P。
2. 查 identity_links，找不到 link。
3. 檢查 auto_link_email_domains：token email 的 domain 在清單內，且 `email_verified=true`。
4. 在 `default_workspace_id` 自動建立 partner（role=guest）。
5. 建立 `identity_link`。
6. 繼續 exchange 成功回傳 delegated JWT。

說明：`email_verified=false` 的 token 不觸發 domain auto-link，fallback 到 Flow P（如果 default_workspace_id 有設定）或 403（如果沒設定）。

## Acceptance Criteria

### P0：Pending Link 核心流程

**AC-FAP-01**：
Given：trusted_app 設定了 `default_workspace_id`，外部 user 第一次呼叫 exchange，系統沒有對應 identity_link，且沒有既有 pending link。
When：呼叫 `POST /api/federation/exchange`。
Then：
- 回傳 HTTP 202，body 含 `{"status": "IDENTITY_LINK_PENDING", "message": "...", "pending_link_id": "<uuid>"}`。
- DB 中新增一筆 `pending_identity_link`，欄位 app_id / issuer / external_user_id / email / workspace_id / status=pending / expires_at=now+7days 均正確填寫。

**AC-FAP-02**：
Given：同一個外部 user 已有 status=pending 的 pending_link。
When：再次呼叫 exchange。
Then：回傳 HTTP 202 `IDENTITY_LINK_PENDING`，不重複建立 pending_link（DB 仍只有 1 筆）。

**AC-FAP-03**：
Given：workspace 中有 status=pending 的 pending_link。
When：workspace owner 呼叫 `GET /api/federation/pending-links?workspace_id=<uuid>`。
Then：回傳清單，每筆包含 id / app_name / issuer / external_user_id / email / created_at / expires_at / status。

**AC-FAP-04**：
Given：pending_link status=pending。
When：workspace owner 呼叫 `POST /api/federation/pending-links/<id>/approve`。
Then：
- 在 `default_workspace_id` workspace 自動建立 partner，role=guest。
- 建立 identity_link，`zenos_principal_id` 指向新 partner。
- pending_link status 更新為 approved。
- 後續 exchange 呼叫成功取得 delegated JWT（status 200）。

**AC-FAP-05**：
Given：pending_link status=pending。
When：workspace owner 呼叫 `POST /api/federation/pending-links/<id>/reject`。
Then：
- pending_link status 更新為 rejected。
- 後續 exchange 呼叫回傳 `IDENTITY_NOT_LINKED`（403），而非 `IDENTITY_LINK_PENDING`。

**AC-FAP-06**：
Given：pending_link 建立後超過 7 天未被審批（status 仍為 pending）。
When：外部 user 再次呼叫 exchange。
Then：
- 舊 pending_link 被標記為 expired（或於查詢時過濾掉）。
- 系統建立新的 pending_link（status=pending，重新計算 expires_at）。
- 回傳 HTTP 202 `IDENTITY_LINK_PENDING`。

**AC-FAP-07**：
Given：exchange 成功建立 identity link 後，新 partner 的 workspace role。
When：owner approve 或 domain auto-link 完成。
Then：新建 partner 的 workspace role 為 `guest`，可讀 ontology、可建 L3/task；不可建 L1/L2。（未來可由 owner 升級 role，不在本 Spec 範圍。）

### P0：Owner 身份驗證

**AC-FAP-08**：
Given：caller 不是 `default_workspace_id` workspace 的 owner。
When：呼叫 pending-links 的 GET / approve / reject API。
Then：回傳 403 Forbidden。

### P1：Domain Auto-Link

**AC-FAP-09**：
Given：trusted_app 的 `auto_link_email_domains` 包含 `zentropy.app`，外部 token 的 email 是 `user@zentropy.app` 且 `email_verified=true`，沒有既有 identity_link。
When：呼叫 exchange。
Then：
- 系統自動在 `default_workspace_id` 建立 partner（role=guest）並建立 identity_link。
- Exchange 成功回傳 delegated JWT（status 200）。
- 不建立 pending_link，不需要 owner 審批。

**AC-FAP-10**：
Given：token 的 `email_verified=false`，但 domain 在 `auto_link_email_domains` 內。
When：呼叫 exchange，無 identity_link。
Then：Domain auto-link 不觸發，fallback 到 Flow P（若 default_workspace_id 已設定，則建立 pending_link + 202）或 403（未設定）。

**AC-FAP-11**：
Given：Domain auto-link 成功，自動建立的 partner。
When：後續 exchange 查 identity_link。
Then：正常回傳 delegated JWT，行為與手動建立的 identity_link 一致。

## DB Schema 變更

### 新增表：`zenos.pending_identity_links`

```sql
CREATE TABLE zenos.pending_identity_links (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id            UUID NOT NULL REFERENCES zenos.trusted_apps(app_id),
    issuer            TEXT NOT NULL,
    external_user_id  TEXT NOT NULL,
    email             TEXT,
    workspace_id      UUID NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | expired
    reviewed_by       UUID REFERENCES zenos.partners(id),
    reviewed_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '7 days',
    -- 同一個 (app, issuer, external_user_id) 最多一筆 active pending
    UNIQUE (app_id, issuer, external_user_id, status)
        WHERE status = 'pending'
);
```

### 修改表：`zenos.trusted_apps`（新增兩欄）

```sql
-- default_workspace_id: nullable at DB level for migration safety (existing rows),
-- but required at application layer (register_trusted_app enforces NOT NULL)
ALTER TABLE zenos.trusted_apps
    ADD COLUMN default_workspace_id     UUID REFERENCES zenos.workspaces(id),
    ADD COLUMN auto_link_email_domains  TEXT[] NOT NULL DEFAULT '{}';

-- Existing trusted_apps: admin must backfill default_workspace_id before they can use auto-provisioning
```

## API 新增

### `GET /api/federation/pending-links`

Query params：`workspace_id` (required)。
Auth：Firebase ID token（Dashboard owner 用）；只有 target workspace 的 owner 可呼叫。

### `POST /api/federation/pending-links/{id}/approve`

Body：無（owner 身份已由 auth header 帶入）。
Response：`{"status": "approved", "identity_link_id": "<uuid>", "partner_id": "<uuid>"}`。

### `POST /api/federation/pending-links/{id}/reject`

Response：`{"status": "rejected"}`。

## 與現有架構的關係

- `SPEC-zenos-auth-federation`：本 Spec 是該 Spec ADR-029 D10 Phase 2 方向的具體化，不矛盾。
- `ADR-029 D3`：本 Spec 擴充步驟 6 的行為分支（找不到 identity_link 時，不一定直接 reject）。
- `ADR-029 D10`：本 Spec 實作了 D10 記錄的「Phase 2 方向 A（Owner approve flow）」與「Phase 2 方向 B（Domain-based auto-link）」。

## Rollout

### Phase 2a（本 Spec P0）

- 實作 pending_identity_links 表 + exchange 行為分支 + owner 審批 API。
- ZenOS admin 為 Zentropy 呼叫 `register_trusted_app.py` 時加入 `--default-workspace-id`。
- Zentropy 對接驗證。

### Phase 2b（本 Spec P1）

- 實作 domain auto-link。
- ZenOS admin 更新 Zentropy trusted_app 的 `auto_link_email_domains`。

### Phase 3（本 Spec 範圍外）

- Dashboard UI：workspace owner 在 UI 上管理 pending approvals（目前 API-only）。
- Token blocklist for jti（ADR-029 Risk 1 緩解）。
