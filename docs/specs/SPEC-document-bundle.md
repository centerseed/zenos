---
type: SPEC
id: SPEC-document-bundle
status: Draft
ontology_entity: L3 文件治理
created: 2026-04-09
updated: 2026-04-09
---

# Feature Spec: Document Bundle — L3 文件節點升級為語意文件索引

## 背景與動機

ZenOS 的 L3 document entity 目前是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部系統。但現行設計有兩個根本限制：

**限制一：一對一綁定。** 每個 doc entity 只能掛一個 source。但在真實工作中，一個知識主題會隨時間累積多份文件——規格、決策紀錄、設計文件、測試場景、行銷版摘要、客戶面對版本。現行做法是為每個檔案建一個獨立的 doc entity，導致 L2 entity 底下掛了大量碎片化的 L3 節點，知識地圖變成文件清單。

**限制二：文件類別僅限軟體開發。** 現有的文件類型（SPEC、ADR、TD、TC、REF）完全圍繞軟體開發流程設計。但 ZenOS 的目標客群是中小企業——他們的文件可能是行銷企劃、客戶合約、報價單、會議紀錄、公司政策。現有分類無法涵蓋這些場景，導致非技術文件只能塞進 REF（語意不精確）或不被治理（更糟）。

**產品定位：**

> ZenOS 是語意索引層，不是內容倉庫。管「意義和關聯」，內容留在原生系統，透過 MCP 聯邦模式讓 AI agent 同時擁有語意理解和內容存取能力。

本 spec 做三件事：
1. **Document Bundle**：L3 doc entity 從「單一文件代理」升級為「語意文件索引」，一個 entity 聚合同一主題的多份文件
2. **泛用文件類別**：擴展文件類別系統，讓非軟體開發的文件也能被穩定治理
3. **治理 Skill 泛用化**：更新 `document-governance.md`，讓任何產業的 agent 都能遵循一致的文件治理流程

## 目標用戶

| 角色 | 場景 | 核心需求 |
|------|------|---------|
| **Workspace Owner** | 把專案知識分享給合作夥伴 | 一個 doc entity 就能展示概念的完整文件集 |
| **Guest / Member（非技術）** | 行銷人員需要讀 spec 來做行銷規劃 | 在 Dashboard 看到文件索引，能找到自己有權限讀的版本 |
| **AI Agent** | 需要讀文件內容來做分析 | 從 doc entity 拿到 change_summary 快速掌握重點，再用外部 MCP 讀取需要深入的 source |
| **PM / Architect** | 建立和維護專案文件 | capture/sync 時，文件自動歸入對應的 doc entity index |
| **非軟體產業用戶** | 管理行銷企劃、客戶合約、會議紀錄等 | 文件類別能涵蓋自己的文件，不是只有 SPEC/ADR |

## Spec 相容性

| Spec | 分析 | 處理方式 |
|------|------|---------|
| SPEC-doc-governance (Approved) | **範圍重疊**。該 spec 定義每份正式文件獨立分類/識別/生命週期。本 spec 將 L3 doc entity 從「一份文件」重新定義為「一組文件的索引」，改變了 L3 的語意身份。 | 不直接修改 Approved spec。本 spec 定義 Document Index 為 L3 的新子類型，與原有 Single Document 共存。個別文件的生命週期追蹤移到 source 層級的 `doc_status` 欄位，保留治理精神。**需要在 SPEC-doc-governance 補充 amendment 說明 L3 新增 Index 子類型。** |
| SPEC-doc-source-governance (Draft) | **需要更新**。source_uri 驗證規則繼續適用於每個 source。開放問題「source_status 放頂層還是每個 source」確認為：**放在每個 source 上**。 | 更新 Draft spec，將 source_status 定義移到 source 層級 |
| SPEC-batch-doc-governance (如存在) | **介面衝突**。`batch_update_sources` 假設 single URI per doc。 | 需要擴展為支援 per-source 操作，使用 `source_id` 定位 |

---

## 需求

### P0（必須有）

#### P0-1: Document Index — L3 doc entity 新子類型

