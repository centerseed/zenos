---
doc_id: ADR-015-auth-enhancement
title: 架構決策：Auth 機制強化與人員刪除權限放寬
type: ADR
ontology_entity: 身份與權限管理
status: approved
version: "1.0"
date: 2026-04-08
supersedes: null
---

# ADR-015: Auth 機制強化與人員刪除權限放寬

## 1. 背景 (Context)

目前的 ZenOS Dashboard 在身份驗證與人員管理上遇到兩個使用情境的瓶頸：
1. **Magic Link 跨裝置體驗不佳**：透過 Email 邀請連結登入的用戶，若更換裝置或瀏覽器，必須重新收發 Magic Link，無法直接使用密碼或 SSO（如 Google）登入，造成移動辦公體驗斷層。
2. **Admin 無法刪除正式用戶**：Admin 目前只能在 `TeamPage` 刪除狀態為 `invited` 的邀請。對於已經啟用 (`active`) 或停用 (`suspended`) 的內部離職員工，只能將其停用，無法從系統中徹底移除。

## 2. 決策 (Decision)

針對上述問題，我們決定進行以下架構與流程調整：

### 2.1 Magic Link 登入流程強化 (SSO 綁定)
*   **變更點**：在 `LoginPage` 的 `signInWithEmailLink` 驗證成功後，攔截原本直接跳轉至首頁的動作。
*   **新流程**：顯示一個中間過渡頁面（Account Setup），引導用戶進行「SSO 綁定 (Google)」或「設定密碼」。
*   **技術實作**：使用 Firebase Auth 的 `linkWithPopup` (GoogleAuthProvider) 或 `updatePassword` API 來完善該 Email 帳號的憑證。完成後再跳轉至受保護的 Dashboard。

### 2.2 放寬 Admin 刪除夥伴 (Partner) 的限制
*   **變更點**：修改後端 `admin_api.py` 中的 `delete_partner` 路由。
*   **新規則**：允許 Admin 刪除狀態為 `active` 或 `suspended` 的用戶（不可刪除自己）。
*   **數據一致性策略 (Data Integrity)**：
    *   在刪除 Partner 紀錄前，必須處理關聯數據（如 Task assignee, comments）。
    *   考量到關聯複雜度，暫不實作聯級刪除 (Cascade Delete) 任務，而是將被刪除者的任務 Assignee 設為 null 或保留其 ID 但前端顯示「已刪除用戶」。SQL Schema 層級若有 Foreign Key 約束，需進行對應處理（例如 `ON DELETE SET NULL`，若目前為 `RESTRICT`，則需在應用層手動解除關聯，或者執行軟刪除）。
    *   **最終決定**：API 端在刪除前，先將該 Partner 負責的 Tasks 的 assignee 設為 NULL。

## 3. 影響與後果 (Consequences)

*   **正面影響**：
    *   大幅提升用戶跨裝置登入的便利性。
    *   完善組織人員管理的生命週期（入職 → 停用 → 刪除）。
*   **負面影響 / 風險**：
    *   刪除用戶可能導致歷史稽核紀錄 (Audit Events) 或任務歷史 (Work Journal) 出現「孤兒 ID」。前端在渲染這些歷史資料時，若找不到對應的 Partner，需有 Fallback 顯示機制（例如顯示 "Unknown User"）。
    *   Firebase 端的使用者帳號也應一併考量是否刪除，但目前 ZenOS 以 SQL `partners` 表為授權 SSOT，因此刪除 SQL 紀錄即剝奪存取權。Firebase 帳號的清理可作為後續增強。

## 4. 替代方案 (Alternatives Considered)

*   **關於 SSO 綁定**：曾考慮在 Dashboard 內部的「個人設定」頁面提供綁定功能。但多數用戶不會主動尋找該功能，導致換電腦時依然卡關。放在登入成功的第一時間轉化率最高。
*   **關於刪除用戶**：曾考慮實作 Soft Delete (加一個 `deleted_at` 欄位)。但考慮到目前已有 `suspended` 狀態作為實質上的 Soft Delete，`DELETE` API 應該具備物理刪除（或解除綁定）的語意，以符合 GDPR 或資料清理的需求。
