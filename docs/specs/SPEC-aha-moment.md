---
type: SPEC
id: SPEC-aha-moment
status: Draft
ontology_entity: dashboard
created: 2026-04-06
updated: 2026-04-23
depends_on: SPEC-dashboard-onboarding, SPEC-agent-integration-contract
---

# Feature Spec: Aha Moment 設計——三角色首次驚喜體驗

**版本：** 0.1（2026-04-06）
**作者：** PM

---

## 背景與動機

ZenOS 的核心價值主張是「建一次 ontology，公司每個 AI agent 都共享同一套 context」。然而一個反覆出現的導入問題是：**新用戶不知道 ZenOS 能替他們做什麼**。

過去的產品策略傾向於「可見性功能」——把知識圖譜視覺化、讓 dashboard 顯示節點、呈現 impact chain 等。這些功能有其價值，但它們回答的是「ZenOS 裡有什麼」，而不是「ZenOS 能幫我做什麼」。

**本 Spec 轉向「體驗瞬間設計」（Aha Moment Design）。** 策略轉換的核心洞察是：

> 用戶不會因為看到知識圖譜而留下來。他們會因為第一次提問就得到正確答案而留下來。

不同角色的「正確答案」不同。本 Spec 鎖定三個高價值、高頻率的首次互動場景，每個場景設計成：**用戶不需要解釋背景，系統就能交付一個立即可用的結果**。

### 三個場景的共同前提

這三個行動都依賴 ontology 資料品質。沒有持續維護的 ADR、沒有工程師寫入的 onboarding 知識、沒有定期更新的 impact chain，任何一個 Aha Moment 都無法成立。這也是本 Spec 把三者放在同一份文件的原因——它們共享同一個底層約束：**知識品質是所有角色體驗的共同前提**。

### Impact Chain 說明（來自 ZenOS ontology 查詢）

本 Spec 掛在 `Action Layer` 節點下（`ontology_entity: action-layer`）。
Action Layer 的下游影響鏈包括 L3 文件治理、L3 Task 治理規則、MCP 介面設計等。
行動 1（ADR 查詢）直接涉及 L3 文件治理；行動 3（Impact Chain 可信度）涉及 MCP 介面設計的回傳格式。
若 Action Layer 的任務模型或反寫規則更動，本 Spec 的驗收場景需重新評估。

---

## 目標用戶

| 角色 | 場景 | 觸發動作 |
|------|------|---------|
| CEO / 高階主管 | 準備週報或季報，想了解這段時間最重要的技術決策 | 問「這季最重要的技術決策是什麼？」 |
| 新進工程師 | 第一週進公司，試著設定本地開發環境或詢問公司特定慣例 | 問「如何設定本地開發環境？」或任何公司專屬問題 |
| 資深工程師 | 評估一個模組的異動風險，查 impact chain 判斷影響範圍 | 呼叫 `mcp__zenos__get`，閱讀 impact chain |

---

## 需求

### P0（必須有）

#### 行動 1：ADR 查詢與提煉（CEO Aha Moment）

- **描述：** 用戶給定一個專案與時間區間（例如「這季」），系統自動撈出該期間所有 `type=ADR` 的文件，提煉成最多 Top 3 的決策摘要，格式可直接貼入週報。每條摘要包含：決策標題、一句話背景、一句話結論、相關模組名稱。輸出不出現技術術語，以高階主管能理解的語言表達。
- **Acceptance Criteria：**
  - Given 一個 `project` + `start_date` + `end_date`，When 用戶查詢「這段時間的技術決策」，Then 系統回傳該期間所有 ADR 文件列表（依日期排序）
  - Given 查詢結果包含多筆 ADR，When 系統提煉摘要，Then 輸出最多 3 筆，每筆包含：標題（不超過 20 字）、背景（1 句）、結論（1 句）、相關模組（不超過 3 個，以產品名稱呈現而非 entity ID）
  - Given 查詢結果為 0 筆，When 系統回傳，Then 明確說明「這段時間無已記錄的決策」，不顯示空白或報錯
  - Given 摘要輸出，When 高階主管閱讀，Then 內容不出現「ontology」「entity」「ADR」等技術術語（以「決策」「紀錄」「模組」替代）

