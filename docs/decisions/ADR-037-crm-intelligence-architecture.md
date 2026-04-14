---
type: ADR
id: ADR-037
status: Draft
ontology_entity: crm-客戶管理
created: 2026-04-14
updated: 2026-04-14
supersedes: null
changelog: "v0.3: 新增決策 7（雙欄佈局）、8（對話式 Briefing）、9（AI Entries API）"
---

# ADR-037: CRM Intelligence 模組技術架構

## Context

SPEC-crm-intelligence 定義了三個 AI 場景（Briefing、Debrief、Deal Health），需要在現有 CRM Core 之上加入 AI 智慧層。有四個核心技術決策需要做：

1. **Deal 是否橋接為 ZenOS entity，以及 type 命名**：ADR-011 決定 Deal 不橋接，但 SPEC-crm-intelligence 要求 AI 產出掛載在 Deal entity 上，必須推翻 ADR-011 的決策 2。
2. **AI 觸發走哪條路徑**：後端 API 直連 LLM vs. Local Helper bridge（用戶明確要求走 Local Helper，復用行銷模組 pattern）。
3. **AI 產出如何存放**：CRM schema 新增 table vs. ZenOS entry/document。
4. **承諾事項提醒機制**：P0 Dashboard-only vs. P1 加被動通知。

同時，行銷模組已建立 Local Helper bridge（ADR-034）和完整的 AI 對話視窗狀態機（SPEC-marketing-automation），CRM Intelligence 應最大程度復用這些基礎設施。

## Decision

### 決策 1：Deal 橋接為 ZenOS entity，type 命名為 `deal`

**推翻 ADR-011 決策 2。** ADR-011 認為 Deal 是「短暫銷售事件」不適合 entity 化。但 SPEC-crm-intelligence 改變了前提——AI 產出（briefing、debrief、承諾事項）需要掛載在 entity 上，且相似案例推薦需要跨 deal 查詢 ontology。Deal 已從「暫態追蹤」升級為「需要累積知識的業務對象」。

**type 命名選 `deal`，不選 `opportunity` 或 `project`。**

- `project` 已被 ZenOS Core 使用（EntityType.PROJECT），語意完全不同——project 是內部專案，deal 是外部銷售機會。復用 project 會造成語意混亂，查詢時無法區分。
- `opportunity` 是 Salesforce 術語，但本產品面向的是中小企業 AI 顧問團隊，使用者說的是「這筆案子」「這個 deal」，不會說「這個 opportunity」。type 命名應貼近使用者心智模型。
- `deal` 精確對應 CRM 領域語意，且與 SPEC-crm-core 的 Deal 概念一致。

**實作影響：**

- DB migration：`zenos.entities` 的 `chk_entities_type` 約束新增 `'deal'`
- Domain model：`EntityType` enum 新增 `DEAL = "deal"`
- Application layer：`CrmService.create_deal()` 同步建立 ZenOS entity（type: deal），掛在公司 entity 之下（relationship: PART_OF）
- `crm.deals` 新增 `zenos_entity_id text` 欄位（同 companies/contacts 的 bridge pattern）

### 決策 2：AI 觸發走 Local Helper，復用行銷模組的完整架構

**選擇方案 (b)：前端透過 Local Helper bridge 呼叫本機 Claude CLI，AI 讀取 ZenOS context 後生成 briefing/debrief，寫回 ZenOS entry，Dashboard 顯示結果。**

不選方案 (a)（後端 API 直連 LLM），原因：

| 考量 | Local Helper (b) | 後端 API (a) |
|------|-----------------|-------------|
| API key 管理 | 不需要，用使用者已有的 Claude 訂閱 | 需要 server-side API key，成本由產品方承擔 |
| MCP context 存取 | 天然可用，helper 啟動 CLI 時自帶 MCP config | 需要另建 server-side MCP client |
| Skill 復用 | 直接用 `.claude/` 下的 CRM skill 定義 | 需要把 skill 邏輯翻譯為 server-side prompt |
| 與行銷模組一致 | 共用 helper、cowork-helper.ts、AI 對話狀態機 | 分叉兩套 AI 架構 |
| 離線風險 | helper 未啟動時需降級 | 後端始終可用 |

**復用清單——從行銷模組直接拿來用，不需重寫：**

