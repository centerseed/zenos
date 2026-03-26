---
type: ADR
id: ADR-002-knowledge-ontology-north-star
status: Approved
ontology_entity: knowledge-ontology
created: 2026-03-21
updated: 2026-03-26
---

# ADR-002：Knowledge Ontology for SMB — 思考收斂紀錄

> 日期：2026-03-21
> 狀態：Accepted
> 參與者：Barry + Claude
> 性質：這不是一個單一技術決策，而是 ZenOS 產品願景的核心推導過程。每一步的失敗和轉折都有價值，未來對齊時應完整回顧。

---

## 起點：問題是什麼

Barry 提出了一個看似簡單但根本的問題：

> 「產品開發會有很多開發文件，但其他部門不會想看。規格文件其他部門又可能要看。資料非常難管理，各部門有各部門的資料，又會有些共同要看的資料。」

這個問題的核心是：**跨部門的 context 管理。** 不是工具問題，不是流程問題，是組織知識治理的根本問題。

---

## 第一輪：嘗試資訊架構解法（全部失敗）

### 方案 1：AI 翻譯層

**構想**：資訊只有一份，AI 根據角色 profile 動態翻譯呈現。每個部門看到同一份文件的不同深度。

**Barry 的反駁**：「你怎麼確保部門 A 的文件部門 B 看得懂？」

**為什麼失敗**：AI 能做語言轉換，但無法填補認知框架的差距。工程師寫「retry logic 最多三次」，就算翻成白話，業務也不知道這對客戶意味著什麼。問題不在語言，在心智模型。

### 方案 2：源頭結構化

**構想**：在資訊產生的時候，強制寫作者回答跨部門的問題。不是事後翻譯，是源頭就結構化。

**Barry 的反駁**：「要訂哪些是共同的，哪些是部門專用的就是治理災難，文件職責邊界很難定義。」

**為什麼失敗**：定義「共用 vs 專用」本身就是一個治理行為，需要跨部門協商。治理的成本隨組織複雜度指數增長，最後沒人遵守。

### 方案 3：訊號路由

**構想**：部門文件完全不共享。跨部門流通的不是文件，是「訊號」——精煉過的、目標部門能理解的摘要。

**Barry 的反駁**：「訊號的 context 量太少，其他部門難以理解，慢慢各部門的資料就形成了資訊孤島。」

**為什麼失敗**：訊號太薄，失去了理解所需的上下文。資訊孤島沒有被打破，只是孤島之間多了一條窄橋。

### 反思：三個方案失敗的共同原因

Barry 指出：「我覺得你已經開始偏離問題的核心了。」

回顧三輪，每個方案都在同一個地方碎裂：

| 方案 | 失敗的本質 |
|------|-----------|
| AI 翻譯 | 語意邊界 — 格式轉了，理解沒通 |
| 源頭結構化 | 分類邊界 — 誰定義共用/專用本身就是治理 |
| 訊號路由 | 資訊量邊界 — 太少就是孤島，太多就沒人看 |

**關鍵認知**：這不是三個不同的問題，是同一個問題的三個面向——**知識邊界（Knowledge Boundaries）**。

---

## 第二輪：找到理論框架

### 知識邊界理論（Carlile 2004）

搜尋學術文獻後發現，Paul Carlile 的研究把跨部門知識問題分為三層：

1. **語法邊界（Syntactic）** — 資訊傳不過去。現代工具已解決。
2. **語意邊界（Semantic）** — 傳過去了但解讀不同。我們卡在這裡。
3. **實務邊界（Pragmatic）** — 看懂了但利益不同，無法直接套用。

### 邊界物件（Boundary Object）

學術上的解法叫 Boundary Object — 一種「兩邊都能用自己的方式理解、但又指向同一個東西」的共享物件。

經典例子：一張產品原型圖。工程師看「怎麼實作」、業務看「客戶看到什麼」、PM 看「符不符合需求」。同一個物件，不同的理解，但足夠的共享。

