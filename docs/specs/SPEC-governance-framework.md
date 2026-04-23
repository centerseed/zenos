---
type: SPEC
id: SPEC-governance-framework
status: Under Review
ontology_entity: governance-framework
created: 2026-03-27
updated: 2026-04-23
depends_on: SPEC-ontology-architecture v2
---

# Feature Spec: ZenOS 治理規則抽象框架

> **2026-04-23 update**：Action Layer 已於 `SPEC-ontology-architecture v2` 併入 Knowledge Layer（task/plan/milestone/subtask 成為 L3-Action subclass）。本 SPEC 的六維框架仍完全適用於新 subclass 體系。

## 背景與動機

ZenOS 的 ontology 有多層治理：L2 知識節點、L3-Semantic（文件 / 角色 / 專案）、L3-Action（任務 / 計畫 / 里程碑 / 子任務）。每一層都有自己的治理 spec，定義品質門檻、生命週期、關聯規則。

但目前這些治理 spec 之間缺乏統一的底層結構：

- 各 spec 的維度不同——有的定義了生命週期但沒定義反饋路徑，有的定義了品質門檻但沒定義關聯規則
- 治理規則變更後，沒有明確的傳播機制——改了 spec 但 skill 沒更新、server 沒驗證、analyze 沒偵測
- 新增治理層時（例如未來的 Plan 層、Protocol 層），沒有標準骨架可遵循
- 跨 spec 發生衝突時，沒有通用的仲裁規則

本 spec 定義 ZenOS **所有治理規則的抽象框架**。它是治理的治理——所有具體治理 spec 都必須遵循此框架，此框架的變更也必須遵循自身定義的傳播契約。

---

## 適用範圍

本框架適用於 ZenOS 中所有定義治理規則的 spec，包括但不限於：

- `SPEC-ontology-architecture v2`（L1 / L2 / L3-Semantic / L3-Action 的 schema 與 lifecycle canonical）
- `SPEC-doc-governance`（L3-Document subclass 治理）
- `SPEC-task-governance`（L3-Action subclass 系列 — Milestone / Plan / Task / Subtask 治理）
- `SPEC-identity-and-access`（身份與權限治理）
- 未來新增的任何治理 spec

> 原 `SPEC-ontology-architecture v2` 已於 2026-04-23 併入 `SPEC-ontology-architecture v2 §7`，本框架對 L2 的引用直接指向主 SPEC。

---

## 通用治理規則結構（六維模型）

任何治理規則，無論它管的是 entity、document、task 或其他對象，都由六個維度組成：

