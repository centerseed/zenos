---
doc_id: TD-federation-auto-provisioning
title: 技術設計：Federation Auto-Provisioning
type: DESIGN
ontology_entity: zenos-auth-federation
status: draft
version: "0.1"
date: 2026-04-19
supersedes: null
spec: SPEC-federation-auto-provisioning
---

# 技術設計：Federation Auto-Provisioning

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-federation-auto-provisioning.md` — 定義 11 條 AC（AC-FAP-01~11），P0=Owner-Approve Flow，P1=Domain Auto-Link
- `docs/decisions/ADR-029-auth-federation-runtime.md` — D10 明確不做 auto-provisioning 的理由；本 TD 實作 D10 Phase 2 方向 A+B
- `src/zenos/domain/identity/federation.py:21-56` — `TrustedApp` 欠 `default_workspace_id`/`auto_link_email_domains`；`IdentityLink` 可直接複用
- `src/zenos/application/identity/federation_service.py:88-179` — `exchange_token()` Step 7（line 136-138）直接 return `IDENTITY_NOT_LINKED`，要改成三路分支
- `src/zenos/application/identity/federation_service.py:47-66` — `_verify_external_token` 回傳 dict 只有 `uid`/`email`，缺 `email_verified`（domain auto-link 要用）
- `src/zenos/infrastructure/identity/sql_trusted_app_repo.py:19-73` — `_row_to_model` 與 `create()` 均未帶新欄位
- `src/zenos/infrastructure/identity/sql_partner_repo.py:101-125` — `create()` 簽名已含所有 provisioning 需要的欄位
- `migrations/20260410_0018_auth_federation.sql` — `trusted_apps` 無 `default_workspace_id`/`auto_link_email_domains`；無 `pending_identity_links` 表
- `migrations/20260325_0001_sql_cutover_init.sql:18` — 無獨立 `workspaces` 表；workspace 由 `partners.shared_partner_id` 實現

### 重要更正（相對於 SPEC）

SPEC DB schema 寫 `REFERENCES zenos.workspaces(id)`，但 ZenOS 無 `workspaces` 表。
正確 FK：`trusted_apps.default_workspace_id REFERENCES zenos.partners(id)` — 指向 workspace owner 的 partner_id，與成員的 `shared_partner_id` 語意一致。

## AC Compliance Matrix

| AC ID | 描述 | 實作位置 | Test Function | 狀態 |
|-------|------|---------|---------------|------|
| AC-FAP-01 | exchange 無 link + default_workspace_id 存在 → 202 IDENTITY_LINK_PENDING + 建 pending_link | `federation_service.py:exchange_token` Step 7 分支 | `test_ac_fap_01_exchange_creates_pending_link` | STUB |
| AC-FAP-02 | 同 user 重複打 exchange → 不重複建 pending_link | `federation_service.py:exchange_token` + `SqlPendingLinkRepo.get_active` | `test_ac_fap_02_no_duplicate_pending_link` | STUB |
| AC-FAP-03 | owner 呼叫 GET pending-links → 正確清單 | `federation_api.py:list_pending_links` | `test_ac_fap_03_list_pending_links` | STUB |
| AC-FAP-04 | owner approve → partner + identity_link 建立 → 後續 exchange 成功 | `federation_service.py:approve_pending_link` | `test_ac_fap_04_approve_creates_link` | STUB |
| AC-FAP-05 | owner reject → pending_link=rejected → 後續 exchange 回 IDENTITY_NOT_LINKED | `federation_service.py:reject_pending_link` | `test_ac_fap_05_reject_blocks_exchange` | STUB |
| AC-FAP-06 | 7 天過期 → 舊 pending_link=expired，新建新 pending_link | `federation_service.py:exchange_token` expired 判斷 | `test_ac_fap_06_expired_pending_link` | STUB |
| AC-FAP-07 | approve/auto-link 建出的 partner role = guest | `federation_service.py:_provision_guest_partner` | `test_ac_fap_07_provisioned_partner_is_guest` | STUB |
| AC-FAP-08 | 已設 `default_workspace_id` 的 app 向 register 必填該欄位 | `federation_service.py:register_trusted_app` | `test_ac_fap_08_register_requires_workspace` | STUB |
| AC-FAP-09 | domain auto-link：verified email + 域名符合 → exchange 直接成功 | `federation_service.py:exchange_token` auto-link 分支 | `test_ac_fap_09_domain_autolink_success` | STUB |
| AC-FAP-10 | `email_verified=false` → domain auto-link 不觸發，fallback pending | `federation_service.py:exchange_token` | `test_ac_fap_10_unverified_email_no_autolink` | STUB |
| AC-FAP-11 | auto-link 建立的 partner，後續 exchange 行為與手動 link 相同 | `federation_service.py:exchange_token` | `test_ac_fap_11_autolink_partner_exchange` | STUB |

## Component 架構

### 新增檔案

| 路徑 | 內容 |
|------|------|
| `src/zenos/domain/identity/pending_link.py` | `PendingIdentityLink` dataclass |
| `src/zenos/infrastructure/identity/sql_pending_link_repo.py` | `SqlPendingIdentityLinkRepository` |
| `migrations/20260419_NNNN_federation_auto_provisioning.sql` | DB schema 變更 |
| `tests/spec_compliance/test_federation_auto_provisioning_ac.py` | AC test stubs |

### 修改檔案

| 路徑 | 變更 |
|------|------|
| `src/zenos/domain/identity/federation.py` | `TrustedApp` 加兩個欄位；`_verify_external_token` 加 `email_verified` 回傳 |
| `src/zenos/application/identity/federation_service.py` | `exchange_token()` Step 7 三路分支；加 `approve/reject/list_pending` 方法；`_provision_guest_partner` helper；`register_trusted_app` 加 `default_workspace_id` 必填 |
| `src/zenos/infrastructure/identity/sql_trusted_app_repo.py` | `_row_to_model` + `create()` 帶新欄位 |
| `src/zenos/infrastructure/identity/__init__.py` | export `SqlPendingIdentityLinkRepository` |
| `src/zenos/interface/federation_api.py` | 加 3 個 route handler + 3 個 Route |
| `scripts/register_trusted_app.py` | 加 `--default-workspace-id`（required）arg |

## Domain Models

### `PendingIdentityLink`（新建 `domain/identity/pending_link.py`）

```python
@dataclass
class PendingIdentityLink:
    id: str
    app_id: str
    issuer: str
    external_user_id: str
    email: str | None
    workspace_id: str        # = trusted_apps.default_workspace_id
    status: str              # pending | approved | rejected | expired
    created_at: datetime
    expires_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
