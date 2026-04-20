---
spec: SPEC-zen-ink-redesign.md
created: 2026-04-19
status: done
---

# PLAN: Zen Ink 全站設計語言落地

## Strategy
一次到位，但分 4 階段 dispatch Developer subagent（context window 考量）。設計稿 JSX 已複製至 `dashboard/design-ref/`，subagent 直接讀取 1:1 port 成 TSX。

## Entry Criteria
- 設計稿在 `dashboard/design-ref/` — done
- SPEC 完成 — done
- 用戶確認「一次到位、UI-only、未支援欄位留空」— done

## Exit Criteria
- AC-ZEN-01 ~ AC-ZEN-15 全部 PASS
- `npm run build` 通過
- 手動 smoke test：Landing + 7 個 dashboard 頁都能 render 不報錯
- 寫 journal

## Tasks

- [ ] S01 · **Foundation + Landing** (Developer)
  - Files: `src/lib/zen-ink/tokens.ts`, `src/components/zen/{InkMark,Icons,SealChop,Chip,Btn,Section,Divider,CmdK,LandingNav,LandingFooter,FeatureCanvas}.tsx`, `src/app/page.tsx`, `src/app/layout.tsx` (fonts)
  - Ref: `design-ref/tokens.js`, `components.jsx`, `landing_parts.jsx`, `landing_a.jsx`, `landing_b.jsx`, `landing_c.jsx`
  - Verify: `/` 渲染 Variant B；`?variant=A|C` 切換；字體載入；build 通過

- [ ] S02 · **Dashboard Shell + Knowledge Map + Home + Tasks** (Developer, depends: S01)
  - Files: `src/components/zen/ZenShell.tsx` (replace AppNav role), `src/app/(protected)/layout.tsx`, `knowledge-map/page.tsx`, `home/page.tsx` (新建), `tasks/page.tsx`
  - Ref: `design-ref/components.jsx` (Shell), `page_map.jsx`, `page_home.jsx`, `page_tasks.jsx`
  - Verify: 側欄 7 項、⌘K 開啟、map/home/tasks 都能 render + TaskDrawer 開啟

- [ ] S03 · **Projects + Clients** (Developer, depends: S02)
  - Files: `(protected)/projects/page.tsx`, `clients/page.tsx`
  - Ref: `design-ref/page_projects.jsx`, `page_clients.jsx`
  - Verify: 列表 + 點擊卡片開啟 detail；pipeline 5 欄

- [ ] S04 · **Docs + Marketing** (Developer, depends: S02)
  - Files: `(protected)/docs/page.tsx`, `marketing/page.tsx`
  - Ref: `design-ref/page_docs.jsx`, `page_marketing.jsx`
  - Verify: docs 三欄、marketing list + detail (6-stage stepper)

- [ ] S05 · **QA final sweep** (QA)
  - Build pass；所有 AC PASS；smoke every route；no console errors

## Decisions
- 2026-04-19: 保留設計稿 inline-style 結構，不重寫為 Tailwind（範圍小、faithful port 較快）。
- 2026-04-19: tokens 以 TS object + `useInk()` hook 提供（呼應原設計稿），非 CSS vars——避免打架 shadcn `:root`。
- 2026-04-19: 現有 `(protected)/*` 頁面的 data hooks 全部移除，改用 design-ref 的 demo data（SPEC non-goal 已允許）。
- 2026-04-19: `/home` 是新路由；`(protected)/layout.tsx` 保持 AuthGuard。
- 2026-04-19: 品牌字「禪作」在 Landing A hero watermark 可留（視覺），但側欄 brand mark 寫「ZenOS」。節氣「穀雨」出現在 Landing hero 標籤可留（用戶選定 B 時已保留），但不在產品內當功能文案。

## Resume Point
全部完成（2026-04-19）。Phase 1-4 Developer 交付 + QA 捉出 2 個 critical（tasks empty-scope prompt / clients route guard），Architect 親自補回。Final: build PASS + 453/453 tests PASS。

## Delivery Summary
- **28 個新/改檔案**，18 個 zen 共用元件，7 個 protected pages 全 port，Landing 3 變體
- **Test results**: 38 test files / 453 tests 全 PASS（無 regression）
- **Build**: 22 routes 全 prerender 成功
- **AC Compliance**: 15/15 AC PASS
- **Route guards / access control**: 保留 — Phase 2/3 Developer 拿掉的 guest empty-scope prompt 與 shared-workspace redirect 已由 Architect 補回，multi-tenant 邊界保持
