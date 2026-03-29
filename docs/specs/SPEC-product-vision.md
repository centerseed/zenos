---
type: SPEC
id: SPEC-product-vision
status: Approved
ontology_entity: TBD
created: 2026-03-19
updated: 2026-03-27
---

# ZenOS 產品願景與核心命題

> 從 `docs/spec.md` Part 0 + Part 1 搬出。


### 一句話定位

**ZenOS 是中小企業的 AI Context 層——建一次 ontology，公司的每一個 AI agent 都共享同一套 context，讓每次 AI 互動都從「懂你的公司」開始。**

### 終極目標

**全公司同一套 context。** 這件事最大的受益者不是人，是 AI agents。

現在的世界是 AI 孤島：每個員工各自 prompt，每個 AI agent 各自的 context，結果是——AI 放大了資料孤島，而不是打破它。

ZenOS 讓所有 AI agent 共享一套公司級的 context：
- 老闆問 AI 行銷策略 → AI 已經知道產品路線圖、客群定義、上季決策
- 行銷夥伴請 AI 寫文案 → AI 已經知道哪些功能上線了、目標客群是誰
- 新人讓 AI 組裝 onboarding 資料 → AI 讀完 ontology 就能產出「你需要知道的一切」
- 任何一個新 AI agent 被部署 → 第一步讀 ontology → 立刻理解整間公司 → 即插即用

**這是 AI 時代的基礎設施。建一次 ontology，每一次 AI 互動都受益。**

### 跟現有解法的本質差距

| 現有解法 | 做什麼 | 為什麼不夠 |
|---------|--------|-----------|
| 文件共享（Notion / Confluence） | 讓人找到文件 | Garbage in, garbage out——沒人治理，AI 讀也是垃圾 |
| 企業搜尋（Glean） | 讓人搜得快 | 只搜不治——文件品質差，查得快也沒用。AI agent 不需要搜尋，需要 context |
| ERP 系統（SAP / Odoo） | 強迫人改流程 | 導入成本高、員工抗拒。而且只處理結構化資料 |
| AI 落地顧問 | 一個一個做 AI 方案 | 每個方案重新理解 context，不可規模化。顧問走了 context 斷了 |

**共同盲點：它們都在解決「人怎麼找到資訊」，沒有人在解決「AI agent 怎麼理解整間公司」。**

ZenOS 不改變人的任何習慣。它在所有文件之上長出一層語意代理，讓 AI 理解公司全貌。人也受益（全景圖、Protocol），但那是副產品。主產品是那一套 ontology——AI agents 的 context 層。

### 為什麼這個問題沒有被解決

這不是工具的問題。根本原因是**知識邊界**（Knowledge Boundaries, Carlile 2004）：

1. **語法邊界** — 資訊格式不通（已被現代工具解決）
2. **語意邊界** — 資訊傳過去了，但各部門解讀不同（現有工具解決不了）
3. **實務邊界** — 就算看懂了，各部門利益和優先級不同，知識無法直接套用

製造業用 PLM / Digital Twin 解決了這個問題，因為物理產品是天然的跨部門錨點——所有部門天然圍繞同一個物理存在協作。但知識工作沒有這個錨點。

Palantir 用 Ontology 為大型組織解決了結構化資料的跨部門問題。但它只處理結構化資料、只服務大型企業、導入成本數百萬。

**中小企業的非結構化知識治理——這個格子是空的。ZenOS 填這個格子。**

```
                    結構化資料              非結構化知識

大型企業            Palantir / SAP          （沒有產品）

中小企業            Oversai（CX 限定）       ← ZenOS
```

### 核心洞察：AI Context Layer for SMB

ZenOS 的核心不是另一個文件管理系統，不是另一個搜尋引擎，不是另一個 ERP，更不是另一個 AI 落地顧問。

**ZenOS 是公司級的 AI Context 層——一套所有 AI agent 共享的知識本體。**

