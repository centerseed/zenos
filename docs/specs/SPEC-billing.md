# Feature Spec: Billing（計費模型）

## 狀態
Approved

## 背景與動機

ZenOS 採用「一公司一 Firebase Project」的物理隔離架構（見 SPEC-multi-tenant.md）。每開一個新客戶，就多一個獨立的 Firebase Project，對應一份基礎設施成本。ZenOS 目前沒有任何計費系統，Phase 0 的唯一客戶 Paceriz 是免費試用（dogfooding）。

當第二間客戶出現時，ZenOS 必須有明確的計費概念模型：向誰收、收什麼、怎麼開始、付費狀態怎麼影響服務存取。這份 Spec 不定義實作細節，而是建立商業與產品層級的決策基礎，讓之後的技術設計能對齊。

---

## 目標用戶

| 用戶 | 場景 |
|------|------|
| 客戶公司管理員 | 需要知道自己在付什麼錢、帳單狀態如何 |
| ZenOS 創辦人 / 業務 | 報價時有清楚的計費結構可以說明 |
| ZenOS 工程師 | 開設新 instance 時知道付費狀態要怎麼管 |

---

## 核心假設（需確認）

以下假設根據現有架構資訊推導，標有「待確認」的項目見「開放問題」。

1. 收費單位是**公司**，不是個人 seat
2. ZenOS 的 AI 功能（ontology 分析、governance AI）用 ZenOS 自己的 LLM key，這部分成本按實際用量計費，反映在帳單明細裡
3. 員工 agent 的 LLM key 是各公司自己提供，不在 ZenOS 計費範圍內
4. Phase 0 Paceriz 繼續免費，不受此 Spec 影響

---

## 需求

### P0（概念模型——不需立刻實作，但架構設計必須考慮）

#### 1. 收費結構：三段式計費

- **描述**：ZenOS 向每間客戶公司收取三個項目的費用，共同構成每期帳單：

  - **月費**：基本服務費，固定金額，不隨用量浮動。客戶可類比「訂閱費」或「平台費」。
  - **LLM 使用費**：ZenOS AI 功能（governance AI、ontology 處理、enriched task dispatch 等）的實際用量費用，按每間公司的實際 AI 呼叫量計算，由 ZenOS 代墊後計入帳單明細。
  - **雲端成本**：該公司 Firebase Project 的實際基礎設施費用（Cloud Run、Firestore reads/writes、Storage 等），直接轉嫁給客戶或包含在方案定價內（Phase 1 定價時決定）。

  Phase 0/1 的帳單可以是 ZenOS 工程師手動計算後開立，Phase 2 才考慮自動化帳單系統。

- **Acceptance Criteria**：
  - Given 一間客戶公司的帳單期到期，When ZenOS 計算帳單，Then 帳單包含三個明細項目：月費（固定）、LLM 使用費（按量）、雲端成本（按量）。
  - Given 兩間用量差異大的客戶，When 同一帳單週期結束，Then 月費相同，LLM 使用費和雲端成本不同，反映各自的實際用量。

- **技術影響（給 Architect）**：
  - LLM 用量必須能被追蹤（per-company），Phase 1 要能顯示在帳單介面上
  - Firebase Project 的雲端成本必須能被查詢（per Firebase project），Phase 1 要能顯示在帳單介面上

#### 2. 付款責任人：公司管理員（第一版）

- **描述**：每間公司的 ZenOS 管理員（`isAdmin: true`）是這間公司的付款責任人。付款資訊（信用卡或匯款）綁定在公司層級，不在個人帳號層級。實務上付款的人通常是會計，但第一版先以 admin 身份做，之後根據需求再調整（例如新增財務角色）。
- **Acceptance Criteria**：
  - Given 一間公司有多個管理員，When 其中任一管理員更新付款資訊，Then 公司層級的付款資訊更新，其他管理員能看到最新狀態。
  - Given 一個一般成員（非管理員），When 他查看帳單相關頁面，Then 沒有存取權限。

