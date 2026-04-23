---
type: SPEC
id: SPEC-governance-feedback-loop
status: Draft
ontology_entity: governance-framework
created: 2026-03-28
updated: 2026-04-23
depends_on: SPEC-ontology-architecture v2 §7, SPEC-task-governance, SPEC-doc-governance, SPEC-governance-framework, SPEC-governance-guide-contract
---

# Feature Spec: 治理品質回饋迴路

> **治理定位：混合（Internal + Agent-Powered Internal）**
> 本 spec 定義的 10 項治理風險與對應機制橫跨內外邊界：
> - **P0-1（分層路由）**：External 規則（三問強制） + Internal 執行（server 端驗證）
> - **P0-2（冷啟��排序）**：Agent-Powered Internal（server 提供品質信號，agent 排序）
> - **P1-1（task→blindspot）**：Agent-Powered Internal（server 提供 task 歷史模式，agent 判斷）
> - **P1-2（impacts 斷鏈）**：Internal（server 圖拓撲分析） + Agent-Powered Internal（agent 建議修復）
> - **P1-3（過時文件）**：Agent-Powered Internal（server 提供矛盾信號，agent 判斷）
> - **P2-1（使用信號）**：Internal（server 追蹤 search_unused）
> - **P2-2（Summary 品質）**：Agent-Powered Internal（server 提供歷史 + 使用數據，agent 評估）
> - **P2-3（規則傳播）**：Internal（自動追蹤）
>
> Agent-Powered Internal 功能透過 `analyze` API 的付費 check_type 暴露全局上下文，由 agent 的大模型執行推理。
> 框架歸屬見 `SPEC-governance-framework` 治理功能索引。

## 第一章：背景與動機

### 問題陳述

ZenOS 治理目前是**單向管線**：規則定義好 → agent 執行 → 結果寫入 ontology。但管線缺少兩個關鍵能力：

1. **寫入時的分層判斷** — agent 把內容寫進 ontology 時，沒有強制觸發「這個東西該放哪一層」的判斷
2. **寫入後的品質回饋** — 品質腐化時，沒有機制能主動偵測並觸發修復

### 觸發這份 spec 的真實案例

#### 案例 A：現有專案的品質腐化（paceriz）

paceriz 是一個中型現有專案，用 `/zenos-capture` 做冷啟動匯入後，agent 反映搜 entity 結果對實際工作沒有幫助：

1. **L2 summary 對外不對內** — summary 寫「這個模組負責排班功能」（行銷語言），但 agent 需要「核心技術挑戰在 SlotDistributionSection 兩階段生成」（開發語言）
2. **缺少 blindspot 記錄** — 模組有已知的 LLM JSON 格式問題，但 ontology 裡沒記錄，agent 反覆踩坑
3. **冷啟動品質天花板** — capture 一次匯入產出的品質只夠用，需要持續校正，但沒有機制觸發校正

#### 案例 B：新知識寫入時的錯誤分層（ERP 整合研究）

agent 承認：如果用戶只說「把這份 ERP 整合研究報告更新到 ZenOS」，agent 會直接 capture，把「ERP 整合研究」建成 L2 entity，把各系統（Oracle、鼎新、正航）各建成子 entity。

但正確分層應該是：
- L2：「ERP Adapter 策略」（公司對外部系統整合的核心方針，有 impacts）
- L3/sources：ERP 整合研究報告、各系統 API 可行性評估

**問題本質**：L2 的三問 + impacts 判斷邏輯存在於 spec 和 skill 裡，但 capture 流程沒有強制觸發這個判斷。只有在用戶主動問「這個適不適合當 L2？」時，分層邏輯才被激活。

### 兩類專案的治理風險差異

| | 現有專案（如 paceriz） | 全新專案 |
|---|---|---|
| **主要風險** | 冷啟動品質不足 + 隨時間腐化 | 寫入時分層錯誤 |
| **典型症狀** | entity 存在但沒用、過時文件沒清理、blindspot 未記錄 | 研究報告被當 L2、技術細節被升太高 |
| **現有防護** | analyze 可抓結構缺陷，但抓不到語意品質 | L2 三問 + impacts gate（server 端），但 capture 沒觸發 |
| **失敗成本** | agent 搜到無用結果 → 失去對 ZenOS 的信任 | ontology 從一開始就退化成文件索引 |

