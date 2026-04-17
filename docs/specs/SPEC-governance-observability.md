# Feature Spec: 治理可觀測性（Governance Observability）

> **治理定位：Internal（治理基礎設施 → Quality Intelligence 數據基礎）**
> 本 spec 定義 server 內部的 LLM 推斷審計、準確度追蹤與 eval dataset 匯出機制。
> 不透過 governance_guide 暴露給��部 agent——這是 ZenOS 飛輪的數據基礎。
> 部分能力（推斷準確度趨勢、健康度指標）可透過 Dashboard 對用戶可見，但演算法細節不對外。
> 框架歸屬見 `SPEC-governance-framework` 治理功能索引。

**狀態：** Under Review
**版本：** 2.0（2026-03-25）
**作者：** PM
**相關文件：** `docs/archive/specs/SPEC-governance-quality.md`、`docs/specs/SPEC-l2-entity-redefinition.md`

> v1.0 草稿已被本版本完整取代。v1.0 聚焦在治理趨勢快照與 Dashboard 健康度，本版本將目標升級為「讓 log 成為治理演算法迭代的 data foundation」。

---

## 第一章：背景與動機

### 問題陳述

ZenOS 治理管線（governance pipeline）現在是黑盒子。LLM 每次跑推斷（infer_all），我們知道它跑了，但不知道：

- 它推斷了什麼（output 是什麼）
- 推斷前後的狀態差了什麼（before/after diff）
- 推斷用了哪些輸入（input snapshot）
- 推斷結果被 confirm 了多少、被 reject 了多少
- reject 的理由是什麼（是語意錯、粒度錯、還是 impacts 說不清）

這個問題不是監控告警問題，而是**演算法迭代的基礎設施缺口**。沒有結構化的歷史紀錄，就無法回答「這次演算法調整讓準確率變好還是變差」，也無法從人類 reject 行為中學到治理判斷基準。

### 真實缺口（基於現有 Cloud Logging 分析）

現有 AUDIT_LOG（textPayload 格式：`{timestamp} __main__ INFO AUDIT_LOG {JSON}`）已捕捉以下 event type（共 37 筆）：

| Event Type | 數量 |
|------------|------|
| ontology.entity.upsert | 18 |
| task.update | 13 |
| task.create | 3 |
| task.confirm | 1 |
| ontology.document.upsert | 1 |
| governance.infer_all.error | 1 |

已知 LLM Usage Logs 在 Firestore（`partners/{partnerId}/usage_logs`），結構有 timestamp、feature、model、tokens_in、tokens_out、partner_id。

已知 error distribution：
- GovernanceInference ValidationError: 5 次
- TaskLinkInference ValidationError: 3 次
- Connection CANCELLED: 2 次
- AuthenticationError: 1 次

**五個核心缺口：**

1. **成功推斷沒有 audit event**：只有 error 有 `governance.infer_all.error`，成功的推斷沒有留任何結構化紀錄。我們無法知道每次 infer_all 推斷了什麼。

2. **推斷的 before/after diff 沒記錄**：entity 被 LLM 更新時，我們知道「有 upsert 發生」，但不知道 upsert 之前是什麼狀態。無法判斷這次推斷是修正了什麼、還是退步了。

3. **LLM 錯誤被靜默吞掉**：`GovernanceInference ValidationError`（5 次）、`TaskLinkInference ValidationError`（3 次）發生時，audit log 沒有記錄足夠的 input context，工程師不知道是哪種輸入讓 LLM 產出無效 output。

4. **confirm/reject 有記但沒聚合分析**：個別的 `task.confirm` 有紀錄，但無法回答「這個 entity 被推斷了幾次、被 reject 了幾次、reject 理由分布是什麼」。

5. **無法回溯 entity 的推斷歷史**：現有 log 是事件流，沒有以 entity 為中心的推斷歷史 view。

### 核心目標

**讓 log 成為治理演算法迭代的 data foundation。**

具體來說，這個 feature 要讓工程師能夠：

1. 回顧每一次推斷的 input、output 和結果（被 confirm 還是被 reject）
2. 從 rejection reason 中找出 pattern，用來改進 prompt
3. 追蹤算法變更前後的推斷品質變化
4. 從歷史資料中抽取 eval dataset（input + output + human verdict）

---

