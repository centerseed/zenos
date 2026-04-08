---
spec: SPEC-identity-and-access.md
created: 2026-04-08
status: done
---

# PLAN: Identity Access Consolidation

## Tasks
- [x] S01: ADR-018 定稿並鎖定實作範圍 (2026-04-08)
  - Files: `docs/decisions/ADR-018-identity-access-runtime-alignment.md`
  - Verify: `sed -n '1,240p' docs/decisions/ADR-018-identity-access-runtime-alignment.md`
- [x] S02: Backend 權限 runtime 對齊 Prosumer-First（workspaceRole / visibility / guest write boundary） (2026-04-08)
  - Files: `src/zenos/domain/partner_access.py`, `src/zenos/application/ontology_service.py`, `src/zenos/interface/dashboard_api.py`, `src/zenos/interface/admin_api.py`, `src/zenos/interface/tools.py`, `migrations/20260408_0013_identity_access_visibility_alignment.sql`
  - Verify: `pytest tests/interface/test_dashboard_api.py tests/interface/test_permission_visibility.py tests/interface/test_permission_isolation.py -q`
- [x] S03: Frontend 導航與管理 UI 對齊（移除公司式 Team/Setup/Clients 主流程，保留 Guest shared-L1 視角） (2026-04-08)
  - Files: `dashboard/src/components/AppNav.tsx`, `dashboard/src/lib/api.ts`, `dashboard/src/lib/partner.ts`, `dashboard/src/types/index.ts`, `dashboard/src/app/team/page.tsx`, `dashboard/src/app/setup/page.tsx`, related route guards/tests
  - Verify: `cd dashboard && npx vitest run src/__tests__/auth-partner-mapping.test.ts src/__tests__/client-portal.test.tsx src/__tests__/team-page-actions.test.tsx`
- [x] S04: QA 驗收 shared-L1 / own-workspace / guest UI concealment (2026-04-08, CONDITIONAL PASS)
  - Files: `tests/interface/test_permission_isolation.py`, `dashboard/src/__tests__/client-portal.test.tsx`, QA verdict artifact
  - Verify: QA Verdict
- [x] S05: 清理 legacy visibility surface（移除前端 `role-restricted` 可寫/可選殘留） (2026-04-08, PASS)
  - Task: `817b0dd678be4fefb7ce264af131835c`
  - Files: `dashboard/src/components/NodeDetailSheet.tsx`, `dashboard/src/components/EntityTree.tsx`, `dashboard/src/types/index.ts`, related tests
  - Verify: `cd dashboard && npx vitest run src/__tests__/NodeDetailSheet.test.tsx`
- [x] S06: 套用並驗證 identity/access visibility migration (2026-04-08)
  - Task: `c828d73f31c7407795da176229dd17ad`
  - Files: `migrations/20260408_0013_identity_access_visibility_alignment.sql`, `scripts/migrate.sh`
  - Verify: `./scripts/migrate.sh --status && ./scripts/migrate.sh`

## Decisions
- 2026-04-08: 採用 `workspaceRole` 作為正規語意，`accessMode` 僅留作相容層。
- 2026-04-08: `hhh1230` 的目標情境定義為「Barry workspace 的 Guest + 自己 workspace 的 Owner」，不得以 company member 模型近似。
- 2026-04-08: Team/Department/company-centric UI 不再是主流程；Guest 只保留 Projects/Tasks。
- 2026-04-08: ADR-018 已定稿並批准；但 migration 與 legacy visibility surface 尚未關閉，因此 PLAN 維持 in-progress 直到 S05/S06 完成。
- 2026-04-08: S05 經 QA 驗收為 PASS；S06 已在真實環境套用 migration，`20260408_0013` 狀態從 Pending 變為 Applied，且 DB constraint 已驗證僅允許 `public/restricted/confidential`。

## Resume Point
本輪已完成。ADR-018 已完成文件定稿、前端 legacy visibility surface 清理、migration 套用與 DB 驗證；整體 verdict = PASS。