- **描述**：L3 doc entity 新增 `doc_role` 欄位，區分兩種角色：

  | doc_role | 語意 | source 數量 | 用途 |
  |----------|------|------------|------|
  | `single` | 單一文件的語意代理（現有行為） | 1 | 向後相容，現有 doc entity 自動為 single |
  | `index` | 某個語意主題的文件索引 | 1..N | 聚合同主題的多份文件 |

- **新建判準**：
  - **選 single**：目前只有一份正式文件，且短期內沒有要聚合多份版本或附件
  - **選 index**：同一主題已知會聚合 2 份以上正式文件，或文件集本身就是產品需求的一部分（如「訂閱管理文件集」包含 SPEC + DECISION + DESIGN）

- **Index 與 Single 的治理差異**：
  - `single`：doc entity 的 `status` 直接反映文件狀態（draft/approved/superseded）
  - `index`：doc entity 的 `status` 反映索引本身的狀態（active/archived）。個別文件的狀態追蹤在每個 source 的 `doc_status` 欄位

- **Acceptance Criteria**：
  - Given 現有 doc entity 未指定 doc_role，When 系統讀取，Then 預設為 `single`（向後相容）
  - Given agent 建立 doc_role=index 的 entity，When 傳入多個 source，Then 全部正確儲存
  - Given doc_role=single 的 entity，When agent 嘗試新增第 2 個 source，Then 拒絕操作，提示「single doc entity 只能有一個 source，若需聚合多份文件請改用 index」

#### P0-2: Source 結構升級（每個 source 獨立可識別）

- **描述**：每個 source 必須有穩定的 `source_id`，支援 per-source 的 CRUD 操作。
- **Source 結構**：

  | 欄位 | 必填 | 說明 |
  |------|------|------|
  | `source_id` | 系統生成 | 穩定識別碼，用於 read_source / update / remove 操作 |
  | `uri` | 必填 | 指向外部文件的完整 URL |
  | `type` | 系統推斷 | github / notion / gdrive / wiki / url（根據 URI pattern 自動判斷） |
  | `label` | 必填 | 人類可讀的檔案名稱 |
  | `doc_type` | 選填 | 文件類別（見 P0-4 泛用文件類別）。single doc entity 的 doc_type 等同 entity 本身的 type |
  | `doc_status` | 選填 | 該份文件的生命週期狀態（draft/approved/superseded/archived）。僅 index 類型使用 |
  | `source_status` | 系統管理 | URI 可達性（valid / stale / unresolvable） |
  | `note` | 選填 | 用途說明（如「行銷版摘要」「客戶面對版本」） |
  | `is_primary` | 預設 false | 標記主要 source。`read_source(doc_id)` 不帶 source_id 時讀取 primary |

- **Mutation 操作**（解決 reviewer Finding #3）：
  - `write(collection="documents", data={..., sources: [...]})` — 建立時傳入完整 sources 陣列
  - `write(collection="documents", data={doc_id: "xxx", add_source: {...}})` — 追加 source
  - `write(collection="documents", data={doc_id: "xxx", update_source: {source_id: "yyy", ...}})` — 更新特定 source
  - `write(collection="documents", data={doc_id: "xxx", remove_source: {source_id: "yyy"}})` — 移除 source（最後一個不可移除）

- **Acceptance Criteria**：
  - Given agent 追加 source 到 index entity，When write 執行，Then 系統生成 source_id，其他 source 不受影響
  - Given agent 用 source_id 更新特定 source 的 URI，When write 執行，Then 只有該 source 被修改
  - Given agent 移除 index entity 的最後一個 source，When write 執行，Then 拒絕操作
  - Given agent 對 batch_update_sources 操作，When 傳入 source_id，Then 只更新對應的 source（不影響其他 source）

#### P0-3: read_source 合約升級（解決 reviewer Finding #2）

- **描述**：`read_source` 從 `read_source(doc_id)` 升級為 `read_source(doc_id, source_id?)`。
  - 有 `source_id` → 讀取指定 source
  - 無 `source_id` → 讀取 `is_primary=true` 的 source；若無 primary，讀取第一個 `source_status=valid` 的 source
  - 讀取失敗時，回傳結構化錯誤，沿用現有 source_status 機制（stale / unresolvable），並在 response 附帶 `setup_hint`（建議性，非新 status）