| 元件 | 來源 | CRM 需要改的 |
|------|------|-------------|
| `tools/claude-cowork-helper/server.mjs` | 行銷模組 | 新增 CRM skill 到 `EXPECTED_SKILLS` 檢查清單 |
| `dashboard/src/lib/cowork-helper.ts` | 行銷模組 | 不改，CRM 直接 import 使用 |
| SSE 串流 event types | ADR-034 定義 | 不改，CRM 用相同的 event schema |
| AI 對話視窗狀態機 | SPEC-marketing-automation | 不改，CRM 對話視窗用相同的 7 狀態轉移 |
| Capability probe | ADR-034 定義 | 不改，CRM session 用同一個 probe 機制 |
| 權限白名單 | `.claude/settings.json` | 新增 CRM 相關 MCP tool 到 allowedTools |
| Redaction rules | `dashboard/src/config/ai-redaction-rules.ts` | 不改（CRM 無額外敏感欄位） |

**CRM 需要新建的部分：**

- CRM skill 定義：`.claude/skills/crm-briefing/` 和 `.claude/skills/crm-debrief/`（或合併為 `.claude/skills/crm-intelligence/`）
- CRM context pack 結構（見決策 4）
- Dashboard CRM 頁面中的 AI 互動區塊

### 決策 3：AI 產出存放為 ZenOS entry，掛載在 deal entity 上

AI 產出不放 CRM schema，放 ZenOS ontology 的 entry/document 模型。理由：

- 與行銷模組一致（行銷的策略、情報、文案都存 ZenOS）
- entry 天然掛載在 entity 上，支援 ontology 層面的關聯查詢
- AI 產出本質上是「知識」不是「交易紀錄」，放 ontology 比放 CRM schema 更合適
- 未來相似案例推薦需要跨 deal 搜尋 ontology，entry 已有搜尋基礎設施

**存放對應：**

| AI 產出 | ZenOS 型態 | type 值 | 掛載於 |
|---------|-----------|---------|-------|
| Briefing | entry | `crm_briefing` | deal entity |
| Debrief | entry | `crm_debrief` | deal entity |
| 承諾事項 | entry | `crm_commitment` | deal entity |
| Follow-up 草稿 | debrief entry 的子欄位 | -- | 隨 debrief |
| Deal Health | 即時計算 | -- | 不持久化 |
| 週報（P1） | document | `crm_weekly_review` | CRM 模組 entity |

**entry 的 metadata 結構擴充：**

Briefing entry 的 `metadata` JSON 存放結構化區塊（客戶背景、互動回顧、產品現況、相似案例、本次建議），前端依此渲染可展開收合的區塊。

Debrief entry 的 `metadata` JSON 存放：關鍵決策、客戶顧慮、承諾事項、階段建議、下一步行動、follow-up 草稿（LINE + Email 兩個版本）。

Commitment entry 的 `metadata` JSON 存放：內容、owner（我方/客戶）、deadline、status（open/done）。

### 決策 4：CRM Context Pack 結構

CRM 的 AI 對話需要專屬的 context pack，類似行銷模組的欄位級 context pack，但結構不同。

**Briefing context pack（前端組裝，送入 helper prompt）：**

```json
{
  "scene": "briefing",
  "deal_id": "deal-xxx",
  "company": {
    "name": "公司名稱",
    "industry": "產業",
    "size_range": "規模",
    "region": "地區"
  },
  "deal": {
    "title": "案子標題",
    "funnel_stage": "提案報價",
    "deal_type": "顧問合約",
    "source_type": "轉介紹",
    "amount_twd": 500000,
    "scope_description": "...",
    "deliverables": ["..."]
  },
  "activities_summary": "最近 N 筆活動的摘要（≤1500 字）",
  "contacts": [{ "name": "...", "title": "..." }],
  "previous_briefings_count": 2,
  "suggested_skill": "/crm-briefing"
}
```

**Debrief context pack：**

```json
{
  "scene": "debrief",
  "deal_id": "deal-xxx",
  "company_name": "公司名稱",
  "deal_title": "案子標題",
  "funnel_stage": "需求訪談",
  "activity": {
    "type": "會議",
    "summary": "使用者剛寫的完整 Activity 摘要"
  },
  "recent_commitments": ["上次承諾事項..."],
  "suggested_skill": "/crm-debrief"
}
```

