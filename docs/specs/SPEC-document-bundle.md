---
type: SPEC
id: SPEC-document-bundle
status: Draft
ontology_entity: L3 文件治理
created: 2026-04-09
updated: 2026-04-16
supersedes:
  - SPEC-doc-source-governance
---

# Feature Spec: Document Bundle — L3 文件節點升級為語意文件索引

> SSOT note: 本 spec 是 `doc entity` 的單一真相來源。
> `doc_role`、multi-source schema、source platform contract、URI 驗證、`read_source` 能力邊界、rollout 狀態，都以本文件為準。

## 背景與動機

ZenOS 的 L3 document entity 目前是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部系統。但現行設計有兩個根本限制：

**限制一：文件模型以單檔為中心，不以檢索為中心。** 現行預設把 doc entity 當成單一文件代理，導致同一主題的規格、決策、設計、測試、客戶版摘要被拆成多個碎片 L3。結果是 L2 底下堆滿文件節點，但使用者與 agent 仍然不知道「這個主題該先讀哪份、重點是什麼、下一步去哪裡」。

**限制二：文件類別僅限軟體開發。** 現有的文件類型（SPEC、ADR、TD、TC、REF）完全圍繞軟體開發流程設計。但 ZenOS 的目標客群是中小企業——他們的文件可能是行銷企劃、客戶合約、報價單、會議紀錄、公司政策。現有分類無法涵蓋這些場景，導致非技術文件只能塞進 REF（語意不精確）或不被治理（更糟）。

**產品定位：**

> ZenOS 是語意索引層，不是內容倉庫。管「意義和關聯」，內容留在原生系統，透過 MCP 聯邦模式讓 AI agent 同時擁有語意理解和內容存取能力。

本 spec 做四件事：
1. **Bundle-first Document Entity**：L3 doc entity 從「單一文件代理」升級為「語意文件索引」，預設聚合同一主題的多份文件
2. **泛用文件類別**：擴展文件類別系統，讓非軟體開發的文件也能被穩定治理
3. **Highlight-first Retrieval Contract**：定義 doc entity 如何聚合底下文件 highlights / links，讓人從 L2 就能判斷先讀什麼
4. **Source Platform Contract**：定義不同平台 URI 如何掛在同一個 doc entity 上，以及哪些平台今天真的可讀
5. **治理 Skill 泛用化**：更新 `document-governance.md`，讓任何產業的 agent 都能遵循一致的文件治理流程

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
| SPEC-doc-source-governance (Draft) | **內容已吸收**。source_uri 驗證、source_status、dead-link policy、platform rollout 由本 spec 直接定義。 | 本 spec 成為 SSOT；舊 spec 降為導向文件 |
| SPEC-batch-doc-governance (如存在) | **介面衝突**。`batch_update_sources` 假設 single URI per doc。 | 需要擴展為支援 per-source 操作，使用 `source_id` 定位 |

---

## 核心模型總覽

> 本 spec 是 doc entity 與 source platform support 的唯一 SSOT。凡是回答「doc entity 是否支援某平台文件資料」、「某平台 URI 是否可被收錄」、「今天是否真的可讀原文」時，都以本章與後續需求為準。

### doc entity 的核心定位

`doc entity` 是語意文件索引，不是檔案本體。

- `index`：預設模式。一個 doc entity 對應同一語意主題下的 1..N 份正式文件
- `single`：例外模式。只在明確需要把某份正式文件當成獨立治理對象時使用

不論 `single` 或 `index`，實際內容都存在外部平台；ZenOS 只保存：

- 文件主題語意
- ontology 掛載脈絡
- source metadata
- source status
- bundle highlights
- change summary

### Bundle-first 檢索原則

對使用者與 agent 而言，文件治理的第一優先不是「存成幾個節點」，而是：

1. 從 L2 能立即看到有哪些文件可讀
2. 不用先知道檔名，也能知道應先點哪一份
3. 同一主題的文件入口只有一個穩定 bundle，不必在多個 L3 間猜測

因此本 spec 定義：

- 預設新建 doc entity 必須使用 `doc_role=index`
- `index` 即使目前只有 1 份 source 也合法
- 每個 index 必須提供 `bundle_highlights`
- L2 detail 與知識地圖必須把 doc bundle 視為該 L2 的文件入口，而不是只顯示零散外鏈

### 不同平台 URI 如何被支援

不同平台的文件不是靠不同 doc entity 型別處理，而是靠同一個 doc entity 底下的多個 `source` 處理。

```text
doc entity
  -> sources[]
     -> source.type
     -> source.uri
     -> source_id
     -> source_status
     -> doc_type
```