### 為什麼 Boundary Object 只在製造業成功

**因為物理產品是天然的錨點。** 一台車就是一台車，所有部門天然圍繞同一個物理存在。不需要有人定義「什麼是實體」——物理世界幫你定義了。

知識工作沒有這個天然錨點。你必須人為創造。而人為創造就需要定義、維護、治理——又回到治理災難。

---

## 第三輪：尋找正確的實體粒度（全部有缺陷）

| 候選實體 | 優點 | 致命傷 |
|---------|------|--------|
| 產品 | 所有人都認得 | 太大，一個產品幾百份文件 |
| 功能 | 粒度適中 | 太多，治理不過來 |
| 目標 | 跨部門天然共享 | 太抽象，難具象化 |
| 專案 | 有生命週期、跨部門 | 專案結束，知識碎片化 |

**關鍵認知**：不存在單一「正確的」實體類型。製造業成功是因為物理產品同時具備所有維度。知識工作裡，這些維度是分離的。

---

## 轉折點：從「選哪種實體」到「用多維標籤」

Barry 的關鍵洞察：

> 「如果我們不糾結在實體要長成什麼樣子，而是我們有沒有辦法用這些維度幫文件貼上正確的標籤呢？」

這把問題從「創造新的東西來管理」變成了「用標籤讓現有的東西可被找到」。治理成本結構完全改變：

- 不需要跨部門協商什麼是共用文件
- 不需要有人維護邊界物件
- 每份文件還是各部門自己的
- 標籤讓它們隱性地連結在一起

---

## 建立理論基礎：Ranganathan 分面分類（1933）

搜尋學術文獻發現，分面分類理論早在 1933 年就提出：任何知識都可以用幾個基本維度描述（PMEST）。對應到組織場景：

| 維度 | 回答的問題 |
|------|-----------|
| **What**（產品 / 功能） | 這跟什麼東西有關 |
| **Why**（目標） | 為什麼做這件事 |
| **How**（專案 / 活動） | 怎麼做的、什麼階段 |
| **Who**（角色 / 客戶） | 誰寫的、給誰的 |

**維度是固定的（普世的，不隨行業變），值是動態的（AI 填）。**

---

## 市場驗證

### 沒有人在做的事

| 層 | 代表產品 | 做了什麼 | 缺什麼 |
|---|---------|---------|--------|
| 搜尋層 | Glean | 跨工具搜尋 | 不治理、不標業務語意 |
| 結構層 | Notion | 人工建 database | 不自動標籤 |
| 分類層 | ABBYY | AI 標文件類型 | 不標業務維度 |
| **治理層** | **空白** | | **用普世維度 AI 自動標注業務語意** |

### Palantir 驗證了 Ontology 模式有效

Palantir 的 Ontology 就是「為組織建立共享實體模型，讓所有部門圍繞同一套真相運作」。已在大型組織驗證有效。但只處理結構化資料、只服務大企業。

### ERP 就是公司的 Ontology

Barry 的洞察：「其實 ERP 系統就是一間公司的 context，只是極其肥大臃腫難用又很貴。」

這讓整個討論收斂到一個清晰的定位：

```
ERP   = 公司的 ontology，但要求人適應系統
Palantir = 更靈活的 ontology，但只處理結構化資料、只服務大企業
Glean = 不建 ontology，只搜尋現有的東西
ZenOS = 公司的 ontology，但 AI 適應人
```

### 市場空白

```
                    結構化資料              非結構化知識

大型企業            Palantir / SAP          （沒有產品）

中小企業            Oversai（CX 限定）       ← ZenOS
```

---

## 技術路線收斂

### 三種做法比較

- **Palantir**：由上而下，人工定義 ontology → data pipeline 灌資料。精確但昂貴。
- **Glean**：由下而上，ML 自動推斷實體和關係。零成本但不治理。
- **學術方案（OntoEKG）**：LLM 從非結構化文件自動建 ontology。有潛力但需人審核。

