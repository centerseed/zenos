# Dashboard v0 — 夥伴入口 Feature Spec

> 日期：2026-03-21
> 狀態：Draft
> 作者：PM
> 交付對象：Architect

---

## 問題陳述

ZenOS 的 MCP server 已部署在 Cloud Run，ontology 資料在 Firestore 裡。但行銷夥伴要接上這個 MCP 之前，卡在三件事：

1. **不知道怎麼設定** — MCP config 要自己拼 URL + API key，非技術人員做不到
2. **不知道裡面有什麼** — ontology 是給 agent 讀的，人沒有入口可以瀏覽
3. **不知道從何開始** — 接上之後該問 agent 什麼？有哪些專案？每個專案有什麼？

Dashboard v0 解決的就是這三件事：**讓夥伴能自己接上、看到概覽、知道怎麼開始用。**

## 目標

- 行銷夥伴登入後，5 分鐘內能完成 MCP 設定，讓自己的 AI agent 接上 ZenOS
- 行銷夥伴能在 Dashboard 看到每個專案的 ontology 概覽，知道可以問 agent 什麼
- Barry 能透過 Dashboard 管理 API key 的發放（誰能接、誰不能）

## 非目標（不在範圍內）

- 不做 ontology 編輯（那是 Barry 在 Claude Code 裡做的事）
- 不做確認佇列（Phase 1 再加）
- 不做 Protocol viewer（等 Protocol 格式穩定）
- 不做 Storage Map
- 不做文件管理（Dashboard ≠ 文件管理工具）
- 不做多語系

---

## 使用者故事

### 行銷夥伴（主要用戶）

- 身為行銷夥伴，我想要登入 Dashboard 後看到 MCP 設定步驟，以便我能照著做、讓我的 Claude Code 接上 ZenOS
- 身為行銷夥伴，我想要瀏覽每個專案的 ontology 概覽（有哪些產品、模組、目標），以便我知道可以請 AI agent 幫我做什麼
- 身為行銷夥伴，我想要看到每個模組的一句話描述和狀態，以便我不用讀技術文件就知道產品現況

### Barry（管理者）

- 身為 Barry，我想要能新增夥伴帳號並發 API key，以便控制誰能存取哪些專案的 ontology
- 身為 Barry，我想要能撤銷 API key，以便在合作結束時關閉存取

---

## 頁面設計

### 頁面 1：登入

**路由：** `/login`

**需求：**

- [ ] Given 未登入的夥伴 When 打開 Dashboard Then 看到登入頁面
- [ ] Given 登入頁面 When 用 Google 帳號登入 Then 進入首頁
- [ ] Given 未被 Barry 授權的 Google 帳號 When 登入 Then 顯示「請聯繫管理員開通權限」

**頁面元素：**
- Google 登入按鈕
- ZenOS logo + 一句話 tagline
- 錯誤訊息區域

---

### 頁面 2：首頁 — 我的專案

**路由：** `/`

**需求：**

- [ ] Given 已登入的夥伴 When 進入首頁 Then 看到自己被授權的專案列表
- [ ] Given 專案列表 When 每個專案卡片 Then 顯示：專案名稱、一句話描述、模組數量、最後更新時間
- [ ] Given 專案卡片 When 點擊 Then 進入該專案的 ontology 概覽

**頁面元素：**
- 專案卡片列表
- 頂部：MCP 設定入口（醒目的 CTA 按鈕「設定你的 AI Agent」）
- 右上角：使用者名稱 + 登出

---

### 頁面 3：MCP 設定指引

**路由：** `/setup`

**需求：**

- [ ] Given 夥伴進入設定頁 When 頁面載入 Then 顯示該夥伴專屬的 API key
- [ ] Given 設定頁 When 選擇 agent 類型（Claude Code / 其他） Then 顯示對應的 config JSON
- [ ] Given config JSON When 點擊「複製」 Then config 被複製到剪貼簿，包含正確的 URL 和 API key
- [ ] Given 設定頁 Then 顯示 step-by-step 設定步驟（附截圖或 GIF）

**Config 範例（Claude Code）：**

```json
{
  "mcpServers": {
    "zenos": {
      "type": "http",
      "url": "https://zenos-mcp-xxxxx.asia-east1.run.app/mcp?api_key={PARTNER_API_KEY}"
    }
  }
}
```