- **setup_hint 結構**（解決 reviewer Finding #4，不引入 mcp_not_configured status）：
  - 當 read_source 回傳 stale 或錯誤時，response 額外附帶：
    - `source_type`：來源類型
    - `setup_hint`：建議的外部 MCP server 名稱（如 `"Google Drive MCP"`）
    - `alternative_sources`：同一 bundle 內其他可用的 source（如有）
  - 這是純建議性資訊，不改變現有的 source_status 狀態機

- **Acceptance Criteria**：
  - Given agent 呼叫 `read_source(doc_id)` 且 entity 有 primary source，When 執行，Then 讀取 primary source 內容
  - Given agent 呼叫 `read_source(doc_id)` 且 entity 無 primary 但有 3 個 source，When 執行，Then 讀取第一個 valid source
  - Given agent 呼叫 `read_source(doc_id, source_id="xxx")`，When 執行，Then 讀取指定 source
  - Given read_source 回傳 stale（gdrive 類型），Then response 包含 `setup_hint: "Google Drive MCP"` 和 `alternative_sources` 列表
  - Given bundle 中 source A 失敗但 source B 可用，Then response 的 `alternative_sources` 包含 source B 的 source_id 和 label

#### P0-4: 泛用文件類別系統

- **描述**：將文件類別從軟體開發專用擴展為通用商業場景。文件類別用於 source 的 `doc_type` 欄位（index 模式）或 entity 的 `type` 欄位（single 模式）。
- **治理原則**：`doc_type` 只表達文件性質，不表達部門歸屬。跨部門文件的區隔必須靠 ontology 掛載脈絡（如 `ontology_entity`、linked L2、product/topic），不能靠 `doc_type` 命名或分叉。

- **類別定義**：

  **核心類別（所有產業適用）**

  | 類別 | 名稱 | 用途 | 範例 |
  |------|------|------|------|
  | `SPEC` | 規格文件 | 定義需求、範圍、驗收標準 | 產品規格、功能需求、服務規格 |
  | `DECISION` | 決策紀錄 | 記錄重大決策與理由 | 架構決策(ADR)、策略決策、採購決策 |
  | `DESIGN` | 設計文件 | 記錄實作或執行方案的設計細節 | 技術設計(TD)、視覺設計稿、流程設計 |
  | `PLAN` | 計畫文件 | 記錄行動計畫、時程、里程碑 | 行銷企劃、專案計畫、上市計畫 |
  | `REPORT` | 報告 | 記錄分析結果、執行成果、定期回顧 | 月報、競品分析、A/B 測試報告 |
  | `CONTRACT` | 合約文件 | 具法律或商業約束力的文件 | 客戶合約、合作協議、SLA |
  | `GUIDE` | 指南 | 操作手冊、新手指引、最佳實踐 | Playbook(PB)、onboarding 指南、SOP |
  | `MEETING` | 會議紀錄 | 會議決議、討論摘要 | 週會紀錄、kickoff 紀錄 |
  | `REFERENCE` | 參考資料 | 長期參考、術語表、背景研究 | 術語表(REF)、市場研究、競品資料 |
  | `TEST` | 測試文件 | 測試場景、驗收案例 | 測試案例(TC)、QA checklist |
  | `OTHER` | 其他 | 無法歸類的文件 | — |

  **與現有類別的映射（向後相容）**

  | 現有類別 | 映射到 | 說明 |
  |---------|--------|------|
  | `SPEC` | `SPEC` | 直接保留 |
  | `ADR` | `DECISION` | ADR 是 DECISION 的一種（軟體架構決策） |
  | `TD` | `DESIGN` | TD 是 DESIGN 的一種（技術設計） |
  | `TC` | `TEST` | TC 是 TEST 的一種（測試案例） |
  | `REF` | `REFERENCE` | 直接映射 |
  | `PB` | `GUIDE` | PB 是 GUIDE 的一種（操作手冊） |
  | `SC` | 依用途判斷 | 預設 `REFERENCE`（場景描述是參考性質）；若用於驗收則映射為 `TEST`；若用於需求定義則映射為 `SPEC`。agent 需根據文件實際用途選擇，不硬編死 |

