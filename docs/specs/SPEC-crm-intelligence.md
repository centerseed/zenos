---
type: SPEC
id: SPEC-crm-intelligence
doc_id: SPEC-crm-intelligence
title: Feature Spec: CRM AI Intelligence 模組
status: draft
version: "0.3"
date: 2026-04-14
supersedes: null
depends_on: SPEC-crm-core
l2_entity: crm-客戶管理
created: 2026-04-14
updated: 2026-04-14
---

# Feature Spec: CRM AI Intelligence 模組

## 背景與動機

SPEC-crm-core 建立了基礎的 B2B CRM 功能——公司、聯絡人、Deal 漏斗、活動紀錄。但這些功能跟市面上任何入門 CRM（HubSpot Free、Pipedrive）沒有本質差異。

真正的痛點不是「記錄」，而是**「知道下一步該做什麼」**：

- 拜訪客戶前，業務花 30 分鐘翻歷史紀錄和準備資料——但常常漏看關鍵訊息
- 會議結束後，承諾的事項和客戶的顧慮散落在腦中和筆記裡——隔兩天就忘了
- Deal 在某個階段卡了三週，沒人意識到要主動推進——直到客戶被競爭對手拿走
- 新案子進來，明明去年有類似的案子成功過——但經驗在某個人的腦袋裡，無法複製

ZenOS 的 ontology 正好解決這些問題。CRM 資料（公司、聯絡人、互動歷史）已經橋接為 ZenOS entity，再加上 ontology 裡的產品狀態、團隊決策、行銷成效——AI 能看到的 context 遠超任何傳統 CRM。

**核心理念：業務不該花時間「準備」和「想下一步」——AI 讀完所有 context，直接告訴你該怎麼做。**

---

## 目標用戶

| 角色 | 場景 | 頻率 |
|------|------|------|
| **老闆 / 業務負責人** | 拜訪前看 briefing、會後記錄並看 AI 建議、每週看 pipeline 健康度 | 每天 |
| **業務人員** | 記錄互動、依 AI 建議跟進、複製 follow-up 訊息到 LINE 發送 | 每天 |

**關鍵假設：**

- 使用者的商談形式以視訊會議為主，但也有面對面、電話、LINE 聊天
- Follow-up 以 LINE 為主要管道——AI 生成的訊息需要適合 LINE 的格式（短、口語、可直接複製貼上）
- 使用者不會手動整理會議逐字稿——AI 從使用者寫的 Activity 摘要中萃取洞察
- v1 先支援單人操作，底層保留多人擴充性

---

## 三個 AI 場景

### 場景 1：商談前 — AI Briefing（對話式）

**什麼時候用**：拜訪客戶或開視訊會議前 10 分鐘，在 Deal 詳情頁按「準備下次會議」。

**與 v0.2 的差異**：v0.2 是單次觸發、一次性生成。v0.3 改為對話式——AI 先自動生成一份帶有完整歷史脈絡的會議準備摘要，使用者可以多輪對話追問、調整重點、模擬客戶反應，最終產出一份具體的商談準備資料。UX 復用行銷模組的 `CoworkChatSheet` 多輪對話模式。

**AI 產出的 Briefing 包含**：

| 區塊 | 內容 | 資料來源 |
|------|------|---------|
| 客戶背景 | 公司產業、規模、CRM 中記錄的基本資訊 | CRM 公司欄位 |
| 互動回顧 | 過去所有互動的重點摘要：談過什麼、客戶在意什麼、我們承諾了什麼 | Activity Timeline 全部紀錄 |
| **累積洞察** | 歷次 debrief 萃取的關鍵決策、未完成承諾、客戶核心顧慮 | **AI 洞察面板的持久化資料（場景 4）** |
| 產品現況 | 客戶關心的功能目前開發到哪裡、最近上了什麼新功能 | ZenOS ontology（產品 entity） |
| 相似案例 | 相似產業/規模的歷史 deal 怎麼進行的，成功/失敗的關鍵因素 | ZenOS ontology（歷史 deal） |
| 外部動態 | 客戶公司最近新聞、產業趨勢、人事異動 | WebSearch（**P1 可選觸發**，P0 不含） |
| 本次建議 | 根據目前漏斗階段 + 累積洞察，這次會議應該達成什麼目標、準備什麼素材、避免什麼地雷 | AI 綜合分析 |

**Briefing 的分層產出（解決冷啟動）**：

| 資料豐富度 | 可產出的區塊 | 預期何時達到 |
|-----------|------------|------------|
| 只有公司名稱 | 客戶背景 + 通用階段建議 | 第一天 |
| 有 3+ 筆 Activity | + 互動回顧 + 針對性建議 | 使用 2-3 週後 |
| 有 1+ 筆 Debrief entry | + 累積洞察（決策、承諾、顧慮） | 第一次商談後 |
| 有產品 entity 在 ontology | + 產品現況連結 | ontology 建立後 |
| 有 5+ 筆已結案 deal | + 相似案例推薦 | 使用 2-3 個月後 |
| 使用者手動觸發外部搜尋（P1） | + 外部動態 | P1 上線後 |

即使剛開始用、資料很少，AI 仍然能產出有用的 briefing——只是深度不同。隨著使用越多，briefing 越精準。

**對話式流程**：

