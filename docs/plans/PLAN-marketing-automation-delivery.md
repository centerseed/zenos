---
spec: SPEC-marketing-automation.md + SPEC-skill-packages.md
created: 2026-04-12
status: completed
---

# PLAN: Marketing Automation Delivery

## Tasks
- [x] S01: 定義 marketing runtime 資料契約與架構決策
  - Files: `docs/designs/TD-marketing-automation-implementation.md`, `docs/decisions/ADR-033-marketing-automation-runtime-and-packages.md`
  - Verify: `rg -n "workflow_status|manifest.packages|Postiz" docs/designs/TD-marketing-automation-implementation.md docs/decisions/ADR-033-marketing-automation-runtime-and-packages.md`
- [x] S02: 實作 marketing Dashboard API layer
  - Files: `src/zenos/interface/marketing_dashboard_api.py`, `src/zenos/interface/mcp/__main__.py`, `tests/interface/test_marketing_dashboard_api.py`
  - Verify: `.venv/bin/pytest -q tests/interface/test_marketing_dashboard_api.py`
  - Action Layer: ticket `53c1ef2f3fba4d0787cdf92eeeaa3cfe`
- [x] S03: 將 `/marketing` 前端改為真實 API（移除 mock 常數）
  - Files: `dashboard/src/lib/marketing-api.ts`, `dashboard/src/app/marketing/page.tsx`, `dashboard/src/lib/__tests__/marketing-api.test.ts`
  - Verify: `npm run build --prefix dashboard`
- [x] S04: 新增 5 個 marketing workflow skills
  - Files: `skills/release/workflows/marketing-intel/SKILL.md`, `skills/release/workflows/marketing-plan/SKILL.md`, `skills/release/workflows/marketing-generate/SKILL.md`, `skills/release/workflows/marketing-adapt/SKILL.md`, `skills/release/workflows/marketing-publish/SKILL.md`
  - Verify: `python3 scripts/sync_skills_from_release.py` + `.venv/bin/pytest -q tests/test_sync_skills_from_release.py`
- [x] S05: 落地 skill package 定義與 setup/installer 相容
  - Files: `skills/release/manifest.json`, `src/zenos/interface/setup_content.py`, `src/zenos/interface/setup_adapters.py`, `src/zenos/skills_installer.py`, `tests/interface/test_setup_tool.py`, `tests/application/test_skills_installer.py`
  - Verify: `.venv/bin/pytest -q tests/interface/test_setup_tool.py tests/application/test_skills_installer.py`
- [x] S06: Postiz 最小整合（skill-side）與回寫契約
  - Files: `skills/release/workflows/marketing-publish/SKILL.md`, `docs/designs/TD-marketing-automation-implementation.md`
  - Verify: `rg -n "postiz|dry_run|job_id" skills/release/workflows/marketing-publish/SKILL.md docs/designs/TD-marketing-automation-implementation.md`
- [x] S07: ADR supersede 流程
  - Files: `docs/decisions/ADR-001-marketing-automation-architecture.md`, `docs/decisions/ADR-033-marketing-automation-runtime-and-packages.md`
  - Verify: `rg -n "status:|supersedes|superseded" docs/decisions/ADR-001-marketing-automation-architecture.md docs/decisions/ADR-033-marketing-automation-runtime-and-packages.md`
- [x] S08: QA + 部署驗證 + spec 同步
  - Files: `tests/interface/test_marketing_dashboard_api.py`, `dashboard/src/lib/__tests__/marketing-api.test.ts`, `docs/specs/SPEC-marketing-automation.md`, `docs/specs/SPEC-skill-packages.md`
  - Verify: `.venv/bin/pytest -q tests/interface/test_marketing_dashboard_api.py` + `npm run build --prefix dashboard`

## Decisions
- 2026-04-12: 先用既有 entity/entry/task 模型，不新增 MCP tool、不新增 core table。
- 2026-04-12: Dashboard 走 `/api/marketing/*` BFF read model，不讓前端自行拼裝多來源資料。
- 2026-04-12: Postiz v1 先走 skill-side 整合；server-side worker 延後到 v1.1。
- 2026-04-12: package schema 採 `manifest.packages[]`，保持與既有 `manifest.skills[]` 向後相容。
- 2026-04-12: ADR-033 草案建立，作為 Marketing runtime + package 策略的決策錨點。
- 2026-04-13: 已建立 Action Layer Plan `97cbacb658144f249ab45f5eaf955e76`（status=active），S02~S08 任務已建票並掛依賴。
- 2026-04-13: S02~S07 已完成實作與本地測試，包含 marketing API、前端串接、workflow skills、manifest packages、ADR supersede。

## Action Layer Mapping
- Plan: `97cbacb658144f249ab45f5eaf955e76`
- S02 ticket: `53c1ef2f3fba4d0787cdf92eeeaa3cfe`
- S03 ticket: `d557321a533a44428249aa459cd5cb1d`
- S04 ticket: `bfd5058b7d1f4c878747f342f63e8612`
- S05 ticket: `836edd36a4e44190b4cacb529bcf24d7`
- S06 ticket: `9ad268053cb244849101249e82637408`
- S07 ticket: `6756ee705d5947a1917c1df3a5810945`
- S08 ticket: `7522ee049b6c4c5a8ae98b904ea356de`

## Assignee Mapping
- S02: `developer`（status: `in_progress`）
- S03: `developer`
- S04: `developer`
- S05: `developer`
- S06: `developer`
- S07: `architect`
- S08: `qa`

## Resume Point
本計畫已完成（S02~S08 done，Plan `97cbacb658144f249ab45f5eaf955e76` completed）。
