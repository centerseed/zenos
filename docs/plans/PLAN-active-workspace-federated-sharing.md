---
spec: SPEC-identity-and-access.md
created: 2026-04-08
status: done
---

# PLAN: Active Workspace 與 Federated Sharing 落地

## Tasks
- [x] S01: 收斂 active workspace context contract (2026-04-08, PASS)
  - Task: `d6fbb764206a49f48ff0072a814c6531`
  - Files: `dashboard/src/lib/auth*`, `dashboard/src/lib/partner.ts`, `src/zenos/interface/dashboard_api.py`, `src/zenos/interface/admin_api.py`
  - Verify: `pytest tests/interface/test_dashboard_api.py tests/interface/test_admin_api.py`

- [x] S02: 重做 workspace entry 與主導航 (2026-04-08, PASS)
  - Task: `c005cb06cbc849399c3c921c9aca7c50`
  - Files: `dashboard/src/components/AppNav.tsx`, `dashboard/src/app/page.tsx`, `dashboard/src/app/tasks/page.tsx`, `dashboard/src/app/login/page.tsx`
  - Verify: `cd dashboard && npx vitest run src/__tests__/AppNav.test.tsx` 或相關 UI 測試

- [x] S03: 完成 Products rename 與前端 surface 對齊 (2026-04-08, PASS)
  - Task: `7ba1ecc06f87457ca2aa7b744cb909c6`
  - Files: `dashboard/src/components/*`, `dashboard/src/app/*`, `dashboard/src/types/index.ts`, `docs/specs/SPEC-client-portal.md`
  - Verify: `cd dashboard && npx vitest run` 確認所有快照/UI 測試通過；手動確認主導航、頁面標題、路由均無 `Projects` 殘留

- [x] S04: 補 server-side query slicing (2026-04-08, PASS)
  - Task: `7f3ee35892064597b005601408915b75`
  - Files: `src/zenos/application/ontology_service.py`, `src/zenos/infrastructure/sql_repo.py`, `src/zenos/interface/tools.py`, `src/zenos/interface/dashboard_api.py`
  - Verify: `pytest tests/interface/test_permission_isolation.py tests/interface/test_permission_visibility.py tests/interface/test_tools.py`

- [x] S05: 補 guest write guard 與 L3 建立限制 (2026-04-08, PASS)
  - Task: `b89b2ef2e4ed4a6db220baf4f300697d`
  - Files: `src/zenos/application/ontology_service.py`, `src/zenos/domain/models.py`, `src/zenos/interface/tools.py`, `tests/application/test_validation.py`
  - Verify: `pytest tests/application/test_validation.py`

- [x] S06: 補 route guard 與 shared workspace app boundary (2026-04-08, PASS)
  - Task: `a36d536d9bd64ce0a6296a94b8d0b6e7`
  - Files: `dashboard/src/app/setup/page.tsx`, `dashboard/src/app/team/page.tsx`, `dashboard/src/app/tasks/page.tsx`, `dashboard/src/app/page.tsx`
  - Verify: `cd dashboard && npx vitest run src/__tests__/` 確認 route guard 相關測試通過

- [x] S07: 跑 identity/access regression (2026-04-08, PASS)
  - Task: `1a5ec33f7fa84d01a5bc00aff209f966`
  - Files: `tests/interface/test_dashboard_api.py`, `tests/interface/test_permission_isolation.py`, `tests/interface/test_permission_visibility.py`, `dashboard/src/__tests__/*`
  - Verify: `.venv/bin/pytest tests/interface/test_dashboard_api.py tests/interface/test_permission_isolation.py tests/interface/test_permission_visibility.py -q && cd dashboard && npx vitest run`

- [x] S08: QA 驗收與文件回寫 (2026-04-08, PASS)
  - Task: `3a7509c452834bb4bf4d2149f7837e54`
  - Files: `docs/specs/TC-identity-and-access.md`, `docs/designs/TD-active-workspace-federated-sharing-implementation.md`
  - Verify: `TC-identity-and-access` P0 全通過

## Decisions
- 2026-04-08: `active workspace context` 是正式執行單位，前後端不得再只靠全域 `workspaceRole` 裁切。
- 2026-04-08: `product(L1)` 是分享與導航主軸；`project` 收斂為 L3 entity。
- 2026-04-08: shared workspace 的 `member` / `guest` 主導航目前統一為 `Knowledge Map / Products / Tasks`。
- 2026-04-08: CRM / Team / Setup / application layer 不納入 shared workspace surface。

## Risks
- `Projects -> Products` 可能不只影響 copy，也影響 route naming、測試快照與歷史文件。
- 若 query slicing 沒完全在 server 端做，前端圖譜仍可能洩漏未授權關聯。
- 若先改 UI 再改 workspace context contract，容易出現多處 duplicated permission logic。

## Resume Point
已完成。S01–S08 全部 PASS。TC-identity-and-access P0 S1–S16 全通過。TD status = approved v1.0。