#### 行動 2：Onboarding 知識條目（新進工程師 Aha Moment）

- **描述：** 新進工程師提問任何公司特定問題（如「如何設定本地開發環境」「這個 MCP key 從哪取得」），系統回傳一份有結構的回答，包含：正確操作步驟、至少一個已知問題、對應解法、適用情境說明。資深工程師寫入一條 onboarding 知識條目不超過 3 個步驟的輸入動作。
- **Onboarding 條目格式定義：**
  - **步驟**：編號清單，每步驟一個操作
  - **已知坑**：至少一條，描述常見錯誤或容易踩的問題
  - **解法**：對應每個已知坑的解決方式
  - **適用情境**：說明這份條目在什麼情境下有效（例如「適用 macOS + Python 3.12，不適用 Windows」）
- **Acceptance Criteria：**
  - Given 新進工程師提問一個公司特定問題，When 系統回傳，Then 回答包含步驟、至少一個已知坑與解法、適用情境四個區塊
  - Given 回答包含「適用情境」，When 工程師閱讀，Then 能判斷這份說明是否適用於自己的環境，不會誤用過期資訊
  - Given 資深工程師想寫入一條新 onboarding 知識，When 完成寫入操作，Then 所需操作步驟不超過 3 步（例如：選擇問題類型 → 填寫內容 → 確認送出）
  - Given 問題無對應條目，When 系統回傳，Then 明確說明「目前無此主題的 onboarding 紀錄」，並提示如何建立

#### 行動 3：Impact Chain 可信度標示（資深工程師 Aha Moment）

- **描述：** `mcp__zenos__get` 回傳的 impact chain 中，每個節點附帶「最後更新時間」（`updated`）。當節點的更新時間超過設定閾值 N 天時，該節點顯示明確的警示文字，提醒工程師這條影響鏈可能已不反映最新狀態。N 值為可設定的參數，不寫死在系統裡。
- **Acceptance Criteria：**
  - Given `mcp__zenos__get` 回傳 impact chain，When 工程師閱讀，Then 每個節點都顯示 `updated` 時間戳（ISO 8601 格式）
  - Given 某節點的 `updated` 時間距今超過 N 天，When 系統標示，Then 該節點旁出現明確警示文字（例如：「此節點已 45 天未更新，請確認是否仍反映現狀」），而非僅顯示顏色或 icon
  - Given N 值需要調整，When 管理員修改設定，Then 不需要修改程式碼即可生效
  - Given 所有 impact chain 節點都在 N 天內更新，When 工程師閱讀，Then 無多餘警示，介面保持簡潔

---

### P1（應該有）

#### ADR 查詢支援自然語言時間描述

- **描述：** 用戶可以用「這季」「上個月」「Q1」等自然語言描述時間區間，系統自動解析為日期範圍，不需要手動輸入 `start_date` / `end_date`。
- **Acceptance Criteria：**
  - Given 用戶輸入「這季」，When 系統解析，Then 正確對應到當前季度的開始與結束日期
  - Given 用戶輸入「上個月」，When 系統解析，Then 對應到上個日曆月的第一天到最後一天

#### Onboarding 條目版本管理

- **描述：** 當一條 onboarding 知識條目被更新時，系統保留上一版本的歷史紀錄，讓工程師能查看「之前的做法是什麼」以及「什麼時候、為什麼改變」。
- **Acceptance Criteria：**
  - Given 一條現有條目被更新，When 更新完成，Then 系統保留前一版本內容與更新時間
  - Given 工程師查詢一條條目，When 選擇查看歷史，Then 能看到所有歷史版本與各版本的更新說明

---

### P2（可以有）

#### Onboarding 條目的自動過期提示

- **描述：** 超過一定時間未更新的 onboarding 條目，自動標記為「可能過時」，並提示最後維護者確認內容是否仍然有效。
- **Acceptance Criteria：**
  - Given 一條條目超過 90 天未更新，When 工程師查詢，Then 系統在結果旁顯示「此條目已超過 90 天未維護，請確認是否有效」
  - Given 維護者確認條目有效，When 確認操作完成，Then 計時器重置，條目不再顯示「可能過時」警示