**設定步驟：**
1. 安裝 Claude Code（附連結）
2. 開啟設定檔（告訴他在哪裡）
3. 貼上 config（一鍵複製）
4. 重啟 Claude Code
5. 驗證：輸入「列出所有產品」，確認有回應

**頁面元素：**
- Agent 類型選擇（Tab：Claude Code / Claude.ai / 其他）
- API key 顯示區（遮罩 + 顯示按鈕）
- Config JSON 區塊 + 複製按鈕
- Step-by-step 步驟（可折疊）
- 「我設定好了，測試連線」按鈕（選做，⚠️ 待 Architect 確認可行性）

---

### 頁面 4：專案 Ontology 概覽

**路由：** `/projects/:projectId`

**需求：**

- [ ] Given 專案概覽頁 When 頁面載入 Then 從 Firestore 讀取該專案的 entities
- [ ] Given entities 資料 Then 顯示：骨架層全景（模組樹 + 依賴關係）
- [ ] Given 每個 entity Then 顯示：名稱、type icon、一句話描述、狀態標籤
- [ ] Given entity 列表 Then 按 type 分組：產品 → 模組 → 目標
- [ ] Given 盲點資料 When 有 severity=red 的盲點 Then 在頁面頂部顯示警示

**頁面元素：**

**區塊 A — 專案摘要**
- 專案名稱 + 一句話描述
- 統計：X 個模組、X 份文件、X 個盲點

**區塊 B — 模組全景**
- 樹狀或卡片列表，每個模組：
  - 名稱
  - 狀態（active / paused / planned）
  - 一句話描述
  - 點開可看 relationships（依賴什麼、被誰依賴）

**區塊 C — 盲點摘要**
- 紅色/黃色盲點列表
- 每個盲點：描述 + 建議動作

**區塊 D — 提示卡片「接下來試試看」**
- 3-5 個範例 prompt，夥伴可以直接複製貼到 Claude：
  - 「幫我寫一篇 {專案名} 的社群貼文」
  - 「{專案名} 的核心功能有哪些？」
  - 「{專案名} 目前有什麼待解決的問題？」

---

## 成功條件

- [ ] 行銷夥伴從登入到完成 MCP 設定，全程不需要問 Barry（自助完成）
- [ ] 行銷夥伴看完 ontology 概覽後，能說出「這個產品大概在做什麼」
- [ ] 行銷夥伴複製範例 prompt、貼到 Claude、拿到有 context 的回應
- [ ] Barry 能在 10 分鐘內幫新夥伴開好帳號（建帳號 + 發 API key）

## 成功指標

- 短期（上線後 1 週）：行銷夥伴成功接上 MCP 並產出第一份素材
- 長期（1 個月）：Dashboard 成為新夥伴加入時的標準入口

---

## 開放問題（待 Architect 決策）

- [ ] 技術棧選型：Next.js? SvelteKit? 純靜態 + Firebase SDK?
- [ ] 部署位置：Vercel? Cloud Run? Firebase Hosting?
- [ ] API key 管理：Firestore 裡存一個 `api_keys` collection? 還是用 Firebase Auth custom claims?
- [ ] 夥伴帳號與專案的關聯：怎麼控制「這個夥伴只能看這些專案」？
- [ ] 「測試連線」功能的可行性：Dashboard 能不能直接呼叫 MCP server 驗證 key 有效？
- [ ] ontology 概覽的資料來源：直接讀 Firestore? 還是透過 MCP server 的 API?

---

## 與既有 spec 的關係

Phase 1 spec（`phase1-ontology-mvp.md`）的非目標寫了「不做 Dashboard UI」。

**這裡的決策變更：** 在驗證 ontology 的過程中發現，夥伴無法自助接上 MCP + 不知道 ontology 裡有什麼 = 驗證流程卡住。Dashboard v0 是解除這個阻塞的最小投入。

scope 刻意比 Phase 1 spec 規劃的 Dashboard（全景圖 + 確認佇列 + Protocol viewer + Storage Map）小很多，只做「入口 + 概覽」。

---

*PM 交付。Architect 請基於此 spec 產出技術設計 + 實作任務拆分。*
