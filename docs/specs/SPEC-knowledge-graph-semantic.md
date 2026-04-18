---
doc_id: SPEC-knowledge-graph-semantic
title: 功能規格：知識地圖語意增強與圖遍歷能力
type: SPEC
ontology_entity: TBD
status: partially_accepted
version: "0.1"
date: 2026-04-03
supersedes: null
---

# Feature Spec: 知識地圖語意增強與圖遍歷能力

**版本：** 0.1（2026-04-03）
**作者：** PM

---

## 背景與動機

現有知識地圖「存知識」但不「產知識」——節點之間的線沒有語意、無法追問「如果 A 改了誰受影響」、也無法從圖結構自動發現洞察。

**具體症狀：**

1. **邊無語意**：所有關聯只有 `type enum`（depends_on / impacts），不同業務意義（校準 vs. 觸發 vs. 驅動）看起來完全一樣
2. **無遍歷**：沒有 API 能問「這個節點的下游影響鏈是什麼」，agent 只能看一跳鄰居
3. **無拓撲洞察**：governance 檢查是逐節點的，圖結構整體（孤島、槓桿點、循環依賴）沒有人分析

這三個缺口導致知識地圖停留在「視覺化列表」，而不是「可推理的知識代理」。

---

## 目標用戶

**1. 知識地圖的人類讀者**（ZenOS dashboard 用戶）
- 場景：查看公司知識地圖時，想理解「這兩個節點為什麼連在一起」
- 現在：只能看到一條線，不知道語意是「校準」還是「觸發」

**2. AI Agent（context consumer）**
- 場景：Agent 被問到某個概念時，需要自動擴散上下文——「A 影響哪些東西、哪些東西影響 A」
- 現在：只能拿到直接一跳的鄰居，無法沿著關係鏈往下走

**3. ZenOS 治理系統（自動化）**
- 場景：每次 governance check 時，從圖結構本身找出系統性問題（孤島、槓桿點、循環依賴）
- 現在：governance 只做逐節點品質檢查，圖層面的問題不會被發現

---

## 需求

### P0（必須有）

#### 1. 關聯語意動詞

**REJECTED 2026-04-18** — 實作後生產環境填寫率 8.8%（388 個 relationship 只有 34 個填），description 欄位已承擔語意表達，無 downstream consumer。已從 codebase 移除 verb 使用（DB schema 中 verb column 保留以避免 migration 風險）。

- **描述**：建立或編輯關聯時，可以填寫一個短語意動詞（2–5 字，例：校準、觸發、驅動、限制）。知識地圖的邊上顯示此動詞。
- **Acceptance Criteria**：
  - Given 一條已有 verb 的關聯，When 用戶開啟知識地圖，Then 邊上顯示該動詞
  - Given 一條沒有 verb 的關聯，When 用戶開啟知識地圖，Then 邊仍正常顯示（verb 可選填）

#### 2. 影響鏈遍歷 API

**ACCEPTED — shipped in commit 0ede9cf (2026-04-03)**. Consumer: dashboard knowledge-map, NodeDetailSheet, MCP get entity response.

- **描述**：給定任一節點，系統能回傳其完整下游影響鏈（多跳），每條邊帶 type。供 agent 消費 context 時使用，不需要 UI。
- **Acceptance Criteria**：
  - Given 節點 A → B → C 的關聯鏈，When agent 查詢 A 的影響鏈，Then 回傳 `[A --impacts--> B --enables--> C]`
  - Given 無下游的節點，When 查詢影響鏈，Then 回傳空列表（不報錯）
  - Given 有循環依賴的圖，When 查詢影響鏈，Then 不陷入無限迴圈

---

### P1（應該有）

#### 3. 圖拓撲自動 Blindspot

**REJECTED 2026-04-18** — 實作後生產環境產生 51 筆拓撲 blindspot（佔總數 89%），大量 false positive（BNI 聯絡人被標 isolated、root 節點被標 leverage、Paceriz 閉環設計被標 circular），且無 UI consumer。已從 codebase 移除。

- **描述**：governance 分析時，從整體圖結構偵測系統性問題，自動產生新型態 Blindspot。偵測項目：
  - **孤立節點**：沒有任何關聯的節點
  - **槓桿點**：有 3 條以上出邊（任何 type）的節點，代表影響面廣但可能缺少文件
  - **循環依賴**：A → B → C → A 的環狀結構
  - **目標斷鏈**：有節點鏈最終沒有連到任何 `goal` 類型的節點