Context pack 上限 2000 字（同行銷），超過按優先序截斷：activity.summary > activities_summary > company > deal。

### 決策 5：承諾事項提醒機制——P0 Dashboard-only，P1 不加被動通知

P0 承諾事項只在 Dashboard Deal Health 洞察區顯示。P1 不加 email / LINE 被動通知。

理由：

- 目標用戶是 2-5 人小團隊，老闆每天打開 Dashboard 看管道狀態，Dashboard 洞察區已足夠觸及。
- P2 的 LINE 通知整合（SPEC-crm-intelligence 已定義）才是合適的時機——等 CRM 使用習慣穩定後，再決定推送的頻率和粒度。
- 過早加被動通知會產生通知疲勞，反而讓使用者忽略真正重要的提醒。

### 決策 6：Deal Health 洞察即時計算，不持久化

Deal Health 洞察（停滯警告、承諾到期、跟進建議）在使用者載入客戶 tab 時即時計算，不存資料庫。

理由：

- 停滯天數和承諾到期是基於當前時間的計算，不需要快取
- P0 deal 數量預計 < 50 筆，即時計算無效能問題
- 避免資料一致性問題（如果快取了洞察，deal 狀態更新後快取會過期）

**計算邏輯放在 server side（API endpoint），不放前端。** 前端只負責渲染。理由：智慧邏輯只放 server 端（CLAUDE.md hard constraint #5）。

API 新增 `GET /api/crm/insights`，回傳結構化洞察清單。

### 決策 7：Deal 詳情頁重構為雙欄佈局（v0.3 新增）

**選擇雙欄佈局：左側 AI 洞察面板（始終可見）+ 右側活動時間軸。**

v0.2 的 deal 詳情頁是單欄線性佈局（deal 資訊 → AI 面板 → 活動時間軸），AI 面板是觸發後才出現的浮動元件，用完就丟。這導致 AI 產出的知識無法累積，使用者每次都從零開始。

雙欄設計讓兩個核心關注點同時可見：
- **左側（AI 洞察）**= 經營脈絡：這個客戶到底在意什麼、我們欠了什麼、下一步該怎麼走
- **右側（活動時間軸）**= 操作記錄：每次互動的原始紀錄 + 內嵌 debrief 摘要

不選 tab 切換：tab 意味著「看 AI 就看不到活動」，但使用者在記錄活動時需要參考 AI 洞察，兩者必須同時可見。

不選全域側邊欄：AI 洞察是 deal-level 的，不是全域的，不適合放在 layout-level 的側邊欄。

**實作影響**：
- `DealDetailClient.tsx` 從單欄改為 CSS grid 雙欄（lg 以上分欄，sm 堆疊）
- 新增 `DealInsightsPanel.tsx` 元件，負責讀取和展示 AI entries
- 活動時間軸的 `ActivityItem` 元件增加可展開的 debrief 摘要

### 決策 8：Briefing 改為對話式，復用 CoworkChatSheet（v0.3 新增）

**選擇對話式 Briefing，不再是單次觸發。復用行銷模組的 CoworkChatSheet 多輪對話模式。**

v0.2 的 briefing 是單次觸發——按一下「準備會議」，生成一段 markdown，用完關閉。這有三個問題：

1. **無法追問**：生成結果不夠具體時，使用者只能重新觸發（拿到幾乎相同的結果）
2. **無法調整焦點**：每次 briefing 都是通用版，不能針對「這次想重點討論定價」客製
3. **無法模擬情境**：使用者想準備「客戶可能的反對意見」但沒有入口

對話式解決所有三個問題：AI 先自動生成第一輪（帶入完整歷史 context），然後使用者可以追問、要求聚焦、模擬客戶反應，最終得到一份**為這次會議量身定做**的準備資料。

**復用 CoworkChatSheet 的元件**：
- 對話歷史渲染（scrollable viewport，Claude / 你 前綴）
- 多輪 SSE streaming（maxTurns=8）
- 健康檢查 + 降級 UI
- 取消和重試機制

**不復用的部分**：
- 行銷的「套用」按鈕（briefing 不需要寫回欄位）
- 行銷的 conversationId 持久化（briefing 對話不需要跨 session 保留）

