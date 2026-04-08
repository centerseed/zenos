---
doc_id: SPEC-partner-data-scope
title: Feature Spec：Partner Data Scope（單 Tenant 內的資料共享模型）
type: SPEC
ontology_entity: ZenOS MCP Server
status: superseded
version: "1.0"
date: 2026-03-30
supersedes: null
superseded_by: SPEC-partner-access-scope
---

> Superseded by `SPEC-partner-access-scope`. This file remains only as historical context for the tenant routing model.

# Feature Spec：Partner Data Scope

## 背景與動機

SPEC-multi-tenant.md 已定義：
- **Tenant** = 一家客戶公司，對應一個 Firebase Project / PostgreSQL schema
- **Partner** = 同一 tenant 內的一個成員，有自己的 `id`、`email`、`apiKey`

但 SPEC-multi-tenant.md 沒有回答的關鍵問題是：
**同一 tenant 內的多個 partner，他們的資料應該共享還是各自隔離？**

過去這個問題被擱置，導致：
- MCP agent 用 API key A 寫的 entity → 存在 partner_id = A 的 partition
- Barry 用 Firebase 登入 → 查的是 partner_id = B 的 partition
- A ≠ B → MCP 寫的資料在 Dashboard 消失

**這份 spec 回答這個問題，並定義正確的實作方式。**

---

## 核心定義

### Tenant Partition Key

每個 tenant 有一個 **canonical partition key**，即該 tenant 的 **admin partner 的 id**。

所有屬於這個 tenant 的資料，在 SQL 裡的 `partner_id` 欄位都等於這個 canonical key。

### sharedPartnerId 機制

每個 partner record 有一個 `sharedPartnerId` 欄位：
- **Admin partner**：`sharedPartnerId = null`，`effective_id = self.id`（自己就是 canonical key）
- **非 admin partner**：`sharedPartnerId = admin_id`，`effective_id = admin_id`

讀寫資料時的 `effective_id` 決定：
```
effective_id = partner.sharedPartnerId ?? partner.id
```

所有非 admin partner 寫入/讀取時都會路由到 admin 的 partition，達成同 tenant 資料共享。

---

## 需求

### P0（立即修復）

#### 1. 新增 partner 時必須設定 sharedPartnerId

**描述**：在同一個 tenant 內建立新 partner 時，系統必須自動將 `sharedPartnerId` 設為 admin 的 `id`。不允許在 tenant 內存在 `sharedPartnerId = null` 的非 admin partner。

**Acceptance Criteria**：
- Given `isAdmin = false` 的新 partner 被建立，When 系統寫入，Then `sharedPartnerId` 自動設為 tenant admin 的 `id`
- Given admin partner，When 查詢，Then `sharedPartnerId = null`（admin 本身就是 partition key）
- Given 任何 partner 的 `effective_id`，When 發起 SQL 查詢，Then `WHERE partner_id = effective_id` 指向同一個 partition

#### 2. 所有既有 partner 補齊 sharedPartnerId

**描述**：現有非 admin partner（包括 MCP API key 的 partner）若 `sharedPartnerId = null`，必須用 migration script 補上。

**Acceptance Criteria**：
- Given 執行 migration script 後，When 查詢所有非 admin partner，Then `sharedPartnerId` 全部非 null
- Given migration 後，When MCP agent 用現有 API key 寫入 entity，Then entity 的 `partner_id` = admin_id

#### 3. 孤立資料（wrong partition）補回正確 partition

**描述**：過去因 `sharedPartnerId` 未設定，entity/task/relationship 等資料可能落在錯誤的 partner partition 下。必須執行 `fix_entity_partner_ids.py` 將這些資料移回 admin partition。

**Acceptance Criteria**：
- Given `fix_entity_partner_ids.py --dry-run` 執行結果，When 顯示有孤立 rows，Then 執行 live 修復
- Given 修復後，When Dashboard 查詢（以 admin 身份登入），Then 所有 entity 包含 paceriz L2 都可見

#### 4. 端到端整合測試

**描述**：加入一條 E2E 測試，驗證「MCP write → SQL → Dashboard API」三層打通。

**Acceptance Criteria**：
- Given MCP agent 用 non-admin API key 寫入一個新 entity
- When Dashboard API 以 admin Firebase token 查詢
- Then 新 entity 出現在結果中（partner_id 一致）

---

### P1（本週修完）

#### 5. 用戶邀請流程自動設定 sharedPartnerId

**描述**：當管理員從 Dashboard 邀請新成員加入時，新成員的 partner record 必須自動帶 `sharedPartnerId = admin_id`。

**Acceptance Criteria**：
- Given admin 邀請新成員（email），When 新成員 partner record 建立，Then `sharedPartnerId = admin.id`
- Given 新成員用自己的 Firebase 帳號登入 Dashboard，When 查詢 entities，Then 看到所有 tenant 資料

#### 6. provision_customer.py 更新

**描述**：開設新客戶 tenant 的腳本必須：先建 admin partner，再建其他成員時自動帶 `sharedPartnerId`。

**Acceptance Criteria**：
- Given 執行 `provision_customer.py` 新增一個 tenant，When 建立第二個成員，Then `sharedPartnerId = first_admin.id`

---

## 明確不包含

- 跨 tenant 資料共享（各 tenant 之間資料完全隔離，不做）
- Per-entity 可見性設定（visibility 欄位管控的是 entity 層級，非 partition 層級，不在此 spec 範圍）
- 成員之間的細粒度 RBAC（誰能修改誰的 entity，Phase 2 再做）

---

## 技術約束（給 Architect）

- `sharedPartnerId` 邏輯已存在於 `tools.py` 和 `dashboard_api.py`，只需要確保 DB 資料正確
- `fix_entity_partner_ids.py` 已寫好，可直接執行
- partner record 在 SQL `partners` 表，有 `shared_partner_id` 欄位（需確認欄位名稱）
- 所有 partner 建立路徑（MCP provisioning、用戶邀請 API、seed script）都需要更新

---

## 成功條件

修復完成後，以下情境全部通過：
1. Barry 用 Firebase 登入 Dashboard → 看到 ZenOS 和 Paceriz 的所有 L1 + L2 entities
2. MCP agent 寫入新 entity → Dashboard 立即可見（不需要 migration）
3. 新邀請的成員加入後 → 看到完整 tenant 資料，不是空的
