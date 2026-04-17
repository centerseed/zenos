---
type: SPEC
id: SPEC-cowork-knowledge-context
doc_id: SPEC-cowork-knowledge-context
title: Feature Spec: Web Cowork 活用知識圖譜的欄位級漸進預填
status: draft
version: "0.1"
date: 2026-04-17
supersedes: null
l2_entity: TBD
created: 2026-04-17
updated: 2026-04-17
---

# Feature Spec: Web Cowork 活用知識圖譜的欄位級漸進預填

## 背景與動機

ZenOS 的核心定位是「AI Context Layer」——一次建 ontology，所有 AI agent 共享同一份 context。這個定位在 Claude Code CLI 已經成立：CLI 透過 MCP tools 天然能讀知識圖譜，agent 一進場就具備產品/模組/文件的完整脈絡。

但 Web UI 這一側的 cowork（SPEC-marketing-automation 的「討論這段」、SPEC-crm-intelligence 的「準備下次會議」）目前只做到**對話橋接**——使用者在 Web 打字，helper 呼叫本機 Claude CLI 回覆。**圖譜資料並沒有被自動注入對話 context**，導致 Web 上的 AI 在關鍵欄位上往往「泛談」而非「引用具體產品現況」。

這造成兩個具體痛點：

1. **行銷策略設定跑不起來**：使用者（包含 dogfood 的 Paceriz 負責人）面對 7 個策略欄位（受眾、品牌語氣、核心訊息、平台、頻率、內容比例、CTA）無從下手；即使按「討論這段」，AI 沒有自動讀圖譜，只能反問使用者「你的產品是什麼？」這讓 cowork 淪為「解釋產品」而不是「討論策略」。
2. **CRM Briefing 的產品現況區塊空泛**：SPEC-crm-intelligence 的 briefing context pack 已列出「產品現況」區塊要從 ontology 拉取，但沒有定義讀到哪一層、遍歷幾跳——實作上容易退化成只讀 L1 product entity 的 summary。

**核心觀察（跨模組共通）**：這個 flow 的底層邏輯在行銷、CRM、未來其他模組都一樣——「討論某個欄位/情境 → helper 沿 seed entity 讀圖 → 漸進式預填欄位」。只有最後套用到哪個 UI 欄位、用什麼 prompt 不同。本 spec 抽出這個共通 flow 為獨立需求，行銷與 CRM 模組各自引用。

---

## 目標用戶

| 角色 | 場景 | 頻率 |
|------|------|------|
| **行銷負責人**（Paceriz dogfood） | 在 Dashboard 新建行銷項目，按「討論策略」希望 AI 讀完產品圖譜後給出策略草案，再逐項確認 | 每個新項目 1 次 |
| **業務人員**（CRM） | 在 Deal 詳情頁按「準備下次會議」希望 briefing 的「產品現況」直接引用該公司關心的具體功能 | 每次會議前 |
| **未來其他模組使用者** | 任何需要「欄位級 AI 預填」的介面，都能套同一套 flow | — |

**關鍵假設**

- 使用者已在本機完成 Claude Code 登入，Local Helper 可運行（SPEC-marketing-automation 的 ADR-034 架構已成立）
- 使用者的 ZenOS ontology 至少有 L1 product entity；豐富度視 dogfood 進度不同
- Demo 場景鎖定 Paceriz，其 ontology 已有多個 L2 active entity，足以驗證 2 跳遍歷

---

## Spec 相容性

已比對的既有 spec：

