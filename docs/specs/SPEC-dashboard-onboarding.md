---
type: SPEC
id: SPEC-dashboard-onboarding
status: Draft
l2_entity: Dashboard 知識地圖
created: 2026-04-09
updated: 2026-04-09
---

# Feature Spec: Dashboard Onboarding — 空知識地圖引導流程

## 背景與動機

用戶完成帳號建立和 MCP 連線後，進入 Dashboard 看到一張空的知識地圖。此時用戶面臨三個斷點：

1. **不知道 ZenOS 能做什麼** — 知識地圖是空的，沒有任何視覺線索說明價值。
2. **不知道如何開始** — 第一份知識從哪來？是要手動建，還是用 AI 自動匯入？
3. **不知道要綁定外部資料源** — Google Drive 等外部 MCP 需要用戶主動在自己的 AI 工具中設定，ZenOS 沒有任何提示。

現有 `/setup` 頁面只處理「MCP 連線 + Skill 安裝」的技術步驟，**不涵蓋「如何使用」的引導**。用戶完成 setup 後到知識地圖之間是斷裂的。

## 目標用戶

| 用戶類型 | 場景 | 關注點 |
|---------|------|--------|
| **技術用戶（開發者）** | 用 Claude Code / Codex 等 CLI 工具開發 | 想快速用 `/zenos-capture` 匯入既有專案 |
| **非技術用戶（老闆 / PM）** | 用 Claude.ai / ChatGPT 等對話式 AI 工具 | 想看到 AI 理解自己的公司，不碰 code |

兩類用戶的 onboarding 步驟相同，但每一步的說明文案和範例需要分流。

## Spec 相容性

已比對的既有 Spec：
- **SPEC-company-onboarding-first-admin**（current）：處理帳號 bootstrap（SSO → partner 建立）。本 spec 接在其之後——帳號已建立、MCP 已連線，但知識地圖是空的。**無衝突，互補關係。**
- **SPEC-dashboard-v1**（approved）：定義知識地圖、任務 view 等核心頁面。本 spec 在知識地圖頁面新增空狀態 overlay，不改變既有頁面結構。**無衝突。**

## 需求

### P0（必須有）

#### P0-1：Onboarding Checklist 元件

- **描述**：當用戶的知識地圖為空（L1 + L2 entity 數量 = 0）時，在知識地圖頁面顯示一個「開始使用」按鈕。用戶點擊後開啟 Onboarding Checklist 面板，列出 4 個步驟，每步有完成狀態。用戶可以按任意順序完成，不強制順序。
- **觸發與消失邏輯**：
  - **顯示條件**：workspace 內 L1+L2 entity = 0，且用戶未手動關閉
  - **消失條件**：workspace 內出現 entity（L1+L2 > 0），或用戶選擇「不再顯示」
  - 具體 UI 位置與互動形式由 Designer 確認後補充到本 Spec
- **Acceptance Criteria**：
  - Given 用戶登入且 workspace 內 L1+L2 entity = 0, When 進入知識地圖頁面, Then 顯示「開始使用」按鈕
  - Given 用戶點擊「開始使用」, When Checklist 面板開啟, Then 顯示 4 個步驟和進度條
  - Given 用戶已完成某些步驟, When 重新進入知識地圖, Then Checklist 反映最新的完成狀態
  - Given workspace 內出現 entity（透過 capture 或其他方式）, When 進入知識地圖, Then Checklist 自動消失，知識地圖正常顯示
  - Given 用戶點擊「不再顯示」, When 重新進入知識地圖, Then 不再顯示「開始使用」按鈕

#### P0-2：Step 1 — 導向知識庫

- **描述**：引導用戶告訴 AI 助手既有知識的位置——本地資料夾或 Google Drive。這是 onboarding 的第一步，因為 AI 需要先知道「知識在哪裡」才能進行後續操作。
- **完成條件判定**：用戶手動標記「已完成」或「稍後再說」。（因為知識來源位置的確認發生在用戶的 AI 工具端，ZenOS server 無法偵測。）
- **內容分流**：
  - **技術用戶路徑**：提示「告訴 AI 你的專案路徑」，附範例指令
  - **非技術用戶路徑**：提示「告訴 AI 你的資料在 Google Drive 哪個資料夾」，附範例對話
