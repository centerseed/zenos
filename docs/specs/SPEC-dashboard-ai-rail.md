---
type: SPEC
id: SPEC-dashboard-ai-rail
doc_id: SPEC-dashboard-ai-rail
title: Feature Spec: Dashboard AI Rail 與入口協議
status: draft
version: "0.1"
date: 2026-04-15
supersedes: null
l2_entity: TBD
created: 2026-04-15
updated: 2026-04-15
---

# Feature Spec: Dashboard AI Rail 與入口協議

## 背景與動機

ZenOS Dashboard 已在多個功能頁引入本機 AI 能力，但目前至少有兩種不同體驗：

1. 行銷頁把 AI 做成可討論、可寫回欄位的 cowork 視窗。
2. CRM 頁把 AI 做成 briefing / debrief 面板，以產出結果為主。

這兩者底層都連到同一個 Local Helper，但入口型態、狀態提示、設定方式、錯誤處理、續聊規則、寫回邏輯已開始分叉。結果是：

- 使用者不知道不同頁面的 AI 是否是同一套能力
- 每個頁面都各自定義 prompt、scope 與 helper UX，維護成本高
- 行銷頁雖然支援寫回，但寫回契約只存在頁面內部，不是 Dashboard 層級的正式協議

本 spec 的目的不是把所有頁面做成同一個畫面，而是定義**同一個 AI Rail shell + 同一份入口協議**。不同 function 頁面只需帶入不同的意圖、範圍與可寫回目標，就能讓使用者拿到一致的 AI 使用邏輯與自動注入的 ZenOS knowledge 能力。

## 目標

1. 使用者在任何 function 頁面看到的是同一種 AI Rail 互動邏輯。
2. 每個入口都可自動帶入對應的 ZenOS scope，而不是讓使用者手動補背景。
3. 行銷頁討論後可直接、安全地寫回行銷設定與 prompt draft。
4. CRM 頁保留 artifact 型 AI 流程，不強迫使用欄位寫回模式。
5. prompt、scope、context pack、writeback target 變成正式契約，而不是散落在頁面內的字串拼接。

## 非目標

- 不在本 spec 重新定義 Local Helper server API。
- 不在本 spec 定義新的雲端 LLM 執行架構；仍沿用本機 helper + 本機 Claude CLI。
- 不要求 CRM 與行銷使用完全相同的內容區塊或文案。
- 不在本 spec 定義各模組 skill 內容本身；只定義 Dashboard 如何掛載它們。

## 核心原則

1. **統一 shell，不統一意圖。**
   CRM briefing 與 marketing strategy 可以是不同任務，但必須走同一個 rail shell。
2. **scope 是結構化資料，不是 prompt 暗示。**
   workspace / project / product / entity / campaign / deal 必須以結構化欄位傳遞。
3. **plain text 不能直接寫回。**
   任何可寫回流程都必須經過 structured result + diff preview + 使用者確認。
4. **每個入口都必須宣告自己的 write boundary。**
   AI 不得跨出入口允許的 write target。
5. **模組差異透過 preset 表達，不透過複製一套新 UI。**

## 名詞定義

### AI Rail

Dashboard 內所有 AI 入口共用的 shell。包含：

- rail / drawer 容器
- connector 狀態
- helper health check
- capability / permission / error 顯示
- streaming、cancel、retry、resume
- prompt / context 預覽
- structured result 的 preview 與 apply gate

### Entry Preset

某個頁面或某個欄位進入 AI Rail 時提供的設定物件。它決定這次 AI 對話的：

- 意圖
- scope
- 建議 skill
- prompt builder
- 啟動方式
- 續聊規則
- 可寫回目標

### Scope Envelope

每次進入 rail 時一起送出的 ZenOS 範圍描述。至少支援：

- `workspace_id`
- `project`
- `product_id`
- `entity_ids`
- `campaign_id`
- `deal_id`
- `scope_label`

### Mode

AI Rail 只允許三種模式：

- `chat`: 自由討論，不提供直接寫回
- `apply`: 討論後可產出 structured result，允許套用到明確欄位
- `artifact`: 目標是生成一份結果物，不提供欄位套用 CTA

## 共同入口協議

每個 AI 入口都必須提供 `CopilotEntryConfig`。欄位名稱可依實作語言調整，但語義不得缺漏。

