---
spec: SPEC-project-progress-console.md
design: TD-project-progress-console-implementation.md
created: 2026-04-21
status: in-progress
---

# PLAN: Project Progress Console

## Entry Criteria

- `SPEC-project-progress-console.md` 已存在且有 `AC-PPC-01~15`
- `TD-project-progress-console-implementation.md` 已完成調查、介面契約、Done Criteria
- AC stubs `dashboard/src/__tests__/project_progress_console_ac.test.tsx` 已建立

## Exit Criteria

- `AC-PPC-01~15` 全 PASS
- `/projects/[id]` 第一層為 plan-centric console，不再以完整 `TaskBoard` 當主視角
- project-level aggregate endpoint 與 AI recap / copy prompt 都已交付
- `cd dashboard && npm run build` 通過
- 相關最小 scope 測試通過
- QA verdict = PASS
- 部署與正式站驗證完成

## Tasks

- [ ] S01: 補 project progress aggregate endpoint 與 client contract
  - Files: `src/zenos/interface/dashboard_api.py`, `dashboard/src/lib/api.ts`, backend tests
  - Verify: backend 最小 scope pytest + frontend API client tests
  - AC Scope: `AC-PPC-01`, `AC-PPC-04`, `AC-PPC-13`, `AC-PPC-14`

- [ ] S02: 重構 `/projects/[id]` 成 plan-centric console
  - Files: `dashboard/src/app/(protected)/projects/page.tsx`, `dashboard/src/features/projects/*`
  - Verify: `cd dashboard && npx vitest run src/__tests__/project_progress_console_ac.test.tsx`
  - AC Scope: `AC-PPC-01~06`, `AC-PPC-11~14`

- [ ] S03: 接 shared AI rail 的 recap 與 copy prompt preset
  - Files: `dashboard/src/features/projects/ProjectRecapRail.tsx`, `dashboard/src/features/projects/projectCopilot.ts`, `dashboard/src/features/projects/projectPrompt.ts`
  - Verify: project progress console AC tests + build
  - AC Scope: `AC-PPC-07~10`, `AC-PPC-15`

- [ ] S04: 補 regression / build gate / deploy verification
  - Files: `dashboard/src/__tests__/project_progress_console_ac.test.tsx`, related regression tests, deploy output
  - Verify: vitest / build / deploy / prod smoke
  - AC Scope: `AC-PPC-01~15`

## Dependencies

- S02 depends on S01
- S03 depends on S01
- S04 depends on S02 and S03

## Decisions

- 2026-04-21: 本輪用單一 aggregate endpoint 收斂 project progress 口徑，不讓前端自行從多支 API 拼湊。
- 2026-04-21: `/projects/[id]` 保留 task drill-down，但第一層主視角改成 plan-centric console。
- 2026-04-21: AI recap / copy prompt 沿用 shared AI rail，不另做新 widget。
- 2026-04-21: S02（console IA）與 S03（AI recap / copy prompt）由同一位 Developer 一次完成，避免 `/projects` 與 `features/projects` write scope 衝突。

## Resume Point

已完成調查、TD、AC stubs，且已建立：

- Plan ID: `06f87c2aa52d411eb2d155f707689e77`
- Parent task ID: `0ac5af49ee274aafa97032a189d7664a`
- S01 task ID: `122f0d068c864275918e2a64f4d4d580`
- S02 task ID: `479557cc2b584b99a0194b821c3bba77`
- S03 task ID: `3cc23cdee12e4a2593a0adddd18179c2`

當前狀態：

- S01 已完成並回到 Architect：aggregate endpoint `/api/data/projects/{id}/progress` 與 `getProjectProgress()` contract 已就位。
- S02 / S03 已 handoff 給同一位 Developer 一次完成前端整批。

下一步：等待 Developer 回傳 S02 + S03 Completion Report；收到後做 architect review，再 dispatch QA。
