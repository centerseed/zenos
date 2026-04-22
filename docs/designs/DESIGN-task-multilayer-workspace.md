---
doc_id: DESIGN-task-multilayer-workspace
title: 設計文件：任務多層次視圖重構
type: DESIGN
ontology_entity: action-layer
status: draft
version: "0.1"
date: 2026-04-22
supersedes: null
---

# 設計文件：任務多層次視圖重構

## 為什麼要重做

目前任務相關畫面有三個根本問題：

1. `/tasks`、`/projects/[id]`、`TaskDetailDrawer` 沒有明確分工，管理層與執行層混在一起。
2. `milestone / plan / task / subtask` 的層級語義存在，但每個畫面用不同方式表達，使用者每切一頁都要重學。
3. AI rail 有資料，但沒有被定義成「根據畫面上下文提供可核對的討論依據」，反而常和主視圖搶焦點。

這份設計文件的目的，不是換一套外觀，而是把任務相關畫面重構成一條固定的工作路徑：

`Task Hub（全局）` → `Product Console（單一產品）` → `Task Detail（單張工作）`

使用者永遠從高層開始，逐步下鑽，並在每一層都能拿當前畫面與 AI 對齊。

## 美學方向

延續現有 `Zen Ink` 視覺語言，不另起一套新風格。

- 方向：`清晰、信任感、管理密度優先`
- 理由：這不是行銷頁，也不是創作工具；它是 owner / PM / architect 用來判斷「現在推到哪、卡在哪、接下來做什麼」的工作主控台。
- 保留：
  - `Zen Ink` 色票與字體 pairing
  - 低圓角、薄邊框、紙面層次
  - `vermillion / jade / ocher` 的語義色
- 禁止：
  - 額外加新的視覺主題
  - 讓每個區塊都長成不同 card 語言
  - 把 hierarchy 區塊做成比操作資訊更重

## 目標使用者與使用情境

### 主要使用者

- 產品 owner / PM
- Architect / tech lead
- 需要用畫面和 AI 一起做狀態對齊與下一步決策的人

### 核心任務

1. 快速 recap 全局：現在所有產品推到哪裡。
2. 找到需要關注的產品 / milestone / plan。
3. 下鑽到單一產品，查看 open work、blocker、最近推進。
4. 展開單一 task / subtask，直接標記完成或更新狀態。
5. 用當前畫面做為 AI 討論依據，核對 AI 的 recap、拆解與建議。

## 設計總原則

1. 先全局，後局部。
2. 同一層只回答一個主問題。
3. hierarchy 是上下文，不是主角。
4. AI rail 是討論與核對區，不是另一個工作區。
5. 所有 drill-down 都保留上一層語境，不切換成另一套產品。

## 新資訊架構

### 1. `/tasks` = Task Hub（全局任務主控台）

這一頁不再預設是 kanban。

它的第一責任是回答：

- 哪些產品正在推進
- 每個產品目前在哪個 milestone
- 哪些 plan 在 active / blocked / review
- 哪些地方值得立刻下鑽

#### 第一屏必備區塊

1. `Portfolio Recap`
   - 全產品數
   - active milestone 數
   - active plan 數
   - blocked plan 數
   - overdue work 數

2. `Products by Health`
   - 每列一個 product
   - 顯示：
     - product 名稱
     - current milestone
     - active plan 數
     - blocked / review / overdue 總數
     - 最近更新
     - `查看產品` CTA

3. `Milestone / Plan Radar`
   - 顯示目前全站最需要注意的 milestone 或 plan
   - 規則：blocked 優先，其次 overdue，其次 review
   - 每個 item 可直接點入產品頁，並帶著 focus

4. `Recent Changes`
   - 顯示最近有推進、handoff、review 的產品級事件
   - 用來讓使用者知道哪些產品真的在動

#### 第二屏才進執行層

5. `Execution Board`
   - 保留 `/tasks` 既有 board/list 能力
   - 但只作為第二層工作面
   - 預設折疊在 recap 下方，或以 secondary tab 呈現