| 文件 | 關係 | 處理 |
|------|------|------|
| **SPEC-marketing-automation** | 擴充 | 已定義 Context Pack 結構（field_id / field_value / project_summary / current_phase / suggested_skill / related_context）。本 spec 新增 `graph_context` 為 Context Pack 的一級欄位，不破壞既有結構。策略設定需求引用本 spec 的 AC |
| **SPEC-crm-intelligence** | 擴充 | Briefing context pack 已列出「產品現況」「累積洞察」「相似案例」等需 ontology 的區塊。本 spec 定義這些區塊如何沿圖遍歷取得，briefing AC 引用本 spec 的 AC |
| **ADR-034 Web Cowork Local Helper Bridge** | 銜接擴充 | 現行 helper 已透過 `--mcp-config` 載入 ZenOS MCP 並有 capability probe（`mcp_ok`）。本 spec 進一步要求「在首輪對話前主動執行圖遍歷並把結果注入 context pack」，而不是只在使用者主動詢問時才讓 AI 叫 MCP tool |
| **SPEC-knowledge-graph-semantic** | 部分依賴 / 部分脫鉤 | 該 spec 的「影響鏈遍歷 API」（P0.2）是本 spec 技術上的理想依賴。但該 spec 的「關聯語意動詞」（P0.1、P1.4、P1.5）**不在本 spec 範圍**——本 demo 使用階層 + tags（what/why/who）即可達成預填目的。若 verb 後續落地，`graph_context` 的 neighbor 結構可加 `relation_verb` 欄位升級，不需改本 spec 語意 |
| **SPEC-zenos-core** | 無衝突 | 屬 Application Layer 的 UX 行為，不改 Core |
| **SPEC-product-vision** | 無衝突，強化 | 這是「AI Context Layer」價值在 Web UI 的具體兌現 |

**無需處理的衝突**：經查，沒有其他既有 spec 對「Web cowork 的圖遍歷」做過不同定義。

---

## 需求

### P0（必須有）

#### Web Helper 具備知識圖譜讀取能力

- **描述**：使用者在 Web UI 觸發的任何 cowork 對話，helper 啟動的 Claude CLI session 都必須具備與 Claude Code CLI 對等的 ZenOS MCP 讀取能力。當對話帶有 seed entity（例如「行銷項目所屬產品」或「CRM Deal 所屬公司/產品」），helper 必須在首輪 AI 回覆前主動沿圖遍歷一次，把結果注入 context pack，而不是被動等待 AI 決定要不要叫 MCP tool
- **Acceptance Criteria**：
  - `AC-CKC-01`: Given 使用者在 Web UI 按任一「討論 XX」按鈕觸發 cowork 對話，When helper 初始化 Claude CLI session，Then MCP config 必須指向 ZenOS server，且 `mcp__zenos__search` / `mcp__zenos__get` 工具可用（等同 Claude Code CLI 的 MCP 能力）
  - `AC-CKC-02`: Given 觸發 cowork 的 UI 入口帶有 `seed_entity`（entity name 或 entity id），When cowork orchestrator（前端 + helper 共同子系統）啟動對話，Then 必須在送出首輪 prompt **之前**完成圖遍歷（實作上由前端先呼叫 Dashboard API `/api/cowork/graph-context` 取得結果），把 `graph_context` 以 inline block 嵌入 prompt 送往 helper；使用者可觀察結果為「首輪 AI 回覆前，已讀取清單即可見」
  - `AC-CKC-03`: Given 觸發 cowork 的 UI 入口 **沒有** seed entity（例如通用自由對話），When helper 啟動 session，Then 不執行主動圖遍歷，`graph_context` 欄位為 null，helper 其他能力（MCP tool 依然可用）不受影響
  - `AC-CKC-04`: Given helper capability probe 回報 `mcp_ok=false`，When 使用者觸發帶 seed entity 的 cowork，Then helper 不執行圖遍歷，在 SSE 串流中回傳 `graph_context_unavailable` 事件，UI 顯示「知識圖譜暫時無法讀取，AI 將以對話內容為準」，對話仍可繼續
  - `AC-CKC-05`: Given 圖遍歷過程中任一 MCP 呼叫失敗或超時（預設 10 秒），When helper 完成部分遍歷，Then helper 把已取得的節點塞進 `graph_context`，並在該欄位附 `partial=true` 與錯誤摘要；不得因為遍歷失敗讓整個 cowork session 失敗

#### 欄位級圖遍歷

