---
type: SPEC
id: SPEC-client-portal
status: Draft
ontology_entity: dashboard
created: 2026-04-03
updated: 2026-04-23
depends_on: SPEC-identity-and-access, SPEC-zenos-auth-federation
---

# Feature Spec: 客戶協作入口（Client Portal）

## 背景與動機

ZenOS 目前是純內部工具——文件、任務、知識圖譜只有持有 GitHub 帳號的團隊成員可見。當 ZenOS 團隊為客戶做落地實施時，需要一個方式讓客戶能即時看到進度、文件、任務狀態，並且能夠參與討論與規劃。

目前做法（Email / Google Drive / Notion）有以下問題：
- 資訊散落多處，沒有單一真相來源
- 客戶無法看到與他們相關的任務與決策的完整脈絡
- ZenOS 本身的語意結構（ontology）無法被客戶感知與使用

**策略意義**：用 ZenOS 做客戶落地，客戶就是 ZenOS 的第一批 Power User。用得好的客戶，自然想自己導入——Client Portal 同時是落地工具也是銷售展示場。

---

## 目標用戶

| 角色 | 描述 |
|------|------|
| ZenOS Admin | 邀請客戶、設定 L1 scope、管理成員 |
| ZenOS 內部成員 | 看全部資料，與客戶協作 |
| 客戶（Scoped Partner）| 被邀請進入特定 L1 空間，可查看、討論、建任務 |
| 未指派 partner | 已完成登入但尚未被分享任何 L1，只看到等待指派畫面 |

---

## 核心概念

每個 **L1 Entity** 就是一個隔離的協作空間。

- 客戶只能看到自己被授權的 L1 空間內的內容（nodes、文件、tasks）
- 客戶無法感知其他 L1 空間的存在
- ZenOS 內部成員可跨所有 L1 操作
- 隔離機制定義於 `SPEC-partner-access-scope` 與 `SPEC-permission-model`

---

## 需求

### P0（必須有）

#### 1. 客戶邀請流程

- **描述**：Admin 以 Email 邀請外部用戶加入特定 L1 空間，對方透過 Google OAuth 完成身份驗證後進入。
- **Acceptance Criteria**：
  - Given Admin 在 Dashboard 選擇一個 L1，輸入外部用戶 Email 並送出邀請，Then 系統建立 partner record（status=invited，`authorized_entity_ids` 設為該 L1 ID），且對方收到含邀請連結的 Email
  - Given 邀請連結有效期為 7 天，When 外部用戶在 7 天內點擊並完成 Google OAuth 登入，Then partner status 更新為 active，用戶被導入對應 L1 的 Dashboard 視角
  - Given 邀請連結已過期（超過 7 天），When 外部用戶點擊，Then 顯示「邀請已過期，請聯繫管理員重新發送」
  - Given 同一個 Email 被重複邀請，When Admin 再次送出，Then 系統重新發送邀請 Email 並重置 7 天有效期，不建立重複 partner record
  - Given Email 發送失敗，Then 系統在 Admin 的邀請列表上標記「發送失敗」，並提供重新發送按鈕
  - Given Admin 查看某 L1 的成員列表，Then 可以看到 active / invited / 發送失敗 三種狀態

#### 2. L1 隔離的 Dashboard 視角

- **描述**：客戶登入後看到同一個 Dashboard，但頁籤與資料根據其 `authorized_entity_ids` 自動過濾。
- **客戶可見頁籤**：Tasks、Products（限自己的 L1）
- **客戶不可見頁籤**：Team、Setup、Clients（CRM）、任何跨 L1 的管理功能
- **Acceptance Criteria**：
  - Given 客戶登入，Then 導覽列只顯示 Tasks 與 Products 頁籤，不出現 Team / Setup / CRM
  - Given 客戶在 Tasks 頁，Then 只看到自己 L1 下的 tasks
  - Given 客戶在 Products 頁，Then 只看到自己 L1 下的 nodes（visibility = public）
  - Given 客戶嘗試直接存取 `/team` 或 `/setup` URL，Then 重導回首頁（不顯示 403 或其他 L1 資訊）
  - Given 客戶的 `authorized_entity_ids` 為空（尚未指派 L1），Then 登入後顯示「您的帳號尚未設定存取空間，請聯繫管理員」，不顯示空白畫面
  - Given 客戶的 `authorized_entity_ids` 為空，When 直接呼叫 API 或刷新頁面，Then 仍回到等待指派畫面，不看到任何 tenant 資料