## 目標用戶

| 用戶 | 場景 |
|------|------|
| ZenOS 工程師 | 要改進治理 prompt，需要知道哪些案例的推斷結果被 reject，以及 reject 的原因 |
| ZenOS 工程師 | 要做算法 A/B 測試，需要能標記不同算法版本，比較同批輸入的推斷品質 |
| ZenOS 工程師 | 要建立 eval dataset，需要匯出「input + LLM output + human verdict」的結構化資料 |
| Partner 管理員 | 要了解自己的知識圖譜治理健康度，需要看到推斷準確率和 confirm 狀況 |

---

## 第二章：AUDIT_LOG 增強

這一章定義需要新增的 event type 和需要補強的欄位內容，讓每一次推斷都留下完整可分析的紀錄。

### 需要新增的 Event Type

#### 2.1 governance.infer_all.success

**為什麼需要：** 目前成功的 infer_all 沒有任何 audit event，工程師無法知道一次推斷的輸入規模、輸出結果、和推斷了哪些 entity。

**需要記錄的資訊：**

- `algorithm_version`：本次使用的算法版本標識（讓工程師能追蹤哪個版本產出哪批推斷）
- `entities_processed`：本次處理的 entity 數量
- `entities_changed`：實際產生變更的 entity 數量（與 entities_processed 的差值 = 未變更數量）
- `inference_diff`：每個被改動 entity 的欄位層級 before/after diff（不需要完整 document，只需記錄哪個欄位從什麼值改成什麼值）
- `input_snapshot_ref`：指向本次推斷輸入摘要的 reference（至少包含觸發這次推斷的事件類型、處理的 entity ID 列表）

**Acceptance Criteria：**
- Given 一次 infer_all 成功完成，When 查詢 AUDIT_LOG，Then 存在一筆 `governance.infer_all.success` event，包含上述所有欄位
- Given 該 event，Then `partner_id` 欄位存在，支援 per-partner 過濾

#### 2.2 governance.infer_all.skip

**為什麼需要：** 區分「推斷了但什麼都沒改」和「根本沒跑推斷」——這兩種狀況需要不同的解釋。

**需要記錄的資訊：**

- `skip_reason`：跳過的原因（例如「沒有需要推斷的 entity」、「距離上次推斷未滿冷卻期」等）

**Acceptance Criteria：**
- Given 一次 infer_all 因條件不滿足而跳過，When 查詢 AUDIT_LOG，Then 存在一筆 `governance.infer_all.skip` event，包含 skip_reason

### 需要補強的現有 Event

#### 2.3 governance.infer_all.error 補強 input context

**為什麼需要：** 現有 error event 只記錄錯誤發生了，但沒有記錄觸發錯誤的輸入。工程師看到 ValidationError 但不知道是哪種 entity 或哪個 prompt 環節出問題。

**現有 event 需要補充的欄位：**

- `error_type`：錯誤類型分類（ValidationError / ConnectionError / AuthError / TimeoutError / UnexpectedError）
- `input_context`：觸發錯誤的輸入摘要，至少包含：處理的 entity_ids 列表、本次推斷的類型（infer_all / infer_task_links 等）、使用的 model
- `raw_llm_output`：LLM 回傳的原始 output（如果有的話），讓工程師能看到為何 validation 失敗

**Acceptance Criteria：**
- Given LLM 推斷發生 ValidationError，When 查詢 `governance.infer_all.error` event，Then governance 欄位包含 error_type、input_context（含 entity_ids 和 model）、raw_llm_output（如有）

#### 2.4 ontology.entity.upsert 補強 before/after diff

**為什麼需要：** 目前 upsert event 的 `changes` 欄位只記錄更新後的值，不記錄更新前的值。工程師看到「summary 被更新了」但不知道從什麼改成什麼。

**需要補充的欄位格式：**

- `changes` 欄位改為 `{field_name: {before: "舊值", after: "新值"}}` 格式
- 如果是新建（before 不存在），before 為 null
- 這個要求對所有觸發 entity upsert 的操作都成立（算法觸發和人工觸發都要記）

