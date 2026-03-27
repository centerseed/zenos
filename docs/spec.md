# ZenOS 治理憲法（Governance Constitution）

> 日期：2026-03-27
> 狀態：Canonical SSOT
> 定位：ZenOS 所有治理規則的最高原則。任何治理 spec 都必須遵循此框架。

---

## 一、本文件的角色

本文件是 ZenOS 的**治理憲法**——定義所有治理規則必須遵循的抽象結構與變更傳播機制。

它不定義具體的治理細節（那是各層 spec 的責任），也不定義產品願景、技術架構或市場定位（那些已拆分為獨立文件）。

```
本文件（憲法）
  │
  ├─→ 六維治理模型：所有治理 spec 的骨架
  ├─→ 傳播契約：規則變更時必須同步的層級
  ├─→ 衝突仲裁：跨 spec 矛盾時的優先序
  ├─→ Skill 架構：治理規則到 Agent 的載體
  └─→ 文件索引：ZenOS 所有受治理文件的導航
```

---

## 二、通用治理規則結構（六維模型）

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

### 定位

此模型是**強制框架**：

- **撰寫新治理 spec 時**：PM 必須明確覆蓋六個維度。允許標注「不適用」並說明原因，但不允許靜默遺漏。
- **審查治理 spec 時**：缺少任何維度即為 P1 問題。
- **現有治理 spec**：下次修訂時應對齊六維結構。

### 各維度定義

#### ① 對象類型（Target Type）

- 對象屬於哪個 collection 或 schema？
- 對象在 ontology 分層中的位置（若適用）？
- 對象與 entity 分層的關係（是 entity 的一種，還是獨立 collection）？

#### ② 品質門檻（Quality Gates）

- 受約束的欄位或屬性
- 約束規則（格式、數量、內容要求）
- 違反時的處理（拒絕 / 降級 / 標記待修）

#### ③ 生命週期（Lifecycle State Machine）

- 初始狀態（建立時允許的狀態）
- 終態（不可再轉換的狀態）
- 合法轉換路徑
- 中間態（如 blocked、under review 等）

#### ④ 關聯規則（Relation Rules）

- 必要關聯（建立時至少要連結什麼）
- 關聯數量限制（最少、最多）
- 關聯語意（part_of / impacts / linked_to 等）

#### ⑤ 反饋路徑（Feedback Triggers）

- 哪些事件觸發反饋（狀態改變 / 完成 / 取消 / 取代）
- 反饋對象是什麼（document / entity / blindspot / task）
- 反饋是自動的還是需要人確認

#### ⑥ 衝突仲裁（Conflict Resolution）

通用仲裁順序：

1. 先依內容本質分層（屬於 L2 / L3 / Task / sources 的哪一層）
2. 再套用該層的權威 spec
3. 任何治理 spec 不得覆寫其他層的權威規範
4. 若同層出現兩條矛盾規則，以較晚標為 Approved 的版本為準；未 Approved 的規則不自動生效

---

## 三、現行治理規則實例

本憲法目前有三份實例 spec，分別治理 ontology 中不同層級的對象。

### 3.1 L2 知識節點治理

> **權威 Spec：** [`SPEC-l2-entity-redefinition`](specs/SPEC-l2-entity-redefinition.md)
> **狀態：** Approved

**治理什麼：** L2 Entity = 公司共識概念。不是技術模組，是「改了它，不同角色都會受到影響」的概念。

**核心規則：**
- **三問判斷**：公司共識？改了有下游 impacts？跨時間存活？全過才是 L2。
- **impacts 硬規則**：沒有至少 1 條具體 impacts 路徑，不得存在於 L2。
- **分層路由**：新內容先過三問 → 不過則路由到 L3 document / Task / sources。
- **演算法約束**：必須先建全景再切概念（全局統合模式），禁止逐檔掃描。

**生命週期：** `draft → confirmed ↔ stale`（confirmed/stale 可循環；長期無法通過三問則降級或移除）

**反饋路徑：** impacts 目標被修改/刪除 → 本 L2 標待 review；L2 狀態變更 → 通知掛載的 L3 documents 與 tasks；impacts 變動雙向檢查。

### 3.2 L3 文件治理

> **權威 Spec：** [`SPEC-doc-governance`](specs/SPEC-doc-governance.md)
> **狀態：** Draft