因此，支援新平台時不需要重做 doc entity；只需要補：

1. `source.type`
2. URI validation
3. reader adapter
4. dead-link policy

這代表 ZenOS 的平台擴充模型是：

> `doc entity` 是穩定殼層，`source platform` 是可插拔能力。

### Source Platform Contract

每個 source platform 至少要定義：

- URI validation
- type normalization
- read capability
- dead-link policy
- setup hint

平台能力必須分層理解，避免誤把「可以掛 URI」等同於「今天可讀原文」：

| 層次 | 問題 | 說明 |
|------|------|------|
| `type normalization` | 這是什麼平台？ | 由 URI pattern 推斷或驗證 `source.type` |
| `URI validation` | 這個 URI 格式合不合法？ | server-side validator 負責拒絕非法值 |
| `status governance` | 這個 source 現在有效嗎？ | 由 `source_status` 與 dead-link policy 表達 |
| `reader adapter` | ZenOS 今天能不能真的讀到內容？ | 由 `read_source(doc_id, source_id?)` 的 adapter 決定 |

### rollout 能力矩陣

| source_type | 合法 URI contract | 可掛入 doc entity | source_status 治理 | 內容讀取 | rollout 狀態 |
|------------|-------------------|------------------|--------------------|----------|-------------|
| `github` | `https://github.com/{owner}/{repo}/blob/{branch}/{path}` | 是 | 正式支援 | **正式支援** | Phase 1 |
| `gdrive` | `https://drive.google.com/file/d/{id}/...` 或 `https://docs.google.com/...`，且需 file ID | 是 | 正式支援 | 規格已定，adapter 待補 | Phase 1.5 |
| `notion` | `https://www.notion.so/...` 且含 UUID 段 | 是 | 基本支援 | 規格已定，adapter 待補 | Later |
| `wiki` | 完整 `https://...`，且不得為 `/edit` | 是 | 基本支援 | 規格已定，adapter 待補 | Later |
| `url` | 完整 `https://...` | 是 | 基本支援 | 不保證，預設 metadata only | Later |

規則：

1. multi-source contract 可以先定案，不需等待所有平台 adapter 完成。
2. spec 必須明確區分「doc entity 架構已支援」與「某平台 today 可讀原文」。
3. `可掛入 doc entity` 只代表資料模型與治理 contract 已支援，不代表 reader 已落地。
4. 當某 source type 尚未有正式 reader adapter 時，`read_source` 必須回傳 unavailable / setup_hint，不得假裝支援。

## 需求

### P0（必須有）

#### P0-1: Bundle-first Document Entity — L3 doc entity 預設使用 index

- **描述**：L3 doc entity 的預設角色改為 `index`。`single` 保留，但降為例外模式，只有在文件本身就是獨立治理單位時才可使用。

  | doc_role | 語意 | source 數量 | 用途 |
  |----------|------|------------|------|
  | `index` | 某個語意主題的文件索引（預設） | 1..N | 聚合同主題的多份文件，作為 L2 的穩定文件入口 |
  | `single` | 單一文件的語意代理（例外） | 1 | 文件本身就是獨立治理單位，不需要再聚合其他文件 |

- **新建判準**：
  - **預設選 index**：只要這份文件屬於某個 L2 主題的正式文件入口，就應建 index，即使現在只有 1 份 source
  - **只有以下情況可選 single**：
    1. 該文件有獨立生命周期，且不希望與同主題其他文件聚合
    2. 該文件被產品明確要求單獨分享、單獨授權、單獨 supersede
    3. 該文件不是某個 L2 的主文件入口，而是單獨存在的正式文件物件

- **Index 與 Single 的治理差異**：
  - `index`：doc entity 的 `status` 反映索引本身的狀態（active/archived）。個別文件的狀態追蹤在每個 source 的 `doc_status` 欄位
  - `single`：doc entity 的 `status` 直接反映文件狀態（draft/approved/superseded）

- **硬規則**：
  - Agent 建新 doc entity 時，若未明確說明 `single` 的例外理由，server/治理規則必須引導使用 `index`
  - 同一個 L2 主題的正式文件，不得預設拆成多個平行 single entity 當作主要入口
  - `index` 的最小合法 source 數量為 1，不得以「目前只有一份文件」作為拒絕建立 index 的理由

