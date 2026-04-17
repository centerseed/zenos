---
spec: SPEC-crm-intelligence.md
adr: ADR-037-crm-intelligence-architecture.md
plan_id: 251065f55b0449a99680e21bf0c66c53
created: 2026-04-14
status: done
---

# PLAN: CRM Intelligence v0.3 — AI 洞察持久化 + 對話式 Briefing

## 設計修正

**Entry 模型衝突**：ADR-037 決策 3 假設 AI 產出存為 ZenOS entry（type: crm_debrief），但 entity_entries 表的 CHECK constraint 只允許 5 種 type，且 content 限制 200 字、無 metadata JSONB。
**修正**：在 CRM schema 新增 `crm.ai_insights` 表。前端 streaming 完成後解析 AI 輸出，透過 Dashboard API 存入 CRM 表。不修改 ZenOS Core entry 模型。與 ADR-037 決策 9（AI entries 走 Dashboard API）完全一致。

## Tasks

- [x] S01: Backend — AI Insights 表 + API
  - Files: `migrations/20260414_0003_crm_ai_insights.sql`, `src/zenos/infrastructure/crm_sql_repo.py`, `src/zenos/application/crm/crm_service.py`, `src/zenos/interface/crm_dashboard_api.py`, `src/zenos/domain/crm_models.py`
  - New DB: `crm.ai_insights` (id, partner_id, deal_id, activity_id, insight_type, content, metadata, status, created_at)
  - New API: `GET /api/crm/deals/{id}/ai-entries`, `POST /api/crm/deals/{id}/ai-insights`, `PATCH /api/crm/commitments/{id}`
  - Verify: `.venv/bin/pytest tests/ -x`

- [x] S02: Frontend — Deal 詳情頁重構（雙欄 + 洞察面板 + 活動內嵌 debrief）(depends: S01)
  - Files: `dashboard/src/app/clients/deals/[id]/DealDetailClient.tsx`, `dashboard/src/app/clients/deals/[id]/DealInsightsPanel.tsx` (new), `dashboard/src/lib/crm-api.ts`
  - 雙欄佈局（lg:grid-cols-[340px_1fr]）
  - AI 洞察面板：關鍵決策、承諾追蹤（checkbox）、客戶顧慮、Deal 摘要
  - Activity 時間軸內嵌可展開 debrief 摘要
  - Debrief streaming 完成後 → 前端解析 → POST /api/crm/deals/{id}/ai-insights 保存
  - Verify: `npm run build --prefix dashboard`

- [x] S03: Frontend — 對話式 Briefing + Context Pack 擴充 + ai-entries mount 修正 (depends: S01, S02)
  - Files: `dashboard/src/app/clients/deals/[id]/CrmAiPanel.tsx`, `dashboard/src/lib/crm-api.ts`
  - Briefing 模式改為多輪對話（復用行銷 CoworkChatSheet 模式）
  - Context pack 新增 debrief_insights + open_commitments（從 GET ai-entries 取得）
  - 最多 8 輪對話
  - Verify: `npm run build --prefix dashboard`

- [x] S04: QA + Deploy (depends: S01-S03)
  - Verify: tests + build + 正式站 smoke

## Dependency Graph

```
S01 ──┬──→ S02 ──→ S03 ──→ S04
      │
      └──────────────────→ S04
```

## Decisions

- 2026-04-14: Plan 建立。ZenOS entry 模型不適合 CRM AI 產出（CHECK constraint + 200 字限制 + 無 metadata），改用 `crm.ai_insights` 表。
- 2026-04-14: S01-S03 完成。QA CONDITIONAL PASS（2 Major：recent_commitments 空陣列 + 無已完成摺疊區）→ 修復後 PASS。

## Resume Point

全部完成。Migration applied、Backend Cloud Run zenos-mcp-00157-zkw deployed、Frontend Firebase Hosting deployed。正式站 smoke 全 200。