1. **語意代理（Semantic Proxy）** — 不改變各部門的文件管理習慣，在所有文件之上長出一層 ontology。每個 entry 是文件的「代理人」，承載多面向的 context（What/Why/How/Who）。AI agent 讀 ontology 就能判斷相關性，不用讀原始文件。
2. **自動治理** — 文件 CRUD 自動觸發 ontology 更新。四維標籤是 AI 治理的依循。人不用花心思維護，但公司多了一層全局 context。
3. **AI Agent 的 context 入口** — 任何 AI agent 第一步讀 ontology → 立刻理解整間公司 → 再依需求連結對應的文件資料。Ontology 就像每間公司的 CLAUDE.md——讓 AI 一秒接手。

**為什麼這是護城河：**

```
Ontology 建一次    → 每個 AI agent 都受益（不像顧問做一個方案只解一個問題）
Ontology 自我成長  → 每次 AI 互動都可能豐富 context
Ontology 有網路效應 → 越多部門參與，context 越完整，AI 越有用，更多人想參與

競爭壁壘不只是 context 本身，更是「如何建立 context」的方法論：
  - 四維標籤體系（怎麼標注才能讓 AI 自動治理）
  - 雙層治理架構（骨架層 + 神經層怎麼互相餵養）
  - 漸進式信任模型（怎麼從零到完整 ontology）
  - ontology 觸發規則（什麼事件該觸發什麼更新）
  - 拆分粒度規則（一間公司的知識該切成多細）

  這些方法論是從反覆 dogfooding 和實戰中慢慢累積出來的。
  競爭者可以抄技術架構，但他不知道「怎麼建出有用的 ontology」。
  就像 Palantir 的護城河不是程式碼，是那套 ontology 建構方法論。
```

### 四維標籤體系

源自 Ranganathan 分面分類理論（1933, PMEST）的普世維度。任何行業、任何公司的知識，都可以用這四個問題標注：

| 維度 | 問的問題 | 範例 |
|------|---------|------|
| **What**（產品 / 功能） | 這跟什麼東西有關？ | ZenOS / 自動排班 |
| **Why**（目標） | 為什麼做這件事？ | 進入顧問市場 |
| **How**（專案 / 活動） | 怎麼做的、什麼階段？ | Q1 上線專案 |
| **Who**（角色 / 客戶） | 誰寫的、給誰的？ | 開發團隊 / 顧問客戶 |

**維度是固定的（人定義），值是動態的（AI 填）。**

AI 讀每份文件的內容，自動判斷它跟哪個產品有關、服務什麼目標、屬於哪個專案、涉及誰。治理成本趨近於零。

#### Who 的三層消費模型

Who 標籤的值是職能角色（functional role），但 context 的消費者可能是人、也可能是 agent。不同公司的 agent 成熟度不同（無 agent → agent 當工具 → agent 當獨立角色），Who 的設計必須在整個光譜上都能運作。

```
Ontology 層（ZenOS 管）
  Who: [marketing, product, ...]     ← 純職能角色，不管誰接

公司層（老闆/主管設定，全公司可見）
  marketing → Barry, 小美            ← 角色→員工的對應

個人層（員工自己設定，只有自己看得到）
  Barry → copywriter-agent, ...      ← 員工→agents 的路由
```

| 層 | 誰設定 | 誰看得到 | 變動頻率 |
|----|--------|---------|---------|
| 職能角色 | ZenOS AI + 人確認 | 全公司 | 低 |
| 角色→員工 | 老闆/主管 | 全公司 | 中 |
| 員工→agents | 員工自己 | 只有自己 | 高（隨時加減 skill） |

**設計原則：Pull Model，不是 Push Model。** Agent 透過 MCP 讀 ontology 時，自帶角色過濾條件（`query_ontology(who: "marketing")`）。ZenOS 不維護 agent registry，不需要知道有多少 agent 存在。新增 agent = 新增 skill + 在 skill 定義裡宣告職能角色，零綁定成本。