```
使用者按「準備下次會議」
  → 開啟對話式面板（CoworkChatSheet 模式）
  → AI 自動生成第一輪 briefing（帶入全部累積洞察）
  → 使用者可以追問：
    「這個客戶上次提到的價格顧慮，我們有什麼新的回應策略嗎？」
    「幫我模擬一下客戶可能的反對意見」
    「這次 demo 應該重點展示哪些功能？」
  → 多輪對話（最多 8 輪，同行銷模組）
  → 最終產出可複製的「商談準備摘要」
```

---

### 場景 2：商談後 — AI Debrief（持久化展示）

**什麼時候用**：會議結束後，使用者在 Deal 詳情頁記錄一筆 Activity（類型：會議），寫完摘要按儲存，AI 自動分析。

**與 v0.2 的差異**：v0.2 的 debrief 是一次性 streaming，使用者關閉面板後所有洞察消失。v0.3 要求 debrief 結果**持久展示**——寫回 ZenOS entry 後，前端從 API 讀取並在活動時間軸和 AI 洞察面板中持久顯示。每次打開 deal 詳情頁，都能看到歷次商談的 AI 分析結果。

**AI 產出的 Debrief 包含**：

| 區塊 | 內容 | 說明 |
|------|------|------|
| 關鍵決策 | 這次會議做了什麼決定 | 從 Activity 摘要萃取，累積到 AI 洞察面板 |
| 客戶顧慮 | 客戶提出了哪些疑慮或反對意見 | 從 Activity 摘要萃取，累積到 AI 洞察面板 |
| 承諾事項 | 我們答應客戶什麼、客戶答應我們什麼 | 從 Activity 摘要萃取，獨立 entry，可追蹤完成狀態 |
| 階段建議 | 這個 deal 是否該推進到下一個漏斗階段 | AI 根據會議內容 + 階段定義判斷 |
| 下一步行動 | 具體該做什麼、什麼時候做 | AI 建議，使用者確認 |
| Follow-up 草稿 | 一則可以直接複製到 LINE 發送的跟進訊息 | LINE 友善格式：短、口語、有溫度 |

**Debrief 的持久化展示**：

| 位置 | 展示方式 |
|------|---------|
| 活動時間軸 | 每筆會議/Demo/電話 Activity 下方，可展開查看對應的 AI debrief 摘要（關鍵決策 + 下一步） |
| AI 洞察面板 | 自動彙整所有 debrief 的關鍵決策、客戶顧慮、承諾事項（見場景 4） |
| Deal Health | 未完成的承諾事項納入 Deal Health 洞察計算 |

**Follow-up 草稿的 LINE 格式要求**：

- 總長度 ≤ 300 字（LINE 訊息太長沒人看）
- 口語化、有溫度，不像制式 email
- 結構：問候 → 會議重點回顧（2-3 點）→ 下一步確認 → 結尾
- 不使用 email 格式（沒有 Subject、Dear、Regards）
- 可選附加：更正式的 email 版本（給需要寄 email 的情境）

---

### 場景 3：持續監控 — AI Deal Health

**什麼時候用**：不需要使用者主動觸發，Dashboard 自動顯示。

**Dashboard 顯示的 AI 洞察**：

| 區塊 | 內容 | 觸發條件 |
|------|------|---------|
| 停滯警告 | 「XX 案已 N 天未互動，建議：...」 | deal 超過設定天數無新 Activity |
| 階段卡關 | 「XX 案在『提案報價』停留 25 天，同類案件平均 12 天」 | 當前階段停留時間 > 同階段歷史平均 × 1.5 |
| 本週待辦 | 「3 個 deal 需要跟進、1 個承諾事項到期」 | 從 Debrief 的承諾事項 + 停滯規則彙整 |
| 管道摘要 | 「進行中 N 案、本月預計成交 $X、上月成交率 Y%」 | 每週自動更新 |
| 跟進建議 | 「建議今天聯繫 XX，上次他提到月底要做決定」 | AI 從互動歷史判斷時機 |

**停滯天數的預設值（可調整）**：

| 漏斗階段 | 預設警告天數 | 理由 |
|---------|------------|------|
| 潛在客戶 | 7 天 | 初次接觸要快，不然客戶忘了你 |
| 需求訪談 | 10 天 | 訪談後應快速安排下一步 |
| 提案報價 | 14 天 | 報價後客戶需要時間評估，但不能放太久 |
| 合約議價 | 14 天 | 議價階段拖太久容易流失 |
| 導入中 | 21 天 | 導入期間間隔可以長一些 |

---

### 場景 4：Deal 智能面板 — 持久化 AI 洞察（v0.3 新增）

**什麼時候用**：使用者打開任何 Deal 詳情頁，智能面板**始終可見**（不需要觸發），展示該 deal 的所有累積 AI 洞察。

**核心理念**：每次商談的 AI debrief 不是一次性報告，而是**知識的累積**。智能面板把散落在各次 debrief 裡的洞察彙整成一個結構化的經營視角——打開 deal 就能看到「這個客戶到底在意什麼、我們欠了什麼、下一步該怎麼走」。

**面板包含的區塊**：

| 區塊 | 內容 | 資料來源 | 互動 |
|------|------|---------|------|
| 關鍵決策 | 歷次商談中做的所有決策，按時間排列 | 所有 `crm_debrief` entries | 唯讀，可展開查看原始 debrief |
| 承諾追蹤 | 我方 + 客戶方的承諾事項，含截止日和完成狀態 | `crm_commitment` entries | ☑ 可標記完成、可標記逾期 |
| 客戶顧慮 | 客戶歷次提出的疑慮和我方應對策略演進 | 所有 `crm_debrief` entries 中的顧慮欄位 | 唯讀 |
| Deal 摘要 | 一段 AI 綜合摘要：目前狀態、風險、建議 | 最新一次 debrief 的下一步 + 階段建議 | 唯讀，隨新 debrief 自動更新 |