### 現有治理機制盤點

| 機制 | 能偵測什麼 | 不能偵測什麼 |
|------|-----------|-------------|
| `analyze` (quality) | 結構完整性（缺 linked_entities、缺 impacts、doc 數量） | 內容是否對 agent 有用 |
| `analyze` (staleness) | 內容新鮮度（多久沒更新） | 內容過時但沒人改（假新鮮） |
| `analyze` (blindspot) | 推斷可能的知識盲點 | 從 task 失敗信號推斷盲點 |
| L2 三問 + impacts gate | 新建 L2 時的最低品質門檻 | 已 confirmed 的 L2 是否在腐化 |
| document-governance skill | 文件生命週期合規 | 文件內容品質 |
| task-governance skill | 建票品質、驗收閉環 | task 執行中的知識信號是否回饋 |
| capture skill | 知識擷取並寫入 ontology | **分層判斷 — capture 不強制走三問路由** |

### 核心風險一句話

**品質腐化是無聲的，分層錯誤是自動的。** 現有機制確保「新建 L2 時品質達標」（server 端 impacts gate），但無法確保 capture 走正確分層路由，也無法確保品質不隨時間退化。

---

## 第二章：治理風險清單

本章列出 ZenOS 目前已識別的治理品質風險，按「現有專案」和「全新專案」分類，並標注每個風險的現有防護程度。

### 現有專案的風險（冷啟動後的持續治理）

#### R1：L2 Summary 語意腐化
- **描述**：L2 entity 建立時 summary 品質尚可，但隨著專案演進，summary 不再反映最新的核心挑戰與知識重點
- **觸發條件**：專案做了重大重構、核心演算法改變、新增關鍵限制，但 L2 summary 沒跟著更新
- **現有防護**：`analyze (staleness)` 只看更新時間，不看語意是否過時 → **無有效防護**
- **影響**：agent 搜到 entity 但內容過時，做出錯誤判斷或忽略 entity

#### R2：Blindspot 沉默累積
- **描述**：agent 在執行 task 時反覆遇到同一個問題（如 paceriz 的 LLM JSON 格式問題），但這些「已知問題」從未被記錄為 blindspot
- **觸發條件**：task 執行失敗或需要 workaround，但 task 完成後只更新 result，沒有反寫 blindspot
- **現有防護**：`analyze (blindspot)` 只從 ontology 結構推斷盲點，不讀 task 歷史 → **無有效防護**
- **影響**：同一個問題被不同 agent 反覆踩，每次都花時間重新發現

#### R3：過時文件污染搜尋結果
- **描述**：現有專案通常有大量歷史文件，capture 冷啟動時全部匯入。其中許多已過時但仍然活躍在 ontology 中
- **觸發條件**：專案有多次重構歷史、有被棄用但沒標記的設計文件、有不再適用的決策記錄
- **現有防護**：document-governance 定義了 archive/supersede 流程，但依賴人手動執行 → **防護存在但不自動**
- **影響**：agent 搜尋時被過時內容干擾，信噪比低

#### R4：Impacts 路徑斷鏈
- **描述**：L2 的 impacts 關聯在建立時正確，但下游目標已被重構、改名或刪除，impacts 路徑名存實亡
- **觸發條件**：下游 L2 被重構拆分、下游概念被降級或移除
- **現有防護**：`analyze (quality)` 可檢查 impacts 是否存在，但不檢查 impacts 目標是否仍有效 → **部分防護**
- **影響**：知識地圖看起來有連結，但連結指向已失效的概念

#### R5：冷啟動品質天花板
- **描述**：`/zenos-capture` 一次性匯入產出的 L2 品質有上限 — 受限於輸入文件的品質和 LLM 單次推斷的能力
- **觸發條件**：每個現有專案的冷啟動
- **現有防護**：capture 後可手動 review，但沒有機制告訴你「哪些 L2 最需要優先校正」 → **無優先級指引**
- **影響**：冷啟動後所有 L2 看起來品質差不多，但其實有些急需校正、有些已夠用

### 全新專案的風險（從零開始建 ontology）