```
┌─────────────────────────────────────────────────────────┐
│ 治理規則 = 通用六維結構                                    │
│                                                          │
│ ① 對象類型（Target Type）                                 │
│   這條規則管什麼？                                         │
│                                                          │
│ ② 品質門檻（Quality Gates）                               │
│   建立或變更時必須滿足的最小品質                             │
│                                                          │
│ ③ 生命週期（Lifecycle State Machine）                     │
│   合法的狀態、合法的轉換路徑、終態條件                       │
│                                                          │
│ ④ 關聯規則（Relation Rules）                              │
│   與其他治理對象的連結約束                                   │
│                                                          │
│ ⑤ 反饋路徑（Feedback Triggers）                           │
│   完成或變更後，哪些下游必須被通知或更新                      │
│                                                          │
│ ⑥ 衝突仲裁（Conflict Resolution）                        │
│   與其他治理規則發生衝突時的優先序與處理原則                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 六維模型的定位

此模型是**強制框架**，不是參考建議。具體要求：

- **撰寫新治理 spec 時**：PM 必須在 spec 中明確覆蓋六個維度。允許某維度標注「不適用」並說明原因，但不允許靜默遺漏。
- **審查治理 spec 時**：審查者應以六維模型為檢查清單，缺少任何維度即為 P1 問題。
- **現有治理 spec**：不要求立即重寫格式，但應在下次修訂時對齊六維結構。

### 各維度定義

#### ① 對象類型（Target Type）

明確定義這條規則治理什麼對象。必須回答：

- 對象屬於哪個 collection 或 schema？
- 對象在 ontology 分層中的位置（若適用）？
- 對象與 entity 分層的關係（是 entity 的一種，還是獨立 collection）？

#### ② 品質門檻（Quality Gates）

定義對象在建立或變更時必須滿足的最小品質。每條品質門檻應包含：

- 受約束的欄位或屬性
- 約束規則（格式、數量、內容要求）
- 違反時的處理（拒絕 / 降級 / 標記待修）

#### ③ 生命週期（Lifecycle State Machine）

定義對象的合法狀態集與轉換規則。必須回答：

- 初始狀態（建立時允許的狀態）
- 終態（不可再轉換的狀態）
- 合法轉換路徑（哪些狀態可轉到哪些狀態）
- 中間態（如 blocked、under review 等）

#### ④ 關聯規則（Relation Rules）

定義對象與其他治理對象的連結約束。必須回答：

- 必要關聯（建立時至少要連結什麼）
- 關聯數量限制（最少、最多）
- 關聯語意（part_of / impacts / linked_to 等）

#### ⑤ 反饋路徑（Feedback Triggers）

定義對象完成或變更後，哪些下游必須被通知或更新。必須回答：

- 哪些事件觸發反饋（狀態改變 / 完成 / 取消 / 取代）
- 反饋對象是什麼（document / entity / blindspot / task）
- 反饋是自動的還是需要人確認

#### ⑥ 衝突仲裁（Conflict Resolution）

定義當這條規則與其他治理規則發生衝突時的處理方式。通用仲裁順序為：

1. 先依內容本質分層（屬於 L2 / L3 / Task / sources 的哪一層）
2. 再套用該層的權威 spec
3. 任何治理 spec 不得覆寫其他層的權威規範
4. 若同層出現兩條矛盾規則，以較晚標為 Approved 的版本為準；未 Approved 的規則不自動生效

---

## 現行治理規則實例

以下表格將現行四套治理規則映射到六維框架。

**注意**：2026-04-23 起，L2 / L3-Semantic（Document 等） / L3-Action（Task / Plan / Milestone / Subtask）都是 entity。canonical schema 在 `SPEC-ontology-architecture v2`；本表列各 subclass 的治理指向。

| 維度 | L2 知識節點 | L3-Document | L3-Action（Task/Plan/Milestone/Subtask）|
|------|-----------|-------------|-------------------------------------|
| **權威 Spec** | `SPEC-ontology-architecture v2 §7` | `SPEC-doc-governance` | `SPEC-task-governance` |
| **對象類型** | `entity_l2` row（level=2） | `entity_l3_document` row | `entity_l3_task / plan / milestone / subtask` row |
| **品質門檻** | 三問全過、summary 跨角色可讀、至少 1 條具體 impacts | frontmatter 必填、分類正確、source 有效 | title 動詞開頭、AC 2-5 條、description 含背景/問題/期望 |
| **生命週期** | (false,active) → (true,active) → (true,stale)（兩維，見主 SPEC §7.2）| draft → current → stale → archived（supersede 可 fork） | 各 subclass `task_status` 狀態機（主 SPEC §11.2）|
| **關聯規則** | 至少 1 條具體 `impacts` | `parent_id` 掛到 L2 / L3 | `parent_id` 歸屬；`relationships` 掛 L2 module（≤3 條）|
| **反饋路徑** | impacts 變動觸發下游檢查 | supersede/archive 時 ontology sync | 完成後反寫 L2 entity.entries / blindspot |
| **衝突仲裁** | 定義三問 + impacts gate | 定義文件生命週期 | 定義建票品質與驗收 |

---

## 治理規則變更傳播契約

### 核心原則

**治理規則不是孤立的文字。變更任何一條治理規則時，必須同步傳播到所有執行該規則的層級。**

### 傳播層級

當某份治理 spec 的規則被變更時，以下層級都必須檢查是否需要同步更新：

```
治理 Spec 變更
     │
     ├─→ ① Protocols（結構化規則）
     │     ZenOS protocols collection 中的 machine-readable 規則。
     │     若已存在，必須同步更新；若尚未結構化，開 task 追蹤。
     │
     ├─→ ② Server 端驗證（MCP tools）
     │     write / task / confirm 等 MCP tools 中的驗證邏輯。
     │     規則改了但驗證沒跟上 = 規則形同虛設。
     │
     ├─→ ③ governance_guide 內容（Agent 行為）
     │     governance_guide tool 回傳的治理規則文本。
     │     這是 agent 取得治理規則的主要管道（取代 local skills）。
     │     規則改了但 guide 沒更新 = agent 拿到舊規則。
     │     註：local skills 作為 optional 加速器仍可存在，但不是治理的必要條件。
     │
     ├─→ ④ Analyze 檢查（治理合規）
     │     analyze tool 的合規檢查邏輯。
     │     新規則必須能被 analyze 偵測違規。
     │
     ├─→ ⑤ 下游 Spec（via impacts）
     │     透過 ontology impacts 關聯的其他治理 spec。
     │     例：文件治理 spec 的 supersede 規則改了，若 task 治理中有引用
     │     supersede 語意的規則，需要檢查是否需同步更新。
     │
     └─→ ⑥ Ontology Entity
           治理節點本身的 metadata（summary / tags / sources）。
           規則改了但節點描述沒更新 = 知識層過時。