```

### `TrustedApp` 擴充（修改 `domain/identity/federation.py`）

新增兩個欄位到 dataclass：

```python
default_workspace_id: str | None = None
auto_link_email_domains: list[str] = field(default_factory=list)
```

新增 helper method：

```python
def can_autolink_email(self, email: str, email_verified: bool) -> bool:
    if not email_verified or not self.auto_link_email_domains:
        return False
    domain = email.split("@")[-1] if "@" in email else ""
    return domain in self.auto_link_email_domains
```

## DB Schema

### Migration（`migrations/20260419_NNNN_federation_auto_provisioning.sql`）

```sql
-- 1. Extend trusted_apps
ALTER TABLE zenos.trusted_apps
    ADD COLUMN IF NOT EXISTS default_workspace_id  UUID REFERENCES zenos.partners(id),
    ADD COLUMN IF NOT EXISTS auto_link_email_domains TEXT[] NOT NULL DEFAULT '{}';

-- 2. New pending_identity_links table
CREATE TABLE IF NOT EXISTS zenos.pending_identity_links (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id           UUID NOT NULL REFERENCES zenos.trusted_apps(app_id),
    issuer           TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    email            TEXT,
    workspace_id     UUID NOT NULL REFERENCES zenos.partners(id),
    status           TEXT NOT NULL DEFAULT 'pending',
    reviewed_by      UUID REFERENCES zenos.partners(id),
    reviewed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '7 days'
);