**Briefing context pack 擴充**：

v0.2 的 context pack 只有 company、deal、activities_summary、contacts。v0.3 新增：

```json
{
  "scene": "briefing",
  "deal_id": "deal-xxx",
  "company": { "..." },
  "deal": { "..." },
  "activities_summary": "...",
  "contacts": [{ "..." }],
  "debrief_insights": {
    "key_decisions": ["歷次決策彙整..."],
    "customer_concerns": ["歷次顧慮彙整..."],
    "open_commitments": [
      {"content": "提供報價單", "owner": "us", "deadline": "2026-04-19"}
    ]
  },
  "previous_briefings_count": 2,
  "suggested_skill": "/crm-briefing"
}
```

Context pack 上限仍為 2000 字。截斷優先序更新為：activity.summary > **debrief_insights** > activities_summary > company > deal。

### 決策 9：AI Entries API 走 CRM Dashboard API，不走 ZenOS MCP（v0.3 新增）

**AI entries 的讀取走 CRM Dashboard REST API（`GET /api/crm/deals/{id}/ai-entries`），不走 ZenOS MCP search。**

理由：

1. **權限一致**：Dashboard API 已有 Firebase ID token auth + partner_id 過濾，直接復用
2. **效能可控**：Server-side 可做 SQL JOIN 一次拉取 deal entity 上的所有 entries，不需要前端多次呼叫 MCP
3. **前端一致**：前端所有 CRM 資料都走 `/api/crm/*`，不混用 MCP search
4. **commitment 更新**：標記完成需要 PATCH 操作，MCP write 不適合（write 是 upsert 語意，不是 partial update）

**不選 ZenOS MCP search 的原因**：MCP search 是全文搜尋語意，適合 agent 探索式查詢，不適合結構化的 CRUD 操作。且 MCP 需要 Local Helper 在線，而 AI entries 的讀取不應依賴 helper——使用者沒啟動 helper 也應該看得到歷史洞察。

**實作影響**：
- `crm_dashboard_api.py` 新增 `GET /api/crm/deals/{id}/ai-entries` 和 `PATCH /api/crm/commitments/{id}`
- `crm_service.py` 新增 `get_deal_ai_entries()` 和 `update_commitment_status()`
- 這些方法內部走 ZenOS repository 讀取 entries（已有基礎設施），不需要新增 DB table

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| Deal type 命名 `opportunity` | Salesforce 標準術語 | 使用者不說 opportunity，ZenOS 面向的中小企業團隊說「案子」「deal」 | 不貼近使用者心智 |
| Deal type 復用 `project` | 不增加 type | 語意完全不同，會污染 project 的查詢結果 | 語意衝突 |
| AI 走後端 API 直連 LLM | 不依賴本機 helper | 需要 API key、成本、與行銷架構分叉 | 不符合訂閱優先策略 |
| AI 產出放 CRM schema | 查詢效能更好 | 失去 ontology 關聯能力、與行銷不一致 | 不利跨模組查詢 |
| 承諾事項 P1 加 email 通知 | 離開 Dashboard 也能收到 | 通知疲勞風險、需要額外 email 基礎設施 | 太早，等 P2 LINE 一起做 |
| Deal 詳情頁用 tab 切換而非雙欄 | 實作簡單 | 看 AI 洞察就看不到活動時間軸，但兩者需同時可見 | 使用者需要同時參考洞察和活動記錄 |
| AI entries 讀取走 ZenOS MCP | 語意一致（都走 ontology） | 需要 helper 在線才能讀取、效能不可控、前端需混用兩套 API | helper 離線時歷史洞察就看不到，不可接受 |
| Briefing 維持單次觸發 | 實作簡單、已完成 | 無法追問、無法調整焦點、無法模擬情境 | 「準備會議」需要的是教練式互動，不是一次性報告 |

## Consequences

### 正面