```

### 強制規則

1. **變更治理 spec 時，必須在 commit 或 PR 中列出受影響的傳播層級。**
2. **若某層級目前無法同步（例如 protocols 尚未結構化），必須開 task 追蹤。** 開出的追蹤 task 必須符合 `SPEC-task-governance` 的建票最小規範，至少包含受影響的傳播層級描述與對應的驗收條件。不得靜默略過。
3. **傳播完成前，治理 spec 不得標為 Approved；可停留在 Under Review。**
4. **本傳播契約本身也是治理規則——修改本契約時，同樣適用此契約。**

### Reject Gate 升級（2026-04-17 — ADR-038）

以下兩層從 checklist 升級為**強制 reject gate**：

- **Layer 2（Server 端驗證，MCP tools）**：若 write/task/confirm 等 tool 的驗證邏輯未對應新規則，治理 spec 不得轉 `Approved`
- **Layer 3（governance_guide 內容）**：若 `src/zenos/interface/governance_rules.py` 對應 topic 未更新，CI lint 失敗，PR 不得 merge

其餘四層（Protocols / Analyze / 下游 Spec / Ontology Entity）仍為 checklist，缺任一為 P1 問題但非 reject。

完整 contract 見 `SPEC-governance-guide-contract`。

#### Acceptance Criteria

- `AC-propagation-1` Given 治理 spec PR 修改規則文字但未改 `governance_rules.py`，When CI 執行，Then lint fail
- `AC-propagation-2` Given 治理 spec 處 `Under Review` 且 Layer 2/3 均同步，When reviewer approve，Then 可轉 `Approved`
- `AC-propagation-3` Given governance SSOT CI lint 執行，Then 可列出所有 Layer 2/3 不同步的治理 spec，且 production server 不必暴露 `analyze(check_type="governance_ssot")`

---

## 治理規則的演進路徑

```
Phase 0（現在）
  規則以 prose 寫在 spec 文件中。
  傳播靠人工 checklist。
  Agent 靠讀 skill 遵循規則。

Phase 1（結構化）
  觸發條件：protocols collection 首次建立、或至少一條治理規則因傳播遺漏造成生產問題。
  規則同時寫入 protocols collection（machine-readable）。
  MCP tools 讀 protocol 做 server 端驗證。
  Skill 可從 protocol 自動生成或校驗。

Phase 2（自動治理）
  觸發條件：Phase 1 穩定運行、且有多個外部客戶導入 ZenOS 治理。
  analyze 自動偵測違規並建議修正。
  規則變更自動觸發傳播 pipeline。
  Governance lint 成為 CI 的一部分。