- **描述**：針對帶有 seed entity 的 cowork，helper 依固定規則沿圖抓取 2 跳鄰居與對應 L3 文件摘要，封裝為 `graph_context`，注入 context pack
- **遍歷規則**：
  - **起點**：seed entity（由前端從 UI 情境提供，例如行銷項目所屬產品、Deal 所屬公司/產品）
  - **深度**：預設 2 跳。第 1 跳抓直接 L2 鄰居；第 2 跳抓每個 L2 鄰居底下掛的 L3 文件（type = SPEC / DECISION / DESIGN / REFERENCE 等）metadata + summary，**不取全文**
  - **篩選**：只取 `status in (active, approved, current)` 的節點；draft / archived / superseded 不納入
  - **排序**：L2 鄰居依 `updated_at` 倒序；L3 文件依 `updated_at` 倒序
  - **節點數上限**：第 1 跳最多 10 個 L2；第 2 跳每個 L2 最多 3 個 L3，全局上限 20 個 L3
  - **Token budget**：`graph_context` 序列化後預估 ≤ 1500 tokens。超出時先裁 L3 摘要，再裁 L3 數量，最後裁 L2；每次裁切後 `graph_context.truncated=true`
- **Acceptance Criteria**：
  - `AC-CKC-10`: Given seed entity 為 Paceriz（L1 product）且其 ontology 有 3+ active L2 模組，When helper 執行遍歷，Then `graph_context.neighbors` 至少包含該 3 個 L2 模組的 `id / name / type / level / tags(what/why/who) / summary / updated_at`
  - `AC-CKC-11`: Given 某個 L2 鄰居底下掛有 1+ 個 status=approved 的 L3 SPEC，When helper 執行第 2 跳遍歷，Then 該 L2 的 `documents` 清單至少包含該 SPEC 的 `doc_id / title / type / status` 和不超過 500 字的 summary（**不含全文**）
  - `AC-CKC-12`: Given seed entity 有 status=draft 或 archived 的鄰居，When helper 遍歷，Then 這些鄰居不出現在 `graph_context.neighbors`
  - `AC-CKC-13`: Given 遍歷結果超過 token budget，When helper 封裝 context pack，Then 執行上述裁切策略，並設 `graph_context.truncated=true` 記錄被裁項目數
  - `AC-CKC-14`: Given 遍歷完成，When helper 發出首輪 SSE 事件，Then 必須包含一個 `graph_context_loaded` 事件，payload 含節點數（`l2_count`、`l3_count`）和是否 truncated；前端可據此更新 UI
  - `AC-CKC-15`: Given 兩次相鄰的 cowork 對話針對同一 seed entity 且間隔 < 60 秒，When helper 執行遍歷，Then 可使用本機 cache（同 session 內生效即可，不需跨 session 持久化），避免重複 MCP 呼叫

#### 圖 Context 透明度（可展開清單）

- **描述**：對話視窗頂部顯示「已讀取 N 個節點 ▸」，預設收合；點開後顯示階層結構的節點清單與其 tags，讓使用者看到 AI 實際讀到哪些知識
- **Acceptance Criteria**：
  - `AC-CKC-20`: Given `graph_context` 已成功載入，When 對話視窗渲染首輪 AI 回覆，Then 視窗頂部必須顯示可展開區塊，摘要文字為「已讀取 {l2_count} 個模組、{l3_count} 個文件 ▸」，預設收合
  - `AC-CKC-21`: Given 使用者點開「已讀取」區塊，When 展開內容，Then 顯示階層結構：seed entity → 直接 L2 鄰居（附 name + type + 簡短 tags 摘要）→ 每個 L2 下的 L3 文件（附 title + type + status）；不顯示 MCP 原始 response JSON
  - `AC-CKC-22`: Given `graph_context.truncated=true`，When 使用者展開，Then 在清單底部顯示「還有 N 個節點因長度限制未載入」提示
  - `AC-CKC-23`: Given `graph_context` 未載入（seed entity 缺失 / mcp_ok=false / 遍歷全失敗），When 視窗渲染，Then 「已讀取」區塊不顯示；若是因 mcp_ok=false 不可用，改顯示 AC-CKC-04 定義的降級提示