#### R6：Capture 不走分層路由
- **描述**：agent 收到「把這個內容加進 ZenOS」的指令時，capture 流程直接寫入，沒有強制觸發「這個內容該放 L2 / L3 / sources 的哪一層」的判斷
- **觸發條件**：任何新知識寫入 ontology 的操作
- **現有防護**：L2 三問 + impacts gate 存在於 server 端（confirm 時檢查），但 capture 產出的 L2 停在 draft，不走 confirm → **門檻存在但被繞過**
- **影響**：ontology 從第一天就退化成文件索引，L2 充斥不該是 L2 的內容

#### R7：研究型內容被錯誤升級
- **描述**：技術研究、競品分析、可行性評估等「一次性研究」被直接建成 L2 entity，而不是掛在策略性 L2 的 sources 下
- **觸發條件**：agent 處理研究報告或分析文件時
- **現有防護**：三問中的「跨時間存活」可過濾，但只在人主動問時才被激活 → **防護存在但不主動**
- **影響**：L2 數量膨脹，信噪比下降，真正重要的公司共識概念被淹沒

#### R8：初始 Impacts 品質不足
- **描述**：新專案建立 L2 時，impacts 寫得模糊（「A impacts B」），缺少具體傳播路徑（「A 的什麼改了 → B 的什麼要跟著看」）
- **觸發條件**：快速建立大量 L2 時（如初始 ontology 建設）
- **現有防護**：server 端檢查 impacts 描述必須含 `→`，但只檢查格式不檢查語意 → **最低防護**
- **影響**：impacts 路徑名存實亡，知識傳播追蹤形同虛設

### 共通風險（兩類專案都有）

#### R9：Agent 使用信號未被捕獲
- **描述**：agent 搜尋 entity 後沒使用結果（如 paceriz 案例），這個「搜了但沒用」的信號沒有被記錄。系統不知道哪些 entity 對 agent 沒有幫助
- **觸發條件**：任何 agent 使用 `mcp__zenos__search` 的場景
- **現有防護**：**完全沒有** — 搜尋行為不被追蹤
- **影響**：無法從使用端信號回推哪些 entity 需要改善

#### R10：治理規則與執行層不同步
- **描述**：治理 spec 更新了但 skill / server / analyze 沒跟上（SPEC-governance-framework 的傳播契約問題）
- **觸發條件**：任何治理 spec 的修改
- **現有防護**：傳播契約定義了 6 個傳播層級，但執行靠人工 checklist → **防護定義完整但執行靠人**
- **影響**：規則形同虛設，agent 按舊規則執行

### 風險嚴重度總覽

| 風險 | 適用場景 | 現有防護 | 影響程度 | 偵測難度 |
|------|---------|---------|---------|---------|
| R6 Capture 不走分層 | 新專案 | 門檻被繞過 | 高 | 低（可結構化檢查） |
| R1 Summary 語意腐化 | 現有 | 無 | 高 | 高（需語意判斷） |
| R2 Blindspot 沉默累積 | 現有 | 無 | 高 | 中（可從 task 信號推斷） |
| R9 使用信號未捕獲 | 共通 | 無 | 中 | 低（可加 logging） |
| R5 冷啟動品質天花板 | 現有 | 無優先級 | 中 | 中（需品質評分） |
| R3 過時文件污染 | 現有 | 有但不自動 | 中 | 低（可結構化檢查） |
| R7 研究型內容錯誤升級 | 新 | 有但不主動 | 中 | 中（需語意判斷） |
| R4 Impacts 斷鏈 | 現有 | 部分 | 中 | 低（可自動檢查） |
| R8 Impacts 品質不足 | 新 | 最低 | 中 | 高（需語意判斷） |
| R10 規則執行不同步 | 共通 | 靠人 | 中 | 中 |

---

## 第三章：需求

### P0（必須有）— 堵住最大的洞

#### P0-1：Capture 強制分層路由

- **描述**：任何知識寫入 ontology 的流程，必須在寫入前強制經過分層判斷：這個內容屬於 L2 / L3 / sources 的哪一層？不允許跳過判斷直接寫入。
- **解決的風險**：R6（capture 不走分層）、R7（研究型內容錯誤升級）
- **為什麼是 P0**：分層錯誤從第一天就讓 ontology 退化成文件索引。這是新專案最大的品質風險，也是現有專案每次新增知識時的持續風險。
- **Acceptance Criteria**：
  - Given agent 執行 capture 或 write 操作，When 內容被判斷為 L2 候選，Then 系統必須要求 agent 回答三問並提供至少一條具體 impacts，才能寫入 L2
  - Given 內容不符合 L2 標準，When agent 嘗試寫入 L2，Then 系統建議降級到 L3 document 或 sources，並提供降級路徑
  - Given 用 `/zenos-capture` 做批次冷啟動，When 產出 L2 候選清單，Then 每個候選必須附帶三問判斷結果和 impacts 草稿，供人工 review 確認

