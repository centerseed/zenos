---
created: 2026-04-22
status: in-progress
---

# PLAN: Dashboard UI Convergence

## Goal

收斂目前 `/tasks`、`/projects` 兩條主幹中「UI 看起來有、但真實行為或資訊契約沒對上」的缺口，讓使用者在主要操作路徑上不再遇到互相矛盾的規則、placeholder 指標或缺半截的 recap。

## Entry Criteria

- 已完成一次實際盤點，明確定位目前主要缺口
- 不再擴散範圍，只收這輪已確認的核心問題
- 本輪以 dashboard 本地實作與 AC 驗證為準，不先等待新 spec 流程

## Local Acceptance Criteria

### AC-DUC-00 L1 collaboration roots are first-class product surfaces

- Given ZenOS 內存在 `level=1`、`parent_id = null` 的 `company` 或 `product` entity
  When 該 entity 承擔的是可分享、可協作的 root subtree
  Then `/tasks` 的 Task Hub 與 `/projects` 的列表都必須把它視為同一級的產品視圖入口，不得因為 `type=company` 就排除。

- Given 使用者從這類 L1 root entity 進入產品視圖
  When 建立 task / plan / milestone 或查詢該 entity 底下的 open work
  Then UI、API、server validation 必須使用同一套 ownership contract，不得出現「看得到但不能操作」。

### AC-DUC-01 Task status rules are consistent

- Given 使用者在 `TaskBoard` 或 `TaskDetailDrawer` 嘗試把非 `review` 的 task 直接改成 `done`
  When 操作完成
  Then 兩個入口都必須給出同一套規則：不得直接完成，且不得出現一個能強制執行、另一個只能阻擋的矛盾行為

- Given 使用者把 `review` 狀態的 task 改成 `done`
  When 操作完成
  Then 兩個入口都必須走同一個驗收語義，不得一邊走 `confirm`、另一邊走普通 `update`

### AC-DUC-02 Task Hub first screen is complete enough

- Given 使用者進入 `/tasks`
  When 第一屏載入完成
  Then 必須同時看得到：
  - portfolio recap
  - products by health
  - milestone / plan radar
  - morning / recent change summary
  - personal risk summary
  - filter snapshot
  - execution board 二級入口
  - task copilot rail

### AC-DUC-03 Projects list only shows real metrics

- Given 使用者進入 `/projects`
  When 列表載入完成
  Then KPI strip 不得再顯示硬編碼 placeholder `—` 來冒充指標

- Given 使用者查看任一產品卡片
  When 卡片渲染完成
  Then card footer 只可顯示真實可追溯的欄位值，不得再以 `成員 — / 文件 — / —` 這類 placeholder 充數

### AC-DUC-04 CTA labels match real behavior

- Given 使用者在 `/projects` 使用建立產品相關 CTA
  When 按鈕可見
  Then 文案必須明確表達真實行為；若目前只能前往 Knowledge Map 建立，CTA 不得偽裝成已完成的 inline create flow

## Tasks

- [ ] S01: 寫入 local convergence plan 與 AC
- [ ] S01A: 把「L1 root collaboration entity（product/company）都是產品視圖入口」寫入 spec 與 AC
- [ ] S02: 統一 `TaskBoard` / `TaskDetailDrawer` 的 `done` 狀態規則
- [ ] S03: 補齊 `/tasks` 首屏 morning / personal risk / filter snapshot / recent changes
- [ ] S04: 移除 `/projects` 列表 placeholder，改用真實 metrics
- [ ] S05: 對齊 `/projects` 建立產品 CTA 文案與真實行為
- [ ] S05A: 對齊 tasks / projects / task create / task-plan-milestone ownership 為 L1 collaboration root contract
- [ ] S06: 補測試並逐條對 AC 驗收

## Verify

- `dashboard/src/__tests__/TaskBoard.test.tsx`
- `dashboard/src/app/(protected)/tasks/page.test.tsx`
- `dashboard/src/app/(protected)/projects/page.test.tsx`
- `tests/application/test_validation_wiring.py`
- `tests/application/test_plan_service.py`
- `tests/interface/test_dashboard_api.py`
- `npm run lint`
- `npm run build`

## Exit Criteria

- `AC-DUC-01~04` 全部滿足
- `AC-DUC-00~04` 全部滿足
- 相關測試通過
- 不再存在本輪已定位的 placeholder / 規則矛盾 / 假 CTA