**面板位置**：Deal 詳情頁左側欄（與右側活動時間軸並列的雙欄佈局）。

**冷啟動**：尚無任何 debrief entry 時，面板顯示引導文字「完成第一次商談並記錄活動後，AI 洞察將在這裡累積」。

---

## 操作入口

延續行銷模組的雙介面模型：

| 操作 | 在哪裡做 |
|------|---------|
| 看 AI 累積洞察 | Dashboard → Deal 詳情頁 → 左側 AI 洞察面板（始終可見） |
| 準備下次會議 | Dashboard → Deal 詳情頁 → 「準備下次會議」→ 對話式面板 |
| 看 AI Debrief | Dashboard → Deal 詳情頁 → 新增 Activity 後自動顯示 + 持久存在活動時間軸 |
| 追蹤承諾事項 | Dashboard → Deal 詳情頁 → AI 洞察面板 → 承諾追蹤區塊 |
| 看 Deal Health | Dashboard → 客戶 tab 頂部 AI 洞察區 |
| 複製 follow-up 到 LINE | Dashboard → Debrief 區塊 → 一鍵複製 |
| CLI 批量分析 | `/crm-briefing {deal_id}`、`/crm-debrief {deal_id}` |

### Web UI 與 CLI 的分工

| Web UI（Dashboard） | Claude Code CLI |
|---------------------|----------------|
| 看 briefing / debrief 結果 | 深入討論 deal 策略、模擬客戶對話 |
| 一鍵觸發 briefing 生成 | 批量分析多個 deal |
| 複製 follow-up 訊息 | 自訂分析角度（例：「從財務角度分析這個 deal」） |
| 看 deal health 總覽 | 跨 deal 比較分析 |

---

## 需求

### P0（必須有）

#### AI Briefing — 對話式商談準備（v0.3 更新）

- **描述**：使用者在 Deal 詳情頁按「準備下次會議」，開啟對話式面板（復用行銷模組 CoworkChatSheet）。前端組裝 briefing context pack（含公司資料、互動歷史、**歷次 debrief 累積洞察、未完成承諾**）並透過 Local Helper bridge 呼叫本機 Claude CLI。AI 先自動生成第一輪結構化簡報，使用者可多輪對話追問、調整重點，最終產出一份具體的商談準備資料
- **Acceptance Criteria**：
  - **核心功能**：
  - Given 使用者在 Deal 詳情頁按「準備下次會議」，When 對話式面板開啟，Then AI 自動生成第一輪 briefing，30 秒內顯示
  - Given deal 只有公司名稱、沒有任何 Activity，When 生成 briefing，Then 仍產出「客戶背景」和「通用階段建議」兩個區塊，不報錯
  - Given deal 有 3+ 筆 Activity，When 生成 briefing，Then 額外產出「互動回顧」區塊，摘要過去所有互動的重點
  - Given deal 有 1+ 筆 debrief entry，When 生成 briefing，Then 額外產出「累積洞察」區塊，包含歷次關鍵決策、未完成承諾、客戶核心顧慮
  - Given ontology 中有與該公司相關的產品 entity，When 生成 briefing，Then 額外產出「產品現況」區塊
  - Given 有 5+ 筆已結案 deal 且其中有相似產業/規模的案例，When 生成 briefing，Then 額外產出「相似案例」區塊，包含成功/失敗因素
  - Given briefing 生成完成，When 使用者查看，Then 每個區塊可展開收合，預設展開「本次建議」區塊
  - Given P0 版本，When 生成 briefing，Then 不執行 WebSearch，僅使用 ZenOS 內部 context（CRM 資料 + ontology）
  - **對話式互動（v0.3 新增，復用行銷模組 CoworkChatSheet）**：
  - Given 第一輪 briefing 已生成，When 使用者在對話框輸入追問（如「客戶上次的價格顧慮怎麼回應？」），Then AI 帶入完整 deal context 回答，對話歷史保留在面板中
  - Given 對話進行中，When 使用者持續追問，Then 最多支援 8 輪對話（同行銷模組），超過後提示「請開啟新的準備 session」
  - Given 對話結束，When 使用者關閉面板，Then 對話歷史不持久化（同行銷模組），但 AI 生成的 briefing entry 寫回 ZenOS
  - Given 使用者已在對話中討論出具體準備策略，When 使用者點「複製準備摘要」，Then 將最新一輪 AI 回覆以純文字複製到剪貼簿
  - **Local Helper 互動（復用行銷模組 ADR-034 架構）**：
  - Given 使用者按「準備下次會議」，When 前端發送請求，Then 前端組裝 briefing context pack（含 company、deal、activities_summary、contacts、**debrief_insights、open_commitments**）並透過 `cowork-helper.ts` 的 `streamCoworkChat()` 送至本機 helper
  - Given helper 啟動 Claude CLI session，When session 初始化完成，Then helper 執行 capability probe，並在 SSE 串流中回傳 `capability_check` 事件
  - Given briefing 生成完成，When AI 呼叫 MCP 寫回 ZenOS entry（type: `crm_briefing`，掛載在 deal entity 上），Then 前端收到 `done` SSE event 後從 ZenOS 讀取 briefing 並渲染
  - Given helper 不可用或未啟動，When 使用者按「準備下次會議」，Then UI 顯示「請先啟動 Local Helper」引導（同行銷模組降級行為），CRM 其他功能不受影響
  - **AI 對話視窗狀態（復用行銷模組狀態機）**：
  - Given briefing 生成流程，When 視窗狀態轉移，Then 遵循行銷模組的 7 狀態機（idle → loading → streaming → idle/error），UI 行為一致

