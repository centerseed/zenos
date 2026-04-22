---
type: TD
id: TD-task-surface-reset-implementation
status: Draft
linked_spec: SPEC-task-surface-reset
created: 2026-04-22
updated: 2026-04-22
---

# 技術設計：Task Surface Reset 實作

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-task-view-clarity.md`
  - 發現：已定義 `/tasks` 的狀態口徑、晨報、跨專案摘要與 richer filter，但明確把「全新 IA 重做」列為非目標。
- `docs/designs/DESIGN-task-multilayer-workspace.md`
  - 發現：新的目標 IA 已被定義成 `Task Hub → Product Console → Task Detail`，其中 `/tasks` 第一屏必須先做全產品 milestone / plan recap。
- `docs/specs/SPEC-task-kanban-operations.md`
  - 發現：已定義 task create / edit / review / handoff 應存在於 `/tasks` 的操作面，未定義 hierarchy 應如何呈現。
- `docs/specs/SPEC-project-progress-console.md`
  - 發現：`/projects/[id]` 應是 management-layer，不該變成第二個 task board。
- `docs/specs/SPEC-dashboard-v2-ui-refactor.md`
  - 發現：過去曾把 structure 與 content 拆成不同區，但 task surface 並沒有真正落實這個邊界。
- `dashboard/src/app/(protected)/tasks/page.tsx`
  - 發現：`/tasks` 已承接摘要、filters、task board 與所有 task 操作，是 execution layer 主場。
- `dashboard/src/components/TaskBoard.tsx`
  - 發現：看板本身只該做卡片群組與拖曳，但目前 detail drawer 成為資訊傾倒點。
- `dashboard/src/components/TaskDetailDrawer.tsx`
  - 發現：同時承擔 hierarchy、meta、description、rich fields、attachments、handoff chain、result，頁面責任失控；`Hierarchy` 區直接佔第一屏。
- `dashboard/src/features/projects/ProjectProgressConsole.tsx`
  - 發現：products 頁右欄 copilot 目前只是普通 grid item，沒有 page-level sticky contract。
- `dashboard/src/features/projects/ProjectRecapRail.tsx`
  - 發現：copilot shell 已共用，但 page layout 沒把它當固定 rail 處理。
- `dashboard/src/features/projects/ProjectOpenWorkPanel.tsx`
  - 發現：project console 已正確把 subtasks 收在 parent 底下，這個規則可反向成為 task surface 的結構設計基準。

### 搜尋但未找到

- `dashboard/src/components/` 中搜尋 `TaskStructureView` → 無結果
- `dashboard/src/components/TaskDetailDrawer.tsx` 中搜尋 `tab` / `structure tab` → 無正式結構模式
- `dashboard/src/app/(protected)/tasks/page.tsx` 中搜尋 `copilot rail` / `sticky` → 無 screen-level rail contract

### 我不確定的事（明確標記）

- [未確認] Phase 0 是否需要保留同一個 `TaskDetailDrawer` 元件並加 tab，或拆成 `TaskDetailDrawer + TaskStructurePanel` 兩個元件；本 TD 先兩案擇一，以低風險優先。
- [未確認] mobile 下 structure view 是否跟 detail 共用同一個 drawer stack；本 TD 先要求功能邊界，不先鎖互動動畫。

### 結論

可以開始設計。

本輪不是 patch 現有 section，而是做以下邊界重切：

1. `/tasks` 留在 task 主入口，但第一屏升級成 `Task Hub`
2. `TaskDetailDrawer` 收斂成 single-task operations
3. hierarchy 抽成 structure mode
4. copilot rail 成為正式 shell contract
5. `/tasks -> /projects?id=&focus=` 成為正式 drill-down contract

## Spec 衝突檢查

- `SPEC-task-surface-reset` vs `SPEC-task-view-clarity`：無衝突。前者定義 screen boundary，後者定義數字口徑與摘要規則。
- `SPEC-task-surface-reset` vs `SPEC-task-kanban-operations`：無衝突。前者定義操作應出現在哪個 screen，後者定義操作本身。
- `SPEC-task-surface-reset` vs `SPEC-project-progress-console`：無衝突。前者要求 product 頁維持 management-layer，後者已明定同方向。

結論：**Spec 衝突檢查：無衝突。**

## 設計方向

### 美學方向

維持現有 Zen Ink 的紙本感與高密度資訊語言，但改為 **task-first operational console**：

- 主內容先回答「現在要做哪件事」
- 結構資訊退到 secondary layer
- rail 與 drawer 都視為正式工作容器，不再是補丁

### 關鍵設計決策

1. `Hierarchy` 從 detail 第一屏移出
   - 理由：它是導航上下文，不是單卡操作的第一優先。
2. `TaskDetailDrawer` 改為 `Overview / Context / Structure / History` 分層
   - 理由：目前問題不是資料太多，而是沒有模式切換。
3. `Task Copilot` 固定為右欄 rail primitive
   - 理由：只要在 desktop，它就必須是穩定工作區，不能跟內容一起滑走。
4. `/projects/[id]` 與 `/tasks` 明確分工
   - 理由：product progress 與 task execution 不能混成一頁。

## Screen Map

### 1. `/tasks`

主問題分兩層：

第一層：

> 目前所有產品推到哪裡，哪個 milestone / plan 值得我先下鑽？

第二層：

> 現在有哪些工作值得我先處理？

第一屏：

- Portfolio Recap
- Products by Health
- Milestone / Plan Radar
- Morning Report
- Global Summary
- Cross-project Summary
- Filter Snapshot
- Kanban / Pulse / Execution Board 二級入口
- Sticky Task Copilot rail

不得預設出現：

- hierarchy inspector
- same-level tree
- plan outline 大區塊

### 2. `TaskDetailDrawer`

預設 landing：`Overview`

包含：

- header：title / status / priority / dispatcher
- action strip：next valid action、handoff、review
- risk strip：blocked / overdue / stalled
- body：description、acceptance criteria、result、attachments

次級層：

- `Context`
  - linked entities
  - richer fields（可收合）
- `Structure`
  - parent / siblings / direct subtasks / plan outline
- `History`
  - handoff chain
  - comments

### 3. `Task Structure View`

只處理：

- current task position
- parent
- sibling summary
- direct subtasks
- plan outline

不處理：

- rich field editing
- review actions
- attachments

### 4. `/projects/[id]`

維持：

- milestone strip
- active plans
- grouped open work
- recent progress
- sticky task copilot rail

新增：

- `focus=milestone:<id>`
- `focus=plan:<id>`

drill-down 才進 task detail；只有使用者明確要求 board，才切到 `/tasks` 的 execution layer。

## 元件與檔案切分

### A. 保留並重構

- `dashboard/src/app/(protected)/tasks/page.tsx`
  - 第一屏改成 Task Hub
  - execution board 退到第二層
- `dashboard/src/components/TaskBoard.tsx`
  - 保留看板與拖曳能力
  - 移除對 detail 內部 IA 的預設假設
- `dashboard/src/components/TaskDetailDrawer.tsx`
  - 收斂為 overview-first
  - 拆出 structure/history 區
- `dashboard/src/features/projects/ProjectProgressConsole.tsx`
  - 補 rail sticky contract

### B. 新增元件

```text
dashboard/src/features/tasks/
  TaskHubRecap.tsx
  ProductHealthList.tsx
  MilestonePlanRadar.tsx
