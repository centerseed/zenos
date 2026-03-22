# AI-Native 小型公司作業系統 — 產品 Spec

> 日期：2026-03-19（2026-03-20 架構對齊｜2026-03-21 North Star 更新｜2026-03-21 Ontology 架構定義）

---

## Part 0 — North Star

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

詳見 `enterprise-governance.md`「Who 的三層消費模型」章節。

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

## Part 2 — 治理架構總覽

### 四大業務種類（公司治理角度）

| 業務 | 範疇 | 對應資料層 |
|------|------|-----------|
| **行銷** | 獲客、市場、素材 | `campaigns` |
| **管理** | 金流、開銷、收支 | `finances` |
| **開發** | 需求、方向、進度 | `projects` |
| **客服 / CRM** | 客戶、合作夥伴 | `contacts`、`orders` |

四大業務透過 Agent 層統一操作資料層，員工不需要直接面對資料庫。

---

## Part 3 — 三層架構

### Layer 1 — 資料層（Firestore）

**原則：** 最穩定、最少變動、AI 可直接讀寫

**公版 Schema（五大 Collection）**

```
contacts/
  - contactId
  - name
  - aliases[]           # 「王大明」「王先生」「大明」同一人
  - type                # lead / partner / customer
  - phone / email
  - sourceText
  - confirmedByUser
  - createdAt

finances/
  - financeId
  - type                # income / expense
  - amount
  - category
  - relatedOrderId      # ref to orders（如適用）
  - dueDate
  - paidAt              # null = 未收付款
  - status              # pending / overdue / paid
  - sourceText
  - confirmedByUser
  - createdAt

projects/
  - projectId
  - name
  - status              # planning / active / on_hold / completed
  - roadmap             # 方向描述
  - sourceText
  - confirmedByUser
  - createdAt

projects/{projectId}/tasks/
  - taskId
  - title
  - assignee
  - status              # todo / in_progress / done
  - dueDate
  - sourceText
  - confirmedByUser

campaigns/
  - campaignId
  - name
  - type                # leads / assets
  - status              # draft / active / completed
  - targetAudience
  - sourceText
  - confirmedByUser
  - createdAt

orders/
  - orderId
  - contactId           # ref to contacts
  - status              # pending / confirmed / in_production / shipped / closed
  - dueDate
  - paymentTerms
  - sourceText          # 原始輸入，保留供 debug
  - sourceChannel       # line / email / form
  - confirmedByUser     # false = draft，true = 正式寫入
  - createdAt
  - createdBy

orders/{orderId}/items/
  - itemId
  - productId           # ref to products
  - productName
  - quantity
  - unitPrice           # null = 待補
  - status

orders/{orderId}/payments/
  - paymentId
  - amount
  - dueDate
  - paidAt              # null = 未收款
  - status              # pending / overdue / paid

products/
  - productId
  - name
  - aliases[]
  - safetyStock
  - currentStock
  - unit
```

**所有 Collection 共用原則：**
- `sourceText` 必存，保留原始輸入供 debug 和重新解析
- `confirmedByUser` 控制 draft / 正式狀態，防止 AI 誤判直接污染資料
- `aliases[]` 處理同義詞對應問題，由 AI 在寫入前比對
- null 優於猜測，缺漏欄位留 null 並觸發補充提醒

**客製部分（20~30%，依產業調整）**

| 產業 | 額外 Collection |
|------|----------------|
| 製造業 | `workOrders` / `bom` |
| 服務業 | `contracts` / `milestones` |
| 貿易商 | `customs` / `exchangeRates` |

---

### Layer 2 — Agent 層

**原則：** 中介人與資料庫之間，承擔所有翻譯與主動邏輯

Agent 有四種角色，共用同一個 Firestore：

#### 2a. 輸入 Agent（被動）
自然語言 → 結構化資料寫入 Firestore

```
流程：
1. 解析自然語言，抽出實體（客戶、品項、數量、交期）
2. 實體對應：查 Firestore 比對 name + aliases
3. 缺漏偵測：有標準答案的自動帶入，沒有的留 null
4. 產生確認訊息回給員工
5. 員工確認後正式寫入（confirmedByUser: true）
```

#### 2b. 查詢 Agent（被動）
任何角色用自然語言問，AI 撈對應資料回答

```
範例：
「王大明的訂單出了嗎？」→ 查 orders，filter by contactId
「這個月還有哪些款沒收？」→ 查 finances，filter status = overdue
「A零件還剩多少？」→ 查 products.currentStock
「行銷活動的 leads 有多少？」→ 查 campaigns
「開發進度到哪了？」→ 查 projects + tasks
```

#### 2c. 監控 Agent（主動）
定期掃描或 onWrite 觸發，主動推播異常

**兩種觸發機制：**

| 類型 | 機制 | 範例 |
|------|------|------|
| 事件驅動 | Firestore onWrite + Cloud Functions | 訂單確認 → 立刻通知採購 |
| 狀態監控 | 排程觸發（每日） | 每早檢查逾期帳款 |

**公版預設通知規則（預設開啟）：**

```
庫存類    currentStock < safetyStock + 有未完成訂單
訂單類    dueDate 剩 3 天，status != shipped
          訂單確認後 24hr，status 仍 pending
財務類    finances.dueDate 已過，paidAt = null
採購類    採購單發出後 X 天未收到供應商回覆
專案類    task.dueDate 已過，status != done
```

#### 2d. 簽核 Agent（主動）
條件觸發，發起決策對話，等待回應後推進狀態

```
觸發條件範例（自然語言定義，存在 Firestore）：
「採購金額超過 10 萬要我點頭」
「報價單出去之前讓我看一眼」

流程：
1. 偵測到觸發條件
2. 發訊息給指定角色，附上完整資訊
3. 等待回應（好 / 不行 / 修改）
4. 更新 Firestore 狀態，通知發起人繼續或退回
```

**通知路由設計：**

不用設定規則，改用「責任描述」：
```
採購：「我負責所有跟料件有關的事」
業務：「我負責我自己的客戶訂單」
老闆：「我要看所有逾期和異常」
```
Agent 根據責任描述決定通知路由，員工事後可調整：「這種通知不用給我」

---

### AI 驅動核心能力

Agent 層之下，支撐四種 Agent 運作的核心能力：

| 能力 | 說明 |
|------|------|
| **排程自動化** | 定期觸發監控、狀態檢查、主動推播 |
| **責任路由** | 根據自然語言描述的職責，自動決定通知和簽核路由 |
| **信任曲線管理** | confirmedByUser 機制、draft 狀態、漸進式授權 |
| **知識沉澱** | sourceText 保留、aliases 累積、業務規則自然語言化存入 Firestore |

---

### Layer 3 — 展示層

**原則：** 補充 Agent 低效的部分，不是主要操作介面

適合用 UI 而非 Agent 處理的場景：

| 場景 | 原因 |
|------|------|
| 儀表板 | 全局總覽，圖表比文字直觀 |
| 批次操作 | 一次改十張訂單狀態，自然語言很慢 |
| 通知規則管理 | 查看 / 修改現有規則 |
| 權限設定 | 誰可以看什麼，需要明確的設定介面 |
| 報表分析 | 跨業務的趨勢分析、視覺化比較 |

---

## Part 4 — Knowledge Ontology 技術路線

### 業界做法研究

| 做法 | 代表 | Ontology 誰建 | 資料來源 | 精確度 | 導入成本 | 治理能力 |
|------|------|-------------|---------|--------|---------|---------|
| 由上而下定義 | Palantir | 人工定義 Object Type / Property / Link | 結構化資料庫 | 極高 | 極高 | 強（人工維護） |
| 由下而上推斷 | Glean | ML 自動推斷實體和關係 | 所有工具的內容 + metadata | 中等 | 極低 | 無 |
| LLM 自動建構 | OntoEKG（學術） | LLM 提取 + 人審核 | 非結構化文件 | 中高 | 中等 | 理論上有，未產品化 |

**Palantir 的做法**：人工定義 Object Type → Data Pipeline 從資料庫灌入 → AI（AIP）在 Ontology 之上查詢和行動。極度精確但極度昂貴，且要求資料已在結構化資料庫中。

**Glean 的做法**：100+ Connector 爬所有工具 → ML 自動識別實體 → 從信號推斷關係。零人工但無業務語意治理，推斷不準也不會告訴你。

**學術前沿（OntoEKG, 2025）**：LLM 從非結構化文件中提取 class 和 property → 組織成階層 → 序列化為標準格式。有潛力但仍需人工審核，未產品化。

### Ontology 的形式與治理架構

#### 三種可能方向（及 ZenOS 的選擇）

| 方向 | 做法 | 優點 | 缺點 |
|------|------|------|------|
| **專案導向** | 開案時建 ontology，文件圍繞 ontology 組織，ontology 本身就是文件 | 高品質、高內聚 | 難維護、建構成本高 |
| **標籤索引** | Ontology 是持續更新的標籤系統，文件 CRUD 觸發標籤治理 | 低摩擦、不改習慣 | 治理深度低、標籤漂移 |
| **DB Schema + 動作** | Ontology 是資料庫定義 + 受控操作（Palantir 模式） | 最嚴謹、可擴展 | 導入成本 SMB 負擔不起 |

**ZenOS 的選擇：結合方向 1 和方向 2。**

方向 1 提供骨架（高品質的實體關係圖），方向 2 提供神經（持續更新的文件級標籤）。兩者在文件 CRUD 事件中融合——標籤治理發生的當下也產生或更新 ontology entry，並找尋關聯的 ontology 實體。

#### Ontology 的本質：文件的語意代理（Semantic Proxy）

Ontology 不是文件本身，不是文件的索引，不是資料庫 schema。Ontology 是每份文件（或一組相關文件）的**語意代理**。

```
傳統做法：人 → 翻遍 Google Drive / Notion / Slack → 找到文件 → 讀完 → 判斷有沒有用
ZenOS 做法：人或 AI → 讀 ontology entry → 知道這份文件講什麼、為什麼存在、給誰用 → 需要時才讀原始文件
```

每個 ontology entry 承載：

| 欄位 | 內容 | 來源 |
|------|------|------|
| What | 這份文件跟什麼實體有關 | AI 自動標注（高準確） |
| Why | 為什麼這份文件存在 | AI 推斷 + 人確認 |
| How | 怎麼用、什麼階段 | AI 推斷 + 人確認 |
| Who | 誰寫的、給誰看 | AI 自動標注（高準確） |
| 關聯實體 | 連結到骨架層的哪些實體 | AI 推斷 + 人確認 |
| 原始位置 | 文件在哪個平台、哪個路徑 | 系統記錄 |
| 狀態 | 現行 / 過時 / 草稿 / 衝突 | AI 推斷 + 人確認 |
| confirmedByUser | 這個 entry 有沒有被人確認 | 系統記錄 |

**ontology entry 跟「好的摘要」的差別：關係。** 摘要只描述一份文件，ontology entry 描述一份文件在公司知識網路中的位置——它跟哪些實體有關、在哪個業務流程中被使用、跟哪些其他文件矛盾或互補。

#### 雙層治理架構

```
骨架層（Skeleton Layer）— 來自方向 1
  什麼：公司的實體關係圖（產品、目標、角色、專案 + 它們之間的關係）
  怎麼建：30 分鐘對話 → 全景圖 → 迭代收斂 2~3 輪
  變動頻率：低（一季一次）
  治理方式：人確認（confirmedByUser）
  類比：Palantir 的 Object Type + Link Type，但由 AI 建、人確認

神經層（Neural Layer）— 來自方向 2
  什麼：每份文件的 ontology entry（語意代理）
  怎麼建：文件 CRUD 事件自動觸發
  變動頻率：高（每天）
  治理方式：AI 自動標注，人可覆寫
  類比：Glean 的自動索引，但帶四維業務語意
```

**兩層互動：**

神經層的異常反推骨架層更新：

```
觸發情境                                       骨架層建議
──────                                       ────────
連續多份新文件都無法關聯到任何已知實體          「看起來有一個新產品/專案還沒進 ontology，要不要加？」
某實體三個月沒有任何新文件關聯                  「這個產品是不是已經停了？」
兩個原本無關的實體突然開始共享文件              「這兩個產品是不是在整合？」
同一主題出現兩份互相矛盾的文件                  「這兩份文件哪份是正確的？」
```

所有骨架層建議都是 draft，需要 confirmedByUser 才生效。

#### AI Agent 的工作流程

公司的 AI agents 讀取 ontology 的方式，跟 Claude 讀取 SKILL.md 的方式一樣：

```
Step 1 — 讀 ontology（骨架層）
  「這間公司有 4 個產品、3 個部門、這些是關鍵關係和目標」
  → 建立公司全局理解

Step 2 — 根據任務需求，從 ontology 找相關 entry（神經層）
  「這個任務需要 Paceriz 的定價策略，ontology 說相關文件在 marketing/paceriz.md」
  → 語意代理充當路由

Step 3 — 透過 ontology 的指引去讀實際文件
  → 拿到真正的資料，執行任務
```

Ontology entry 就是每份公司文件的 SKILL.md——告訴 AI「這份文件能幹嘛、什麼時候該讀、怎麼用」。

#### Ontology 架構演化路線

```
Phase 0（現在）— 手動 + Markdown
  骨架層：ontology.md（實體 + 關係 + 文件索引）
  神經層：不存在（文件量小，手動可管）
  Context Protocol：手寫的 .md 文件
  → 驗證概念正確性，不依賴存儲格式

Phase 1 — 輕量 DB
  骨架層：SQLite / JSON（BYOS 友好，單機可跑）
  神經層：文件 CRUD webhook → AI 自動建 entry
  Context Protocol：從 ontology 自動生成的 view（人微調確認）
  → 驗證自動治理的準確率

Phase 2+ — 結構化存儲
  骨架層：PostgreSQL + Graph index
  神經層：即時同步 + 跨實體查詢
  Context Protocol：動態生成，底層資料變了 view 自動變
  → 支援盲點推斷、過時偵測等高階分析
```

