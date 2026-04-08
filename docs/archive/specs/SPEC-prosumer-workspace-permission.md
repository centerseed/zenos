---
type: SPEC
id: SPEC-prosumer-workspace-permission
status: Draft
ontology_entity: 夥伴身份與邀請
created: 2026-04-08
updated: 2026-04-08
supersedes: 
  - SPEC-permission-model
  - SPEC-partner-access-scope
  - SPEC-workspace-identity-boundary
---

# Feature Spec: Prosumer-First Workspace & Permission Model

## 產品願景與定位轉向

ZenOS 的核心定位從傳統的「企業由上而下發起 (Enterprise-First)」正式轉向為「**個體戶/專業人士由下而上發起 (Prosumer-First)**」。

在這個願景下：
1. **每個使用者 (User) 都是一等公民**：無論是自己註冊或是被邀請，每個使用者都可以擁有自己的專屬工作空間 (Workspace)。
2. **資料隔離與協作 (Federated Sharing)**：個體戶之間透過「切換 Workspace」來參與別人的專案 (L1 Scope)，而不是把別人的資料拉進自己的空間裡混淆。
3. **保留未來的 B2B 彈性**：當中小企業想要導入時，只需將某些外部個體戶 (Guest) 升級為內部成員 (Member)，現有的 Codebase 即可無縫支援傳統企業的權限架構。

本 Spec 統整並取代了過去所有零碎的權限文件，成為 ZenOS 身份與權限治理的 **Single Source of Truth (SSOT)**。

---

## 核心架構 (The 3 Layers)

### 1. 身份層 (Identity Layer)
*   **實體**：Firebase Auth User (Email, UID)。
*   **特性**：代表一個「會呼吸的真人」。身份本身不帶有任何資料權限，僅用於登入認證。一個 User 可以加入無限個 Workspaces。

### 2. 工作空間層 (Workspace Layer)
*   **實體**：Tenant (以 `shared_partner_id` 或 `tenant_id` 為隔離鍵)。
*   **特性**：資料庫層級的絕對物理/邏輯隔離。不同 Workspace 之間的資料完全不互通。
*   **UX 表現**：使用者登入後，若擁有多個 Workspace，必須透過左側邊欄的 **Workspace Switcher (工作空間切換器)** 進行明確切換。這解決了「資料與應用聚合」帶來的維度爆炸問題。

### 3. 空間內身份 (Workspace Role / Member Profile)
使用者在特定的 Workspace 內，必定屬於以下三種角色之一（對應資料庫的 `access_mode` 與 `is_admin`）：

| 角色 (Role) | 適用對象 | 權限範圍 (Scope) | 應用模組 (Apps) | Entity 建立權限 |
| :--- | :--- | :--- | :--- | :--- |
| **Owner** | 空間建立者/管理員 | 擁有該空間的絕對控制權，無死角。可以管理成員與帳單。 | ✅ 可使用 | ✅ 任意建立 |
| **Member** | 企業內部員工 | 跨 L1 協作（不受限於單一 L1），但受限於 Entity 的 `visibility` 級別。 | ✅ 可使用 | ✅ 任意建立 |
| **Guest** | 外部個體戶/客戶 | **僅限被明確授權的 L1 子樹**（儲存於 `authorized_entity_ids`）。 | ❌ 禁用 | ⚠️ 僅限建立 Task，不可建 Knowledge |

---

## 權限控制細則

### 1. Entity 可見性 (Visibility) 的極簡化
為了適應 Prosumer 模式，拔除過去過度複雜的 `role-restricted`，只保留三個最直覺的級別：
*   **`public` (公開)**：Owner、Member 以及被授權該 L1 的 Guest 皆可見。
*   **`restricted` (內部)**：僅 Owner 與 Member 可見（Guest 永遠看不到，即使該 Entity 在他被授權的 L1 內）。
*   **`confidential` (機密)**：僅 Owner 可見。

*(註：Guest 永遠看不到 Blindspots 類型的資料。)*

### 2. 寫入與建立邊界 (Write Boundaries)
保護 Ontology (知識圖譜) 的結構不被外部人員破壞是最高指導原則。
*   **Guest 的寫入限制**：
    *   可以**讀取**授權 L1 內的 public 資料。
    *   可以**留言/回覆**指派給自己的 Tasks。
    *   可以**建立**新的 Tasks (強制掛載在自己被授權的 L1 下)。
    *   **絕對禁止**建立 L1 (Product/Project) 或 L2 (Module/Domain) 的 Ontology Entities。
*   如果 Guest 認為需要新增知識節點，他們必須透過建立 Task 提出建議，由 Owner/Member (或 Agent) 審核後建立。

### 3. 應用層的絕對隔離 (Application Boundary)
*   所有建構在核心資料 (Knowledge + Task) 之上的複雜業務模組（例如：CRM、財務報表、HR 模組），**永遠不對 Guest 開放**。
*   這保證了未來開發新模組時，不需要去處理外部協作的複雜權限矩陣。

### 4. Agent 的權限繼承 (Agent-Aware Governance)
*   ZenOS 是一個 AI 驅動的系統。所有的 Agent (包含 MCP Server 執行的工具) 在進行任何資料讀寫時，**必須強制繼承並降級為當前觸發對話的 User 的 Role 權限**。
*   例如：Guest 呼叫 Agent 查詢資料時，Agent 傳遞給 Server 的 ContextVar 必須帶有該 Guest 的 `authorized_entity_ids` 與 `access_mode='scoped'`。Server 端會直接過濾掉不屬於他的資料，防止 Agent 產生幻覺或發生越權洩漏 (Data Exfiltration)。

---

## 狀態轉換與 B2C 增長流程 (PLG)

1. **新戶註冊 (Pure SSO)**：
    *   自動為其建立一個專屬的 Workspace。
    *   User 成為該 Workspace 的 Owner。
2. **被邀請者 (Invited via Magic Link)**：
    *   User 點擊邀請連結並完成 SSO 後，自動加入邀請者的 Workspace 成為 Guest 或 Member。
    *   **PLG 鉤子**：在 Workspace Switcher 的底部，永遠保留一個「➕ 建立我的個人空間」的按鈕，讓 Guest 能隨時無縫轉換為擁有自己空間的 Prosumer Owner。
3. **權限撤銷 (Revoke)**：
    *   當 Owner 將某個 Guest 移出空間，或拔除其 L1 授權時，系統必須**自動將該 Guest 從該範圍內的所有 Task Assignee 中移除**，確保資料與責任的一致性。

---

## 結論

此架構（Workspace Switcher + Owner/Member/Guest + 拔除應用層外部存取）完美契合了「To C 為主、B2B 為輔」的產品戰略。它把權限複雜度降到最低，同時確保了資料的絕對安全與未來向企業級擴充的彈性。這也是未來所有開發與架構設計的唯一依歸。
