---
spec: SPEC-marketing-automation.md
created: 2026-04-14
status: draft
---

# PLAN: Marketing Automation Spec Alignment Delta

## Why

`PLAN-marketing-automation-delivery.md` 完成的是第一輪 marketing POC。  
2026-04-14 的 spec/ADR refresh 將核心 contract 改成 `project + styles + helper deep integration`，需要新一輪 delta plan。

## Tasks

- [x] D02: 對齊 marketing data/API contract 到 project model
  - Files: `src/zenos/interface/marketing_dashboard_api.py`, `tests/interface/test_marketing_dashboard_api.py`
  - Verify: `.venv/bin/pytest -q tests/interface/test_marketing_dashboard_api.py`
  - AC Scope: `AC-MKTG-01~08`, `AC-MKTG-16`, `AC-MKTG-18~21`, `AC-MKTG-24`, `AC-MKTG-44~48`

- [x] D03: 對齊 dashboard marketing API client 與 page UI
  - Files: `dashboard/src/lib/marketing-api.ts`, `dashboard/src/app/marketing/page.tsx`, `dashboard/src/lib/__tests__/marketing-api.test.ts`
  - Verify: `npm run build --prefix dashboard` + `npm exec vitest run src/lib/__tests__/marketing-api.test.ts`
  - AC Scope: `AC-MKTG-04`, `AC-MKTG-09~15`, `AC-MKTG-18~19`, `AC-MKTG-69~102`

- [x] D04: 補齊 helper capability/permission/context-pack/state-machine
  - Files: `tools/claude-cowork-helper/server.mjs`, `dashboard/src/lib/cowork-helper.ts`, `dashboard/src/app/marketing/page.tsx`
  - Verify: helper smoke + `npm run build --prefix dashboard`
  - AC Scope: `AC-MKTG-22~23`, `AC-MKTG-53~68`, `AC-MKTG-73~88`, `AC-MKTG-99`

- [x] D05: 更新 marketing workflow skill contract 與 style composition
  - Files: `skills/release/workflows/marketing-*/SKILL.md`, `scripts/sync_skills_from_release.py`
  - Verify: `.venv/bin/pytest -q tests/test_sync_skills_from_release.py`
  - AC Scope: `AC-MKTG-25~52`

- [x] D06: QA 與正式站驗收
  - Files: 測試與 deploy script 為主
  - Verify: pytest + build + `/ /tasks /knowledge-map /marketing` smoke
  - AC Scope: `AC-MKTG-89~102` 的正式站 / E2E 驗證補完

## Decisions

- 2026-04-14: P0 不含圖片附件發佈。
- 2026-04-14: style 初始內容不由工程預填，工程只交付 CRUD/preview/composition。
- 2026-04-14: 長期 project 不做自動延展，透過重新執行 `/marketing-plan` 滾動更新。
- 2026-04-14: 先做 API/DTO 對齊，再做 helper deep integration，避免 page state 同時承受兩種 blast radius。

## Dependencies

- D03 depends on D02
- D04 depends on D02 and can overlap late D03
- D05 depends on D02
- D06 depends on D03, D04, D05

## Review Gate

- `review` 不再代表「工程第一輪寫完」，只代表「該 task 綁定的 AC 已有可執行測試，且綠燈或明確標記 xfail」。
- build / unit / smoke 只證明「技術切片可用」，不能單獨作為 spec 驗收。
- `tests/spec_compliance/test_marketing_ac.py` 是 marketing spec 的 release dashboard：
  - `pass` = 已實作且有 executable contract
  - `xfail` = 已知未完成 / 僅 partial / 缺 E2E
  - `fail` = regression 或 spec drift
- 新增或修改 marketing task 時，必須在 task description / AC 中標註對應的 `AC-MKTG-*` 範圍。

## Action Layer Mapping

- Plan: `b3a66bb409a7412381e883560c4582df`
- D02: `64f2494733b04639b449466d50d27333`
- D03: `82f22fed0c7d46deb7c1a0ce167642c9`
- D04: `bdff05bfdb03431e9b228afa8a4c1219`
- D05: `d0ef354861414293949d5ba0f6d4d476`
- D06: `f19a933ff7294df1a29017ad0b451b25`

## Current Status

- Plan 已建立並進入 `active`
- D02 已完成第一輪 backend contract 落地；其中已落地 AC 已轉成 executable tests
- D03 已完成前端 contract 與 UI 第一輪對齊；但大量 UX / E2E AC 仍待補測
- D04 已完成 helper capability/context-pack/state-machine 第一輪；helper 深度互動 AC 仍有 partial 項
- D05 已完成 skill contract 與 style composition 說明更新；workflow runner 類 AC 尚未完成
- D06 已完成 deploy script 與正式站 smoke；但這不等於 spec 全綠
- 2026-04-14 補充：過去把 task 提前標成 `review` 的判準過弱，已改為 AC-gated semantics

## Resume Point

下一步不是直接 PM 驗收，而是：
1. 先把 `tests/spec_compliance/test_marketing_ac.py` 中仍為 `xfail` 的 AC 逐批轉成 executable tests
2. 補齊 workflow runner / helper 深度互動 / frontend E2E
3. 只有當對應 AC 綠燈後，相關 task 才能正式進 `review`
