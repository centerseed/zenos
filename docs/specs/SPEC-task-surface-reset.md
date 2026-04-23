---
type: SPEC
id: SPEC-task-surface-reset
status: Draft
ontology_entity: l3-action
created: 2026-04-22
updated: 2026-04-23
depends_on: SPEC-task-view-clarity, SPEC-task-kanban-operations, SPEC-task-governance, SPEC-project-progress-console, SPEC-dashboard-ai-rail
---

> **Layering note（2026-04-23）**：本 SPEC 定義 **task-related screens 的責任邊界**（Task Hub / Product Console / Task Detail / AI Rail），不重定義 task schema、status 或 lifecycle——那些 canonical 在 `SPEC-task-governance §3` + `SPEC-ontology-architecture v2 §9`。舊 refactor-index 曾把本檔標為 DELETE（被 task-governance 取代），此判斷不成立：本 SPEC 是 UI 層，與 task-governance 的 L3-Action 治理正交。

# Feature Spec: Task Surface Reset

## 背景與動機

目前 task 相關畫面不是單點 bug，而是整個 surface 的責任邊界混亂：

1. `/tasks` 同時想做晨報、跨專案摘要、kanban、hierarchy 入口、detail 編輯，卻沒有真正承接「全產品任務概況」。
2. `TaskDetailDrawer` 同時承擔單卡操作、plan 導航、same-level 對照、subtask tree、handoff timeline、rich field editor。
3. `/projects/[id]` 是 product progress console，但畫面與 task 執行層仍有重疊。
4. 右側 `Task Copilot` 沒有被視為正式的 screen primitive，而是附著在各頁的局部補丁。
5. 使用者想先從高層次理解所有產品的 milestone / plan 進度，再逐層下鑽，但現有 task surface 沒有這條明確路徑。

結果不是資訊不夠，而是每個畫面都在同時回答太多問題。使用者看得到很多資料，卻無法快速判斷「我現在該做什麼」。

本 spec 的目的，是重新定義整個 task surface 的 screen contract，讓 `/tasks`、`TaskDetailDrawer`、`Hierarchy/Structure`、`/projects/[id]` 各自只做一件事，並形成一條穩定的多層次工作路徑：

`Task Hub（全局）` → `Product Console（單一產品）` → `Task Detail（單張工作）`

## 目標

1. 使用者在 5 秒內看懂「這一頁主要是拿來做什麼」。
2. `/tasks` 第一屏成為全產品的 milestone / plan recap 入口，而不是直接掉進 task board。
3. `/projects/[id]` 成為單一產品的管理層 console，而不是 task board 替身。
4. `TaskDetailDrawer` 成為單張 task 操作面，而不是結構總覽頁。
5. task hierarchy 有正式入口，但不得搶走全局 recap 或單卡操作的主視角。
6. `Task Copilot` 在 desktop 是穩定固定的 side rail，在 mobile 是可開關的 drawer，不再跟主內容一起漂移。

## 非目標

- 不重定義 task / plan / milestone / subtask 的 core schema。
- 不新增新的 AI runtime 或新的 helper protocol。
- 不在本 spec 定義新的 task status。
- 不直接重做 knowledge map 或 entity graph 的 IA。

## 目標使用者

- 每日推進任務的 PM / owner / reviewer
- 需要處理單張 task 的執行者
- 需要看 plan/task/subtask 結構的 Architect / PM

## 核心原則

1. **一個畫面只回答一個主問題。**
2. **先全局 recap，再進局部操作。**
3. **操作優先於結構。**
4. **Hierarchy 是輔助導航，不是預設主角。**
5. **Copilot 是正式 screen primitive，不是浮動補丁。**
6. **同一資料只能有一個預設閱讀方式。**

## Screen Contract

### 1. `/tasks` = Task Hub

`/tasks` 的第一層主問題只能是：

> 目前所有產品推到哪裡，哪個 milestone / plan 值得我先下鑽？

此頁必須包含：

- 全產品高層 recap
- products by health / stage
- milestone / plan radar
- 晨報 / 個人風險摘要
- 全域摘要與跨專案摘要
- filter snapshot
- execution board 的二級入口
- task copilot rail

此頁不得預設包含：

- 完整 hierarchy inspector
- same-level task 對照區
- plan outline 大圖
- 會把主畫面變成結構瀏覽器的樹狀區塊

此頁的第二層才回答：

> 現在有哪些工作要推進，哪一張值得我先處理？

### 2. `TaskDetailDrawer` = Single Task Operations

Task detail 的主問題只能是：

> 這張 task 現在狀態是什麼，我要對它做什麼操作？

第一屏只允許出現：

- title
- status / priority / dispatcher
- owner / due date / project
- next action / `blocked_by` + `blocked_reason`（欄位值）/ overdue signal
- description
- acceptance criteria
- result / handoff / review / attachments

Hierarchy 不得佔據 detail drawer 的第一屏。

