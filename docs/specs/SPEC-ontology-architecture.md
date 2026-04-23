---
type: SPEC
id: SPEC-ontology-architecture
status: Approved
ontology_entity: TBD
created: 2026-03-21
updated: 2026-04-23
superseded_sections:
  - "L1 = product 單一 type"（2026-04-23 由 ADR-047 改為 level-based 判定）
---

# ZenOS Knowledge Ontology 架構

> Layering note: 本 spec 只定義 `ZenOS Core` 中的 Knowledge Layer。
> `Task` / `Plan` 屬於 `SPEC-zenos-core` 定義的 Action Layer，不屬於 ontology entity。

> 從 `docs/spec.md` Part 4 搬出。包含 Entity 分層模型、雙層治理架構、四維標籤、演化路線等。


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

#### Entity 分層模型（2026-03-23 確立；2026-04-23 由 ADR-047 更新 L1 定義）

所有知識都是 entity。Entity 分三層，**由 `level` 欄位判定，不由 `type` 判定**：

```
第一層（level=1，共享根）  任何 type，預設 label=product
                           ← 共享邊界（collaboration root）；可整棵子樹分享給別的用戶
                           ← CRM 擴充：company / person / deal 也是合法 L1 label
第二層（level=2，治理概念）module + governance concepts
                           ← L1 底下的長期共識概念；module 是常見 label，不是唯一型態
第三層（level=3，應用）    document, goal, role, project
                           ← 按需生長，不是每間公司都需要全部
```

**判定 SSOT（ADR-047）：**
- L1 = `level == 1 AND parent_id IS NULL`
- type 是 UI label，**不是**業務邏輯的 gate
- 所有 L1 entity 在 API 層一律用 `product_id` 作為欄位名稱，無論 type

**全部都在同一個 `entities/` collection**，透過 `level` 區分層級、`parent_id` 串成樹、`type` 決定 UI 顯示。知識地圖上每個節點都是一個 entity。

**Task 不是 entity。** Task 是 `ZenOS Core Action Layer` 的標準 action primitive，不是知識。它有自己的生命週期、指派人、驗收條件；Task 透過 `linkedEntities` 連到 ontology，是 ontology 的消費者，不是 ontology 的一部分。

**分層路由規則（摘要）：**
- 治理原則/跨角色共識且具 impacts -> L2
- 正式受治理文件 -> L3 document entity
- 可指派可驗收工作 -> task
- 一次性參考材料 -> entity.sources

#### Entity 的邊界定義

**一個東西該不該成為 entity？三個判斷標準：**

1. **它會跨專案/跨時間存活嗎？**
   - 「訓練計畫系統」→ 會，產品換了十個版本它還在 → entity ✓
   - 「修復 ACWR bug #123」→ 不會，做完就結束 → task ✗

2. **它有 What/Why/How/Who 可以描述嗎？**
   - 「ACWR 安全機制」→ What: 訓練負荷比、Why: 防受傷、How: 計算公式、Who: 跑者 → entity ✓
   - 「下週三前完成」→ 沒有四維可描述 → task ✗

3. **它能成為其他知識的錨點嗎？**
   - 「Paceriz API Service」→ 文件、任務、盲點都掛在它下面 → entity ✓
   - 隨手記的會議筆記 → 不能當錨點，最多是某個 entity 的 source → 不是 entity

**最精簡的判斷規則：如果這個東西消失了，AI agent 在回答問題時會不會少了一塊重要的 context？會 → entity。不會 → 不是 entity。**

#### Entity.sources — 非 entity 級文件的連結

不是所有文件都值得成為 entity(type="document")。會議筆記、零散的 todo、草稿——這些只需要掛在相關 entity 底下作為參考連結：

```
entities/{id}
  sources: [
    { uri: "github://owner/repo/path", label: "週課表規格", type: "github" },
    { uri: "gdrive://fileId/報價單", label: "Q1 報價", type: "gdrive" },
  ]
```

