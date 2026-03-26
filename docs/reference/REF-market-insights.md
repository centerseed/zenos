---
type: REF
id: REF-market-insights
status: Draft
ontology_entity: market-insights
created: 2026-03-26
updated: 2026-03-26
---

# ZenOS 市場洞察

> 最後更新：2026-03-22
> 狀態：持續更新的活文件

---

## 市場定位矩陣

```
                    結構化資料              非結構化知識

大型企業            Palantir / Fabric IQ    Glean（搜尋非 ontology）
                    Atlan / Collibra        Graphlit（開發者工具）

中型企業            （碎片化）               （空白）

SMB                 Oversai（CX 限定）       ← ZenOS
```

**ZenOS 的位置：非結構化知識 x SMB — 全球空白象限。**

---

## 品類驗證

「Context Layer for AI」已被產業驗證為真實品類：
- Foundation Capital 稱 context graphs 為「AI 的兆美元機會」
- Gartner 預測 2028 年 50%+ AI agent 系統會用 context graph
- Microsoft Fabric IQ（2025-11）、Atlan、Graphlit 都明確使用「context layer」語言
- MCP 正在成為跨 agent context 共享的標準協議

---

## 全球競品追蹤

### Tier 1：最相關（同品類不同象限）

| 競品 | 做什麼 | 目標市場 | 跟 ZenOS 差異 | 威脅度 | 發現日期 |
|------|--------|---------|--------------|--------|---------|
| Microsoft Fabric IQ | 結構化資料 ontology + MCP | 大企業（Fabric 用戶） | 只管結構化資料、需 Fabric 基建 | 中低 | 2026-03-22 |
| Glean | 企業 AI 搜尋 + Enterprise Graph | 中大企業（$50K+/年） | 搜尋導向非 ontology、不治理知識 | 低 | 2026-03-22 |
| Workfabric ContextFabric | 企業 agent 的 context backbone | Fortune 500（via Cognizant） | 最接近 ZenOS 願景但只做大企業 | 中 | 2026-03-22 |
| Cybic Drava | Ontology-first 企業 agentic AI | 大型受監管企業 | 語言最像 ZenOS 但不做 SMB | 低 | 2026-03-22 |

### Tier 2：間接相關（不同品類但有交集）

| 競品 | 做什麼 | 跟 ZenOS 差異 | 威脅度 | 發現日期 |
|------|--------|--------------|--------|---------|
| Palantir AIP | 企業級操作型 ontology | 百萬級部署、只管結構化資料 | 極低 | 2026-03-22 |
| Atlan | 資料治理 context layer | 資料目錄工具、需 data infra | 極低 | 2026-03-22 |
| Notion AI | 工作空間 + AI 搜尋 | 文件工具加 AI、無 ontology、單一 app | 中 | 2026-03-22 |
| Zep / Mem0 | Agent 記憶層 | per-agent 記憶非公司級、互補非競爭 | 極低 | 2026-03-22 |
| Galaxy | 自動化 ontology 平台 | 開發者工具、非 SMB | 低 | 2026-03-22 |

### Tier 3：市場教育者（不是競品但影響 TA 認知）

| 名稱 | 做什麼 | 對 ZenOS 的意義 | 發現日期 |
|------|--------|----------------|---------|
| 侯智薰（雷蒙）Notion AI 課程 | 教 SMB 用 Notion 手動整理知識 | 他的受眾 = ZenOS 潛在 TA。他教手動整理，ZenOS 做自動治理。互補非競爭。 | 2026-03-22 |

---

## 台灣市場特性

### 市場現狀
- 台灣 AI 新創生態仍在「RAG + Chat」階段
- 92% 台灣 SMB 不了解或只模糊了解 AI
- 僅 7.4% 已採用或計畫採用 AI
- 「Context layer」概念尚未進入台灣市場討論

### 台灣相關玩家

| 公司 | 產品 | 定位 | 跟 ZenOS 差異 |
|------|------|------|--------------|
| 大數軟體 LargitData | RAGi | 企業 RAG 搜尋引擎 | 搜尋工具非 ontology |
| 網創 Netron | NAVI | 企業 AI 知識管理 | 知識庫+AI 問答非語意層 |
| 台灣 AI Labs | FedGPT | 聯邦式企業 GPT | 大企業限定 |
| 杰倫智能 Profet AI | Domain Twin | 製造業 domain knowledge | 精神最接近但只做製造業 |
| 瑞比智慧 airabbi | AIMATE | SMB AI 培訓顧問 | 教育非產品，但服務同一群 SMB |

### 可用資源
- 數位部 NT$100 億 AI 投資基金
- 中小企業數位轉型補助（最高 NT$500 萬）
- Taiwan Tech Arena (TTA) 加速器
- A+ 企業創新研發計畫（AI 國際合作加碼 20%）

---

## 突破點假設

### 假設 1：Free Panorama 是最強的獲客武器
- 依據：30 分鐘對話 → 全景圖，零門檻體驗。所有競品都要求先接資料源。
- 驗證方式：找 3 間外部 SMB 做免費全景圖，看轉換率。
- 狀態：待驗證

### 假設 2：技術型創辦人是最好的早期 TA
- 依據：理解 CLAUDE.md 類比、已經痛過「AI 不懂公司」、有決策權。
- 驗證方式：前 5 個 Free Panorama 優先找技術型創辦人。
- 狀態：待驗證

### 假設 3：Notion 用戶是最容易轉換的群體
- 依據：已經在手動整理知識（痛過）、接 Notion Adapter 最容易建 ontology。
- 驗證方式：觀察前 5 個客戶中是否有 Notion 重度用戶，比較導入難度。
- 狀態：待驗證

### 假設 4：品類教育必須用痛點故事而非功能介紹
- 依據：台灣市場不存在「AI context layer」概念，92% SMB 不了解 AI。
- 驗證方式：A/B 測試兩種內容——功能導向 vs 痛點故事——看哪個有互動。
- 狀態：待驗證

---

## 更新紀錄

| 日期 | 更新內容 |
|------|---------|
| 2026-03-22 | 初版建立。完成全球 + 台灣競品分析、市場定位矩陣、4 個突破點假設。 |
