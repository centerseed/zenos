---
doc_id: SPEC-impact-chain-enhancement
title: 功能規格：Impact Chain 三向增強（反向查詢、視覺化、變更推送）
type: SPEC
ontology_entity: 影響鏈
status: approved
version: "1.0"
date: 2026-04-05
supersedes: null
---

# Feature Spec: Impact Chain 三向增強

**版本：** 0.1（2026-04-05）
**作者：** PM

---

## 背景與動機

ZenOS 的 `impact_chain` 是知識圖譜的核心差異化能力——用 BFS 從一個節點走 outgoing edges，產出完整的影響鏈（例如：VDOT→訓練計畫→AI教練）。這是 RAG 做不到的結構化推理能力。

**現存三個缺口：**

1. **只有前向**：只能問「我改了會影響誰」，不能問「誰改了會影響我」——agent 在做決策前無法掌握上游依賴風險。
2. **Dashboard 看不到**：`impact_chain` 被埋在 MCP `get` 回傳裡，Dashboard 的節點詳情只顯示直接 impacts（一跳），多跳鏈路不可見，用戶無法感知真實的影響範圍。
3. **沒有主動推送**：sync/capture 更新節點後，下游 owner 不知情，只能靠人工追蹤。

這三個缺口讓 impact_chain 淪為「存在但沒被用到」的能力，無法兌現「語意代理」的價值主張。

---

## 目標用戶

| 用戶 | 使用場景 |
|------|---------|
| AI agent（開發者呼叫） | 做技術決策前，查詢「改這個節點，誰會受影響」以及「哪些上游節點改了會波及我」 |
| Dashboard 使用者（PM/負責人） | 點開節點詳情，直觀看到整條上下游影響路徑，判斷變更風險 |
| 下游模組 owner | 上游節點被更新時，收到通知，知道要主動評估影響 |

---

## 需求

### P0（必須有）

#### 反向 Impact Chain 查詢

- **描述**：用戶（agent 或 API 呼叫者）在取得一個節點的詳情時，除了現有的 `impact_chain`（往下游走），還能同時取得 `reverse_impact_chain`（往上游走）——即「哪些節點的變更會影響到我」。
- **Acceptance Criteria**：
  - Given 節點 B depends_on 節點 A（A→B 存在 edge），When 取得節點 B 的詳情，Then 回傳內容中包含 `reverse_impact_chain`，其中包含節點 A（及 A 的上游，若存在）。
  - Given 節點 C 沒有任何上游節點，When 取得節點 C 的詳情，Then `reverse_impact_chain` 回傳空串列，不報錯。
  - Given 影響鏈深度超過 5 跳，When 取得節點詳情，Then `reverse_impact_chain` 最多回傳 5 跳，並標示「已截斷」。
  - Given 現有已在使用 `impact_chain` 的呼叫者，When 不帶任何額外參數呼叫，Then 現有 `impact_chain` 回傳格式不變（向後相容）。

---

### P1（應該有）

#### Dashboard 節點詳情顯示完整 Impact Chain

- **描述**：Dashboard 的節點詳情面板（NodeDetailSheet）顯示完整的上游和下游影響路徑，以多跳鏈的方式呈現，用戶可以展開或摺疊各層級。
- **Acceptance Criteria**：
  - Given 用戶在知識地圖點擊一個節點，When 詳情面板開啟，Then 面板中出現「影響鏈」區塊，分為「上游（誰影響我）」與「下游（我影響誰）」兩個子區塊。
  - Given 節點有多跳下游（如 A→B→C），When 詳情面板顯示，Then 下游區塊以層級結構呈現多跳，而非只顯示直接一跳。
  - Given 影響鏈有 3 跳以上，When 初始顯示，Then 預設摺疊第 2 跳以後，用戶可點擊展開。
  - Given 節點沒有上游或下游，When 詳情面板顯示，Then 對應子區塊顯示「無影響鏈」，不顯示空白或錯誤。
  - Given 用戶使用行動裝置或小螢幕，When 詳情面板顯示影響鏈，Then 影響鏈區塊仍可正常展開/摺疊，不溢出畫面。

---

### P2（可以有）

#### 變更推送通知

- **描述**：當一個節點被 write 或 sync 更新後，系統沿 `impact_chain` 找出下游節點的 owner，為每個 owner 產出一則通知任務（notification task），告知上游有更新、需評估影響。
- **Acceptance Criteria**：
  - Given 節點 A 被更新（write 或 sync），且 A 有下游節點 B（B 有 owner），When 更新完成後，Then 系統為 B 的 owner 產出一則 notification task，任務內容包含：更新節點名稱、更新時間、影響路徑（A→B）。
  - Given 節點 A 被更新，且下游鏈為 A→B→C（B 和 C 各有不同 owner），When 更新完成後，Then B 的 owner 和 C 的 owner 各自收到獨立的 notification task。
  - Given 節點 A 被更新，但下游節點均無 owner，When 更新完成後，Then 不產出 notification task，不報錯，系統記錄一則 warning log。
  - Given 同一節點 A 在 10 分鐘內被更新兩次，When 第二次更新完成後，Then 同一 owner 的 notification task 合併為一則（或更新既有未讀任務），不重複發送。
  - Given 影響鏈深度超過 5 跳，When 產出通知，Then 只通知 5 跳以內的 owner，超過部分不通知（防止廣播風暴）。

---

## 明確不包含

- **通知管道實作**：notification task 的產出格式與下游分發（email、Slack、webhook）不在本 Spec 範圍，由 Architect 設計。
- **Edge 語意類型篩選**：本 Spec 的 impact_chain 沿所有 edge 類型走，不支援「只走特定 edge type」的篩選——這是後續語意增強的範疇（參見 SPEC-knowledge-graph-semantic）。
- **圖上的循環偵測 UI**：若知識圖譜存在循環依賴，BFS 截斷後不會在 Dashboard 特別標示循環，只截斷不提示。
- **批次查詢**：本 Spec 只定義單節點查詢反向 impact_chain，批次查詢留待後續。
- **歷史影響鏈比較**：不做「變更前 vs. 變更後影響鏈差異比較」。

---

## 技術約束（給 Architect 參考）

- **BFS 深度上限**：影響鏈（正向與反向）最多走 5 跳，防止大圖上的效能問題。這是產品決策，不是技術限制——若 Architect 評估需要可調整上限，請回拋討論。
- **向後相容**：反向影響鏈必須作為「新增欄位」回傳，不能改變現有 `impact_chain` 的格式，避免 breaking change。
- **通知冪等性**：同一更新事件對同一 owner 的通知必須冪等（10 分鐘視窗內合併），避免 sync 批量觸發大量重複通知。

---

## 開放問題

1. **5 跳上限是否合適？** 目前 ZenOS 最深的影響鏈有多少跳？是否需要可配置？（待 Architect 查 DB 確認）
2. **notification task 格式**：notification task 要寫入 ZenOS task collection，還是另闢新的 collection？owner 如何定義（entity 的 owner 欄位，還是 department？）
3. **Dashboard 影響鏈載入時機**：影響鏈是點擊節點時即時查詢，還是節點資料預載？若節點很多（50+）即時查詢是否有效能疑慮？
4. **P2 的通知去重視窗**：10 分鐘是假設值，實際合適的視窗長度需確認（依 sync 頻率決定）。
