---
spec: SPEC-dashboard-ai-rail.md
design: TD-dashboard-ai-rail-implementation.md
created: 2026-04-15
status: draft
---

# PLAN: Dashboard AI Rail Implementation

## Why

`SPEC-dashboard-ai-rail.md` 已把 shared AI Rail 的產品協議定出來，`TD-dashboard-ai-rail-implementation.md` 已把實作切片定義成 shared shell、marketing apply、CRM artifact 三層。

下一步不能直接零散修頁面，否則很容易又回到：

- helper 共用，但 UI 分叉
- marketing 邏輯藏在 page local state
- CRM 只共用 helper client，沒共用 shell

這份 plan 的目的是把 AI Rail 收斂工作變成可派工、可驗收、可續做的 implementation sequence。

## Tasks

- [ ] D01: 抽出 copilot foundation 與 shared AI Rail shell
  - Files: `dashboard/src/components/ai/`, `dashboard/src/lib/copilot/`, `dashboard/src/lib/cowork-helper.ts`
  - Verify: foundation unit tests + shell interaction tests
  - AC Scope: `AC-AIR-01~13`, `AC-AIR-20~21`

- [ ] D02: 收斂 marketing 成單一 rail 與 apply adapters
  - Files: `dashboard/src/app/marketing/page.tsx`, `dashboard/src/app/marketing/copilot-presets.ts`, `dashboard/src/app/marketing/copilot-adapters.ts`
  - Verify: marketing interaction tests + build
  - AC Scope: `AC-AIR-14~16`, `AC-AIR-22`

- [ ] D03: 收斂 CRM 成 artifact rail presets
  - Files: `dashboard/src/app/clients/deals/[id]/CrmAiPanel.tsx`, `dashboard/src/app/clients/deals/[id]/crm-copilot-presets.ts`
  - Verify: CRM behavior tests + build
  - AC Scope: `AC-AIR-17~19`, `AC-AIR-22`

- [ ] D04: 補齊 regression、contract tests 與跨頁一致性驗收
  - Files: `dashboard/src/lib/__tests__/cowork-helper.test.ts`, `dashboard/src/app/marketing/cowork-chat.test.tsx`, `dashboard/src/app/clients/deals/[id]/CrmAiPanel.behavior.test.tsx`, 新增 `dashboard/src/lib/copilot/*.test.ts`
  - Verify: vitest full run + dashboard build
  - AC Scope: `AC-AIR-01~22` 的測試補完與 release gate

## Dependencies

- D02 depends on D01
- D03 depends on D01
- D04 depends on D02 and D03

## Dependency Graph

```text
D01 ──┬──→ D02 ──┐
      │          ├──→ D04
      └──→ D03 ──┘
```

## Decisions

- 2026-04-15: 先抽 shell foundation，再接 marketing / CRM；不接受先在 CRM 或 marketing 各自 patch 出第三種中間態。
- 2026-04-15: marketing page 的 AI 入口保留區塊語意，但桌機版只允許單一 rail instance。
- 2026-04-15: `marketing_prompt_draft` 的 AI 寫回只允許 draft update，不允許 publish side effect。
- 2026-04-15: CRM briefing / debrief 保留 artifact 體驗，不強行改成 apply UX。

## Review Gate

- D01 不完成，D02 / D03 不得各自發展新的 shell state。
- D02 完成不代表 AI Rail 完成；只有 marketing path 對齊。
- D03 完成不代表 AI Rail 完成；只有 CRM path 對齊。
- D04 完成前，不得宣稱 shared AI Rail 已交付。
- `review` 的最小標準：
  - 對應 AC scope 有 executable tests
  - 無未知 fail
  - 若有 `xfail`，task 只能宣稱 partial / engineering slice complete，不得宣稱 spec complete

## Deliverable Boundary

只有同時滿足以下條件，這個 plan 才能算完成：

1. Dashboard 內存在獨立的 shared AI Rail shell
2. marketing page 已改成單一 rail instance
3. CRM briefing / debrief 已改走 shared shell 的 artifact mode
4. `prompt draft` AI 寫回不會直接 publish
5. 共用 shell / marketing apply / CRM artifact 三條主路徑均有自動化測試

## Resume Point

下一步應先開 `D01`。  
因為 storage key、session policy、structured result、shared diagnostics 都是 marketing / CRM 共同依賴；不先做 foundation，後面只會繼續分叉。