**治理什麼：** 專案內以 Markdown 維護、且需被 ZenOS 納入知識治理的正式文件（SPEC / ADR / TD / PB / SC / REF）。

**核心規則：**
- **Frontmatter 必填**：type、id、status、ontology_entity、created、updated。
- **分類與命名**：六種文件類型，各有前綴與命名規則，不可混用。
- **Ontology 同步契約**：文件的分類、狀態、命名、取代關係任何變更，都必須同步更新 L2/L3 entity。未同步 = 未完成。
- **版本邊界**：實作對齊型更新可直接改；決策改向型更新必須開新文件，舊文件標 Superseded。

**生命週期：** `Draft → Under Review → Approved → Superseded → Archived`

### 3.3 Task 治理（Action Layer）

> **權威 Spec：** [`SPEC-task-governance`](specs/SPEC-task-governance.md)
> **狀態：** Draft

**治理什麼：** Task 是獨立 collection（非 entity），代表可指派、可驗收的具體工作。

**核心規則：**
- **建票品質門檻**：title 動詞開頭、AC 2-5 條、description 含背景/問題/期望。
- **linked_entities 規則**：1-3 個，分 Type A（主要治理節點）/ Type B（影響節點）/ Type C（參考節點）。
- **Plan 層整合**：支援 plan_id / plan_order，task 可歸屬於 plan 做階段管理。
- **知識反饋閉環**：完成後必須反寫 document / blindspot / entity，反饋未完成不得通過驗收。
- **Draft review 流程**：建票後先 review 品質，不合格退回修正。

**生命週期：** `backlog → todo → in_progress → review → done → archived`（+ `blocked` 中間態）

### 3.4 六維比較總覽

**注意**：L2、L3 文件屬於 entity 分層；Task 不屬於任何 entity 層，它是獨立的 collection。在此列入是為對比治理結構的共通性。

| 維度 | L2 知識節點 | L3 文件 | Task（Action Layer） |
|------|-----------|---------|---------------------|
| **對象類型** | entity（L2 層，公司共識概念） | document entity（L3 層） | task（獨立 collection，非 entity） |
| **品質門檻** | 三問全過、summary 跨角色可讀、≥1 條 impacts | frontmatter 必填、分類正確、ontology_entity 有值 | title 動詞開頭、AC 2-5 條、linked 1-3 個 |
| **生命週期** | draft → confirmed ↔ stale（可循環；無法通過三問則降級） | Draft → Under Review → Approved → Superseded → Archived | backlog → todo → in_progress → review → done → archived（+ blocked / cancelled） |
| **關聯規則** | ≥1 條具體 impacts 路徑 | parent_id + source.uri + ontology_entity | linked_entities 1-3 個（Type A/B/C） |
| **反饋路徑** | impacts 目標變動 → 標待 review；狀態變更 → 通知下游 L3/tasks；雙向檢查 | supersede/archive/rename → 更新 L3 entity + 通知引用方；路徑變更原子完成 | 完成後反寫 document / blindspot / entity；知識反饋未完成不得通過驗收 |
| **衝突仲裁** | 不覆寫 L3 或 Task 規則；依憲法仲裁序 | 不覆寫 L2 升降級規則；L2 狀態優先於文件狀態 | 不覆寫 L2 或 L3 規則；Plan 不覆蓋 task 驗收 |

---

## 四、治理規則變更傳播契約

### 核心原則

**治理規則不是孤立的文字。變更任何一條治理規則時，必須同步傳播到所有執行該規則的層級。**

### 傳播層級

```
治理 Spec 變更
     │
     ├─→ ① Protocols（結構化規則）
     │     若已存在，必須同步更新；若尚未結構化，開 task 追蹤。
     │
     ├─→ ② Server 端驗證（MCP tools）
     │     規則改了但驗證沒跟上 = 規則形同虛設。
     │
     ├─→ ③ Skills（Agent 行為）
     │     Skill 是 agent 執行治理規則的入口，必須與 spec 同步。
     │
     ├─→ ④ Analyze 檢查（治理合規）
     │     新規則必須能被 analyze 偵測違規。
     │
     ├─→ ⑤ 下游 Spec（via impacts）
     │     透過 ontology impacts 關聯的其他治理 spec。
     │
     └─→ ⑥ Ontology Entity
           治理節點本身的 metadata。
```