```ts
type CopilotEntryConfig = {
  intent_id: string
  title: string
  description?: string
  mode: "chat" | "apply" | "artifact"
  launch_behavior: "manual" | "auto_start"
  session_policy: "scoped_resume" | "ephemeral"
  suggested_skill?: string
  scope: {
    workspace_id?: string
    project?: string
    product_id?: string
    entity_ids?: string[]
    campaign_id?: string
    deal_id?: string
    scope_label: string
  }
  context_pack: Record<string, unknown>
  write_targets?: string[]
  build_prompt: (input: string) => string
  parse_structured_result?: (raw: string) => StructuredResult | null
  on_apply?: (result: StructuredResult) => Promise<void>
}
```

### StructuredResult

`mode=apply` 的入口，AI 最終輸出必須可被解析為下列邏輯結構：

```ts
type StructuredResult = {
  target: string
  value: unknown
  summary?: string
  missing_keys?: string[]
}
```

規則：

- `target` 必須落在該入口宣告的 `write_targets` 內。
- `value` 必須符合該 target 的 schema。
- `missing_keys` 非空時，不得直接進入 apply。
- shell 必須保留 AI 的自然語言回覆，但不得用自然語言直接寫回。

## 共用 AI Rail UX

### 版面規則

- 桌機（`>=1024px`）必須使用右側 AI Rail。
- 手機（`<1024px`）必須使用全高 Drawer。
- CRM 與行銷不得各自發展成完全不同的容器型態。

### Header 必備資訊

每次開啟 rail，header 必須顯示：

- 入口標題
- 當前 `scope_label`
- connector 狀態
- AI 對話狀態
- 規則版本 / redaction version（若 capability 有回傳）

### 狀態機

所有頁面共用同一套狀態名稱：

- `idle`
- `loading`
- `streaming`
- `awaiting-local-approval`
- `apply-ready`
- `applying`
- `error`

任何 function 頁面不得自創等義的新狀態名稱。

### 共用控制

所有 rail 必須支援：

- health check
- capability probe 顯示
- local permission request / result 顯示
- cancel
- retry last turn
- resume（若 `session_policy=scoped_resume`）
- connector diagnostics

## 需求（含優先級與對應驗收）

### P0-1（R1）Shared AI Rail Shell

Dashboard 內所有 AI 入口必須使用同一個 AI Rail shell，不得由頁面各自維護不同的 helper UX。

AC-AIR-01:
- Given 使用者在 CRM 或行銷頁開啟 AI  
  When rail 顯示  
  Then header、狀態名稱、connector 狀態、cancel/retry/diagnostics 的互動規則必須一致。

AC-AIR-02:
- Given helper 不可用  
  When 使用者從不同 function 頁面開啟 AI  
  Then 都必須看到同級的修復引導，不得一頁只有錯誤字串、另一頁才有可執行動作。

### P0-2（R2）Entry Preset 與 Scope Envelope 契約化

每個 AI 入口必須透過 `CopilotEntryConfig` 宣告意圖、scope、context pack、session policy、write target 與 prompt builder，不得在頁面內臨時拼接不透明 prompt 當作唯一協議。

AC-AIR-03:
- Given 任一 AI 入口  
  When 進入 rail  
  Then shell 必須拿到完整的 `intent_id`、`mode`、`scope`、`context_pack`、`build_prompt`。

AC-AIR-04:
- Given 同一頁的不同入口  
  When 使用者切換目標  
  Then 可更換 `intent_id` 與 `scope`，但 shell 本身不重新換一套 UI。

AC-AIR-05:
- Given scope 中有 `workspace_id/project/product_id/entity_ids`  
  When shell 組 prompt  
  Then 這些資訊必須以結構化 context envelope 注入，而不是只藏在自由文字敘述內。

### P0-3（R3）統一的 Session / Health / Permission 行為

Local Helper 的 health、capability、resume、permission timeout、cancel/retry 行為必須由共用 rail 管理，不得各頁自行實作不同版本。

AC-AIR-06:
- Given rail 開啟  
  When shell 初始化  
  Then 必須先做 health check，並在 UI 顯示 connector 狀態。

AC-AIR-07:
- Given helper 回傳 `capability_check`  
  When rail 收到事件  
  Then 必須顯示 MCP/skill 狀態與對應 warning。

