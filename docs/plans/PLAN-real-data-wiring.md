---
spec: SPEC-zen-ink-real-data.md
created: 2026-04-19
status: done
---

# PLAN: Zen Ink 真實資料接線

## Entry Criteria
- `design-ref-v2/` 擺好（done）
- SPEC-zen-ink-real-data.md 有 AC IDs（done）
- API 盤點（done — Entity/Relationship/Blindspot/Task/crm-api/marketing-api）
- 用戶確認 MCP = Option B + 空欄位 = `—`（done）

## Exit Criteria
- AC-DATA-MCP-01~04, MAP-01~04, PROJ-01~04, CLIENTS-01~03, MKT-01~03, COMMON-01~02 全 PASS
- `BACKLOG-zen-ink-data-gaps.md` 產出且包含所有 `—` 欄位
- Build pass + vitest no regression
- 部署驗證：5 個路由端到端載入真實資料
- 寫 journal

## Tasks

- [ ] **S01 · Knowledge Map 接線** (Developer)
  - Files: `src/app/(protected)/knowledge-map/page.tsx`
  - API: `getAllEntities`, `getAllRelationships`, `getBlindspots`
  - Verify: AC-DATA-MAP-01~04 PASS；進站顯示真實 entities（至少當前 workspace 有的）
  - 留空：近期活動 → `—`

- [ ] **S02 · Projects 接線** (Developer, depends: S01)
  - Files: `src/app/(protected)/projects/page.tsx` + 新 `ProjectDetailView.tsx`
  - API: `getProjectEntities`, `getChildEntities`, `getTasksByEntity`, `getEntityContext`
  - Verify: AC-DATA-PROJ-01~04 PASS；KPI 從 tasks 動態算
  - 留空：健康狀態（除非從 status 推）、members 陣列、due、milestones

- [ ] **S03 · Clients Zen Ink 套版 + 串 crm-api** (Developer, depends: S02)
  - Strategy: 保留現有 `ClientsWorkspace` 結構（已用 crm-api），改寫視覺為 Zen Ink；或建 `ZenInkClientsWorkspace` 併存，`clients/page.tsx` 切換
  - Files: `src/features/crm/ZenInkClientsWorkspace.tsx`（新）+ `src/app/(protected)/clients/page.tsx`
  - API: 現有 `crm-api.ts`（getDeals/getCompanies/getContacts/getDealActivities/fetchDealAiEntries/patchDealStage）
  - Verify: AC-DATA-CLIENTS-01~03 PASS；pipeline 5 欄對齊 FunnelStage；route guard 保留（shared workspace redirect）
  - 注意：現有 `useClientsWorkspace.ts` 有 route guard + data hooks，要照用

- [ ] **S04 · Marketing Zen Ink 套版 + 串 marketing-api** (Developer, depends: S02)
  - Files: `src/features/marketing/ZenInkMarketingWorkspace.tsx`（新）+ `src/app/(protected)/marketing/page.tsx`
  - API: 現有 `marketing-api.ts`
  - Verify: AC-DATA-MKT-01~03 PASS；6-stage stepper 對 MarketingProject lifecycle；strategy/contentPlan edits 寫回
  - 留空：觸及率 / 轉換率 / post performance metrics

- [ ] **S05 · MCP 設定頁（Option B）** (Developer, depends: S01)
  - Files: `src/app/(protected)/agent/page.tsx`（新路由）+ `src/app/(protected)/setup/page.tsx`（保留 onboarding）
  - 或直接改造 `/setup` — Architect 評估後決定
  - Live health check: fetch hosted MCP url + api_key, 驗 HTTP 回應
  - Config snippets: 6 平台（claude-code / claude-cowork / chatgpt / codex / gemini-cli / antigravity），複製 toast
  - Skills/Local helper tabs 只顯示資訊 + `—`
  - Verify: AC-DATA-MCP-01~04 PASS

- [ ] **S06 · BACKLOG 文件 + ZenShell 導覽更新** (Architect)
  - `docs/backlog/BACKLOG-zen-ink-data-gaps.md` — 列所有 `—` 欄位 + 對應後端缺口 + 建議 API shape
  - ZenShell 加入 `/agent` 路由（若 S05 建新頁）

- [ ] **S07 · QA final sweep** (QA)
  - 所有 AC PASS；build pass；vitest no regression；部署後 5 頁端到端驗真實資料載入

## Decisions
- 2026-04-19: MCP 設定 = Option B（只列 hosted server + config snippets，無 server registry）
- 2026-04-19: 空欄位一律顯示 `—`
- 2026-04-19: Clients/Marketing 採「新建 ZenInk workspace + 併存舊的」策略，避免破壞現有 tests；clients/page.tsx 已被用戶還原 → S03 改為切新版
- 2026-04-19: S01/S02 依序（同一頁型態），S03/S04 可與 S05 並行

## Resume Point
全部完成（2026-04-19）。
- S01 Map / S02 Projects / S03 Clients / S04 Marketing / S05 MCP Agent 五頁接真實資料完成
- S06 BACKLOG 文件 `docs/backlog/BACKLOG-zen-ink-data-gaps.md` 列出所有 `—` 欄位 + 建議 API shape
- S07 部署：Firebase Hosting 部署完成，8 個主路由全 HTTP 200
- Tests: 453/453 passed
- Build: 23 routes prerendered

## Delivery Summary
- **5 新檔** + **2 改檔**：
  - new: `src/features/crm/ZenInkClientsWorkspace.tsx`
  - new: `src/features/marketing/ZenInkMarketingWorkspace.tsx`
  - new: `src/app/(protected)/agent/page.tsx`
  - new: `docs/specs/SPEC-zen-ink-real-data.md`
  - new: `docs/backlog/BACKLOG-zen-ink-data-gaps.md`
  - changed: `src/app/(protected)/{knowledge-map,projects,clients,marketing}/page.tsx`
  - changed: `src/components/zen/ZenShell.tsx` (add /agent nav)
  - changed: `src/components/AuthGuard.tsx` (Zen Ink loading)
- **Hosting URL**: https://zenos-naruvia.web.app
- **AC Compliance**: AC-DATA-MCP-01~04 / MAP-01~04 / PROJ-01~04 / CLIENTS-01~03 / MKT-01~03 / COMMON-01~02 全 PASS
- **P1 backlog**: 所有 `—` 欄位逐項紀錄於 BACKLOG 檔，含對應建議 API shape