**關鍵設計原則：Context Protocol 不是 ontology 本身，它是 ontology 的 view。** 就像 SQL 的 view，底層資料變了 view 就自動更新。現在手寫 paceriz.md 是因為 Phase 0 沒有系統，未來這份文件應該是從 ontology 自動生成、人微調確認的。

#### Ontology 的層次結構

```
Meta-Ontology（1 份，ZenOS 產品定義）
  定義：四維標籤體系、confirmedByUser 機制、治理規則
  性質：Schema — 「一間公司的 ontology 應該長什麼樣」
  變動：極少（除非發現四維不夠用）

  └── Company Ontology（每客戶 1 份）
        定義：某間公司的骨架層 + 神經層
        性質：Instance — 某間公司實際填完的 ontology
        變動：骨架低頻、神經高頻

        ├── Entity Protocol: 產品 A（Context Protocol）
        ├── Entity Protocol: 產品 B
        ├── Entity Protocol: 目標 X
        └── ...按需展開
```

Schema 只需要一套（Meta-Ontology），Instance 每間公司一份。增長的是 Instance 的數量和每個 Instance 的領域深度，不是 Schema 本身。

#### 已知風險與驗證計畫

**市場現況：** 碎片存在，完整產品不存在。Microsoft Semantic Index（最接近但鎖死微軟生態）、Glean（實體中心非文件中心）、Collibra Unstructured AI（面向大企業）、GraphRAG（基礎設施層非產品）都做了拼圖的一塊，但沒有面向 SMB 的整合產品。

| 風險 | 說明 | 驗證方式 | Phase 0 能驗？ |
|------|------|---------|--------------|
| **AI 標籤幻覺** | LLM 自動建知識圖譜時高比例節點捏造。What/Who 準確但 Why/How 可能幻覺。confirmedByUser 對沖但若大部分都要改則自動治理破產 | What/Who 自動標準確率 >90%？ | ✅ 用 Naruvia 文件測 |
| **過時偵測** | 最危險的是「文件沒動但內容已過時」。所有現有產品都沒有可靠方案 | 跨實體更新頻率推斷能否抓到過時？ | ⚠️ 小規模可測 |
| **跨平台權限** | ontology entry 包含太多 context 可能繞過原始權限。BYOS 解決跨客戶但不解決公司內部角色權限 | Who 維度能否當過濾器？ | ✅ 定義規則即可 |
| **部門存取授權** | SMB 沒有 IT team 打通 API。實際可能是老闆手動上傳，覆蓋率低影響全景性 | 手動上傳 vs API 的 ontology 覆蓋率差異 | ❌ 需真實客戶 |
| **語意代理 vs 摘要** | 如果骨架層品質差，entry 退化成 tag 較多的摘要，價值有限 | 有關係 entry vs 純摘要，AI 任務完成率差異 | ✅ 可設計 A/B 測試 |
| **Demo vs Production gap** | 知識工具常在 demo 很強但 production 失敗，根因是底層資料品質差 | 持續 dogfooding + 真實客戶驗證 | ⚠️ dogfooding 部分可驗 |

### ZenOS 的路線：confirmedByUser 混合模式

ZenOS 不走 Palantir（太貴）、不走 Glean（不治理）、不走純學術路線（未產品化）。

關鍵洞察：**ZenOS 資料層已有的 `confirmedByUser` 模式，直接延伸到知識層。**

```
confirmedByUser 在資料層：
  員工說「王大明訂了 100 個」→ AI 解析為結構化資料（draft）→ 員工確認 → 正式寫入

confirmedByUser 在知識層：
  開發寫了一份 BDD → AI 自動標注 What/Why/How/Who（draft）→ 負責人確認 → 標籤生效
```

同一套設計哲學、同一個信任機制，從結構化資料延伸到非結構化知識。

### 建構流程（五步驟，Step 2 為核心）

```
Step 1 — 輕量骨架（人定義，一次性）
  四個維度是固定的：What / Why / How / Who
  Context Protocol 模板是固定的
  → Palantir 的極簡版：不定義幾百種 object type，只定義四個維度

Step 2 — 導入啟動（AI 主導，業主驗證）→ 詳見下方完整流程
  2a. AI 掃描既有文件（非程式碼）→ 產出公司全景圖
  2b. 老闆看全景圖 → 建立信任 + 發現盲點 → 指派高管補資料
  2c. 迭代收斂 2~3 輪 → 鎖定 v1 Ontology
  2d. 為每個產品產出 Context Protocol → 各部門可用

Step 3 — 日常治理（AI 自動，人確認）→ 詳見下方「Ontology 觸發規則」
  何時新建 ontology entry？何時更新？何時歸檔？
  不同階段（設計期 vs 營運期）的觸發源不同
  → confirmedByUser 從資料層延伸到知識層

Step 4 — AI 持續治理（監控 Agent 的延伸）
  完整性：Protocol 四個維度有缺嗎？
  一致性：部門文件跟 Protocol 矛盾嗎？
  新鮮度：超過 X 天沒更新？
  衍生同步：Protocol 更新 → 通知相關部門文件需連動
  過時推斷：跨實體更新頻率異常 → 建議 review
  → Palantir AIP Logic 的簡化版

Step 5 — Ontology 演化
  新產品上線 / 目標調整 / 組織變動 → 觸發 ontology 更新
  回到 Step 2c 的迭代收斂，不需要從頭開始
```

### Step 2 完整流程：導入啟動

Step 2 是 ZenOS 能否成功導入的關鍵。它不是「填表」，是「展示能力 → 建立信任 → 逐步收斂」。

設計原則：**老闆是 top-down 思維。不要先問他要什麼，先讓他看到 AI 已經理解了什麼。**

#### Step 2a — AI 產出公司全景圖（信任 Stage 0：只需對話）

**資訊來源：只有對話。** 不讀文件、不掃程式碼、不進資料庫。老闆只需要回答「可以寫在官網上」的問題：你有幾個產品？叫什麼？現在最重要的目標？誰在做什麼？

AI 從對話中自動產出「公司全景圖」：

```
全景圖包含：
  ① 公司在做什麼 — 所有產品線、基礎架構、行銷資產
  ② 現在為什麼而戰 — 活躍目標（由老闆口述，AI 結構化）
  ③ 事情之間怎麼連 — 產品間的依賴和關聯
  ④ 誰在做什麼 — 角色和職責分佈
  ⑤ AI 發現的盲點 — 跨產品推斷出的風險和矛盾（關鍵差異化）
  ⑥ 每個盲點的 Ontology 解法 — 不只看到問題，還看到怎麼解

→ 全景圖 = ZenOS 的免費增值入口
→ 零機密風險（全部來自對話，不含任何文件內容）
→ 30 分鐘見效
```

如果老闆在 Stage 1 選擇開放部分文件，AI 會用文件佐證來提高全景圖的準確度。但全景圖不依賴文件——純對話也能產出有價值的結果。

**AI 標注準確度因維度而異**（2026-03-21 驗證）：

| 維度 | AI 準確度 | 原因 |
|------|----------|------|
| **What**（產品） | 高 | 文件中有明確錨點（產品名、功能描述） |
| **Who**（角色） | 高 | 文件內容和組織結構能推斷 |
| **Why**（目標） | 低 | AI 分不清技術里程碑和商業目標 |
| **How**（專案狀態） | 低 | AI 無法判斷已完成、進行中、尚未開始 |

**核心發現：What/Who 是事實性維度，Why/How 是意圖性維度。AI 能讀事實但讀不了意圖。全景圖的 What/Who 可信，Why/How 標為 draft 待確認。**

#### Step 2b — 老闆看全景圖，建立信任

全景圖的目的不是完美，是讓老闆產生兩個反應：

1. **「對，大致上是這樣」** → 信任建立。AI 看了我的文件就能拼出公司八成的樣子。
2. **「但你漏了 X / 搞錯了 Y / 其實 Z 是這樣」** → 修正啟動。老闆開始主動補充。

更重要的是**盲點區塊**——AI 從跨產品關係中推斷出老闆可能沒注意到的問題。這是價值展示的核心：

```
盲點推斷邏輯：
  依賴瓶頸：多個產品都依賴某個實體，但該實體沒有明確負責人或時程
  資源衝突：同一人同時是多個活躍目標的唯一負責人
  定位模糊：某個產品在運作但沒有對應的目標
  斷裂連結：行銷需要的資訊在技術文件裡，但沒有翻譯成行銷語言
  隱藏依賴：某個專案是另一個產品的關鍵前置，但沒被顯性管理
```

老闆看完後的自然反應：**叫高管來補資料**。這正是我們要的——從 top-down 驅動組織把知識補完。

#### Step 2c — 迭代收斂（2~3 輪）

```
Round 1 — 全景圖 + 老闆初步反應
  AI 產出全景圖（含盲點）→ 老闆看 → 修正 + 補充
  老闆指派高管補充各產品的 Why / How 細節
  → 產出：v0.5 ontology（結構正確，細節待校準）

Round 2 — AI 追問 + 高管補充
  AI 根據 v0.5 產生追問清單（針對缺漏和矛盾）
  高管補充 → AI 更新 ontology
  → 產出：v0.8 ontology（接近完整）

Round 3 — 校準 + 鎖定
  AI 展示完整 ontology → 老闆最終確認
  確認邊界規則（什麼該進、什麼不該進）
  → 產出：v1.0 ontology（可進入日常治理）

收斂判斷：當一輪新發現 ≤ 1 個實體時，建議鎖定
```

#### Step 2d — 產出 Context Protocol

Ontology 鎖定後，AI 為每個產品自動產出 Context Protocol：

```
Context Protocol = 全公司共享的產品真相
  結構：What / Why / How / Who 四個區塊
  語言：非技術人員能讀懂
  來源：ontology + 既有文件，AI 翻譯成共通語言
  缺漏：明確標記，附帶 AI 建議的追問問題

  行銷夥伴拿到 Protocol 就能開工，不用再去問開發
  新人拿到 Protocol 就能理解產品，不用讀技術文件
```

#### Step 3 展開：Ontology 觸發規則（何時新建、何時更新、何時歸檔）

Ontology 不是建完就放著的產物，它需要持續治理。但「持續」不等於「隨時」——需要明確的觸發規則，否則要嘛治理過度（每個 typo 都觸發），要嘛治理不足（重大變更被忽略）。

##### 新建 Ontology Entry 的觸發

```
觸發事件                          Ontology 動作                         誰負責
──────                          ──────────                           ────────
新建文件                          → 神經層：自動建 ontology entry（draft）   AI 自動
                                → 嘗試關聯到骨架層已知實體                  AI 自動
                                → 關聯不上 = 標記 unlinked（本身是訊號）     AI 自動

對話產生新概念                     → 骨架層：新增實體 entry（draft）          AI 建議
（新產品、新目標、新角色）           → 更新關係圖                              AI 建議 + 人確認

文件大幅修改後 AI 偵測到新實體      → 骨架層：建議新增                         AI 建議 + 人確認
（spec 裡突然出現五個新概念名詞）
```

##### 更新既有 Ontology Entry 的觸發

```
觸發事件                          Ontology 動作                         誰負責
──────                          ──────────                           ────────
文件被大幅修改                     → 神經層：重新檢查 4D 標籤是否還準確       AI 自動
                                → 骨架層：檢查有沒有新實體出現              AI 建議

骨架層實體變更                     → 級聯更新：所有關聯的 ontology entry       AI 自動
（產品改名、目標調整）              → 級聯更新：相關 Context Protocol          AI 自動（draft）

兩份文件出現矛盾內容                → 神經層：兩個 entry 都標記 conflict       AI 自動
                                → 推給相關人確認哪份是正確的                AI 通知

文件小幅修改（typo、格式）          → 不觸發                                  —
```

##### 歸檔 / 休眠的觸發

```
觸發事件                          Ontology 動作                         誰負責
──────                          ──────────                           ────────
文件被刪除                        → 神經層：entry 標記 archived             AI 自動

定期掃描：實體 N 個月              → 骨架層：建議「這個產品是不是停了？」       AI 建議
沒有新文件關聯                                                              + 人確認

定期掃描：文件 N 個月沒修改         → 神經層：entry 標記 possibly-stale        AI 自動
但關聯實體有高活動度                → 推給相關人確認是否過時                    AI 通知
```

##### 過時推斷邏輯（Step 4 的核心）

純粹看「文件有沒有更新」不夠。最危險的過時是「文件沒動但世界變了」。ZenOS 用跨實體活動度推斷：

```
推斷情境                                         推斷邏輯
────────                                       ────────
「產品功能」更新了 5 次，但「定價」0 次            → 定價可能需要 review
某產品的 ontology entry 標記「Phase 1」           → 但其他文件暗示已進 Phase 2
  已超過預期時間                                  → 狀態可能需要更新
某目標下的所有專案都已 completed                   → 但目標本身還標記 active
                                                → 目標可能需要關閉或更新
兩個產品開始出現在同一份文件的 entry 中            → 可能正在整合，骨架層關係需要更新
```

這些推斷不是確定性判斷，是「建議 review」。全部走 confirmedByUser。

##### 設計期 vs 營運期的觸發差異（從 ZenOS dogfooding 提煉）

```
                    設計期（Phase 0）              營運期（Phase 1+）
                    ──────────────              ──────────────
主要觸發源          對話（概念迭代）               文件 CRUD 事件
骨架層更新頻率      高（每次重大討論）              低（一季一次）
神經層更新頻率      低（文件少）                    高（每天）
治理方式           手動更新 ontology.md            AI 自動 + confirmedByUser
觸發機制           session 結束前人工觸發          CRUD webhook + 定期掃描
```

**設計期的觸發規則（現在 ZenOS 適用）：** 每次討論產生了新概念、修正了架構、或改變了方向時，session 結束前更新 ontology。這是手動版的「對話觸發」。

**營運期的觸發規則（未來客戶適用）：** 文件 CRUD 事件驅動 + 定期掃描。骨架層變更需要 confirmedByUser，神經層標籤可以 AI 自動打但可以人覆寫。

#### Ontology 邊界規則

不是所有東西都該進 ontology。實體進入的條件：