- **架構統一**：CRM 和行銷的 AI 對話共用同一套 Local Helper bridge、cowork-helper 客戶端、AI 對話狀態機，維護成本低。
- **零 API key**：使用者只需有 Claude 訂閱，不需要另外管理 API key 或承擔 API 費用。
- **ontology 串聯**：Deal 作為 entity，AI 產出作為 entry，天然支援 ontology 層面的跨模組查詢（例：從知識地圖看到某公司的所有 deal + briefing + debrief）。
- **漸進式複雜度**：context pack 支援冷啟動（資料少時產出精簡版 briefing），隨使用量增加自動豐富。
- **AI 洞察持久化**（v0.3）：debrief 結果不再拋棄式，每次商談的知識自動累積到 deal 智能面板，越用越有價值。
- **對話式 briefing**（v0.3）：使用者可以針對特定會議需求調整準備方向，AI 從「報告生成器」升級為「會前教練」。
- **helper 離線不影響歷史洞察**（v0.3）：AI entries 走 Dashboard API，helper 離線只影響新的 AI 生成，不影響已有洞察的查看。

### 負面

- **本機依賴**：使用者必須安裝並啟動 Local Helper 才能使用 AI 功能。Helper 未啟動時 Briefing/Debrief 不可用（Dashboard 其他 CRM 功能不受影響）。
- **ADR-011 部分推翻**：Deal 橋接為 entity 增加 CrmService 複雜度（每次 create_deal 同步建立 entity），且增加 entity 表資料量。但 deal 數量遠小於 activity，影響可控。
- **entity type 擴充**：需要 DB migration 新增 `deal` type，影響 chk_entities_type 約束。此為單次操作，後續無維護成本。
- **前端複雜度增加**（v0.3）：雙欄佈局 + 洞察面板 + 內嵌 debrief + 對話式 briefing，deal 詳情頁元件數量增加。需要良好的元件拆分避免單一檔案過大。
- **AI entries 讀取依賴後端新 API**（v0.3）：需要新增 `GET /api/crm/deals/{id}/ai-entries` 和 `PATCH /api/crm/commitments/{id}`，增加後端維護面積。但邏輯簡單（讀取 + partial update），不會成為瓶頸。

## Implementation

### 已完成（v0.2 P0）

以下在 PLAN-crm-intelligence-implementation 中已完成：

- DB Migration：`chk_entities_type` 加入 `deal`、`crm.deals` 新增 `zenos_entity_id`、`crm.settings` table
- Domain Model：`EntityType.DEAL`
- Application Layer：`CrmService.create_deal()` entity bridge、`CrmInsightsService`
- API：`GET /api/crm/insights`、`GET/PUT /api/crm/settings/stale-thresholds`
- Skill 定義：`/crm-briefing`、`/crm-debrief`
- Helper 擴充：`EXPECTED_CRM_SKILLS`
- Dashboard：CrmAiPanel（單次 briefing/debrief）、DealHealthInsights、StaleThresholdsModal

### 待實作（v0.3 新增）

#### Backend

- `crm_service.py` 新增 `get_deal_ai_entries(partner_id, deal_id)` — 讀取 deal entity 上的所有 crm_debrief + crm_commitment entries
- `crm_service.py` 新增 `update_commitment_status(partner_id, commitment_id, status)` — 更新 commitment entry 的 metadata.status
- `crm_dashboard_api.py` 新增 `GET /api/crm/deals/{id}/ai-entries` — 回傳 debriefs + commitments
- `crm_dashboard_api.py` 新增 `PATCH /api/crm/commitments/{id}` — 更新 commitment 狀態

#### Frontend

- `DealDetailClient.tsx` 重構為雙欄佈局（CSS grid，lg:grid-cols-[340px_1fr]）
- 新增 `DealInsightsPanel.tsx` — AI 洞察面板（關鍵決策、承諾追蹤、客戶顧慮、Deal 摘要）
- `ActivityItem.tsx` 增加可展開的 debrief 摘要（「AI 分析 ▸」標籤）
- `CrmAiPanel.tsx` briefing 模式改為對話式（復用 CoworkChatSheet 的多輪 streaming 模式）
- `buildBriefingPrompt()` context pack 新增 `debrief_insights` 和 `open_commitments`
- `crm-api.ts` 新增 `fetchDealAiEntries()`、`updateCommitmentStatus()`

#### Skill 更新

- `/crm-briefing` SKILL.md 更新：輸入 context pack 新增 debrief_insights 結構
- `/crm-debrief` SKILL.md 更新：確保 metadata 結構化輸出（key_decisions、customer_concerns 作為 array），便於前端解析