**Acceptance Criteria：**
- Given 治理算法對 entity 的 summary 欄位做出修改，When 查詢 `ontology.entity.upsert` event，Then `changes` 欄位包含 `{summary: {before: "原有文字", after: "新文字"}}` 格式
- Given 人工手動更新 entity，When 查詢 event，Then changes 格式相同（before/after 都有）
- Given 新建 entity（無 before 狀態），When 查詢 event，Then before 為 null，after 為初始值

#### 2.5 confirm/reject 的 rejection reason 結構化

**為什麼需要：** 目前 `task.confirm` event 有記錄 accept 或 reject，但 reject 的原因是自由文字（如果有的話）。無法跨事件聚合「最常見的 reject reason 是什麼」。

**需要新增的欄位：**

當操作為 reject 時，`changes` 欄位需要包含：

- `reject_reason_category`：以下五個固定分類之一
  - `wrong_semantic`：語意判斷錯誤（推斷出了錯誤的概念）
  - `wrong_granularity`：粒度錯誤（切太細或太粗）
  - `missing_impacts`：缺少具體 impacts，推斷的 L2 說不清楚下游影響
  - `factually_incorrect`：事實錯誤（推斷的內容與現實不符）
  - `other`：其他
- `reject_reason_detail`：自由文字補充說明（optional）

**Acceptance Criteria：**
- Given 用戶 reject 一個治理推斷，When 系統記錄 reject 事件，Then `changes` 欄位包含 `reject_reason_category`（必填）和 `reject_reason_detail`（選填）
- Given 工程師查詢歷史 reject 記錄，When 按 `reject_reason_category` 聚合，Then 能得到各類 rejection 的數量分布

---

## 第三章：查詢介面增強

這一章定義新的查詢能力，讓工程師能從 AUDIT_LOG 中回答治理演算法迭代所需的問題。這些查詢能力應透過現有的 `analyze` MCP tool 新增 check_type，或透過新 MCP tool 暴露——技術選擇由 Architect 決定。

### 3.1 以 entity 為中心的推斷歷史查詢

**能回答的問題：**「這個 entity 被推斷過幾次？推斷結果被 reject 幾次？常見的 reject reason 是什麼？每次推斷前後狀態差了什麼？」

**查詢輸入：**
- entity_id（必填）
- 時間範圍（optional，預設最近 30 天）

**查詢輸出，每筆推斷歷史包含：**
- 推斷發生的時間戳
- 推斷前後的 diff（哪些欄位改了什麼）
- 觸發這次推斷的 input_snapshot_ref（哪些文件或事件驅動的）
- human verdict：confirm / reject / pending
- 如果 reject，包含 reject_reason_category 和 reject_reason_detail
- 使用的 algorithm_version

**Acceptance Criteria：**
- Given 工程師提供 entity ID，When 執行推斷歷史查詢，Then 返回該 entity 的推斷歷史列表，每筆包含上述所有欄位
- Given 查詢結果有 N 筆，Then 工程師能計算「被推斷了 N 次，被 reject 了 M 次，最常見的 reject 原因是 X」
- Given entity ID 不存在，Then 回傳 NOT_FOUND 錯誤，不回傳空列表（避免與「存在但無推斷記錄」混淆）

### 3.2 推斷準確率聚合查詢

**能回答的問題：**「最近一週的推斷準確率如何？哪些 entity type 最常被錯誤推斷？reject reason 分布是什麼？」

**查詢輸入：**
- 時間範圍（必填，或預設最近 7 天）
- entity_type（optional，過濾特定 entity type）
- algorithm_version（optional，過濾特定算法版本）

**查詢輸出：**
- 總推斷次數
- confirm 次數、confirm rate（百分比）
- reject 次數、reject rate（百分比）
- pending（尚未有 human verdict）次數
- rejection reason 分布（各 category 的數量和比例）
- 按 entity type 分組的 confirm rate（讓工程師知道哪個 entity type 推斷最不準確）

**Acceptance Criteria：**
- Given 指定時間範圍，When 執行準確率查詢，Then 回傳上述所有欄位
- Given 工程師查看結果，Then 能回答「最近一週推斷準確率是 X%，最常見的錯誤類型是 Y，問題最多的 entity type 是 Z」

### 3.3 Eval Dataset 匯出

**能回答的問題：**「我要跑新版 prompt 的 batch evaluation，需要一批有 human verdict 的歷史推斷資料。」

