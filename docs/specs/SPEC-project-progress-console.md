---
type: SPEC
id: SPEC-project-progress-console
doc_id: SPEC-project-progress-console
title: Feature Spec: Product Progress Console
status: draft
version: "0.1"
date: 2026-04-21
supersedes: null
l2_entity: Dashboard 知識地圖
created: 2026-04-21
updated: 2026-04-21
---

# Feature Spec: Product Progress Console

## 背景與動機

目前 ZenOS 的 task 能力已經有較完整的 schema 與欄位，但 Dashboard 的呈現仍以 task-centric 為主：

1. `/tasks` 是執行層看板，適合追 task 狀態與操作。
2. `/projects/[id]` 雖然是產品/專案頁，實際上仍缺少管理層視角，無法快速回答「這個產品現在推到哪裡」。
3. 使用者在產品頁看不到清楚的 `active plan`、`未完成工作`、`blocker`、`待決策項`，只能掉進過細的 task 清單或看到空值摘要。

這使得產品 owner / PM / Architect 很難把 `/projects/[id]` 當成真正的主控台使用，也無法在對齊狀態後，快速把下一步工作交給 Claude Code / Codex 繼續推進。

本 spec 的目的，是把 `/projects/[id]` 明確定義成 **產品推進主控台（Product Progress Console）**，讓使用者先看到「進度與決策」，再視需要 drill down 到 task。

## 目標

1. 使用者進入產品頁後，能在 30 秒內知道目前有哪些 plan 在進行。
2. 使用者能快速看出每個 plan 還有哪些未完成 task、哪些工作卡住。
3. 使用者能用 AI 產生一份可決策的 recap，而不是自己手動整理 context。
4. 使用者能把目前產品狀態與下一步目標，一鍵整理成可複製 prompt，帶去 Claude Code 或 Codex 開工。
5. 明確切開管理層與執行層：
   - `/projects/[id]` = 管理層產品進度主控台
   - `/tasks` = 執行層 task board

## 非目標

- 不在本 spec 重定義 task / plan / milestone / subtask 的 core schema。
- 不在本 spec 取代 `/tasks` 的 kanban 與編輯能力。
- 不在本 spec 定義新的 AI runtime 或新的 helper protocol。
- 不在本 spec 定義 Claude Code / Codex 各自的工具細節或 CLI 參數。

## 目標使用者

- 產品 owner / PM
- Architect / tech lead
- 需要快速判斷產品目前推進狀態與下一步方向的管理者

## 核心原則

1. **先回答進度，再展開細節。**
   產品頁第一層應先回答「現在在哪個 plan / milestone、卡在哪裡、接下來推什麼」，而不是先平鋪所有 task。
2. **Plan 是主視角，task 是 supporting detail。**
   在產品頁，未完成工作必須依 `plan` 組織，而不是一張張 task 平鋪。
3. **AI 是決策加速器，不是另一個獨立工作區。**
   AI recap 與 prompt generation 應服務於「快速對齊現況並推進下一步」，不是把產品頁變成通用聊天頁。
4. **管理層視圖與執行層視圖必須分工。**
   `/projects/[id]` 不應與 `/tasks` 重複成兩個 task board。
5. **任何進度數字都必須可追溯。**
   若畫面顯示 plan progress、未完成數、blocked 數、待 review 數，必須可對回同一批資料。

## 現況問題定義（As-Is）

1. 產品頁缺少 plan-centric 視角，使用者看不到產品底下哪些 plan 正在進行。
2. 產品頁與 task 頁同時呈現 task，但沒有清楚分工，造成資訊架構重疊。
3. richer task schema 雖已存在，UI 仍無法把 `plan`、`subtask`、`milestone` 組成管理層可理解的工作結構。
4. 使用者無法在產品頁快速生成一份「現在狀態 recap + 下一步 prompt」交給 AI coding agent。

## 名詞與視圖語義

- `產品頁 / Product Progress Console`：`/projects/[id]` 的管理層視圖。
- `plan`：Action Layer 的 orchestration primitive，以 `goal` 作為顯示名稱。
- `milestone`：沿用既有治理語義，為 `goal` entity；在產品頁可作為進度階段或分組語意，但不重定義為新的 task kind。
- `subtask`：沿用既有治理語義，為 `parent_task_id != null` 的 task；在產品頁不得與 parent task 平鋪於同一層。
- `open work`：尚未結束的 task，包含至少 `backlog,todo,in_progress,review,blocked`。
- `AI recap`：AI 針對當前產品狀態所產出的決策摘要。
- `copy prompt`：可直接複製到 Claude Code / Codex 的 continuation prompt。