AC-AIR-08:
- Given AI 觸發白名單外 tool  
  When helper 回傳 `permission_request`  
  Then UI 必須進入 `awaiting-local-approval`，並顯示等待本機確認。

AC-AIR-09:
- Given 某輪對話失敗  
  When UI 進入 `error`  
  Then 必須提供 retry，且不得丟失本輪以前已收到的內容。

### P0-4（R4）`mode=apply` 的寫回安全邊界

AI Rail 只有在 `mode=apply` 且 structured result 合法時，才可顯示 apply CTA。所有寫回都必須先經 diff preview，再由使用者確認。

AC-AIR-10:
- Given `mode=apply` 入口  
  When AI 只回傳自然語言、沒有可解析 structured result  
  Then UI 不得顯示 apply CTA。

AC-AIR-11:
- Given structured result 的 `target` 不在 `write_targets`  
  When shell 驗證  
  Then 必須拒絕套用並顯示錯誤。

AC-AIR-12:
- Given structured result 合法  
  When UI 顯示 apply preview  
  Then 必須至少顯示 target、before、after，且需由使用者手動點擊「套用」。

AC-AIR-13:
- Given 套用期間基準版本已變更  
  When shell 檢測到衝突  
  Then 必須顯示覆蓋確認或放棄，不得靜默覆蓋。

### P0-5（R5）行銷頁的單一 Rail 與可寫回目標

行銷頁必須改為同一個 AI Rail，欄位上的 AI 按鈕只負責切換目前 target，不得讓每個區塊看起來像獨立的 AI 系統。

P0 允許的行銷 write target 僅限：

- `marketing_strategy`
- `marketing_schedule`
- `marketing_topic`
- `marketing_style`
- `marketing_prompt_draft`
- `marketing_review_note`

規則：

- `marketing_prompt_draft` 只能更新 draft，不得直接發布。
- `marketing_review_note` 只能回填建議，不得直接執行 approve / reject / publish。
- writeback 必須走對應的頁面 adapter / API，不得由 shell 直接操作資料來源。

AC-AIR-14:
- Given 使用者在行銷頁的策略、主題、排程、文風、prompt 管理區點 AI  
  When rail 開啟  
  Then 必須進入同一個 rail shell，只切換當前 target 與 context。

AC-AIR-15:
- Given AI 產出 `marketing_prompt_draft`  
  When 使用者按套用  
  Then 只能更新 prompt draft，不能直接把版本發布為 latest。

AC-AIR-16:
- Given AI 產出 review 類建議  
  When 使用者查看結果  
  Then UI 只能提供回填建議或帶出建議，不得直接替使用者執行審核決策。

### P0-6（R6）CRM 頁的 Artifact 模式

CRM briefing / debrief 必須使用同一個 rail shell，但預設走 `mode=artifact`，不顯示欄位套用 CTA。

規則：

- briefing 可 `auto_start`
- debrief 可 `auto_start`
- 可提供 copy / save / reopen 等 artifact 動作
- 不使用 marketing 的 apply CTA 與 write-target preview

AC-AIR-17:
- Given 使用者在 CRM 按「準備下次會議」  
  When rail 開啟  
  Then 必須以 `mode=artifact` auto-start 第一輪生成。

AC-AIR-18:
- Given CRM briefing / debrief 完成  
  When 使用者查看  
  Then 可看到 copy / save 類動作，但不得出現「套用到欄位」。

AC-AIR-19:
- Given CRM 與行銷都使用 AI Rail  
  When 比較兩邊操作  
  Then shell 一致，但 CRM 的 artifact mode 與行銷的 apply mode 差異必須明確可理解。

### P0-7（R7）Prompt 與 Context 的組裝責任

prompt 不得散落在頁面中臨時拼接為唯一真相來源。每個入口必須透過 entry preset 的 `build_prompt()` 產生，shell 則負責組合標準 envelope。

標準 envelope 至少包含：

- rail metadata（`intent_id`, `mode`, `session_policy`）
- scope envelope
- context pack
- user input

AC-AIR-20:
- Given 某入口需要不同 prompt  
  When 頁面實作  
  Then 必須以 `build_prompt()` 或等價 registry 定義，而不是在 click handler 內直接散拼字串。

AC-AIR-21:
- Given shell 送出請求  
  When helper 收到 prompt  
  Then prompt 中必須可辨識 `intent_id`、scope、context pack 與 user input。