### 3. `Task Structure View` = Hierarchy / Plan Navigation

plan / task / subtask / sibling / same-level / outline 這類結構資訊必須有正式入口，但需退到次要模式：

- drawer 內的 `Structure` tab，或
- 獨立的結構面板 / overlay

此畫面的主問題只能是：

> 這張 task 在整個 plan 結構裡的位置是什麼？

它不是預設 landing state。

### 4. `/projects/[id]` = Product Progress Console

此頁維持 management-layer 定位：

- milestone
- active plans
- grouped open work
- recent progress
- task copilot

此頁允許 `focus` 模式：

- `focus=milestone:<id>`
- `focus=plan:<id>`

讓使用者從 Task Hub 點擊 milestone / plan 後，保留上下文進到對應產品的聚焦狀態。

此頁不得再次承接 `/tasks` 的詳細操作負擔。

## 需求（含優先級與驗收）

### P0-1（R1）Screen Responsibility Reset

- `/tasks`、`TaskDetailDrawer`、`Task Structure View`、`/projects/[id]` 必須各自有唯一主責。
- 任一 screen 不得同時混入兩種以上主視角（execution / structure / management）。

AC-TSR-01:
- Given 使用者進入 `/tasks`
  When 第一屏載入完成
  Then 畫面必須先呈現全產品的 milestone / plan recap 與可下鑽入口，不得先看到 hierarchy inspector、same-level 結構區或完整 task board。

AC-TSR-02:
- Given 使用者打開一張 task 的 detail
  When drawer 開啟
  Then 第一屏必須先看到單卡狀態、風險與操作，而不是 plan outline、same-level、children 結構對照。

AC-TSR-03:
- Given 使用者需要看 task 結構
  When 進入 structure 模式
  Then 系統必須提供正式入口，但該模式不得是 task detail 的預設 landing state。

### P0-1A（R1A）Task Hub：全產品高層 recap

- `/tasks` 第一屏必須先顯示所有 L1 collaboration root entity 的高層任務概況。
- 此處的「產品」是 route / UI 語言，不是限制 entity.type；只要是 `level=1`、`parent_id=null`、可分享的 `product` 或 `company`，都必須納入同一套入口。
- 每個 product 至少顯示：
  - product 名稱
  - current milestone / stage
  - active plan 數
  - **阻塞 / review / overdue 計數**：阻塞定義為 `blocked_by` 非空（不是 `status="blocked"`；runtime 已不使用該 status，見 `governance_rules.py:798` 「不使用 blocked/backlog/archived 狀態」）；review 為 `status=review`；overdue 為 `dueDate < now` 且狀態 ∈ open
  - 最近更新
- 使用者必須能從 milestone 或 plan 直接進入對應產品頁。

AC-TSR-04:
- Given 系統有多個 active L1 collaboration roots（含 `product` 與 `company`）
  When 使用者進入 `/tasks`
  Then 第一屏必須可直接看到各 root 的 milestone / plan 進度概況，而不是只看到 task board 或單純 task 統計卡。

AC-TSR-05:
- Given 某 product 底下有阻塞（任一 task `blocked_by` 非空）或 overdue open work
  When 使用者查看 `/tasks`
  Then 該 product 的列或卡片必須直接顯示風險訊號，不需先進產品頁。
  > 註：Plan 合法 status（`SPEC-task-governance §3.2`）為 `draft / active / completed / cancelled`，**無 blocked**；「blocked plan」是以 plan 下轄 task 有 `blocked_by` 推導的衍生 signal，不是 Plan 自身 status。

AC-TSR-06:
- Given 使用者點擊某個 milestone 或 plan
  When 系統完成導頁
  Then 必須進入對應的 `/projects?id=<product_id>&focus=...` 狀態，而不是只打開一般產品頁或直接掉進 task board。

> 2026-04-22 contract note（ADR-044）：
> 產品頁 task 查詢契約以 `product_id` 為唯一 ownership SSOT。
> 2026-04-22 collaboration-root note：
> `product_id` 的欄位名沿用不變，但合法 ownership target 已擴為 L1 collaboration root entity（`product` / `company`）。
> `/projects` 與 `/tasks` 之間的跳轉、focus 與 filter 不得再依賴 `project` 字串或把 product entity 偷塞進 `linked_entities`。

### P0-2（R2）Task Detail 第一屏只保留操作關鍵

- `TaskDetailDrawer` 第一屏只保留單張 task 的操作與風險資訊。
- `Hierarchy`、`Plan Outline`、`Same Level`、`Subtasks` 不得預設出現在第一屏。

AC-TSR-07:
- Given 使用者開啟任一 task detail
  When 不做任何切換
  Then 第一屏必須看得到 `status / priority / owner / due / blocked_by（阻塞中 badge 取自欄位值，不是 status=blocked）/ next action / handoff controls`。

AC-TSR-08:
- Given 該 task 有 parent / siblings / subtasks / plan
  When 使用者尚未切到 `Structure`
  Then 這些資訊最多以一行 summary 呈現，不得展開為大型雙欄結構區。