sources 不出現在知識地圖上，只在右側詳情面板裡列出。

#### Entity Entries — L2 的結構化知識條目

L2 entity 不只是 summary + 指向外部文件的指標。每個 L2 可承載**時間軸上的結構化知識條目**（entity entries），記錄 code 裡不存在的決策脈絡、已知限制、重要變更等。

```
entity_entries:
  entity_id → entities/{id}（一對一，一條 entry 只屬於一個 entity）
  type: decision | insight | limitation | change | context
  content: "選 VDOT 不選心率區間，因為 Garmin 心率前幾分鐘不穩"（必填，上限 200 字元）
  context: "在評估了三種方案後做出的決定"（可選，上限 200 字元）
  author: "barry"（誰/哪個 agent 產出）
  source_task_id → tasks/{id}（從哪個 task 產出，可選）
  status: active | superseded | archived（預設 active，沒有 confirmed_by_user）
  superseded_by → entity_entries/{id}（被哪條 entry 取代，superseded 時必填）
  created_at: 時間戳
```

**治理約束**：content 上限 200 字元（~100 中文字），一個知識點用 100 字一定能表達完。表達不完代表要拆成多條 entry 或粒度太大。沒有 confirmed_by_user — entry 是低成本記錄，品質治理靠 server 端的 Internal API（重複偵測、矛盾偵測、壓縮、summary 漂移警告）。

**Entry 的定位**：Ontology 從「文件的語意代理」升級為「公司的經驗記憶體」。Entity 不只告訴你「這個概念是什麼」，還告訴你「為什麼這樣設計、踩過什麼坑、做過什麼決定」——這些是 agent 靠讀 code 絕對拿不到的知識。

**與其他結構的分工**：
- **Entry vs Summary**：summary 是搜尋索引（靜態），entry 是時間軸記憶（累積）
- **Entry vs Document**：entry 是內嵌知識（code 裡沒有的），document 是外部文件指標
- **Entry vs Blindspot**：entry 是事實記錄（永久），blindspot 是待處理問題（有生命週期）
- **Entry vs Sources**：entry 有結構化的 type 和 content，sources 只是 URI 連結

**Entry 解決的願景**：
1. 跨 agent 開發 — 所有 agent 讀同一組 entries，context 跨 session 存活
2. 非同步對齊 — 重要決策記在 entity 裡，不需要開會傳達
3. PM↔工程師 — 決策脈絡在 entries 裡，不用反覆確認
4. 跨部門知識 — 會後決定寫成 entry，可搜尋、可發現
5. ERP 理解 — ERP 欄位的業務含義可作為 context entry 記錄

詳細設計見 `SPEC-l2-entity-redefinition`「Entity Entries」章節與 `ADR-010-entity-entries`。

#### 治理規則抽象框架

所有治理規則（L2 知識節點、L3 文件、Task）都遵循同一套六維結構與變更傳播契約。

完整定義見：[`SPEC-governance-framework`](../specs/SPEC-governance-framework.md)

---

#### 雙層治理架構

分層模型和雙層治理是互補的：

```
骨架層（Skeleton Layer）
  涵蓋：第一層（product）+ 第二層（L2 治理概念）+ 第三層的 goal / role / project
  怎麼建：30 分鐘對話 → 全景圖 → 迭代收斂 2~3 輪
  變動頻率：低（一季一次）
  治理方式：人確認（confirmedByUser）

神經層（Neural Layer）
  涵蓋：第三層的 document entity + entity.sources
  怎麼建：文件 CRUD 事件自動觸發（Adapter 掃描 GitHub / Google Drive / Notion）
  變動頻率：高（每天）
  治理方式：AI 自動標注，人可覆寫
```

兩層在同一個 `entities/` collection 裡，只是建構方式和治理方式不同。

**兩層互動：**

神經層的異常反推骨架層更新：

