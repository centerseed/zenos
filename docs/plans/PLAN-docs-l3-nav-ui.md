---
spec: SPEC-docs-l3-nav-ui.md
td: TD-docs-l3-nav-ui.md
created: 2026-04-27
status: done
---

# PLAN: 文件 UI — L3 Entity 導航展開

## Tasks

- [x] S01+S02: Developer 實作（Type 補欄位 + DocL3AccordionList + DocListSidebar 展開）
  - Files:
    - `dashboard/src/types/index.ts` — 補 `Source.snapshot_summary`
    - `dashboard/src/features/docs/DocSourceList.tsx` — 補 `DocSource.snapshot_summary`
    - `dashboard/src/features/docs/DocL3AccordionList.tsx` — 新建元件
    - `dashboard/src/app/(protected)/projects/page.tsx` — tab=docs 換 DocL3AccordionList
    - `dashboard/src/features/docs/DocListSidebar.tsx` — 加 expandedDocIds state + doc_role 分流
    - `dashboard/src/__tests__/docs_l3_nav_ui_ac.test.tsx` — 填 AC stubs 實作
  - Verify: `cd dashboard && npx vitest run src/__tests__/docs_l3_nav_ui_ac.test.tsx`
  - Done Criteria:
    - AC-DOCNAV-01/02/03/04/05/06/07/08/09 test 全 PASS
    - TypeScript type check 無新錯誤

- [x] S03: QA 驗收
  - 跑 AC test suite 全 PASS
  - 瀏覽器 smoke test：原心生技專案文件分頁展開 L3 + source click inline preview
  - /docs sidebar 展開行為驗證（single/index 分流）

## Decisions
- 2026-04-27: source click 在 /docs sidebar 仍傳 doc.id（不傳 source_id），因 getDocumentContent 不支援 per-source 讀取
- 2026-04-27: inline preview fallback chain：snapshot_summary > entity.summary > "—"，不呼叫額外 API
- 2026-04-27: listDocs 已回傳完整 sources，不需要 lazy-load 設計

## Resume Point
完成。AC-DOCNAV-01~09 全 PASS，QA Verdict: PASS，待部署。
