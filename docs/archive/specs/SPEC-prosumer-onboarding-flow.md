---
type: SPEC
id: SPEC-prosumer-onboarding-flow
status: Draft
ontology_entity: 夥伴身份與邀請
created: 2026-04-08
updated: 2026-04-08
supersedes: []
---

# Feature Spec: Prosumer Onboarding & Invitation Flow

## 背景與動機

在確立了 `SPEC-prosumer-workspace-permission` (多重 Workspace、Owner/Member/Guest 三層角色) 之後，我們需要定義「使用者如何進入 ZenOS」的具體流程。

現有的流程是基於「單一 Tenant」假設的 Magic Link 邀請。我們必須重新設計一條能支援 B2C (自主註冊) 與 B2B (受邀加入) 的平滑入職路徑。

---

## 目標用戶與場景

1. **自主探索者 (Prosumer)**：沒有被任何人邀請，直接來到 ZenOS 首頁點擊「Sign Up」。
2. **被邀請的協作者 (Guest / Member)**：收到一封來自 ZenOS 某個 Workspace Owner 的邀請信。

---

## 核心流程需求

### P0 (必須有)

#### 1. 自主註冊流程 (Self-Serve Sign Up)
- **描述**：使用者主動來到系統進行註冊，系統必須自動為其分配專屬空間。
- **Acceptance Criteria**:
  - Given 使用者在首頁點擊「Sign Up with Google」，When 授權成功且系統確認該 Email 不存在於任何 Workspace，Then 系統自動建立一個新的 Tenant (Workspace)。
  - Given 新 Workspace 建立完成，When 初始化完成，Then 該使用者被設為該 Workspace 的 `Owner`，並導向一個空的 Dashboard (首頁顯示：「歡迎來到您的個人空間」)。

#### 2. Magic Link 邀請與接受流程 (Invite & Accept)
- **描述**：Owner 可以透過 Email 邀請外部人員。被邀請者點擊信件連結後，必須明確選擇登入方式 (SSO/密碼)，並綁定到正確的 Workspace。
- **Acceptance Criteria**:
  - Given Owner 在 Workspace A 輸入 `test@example.com` 送出邀請，When 送出後，Then `test@example.com` 收到一封帶有專屬 Magic Link 的邀請信。
  - Given 使用者點擊 Magic Link 進入註冊/登入頁面，When 選擇「Continue with Google」並完成驗證，Then 系統將該 Auth UID 綁定至 Workspace A 的該筆邀請紀錄，並將其狀態從 `invited` 改為 `active`。
  - Given 使用者綁定完成，When 跳轉至 Dashboard，Then 系統自動載入 Workspace A 的上下文，並套用他在該空間的 Role (Member 或 Guest)。

#### 3. 多重身份衝突處理 (Multi-Workspace Conflict)
- **描述**：如果一個已經擁有自己 Workspace 的 Prosumer，收到別人的邀請信。
- **Acceptance Criteria**:
  - Given User X 已經是 Workspace X 的 Owner，When 他點擊 Workspace Y 的邀請信連結並登入，Then 系統將他的 Email 加入 Workspace Y 的 Member Profile。
  - Given 接受邀請成功，When 跳轉至 Dashboard，Then 畫面會提示「您已加入 Workspace Y」，並且可以在側邊欄 Switcher 自由切換 Workspace X 與 Y。

### P1 (應該有)

#### 4. Magic Link 登入流程強化 (SSO 綁定)
- *(繼承自稍早擱置的 ADR-015 / auth-enhancement-plan)*
- **描述**：如果用戶是透過「純 Email Magic Link (無 Google SSO)」點擊進來的，為了避免跨裝置登入的斷層，系統應在第一次成功登入後，攔截跳轉，引導其綁定 Google SSO 或設定密碼。
- **Acceptance Criteria**:
  - Given 使用者第一次點擊純 Email Magic Link 登入成功，When 準備跳轉首頁前，Then 顯示「帳號設定 (Account Setup)」過渡頁面。
  - Given 過渡頁面顯示，When 用戶點擊「關聯 Google 帳號」並完成授權，Then 該 Firebase Auth 帳號成功與 Google Provider 綁定，隨後進入 Dashboard。

---

## 開放問題 (交給 Architect 解決)

1. **邀請碼的安全性**：Magic Link 裡帶的 Token 是 Firebase 內建的 `signInWithEmailLink`，還是我們自己產生的 `invite_token`？如果是 Firebase 的，如何確保它準確對應到我們資料庫裡的特定 Workspace？
2. **預設 Workspace 選擇**：當一個擁有 3 個 Workspace 的使用者直接從書籤 (Bookmark) 進入 ZenOS 首頁，系統應該預設載入哪一個 Workspace？(建議：記錄上次登出前所在的 Workspace ID 於 LocalStorage，若無則預設選第一個)。