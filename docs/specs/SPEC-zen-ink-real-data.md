---
type: SPEC
id: SPEC-zen-ink-real-data
status: Draft
ontology_entity: dashboard
created: 2026-04-19
updated: 2026-04-23
extends: SPEC-zen-ink-redesign
depends_on: SPEC-mcp-tool-contract, SPEC-zen-ink-redesign
---

# SPEC: Zen Ink 真實資料接線 + MCP 設定頁

## What
把 Zen Ink UI 的 P0 五頁（MCP 設定 / Knowledge Map / Projects / Clients / Marketing）接上後端真實資料。設計稿有但後端沒有的欄位一律顯示 `—`；重度 missing 區塊記入 P1 backlog。

## Why
SPEC-zen-ink-redesign 一次到位 UI，但 non-goal 是「不接 API」。用戶確認翻轉：「假資料沒用，要接真實資料」。P0 先接能接的，將無法接的清單化成 P1。

## Scope
1. **MCP 設定頁**（`/setup` 或新 `/agent`）— Option B：列 MCP servers（目前只有 hosted ZenOS server）+ health check + 給各平台的 config snippet 可複製，保留設計稿 Tabs（Local helper / MCP / Skills）
2. **Knowledge Map** — 用 `getAllEntities` + `getAllRelationships` + `getBlindspots`；節點類型 map 到 Entity.type
3. **Projects** — 用 `getProjectEntities` + `getTasksByEntity`（aggregate KPI）
4. **Clients** — Zen Ink 視覺套到現有 `ClientsWorkspace`（已用 crm-api），或重建套 Zen Ink + 串同樣 crm-api
5. **Marketing** — Zen Ink 視覺套到現有 `MarketingWorkspace`（已用 marketing-api），或重建套 Zen Ink + 串同樣 marketing-api

## Acceptance Criteria

### AC-DATA-MCP-01 ~ 04（MCP 設定頁 · Option B）
- **AC-DATA-MCP-01**: 頁面渲染 designv2/page_agent 的三 tabs（Local helper / MCP / Skills），Zen Ink 視覺
- **AC-DATA-MCP-02**: MCP tab 列出 hosted ZenOS server（`https://zenos-mcp-165893875709.asia-east1.run.app`）+ 執行 live health check（用戶 apiKey），顯示狀態（connected/error）、latency（接不上 → `—`）
- **AC-DATA-MCP-03**: MCP tab 提供各平台 config snippet copy（claude-code / claude-cowork / chatgpt / codex / gemini-cli / antigravity），複製後 toast 確認
- **AC-DATA-MCP-04**: Skills tab 顯示 `—` / "本地 agent skills 由 Claude Code CLI 管理"；Local helper tab 給 install 指示（保留設計稿 UI 但 disabled action）

### AC-DATA-MAP-01 ~ 04（Knowledge Map）
- **AC-DATA-MAP-01**: `/knowledge-map` 載入 `getAllEntities` + `getAllRelationships`；loading 用 Zen Ink spinner
- **AC-DATA-MAP-02**: SVG 圖渲染真實 entities（自動佈局 or force layout），節點顏色依 Entity.type 映射（product/module=vermillion, goal=ocher, company/deal=jade, role=ink, document=inkMuted, person=seal）
- **AC-DATA-MAP-03**: 點擊節點 → Inspector 顯示 Entity.name / type / summary；Relations 列出該 entity 所有 relationships；近期活動顯示 `—`（P1）
- **AC-DATA-MAP-04**: Agent Summary 區塊顯示 entity.summary（若為空 → `—`）；空資料時顯示 "目前沒有節點" empty state

### AC-DATA-PROJ-01 ~ 04（Projects）
- **AC-DATA-PROJ-01**: `/projects` 載入 `getProjectEntities`（type=product）；KPI strip 從 entities 算：進行中數量、待分派任務數、整體進度
- **AC-DATA-PROJ-02**: 專案卡片顯示 entity.name / summary / owner；code 用 entity.id 前綴；健康（順利/風險/暫停）映射 entity.status (active→順利, paused→暫停, stale/conflict→風險)
- **AC-DATA-PROJ-03**: 進度從 `getTasksByEntity(entityId)` 算 `done/total`；成員數 / 文件數 / 截止日 → `—`（P1 後端補）
- **AC-DATA-PROJ-04**: Detail 頁接 `getEntityContext` + `getTasksByEntity` + `getChildEntities`（modules）；milestones / activity / 成員頭像 → `—`

### AC-DATA-CLIENTS-01 ~ 03（Clients）
- **AC-DATA-CLIENTS-01**: `/clients` 用 Zen Ink 視覺 + 串 crm-api 的 `getDeals` / `getCompanies` / `getContacts`；pipeline 5 欄對齊 `FunnelStage` 映射
- **AC-DATA-CLIENTS-02**: Deal 點擊進 detail 用 `getDeal` + `getDealActivities` + `fetchDealAiEntries`；AI 複盤用既有 `AiInsight.briefing` 資料
- **AC-DATA-CLIENTS-03**: 推進階段按鈕接 `patchDealStage`；新建 Deal / 承諾事項 CRUD 若現有 API 支援就接，否則 `—`

### AC-DATA-MKT-01 ~ 03（Marketing）
- **AC-DATA-MKT-01**: `/marketing` 用 Zen Ink 視覺 + 串 marketing-api 的 `getMarketingProjectGroups` 列 campaigns
- **AC-DATA-MKT-02**: Campaign 點擊進 detail，6-stage stepper 映射到 MarketingProject 的 strategy/content_plan/posts lifecycle；寫作計畫區塊接 `updateMarketingProjectStrategy` + `updateMarketingProjectContentPlan`
- **AC-DATA-MKT-03**: 文風管理接 `getMarketingProjectStyles` + `createMarketingStyle` + `updateMarketingStyle`；KPI 觸及/轉換率 → `—`（P1）

### AC-DATA-COMMON-01 ~ 02
- **AC-DATA-COMMON-01**: 所有頁面在 token 尚未載入時顯示 Zen Ink loading；API 錯誤顯示 Zen Ink 錯誤卡片（含 retry）
- **AC-DATA-COMMON-02**: 空欄位一律顯示 `—`（不是 "N/A" / 留白 / "loading..."）；`backlog` 文件 `docs/backlog/BACKLOG-zen-ink-data-gaps.md` 記下所有 `—` 欄位與對應後端缺口

## Non-goals
- 不改 API schema（後端不動）
- 不做 entity/relationship 的 CRUD（只讀 + 現有 mutation 如 patchDealStage/updateStrategy）
- 不做 real-time / websocket（fetch 一次就好）
- 不做 client-side 快取 / stale-while-revalidate（SWR 以後再說）

## P1 Backlog（在 AC-DATA-COMMON-02 產出）
以下欄位目前後端沒有，需後端/Entity schema 補：
- Entity: health status, members, due_date, code prefix, color theme
- Tasks: milestones
- Marketing: 觸及率 / 轉換率 / Post performance metrics
- Knowledge Map: 節點 recent activity
- MCP: server registry（多 server 支援）/ skills installation state