#### P0-2：冷啟動後的品質校正優先級

- **描述**：capture 冷啟動完成後，系統應產出一份「品質校正優先級清單」，告訴用戶哪些 L2 最需要優先人工校正。
- **解決的風險**：R5（冷啟動品質天花板）
- **為什麼是 P0**：每個現有專案的第一步就是冷啟動。沒有校正優先級，用戶不知道從哪裡開始改善，最後就不改了。
- **Acceptance Criteria**：
  - Given capture 冷啟動完成，When 用戶查看結果，Then 系統提供按品質風險排序的 L2 清單，至少包含：impacts 模糊度、summary 通用性（是否只有技術語言）、三問通過信心度
  - Given 優先級清單中的第一名，When 用戶校正該 L2，Then 校正後的 ontology 品質可被 analyze 驗證為改善

### P1（應該有）— 建立回饋迴路

#### P1-1：Task 信號 → Blindspot 管道

- **描述**：當 task 執行過程中遇到反覆出現的問題（workaround、已知限制、非預期行為），且該問題與某個 L2 模組相關，系統應能將這個信號轉化為 blindspot 記錄。
- **解決的風險**：R2（blindspot 沉默累積）
- **為什麼是 P1**：paceriz 案例的核心教訓。agent 反覆踩同一個坑但 ontology 不知道。這個能力可以大幅降低知識腐化速度，但需要定義「什麼算反覆出現的問題」。
- **Acceptance Criteria**：
  - Given 同一個 linked_entity 下有 N 張 task 的 result 或 description 提到類似問題（N 的閾值待定義），When 系統偵測到此模式，Then 自動建議建立 blindspot，包含問題摘要和相關 task 引用
  - Given 系統建議的 blindspot，When 用戶確認，Then blindspot 被建立並掛載到對應 L2 entity
  - Given 系統建議的 blindspot，When 用戶拒絕，Then 記錄拒絕原因，避免重複建議

#### P1-2：Impacts 斷鏈自動偵測

- **描述**：analyze 應能偵測 impacts 路徑的目標是否仍然有效 — 目標 entity 是否存在、是否已被重構拆分、是否已降級。
- **解決的風險**：R4（impacts 斷鏈）
- **為什麼是 P1**：結構性問題，可以完全自動化偵測，不需要語意判斷。投入低、收益確定。
- **Acceptance Criteria**：
  - Given L2 entity A 有 impacts 指向 entity B，When B 已被刪除或狀態為 stale，Then analyze 報告 A 的 impacts 路徑斷鏈，建議更新
  - Given analyze 報告斷鏈，Then 報告中包含斷鏈的具體 impacts 描述和建議動作（更新目標 / 移除 impacts / 替換為新目標）

#### P1-3：過時文件主動標記

- **描述**：對於現有專案的冷啟動匯入，系統應能從文件內容信號（如：引用的 API 已不存在、提到的版本號已過時、與其他文件矛盾）推斷文件可能過時，主動標記供人工確認。
- **解決的風險**：R3（過時文件污染搜尋結果）
- **為什麼是 P1**：現有專案最常見的問題。paceriz 有大量過時文件拉低搜尋品質。自動標記可大幅降低人工清理的發現成本。
- **Acceptance Criteria**：
  - Given 冷啟動匯入一批文件，When 系統分析文件間的一致性，Then 標記出可能過時的文件（依據：與其他文件矛盾、引用已不存在的概念、最後修改時間超過閾值）
  - Given 標記為可能過時的文件，When 用戶確認確實過時，Then 文件走 archive/supersede 流程

### P2（可以有）— 深度語意治理

#### P1-4：Entry 飽和壓縮執行 Workflow