- **Acceptance Criteria**：
  - `AC-P0-1-1` Given agent 建立新的 doc entity 且未傳 `doc_role`，When write 執行，Then 系統以 `index` 建立，而不是 `single`
  - `AC-P0-1-2` Given agent 建立 `doc_role=index` 的 entity 且只傳入 1 個 source，When write 執行，Then 寫入成功
  - `AC-P0-1-3` Given agent 建立 `doc_role=single` 的 entity，When write 執行，Then 必須同時提供 single 理由；未提供時回傳 warning 或 reject，引導改用 `index`
  - `AC-P0-1-4` Given 現有舊 doc entity 未指定 doc_role，When 系統讀取，Then 仍向後相容視為 `single`；但新建流程不得再以 `single` 為預設
  - `AC-P0-1-5` Given doc_role=single 的 entity，When agent 嘗試新增第 2 個 source，Then 拒絕操作，提示「single doc entity 只能有一個 source，若需聚合多份文件請改用 index」

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

#### P0-3.1: 平台能力與 reader adapter 對齊

- **描述**：每個 source type 的 `read_source` 行為必須與 rollout 能力矩陣一致。
- **規則**：
  - `github`：可讀原文，屬正式支援
  - `gdrive` / `notion` / `wiki`：在 reader adapter 未完成前，可建立 source、可治理 status、可回傳 setup_hint，但不得宣稱正式可讀
  - 尚未有 reader adapter 的 type，`read_source` 應回傳結構化 unavailable，而不是嘗試偽造內容
- **Acceptance Criteria**：
  - Given `github` source，When `read_source` 執行，Then 取得原文或結構化 dead-link 結果
  - Given `gdrive` source 且 reader adapter 尚未落地，When `read_source` 執行，Then 回傳 unavailable/setup_hint，而不是假裝成功
  - Given `notion` 或 `wiki` source 且 reader adapter 尚未落地，When `read_source` 執行，Then 回傳 unavailable/setup_hint

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

#### P0-5: Bundle Highlights + Change Summary — Doc Entity 層級的檢索摘要

- **描述**：Doc entity 必須同時提供 `bundle_highlights` 與 `change_summary`。前者回答「這個文件集底下有哪些值得先看的文件與重點」，後者回答「最近變了什麼」。兩者都由 agent 在 capture/sync 時更新（不是 server 自動生成）。

- **欄位結構**：
  - `bundle_highlights`（index 必填，list[object]，1..5 筆）：
    - `source_id`：指向哪一份 source
    - `headline`：一句話說這份文件最值得看的點
    - `reason_to_read`：為什麼現在要先看它（例如「這是 SSOT」「這份定義 AC」「這份描述最新決策」）
    - `priority`：`primary` / `important` / `supporting`
  - `change_summary`（選填，string）：一段人話摘要，描述文件集最近的重要變化
  - `summary_updated_at`（系統管理）：change_summary 最後更新時間
  - `highlights_updated_at`（系統管理）：bundle_highlights 最後更新時間

- **使用場景範例**：
  - `bundle_highlights`
    - `SPEC-dashboard-onboarding.md` — 這是 onboarding flow 的 SSOT，定義 4 步流程與觸發/消失邏輯
    - `ADR-023-dashboard-onboarding.md` — 這份解釋 preferences JSONB、前端 overlay 與 API 選型理由
  - 「2026-04-09：新增 ADR-020 決定採用 MCP 聯邦模式，不做 content snapshot。SPEC 已更新 Phase 規劃。」
  - 「2026-04-05：客戶合約 v2 簽署完成，新增 SLA 附件。舊合約已標記 superseded。」

- **硬規則**：
  - `doc_role=index` 若沒有 `bundle_highlights`，不得視為完成治理
  - `bundle_highlights` 必須至少標出 1 份 `priority=primary` 的 source
  - `bundle_highlights` 只能引用屬於該 bundle 的 `source_id`，不得寫成游離文字清單

- **Acceptance Criteria**：
  - `AC-P0-5-1` Given agent 建立或更新 `doc_role=index` 的 entity，When write 執行，Then `bundle_highlights` 必須可被寫入與讀回
  - `AC-P0-5-2` Given index entity 缺少 `bundle_highlights`，When 該 entity 被標記為 current/active，Then 系統回傳 warning 或治理失敗提示
  - `AC-P0-5-3` Given agent 更新 doc entity 的 `change_summary`，When write 執行，Then `summary_updated_at` 自動設為當前時間
  - `AC-P0-5-4` Given agent 更新 doc entity 的 `bundle_highlights`，When write 執行，Then `highlights_updated_at` 自動設為當前時間
  - `AC-P0-5-5` Given agent 搜尋 doc entity，When search 結果回傳，Then 包含 `bundle_highlights`、`change_summary`
  - `AC-P0-5-6` Given agent 呼叫 get(doc_id)，When 回傳，Then 包含 `bundle_highlights`、`change_summary`、`summary_updated_at`、`highlights_updated_at`
  - `AC-P0-5-7` Given `change_summary` 超過 90 天未更新且 entity 有活躍的 source 變動，When analyze 執行，Then 回傳 warning「change_summary 可能過時」

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
  - 預設永遠直接建 index（即使目前只有 1 份文件）
  - 當 agent 同時 capture 同一主題的 2+ 份文件時，直接把全部 sources 收進同一個 index
  - 只有在符合 P0-1 的 single 例外條件時，才可建立 single