**查詢輸入（過濾條件）：**
- 時間範圍
- verdict 類型（confirm only / reject only / all）
- entity_type
- algorithm_version

**匯出格式，每筆記錄包含：**
- `input`：本次推斷的輸入快照（entity 狀態 + 觸發事件摘要）
- `llm_output`：LLM 的原始輸出
- `human_verdict`：confirm / reject
- `rejection_reason`：如果 reject，包含 category 和 detail
- `algorithm_version`：哪個版本的算法產出這個結果

**Acceptance Criteria：**
- Given 工程師指定過濾條件，When 執行匯出，Then 返回符合條件的 eval dataset，每筆包含上述欄位
- Given 匯出的 dataset，Then 工程師能直接用它對新 prompt 跑 batch evaluation，比較 predicted verdict 和 human verdict，不需要額外的資料轉換

---

## 第四章：Dashboard 治理儀表板

Dashboard 需要新增「治理品質」視圖，讓 Partner 管理員和工程師能直接在 UI 看到推斷健康度。

### 4.1 需要可視化的指標

**推斷準確率趨勢（折線圖）：**
- x 軸：時間（最近 30 天）
- y 軸：confirm rate（百分比）
- 目的：讓工程師能看出算法變更是否讓準確率改善或退步
- 每個點代表一天的統計（或一次 analyze 快照）

**Rejection Reason 分布（長條圖）：**
- 目前 pending 的 rejection 和歷史 rejection 的 category 分布
- 讓工程師一眼看出目前最常見的推斷錯誤類型
- 五個 category：wrong_semantic / wrong_granularity / missing_impacts / factually_incorrect / other

**Entity Type 推斷健康度（排行表）：**
- 各 entity type 的 confirm rate 排列
- 讓工程師知道哪個 entity type 最需要改進 prompt

**Confirm Backlog（數字 + 分組）：**
- 目前有多少推斷結果等待 human verdict
- 按滯留天數分組：< 1 天 / 1-3 天 / > 3 天

### 4.2 治理健康度的定義

| 狀態 | 條件 |
|------|------|
| 健康（綠）| 7 日 confirm rate >= 80%，backlog 筆數 < 10，無連續 3 日 reject rate 上升 |
| 注意（黃）| 7 日 confirm rate 60%-79%，或 backlog 10-30 筆，或連續 2 日 reject rate 上升 |
| 警告（紅）| 7 日 confirm rate < 60%，或 backlog > 30 筆，或出現 3 筆以上 factually_incorrect reject |

**Acceptance Criteria：**
- Given 工程師打開治理儀表板，When 頁面載入完成，Then 能在 5 秒內看到當前治理健康度狀態（綠/黃/紅）
- Given 治理健康度為紅，When 工程師點擊狀態，Then 能看到觸發紅燈的具體指標
- Given 推斷準確率趨勢圖，When 工程師 hover 某一天，Then 能看到該天的 confirm/reject 數量明細
- Given quality score 低於 70，Then 頁面有醒目顏色標示（不用 emoji，用顏色區分）

### 4.3 LLM 費用可觀測性整合

將現有 Firestore 中的 `usage_logs` 整合進治理儀表板，讓工程師能同時看到「推斷品質」和「推斷成本」。

**Acceptance Criteria：**
- Given 工程師查看治理儀表板，When 切換到費用 tab，Then 能看到過去 30 天按 `feature` 分組的 token 用量
- Given 工程師查看某次 infer_all 的推斷記錄，When 查看詳情，Then 能看到該次推斷消耗的 tokens_in / tokens_out（需要 audit event 和 usage_log 能 join）

---

## 第五章：演算法迭代支援

這一章定義讓工程師能夠有系統地迭代治理演算法的機制。

### 5.1 Algorithm Version 標記

**為什麼需要：** 工程師改了 prompt 或治理邏輯後，需要能比較「新版本和舊版本在相同類型輸入上的推斷品質差異」。如果推斷記錄沒有版本標記，就無法做這個比較。

**定義：** `algorithm_version` 是一個版本標識，標記「這批推斷是用哪個版本的 prompt 和邏輯產出的」。每次 infer_all 都必須帶上這個標記，讓歷史紀錄可以按版本過濾。