#### 3. 新客戶流程：試用先行，訂閱無縫銜接

- **描述**：新客戶預設進入試用（`trial`）狀態。試用到期日由 ZenOS 工程師在開設 instance 時手動設定（configurable，不是固定天數）。到期日前若客戶確認訂閱並完成首次付款，trial 期間的所有使用記錄完整保留，等於試用期不浪費。到期日後未訂閱則轉入 `grace_period`，之後進入 `suspended`。

  整個流程：
  1. ZenOS 工程師開設 instance，設定試用到期日，instance 狀態為 `trial`
  2. 客戶使用 ZenOS，試用期間 LLM 用量和雲端成本開始累計
  3. 到期日前 → 客戶確認訂閱 + 首次付款 → instance 狀態變為 `active`，試用記錄保留
  4. 到期日後未付款 → 轉 `grace_period`（預設 7 天）→ 仍未付款 → `suspended`

- **Acceptance Criteria**：
  - Given ZenOS 工程師開設新 instance，When 設定試用到期日，Then instance 狀態為 `trial`，到期日被記錄並可被查詢。
  - Given `trial` 狀態的 instance，When 管理員在到期日前完成首次付款，Then instance 狀態更新為 `active`，試用期間的所有資料（entities、tasks、用量記錄）完整保留，無需重新建立。
  - Given `trial` 狀態的 instance，When 到期日已過且未付款，Then instance 自動進入 `grace_period`。
  - Given 試用到期日可由工程師在開設 instance 時設定，When 不同客戶的談判週期不同，Then 工程師可以為每個 instance 設定不同的試用到期日，而非所有客戶都是固定天數。

#### 4. 付費狀態影響服務存取

- **描述**：付費狀態有四種：`trial`（試用中）、`active`（正常付費）、`grace_period`（逾期但在寬限期）、`suspended`（暫停服務）。不直接刪除資料，而是暫停存取，讓客戶有機會補繳或決定是否繼續。
- **Acceptance Criteria**：
  - Given instance 付費狀態為 `trial` 或 `active`，When 成員登入 Dashboard 或用 MCP 連線，Then 正常存取，無任何障礙提示。
  - Given 帳單逾期但在寬限期內（預設 7 天），When 成員登入 Dashboard，Then 能正常使用，但管理員看到帳單警告橫幅。MCP 連線不中斷。
  - Given 超過寬限期，When 成員嘗試登入 Dashboard 或用 MCP 連線，Then 無法存取，看到「服務暫停，請聯繫 ZenOS」的說明。資料保留不刪除。
  - Given instance 從 `suspended` 恢復付款，When 付款確認，Then 存取在 N 小時內恢復（N 待 Architect 評估）。

#### 5. suspended 後資料保留 3 個月

- **描述**：instance 進入 `suspended` 後，資料保留 3 個月。3 個月後若仍未恢復付款，ZenOS 可以歸檔或刪除資料。這個期限讓客戶有充分時間決定是否續約，同時控制儲存成本。
- **Acceptance Criteria**：
  - Given instance 進入 `suspended` 狀態，When 3 個月內客戶恢復付款，Then 所有資料完整保留，服務可以恢復。
  - Given instance 進入 `suspended` 後超過 3 個月，When ZenOS 工程師執行資料清理，Then 可以歸檔或刪除這個 instance 的資料，屬於正常操作範圍。
  - Given instance 的資料保留截止日期，When 截止日前 30 天，Then ZenOS 工程師收到提醒（Phase 1 可以是手動流程）。

#### 6. ZenOS 自用 LLM cost 的處理方式

