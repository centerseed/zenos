# Task 治理規則 v1.0（完整版）

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。
每個 task 必須連結回 ontology（linked_entities），讓執行者自動獲得相關 context。

## 建票最小規範
- title: 動詞開頭（「實作 X」「設計 Y」「修復 Z」）
- description: 包含背景、問題、期望結果三段
- acceptance_criteria: 2-5 條，每條可獨立驗收
- linked_entities: 1-3 個相關 entity（最重要的 L2 必須在其中）
- plan_id + plan_order: 如果屬於某個計畫，必填

## plan_id / plan_order 規則
- plan_id：所屬計畫的 ID。一個計畫通常對應一個 milestone 或 sprint
- plan_order：此 task 在計畫中的執行順序（整數，從 1 開始）
- 沒有 plan 的 task 可以省略，但有 plan_id 時 plan_order 必填
- plan_order 決定 Kanban 的排列順序，也是 AI 優先級推薦的參考

## 狀態流
backlog → todo → in_progress → review → done → archived
任何狀態 → cancelled
blocked（需填 blocked_reason）

### Blocked 狀態細節
- blocked_reason 必填：說明被什麼阻塞（依賴項/外部因素/等待決策）
- blocked 不是最終狀態，必須有後續行動（建立 dependency task 或等待解除）
- blocked 解除後應恢復到 in_progress 或 todo

## 驗收規則
- status=review 時 result 必填
- result 格式：描述做了什麼、驗證了什麼、遇到什麼問題
- done 狀態只能透過 confirm 工具達成（不能直接 write status=done）
- confirm 時 QA/reviewer 必須確認每條 acceptance_criteria 都已達成

## 知識反饋閉環
Task 完成後的知識應流回 ontology：
1. 萃取 insight：從 result 中找出值得記錄的技術洞察
2. 寫回 entity entry：write(collection=\"entity_entries\", data={type=\"insight\", ...})
3. 記錄 blindspot：如果過程中發現未知的未知，建 blindspot entity
4. 更新相關 L2：如果 task 改變了某個概念的語意，更新 entity summary

## AI 優先級推薦邏輯
系統根據以下因素自動推薦任務優先順序：
- plan_order（計畫中的順序）
- 與 blocked task 的依賴關係
- linked_entities 的 staleness（對應 L2 是否過時）
- 上次更新時間（越久未動越往前排）
推薦結果僅供參考，人類可覆蓋。