dashboard/src/components/
  TaskDetailOverview.tsx
  TaskDetailContext.tsx
  TaskStructurePanel.tsx
  TaskHistoryPanel.tsx
```

責任：

- `TaskHubRecap`
  - `/tasks` 第一屏全產品高層摘要
- `ProductHealthList`
  - product list / row，支援進 product 與 focus 下鑽
- `MilestonePlanRadar`
  - 顯示 blocked / overdue / review 的高優先 milestone / plan
- `TaskDetailOverview`
  - task 主資訊與主操作
- `TaskDetailContext`
  - linked entities + richer fields
- `TaskStructurePanel`
  - hierarchy / plan outline
- `TaskHistoryPanel`
  - handoff chain / comments / timeline

### C. Page Shell

- `/tasks` page
  - 明確建立 `main column + sticky rail` shell
- `/projects/[id]`
  - 套同一個 rail shell contract

## 實作方案

### 方案 A：在既有 Drawer 上加 Tab，並把 `/tasks` 升級成雙層主視圖（推薦）

做法：

- 保留 `TaskDetailDrawer`
- 增加 `Overview / Context / Structure / History` tab
- 把現有 hierarchy 區移到 `Structure`
- 把 handoff chain / comments 放到 `History`
- richer fields 改到 `Context`

優點：

- 改動集中
- 風險最低
- 不需要大搬 route state
- 可沿用現有 `/projects?id=` query state，直接擴充 `focus`

缺點：

- 仍受單一 drawer 結構限制

### 方案 B：拆成 Drawer + Secondary Panel

做法：

- detail 只留 overview/context
- structure 用二次 panel / overlay 顯示

優點：

- screen boundary 最清楚

缺點：

- 實作與狀態同步成本更高

結論：Phase 0 採 **方案 A**。先把 mode 分出來，再評估 Phase 1 是否升級成獨立 structure panel。

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-TSR-01 | `/tasks` 第一屏先顯示全產品 recap，不是 hierarchy / 完整 task board | `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/features/tasks/TaskHubRecap.tsx` | `acTsr01TasksFirstFoldTaskHub` | STUB |
| AC-TSR-02 | task detail 第一屏不是 plan outline / same-level | `dashboard/src/components/TaskDetailDrawer.tsx` | `acTsr02TaskDetailOverviewFirst` | STUB |
| AC-TSR-03 | structure 有正式入口但非預設 | `dashboard/src/components/TaskDetailDrawer.tsx`, `dashboard/src/components/TaskStructurePanel.tsx` | `acTsr03StructureModeExplicitEntry` | STUB |
| AC-TSR-04 | `/tasks` 第一屏顯示各 product 的 milestone / plan 概況 | `dashboard/src/features/tasks/TaskHubRecap.tsx`, `dashboard/src/features/tasks/ProductHealthList.tsx` | `acTsr04TaskHubShowsProductsByHealth` | STUB |
| AC-TSR-05 | `/tasks` 直接顯示 product 風險訊號 | `dashboard/src/features/tasks/ProductHealthList.tsx`, `dashboard/src/features/tasks/MilestonePlanRadar.tsx` | `acTsr05TaskHubShowsRiskSignals` | STUB |
| AC-TSR-06 | 點 milestone / plan 進入 `/projects?id=&focus=` | `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/app/(protected)/projects/page.tsx` | `acTsr06TaskHubDrillDownKeepsFocus` | STUB |
| AC-TSR-07 | detail 第一屏看得到主操作與風險 | `dashboard/src/components/TaskDetailOverview.tsx` | `acTsr07TaskDetailPrimaryOpsVisible` | STUB |
| AC-TSR-08 | hierarchy 未切換前只以 summary 呈現 | `dashboard/src/components/TaskDetailDrawer.tsx` | `acTsr08HierarchyCollapsedByDefault` | STUB |
| AC-TSR-09 | structure mode 可辨識 current / parent / subtasks / outline | `dashboard/src/components/TaskStructurePanel.tsx` | `acTsr09StructureModeShowsRelativePosition` | STUB |
| AC-TSR-10 | 從 structure 可切換相鄰 task 而不丟 context | `dashboard/src/components/TaskStructurePanel.tsx` | `acTsr10StructureNavigationKeepsContext` | STUB |
| AC-TSR-11 | desktop copilot rail 固定於 viewport | `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/features/projects/ProjectProgressConsole.tsx` | `acTsr11CopilotRailSticky` | STUB |
| AC-TSR-12 | copilot rail 文案必須對應當前 screen | `dashboard/src/features/projects/ProjectRecapRail.tsx`, `dashboard/src/lib/copilot/*` | `acTsr12CopilotRailScopedLanguage` | STUB |
| AC-TSR-13 | 第一視線是操作與風險，不是 hierarchy metadata | `dashboard/src/components/TaskCard.tsx`, `dashboard/src/components/TaskDetailOverview.tsx` | `acTsr13VisualPriorityExecutionFirst` | STUB |
| AC-TSR-14 | `/tasks` 只有一個 primary CTA | `dashboard/src/app/(protected)/tasks/page.tsx` | `acTsr14SinglePrimaryCtaTasks` | STUB |
| AC-TSR-15 | `TaskDetailDrawer` 只有一個狀態對應主操作 | `dashboard/src/components/TaskDetailOverview.tsx` | `acTsr15SinglePrimaryCtaDetail` | STUB |
| AC-TSR-16 | `/tasks -> /projects -> back` 保留上下文 | `dashboard/src/app/(protected)/tasks/page.tsx`, `dashboard/src/app/(protected)/projects/page.tsx` | `acTsr16ReturnKeepsTaskHubContext` | STUB |

## 實作切分

### Slice 1：Rail Shell Contract

- 補 `/tasks` 與 `/projects/[id]` 的 sticky rail 外層
- 統一 rail 的 top offset / max height / mobile drawer contract

### Slice 2：Task Hub First Fold

- `/tasks` 首屏加入全產品 recap
- execution board 下沉到二級
- 產品 / milestone / plan 建立 drill-down CTA

### Slice 3：Task Detail IA Reset

- 抽 `TaskDetailOverview`
- hierarchy 從預設第一屏移除
- 建立 `Overview / Context / Structure / History` mode

### Slice 4：Structure Panel

- 抽 `TaskStructurePanel`
- 保留 current / parent / subtasks / outline
- 支援 task 間導航

### Slice 5：Product Focus Query Contract

- `/projects` 擴充 `focus` query state
- 支援 `milestone` / `plan` focus
- back / refresh 不丟上下文

### Slice 6：Execution-first Visual Cleanup

- `/tasks` 第一屏只保留 execution summary
- 降低 breadcrumb、plan UUID、same-level metadata 的視覺權重
- task card / detail header 以風險與主操作為主

## Done Criteria

1. `/tasks` 第一屏先顯示全產品 milestone / plan recap，不再直接掉進完整 execution board。
2. 使用者能從 `/tasks` 的 product / milestone / plan 直接下鑽到 `/projects?id=&focus=`。
3. `TaskDetailDrawer` 預設打開時，第一屏可直接做單張 task 的主操作，不需先略過 hierarchy 區。
4. hierarchy 仍可被查看，但必須透過正式 structure mode 進入。
5. desktop 下的 task copilot rail 在 `/tasks` 與 `/projects/[id]` 都固定於 viewport 內。
6. 至少一組自動化測試覆蓋 `Task Hub first fold`、`detail overview-first`、`focus drill-down` 與 `sticky rail`。
7. 現有 `SPEC-task-view-clarity`、`SPEC-task-kanban-operations` 的核心能力不得因這次重構而消失。

## 交付建議

這份 TD 可直接交給 architect 做 implementation 切票，優先順序：

1. Rail shell contract
2. Task Hub first fold
3. Task detail IA reset
4. Structure mode
5. Product focus query contract
6. 視覺清理與 CTA 收斂

## Changelog

- 2026-04-22: initial draft. Converts the current section-heavy task UI into explicit screen modes that architect can dispatch.