| 規則 | 說明 | 範例 |
|------|------|------|
| **多部門關注** | 至少兩個部門需要知道它的存在 | Paceriz（開發 + 行銷都需要） |
| **正在產生文件** | 有活躍的文件產出圍繞這個實體 | v2 課表流程（BDD、spec 持續產出中） |
| **目標關鍵路徑** | 在某個商業目標的關鍵路徑上 | naru_agent（Paceriz Agent 導入的前置） |

不該進 ontology 的：純內部工具、已完成且不再參考的歷史專案、個人筆記。

### 實戰驗證：Naruvia 導入前 vs 導入後（2026-03-21）

以 Naruvia（4 個產品線、2 人團隊）為對象，實際走完 Step 2a~2c，以下是導入前後的對比：

#### 導入前：老闆腦中的公司

```
老闆（Barry）知道的：
  ✓ 自己在做 4 個產品
  ✓ 每個產品大致在什麼階段
  ✓ 行銷夥伴需要素材

老闆沒有顯性化的：
  ✗ 4 個產品之間的依賴關係（naru_agent → Paceriz → 官網）
  ✗ 官網是 3 條產品線的交匯瓶頸，但沒人負責
  ✗ 1 人扛 4 條線的資源衝突在哪裡
  ✗ 行銷夥伴拿到的「行銷文件」其實是技術文件
  ✗ 4 個產品都跟 AI 有關，但沒有統一的對外故事線
  ✗ Zentropy 在運作但沒有目標——是繼續還是暫停？

行銷夥伴的狀態：
  - 想做素材，但不知道產品現在能說什麼
  - 有一份 marketing/paceriz.md，打開全是 Webhook 和 OAuth
  - 不確定什麼功能已上線、什麼還在開發
  - 要等 Barry 有空才能問到答案
```

#### 導入後：Ontology 讓公司知識顯性化

```
全景圖展示的（AI 自動產生）：
  ✓ 4 產品 + 2 基礎設施 + 相互依賴圖
  ✓ 3 個活躍目標 + 各自的關聯產品
  ✓ 6 個盲點（含官網瓶頸、資源衝突、定位模糊）
  ✓ 2 個機會（naru_agent 品牌化、Paceriz 作為 dogfooding 案例）
  ✓ 6 項老闆需要決策的事項（優先級、商業模式、時程...）

Context Protocol 提供的（以 Paceriz 為例）：
  ✓ 行銷夥伴可讀的產品描述（零技術術語）
  ✓ 明確標記已上線 vs 開發中的功能
  ✓ 目標用戶畫像 + 地區策略
  ✓ 跟其他產品的關係（行銷需要知道的部分）
  ✓ 可用的數據能力（用戶分群 → 精準行銷）
  ✓ 缺漏清單（AI 建議的下一步追問）

具體效益量化：
  ① 行銷夥伴不用等 Barry 有空：Protocol 就是隨時可查的答案
  ② 盲點可視化：官網瓶頸、資源衝突等問題浮出水面
  ③ 決策加速：老闆看到全景圖就知道該先解決什麼
  ④ 新人 onboarding：從數天降到數小時（讀 Protocol 而非散落文件）
  ⑤ 文件品質監控：AI 發現「marketing 資料夾裡放的是技術文件」
```

#### 導入成本

```
老闆投入時間：~30 分鐘對話（確認 + 補充）
高管投入時間：每人 ~15 分鐘（補充各自負責的 Why/How）
AI 處理時間：全自動（掃描 + 產圖 + 產 Protocol）
導入週期：1 天內可完成 v1
持續成本：趨近於零（AI 自動標注 + 治理）
```

### 架構延伸：從資料層到知識層

現有三層架構直接延伸，不是蓋新系統：

```
               資料層（現有）              知識層（新增：語意代理架構）
               ─────────────              ─────────────────────────
存什麼         contacts / orders / ...    骨架層（實體關係圖）+ 神經層（文件 ontology entry）
本質           結構化業務資料              非結構化知識的語意代理
儲存           Firestore                  Phase 1: SQLite → Phase 2: PostgreSQL + Graph
產出           業務報表                    Context Protocol（= ontology 的 view）

               Agent 層（現有）            Knowledge Agent（新增）
               ─────────────              ─────────────
寫入           輸入 Agent → 自然語言寫資料  標注 Agent → 文件 CRUD 觸發 ontology entry 建立/更新
查詢           查詢 Agent → 自然語言問資料  Context Agent → 讀 ontology → 找文件 → 組裝 context
監控           監控 Agent → 資料異常偵測    治理 Agent → 知識品質 + 神經層異常推骨架層更新
確認           簽核 Agent → 業務流程審核    確認 Agent → confirmedByUser 知識版
```

---

## Part 5 — 漸進式信任模型（Progressive Trust）

### 這是 ZenOS 最關鍵的設計

ZenOS 面對的不是技術問題，是**信任問題**。

中小企業老闆的心理模型：

```
「你要看我的文件？不可能。」
「你說資料安全？每個系統都這樣說。」
「你的 AI 真的看得懂我的公司？先證明給我看。」
```

Glean 的做法是一次要求所有工具的 connector 權限——大企業有 IT 部門評估後統一授權，可以接受。但中小企業的老闆就是數據擁有者本人，他對風險的感知是直覺的、個人的。

Palantir 的做法是派顧問團隊進場，花數月建立關係。中小企業付不起這個成本。

**ZenOS 的做法：不要求資料，先用最少的輸入展示最大的價值。信任是賺來的，不是要求來的。**

### 信任三階段

```
                        老闆投入          ZenOS 產出              信任水平
                        ──────          ─────────              ────────
Stage 0 — 對話          30 分鐘對話      公司全景圖 + 盲點洞察    「你懂我的公司」
  AI 問：你有幾個產品？目標是什麼？誰在做什麼？
  老闆回答的全部是「可以寫在官網上」的資訊——不是機密
  產出：全景圖（含跨產品盲點推斷）
  → 老闆心理：「你只問了我 30 分鐘就能拼出這個？值得繼續看看。」

Stage 1 — 選擇性開放    老闆主動給文件    完整 Context Protocol    「有用，給你更多」
  老闆看到全景圖 → 覺得盲點推斷有價值
  → 主動說「我再讓你看一些文件」
  機密的開放是老闆主動的，不是 ZenOS 要求的
  AI 讀文件 → 充實每個產品的 Context Protocol
  → 老闆心理：「行銷夥伴終於能自己找到答案了，不用一直來問我。」

Stage 2 — 完整部署      BYOS 部署        持續治理 + 自動標注     「這是我公司的系統」
  老闆確認 ontology 有用 → ZenOS 提案 BYOS 部署
  所有資料在客戶自己的環境裡（每客戶一個 VM + 一個 Claude 訂閱）
  ZenOS 碰不到客戶資料——徹底解決「機密放在你那邊」的問題
  AI 持續自動標注新文件、監控品質、同步更新
  → 老闆心理：「這是我自己的系統，不是寄人籬下。」
```

### 核心設計原則：Ontology ≠ 原始文件

```
ZenOS 的 Ontology 存的是「標籤 + 結構 + 關係」，不是文件內容本身。

Ontology 裡的資訊：
  ✓ Paceriz 是 AI 跑步教練
  ✓ 目前目標是 v2 課表驗證
  ✓ 依賴 naru_agent
  ✓ 行銷夥伴需要產品 context

Ontology 裡沒有的：
  ✗ Paceriz 的原始碼
  ✗ 商業合約的具體金額
  ✗ 客戶的個資
  ✗ 任何原始文件的全文

→ 即使 Ontology 洩漏，暴露的是公司結構（公開資訊），不是商業機密
→ 洩漏風險等級：從「災難性」降到「可接受」
```

### 三種客戶情境的應對

現實中客戶的資料狀態差異極大。ZenOS 的漸進式信任模型讓每種情境都能啟動：

```
情境 A — 有文件但很亂（最理想）
  代表：Naruvia 的現況
  Stage 0：對話建立全景圖
  Stage 1：老闆開放部分文件 → AI 掃描充實 Protocol
  全景圖品質最高，因為 AI 有文件佐證
  迭代收斂 2~3 輪即可鎖定 v1

情境 B — 老闆只給碎片
  代表：謹慎的老闆，只口頭描述不給文件
  Stage 0：對話建立全景圖（品質稍低但仍可用）
  Stage 1：可能停在對話階段較久，需要更多輪迭代
  關鍵：全景圖的盲點推斷仍然有效——因為盲點來自「結構矛盾」而非文件內容
  例如：「一個人負責四個產品」「某產品沒有目標」不需要看文件也能推斷

情境 C — 完全沒文件
  代表：新創公司、一人公司
  Stage 0：純對話建立全景圖
  AI 的追問清單反而成為公司建立第一批文件的引導
  ZenOS 不只是治理知識，還在幫客戶「第一次把知識寫下來」
  → 這是最低門檻的導入情境，也是對中小企業最有價值的
```

### 為什麼這是 ZenOS 的護城河

```
Glean    → 要求一次授權所有工具 → 中小企業不敢
Palantir → 要求數月顧問進場    → 中小企業付不起
Notion   → 要求員工自己整理     → 中小企業沒有這個文化
ERP      → 要求全公司改流程     → 中小企業不願意

ZenOS    → 只要 30 分鐘對話     → 中小企業做得到
         → 先展示價值再要資料   → 中小企業信得過
         → 不改變任何人的習慣   → 中小企業撐得住
         → 最終部署在客戶自己的環境 → 中小企業放得下心
```

**漸進式信任不只是導入策略，是產品的核心競爭力。** 它決定了 ZenOS 的 go-to-market：不是 SaaS 冷啟動（先付費再用），是 value-first（先看到價值再決定）。全景圖就是 ZenOS 的免費增值入口——零成本、零風險、30 分鐘見效。

### 信任曲線與數據開放的正循環

```
信任建立 → 老闆開放更多資料 → Ontology 更完整 → 盲點推斷更精準 → 信任加深
信任破裂 → 老闆收回資料     → Ontology 退化   → 價值消失         → 客戶流失

前三個月的目標不是功能完整，而是管理這條信任曲線。
每一次互動都要讓老闆覺得：「給你看這些是值得的。」
```

---

## Part 6 — 導入策略

### 導入順序（漸進式信任 + 資料層 + 知識層 三線並行）

```
Phase 0 — 驗證（現在）
→ 用 Naruvia 自身走完 Step 2 全流程（已完成 Stage 0 + 部分 Stage 1）
→ 驗證：30 分鐘對話能否產出有價值的全景圖 ✅ 已驗證
→ 驗證：盲點推斷是否讓老闆覺得「你懂我」 ✅ 已驗證
→ 驗證：Context Protocol 是否讓行銷夥伴能直接開工 → 待驗證
→ 產出：第一份 Paceriz Context Protocol 作為樣本 ✅ 已完成
→ 產出：ZenOS 自身的 Context Protocol（dogfooding）✅ 已完成
→ 完成：ZenOS 專案文件重組（用 ontology 邏輯治理自己的知識）✅ 已完成
→ 待做：讓行銷夥伴試讀 Protocol，驗證可用性

Dogfooding 驗證（2026-03-21）：
  ZenOS 自身的文件經歷了三個時代（kickoff → 行銷自動化 → Knowledge Ontology），
  散落的過時文件和現行文件混在一起，新 session 無法快速接手。
  用 ZenOS 自己的方法論重新組織後：
    - CLAUDE.md = AI 入口（新 session 30 秒接手）
    - Context Protocol = 人的入口（行銷夥伴 5 分鐘理解）
    - spec.md = SSOT（完整真相）
    - archive/ = 過時文件隔離
  → 這個過程本身就是 ZenOS 產品化後要幫客戶做的事
  → 差別在：目前是手動，產品化後要自動

Phase 1 — 信任建立（第 1 個月）
→ 知識層：全景圖 + 盲點推斷（Stage 0，只需對話）
→ 知識層：Context Protocol 初版（Stage 1，選擇性開放文件）
→ 資料層：公版 Schema + 輸入 Agent + 查詢 Agent
→ 目標：老闆覺得「這東西懂我的公司」→ 決定繼續

Phase 2 — 主動價值（第 2~4 個月）
→ 知識層：治理 Agent 定期掃描 Protocol 完整性 / 一致性 / 新鮮度
→ 知識層：跨部門查詢（任何人自然語言問 → AI 從標籤體系組裝 context）
→ 資料層：監控 Agent + 公版通知規則
→ 部署：BYOS 上線（Stage 2，資料完全在客戶環境）
→ 目標：老闆感受到「不只是看到全景圖，系統真的在幫我盯」

Phase 3 — 自動化（第 5 個月後）
→ 知識層：自動 Protocol 生成（新功能完成 → AI 草擬 Protocol）
→ 知識層：依賴追蹤（Protocol 更新 → 自動通知相關部門文件需同步）
→ 資料層：排程 Agent + 簽核 Agent + 展示層儀表板
→ 目標：系統成為公司的知識中樞 + 業務神經系統
```

### 知識重組五步流程（從 Dogfooding 提煉）

2026-03-21 用 ZenOS 自己的文件做了一次完整的知識重組。以下是從中提煉的可重複流程：

```
Step A — 盤點：現在有什麼
  掃所有文件 → 列出清單
  不看內容，只看：檔名、位置、最後修改時間
  產出：文件清單 + 粗略時間線

Step B — 分代：哪些是活的、哪些是死的
  根據時間線和內容，把文件分成「代」：
    ZenOS 的例子：第一代（kickoff）、第二代（行銷自動化）、第三代（Knowledge Ontology）
  判斷每份文件屬於哪一代 → 標記：現行 / 過時 / 參考
  產出：文件 × 狀態 的對照表

Step C — 歸檔：讓過時的不再干擾
  過時文件移到 archive/
  不刪除（歷史決策有參考價值）但隔離（新人不會被混淆）
  產出：乾淨的目錄結構

Step D — 建索引：每份文件貼四維標籤
  對每份現行文件標注 What / Why / How / Who（目標讀者）
  發現問題：
    - 文件放錯位置（marketing/ 裡放技術文件）
    - 文件缺目標讀者（寫了但不知道給誰看）
    - 同一主題散落多處（沒有 SSOT）
  產出：文件索引表（見 ontology.md）

Step E — 建入口：按角色建不同的讀取路徑
  不是所有人都需要讀所有文件。按 Who 建入口：
    AI / 新 session → CLAUDE.md（30 秒接手）
    行銷夥伴 → Context Protocol（5 分鐘理解）
    技術夥伴 → spec.md（完整真相）
    老闆 / 客戶 → 全景圖（能力展示）
  產出：入口文件 + 讀取順序指引
```