#### 漸進式欄位預填

- **描述**：AI 以 seed entity 的 `graph_context` 為依據，先主動預填「從圖譜可推」的欄位給使用者確認；對於「圖譜無依據」的欄位，AI 在後續輪次中逐個追問，每輪一題，使用者回應後 AI 接著追問下一題。全部欄位補齊後，AI 整理出最終結構化摘要，使用者按「套用到欄位」一次寫回對應 UI
- **欄位分類（由調用此 flow 的模組自己定義）**：
  - 每個調用模組必須在觸發 cowork 時於 context pack 指定 `target_fields`（陣列），每個 field 標註 `source_preference`（`graph_derivable` / `user_required` / `mixed`）
  - `graph_derivable`：AI 優先從 `graph_context` 推出草案
  - `user_required`：AI 不自作預設值，透過追問取得
  - `mixed`：AI 可提候選值但必須請使用者確認
- **Acceptance Criteria**：
  - `AC-CKC-30`: Given context pack 含 `target_fields` 且其中 1+ 個標記為 `graph_derivable`，When AI 產出首輪回覆，Then 首輪必須包含針對每個 `graph_derivable` 欄位的草案，且草案文字必須**明確引用** `graph_context` 中的至少一個節點（例如「根據你 ontology 的『Rizo AI 教練』L2 模組，建議品牌語氣：有原則的專業」）
  - `AC-CKC-31`: Given `graph_derivable` 欄位的草案無依據可引用（graph_context 為空 / 僅 L1 fallback），When AI 產出首輪回覆，Then 草案必須標明「僅基於 L1 summary 推估」或「缺少依據，請提供」，**不得捏造**引用
  - `AC-CKC-32`: Given 首輪已給 `graph_derivable` 欄位草案，When 使用者回應（確認 / 修改），Then AI 下一輪**一次只追問一個** `user_required` 欄位；每輪對話最多處理一個欄位，避免一次丟 3+ 個問題讓使用者失焦
  - `AC-CKC-33`: Given 使用者略過某輪追問（例如回「先跳過」），When AI 收到回應，Then AI 把該欄位標記為 pending、繼續問下一個，最後整理摘要時明確列出 pending 欄位
  - `AC-CKC-34`: Given 所有 target_fields 都已獲得使用者確認或明確 pending，When 使用者自然語言觸發整理（「就這樣」「確定」）或按「整理結果」按鈕，Then AI 輸出符合 SPEC-marketing-automation「回寫契約」格式的結構化摘要（`target_field` + `value`），供前端套用
  - `AC-CKC-35`: Given 漸進對話進行中，When 對話輪數達到 10 輪（統一上限，取代 SPEC-marketing-automation 原 8 輪與 SPEC-crm-intelligence briefing 原 8 輪），Then 系統提示「達到對話上限，請整理當前結果或開啟新 session」，不得強制截斷對話

#### L1-only Fallback

- **描述**：若 seed entity 只有 L1、沒有（或只有 1 個）可用的 L2 鄰居，helper 仍必須產出可用的 context pack；AI 以 L1 entity 的 tags（what / why / who）為最低依據提出草案，同時在回覆中**明確提示**使用者該產品的 ontology 還不夠豐富，建議去補 L2，但**不強迫**使用者中斷當前流程
- **Acceptance Criteria**：
  - `AC-CKC-40`: Given seed entity 是 L1 product 且圖遍歷回傳 0~1 個 active L2 鄰居，When helper 產出 `graph_context`，Then `graph_context.fallback_mode = "l1_tags_only"`，neighbors 為空或僅 1 筆，但 L1 自身的 tags 必須完整填入 `graph_context.seed`
  - `AC-CKC-41`: Given `fallback_mode = "l1_tags_only"`，When AI 產出首輪回覆，Then 回覆中必須包含一句明確提示：「你的 {產品名} 目前只有基本產品資訊，建議先補齊 L2 模組讓我能給更精準的建議；以下草案僅基於產品 tags」
  - `AC-CKC-42`: Given `fallback_mode = "l1_tags_only"`，When 使用者選擇繼續，Then 對話仍完整走完漸進預填流程（不因 fallback 提前結束），最終結構化摘要標記 `confidence = "low"`

