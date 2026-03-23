# 用戶邀請與權限管理 MVP

## 問題陳述

ZenOS 目前只有 Barry 一個人在用。要讓其他人（夥伴、員工）加入同一個 ZenOS instance，
目前只能手動改 Firestore——沒有邀請流程、沒有權限管理 UI。
此外，不同用戶的 AI agent 共用同一個資料空間但無法區分身份，導致 agent 看到不屬於自己的任務而搞亂。

## 目標

1. Admin 在 Dashboard 輸入 email → 對方收到邀請信 → Google SSO 登入 → 看到同一個 ZenOS
2. Admin 可以管理用戶（提升為 admin / 停用帳號）
3. 每個用戶的 AI agent 有獨立身份，MCP 請求能辨識「這是誰的 agent」

## 非目標

- 細粒度資料權限（entity-level visibility）— 不在這次範圍
- 用戶自助註冊（必須由 admin 邀請）
- 自訂角色（只有 admin / member 兩種）
- Agent 資料隔離（agent 仍看得到所有資料，但能辨識身份、過濾 assignee）

---

## 使用者故事

### 邀請流程

- 身為 admin，我想要在 Dashboard 輸入 email 邀請新用戶，以便他們能自助登入使用 ZenOS
- 身為被邀請者，我想要收到邀請信後點連結直接登入，不需要額外設定帳號

### 權限管理

- 身為 admin，我想要把 member 提升為 admin，以便他也能邀請和管理用戶
- 身為 admin，我想要停用某個用戶，以便他無法再存取系統

### Agent 身份

- 身為用戶，我想要我的 AI agent 在建立任務時自動帶上我的身份，以便其他人的 agent 不會誤操作我的任務

---

## 需求

### P0（最小閉環）

**邀請流程**

- [ ] Given admin 在 Dashboard 的用戶管理頁面
      When 輸入 email 並點擊「邀請」
      Then 系統在 `partners` 建立 `status: "invited"` 的記錄，並發送 Firebase email link

- [ ] Given 被邀請者收到邀請信
      When 點擊連結
      Then 跳轉至 ZenOS Dashboard，自動完成 Google SSO 登入

- [ ] Given 被邀請者首次登入
      When AuthGuard 比對 `partners` collection 找到 email 且 status 為 "invited"
      Then 更新 status 為 "active"，自動生成 API key，進入 Dashboard

**用戶管理 UI**

- [ ] Given admin 在用戶管理頁面
      When 查看用戶列表
      Then 看到所有 partners 的 email、角色、狀態、邀請時間

- [ ] Given admin 在用戶列表
      When 點擊某 member 的「設為 Admin」按鈕
      Then 該用戶的 `isAdmin` 更新為 true

- [ ] Given admin 在用戶列表
      When 點擊某用戶的「停用」按鈕
      Then 該用戶的 `status` 更新為 "suspended"，下次請求被拒絕

**Agent 身份辨識**

- [ ] Given MCP server 收到帶有 partner API key 的請求
      When 驗證通過
      Then 將 partner identity（email, displayName）注入 request context，
           後續 tool handler 可取得「這是誰的 agent」

- [ ] Given agent 透過 `task` tool 建立任務
      When 未指定 `createdBy`
      Then 自動填入 partner 的 displayName（而非固定字串）

- [ ] Given agent 透過 `search` / `task` tool 查詢任務
      When 帶有 `assignee` filter
      Then 可用 partner displayName 過濾「派給我的任務」

### P1（重要但不阻塞 MVP）

- [ ] Firestore rules 強制檢查 partner status（suspended 用戶的 read 請求也拒絕）
- [ ] 重新邀請（resend invitation email）
- [ ] Admin 不能停用自己
- [ ] 邀請連結過期機制（7 天）

### P2（未來）

- [ ] Entity-level 權限（visibility: restricted + allowedRoles）
- [ ] Agent registry — 每個用戶可命名自己的 agents（"Android Agent", "Code Agent"）
- [ ] 操作稽核日誌

---

## 狀態定義

### Partner Status

| 狀態 | 說明 | 誰觸發 | 可轉移到 |
|------|------|--------|---------|
| `invited` | 已邀請，尚未登入 | admin 邀請時 | `active` |
| `active` | 正常使用中 | 首次登入時 / admin 啟用 | `suspended` |
| `suspended` | 已停用 | admin 停用時 | `active` |

### Partner Schema 變更

```typescript
interface Partner {
  // 既有欄位不變
  id: string;
  email: string;
  displayName: string;
  apiKey: string;              // invited 時為空，首次登入時生成
  authorizedEntityIds: string[];
  isAdmin: boolean;
  status: "invited" | "active" | "suspended";  // 新增 invited
  createdAt: Date;
  updatedAt: Date;
  // 新增
  invitedBy: string;           // 邀請者的 email
}
```

---

## 頁面元素清單

### `/team` — 用戶管理頁面（新頁面）

**進入條件**：僅 admin 可見此頁面導航項目

**UI 組件**
- 邀請表單：email input + 「邀請」按鈕
- 用戶列表表格：email、名稱、角色 badge、狀態 badge、邀請時間
- 每行 action menu：「設為 Admin」/「設為 Member」、「停用」/「啟用」

**資訊展示**
- 用戶總數、active 數量
- 邀請中（pending）的用戶特別標示

---

## MCP Agent Identity 設計

### 目標

讓每個 MCP tool handler 知道「這個請求來自哪個 partner」。

### 方式

```
API Key → ApiKeyMiddleware 驗證 → partner data 注入 ASGI scope
→ tool handler 從 context 取得 partner identity
```

具體改動：
1. `ApiKeyMiddleware` 驗證成功後，把 partner data 存入 `scope["state"]["partner"]`
2. FastMCP 的 tool handler 透過 request context 取得 partner
3. `task` tool 的 `createdBy` 預設填入 `partner.displayName`
4. `search` tool 支援 `assignee` 用 partner displayName 過濾

---

## 成功指標

- 短期（1 週）：Barry 成功邀請 1 位用戶，對方自助登入看到 Dashboard
- 短期（1 週）：兩個不同用戶的 agent 建立的任務能正確辨識來源

---

## 開放問題

- ⚠️ 待 Architect 確認：FastMCP 的 context / dependency injection 機制能否在 tool handler 裡拿到 ASGI scope 裡的 partner data？
- ⚠️ 待 Architect 確認：Firebase email link 登入 + Google SSO 的整合方式（是 email link 導到登入頁觸發 Google popup，還是 email link 本身就是 auth？）
- ⚠️ 待 Architect 確認：Dashboard 寫入 Firestore（用戶管理）目前 rules 是 `allow write: if false`，需要用 Cloud Functions 還是開放特定 collection 的 write？