- **向後相容策略**：舊類別（ADR、TD、TC、PB、SC）繼續被接受，系統內部映射到新類別。agent 寫入時兩種都可以用。搜尋時新舊類別都能匹配。
- **跨部門使用規則**：
  - 行銷、客服、營運、業務可以共用同一套 `doc_type`
  - 同樣是 `REPORT` / `GUIDE` / `MEETING`，其部門差異由文件掛載到哪個 L2 主題決定，不由 `doc_type` 決定
  - 禁止為了區分部門而新增 `MARKETING_REPORT`、`CS_REPORT` 這類型別；應維持 `REPORT`，並掛到對應的 ontology topic
  - 搜尋與展示時，`doc_type` 應可與 `ontology_entity` / product / topic 條件疊加使用，避免退化為跨部門混雜的文件倉庫

- **Acceptance Criteria**：
  - Given agent 寫入 `doc_type: "ADR"`，When write 執行，Then 系統接受並內部映射為 `DECISION`
  - Given agent 寫入 `doc_type: "PLAN"`，When write 執行，Then 系統接受（新類別）
  - Given agent 搜尋 `doc_type: "DECISION"`，When search 執行，Then 同時回傳 DECISION 和 ADR 類型的文件
  - Given agent 寫入 `doc_type: "UNKNOWN_TYPE"`，When write 執行，Then 回傳 warning 建議使用 `OTHER`，但不拒絕
  - Given 行銷競品分析與客服客訴分析都使用 `doc_type: "REPORT"`，When 文件分別掛到不同 L2 entity，Then 兩者在 ontology 與 Dashboard 中視為不同主題，不因類型相同而混為同一組文件

#### P0-5: Change Summary — Doc Entity 層級的變化摘要

- **描述**：Doc entity 新增 `change_summary` 欄位，記錄文件集的最新重要變化。讓 agent 不需要讀取所有 source 原文就能快速掌握重點。change_summary 由 agent 在 capture/sync 時更新（不是 server 自動生成）。

- **欄位結構**：
  - `change_summary`（選填，string）：一段人話摘要，描述文件集最近的重要變化
  - `summary_updated_at`（系統管理）：change_summary 最後更新時間

- **使用場景範例**：
  - 「2026-04-09：新增 ADR-020 決定採用 MCP 聯邦模式，不做 content snapshot。SPEC 已更新 Phase 規劃。」
  - 「2026-04-05：客戶合約 v2 簽署完成，新增 SLA 附件。舊合約已標記 superseded。」

- **Acceptance Criteria**：
  - Given agent 更新 doc entity 的 change_summary，When write 執行，Then summary_updated_at 自動設為當前時間
  - Given agent 搜尋 doc entity，When search 結果回傳，Then 包含 change_summary 欄位
  - Given agent 呼叫 get(doc_id)，When 回傳，Then 包含 change_summary 和 summary_updated_at
  - Given change_summary 超過 90 天未更新且 entity 有活躍的 source 變動，When analyze 執行，Then 回傳 warning「change_summary 可能過時」

#### P0-6: Capture/Sync 路由規則（解決 reviewer Finding #1）

- **描述**：定義 agent 在 capture 和 sync 時的明確路由規則，決定新文件應該建新 entity、追加到既有 index、或掛到 L2 entity 的 sources。

- **路由決策樹**：

  ```
  Agent 發現一份新文件
       │
       ├─ Step 1：搜尋 ontology，是否有同主題的 doc entity？
       │         search(collection="documents", query="<主題關鍵字>")
       │
       ├─ 找到 doc_role=index 的 entity？
       │    │
       │    └─ YES → 追加 source 到該 index（add_source）
       │
       ├─ 找到 doc_role=single 的 entity，且新文件與其高度相關？
       │    │
       │    └─ YES → 提議將 single 升級為 index，
       │            把原有 source + 新文件一起放入 index
       │            （需 confirm 確認）
       │
       ├─ 沒有找到相關 doc entity？
       │    │
       │    ├─ 文件屬於某個 L2 module 的正式產出？
       │    │    └─ YES → 建立新 doc entity（single 或 index）掛在該 L2 下
       │    │
       │    └─ 文件是 L2 的輕量參考？
       │         └─ YES → 掛到 L2 entity 的 sources[]（不建 L3）
       │
       └─ 不確定？→ 停止，回報用戶確認
  ```

