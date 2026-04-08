---
type: SPEC
id: SPEC-partner-access-scope
status: Under Review
ontology_entity: 夥伴身份與邀請
created: 2026-04-06
updated: 2026-04-06
---

# Feature Spec: Partner 存取範圍與分享模型

## 背景與動機

ZenOS 現有 spec 對同 tenant 內 partner 的資料語意有衝突：

- `SPEC-partner-data-scope` 將 `sharedPartnerId` 定義為同 tenant 共享資料的主機制
- `SPEC-permission-model` 與 `SPEC-client-portal` 又要求 partner 只能看到被授權的 L1 空間

這導致一個核心問題沒有被明確定義：

**新 partner 進入同一個 tenant 後，預設應該看到全部、看到空白，還是看到被分享的部分？**

本 spec 用來收斂這個語意，作為後續 Partner 權限、Client Portal、邀請流程的共同基礎。

---

## 核心原則

### 1. Tenant 路由與資料可見性是兩個不同維度

- `sharedPartnerId` 只負責把請求路由到正確的 tenant partition
- Partner 最終能看到什麼資料，不由 `sharedPartnerId` 決定
- 資料可見性由「Partner 存取狀態 + L1 分享範圍 + visibility 規則」共同決定

### 2. 同一個 tenant / 同一個 DB 內，也可以做到預設完全隔離

不需要拆成不同 project 或不同 DB，仍可在同一 tenant partition 下做到：

- Partner A 看不到 Partner B 的未分享資料
- Partner A 不會感知未分享 L1 的存在
- 只有被明確分享的 L1 product 子樹才可見

### 3. 分享單位是 L1 product

Admin 對 partner 的分享邊界是 **L1 product**。

- 分享某個 L1 product
- 該 partner 便可看到該 L1 底下的 entity / document / task
- 未被分享的其他 L1 完全不可見

### 4. 新 partner 預設不應自動取得 tenant 全域可見性

新 partner 完成 SSO 後，若尚未被分享任何 L1，應進入「未指派空間」狀態：

- 看不到 tenant 內任何 product、entity、document、task
- UI 顯示「尚未設定存取空間」
- 不顯示空白畫面，也不洩漏其他 L1 的存在

---

## Partner 存取狀態

### 1. Internal Member

內部成員可以跨 tenant 內的所有 L1 工作，但仍受 visibility 規則限制。

### 2. Scoped Partner

Scoped partner 只能看到被分享的 L1 product 子樹。

- 單一 L1 為 P0
- 多個 L1 為 P1

### 3. Unassigned Partner

Unassigned partner 是已完成身份驗證、存在 partner profile，但尚未被分享任何 L1 的使用者。

- 可登入
- 不可看到任何 tenant 資料
- 可被 admin 之後指派為 Internal Member 或 Scoped Partner

> 本 spec 只定義這三種產品語意，不限定資料表一定用哪個欄位表示。是否新增明確欄位、或以既有欄位組合表示，由 Architect 決定。

---

## 需求

### P0（必須有）

#### 1. 新 partner 預設為未指派空間

- **描述**：新 partner 第一次完成 SSO 或被建立 partner profile 時，若 admin 尚未分享任何 L1，該 partner 不得自動看到 tenant 全部資料。
- **Acceptance Criteria**：
  - Given 新 partner 完成登入，When 尚未被分享任何 L1，Then 看不到任何 product、entity、document、task
  - Given 新 partner 完成登入，When 尚未被分享任何 L1，Then 顯示「尚未設定存取空間，請聯繫管理員」
  - Given 新 partner 尚未被分享任何 L1，When 直接呼叫 API 或 MCP 查詢，Then 回傳空結果，不洩漏其他 L1 存在

#### 2. L1 分享後才可見