```

---

## 治理架構：模組化與內外邊界

### 設計原則

治理能力不是一坨全有或全無的東西。它應該是可疊加的模組，用戶按需啟用。同時，每個模組內部的功能要區分「對外開放」和「內部飛輪」——前者降低門檻加速採用，後者是 ZenOS 的核心價值與護城河。

### 模組堆疊架構

```
┌──────────────────────────────────────────────────────────┐
│  Base Layer（核心層，所有用戶都有）                            │
│                                                           │
│  Entity 三層模型（L1/L2/L3）                                │
│  MCP Tools（search / get / write / confirm / analyze）      │
│  governance_guide tool（按需提供治理規則）                     │
│  結構驗證（server 端強制）                                    │
│                                                           │
├──────────────────────────────────────────────────────────┤
│  可疊加模組（按需啟用）                                       │
│                                                           │
│  ┌────────────────────┐  ┌────────────────────┐           │
│  │  Doc 治理模組        │  │  Task 治理模組       │           │
│  │                     │  │                     │           │
│  │  文件生命週期管理     │  │  建票品質門檻        │           │
│  │  過時偵測與標記       │  │  驗收與知識反饋閉環   │           │
│  │  supersede/archive  │  │  Plan 層整合         │           │
│  │  source.uri 去重     │  │  去重與 supersede    │           │
│  └────────────────────┘  └────────────────────┘           │
│                                                           │
├──────────────────────────────────────────────────────────┤
│  Quality Intelligence（付費增值）                             │
│                                                           │
│  品質評分演算法 + 跨公司 benchmark + 使用信號分析               │
│  自動修復建議 + 盲點推斷 + 冷啟動品質校正排序                   │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### 模組啟用條件與依賴

| 模組 | 前置依賴 | 啟用時機 | 可獨立停用？ |
|------|---------|---------|------------|
| Base Layer | 無 | MCP 連線即啟用 | 不可（核心） |
| Doc 治理 | Base Layer | 用戶開始管理文件時 | 可 |
| Task 治理 | Base Layer | 用戶開始用 task 時 | 可 |
| Quality Intelligence | Base Layer + 至少一個治理模組 | 用戶想要品質持續提升時 | 可 |

Doc 治理和 Task 治理之間**無依賴關係**，可以只啟用其中一個。Quality Intelligence 則需要至少一個治理模組的數據才能運作。

### 每個模組的內外邊界

每個治理模組（包括 Base Layer）都有兩面：

```
對外開放（Open）                      內部飛輪（Internal）
───────────────                      ─────────────────
透過 governance_guide 提供              ZenOS server 內部執行
任何 agent 都能取用                     不透過 API 暴露
降低門檻、加速採用                      產生數據護城河
知道規則 ≠ 能做到同等品質               需要跨公司數據才能持續優化
```

#### Base Layer 的內外切分

| 對外開放 | 內部飛輪 |
|---------|---------|
| Entity 三層模型定義（L1/L2/L3） | L2 推斷演算法（全局優先策略、prompt） |
| 三問判斷標準 | 三問的語意閘 prompt 與 accuracy 調校 |
| 四維標籤結構（what/why/how/who） | 四維標注的自動分類模型 |
| 分層路由規則（L2/L3/sources 邊界） | 路由判斷的 LLM pipeline |
| 命名規範與格式要求 | 命名去重與衝突解析演算法 |
| 關係類型定義（impacts/enables/...） | impacts 目標有效性自動偵測 |

#### Doc 治理模組的內外切分

| 對外開放 | 內部飛輪 |
|---------|---------|
| 文件生命週期狀態機（Draft→Approved→...） | 過時偵測的語意推斷演算法 |
| frontmatter 必填欄位定義 | 跨文件矛盾偵測邏輯 |
| supersede/archive 流程規則 | 文件關聯性自動推斷 |
| source.uri 去重規範 | 去重匹配的模糊比對演算法 |

#### Task 治理模組的內外切分

| 對外開放 | 內部飛輪 |
|---------|---------|
| 建票品質規則（verb-first、AC 2-5 條） | Task 信號 → blindspot 轉換演算法 |
| 8 問 checklist | 「反覆出現的問題」偵測閾值 |
| linked_entities 掛法（Type A/B/C） | linked_entities 自動推薦演算法 |
| 知識反饋閉環要求 | 反饋完整度評分邏輯 |
| Anti-patterns 定義 | Anti-pattern 自動偵測 |

#### Quality Intelligence 的定位

Quality Intelligence 的核心競爭力來自**資訊不對稱**——server 看到的全局視野是任何單一 agent session 無法擁有的：

```
Agent 知道的（單一 session 局部視野）     Server 知道的（全局 + 歷史）
──────────────────────────           ─────────────────────────
當前這個 task 的 context               這個 entity 下過去 50 個 task 的結果
當前這個 entity 的 summary             這個 entity 的 summary 改了 8 次的歷史
當前 write 的內容                      過去 200 次 write 被 reject 的 pattern
這個 session 的對話                    所有 agent 的 search → 使用/未使用記錄
                                     跨公司同類型 entity 的品質分布
                                     整個 ontology 的關係圖拓撲結構
```