- **Acceptance Criteria**：
  - `AC-P0-6-1` Given agent capture 一份新 SPEC 且已存在同主題的 index entity，When 路由判斷，Then agent 選擇 `add_source` 而非建新 entity
  - `AC-P0-6-2` Given agent capture 一份新文件且沒有任何相關 doc entity，When 路由判斷，Then agent 建立新的 `index` doc entity，而不是 `single`
  - `AC-P0-6-3` Given agent 同時 capture 同一主題的 3 份文件，When 路由判斷，Then 3 份文件被收進同一個 index entity
  - `AC-P0-6-4` Given agent 不確定路由，When 路由判斷，Then agent 停止並回報用戶（不自行猜測）
  - `AC-P0-6-5` Given governance skill 已更新，When agent 讀取 `governance_guide("document")`，Then 回傳包含 bundle-first 路由規則

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

#### P0-8.1: Notion / Wiki / Generic URL URI 驗證

- **描述**：非 GitHub / GDrive 平台也必須有最小合法 URI contract，讓 doc entity 能穩定保存多平台 source。
- **驗證規則**：
  1. `notion`：必須為 `https://www.notion.so/...` 且帶 UUID
  2. `wiki`：必須為完整 `https://` view URL，不接受 `/edit`
  3. `url`：必須為完整 `https://` URL，不接受相對路徑或裸字串
- **Acceptance Criteria**：
  - Given agent 傳入不含 UUID 的 Notion URL，When `write` 執行，Then 回傳 400
  - Given agent 傳入 wiki edit URL，When `write` 執行，Then 回傳 400
  - Given agent 傳入裸字串作為 `url` 類型 source，When `write` 執行，Then 回傳 400

#### P0-9: Dashboard 外鏈跳轉與 Source 列表

- **描述**：Dashboard 在 doc entity 詳情頁顯示所有 source。對 index 類型，按 doc_type 分組顯示。每個 source 旁有平台圖標和「在 XXX 中打開」按鈕，且必須優先顯示 `bundle_highlights`，讓使用者先看懂哪些文件最重要。
- **Acceptance Criteria**：
  - `AC-P0-9-1` Given `doc_role=index` 的 entity 有 4 個 source（SPEC、DECISION、DESIGN、TEST），When Dashboard 顯示，Then 按 `doc_type` 分組展示
  - `AC-P0-9-2` Given index entity 有 `bundle_highlights`，When Dashboard 顯示，Then highlights 區塊顯示在 source 清單之前
  - `AC-P0-9-3` Given highlight 指向某個 source，When 使用者點擊 highlight，Then 打開對應 source 或 doc reader
  - `AC-P0-9-4` Given source 的 `source_status` 為 `stale`，Then 連結旁顯示警告標記
  - `AC-P0-9-5` Given source 的 `source_status` 為 `unresolvable`，Then 連結顯示為不可點擊

#### P0-10: L2 Detail 必須把 Doc Bundle 視為主要文件入口

- **描述**：每個 L2 detail 頁或右側 detail sheet，必須直接顯示掛在該 L2 下的 doc bundles。使用者不需要先知道檔名或切去 documents 頁，應能從 L2 直接看到「有哪些文件、先看哪份、SSOT 是哪份」。

- **顯示內容**：
  - bundle 標題
  - `bundle_highlights`
  - `change_summary`
  - primary source link
  - 其餘 source 計數與入口

- **硬規則**：
  - L2 detail 不得只顯示「有幾份文件」或一排外鏈；必須顯示可讀的 highlights
  - 若某 L2 掛了多個 doc bundles，必須分別顯示，避免不同主題文件混在一起

