# ZenOS Ontology — 當前狀態

> 版本：v0.7 | 更新：2026-03-21 | 方法：手動建構（未來自動化）

---

## 實體清單

### 產品（What）

| 實體 | 類型 | 狀態 | 說明 |
|------|------|------|------|
| ZenOS | 產品 | Phase 0 概念驗證 | AI 知識本體層，面向中小企業的 Palantir |

### 概念構件（What 的組成）

| 實體 | 歸屬 | 狀態 | 說明 |
|------|------|------|------|
| 語意代理（Semantic Proxy） | ZenOS 核心架構 | ✅ 設計完成 | Ontology entry = 文件的代理人，承載多面向 context |
| 骨架層（Skeleton Layer） | ZenOS Ontology 架構 | ✅ 設計完成 | 公司實體關係圖，從對話建立，低頻變動，人確認 |
| 神經層（Neural Layer） | ZenOS Ontology 架構 | 📋 設計完成未實作 | 文件級 ontology entry，CRUD 自動觸發，高頻變動 |
| Meta-Ontology | ZenOS Ontology 架構 | ✅ 設計完成 | Schema 層：定義「ontology 應該長什麼樣」，全客戶共用 |
| 四維標籤體系 | Meta-Ontology 核心機制 | ✅ 設計完成 | What/Why/How/Who，源自 Ranganathan PMEST |
| Context Protocol | ZenOS 核心產出物 | ✅ 模板驗證中 | Ontology 的 view — 從 ontology 自動生成，人微調確認 |
| 全景圖 | ZenOS 導入入口 | ✅ 原型完成 | 30 分鐘對話 → 公司全貌 + 盲點推斷 |
| 盲點推斷 | ZenOS 差異化能力 | ✅ 原型驗證 | 從跨實體關係圖推斷未顯性化的問題 |
| 漸進式信任 | ZenOS 導入策略 | ✅ 機制設計完成 | 三階段：對話 → 選擇性開放 → BYOS |
| confirmedByUser | ZenOS + 資料層共用 | ✅ 設計完成 | AI 產出 = draft，人確認 = 生效 |
| 迭代收斂 | ZenOS 建構流程 | ✅ 流程驗證 | 2-3 輪對話收斂，不是一次到位 |
| 雙層互動 | ZenOS Ontology 治理 | ✅ 設計完成 | 神經層異常反推骨架層更新（unlinked 文件、休眠實體、突發關聯） |
| Ontology 觸發規則 | ZenOS Ontology 治理 | ✅ 設計完成 | 何時新建/更新/歸檔 entry，設計期 vs 營運期差異 |
| 過時推斷 | ZenOS Ontology 治理 | ✅ 設計完成 | 跨實體活動度推斷文件是否過時（不靠文件本身有沒有動） |
| BYOS 部署 | ZenOS 部署模式 | 📋 設計完成未實作 | 每客戶一個 VM + 一個 Claude 訂閱 |
| 三層治理系統 | ZenOS 服務架構 | ✅ 設計完成 | 事件源層 → 治理引擎層 → 確認與同步層 |
| 事件源層 | 三層治理系統 | ✅ 設計完成 | Git hook / fswatch / Cloud API → 統一事件格式 |
| 治理引擎層 | 三層治理系統 | ✅ 設計完成 | 變更分類器 + 影響分析器 + 過時偵測器 + 草稿產生器 |
| Governance Daemon | 三層治理系統 Phase 2 | 📋 設計完成未實作 | 常駐服務，事件佇列 + AI 分析 + 自動更新 |
| Phase 0.5 手動觸發 | ZenOS 落地方案 | 🔄 可立即使用 | git log + Claude Code session = 零基礎設施治理 |
| Adapter 架構 | ZenOS 整合層 | ✅ 設計完成 | 統一介面（watchChanges/readContent/getMetadata）+ 多生態系 Adapter |
| ZenOS Dashboard | ZenOS 消費介面 | ✅ 定位確立 | 做四件事：展示全景圖、收集確認、提供 Protocol、Storage Map。不做文件管理 |
| Drop Zone | ZenOS Dashboard | 📋 設計完成未實作 | 文件讀完即丟，不儲存，解決「什麼都沒有」的 Stage 1 |
| 模式 A 架構 | ZenOS 核心決策 | ✅ 決策完成 | 分散 agents + 共享 context（vs 模式 B super agent / 模式 C orchestrator） |
| ZenOS MCP Server | 模式 A 核心組件 | 📋 設計完成未實作 | AI agents 的 context 接口，唯讀 + propose_update |
| Firestore Ontology | 模式 A 核心組件 | 📋 設計完成未實作 | Ontology SSOT，ZenOS 治理服務是唯一寫入入口 |
| Who + Owner 分離 | ZenOS 企業治理 | ✅ 設計完成 | Who = 多值 context 分發，Owner = 單值治理問責，解決傳統部門架構映射 |
| Conversation Adapter | ZenOS Adapter 架構 | ✅ 概念設計完成 | AI 對話作為事件源，透過 Skill + MCP propose ontology 更新，知識捕獲在產生點 |