**這五步就是 ZenOS 產品化後要自動做的事。**

目前的實現方式：AI（Claude）手動執行，約 20 分鐘。
產品化目標：客戶把文件授權給 ZenOS 後，AI 自動執行 Step A~D，Step E 需要業主確認讀者角色。

### 說服客戶的定位

> 「我們不是要再裝一套 Odoo。我們是讓你們現有的資料開始會說話，員工不需要改習慣，從你們已經在用的地方開始。」

---

## Part 7 — 服務架構：Ontology 治理的落地實作

### 核心問題：文件 CRUD 怎麼被偵測、ontology 怎麼主動更新？

Ontology 的價值在「持續治理」，不在「建一次」。但持續治理需要兩個前提：
1. **知道文件變了**（事件源）
2. **知道要怎麼更新 ontology**（治理引擎）

不同公司的文件環境差異極大。ZenOS 的架構必須支持多種事件源，但從最簡單的開始。

### 架構總覽：三層治理系統

```
┌─────────────────────────────────────────────────────────────┐
│ 事件源層（Detection Layer）                                    │
│ 「文件 CRUD 怎麼被偵測到？」                                   │
│                                                              │
│ ┌──────────┐  ┌──────────────┐  ┌──────────────┐            │
│ │ Git Hook  │  │ File Watcher │  │ Cloud API    │            │
│ │ post-commit│  │ fswatch /    │  │ Google Drive │            │
│ │ pre-push  │  │ inotify      │  │ MS Graph     │            │
│ └─────┬─────┘  └──────┬───────┘  └──────┬───────┘            │
│       └───────────────┼─────────────────┘                    │
│                       ▼                                       │
│              統一事件格式（Unified Change Event）               │
│              { file, action, diff, author, timestamp }        │
└──────────────────────┬────────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 治理引擎層（Governance Engine）                                │
│ 「偵測到之後誰來分析、怎麼更新 ontology？」                     │
│                                                              │
│ ┌──────────────┐  ┌──────────────┐  ┌────────────────┐      │
│ │ 變更分類器    │  │ 影響分析器    │  │ 過時偵測器      │      │
│ │ 重大/小修/    │  │ 哪些 entry   │  │ 定期掃描       │      │
│ │ 新檔/刪除/   │  │ 受影響？     │  │ 跨實體活動度   │      │
│ │ 重命名       │  │              │  │ 異常           │      │
│ └──────┬───────┘  └──────┬───────┘  └───────┬────────┘      │
│        └─────────────────┼──────────────────┘                │
│                          ▼                                    │
│                 草稿產生器（Draft Generator）                   │
│                 提出 ontology 更新建議                          │
│                 神經層：自動生效                                │
│                 骨架層：draft → confirmedByUser                 │
└──────────────────────┬────────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 確認與同步層（Confirmation & Sync）                            │
│ 「人怎麼介入？下游怎麼更新？」                                  │
│                                                              │
│ ┌──────────────┐  ┌──────────────┐  ┌────────────────┐      │
│ │ 待確認佇列    │  │ 級聯更新器    │  │ Protocol 重生器 │      │
│ │ 骨架層變更    │  │ 骨架→神經    │  │ ontology →     │      │
│ │ 需人確認      │  │ 自動聯動     │  │ Protocol 自動   │      │
│ │              │  │              │  │ 重新產出        │      │
│ └──────────────┘  └──────────────┘  └────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 事件源：不同環境的 CRUD 偵測方式

```
環境                    事件源                   CRUD 偵測機制              延遲
──────                 ──────                  ──────────               ────
Markdown + Git         git post-commit hook    git diff --name-status   即時（commit 觸發）
Markdown 無 Git        fswatch / inotify       檔案系統事件              即時（儲存觸發）
Google Workspace       Drive API webhook       Changes API (push)       ~秒級
Microsoft 365          MS Graph webhook        Change Notifications     ~秒級
Notion                 Notion API webhook      Search/Query delta       ~分鐘級
混合環境               多源歸一                 統一 Change Event 格式    依來源而異
```

**核心洞察：Markdown + Git 是最乾淨的事件源。**

Git commit 自帶完整的 CRUD 語意：
- **C**reate：`git diff --name-status` 顯示 `A`（Added）
- **R**ead：不觸發（讀不改 ontology）
- **U**pdate：`git diff --name-status` 顯示 `M`（Modified）+ `git diff` 顯示具體改了什麼
- **D**elete：`git diff --name-status` 顯示 `D`（Deleted）

而且 git 天然提供：author（誰改的）、timestamp（什麼時候改的）、message（為什麼改）、diff（改了什麼）。不需要額外 metadata。

### 分階段實作：從零基礎設施到完整自動化

#### Phase 0.5 — 手動觸發、零基礎設施（立刻可用）

**適用情境：** Barry 現在的狀態。一個人、幾個 git repo、用 Claude Code 開發。

**做法：** 不建任何基礎設施，利用已有的工具鏈。

```
觸發方式：Claude Code session 開始時手動觸發
             ↓
分析引擎：Claude 讀 git log --since="上次 ontology sync 時間"
             ↓
          Claude 讀變更的文件 + 現有 ontology
             ↓
          Claude 提出 ontology 更新建議
             ↓
確認方式：Barry 在對話中確認 → Claude 直接更新 .md 文件
             ↓
同步方式：git commit ontology 變更
```

**具體流程（每次 session 開始或結束前）：**

```bash
# 1. 看上次 ontology 更新之後改了什麼
git log --since="2026-03-21" --name-status --oneline

# 2. Claude 分析變更清單，對照現有 ontology
#    → 哪些 entry 需要更新？
#    → 有新文件需要建 entry 嗎？
#    → 有文件被刪需要歸檔嗎？

# 3. Barry 確認後，Claude 更新 ontology .md 文件
# 4. git commit 更新後的 ontology
```

**優點：** 零成本、零基礎設施、今天就能開始。
**缺點：** 依賴人記得觸發、沒有自動提醒。

**Phase 0.5 的進化：在 CLAUDE.md 加入 ontology sync 提醒**

```markdown
# Session 結束前的 checklist
- [ ] 這次 session 有改到文件嗎？如果有，跑一次 ontology sync
- [ ] 骨架層有變嗎？（新產品、新目標、角色變動）
- [ ] 神經層有變嗎？（新文件、文件大改、文件刪除）
```

這就是 Phase 0 的「設計期觸發規則」的落地實作——不是系統自動觸發，是靠流程規範 + AI 提醒。

#### Phase 1 — Git Hook 自動偵測 + 待辦佇列

**適用情境：** 第一個客戶、或 Barry 覺得手動觸發不夠用時。

**新增基礎設施：** 一個 git post-commit hook + 一個 changelog 文件。

```bash
# .git/hooks/post-commit（每次 commit 自動觸發）
#!/bin/bash

# 取得這次 commit 改了什麼
CHANGES=$(git diff --name-status HEAD~1 HEAD -- '*.md' '*.pdf' '*.docx')

if [ -n "$CHANGES" ]; then
  # 寫入 ontology 待處理佇列
  echo "---" >> docs/ontology-pending.md
  echo "commit: $(git rev-parse --short HEAD)" >> docs/ontology-pending.md
  echo "date: $(date -Iseconds)" >> docs/ontology-pending.md
  echo "author: $(git log -1 --format='%an')" >> docs/ontology-pending.md
  echo "changes:" >> docs/ontology-pending.md
  echo "$CHANGES" | while read line; do
    echo "  - $line" >> docs/ontology-pending.md
  done
fi
```

**效果：** 每次 commit 之後，`ontology-pending.md` 自動累積變更清單。下次 Claude session 一打開，先讀 `ontology-pending.md`，一次處理所有待更新。

```
流程：
  開發者正常工作 → git commit → hook 自動記錄變更
        ↓
  下次 Claude session 開始
        ↓
  Claude 讀 ontology-pending.md
  「上次之後有 3 個 commit 改了 5 個文件，建議以下 ontology 更新…」
        ↓
  Barry 確認 → Claude 更新 ontology → 清空 pending
```

**加入定期掃描（過時偵測）：**

```bash
# crontab（每週一早上跑一次）
0 9 * * 1 cd /path/to/repo && ./scripts/ontology-staleness-check.sh
```

```bash
# ontology-staleness-check.sh
#!/bin/bash

# 找出超過 30 天沒修改但有關聯 ontology entry 的文件
echo "# Staleness Report $(date -I)" > docs/ontology-staleness-report.md
echo "" >> docs/ontology-staleness-report.md

find docs/ -name "*.md" -mtime +30 | while read file; do
  echo "- ⚠️ $file (last modified: $(stat -c %y "$file" | cut -d' ' -f1))" \
    >> docs/ontology-staleness-report.md
done
```

**優點：** CRUD 偵測自動化、不遺漏變更、有定期過時掃描。
**缺點：** AI 分析還是在 session 內手動觸發。

#### Phase 2 — 全自動治理（BYOS 部署）

**適用情境：** 付費客戶、BYOS 部署環境。

**架構：** 客戶的 VM 上跑一個常駐的 Governance Daemon。

```
┌─ 客戶的 VM ──────────────────────────────────────────────┐
│                                                          │
│  ┌──────────────┐     ┌──────────────┐                  │
│  │ File Watcher │     │ Git Hook     │                  │
│  │ (fswatch)    │     │ (post-commit)│                  │
│  └──────┬───────┘     └──────┬───────┘                  │
│         └───────────┬────────┘                           │
│                     ▼                                     │
│  ┌──────────────────────────────────┐                    │
│  │ Event Queue（本地 SQLite）        │                    │
│  │ { file, action, diff, ts }      │                    │
│  └──────────────┬───────────────────┘                    │
│                 ▼                                         │
│  ┌──────────────────────────────────┐                    │
│  │ Governance Daemon（Python/Node）  │                    │
│  │                                  │                    │
│  │ 1. 從 queue 讀事件               │                    │
│  │ 2. 分類：重大修改 / 小修 / 新增  │                    │
│  │ 3. 呼叫 Claude API 分析影響      │                    │
│  │ 4. 產出 ontology 更新草稿        │                    │
│  │ 5. 神經層 → 自動寫入             │                    │
│  │    骨架層 → 推入待確認佇列        │                    │
│  └──────────────┬───────────────────┘                    │
│                 ▼                                         │
│  ┌──────────────────────────────────┐                    │
│  │ 確認介面（Web UI / CLI / Slack） │                    │
│  │                                  │                    │
│  │ 「ACWR.md 更新了 → 建議更新      │                    │
│  │   acwr.md ontology entry 的      │                    │
│  │   '待決策' 為 '已修復'」          │                    │
│  │                                  │                    │
│  │  [確認] [修改] [忽略]             │                    │
│  └──────────────────────────────────┘                    │
│                                                          │
│  客戶的 Claude 訂閱（API key）← 全部在本地，不過 ZenOS    │
└──────────────────────────────────────────────────────────┘
```

**Phase 2 支持的事件源擴展：**

```
Markdown + Git     → git hook（Phase 1 已有）
非 Git 的本地文件  → fswatch / inotify → 偵測 .md/.docx/.pdf 的 create/modify/delete
Google Drive       → Drive Changes API（push notification 到本地 webhook endpoint）
Microsoft 365      → MS Graph Change Notifications（同上）
Notion             → Notion API polling（每 5 分鐘查詢 last_edited_time 變更）
Slack / Email      → 不主動監控，但可以手動「capture」一段對話進 ontology
```

**每個事件源都歸一到統一格式：**

```json
{
  "source": "git",
  "action": "modified",
  "file": "cloud/api_service/FIRESTORE_STRUCTURE.md",
  "diff_summary": "新增 `training_sessions` collection 定義",
  "author": "barry",
  "timestamp": "2026-03-21T14:30:00+08:00",
  "commit": "a1b2c3d"
}
```

**Governance Daemon 的決策邏輯：**

```
收到事件
  │
  ├─ action = "created" 且是非程式碼文件
  │   → 需要新建 ontology entry？
  │   → AI 分析文件內容，打 4D 標籤
  │   → 自動寫入神經層
  │   → 如果涉及新實體 → 建議骨架層更新（待確認）
  │
  ├─ action = "modified"
  │   → 變更量大嗎？（> 20% diff = 重大修改）
  │   │   ├─ 大：重新分析 4D 標籤，對比舊標籤
  │   │   │   → 標籤變了 → 更新神經層 entry
  │   │   │   → 標籤沒變 → 只更新 last_reviewed 時間戳
  │   │   └─ 小（typo/格式）：不觸發
  │   │
  │   → 影響骨架層嗎？（改了產品名、改了目標描述、改了依賴關係）
  │       → 是：推入待確認佇列
  │       → 否：神經層自動更新
  │
  ├─ action = "deleted"
  │   → ontology entry 標記 archived
  │   → 檢查有沒有其他 entry 依賴這個文件
  │       → 有：通知「依賴斷裂，需要 review」
  │
  └─ action = "renamed"
      → 更新 ontology entry 的路徑引用
      → 自動，不需確認