#### AI Debrief — 會後洞察與下一步（v0.3 更新：持久化展示）

- **描述**：使用者新增一筆會議類型的 Activity 並儲存後，前端自動組裝 debrief context pack 並透過 Local Helper bridge 呼叫本機 Claude CLI，AI 分析 Activity 摘要內容，以 SSE 串流產出結構化的會後洞察，寫回 ZenOS entry。**v0.3 新增**：debrief 結果持久展示在活動時間軸和 AI 洞察面板中，不再隨面板關閉而消失
- **Acceptance Criteria**：
  - **核心功能**：
  - Given 使用者新增 Activity（類型：會議 或 Demo 或 電話），When 儲存成功，Then AI 自動開始分析，15 秒內產出 debrief
  - Given Activity 摘要 ≥ 50 字，When AI 分析，Then 產出完整 debrief：關鍵決策、客戶顧慮、承諾事項、階段建議、下一步行動、follow-up 草稿
  - Given Activity 摘要 < 50 字，When AI 分析，Then 產出簡化版 debrief（僅下一步行動 + follow-up 草稿），並提示「摘要越詳細，AI 建議越精準」
  - Given debrief 產出 follow-up 草稿，When 使用者查看，Then 預設顯示 LINE 格式版本（≤ 300 字、口語化），可切換到 Email 格式版本
  - Given follow-up 草稿顯示，When 使用者按「複製」，Then 純文字複製到剪貼簿（不含 HTML 標記），可直接貼到 LINE
  - Given debrief 建議推進漏斗階段，When 使用者同意，Then 提供一鍵「推進到 XX 階段」按鈕，點擊後更新 deal 狀態
  - Given debrief 萃取出承諾事項，When 寫回 ZenOS，Then 每個承諾事項包含：內容、owner（我方/客戶）、建議期限
  - Given 使用者新增 Activity 類型為「備忘」或「Email」，When 儲存，Then 不自動觸發 debrief（這些類型通常是補充記錄，非會議後）
  - Given AI 分析過程中 MCP 連線中斷，When 處理失敗，Then Activity 本身不受影響（已儲存），debrief 區域顯示「分析失敗，點擊重試」
  - **持久化展示（v0.3 新增）**：
  - Given debrief 已寫回 ZenOS entry，When 使用者下次打開 Deal 詳情頁，Then 活動時間軸中該 Activity 下方顯示對應 debrief 摘要（關鍵決策 + 下一步），可展開查看完整 debrief
  - Given deal 有多筆 debrief entry，When 使用者查看 AI 洞察面板，Then 面板自動彙整所有 debrief 的關鍵決策、客戶顧慮（按時間排列），承諾事項獨立追蹤
  - Given 新的 debrief 生成完成，When 寫回 ZenOS entry 成功，Then AI 洞察面板和活動時間軸自動刷新（不需使用者手動重新整理頁面）
  - Given 使用者關閉 debrief streaming 面板，When 回到 Deal 詳情頁，Then 已完成的 debrief 仍在活動時間軸和 AI 洞察面板中可見
  - **Local Helper 互動（復用行銷模組 ADR-034 架構）**：
  - Given Activity 儲存成功，When 前端觸發 debrief 生成，Then 前端組裝 debrief context pack（含 company_name、deal_title、funnel_stage、activity.summary、recent_commitments）並透過 `streamCoworkChat()` 送至本機 helper
  - Given debrief 串流生成中，When SSE 串流回傳 AI 分析內容，Then 前端即時渲染 debrief 各區塊（與行銷模組的串流顯示行為一致）
  - Given debrief 生成完成，When AI 呼叫 MCP 寫回 ZenOS entry（type: `crm_debrief`，掛載在 deal entity 上），Then 承諾事項同時寫為獨立 entry（type: `crm_commitment`）
  - Given helper 不可用，When Activity 儲存成功，Then Activity 正常儲存不受影響，debrief 區域顯示「AI 助手未啟動，無法自動分析。請啟動 Local Helper 後點擊重試」
  - Given debrief 串流中使用者離開 Deal 詳情頁，When 串流未完成，Then 前端發送 cancel 請求中止 CLI process，下次回到頁面可手動觸發重新生成
  - **AI 對話視窗狀態（復用行銷模組狀態機）**：
  - Given debrief 生成流程，When 視窗狀態轉移，Then 遵循行銷模組的 7 狀態機（idle → loading → streaming → idle/error），UI 行為一致

#### Follow-up 草稿生成

- **描述**：AI 為每次商談後生成可直接使用的 follow-up 訊息。以 LINE 為主要格式，同時提供 Email 格式
- **LINE 格式規範**：
  - 總長度 ≤ 300 字
  - 語氣：口語、有溫度、像跟朋友說話但保持專業
  - 結構：問候（1 句）→ 會議重點（2-3 點，用列點或換行）→ 下一步確認（1-2 句）→ 結尾（1 句）
  - 禁止：email 格式用語（Dear / 敬啟者 / Regards / 此致）、過度正式、長段落
  - 允許適當使用表情符號（≤ 3 個），但不過度
- **Email 格式規範**：
  - 含主旨行
  - 正文 ≤ 500 字
  - 結構：開頭感謝 → 會議摘要 → 承諾事項確認 → 下一步 → 結尾