### P1（應該有）

#### CRM Briefing 引用本 flow

- **描述**：SPEC-crm-intelligence 的「AI Briefing」對話式面板中，「產品現況」與「相似案例」區塊的 context pack 組裝，統一走本 spec 的圖遍歷 flow。seed entity 為該 deal 所連結的公司/產品 entity
- **Acceptance Criteria**：
  - `AC-CKC-50`: Given 使用者在 Deal 詳情頁按「準備下次會議」，When briefing context pack 被組裝，Then 其中的「產品現況」區塊資料來源為本 spec 定義的 `graph_context`（seed = 該 deal 所屬公司或關聯產品 entity），而不是由 CRM skill 自行組不同格式
  - `AC-CKC-51`: Given briefing 面板載入，When 首輪 briefing 顯示，Then 產品現況區塊必須引用 `graph_context` 中的具體 L2 模組 / L3 文件，且 UI 顯示「已讀取」可展開清單（見 AC-CKC-20~23）

#### 行銷策略設定引用本 flow

- **描述**：SPEC-marketing-automation 的「欄位級一鍵開聊」在「策略」欄位按「討論這段」時，context pack 組裝走本 spec。seed entity 為該行銷項目所屬產品 entity；target_fields 為 7 個策略欄位並標註 source_preference
- **Acceptance Criteria**：
  - `AC-CKC-55`: Given 使用者在行銷項目的策略區塊按「討論這段」，When cowork 啟動，Then context pack `seed_entity` = 該項目的產品 entity，`target_fields` 列出 7 個策略欄位，標註：受眾/品牌語氣/核心訊息 = `graph_derivable`；平台/頻率/內容比例/CTA = `user_required`
  - `AC-CKC-56`: Given seed entity 為 Paceriz（已知 ontology 豐富），When 使用者走完漸進式預填並按「套用到欄位」，Then 7 個策略欄位全部有值或有明確 pending 標記，且寫回 ZenOS 的 strategy document + entry 中至少 3 個欄位可追溯到 `graph_context` 的具體節點引用

#### Demo 驗收（Paceriz 端到端）

- **描述**：以 Paceriz 的「官網 Blog」行銷項目為 dogfood 驗收場景，端到端跑完策略設定流程並錄製 demo
- **Acceptance Criteria**：
  - `AC-CKC-60`: Given Paceriz「官網 Blog」行銷項目已建立、策略欄位全部為空，When 使用者按「討論策略」，Then 10 秒內對話視窗開啟並顯示首輪 AI 回覆 + 「已讀取」可展開清單含至少 3 個 L2 模組
  - `AC-CKC-61`: Given 使用者依 AI 追問逐輪回覆，When 完成漸進對話，Then 10 分鐘內可完成 7 個策略欄位的討論（包含 3 個 graph_derivable + 4 個 user_required）
  - `AC-CKC-62`: Given 對話結束使用者按「套用到欄位」，When 前端寫回 ZenOS，Then Dashboard 行銷項目的策略區塊顯示 7 個欄位完整值，且刷新後資料仍在（ZenOS 已持久化）
  - `AC-CKC-63`: Given Demo 錄製完成，When 交付 demo 影片，Then 影片必須清楚展示：(a) 「已讀取」清單展開後看到 Paceriz 的真實 L2 模組（Rizo AI 教練 / 付費分級系統等），(b) AI 草案引用 L2 節點的具體內容（不是通泛話），(c) 漸進追問一次一題，(d) 套用後 ZenOS 刷新有資料
  - `AC-CKC-64`: Given Demo 驗收，When 切換到一個 ontology 只有 L1 的產品（例如「SME 製造業自動化橋樑」）重複流程，Then 對話順利進入 L1-only fallback 模式，首輪回覆包含 AC-CKC-41 定義的提示，漸進對話仍可走完

