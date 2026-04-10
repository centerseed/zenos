---
type: SPEC
id: SPEC-entry-distillation-quality
status: Draft
l2_entity: 語意治理 Pipeline
created: 2026-04-10
updated: 2026-04-10
---

# Feature Spec: Entry Distillation Quality

## 背景與動機

ZenOS 已有 `entity entries` 資料結構，也已有兩條 entry 進入路徑：

- `/zenos-capture` 從對話或工作結果萃取 entry
- journal 壓縮後，依 `ADR-014` 觸發 entry 蒸餾

但目前規則分散在多份文件裡：

- `SPEC-l2-entity-redefinition` 定義 L2 的定位與 entry 的存在理由
- `ADR-010-entity-entries` 定義 entries 的資料模型與生命週期
- `ADR-014-journal-entry-distillation` 定義 journal 壓縮後要觸發蒸餾
- `capture-governance.md` 定義 entry 的排除關與價值關
- `SPEC-governance-feedback-loop` / `SPEC-entry-consolidation-skill` 定義 entry 飽和後的壓縮治理

結果是：ZenOS 已經知道「entry 可以存什麼」與「什麼時候要蒸餾」，但還沒有一份單一文件清楚定義：

- 什麼叫高品質的 entry
- journal 和 entry 的邊界在哪裡
- 蒸餾時應如何判斷保留、跳過、或降級為其他層
- 蒸餾品質應如何被驗證與持續改善

缺少這份規格，會導致不同 agent 對同一段素材做出不同品質的蒸餾結果：

- 有些 entry 只是 journal 的縮句版
- 有些 entry 重複了 SPEC / ADR 已經是 SSOT 的內容
- 有些 entry 雖然正確，但不會改變任何後續行為
- 有些 entry 缺少來源脈絡，日後難以判斷是否仍可信

本 spec 的目標，是把「entry 蒸餾品質」定義成可驗收、可治理、可傳播的產品能力，而不是把它留在 skill prompt 裡各自猜。

## 目標用戶

- 使用 ZenOS capture / governance workflow 的 client agent
- 依賴 L2 entity 做理解與決策的 PM / Architect / Developer / QA
- 需要判斷知識是否值得長期留存的知識治理者

## Spec 相容性

已比對的既有 Spec / ADR：

- `docs/specs/SPEC-l2-entity-redefinition.md`
- `docs/decisions/ADR-010-entity-entries.md`
- `docs/decisions/ADR-014-journal-entry-distillation.md`
- `docs/specs/SPEC-governance-feedback-loop.md`
- `docs/specs/SPEC-entry-consolidation-skill.md`

衝突結論：無直接衝突，且本 spec 應獨立成文件，不應回填進 `SPEC-l2-entity-redefinition`。

原因：

- `SPEC-l2-entity-redefinition` 的責任是定義 L2 的升降級標準，不是定義蒸餾品質
- `ADR-010` 的責任是資料模型與生命週期，不是定義產品層品質判準
- `ADR-014` 的責任是觸發時機，不是定義蒸餾好壞
- `SPEC-governance-feedback-loop` 與 `SPEC-entry-consolidation-skill` 的責任是飽和後治理，不是定義 entry 產生前的品質閘

## 需求

### P0（必須有）

#### 1. 明確定義 journal 與 entry 的邊界

- **描述**：系統必須把 `journal` 與 `entry` 的定位清楚切開。journal 是工作時間軸記錄；entry 是掛在 L2 entity 上、會改變後續理解或行為的知識蒸餾。
- **Acceptance Criteria**：
  - Given 一段 work journal 只描述「今天做了什麼」，When 執行蒸餾，Then 不得直接把該段 journal 原文或其縮句版寫成 entry
  - Given 一段素材包含「決策原因 / 已知限制 / 定義變更 / 關鍵脈絡」，When 這些內容能掛到某個 L2 entity，Then 才可被蒸餾為 entry
  - Given 一條候選內容無法回答「這會改變下一個 agent 或同事的行為嗎」，Then 該內容不得寫成 entry

#### 2. 定義 entry 蒸餾的品質標準

- **描述**：每條 entry 在寫入前，都必須通過統一品質標準，至少包含：非重述、可行動、可歸屬、可追溯、單一知識點。
- **Acceptance Criteria**：
  - Given 候選內容只是重述既有 SPEC / ADR / 文件中已明確定義的內容，Then 系統跳過，不寫 entry
  - Given 候選內容包含兩個以上獨立知識點，Then 系統拆分成多條候選，或整條跳過並標記粒度過大
  - Given 候選內容無法掛載到單一 L2 entity，Then 系統不得寫 entry，需改走其他層級或人工處理
  - Given 候選內容正確但過度抽象，不足以改變後續行為，Then 系統標記為低價值並跳過

#### 3. 定義蒸餾來源的優先級與可信度

- **描述**：不同來源的素材品質不同，系統必須對蒸餾來源做明確分級，避免把低脈絡素材蒸餾成高信度知識。
- **Acceptance Criteria**：
  - Given 同一知識點同時出現在對話與文件中，Then 系統優先保留「文件未寫明、但對話提供的決策原因 / 限制 /背景」作為 entry，而不是重抄文件內容
  - Given 候選內容只來自工作 journal，Then 系統需把它視為「待蒸餾素材」，而不是自動等同高品質 entry
  - Given 候選內容只來自 code / git history 可直接取得的事實，Then 系統不得把它寫成 entry

#### 4. 蒸餾結果必須保留來源脈絡