## 需求（含優先級與對應驗收）

### P0-1（R1）Current Plans：產品當前進行中的 Plan 總覽

- `/projects/[id]` 第一層必須直接顯示此產品底下正在進行中的 plan。
- 每張 plan 卡至少顯示：
  - plan 顯示名稱（`goal`）
  - status
  - 未完成 task 數
  - blocked task 數
  - 待 review task 數
  - 最近更新時間
- 畫面必須優先凸顯 `active` 與 `blocked` 的 plan，不得先把使用者帶入單張 task。

AC-PPC-01:
- Given 某產品底下有兩個 active plans  
  When 使用者進入 `/projects/[id]`  
  Then 第一層可見區域必須直接顯示這兩個 plans，而不是只顯示 task 摘要或空態。

AC-PPC-02:
- Given 某 plan 有 `goal`、未完成 task、blocked task、review task  
  When 查看 plan 卡  
  Then 必須直接看到 plan 名稱、未完成數、blocked 數、review 數與最近更新時間。

AC-PPC-03:
- Given 某產品沒有任何 active plan  
  When 進入 `/projects/[id]`  
  Then 畫面必須明確顯示「目前沒有進行中的 plan」空態，而不是只剩空白 task 區。

### P0-2（R2）Open Work：依 Plan 分組的未完成工作

- 產品頁必須顯示 `open work`，但必須依 `plan` 分組，不得把所有 task 平鋪成單一長列表。
- 每個 plan 區塊至少顯示：
  - 下一步最重要的 task
  - blocked task
  - 待 review task
  - overdue task（若有）
- subtask 必須收在 parent task 底下呈現，不得與 parent task 並列搶第一層注意力。

AC-PPC-04:
- Given 某產品底下有多張未完成 task，且分屬不同 plan  
  When 使用者查看 open work 區  
  Then task 必須依 plan 分組呈現，而不是單一混合列表。

AC-PPC-05:
- Given 某 parent task 底下有 subtasks  
  When 使用者查看產品頁的 open work 區  
  Then subtask 必須附屬於 parent task 顯示，不得與其他主 task 平鋪在同一層。

AC-PPC-06:
- Given 某 plan 有 blocked / review / overdue 的 task  
  When 查看該 plan 的 open work 區  
  Then 必須能直接辨識這三種風險或狀態，不需先進 task 詳情。

### P0-3（R3）AI Recap：可決策的產品進度摘要

- 產品頁必須提供 `AI recap` 入口，讓使用者可針對當前產品狀態生成摘要。
- AI recap 的輸出至少包含：
  - 目前進度到哪裡
  - 正在進行的 plans
  - 主要未完成工作與 blocker
  - 建議下一步
  - 需要使用者決策的點
- 此 recap 應以「快速決策」為目的，不得退化成純 task dump。

AC-PPC-07:
- Given 某產品有 active plans、未完成 task 與 blocker  
  When 使用者觸發 AI recap  
  Then AI 輸出必須同時涵蓋進度、plans、blockers、建議下一步與待決策點。

AC-PPC-08:
- Given 產品目前無 active plan 或 open work 很少  
  When 觸發 AI recap  
  Then AI 仍必須回覆當前狀態與下一步建議，不得只回傳「無資料」。

### P0-4（R4）Continue In Claude / Codex：可複製的下一步 Prompt

- 產品頁必須提供 `copy prompt` 能力，讓使用者可把目前產品狀態整理成下一步工作 prompt。
- Prompt 內容至少包含：
  - 產品名稱與當前目標
  - active plans
  - 關鍵未完成 task / blockers
  - AI recap 摘要
  - 使用者選定的下一步方向
- prompt 必須設計成可直接複製到 Claude Code 或 Codex，不要求使用者自己再拼 context。

AC-PPC-09:
- Given 使用者已生成 AI recap，並選定下一步方向  
  When 點擊 copy prompt  
  Then 系統必須提供一份包含產品 context、active plans、open work、blockers、AI recap 與下一步目標的可複製 prompt。

AC-PPC-10:
- Given 同一個產品頁面  
  When 使用者尚未進入 task 詳情  
  Then 仍可直接從產品頁生成並複製下一步 prompt，不需跳去 `/tasks` 手動整理。

### P0-5（R5）視圖分工：Project Console 與 Task Board 不得重疊

- `/projects/[id]` 必須明確定位為管理層主控台。
- `/tasks` 必須保留為執行層 board。
- 產品頁第一層不得退化成另一個 kanban 或 task list 的翻版。