- **Acceptance Criteria**：
  - Given debrief 完成，When 顯示 follow-up 草稿，Then 預設 tab 為 LINE 格式
  - Given LINE 格式草稿，When 使用者檢視，Then 文字長度 ≤ 300 字、無 email 格式用語
  - Given 使用者切換到 Email tab，When 顯示，Then 含主旨行、≤ 500 字正文
  - Given 使用者對草稿不滿意，When 點「重新生成」或跟 AI 討論修改，Then 生成新版本
  - Given 使用者修改草稿內容，When 直接在文字框編輯，Then 可手動調整後再複製

#### Deal Health 洞察看板

- **描述**：在客戶 tab 頂部顯示規則驅動的洞察區塊，提醒哪些 deal 需要注意、建議什麼行動。洞察由 server-side API 即時計算（`GET /api/crm/insights`），不依賴 Local Helper，不持久化
- **Acceptance Criteria**：
  - Given 使用者進入客戶 tab，When 頁面載入，Then 前端呼叫 `GET /api/crm/insights`，在現有統計卡片下方顯示洞察區塊
  - Given 有 deal 超過該階段設定天數未互動，When 洞察區更新，Then 顯示停滯警告卡片，含 deal 名稱、停滯天數、AI 建議的行動
  - Given 有 debrief 產生的承諾事項即將到期或已過期，When 洞察區更新，Then 顯示「待辦到期」卡片
  - Given 所有 deal 都健康（無停滯、無過期待辦），When 洞察區顯示，Then 顯示「目前一切正常」+ 管道摘要（進行中案數、本月預計成交金額）
  - Given 洞察區顯示多張卡片，When 排序，Then 按緊急度排序：過期承諾 > 停滯警告 > 跟進建議
  - Given 使用者點擊洞察卡片，When 跳轉，Then 直接開啟對應 Deal 詳情頁
  - Given deal 被標記為「流失」或「暫緩」，When 計算洞察，Then 不納入停滯警告（已主動處理的不提醒）
  - Given Deal Health 計算，When 處理，Then 計算邏輯在 server-side（Cloud Run API），前端只負責渲染。不依賴 Local Helper——helper 離線時洞察仍可正常顯示

#### 停滯天數設定

- **描述**：每個漏斗階段的停滯警告天數可調整，提供合理預設值
- **Acceptance Criteria**：
  - Given 使用者進入 CRM 設定頁，When 查看停滯天數，Then 看到每個漏斗階段的預設值（潛在客戶 7 天、需求訪談 10 天、提案報價 14 天、合約議價 14 天、導入中 21 天）
  - Given 使用者修改某階段天數，When 儲存，Then 立即生效，所有 deal 的停滯判定使用新天數
  - Given 停滯天數被修改，When 使用者未填入值，Then 回退到預設值

#### Deal 智能面板 — AI 洞察持久展示（v0.3 新增）

- **描述**：Deal 詳情頁重構為雙欄佈局——左側 AI 洞察面板（始終可見）、右側活動時間軸。洞察面板從後端 API 讀取該 deal 的所有 AI entries（crm_debrief、crm_commitment），彙整為結構化的經營視角。活動時間軸中每筆會議/Demo/電話 Activity 可展開查看對應的 AI debrief 摘要
- **Acceptance Criteria**：
  - **AI 洞察面板**：
  - Given 使用者打開 Deal 詳情頁，When 頁面載入，Then 左側顯示 AI 洞察面板，從 `GET /api/crm/deals/{id}/ai-entries` 拉取資料
  - Given deal 有 1+ 筆 debrief entry，When 面板載入，Then 顯示「關鍵決策」區塊，按時間倒序列出所有 debrief 萃取的決策
  - Given deal 有 1+ 筆 commitment entry，When 面板載入，Then 顯示「承諾追蹤」區塊，分為「我方承諾」和「客戶承諾」兩組，每項顯示內容、截止日、完成狀態
  - Given deal 有 1+ 筆 debrief entry 含客戶顧慮，When 面板載入，Then 顯示「客戶顧慮」區塊，彙整歷次顧慮
  - Given deal 有最近一筆 debrief，When 面板載入，Then 顯示「Deal 摘要」區塊，內容為最新 debrief 的階段建議 + 下一步行動
  - Given deal 尚無任何 debrief entry，When 面板載入，Then 顯示引導文字「完成第一次商談並記錄活動後，AI 洞察將在這裡累積」
  - **承諾事項追蹤**（從 P1 提升到 P0）：
  - Given 承諾事項顯示在洞察面板，When 使用者點擊 checkbox，Then 承諾狀態更新為「已完成」（`PATCH /api/crm/commitments/{id}`），面板即時刷新
  - Given 承諾事項超過建議期限且未完成，When 面板載入，Then 該事項標示紅色「逾期」標籤
  - Given 承諾事項被標記完成，When 面板刷新，Then 完成的事項移到底部「已完成」摺疊區，不從面板消失
  - **活動時間軸內嵌 debrief**：
  - Given Activity（會議/Demo/電話）有對應 debrief entry，When 時間軸顯示該 Activity，Then Activity 下方顯示可展開的 AI debrief 摘要（預設收合，僅顯示「AI 分析 ▸」標籤）
  - Given 使用者點擊「AI 分析 ▸」，When 展開，Then 顯示該次 debrief 的關鍵決策和下一步行動（不是完整 debrief，是精簡版）
  - Given Activity 沒有對應 debrief entry（例如備忘類型），When 時間軸顯示，Then 不顯示「AI 分析」標籤
  - **後端 API**：
  - Given `GET /api/crm/deals/{id}/ai-entries`，When 呼叫，Then 回傳該 deal entity 上所有 crm_debrief 和 crm_commitment entries，按 created_at 排序
  - Given `PATCH /api/crm/commitments/{id}`，When 呼叫並傳入 `{status: "done"}`，Then 更新該 commitment entry 的 metadata.status，回傳更新後的 entry