### P1-1（R8）跨頁一致的 Rail 啟動語言

不同 function 頁面的 AI 入口文案可以保留模組語意，但必須有一致的主語彙，讓使用者知道自己是在進入同一套 AI Rail。

建議規則：

- 頁面主入口：`AI 助手`
- 欄位入口：`帶這段進 AI`
- artifact 入口：`生成 AI 結果`

AC-AIR-22:
- Given 使用者從 CRM 或行銷進入 AI  
  When 比較入口  
  Then 能辨識這是同一套 AI Rail，而不是不同產品。

## 交付驗收邊界

- 至少需有一條共用 shell interaction test 覆蓋 `health -> capability -> stream -> error/retry`。
- 至少需有一條行銷 `mode=apply` interaction test 覆蓋 `structured_result -> diff preview -> apply success`。
- 至少需有一條 CRM `mode=artifact` interaction test 覆蓋 `auto_start -> first artifact -> follow-up artifact`。
- 若上述任一條未通過，不得宣稱 AI Rail 已完成跨模組收斂。

## 行銷頁的專屬補充規則

### 單一 Rail，不做多套 AI 視窗

- 行銷頁桌機版應以同一個右側 rail 為主。
- 策略、主題、排程、文風、prompt manager 上的按鈕只切換目前 target。
- 不得讓使用者感覺每個區塊各有一個獨立 AI。

### Prompt Draft 的治理

- AI 討論可以更新 `prompt draft`。
- `發布為最新版本` 必須是獨立的明確操作，不在 AI apply 內自動觸發。
- 若 draft 已在使用者對話期間變更，套用前必須做衝突檢查。

### 寫回後的可見性

- 策略 / 主題 / 排程 / 文風 / prompt draft 被套用後，頁面上對應區塊必須立即更新。
- 若 server 寫回失敗，rail 必須停在 `error`，並保留 AI 給出的結構化內容供重試。

## CRM 的專屬補充規則

- CRM 的 rail 雖共用 shell，但不負責直接修改 deal 欄位。
- CRM 的 AI 結果以 briefing / debrief / follow-up artifact 為主。
- 若未來 CRM 要支援「討論策略」或其他 writeback 功能，必須新增明確 write target，不得沿用 artifact mode 偷做 apply。

## 技術約束（給 Architect）

- 既有 `cowork-helper.ts` 必須升級為模組中立命名，不得保留 `marketing` 專屬 storage key 作為全域協議。
- CRM 與行銷都必須使用同一組 helper client API。
- rail shell 不得直接調用 marketing API / CRM API；寫回必須透過 entry preset 提供的 adapter。
- shell 可做通用驗證，但不得理解各模組的業務欄位細節。
- page-level preset 必須可被測試覆蓋；至少需驗證 target 白名單、structured result 驗證、衝突行為、artifact/apply mode 差異。

## 預期交付切片

此 spec 為跨模組交付，實作時必須至少拆成以下 slices：

1. 共用 `AI Rail shell` 與 helper client 對齊
2. 行銷頁改接 `Entry Preset + apply adapter`
3. CRM 頁改接 `Entry Preset + artifact mode`

若未建立 plan layer 管理上述切片，不得宣稱此 spec 已完整交付。

## 與既有規格關係

- `SPEC-marketing-automation`：保留行銷流程與欄位級 AI 的產品需求；其 shell / entry contract 需對齊本 spec。
- `SPEC-crm-intelligence`：保留 briefing / debrief 的 CRM 需求；其 rail UX 與 shell 行為需對齊本 spec。
- `ADR-034-web-cowork-local-helper-bridge`：沿用同一 Local Helper bridge。
- `ADR-037-crm-intelligence-architecture`：沿用「CRM 與行銷共用 helper 與對話基礎設施」的方向，但以本 spec 補齊 Dashboard 入口協議與 UI 邊界。

若 CRM / 行銷 spec 在 AI shell、狀態機、entry contract、writeback gate 上與本 spec 衝突，以本 spec 為準。

## Open Questions

1. 行銷頁桌機版是否要把 rail 做成常駐側欄，而不是每次點擊才展開？
2. `mode=chat` 是否需要支援「整理成 structured result」的二段式轉換，作為通用能力？
3. 是否需要把 `scope envelope` 原樣顯示給使用者，還是只顯示人類可讀的 `scope_label`？
