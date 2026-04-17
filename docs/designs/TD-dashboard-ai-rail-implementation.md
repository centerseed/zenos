---
type: TD
id: TD-dashboard-ai-rail-implementation
status: Draft
linked_spec: SPEC-dashboard-ai-rail
created: 2026-04-15
updated: 2026-04-15
---

# 技術設計：Dashboard AI Rail 實作

## 結論

這次不是再做第三套 AI UI，而是把已存在的兩套路徑重新收斂成：

1. 一個共用 `AI Rail shell`
2. 一份共用 `Entry Preset` / `Scope Envelope` 契約
3. 兩種上層模式
   - marketing = `mode=apply`
   - CRM = `mode=artifact`

實作上不走「把 `CrmAiPanel` 硬改成 `CoworkChatSheet`」這種直接貼 patch 的方式，因為兩邊的產品語意不同。正確做法是：

- 抽出 shell 層與 helper session/state machine
- 把 marketing 與 CRM 改成各自提供 preset / adapter
- 讓寫回邏輯留在模組側，不留在 shell 內

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-dashboard-ai-rail.md`
  - 發現：shared shell、`CopilotEntryConfig`、`mode=apply|artifact|chat`、`write_targets` 已定成正式協議，並有 `AC-AIR-*` 可對應 implementation。
- `docs/specs/SPEC-marketing-automation.md`
  - 發現：行銷原本已把 AI 定義成欄位級一鍵開聊、context pack、7 狀態機、structured apply flow；但沒有抽成 dashboard 共用協議。
- `docs/specs/SPEC-crm-intelligence.md`
  - 發現：CRM 明確要求復用行銷的 helper / state machine，但實作目前仍保有獨立 `CrmAiPanel` 邏輯。
- `docs/decisions/ADR-034-web-cowork-local-helper-bridge.md`
  - 發現：helper bridge、capability probe、permission_request/result、context 注入兩層模型都已定義，不需要另開新 helper protocol。
- `docs/decisions/ADR-037-crm-intelligence-architecture.md`
  - 發現：CRM 與行銷共用 helper / cowork-helper 客戶端 / 對話狀態機是已做出的架構決策，但目前前端仍未完全收斂。
- `dashboard/src/app/marketing/page.tsx`
  - 發現：`CoworkChatSheet` 已內建最完整的 shell 能力，但元件仍嵌在 page 檔內，且在同頁被多次掛載，造成「到處都是獨立 AI」的感受。
- `dashboard/src/app/clients/deals/[id]/CrmAiPanel.tsx`
  - 發現：CRM 有自己的 artifact UI，但 helper 事件只消化 `message/stderr/done/error`，未完整對齊 capability / permission / cancel endpoint。
- `dashboard/src/lib/cowork-helper.ts`
  - 發現：helper client 已足夠共用，但 storage key 仍以 `zenos.marketing.*` 命名，與 shared shell 方向衝突。

### 搜尋但未找到

- `docs/designs/` 中沒有專門定義 dashboard 級 shared copilot shell 的 TD。
- 現有 repo 中沒有獨立的 `dashboard/src/components/ai/` 或 `dashboard/src/lib/copilot/` 模組。

### 我不確定的事（明確標記）

- [未確認] 桌機版 AI Rail 是否最終要做成常駐側欄，還是仍由按鈕打開；本 TD 先以「單一右側 rail，可由頁面控制開關」為前提。
- [未確認] shared shell 是否要同時支援 `mode=chat` 的正式 landing page；本 TD 先只保證 marketing / CRM 兩條路徑。

### 結論

可以開始設計。  
核心不是新 helper，也不是新 prompt，而是前端結構重整與 entry contract 固化。

## 現況問題

### 1. `CoworkChatSheet` 被困在 marketing page

目前最完整的 shell 邏輯存在於 `dashboard/src/app/marketing/page.tsx` 內部：

- helper health
- capability / permission 事件
- 7-state state machine
- structured apply
- conflict detection
- diagnostics

問題不是能力不夠，而是它沒有被抽成 Dashboard 共用 primitive。

### 2. CRM artifact mode 沒有真正復用 shared shell

`CrmAiPanel.tsx` 雖然共用 `cowork-helper.ts`，但 UI 行為仍是獨立實作：

- 不處理 capability / permission 事件
- cancel 只 abort fetch，不走 helper cancel endpoint
- helper 設定 / diagnostics 不可見

這造成「底層同一個 helper，表層卻像兩個產品」。

### 3. 行銷頁的 AI 入口太分散

行銷頁現在在多個區塊各自 mount `CoworkChatSheet`：

- strategy
- schedule
- review
- style
- topic
- 全域入口

雖然它們共用同一套元件，但因為是多個實例，使用者感受仍像「每塊各有一個 AI」。

### 4. 寫回契約只存在頁面內部

行銷的 `target_field/value`、衝突檢查、寫回 adapter 只存在在 page local state 裡，不是 Dashboard 正式 contract。這會讓：

- 新頁面難以安全接入
- prompt / parser / apply 行為容易漂移
- prompt draft 的「只能寫 draft、不能 publish」缺少 dashboard 層保護

## 實作目標

### 1. Shared Shell

抽出一個可被 CRM / marketing 共用的 `CopilotRailShell`。

### 2. Entry Preset

每個入口只提供 preset，不直接操作 helper session。

### 3. Marketing 單一 Rail

marketing page 改為單一 rail instance，由各區塊按鈕切換 preset。

### 4. CRM Artifact Preset

CRM 保留 briefing / debrief 的 artifact 體驗，但外殼改為同一 shell。

## 目標架構

### 1. 模組切分

```text
dashboard/src/components/ai/
  CopilotRailShell.tsx
  CopilotRailView.tsx
  CopilotDiffPreview.tsx
  CopilotDiagnostics.tsx
  CopilotMessageList.tsx