```

### 特別回答你的問題：只有 markdown、沒有 Google Docs，怎麼主動治理？

你的情境其實是最理想的，因為：

```
你的優勢                           為什麼是優勢
──────                            ──────────
全 markdown                       AI 讀寫零成本，不需解析 binary 格式
全在 git                          CRUD 歷史完整，免費的 audit trail
用 Claude Code 開發               治理引擎就是 Claude，不需另建 AI pipeline
CLAUDE.md 慣例已建立               AI 入口已存在，ontology 只是擴展
一個人                            confirmedByUser 就是你自己，沒有跨部門審批問題
```

**你現在就能用的「主動治理」流程：**

```
1. 工作日常態（Phase 0.5）
   ├── 每次 Claude Code session 結束前
   │   Claude 自動問：「這次 session 有影響 ontology 的變更嗎？」
   │   ├── 有 → 提出更新建議 → Barry 確認 → 直接更新 .md
   │   └── 沒有 → 跳過
   │
   ├── 每週一次（手動或 cron）
   │   跑 staleness check：哪些文件超過 30 天沒動但關聯實體活躍？
   │   → 產出 staleness report → Barry 花 5 分鐘 review
   │
   └── 每次大方向調整時
       手動觸發全量 ontology sync
       → Claude 重新掃描所有文件 vs 現有 ontology
       → 提出批量更新建議

2. 加入 Git Hook 之後（Phase 1）
   ├── 每次 git commit 自動記錄變更到 pending 佇列
   ├── 下次 session 開始時 Claude 自動讀 pending
   └── 不再依賴「人記得觸發」

3. 最終形態（Phase 2）
   ├── Governance Daemon 常駐
   ├── 文件改了 → 秒級偵測 → AI 自動更新神經層
   ├── 骨架層變更 → 推通知 → Barry 在手機上確認
   └── Context Protocol 自動重生
```

### 技術選型決策

```
                    Phase 0.5           Phase 1              Phase 2
                    ──────────          ──────────           ──────────
事件偵測            手動（git log）     git hook              git hook + fswatch + Cloud API
事件佇列            不需要              ontology-pending.md   SQLite（本地）
治理引擎            Claude Code session Claude Code session   Governance Daemon + Claude API
Ontology 儲存       .md 文件（git）     .md 文件（git）       SQLite → PostgreSQL（可選）
確認介面            Claude 對話         Claude 對話           Web UI / CLI / Slack bot
過時偵測            手動 review         cron + shell script   Daemon 內建定期掃描
部署               無                  git hook 安裝         BYOS VM
成本               $0                  $0                    Claude API 用量
```

### Ontology 儲存的演化路線

```
Phase 0~1: Markdown 文件（現在）
  ├── 優點：零成本、人可讀、git 版本控制、AI 直接讀寫
  ├── 缺點：無法做結構化查詢、關聯性靠文件內文字引用
  └── 適用：< 50 份 ontology 文件、單人/小團隊

Phase 2: SQLite（單客戶 BYOS）
  ├── 優點：結構化查詢、關聯性靠 foreign key、仍是單文件部署
  ├── 缺點：人不能直接讀、需要工具層
  ├── 遷移：.md 是 view，SQLite 是 source of truth
  └── 適用：50~200 份 entry、中型公司

Phase 3: PostgreSQL + Graph Extension（規模化）
  ├── 優點：圖查詢（找三跳內的關聯）、全文搜索、多 agent 並發
  ├── 缺點：需要 DB 維運
  └── 適用：200+ entry、多產品線、需要跨公司 meta 分析
```

**關鍵設計原則：.md 永遠可以作為 export 格式。** 即使底層遷移到 SQLite/PostgreSQL，用戶看到的 ontology 仍然可以是 .md 文件（由 DB 自動生成）。這保持了人類可讀性和 git 版本控制。

### 多角色協作：非技術成員的事件源策略

現實中一間公司不會所有人都用 git。關鍵區分：**誰是 ontology 的生產者，誰是消費者？**

```
角色                 跟 ontology 的關係          事件源策略
──────              ────────────────          ──────────
開發者 / 技術人員    生產者 + 消費者             Git hook（最乾淨）
老闆 / 決策者        主要是消費者（看全景圖）     對話觸發（Stage 0）
                     偶爾是生產者（改方向時）     Governance Daemon 推確認
行銷 / 非技術成員    主要是消費者（讀 Protocol）  Protocol 推送（被動接收）
                     偶爾是生產者（寫素材時）     Cloud Docs API / 共享資料夾監控
外部顧問 / 客戶      純消費者                    不觸發事件，只讀 Protocol
```

**核心洞察：行銷夥伴的文件變更不需要跟開發者走同一套偵測機制。**

行銷夥伴的痛點不是「她的文件沒被偵測到」，而是「她沒有可用的素材」。所以流向是反的：

```
開發者改了程式碼/文件
  → git hook 偵測
  → ontology 更新
  → Context Protocol 自動重生
  → 推送給行銷夥伴（email / Slack / 共享資料夾）
  → 行銷夥伴看到最新的產品 context，直接產素材

行銷夥伴基於 Protocol 寫了素材
  → 素材存在共享資料夾 / Google Docs
  → Cloud API 偵測到
  → ontology 記錄「行銷素材已更新」
  → 閉環
```

**針對不同非技術成員的事件源方案：**

```
情境 A — 行銷夥伴用 Google Docs
  偵測：Google Drive Changes API（push notification）
  觸發：Docs 被編輯 → Governance Daemon 讀取 → 更新神經層 entry
  延遲：秒級
  成本：Google API 免費額度足夠

情境 B — 行銷夥伴用 Word + 共享資料夾
  偵測：Dropbox / Google Drive / OneDrive 同步監控
  觸發：本地 fswatch 監控同步資料夾 → 偵測 .docx 變更
  延遲：秒~分鐘級（取決於同步速度）
  成本：零（fswatch 是免費工具）

情境 C — 行銷夥伴用 Notion
  偵測：Notion API polling（每 5 分鐘查詢 last_edited_time）
  觸發：頁面被編輯 → 讀取內容 → 更新神經層 entry
  延遲：分鐘級
  成本：Notion API 免費

情境 D — 行銷夥伴沒有固定工具（最常見的中小企業現實）
  策略：不監控她的文件，監控 ontology 的消費端
  → Protocol 更新時通知她
  → 她寫完素材後手動「提交」（上傳到指定資料夾 / 發 Slack 訊息）
  → Governance Daemon 被動接收
  延遲：不即時，但夠用
  成本：零
```

**Phase 0.5 的行銷夥伴方案（立刻可用）：**

行銷夥伴不需要任何技術工具。流程：
1. Barry 更新了 ontology → Context Protocol（paceriz.md）自動更新
2. Barry 把更新後的 Protocol 用 email / LINE / Slack 傳給行銷夥伴
3. 行銷夥伴讀 Protocol → 寫素材 → 回傳給 Barry review
4. Barry 把素材放進 repo → git 偵測 → ontology 記錄

這不優雅，但零成本、今天就能開始。等 Phase 2 有 Governance Daemon 和 Web UI 之後，行銷夥伴才會有自己的「確認介面」。

### 跨生態系整合策略：ZenOS 的 Adapter 架構

ZenOS 的核心定位是「語意層」，不是「儲存層」。文件留在用戶自己的工具裡，ZenOS 透過 Adapter 讀取事件和內容。

#### 四種 SMB 環境的整合方式

```
環境                Adapter 策略              事件偵測                   內容讀取                免費可行性
──────             ──────────              ──────────                ──────────             ──────────
Google Drive       Google Drive API         Changes API push webhook   files.get + export     ✅ 免費額度夠用
Microsoft 365      MS Graph API             Change subscriptions       driveItem /content     ✅ 標準 Graph 配額
Wiki（Notion）     Notion API               Webhooks（page/db 事件）    Page query 取內容      ✅ 免費
Wiki（Confluence） Atlassian REST API       Webhooks（page CRUD 事件）  REST 取頁面內容        ✅ 免費雲版
Git（技術團隊）    Git hooks                 post-commit hook           git diff / git show    ✅ 完全免費
什麼都沒有         → 見下方專門討論
```

#### 「什麼都沒有」的產品策略（最關鍵的決策）

**核心問題：沒有儲存層，語意層就沒有東西可以代理。ZenOS 該怎麼辦？**

三個選項的分析：

```
選項 A — ZenOS 自建文件管理 + UI
  ✓ 完整體驗控制
  ✗ 你在重新發明 Notion / Google Drive
  ✗ 開發成本巨大（6~12 個月）
  ✗ 偏離 North Star：ZenOS 是 ontology，不是文件管理
  ✗ 跟免費的 Google Drive / Notion 競爭 = 死路

選項 B — ZenOS 推薦用戶先用現有免費工具，自己只做語意層
  ✓ 不偏離定位
  ✓ 零儲存層開發成本
  ✗ 「什麼都沒有」的用戶可能連 Google Drive 都不想學
  ✗ 導入多一步 = 流失率高

選項 C — ZenOS Dashboard：最小 UI，只做 Ontology 消費介面（✅ 選這個）
  ✓ 不競爭文件管理
  ✓ 用戶有一個「看到知識全貌」的地方
  ✓ 文件在哪不影響 — Google Drive / 本地 / 什麼都沒有
  ✓ 完美對齊漸進式信任模型
  → 儲存層可以後來再接（或不接）
```

**選項 C 的核心思路：ZenOS Dashboard 是「公司知識的體檢報告」，不是「公司文件的管理工具」。**

```
類比：
  醫院 ≠ 你家               → ZenOS ≠ 文件儲存
  你在家裡吃飯睡覺           → 文件在 Google Drive / 本地 / Git
  你去醫院看體檢報告          → 你在 ZenOS Dashboard 看全景圖 + Protocol
  醫生告訴你哪裡有問題        → ZenOS 告訴你哪些知識過時/矛盾/缺漏
  你決定要不要治療            → confirmedByUser
  你不會因為醫院好就搬去住    → 用戶不會因為 ZenOS 好就把文件搬過來
```

#### ZenOS Dashboard 做六件事

```
┌─────────────────────────────────────────────────────────────┐
│  ZenOS Dashboard（唯一自建的 UI）                             │
│                                                              │
│  1. 展示全景圖                                               │
│     骨架層視覺化 + 盲點推斷 + 跨實體依賴圖                     │
│     → 老闆來這裡「看全貌」                                    │
│                                                              │
│  2. 收集確認                                                  │
│     ontology 變更 + 任務完成的 confirm 佇列                    │
│     → 老闆來這裡「做決定」                                    │
│     （兩種確認合併：知識確認 confirmedByUser +                  │
│      任務驗收 confirmedByCreator）                             │
│                                                              │
│  3. 提供 Protocol                                            │
│     給行銷/非技術成員的可讀 view                               │
│     → 行銷夥伴來這裡「找 context」                            │
│                                                              │
│  4. 資料存放點地圖（Storage Map）                              │
│     公司知識散落在哪些地方的視覺化總覽                          │
│     → 老闆來這裡「看知識散落在哪」                             │
│                                                              │
│     Git repo (paceriz)        ████████████  38 entries       │
│     Google Drive              ██████        15 entries       │
│     Firestore（對話產出）      ████          10 entries       │
│     未連結                     ██             5 entries       │
│                                                              │
│  5. 任務看板（Action Layer）                                  │
│     Kanban 五欄 + Inbox/Outbox 雙視角                         │
│     → 所有人來這裡「看任務、追進度、確認完成」                  │
│     （詳見 Part 7.1 — Action Layer）                          │
│                                                              │
│  6. 團隊設定（角色→員工對應）                                  │
│     設定職能角色由哪些員工擔任                                  │
│     → 老闆/主管來這裡「設定 Who 的公司層綁定」                  │
│     + Agent 身份宣告指引（教員工設定 agent 的職能角色）          │
│     （詳見 enterprise-governance.md「Who 的三層消費模型」）      │
│                                                              │
│  它 不做：                                                    │
│  ✗ 文件編輯                                                   │
│  ✗ 文件儲存                                                   │
│  ✗ 文件上傳（只有 Stage 1 的 Drop Zone，讀完就丟）             │
│  ✗ 搜尋（那是 Glean 的事）                                    │
│  ✗ 協作（那是 Notion / Google Docs 的事）                     │
│  ✗ Agent 管理（員工→agent 的綁定在員工自己的環境）              │
└─────────────────────────────────────────────────────────────┘
```

#### Dashboard 頁面架構

```
/login                          ← Google OAuth
/                               ← 專案列表
/projects/:id                   ← 全景圖（EntityTree + Blindspots + 依賴圖）
/projects/:id/tasks             ← 任務看板（Kanban + Inbox/Outbox）
/projects/:id/confirm           ← 確認佇列（知識確認 + 任務驗收）
/projects/:id/protocol          ← Protocol Viewer
/projects/:id/map               ← Storage Map
/projects/:id/team              ← 角色→員工設定
/setup                          ← MCP 設定引導 + Agent 身份宣告指引
```

#### 「什麼都沒有」的漸進式導入路徑

```
Stage 0 — 只有對話（什麼儲存工具都不需要）
  老闆跟 ZenOS 聊 30 分鐘
  → 全景圖出現在 ZenOS Dashboard 上
  → 老闆第一次看到自己公司的知識結構
  → 不需要任何文件、任何工具
  → 這就夠了。信任從這裡開始。

Stage 1 — 老闆願意給文件（但文件散落各處）
  ZenOS Dashboard 提供 Drop Zone：
  「把你覺得重要的文件拖進來，我看一看就好，不會留下。」
  → ZenOS 讀取 → 建 ontology → 文件不儲存在 ZenOS
  → 或者老闆授權 Google Drive / 本地資料夾
  → Ontology 充實 → Protocol 產出

Stage 2 — 需要持續治理（這時才需要儲存層）
  ZenOS 問：「你們想把文件集中管理嗎？」
  → 老闆決定用 Google Drive（免費、最低摩擦）
  → ZenOS 自動設定 Adapter
  → 從此 CRUD 事件自動偵測
  → 或者老闆決定不用 → ZenOS 定期掃描（手動 + cron）也行
