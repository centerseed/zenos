---
type: SPEC
id: SPEC-identity-and-access
status: Under Review
ontology_entity: 身份與權限管理
created: 2026-04-08
updated: 2026-04-10
supersedes:
  - SPEC-permission-model
  - SPEC-partner-access-scope
  - SPEC-workspace-identity-boundary
  - SPEC-prosumer-workspace-permission
  - SPEC-prosumer-onboarding-flow
  - SPEC-client-portal
---

# Feature Spec: Identity, Workspace & Access Management (SSOT)

## 1. 產品定位

ZenOS 採用 `Prosumer-First` 的多 Workspace 協作模型：

1. 每個使用者都是一等公民，第一次註冊即擁有自己的 `home workspace`
2. 每個使用者都可以加入別人的 workspace，但不會失去自己的 workspace 主體性
3. 協作是透過切換 `active workspace` 完成，而不是把他人資料混進自己的空間
4. 目前跨 workspace 共享的範圍，僅限知識地圖對應的 L1-L3、以及依附其上的 task / doc
5. 未來可擴充企業版權限能力，但不得反向污染目前的 prosumer 協作主模型

本 Spec 是 ZenOS 身份、workspace、授權、共享與主導航行為的單一真相來源。

Layering note：

- 本 spec 定義 `ZenOS Core` 的 Identity & Access Layer
- 跨 workspace 共享邊界，以 `ZenOS Core` contract 為準
- application-specific surface 是否共享，必須由各 application spec 額外定義
- external app 若要接入 ZenOS，auth federation contract 以 `SPEC-zenos-auth-federation` 為準

## 1.1 身份來源原則

- ZenOS 可以有自己的第一方登入方式（例如 ZenOS 自有 Firebase Auth）
- 但 ZenOS 不得要求所有 application layer 共用同一個 identity provider
- 上層 app 的 end-user authentication 與 ZenOS 的 workspace authorization 必須分離
- external app 接入 ZenOS 時，必須透過 federation / delegated credential 進入同一套 authorization runtime

## 2. 核心模型

### 2.1 Identity Layer

身份來源不限於單一 identity provider。ZenOS 接受以下身份來源：

| 來源 | 適用場景 | 驗證方式 |
|------|---------|---------|
| ZenOS 自有 Firebase Auth（Email / UID） | Dashboard、第一方產品 | `firebase_admin.auth.verify_id_token()` |
| External App Identity（透過 identity_link） | 上層 app 的 end-user | Federation exchange → delegated credential（見 SPEC-zenos-auth-federation、ADR-029） |
| API Key | MCP agent / CLI | `SqlPartnerKeyValidator` 查 partners 表 |

- 定位：代表真實使用者或外部 app 代理的使用者，不直接承載資料權限
- 規則：
  - 一個 user 可同時加入多個 workspace
  - 外部 app 的 end-user 必須透過 `identity_links` 映射到 ZenOS principal（即 partner），才能操作 ontology
  - 所有身份來源最終都收斂到同一個 partner-based authorization runtime

### 2.2 Workspace Layer

- 實體：Tenant（以 `shared_partner_id` 或 `tenant_id` 為隔離鍵）
- 定位：可被多人加入的協作空間，不是單人私有容器
- 規則：
  - 每個 user 首次註冊時，系統自動建立一個空的 `home workspace`
  - 該 user 成為其 `home workspace` 的 owner
  - user 可加入其他 workspace，但不會失去自己的 `home workspace`
  - 每次登入後，系統一律先進入自己的 `home workspace`

### 2.3 Active Workspace Context

系統所有資料與功能判定，皆以 `active workspace context` 為準。

- 同一個 user 在不同 workspace 內，可擁有不同角色與不同可見範圍
- UI、route guard、API 權限檢查，不得以 user 的全域身份直接裁切功能
- 權限與功能集合，必須由 `active workspace + workspace role + visibility` 共同決定

### 2.4 Workspace Role

使用者在特定 workspace 內，必定屬於以下三種角色之一：

| Role | 定位 | 可見範圍 | 建立權限 | 主導航 |
| :--- | :--- | :--- | :--- | :--- |
| `owner` | workspace 建立者 / 管理者 | 該 workspace 全域 | 可建立 L1 / L2 / L3 / task / doc | home workspace = 全功能；shared workspace = 全功能 |
| `member` | workspace 內部成員 | 該 workspace 全域，受 visibility 限制 | 可建立 L1 / L2 / L3 / task / doc | `Knowledge Map` / `Products` / `Tasks` |
| `guest` | 被分享進來的外部協作者 | 僅限被授權的 L1 子樹，受 visibility 限制 | 可建立 L3 / task；不可建立 L1 / L2 | `Knowledge Map` / `Products` / `Tasks` |

補充規則：

- `member` 保留作為未來企業版的擴充基礎
- 目前在 shared workspace 中，`member` 與 `guest` 的主導航相同；差異先保留在權限與建立能力
- `owner` 在自己的 `home workspace` 具有完整 app surface；未來新增任何 app 模組，預設只屬於自己的 workspace，不自動變成可共享 surface

## 3. Ontology 與分享邊界

### 3.1 L1 主軸

- `L1` 是 workspace 內可被獨立授權與分享的主軸 root
- `product` 是最常見的 L1 類型，但不是唯一類型
- 在 B2B 協作場景下，`company/customer/account` 也可以是 L1；前提是它承擔的是一整棵 ontology subtree 的分享邊界，而不是單純 CRM view model
- 跨 workspace 分享的授權入口，以 `L1 subtree` 為準
- owner 只需要決定「分享哪些 L1 給誰」，不做額外 node whitelist