- **描述**：ZenOS 的 AI 功能（ontology 分析、governance AI、enriched task dispatch 等）使用 ZenOS 自己持有的 LLM API key。這部分費用由 ZenOS 代墊，按各公司實際用量計算後列入帳單的「LLM 使用費」明細（見需求 1）。員工 agent 的 LLM key 是各公司自己的事，ZenOS 不管也不計入帳單。
- **Acceptance Criteria**：
  - Given ZenOS 向一間公司收取帳單，When 這間公司的成員使用 ZenOS AI 功能（如 governance AI 建議），Then LLM 費用被記錄到這間公司的用量帳戶，列入下期帳單的 LLM 使用費明細。
  - Given 一個員工用自己的 Claude / GPT agent 連線 ZenOS MCP，When 這個 agent 產生 LLM token 費用，Then 這筆費用在這個員工的帳號上，與 ZenOS 帳單無關。

---

### P1（Phase 1 開始收費時要做的功能）

#### 7. 帳單管理介面（管理員視角）

- **描述**：管理員能在 Dashboard 看到帳單狀態、付款紀錄、到期日，以及 LLM 使用費和雲端成本的用量明細。不一定要在 Dashboard 內完成付款（可以轉到第三方付款頁面），但狀態和用量明細要在 Dashboard 可見。
- **Acceptance Criteria**：
  - Given 管理員登入 Dashboard，When 進入帳單頁面，Then 能看到：當前方案、下次收費日期、上次付款紀錄、付款狀態、本期 LLM 使用費累計、本期雲端成本累計。
  - Given 付款即將到期（30 天內），When 管理員登入，Then Dashboard 顯示到期提醒。

#### 8. 付款逾期通知

- **描述**：帳單到期時，自動發 email 給管理員，說明逾期狀態、寬限期天數、付款連結。不依賴管理員主動進 Dashboard 才知道。
- **Acceptance Criteria**：
  - Given 帳單到期日當天，When 自動結帳失敗，Then 管理員收到逾期通知 email，包含寬限期截止日期和付款連結。
  - Given 寬限期剩 1 天，When 尚未付款，Then 管理員收到最後提醒 email。

#### 9. 試用轉付費無縫接軌（ZenOS 工程師操作）

- **描述**：試用中的客戶確認付款後，ZenOS 工程師手動將 instance 狀態從 `trial` 更新為 `active`。資料完整保留，instance 不需要重建。Phase 1 先用手動流程，Phase 2 才評估自動化。
- **Acceptance Criteria**：
  - Given 一個 `trial` 狀態的 instance，When ZenOS 工程師確認付款後更新狀態為 `active`，Then instance 狀態正確更新，試用期間的所有資料保留，管理員下次登入看到正常的 `active` 狀態。

---

### P2（進階計費功能）

#### 10. 用量分層定價

- **描述**：若未來 ZenOS 的 LLM cost 與客戶規模高度相關，可以考慮按用量（entity 數量、AI 呼叫次數）分層定價。Phase 0/1 先用固定月費 + 實際用量模型，Phase 2 才評估是否需要分層方案。
- **Acceptance Criteria**：
  - Given 客戶選擇進階方案，When 月 AI 呼叫量超過基礎方案上限，Then 超出部分按設定費率計費，管理員能在帳單頁面看到明細。

#### 11. 地端部署授權到期提醒

- **描述**：地端部署的客戶，授權到期前 30 天通知管理員。（對應 SPEC-multi-tenant.md P2）
- **Acceptance Criteria**：
  - Given 地端部署的 instance，When 授權到期日前 30 天，Then 管理員收到 email 提醒。
  - Given 授權到期，When 管理員登入 Dashboard，Then 看到續約提示橫幅。

#### 12. 多方案管理（ZenOS 內部）

- **描述**：ZenOS 內部能管理不同客戶的不同方案（月費 vs 年費、試用 vs 正式、標準 vs 企業）。Phase 1 先用 spreadsheet 管理，Phase 2 才評估是否需要 ops dashboard。
- **Acceptance Criteria**：
  - Given ZenOS 有多間客戶，When 查看方案管理介面，Then 能看到每間公司的方案類型、有效期、付款狀態。

#### 13. 自動付款整合（Stripe 等）