- **Acceptance Criteria**：
  - `AC-P0-10-1` Given 某個 L2 底下掛有 doc bundle，When 使用者開啟 L2 detail，Then 直接看到該 bundle 的 title、highlights、primary source
  - `AC-P0-10-2` Given bundle 有 `priority=primary` 的 highlight，When L2 detail 顯示，Then 該 highlight 以「先讀這份」或等價標示呈現
  - `AC-P0-10-3` Given 某個 L2 掛有 2 個 doc bundles，When L2 detail 顯示，Then 兩個 bundle 分開呈現，不合併為單一清單
  - `AC-P0-10-4` Given bundle 缺少 `bundle_highlights`，When L2 detail 顯示，Then 顯示治理缺口警告，而不是沉默顯示空白

#### P0-11: Knowledge Map 必須提供 L2 → Doc Bundle 的可視入口

- **描述**：知識地圖中的 L2 與 doc bundle 之間必須有穩定、可點擊的圖譜關聯。目的是讓使用者從概念節點出發時，能自然沿圖走到相關文件，而不是只能靠搜尋或 detail 面板猜。

- **圖譜要求**：
  - doc bundle 與其 primary L2 之間有穩定邊（`parent_id` 或物化 graph edge）
  - 點擊 L2 時，UI 能顯示其下 doc bundles
  - 點擊 doc bundle 時，UI 能顯示 bundle highlights 與 source links

- **Acceptance Criteria**：
  - `AC-P0-11-1` Given L2 掛有 doc bundle，When 知識地圖載入，Then 圖上存在 L2 → doc bundle 的穩定關聯
  - `AC-P0-11-2` Given 使用者從 L2 節點開啟 detail，When 點擊文件入口，Then 能進入對應 doc bundle detail
  - `AC-P0-11-3` Given 使用者從 doc bundle 節點開啟 detail，When 查看內容，Then 能看到 highlights 與 source links，而不是只有 metadata
  - `AC-P0-11-4` Given doc bundle 被移動或重分類，When ontology sync 完成，Then 圖譜邊與 detail 顯示仍與新的 primary L2 一致

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
  - `AC-P1-2-1` Given `doc_role=single` 的 entity，When agent 寫入 `doc_role=index` 並追加新 source，Then 原有 source 保留，doc_role 更新為 index
  - `AC-P1-2-2` Given 升級後的 entity，When search/get 回傳，Then 顯示完整的 sources 陣列
  - `AC-P1-2-3` Given single 升級為 index，When 升級完成，Then agent 必須補上 `bundle_highlights`

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
- **source platform rollout** — `github` 先正式支援；`gdrive` / `notion` / `wiki` 先定義 contract 與 setup_hint，後續補 reader adapter
- **doc_role 欄位** — documents 表新增 enum 欄位，預設 `single`（向後相容）
- **doc_role 欄位** — documents 表新增 enum 欄位。舊資料預設視為 `single`（向後相容）；新建流程預設使用 `index`
- **doc_type 映射** — server-side 維護新舊類別映射表，搜尋時透明展開
- **bundle_highlights 欄位** — documents 表新增 JSONB 欄位，存 source-linked highlight objects
- **change_summary 欄位** — documents 表新增 text 欄位 + timestamp
- **read_source 介面變更** — 新增可選 source_id 參數，向後相容（不帶=讀 primary）
- **write mutation 擴展** — 新增 add_source / update_source / remove_source 操作語意
- **Git URI 驗證為 server-side reject** — 不依賴 agent，server 直接拒絕
- **governance_guide("document") 更新** — 回傳內容需包含泛用類別表和路由決策樹
- **SPEC-doc-governance 需補 amendment** — 說明 L3 新增 index 子類型，不改變原有 single 行為
- **SPEC-doc-source-governance 已被吸收** — 本 spec 成為 doc entity/source platform 的單一真相來源
- **L2 detail / graph integration** — Dashboard 必須把 doc bundle 視為 L2 的文件入口，而不是 documents 頁的旁支功能

## 已決議事項（原開放問題）

1. **既有 doc entity 遷移策略** — **自然演進**，不做一次性主動合併。agent 在 capture/sync 時透過 P1-2 的 single→index 升級流程逐漸遷移。風險最低，符合漸進設計。

2. **doc_type 映射的過渡期** — **讀取永久相容**（搜尋時新舊類別都能匹配）。**寫入從 skill 層先全面改用新類別**（governance skill 引導 agent 使用新類別）。等 1-2 個 release cycle 後再考慮把舊類別寫入降成 warning，不硬砍讀相容。

3. **change_summary 的更新責任** — **不做 server 自動生成**。但在 `add_source` / `update_source` / `remove_source` / `supersede` 操作完成時，response 回傳 `suggestions` 欄位提醒 agent 更新 change_summary。agent 應在同一輪操作中更新。

## 開放問題

1. `wiki` 是否要拆成 `confluence` / `generic_wiki`，而不是維持單一泛稱？