### P0-3（R3）Structure View 正式化

- 結構檢視需被視為獨立模式，而非 detail 內的大型附屬區。
- Structure view 至少包含：
  - current task
  - parent
  - sibling summary
  - direct subtasks
  - plan outline

AC-TSR-09:
- Given 使用者切到 `Structure`
  When 畫面顯示完成
  Then 必須可辨識 current task、parent、subtasks 與 plan outline 的相對位置。

AC-TSR-10:
- Given 使用者從 structure 中點選相鄰 task
  When 導航成功
  Then 必須能切到新 task，而不丟失目前的 screen context。

### P0-4（R4）Task Copilot Rail Contract

- desktop 下的 `Task Copilot` 必須固定在 viewport 內。
- mobile 下的 `Task Copilot` 必須改為 drawer / sheet。
- rail 必須服務當前 screen 的單一主問題，不得同時承擔 unrelated prompt toolbar。

AC-TSR-11:
- Given desktop viewport
  When 使用者向下捲動主內容
  Then 右側 `Task Copilot` 必須固定在 viewport 內，而不是與主內容一起滑走。

AC-TSR-12:
- Given 任一 task-related screen
  When 查看 copilot rail
  Then rail 的 scope label、placeholder、empty state 必須對應當前 screen 的主問題，不得混用其他頁面的語言。

### P1-1（R5）Execution-first Visual Hierarchy

- execution board 上的主視覺權重必須先給：
  - next work
  - 阻塞（`blocked_by` 非空）/ overdue / status=review 三類風險 signal
  - owner / due
  - primary CTA
- 編號、breadcrumb、plan UUID、same-level 對照、outline 樹，不得搶第一視線。

AC-TSR-13:
- Given `/tasks` 或 `TaskDetailDrawer`
  When 使用者第一次掃視畫面
  Then 最先被看見的資訊必須是 task 狀態、風險與可執行操作，而不是 hierarchy metadata。

### P1-2（R6）Single Primary CTA Per Screen

- 每個 task-related screen 只允許一個 primary CTA。
- 其餘操作需降為 secondary / tertiary。

AC-TSR-14:
- Given `/tasks`
  When 畫面載入完成
  Then 該頁只能有一個主操作焦點，例如 `查看產品` 或 `新增任務`，不得同時把 `handoff / cancel / structure / copy prompt` 全做成主按鈕。

AC-TSR-15:
- Given `TaskDetailDrawer`
  When 畫面載入完成
  Then 主操作必須跟 task 當前狀態一致，例如 `開始處理 / 送審 / 完成 review / handoff` 其中之一，而不是並列多個同權按鈕。

### P1-3（R7）Product Focus Navigation

- Task Hub 與 Product Console 的導覽必須形成同一條路。
- 使用者從 `/tasks` 下鑽進產品頁後，回上一層時不得遺失原本的全局上下文。

AC-TSR-16:
- Given 使用者從 `/tasks` 點進某個 product / milestone / plan
  When 在產品頁完成查看後返回
  Then 必須保留原本 `/tasks` 的 scroll / filter / recap context，不得回到錯誤位置或重置成無上下文狀態。

## 技術約束（給 Architect）

- 不得以「加更多 section」達成需求；必須透過 screen boundary 重切解決。
- `TaskDetailDrawer` 若保留 richer field editor，需透過可收合區或次級 tab 降低第一屏負擔。
- `Task Structure View` 可作為 drawer 內 tab、二級 panel、或 route state，但不得與 default detail state 混成同一屏。
- `Task Copilot` 必須使用 shared rail shell，不可重做另一套 side panel。
- sticky / fixed 行為若受外層 scroll container 影響，應先修正 page shell，不得用 JS scroll hack 補救。

## 與既有規格關係

- `SPEC-task-view-clarity`：沿用其狀態口徑、晨報、跨專案摘要與 filter 規則；本 spec 另外定義 screen boundary。
- `SPEC-task-kanban-operations`：沿用其拖曳、編輯、review、handoff 的操作契約；本 spec 定義這些操作應出現在哪個 screen。
- `SPEC-project-progress-console`：維持 `/projects/[id]` 的 management-layer 定位；本 spec 只要求它不再與 task execution layer 重疊。
- `SPEC-dashboard-ai-rail`：沿用 shared AI rail shell 與 entry contract。
- `DESIGN-task-multilayer-workspace`：本 spec 把其設計方向翻成 executable screen contract 與 AC。

## Open Questions

1. `Task Structure View` Phase 0 要做 drawer 內 tab，還是獨立 overlay？由 architect 在 TD 決策。
2. `/tasks` 的 primary CTA 要以 `新增任務` 還是 `回到我的風險任務` 為主？由設計稿與實測決定。

## Changelog

- 2026-04-22: initial draft. Redefines task-related screens by responsibility boundary instead of continuing section-by-section patching.