**小模型 + 全局數據 > 大模型 + 局部視野。** Quality Intelligence 不是用小模型做大模型的事，而是做大模型做不到的事——全局分析、歷史趨勢、跨公司模式識別。

具體能力與 agent 端的分工：

| 能力 | Agent（大模型 + 局部） | Server（小模型/演算法 + 全局） |
|------|---------------------|---------------------------|
| 「AC 寫得好嗎」（語意品質） | ✅ 大模型強項 | ❌ 留給 agent |
| 「這個 entity 在腐化嗎」 | ❌ 看不到歷史 | ✅ 比對 3 個月 summary 變化 |
| 「哪個 L2 最需要先修」 | ❌ 不知道其他 L2 狀態 | ✅ 全局品質排序 |
| 「這個問題是不是反覆出現」 | ❌ 只看到這次 task | ✅ 掃同 entity 下所有 task |
| 「你的 ontology 品質如何」 | ❌ 沒有 benchmark | ✅ 跨公司比較 |
| 「哪些 impacts 已斷鏈」 | ❌ 只看當前 entity | ✅ 掃全圖拓撲 |
| 「search 結果對 agent 有沒有用」 | ❌ 不自知 | ✅ 追蹤 search_unused |

其中許多能力甚至不需要 LLM：圖拓撲分析用演算法、統計分析用 SQL、percentile 排名用純數學。需要 LLM 的（如 summary 差異比較）用 Flash Lite 即夠。

**開放思路：Quality Intelligence 的部分能力可以設計為「server 提供全局數據 + 分析結果，由 agent 端���大模型做最終判斷」的協��模式。** 例如：server 告訴 agent「這個 entity 的 summary 與 3 個月前差異度 0.8，且關聯的 5 個 task 中有 3 個提到類似問題」，agent 的大模型據此決定如何修復。這讓 server 保持低成本，同時借用 agent 的大模型能力做高品質治理——可作為付費 API 呼叫計費。

Quality Intelligence 沒有「對外開放」的部分——它整體都是飛輪：

| 能力 | 為什麼不開放 |
|------|------------|
| 品質評分演算法與權重 | 跑過多間公司的數據調校的，fork 了沒數據無法校準 |
| 跨公司 benchmark | 「你的品質在同業 top 20%」——只有平台有這個數據 |
| 冷啟動品質校正排序 | 「哪個 L2 最需要先修」的排序依據歷史 capture 數據 |
| 使用信號分析 | search_unused 偵測需要大量 agent 行為數據 |
| 自動修復建議 | 「像你這樣的公司，通常這樣修」需要跨公司模式識別 |
| Summary 語意品質評估 | 「agent-oriented」的定義是跨角色、跨公司校準的 |

### 治理的三層執行機制

無論用戶啟用了哪些模組，治理都透過三層機制執行，確保不依賴特定 agent 設定：

```
Layer 1 — Tool Descriptions（永遠載入，~200 tokens/tool）
  每個 MCP tool 的 description 包含最小治理提示。
  例：task tool 寫「Tasks require verb-first title, 2-5
  acceptance_criteria. Call governance_guide('task') first.」
  任何 MCP client 看到 description 就知道有規則。

Layer 2 — governance_guide tool（按需載入，~2-3k tokens/topic）
  agent 呼叫 governance_guide(topic, phase?, detail?) 取得：
  - Level 1：流程概覽（什麼時候用、分幾階段）
  - Level 2：階段細節（具體規則、checklist）
  - Level 3：範例與模板（好壞對照、JSON payload）
  規則來自 server 端，更新即時生效。
  語意品質判斷由 agent 的 LLM 執行（成本在用戶端）。

Layer 3 — Server 驗證（自動執行，agent 無法繞過）
  結構驗證：無 LLM，pattern matching（零成本）。
  輕量語意檢查：Flash Lite 級別（極低成本）。
  不合格 → reject + 具體錯誤訊息 + 指引 call governance_guide。
  合格 → 寫入 + 觸發啟用模組的後續治理流程。
```