- **描述**：Phase 1 先用手動確認付款流程（工程師確認付款後手動改狀態）。Phase 2 才整合 Stripe 等支付閘道，實現自動扣款和自動狀態更新。
- **Acceptance Criteria**：
  - Given 客戶帳單到期，When 自動扣款成功，Then instance 狀態保持 `active`，付款紀錄自動更新。
  - Given 自動扣款失敗，When 系統偵測到失敗，Then 自動進入 `grace_period` 流程並發送通知。

---

## 明確不包含

- 個人 seat 計費（ZenOS 不走 per-seat 模型）
- 自助開設 instance 並自動付款（Phase 0/1 由 ZenOS 工程師手動開設）
- 員工 agent 的 LLM cost 管理（各公司自行負責）
- 退款政策細節（商業決策，不在 spec 範圍）
- 多貨幣支援（Phase 0/1 先處理台幣 / 美元，不做多幣種切換介面）
- 電子發票（ZenOS 目前是日本公司，Phase 0 不處理）
- 台灣電子發票 / 統一發票（暫不適用）

---

## 技術約束（給 Architect 參考）

- **付費狀態必須在 Firebase Project 層級可讀**：MCP server 在驗證請求時需要能快速判斷這個 instance 是否 `active` 或 `trial`，不能每次都打外部 API
- **付費狀態變更必須有 audit trail**：`trial → active`、`active → suspended`、`suspended → active` 等狀態轉換要有時間戳記和操作者紀錄，避免糾紛
- **LLM 用量追蹤（per-company）**：Phase 1 帳單介面要顯示各公司的 LLM 使用費，Architect 需要設計用量記錄機制（per AI 呼叫，per company）
- **雲端成本查詢（per Firebase project）**：Phase 1 帳單介面要顯示各公司的雲端成本，Architect 需要評估如何從 Firebase / GCP billing API 查詢 per-project 費用
- **試用到期日為可設定欄位**：工程師開設 instance 時能指定到期日，不是 hardcode 天數
- **資料保留 3 個月**：`suspended` 後 3 個月資料才可歸檔或刪除，Architect 設計時先保留資料，不自動刪除

---

## 開放問題

1. **月費定價**：ZenOS 向每間公司收多少錢？這個數字會影響 LLM cost 的上限設定。（Barry 待確認）

2. **寬限期長度**：帳單逾期後的寬限期預設幾天？本 spec 假設 7 天，待 Barry 確認是否調整。

3. **地端部署的計費模型**：地端客戶無法靠 Firebase 層檢查付費狀態，授權機制是什麼？是 license key？還是另一套流程？（SPEC-multi-tenant.md P2 也提到，需要一起討論）

4. ~~**LLM cost 超支的安全網**：若某間公司的 governance AI 用量異常暴增，ZenOS 是否設上限？超出後降級服務還是繼續但發警告？（影響 SLA 設計）~~ **已解答**：由客戶自行決定。管理介面提供用量上限設定，客戶可選擇超出後的行為（如暫停 AI 功能、發警告繼續使用等），ZenOS 不強制統一策略。

5. ~~**雲端成本轉嫁 vs 包含在月費**：三段式計費中，雲端成本是直接轉嫁客戶（實報實銷），還是包含在月費定價內（ZenOS 吸收浮動）？Phase 1 定價時需要決定。~~ **已解答**：按實際費用轉嫁。ZenOS 直接讀取 Firebase 帳單，加上 margin 後列在帳單明細中，客戶看到的是含 margin 的實際雲端成本，ZenOS 不吸收浮動。

---

## 變更紀錄

| 日期 | 變更摘要 |
|------|----------|
| 2026-03-24 | 根據 Barry 回覆更新：收費結構改為三段式（月費 + LLM 使用費 + 雲端成本）；試用流程改為 configurable 到期日 + 試用記錄保留；suspended 後資料保留 3 個月；關閉電子發票問題（日本公司，Phase 0 不處理）；付款責任人加入「先用 admin 做第一版」說明 |
| 2026-03-24 | 初版 Draft 建立 |