dashboard/src/lib/copilot/
  types.ts
  state.ts
  envelope.ts
  structured-result.ts
  helper-session.ts

dashboard/src/app/marketing/
  copilot-presets.ts
  copilot-adapters.ts

dashboard/src/app/clients/deals/[id]/
  crm-copilot-presets.ts
```

說明：

- `components/ai/` 放 shell 與純 UI primitive
- `lib/copilot/` 放共用型別、狀態機、prompt envelope、structured result 驗證
- marketing / CRM 各自提供 preset builder 與 apply/save adapter

### 2. Shared Shell 責任

`CopilotRailShell` 只負責：

- helper health / diagnostics
- session start / continue / cancel
- capability / permission / error 顯示
- streaming messages
- retry / resume
- structured result 驗證與 diff preview 顯示
- 根據 `mode` 控制 CTA

`CopilotRailShell` 不負責：

- 組 business-specific prompt 文案
- 理解 strategy / schedule / prompt draft schema
- 直接 call marketing API / CRM API

### 3. Entry Preset 責任

每個 preset 負責：

- `intent_id`
- `title`
- `mode`
- `launch_behavior`
- `session_policy`
- `scope`
- `context_pack`
- `build_prompt()`
- `write_targets`
- `parse_structured_result()`（如有）
- `on_apply()` / `on_artifact_ready()`（如有）

### 4. Prompt Envelope

shell 發給 helper 的 prompt 不再是頁面自己拼接的裸字串，而是固定包一層 envelope：

```text
[AI_RAIL]
intent_id=...
mode=...
session_policy=...

[SCOPE]
workspace_id=...
project=...
product_id=...
entity_ids=...
campaign_id=...
deal_id=...
scope_label=...

[CONTEXT_PACK]
{...json...}

[USER_INPUT]
...
```

規則：

- shell 只包 envelope
- preset 的 `build_prompt()` 只處理該入口的 task framing
- helper 不解析 envelope；它仍只是透傳 prompt 給 Claude

### 5. Structured Result 契約

`mode=apply` 一律用共用 parser：

```ts
type StructuredResult = {
  target: string
  value: unknown
  summary?: string
  missing_keys?: string[]
}
```

marketing-specific parser 只做 schema validation：

- `marketing_strategy`
- `marketing_schedule`
- `marketing_topic`
- `marketing_style`
- `marketing_prompt_draft`
- `marketing_review_note`

如果 `target` 不合法或 `missing_keys` 非空：

- shell 顯示錯誤
- 不出現 apply CTA

### 6. Marketing 單一 Rail 設計

marketing page 改為頁面層只有一個 rail state：

```ts
const [activePreset, setActivePreset] = useState<CopilotEntryConfig | null>(null)
const [railOpen, setRailOpen] = useState(false)
```

各區塊 AI 按鈕只做：

1. 建立對應 preset
2. `setActivePreset(...)`
3. `setRailOpen(true)`

這樣效果是：

- 同一個 rail shell
- 同一組 session / diagnostics / status UI
- 不同區塊只切 scope / prompt / write target

### 7. Marketing Prompt Draft Adapter

`marketing_prompt_draft` 寫回必須走單獨 adapter：

```text
AI result -> parse -> diff preview -> on_apply()
  -> updateMarketingPromptDraft()
  -> refresh prompt SSOT state
