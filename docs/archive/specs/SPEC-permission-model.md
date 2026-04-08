---
type: SPEC
id: SPEC-permission-model
status: Under Review
ontology_entity: 夥伴身份與邀請
created: 2026-04-03
updated: 2026-04-06
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

### `authorized_entity_ids` 重新定義為 L1 分享範圍

`partners.authorized_entity_ids`（現有欄位，`text[]`）重新定義語意：存放該 partner 被分享的 **L1 product ID 列表**。

- 原設計為細粒度 per-entity 授權，但從未實際使用（無任何查詢邏輯）。
- 重新定義為 L1-level scope；scope 本身不需要新增欄位，但若要明確表達 Internal / Scoped / Unassigned 身份，允許另加獨立欄位。
- 該欄位只描述「被分享哪些 L1」，**不再負責區分內部成員 vs 外部 / scoped partner 身份**。

| `authorized_entity_ids` 值 | 身份 | 能看什麼 |
|---------------------------|------|---------|
| `null` 或 `{}` | 未指派空間的 partner | 不自動取得任何 L1 可見性 |
| `{product-abc}` | Scoped partner | 只看 L1 `product-abc` 底下的資料 |
| `{product-abc, product-xyz}` | Scoped partner（多 L1，P1）| 看兩個 L1 底下的資料 |

空陣列（`{}`）與 null 等價，視為「尚未被分享任何 L1」，不是內部成員。

### Internal Member 是獨立狀態，不由空 scope 推導

內部成員能看整個 tenant 的資料，是一個**獨立身份狀態**，不能再由 `authorized_entity_ids` 為空來推導。

本 spec 定義產品語意如下：

- `authorized_entity_ids = []`：未被分享任何 L1，應看不到 tenant 資料
- `authorized_entity_ids = [L1...]`：Scoped partner，只看被分享的 L1
- Internal Member：可跨 L1 工作，但其身份由另一個明確狀態決定，不由空 scope 猜測
- Architect 可透過獨立欄位（例如 `access_mode`）表達此狀態；重點是 server-side 不得再用空 scope 推導 internal member

---

## 需求

### P0（必須有）

#### 1. `authorized_entity_ids` 重新定義語意

- **描述**：`authorized_entity_ids` 欄位存放 L1 product ID 列表。null 或空陣列代表「尚未分享任何 L1」，有值代表 scoped partner 的分享範圍。
- **Acceptance Criteria**：
  - Given partner 的 `authorized_entity_ids = null`，When 查詢任何資料，Then 不自動返回任何 L1 資料
  - Given partner 的 `authorized_entity_ids = {}`，When 查詢任何資料，Then 行為與 null 等價（不返回任何 L1 資料）
  - Given partner 的 `authorized_entity_ids = {product-abc}`，When 查詢 entities，Then 只返回 `product_id = product-abc` 的資料
  - Given partner 尚未被分享任何 L1，When 登入 Dashboard，Then 顯示「尚未設定存取空間」

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

- **描述**：`authorized_entity_ids` 的設定與修改只能由 tenant admin 執行。移除所有分享後，partner 回到「尚未設定存取空間」，而不是自動升格為內部成員。
- **Acceptance Criteria**：
  - Given 非 admin partner 嘗試修改自己或他人的 `authorized_entity_ids`，Then 系統拒絕並回傳 403
  - Given admin 將 scoped partner 的 `authorized_entity_ids` 改回 null，Then 該 partner 立即失去所有 L1 可見性
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
- Internal Member 的資料模型欄位設計（由 Architect 決定，必要時可加 migration）

---

## 安全測試需求（給 QA 參考）

本節定義在功能 AC 之外、必須通過的安全邊界測試場景。任何新實作或修改影響 auth/permission 路徑時，以下場景必須全部通過才算交付完成。

### ST-1：無效 API Key 應被拒絕（P0）

