---
type: ADR
doc_id: ADR-018-identity-access-runtime-alignment
title: 架構決策：Identity、Active Workspace 與 Federated Sharing 執行模型
ontology_entity: 身份與權限管理
status: approved
version: "2.0"
date: 2026-04-08
supersedes:
  - ADR-009-permission-model
  - ADR-019-active-workspace-federated-sharing
---

# ADR-018: Identity、Active Workspace 與 Federated Sharing 執行模型

## Context

ZenOS 已確認採用 `Prosumer-First` 的多 workspace 協作模型，但先前文件與 runtime 曾把兩種不同產品模型混在一起：

1. `Federated workspace sharing`
   - 每個 user 都是完整使用者
   - 每個 user 都有自己的 workspace
   - user 可以加入別人的 workspace
   - 受限的是「在別人的 workspace 內能做什麼」

2. `Client portal guest`
   - guest 沒有完整產品主體性
   - guest 只剩 Projects / Tasks 視角
   - ontology / setup / CRM / settings 被當成「內部人才有」

舊版 `ADR-018` 雖然已開始從 company-centric permission 語言轉向 workspace sharing，但仍留下四個結構性錯位：

1. 把 `guest` 過度實作成全域低權限帳號，而不是「shared workspace 中的受限角色」
2. 把 `Projects / Tasks only` 的 portal surface 混入主要產品模型
3. 未明確定義 `active workspace context`，導致 UI 容易依 user 全域角色裁切
4. 未收斂 `product / project / ontology` 三者關係，讓共享邊界與導航語意漂移

產品確認後，ZenOS 的正確模型是：

- 每個 user 註冊後自動擁有自己的 `home workspace`
- 每個 user 都可以加入其他 workspace，但不會失去自己的 workspace 主體性
- 每次登入後先回 `home workspace`
- 系統所有資料與功能判定，皆以 `active workspace context` 為準
- 跨 workspace 共享目前只涵蓋知識地圖對應的 L1-L3 與其 task / doc
- `product(L1)` 是分享與導航主軸
- `project` 不是獨立主軸，而是一種 L3 entity
- shared workspace 中，`guest` 與 `member` 目前都以 `Knowledge Map / Products / Tasks` 為主要 surface

若不把這些點一次寫進正式架構決策，系統會持續出現：

- 同一個人既是某 workspace 的 owner，又在另一個 workspace 被當成 portal guest
- nav、route guard、server filter 各自使用不同語言
- `Projects` 與 `Products` 語意打架
- ontology 共享邊界與 application layer 邊界混淆

## Decision

### 1. `active workspace context` 成為正式執行單位

從 ADR-018 v2 起，所有 UI、route guard、API、agent 權限判斷，一律以 `active workspace context` 為正式執行單位。

規則：

- 每個 user 第一次註冊時，自動建立一個空的 `home workspace`
- 該 user 成為其 `home workspace` 的 `owner`
- user 可加入其他 workspace，但不會失去 `home workspace`
- 每次登入後，系統一律先進入 `home workspace`
- 切換 workspace 時，整個前端 surface 與後端權限都必須重新計算
- 受限的是「在某個 workspace 內能做什麼」，不是這個 user 全域只能用什麼功能

### 2. Workspace Role 只描述空間內角色，不描述 user 全域階級

正式角色仍維持：

- `owner`
- `member`
- `guest`

語意改為：

- `owner`：該 workspace 的建立者 / 管理者
- `member`：該 workspace 的內部協作者
- `guest`：被分享進來、只在該 workspace 內受限的外部協作者

`accessMode` 只保留為資料相容層：

- `isAdmin = true` → `owner`
- `accessMode = internal` → `member`
- `accessMode = scoped` → `guest`
- `accessMode = unassigned` → 尚未進入任何有效協作空間

禁止再把 `guest` 視為全域低權限帳號。

### 3. 共享模型正式採 `federated sharing`，不再保留 portal 主模型

ZenOS 主產品不再以 `client portal` 作為主要身份模型。