---

### P1（應該有）

#### 相似案例推薦（Enhanced）

- **描述**：當 ontology 中累積足夠的已結案 deal 資料時，AI 可以找出相似案例並分析成敗因素。相似度基於：產業、公司規模、案子類型、金額區間
- **相似度匹配維度**：

| 維度 | 權重 | 說明 |
|------|------|------|
| 產業 | 高 | 同產業的銷售模式最相近 |
| 案子類型 | 高 | 一次性專案 vs 顧問合約，打法完全不同 |
| 公司規模 | 中 | 規模影響決策流程和預算 |
| 金額區間 | 低 | 參考用，不做精確匹配 |

- **Acceptance Criteria**：
  - Given 已結案 deal < 5 筆，When briefing 嘗試生成相似案例，Then 跳過此區塊，不報錯
  - Given 已結案 deal ≥ 5 筆，When briefing 生成，Then AI 從已結案 deal 中找出最相似的 1-3 筆，顯示：案例摘要、成交/流失原因、可借鑑的做法
  - Given 相似案例中有成交也有流失，When 顯示，Then 兩種都顯示，讓使用者同時看到正面和負面參考
  - Given 相似案例推薦結果，When 使用者認為不準確，When 點「這個不相關」，Then 標記排除，未來不再推薦該配對

#### 每週 Pipeline Review 摘要

- **描述**：每週自動生成一份 pipeline 健康度報告，涵蓋本週動態、下週建議、趨勢觀察
- **報告內容**：
  - 本週動態：新增 deal、階段推進、成交、流失
  - 下週建議：哪些 deal 需要重點跟進、哪些承諾事項即將到期
  - 趨勢觀察：平均成交週期變化、各階段轉換率（資料夠多時）
  - 亮點與風險：表現最好的 deal、最危險的 deal
- **Acceptance Criteria**：
  - Given 使用者進入客戶 tab，When 是新的一週（週一首次進入），Then 顯示上週摘要通知，可展開查看完整報告
  - Given 週報生成，When 使用者查看，Then 報告包含上述四個區塊
  - Given 本週無任何 deal 活動，When 生成週報，Then 摘要顯示「本週無活動」+ 強調需要跟進的 deal

#### ~~Debrief 承諾事項追蹤~~ → 已提升至 P0（v0.3）

> v0.3 決策：承諾事項追蹤是 AI 洞察持久展示的核心組件，不能等到 P1。已移至 P0「Deal 智能面板」需求中。

#### 一鍵開聊：Deal 策略討論

> v0.3 備註：此功能與 P0「對話式 Briefing」高度重疊。P0 的對話式 Briefing 已支援多輪追問（最多 8 輪），涵蓋策略討論的主要場景。P1 可評估是否需要額外的「純討論」入口，或直接由 Briefing 對話承擔。

- **描述**：復用行銷模組的 Local Helper 架構，在 Deal 詳情頁提供「討論策略」入口，AI 帶入完整 deal context 進行多輪對話
- **可討論的面向**：
  - 「這個客戶可能的預算範圍？」
  - 「如何回應客戶的價格顧慮？」
  - 「這個 deal 卡在報價階段，怎麼推進？」
  - 「幫我模擬一下客戶可能的反對意見」
- **Acceptance Criteria**：
  - Given 使用者在 Deal 詳情頁按「討論策略」，When 對話視窗開啟，Then 自動帶入 deal 完整 context（公司、所有 Activity、當前階段、歷史 briefing/debrief + AI 洞察面板資料）
  - Given 對話進行中，When AI 提出建議，Then 可透過「套用」按鈕將建議寫回 deal 備忘或承諾事項
  - Given Local Helper 不可用，When 使用者按「討論策略」，Then 顯示啟動 helper 的引導（同行銷模組降級行為）

---

#### Briefing 外部資訊搜尋（WebSearch）

- **描述**：Briefing 頁面提供「搜尋外部資訊」按鈕，使用者按下後 AI 搜尋客戶公司最新新聞、產業趨勢、人事異動，補充到 briefing 中。適用於較大型或有公開資訊的客戶；小型客戶可能搜不到內容
- **搜尋範圍**：公司最近新聞、產品/服務動態、人事異動、所屬產業趨勢
- **Acceptance Criteria**：
  - Given briefing 已生成（P0 版本），When 使用者按「搜尋外部資訊」，Then AI 執行 WebSearch 並在 briefing 中新增「外部動態」區塊
  - Given WebSearch 無相關結果（小型公司），When 搜尋完成，Then 顯示「未找到近期公開資訊」，不報錯
  - Given 同一公司 24 小時內已搜尋過，When 再次按搜尋，Then 使用快取結果，旁邊顯示「上次搜尋時間」，使用者可按「強制重新搜尋」

#### Follow-up 語氣偏好設定

- **描述**：使用者可設定 follow-up 草稿的語氣偏好，讓 AI 產出更符合個人風格的訊息。提供預設選項 + 自訂描述
- **語氣選項**：
  - 正式專業（適合大企業、初次接觸）
  - 友善專業（適合中小企業、熟悉的客戶）← 預設
  - 輕鬆親切（適合長期合作、關係好的客戶）
  - 自訂（使用者貼上自己的風格描述）
