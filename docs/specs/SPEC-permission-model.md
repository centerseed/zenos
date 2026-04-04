---
type: SPEC
id: SPEC-permission-model
status: Draft
ontology_entity: TBD
created: 2026-04-03
updated: 2026-04-03
---

# Feature Spec: Partner 權限模型

## 背景與動機

ZenOS 現有的 partner 模型假設所有 partner 都看到同一個 tenant 的全部資料（透過 `sharedPartnerId` 機制）。這對內部成員是正確的，但無法支援以下場景：

- 邀請外部客戶進入 ZenOS，讓他們只看到與自己相關的 L1 資料
- 在同一個 tenant 內，針對特定 entity 管控誰能看到

本 spec 定義 ZenOS 的完整權限模型，作為 Client Portal（SPEC-client-portal）的基礎。

---

## 核心概念

### 兩個維度的存取控制

| 維度 | 欄位 | 控制什麼 |
|------|------|---------|
| **範圍（Scope）** | `partner.authorized_entity_ids` | 這個 partner 能看哪些 L1？ |
| **可見性（Visibility）** | `entity.visibility` | 這個 entity 能被哪些角色看到？ |

兩個維度同時成立：partner 必須先有對應 L1 的 scope，且 entity 的 visibility 允許，才能看到該 entity。

### `authorized_entity_ids` 重新定義為 L1 Scope

`partners.authorized_entity_ids`（現有欄位，`text[]`）重新定義語意：存放該 partner 被授權存取的 **L1 product ID 列表**。

- 原設計為細粒度 per-entity 授權，但從未實際使用（無任何查詢邏輯）。
- 重新定義為 L1-level scope，不需要新增欄位或 migration。

| `authorized_entity_ids` 值 | 身份 | 能看什麼 |
|---------------------------|------|---------|
| `null` 或 `{}` | 內部成員 | 走現有 `sharedPartnerId` 邏輯，看整個 tenant 的資料 |
| `{product-abc}` | Scoped partner | 只看 L1 `product-abc` 底下的資料 |
| `{product-abc, product-xyz}` | Scoped partner（多 L1，P1）| 看兩個 L1 底下的資料 |

空陣列（`{}`）與 null 等價，視為內部成員。

---

## 需求

### P0（必須有）

#### 1. `authorized_entity_ids` 重新定義語意

- **描述**：`authorized_entity_ids` 欄位存放 L1 product ID 列表。null 或空陣列 = 內部成員；有值 = scoped partner。
- **Acceptance Criteria**：
  - Given partner 的 `authorized_entity_ids = null`，When 查詢任何資料，Then 行為與現有內部成員一致（看全部）
  - Given partner 的 `authorized_entity_ids = {}`，When 查詢任何資料，Then 行為與 null 等價（看全部）
  - Given partner 的 `authorized_entity_ids = {product-abc}`，When 查詢 entities，Then 只返回 `product_id = product-abc` 的資料

#### 2. Server 端強制執行 scope 過濾

- **描述**：scope 過濾必須在 server 端強制執行，涵蓋 Dashboard API 與 MCP tools 兩層，前端無法繞過。
- **Acceptance Criteria**：
  - Given scoped partner 直接打 API 存取其他 L1 的資源，Then 回傳空結果，不洩漏其他 L1 的存在（不使用 403，以免暴露該 L1 存在）
  - Given scoped partner 透過 MCP 工具查詢，Then 查詢結果同樣受 scope 限制
  - Given scoped partner 的 `authorized_entity_ids` 為有效 L1 ID 但該 L1 已被刪除，Then 查詢回傳空結果，不報錯

#### 3. Entity visibility 與 scope 的組合規則