**Acceptance Criteria：**
- Given 每一筆 `governance.infer_all.success` 或 `governance.infer_all.error` event，Then 必須包含 `algorithm_version` 欄位
- Given 工程師查詢某個時間範圍的推斷結果，When 按 `algorithm_version` 過濾，Then 能只看到特定版本的推斷記錄
- Given 工程師比較兩個算法版本的準確率，When 分別查詢 v1 和 v2 的 confirm rate，Then 能得到可比較的數字

### 5.2 Prompt Regression Detection

**為什麼需要：** 治理演算法更新後，工程師需要能偵測「新版本是否讓歷史上表現良好的 entity type 的準確率下降了」。

**定義：** Regression 的判斷標準是：新 algorithm_version 在某個 entity type 上的 reject rate，比舊版本高出超過 20 個百分點（且樣本數量 >= 10 筆才有效）。

**能回答的問題：**「新版本和舊版本相比，在相同 entity type 上的推斷準確率差異是什麼？新版本出現了哪些舊版本沒有的 rejection reason 類型？」

**Acceptance Criteria：**
- Given 工程師指定兩個 algorithm_version，When 執行版本比較查詢，Then 能看到各 entity type 的 confirm rate 差異，以及新版本出現的新 rejection reason 類型（在舊版本中不存在的失敗模式）
- Given 新版本的某個 entity type reject rate 比舊版本高 20% 以上（且樣本 >= 10），Then 這個 entity type 會在比較結果中被標記為 regression

### 5.3 如何用歷史資料做 Eval

**流程定義（從工程師視角）：**

1. 從歷史推斷中匯出 eval dataset（第三章 3.3 的匯出功能）
2. 過濾出有 human verdict 的記錄（已 confirm 或已 reject 的）
3. 對每筆記錄，用新版 prompt 對原始 input 跑推斷
4. 比較新 prompt 的 predicted verdict 和 human verdict 的一致率
5. 如果一致率高於舊版本，代表新 prompt 在這批 eval set 上表現更好

這個 eval 流程本身由工程師手動執行，ZenOS 只需要提供「結構化可匯出的 eval dataset」（已在第三章 3.3 定義）和「version 比較查詢」（已在 5.2 定義）。

**ZenOS 需要支援的部分（不包含自動化 eval runner）：**
- eval dataset 匯出（3.3）
- algorithm_version 標記讓版本可比較（5.1）
- 版本間的 confirm rate 差異查詢（5.2）

---

## 明確不包含

- **即時告警（Alerting）**：不包含 Slack / email 通知、PagerDuty 整合等。告警機制另立 spec。
- **自動化 Prompt 改進**：不包含「系統自動根據 rejection pattern 更新 prompt」。這是算法工程工作，由工程師手動完成。
- **跨 Partner 比較**：每個 partner 只能看自己的推斷歷史和準確率，不做跨 partner 的 benchmark 比較。
- **LLM 費用告警**：不包含費用超過閾值的告警，只包含費用可見性。
- **Partner 看到推斷 diff 明細**：Partner 管理員只看到 confirm backlog 和整體健康度，不看到 LLM 的原始輸入/輸出和推斷 diff。這些原始資料只給工程師。
- **重新設計現有 Cloud Logging 結構**：只在現有 JSON 結構中補充欄位，不改變 log sink 和格式基礎。

---

## 技術約束（給 Architect 參考）

- **Cloud Logging 是 AUDIT_LOG 的唯一 sink**：現有架構的 AUDIT_LOG 寫入 Cloud Logging（textPayload 格式），新增的 event type 必須相容現有格式，不能改變 sink。

- **LLM Usage Logs 在 Firestore**：`partners/{partnerId}/usage_logs` 已有結構（timestamp / feature / model / tokens_in / tokens_out / partner_id）。Dashboard 的費用整合需要 join AUDIT_LOG 和 Firestore usage_logs，Architect 需要決定這個 join 在哪一層做。

- **推斷歷史的持久化**：before/after diff、input_snapshot_ref、algorithm_version、rejection_reason 這些資料目前沒有 persistence。Architect 需要決定是擴充 Cloud Logging 的 JSON 結構、還是另開一個 Firestore collection 做 inference_history。PM 只要求資料必須持久化且可查詢，不規定存在哪裡。

- **Eval Dataset 的格式**：PM 要求匯出包含 input + llm_output + human_verdict + algorithm_version，但不規定是 JSONL、CSV 還是 API response。由 Architect 決定。