- **Acceptance Criteria**：
  - Given 用戶查看 Step 1, When 展開詳情, Then 顯示根據平台類型的引導文案和範例
  - Given 用戶點擊「已完成」或「稍後再說」, When Checklist 更新, Then Step 1 標記為對應狀態

#### P0-3：Step 2 — 設定 MCP + 安裝 Skills

- **描述**：引導用戶將 ZenOS MCP 連結設定到自己的 AI 工具中，並透過 `/zenos-setup` 安裝 ZenOS skills。這一步大部分用戶在 `/setup` 頁面已完成，但 Checklist 仍需顯示以提供完整脈絡。
- **完成條件判定**：用戶的 partner 記錄存在且 API key 已啟用（= 帳號已建立即視為完成，因為 MCP 連線無法從 server 端偵測）。
- **Acceptance Criteria**：
  - Given 用戶帳號已建立, When 查看 Step 2, Then 該步驟自動標記為已完成
  - Given 用戶帳號已建立, When 點擊 Step 2, Then 展開顯示 MCP 連結、複製按鈕、以及 `/zenos-setup` 安裝提示

#### P0-4：Step 3 — 捕捉知識

- **描述**：引導用戶透過 `/zenos-capture` 把專案知識匯入 ZenOS。這是最關鍵的一步——用戶完成後就能在知識地圖上看到節點，體驗到 ZenOS 的核心價值。
- **完成條件判定**：workspace 內 L1+L2 entity 數量 > 0。
- **內容分流**：
  - **技術用戶路徑**：提示「在 AI 工具中輸入 `/zenos-capture {你的專案目錄}`」，附範例指令
  - **非技術用戶路徑**：提示「告訴你的 AI 助手：『幫我把這個專案加入 ZenOS』」，附範例對話
- **Acceptance Criteria**：
  - Given 用戶的 workspace 內無 entity, When 查看 Step 3, Then 顯示「捕捉知識」引導，根據用戶在 /setup 選擇的平台類型顯示對應的文案
  - Given 用戶透過 AI 工具執行 capture 後產生了 entity, When 重新進入知識地圖, Then Step 3 自動標記為已完成，知識地圖開始顯示節點

#### P0-5：Step 4 — 體驗 AI 角色

- **描述**：引導用戶體驗 ZenOS 的 AI 角色能力（/pm、/architect 等），讓用戶感受到「AI 懂我的公司」的價值。如果用戶的 AI 工具中沒有看到這些角色，提示他們先執行 `/zenos-setup` 安裝 ZenOS Agent。
- **完成條件判定**：用戶手動標記「已完成」或「稍後再說」。
- **內容**：
  - 精選 3 個最容易上手的角色，附帶「試試看」的範例指令：
    - 「試試問你的 AI：『用 /pm 幫我規劃一個新功能的需求』」
    - 「試試問你的 AI：『用 /architect 幫我分析這個系統的架構』」
    - 「試試問你的 AI：『用 /marketing 幫我寫一篇產品介紹文案』」
  - 缺失角色提示：「如果沒有看到這些角色，請先執行 `/zenos-setup` 安裝 ZenOS Agent」
- **Acceptance Criteria**：
  - Given 用戶查看 Step 4, When 展開詳情, Then 顯示推薦的 AI 角色和試用指令
  - Given 用戶的 AI 工具中沒有角色, When 查看 Step 4, Then 顯示安裝 ZenOS Agent 的提示
  - Given 用戶點擊「已完成」或「稍後再說」, When Checklist 更新, Then Step 4 標記為對應狀態

### P1（應該有）

#### P1-0：/setup 完成後導向知識地圖

- **描述**：用戶完成 /setup 頁面的 MCP 設定後，頁面底部的 CTA 從「Back to projects」改為「前往知識地圖」，將用戶導向知識地圖頁面，讓 Checklist 自然出現。
- **Acceptance Criteria**：
  - Given 用戶在 /setup 頁面完成設定, When 查看頁面底部, Then 顯示「前往知識地圖」按鈕（取代原有的「Back to projects」連結）
  - Given 用戶點擊「前往知識地圖」, When 頁面跳轉, Then 進入知識地圖頁面並看到「開始使用」按鈕