- **描述**：Partner 能看到某個 entity，必須同時滿足 scope 條件和 visibility 條件。
- **可見性規則**：

  | `entity.visibility` | Admin | 內部非 admin | Scoped partner（客戶）|
  |---------------------|-------|------------|----------------------|
  | `public` | ✅ | ✅ | ✅（在 scope 內）|
  | `restricted` | ✅ | ❌ | ❌ |
  | `role-restricted` | ✅ | 依 roles 判斷 | ❌ |
  | `confidential` | ✅ | ❌ | ❌ |

- **設計原則**：Scoped partner（客戶）預設看得到 L1 內所有 `public` entity，admin 刻意標記才能隱藏。`restricted` 與 `confidential` 的差異是內部管理用的，對客戶效果相同（都看不到）。
- **Acceptance Criteria**：
  - Given scoped partner 查詢自己 L1 下的 entities，Then 只返回 `visibility = public` 的 entity
  - Given admin 將一個 entity 改為 `restricted`，When scoped partner 查詢，Then 該 entity 從結果消失
  - Given 非 admin 內部成員查詢，Then 看不到 `restricted` 和 `confidential` 的 entity
  - Given admin 查詢，Then 可以看到所有 visibility 的 entity

#### 4. Task 可見性規則

- **描述**：Task 不使用 visibility 欄位控制客戶可見性。Scoped partner 在自己的 L1 內預設能看到所有 task。
- **Acceptance Criteria**：
  - Given scoped partner 查詢自己 L1 下的 tasks，Then 返回該 L1 下所有 task，不受 visibility 過濾
  - Given scoped partner 查詢其他 L1 的 tasks，Then 回傳空結果

#### 5. Documents 與 Blindspots 的 scope 規則

- **描述**：Document（文件）跟 entity 一樣適用 visibility 規則；Blindspot 對 scoped partner 完全不可見。
- **Acceptance Criteria**：
  - Given scoped partner 查詢文件，Then 只返回 L1 scope 內、visibility = public 的文件
  - Given scoped partner 查詢，Then Blindspot 類型資料完全不出現在結果中

#### 6. 只有 Admin 可以設定 `authorized_entity_ids`

- **描述**：`authorized_entity_ids` 的設定與修改只能由 tenant admin 執行，包含升格（改回 null）與降格（設為 L1 ID）。
- **Acceptance Criteria**：
  - Given 非 admin partner 嘗試修改自己或他人的 `authorized_entity_ids`，Then 系統拒絕並回傳 403
  - Given admin 將 scoped partner 的 `authorized_entity_ids` 改回 null，Then 該 partner 立即取得內部成員的完整存取權
  - Given admin 修改設定，Then 下次該 partner 查詢時即套用新的 scope

### P1（應該有）

#### 7. 單一 partner 可授權多個 L1

- **描述**：一個 scoped partner 可以被授權存取多個 L1。
- **Acceptance Criteria**：
  - Given `authorized_entity_ids = {product-abc, product-xyz}`，When 查詢，Then 返回兩個 L1 下的 public entity
  - Given admin 新增或移除某個 L1，When 操作完成，Then 下次查詢即反映新的 scope

---

## 明確不包含

- 細粒度的 per-entity per-partner 授權（`authorized_entity_ids` 不再用於單一 entity 控制）
- Partner 自行管理自己的 `authorized_entity_ids`
- L2 / L3 層級的獨立 scope 設定（scope 以 L1 為單位，L2/L3 繼承）

---

## 技術約束（給 Architect 參考）

- `authorized_entity_ids` 欄位現有 GIN index，可直接用於 `@>` 查詢，不需要額外 migration
- 所有查詢入口（dashboard_api.py、tools.py）必須在 session 建立時解析 `authorized_entity_ids`，注入查詢 context
- `authorized_entity_ids` 與 `sharedPartnerId` 是不同維度：scoped partner（客戶）的 `sharedPartnerId` 設為 admin_id（才能路由到正確 partition），但 scope 過濾在其之上額外執行
- 存取其他 L1 資源時回傳空結果（非 403），以免暴露 L1 存在