-- Partial unique: only one active pending per (app, issuer, external_user_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_links_active
    ON zenos.pending_identity_links (app_id, issuer, external_user_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_pending_links_workspace
    ON zenos.pending_identity_links (workspace_id, status);
```

## 介面合約

### `FederationService.exchange_token()` Step 7 擴充邏輯

```python
# Step 7: Look up identity link (extended)
link = await self._link_repo.get(app_id, issuer, external_user_id)
if link is None:
    email = token_payload.get("email")
    email_verified = token_payload.get("email_verified", False)

    # P1: Domain auto-link (check first — lower friction)
    if app.can_autolink_email(email or "", email_verified):
        partner_id = await self._provision_guest_partner(
            workspace_id=app.default_workspace_id,
            email=email,
        )
        link = await self._link_repo.create(app_id, issuer, external_user_id, partner_id, email)
        # fall through to step 8

    # P0: Owner-approve pending flow
    elif app.default_workspace_id:
        pending = await self._pending_repo.get_active(app_id, issuer, external_user_id)
        if pending is None:
            await self._pending_repo.create(
                app_id=app_id, issuer=issuer,
                external_user_id=external_user_id,
                email=email, workspace_id=app.default_workspace_id,
            )
        return {
            "status": "IDENTITY_LINK_PENDING",
            "message": "Approval pending from workspace owner",
            "pending_link_id": pending.id if pending else None,
        }

    # Legacy: no workspace configured → 403
    else:
        return {"error": IDENTITY_NOT_LINKED, "message": "No identity link found"}
```

### 新增 `FederationService` 方法

| 方法 | 簽名 | 說明 |
|------|------|------|
| `_provision_guest_partner` | `(workspace_id, email, display_name=None) → str` | 建立 guest partner（`access_mode=guest`, `status=active`, `shared_partner_id=workspace_id`）；回傳 partner_id |
| `approve_pending_link` | `(pending_link_id, reviewer_partner_id) → dict` | 驗 owner 身份 → `_provision_guest_partner` → 建 identity_link → status=approved |
| `reject_pending_link` | `(pending_link_id, reviewer_partner_id) → dict` | 驗 owner 身份 → status=rejected |
| `list_pending_links` | `(workspace_id, reviewer_partner_id) → list[dict]` | 驗 owner 身份 → 列出 status=pending 的 pending_links |

### Owner 身份驗證（所有 pending 操作前）

```python
owner = await self._partner_repo.get_by_id(reviewer_partner_id)
# owner 的 id = workspace_id（即他就是 workspace 的建立者）
if owner is None or str(owner["id"]) != pending.workspace_id:
    return {"error": "FORBIDDEN", "message": "Not workspace owner"}
```

### 新增 HTTP Routes（`interface/federation_api.py`）

| Method | Path | Auth | Handler |
|--------|------|------|---------|
| GET | `/api/federation/pending-links` | Firebase ID token（Dashboard） | `list_pending_links` |
| POST | `/api/federation/pending-links/{id}/approve` | Firebase ID token | `approve_pending_link` |
| POST | `/api/federation/pending-links/{id}/reject` | Firebase ID token | `reject_pending_link` |

Auth 複用現有 Dashboard 的 `_auth_and_scope`（Firebase token → partner）。

### `_verify_external_token` 補充回傳欄位

```python
return {
    "uid": decoded.get("uid") or decoded.get("user_id"),
    "email": decoded.get("email"),
    "email_verified": decoded.get("email_verified", False),  # 新增
}
```

## `register_trusted_app.py` 更新

```bash
# 新增 --default-workspace-id（required for new apps）
python scripts/register_trusted_app.py \
  --app-name "zentropy" \
  --app-secret "<secret>" \
  --issuers "https://securetoken.google.com/<project>" \
  --scopes "read,write,task" \
  --default-workspace-id "<owner-partner-uuid>"
  [--auto-link-domains "zentropy.app"]   # optional, P1
```

## Done Criteria（Developer 必須全部滿足）

1. `migrations/20260419_NNNN_federation_auto_provisioning.sql` 可無錯跑完（`.venv/bin/python scripts/run_sql_migrations.py`）。
2. `tests/spec_compliance/test_federation_auto_provisioning_ac.py` 的 11 條 AC test 全部從 FAIL 轉 PASS（`.venv/bin/pytest tests/spec_compliance/test_federation_auto_provisioning_ac.py -x`）。
3. AC-FAP-01：exchange 回傳 `{"status": "IDENTITY_LINK_PENDING", "pending_link_id": "<uuid>"}` + DB 有新 pending 記錄。
4. AC-FAP-02：相同 user 重打不新增 pending_link（DB count 仍 1）。
5. AC-FAP-04：approve 後 `SqlIdentityLinkRepository.get()` 能找到新 link，後續 exchange 回 200 access_token。
6. AC-FAP-05：reject 後下次 exchange 回 `{"error": "IDENTITY_NOT_LINKED"}`（非 `IDENTITY_LINK_PENDING`）。
7. AC-FAP-07：`_provision_guest_partner` 建出的 partner：`access_mode="guest"`, `status="active"`, `shared_partner_id=workspace_id`。
8. AC-FAP-09：domain auto-link 的 partner 在同一次 exchange 呼叫內完成（不需第二次呼叫）。
9. `register_trusted_app.py --help` 顯示 `--default-workspace-id` 為 required 參數。
10. 既有 unit tests 全部繼續通過（`.venv/bin/pytest tests/ -x --ignore=tests/spec_compliance`）。

**以下 AC test 必須從 FAIL 變 PASS：**
AC-FAP-01, AC-FAP-02, AC-FAP-03, AC-FAP-04, AC-FAP-05, AC-FAP-06, AC-FAP-07, AC-FAP-08, AC-FAP-09, AC-FAP-10, AC-FAP-11

## Risk Assessment

### 1. 不確定的技術點

- **Owner 身份驗證 route**：pending-link API 複用 `dashboard_api._auth_and_scope` 的 Firebase token 解析，但 `federation_api.py` 目前是獨立 Starlette app，不共享 Dashboard middleware。需確認 Firebase Admin SDK 在 `federation_api.py` handler 內已初始化（`firebase_admin.initialize_app()` 在 server startup 跑）。[需 Developer 確認]
- **`partners.id` 是 UUID 還是 TEXT？** migration 0001 的 `shared_partner_id` 欄位是 `text null`，`partners.id` 也是 text。`default_workspace_id` FK 需要對應型別（UUID vs TEXT）。[Developer 必須讀 migration 0001 確認]

### 2. 替代方案與選擇理由

- **`workspace_id` FK 指向 `partners` 而非獨立 `workspaces` 表**：ZenOS 無 `workspaces` 表，workspace 概念由 `shared_partner_id` 實現。直接 FK partners 最省改動。
- **Owner 驗證用 `reviewer_partner_id == workspace_id`**：workspace owner 的 `id` 就是 workspace key（其他成員的 `shared_partner_id` 都指向 owner.id），這是現有語意，不需新增 `workspace_owner` 欄位。

### 3. 需要用戶確認的決策

- `auto_link_email_domains` 留作 P1 optional，Zentropy 初期只用 Owner-Approve 就夠。部署後若要啟用 domain auto-link，需要 ZenOS admin 手動 `UPDATE zenos.trusted_apps SET auto_link_email_domains = '{"zentropy.app"}' WHERE app_name = 'zentropy'`。[已與用戶確認]

### 4. 最壞情況與修正成本

- **`_provision_guest_partner` 建了 partner 但 identity_link create 失敗**：會留下孤兒 partner。目前 `approve_pending_link` 應包在 DB transaction 內（partner insert + identity_link insert + pending status update = 一個 atomic transaction）。Developer 必須確保 atomicity。成本：若未加 transaction，修正需額外一個 cleanup script。