### ZenOS 的選擇：confirmedByUser 混合模式

關鍵洞察：ZenOS 資料層已有的 `confirmedByUser` 模式，直接延伸到知識層。

```
Step 1 — 輕量骨架：四個維度固定（What/Why/How/Who），人定義一次
Step 2 — AI 自動填充：LLM 讀文件，自動標注四維標籤
Step 3 — 人確認：AI 標注 = draft，負責人確認後生效
Step 4 — AI 持續治理：完整性、一致性、新鮮度、衍生同步
```

### Context Protocol 作為 SSOT

Barry 的決定：以 PRD 為實體核心，各部門文件圍繞 PRD 展開。

抽象化後成為 **Context Protocol**——跨行業通用的 SSOT 模板。軟體公司叫 PRD，顧問公司叫服務提案，餐廳叫品項卡。名字不同，結構（What/Why/How/Who）相同。

---

## 最終定位

**ZenOS 是中小企業的知識本體層（Knowledge Ontology）——用 AI 讓組織的非結構化知識自動獲得業務語意，讓正確的 context 在正確的時機到達正確的人。**

不是另一個文件管理系統（Notion），不是另一個搜尋引擎（Glean），不是另一個 ERP（SAP/Odoo）。是 Palantir 為大企業結構化資料做的事，用 AI 帶到中小企業的非結構化知識。

---

## 思考過程的關鍵教訓

1. **每一輪「失敗」都在縮小問題空間。** AI 翻譯失敗排除了語言層解法；源頭結構化失敗排除了治理層解法；訊號路由失敗排除了低 context 解法。剩下的路越來越窄，最後收斂到標籤 + Protocol。

2. **Barry 的每次反駁都把問題推深一層。** 從「怎麼管文件」→「怎麼定義邊界」→「怎麼選實體」→「怎麼選粒度」→「維度比實體更根本」→「需要理論基礎」→「市場有沒有人做」→「怎麼實現」。

3. **最終的解法不是發明出來的，是排除出來的。** 每一個「不是這個」都有價值。

4. **confirmedByUser 是 ZenOS 最核心的設計哲學。** 它不只是一個技術機制，它是「AI 適應人」的具體體現。從資料輸入到知識標注，同一套邏輯。

5. **理論基礎（Ranganathan 1933、Carlile 2004、Boundary Object）不是裝飾。** 它們驗證了我們推導出的方向不是拍腦袋，是有學術根據的。同時也指出了為什麼這個問題這麼難——知識邊界本身就是組織理論的核心難題。

---

## 參考資料

- Carlile, P. R. (2004). Transferring, Translating, and Transforming: An Integrative Framework for Managing Knowledge Across Boundaries. *Organization Science*.
- Ranganathan, S. R. (1933). *Colon Classification*. 分面分類理論（PMEST）。
- Star, S. L. & Griesemer, J. R. (1989). Institutional Ecology, 'Translations' and Boundary Objects. *Social Studies of Science*.
- [LLM-Driven Ontology Construction for Enterprise Knowledge Graphs (OntoEKG)](https://arxiv.org/html/2602.01276v1)
- [Palantir Ontology Documentation](https://www.palantir.com/docs/foundry/ontology/overview)
- [Glean Enterprise Graph](https://www.glean.com/product/enterprise-graph)
- [Ontology is the real guardrail for AI agents — VentureBeat](https://venturebeat.com/infrastructure/ontology-is-the-real-guardrail-how-to-stop-ai-agents-from-misunderstanding/)

---

*本文件記錄 2026-03-21 Barry 與 Claude 的完整討論收斂過程。這個推導路徑本身就是 ZenOS 產品願景的 context，未來對齊新成員或重新審視方向時，應從本文件開始。*