- **L2 sources[] vs L3 doc entity 的邊界**：

  | 層級 | 定義 | 判斷標準 | 正例 | 反例（不應放在此層級） |
  |------|------|---------|------|---------------------|
  | **L2 sources[]** | 輕量參考連結。不需要獨立語意標注或生命週期追蹤 | 拿掉這個連結，L2 entity 的語意描述不會受影響 | 原始碼檔案路徑、外部 API 文件連結、工具設定檔 | 客戶合約（有獨立生命週期）、產品規格（需要狀態追蹤） |
  | **L3 single doc** | 一份正式文件的語意代理。需要獨立狀態追蹤（draft→approved→superseded） | 這份文件有明確的審核流程、版本邊界、或法律/商業效力 | 一份 SPEC、一份 ADR、一份客戶合約 | README（輕量參考）、程式碼註解（不受文件治理） |
  | **L3 index doc** | 一組正式文件的語意索引。需要聚合展示、change_summary、per-source 狀態追蹤 | 這個主題已知會產生 2+ 份正式文件，或文件集本身是產品需求的一部分 | 「訂閱管理文件集」（SPEC+DECISION+DESIGN）、「客戶 X 交付文件」（合約+SLA+驗收報告） | 只有一份 SPEC 且短期不會增加（用 single） |

- **防混雜原則**：
  - 文件是否屬於同一個 bundle，優先看是否服務同一個 ontology 主題，而不是是否屬於同一個 `doc_type`
  - 不同部門即使共用 `REPORT`、`MEETING`、`GUIDE`，只要掛載的 L2 主題不同，就應建立不同 doc entity 或 index
  - agent 不得因兩份文件 `doc_type` 相同，就自動追加到同一個 index；必須先確認它們是否指向同一個語意主題

  **「正式產出」的定義**：具有以下任一特徵的文件——
  1. 需要走審核流程（Draft → Under Review → Approved）
  2. 有明確的版本邊界（v1 → v2，而非持續編輯）
  3. 具法律、商業、或跨團隊約束力（合約、SPEC 的 AC、ADR 的決策結論）
  4. 被其他文件或任務引用為依據

  **「輕量參考」的定義**：不具備上述任一特徵的連結。移除它不影響知識圖譜的語意完整性。

- **首次建立時何時直接建 index**：
  - 當 agent 同時 capture 同一主題的 2+ 份文件時，直接建 index（不先建 single 再升級）
  - 當主題的性質明確會產出多份文件時（如「客戶交付」天生包含合約+SLA+驗收），直接建 index
  - 不確定時，建 single。後續需要時再升級為 index

- **Acceptance Criteria**：
  - Given agent capture 一份新 SPEC 且已存在同主題的 index entity，When 路由判斷，Then agent 選擇 add_source 而非建新 entity
  - Given agent capture 一份新文件且沒有任何相關 doc entity，When 路由判斷，Then agent 建立新 doc entity
  - Given agent 不確定路由，When 路由判斷，Then agent 停止並回報用戶（不自行猜測）
  - Given governance skill 已更新，When agent 讀取 governance_guide("document")，Then 回傳包含路由決策樹的治理指引

#### P0-7: Git URI 嚴格驗證

- **描述**：GitHub 類型的 source URI 必須通過嚴格的格式驗證。Git URI 錯誤是已知的高頻問題，必須在寫入時 server-side 阻擋。
- **驗證規則**：
  1. 必須符合 `https://github.com/{owner}/{repo}/blob/{branch}/{path}` 格式
  2. 不接受相對路徑（如 `docs/specs/file.md`）
  3. 不接受 tree URL（目錄連結）
  4. 不接受 raw URL（`raw.githubusercontent.com`）
- **Acceptance Criteria**：
  - Given agent 傳入相對路徑，When `write` 執行，Then 回傳 400，entity 不寫入
  - Given agent 傳入合法 GitHub blob URL，When `write` 執行，Then source 正常寫入
  - Given agent 傳入 tree URL，When `write` 執行，Then 回傳 400，附說明「請提供檔案連結而非目錄連結」

#### P0-8: Google Drive URI 驗證