### P2（可以有）

#### 跨 partner / 跨租戶驗證

- **描述**：除了 Paceriz dogfood 外，選 1 個真實 partner 驗證此 flow 在非 dogfood ontology 上也能運作
- **Acceptance Criteria**：
  - `AC-CKC-70`: Given 選定 1 個非 dogfood partner 的行銷項目，When 使用者觸發策略討論，Then 7 個欄位仍可完成漸進預填且資料可寫回

#### 圖 context 即時同步（ontology 更新回寫）

- **描述**：使用者在 cowork 對話中提到的產品描述若與 ontology 不一致，AI 可主動提議「要不要把這個更新回 ontology」並在使用者同意後寫回
- **Acceptance Criteria**：
  - `AC-CKC-75`: Given 使用者在對話中描述某個產品功能與 `graph_context` 中 L2 summary 有明顯衝突，When AI 偵測到，Then AI 於對話中主動提示並提供「更新到 ontology」按鈕（走既有 `mcp__zenos__write` 路徑）

#### 自動 seed entity 推斷

- **描述**：若 UI 入口未明確指定 seed entity，但 cowork 所在的 context（例如項目詳情頁）有隱含 entity 關聯，helper 可自動推斷
- **Acceptance Criteria**：
  - `AC-CKC-80`: Given UI 入口未傳 seed_entity 但 context pack 含 `project_summary` 且 project 有 ontology_entity_id，When helper 初始化，Then 自動以該 entity 為 seed 執行圖遍歷

---

## 明確不包含

- **不依賴語意動詞（verb）**：`graph_context.neighbors` 結構可預留 `relation_verb` 欄位，但本 spec 的 AC 不使用 verb 做篩選或推理；verb 何時落地由 SPEC-knowledge-graph-semantic 決定，不阻塞本 spec 交付
- **不做影響鏈 API（多跳傳遞式查詢）**：本 spec 只做「seed + 2 跳鄰居」，不做 A → B → C → D 的傳遞查詢。多跳傳遞留給 SPEC-knowledge-graph-semantic 的 P0.2「影響鏈遍歷 API」交付後再評估
- **不做圖譜治理**：若 Paceriz ontology 不夠豐富，是另一條治理線（由 capture / sync skill 處理）；本 spec 只負責「有多少資料做多少事」，不負責「補資料」
- **不做 L3 文件全文載入**：`graph_context` 只載 L3 metadata + 500 字摘要，full content 要由 AI 自行呼叫 `mcp__zenos__read_source`
- **不做跨 partner 圖遍歷**：seed 屬於哪個 partner，遍歷就在該 partner 範圍內
- **不改 ontology 資料模型**：使用現有 entity / relationship / document 結構
- **不取代既有通用 cowork 自由對話入口**：不帶 seed 的通用討論入口保留，helper 行為與現行一致
- **不在 Web 端代理權限確認**：沿用 ADR-034 的白名單 + console fallback 策略，不為本 spec 新增權限模型
- **不做快取跨 session 持久化**：僅同一 cowork session 內快取圖遍歷結果；session 結束即清除

---

## 技術約束（給 Architect 參考）

| 約束 | 原因 |
|------|------|
| Helper 主動執行圖遍歷，不依賴 AI 自己決定是否叫 MCP | 確保首輪回覆就有圖 context；被動模式下 AI 常常不會主動叫 tool |
| `graph_context` 為 context pack 的一級欄位 | 與既有 `field_value` / `project_summary` / `related_context` 同層，便於跨模組復用 |
| L3 只載 metadata + summary，不載全文 | Token budget 控管；full content 留給 AI 需要時自取 |
| Token budget 軟上限 1500，超出裁切 | 避免把 context window 吃滿，留空間給對話歷史 |
| 同 session 圖遍歷結果快取，不跨 session | 避免同一討論內重複叫 MCP；但不需要長期持久化複雜度 |
| 使用現有 `mcp__zenos__search` / `get` / `read_source` 工具 | 不新增 MCP tool，組合既有能力即可（SPEC-marketing-automation 的技術約束同）|
| Helper 遍歷錯誤不得讓整個 cowork session 失敗 | 與 ADR-034 的「降級不中斷」原則一致 |
| `target_fields` 與 `source_preference` 由調用模組提供 | 保持本 spec 跨模組通用性；UI 對應由各模組 spec 負責 |