| 情境 | 預期結果 |
|------|---------|
| Bearer header 帶不存在的 api_key | HTTP 401，不洩漏錯誤細節 |
| X-Api-Key header 帶格式正確但已停用的 key | HTTP 401 |
| 完全不帶任何認證資訊 | HTTP 401 |
| 帶 status=suspended 的 partner 的 key | HTTP 401 |

**Acceptance Criteria**：
- Given 任何無效/停用的 API key，When 呼叫任何 MCP tool 或 Dashboard API，Then 回傳 HTTP 401，回應 body 不包含內部錯誤訊息或 stack trace

### ST-2：並發請求 ContextVar 隔離（P0）

場景：Partner A 和 Partner B 同時打相同的查詢 endpoint。

**Acceptance Criteria**：
- Given 兩個不同 partner 的請求同時進入 server，When 請求完成，Then Partner A 的回應只包含 Partner A 的資料，Partner B 的回應只包含 Partner B 的資料
- Given server 在處理 Partner A 的請求時拋出異常，When 異常被捕捉，Then ContextVar 必須被正確重置，不影響後續請求
- 測試方式：使用 asyncio 同時發出 2 個請求，驗證回傳的 `partner_id` 不交叉

### ST-3：跨租戶資料洩露（P0）

**Acceptance Criteria**：
- Given Partner A 持有合法 key，When 嘗試直接用 entity ID 存取屬於 Partner B 的 entity（GET by ID），Then 回傳空結果（非 403，以免洩漏存在性）
- Given Scoped partner 的 `authorized_entity_ids = {product-abc}`，When 嘗試存取 `product-xyz` 下的任何資源，Then 回傳空結果
- Given 任何 partner，When 執行 `search` 查詢，Then 結果集中不出現任何其他 tenant 的 entity/task/document

### ST-4：Admin 權限提升防護（P1）

**Acceptance Criteria**：
- Given 非 admin partner，When 嘗試修改自己的 `is_admin = true`，Then 系統拒絕並回傳 403
- Given 非 admin partner，When 嘗試修改他人的 `is_admin`，Then 系統拒絕並回傳 403
- Given 非 admin partner，When 嘗試修改他人的 `authorized_entity_ids`，Then 系統拒絕並回傳 403

### ST-5：Shared Partner 隔離（P1）

**Acceptance Criteria**：
- Given Partner A 與 Partner B 共享同一個 `shared_partner_id`，When Partner A 查詢，Then 只看到 shared_partner_id 對應 tenant 的資料，看不到其他 tenant 的資料
- Given 兩個不同 tenant 各有自己的 admin，When 分別查詢，Then 資料完全隔離

### 測試覆蓋要求

以下測試檔案必須存在且全部通過：

| 測試檔案 | 涵蓋場景 |
|---------|---------|
| `tests/interface/test_api_key_auth.py` | ST-1 全部情境 |
| `tests/interface/test_concurrent_isolation.py` | ST-2 全部情境 |
| `tests/interface/test_permission_isolation.py` | ST-3（已部分覆蓋，需補 cross-tenant by ID 測試）|
| `tests/interface/test_permission_visibility.py` | ST-4 全部情境 |

---

## 技術約束（給 Architect 參考）

- `authorized_entity_ids` 欄位現有 GIN index，可直接用於 `@>` 查詢；若 Architect 新增身份欄位，該 migration 應與 runtime enforcement 一起交付
- 所有查詢入口（dashboard_api.py、tools.py）必須在 session 建立時解析 `authorized_entity_ids`，注入查詢 context
- `authorized_entity_ids` 與 `sharedPartnerId` 是不同維度：scoped partner（客戶）的 `sharedPartnerId` 設為 admin_id（才能路由到正確 partition），但 scope 過濾在其之上額外執行
- `sharedPartnerId` 不得被當成「可看整個 tenant」的授權來源
- 存取其他 L1 資源時回傳空結果（非 403），以免暴露 L1 存在