### 目標（Why）

| 實體 | 關聯產品 | 狀態 | 說明 |
|------|---------|------|------|
| 進入顧問市場 | ZenOS | 規劃中 | 用 ZenOS 作為 Naruvia 顧問服務的核心產品 |
| Phase 0 概念驗證 | ZenOS | 🔄 進行中 | 用 Naruvia 自身 dogfooding 驗證核心流程 |

### 專案 / 活動（How）

| 實體 | 服務的目標 | 狀態 | 說明 |
|------|----------|------|------|
| Naruvia dogfooding | Phase 0 驗證 | 🔄 進行中 | 用自己公司走完 Step 2 全流程 |
| Paceriz Protocol 建立 | Phase 0 驗證 | ✅ 完成 | 第一份 Context Protocol |
| Paceriz Ontology Instance 建立 | Phase 0 驗證 | ✅ 完成 | 第一份多檔 Ontology（骨架+神經+盲點），驗證架構可行性 |
| 行銷夥伴試讀 | Phase 0 驗證 | 📋 待做 | 驗證 Protocol 對非技術人員的可用性 |
| ZenOS 文件重組 | Phase 0 驗證 | ✅ 完成 | 用 ontology 邏輯治理自己（dogfooding） |
| spec 持續迭代 | Phase 0 驗證 | 🔄 持續 | 每次討論後更新 spec.md |

### 角色（Who）

| 實體 | 跟 ZenOS 的關係 | 需要什麼 context |
|------|----------------|-----------------|
| Barry | 產品 / 開發 / 決策 | 全部 |
| 行銷夥伴 | 推廣顧問服務 | ZenOS 的定位、價值主張、客戶案例 |
| 新 Claude session | 接手討論 | CLAUDE.md → spec 的讀取順序 |
| 未來顧問客戶 | ZenOS 的使用者 | 全景圖體驗、Protocol 產出 |

---

## 關係圖

