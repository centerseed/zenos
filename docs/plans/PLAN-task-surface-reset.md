---
spec: SPEC-task-surface-reset.md
design: TD-task-surface-reset-implementation.md
created: 2026-04-22
status: in-progress
---

# PLAN: Task Surface Reset

## Entry Criteria

- `SPEC-task-surface-reset.md` 已存在且帶 `AC-TSR-01~16`
- `TD-task-surface-reset-implementation.md` 已完成調查、AC Compliance Matrix 與 Done Criteria
- `DESIGN-task-multilayer-workspace.md` 已將高層 IA 定義成 `Task Hub → Product Console → Task Detail`
- 現有 `/projects/[id]` plan-centric console 已可作為 product-side 基礎，不需重造

## Exit Criteria

- `AC-TSR-01~16` 全 PASS
- `/tasks` 第一屏改成 Task Hub，不再直接掉進完整 execution board
- `/tasks` 可直接 drill-down 到 `/projects?id=<product_id>&focus=...`
- `TaskDetailDrawer` 預設 landing 為 overview-first
- `Structure mode` 成為正式入口，但非預設主視角
- `Task Copilot` 在 `/tasks` 與 `/projects/[id]` 皆滿足 sticky rail contract
- QA verdict = PASS

## Tasks

- [x] S01: 補 Task Hub 首屏 recap 與 product-level aggregates
  - Files: `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/features/tasks/*`, 如有必要補 `dashboard/src/lib/api.ts`
  - Owner: Developer Worker A (`agent_id=019db3f4-25a1-74a1-96d5-2a8b77ad906e`, ZenOS task `e3b8d395185e43e582cd94bf5604ef33`)
  - Verify: vitest task surface AC subset
  - AC Scope: `AC-TSR-01`, `AC-TSR-04`, `AC-TSR-05`, `AC-TSR-14`

- [x] S02: 補 `/tasks -> /projects?id=&focus=` drill-down contract
  - Files: `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/app/(protected)/projects/page.tsx`, `dashboard/src/features/projects/*`
  - Owner: Developer Worker A (`agent_id=019db3f4-25a1-74a1-96d5-2a8b77ad906e`, ZenOS task `886f0fecddbf496ab3b9f6344d46f00c`)
  - Verify: vitest navigation / query-state AC subset
  - AC Scope: `AC-TSR-06`, `AC-TSR-16`

- [x] S03: 重構 `TaskDetailDrawer` 為 overview-first + structure mode
  - Files: `dashboard/src/components/TaskDetailDrawer.tsx`, `dashboard/src/components/TaskDetailOverview.tsx`, `dashboard/src/components/TaskDetailContext.tsx`, `dashboard/src/components/TaskStructurePanel.tsx`, `dashboard/src/components/TaskHistoryPanel.tsx`
  - Owner: Developer Worker B (`agent_id=019db3f4-60f9-7332-9afb-78514b2db8ad`, ZenOS task `3c418b695bc84fcaa01b8bf1b497627b`)
  - Verify: vitest detail AC subset
  - AC Scope: `AC-TSR-02`, `AC-TSR-03`, `AC-TSR-07`, `AC-TSR-08`, `AC-TSR-09`, `AC-TSR-10`, `AC-TSR-15`

- [x] S04: 統一 task-related copilot rail contract
  - Files: `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/features/projects/ProjectProgressConsole.tsx`, `dashboard/src/features/projects/ProjectRecapRail.tsx`, shared copilot shell files if needed
  - Owner: Developer Worker A (`agent_id=019db3f4-25a1-74a1-96d5-2a8b77ad906e`, ZenOS task `38bc59729e65419eb56820ba75895c74`)
  - Verify: vitest sticky / scoped-language AC subset
  - AC Scope: `AC-TSR-11`, `AC-TSR-12`

- [ ] S05: 補 AC 測試、回歸、build gate
  - Files: `dashboard/src/__tests__/task_surface_reset_ac.test.tsx`, related regression tests
  - Owner: Architect after Developer handoff, then QA
  - Verify: vitest + dashboard build
  - AC Scope: `AC-TSR-01~16`

## Dependencies

- S02 depends on S01
- S03 independent of S01, but must reuse S02 query contract where needed
- S04 depends on S01 and current shared rail shell
- S05 depends on S01~S04

## Decisions

- 2026-04-22: 採單一多層次 IA，`/tasks` 第一屏為 Task Hub，execution board 下沉為第二層。
- 2026-04-22: 產品側沿用現有 `ProjectProgressConsole`，新增 `focus` query contract，不再另做新 product route。
- 2026-04-22: `TaskDetailDrawer` Phase 0 採 tab/mode 重構，不先拆成獨立 overlay route。
- 2026-04-22: sticky rail 與 scoped prompt 文案沿用 shared AI rail shell，不另開新 copilot primitive。

## Resume Point

已完成：

- 調查報告
- `SPEC-task-surface-reset.md` 升級為可派工版本（含 `AC-TSR-01~16`）
- `TD-task-surface-reset-implementation.md` 升級為可派工版本
- `DESIGN-task-multilayer-workspace.md` 已落地並同步 ZenOS
- `PLAN-task-surface-reset` 已建立
- `dashboard/src/__tests__/task_surface_reset_ac.test.tsx` 已補 architect AC stubs
- ZenOS plan `1b16ee3cad40468ba8f8ba657fb4db8c` 已建立並切成 S01~S05 對應 implementation tasks
- Task Hub / projects focus / rail 第一批實作已直接在主線落地，並通過 targeted vitest、TypeScript 與 `next build`

下一步：

- 補 `S03`：TaskDetailDrawer overview-first / structure mode
- 將 AC stubs 逐步轉成真實驗收測試
- 我整合剩餘交付後執行 `S05`，再派 QA 驗收
