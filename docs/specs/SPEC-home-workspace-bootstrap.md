---
type: SPEC
id: SPEC-home-workspace-bootstrap
status: Under Review
ontology_entity: 夥伴身份與邀請
created: 2026-04-22
updated: 2026-04-22
supersedes:
---

# Feature Spec: Home Workspace Bootstrap from Shared Product

## 1. 背景

ZenOS 目前的正式模型是：

- 使用者登入後預設進入自己的 `home workspace`
- 與他人協作時，透過切換到對方的 `shared workspace`
- `guest` 在 shared workspace 只看到被授權的 `product(L1)` subtree

這個模型解決了「安全共享」問題，但沒有解決另一個合作型場景：

- owner 已經在自己的 workspace 整理好一棵特定 `product(L1)` 與其下游資訊
- 客戶接受邀請後，希望在自己的 `home workspace` 就先有一份可工作的起始內容
- 這份內容不是 shared projection，而是客戶自己 home workspace 裡的 owned copy

目前系統沒有這個 bootstrap 能力。

## 2. 問題定義

如果沒有 home workspace bootstrap，外部合作對象每次都只能：

1. 登入後先回自己的空白 home workspace
2. 再切去 owner 的 shared workspace
3. 在 shared projection 裡查看資料

這不利於以下情境：

- 顧問案啟動時，先給客戶一份 product subtree 模板
- 要求客戶在自己的 workspace 持續補資料，而不是永遠留在別人的 shared workspace
- 後續希望 shared workspace 與 home workspace 各自演化，不互相污染

## 3. 目標

新增一個正式能力，讓 workspace owner 可以指定某個 shared `product(L1)` 作為 bootstrap 來源，讓被邀請者在自己的 `home workspace` 中建立一份可工作的 copy。

這個功能必須：

- 保持「登入預設進 home workspace」不變
- 保持 shared workspace projection 與 home workspace owned copy 的邊界清楚
- 先支援 `product(L1)` subtree 作為 bootstrap 單位

## 4. 明確不做

- 不改成登入後直接進 shared workspace
- 不把 shared workspace projection 自動變成 home workspace 內容
- 不做雙向自動同步
- 不在 P0 複製 CRM、設定、Team、Zentropy 等 application layer surface
- 不在 P0 複製 `task / plan / task comment / attachment`

## 5. 核心模型

### 5.1 Shared Projection 與 Home Bootstrap Copy

`shared workspace projection`：

- 是 owner workspace 的受限投影
- guest 在該空間中看到的內容仍屬於 owner workspace
- guest 在 shared workspace 新建的 L3 / task 仍寫回 shared workspace

`home workspace bootstrap copy`：

- 是把來源 `product(L1)` subtree 複製成 target user `home workspace` 裡的新內容
- 複製完成後，內容的 owner / tenant 屬於 target user home workspace
- 複製後與來源不是同一份資料，不共享主鍵，不共享 write path

### 5.2 Bootstrap 單位

P0 的正式 bootstrap 單位固定為：

- 一個或多個 `product` type 的 L1 entity

不得在 P0 直接以：

- 任意 L2
- 任意單一 L3
- `company` L1

作為 bootstrap root。

原因：

- 目前 Team UI 的分享入口與 guest scope 都以 `product(L1)` 為主
- 先把 `product` 路徑做穩，比同時支援多種 root type 更重要

### 5.3 Bootstrap Provenance

每個被 bootstrap 進 home workspace 的 entity，必須保留來源追溯資訊。

至少包含：

- `source_workspace_id`
- `source_entity_id`
- `source_root_entity_id`
- `bootstrap_applied_at`

這份 provenance 用於：

- 後續 re-apply / idempotent update
- UI 顯示這份內容來自哪個 shared product
- 未來若要做 manual sync / rebase，有穩定對應依據

## 6. P0 需求

### P0-1 Owner 可設定哪些 shared product 可 bootstrap 到對方 home workspace

- Team invite flow 與 scope edit flow 必須支援設定 `home workspace bootstrap sources`
- bootstrap source 必須是目前已授權給該 guest 的 `product(L1)` 子集
- 若 guest 沒有任何授權 product，則不得設定 bootstrap source

### P0-2 Guest 在 home workspace 可看到待匯入的 bootstrap 入口

- 當 guest 回到自己的 `home workspace`，若存在尚未套用的 bootstrap source，Products 頁必須顯示明確入口
- 入口必須列出將被匯入的來源 product 名稱
- 入口不得把 shared workspace 誤導成已自動匯入

### P0-3 Apply bootstrap 會在 home workspace 建立 owned copy

- 使用者在 home workspace 觸發 apply 後，系統必須把來源 `product(L1)` subtree 複製進自己的 home workspace
- P0 先支援複製：
  - `public` entities
  - 複製集合內的 relationships
- P0 不複製：
  - tasks / plans
  - task comments / attachments
  - 非 public 節點

### P0-4 Apply bootstrap 必須 idempotent

- 若同一個來源 product 已 bootstrap 過，再次 apply 不得建立平行重複 product
- 系統必須根據 provenance 對應到既有 copy，做 update-or-skip

### P0-5 Login 與 active workspace 規則不得被改壞

- 套用 bootstrap 後，登入預設仍回 home workspace
- shared workspace 仍是獨立可切換的 active workspace
- 不得因為 bootstrap 存在，就把 shared workspace 設成新的預設入口

## 7. Acceptance Criteria

- `AC-HWB-01`
  - Given owner 在 Team 邀請或編輯 guest 範圍
  - When guest 被授權 `product-A` 與 `product-B`
  - Then owner 可另外指定其中一個或多個 product 作為 `home workspace bootstrap sources`