- **描述**：`analyze` 偵測到 entry 飽和並產出 consolidation proposal 後，client agent 必須走標準 workflow 執行壓縮。目前沒有定義執行路徑，agent 各自解讀，容易踩到「先 archive 再 write，write 失敗 → 知識消失」的坑。
- **解決的風險**：entry 飽和時 `write` 被阻擋，但 agent 不知道標準處置步驟
- **為什麼是 P1**：detection 已存在（analyze 已輸出 proposal），缺的是標準執行路徑。不定義就是讓每個 agent 自行猜。
- **執行順序（硬規則）**：
  1. 呈現 proposal 給用戶（顯示合併計畫 + 保留項目）
  2. 取得明確人工確認才執行
  3. 每組合併：先 `write` 新 merged entry → 成功後才 archive 舊 entries（`archive_reason="merged"`）
  4. 若 write 失敗，跳過本組、不 archive 舊 entries
  5. 全部完成後 `get` 驗證 active entries < 20
- **為什麼先 write 再 archive**：若順序反過來，archive 成功但 write 失敗 → 舊 entries 消失，知識不可逆損失
- **Acceptance Criteria**：
  - Given `analyze` 回傳 `entry_saturation` 非空，When agent 執行壓縮，Then 必須先呈現 proposal 取得確認才執行任何 write/archive
  - Given 用戶確認執行，When 執行每組合併，Then 順序為：write 新 entry → archive 舊 entries，兩步均有 error handling
  - Given write 新 entry 失敗，Then 本組所有舊 entries 保持 active，回報錯誤，不 archive
  - Given 全部執行完，Then `get` 驗證 active entries < 20；若仍 >= 20 回報未完成項目

#### P2-1：Agent 使用信號追蹤

- **描述**：記錄 agent 的 search → 使用行為鏈。當 agent 搜尋 entity 但最終沒有使用搜尋結果時，記錄這個「搜了但沒用」的信號，累積後可推斷哪些 entity 需要改善。
- **解決的風險**：R9（使用信號未捕獲）
- **為什麼是 P2**：需要定義「使用」和「沒使用」的判斷邏輯，且依賴 agent 端的行為追蹤能力。概念清楚但實作邊界需要更多探索。
- **Acceptance Criteria**：
  - Given agent 執行 search 後，When agent 的後續操作未引用任何搜尋結果中的 entity，Then 記錄一筆「search_unused」事件
  - Given 某個 entity 累積 M 次「search_unused」事件（M 閾值待定義），Then 系統標記該 entity 為「低使用效能」，建議 review

#### P2-2：L2 Summary 語意品質評估

- **描述**：analyze 增加一個維度，評估 L2 summary 是否「agent-oriented」— 是否包含對開發者 agent 有用的技術關鍵字和上下文，而不只是對外行銷語言。
- **解決的風險**：R1（summary 語意腐化）
- **為什麼是 P2**：需要 LLM 做語意判斷，成本較高。且「agent-oriented」的定義會隨不同專案和角色而變。需要先有 P1 的使用信號資料，才能校準什麼叫「有用」。
- **Acceptance Criteria**：
  - Given analyze 對 L2 entity 執行品質檢查，When summary 只包含泛用描述而缺少技術關鍵字/核心挑戰/已知限制，Then 標記為「summary 需要 agent-oriented 補強」
  - Given 標記結果，Then 提供具體改善建議（如：「建議補充核心演算法名稱、已知限制、常見失敗模式」）

#### P2-3：治理規則傳播自動追蹤

- **描述**：當治理 spec 被修改時，系統自動識別需要同步更新的傳播層級（skill / server / analyze / 下游 spec），並開出追蹤 task。
- **解決的風險**：R10（規則執行不同步）
- **為什麼是 P2**：SPEC-governance-framework 已定義傳播契約，但目前靠人工。自動化有價值但優先級低於品質回饋迴路本身。
- **Acceptance Criteria**：
  - Given 治理 spec 的內容被修改，When commit 發生，Then 系統列出受影響的傳播層級並建議開 task 追蹤
  - Given 建議的追蹤 task，When 用戶確認，Then task 按 task-governance 規範建立

---

## 第四章：明確不包含

