---
type: SPEC
id: SPEC-workspace-identity-boundary
status: Draft
ontology_entity: 夥伴身份與邀請
created: 2026-04-08
updated: 2026-04-08
---

# Feature Spec: Workspace, Identity & Application Boundary

## 背景與動機

ZenOS 具備 B2B 與 B2C 混合的使用情境（例如：外部顧問被邀請進入客戶 A 的 ZenOS 協作，隨後也想用 ZenOS 管理自己的團隊）。

在初期的架構中，身份 (Identity/Email) 與租戶空間 (Workspace/Tenant) 緊密綁定，導致：
1. **身份被綁架**：用戶無法用同一個 Email 加入多個公司的 ZenOS，也無法在被邀請後建立自己的 Workspace。
2. **應用層權限爆炸**：隨著 ZenOS 長出 CRM、會計等複雜應用模組 (Application Layer)，如果允許外部人員 (Scoped Partner) 存取這些模組，權限矩陣與 UI 邏輯將會呈指數級膨脹（例如：用戶 A 的 CRM 混雜了自己公司的客戶與客戶 A 分享的客戶）。

本 Spec 旨在解決這兩個深層的架構與產品邊界問題。

---

## 核心原則與產品紅線

### 1. 身份與工作空間解耦 (Decoupling Identity and Workspace)
- **Identity (Auth User)**：基於 Firebase Auth (Email/UID) 的真人身份。
- **Workspace (Tenant)**：基於 `shared_partner_id` (或未來的 Tenant ID) 的資料隔離區。
- **Member Profile (Partner)**：User 在某個 Workspace 內的實體與權限設定。
- **原則**：一個 User (Email) 可以對應多個 Workspace 的 Member Profile。用戶登入後，必須先選擇或處於一個明確的 Workspace Context 下。

### 2. 外部協作的絕對邊界：止步於資料層 (Knowledge + Task)
這是一條不可逾越的產品紅線，用以切斷權限設定的複雜度。
- **資料層 (Data Layer)**：包含 Ontology Entities (L1/L2/L3)、Documents、Tasks。這是 ZenOS 跨組織協作的核心。
- **應用層 (Application Layer)**：包含建立在資料層之上的複雜業務模組（如 CRM、HR、會計、自訂表單等）。
- **原則**：**所有的應用層模組 (Application Modules) 永遠不對外部人員 (Scoped Partner) 開放。** 外部人員即使被分享了某個 L1，他們也只能透過基礎的 Knowledge 視圖與 Task 視圖進行協作。應用層的 UI 與邏輯僅限 Internal Members 使用。

---

## 需求定義

### P0: 架構與邊界確立

#### 1. 多重 Workspace 支援架構
- **描述**：解除 `partners` 資料表對 `email` 欄位的 Global Unique 限制（如果有的話，改為 `(tenant_id, email)` unique）。允許同一個 Auth User 擁有多個 `partner` 紀錄（分別對應不同的 `shared_partner_id`）。
- **Acceptance Criteria**:
  - Given 一個已存在的 User (Email: a@test.com)，When 另一個 Tenant 的 Admin 邀請該 Email，Then 系統能成功建立新的 Partner 紀錄，不發生 Unique Constraint 錯誤。
  - Given User 登入系統，When 他擁有多個 Workspace 的權限，Then 系統提供一個明確的 UI (Workspace Switcher) 供其切換上下文。

#### 2. Application Layer 的存取阻斷
- **描述**：所有被定義為「應用層」的功能模組（如 CRM 頁面、CRM 相關的 API 端點），必須在 Server 端強制檢查使用者的 `access_mode`。
- **Acceptance Criteria**:
  - Given 使用者 `access_mode = 'scoped'` (外部合作者)，When 他嘗試存取 CRM API 或導航至 CRM 頁面，Then 系統回傳 403 Forbidden 或在 UI 上隱藏該入口。
  - Given 應用模組依賴某些 Ontology Entities，When 外部人員存取這些 Entities 的基礎視圖時，Then 他們只能看到標準的 Entity 內容，看不到應用模組附加的特殊業務視圖。

### P1: B2C 轉化流程 (PLG)

#### 3. 從 Scoped Partner 到 Own Workspace 的平滑過渡
- **描述**：當外部人員 (Scoped Partner) 覺得 ZenOS 很好用，想要建立自己的團隊空間時，系統必須提供流暢的升級路徑。
- **Acceptance Criteria**:
  - Given User 目前身處被邀請的 Workspace，When 他點擊「建立我的組織/空間」，Then 系統為其配置一個全新的 Tenant，並將其設為該 Tenant 的 Admin (Internal Member)。
  - Given User 建立了自己的 Workspace，When 下次登入時，Then 他可以在自己的 Workspace 與被邀請的 Workspace 之間自由切換。

---

## 結論與後續行動

透過將「外部協作嚴格限制在資料層（Knowledge + Task）」，我們成功避免了把 ZenOS 變成一個極度複雜、難以維護的「全自訂企業 ERP」的命運。這保證了核心產品（AI 知識庫與任務驅動）的純粹性，同時也為未來的多工作空間（PLG 增長）打下了堅實的地基。