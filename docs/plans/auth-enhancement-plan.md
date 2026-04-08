# 執行計畫：Auth 機制強化與人員刪除

**目標**：實作 ADR-015 所定義的兩項需求。
**負責角色**：Developer (實作), QA (驗證)
**狀態**：待執行 (To Do)

## Phase 1: 後端 API 修改 (Developer)
- [ ] 檢查 `src/zenos/interface/admin_api.py` 的 `delete_partner` 函數。
- [ ] 移除 `target.get("status") != "invited"` 的阻擋邏輯。
- [ ] 在呼叫 `repo.delete(partner_id)` 前，處理資料庫的關聯約束：
      - 將該 partner 負責的 tasks 的 `assignee` 設為 `NULL`。
      - （選作）檢查是否有其他 Foreign Key 約束會阻擋 DELETE 操作（如 `task_comments`），若有則一併刪除或轉移。
- [ ] 撰寫/更新對應的 pytest 測試 (`tests/`) 以確保 active 用戶可被刪除且不引發 SQL Constraint Error。

## Phase 2: 前端 UI 修改 (Developer)
- [ ] **修改 `TeamPage.tsx`**:
      - 將列表中的「刪除」按鈕顯示邏輯從 `p.status === "invited"` 改為 `!isSelf`（即除自己外皆可刪除）。
      - 點擊刪除 active/suspended 狀態用戶時，加入 `window.confirm` 的強烈警告語（例如：「確定要徹底刪除此用戶嗎？此操作不可逆，且將解除其負責的任務關聯。」）。
- [ ] **修改 `LoginPage.tsx`**:
      - 引入新的狀態變數（如 `showAccountSetup: boolean`）。
      - 在 `signInWithEmailLink` 的 `.then()` 中，不要 `router.replace("/")`，而是 `setShowAccountSetup(true)`。
      - 在 `showAccountSetup` 為 true 時，渲染一個新視圖，提供三個按鈕：
          1. 關聯 Google 帳號 (`linkWithPopup`)
          2. 設定密碼 (`updatePassword` 邏輯，可能需要一個密碼輸入框組件)
          3. 稍後再說（跳轉 `/`）
      - 若綁定成功，跳轉至 `/`。

## Phase 3: QA 驗證 (QA)
- [ ] **TC-Auth-01**: 以新 Email 透過 Magic Link 登入，驗證是否進入設定頁面。
- [ ] **TC-Auth-02**: 點擊「關聯 Google 帳號」，驗證是否成功綁定並進入首頁。
- [ ] **TC-Admin-01**: 以 Admin 身分進入 Team 頁面，嘗試刪除一個 `active` 狀態的用戶，驗證是否成功。
- [ ] **TC-Admin-02**: 驗證被刪除用戶原本負責的任務，其 Assignee 狀態是否正確（變成 Unassigned/Null，不報錯）。

---
*此計畫將透過 Developer Agent 逐步執行並更新狀態。*