- **描述**：Google Drive 類型的 source URI 必須包含有效的 file ID pattern。
- **驗證規則**：
  1. 必須符合 `https://docs.google.com/...` 或 `https://drive.google.com/...` 格式
  2. URL 中必須包含 file ID
  3. 不接受純資料夾連結
- **Acceptance Criteria**：
  - Given agent 傳入合法 Google Doc URL，When `write` 執行，Then source 正常寫入，type 設為 `gdrive`
  - Given agent 傳入 Google Drive 資料夾 URL，When `write` 執行，Then 回傳 400

#### P0-9: Dashboard 外鏈跳轉與 Source 列表

- **描述**：Dashboard 在 doc entity 詳情頁顯示所有 source。對 index 類型，按 doc_type 分組顯示。每個 source 旁有平台圖標和「在 XXX 中打開」按鈕。
- **Acceptance Criteria**：
  - Given doc_role=index 的 entity 有 4 個 source（SPEC、DECISION、DESIGN、TEST），When Dashboard 顯示，Then 按 doc_type 分組展示
  - Given source 的 source_status 為 `stale`，Then 連結旁顯示警告標記
  - Given source 的 source_status 為 `unresolvable`，Then 連結顯示為不可點擊

---

### P1（應該有）

#### P1-1: 文件治理 Skill 泛用化

- **描述**：更新 `skills/governance/document-governance.md`，從軟體開發專用升級為通用商業文件治理。核心改動：

  1. **文件類別擴展**：引用 P0-4 的泛用類別系統，不再只列 SPEC/ADR/TD/TC/REF
  2. **路由規則內建**：將 P0-6 的路由決策樹寫入 skill，讓 agent 在 capture/sync 時自動判斷
  3. **情境→文件對應表泛用化**：

     | 情境 | 文件類別 | 軟體開發範例 | 非軟體範例 |
     |------|---------|------------|-----------|
     | 定義需求或規格 | SPEC | 功能規格 | 產品規格、服務規格 |
     | 記錄重大決策 | DECISION | ADR | 策略決策、採購決策 |
     | 設計實作方案 | DESIGN | TD | 視覺設計、流程設計 |
     | 制定行動計畫 | PLAN | Sprint 計畫 | 行銷企劃、上市計畫 |
     | 分析或回顧結果 | REPORT | 事後檢討 | 月報、競品分析 |
     | 簽約或協議 | CONTRACT | SLA | 客戶合約、合作協議 |
     | 操作指引 | GUIDE | Playbook | SOP、新人指南 |
     | 會議產出 | MEETING | — | 週會紀錄、kickoff |
     | 長期參考 | REFERENCE | 術語表 | 市場研究、品牌指南 |
     | 測試驗證 | TEST | TC | QA checklist |

  4. **governance_guide("document") 回傳更新**：server 端的 governance_guide tool 回傳新的文件治理規則，包含泛用類別和路由決策樹

- **Acceptance Criteria**：
  - Given agent 呼叫 governance_guide("document")，When 回傳，Then 包含泛用文件類別表和路由決策樹
  - Given 行銷人員透過 agent 建立「行銷企劃」文件，When agent 遵循 governance skill，Then 文件被分類為 PLAN，掛到對應的 doc entity

#### P1-2: Single → Index 升級流程

- **描述**：當一個 single doc entity 需要開始聚合多份文件時，提供升級流程。
- **流程**：
  1. Agent 發現新文件與既有 single entity 高度相關
  2. Agent 提議升級：`write(doc_id, data={doc_role: "index", add_source: {...}})`
  3. 原有的 single source 自動成為 index 的第一個 source（繼承 is_primary=true）
  4. 新文件成為第二個 source
- **Acceptance Criteria**：
  - Given doc_role=single 的 entity，When agent 寫入 doc_role=index 並追加新 source，Then 原有 source 保留，doc_role 更新為 index
  - Given 升級後的 entity，When search/get 回傳，Then 顯示完整的 sources 陣列

#### P1-3: Bundle Source 主動同步