- **Acceptance Criteria**：
  - Given 一個孤立節點，When 執行 governance analyze，Then 產生一條「孤立節點」Blindspot，附上節點名稱
  - Given 一個有 4 條出邊的節點且無文件，When 執行 governance analyze，Then 產生「高影響節點缺乏文件」Blindspot
  - Given A → B → C → A 的循環，When 執行 governance analyze，Then 產生「循環依賴」Blindspot，附上完整路徑

#### 4. 建立關聯時 AI 建議動詞

**REJECTED 2026-04-18** — 依附於 P0.1 verb，一併移除。

- **描述**：建立新關聯時，系統根據兩個節點的 tags（what / who / why）自動建議 2–3 個動詞候選，用戶可選用或自行填寫。
- **Acceptance Criteria**：
  - Given 兩個節點各有 tags，When 用戶建立關聯，Then 系統提供至少 1 個動詞建議
  - Given 用戶不採用建議，When 用戶自行填寫動詞，Then 系統接受自定義值

#### 5. 治理評分納入語意動詞完整度

**REJECTED 2026-04-18** — 依附於 P0.1 verb，一併移除。

- **描述**：governance 品質評分新增「關聯語意完整度」維度。有關聯但缺少 verb 的節點，評分扣分；verb 填寫比例越高，分數越高。
- **Acceptance Criteria**：
  - Given 一個節點有 3 條關聯全部填寫了 verb，When 執行 governance analyze，Then 該節點的語意完整度分項得滿分
  - Given 一個節點有關聯但全部缺少 verb，When 執行 governance analyze，Then 產生「關聯缺少語意動詞」品質警告，並反映在治理評分中
  - Given partner 整體 verb 填寫率低於 50%，When 執行 governance analyze，Then 在整體健康摘要中標記為待改善項

---

### P2（可以有）

#### 6. 圖面板：依動詞篩選
- **描述**：知識地圖提供篩選控制項，用戶可選擇只顯示特定動詞的邊，聚焦在單一語意維度上分析。
- **Acceptance Criteria**：
  - Given 圖中有多種動詞的邊，When 用戶選擇篩選「觸發」，Then 只有帶「觸發」動詞的邊顯示，其餘邊淡化或隱藏
  - Given 用戶清除篩選，When 操作完成，Then 圖恢復顯示所有邊

#### 7. 節點間路徑查詢
- **描述**：用戶可指定任意兩個節點，系統回傳它們之間所有路徑（含每條邊的動詞），幫助發現間接關聯。
- **Acceptance Criteria**：
  - Given A 和 C 有間接路徑 A → B → C，When 用戶查詢 A 到 C 的路徑，Then 回傳 `A →校準→ B →觸發→ C`
  - Given 兩節點不連通，When 查詢路徑，Then 回傳「無路徑」，不報錯

---

## 明確不包含

- **動詞標準化 / 詞彙管理**：不建立統一動詞詞庫，不強制動詞必須來自預設清單，用戶自由填寫
- **跨 partner 圖分析**：影響鏈遍歷與拓撲分析只在單一 partner 範圍內執行
- **時序關係**：不處理「這條關聯在某時間點之後才成立」的時態語意
- **關聯權重 / 強度**：不加數值權重，動詞即語意，不做量化排序
- **自動推論新關聯**：系統不自動建立 transitive 推論邊（A→B, B→C 不自動建立 A→C），只做查詢時的遍歷

---

## 技術約束（給 Architect 參考）

- **verb 為可選欄位**：不可破壞現有關聯資料，舊資料 verb 為 null 需能正常顯示
- **影響鏈遍歷需防循環**：圖中可能存在環狀結構，遍歷演算法必須有訪問記錄避免無限迴圈
- **拓撲分析為批次操作**：不要求即時，可在 governance analyze 時執行，不需要 streaming

---

## 開放問題

- **verb 長度上限**：建議 2–5 字，但是否強制驗證？還是只做 UI 提示？
- **槓桿點門檻**：P1 暫定「3 條以上出邊」觸發 Blindspot，實際數字需 dogfooding 後調整
- **動詞建議的觸發時機**：建立關聯時主動顯示，還是用戶點擊「建議」才觸發？