正式產品語意為：

- user 是完整使用者
- workspace 是協作容器
- 分享是以 `product(L1)` 為入口，把 ontology 子樹共享給他人
- shared workspace 的 `guest` 仍可使用 `Knowledge Map`
- shared workspace 的 `member` / `guest` 主導航目前固定為 `Knowledge Map / Products / Tasks`

任何 portal 式 guest surface 只能視為未來可能的獨立模式，不得再當成 ZenOS 主模型的預設解釋。

### 4. `product` 成為共享與導航主軸，`project` 收斂為 L3 entity

ZenOS 的 ontology 主軸正式收斂為：

- `product` = L1 主軸，也是分享授權入口
- `L2` = product 底下的持久知識節點
- `project` = L3 entity，用來聚合 task / doc / delivery context
- `task` = L3 entity
- `doc` = 可直接掛在 L2，或掛在某個 L3 doc entity

補充規則：

- `project` 不再視為主導航概念
- `project` 可以多重隸屬多個 L1，但這是例外情境，不得反向改寫 L1 主軸模型
- Web 現有 `Projects` 主導航與文案，應收斂為 `Products`

### 5. 共享邊界只涵蓋 ontology 與其依附資源

當前可共享範圍：

- L1 / L2 / L3 ontology
- task
- doc

當前不共享範圍：

- CRM
- team / setup / company-oriented app modules
- 其他 application layer

這些模組仍只屬於使用者自己的 workspace。未來若企業版要開放更多模組，必須透過新 spec / ADR 擴充，不得默默沿用當前 guest/member 模型。

### 6. Guest 看到的是授權 ontology 子樹，不是「只有 Projects / Tasks」

Guest 的正規規則一律固定為：

- 只能在當前 workspace 內看見 `authorized_entity_ids` 對應的 `product(L1)` 子樹
- 可進入 shared workspace 的 `Knowledge Map`
- 只可看見授權子樹中的 `public` entity / document / task
- 不可看 `restricted`
- 不可看 `confidential`
- 不可看 blindspot
- 不可看未授權節點、未授權 impacts、未授權關聯
- 不顯示灰階、鎖頭、占位提示，也不透露未授權範圍存在

若某個 L3 同時掛在多個 L1，且 guest 只被授權其中一個 L1：

- 該 L3 仍可見
- 節點內容可完整顯示
- 圖譜展開、關聯與 impacts 只顯示授權範圍內的部分

### 7. 建立邊界以角色與授權子樹共同決定

`owner`：

- 可建立 L1 / L2 / L3 / task / doc
- 可管理 workspace 成員、授權與完整 app surface

`member`：

- 可看整個 active workspace
- 受 visibility 限制
- 可建立 L1 / L2 / L3 / task / doc

`guest`：

- 可建立 task
- 可建立 L3
- 不可建立 L1 / L2
- 新建 L3 必須至少掛到一個自己被授權範圍內的 L2
- guest 新建 L3 預設寫回當前 `active workspace`
- 除非未來新增明確同步功能，否則不自動同步回自己的 `home workspace`
- guest 建立的 L3 預設 visibility 為 `public`

### 8. Visibility 正式收斂為三層，但保留企業擴充能力

正規 visibility 僅允許：

- `public`
- `restricted`
- `confidential`

權限規則：

- `owner` 可見全部
- `member` 可見 `public + restricted`
- `guest` 只可見授權 L1 子樹中的 `public`
- `confidential` 僅 `owner`

Legacy `role-restricted` 一律只作 migration 相容，不再是可寫值，也不得再出現在任何新的 UI selector、型別定義或寫入路徑。

未來允許擴充至部門、白名單、企業 policy，但那是新一層企業能力，不得污染當前 Prosumer-First 的基礎語意。

### 9. 導航與 workspace entry 收斂到同一套心智模型

Dashboard 主路徑正式收斂為：

- 單一 workspace：左側顯示 `我的工作區`
- 多 workspace：`我的工作區` 升級為 `workspace picker`
- `Knowledge Map` 永遠排第一
- `Products`
- `Tasks`