### 強制規則

1. 變更治理 spec 時，必須在 commit 或 PR 中列出受影響的傳播層級。
2. 若某層級目前無法同步，必須開 task 追蹤（符合 `SPEC-task-governance` 建票規範）。不得靜默略過。
3. 傳播完成前，治理 spec 不得標為 Approved；可停留在 Under Review。
4. 本傳播契約本身也是治理規則——修改本契約時，同樣適用此契約。

---

## 五、Skill 架構——治理規則到 Agent 的載體

### 5.1 定位

ZenOS 的治理規則寫在 Spec 裡（what & why），但 Agent 不會自動遵守 Spec。**Skill 是把治理規則翻譯成 Agent 可執行動作序列的載體。**

```
治理 Spec（規則定義）                Agent（執行者）
  SPEC-l2-entity-redefinition          用戶自己的 Agent
  SPEC-doc-governance            ←──  （Claude Code / Codex /
  SPEC-task-governance                  ChatGPT / Gemini / ...）
         │                                    ↑
         ↓                                    │
    Skill（行為規範）              ──────────→ │
      roles/pm.md                   Agent 掛載 Skill
      roles/architect.md            + 連接 MCP
      governance/l3-document.md     = 具備治理能力
      ...
```

### 5.2 核心原則

1. **Skill 不依賴特定 Agent 平台。** Skill 是純 Markdown 行為規範，任何能讀文字的 LLM 都能遵循。不綁定 Claude Code、不綁定任何 SDK。
2. **ZenOS 提供 Skill，不定義 Agent。** Agent 是用戶自己的事（角色、model、偏好）。ZenOS 只提供 Skill（治理行為）和 MCP（ontology 讀寫）。
3. **SSOT 在 ZenOS repo，版本控管。** 所有 Skill 放在 ZenOS repo 的 `skills/` 資料夾，隨 repo 發佈與更新。不同機器、不同專案透過 clone 或同步取得最新版本。
4. **Spec 定義 what，Skill 定義 how。** Spec 和 Skill 是一對搭檔，不是重複。Spec 改了，對應的 Skill 必須同步更新（傳播契約第③層）。

### 5.3 Skill 分類與目錄結構

```
ZenOS repo/
  skills/                          ← SSOT，一般資料夾，git 版控
    README.md                      ← 索引 + 標準載入說明
    roles/                         ← 角色行為定義
      pm.md                          PM：需求訪談、撰寫 Spec、L3 文件治理合規
      architect.md                   Architect：技術設計、L2+L3 治理、subagent 調度
      developer.md                   Developer：實作、不碰文件、回報 spec 差異
      qa.md                          QA：驗收、文件合規檢查、L3 狀態驗證
      designer.md                    Designer：UI/UX 設計、Design System
      marketing.md                   Marketing：文案、SEO、受眾分析
    governance/                    ← 治理規則的 Agent 操作版（可組合、可獨立掛載）
      l2-entity.md                   L2 三問判斷、impacts gate、生命週期操作
      l3-document.md                 L3 文件治理四階段合規流程
      task.md                        Task 建票品質、驗收流程、知識反饋閉環
    workflows/                     ← ZenOS 操作流程
      capture.md                     知識擷取（對話/檔案/目錄三種模式）
      sync.md                        增量同步（git diff → ontology 更新）
      setup.md                       初始化設定（MCP token + skill 安裝）
      governance-loop.md             治理閉環（setup → capture → sync → analyze → fix）
```

**三類 Skill 的差異：**