- **Acceptance Criteria**：
  - Given 使用者進入 CRM 設定頁，When 查看語氣偏好，Then 看到四個選項，預設選中「友善專業」
  - Given 使用者選擇「自訂」，When 填入風格描述並儲存，Then 後續所有 follow-up 草稿使用該風格
  - Given 使用者修改語氣偏好，When 下次 debrief 生成 follow-up 草稿，Then 使用新的語氣設定
  - Given 使用者隨著更多商談累積經驗，When 調整語氣偏好，Then 立即生效，不影響歷史草稿

---

### P2（可以有）

#### AI 從會議錄影/錄音萃取 Activity

- **描述**：使用者上傳視訊會議錄影或錄音檔，AI 自動轉錄並萃取重點，生成 Activity 摘要
- **Acceptance Criteria**：
  - Given 使用者上傳會議錄影/錄音，When AI 處理完成，Then 自動生成 Activity 摘要，使用者審核後儲存
  - Given 錄影檔案 > 2 小時，When 上傳，Then 提示「檔案較大，處理需要較長時間」

#### 跨 Deal 分析

- **描述**：選擇多個 deal 進行比較分析——為什麼有些成交有些流失、各來源的成交率差異
- **Acceptance Criteria**：
  - Given 使用者選擇 3+ 個已結案 deal，When 執行跨案分析，Then AI 產出比較報告：共同因素、差異點、改善建議

#### LINE 通知整合

- **描述**：將 Deal Health 的重要提醒推送到使用者的 LINE
- **Acceptance Criteria**：
  - Given 使用者綁定 LINE 通知，When 有過期承諾事項或嚴重停滯，Then 推送 LINE 訊息提醒

#### 結案回顧（Deal Retrospective）

- **描述**：Deal 進入「結案」狀態時，AI 自動觸發結案回顧——分析整個 deal 的成敗因素，寫回 ontology，充實相似案例庫
- **Acceptance Criteria**：
  - Given deal 漏斗階段變更為「結案」，When 狀態更新完成，Then 提示使用者進行結案回顧
  - Given 使用者啟動結案回顧，When AI 分析完成，Then 產出：成交/流失原因、關鍵轉折點、可複製的做法/應避免的做法
  - Given 回顧完成，When 寫回 ZenOS，Then 成為相似案例推薦（P1）的資料來源

---

## 資料模型

### AI 產出的資料如何存放

| AI 產出 | 存放方式 | 說明 |
|---------|---------|------|
| Briefing | ZenOS entry（掛在 deal entity） | type: `crm_briefing`，每次生成存一筆，保留歷史 |
| Debrief | ZenOS entry（掛在 deal entity） | type: `crm_debrief`，跟隨 Activity 一一對應 |
| 承諾事項 | ZenOS entry（掛在 deal entity） | type: `crm_commitment`，含 owner / deadline / status（**P0 可追蹤**） |
| Follow-up 草稿 | Debrief entry 的子欄位 | 不獨立存放，屬於 debrief 的一部分 |
| Deal Health 洞察 | 即時計算，不持久化 | 每次載入頁面時根據當前資料計算 |
| 週報 | ZenOS document（掛在 CRM 模組） | type: `crm_weekly_review`，每週一份 |

### AI Entries 的前端讀取路徑（v0.3 新增）

v0.2 只定義了 AI 產出的寫入路徑（helper → MCP → ZenOS entry），但**沒有定義前端如何讀取和展示**。v0.3 補齊：

| 前端元件 | 讀取 API | 顯示內容 |
|---------|---------|---------|
| AI 洞察面板 | `GET /api/crm/deals/{id}/ai-entries` | 彙整所有 debrief 的關鍵決策、客戶顧慮 + commitment 追蹤 |
| 活動時間軸 | 同上（按 activity_id 匹配 debrief entry） | 每筆 Activity 下方可展開對應 debrief 摘要 |
| Briefing context pack | 同上 | 歷次 debrief 摘要 + 未完成 commitment 作為 briefing 輸入 |

**`GET /api/crm/deals/{id}/ai-entries` 回傳結構**：

```json
{
  "debriefs": [
    {
      "id": "entry-xxx",
      "created_at": "2026-04-12T10:00:00Z",
      "activity_id": "act-yyy",
      "metadata": {
        "key_decisions": ["決策A", "決策B"],
        "customer_concerns": ["顧慮X"],
        "next_steps": ["下一步1"],
        "stage_recommendation": "建議推進到提案報價",
        "follow_up": {
          "line": "...",
          "email": {"subject": "...", "body": "..."}
        }
      }
    }
  ],
  "commitments": [
    {
      "id": "entry-zzz",
      "created_at": "2026-04-12T10:00:00Z",
      "metadata": {
        "content": "提供報價單",
        "owner": "us",
        "deadline": "2026-04-19",
        "status": "open"
      }
    }
  ]
}
```

### 與 SPEC-crm-core 的關係

本 spec 基於 SPEC-crm-core 的資料模型。不新增 CRM schema 的 table，但需要一項 schema 變更：`crm.deals` 新增 `zenos_entity_id text` 欄位（同 companies/contacts 已有的 bridge pattern）。

所有 AI 產出透過 ZenOS ontology（entry）存放，掛載在 deal entity 上。