補充規則：

- shared workspace 中，`member` / `guest` 目前都只顯示 `Knowledge Map / Products / Tasks`
- `member` 比 `guest` 的差異先保留在權限與建立能力，不急著展現在主導航
- 自己的 `home workspace` 顯示完整功能集合
- 其他 workspace 若有更新，可在 picker 中顯示 badge

### 10. Route Guard 與 server filter 一律以同一套規則執行

route guard 必須遵循以下順序：

1. 未登入：導回登入頁
2. 已登入但無 active workspace：導向 workspace bootstrap / chooser
3. 已登入且有 active workspace：依 `active workspace + workspaceRole + visibility` 決定可否進入頁面

Server 端必須強制執行同一套資料裁切；前端與 agent 只能消費過濾後結果，不可自行推斷授權。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| 保留 `internal/scoped` 為主，僅文件上改名 | 改動最少 | runtime、UI、Spec 持續三套語言並存；`home workspace / shared workspace` 無法形成單一語意 | 不能形成穩定產品模型 |
| 繼續使用 company/department 權限，只在 guest 上加例外 | 可沿用既有 Team UI 與企業心智 | 權限中心仍是公司組織，不是 workspace sharing；Prosumer 自建 ontology 的邊界仍混亂 | 與主產品願景衝突 |
| 為 guest 維持獨立 portal，內部用戶走另一套路徑 | 短期可隔離 UI 風險 | 兩套 frontend / permission surface 長期分叉，維護成本高，語意不一致 | 會讓同一產品出現雙軌架構 |

## Consequences

- 正面：
  - `home workspace` 與 `shared workspace` 的心智模型清楚一致
  - `guest` 不再被錯誤視為全域低權限帳號
  - `product` 成為分享與導航主軸，`project` 回到 L3 execution entity
  - nav、route guard、server filter、ontology 邊界終於使用同一套語言
- 負面：
  - 既有前端與測試中大量 `accessMode/internal/scoped/team/department` 心智模型需要更新
  - `Projects` 改名 `Products` 會影響前端文案、測試與既有假設
  - 既有 portal 式 guest surface 需要回退
  - `project` 多重隸屬多個 L1 的例外情境，後續仍需補更細授權規則
- 後續處理：
  - 套用 visibility migration：`role-restricted -> restricted`
  - 清除前端 visibility editor / type surface 中仍可寫入 `role-restricted` 的殘留相容入口
  - 補前端 workspace entry、workspace picker、`Products` rename、shared subtree 的完整驗收
  - 維持 QA 場景覆蓋：home workspace、shared workspace、guest subtree、member full workspace、Products rename
  - 後續若需要企業版部門 / 白名單 / CRM 共享，必須另開 spec / ADR

## Implementation

1. 後端 runtime 全面以 `active workspace context` 與 `workspaceRole` 為正規權限輸出，`accessMode` 退為相容欄位
2. 實作 visibility migration：`role-restricted -> restricted`
3. 以 `product(L1)` 作為共享授權入口與 server 查詢裁切基準
4. 嚴格禁止 guest 建立 L1 / L2，只允許建立 task 與掛在授權 L2 下的 L3
5. Dashboard navigation 與 route guard 改為 active-workspace-based：shared workspace 的 `member` / `guest` 皆顯示 `Knowledge Map / Products / Tasks`
6. Web `Projects` 文案與主語意收斂為 `Products`
7. 單一 workspace 時顯示 `我的工作區`；多 workspace 時升級為 `workspace picker`
8. 將 CRM / Team / Setup / Company-oriented 主流程 UI 從 shared workspace surface 中移除
9. 補 Workspace Switcher 與共享子樹驗證：`hhh1230` 可看 Barry 分享的 product，但回自己 workspace 時仍保有完整產品 surface
10. 以 permission regression suite、TC PASS 與 server-side filter 驗證作為 ADR-018 v2 落地完成 gate