Layer 2 的關鍵設計：**用 server 端的規則驅動 agent 端的大模型做語意判斷。** 治理品質由 agent 的 LLM 能力決定，但規則由 ZenOS 集中管理。server 不需要跑大模型，成本可控。

### governance_guide tool 的分層載入設計

```
governance_guide(topic)
  topic: "entity" | "document" | "task" | "capture" | "sync" | "remediation"

  回傳 Level 1：流程概覽（~1k tokens）
    - 這個治理模組做什麼
    - 分幾個階段
    - 每階段用哪些 MCP tools
    - 前置條件（需要先啟用什麼模組）

governance_guide(topic, phase)
  phase: 模組內的具體階段

  回傳 Level 2：階段細節（~2-3k tokens）
    - 具體規則與約束
    - Checklist
    - 好壞範例摘要

governance_guide(topic, phase, detail="examples")

  回傳 Level 3：完整範例與模板（~3-5k tokens）
    - 好/壞範例對照
    - JSON payload 模板
    - 常見錯誤與修正方式
```

Agent 按需逐層深入，一個 session 只載入需要的部分。相比現在每個 skill 一次全載入 15k+ tokens，token 使用量大幅降低。

---

## 治理功能索引（Internal / External 分類）

### 分類原則

每一項治理功能都歸入以下三類之一：

| 分類 | 定義 | 對 agent 可見？ | 計費模式 |
|------|------|---------------|---------|
| **External** | Agent 應遵循的規則與流程 | 透過 governance_guide 完整提供 | 免費（降低門檻） |
| **Internal** | Server 內部執行的智慧邏輯 | 不透過 API 暴露實作細節 | 包含在基礎服務中 |
| **Agent-Powered Internal** | Server 提供全局數據 + 分析上下文，由 agent 的大模型執行治理推理 | 透過 analyze API 暴露數據與上下文 | 按 API 呼叫計費 |

**Agent-Powered Internal** 是關鍵設計——它讓 ZenOS 借用 agent 端的大模型能力來執行需要語意判斷的治理任務，同時保持 server 端低成本。server 提供的是 agent 看不到的全局資訊（資訊不對稱），agent 提供的是 server 負擔不起的大模型推理能力。

### 功能索��

#### Base Layer — Entity 治理

| 功能 | 分類 | 權威 Spec | 說明 |
|------|------|----------|------|
| Entity 三層模型定義 | External | `SPEC-ontology-architecture` | L1/L2/L3 的邊界與路由規則 |
| L2 三問判斷標準 | External | `SPEC-ontology-architecture v2` | 三問的文字定義與判斷流程 |
| 四維標籤結構 | External | `SPEC-ontology-architecture` | what/why/how/who 的定義與用法 |
| 命名規範與格式要求 | External | `SPEC-ontology-architecture v2` | 命名限制、長度、禁止模式 |
| 關係類型定義 | External | `SPEC-ontology-architecture v2` | impacts/enables/depends_on ��語意 |
| L2 生命週期狀態機 | External | `SPEC-ontology-architecture v2 §7.2` | 二維模型：`confirmed_by_user × status` — Draft `(false, active)` → Confirmed `(true, active)` ↔ Stale `(true, stale)` |
| 可調整 vs 不可調整參數 | External | `SPEC-ontology-architecture v2` | server hardcoded 與 user adjustable 邊界 |
| L2 推斷演算法（全局優先） | Internal | — | prompt 工程 + 全局合成策略 |
| 三問語意閘 prompt | Internal | — | Flash Lite 93% accuracy 的判斷 prompt |
| 命名去重與衝突解析 | Internal | — | 模糊匹配 + 合併建議演算法 |
| L2 腐化偵測 | Agent-Powered Internal | `SPEC-governance-feedback-loop` R1 | server 提供歷史 summary 變化 + task 信號，agent 判斷是否需要修復 |
| Impacts 斷鏈偵測 | Agent-Powered Internal | `SPEC-governance-feedback-loop` P1-2 | server 掃全圖拓撲找到斷鏈，agent 建議修復方案 |

#### Doc 治理模組