- `AC-HWB-02`
  - Given owner 把 guest 設為 `member` 或 `unassigned`
  - When 儲存範圍
  - Then 系統不得保留任何 bootstrap source 設定

- `AC-HWB-02A`
  - Given owner 設定 bootstrap source
  - When 該 source 不在 guest 當前被授權的 `authorizedEntityIds` 內
  - Then 系統拒絕儲存該設定，不得接受超出分享範圍的 bootstrap source

- `AC-HWB-03`
  - Given guest 登入 ZenOS 且預設回到自己的 `home workspace`
  - When 該 user 存在待套用 bootstrap source
  - Then Products 頁顯示明確的 bootstrap CTA 與來源 product 名稱

- `AC-HWB-03A`
  - Given guest 回到自己的 `home workspace`
  - When 不存在任何 pending bootstrap source
  - Then Products 頁不得顯示 bootstrap CTA 或誤導性的「已同步」文案

- `AC-HWB-04`
  - Given guest 在 home workspace 按下 apply bootstrap
  - When 套用成功
  - Then target home workspace 內建立一份新的 `product(L1)` copy 與其 `public` 下游 entities

- `AC-HWB-04A`
  - Given guest 不在 `home workspace`
  - When 嘗試呼叫 apply bootstrap
  - Then 系統拒絕該操作，不得在 shared workspace 直接執行 home bootstrap

- `AC-HWB-04B`
  - Given bootstrap source 對應的來源 workspace 或來源 entity 已不存在
  - When guest 在 home workspace 觸發 apply bootstrap
  - Then 系統回傳明確錯誤，且不得建立半套 copy

- `AC-HWB-04C`
  - Given 同一次 apply 包含多個 bootstrap source
  - When 其中一個 source 複製失敗
  - Then 失敗 source 不得標記為 applied，且 API 回應必須指出成功與失敗的 source 清單

- `AC-HWB-05`
  - Given 來源 subtree 中有 `public` 與 `restricted/confidential` 節點
  - When apply bootstrap
  - Then P0 只複製 `public` 節點與其內部 relationships，不複製 `restricted/confidential`

- `AC-HWB-05A`
  - Given 某條 relationship 的 source 與 target 沒有同時落在複製集合內
  - When apply bootstrap
  - Then 該 relationship 不得被複製到 target home workspace

- `AC-HWB-06`
  - Given 同一個來源 product 已 bootstrap 過一次
  - When 使用者再次 apply
  - Then 系統只可補齊缺少的 bootstrap entity / relationship，或略過既有 copy，不得建立第二份平行 product，也不得覆寫 target home workspace 的本地整理內容

- `AC-HWB-06A`
  - Given 同一個來源 entity 已在 target home workspace 有對應的 bootstrap copy
  - When 再次 apply
  - Then 系統必須根據 `details.bootstrap_origin` 對應既有 entity，而不是只靠名稱判重

- `AC-HWB-07`
  - Given bootstrap copy 已建立在 home workspace
  - When 使用者重新登入
  - Then 系統仍先回 home workspace，而不是 shared workspace

- `AC-HWB-08`
  - Given 使用者切到 shared workspace
  - When 查看同一個來源 product
  - Then shared projection 與 home workspace copy 仍是兩份不同資料，互不共用主鍵

- `AC-HWB-09`
  - Given apply bootstrap 成功
  - When 系統寫入 target entities
  - Then 每個 bootstrap entity 的 `details.bootstrap_origin` 都必須包含 `source_workspace_id`、`source_entity_id`、`source_root_entity_id`、`bootstrap_applied_at`

- `AC-HWB-10`
  - Given apply bootstrap 成功
  - When Products 頁重新整理
  - Then 新匯入的 product copy 立即出現在 target home workspace product list 中

## 8. 資料規則

### 8.1 Entities

P0 複製時：

- 保留 `name / type / summary / tags / status / sources / visibility`
- 重建 `parent_id` 指向新的 target entity IDs
- 在 `details.bootstrap_origin` 寫入 provenance
- 若 target home workspace 已存在對應的 bootstrap copy，P0 只可沿用既有 target entity 並補齊缺少的關係；不得把 source 欄位覆寫回 target

### 8.2 Relationships

只複製 source 與 target 都落在本次複製集合內的 relationships。

不得複製：

- 指向未被複製節點的跨邊界 relationship

### 8.3 Tasks / Plans

P0 不複製 task / plan。正式規則：

- spec 必須定義其策略
- implementation 可先不做

P0 策略為：

- shared workspace 的 task / plan 仍留在 shared workspace
- 若未來需要在 home workspace 初始化執行清單，應由後續 spec 定義 bootstrap template read model，而不是直接鏡像現有 task

## 9. UI 規則

### 9.1 Team / Invite

- bootstrap source 選擇器必須只列出可分享的 `product(L1)`
- owner 在設定 guest scope 時，應能同時設定 bootstrap sources

### 9.2 Products Page

- 只有在 `home workspace` 中才顯示 bootstrap apply 入口
- 只有存在 pending bootstrap source 時才顯示
- apply 完成後，應立即刷新 product list

## 10. 風險與邊界

- 若直接複製 tasks，會把 shared execution history 汙染進客戶 home workspace，P0 明確禁止
- 若直接改預設登入行為，會違反 `SPEC-identity-and-access`，P0 明確禁止
- 若不保留 provenance，之後無法做 idempotent update 與後續 sync，P0 明確禁止

## 11. 相關文件

- `SPEC-identity-and-access`
- `TC-identity-and-access`
- `ADR-018-identity-access-runtime-alignment`
- `ADR-019-active-workspace-federated-sharing`
- `ADR-024-mcp-multi-workspace-context`