| 類別 | 用途 | 掛載方式 |
|------|------|---------|
| **roles/** | 定義角色的完整行為（含治理義務） | Agent 掛載對應角色 |
| **governance/** | 獨立的治理規則操作指南 | 按需掛載，可組合（例如 PM 掛 l3-document.md） |
| **workflows/** | ZenOS 工具操作流程 | 需要執行 ZenOS 操作時掛載 |

**roles/ 與 governance/ 的關係：** 角色 skill 引用治理 skill，不重複定義。例如 `roles/pm.md` 會說「寫文件時遵循 `governance/l3-document.md`」，而不是把 L3 治理規則複製一份。

### 5.4 Skill vs Spec 的分工

| | Spec（`docs/specs/`） | Skill（`skills/`） |
|---|---|---|
| **定義** | 治理規則的 what 和 why | Agent 如何遵循規則的 how |
| **讀者** | PM、Architect、人類審查者 | Agent（任何 LLM） |
| **格式** | 六維結構、狀態表、品質門檻 | 動作序列、判斷樹、checklist、模板 |
| **例子** | 「Approved 前 ontology_entity 不得為 TBD」 | 「Step 3c: 若 frontmatter ontology_entity == TBD，開追蹤 task」 |
| **變更頻率** | 低（治理規則穩定後不常改） | 中（隨實作經驗微調流程） |

### 5.5 Agent 掛載 Skill 的標準方式

用戶的 Agent 透過以下方式獲得 ZenOS 治理能力：

```
┌─────────────────────────────────────────────────┐
│ 用戶的 Agent                                      │
│                                                   │
│  1. 掛載 Skill（讀取 skills/*.md）                  │
│     → Agent 知道「寫文件前要查重、要走四階段流程」     │
│                                                   │
│  2. 連接 MCP（ZenOS MCP Server）                   │
│     → Agent 能 search/write/confirm ontology       │
│                                                   │
│  = 按照 ZenOS 治理方式工作                           │
└─────────────────────────────────────────────────┘
```

**掛載方式因平台而異：**

| Agent 平台 | 掛載 Skill 的方式 |
|-----------|-----------------|
| Claude Code | `.claude/skills/` 薄殼指向 `skills/`；或 Agent 定義中 `skills:` 欄位 |
| Codex / OpenAI | System prompt 中引入 skill 內容 |
| ChatGPT Custom GPT | Instructions 中引入 skill 內容 |
| Gemini | System instruction 中引入 skill 內容 |
| 自建 Agent | 啟動時讀取 skill 檔案，注入 context |

**標準載入 Prompt（任何平台通用）：**

```
你是 {角色}。在開始工作前，讀取以下技能定義並嚴格遵循：

角色技能：skills/roles/{role}.md
治理規則：skills/governance/l3-document.md（若需寫/改文件）
治理規則：skills/governance/l2-entity.md（若涉及知識節點操作）

讀完後按照技能中的流程執行。ZenOS ontology 操作使用 MCP tools。
```

### 5.6 與 `.claude/skills/` 的關係

Claude Code 的 `.claude/skills/` 是平台特定的整合機制。在 ZenOS 架構中，它是**薄殼**——指向 `skills/` SSOT，不自己定義治理邏輯。

```
.claude/skills/pm/SKILL.md        ← Claude Code 整合薄殼
  │
  └─→ 引用 skills/roles/pm.md     ← SSOT
  └─→ 引用 skills/governance/l3-document.md
```

若 SSOT 與薄殼內容衝突，以 `skills/` 為準。

### 5.7 Skill 的治理（Skill 本身也是治理對象）

Skill 的變更適用傳播契約：

- Spec 改了 → 對應 Skill 必須同步更新（傳播契約第③層）
- Skill 改了 → 不需要改 Spec（Skill 是 how，Spec 是 what）
- Skill 改了 → 對應的 `.claude/skills/` 薄殼必須同步（若有）

Skill 的品質門檻：

- 每個 Skill 必須有明確的角色邊界（做什麼、不做什麼）
- 治理相關 Skill 必須引用權威 Spec 作為依據
- Skill 的動作序列必須可被 Agent 無歧義地執行

---

## 六、演進路徑

```
Phase 0（現在）
  規則以 prose 寫在 spec 文件中。
  傳播靠人工 checklist。
  Agent 靠讀 skill 遵循規則。

Phase 1（結構化）
  觸發條件：protocols collection 首次建立，或傳播遺漏造成生產問題。
  規則同時寫入 protocols collection（machine-readable）。
  MCP tools 讀 protocol 做 server 端驗證。
  Skill 可從 protocol 自動生成或校驗。

Phase 2（自動治理）
  觸發條件：Phase 1 穩定運行，且多個外部客戶導入。
  analyze 自動偵測違規。
  規則變更自動觸發傳播 pipeline。
  Governance lint 成為 CI 的一部分。
```

---

## 七、ZenOS 文件索引

本文件（憲法）之下，ZenOS 的受治理文件分布如下：

### 產品與架構

| 文件 | 類型 | 內容 |
|------|------|------|
| [`SPEC-product-vision`](specs/SPEC-product-vision.md) | SPEC | North Star、核心命題、一句話定位 |
| [`SPEC-ontology-architecture`](specs/SPEC-ontology-architecture.md) | SPEC | Ontology 技術路線、Entity 分層、雙層治理、四維標籤 |
| [`SPEC-progressive-trust`](specs/SPEC-progressive-trust.md) | SPEC | 漸進式信任模型（三階段） |
| [`ADR-007-entity-architecture`](decisions/ADR-007-entity-architecture.md) | ADR | Entity 架構決策（三層模型、Task 不是 entity） |
| [`ADR-008-dashboard-multi-view`](decisions/ADR-008-dashboard-multi-view.md) | ADR | Dashboard 多 View 架構決策 |
| [`ADR-009-permission-model`](decisions/ADR-009-permission-model.md) | ADR | 權限模型 Phase 0 設計（已被 SPEC-agent-aware-permission 取代） |

### 治理規則（本憲法的實例）

| 文件 | 類型 | 治理對象 |
|------|------|---------|
| [`SPEC-l2-entity-redefinition`](specs/SPEC-l2-entity-redefinition.md) | SPEC | L2 知識節點 |
| [`SPEC-doc-governance`](specs/SPEC-doc-governance.md) | SPEC | L3 文件 |
| [`SPEC-task-governance`](specs/SPEC-task-governance.md) | SPEC | Task（Action Layer） |
| [`SPEC-governance-observability`](specs/SPEC-governance-observability.md) | SPEC | 治理 pipeline 可觀測性 |

### 技術設計

| 文件 | 類型 | 內容 |
|------|------|------|
| [`TD-three-layer-architecture`](designs/TD-three-layer-architecture.md) | TD | 三層架構（資料層/Agent層/展示層） |
| [`TD-service-architecture`](designs/TD-service-architecture.md) | TD | 服務架構（事件源/治理引擎/確認同步） |
| [`TD-action-layer`](designs/TD-action-layer.md) | TD | Action Layer 技術設計（已被 SPEC-task-governance 取代） |

### 參考資料

| 文件 | 類型 | 內容 |
|------|------|------|
| [`REF-competitive-landscape`](reference/REF-competitive-landscape.md) | REF | 競品定位研究 |
| [`REF-taiwan-smb-positioning`](reference/REF-taiwan-smb-positioning.md) | REF | 台灣 SMB 市場定位 |
| [`REF-adapter-feasibility`](reference/REF-adapter-feasibility.md) | REF | Adapter 可行性研究 |
| [`REF-glossary`](reference/REF-glossary.md) | REF | 概念速查與關鍵發現 |
| [`REF-active-spec-surface`](reference/REF-active-spec-surface.md) | REF | 現行 active spec 清單 |
| [`REF-open-decisions`](reference/REF-open-decisions.md) | REF | 待決策項目（從原 Part 8 搬出） |

### 操作手冊

| 文件 | 類型 | 內容 |
|------|------|------|
| [`PB-onboarding-strategy`](playbooks/PB-onboarding-strategy.md) | PB | 導入策略與知識重組流程 |
| [`PB-zenos-shared-cloudsql`](playbooks/PB-zenos-shared-cloudsql.md) | PB | Cloud SQL 部署 |
| [`PB-zenos-sql-cutover`](playbooks/PB-zenos-sql-cutover.md) | PB | SQL Cutover Runbook |

---

## 八、完成定義

1. 本文件已列入 `REF-active-spec-surface`。
2. 現行三份治理 spec 的六維映射表通過交叉比對驗證。
3. 傳播契約的六個層級定義清楚，且至少一次實際傳播有留存證據。
4. 新治理 spec 撰寫時，PM 可依據六維模型作為 checklist；Architect 可據此審查完整性。
5. `skills/` 資料夾已建立，至少包含 roles/、governance/、workflows/ 三個子目錄。
6. 至少一個非 Claude Code 的 Agent 平台成功透過標準載入 Prompt 掛載 Skill 並執行治理流程。