#### 3. 客戶可查看文件與任務

- **描述**：客戶在自己的 L1 空間內可瀏覽文件（visibility = public）與所有 tasks。
- **Acceptance Criteria**：
  - Given 客戶查看文件列表，Then 只看到該 L1 下 visibility = public 的文件，含標題、類型、狀態
  - Given 客戶點開一份文件，Then 可完整閱讀內容
  - Given Admin 將文件改為 restricted，Then 該文件從客戶的文件列表消失
  - Given 客戶查看任務看板，Then 看到該 L1 下所有 tasks，含標題、狀態、負責人、截止日
  - Given 任務的負責人欄位，Then 顯示姓名，不顯示內部 email 或 partner ID

### P1（應該有）

#### 4. 客戶可在任務上留言

- **描述**：客戶可以在任務上留言，與 ZenOS 團隊進行討論。留言不納入 ontology 治理。
- **Acceptance Criteria**：
  - Given 客戶點開一個 task，When 他送出留言，Then 留言顯示在該 task 下，且該 task 的 owner 收到 Email 通知
  - Given 內部成員回覆留言，When 客戶再次進入，Then 看到完整討論串（含內部成員的回覆）
  - Given 客戶離開該 L1（`authorized_entity_ids` 被移除），Then 其留言仍保留（不自動刪除），但客戶無法再讀取

#### 5. 客戶可建立任務

- **描述**：客戶可以在自己的 L1 空間內建立 task，用於提出需求、回報問題。
- **Acceptance Criteria**：
  - Given 客戶在 Tasks 頁，When 他建立任務（填入標題與描述），Then 任務出現在該 L1 的任務看板，且對內部成員可見
  - Given 客戶建立的任務，Then 自動掛載在其 `authorized_entity_ids` 中的 L1 下
  - Given 客戶建立的任務，Then visibility 預設為 `public`（客戶自己也能持續看到）
  - Given 客戶被授權多個 L1（P1），When 建立任務，Then 需選擇要掛載在哪個 L1

### P2（可以有）

#### 6. 客戶可上傳附件

- **描述**：客戶可以在 task 上傳附件，作為協作輸入。
- **Acceptance Criteria**：
  - Given 客戶在一個 task 頁面，When 他上傳附件，Then 附件可被內部成員下載查看
  - Given 附件，Then 只在對應 L1 可見，不跨 L1

#### 7. 客戶自助管理通知偏好

- **描述**：客戶可以設定想收到哪些 Email 通知。
- **Acceptance Criteria**：
  - Given 客戶在個人設定，When 他關閉特定通知類型，Then 該類型通知不再發送給他

---

## 明確不包含

- 客戶邀請自己公司的其他人（這等同於幫客戶導入 ZenOS，屬於另一個商業決策）
- 客戶修改或刪除受治理文件內容（可留言，不可直接編輯）
- 客戶跨 L1 協作或查看
- 客戶在文件上留言（僅支援 task 留言）
- 客戶變更 task 的 visibility

---

## 依賴

- **SPEC-partner-access-scope**：新 partner 預設空白、L1 分享、未指派狀態
- **SPEC-permission-model**：L1 隔離、visibility 規則、`authorized_entity_ids` 語意

---

## 技術約束（給 Architect 參考）

- **身份驗證**：客戶使用 Google OAuth，沿用現有 Firebase Auth 流程；`partners.email` 必須與 Google 帳號 email 完全匹配
- **整合現有 Dashboard**：不另立獨立入口，scoped partner 登入後的頁面分流在同一套 codebase 中處理
- **多 L1 支援**：單一 L1 為 MVP，多 L1 為 P1（`authorized_entity_ids` 已是 `text[]`，擴展不需改 schema）
- **留言儲存**：留言需新 table 或 task 欄位，Email 通知需新基礎設施（現有無 Email 發送能力）
- **L1 被刪除**：scoped partner 的 `authorized_entity_ids` 不自動清除，由 admin 手動處理；系統查詢回傳空結果，不報錯

---

## 開放問題

1. **Email 通知服務選型**：P1 留言通知需要 Email 發送能力，待 Architect 評估（SendGrid / Firebase Extensions / 其他）