```

**「什麼都沒有」不是障礙，因為 Stage 0 本來就不需要儲存層。** 這正是漸進式信任的威力——ZenOS 從零開始也能展示價值。

#### Adapter 架構設計

```
                    ZenOS Ontology Engine
                           │
                    ┌──────┴──────┐
                    │ Adapter Hub │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │ Google    │   │ Microsoft │   │ Notion    │
    │ Adapter   │   │ Adapter   │   │ Adapter   │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │                │                │
    統一介面：
    ┌────────────────────────────────────────┐
    │ interface StorageAdapter {              │
    │   watchChanges() → Stream<ChangeEvent> │
    │   readContent(fileId) → string         │
    │   getMetadata(fileId) → FileMetadata   │
    │   listFiles(folder) → File[]           │
    │ }                                      │
    └────────────────────────────────────────┘

    每個 Adapter 實作同一個介面。
    Ontology Engine 不關心文件在哪——它只跟 Adapter 介面互動。
    新增一個生態系 = 新增一個 Adapter，Engine 零改動。
```

**Adapter 的開發優先順序（基於 SMB 市場調查）：**

```
優先順序    Adapter              理由
──────    ──────────          ──────
1         Git                  已有（Phase 0.5）+ 技術客群起步
2         Conversation         MCP + Skill，知識捕獲在產生點，不需檔案系統
3         Google Drive         80%+ SMB 使用 Google Workspace
4         本地檔案 (fswatch)   搭配 BYOS，零雲端依賴
5         Notion               知識工作者常用
6         Microsoft Graph      企業客群（Phase 2+）
7         Confluence           大企業/轉型客群
```

### Conversation Adapter：AI 對話作為事件源（2026-03-21 dogfooding 發現）

**來源：ZenOS 創辦人自身的 dogfooding。** 在 Claude Cowork session 中產出了 Paceriz 的 Threads 發文策略（20 篇排程 + 4 篇草稿 + 語感備忘 + v2 鋪路時間線），但這份知識不在任何檔案系統裡——只存在對話中。手動匯出、上傳、分類是不會發生的事。

**核心洞察：知識的捕獲點必須在產生知識的地方。** 現有的所有 Adapter（Git / Google / MS / Notion）都假設知識的載體是「檔案」，事件源是「檔案 CRUD」。但 AI 時代有一種新的知識載體——**對話**。AI 對話產出的策略、決策、分析，品質經常比正式文件更高，但它們不會自動變成檔案。

#### 跟其他 Adapter 的差別

```
                    傳統 Adapter              Conversation Adapter
──────              ──────────              ──────────────────
觸發方式            自動（file CRUD 事件）     人主動觸發（呼叫 skill）
事件源              檔案系統                   AI 對話 session
內容來源            檔案內容                   對話 context
觸發頻率            高頻（每次存檔）           低頻（人覺得值得時才觸發）
四維標籤            AI 從檔案內容推斷          AI 從對話 context 推斷（更準確，因為有完整討論脈絡）
```

**意外的優勢：對話 context 比檔案更適合推斷 Why 和 How。** 檔案只有結果，但對話有完整的推導過程。AI 從對話推斷 Why/How 的準確度應該顯著高於從檔案推斷。（待驗證）

#### 技術流程

```
用戶在任何 AI session 中產出有價值的內容
    ↓
呼叫 skill（例如 /zenos-update）
    ↓
Skill 做三件事：
  1. 讀取當前 session 的對話 context
  2. AI 推斷四維標籤 + 關聯的骨架層實體
  3. 呼叫 ZenOS MCP Server：
     - propose_update()  → 更新既有 entry
     - propose_new()     → 建立新 entry
     - 或兩者都有（例如：新建「發文策略」entry + 更新「Paceriz」骨架層實體的關聯）
    ↓
ZenOS Governance Service 收到 proposal → 建 draft entry
    ↓
用戶在 Dashboard 確認佇列 or 直接在 skill 中確認 → confirmedByUser → 生效
    ↓
所有 Who 角色的 AI agent 在下次讀 context 時拿到更新
```

#### 介面設計：擴展 StorageAdapter 還是新介面？

Conversation Adapter 跟 StorageAdapter 的介面不完全一樣——它沒有 `watchChanges()`（不是自動偵測）、沒有 `listFiles()`（沒有檔案系統）。

```
建議：新介面 ConversationAdapter，不強行塞進 StorageAdapter

interface ConversationAdapter {
  extractContext(sessionId) → ConversationContext    // 讀取對話 context
  proposeEntries(context) → OntologyProposal[]      // AI 推斷 ontology entries
  confirm(proposalId) → void                        // 用戶確認
}

ConversationAdapter 的 output 跟 StorageAdapter 一樣：
  都是 OntologyProposal → 進入 Governance Service → confirmedByUser → 生效

差別只在 input：一個是檔案事件，一個是對話 context。
```

#### Skill 的實作要素

```
1. ZenOS MCP Server 先跑起來（Phase 1）
2. Cowork skill 檔案：
   - 讀取 session context（Cowork API 或 transcript）
   - 呼叫 ZenOS MCP 的 propose_update / propose_new
   - 顯示 proposal 讓用戶確認
3. 認證：skill 帶 token，對應用戶的 role mapping
4. 跨平台：同一套 MCP，Claude Code / Cowork / 任何 MCP client 都能用
```

#### PM 交付清單

這個概念交付給 PM 寫 PRD 時，需要回答的問題：

```
必答：
  - Skill 的觸發 UX：用戶怎麼呼叫？呼叫時需要提供什麼？
  - Proposal 的確認 UX：在 skill 裡直接確認，還是導去 Dashboard？
  - Session context 的讀取範圍：整段對話，還是用戶標記的片段？
  - 骨架層 vs 神經層的 propose 規則：對話可以直接 propose 新的骨架層實體嗎？
  - 錯誤處理：MCP 連不上 / 推斷結果用戶不滿意怎麼辦？

可延後：
  - 自動觸發建議：AI 偵測到「這段對話產出了有價值的東西」主動問要不要存
  - 批次處理：一次 propose 多個 entry
  - 衝突處理：propose 的 entry 跟既有 entry 矛盾
```

#### 雙動作設計：Ontology 更新 + 原始內容存放

Conversation Adapter 的 skill 觸發時，做兩件事而不是一件：

```
/zenos-update 觸發：

動作 1 — 更新 ontology（via MCP propose_update / propose_new）
  → 結構化的知識索引：What/Why/How/Who + 關聯
  → 這是 ZenOS 核心職責

動作 2 — 存放原始內容（follow 用戶習慣）
  → 用戶習慣存 git → agent 幫你 commit markdown
  → 用戶習慣存 Google Drive → agent 幫你建文件
  → 什麼都沒有 → 存進 Firestore（ZenOS 託管）
  → ontology entry 的「原始位置」欄位指向這份內容
```

**為什麼需要動作 2：** Ontology 是語意代理，不是原始內容。Agent 未來接手工作時（例如寫第 5 篇草稿），需要讀到前 4 篇的完整文字——這不在 ontology 裡，在原始文件裡。

**關鍵原則：用戶習慣存到哪就存到哪，skill 順帶把 ontology 更新處理掉。** ZenOS 不規定內容該存在哪。

#### Adapter 事件去重（Dedup）

當 Conversation Adapter 和 Storage Adapter 同時觸發時，需要去重：

```
情境：用戶在 Cowork 討論完 → 呼叫 /zenos-update → agent 同時把內容存進 Google Drive

兩個事件同時發生：
  A. Conversation Adapter → propose entry（有完整 Why/How，來自對話 context）
  B. Google Drive Adapter → 偵測到新檔案 → 也想 propose entry（只有 What/Who）

去重規則：
  - Conversation Adapter 產出的 entry 標記 source: "conversation"
  - Storage Adapter 偵測到同一份檔案時（標題/內容 hash 比對）：
    → 如果已存在 source: "conversation" 的 entry → 不重複建立
    → 而是把檔案位置補進既有 entry 的「原始位置」欄位
  - 如果用戶沒呼叫 /zenos-update，直接存檔：
    → 只有 Storage Adapter 觸發 → 正常建 entry（Why/How 品質較低）
```

**為什麼 Conversation Adapter 的 entry 品質更高：** 檔案只有結果，對話有完整的推導過程、否決的替代方案、決策脈絡。AI 從對話推斷 Why/How 比從檔案推斷準確得多。

#### Dogfooding 案例：Paceriz 發文策略

這是第一個被發現的 Conversation Adapter 使用案例：

```
對話內容：Paceriz Threads 發文策略 v2 鋪路版
產生位置：Claude Cowork session（不在任何檔案系統中）

應該產生的 ontology 更新：

骨架層：
  新實體 → 「Paceriz Go-to-Market」（之前不存在）
  新關係 → Paceriz Go-to-Market ↔ Rizo AI（Phase 3 揭幕依賴 v2 功能）
  新關係 → Paceriz Go-to-Market ↔ ACWR（#7 和 #19 交叉引用安全閘門）

神經層：
  新 entry → Threads 發文策略
    What: 20 篇發文排程 + 4 篇草稿 + 語感備忘 + 成效追蹤指標
    Why:  用知識內容建立跑步圈信任 → 自然導入 v2 AI 教練定位
    How:  三階段鋪路（養信任→埋種子→揭幕），5-6 週，每週 3-4 hr
    Who:  marketing, product
    關聯: Paceriz、Rizo AI、ACWR、training-plan
```

### 開放問題（新增）

- [ ] Git hook 的跨平台安裝方式（Windows 客戶怎麼辦）
- [ ] Governance Daemon 的最小技術棧選擇（Python? Node? Go?）
- [ ] 變更分類器的「重大修改」閾值如何設定（20% diff? 語意判斷?）
- [ ] 多 repo 客戶的事件歸一機制（Paceriz 和 ZenOS 在不同 repo）
- [ ] Cloud API webhook 的 BYOS 部署方式（客戶 VM 需要暴露 endpoint 嗎？用 polling 替代？）
- [ ] 確認介面的最小可行形式（Slack bot 最低成本？CLI 最簡單？）
- [ ] 非技術成員的最低摩擦 Protocol 推送方式（email / Slack / 共享資料夾 / Web UI）
- [x] 「什麼都沒有」的產品策略 → Dashboard（ontology 消費介面）+ Drop Zone + 漸進式引導至免費工具
- [ ] ZenOS Dashboard 的技術棧選擇（SSR? SPA? PWA?）
- [x] Dashboard 的最小可行功能定義 → 四件事：全景圖 + 確認佇列 + Protocol viewer + Storage Map
- [ ] Drop Zone 的隱私設計（文件讀完即丟的技術保證）
- [ ] Adapter Hub 的 plugin 機制（第三方能不能寫 adapter？）
- [ ] Conversation Adapter 的 session context 讀取方式（全段對話 vs 用戶標記片段）
- [ ] Conversation Adapter 是否支援自動觸發建議（AI 主動問「要不要存？」）

### Adapter 整合成本估算（2026-03-21 研究）

```
Adapter              開發天數        最大風險                            SDK 節省
                    （資深工程師）
──────              ──────────     ──────────────────────            ────────
Notion               10-16 天      Webhook 不保證送達                   ~40%
Google Drive         12-20 天      Changes API 只保留 ~4000 筆歷史      ~30%
Confluence           11-18 天      Webhook 連續失敗 5 次自動停用         ~35%
Microsoft Graph      14-22 天      Subscription 過期需主動續期           ~30%

四個全做（考慮共用模式）：35-50 天，約 2-3 個月 for 1 資深工程師
```

每個 Adapter 的必要工程工作：
1. OAuth/Auth 流程（各平台不同）
2. 變更偵測（webhook + polling 兜底 — 所有平台的 webhook 都不可靠）
3. 內容讀取 + 格式轉換（各平台的 rich text → 純文字/markdown）
4. 權限處理（不能讀用戶沒權限的文件）
5. Rate limiting + 指數退避 + 重試
6. 生產環境審核（Google 3-5 天、Microsoft 需 tenant admin 同意）

**結論：整合成本明確可控。不是探索性研究，是已知的工程工作。** 建議先做第一個 Adapter（含所有共用模式），後續 Adapter 可節省 40-50% 工時。

### 「什麼都沒有」的完整產品架構

**核心洞察：「什麼都沒有」的公司，問題不是「文件沒地方放」，而是「知識在老闆腦袋裡出不來」。**

ZenOS 的價值不是幫他管文件（那是 Google Drive 的事），而是幫他把隱性知識結構化。

#### ZenOS 需要自建什麼 vs 不建什麼

```
必建（ZenOS 核心）：
  ✅ Dashboard UI — 全景圖 + 確認佇列 + Protocol viewer + Storage Map + Drop Zone
  ✅ Ontology 儲存 — 骨架層 + 神經層（ZenOS 自己的核心資料）
  ✅ 引導式對話引擎 — Stage 0 的結構化訪談（核心體驗）
  ✅ Auth — Google OAuth / GitHub OAuth（不自建帳號系統）
  ✅ 金流 — Stripe（標準方案，月費制）
  ✅ Adapter Hub — 統一介面 + 多生態系 Adapter

不建（借用現有工具）：
  ❌ 文件儲存 — 留在用戶的 Google Drive / Notion / 自己的系統
  ❌ 文件編輯 — Google Docs / Notion / Word
  ❌ 搜尋引擎 — 那是 Glean 的事
  ❌ 協作工具 — 那是 Notion / Google Docs 的事
  ❌ 帳號系統 — Google OAuth / GitHub OAuth
  ❌ 訊息推送 — email + 現有 Slack/LINE（不自建通訊）
```

#### 三條路線的分析與選擇

```
路線 A — Pure SaaS（全自建）
  ZenOS 自建一切：Dashboard + 文件儲存 + 帳戶 + 金流
  開發量：3-6 個月
  風險：重新發明 Notion/Google Drive
  結論：❌ 偏離定位

路線 B — 寄生現有平台（做成 Notion 整合 / Google Add-on）
  不自建 UI，依附平台
  開發量：1-2 個月
  風險：被平台綁架、功能受限
  結論：❌ 受限太大

路線 C — 最小 Dashboard + 引導選擇儲存層（✅ 選這個）
  自建極簡 Dashboard + 借用 OAuth + Stripe
  開發量：1.5-3 個月
  風險：Dashboard 夠不夠好
  結論：✅ 專注語意層，不重發明文件管理