- **描述**：每條 entry 至少要能回溯到來源素材類型與最小脈絡，避免日後無法判斷它為何存在。
- **Acceptance Criteria**：
  - Given 系統寫入一條 entry，Then 蒸餾流程必須保留其來源類型（例如 conversation / journal / task result / document）
  - Given entry 來自 journal 壓縮蒸餾，Then 必須能回溯到對應的 summary journal
  - Given entry 來自 task result，Then 必須能回溯到對應 task 或結果脈絡

#### 5. 蒸餾流程必須輸出「為什麼跳過」

- **描述**：高品質蒸餾不只要輸出 entry，也要能解釋哪些候選被排除，以及為什麼排除。
- **Acceptance Criteria**：
  - Given 一次蒸餾沒有寫入任何 entry，Then 系統仍需回報是因為「無新知識 / 重複 / 太抽象 / 無法歸屬 / 已在文件內」中的哪一類原因
  - Given 一次蒸餾寫入部分 entry 並跳過其他候選，Then 系統需同時呈現新增與跳過摘要

#### 6. entry 品質必須進入治理檢查

- **描述**：entry 品質不能只靠單次 skill prompt，必須成為 analyze / governance loop 可檢查的品質面向。
- **Acceptance Criteria**：
  - Given 某個 L2 的 entries 大量缺少來源脈絡、重複、或內容過於抽象，Then analyze 必須能標出該 L2 的 entry_quality 風險
  - Given 某個來源路徑持續產出低價值 entry，Then 系統能提示需要回頭調整蒸餾規則或 workflow

### P1（應該有）

#### 7. 建立低信度蒸餾的人工審核路徑

- **描述**：高價值但低信度的候選，不應在自動蒸餾時直接丟棄，也不應直接寫入；需要標準化的人工審核路徑。
- **Acceptance Criteria**：
  - Given 候選內容具有潛在價值，但無法穩定判斷 entity 歸屬或是否重複，Then 系統將其標記為 review-needed，而不是直接寫入
  - Given 人工確認該候選值得保留，Then 可升級為 entry

#### 8. 蒸餾品質要能從使用信號反饋

- **描述**：若某些 entry 常被搜尋但未被採用，或讀取後仍無法支持決策，應作為品質改善信號。
- **Acceptance Criteria**：
  - Given 某個 L2 的 entries 長期存在但幾乎不被後續工作使用，Then 系統能將其視為「低行為改變價值」的候選
  - Given 某種蒸餾來源持續產生低使用價值的 entry，Then analyze 或治理報告能提出改善建議

#### 9. 支援跨來源交叉驗證的蒸餾加權

- **描述**：同一知識點若同時被 journal、task result、對話或文件間接支持，應比單一來源更值得被保留。
- **Acceptance Criteria**：
  - Given 同一知識點被多個來源支持，Then 系統提高其蒸餾保留優先級
  - Given 某候選只出現在單一低脈絡來源，Then 系統降低其自動寫入優先級

### P2（可以有）

#### 10. 對不同 entry type 建立專屬品質規則

- **描述**：`decision`、`insight`、`limitation`、`change`、`context` 的品質標準不應完全相同，未來應逐步細化。
- **Acceptance Criteria**：
  - Given 候選 type 為 `decision`，Then 系統要求它能說出選擇或取捨理由，而不是只有結論
  - Given 候選 type 為 `change`，Then 系統要求它能說出「改了什麼」與對既有理解的影響
  - Given 候選 type 為 `context`，Then 系統要求它補的是背景，不是價值口號

## 明確不包含

- **不重新定義 L2 三問**：L2 的分層標準仍以 `SPEC-l2-entity-redefinition` 為準
- **不重寫 entry 資料表 schema**：entry 的 DB 結構與生命週期仍以 `ADR-010` 為準
- **不改寫 journal 壓縮觸發時機**：journal compressed 的觸發契約仍以 `ADR-014` 為準
- **不定義 entry consolidation workflow**：entry 飽和後的合併、archive、驗證流程仍以 `SPEC-entry-consolidation-skill` 為準
- **不要求所有 entry 都走人工確認**：本 spec 只定義品質與邊界，不把 entry 升級成高成本審批流

## 技術約束（給 Architect 參考）

- 蒸餾品質規則至少會影響三條路徑：
  - `/zenos-capture` 對話 / 結果蒸餾
  - `journal_write -> compressed:true` 後的 entry 蒸餾
  - `analyze(check_type="quality")` 的 entry 品質檢查
- 若需要新增資料欄位或回傳欄位，必須證明它們服務於以下其中一項：
  - 可追溯性
  - 去重 / 衝突判斷
  - 品質評估
  - 人工 review 路徑
- 不得把「蒸餾品質」只藏在 skill prompt 中。至少要有一層 server / analyze / tool response 可觀測

## 開放問題

- 來源脈絡應以何種形式保留最合適：寫入 DB 欄位、寫入 context、還是只保留在 tool response / audit log？
- 低信度候選應走哪一條最小人工 review 路徑，才不會讓蒸餾成本過高？
- `entry_quality` 應作為 `analyze(check_type="quality")` 的既有子項，還是獨立 check_type？
- 「已在文件裡，不必重複寫 entry」的判斷，要用字串比對、語意比對，還是由 agent 先做粗判再交由 server 驗證？

## 下一步

- PM：確認本 spec 作為獨立文件成立，不併入 `SPEC-l2-entity-redefinition`
- Architect：基於本 spec 撰寫技術 ADR，決定蒸餾管線、可觀測欄位、品質檢查與回寫路徑
- Developer：依 ADR 實作 capture / journal / analyze 的對應變更