| 功能 | 分類 | 權威 Spec | 說明 |
|------|------|----------|------|
| 文件分類（7 type） | External | `SPEC-doc-governance` | SPEC/ADR/TD/PB/SC/REF/SKILL |
| Frontmatter 必填欄位 | External | `SPEC-doc-governance` | type, id, status, ontology_entity, created, updated |
| 文件命名規則 | External | `SPEC-doc-governance` | SPEC-{slug}.md, ADR-{nnn}-{slug}.md 等 |
| 生命週期狀態機 | External | `SPEC-doc-governance` | Draft→Under Review→Approved→Superseded/Archived |
| Agent 合規工作流（4 stage） | External | `SPEC-doc-governance` | pre-write→decision→atomic write→post-write |
| supersede/archive 流程 | External | `SPEC-doc-governance` | 取代與歸檔的操作規則 |
| source.uri 去重規範 | External | `SPEC-doc-governance` | 寫入前搜尋避免重複 |
| 過時文件語意偵��� | Agent-Powered Internal | `SPEC-governance-feedback-loop` P1-3 | server 提供跨文件矛盾信號 + 活動度數據，agent 判斷是否過時 |
| 文件關聯性自動推斷 | Internal | — | 新文件自動找關聯 entity 的演算法 |
| 去重模糊比對 | Internal | — | source.uri 和內容的相似度比對 |

#### Task 治理模組

| 功能 | 分類 | 權威 Spec | 說明 |
|------|------|----------|------|
| 建票品質規則（8 欄位） | External | `SPEC-task-governance` | title/desc/AC/linked/priority/status/owner/result |
| 8 問 checklist | External | `SPEC-task-governance` | 建票前的品質自檢 |
| linked_entities 掛法 | External | `SPEC-task-governance` | Type A/B/C 模式 |
| 生命週期狀態機 | External | `SPEC-task-governance` | backlog→todo→...→done + blocked |
| 去重流程 | External | `SPEC-task-governance` | 建票前搜尋 + 比較規則 |
| 知識反饋閉環要求 | External | `SPEC-task-governance` | 完成後反寫 document/blindspot/entity |
| Plan 層（任務分組） | External | `SPEC-task-governance` | plan_id + plan_order 分組與排序 |
| Anti-patterns 定義 | External | `SPEC-task-governance` | orphan/fake link/mixed/duplicate/reminder |
| 可調整 vs 不可調整參數 | External | `SPEC-task-governance` | server hardcoded 與 agent adjustable 邊界 |
| Task 信號 → blindspot 轉換 | Agent-Powered Internal | `SPEC-governance-feedback-loop` P1-1 | server 提供同 entity 的 task 歷史 + 問題模式，agent 判斷是否建 blindspot |
| linked_entities 自動推薦 | Internal | — | 基於 ontology graph 的關聯推薦 |
| Anti-pattern 自動偵測 | Internal | — | 結構化 pattern matching |
| 優先級 AI 推薦 | Internal | — | 基於 urgency + ontology context 的推薦 |

#### Quality Intelligence（付費增值）

| 功能 | 分類 | 權威 Spec | 說明 |
|------|------|----------|------|
| 品質評分演算法 | Internal | `governance-quality` | Coverage/Freshness/Consistency/Actionability 權重 |
| 跨公司 benchmark | Internal | — | percentile 排名，需跨租戶數據 |
| 冷啟動品質校正排序 | Agent-Powered Internal | `SPEC-governance-feedback-loop` P0-2 | server 提供全局品質信號，agent 排序修復優先級 |
| 使用信號分析 | Internal | `SPEC-governance-feedback-loop` P2-1 | search_unused 模式偵測 |
| Summary 語意品質評估 | Agent-Powered Internal | `SPEC-governance-feedback-loop` P2-2 | server 提供 summary 歷史 + 使用數據，agent 評估品質 |
| 自動修復建議 | Agent-Powered Internal | — | server 提供問題清單 + 跨公司修復模式，agent 生成修復方案 |

#### 治理基礎設施

| 功能 | 分類 | 權威 Spec | 說明 |
|------|------|----------|------|
| 六維模型框架 | External | `SPEC-governance-framework` | 所有治理規則的抽象結構 |
| 傳播契約 | External | `SPEC-governance-framework` | 規則變更的 6 層傳播要求 |
| Audit log 結構 | Internal | `SPEC-governance-observability` | LLM 推斷歷史記錄 |
| 推斷準確度追蹤 | Internal | `SPEC-governance-observability` | confirm/reject 比率分析 |
| Eval dataset 匯出 | Internal | `SPEC-governance-observability` | 模型���練數據 |
| 演算法版本追蹤 | Internal | `SPEC-governance-observability` | prompt regression 偵測 |
| Task view 一致性規則 | External | `SPEC-task-view-clarity` | UI 計數/篩選/空狀態規則 |

