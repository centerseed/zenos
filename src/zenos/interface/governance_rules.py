"""ZenOS Governance Rules — server-side rule content for governance_guide MCP tool.

規則文本 hardcode 在 server 端，不讀取 local skill 文件。
更新規則只需重新部署 server。

只暴露 External 治理規則（「需要三問通過」），
不暴露 Internal 演算法（LLM 如何判斷三問的 prompt 細節）。

Structure: dict[topic][level] -> str
  topic: entity | document | bundle | task | capture | sync | remediation
  level: 1 (core summary) | 2 (full rules) | 3 (with examples)
"""

GOVERNANCE_RULES: dict[str, dict[int, str]] = {
    "entity": {
        1: """# L2 知識節點治理規則 v1.1

## 什麼是 L2 Entity
L2 Entity = 公司共識概念。改了它，不同角色（工程師、行銷、老闆）都會受影響。
不是技術模組的文件索引，而是值得被治理傳播追蹤的概念。

## Phase 1 統一回傳格式
所有 MCP 回傳改為 `{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**Server 端驗證：** `confirm` 時 Server 強制驗證 impacts≥1。`write` 回傳 `similar_items` 列出相似 entity。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates` 列出需要更新的下游 entity。

## 三問 + impacts 門檻（全通過才能建 L2）

### 三問（boolean，layer_decision 中的欄位）
1. 持久性（`q1_persistent`）：是否為公司核心持久知識？不是臨時性、不會隨某個 sprint 或文件消失
2. 跨角色（`q2_cross_role`）：是否跨角色共識？不是某個人的個人筆記，任何角色都理解
3. 全司共識（`q3_company_consensus`）：是否為經確認的公司知識？在不同情境都指向同一件事

### impacts 門檻（string，獨立驗證）
4. 影響描述（`impacts_draft`）：具體影響描述，格式「A 改了什麼 → B 的什麼要跟著看」（至少 1 條）

三問任一為 false → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問全 true 但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

## 硬規則
- 每個 L2 必須至少有 1 條具體 impacts relationship
- impacts 必須說清楚「A 改了什麼 → B 的什麼要跟著看」
- 新建 L2 一律 draft 狀態
- draft → confirmed 必須走 confirm 工具，且需通過 impacts 驗證
- 沒有 impacts 的候選概念，應降為 L3 document 或 sources

## 生命週期
draft → confirmed（三問通過 + ≥1 具體 impacts）
confirmed → stale（impacts 目標失效或過時）
stale → confirmed（重新補齊有效 impacts）

## 分層路由
- 治理規則或跨角色共識 → L2（走三問+impacts gate）
- 正式文件（SPEC/ADR）→ L3 document
- 可指派可驗收的工作 → Task
- 一次性草稿或低價值參考 → entity.sources

## 影響鏈（impact_chain）
`get(collection="entities", id=...)` 回傳中包含 `impact_chain`：
多跳 BFS 遍歷，格式 `[{from_name, type, to_name}, ...]`
- 回答「X 改了會影響什麼」時，優先讀 impact_chain，不需要逐跳手動 get
- 例：`[A --impacts--> B --enables--> C]` 代表 A 間接影響到 C""",

        2: """# L2 知識節點治理規則 v1.1（完整版）

## 什麼是 L2 Entity
L2 Entity = 公司共識概念。改了它，不同角色（工程師、行銷、老闆）都會受影響。
不是技術模組的文件索引，而是值得被治理傳播追蹤的概念。

## Phase 1 統一回傳格式
所有 MCP 回傳改為 `{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**Server 端驗證：** `confirm` 時 Server 強制驗證 impacts≥1。`write` 回傳 `similar_items` 列出相似 entity。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates` 列出需要更新的下游 entity。

## 三問 + impacts 門檻（全通過才能建 L2）

### 三問（boolean，layer_decision 中的欄位）
1. 持久性（`q1_persistent`）：是否為公司核心持久知識？不是臨時性、不會隨某個 sprint 或文件消失
2. 跨角色（`q2_cross_role`）：是否跨角色共識？不是某個人的個人筆記，任何角色都理解
3. 全司共識（`q3_company_consensus`）：是否為經確認的公司知識？在不同情境都指向同一件事

### impacts 門檻（string，獨立驗證）
4. 影響描述（`impacts_draft`）：具體影響描述，格式「A 改了什麼 → B 的什麼要跟著看」（至少 1 條）

三問任一為 false → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問全 true 但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

### 三問判斷範例

✓ 通過的案例：
- 「定價模型」：工程師、行銷、客服都理解，改了會影響文件/合約/程式碼，比任何一個 sprint 都長壽
- 「用戶信任等級」：跨角色共識，改了影響產品流程/合規要求/UI設計，隨產品成長持續存在
- 「知識捕獲分層」：全公司 agent 都依賴，改了影響所有 agent 行為，是持久的架構概念

✗ 不通過的案例：
- 「Sprint-23 auth 模組」：名稱綁定 sprint，不跨時間
- 「login.py 技術實作」：只有工程師理解，不是公司共識
- 「上週的客戶訪談筆記」：一次性資料，不會跨時間存活

## impacts 的正確寫法

具體（正確）：
- 「定價模型 改了費率算法 → 合約模板 的計費條款要重新審」
- 「用戶信任等級 新增等級 → 產品功能門檻 的解鎖條件要更新」

模糊（不正確）：
- 「定價模型 影響 合約」（缺少「改了什麼」和「要跟著看什麼」）
- 「功能 A 相關 功能 B」（「相關」不是 impacts）

## Entity Entries（附加脈絡）
每個 L2 可以有多條 entry，記錄演變脈絡：

- decision：關於這個 entity 的架構決策（≤100字）
- insight：從實際使用中萃取的洞察（≤100字）
- limitation：已知限制或注意事項（≤100字）
- change：重要的狀態變化紀錄（≤100字）
- context：補充背景資訊（≤100字）

所有 entry 限制 100 字。

## Server 硬性底線 vs 可客製化

硬性底線（server 強制）：
- write type=module 必須附 layer_decision（三問 + impacts_draft）
- 三問任一為 false → 回傳 LAYER_DOWNGRADE_REQUIRED
- 三問全 true 但 impacts_draft 空 → 回傳 IMPACTS_DRAFT_REQUIRED
- draft → confirmed 必須有 ≥1 有效 impacts

可客製化（partner 設定）：
- impacts 的詳細驗證規則
- 哪些角色可以 confirm entity
- stale 偵測的時間閾值

## 常見錯誤：技術模組降級案例

錯誤判斷 → 正確處理：
- 「auth 模組」（技術模組）→ 降為 L3 document，掛到「用戶認證架構」L2
- 「API v2」（版本標籤）→ 降為 L3 document，掛到對應的服務 L2
- 「資料庫 schema v3」→ 降為 L3 document 或 sources，掛到「資料架構」L2

## 影響鏈（impact_chain）
`get(collection="entities", id=...)` 回傳中包含 `impact_chain` key：
BFS 多跳遍歷出邊，最多 5 跳，格式 `[{from_id, from_name, type, to_id, to_name}]`

使用時機：
- 回答「X 改了會影響什麼下游」→ 直接讀 impact_chain，不需要逐跳手動 get
- 回答跨節點的問題時，先展開 impact_chain 確認語意鏈是否相關
- 例：`[A --impacts--> B --enables--> C]` 表示 A 的改動最終傳播到 C""",

        3: """# L2 知識節點治理規則 v1.1（含完整範例）

## 什麼是 L2 Entity
L2 Entity = 公司共識概念。改了它，不同角色（工程師、行銷、老闆）都會受影響。
不是技術模組的文件索引，而是值得被治理傳播追蹤的概念。

## Phase 1 統一回傳格式
所有 MCP 回傳改為 `{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**Server 端驗證：** `confirm` 時 Server 強制驗證 impacts≥1。`write` 回傳 `similar_items` 列出相似 entity。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates` 列出需要更新的下游 entity。

## 三問 + impacts 門檻（全通過才能建 L2）

### 三問（boolean，layer_decision 中的欄位）
1. 持久性（`q1_persistent`）：是否為公司核心持久知識？不是臨時性、不會隨某個 sprint 或文件消失
2. 跨角色（`q2_cross_role`）：是否跨角色共識？不是某個人的個人筆記，任何角色都理解
3. 全司共識（`q3_company_consensus`）：是否為經確認的公司知識？在不同情境都指向同一件事

### impacts 門檻（string，獨立驗證）
4. 影響描述（`impacts_draft`）：具體影響描述，格式「A 改了什麼 → B 的什麼要跟著看」（至少 1 條）

三問任一為 false → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問全 true 但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

### 三問判斷範例

✓ 通過的案例：
- 「定價模型」：工程師、行銷、客服都理解，改了會影響文件/合約/程式碼，比任何一個 sprint 都長壽
- 「用戶信任等級」：跨角色共識，改了影響產品流程/合規要求/UI設計，隨產品成長持續存在
- 「知識捕獲分層」：全公司 agent 都依賴，改了影響所有 agent 行為，是持久的架構概念

✗ 不通過的案例：
- 「Sprint-23 auth 模組」：名稱綁定 sprint，不跨時間
- 「login.py 技術實作」：只有工程師理解，不是公司共識
- 「上週的客戶訪談筆記」：一次性資料，不會跨時間存活

## 從一批文件識別 L2（全局統合模式 6 步驟）

Step 1：全局閱讀——先讀所有文件，不急著建 entity
Step 2：列出候選概念——從文件中找出反覆出現、跨角色使用的詞彙
Step 3：三問過濾——對每個候選概念跑三問，排除不通過的
Step 4：切割獨立概念——確保每個 L2 可以獨立改變（不是「某文件的 section」）
Step 5：推斷 impacts——對每個 L2 問：「它改了，哪些其他 L2 要跟著看？」
Step 6：說不出 impacts → 降為 L3 或 sources，不強行建 L2

## impacts 寫法模板（3 個完整範例）

範例 1：定價調整影響合約
```
source_entity: 訂閱定價模型
relationship_type: impacts
target_entity: 合約模板
note: 訂閱定價模型 改了費率結構或計費週期 → 合約模板 的計費條款章節需重新審核確認
```

範例 2：信任等級影響功能解鎖
```
source_entity: 用戶信任等級
relationship_type: impacts
target_entity: 功能存取控制
note: 用戶信任等級 新增或調整等級定義 → 功能存取控制 的各功能解鎖門檻需同步更新
```

範例 3：架構決策影響部署流程
```
source_entity: 服務分層架構
relationship_type: impacts
target_entity: 部署流程
note: 服務分層架構 調整層間依賴方向 → 部署流程 的服務啟動順序需重新驗證
```

## Entity Entry 範例（各 type 各一個）

decision entry：
```
type: decision
content: 決定採用三層架構（L1/L2/L3）而非扁平 entity，原因是需要不同治理強度的分層管理
```

insight entry：
```
type: insight
content: 冷啟動時「說不出 impacts」是最強的 L3 降級訊號，比三問更有判別力
```

limitation entry：
```
type: limitation
content: 跨公司的通用概念（如「客戶」）容易被建成 L2，但缺少公司特定語意，需加 summary 補充
```

change entry：
```
type: change
content: 2026-Q1 將「技術架構」拆成「服務分層架構」和「資料模型架構」兩個獨立 L2
```

context entry：
```
type: context
content: 此 entity 的命名沿用 Phase 0 決策，未來如果用語改變需更新所有 linked_entities
```

## L2 → L3 降級流程（step by step）

1. 確認降級原因（三問哪題沒過 / 說不出 impacts）
2. 建 L3 document entity，type=ADR 或 REF
3. 將原 L2 的 summary / sources 複製到 L3
4. 找到最相關的 L2，設定 ontology_entity 指向它
5. 如果原 L2 已有 confirmed 狀態，先改為 stale，說明降級原因
6. 通知相關 task 的 linked_entities 更新為新的 L3 entity

## 影響鏈（impact_chain）使用指引

### 什麼是 impact_chain
`get(collection="entities", id=...)` 回傳包含 `impact_chain`：
從該節點出發，BFS 遍歷所有出邊，最多 5 跳，回傳完整路徑。
格式：`[{from_id, from_name, type, to_id, to_name}, ...]`

### 何時使用
- 使用者問「如果 X 改了，哪些東西要跟著看？」→ 讀 impact_chain，不需逐跳 get
- 回答跨節點問題前，先檢視 impact_chain 確認語意鏈是否相關
- 建立新任務時，impact_chain 可幫助識別所有需要同步更新的下游概念

### 範例
```
impact_chain: [
  {from_name: "訂閱定價模型", type: "impacts", to_name: "Race Prediction"},
  {from_name: "Race Prediction", type: "enables", to_name: "行銷定位策略"}
]
```
代表：定價模型改動 → 影響預測計算 → 最終驅動行銷策略調整

## Server 端驗證（Phase 0.5）
- confirm entity 時，Server 會檢查是否有 ≥1 條有效 impacts relationship；不足會 reject 並回傳 IMPACTS_REQUIRED
- write entity 回傳會包含 `similar_items` 欄位（相似 entity 列表），agent 應在確認建立前先檢查是否重複
- 支援 `supersedes` 欄位，可在 write 時原子取代既有 entity（新建 + 標記舊 entity 為 superseded 一次完成）""",
    },

    "document": {
        1: """# L3 文件治理規則 v2.0

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 必要欄位
- title: 文件標題
- type: 11 種泛用類別之一（見下方分類說明）
- source.uri: 文件的存放位置（GitHub URL、Google Drive 連結、Notion URL 等）
- ontology_entity: 掛載到哪個 L2 entity 的名稱
- status: draft / under_review / approved / superseded / archived

## 11 種泛用文件類別
| 類別 | 用途 | 軟體範例 | 非軟體範例 |
|------|------|---------|-----------|
| SPEC | 需求/規格（what + why） | Feature Spec | 採購規格書、產品需求文件 |
| DECISION | 決策紀錄（why this choice） | ADR | 供應商選型紀錄、策略決策備忘 |
| DESIGN | 設計文件（how） | 技術設計文件 | 流程設計、組織架構設計 |
| PLAN | 計畫/排程 | Sprint Plan | 行銷活動企劃、專案時程表 |
| REPORT | 報告/分析 | 效能分析報告 | 月報、競品分析、市場調研 |
| CONTRACT | 合約/協議 | API 合約 | 服務合約、NDA、合作備忘錄 |
| GUIDE | 指南/手冊/SOP | Playbook | 新人手冊、操作 SOP、品管手冊 |
| MEETING | 會議紀錄 | 架構討論紀錄 | 董事會紀錄、部門週會紀錄 |
| REFERENCE | 參考資料 | 競品技術分析 | 法規摘要、產業白皮書 |
| TEST | 測試文件 | Test Case | 品質檢驗標準、驗收清單 |
| OTHER | 不屬於以上類別 | Script 文件 | 其他 |

Legacy 別名（自動轉換）：ADR→DECISION, TD→DESIGN, TC→TEST, PB→GUIDE, REF→REFERENCE

## doc_role: single vs index
- **index**（預設）：文件本身是多個 source 的索引；即使目前只有 1 個 source 也合法
- **single**（例外）：文件本身就是獨立治理單位
- 不得因為「現在只有一份文件」就直接建 single
- 同一個 L2 主題的正式文件，預設應收斂到同一個 index
- index 文件在 Dashboard 按 doc_type 分組顯示 sources，且優先顯示 bundle_highlights

## 生命週期
draft → under_review → approved（正式文件）
approved → superseded（被新版取代時，保留原文件，建立指向）
任何狀態 → archived（廢棄）

## 硬規則
- 每份文件必須掛載到至少一個 L2 entity（ontology_entity 必填）
- MCP payload 寫 document 時，`linked_entity_ids` 必填；第一個 ID 映射為 primary parent
- source.uri 必填（沒有 URI 的文件不值得建 entity）
- supersede 時必須更新被取代文件的 status 並指向新版

## Capture/Sync 路由決策樹
1. 收到一份新文件 → 用 search 查重
2. 已有 index entity？→ 加為新 source（走 write per-source 操作），並更新 bundle_highlights
3. 已有 single entity？→ 預設升級為 index，再加新 source
4. 無既有 entity？→ 判斷類別（11 類），預設建新 index document entity
5. 檔案已刪除/改名？→ 更新 source_status（stale / unresolvable）""",

        2: """# L3 文件治理規則 v2.0（完整版）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 必要欄位
- title: 文件標題
- type: 11 種泛用類別之一（SPEC/DECISION/DESIGN/PLAN/REPORT/CONTRACT/GUIDE/MEETING/REFERENCE/TEST/OTHER）
- source.uri: 文件的存放位置（GitHub URL、Google Drive 連結、Notion URL 等）
- ontology_entity: 掛載到哪個 L2 entity 的名稱
- status: draft / under_review / approved / superseded / archived

## 完整 Frontmatter 格式
```yaml
---
doc_id: SPEC-feature-name          # 唯一 ID（格式：類別-描述）
title: 功能規格：功能名稱
type: SPEC                          # 11 種類別之一
ontology_entity: L2 Entity 名稱     # 掛載的 L2 entity
status: draft                       # draft|under_review|approved|superseded|archived
version: "0.1"
date: 2026-01-01
supersedes: null                    # 被此文件取代的文件 ID（如有）
---
```

**Phase 1 統一回傳格式：** 所有回傳改為 `{status, data, warnings, suggestions, similar_items, ...}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**重複文件檢查：** `write` 回傳 `similar_items` 列出相近的既有文件。建立前應檢查避免重複。

**原子取代：** 建立新版文件時，可在 `write` 的 data 中同時填入 `supersedes` 欄位，Server 會原子性地將舊文件標為 superseded，省去手動更新舊 entity 的步驟。

**關聯要求：** `write(collection="documents")` 時 `linked_entity_ids` 必填；缺少或空陣列應 reject，先 search 正確的 entity IDs 再重試。

## 11 種泛用文件類別（詳細）
| 類別 | 用途 | 面向 | 選型準則 |
|------|------|------|---------|
| SPEC | 需求/規格 | 產品 | 定義「做什麼」和「為什麼做」 |
| DECISION | 決策紀錄 | 治理 | 記錄「為什麼選這個方案」，可被 supersede |
| DESIGN | 設計文件 | 實作 | 說明「怎麼做」，component 架構、流程設計 |
| PLAN | 計畫/排程 | 管理 | 時程、milestone、資源分配 |
| REPORT | 報告/分析 | 資訊 | 狀態報告、分析結果、回顧 |
| CONTRACT | 合約/協議 | 法務 | 有約束力的文件、SLA、API contract |
| GUIDE | 指南/SOP | 操作 | 操作手冊、新人指南、Playbook |
| MEETING | 會議紀錄 | 溝通 | 會議決議、行動項目 |
| REFERENCE | 參考資料 | 研究 | 不可修改的外部參考、法規、白皮書 |
| TEST | 測試文件 | 品質 | Test case、驗收標準、品質檢驗清單 |
| OTHER | 其他 | - | 不屬於以上類別 |

選型準則：看受眾和目的，不看篇幅。一份短的「為什麼」= DECISION，長的「怎麼做」= DESIGN。

### Legacy 別名（自動轉換）
舊類別會自動對應到新類別：ADR→DECISION, TD→DESIGN, TC→TEST, PB→GUIDE, REF→REFERENCE。
搜尋時會自動展開（搜 ADR 也會找到 DECISION，反之亦然）。

## doc_role: single vs index（ADR-022 Document Bundle）

### 概念
- **index**（預設）：文件本身是多個 source 的索引/集合，即使目前只有 1 個 source 也合法
- **single**（例外）：文件有一個主要 source，且文件本身就是獨立治理單位
  - 例：「產品文件集」包含 SPEC + DESIGN + TEST 三類文件
  - 例：「合規文件包」包含 CONTRACT + REFERENCE + GUIDE

### single → index 升級流程
觸發條件：single 新增第 2 份同主題正式文件，或已成為某個 L2 的主文件入口
```
write(collection="documents", data={
    "doc_id": "existing-doc-id",
    "doc_role": "index"
})
```

### Dashboard 顯示差異
- single：平面 source 列表
- index：按 doc_type 分組顯示 sources（SPEC 區、DESIGN 區、TEST 區...）

## 生命週期
draft → under_review → approved（正式文件）
approved → superseded（被新版取代時，保留原文件，建立指向）
任何狀態 → archived（廢棄）

## Supersede 流程細節
1. 建立新版文件（新 doc_id，status=draft）
2. 新文件 frontmatter 加 supersedes: 舊文件 ID
3. 舊文件 status 更新為 superseded
4. 在 ZenOS 建 relationship：新文件 supersedes 舊文件
5. 保留舊文件（不刪除），讓歷史可追溯

## Stale 偵測規則
文件可能過時的訊號：
- approved 文件已超過 90 天未被 review
- 掛載的 L2 entity 已變為 stale 狀態
- 相關 task 的 result 顯示文件描述的行為已改變
- git log 顯示實作已大幅偏離文件描述
- source_status 變為 stale 或 unresolvable

偵測到 stale 時：建 task 要求 review，tag 文件為 under_review。

## Capture/Sync 路由決策樹（完整）
```
收到一份文件
    ↓
1. search(collection="documents", query="文件主題") 查重
    ↓
2a. 找到既有 document entity
    → 若是 index：加為新 source，並更新 bundle_highlights
    → 若是 single：預設升級為 index，再加新 source
    ↓
2b. 無既有 entity
    → 判斷類別（11 類 + legacy 別名自動轉換）
    → write(collection="documents", data={doc_role:"index", ...}) 建新 entity
    → 補 bundle_highlights
    ↓
3. 檔案已刪除/改名？
    → 更新 source_status：stale（暫時不可達）或 unresolvable（確認已刪除）
    → 唯一 source 且 unresolvable → 文件 status 改為 archived
```

## Batch Sync 操作說明
從 git log 批量同步文件狀態：
1. 掃描 git log，找出最近修改的文件
2. 比對 ZenOS 中對應 document entity 的 status
3. 如果 git 文件有新 commit 但 ZenOS status 仍是 draft → 建議更新為 under_review
4. 如果 git 文件已刪除但 ZenOS 仍 approved → 標記為 archived

## Source 稽核規則

### source.label 規範
- **必須是實際檔名**，例如 `SPEC-agent-system.md`、`ADR-007-entity-architecture.md`
- **不可只寫 type**：`"github"` 是無意義的 label，Dashboard 顯示時毫無資訊量
- 若 label 為空或等於 type 名稱（如 "github"），視為 `bad_label`，應從 URI 尾段提取正確檔名

提取規則：取 URI 最後一個 `/` 之後的部分作為 label。

### source.uri 規範
- 必須指向**有效的檔案位置**，不可指向已刪除或已改名的路徑
- 對 `type=github` 的 source，可用 `git ls-files` 驗證路徑是否存在
- 若檔案已改名，應更新 URI 為新路徑
- 若檔案已刪除且無改名記錄，應標記為 broken 並等用戶確認後才移除

### source_status 欄位
- **valid**（預設）：source 可正常存取
- **stale**：source 可能過時（偵測到但尚未確認）
- **unresolvable**：source 確認不可達（已刪除、連結失效）

### 稽核觸發時機
每次執行 `/zenos-sync` 時，**Step 0: Source Audit 預設自動執行**。
若只想執行稽核而不做增量同步，使用 `/zenos-sync --audit`。""",

        3: """# L3 文件治理規則 v2.0（含完整範例）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 各文件類別完整範例 Frontmatter

### 軟體專案範例

SPEC 範例：
```yaml
---
doc_id: SPEC-governance-framework
title: 功能規格：治理框架
type: SPEC
ontology_entity: 知識治理框架
status: approved
version: "1.0"
date: 2026-02-15
supersedes: null
---
```

DECISION 範例（取代原 ADR）：
```yaml
---
doc_id: DECISION-entity-architecture
title: 決策紀錄：Entity 三層模型
type: DECISION
ontology_entity: 知識節點架構
status: approved
version: "1.0"
date: 2026-01-20
supersedes: DECISION-entity-flat-model
---
```

DESIGN 範例（取代原 TD）：
```yaml
---
doc_id: DESIGN-three-layer-arch
title: 技術設計：三層架構實作
type: DESIGN
ontology_entity: 服務分層架構
status: under_review
version: "0.3"
date: 2026-03-01
supersedes: null
---
```

### 非軟體專案範例

PLAN 範例（行銷企劃）：
```yaml
---
doc_id: PLAN-q2-launch
title: Q2 產品上市企劃
type: PLAN
ontology_entity: 產品上市策略
status: approved
version: "1.0"
date: 2026-03-15
---
```

CONTRACT 範例（合作協議）：
```yaml
---
doc_id: CONTRACT-vendor-sla
title: 供應商服務水準協議
type: CONTRACT
ontology_entity: 供應商管理
status: approved
version: "2.0"
date: 2026-02-01
supersedes: CONTRACT-vendor-sla-v1
---
```

MEETING 範例：
```yaml
---
doc_id: MEETING-2026-03-board
title: 2026-03 董事會紀錄
type: MEETING
ontology_entity: 公司治理
status: approved
version: "1.0"
date: 2026-03-28
---
```

**Phase 1 統一回傳格式：** 所有回傳改為 `{status, data, warnings, suggestions, similar_items, ...}`。

**重複文件檢查：** `write` 回傳 `similar_items` 列出相近的既有文件。建立前應檢查避免重複。

**原子取代：** 建立新版文件時，可在 `write` 的 data 中同時填入 `supersedes` 欄位。

## Legacy 別名（自動轉換）
舊類別自動對應新類別：
- ADR → DECISION（搜尋 ADR 也會找到 DECISION，反之亦然）
- TD → DESIGN
- TC → TEST
- PB → GUIDE
- REF → REFERENCE
- SC 無固定映射，歸入 OTHER 或自訂

## doc_role: single vs index（ADR-022 Document Bundle）

### 概念
- **index**（預設）：文件是多個 source 的索引/集合，即使目前只有 1 個 source 也合法
- **single**（例外）：文件有一個主要 source，且文件本身就是獨立治理單位

### 建立 index 文件範例
```
write(
  collection="documents",
  data={
    "doc_id": "INDEX-product-docs",
    "title": "產品文件集",
    "type": "REFERENCE",
    "doc_role": "index",
    "ontology_entity": "產品知識",
    "source": [
      {"uri": "docs/specs/SPEC-pricing.md", "type": "github", "doc_type": "SPEC"},
      {"uri": "docs/design/DESIGN-pricing-impl.md", "type": "github", "doc_type": "DESIGN"},
      {"uri": "https://docs.google.com/...", "type": "google_drive", "doc_type": "REPORT"}
    ]
  }
)
```

### single → index 升級
觸發條件：single 新增第 2 份同主題正式文件，或已成為某個 L2 的主文件入口
```
write(collection="documents", data={
    "doc_id": "existing-doc-id",
    "doc_role": "index"
})
```

## Supersede 操作步驟（完整流程）

情境：DECISION-007 取代了 DECISION-003

Step 1：在文件系統建立新文件，frontmatter 加 supersedes
Step 2：在 ZenOS 建 document entity（原子取代）：
```
write(
  collection="documents",
  data={
    "doc_id": "DECISION-entity-architecture",
    "title": "決策紀錄：Entity 三層模型",
    "type": "DECISION",
    "ontology_entity": "知識節點架構",
    "status": "approved",
    "source": {"uri": "docs/decisions/DECISION-entity-architecture.md"},
    "supersedes": "DECISION-entity-flat-model"
  }
)
```
Server 自動將舊文件 status 標為 superseded。

## Capture/Sync 路由決策樹

```
收到一份文件
    ↓
1. search(collection="documents", query="文件主題") 查重
    ↓
2a. 找到既有 document entity
    → 若是 index：加為新 source，並更新 bundle_highlights
    → 若是 single：預設升級為 index，再加新 source
    ↓
2b. 無既有 entity
    → 判斷類別（11 類 + legacy 別名自動轉換）
    → write(collection="documents", data={doc_role:"index", ...}) 建新 entity
    → 補 bundle_highlights
    ↓
3. 檔案已刪除/改名？
    → stale：暫時不可達（可能本地 repo 落後）
    → unresolvable：確認已永久刪除
    → 唯一 source 且 unresolvable → 文件 status 改為 archived
```

## 從 git log 同步 document 狀態的流程

```
1. git log --name-only --since="30 days ago" -- "docs/**/*.md"
   → 找出最近 30 天修改的文件

2. 對每個修改的文件：
   a. 讀取 frontmatter 取得 doc_id 和 type
   b. search(collection="documents", query=doc_id) 找對應 entity
   c. 比對：
      - git 有修改 + ZenOS status=draft → 建議 under_review
      - git 有新文件 + ZenOS 無 entity → 建議建立 entity
      - git 文件已刪除 + ZenOS status=approved → 建議 archived

3. batch write 更新
```

## 常見陷阱

陷阱 1：把 L2 entity 的 summary 當 document
→ summary 是概念描述，不是文件。文件必須有 source.uri。

陷阱 2：不設 ontology_entity
→ 每份文件都是某個 L2 概念的具體化。找不到 L2？先建 L2 再掛文件。
→ 例外：REFERENCE 的 ontology_entity 可為 null（唯一例外）。

陷阱 3：supersede 時刪除舊文件
→ 不刪除，改 status=superseded。歷史決策需要可追溯。

陷阱 4：用舊類別名稱建立文件
→ 可以用（ADR/TD/TC/PB/REF），server 會自動轉換為 canonical 類別。
→ 但建議直接用新類別名稱，保持一致性。

陷阱 5：index 文件不設 doc_type
→ index 文件的每個 source 應設 doc_type，讓 Dashboard 能正確分組顯示。

## Source 稽核規則

### source.label 規範
- **必須是實際檔名**，不可只寫 type
- 若 label 為空或等於 type 名稱，從 URI 尾段提取

### source.uri 規範
- 必須指向有效檔案位置
- 對 `type=github` 的 source，可用 `git ls-files` 驗證
- 已刪除→標記 broken，等用戶確認後才移除

### source_status 欄位
- **valid**（預設）：source 可正常存取
- **stale**：source 可能過時
- **unresolvable**：source 確認不可達

### 稽核觸發時機
每次 `/zenos-sync` 自動執行 Source Audit。
`/zenos-sync --audit` 只做稽核不做增量同步。""",
    },

    "task": {
        1: """# Task 治理規則 v2.0

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。
每個 task 必須連結回 ontology（linked_entities），讓執行者自動獲得相關 context。

## Phase 1 統一回傳格式
所有回傳改為 `{status, data, warnings, suggestions, ...}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**Server 端驗證：** Server 驗證 title 長度（≥4 字元）並拒絕停用詞開頭。`linked_entities` 不存在的 ID 直接 reject（不再靜默忽略）。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates`。`confirm` 成功後回傳包含 `suggested_actions` 欄位，列出後續建議動作。

## 建票最小規範
- title: 動詞開頭（「實作 X」「設計 Y」「修復 Z」）
- description: 包含背景、問題、期望結果三段
- acceptance_criteria: 2-5 條，每條可獨立驗收
- linked_entities: 1-3 個相關 entity（最重要的 L2 必須在其中）
- plan_id + plan_order: 如果屬於某個計畫，必填
- dispatcher: 派工對象，namespace `human[:<id>] | agent:<role>`（2026-04-19 升級）
- parent_task_id: 若為 subtask，必帶 parent ID 且繼承 parent.plan_id（2026-04-19 升級）

## 建票前 10 題 checklist（2026-04-19 擴充自舊 8 題）
1. 這件事真的是 task，不是 spec / blindspot / doc update 嗎？
2. 這張票只有一個主要 outcome 嗎？
3. 這張票有清楚 owner / assignee / dispatcher 嗎？
4. 這張票能用 2-5 條 acceptance_criteria 驗收嗎？
5. `linked_entities` 真的是最相關的 1-3 個節點嗎？
6. title 是否動詞開頭且描述單一行動？
7. description 是否交代背景、問題、期望結果？
8. todo / in_progress / review 中確認沒有重複票嗎？
9. **這是不是該開 subtask 而非新 task？**（若屬於既有 parent task 的同 plan 子單位 → 用 `parent_task_id`，不要另起 plan）
10. **dispatcher 有沒有依 namespace 規則填對？**（`human` / `human:<id>` / `agent:<role>` 正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`）

若有 2 題以上答案為否，不應直接建票。

## 狀態流（2026-03-31）
todo → in_progress → review → done
任何活躍狀態 → cancelled
（不使用 blocked/backlog/archived 狀態；阻塞資訊改用 blocked_by/blocked_reason）

## 欄位責任
- created_by：owner 的 partner.id（MCP 由 API key context 決定）
- assignee：執行者 partner.id（可空，但需有明確責任落點）
- updated_by：最後更新者 partner.id（create 時預設 = created_by）

## 驗收規則
- 完成後必須更新 result 欄位（status=review 時必填）
- done 狀態只能透過 confirm 工具達成
- 知識反饋：task 完成後，從 result 中萃取的 entry/blindspot 應寫回 ontology
- confirm 預設開放給所有 partner key，操作會記錄 updated_by 和 audit log
- 知識反饋：confirm 時可通過 entity_entries 參數直接回寫 entry 到 linked entities

## 禁止行為
- title 不動詞開頭
- description 缺少背景/問題/期望結果
- linked_entities 為空
- 完成後不更新 result""",

        2: """# Task 治理規則 v2.0（完整版）

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。
每個 task 必須連結回 ontology（linked_entities），讓執行者自動獲得相關 context。

## Phase 1 統一回傳格式
所有回傳改為 `{status, data, warnings, suggestions, ...}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**Server 端驗證：** Server 驗證 title 長度（≥4 字元）並拒絕停用詞開頭。`linked_entities` 不存在的 ID 直接 reject（不再靜默忽略）。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates`。`confirm` 成功後回傳包含 `suggested_actions` 欄位，列出後續建議動作。

## 建票最小規範
- title: 動詞開頭（「實作 X」「設計 Y」「修復 Z」）
- description: 包含背景、問題、期望結果三段
- acceptance_criteria: 2-5 條，每條可獨立驗收
- linked_entities: 1-3 個相關 entity（最重要的 L2 必須在其中）
- plan_id + plan_order: 如果屬於某個計畫，必填
- dispatcher: 派工對象，namespace `human[:<id>] | agent:<role>`（2026-04-19 升級）
- parent_task_id: 若為 subtask，必帶 parent ID 且繼承 parent.plan_id（2026-04-19 升級）

## 建票前 10 題 checklist（2026-04-19 擴充自舊 8 題）
1. 這件事真的是 task，不是 spec / blindspot / doc update 嗎？
2. 這張票只有一個主要 outcome 嗎？
3. 這張票有清楚 owner / assignee / dispatcher 嗎？
4. 這張票能用 2-5 條 acceptance_criteria 驗收嗎？
5. `linked_entities` 真的是最相關的 1-3 個節點嗎？
6. title 是否動詞開頭且描述單一行動？
7. description 是否交代背景、問題、期望結果？
8. todo / in_progress / review 中確認沒有重複票嗎？
9. **這是不是該開 subtask 而非新 task？**（若屬於既有 parent task 的同 plan 子單位 → 用 `parent_task_id`，不要另起 plan）
10. **dispatcher 有沒有依 namespace 規則填對？**（`human` / `human:<id>` / `agent:<role>` 正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`）

若有 2 題以上答案為否，不應直接建票。

## plan_id / plan_order 規則
- plan_id：所屬計畫的 ID。一個計畫通常對應一個 milestone 或 sprint
- plan_order：此 task 在計畫中的執行順序（整數，從 1 開始）
- 沒有 plan 的 task 可以省略，但有 plan_id 時 plan_order 必填
- plan_order 決定 Kanban 的排列順序，也是 AI 優先級推薦的參考

## 狀態流（2026-03-31）
todo → in_progress → review → done
任何活躍狀態 → cancelled
（不使用 blocked/backlog/archived 狀態；阻塞資訊改用 blocked_by/blocked_reason）

## 欄位責任
- created_by：owner 的 partner.id（MCP 由 API key context 決定）
- assignee：執行者 partner.id（可空，但需有明確責任落點）
- updated_by：最後更新者 partner.id（create 時預設 = created_by）

## 驗收規則
- status=review 時 result 必填
- result 格式：描述做了什麼、驗證了什麼、遇到什麼問題
- done 狀態只能透過 confirm 工具達成（不能直接 write status=done）
- confirm 時 QA/reviewer 必須確認每條 acceptance_criteria 都已達成

## 確認授權（預設策略）
- 預設：任何持有有效 partner key 的 agent 都可以 confirm 任何 task
- confirm 時 `updated_by` 會自動記錄執行者的 partner.id
- 所有 confirm 操作都有 audit log（event_type="task.confirm"）
- 建議最佳實踐：task creator 不應 confirm 自己的 task（自己寫自己驗 = 沒有驗）

## 知識反饋閉環
Task 完成後的知識應流回 ontology：
1. 萃取 insight：從 result 中找出值得記錄的技術洞察
2. 寫回 entity entry：可在 confirm 時通過 entity_entries 參數一併提交，
   或事後用 write(collection="entries", ...) 單獨寫入
3. 記錄 blindspot：如果過程中發現未知的未知，可在 confirm 時通過 new_blindspot 參數提交
4. 更新相關 L2：如果 task 改變了某個概念的語意，更新 entity summary

## AI 優先級推薦邏輯
系統根據以下因素自動推薦任務優先順序：
- plan_order（計畫中的順序）
- 與被阻塞依賴（blocked_by）的關係
- linked_entities 的 staleness（對應 L2 是否過時）
- 上次更新時間（越久未動越往前排）
推薦結果僅供參考，人類可覆蓋。

## Server 端驗證（Phase 0.5 / Phase 1）
- Task title 必須 ≥4 字元，且不能以名詞性停用詞開頭（如「的」「一個」等）；不符合會被 Server reject
- linked_entities 中的 entity ID 必須實際存在；任何不存在的 ID 會被 Server reject 並回傳錯誤列表（不再靜默忽略）
- confirm task 回傳會包含 `suggested_actions` 欄位，列出後續建議操作（如知識回寫、關聯 task）

## 各角色操作時機速查

| 角色 | 時機 | 操作 |
|------|------|------|
| PM | 開 Feature Spec 完 | `task(action="create", dispatcher="agent:pm", linked_entities=[...])` |
| PM | Spec ready | `task(action="handoff", to_dispatcher="agent:architect", reason="spec ready", output_ref="<spec path>")` |
| Architect | 接手開 TD / subtask | `task(action="create", parent_task_id=<parent>, dispatcher="agent:architect")`（subtask 必須繼承 parent.plan_id） |
| Architect | TD ready | `task(action="handoff", to_dispatcher="agent:developer", output_ref="<TD path>")` |
| Developer | 拿到任務 | `task(action="update", status="in_progress")` |
| Developer | 完成實作 | `task(action="handoff", to_dispatcher="agent:qa", output_ref="<commit SHA>")`（status 自動升 review） |
| QA | PASS | `confirm(collection="tasks", accept=True, ...)`（自動 append 結束 handoff event + status=done） |
| QA | FAIL | `task(action="handoff", to_dispatcher="<上一 dispatcher>", reason="rejected: ...")` |

## 2026-04-19 Action-Layer 升級硬約束

三條 Server 端強制執行，任一違反直接 reject：

**DISPATCHER_NAMESPACE**：`dispatcher` 與 `to_dispatcher` 必須符合正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`。
- 合法：`human`、`human:barry`、`agent:pm`、`agent:architect`、`agent:developer`、`agent:qa`
- 不合法：`AGENT:PM`、`agent:pm!`、自由字串
- 違反 → `error_code=INVALID_DISPATCHER`

**CROSS_PLAN_SUBTASK**：`parent_task_id` 存在時，subtask 的 `plan_id` 必須等於 parent 的 `plan_id`。
- 設計理由：subtask 是同 plan 內的獨立可驗收子單位，不是跨 plan 的組合器；不允許跨 plan 確保粒度收斂
- 違反 → `error_code=CROSS_PLAN_SUBTASK`
- Parent 不存在 → `error_code=PARENT_NOT_FOUND`

**HANDOFF_EVENTS_READONLY**：`task(action="create" | "update")` 的 `data` 中若包含 `handoff_events` 欄位，server 強制忽略並回 warning。
- 唯一合法 append 入口：`task(action="handoff", ...)`，server 原子操作
- 違反 → warning `HANDOFF_EVENTS_READONLY`（不 reject，但變更不會生效）

## Handoff 履歷（append-only）

`handoff_events` 是 task 的 audit trail——從 PM → Architect → Developer → QA 的完整派工記錄。
每次 `task(action="handoff")` 自動 append 一條事件：
- `at` / `from_dispatcher` / `to_dispatcher` / `reason` / `output_ref` / `notes`

讀取歷史：`get(collection="tasks", id=X).handoff_events`

副作用：
- `to_dispatcher="agent:qa"` 且當前 status=in_progress → 自動升 status=review
- `confirm(accepted=true)` → 自動 append 結束事件 `{to="human", reason="accepted", output_ref=entity_ids}`
- `confirm(accepted=false)` → 自動 append `{to=<前一 dispatcher>, reason="rejected: ..."}` + status 回 in_progress""",

        3: """# Task 治理規則 v2.0（含完整範例）

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。

## 建票範例：好 vs 不好的對比

### 不好的建票
```
title: auth 修改
description: 改一下 auth 相關的東西
acceptance_criteria: 完成
linked_entities: []
```
問題：title 沒動詞、description 缺三段結構、AC 不可驗收、linked_entities 空

### 好的建票
```
title: 實作 JWT refresh token 自動輪換
description: |
  背景：目前 JWT token 有效期 24 小時，用戶需要頻繁重新登入。
  問題：長期有效的 token 如果被竊取，攻擊視窗過大。
  期望結果：access token 有效期縮短為 1 小時，refresh token 自動輪換，
           用戶體驗不受影響。
acceptance_criteria:
  - access token 有效期為 1 小時，超過後自動使用 refresh token 換新
  - refresh token 使用後立即失效（one-time use）
  - 前端無感刷新（用戶不需要重新登入）
  - 所有 token 輪換操作有 audit log
linked_entities: ["用戶認證架構", "資安合規要求"]
plan_id: "plan-q1-security"
plan_order: 3
```

## 知識反饋範例（從 result 萃取 entry 的流程）

完成後的 result：
```
實作了 JWT refresh token 輪換。遇到問題：Redis 在 Cloud Run 無狀態環境下
需要特別處理 token 黑名單。最終採用 short-lived token + DB 記錄已用 token 方案。
性能影響：每次 refresh 多一次 DB 查詢，p99 增加 20ms，可接受。
```

從 result 萃取並寫回 ontology：

insight entry：
```
write(
  collection="entity_entries",
  data={
    "entity_name": "用戶認證架構",
    "type": "insight",
    "content": "Cloud Run 無狀態環境不適合 Redis token 黑名單，改用 DB 記錄已用 token，p99 增加 20ms"
  }
)
```

limitation entry：
```
write(
  collection="entity_entries",
  data={
    "entity_name": "用戶認證架構",
    "type": "limitation",
    "content": "每次 token refresh 需 DB 查詢，高頻刷新場景需要監控"
  }
)
```

## Plan 結構範例

計畫通常對應一個 milestone，tasks 按 plan_order 排序：

```
plan_id: "plan-q1-security"
plan_name: Q1 資安強化

plan_order 1: 審查現有 auth 流程（linked: 用戶認證架構）
plan_order 2: 建立資安 checklist（linked: 資安合規要求）
plan_order 3: 實作 JWT refresh token 輪換（linked: 用戶認證架構, 資安合規要求）
plan_order 4: 滲透測試與修復（linked: 資安合規要求）
plan_order 5: 更新 auth 架構文件（linked: 用戶認證架構）
```

## 禁止行為（含說明）

| 禁止行為 | 原因 |
|---------|------|
| title 不動詞開頭 | 無法快速判斷要做什麼 |
| description 缺三段結構 | 執行者缺少背景，容易做錯方向 |
| linked_entities 為空 | 切斷 task 與知識層的連結，失去 ontology 價值 |
| 完成後不更新 result | 知識無法流回 ontology，形成知識黑洞 |
| 直接 write status=done | 繞過驗收流程，AC 可能未達成 |

## Phase 1 統一回傳格式
所有回傳改為 `{status, data, warnings, suggestions, ...}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

**Server 端驗證：** Server 驗證 title 長度（≥4 字元）並拒絕停用詞開頭。`linked_entities` 不存在的 ID 直接 reject（不再靜默忽略）。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates`。`confirm` 成功後回傳包含 `suggested_actions` 欄位，列出後續建議動作。

## 各角色操作時機速查

| 角色 | 時機 | 操作 |
|------|------|------|
| PM | 開 Feature Spec 完 | `task(action="create", dispatcher="agent:pm", linked_entities=[...])` |
| PM | Spec ready | `task(action="handoff", to_dispatcher="agent:architect", reason="spec ready", output_ref="<spec path>")` |
| Architect | 接手開 TD / subtask | `task(action="create", parent_task_id=<parent>, dispatcher="agent:architect")`（subtask 必須繼承 parent.plan_id） |
| Architect | TD ready | `task(action="handoff", to_dispatcher="agent:developer", output_ref="<TD path>")` |
| Developer | 拿到任務 | `task(action="update", status="in_progress")` |
| Developer | 完成實作 | `task(action="handoff", to_dispatcher="agent:qa", output_ref="<commit SHA>")`（status 自動升 review） |
| QA | PASS | `confirm(collection="tasks", accept=True, ...)`（自動 append 結束 handoff event + status=done） |
| QA | FAIL | `task(action="handoff", to_dispatcher="<上一 dispatcher>", reason="rejected: ...")` |

## 2026-04-19 Action-Layer 升級硬約束

三條 Server 端強制執行，任一違反直接 reject：

**DISPATCHER_NAMESPACE**：`dispatcher` 與 `to_dispatcher` 必須符合正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`。
- 合法：`human`、`human:barry`、`agent:pm`、`agent:architect`、`agent:developer`、`agent:qa`
- 不合法：`AGENT:PM`、`agent:pm!`、自由字串
- 違反 → `error_code=INVALID_DISPATCHER`

**CROSS_PLAN_SUBTASK**：`parent_task_id` 存在時，subtask 的 `plan_id` 必須等於 parent 的 `plan_id`。
- 設計理由：subtask 是同 plan 內的獨立可驗收子單位，不是跨 plan 的組合器；不允許跨 plan 確保粒度收斂
- 違反 → `error_code=CROSS_PLAN_SUBTASK`
- Parent 不存在 → `error_code=PARENT_NOT_FOUND`

**HANDOFF_EVENTS_READONLY**：`task(action="create" | "update")` 的 `data` 中若包含 `handoff_events` 欄位，server 強制忽略並回 warning。
- 唯一合法 append 入口：`task(action="handoff", ...)`，server 原子操作
- 違反 → warning `HANDOFF_EVENTS_READONLY`（不 reject，但變更不會生效）

## Handoff 履歷（append-only）

`handoff_events` 是 task 的 audit trail——從 PM → Architect → Developer → QA 的完整派工記錄。
每次 `task(action="handoff")` 自動 append 一條事件：
- `at` / `from_dispatcher` / `to_dispatcher` / `reason` / `output_ref` / `notes`

讀取歷史：`get(collection="tasks", id=X).handoff_events`

副作用：
- `to_dispatcher="agent:qa"` 且當前 status=in_progress → 自動升 status=review
- `confirm(accepted=true)` → 自動 append 結束事件 `{to="human", reason="accepted", output_ref=entity_ids}`
- `confirm(accepted=false)` → 自動 append `{to=<前一 dispatcher>, reason="rejected: ..."}` + status 回 in_progress""",
    },

    "bundle": {
        1: """# L3 Document Bundle 規則 v1.0

## bundle-first 原則
- 新建 document 預設 `doc_role=index`
- 同一主題的正式文件應收斂到同一個 bundle，不再平行建多個 single
- index 必須帶 `bundle_highlights`

## 最低要求
- `bundle_highlights` 至少 1 筆，且至少 1 筆 `priority=primary`
- highlight 只能引用本 bundle 的 `source_id`
- 從 L2 detail 應直接看到 bundle_highlights 與 primary source""",
        2: """# L3 Document Bundle 規則 v1.0（完整版）

## bundle-first 原則
- 新建 document 預設 `doc_role=index`
- 同一主題的正式文件，優先 `add_source` 到既有 index bundle
- `single` 僅保留例外模式，不再是預設

## bundle_highlights 最低要求
- index 必須帶 `bundle_highlights`
- 至少 1 筆 `priority=primary`
- highlight 只能引用該 bundle 內的 `source_id`
- 缺少 highlights 時，不得視為治理完成

## capture / sync 路由
- 已有同主題 index entity → `add_source`
- 沒有相關 bundle → 建新 `index`
- 若不確定是否同主題 → 停下來回報，不自行猜測

## Server 行為
- write(add_source) / write(update_source) / write({sources:[...]}) 只回 deterministic `bundle_highlights_suggestion`
- Server 不得用 LLM 生成 `bundle_highlights` 或 `change_summary`
- `change_summary` / `bundle_highlights` 的語意內容由 agent 產生後寫回""",
        3: """# L3 Document Bundle 規則 v1.0（含範例）

## 路由範例
- 新增同主題 SPEC：找到既有 index bundle → `add_source`
- single 升級：當同主題第二份正式文件出現 → 升級為 `index` 並補 `bundle_highlights`

## highlights 範例
```
bundle_highlights:
  - source_id: src-spec
    headline: SPEC-pricing.md
    reason_to_read: 先看這份定義正式規格
    priority: primary
```

## Server suggestion 範例
- `doc_type=SPEC` → `priority=primary`
- `doc_type=PLAN` → `priority=important`
- `doc_type=GUIDE` → `priority=supporting`""",
    },

    "sync": {
        1: """# 文件同步規則 v1.0

## Source Audit
- 每次 sync 先做 Source Audit
- rename → 更新 URI，`source_status=valid`
- delete → `source_status=stale`
- 對 index bundle，不只同步 sources，也要同步 primary source 與 highlights""",
        2: """# 文件同步規則 v1.0（完整版）

## Source Audit
- 每次 `/zenos-sync` 先檢查 source 是否 rename / delete / stale
- rename → 更新 URI，維持 `source_status=valid`
- delete / 不可讀 → `source_status=stale`

## 同步 contract
- sync 必須採局部更新，不可清空未明示欄位
- 對 index bundle，除 sources 外還要檢查 primary source、`bundle_highlights`、L2 掛載入口
- rename / reclassify / archive / supersede 應走治理 sync 模式，不拆成危險的多次手動 write""",
        3: """# 文件同步規則 v1.0（含範例）

## rename 範例
- 舊 URI：`docs/specs/SPEC-a.md`
- 新 URI：`docs/specs/SPEC-b.md`
- sync 後：source.uri 更新，`source_status=valid`

## stale 範例
- sync 找不到檔案 → `source_status=stale`
- agent 應回報並補救，不得靜默留下壞連結""",
    },

    "remediation": {
        1: """# 治理修復規則 v1.0

## 修復優先順序
1. 先修 red findings
2. 再修 stale / broken impacts
3. 最後補 yellow warnings 與 blindspot / quality 缺口

## 原則
- 修復要回寫 ontology
- 無法自動判斷時停下來，不硬猜""",
        2: """# 治理修復規則 v1.0（完整版）

## 修復優先順序
1. red findings：broken impacts、missing linked entities、權限風險
2. yellow findings：reference-only 缺失、待確認草稿、summary 腐化
3. green / advisory：補充文件、補 highlights、補 entries

## remediation 流程
- 先 analyze，讀 findings，特別看 `analyze(quality)` 與 `analyze(blindspot)`
- 能安全自動修就 write / confirm / task
- 不能安全自動修就建立 task 或回報用戶
- 每次修復後重跑 analyze 驗證缺口是否消失

## 禁止
- 不得為了清綠燈而刪除仍有價值的 knowledge
- 不得在沒有證據時硬改 impacts 目標
- 不得跳過 confirm gate 直接把草稿當成已驗收""",
        3: """# 治理修復規則 v1.0（含範例）

## broken impacts 範例
- 發現 target 是 draft / stale / missing
- 做法：先確認 target 是否該升級；不該升級就改 impacts 或移除無效關聯

## orphan document 範例
- 先找正確 `linked_entity_ids`
- 無法確定就停下來問，不靜默掛錯 L2

## 修復完成
- 重跑 analyze，確認 finding 歸零
- 把修復結果寫進 task result 或 journal""",
    },

    "capture": {
        1: """# 知識捕獲分層路由規則 v1.0

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 寫入 L2 的強制要求（Server 端硬性規則）
write(collection="entities", data={type="module", ...}) 時必須附帶 layer_decision：
- q1_persistent: true/false（跨時間存活？）
- q2_cross_role: true/false（跨角色共識？）
- q3_company_consensus: true/false（公司共識？）
- impacts_draft: ["A 改了 X → B 的 Y 要跟著看"] （至少 1 條）

三問未全通過 → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問通過但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

## 冷啟動（首次捕獲一批文件）
Step 1: 讀完所有文件（先全局，後切割）
Step 2: 辨識公司共識概念（三問過濾）
Step 3: 切割獨立的 L2 候選（可獨立改變原則）
Step 4: 推斷 impacts（A 改了 → B 要跟著看）
Step 5: 說不出 impacts → 降為 L3 或 sources
Step 6: 全局確認後，批量 write（帶 layer_decision）""",

        2: """# 知識捕獲分層路由規則 v1.0（完整版）

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 寫入 L2 的強制要求（Server 端硬性規則）
write(collection="entities", data={type="module", ...}) 時必須附帶 layer_decision：
- q1_persistent: true/false（跨時間存活？）
- q2_cross_role: true/false（跨角色共識？）
- q3_company_consensus: true/false（公司共識？）
- impacts_draft: ["A 改了 X → B 的 Y 要跟著看"] （至少 1 條）

三問未全通過 → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問通過但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

## 錯誤路徑處理

收到 LAYER_DOWNGRADE_REQUIRED 時：
1. 找出哪問沒通過（q1/q2/q3 哪個是 false）
2. 重新考慮是否真的是公司共識概念
3. 如果確實不是 L2 → 改為 L3 document 或 sources
4. 如果認為判斷錯誤 → 在 layer_decision 中補充說明後重試

收到 IMPACTS_DRAFT_REQUIRED 時：
1. 問自己：「這個概念改了，哪個其他概念要跟著看？」
2. 如果真的想不出任何 impacts → 強烈訊號此概念不夠 L2
3. 補充至少一條具體 impacts 後重試

## 增量捕獲 vs 全局統合模式

增量模式（日常使用）：
- 一次捕獲 1-3 個概念
- 適合：開完會、看完一份文件、做完一個 task
- 流程：識別概念 → 三問 → 如通過直接 write

全局統合模式（冷啟動 / 大型 review）：
- 一次處理整個 codebase 或一批文件
- 適合：首次接手專案、季度 ontology review
- 流程：先讀全局，再識別，再統一 write
- 重點：不要邊讀邊 write，等全局視野建立後再決定 L2 邊界

## Impacts 推斷策略

問法 1（改變傳播）：「如果這個概念的定義改了，哪些文件/流程/系統要更新？」
問法 2（依賴關係）：「哪些東西的正確性依賴於這個概念是穩定的？」
問法 3（跨角色影響）：「工程師改了這個，行銷/法務/客服需要知道什麼？」

如果三個問法都問不出答案 → 此概念不是 L2。

## 降級流程細節

降為 L3 document：
- 建 document entity，設 type 和 source.uri
- ontology_entity 指向最相關的 L2
- 適合：有正式文件形式的內容

降為 sources：
- 不建 entity，直接加到現有 L2 的 sources 陣列
- 適合：參考資料、草稿、一次性輸入
- sources 格式：{uri: "...", type: "document|github|notion", synced_at: "..."}""",

        3: """# 知識捕獲分層路由規則 v1.0（含完整範例）

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 完整冷啟動範例（從原始文件到 ontology）

### 原始文件（假設接手一個新專案）
```
- README.md：介紹 ZenOS 是 AI Context 層
- docs/ADR-001.md：決定採用 PostgreSQL
- docs/SPEC-pricing.md：定價模型規格
- docs/SPEC-auth.md：用戶認證規格
- src/models/user.py：用戶資料模型
```

### Step 1：全局閱讀
先讀所有文件，建立整體印象，不急著建 entity。

### Step 2：列出候選概念
從文件中識別反覆出現的詞彙：
- ZenOS（產品概念）
- 定價模型（跨文件出現，有完整規格）
- 用戶認證（有完整規格）
- PostgreSQL（技術選型）
- 用戶資料模型（技術實作）

### Step 3：三問過濾

「定價模型」：
- 公司共識？✓（行銷、工程、法務都理解）
- 改了有 impacts？✓（影響合約、程式碼、文件）
- 跨時間存活？✓（比任何 sprint 都長壽）
→ 通過，L2 候選

「PostgreSQL」：
- 公司共識？△（工程師理解，行銷不需要理解）
- 改了有 impacts？✓（影響部署/遷移腳本）
- 跨時間存活？✓
→ 不通過（q1），降為 ADR 文件

「用戶資料模型」：
- 公司共識？✗（只有工程師理解）
→ 不通過，降為 L3 document 或 sources

### Step 4：推斷 impacts

「定價模型」的 impacts：
- 定價模型 改了費率結構 → 合約模板 的計費條款需更新
- 定價模型 新增方案 → 產品功能門檻 的解鎖邏輯需更新

### Step 5：批量 write

```python
# 建 L2：定價模型
write(
  collection="entities",
  data={
    "name": "定價模型",
    "type": "module",
    "summary": "ZenOS 的訂閱費率結構和計費邏輯",
    "status": "draft",
    "layer_decision": {
      "q1_persistent": True,
      "q2_cross_role": True,
      "q3_company_consensus": True,
      "impacts_draft": [
        "定價模型 改了費率結構 → 合約模板 的計費條款需更新",
        "定價模型 新增方案 → 產品功能門檻 的解鎖邏輯需更新"
      ]
    }
  }
)

# 建 L3 document：PostgreSQL ADR
write(
  collection="documents",
  data={
    "doc_id": "ADR-001-postgresql",
    "title": "架構決策：選用 PostgreSQL",
    "type": "ADR",
    "ontology_entity": "資料儲存架構",
    "status": "approved",
    "source": {"uri": "docs/ADR-001.md"}
  }
)
```

## layer_decision 填寫範例：好 vs 不好

### 不好的填寫
```python
layer_decision={
  "q1_persistent": True,
  "q2_cross_role": True,
  "q3_company_consensus": True,
  "impacts_draft": ["影響其他東西"]  # 太模糊
}
```

### 好的填寫
```python
layer_decision={
  "q1_persistent": True,
  "q2_cross_role": True,
  "q3_company_consensus": True,
  "impacts_draft": [
    "定價模型 調整計費週期（月→年） → 合約模板 的自動續約條款需法務重新審核",
    "定價模型 新增企業方案 → 功能存取控制 的企業功能白名單邏輯需更新"
  ]
}
```

## 常見錯誤與修正

錯誤 1：「每個文件都應該有對應的 L2」
→ 不對。文件是 L3，掛在 L2 下面。一個 L2 可以有多份文件。

錯誤 2：「說不出 impacts 沒關係，先建起來再說」
→ 不對。說不出 impacts 是 L3 降級的強烈訊號。強行建立沒有 impacts 的 L2 只會讓 ontology 膨脹卻沒有治理價值。

錯誤 3：「全局讀完再 capture 太慢，邊讀邊 write 比較快」
→ 冷啟動時不要邊讀邊 write。全局視野建立後才能正確判斷 L2 邊界。增量模式才邊讀邊 write。""",
    },
}