---

## 已決定的設計決策

| # | 問題 | 決定 | 理由 |
|---|------|------|------|
| 1 | Demo 情境 | Paceriz dogfood 的「官網 Blog」策略設定 | 使用者自己的產品 ontology 最豐富，先驗證 flow；後續其他模組（CRM）引用此 flow 做二級 demo |
| 2 | 圖遍歷深度 | 預設 2 跳（L1 → L2 → L3 metadata） | 1 跳抓不到具體功能/定價細節；2 跳在 token budget 內可覆蓋大多數 dogfood 場景 |
| 3 | 語意動詞（verb） | 不在 scope | verb 先前因「沒用處」被移除，ontology 現況就沒有；若 SPEC-knowledge-graph-semantic 後續把它補回，本 spec 的 neighbor 結構可升級承接 |
| 4 | 欄位預填策略 | 漸進式多輪對話（一次一題） | 一次彈 7 個欄位讓使用者認知負擔大；漸進確認符合現場感，使用者的原話「讓使用者一步一步確認總好過回頭重新設定或自己填」 |
| 5 | 圖 Context 可見性 | 預設收合，可展開 | 讓使用者看到「AI 真的讀了圖」做信任建立，但不佔對話版面 |
| 6 | Fallback 策略 | L1 tags 保底 + 明確提示補 ontology | 永遠有輸出比「因資料不足直接失敗」好；但要誠實告訴使用者為何草案粗糙 |
| 7 | 跨模組抽象層級 | 抽出共通 flow 為獨立 spec，行銷/CRM 引用 | 使用者原話「這個 flow 理論上是跨模組的，底層邏輯都一樣，只是最後 UI 要切不同模組自己的 prompt」；避免每個模組各自刻一份 |
| 8 | Helper 主動 vs 被動讀圖 | 主動：首輪前就遍歷完注入 context pack | 被動模式（讓 AI 自己叫 tool）常常 AI 不主動，首輪回覆品質不穩定；主動預載確保每次首輪都帶 context |
| 9 | Token budget 策略 | 軟上限 1500，裁 L3 > L3 數 > L2 | 優先保留 L2 概念結構，L3 細節可被 AI 後續 on-demand 讀取 |
| 10 | Seed entity 來源 | 由調用模組的 UI 入口明確提供，P2 再做自動推斷 | 顯式優於隱式；P0 不讓「推斷失敗」變 debug 黑洞 |

---

## 開放問題

| # | 問題 | 影響範圍 | 建議 |
|---|------|---------|------|
| 1 | Token budget 1500 是否合適？ | 圖遍歷結果大小 | 待 Architect 壓測實際 MCP 回應大小後調整；或改為 context window 百分比（如 15%）而非絕對值 |
| 2 | 漸進對話輪數上限 12 是否合理？ | 使用者體驗 | 與 SPEC-marketing-automation 現行 8 輪有落差（因本 spec 要補齊 7 欄）；若實測 8 輪夠用，降回 8 輪即可 |
| 3 | L3 summary 500 字上限？ | `graph_context` 大小 | 等 dogfood 資料看實際 SPEC / DECISION 的 summary 長度再微調 |
| 4 | 前端 vs helper 誰組 `graph_context`？ | 實作責任劃分 | 技術決策留給 Architect；PM 立場只要求「graph_context 結果穩定、可被 UI 顯示」 |
| 5 | 多個 seed entity（例如 Deal 同時關聯公司與多個產品）如何處理？ | CRM briefing 場景 | 本 spec P0 預設單 seed；多 seed 留 P1 由 SPEC-crm-intelligence 細化驗收條件 |