### Agent-Powered Internal Governance 的運作模式

這是 ZenOS 的獨特付費模式：server 提供「全局情報」，agent 的大模型提供「推理能力」，合作完成 server 單獨做不好、agent 單獨做不到的治理任務。

```
┌──────────────┐                    ┌──────────────┐
│  ZenOS Server │                    │  Agent (LLM) │
│              │  ① analyze API      │              │
│  全局數據     │ ──────────────→    │  大模���推理   │
│  歷史趨勢     │  提供：            │              │
│  跨公司模式   │  - entity 歷史     │  執行：       │
��  使用信號     │  - task 模式       │  - 語意判斷   │
│              │  - 品質信號        │  - 修復方案   │
│              │  - benchmark 位置   │  - 優先排序   │
│              │                    │              │
│              │  ② write/task API   │              │
│              │ ←──────────────    │              │
│  驗證 + 存儲  │  回傳：            │              │
│              ���  - 修復結果        │              │
│              │  - 新建 blindspot  │              │
│              │  - 品質改善動作     │              │
└──────────────┘                    └──────────────┘

計費：按 analyze API 的 check_type 計費
  - check_type="quality" → 基礎（含在訂閱中）
  - check_type="deep_quality" → 付費（回傳全局數據上下文）
  - check_type="remediation_context" → 付費（回傳修復建議上下文）
  - check_type="benchmark" → 付費（回傳跨公司比較）
```

**為什麼 agent 會願意付費 call 這些 API？** 因為 agent 自己做不到——它看不到歷史趨勢、看不到其他 agent 的使用模式、看不到跨公司的品質基準。這些資訊只有 ZenOS platform 有。

---

## 明確不包含

- 不在本框架中定義任何具體治理規則的細節（那是各模組 spec 的責任）
- 不定義 Entity 分層模型本身（那是 `SPEC-ontology-architecture` 的責任）
- 不定義 Ontology 雙層治理架構（骨架層/神經層）的運作方式
- 不定義 MCP tools 的介面規格
- 不定義 governance_guide tool 的實作細節（那是 Architect 的責任）
- 不定義 Quality Intelligence 的具體演算法（那是內部飛輪，不進入公開 spec）

---

## 與其他文件的關係

| 文件 | 關係 | 模組歸屬 |
|------|------|---------|
| `SPEC-ontology-architecture` | 定義 Entity 分層模型與雙層治理架構；本框架定義治理規則的抽象結構 | Base Layer |
| `SPEC-ontology-architecture v2` | 本框架的實例——L2 治理規則 | Base Layer |
| `SPEC-doc-governance` | 本框架的實例——L3 文件治理規則 | Doc 治理模組 |
| `SPEC-task-governance` | 本框架的實例——Task 治理規則 | Task 治理模組 |
| `SPEC-governance-feedback-loop` | 定義回饋迴路機制，橫跨多個模組 | 跨模組 |
| `SPEC-governance-observability` | 定義治理可觀測性，為 Quality Intelligence 提供數據基礎 | Quality Intelligence |
| `SPEC-progressive-trust` | 定義漸進式信任模型，影響模組啟用順序 | 跨模組 |

---

## 完成定義

1. 本 spec 已列入 `REF-active-spec-surface`。
2. 現行三份治理 spec 的六維映射表通過交叉比對驗證（與各 spec 正文一致）。
3. 傳播契約的六個層級定義清楚，且至少一次實際傳播（例如修改某治理 spec 後，按照本契約追蹤傳播層級）有留存證據。
4. 下次撰寫新治理 spec 時，PM 可依據六維模型作為 checklist 撰寫，Architect 可據此審查完整性。
5. 模組化架構的內外邊界定義清楚，governance_guide 的分層載入設計可供 Architect 實作。
6. Doc 治理和 Task 治理各自可獨立啟用/停用，不產生破壞性影響。