```
觸發情境                                       骨架層建議
──────                                       ────────
連續多份新 document entity 無法關聯到任何 module 「看起來有一個新模組還沒進 ontology，要不要加？」
某 module 三個月沒有任何新 document 關聯         「這個模組是不是已經停了？」
兩個原本無關的 module 突然共享 document          「這兩個模組是不是在整合？」
同一主題出現兩份互相矛盾的 document              「這兩份文件哪份是正確的？」
```

所有骨架層建議都是 draft，需要 confirmedByUser 才生效。

#### AI Agent 的工作流程

公司的 AI agents 讀取 ontology 的方式，跟 Claude 讀取 SKILL.md 的方式一樣：

```
Step 1 — 讀 ontology（骨架層：product + module）
  「這間公司有 4 個產品、每個產品有哪些 L2 概念（模組/治理節點）、它們之間的關係」
  → 建立公司全局理解

Step 2 — 根據任務需求，從 ontology 找相關 entity
  「這個任務需要 Paceriz 的定價策略」
  → 找到相關 L2 entity → 讀 summary（判斷相關性）
  → 讀 entries（拿到決策脈絡、已知限制、重要變更）
  → 讀 impacts（知道改這裡會影響什麼）
  → 讀 blindspots（知道哪裡有雷）

Step 3 — 需要深入時，透過 sources 或 document entity 去讀實際文件
  → 拿到完整細節，執行任務

Step 4 — 工作完成後，產出新的 entry 回饋到 ontology
  → 做了什麼決定、發現了什麼限制、改了什麼
  → 知識沉澱為下一個 agent/人 的 context
```

Entity 不只是公司知識的 SKILL.md，更是**公司的經驗記憶體**——不只告訴 AI「這塊知識是什麼」，還告訴它「為什麼這樣設計、踩過什麼坑、做過什麼決定」。

#### Ontology 架構演化路線

```
Phase 0（現在）— MCP Server + Firestore
  骨架層：entities collection（product + module），手動 /zenos-capture 建構
  神經層：entities collection（document type），手動 /zenos-capture 掃目錄建構
  Context Protocol：手寫的 .md 文件
  → 驗證概念正確性

Phase 1 — Adapter 自動化
  骨架層：對話驅動建構 + Dashboard UI 建構
  神經層：GitHub/Google Drive/Notion Adapter 自動偵測文件 CRUD → 建 document entity
  Context Protocol：從 ontology 自動生成的 derived collection（人微調確認）
  → 驗證自動治理的準確率

Phase 2+ — 全自動治理
  骨架層：Governance Daemon 主動推斷結構變化
  神經層：即時同步 + 跨 entity 關聯推斷
  Context Protocol：動態生成，但作為 derived collection 可在確認後凍結版本
  → 支援盲點推斷、過時偵測等高階分析
```

**關鍵設計原則：Context Protocol 不是 ontology 本身，它是從 ontology 推導出的 derived collection。** 它不是即時 projection，因為除了自動生成之外，還有 `generated_at / updated_at / confirmed_by_user` 這種獨立 lifecycle；一旦被人確認，就可以凍結成當下可供他人消費的版本。現在手寫 paceriz.md 是因為 Phase 0 沒有系統，未來這份文件應該是從 ontology 自動生成、人微調確認的。

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
治理方式           手動更新 REF-ontology-current-state.md            AI 自動 + confirmedByUser
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
產出           業務報表                    Context Protocol（= ontology 的 derived collection）

               Agent 層（現有）            Knowledge Agent（新增）
               ─────────────              ─────────────
寫入           輸入 Agent → 自然語言寫資料  標注 Agent → 文件 CRUD 觸發 ontology entry 建立/更新
查詢           查詢 Agent → 自然語言問資料  Context Agent → 讀 ontology → 找文件 → 組裝 context
監控           監控 Agent → 資料異常偵測    治理 Agent → 知識品質 + 神經層異常推骨架層更新
確認           簽核 Agent → 業務流程審核    確認 Agent → confirmedByUser 知識版
```

---