```

#### 「什麼都沒有」的用戶旅程

```
老闆看到 ZenOS（可能從介紹、口碑、廣告）
  │
  ├── 登入（Google OAuth — 台灣幾乎人人有 Google 帳號）
  │
  ├── Stage 0：引導式對話（核心體驗，不需任何文件）
  │   ZenOS 問：「你公司做什麼？有幾個產品？目標是什麼？」
  │   30 分鐘後 → 全景圖出現在 Dashboard 上
  │
  │   此時 ZenOS 儲存的內容：
  │   ✅ 骨架層 ontology（從對話建立）
  │   ✅ 全景圖 + 盲點推斷
  │   ❌ 沒有任何用戶的原始文件
  │
  │   → 老闆已經看到價值了。Zero file, zero risk.
  │   → 這就是 freemium 的轉化入口
  │
  ├── Stage 1：老闆想深入（觸發付費轉化）
  │   ZenOS：「想讓我看看相關的文件嗎？」
  │
  │   → 有 Google Drive → 授權 → Adapter 讀取 → 建 ontology
  │   → 有散落文件 → Drop Zone 上傳 → 讀完建 ontology → 文件不留
  │   → 什麼都沒有 → 繼續對話補充 → 產出 Context Protocol
  │
  │   → 老闆拿到第一份 Context Protocol，可以分享給團隊
  │   → 這是付費牆的自然位置
  │
  └── Stage 2：持續治理
      ZenOS：「要不要接上你們的文件系統？」

      → 有 Google Drive → 接 Adapter，自動監控
      → 什麼都沒有 → ZenOS 建議「Google Drive 免費，我幫你設定好」
      → 資料敏感 → BYOS 方案（每客戶一個 VM）
```

### 架構模式比較與最終決策（2026-03-21 收斂）

「全公司同一套 context」只有三種根本架構模式：

```
模式 A — 分散 agents + 共享 context（✅ 選這個）
  每個人用自己的 AI（Claude / ChatGPT / Gemini / Cursor）
  所有 agents 透過 MCP 讀同一套 ontology
  ZenOS = context 層（Firestore + MCP + 治理服務）

模式 B — 全公司一個 super agent
  開一台 server 跑一個 AI，所有人跟同一個 AI 互動
  Context 天然統一（只有一個 agent）
  ZenOS = 就是這個 AI 本身

模式 C — 中央 orchestrator + 衛星 agents
  一個中央 agent 持有 context，各部門 agent 需要時問中央
  ZenOS = 中央 orchestrator
```

**選 A 的理由：**

```
1. 用戶用自己偏好的 AI — 不跟 Claude/ChatGPT/Copilot 正面競爭
2. ZenOS 不付 AI 費用 — 用戶自己的訂閱，ZenOS 只收 context 服務費
3. MCP 是跨平台標準 — Claude、ChatGPT、Gemini、Cursor 都支持
4. 專注做 context 層 — 護城河在方法論和 ontology，不在 AI 能力
5. 最符合 BYOS 原則 — 資料在客戶環境，AI 在客戶的訂閱
```

**不選 B 的理由：**

```
1. 產品定位衝突 — 變成 AI 聊天產品，跟巨頭競爭
2. AI 費用由 ZenOS 承擔 — 成本結構不健康
3. 用戶被鎖在 ZenOS 的 AI 裡 — 無法用偏好的工具
4. 需要做完整 Chat UI + Session 管理 + 併發 — 開發量大增
```

**不選 C 的理由：**

```
1. A2A 不成熟 — Anthropic/OpenAI 還沒採納
2. 架構最複雜 — 既要中央 agent 又要衛星 agent
3. 沒有比 A 明顯的好處 — MCP 已經能解決 context 共享
```

### 最終技術棧（Phase 1）

```
┌─────────────────────────────────────────────────────────────┐
│ 用戶的 AI agents（Claude / ChatGPT / Gemini / Cursor）       │
│ 每個人用自己偏好的 AI 工具                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ MCP（唯讀：讀 context）
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ZenOS MCP Server                                             │
│                                                              │
│ read_context(company, role?)    → 回傳該角色的 context        │
│ get_panorama(company)           → 回傳全景圖                  │
│ list_blindspots(company)        → 回傳盲點推斷                │
│ propose_update(entity, changes) → 提議更新（進入治理流程）     │
│                                                              │
│ ⚠️ 不提供直接寫入 ontology 的 tool                            │
│ → agents 只能「提議」，不能「直接改」                          │
│ → 防止 AI 幻覺污染 ontology                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ 讀 / 提議寫入
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Firestore（Ontology SSOT）                                    │
│                                                              │
│ 骨架層：公司實體關係圖                                        │
│ 神經層：文件級 ontology entries + 4D 標籤                     │
│ 待確認佇列：agents 的 propose_update 進這裡                   │
│ 版本歷史：每次確認的 snapshot                                 │
└──────────────────────┬──────────────────────────────────────┘
                       ↑ 唯一寫入入口
┌─────────────────────────────────────────────────────────────┐
│ ZenOS 治理服務                                                │
│                                                              │
│ Step 2 方法論：全景圖 → 迭代收斂 → confirmedByUser            │
│ 事件源接收：git hook / Google Drive API / 對話觸發             │
│ 治理引擎：變更分類 → 影響分析 → 草稿產生                      │
│ 確認流程：骨架層需人確認 / 神經層自動 + 可覆寫                 │
│                                                              │
│ → 這是 ontology 品質的唯一守門員                              │
│ → AI agents 提議更新，治理服務決定是否採納                     │
└─────────────────────────────────────────────────────────────┘
```

**為什麼 MCP 只提供「提議」而不提供「直接寫入」：**

```
已知風險 #1：AI 標籤幻覺
  → 如果 agent 可以直接寫 ontology，幻覺會直接污染全公司 context
  → 一個 agent 的幻覺 × 全公司共享 = 災難性擴散

ZenOS 的治理流程就是為了解決這個問題：
  Agent 提議 → 治理服務驗證 → confirmedByUser → 才寫入
  這跟 git 的 PR review 是同一個邏輯
```

**跨 agent context 共享的方法論比較（完整研究記錄）：**

```
方法              跨平台？   多 agent？  即時？   非技術用戶？  成熟度      ZenOS 適用？
──────           ────────  ────────  ──────  ─────────  ──────    ──────────
MCP              ✅ 50+    ✅        即時    ❌ 需設定   Production  ✅ 主要接口
Claude Projects  ❌ Claude  ❌        即時    ✅ 最簡單   Production  ❌ 不能程式更新
RAG（向量 DB）   ✅        ✅        即時    ❌ 需建置   Production  ⚠️ Phase 2+ 補充
Google A2A       ⚠️ Google  ✅        即時    ❌         Beta       ❌ 不成熟
API 中間件       ✅        ✅        即時    ❌         風險高     ❌ 安全問題
Mem0 / Zep       ⚠️ 部分    ✅        即時    ⚠️ 部分    Production  ❌ vendor lock-in
檔案（CLAUDE.md）⚠️ 部分    ✅        批次    ❌ 需 git   Production  ✅ Phase 0.5
OpenAI GPTs      ❌ OpenAI  ❌        批次    ✅         即將淘汰   ❌

結論：MCP 是唯一同時滿足「跨平台 + 多 agent + 即時 + Production」的方案。
     RAG 可作為 Phase 2 的語意搜尋補充層，當 ontology 規模超出 context window 時啟用。
     但 SMB 的 ontology 規模不會塞爆 context window（Paceriz 完整 ontology = 7 檔 < 500 行）。
     會有那種規模的公司是 Palantir 的客群，不是 ZenOS 的。
```

### 員工資料：ZenOS 不做 HR，只做 role mapping

ZenOS 不管理員工資料（那是 Google Workspace / Microsoft Teams / ERP 的事）。ZenOS 只需要知道一件事：**這個人是什麼角色 → 決定他的 agent 拿到什麼 context。**

```
ZenOS 需要的（Firestore /companies/{id}/members/）：
  { uid, email, role, confirmedBy, createdAt }
  → role 是唯一重要的欄位

ZenOS 不需要的：
  員工編號、薪資、出勤、績效、組織架構圖
  → 那是 HR 系統 / ERP 的事

Who 維度存的是角色，不是個人：
  ontology 說「這跟行銷有關」，不說「這跟小美有關」
  小美離職、小明接手 → ontology 不用改，只改 role mapping
  角色是穩定的，人是流動的
```

Phase 0 概念驗證階段不需要實作此功能。Phase 1 只需 Google OAuth + 簡單 role 欄位。

---

## Part 7.1 — Action Layer（任務管理）

### 為什麼需要 Action Layer

Ontology 承載的是 context（知識），但知識本身不會產生行動。dogfooding 發現的核心缺口：ontology 缺少 output 路徑——從知識到任務派發的閉環不存在。

```
Ontology（知識）──→ 任務（行動）──→ 完成（反饋）
     ↑                                    │
     └────────────────────────────────────┘
     ontology 更新（完成的任務可能產出新知識）
```

Action Layer 不只是「任務管理功能」，它是驗證 ontology 治理品質的唯一手段：
- 任務引用 entity → 驗證 ontology 粒度是否夠用
- 任務帶 blindspot → 驗證盲點推斷是否可行動
- 任務完成反寫 → 驗證雙向治理是否成立

### 架構定位

```
ZenOS 分層架構：

Context Layer（ontology 底座）
  └─ 四維標籤、骨架層、神經層、治理引擎
       │
Application Layers（各 app 共用 ontology context，但有自己的 data model）
  ├─ Action Layer（任務管理）  ← 本章
  ├─ CRM Layer（未來）
  └─ 其他 app layers（未來）
```

每個 Application Layer 的共同特徵：
- 共用 ontology context（透過 linkedEntities / linkedProtocol 連結）
- 有自己的維度（任務加狀態/期限/優先度，CRM 加管線/金額）
- 透過同一套 MCP 介面操作

**Ontology 是底座不是容器——四維標籤是公約數，各 app 加自己的維度。**

### 任務的維度 = Ontology Context + 行動屬性

```
來自 Ontology（自動帶入）           任務自己的（行動屬性）
─────────────────────────           ─────────────────────
What: 跟什麼產品/模組有關            優先度
Why:  為什麼要做這件事               狀態
How:  在什麼專案脈絡下               指派對象（assignee）
Who:  跟哪些角色有關                 期限（dueDate）
                                    依賴關係（blockedBy / subtasks）
                                    驗收條件（acceptanceCriteria）
```

**AI 從 ontology context 推薦行動屬性，人做最終決定。** 例如：連結到 blindspot 的任務 → 建議高優先度。連結到 `status: paused` 的 entity → 建議低優先度。

### 任務模型

```yaml
task:
  id: "task-001"
  title: "寫 Paceriz Q2 社群貼文系列"
  description: "根據 Protocol 的 Why 和目標受眾，產出 4 篇社群貼文"

  # ── 來自 Ontology 的 Context（自動帶入）──
  linkedEntities: ["paceriz", "marketing-campaign-q2"]
  linkedProtocol: "paceriz-protocol"
  linkedBlindspot: "blindspot-003"        # 選填

  # ── 行動屬性 ──

  # 優先度
  priority: "high"              # critical / high / medium / low
  priorityReason: "Q2 行銷啟動在即，且此為盲點 #003 的解法"  # AI 建議理由

  # 狀態（Kanban 六欄）
  status: "in_progress"
  #   backlog      規劃中，還沒排進當前工作
  #   todo         已排定，等待開始
  #   in_progress  進行中
  #   review       等待驗證（做完了，等派任者確認）
  #   done         已完成確認
  #   archived     封存（不再顯示，但保留紀錄）

  # 指派
  createdBy: "barry"            # 人或 agent ID
  assignee: "xiaomei"           # 人（公司層）

  # 時間
  createdAt: "2026-03-22"
  dueDate: "2026-03-29"         # 選填
  completedAt: null

  # 依賴
  blockedBy: ["task-000"]       # 選填
  subtasks: ["task-002", "task-003"]  # 選填

  # 驗收
  acceptanceCriteria:            # 選填
    - "4 篇貼文草稿"
    - "每篇含 CTA 連結"
    - "經 Barry 確認語氣符合品牌"

  # 完成確認（雙向）
  completedBy: null              # 執行者標記完成
  confirmedByCreator: false      # 派任者確認驗收
  rejectionReason: null          # 打回時的原因
```

### 狀態流

```
backlog ──→ todo ──→ in_progress ──→ review ──→ done ──→ archived
                         │              │         │
                         ↓              ↓         ↓
                      blocked        rejected   (自動 archive
                         │              │        after N days)
                         ↓              ↓
                      (解除後)       in_progress
                      回 todo         (重做)
```

| 狀態 | 意義 | 誰觸發 | Dashboard 顯示 |
|------|------|--------|----------------|
| backlog | 規劃中，未排入當前工作 | 建立者 | 規劃池 |
| todo | 已排定，等待開始 | 建立者排定 / AI 建議 | 待辦欄 |
| in_progress | 正在做 | 執行者開始 | 進行中欄 |
| review | 做完了，等派任者確認 | 執行者標記完成 | 等待驗證欄 |
| done | 派任者確認通過 | 派任者確認 | 已完成欄 |
| archived | 封存 | 自動（N 天後）/ 手動 | 隱藏，可查詢 |
| blocked | 被其他任務阻塞 | 執行者標記 | 進行中欄（紅色標記） |

### 優先度的 AI 推薦邏輯

AI 從 ontology context 推薦優先度，人永遠可以覆蓋：

| 訊號（來自 ontology） | 建議優先度 | 理由 |
|----------------------|-----------|------|
| 連結到 blindspot | high+ | 盲點 = 沒人注意到的問題 |
| 連結到 `status: active` 的 entity | medium+ | 正在運作的東西 |
| 連結到 `status: paused` 的 entity | low | 暫停中的東西 |
| 有 dueDate 且 < 3 天 | critical | 快到期 |
| blockedBy 其他任務 | 降一級 | 現在做不了 |
| 被其他任務 blockedBy | 升一級 | 別人在等你 |
| 連結到多個 entity（高 context 交叉度） | 升一級 | 影響範圍大 |

### 任務的雙視角：Inbox / Outbox

每個使用者（人或 agent）看到兩個視角：

**Outbox — 我派出的任務**
```
┌─────────────────────────────────────────────┐
│  📤 我派出的任務                              │
│                                              │
│  🔄 進行中                                   │
│  ├─ 寫 Paceriz 社群貼文 → 小美 (3天前)        │
│  └─ 更新產品頁 SEO → analytics-agent (1小時前) │
│                                              │
│  ✅ 待確認（對方說做完了）                      │
│  └─ 整理客戶回饋 → 小美 ← 點擊確認或打回       │
│                                              │
│  📦 已完成                                    │
│  └─ ...                                      │
└─────────────────────────────────────────────┘
```

**Inbox — 派給我的任務**
```
┌─────────────────────────────────────────────┐
│  📥 派給我的任務                              │
│                                              │
│  🆕 新任務（待接受）                           │
│  └─ 設計 Q2 行銷策略 ← Barry 派的             │
│                                              │
│  🔄 我在做的                                  │
│  └─ 寫技術文件 ← Barry 派的 (進行中)           │
│                                              │
│  ✅ 我完成的（等對方確認）                      │
│  └─ 更新報價單 → 等 Barry 確認                 │
└─────────────────────────────────────────────┘
```

### 任務的 Kanban View（Dashboard）

```
/projects/:id/tasks

┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ Backlog  │   Todo   │ 進行中   │ 等待驗證  │  已完成   │
│          │          │          │          │          │
│ [低]     │ [高]     │ [高]     │ [中]     │ ✅       │
│ 研究競品  │ 寫社群   │ 更新SEO  │ 整理回饋  │ 報價單   │
│ → 未指派  │ →小美    │ →agent-1 │ →小美     │ →小美    │
│          │ 3/29到期  │          │ 等Barry確認│         │
│          │          │ 🔴blocked│          │          │
│          │          │ by task-0│          │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘

切換視角：[全部] [我派出的] [我的任務]
篩選：[角色▼] [優先度▼] [關聯產品▼] [指派對象▼]
```

### 任務與 Who 三層模型的關係

任務的 assignee 是 Who 三層模型的路由終點：

```
建立任務（指定 assignee）
    │
    ├─ 派給角色（marketing）
    │   → 公司層解析成員工（小美）
    │   → 小美自己決定：親自做 or 轉給 agent
    │
    ├─ 派給特定人（barry）
    │   → Barry 的個人層決定：親自做 or 丟給哪個 agent
    │
    └─ Agent 間互派（完全在個人層內部）
        → ZenOS 不管
```

**ZenOS 管到「派給人」就結束。人怎麼分給 agent 是個人層的事。**

### MCP 介面（與 UI 對稱）

UI 能做的事，MCP 都能做。Agent 用 MCP，人用 UI，操作同一份資料：

| 動作 | UI 操作 | MCP 呼叫 |
|------|---------|----------|
| 建任務 | 表單 / 快速建立 | `create_task(title, assignee, linkedEntities, ...)` |
| 改狀態 | 拖卡片到下一欄 | `update_task(id, status: "in_progress")` |
| 標記完成 | 點「完成」 | `update_task(id, status: "review", result: "...")` |
| 確認驗收 | 確認佇列點「確認」 | `confirm_task(id, accepted: true)` |
| 打回重做 | 點「打回」+ 填原因 | `confirm_task(id, accepted: false, reason: "...")` |
| 查我的任務 | Inbox/Outbox 頁籤 | `list_tasks(assignee: "me")` / `list_tasks(createdBy: "me")` |
| 查全部任務 | Kanban 全覽 | `list_tasks(projectId: "...")` |

### 通知機制

| 事件 | 通知誰 | 方式 |
|------|--------|------|
| 任務被指派 | assignee | Dashboard 通知 + MCP event（agent 可訂閱） |
| 狀態變為 review | createdBy | 確認佇列出現 + 通知 |
| 被打回（rejected） | assignee | Dashboard 通知 + rejectionReason |
| 被阻塞解除 | assignee | 任務自動回到 todo |
| 逾期未完成 | createdBy + assignee | Dashboard 高亮 + 通知 |

Phase 0-1 通知只在 Dashboard 內（notification badge）。Phase 2 可擴展到 Slack / email / LINE。

### Firestore Schema（Action Layer）

```
tasks/{taskId}
  title           string    必填
  description     string    選填
  linkedEntities  string[]  選填    連結到 ontology 的 entity ID
  linkedProtocol  string?   選填    連結到 Protocol ID
  linkedBlindspot string?   選填    連結到 blindspot ID
  priority        string    必填    "critical" | "high" | "medium" | "low"
  priorityReason  string    選填    AI 建議理由
  status          string    必填    "backlog" | "todo" | "in_progress" | "review" | "done" | "archived" | "blocked"
  createdBy       string    必填    建立者 UID
  assignee        string?   選填    被指派者 UID（null = 未指派）
  dueDate         timestamp 選填
  blockedBy       string[]  選填    阻塞此任務的其他 task ID
  subtasks        string[]  選填    子任務 task ID
  acceptanceCriteria string[] 選填  驗收條件列表
  completedBy     string?   選填    執行者標記完成時的 UID
  confirmedByCreator boolean 必填   false = 待確認，true = 驗收通過
  rejectionReason string?   選填    打回時的原因
  result          string?   選填    完成時的產出描述或連結
  createdAt       timestamp 必填
  updatedAt       timestamp 必填
  completedAt     timestamp 選填
```

### 它不做什麼

- ✗ 不做 Sprint 管理（SMB 不跑 Scrum）
- ✗ 不做工時追蹤（那是 HR / PM 工具的事）
- ✗ 不做 Gantt 圖（過度工程化，SMB 不需要）
- ✗ 不管 agent 的內部任務拆分（個人層的事）
- ✗ 不做自動指派（AI 建議，人決定）

### 實作優先級

| 優先級 | 功能 | Phase |
|--------|------|-------|
| P0 | 任務 CRUD（建/改/查） + 狀態流 | Phase 1 |
| P0 | Inbox / Outbox 雙視角 | Phase 1 |
| P0 | 確認佇列（review → done / rejected） | Phase 1 |
| P0 | MCP 介面（agent 可操作任務） | Phase 1 |
| P1 | 優先度 AI 推薦 | Phase 1 |
| P1 | Kanban 視覺化 | Phase 1 |
| P1 | 依賴關係（blockedBy） | Phase 1 |
| P2 | 子任務 | Phase 2 |
| P2 | 外部通知（Slack / email） | Phase 2 |
| P2 | 任務模板（重複性任務） | Phase 2 |

---

## Part 8 — 待決策項目

- [ ] 服務架構：Git hook 的跨平台安裝方式（Windows 客戶怎麼辦）
- [ ] 服務架構：Governance Daemon 的最小技術棧選擇
- [ ] 服務架構：變更分類器的「重大修改」閾值設定
- [ ] 服務架構：多 repo 客戶的事件歸一機制
- [ ] 服務架構：Cloud API webhook 在 BYOS 環境的部署方式
- [ ] 服務架構：確認介面的最小可行形式
- [ ] 整合策略：ZenOS Dashboard 的技術棧選擇
- [x] 整合策略：Dashboard 的最小可行功能定義 → 六件事：全景圖、確認佇列、Protocol、Storage Map、任務看板、團隊設定
- [ ] 整合策略：Drop Zone 的隱私設計（讀完即丟的保證）
- [ ] 整合策略：Adapter Hub 的 plugin 機制（第三方寫 adapter）
- [ ] 整合策略：Adapter 開發優先順序的市場驗證
- [ ] 公版 Schema 各 Collection 的欄位細節（由場景倒推收斂）
- [ ] 排程 Agent 的觸發頻率與成本控制
- [ ] 多租戶架構：不同客戶的資料隔離方式
- [ ] 簽核 Agent 的逾時處理（簽核人沒回應怎麼辦）
- [ ] 與 Zentropy 個人版的架構共用程度
- [ ] Context Protocol 的標準模板定義（先為 Paceriz 建立第一份）
- [x] 四維標籤體系的自動標注準確度驗證 → What/Who 高、Why/How 低，已記錄
- [ ] Ontology entry 的最小可行欄位定義（語意代理需要承載多少 context 才夠用）
- [ ] 神經層 → 骨架層異常推斷的規則設計（閾值、觸發條件）
- [ ] SMB 場景下的檔案存取方式（API 串接 vs 手動上傳 vs 混合）對 ontology 覆蓋率的影響
- [ ] AI 標籤幻覺的量化驗證：What/Who 準確率 >90% 是否成立
- [x] Who 維度作為 ontology entry 權限過濾器的可行性 → Who 三層模型（職能角色→員工→agents），Pull Model，agent 自宣告身份
- [ ] AI 治理（完整性 / 一致性 / 新鮮度檢查）的觸發機制與頻率
- [ ] 迭代收斂的 UX 流程設計（全景圖互動介面、追問介面、確認介面）
- [ ] Ontology 版本管理機制（v1 鎖定後如何演化）
- [ ] 全景圖的盲點推斷邏輯（規則化 vs LLM 推斷 vs 混合）
- [ ] 全景圖的視覺設計標準（不同公司規模的適配）
- [x] Step 2 完整流程設計 → 全景圖優先 + 迭代收斂 + Protocol 產出，已記錄
- [x] 導入效益驗證 → Naruvia 實戰 before/after 對比，已記錄
- [ ] Action Layer：任務逾期的自動升級規則（逾期多久通知誰）
- [ ] Action Layer：任務 archived 的自動化時機（done 後幾天自動封存）
- [ ] Action Layer：任務與 ontology 的反寫機制（任務完成後是否自動觸發 ontology 更新）
- [ ] Action Layer：角色指派（assignee 填 role 而非 person）的解析機制
- [ ] Action Layer：MCP create_task / update_task / confirm_task / list_tasks 的詳細參數規格 ⚠️ 待 Architect 確認
- [ ] Action Layer：通知機制的最小可行實作（Phase 1 只做 Dashboard 內 badge？）

---

*本文件從 2026-03-19 與 Claude 的對話中收斂整理*
*2026-03-20 對齊治理架構總覽圖*
*2026-03-21 加入 North Star：Knowledge Ontology for SMB 願景、四維標籤體系、Context Protocol、AI 治理責任*
*2026-03-21 加入 Part 4：技術路線研究（Palantir / Glean / 學術）、confirmedByUser 混合模式、架構延伸、導入順序更新*
*2026-03-21 加入 Step 2 驗證結論：AI 準確度因維度而異、迭代收斂流程、Ontology 邊界規則*
*2026-03-21 重寫 Step 2 完整流程：全景圖優先（建立信任）→ 迭代收斂 → Context Protocol 產出*
*2026-03-21 加入實戰驗證：Naruvia 導入前 vs 導入後對比、具體效益量化、導入成本估算*
*2026-03-21 加入 Part 5 漸進式信任模型：信任三階段、Ontology ≠ 原始文件、三種客戶情境、護城河分析*
*2026-03-21 重構導入策略：信任 + 資料層 + 知識層三線並行、Step 2a 改為純對話驅動（零機密風險）*
*2026-03-21 加入 Ontology 架構定義：語意代理（Semantic Proxy）+ 雙層治理（骨架層/神經層）+ 演化路線 + 六項已知風險*
*2026-03-21 更新 Part 0 核心定位：從「標籤+查詢」改為「語意代理層 + AI Agent 知識入口 + 自動治理」*
*2026-03-21 更新 Part 1 競品比較：加入 Ontology 形式維度*
*2026-03-21 加入 Step 3 展開：Ontology 觸發規則（新建/更新/歸檔）、過時推斷邏輯、設計期 vs 營運期差異*
*2026-03-21 加入 Part 7 服務架構：三層治理系統（事件源 → 治理引擎 → 確認同步）、分階段實作（Phase 0.5~2）、Markdown+Git 事件源設計、Governance Daemon 架構*
*2026-03-21 加入 Part 7 跨生態系整合策略：四種 SMB 環境（Google/Wiki/MS/Nothing）分析、Adapter 架構、ZenOS Dashboard 定位（只做消費介面不做文件管理）、「什麼都沒有」的產品策略*
*2026-03-21 重寫 Part 0 核心定位：從「讓人看到知識全貌」改為「AI Context Layer — 全公司同一套 context，AI agents 百倍產能」。護城河從技術壁壘改為 context 壁壘 + 方法論壁壘*
*2026-03-21 加入架構模式決策：三種模式比較（A 分散+共享 / B super agent / C orchestrator），選 A。技術棧：Firestore + MCP Server + ZenOS 治理服務。MCP 唯讀 + propose_update，治理服務是唯一寫入入口*
*2026-03-21 加入跨 agent context 共享研究：8 種方法完整比較（MCP/Projects/GPTs/RAG/A2A/API中間件/Mem0/檔案），MCP 是唯一滿足所有條件的方案。RAG 留 Phase 2+，SMB ontology 不會塞爆 context window*
*2026-03-21 加入 Conversation Adapter：AI 對話作為事件源（dogfooding 發現）、雙動作設計（ontology 更新 + 原始內容存放）、Adapter 事件去重邏輯、ConversationAdapter 介面設計、PM 交付清單*
*2026-03-21 Dashboard 從三件事擴展為四件事：新增 Storage Map（資料存放點地圖），特別用於可視化 Firestore 中的對話產出知識*
*2026-03-22 加入 Who 三層消費模型：職能角色（ontology）→ 員工（公司層）→ agents（個人層）。Pull Model——agent 自宣告身份，ZenOS 不維護 agent registry*
*2026-03-22 Dashboard 從四件事擴展為六件事：新增任務看板（Action Layer）和團隊設定（角色→員工對應）。新增完整頁面架構*
*2026-03-22 加入 Part 7.1 Action Layer：完整任務模型（Ontology Context + 行動屬性）、Kanban 六狀態流、優先度 AI 推薦、Inbox/Outbox 雙視角、MCP 與 UI 對稱介面、Firestore Schema、通知機制、實作優先級*