- **描述**：Admin 分享某個 L1 product 後，partner 才取得該 L1 子樹的可見性。
- **Acceptance Criteria**：
  - Given Admin 對 partner 分享 `product-abc`，When partner 查詢 Projects，Then 只看到 `product-abc`
  - Given partner 已被分享 `product-abc`，When 查詢其底下的 entity，Then 看到 `product-abc` 子樹內允許可見的資料
  - Given partner 已被分享 `product-abc`，When 查詢其他 L1，Then 回傳空結果

#### 3. 分享邊界是整個 L1 子樹

- **描述**：L1 product 的分享效果向下涵蓋所有掛在該 L1 下的資料。
- **Acceptance Criteria**：
  - Given partner 被分享某個 L1，When 查詢 entities，Then 可見範圍包含該 L1 與其子孫節點
  - Given partner 被分享某個 L1，When 查詢 documents，Then 可見範圍只限該 L1 子樹內且符合 visibility 的文件
  - Given partner 被分享某個 L1，When 查詢 tasks，Then 可見範圍只限該 L1 子樹內的任務

#### 4. `sharedPartnerId` 不得再被解讀為資料共享授權

- **描述**：`sharedPartnerId` 只能代表 tenant routing，不代表「可看到整個 tenant」。
- **Acceptance Criteria**：
  - Given 兩個 partner 具有相同 tenant routing key，When 其中一人未被分享任何 L1，Then 他仍看不到另一人的資料
  - Given 兩個 partner 具有相同 tenant routing key，When 其中一人只被分享 `product-abc`，Then 他仍看不到其他未分享的 L1

#### 5. 分享可被撤回

- **描述**：Admin 可以移除 partner 的 L1 scope；移除後應立即失去該 L1 可見性。
- **Acceptance Criteria**：
  - Given partner 原本可見 `product-abc`，When admin 移除該分享，Then partner 下次查詢起即看不到 `product-abc`
  - Given partner 所有已分享 L1 都被移除，Then partner 回到「尚未設定存取空間」狀態

### P1（應該有）

#### 6. 單一 partner 可被分享多個 L1

- **Acceptance Criteria**：
  - Given partner 被分享 `product-abc` 與 `product-xyz`，When 查詢，Then 只看到這兩個 L1 的子樹

#### 7. Internal Member 與 Scoped Partner 必須是明確狀態，不可用空 scope 猜測

- **Acceptance Criteria**：
  - Given 某 partner 被標記為 Internal Member，When 查詢，Then 可跨 tenant 內所有 L1 工作
  - Given 某 partner 為 Scoped Partner 且未被分享任何 L1，When 查詢，Then 不可見任何 tenant 資料

---

## 與既有 spec 的關係

### 對 `SPEC-partner-data-scope`

本 spec 取代其中「同 tenant 非 admin partner 預設共享全部資料」的語意。

保留的部分：

- `sharedPartnerId` / canonical partition key 作為 tenant routing 機制
- 同 tenant partner 的資料可落在同一 partition

被取代的部分：

- 新成員登入後預設看到完整 tenant 資料
- `sharedPartnerId` 等同於資料共享授權

### 對 `SPEC-permission-model`

本 spec 定義其前置語意：

- `authorized_entity_ids` 代表 L1 分享範圍，而不是身份類型本身
- 空分享範圍不等於內部成員
- Internal / Scoped / Unassigned 是另一個明確狀態維度

### 對 `SPEC-client-portal`

Client Portal 的「尚未設定存取空間」畫面與 L1 scope 行為，以本 spec 為準。

---

## 明確不包含

- 不定義 partner 狀態如何儲存在資料表
- 不定義分享設定 UI 細節
- 不定義 API / schema / migration 方案
- 不處理跨 tenant 物理隔離

---

## 開放問題

1. Internal Member / Scoped Partner / Unassigned Partner 的正式資料模型要如何表達？
2. 新 SSO 使用者若 email 已存在於 tenant 內，是否沿用原 partner profile 還是進入待認領流程？
3. 多 L1 partner 在 UI 上是否需要「切換目前工作空間」的明確互動？