### 2. `/projects/[id]` = Product Console（單一產品進度主控台）

這一頁的責任是回答：

- 這個產品現在在哪個 milestone / plan
- 哪些工作卡住
- 最近推進了什麼
- 我現在要關注哪張 task

它不是 task board 替身。

#### 固定區塊順序

1. `Product Header`
   - product 名稱
   - health summary
   - 最近更新
   - 主要 CTA：`查看任務板`

2. `Milestone Strip`
   - 橫向顯示 milestones
   - 每個 milestone 顯示：
     - 名稱
     - open work 數
     - status tone
   - 可點擊，點後進入 `focus mode`

3. `Current Plans`
   - 依 milestone 分組顯示 plan card
   - 每張 plan card 顯示：
     - plan goal
     - owner
     - open / blocked / review / overdue
     - next task preview
   - 可點擊，點後進入 `focus mode`

4. `Focused Open Work`
   - 預設顯示所有 active plan 的 open work
   - 若選到 milestone / plan，只顯示該 focus 範圍
   - task 以 parent task 為第一層，subtask 嵌套在下

5. `Recent Progress`
   - 顯示該產品最近推進軌跡

6. `Task Board Entry`
   - 一個明確入口去 `/tasks` 或此產品範圍下的 board
   - 不在本頁直接展開全尺寸 board

### 3. `Task Detail` = 單張工作操作面

單張 task / subtask 的操作，永遠在 drawer / overlay / detail panel 做，不取代上一層主視角。

它的責任是：

- 看單張工作的完整上下文
- 更新狀態
- 標記完成
- handoff
- 檢查 blocker / dependency / protocol / blindspot

#### Detail 的必備資訊順序

1. title + status + priority + dispatcher
2. breadcrumb：`product > milestone > plan > task > subtask`
3. next action / due / owner / blocked reason
4. description / acceptance criteria / result
5. related context：linked entities / protocol / blindspot / parent / children
6. comments / handoff / attachments

## Drill-down 規則

### 從 `/tasks` 點 product

- 進 `/projects?id=<product_id>`
- 不直接進 task board

### 從 `/tasks` 點 milestone / plan

- 進 `/projects?id=<product_id>&focus=milestone:<id>` 或 `focus=plan:<id>`
- 產品頁保留同一 layout，只切換 focus 區塊

### 從產品頁點 task / subtask

- 開 `Task Detail Drawer`
- 不整頁跳走
- 只有使用者明確點 `查看任務板`，才進 board

### 從 detail 返回

- 永遠回上一層原本的 focus 狀態
- 不可丟失 filter / focus / scroll context

## 共同視覺語法

### 一致的階層表示

- `milestone`：永遠用 stage strip / chip 群組表示
- `plan`：永遠用 summary card 表示
- `task`：永遠用可展開 row / card 表示
- `subtask`：永遠嵌套於 parent task 下，不獨立升格成第一層卡片

### 一致的狀態表示

- `blocked`：vermillion
- `review`：ocher
- `done / healthy`：jade
- `neutral / todo`：ink muted

不能只靠顏色，所有關鍵狀態都必須有文字 pill。

### 一致的 CTA

只允許以下主操作文法：

- `查看產品`
- `聚焦 milestone`
- `聚焦 plan`
- `展開細節`
- `標記完成`
- `更新狀態`
- `交棒 Handoff`
- `查看任務板`

不要在不同畫面發明不同命名。

## AI Rail 設計規則

右欄 AI rail 必須全站任務相關畫面統一。

### 它是什麼

- 當前畫面的討論與核對區

### 它不是什麼

- 不是第二套導航
- 不是隨畫面亂滾的浮動聊天窗
- 不是和主內容爭奪第一視線的主角

### 固定規則

1. rail 固定在 viewport 內
2. chat 只捲自己的 viewport，不可影響 document scroll
3. placeholder 與系統提示必須依當前頁型變化：
   - Task Hub：問全產品 recap / 風險 / 下一步
   - Product Console：問該產品的 milestone / plan / blocker / next step
   - Task Detail：問這張 task 要怎麼處理 / 驗收 / handoff