```
ZenOS（產品）
  ├── 由什麼組成（What 展開）
  │   ├── Ontology 架構
  │   │   ├── 語意代理（Semantic Proxy）← 核心概念：文件的代理人
  │   │   ├── 骨架層（Skeleton Layer）← 來自「專案導向」方向
  │   │   ├── 神經層（Neural Layer）← 來自「標籤索引」方向
  │   │   ├── 雙層互動 ← 神經層異常反推骨架層更新
  │   │   ├── Ontology 觸發規則 ← 新建/更新/歸檔的事件驅動規則
  │   │   ├── 過時推斷 ← 跨實體活動度推斷，不靠文件本身
  │   │   └── Meta-Ontology ← Schema：定義 ontology 長什麼樣
  │   │       └── 四維標籤 ← 理論基礎：Ranganathan PMEST
  │   │
  │   ├── 產出物
  │   │   ├── Context Protocol ← Ontology 的 view，實例：paceriz.md, zenos.md
  │   │   └── 全景圖 ← 骨架層的視覺展示，含盲點推斷
  │   │
  │   ├── 核心機制
  │   │   ├── 漸進式信任 ← 護城河，寫在 spec Part 5
  │   │   ├── confirmedByUser ← 從資料層延伸到知識層
  │   │   ├── 迭代收斂 ← 2-3 輪對話收斂
  │   │   └── 盲點推斷 ← 跨實體關係推斷未顯性化問題
  │   │
  │   ├── 服務架構（三層治理系統）
  │   │   ├── 事件源層 ← Git hook / fswatch / Cloud API → 統一事件格式
  │   │   ├── 治理引擎層 ← 變更分類 + 影響分析 + 過時偵測 + 草稿產出
  │   │   ├── 確認與同步層 ← 待確認佇列 + 級聯更新 + Protocol 重生
  │   │   └── Adapter Hub ← 統一介面，多生態系 Adapter（Git/Google/MS/Notion）
  │   │
  │   ├── ZenOS Dashboard（唯一自建 UI）
  │   │   ├── 全景圖展示 ← 骨架層視覺化 + 盲點
  │   │   ├── 確認佇列 ← confirmedByUser 介面
  │   │   ├── Protocol Viewer ← 給非技術成員的可讀 view
  │   │   └── Drop Zone ← 文件讀完即丟，不儲存（Stage 1 用）
  │   │
  │   └── 部署
  │       └── BYOS ← 每客戶一個 VM + 一個 Claude 訂閱 + Governance Daemon
  │
  ├── 為什麼做（Why）
  │   └── 進入顧問市場
  │       └── 前置：Phase 0 概念驗證 🔄
  │
  ├── 怎麼做（How）
  │   ├── Naruvia dogfooding 🔄
  │   │   ├── 全景圖原型 ✅
  │   │   ├── Paceriz Protocol ✅
  │   │   ├── Paceriz Ontology Instance ✅ ← 第一份多檔 ontology（骨架+神經+盲點）
  │   │   ├── ZenOS 文件重組 ✅
  │   │   ├── Ontology 架構定義 ✅
  │   │   ├── 服務架構設計 ✅ ← 三層治理系統 + 分階段實作方案
  │   │   └── 行銷夥伴試讀 📋
  │   └── 技術架構設計 📋（Phase 1）
  │
  └── 誰相關（Who）
      ├── Barry → 全端負責
      ├── 行銷夥伴 → 需要可用素材
      └── 顧問客戶 → 尚未獲取
```

---

## 文件索引（每份文件的四維標籤）

| 文件 | What | Why | How | Who（目標讀者） |
|------|------|-----|-----|----------------|
| CLAUDE.md | ZenOS 全局 | 快速接手 | — | AI / 新 session |
| spec.md | ZenOS 全局 | SSOT | Phase 0~3 全部 | Barry / 技術夥伴 |
| ontology.md | ZenOS | 自我治理 | ontology 範例 | Barry / 新 session |
| ontology-instances/paceriz/ | Paceriz | 第一份客戶端 ontology | 多檔架構驗證 | 老闆 / 高管 / AI agent |
| context-protocols/zenos.md | ZenOS | 理解產品 | — | 行銷夥伴 / 非技術人 |
| context-protocols/paceriz.md | Paceriz | 行銷素材 | Protocol 範例 | 行銷夥伴 |
| demo/naruvia-panorama.html | Naruvia 全局 | 能力展示 | Step 2a 產出物 | 老闆 / 客戶 |
| decisions/ADR-002-...md | ZenOS | 思考記錄 | North Star 推導 | Barry / 深度理解者 |
| archive/* | — | — | — | 已過時，僅供考古 |

---

*這份文件本身就是 ZenOS 的 ontology 實例 — 用產品自己的方法論描述產品自己*