**ZenOS 的責任邊界：** 提供按 Who 過濾的 MCP query 介面 + agent 身份宣告的指引文件。不參與員工底下 agents 的管理或路由。

詳見 `docs/reference/REF-enterprise-governance.md`「Who 的三層消費模型」章節。

### Context Protocol — 跨部門的 SSOT

每個業務實體（產品、功能、服務項目）維護一份 **Context Protocol**——不是部門文件，是全公司的共享真相。

在軟體公司叫 PRD，在顧問公司叫服務提案，在餐廳叫品項卡。名字不同，結構相同：

```
Context Protocol = What + Why + How + Who 的結構化表達

各部門文件圍繞 Protocol 展開：
  開發 → 技術規格（What 的展開）
  行銷 → 文案素材（Why + Who 的展開）
  客服 → FAQ（What + How 的展開）
  業務 → 報價策略（Why + Who 的展開）
```

每份部門文件透過標籤連回 Protocol。Protocol 變了，AI 主動通知相關部門文件可能需要同步。

### AI 的治理責任

AI 不是寫文件的人，是治理文件品質的人：

| 責任 | 說明 |
|------|------|
| **自動標注** | 讀文件內容，自動貼上 What / Why / How / Who 標籤 |
| **完整性檢查** | Protocol 的四個維度是否都有內容，缺了提醒負責人 |
| **一致性檢查** | 部門文件跟 Protocol 是否衝突（行銷寫的跟開發做的對不上） |
| **新鮮度檢查** | Protocol 最後更新時間過久，提醒確認是否過期 |
| **衍生同步** | Protocol 更新後，通知相關部門文件可能需要連動更新 |

---

## Part 1 — 核心命題

傳統 ERP 失敗的根本原因不是系統不夠強，而是兩個根本假設錯了：

1. **「流程可以在導入前就設計好」** — 現實的業務流程是活的，會隨業務演化
2. **「員工會配合系統輸入結構化資料」** — 人的輸入摩擦是無法規模化解決的

本架構的核心轉換：

> **把人與資料庫的摩擦，變成 AI 與資料庫的摩擦（由開發者維護）**

員工用最自然的方式輸入，AI 負責翻譯成結構化資料。流程定義保持彈性，系統適應現實而不是逼現實適應系統。

### 與既有產品的差異

| | ERP | Palantir | Glean | ZenOS |
|---|---|---|---|---|
| 核心功能 | 業務流程管理 | 結構化資料 Ontology | 企業搜尋 | 知識 Ontology（語意代理層）+ 業務流程 |
| Ontology 形式 | 流程定義 | DB Schema + Action | 自動索引（無治理） | 語意代理（骨架層 + 神經層）|
| 資料類型 | 結構化 | 結構化 | 非結構化（只讀） | 結構化 + 非結構化（讀寫治理） |
| 目標客戶 | 中大型企業 | 政府 / 大型企業 | 中大型企業 | 中小企業 |
| 導入成本 | 半年 + 數百萬 | 數月 + 數百萬 | 數週 + 高月費 | 趨近於零 |
| 誰適應誰 | 人適應系統 | 人定義 Ontology | 不治理 | AI 適應人，不改部門習慣 |
| 跨部門 context | 靠流程強制 | 靠 Ontology 串連 | 靠搜尋 | 靠語意代理 + Protocol + AI 自動治理 |

---


---

## 四大業務種類（公司治理角度）

| 業務 | 範疇 | 對應資料層 |
|------|------|-----------|
| **行銷** | 獲客、市場、素材 | `campaigns` |
| **管理** | 金流、開銷、收支 | `finances` |
| **開發** | 需求、方向、進度 | `projects` |
| **客服 / CRM** | 客戶、合作夥伴 | `contacts`、`orders` |

四大業務透過 Agent 層統一操作資料層，員工不需要直接面對資料庫。