- **查詢介面的暴露方式**：第三章的推斷歷史查詢（3.1）和準確率聚合（3.2）需要讓工程師能呼叫（透過 MCP 或 admin API）。是在 `analyze` 的新 check_type、還是開新 MCP tool、還是 admin API endpoint，由 Architect 決定。

- **Rejection Reason 的 UI 流程**：目前 confirm/reject 操作在 `mcp__zenos__confirm` tool 中進行。2.5 要求 reject 時選擇 reason category，Architect 需要評估是在 MCP tool 新增參數、還是在 Dashboard 上做 reject 流程。

---

## 開放問題

1. **Input Snapshot 的儲存範圍**：每次 infer_all 的 input snapshot 可能很大（partner 的所有 entity 狀態）。是要存完整快照、只存 diff、還是只存 entity ID list + 指向 Firestore 的 reference？這個 trade-off 需要 Architect 評估儲存成本後決定。

2. **Algorithm Version 的語意和管理方式**：工程師更新 prompt 時，algorithm_version 應該怎麼指定？是 git commit hash、還是手動維護的語意化版本號（v1.2.3）、還是兩者都記？PM 沒有強偏好，但需要 Architect 給出一個方案讓工程師能遵循。

3. **KPI 快照的觸發頻率**：Dashboard 的推斷準確率趨勢圖需要歷史資料。如果只在 agent 呼叫 `analyze` 時才寫快照，資料可能過於稀疏。是否需要排程定期觸發快照？

4. **Dashboard 治理頁面的位置**：是作為獨立頁面（/governance），還是整合在現有頁面的分頁？待 UX 確認。

5. **Cloud Logging 查詢權限**：Cloud Run 的 service account 是否已有讀取 Cloud Logging 的 IAM 權限？如果沒有，讀取 audit log 歷史的路徑需要重新評估（改從 Firestore 的 usage_logs 做）。

---

## Done Criteria

以下所有項目完成才算這個 feature 交付：

### AUDIT_LOG 增強
- [ ] 成功的 infer_all 有 `governance.infer_all.success` event，包含 algorithm_version、entities_changed、inference_diff（before/after）、input_snapshot_ref
- [ ] 跳過的 infer_all 有 `governance.infer_all.skip` event，包含 skip_reason
- [ ] LLM 推斷失敗的 error event 包含 error_type、input_context（含 entity_ids、model）、raw_llm_output（如有）
- [ ] 所有 entity upsert（算法或人工觸發）的 changes 欄位包含 before/after 格式

### Rejection Reason 結構化
- [ ] reject 操作必須選擇 reject_reason_category（wrong_semantic / wrong_granularity / missing_impacts / factually_incorrect / other）
- [ ] 歷史 reject 記錄可以按 category 聚合查詢

### 推斷歷史查詢
- [ ] 能查詢指定 entity 的完整推斷歷史（時間戳、diff、input_snapshot_ref、verdict、rejection_reason、algorithm_version）
- [ ] 能查詢指定時間範圍和 entity type 的推斷準確率聚合數據
- [ ] 能按 algorithm_version 過濾查詢結果

### Eval Dataset
- [ ] 能匯出包含 input + llm_output + human_verdict + rejection_reason + algorithm_version 的 eval dataset
- [ ] 匯出結果能直接用於 batch evaluation，不需要額外轉換

### Dashboard
- [ ] 治理健康度狀態（綠/黃/紅）在 Dashboard 可見，定義符合第四章 4.2 的門檻
- [ ] 推斷準確率 30 日趨勢折線圖
- [ ] Rejection reason 分布圖（五個 category）
- [ ] Confirm backlog 按滯留天數分組
- [ ] LLM 費用 tab（按 feature 分組的 token 用量）

### 算法迭代支援
- [ ] 每次 infer_all 帶有 algorithm_version 標記
- [ ] 能比較兩個 algorithm_version 在各 entity type 上的 confirm rate 差異
- [ ] 能識別新版本出現的新 rejection reason 類型（regression detection）

---

## 第八章：Server 端 LLM 依賴健檢（2026-04-17 新增 — ADR-039）

### 8.1 背景