#### P1-1：Checklist 持久化

- **描述**：Checklist 的完成狀態需要持久化，避免用戶刷新頁面後狀態遺失。自動偵測的步驟（Step 2、Step 3）從 server 即時計算；手動標記的步驟（Step 1、Step 4）持久化到 server 端（partner preferences JSONB 欄位）。
- **Acceptance Criteria**：
  - Given 用戶手動標記 Step 1 為已完成, When 刷新頁面或換裝置登入, Then Step 1 仍顯示已完成
  - Given 另一位 workspace 成員完成 capture, When owner 查看 Checklist, Then Step 3 自動標記為完成（entity count 變 > 0）

#### P1-2：文案分流 — 技術 vs 非技術

- **描述**：根據用戶在 `/setup` 選擇的平台（Claude Code / Codex = 技術; Claude.ai / ChatGPT = 非技術），自動切換每一步的文案和範例。如果用戶未經過 /setup，預設顯示非技術版本。
- **Acceptance Criteria**：
  - Given 用戶在 /setup 選擇了 Claude Code, When 查看 Step 1/3, Then 顯示 CLI 風格的指令範例
  - Given 用戶在 /setup 選擇了 ChatGPT, When 查看 Step 1/3, Then 顯示對話風格的範例

### P2（可以有）

#### P2-1：Onboarding 完成慶祝

- **描述**：用戶完成全部必要步驟後，顯示一個簡短的慶祝畫面或 toast，強化正向回饋。
- **Acceptance Criteria**：
  - Given 用戶完成必要步驟, When Checklist 判定為完成, Then 顯示慶祝 toast 或短動畫，3 秒後自動消失

#### P2-2：Onboarding 進度提示（側邊欄）

- **描述**：在知識地圖有少量節點但 Checklist 尚未全部完成時，在側邊欄底部顯示一個迷你進度提示（如「2/4 步驟已完成」），引導用戶繼續完成。
- **Acceptance Criteria**：
  - Given 知識地圖有 entity 但 Checklist 未全部完成, When 查看知識地圖, Then 側邊欄底部顯示迷你進度提示
  - Given 用戶點擊迷你提示, When 展開, Then 顯示完整 Checklist

## 明確不包含

- **帳號建立流程** — 由 SPEC-company-onboarding-first-admin 處理
- **MCP 連線設定的完整 UI** — 由現有 /setup 頁面處理，本 spec 只做精簡版的 Step 2 卡片
- **外部 MCP 的自動偵測** — 外部 MCP 由用戶端主動綁定，ZenOS 不偵測
- **強制順序的 Wizard** — Checklist 不強制順序，用戶可以跳過任何步驟
- **收費 / 升級引導** — 不在 onboarding 流程中推銷付費功能

## 技術約束（給 Architect 參考）

- **Entity count 查詢**：Checklist 需要查詢 workspace 內的 entity 數量。可利用現有 Dashboard API 的 entities endpoint，不需要新 API。但需注意效能——不要每次 render 都 call API，應快取結果。
- **手動標記持久化**：Step 1 / Step 4 的手動完成狀態需要持久化。建議放在 partner metadata（已有 JSONB 欄位）或新增專用欄位。不要放 localStorage——換裝置會丟失。
- **文案分流**：需要知道用戶選擇的平台。目前 /setup 頁面沒有持久化平台選擇。需要在 /setup 完成時存下來（partner metadata），或讓 Checklist 自己問一次。
- **/setup 與 Checklist 的銜接**：用戶從 /setup 完成後，應該被導向知識地圖頁面（而非停留在 /setup），讓 Checklist 自然出現。

## 已決定的開放問題

1. ~~Checklist 的顯示位置~~ → 知識地圖空狀態顯示「開始使用」按鈕，點擊後開啟 Checklist。具體 UI 由 Designer 確認後補充。
2. ~~Checklist 消失的閾值~~ → 有 entity 後自動消失，或用戶選擇「不再顯示」。
3. ~~/setup 完成後的導向~~ → 加「前往知識地圖」CTA 按鈕。

## 開放問題

1. **「開始使用」按鈕的視覺設計**：按鈕放在畫布中央？還是頂部 banner？→ 需 Designer 確認。