AC-PPC-11:
- Given 使用者進入 `/projects/[id]`  
  When 畫面載入完成  
  Then 第一層必須先看到 plan / open work / AI recap / copy prompt 等管理資訊，而不是完整 task board。

AC-PPC-12:
- Given 使用者需要操作單張 task 狀態或編輯欄位  
  When 從產品頁 drill down  
  Then 可以進入 task 層，但 `/projects/[id]` 本身的主視角不得被 task 操作 UI 取代。

### P1-1（R6）Milestone View：產品推進階段感

- 若產品底下已有 milestone（goal entity）語意，產品頁應能看出目前工作屬於哪個 milestone / 階段。
- milestone 在本頁的角色是「進度階段」，不是另一種 task 卡片。

AC-PPC-13:
- Given 某產品底下的 open work 連到不同 milestone  
  When 查看產品頁  
  Then 使用者必須能辨識目前主要工作落在哪個 milestone 或階段，而不是只看到無脈絡的 plan/task。

### P1-2（R7）Recent Progress：近期推進軌跡

- 產品頁應顯示近期推進摘要，幫助使用者快速理解最近是否真的有前進。
- 此區應偏向「關鍵變化」，不是完整事件流水帳。

AC-PPC-14:
- Given 某產品最近一週有 task 狀態推進、review、handoff 或 plan 更新  
  When 查看產品頁  
  Then 應可看到近期推進摘要，而不是只能靠 task 卡片猜測。

### P2-1（R8）Prompt Presets：不同 agent 入口的 prompt 版本

- 未來可支援不同 prompt preset，例如 Claude Code 版、Codex 版，但不阻塞 P0。

AC-PPC-15:
- Given 系統已提供不同 agent preset  
  When 使用者切換 prompt preset  
  Then 複製內容可依目標 agent 調整，但核心 product context 不得遺失。

## 技術約束（給 Architect）

- 本 spec 不改動 `Task` / `Plan` / `Goal` 的核心語義；必須沿用 `SPEC-task-governance`。
- `milestone` 仍是 `goal` entity，不新增新的 task kind。
- `subtask` 仍是 `parent_task_id != null` 的 task，不在產品頁被提升為與 parent task 平級的第一層物件。
- `/projects/[id]` 若顯示 plan progress、open work、blocked、review 等數字，必須使用可追溯的正式口徑，不得由前端各區塊自行推測不同分母。
- 若目前無完整 plan/milestone read model，implementation 可以分階段補齊，但產品頁的資訊架構不得先退回 task-flat 視角。
- AI recap 與 copy prompt 應建立在正式 product context 之上，不得要求使用者手動重貼 plan/task 背景。

## 邊界與治理規則

- 本 spec 定義的是產品頁的管理層體驗，不定義 task 執行操作細節。
- 若 implementation 同時涉及：
  - 產品頁資訊架構重整
  - task 資料口徑補齊
  - AI recap / prompt contract
  應拆成多張 implementation task，各自可驗收。
- 任何把 `/projects/[id]` 重新做成 task board 的實作，都視為不符合本 spec。

## 與既有規格關係

- `ADR-008-dashboard-multi-view`：本 spec 補齊其中「專案 view 給老闆/PM 日常使用」的具體產品契約。
- `SPEC-task-governance`：沿用既有 `plan / milestone(goal) / subtask` 語義，不重定義 Core 模型。
- `SPEC-task-view-clarity`：該 spec 定義 `/tasks` 的可讀性與跨專案任務摘要；本 spec 不取代 `/tasks`，而是補上 `/projects/[id]` 的管理層視圖。
- `SPEC-task-kanban-operations`：該 spec 定義 `/tasks` 的操作能力；本 spec 不把這些操作搬進產品頁作為主視角。
- `SPEC-dashboard-ai-rail`：若產品頁導入 AI recap / prompt generation，應沿用同一個 AI rail shell 與入口協議。

## Open Questions

1. 產品頁的 `AI recap` 應為每次即時生成，還是允許保留最近一次摘要快照？
2. milestone 在 UI 上是否直接顯示為 `milestone`，或抽象為「階段 / progress stage」即可？
3. `copy prompt` Phase 0 是否先提供單一通用版本，再於後續補 `Claude Code` / `Codex` 差異化 preset？

## Changelog

- 2026-04-21: initial draft. Defines `/projects/[id]` as a management-layer product progress console centered on plans, open work, AI recap, and copyable execution prompts.