2026-04-10 起 Gemini API 故障 7 天期間，觀察到 L3 document bundle 路徑部分退化。回溯發現 server 端有隱式 LLM 依賴進入 bundle 主路徑，違反 `SPEC-document-bundle` 的「明確不包含」規範。本章定義持續性的 server 端 LLM 依賴健檢機制，避免類似問題再次發生。

### 8.2 `analyze(check_type="llm_health")` 新增 check

#### 輸入與輸出

```
analyze(check_type="llm_health")
  → data: {
      check_type: "llm_health",
      provider_status: [
        { name: "gemini", status: "healthy" | "degraded" | "down", last_success_at, error_rate_1h }
      ],
      dependency_points: [
        {
          location: "src/zenos/...",
          path_category: "critical" | "non_critical" | "optional_enrichment",
          purpose: "L2 三問語意閘" | "bundle_highlights" | ...,
          compliant: bool,
          notes: "..."
        }
      ],
      findings: [
        {
          severity: "red" | "yellow" | "green",
          type: "critical_path_llm_dependency" | "deprecated_dependency" | ...,
          location,
          description
        }
      ]
    }
```

#### 白名單（ADR-039 D5）

以下 server 端 LLM 依賴點列為合法，不觸發 red finding：

1. L2 三問判斷的語意閘（Flash Lite），故障時 degrade 為接受 caller 的 boolean
2. Quality Intelligence 付費層的 summary 腐化偵測，故障時跳過該項
3. 標示為 `optional_enrichment` 且有 fallback 的 LLM 輔助 call

### 8.3 關鍵路徑硬規則

server 端以下路徑**禁止**任何 LLM 依賴（即使宣稱有 fallback）：

- `write(collection="documents")` 主路徑（create / add_source / update_source / remove_source）
- `write(collection="entities")` 主路徑
- `task(action=*)` 主路徑
- `confirm` 主路徑
- `governance_guide` 主路徑
- `read_source` 主路徑
- `batch_update_sources` 主路徑

違反以上硬規則 → `analyze(check_type="llm_health")` 回 severity=red finding。

### 8.4 Acceptance Criteria

- `AC-obs8-1` Given server 在 `write(add_source)` code path 中有 LLM call，When `analyze(check_type="llm_health")` 執行，Then 回傳 severity=red finding 指出該 location
- `AC-obs8-2` Given 所有 LLM provider 全部故障，When agent 執行 `write(collection="documents")`，Then write 成功（不受 LLM 依賴阻擋），且 `governance_hints.health_signal` 含 `llm_providers_down=true` warning
- `AC-obs8-3` Given L2 三問語意閘的 LLM call 失敗，When entity write 執行，Then degrade 為接受 caller 傳入的 boolean，write 成功
- `AC-obs8-4` Given `analyze(check_type="llm_health")` 回傳 dependency_points，Then 每個 point 的 `path_category` 為 `critical`/`non_critical`/`optional_enrichment` 三者之一，無其他值
- `AC-obs8-5` Given Gemini 恢復正常，Then `analyze(check_type="llm_health")` 的 `provider_status` 反映健康狀態變化，不需重啟 server

### 8.5 完成定義

- [ ] `analyze(check_type="llm_health")` 已實作
- [ ] CI 中有 smoke test：模擬所有 LLM provider down 時，`write(documents)` / `write(entities)` / `task(create)` 仍成功
- [ ] Dashboard 顯示 provider_status 與 dependency_points 數量
- [ ] 至少一次實際執行回報 0 red findings

### 8.6 Health 聚合補充

`compute_health_signal()` / `analyze(check_type="health")` 應聚合治理相關衍生訊號，不只限於基礎 ontology KPI：

- `llm_health`：server 端 LLM provider 與 dependency health
- `governance_ssot`：spec ↔ server rules ↔ reference skills 的 SSOT 漂移
- `bundle_highlights_coverage`：已有 highlights 的 index doc 數 / 所有 index doc 數

其中：

- `bundle_highlights_coverage` 門檻沿用 `SPEC-document-bundle`：
  - `>= 80%` → green
  - `50% ~ 80%` → yellow
  - `< 50%` → red
- `governance_ssot` 若有 red drift finding，`health_signal.overall_level` 必須至少為 red
- `analyze(check_type="all")` 的平面 `kpis` 輸出也必須帶 `bundle_highlights_coverage`