**Deal entity bridge（ADR-037 決策 1）**：建立 deal 時自動橋接為 ZenOS entity（type: `deal`），掛在公司 entity 之下（relationship: PART_OF）。這推翻了 ADR-011 決策 2（原本決定 Deal 不橋接）。推翻理由：AI 產出需要掛載在 entity 上，且相似案例推薦需要跨 deal 查詢 ontology。Deal 已從「暫態銷售事件」升級為「需要累積知識的業務對象」。

---

## Spec 相容性

| 文件 | 關係 | 處理 |
|------|------|------|
| **SPEC-crm-core** | 依賴 | 本 spec 的所有功能建立在 CRM Core 之上。新增 Deal entity bridge（ADR-037 推翻 ADR-011 決策 2），需在 `crm.deals` 加 `zenos_entity_id` 欄位 |
| **SPEC-marketing-automation** | 共用架構 | 復用 Local Helper bridge、一鍵開聊（Auto Context Launch）、AI 對話視窗 7 狀態機、SSE 串流 event types、capability probe、權限白名單機制。CRM 和行銷的 AI 對話走同一套 helper |
| **ADR-034 Web Cowork Local Helper Bridge** | 已銜接 | CRM 的 AI 對話使用相同的 helper 架構，不需修改 helper server |
| **ADR-037 CRM Intelligence 架構** | 本 spec 的技術決策 | Deal type 命名、Local Helper 復用策略、AI 產出存放方式、context pack 結構、承諾提醒機制 |
| **ADR-011 CRM 模組架構** | 部分推翻 | ADR-011 決策 2「Deal 不橋接 entity」被 ADR-037 決策 1 推翻。Deal 現在橋接為 ZenOS entity（type: deal） |
| **SPEC-zenos-core** | 無衝突 | CRM Intelligence 屬於 Application Layer，使用 Core 的 Knowledge Layer |

---

## 明確不包含

- **Email 發送整合**：不接 Gmail / Outlook API 自動寄信（v1 用複製貼上就好）
- **LINE Bot 整合**：不做 LINE 自動發送（v1 用複製貼上，P2 再評估通知）
- **會議自動排程**：不接 Google Calendar / Outlook Calendar
- **Lead Scoring 評分模型**：中小企業 deal 量太少，統計評分沒意義。用 AI 定性分析取代定量評分
- **自動撥打電話 / 錄音轉錄**：隱私和法規風險，且使用者以視訊為主
- **Salesforce / HubSpot 同步**：不做外部 CRM 整合

---

## 已決定的設計決策

| # | 問題 | 決定 | 理由 |
|---|------|------|------|
| 1 | Deal 橋接時機 | 建立 deal 時自動橋接為 ZenOS entity（type: deal） | 與公司/聯絡人一致，且 AI 產出需要掛載在 entity 上。SPEC-crm-core 的開放問題「商機是否橋接」同步解決 |
| 2 | Briefing WebSearch | P0 不做 WebSearch，P1 加「搜尋外部資訊」可選按鈕（24 小時快取） | 中小企業客戶公開資訊有限，P0 先聚焦內部 context |
| 3 | Follow-up 語氣 | P0 預設「友善專業」一套口吻，P1 加語氣偏好設定（4 種預設 + 自訂） | 零設定門檻先讓人用起來，隨商談經驗累積再微調 |
| 4 | 多人可見性 | 同 partner 下全部可見 | 小團隊需要透明共享，ZenOS 核心理念是所有 AI 共享同一套 context |
| 5 | 階段變更觸發治理 | P0 不觸發，P2 加結案回顧（Deal Retrospective） | 先跑通 CRM + AI，不過早綁自動化 |
| 6 | Dashboard tab 命名 | 維持「客戶」 | 「業務」有歧義，「客戶」直覺明確 |
| 7 | Deal entity type 命名 | `deal` | 不選 `opportunity`（Salesforce 術語，使用者不說）、不復用 `project`（語意完全不同，會污染查詢）。`deal` 貼近使用者說的「這筆案子」。詳見 ADR-037 |
| 8 | Briefing / Debrief 觸發方式 | Local Helper bridge（方案 b） | 復用行銷模組架構（ADR-034）：前端 → Local Helper → 本機 Claude CLI → MCP 讀取 ZenOS context → 生成 briefing/debrief → 寫回 ZenOS entry → 前端顯示。不需要 API key、不需要 server-side LLM 接入。詳見 ADR-037 |
| 9 | 承諾事項提醒機制 | P0 Dashboard-only，P1 不加被動通知，P2 隨 LINE 通知整合一起做 | 目標用戶每天看 Dashboard，Dashboard 洞察區已足夠。過早加通知會通知疲勞。詳見 ADR-037 |
| 10 | Deal 詳情頁佈局 | 雙欄佈局：左側 AI 洞察面板 + 右側活動時間軸 | AI 洞察必須持久可見，不能藏在按鈕後面。雙欄讓經營脈絡（左）和操作記錄（右）同時可見。詳見 ADR-037 決策 7 |
| 11 | Briefing 互動模式 | 對話式（復用 CoworkChatSheet），不再是單次觸發 | 單次生成太粗糙——使用者需要追問、調整重點、模擬情境。對話式讓 AI 真正成為「會前教練」。詳見 ADR-037 決策 8 |
| 12 | 承諾事項追蹤優先級 | 從 P1 提升到 P0 | 承諾追蹤是 AI 洞察面板的核心組件，沒有它面板就缺少可互動的內容。且承諾追蹤直接影響 Deal Health 計算和下次 briefing 的準確度 |

## 開放問題

無。