- **描述**：`/zenos-sync` 執行時，對 git repo 內的 source，主動比對檔案是否已被移動或刪除，自動更新 URI 和 source_status（主動同步策略）。
- **Acceptance Criteria**：
  - Given sync 偵測到 source URI 的檔案已改名，When sync 執行，Then 自動更新 URI，source_status 設為 valid
  - Given sync 偵測到 source URI 的檔案已刪除，When sync 執行，Then source_status 設為 stale，回報用戶

---

### P2（可以有）

#### P2-1: 跨 Bundle 去重偵測

- **描述**：同一個 source URI 不應出現在多個 doc entity 中。write 時偵測到 URI 重複，回傳 warning（不阻擋寫入）。
- **Acceptance Criteria**：
  - Given URI 已存在於 entity A，When agent 寫入 entity B，Then write 成功但附 warning

#### P2-2: Bundle 視覺化（知識地圖）

- **描述**：知識地圖中 doc entity 的視覺反映 bundle 豐富度和 doc_role。
- **Acceptance Criteria**：
  - Given doc_role=index 的 entity 有 5 個 source，When 知識地圖顯示，Then 視覺上區別於 single doc entity

#### P2-3: 自訂文件類別

- **描述**：workspace 層級可以新增自訂文件類別（超出預設的 11 種）。
- **Acceptance Criteria**：
  - Given workspace admin 新增類別 `INVOICE`，When agent 使用該類別，Then 系統接受

---

## 明確不包含

- **儲存文件內容** — ZenOS 是語意索引層，不存內容
- **Content snapshot / 快取** — 不做內容副本
- **Content fallback** — 外部 MCP 不可用時不自己去抓內容
- **文件編輯器** — 不提供文件編輯功能
- **文件版本控制** — 版本管理是原生系統的責任
- **檔案上傳 / 託管** — 不做 file hosting
- **全文搜尋** — ZenOS 的搜尋是語意索引層搜尋
- **排程爬取外部系統** — 所有治理操作 on-demand
- **MCP 設定管理** — ZenOS 不管使用者掛了哪些 MCP，只在 read_source 失敗時附帶 setup_hint
- **強制建立 mcp_not_configured status** — 不引入新的 source_status 值，沿用現有 stale/unresolvable 機制

## 技術約束（給 Architect 參考）

- **L3 文件治理 impact chain** — 本 spec 變更影響下游：L3 Task 治理規則、MCP 介面設計、Dashboard 知識地圖
- **source 從 object 升級為 array** — 需要 DB migration。每個 source 帶 source_id（UUID）
- **source_status 在 source 層級** — 確認 SPEC-doc-source-governance 開放問題：每個 source 獨立追蹤 source_status
- **doc_role 欄位** — documents 表新增 enum 欄位，預設 `single`（向後相容）
- **doc_type 映射** — server-side 維護新舊類別映射表，搜尋時透明展開
- **change_summary 欄位** — documents 表新增 text 欄位 + timestamp
- **read_source 介面變更** — 新增可選 source_id 參數，向後相容（不帶=讀 primary）
- **write mutation 擴展** — 新增 add_source / update_source / remove_source 操作語意
- **Git URI 驗證為 server-side reject** — 不依賴 agent，server 直接拒絕
- **governance_guide("document") 更新** — 回傳內容需包含泛用類別表和路由決策樹
- **SPEC-doc-governance 需補 amendment** — 說明 L3 新增 index 子類型，不改變原有 single 行為
- **SPEC-doc-source-governance 需更新** — source_status 移到 source 層級

## 已決議事項（原開放問題）

1. **既有 doc entity 遷移策略** — **自然演進**，不做一次性主動合併。agent 在 capture/sync 時透過 P1-2 的 single→index 升級流程逐漸遷移。風險最低，符合漸進設計。

2. **doc_type 映射的過渡期** — **讀取永久相容**（搜尋時新舊類別都能匹配）。**寫入從 skill 層先全面改用新類別**（governance skill 引導 agent 使用新類別）。等 1-2 個 release cycle 後再考慮把舊類別寫入降成 warning，不硬砍讀相容。

3. **change_summary 的更新責任** — **不做 server 自動生成**。但在 `add_source` / `update_source` / `remove_source` / `supersede` 操作完成時，response 回傳 `suggestions` 欄位提醒 agent 更新 change_summary。agent 應在同一輪操作中更新。

## 開放問題

（無）