### rail 的輸出契約

AI 回答至少要對齊畫面上可見的：

- 當前 focus 範圍
- active plans / milestones
- open work
- blocker / risk
- next step

若 AI 的回答和畫面證據對不起來，使用者應能一眼看出不一致。

## 要移除或降級的模式

以下模式不再作為主任務視圖：

1. 在產品頁第一屏直接出現完整 task board
2. 同時並列 `hierarchy / same level / outline / breakdown` 多套關係視圖
3. 把 prompt toolbar 當成右欄主體
4. 讓 copilot 因為新訊息把整頁 scroll 拉走
5. 讓 refresh 後失去現在看的 product / focus context

## 組件清單

- `TaskHubRecap`
  - `/tasks` 第一屏全局摘要
- `ProductHealthRow`
  - product 列表列
- `MilestoneRadar`
  - 全局風險 / 焦點 milestone 與 plan
- `ProductConsoleHeader`
  - 單一產品 header
- `MilestoneStrip`
  - 單一產品階段條
- `PlanCard`
  - 單一 plan 摘要卡
- `OpenWorkTree`
  - parent task / subtask 樹狀區
- `TaskDetailDrawer`
  - 單張工作詳情與操作
- `CopilotRailShell`
  - 任務相關畫面共用右欄骨架

## Spec Compliance Matrix

| Source Spec | 必須對齊的設計決策 |
| --- | --- |
| `SPEC-project-progress-console` | `/projects/[id]` 是管理層 console，不是 task board |
| `SPEC-task-view-clarity` | `/tasks` 必須先給全局摘要，再進執行層，不得只剩板子 |
| `SPEC-task-governance` | `milestone / plan / task / subtask` 沿用既有治理語義，不重定義 core model |
| `SPEC-dashboard-ai-rail` | 任務畫面右欄沿用同一 rail shell 與上下文契約 |

## Done Criteria

1. 使用者在 `/tasks` 第一屏可直接回答：
   - 目前有哪些產品在推進
   - 哪些 milestone / plan 有風險
2. 使用者從 `/tasks` 點進任一 milestone / plan，能進到正確產品頁且保留 focus。
3. `/projects/[id]` 第一屏不再被 task board 取代。
4. 使用者能從產品頁展開 task / subtask 細節並直接標記完成。
5. AI rail 在三種頁型都使用同一骨架，但上下文不同。
6. refresh / deep-link / back navigation 不丟失 `product` 與 `focus`。
7. 任務相關畫面的 hierarchy 表達與 CTA 命名一致。

## 驗證方式

### Scenario 1：全局 recap

1. 進 `/tasks`
2. 第一屏看到所有產品的 milestone / plan 概況
3. 點一個 blocked plan
4. 成功進到對應產品頁且 focus 在該 plan

### Scenario 2：產品下鑽

1. 在產品頁看 milestone strip 與 current plans
2. 點一張 parent task
3. 開 drawer
4. 完成狀態更新後，回到原本產品 focus，不跳錯頁

### Scenario 3：AI 對齊

1. 在 product console 問 AI「現在卡點是什麼」
2. AI 回答必須可對回畫面上的 blocked / review / overdue 訊號
3. 在 task detail 問 AI「這張 task 下一步」
4. AI 不能回成整個產品的泛泛摘要

## 交付建議

這次不要再以畫面切片方式修。

應按以下順序交付：

1. `IA / route / state contract`
   - `product id`
   - `focus`
   - `task drawer`
2. `Task Hub` 第一屏 recap
3. `Product Console` 的 milestone / plan / open work 一致化
4. `Task Detail` breadcrumb 與操作語法整理
5. `AI Rail` 上下文與滾動規則統一

## Changelog

- 2026-04-22: initial draft. Redefines task-related dashboard views into a top-down multilayer workspace: Task Hub → Product Console → Task Detail.