### 3.2 L2 / L3 模型

- `L2` 是 L1 底下的持久知識節點
- `project` 不是獨立主軸，而是一種 `L3 entity`
- `project(L3)` 用於聚合 task / doc / delivery context
- `task` 不是 L3 entity；task 屬於 `ZenOS Core Action Layer`，但可直接連結到 L1/L2/L3 context，不必先包在 project 下
- `doc` 可直接掛在 L2，或掛在某個 L3 doc entity，不必先掛在 project 下
- `project(L3)` 可同時隸屬多個 L1，但這是例外情境，不可反向改寫 L1 主軸模型

### 3.3 應用層邊界

- 目前只有知識地圖對應的 L1-L3、以及依附其上的 task / doc 可跨 workspace 共享
- CRM、設定、Zentropy 等其他 application modules 目前只存在於自己的 workspace surface，不納入共享面，除非各自 spec 明確定義共享 contract
- 未來若企業版要開放更多模組，必須透過新 spec / ADR 明確擴充，不得默默沿用當前 guest/member 模型

## 4. 可見性與授權規則

### 4.1 Visibility

正規 visibility 僅保留三層：

- `public`
- `restricted`
- `confidential`

規則：

- `owner`：可見全部
- `member`：可見 `public + restricted`
- `guest`：只可見授權 L1 子樹中的 `public`
- `confidential`：僅 owner 可見

補充：

- 這三層是目前的正式模型
- 未來允許擴充至部門、白名單、企業策略，但不得污染當前 SSOT 的基礎語意

### 4.2 Guest 子樹裁切

guest 在 shared workspace 中的資料裁切規則如下：

- 系統先算出該 guest 被授權的 L1 集合
- guest 僅可見這些 L1 底下的授權子樹
- 未授權節點、未授權關聯、未授權 impacts 全部直接隱藏
- 不顯示灰階、鎖頭、占位提示，也不透露未授權範圍存在

### 4.3 多重歸屬節點

若某個 L3 同時掛在多個 L1，且 guest 只被授權其中一個 L1：

- 該 L3 仍可見
- 節點內容可完整顯示
- 但圖譜展開、關聯與 impact 只顯示授權範圍內的部分

### 4.4 建立邊界

guest 的建立邊界：

- 可建立 task
- 可建立 L3
- 不可建立 L1
- 不可建立 L2
- 新建 L3 必須至少掛到一個自己被授權範圍內的 L2
- guest 新建 L3 預設寫回當前 `active workspace`
- 除非未來新增明確同步功能，否則不自動同步回自己的 home workspace
- guest 建立的 L3 預設 visibility 為 `public`

member / owner 的建立邊界：

- `member` 可在當前 workspace 建立 L1 / L2 / L3 / task / doc
- `owner` 可建立並管理全部內容與授權配置

## 5. 導航、切換與路由

### 5.1 Workspace Entry

- 每次登入後，系統一律先回到 user 的 `home workspace`
- 單一 workspace 時，左側顯示 `我的工作區` 入口
- 當 user 加入第二個 workspace 後，該入口升級為 `workspace picker`
- 其他 workspace 若有更新，可在 picker 中顯示 badge

### 5.2 主導航

`Knowledge Map` 是主入口，永遠排第一。

命名規則：

- Web 目前的 `Projects` 文案應改為 `Products`
- `Products` 是從 ontology 中抽出的列表 / 執行視圖，不是獨立於知識圖譜之外的第二套主模型

共享 workspace 的主導航：

- `Knowledge Map`
- `Products`
- `Tasks`

自己的 workspace：

- 顯示完整功能集合
- 未來新增 app 模組時，預設先只屬於自己的 workspace

### 5.3 Route Guard

route guard 必須遵循以下順序：

1. 未登入：導回登入頁
2. 已登入但無 active workspace：導向 workspace bootstrap / chooser
3. 已登入且有 active workspace：依 `active workspace + workspace role + visibility` 決定可否進入頁面

禁止把 `guest` 視為全域低權限帳號。受限的是「在某個 shared workspace 內能做什麼」，不是這個 user 整體只能用什麼功能。

## 6. Onboarding 與邀請流程

### 6.1 Self-Serve Sign Up

- user 主動註冊成功後，系統自動建立一個空的 `home workspace`
- user 成為該 workspace 的 `owner`

### 6.2 Invite & Accept

- owner 可邀請其他 user 加入自己的 workspace
- 被邀請者接受後，原本的 `home workspace` 保持不變
- 系統新增一個新的 workspace membership，而不是搬移或覆蓋既有身份

### 6.3 Multi-Workspace Presence

- user 可在自己的 workspace 與他人分享給自己的 workspace 之間切換
- 切換 workspace 不得改變資料歸屬
- 切換 workspace 後，整個 UI 與資料查詢需立刻以新的 `active workspace context` 重新計算

## 7. 權限撤銷與一致性

- 當 owner 將 guest 移出 workspace，或拔除其某個 L1 授權時，系統必須自動移除該 guest 在失效範圍內的 task assignee 關聯
- guest 失去授權後，既有留言 / 歷史紀錄保留，但該 guest 不得再讀取失效範圍內容
- 權限過濾必須由 server 端強制執行；前端與 agent 只可消費過濾後結果，不可自行推斷授權
