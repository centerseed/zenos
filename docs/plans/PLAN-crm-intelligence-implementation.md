---
spec: SPEC-crm-intelligence.md
adr: ADR-037-crm-intelligence-architecture.md
plan_id: b22c427132b541fdbf50aef6df4b511a
created: 2026-04-14
status: done
---

# PLAN: CRM AI Intelligence 模組 P0 實作

## Tasks

- [x] S01: Deal Entity Bridge — DB migration + Domain + CrmService 橋接 (`40fa62ef`)
  - Files: `migrations/`, `src/zenos/domain/knowledge/enums.py`, `src/zenos/infrastructure/crm_sql_repo.py`, `src/zenos/application/crm/crm_service.py`
  - Verify: `.venv/bin/pytest tests/ -x`

- [x] S02: CRM AI Skills + Helper 更新 (`8b871163`) (depends: S01)
  - Files: `skills/release/workflows/crm-briefing/`, `skills/release/workflows/crm-debrief/`, `tools/claude-cowork-helper/server.mjs`, `.claude/settings.json`
  - Verify: helper smoke 識別 CRM skills

- [x] S03: Deal Health Insights API (`f44cc3de`) (depends: S01)
  - Files: `src/zenos/interface/crm_dashboard_api.py`, `src/zenos/application/crm/crm_service.py`
  - Verify: `.venv/bin/pytest tests/ -x`

- [x] S04: Frontend — Briefing + Debrief UI (`a700eb5f`) (depends: S01, S02)
  - Files: `dashboard/src/app/clients/deals/[id]/page.tsx`, `dashboard/src/lib/crm-api.ts`
  - Verify: `npm run build --prefix dashboard`

- [x] S05: Frontend — Deal Health + 停滯設定 (`27f8e8f1`) (depends: S03)
  - Files: `dashboard/src/app/clients/page.tsx`, `dashboard/src/app/clients/settings/`
  - Verify: `npm run build --prefix dashboard`

- [x] S06: QA + Deploy (`6f7d2ba0`) (depends: S01-S05)
  - Verify: tests + build + 正式站 smoke

## Dependency Graph

```
S01 ─┬─→ S02 ──┐
     │         ├──→ S04
     ├─→ S03 ──┤
     │         ├──→ S05
     │         │
     └─────────┴──→ S06
```

## Decisions

- 2026-04-14: Plan 建立。S01 先行，S02/S03 可並行（都只依賴 S01），S04 依賴 S01+S02，S05 依賴 S03。
- 2026-04-14: S01-S06 全部完成。QA 發現 briefing context pack 缺 scope_description/deliverables → 已修復。recent_commitments=[] 標記為 accepted P0 degradation。

## Resume Point

全部完成。DB migration applied、Backend Cloud Run deployed、Frontend Firebase Hosting deployed。正式站 smoke：/、/tasks、/knowledge-map、/clients 全部 200。