---

## 明確不包含

- **主動推送機制：** 系統不主動通知 CEO、工程師或任何人。Aha Moment 設計的前提是用戶主動提問，推送機制屬於不同的需求場景。
- **外部整合（Notion / Linear 等）：** 本 Spec 的三個行動都在 ZenOS 內部完成，不連接外部工具。
- **業務或設計師的 Aha Moment：** 本 Spec 鎖定 CEO、新進工程師、資深工程師三個角色。其他角色的首次體驗設計留待後續 Spec。
- **ADR 自動生成：** 行動 1 只做查詢與提煉，不自動從程式碼或 PR 生成 ADR 草稿。
- **Onboarding 條目的 AI 自動補全：** 條目內容由工程師手動填寫，系統不自動從 codebase 生成建議內容。

---

## 技術約束（給 Architect 參考）

- **資料品質是前提：** 行動 1 依賴 ontology 中有完整的 ADR 文件（`type=ADR`，`date` 欄位正確填寫）；行動 2 依賴工程師實際寫入條目；行動 3 依賴 impact chain 節點的 `updated` 時間戳由系統自動維護（不可依賴人工填寫）。若 `updated` 時間戳需要由 server 在每次 entity 更新時自動打點，需確認目前 schema 是否已支援。
- **Impact chain 更新時間：** 行動 3 的「最後更新時間」必須由系統在 entity 寫入時自動維護，不能依賴 partner 手動填寫 `updated` 欄位，否則警示機制毫無意義。Architect 需確認 `write` 操作是否已正確 upsert `updated_at`。
- **ADR 摘要的語言轉換：** 行動 1 的「無技術術語」要求涉及語言轉換邏輯（ADR 原文可能有技術術語）。Architect 需決定這個轉換是在 server 端由 LLM 執行，還是由 calling agent 負責 prompt engineering。
- **N 值的設定機制：** 行動 3 的閾值 N 天需要一個可設定的位置（例如 per-partner 設定、或全域設定），Architect 需決定存放位置與讀取方式。
- **Onboarding 條目的存放：** 行動 2 的條目格式（步驟 + 已知坑 + 解法 + 適用情境）需要決定存放在 journal entry、獨立 entity，還是新的 collection——這是一個未解決的架構問題，見「開放問題」。

---

## 開放問題

1. **Onboarding 條目用 journal 還是獨立 entity？**
   - 選項 A：用 `journal_write` 寫入 flow_type="onboarding" 的日誌條目，利用現有機制，不需要新 schema。
   - 選項 B：建立獨立的 `entries` collection 條目（`type=onboarding`），有更好的查詢能力與版本管理。
   - 選項 C：建立新的 `onboarding` collection，完整支援條目格式、版本歷史、適用情境索引。
   - 待 Architect 評估實作成本與查詢效能後決定。

2. **Impact Chain 可信度的 N 值預設是多少天？**
   - 候選值：30 天、45 天、60 天。
   - 設計原則：太短會產生大量誤報（ontology 核心節點可能很穩定，不需要頻繁更新）；太長則警示失去意義。
   - 建議 Architect 在 TD 中提出預設值建議，並說明是否支援 per-entity 類型的不同閾值（例如：基礎建設節點 90 天、業務邏輯節點 30 天）。

3. **ADR Top 3 的排序邏輯是什麼？**
   - 選項 A：依文件日期排序，取最新 3 筆。
   - 選項 B：依 impact chain 中的影響廣度排序（影響更多下游的 ADR 優先）。
   - 選項 C：依 ontology 查詢頻率排序（被 search/get 次數最多的相關 entity 對應的 ADR 優先）。
   - 若選項 B 或 C，需要 server 端計算支援，複雜度更高。PM 傾向先實作選項 A，在 P1 時評估升級。

4. **行動 2 的「不超過 3 步」是指 UI 操作步驟還是 MCP 工具調用次數？**
   - 若透過 Dashboard UI 寫入，3 步指 UI 操作流程。
   - 若透過 MCP 工具寫入，3 步指 tool call 次數。
   - 需 Architect 確認主要入口是 Dashboard 還是 MCP。