- **不重新定義 L2 三問標準** — 三問 + impacts gate canonical 在 `SPEC-ontology-architecture v2 §7.1`（舊 `SPEC-l2-entity-redefinition` 已於 2026-04-23 併入主 SPEC）；本 SPEC 只要求 capture 流程強制觸發三問判斷
- **不定義 analyze 的技術實作方式** — 新增的偵測能力（impacts 斷鏈、過時文件標記）由 Architect 決定是擴展現有 check_type 還是新增 tool
- **不定義 agent 端的行為追蹤機制** — P2-1 的 search_unused 信號如何從 agent 端收集，由 Architect 決定
- **不取代 SPEC-governance-observability** — 該 spec 聚焦 LLM 推斷歷史的可觀測性（audit log、eval dataset）；本 spec 聚焦治理品質的回饋迴路。兩者互補，不重疊
- **不定義自動修復** — 本 spec 所有機制的產出都是「偵測 + 建議」，最終修復動作由人或 agent 確認後執行。不做無人確認的自動覆寫

---

## 第五章：技術約束（給 Architect 參考）

- **Capture 分層路由必須在 server 端強制**：不能只靠 skill 提醒 agent「記得走三問」— 案例 B 證明 agent 不會主動走。分層判斷至少要有 server 端的結構化檢查（如 write L2 時必須附帶 impacts），語意判斷可以在 agent 端
- **冷啟動品質評分不能依賴外部服務**：capture 後的品質校正清單必須用 ontology 自身資料就能產出（impacts 模糊度、summary 長度/通用性、三問信心度），不依賴額外的 LLM 呼叫
- **Task 信號分析的效能考量**：P1-1 的 task 信號 → blindspot 管道需要讀取同一 linked_entity 下的多筆 task history。Architect 需考慮這個查詢在大型專案（數百筆 task）下的效能
- **與現有 analyze 的整合**：P1-2（impacts 斷鏈）和 P1-3（過時文件標記）的偵測結果應整合進現有 `analyze` 的輸出格式，不另立報告管道

---

## 第六章：開放問題

1. **「反覆出現的問題」閾值**：P1-1 的 task 信號 → blindspot，N 張 task 提到類似問題才觸發建議。N 應該是多少？2？3？是否應依專案規模動態調整？
2. **冷啟動品質評分的權重**：P0-2 的品質校正優先級清單，impacts 模糊度、summary 通用性、三問信心度三個維度的權重如何設定？是否需要跑幾輪實測來校準？
3. **Capture 分層路由對批次匯入的影響**：P0-1 要求每個 L2 候選都過三問。但冷啟動可能一次匯入數十個候選，逐個判斷會大幅拉長匯入時間。是否允許批次判斷（一次給 LLM 多個候選），還是必須逐個？
4. **Summary 的「agent-oriented」定義是否因角色而異**：P2-2 假設 summary 應對開發者 agent 有用。但如果公司主要用行銷 agent，「有用」的定義完全不同。是否需要按角色定義不同的品質評估標準？
5. **本 spec 與 SPEC-governance-observability 的執行順序**：兩份 spec 都增強 analyze 能力。是否應先做 observability（有資料基礎），再做回饋迴路（用資料驅動改善）？還是可以平行？

---

## 第七章：完成定義

1. 本 spec 已列入 ZenOS active spec surface
2. P0-1 的分層路由在至少一個真實專案（如 paceriz 或新專案）驗證：capture 寫入 L2 時被強制要求三問 + impacts，不符合標準的被降級
3. P0-2 的品質校正清單在 paceriz 冷啟動資料上跑出結果，排序與人工判斷一致度 ≥ 70%
4. P1-1 的 task 信號 → blindspot 管道在 paceriz 上回溯驗證：能從歷史 task 中偵測到至少 1 個已知但未記錄的 blindspot（如 LLM JSON 格式問題）
5. P1-2 的 impacts 斷鏈偵測在 analyze 中可用，且能正確識別已失效的 impacts 路徑

---

## 第八章：與其他文件的關係

| 文件 | 關係 |
|------|------|
| `SPEC-ontology-architecture v2 §7.1` | 本 SPEC 要求 capture 強制觸發主 SPEC 定義的三問 + impacts gate（舊 `SPEC-l2-entity-redefinition` 已併入）|
| `SPEC-doc-governance` | 本 spec 的 P1-3（過時文件標記）產出進入該 spec 定義的 archive/supersede 流程 |
| `SPEC-task-governance` | 本 spec 的 P1-1 讀取 task 歷史作為品質信號來源 |
| `SPEC-governance-framework` | 本 spec 是該框架 Phase 0 → Phase 1 演進的具體實作需求 |
| `SPEC-governance-observability` | 互補關係：observability 聚焦推斷歷史的可觀測性，本 spec 聚焦治理品質的回饋迴路 |