```

硬規則：

- 只能改 draft content
- 不得在 apply 內呼叫 `publishMarketingPrompt`
- 若使用者要 publish，必須按原本 UI 的獨立 publish CTA

### 8. CRM Artifact Preset

CRM 的 preset 分兩種：

- `crm_briefing`
- `crm_debrief`

共通特性：

- `mode=artifact`
- `launch_behavior=auto_start`
- `session_policy=ephemeral` 或 deal-scoped resume
- 不提供 `write_targets`
- 結果走 `on_artifact_ready()`，由 CRM 頁面決定存檔 / copy / update local state

CRM 不使用 apply preview，但仍使用：

- shared header
- shared connector state
- shared error/retry/cancel
- shared diagnostics

## Session Policy

### `scoped_resume`

用於 marketing 欄位討論：

- conversation key = `page scope + target`
- 關閉 rail 再打開，可繼續同一段欄位討論
- 適合漸進式 refine strategy / style / prompt draft

### `ephemeral`

用於 CRM artifact：

- 以當前 briefing / debrief 任務為單位
- 關閉後不保證保留 session
- 保存的是 artifact，不是對話 session 本身

## Storage Key 調整

`dashboard/src/lib/cowork-helper.ts` 需從：

- `zenos.marketing.cowork.helperBaseUrl`
- `zenos.marketing.cowork.helperToken`
- `zenos.marketing.cowork.cwd`
- `zenos.marketing.cowork.model`

改為模組中立命名：

- `zenos.copilot.helperBaseUrl`
- `zenos.copilot.helperToken`
- `zenos.copilot.cwd`
- `zenos.copilot.model`

過渡策略：

- 先讀新 key
- 新 key 無值時回退讀舊 key
- 寫入一律寫新 key

## Spec Compliance Matrix

| AC | 需求 | 實作方式 | 主要檔案 | 驗證 |
|----|------|---------|---------|------|
| AC-AIR-01~02 | shared shell / shared fallback | 抽 `CopilotRailShell` 與共用 diagnostics UI | `dashboard/src/components/ai/CopilotRailShell.tsx` | vitest interaction |
| AC-AIR-03~05 | entry preset / scope envelope contract | 新增 `CopilotEntryConfig`、`envelope.ts`、preset builders | `dashboard/src/lib/copilot/types.ts`, `dashboard/src/lib/copilot/envelope.ts`, `dashboard/src/app/marketing/copilot-presets.ts`, `dashboard/src/app/clients/deals/[id]/crm-copilot-presets.ts` | unit tests |
| AC-AIR-06~09 | helper health / capability / permission / retry | shell 集中處理 helper events；CRM 不再自行實作 event 分支 | `dashboard/src/components/ai/CopilotRailShell.tsx`, `dashboard/src/lib/cowork-helper.ts` | vitest interaction |
| AC-AIR-10~13 | apply gate / diff / conflict | 共用 structured result parser + diff preview + conflict hook | `dashboard/src/lib/copilot/structured-result.ts`, `dashboard/src/components/ai/CopilotDiffPreview.tsx` | unit + interaction |
| AC-AIR-14 | marketing 單一 rail | marketing page 改為一個 mounted rail + active preset state | `dashboard/src/app/marketing/page.tsx` | page interaction test |
| AC-AIR-15 | prompt draft 只能改 draft | prompt draft adapter 只接 `updateMarketingPromptDraft()` | `dashboard/src/app/marketing/copilot-adapters.ts` | adapter test |
| AC-AIR-16 | review note 不直接執行審核 | review preset 僅回填建議，不觸發 review action | `dashboard/src/app/marketing/copilot-presets.ts` | interaction test |
| AC-AIR-17~19 | CRM artifact mode | CRM briefing/debrief 改吃 shared shell + artifact preset | `dashboard/src/app/clients/deals/[id]/CrmAiPanel.tsx`, `dashboard/src/app/clients/deals/[id]/crm-copilot-presets.ts` | behavior test |
| AC-AIR-20~21 | prompt builder / envelope | prompt 組裝從 page local 字串移到 preset builder | `dashboard/src/lib/copilot/envelope.ts`, marketing/CRM preset files | unit tests |
| AC-AIR-22 | 跨頁一致語言 | 收斂 rail header / CTA naming | `dashboard/src/components/ai/CopilotRailView.tsx`, page entry labels | visual / interaction review |

## 任務拆分

### D01. Copilot Foundation

- 新增 `dashboard/src/lib/copilot/*`
- 新增 `dashboard/src/components/ai/*`
- `cowork-helper.ts` storage key 中立化
- 抽共用 state machine / envelope / structured result utilities

### D02. Marketing Rail Consolidation

- `CoworkChatSheet` 從 `marketing/page.tsx` 抽離
- 行銷頁改為單一 rail instance
- strategy / schedule / topic / style / review / prompt SSOT 全部改走 preset
- prompt draft 寫回 adapter 補測試

### D03. CRM Rail Adoption

- `CrmAiPanel` 改接 shared shell
- briefing / debrief 轉成 artifact preset
- 接回 CRM 既有 save / copy / onStreamComplete 行為
- 補 capability / permission / cancel / retry 一致行為

### D04. Regression / Contract Alignment

- 更新 marketing / CRM interaction tests
- 新增 copilot foundation 單元測試
- 補 shared shell 的 error / permission / diff preview 測試

## Done Criteria

| # | Criteria |
|---|----------|
| 1 | Dashboard 內存在獨立的 shared AI Rail shell，不再把主要 shell 邏輯埋在 `marketing/page.tsx` |
| 2 | `cowork-helper.ts` 的 storage key 已改為模組中立命名，且保留舊 key 讀取相容 |
| 3 | marketing page 在桌機上只 mount 一個 rail instance；各區塊 AI 按鈕只切 preset，不再各自持有一套 shell state |
| 4 | marketing `prompt draft` 的 AI 寫回只能更新 draft，不會直接 publish |
| 5 | CRM briefing / debrief 使用 shared shell，並支援與 marketing 一致的 connector / capability / permission / retry UX |
| 6 | `mode=apply` 與 `mode=artifact` 的 CTA 明確分流；CRM 不會出現 apply CTA，marketing 的 apply 需要 structured result + diff preview |
| 7 | 至少有一條共用 shell interaction test、一條 marketing apply test、一條 CRM artifact test 通過 |
| 8 | 所有 AC-AIR-* 均能在本 TD 的 compliance matrix 找到實作對應，不存在無 owner 的 AC |

## 測試矩陣

### Foundation

- `dashboard/src/lib/copilot/*.test.ts`
  - envelope 組裝
  - session policy key 計算
  - structured result 驗證
  - storage key fallback

### Marketing

- `dashboard/src/app/marketing/cowork-chat.test.tsx`
  - shared shell 仍能顯示 capability / diagnostics / error / retry
- 新增或更新 `marketing` interaction test
  - strategy preset -> structured result -> diff -> apply
  - prompt draft preset -> apply -> draft update only
  - review preset -> no direct approve/reject side effect

### CRM

- `dashboard/src/app/clients/deals/[id]/CrmAiPanel.behavior.test.tsx`
  - auto-start first artifact
  - follow-up artifact turn
  - helper stderr / non-zero exit -> visible error + retry
  - capability / permission event 對 UI 可見

## 風險

### 1. 最大風險

marketing page 目前耦合過深，`CoworkChatSheet` 不是純元件，而是混著 marketing local types、parse、apply、diagnostics。抽離時最容易出現：

- 邏輯被搬散
- 測試大面積失效
- rail 看似共用，實際仍殘留 marketing 假設

### 2. 控制策略

- 先抽 foundation，再接 marketing，再接 CRM
- shell 只抽共用行為，不先碰 marketing 的 prompt 細節
- preset / adapter 採 page-owned 模式，避免 shared shell 滲入 business logic

### 3. 不做的事

- 不在這輪新增 helper server API
- 不在這輪做 `mode=chat` 的新 dashboard landing
- 不在這輪改 CRM / marketing skill 內容本身
- 不在這輪把 AI rail 推廣到 setup / tasks / knowledge-map 等其他頁

## Resume Point

下一步應建立 implementation plan / action layer tasks。  
第一張要開工的是 `D01 Copilot Foundation`，因為它會決定 marketing 與 CRM 都依賴的 shell contract、storage key、structured result parser 與 session policy。
