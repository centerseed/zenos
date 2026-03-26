# SPEC: 新公司 Onboarding（第一位 Admin 建立）

## 狀態
Draft

## 背景

目前 ZenOS 的登入流程是：
- 使用者先完成 SSO（Google / email link）
- Dashboard 再用 email 到 `partners` collection 查身份

這代表新公司在「還沒有任何 `partners` 資料」時，第一位使用者即使 SSO 成功，也會被擋在 `NO_PARTNER`。
因此需要一個明確的 bootstrap 流程，先建立第一位 admin 身份。

## 目標

1. 新公司可以用內部 email（例如 IT）作為第一位 admin。
2. 第一位 admin 建立後可直接登入 Dashboard，並邀請其他成員。
3. 新成員加入後可看到與 admin 相同的任務資料 scope。

## 非目標

- 不處理跨公司資料共享
- 不提供終端客戶自助開通 portal（先用 script）
- 不在這個 spec 內重構 multi-tenant 資料模型

## 需求

### P0. 第一位 Admin 建立（Provision）

給定一個新的 Firebase project，營運或工程人員可用 script 建立第一位 admin partner。

必填輸入：
- `project_id`
- `admin_email`
- `display_name`

建立文件：`partners/{partnerId}`

欄位要求：
- `email = admin_email`
- `displayName = display_name`
- `status = "active"`
- `isAdmin = true`
- `apiKey = UUID`
- `authorizedEntityIds = []`（或初始化後回填）
- `sharedPartnerId = partnerId`（關鍵：公司共享 scope 起點）
- `invitedBy = null`
- `createdAt / updatedAt = now`

### P0. 登入與可用性

第一位 admin 完成 SSO 後，Dashboard 應可正常進入，不顯示 `NO_PARTNER`。

### P0. 後續邀請成員

admin 透過 Team 邀請成員時：
- 新成員 `sharedPartnerId` 繼承 inviter 的 shared scope（若 inviter 無此欄，fallback inviter id）
- 新成員啟用後能看到同一份 tasks 資料

## 驗收條件

1. Given 全新 Firebase project（`partners` 為空）  
   When 執行 provision script  
   Then `partners` 產生 1 筆 admin，且 `sharedPartnerId` 等於該文件 id。

2. Given 第一位 admin 已建立  
   When admin 用相同 email SSO 登入  
   Then 可進入 Dashboard，不出現尚未開通。

3. Given 第一位 admin 已登入  
   When 邀請第二位成員並完成啟用  
   Then 第二位成員在 `/tasks`、`/knowledge-map` 看到與 admin 相同的 task scope。

## 實作建議

1. 將 `scripts/seed_partners.py` 重構為可參數化的 `provision_customer.py` 或 `seed_first_admin.py`。
2. 寫入第一位 admin 時，立即寫入 `sharedPartnerId=self`。
3. 加入 idempotent 保護（同 email 已存在時拒絕重建並回報）。

## 風險與注意

1. 若既有資料缺少 `sharedPartnerId`，前端目前有 fallback，但應以回填 script 收斂。
2. 若同 email 存在多筆 partner，應有 deterministic 選擇規則（建議最早 createdAt）並盡快清理資料。

