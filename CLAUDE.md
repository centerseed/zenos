# ZenOS

## 一句話

**中小企業的 AI Context 層——建一次 ontology，公司的每一個 AI agent 都共享同一套 context，讓每次 AI 互動都從「懂你的公司」開始。**

不是 ERP、不是搜尋引擎、不是文件管理、不是 AI 落地顧問。ZenOS 在所有文件之上長出一層語意代理（Semantic Proxy），讓公司的 AI agents 共享全局 context。人也受益（全景圖、Protocol），但最大的受益者是 AI agents——從資料孤島到全公司同一套 context，產能百倍提升。

---

## 現在在什麼階段

Phase 0 — 概念驗證。還沒寫程式碼，在打磨核心流程設計。

2026-03-21 的進度：
- ✅ North Star 確立：Knowledge Ontology for SMB
- ✅ Ontology 架構定義：語意代理 + 雙層治理（骨架層/神經層）+ 演化路線
- ✅ 四維標籤體系（What/Why/How/Who）設計完成
- ✅ Step 2 導入流程驗證：用 Naruvia 自身做 dogfooding
- ✅ 漸進式信任模型（Progressive Trust）定義完成 — 這是產品的護城河
- ✅ 公司全景圖 + 盲點推斷 + 問題→解法展示 原型完成
- ✅ 第一份 Context Protocol（Paceriz）完成
- ✅ 已知風險分析：6 項風險 + 驗證計畫
- ✅ 服務架構設計：三層治理系統（事件源 → 治理引擎 → 確認同步）+ 分階段實作（Phase 0.5~2）
- ✅ 跨生態系整合策略：Adapter 架構（Git/Google/MS/Notion）+ ZenOS Dashboard 定位（只做消費介面）
- ✅ 「什麼都沒有」產品策略：不自建文件管理，Dashboard = 知識體檢報告 + Drop Zone 讀完即丟
- ✅ 架構模式決策：選模式 A（分散 agents + 共享 context）— Firestore + MCP + ZenOS 治理服務
- ✅ 跨 agent context 共享研究：8 種方法比較，MCP 是唯一滿足所有條件的方案
- ✅ 企業導入治理文件：Who + Owner 分離、部門架構映射、Proposal 問答集
- ✅ Who 三層消費模型：職能角色→員工→agents，Pull Model，agent 自宣告身份
- ✅ Action Layer 設計：任務模型（Ontology Context + 行動屬性）、Kanban 狀態流、優先度 AI 推薦、Inbox/Outbox 雙視角
- ✅ Dashboard 擴展為六件事：全景圖、確認佇列、Protocol、Storage Map、任務看板、團隊設定
- 📋 下一步：Architect 確認 Action Layer MCP 介面規格 + Dashboard v1 頁面實作優先級

---

## 讀文件的順序

新 session 或新夥伴，按這個順序讀：

### 1. 理解 ZenOS 在幹嘛（10 分鐘）

讀 `docs/spec.md` 的 Part 0（North Star）和 Part 1（核心命題）。
這告訴你：問題是什麼、為什麼現有解法都失敗、ZenOS 怎麼解。

### 2. 理解核心流程（15 分鐘）

讀 `docs/spec.md` 的 Part 4（Knowledge Ontology 技術路線）。
重點是：
- Ontology 的形式與治理架構（語意代理 + 雙層治理）
- 四維標籤體系（What/Why/How/Who）
- Step 2 完整流程（全景圖 → 迭代收斂 → Context Protocol）
- Step 3 Ontology 觸發規則（何時新建/更新/歸檔）
- 漸進式信任模型（Part 5）— **這是最關鍵的章節**
- 服務架構（Part 7）— 三層治理系統 + 分階段實作 + 跨生態系 Adapter + Dashboard 定位

### 3. 看 ZenOS 自身的 Ontology（5 分鐘）

`docs/ontology.md` — ZenOS 用自己的方法論描述自己。包含：
- 所有實體的四維標籤（What/Why/How/Who）
- 實體之間的關係圖
- 每份文件的索引（哪份文件給誰看、關於什麼）

### 4. 看實戰成果（5 分鐘）

- `docs/demo/naruvia-panorama.html` — 用 Naruvia 自身驗證的全景圖原型
- `docs/context-protocols/paceriz.md` — 第一份 Context Protocol 實例

### 5. 理解思考過程（選讀）

- `docs/decisions/ADR-002-knowledge-ontology-north-star.md` — 從「跨部門 context 管理」到「Knowledge Ontology」的完整推導過程

---

## 文件地圖

```
docs/
├── spec.md                          ← 產品 Spec（SSOT，所有設計的真相來源）
├── ontology.md                      ← ZenOS 自身的 Ontology（實體 + 關係 + 文件索引）
├── ontology-methodology.md          ← Ontology 治理方法論（拆分粒度規則）
├── enterprise-governance.md         ← 部門架構與責任歸屬（Proposal 武器庫）
├── specs/
│   └── phase1-ontology-mvp.md       ← Phase 1 MVP Feature Spec（PM → Architect）
├── ontology-instances/
│   └── paceriz/                     ← 第一份客戶端 Ontology Instance（dogfooding）
│       ├── index.md                 ← 骨架層全景（老闆看這份）
│       ├── modules/
│       │   ├── training-plan.md     ← 訓練計畫系統
│       │   ├── data-integration.md  ← 運動數據整合
│       │   ├── acwr.md              ← ACWR 安全機制
│       │   └── rizo-ai.md           ← Rizo AI 教練
│       ├── blindspots.md            ← AI 盲點分析
│       └── neural-layer.md          ← 文件級 entry 索引（AI agent 用）
├── context-protocols/
│   ├── zenos.md                     ← ZenOS 自己的 Context Protocol（dogfooding）
│   └── paceriz.md                   ← 第一份客戶端 Context Protocol 實例
├── demo/
│   └── naruvia-panorama.html        ← 全景圖原型（含問題→解法展示）
├── decisions/
│   ├── ADR-001-marketing-automation-architecture.md  ← 已過時（方向已轉）
│   └── ADR-002-knowledge-ontology-north-star.md      ← 核心推導過程
└── archive/
    ├── marketing-automation-spec.md  ← 3/20 時代的行銷自動化 spec（已過時）
    ├── open-questions.md             ← 3/20 時代的待決策項目（部分已過時）
    └── paceriz-v0-single-file.md.bak ← 單檔版 ontology 原型（已被多檔版取代）
```

---

## 核心概念速查

| 概念 | 一句話 | 在 spec 的哪裡 |
|------|--------|---------------|
| 語意代理 | Ontology entry = 文件的代理人，承載 context 讓 AI 不用讀原始文件就能判斷相關性 | Part 4「Ontology 的形式與治理架構」 |
| 骨架層 | 公司的實體關係圖（產品、目標、角色），從對話建立，低頻變動 | Part 4「雙層治理架構」 |
| 神經層 | 每份文件的 ontology entry，CRUD 自動觸發，高頻變動 | Part 4「雙層治理架構」 |
| 雙層互動 | 神經層異常反推骨架層更新（新實體、休眠實體、突發關聯） | Part 4「雙層治理架構」 |
| 四維標籤 | 所有知識用 What/Why/How/Who 四個維度標注，是 AI 自動治理的依循 | Part 0 |
| Context Protocol | Ontology 的 view — 從 ontology 自動生成、人微調確認，不是手寫文件 | Part 0 + Part 4 Step 2d |
| 漸進式信任 | 不要求資料，先用對話展示價值，信任是賺來的 | Part 5 |
| 全景圖 | AI 從 30 分鐘對話產出公司全貌 + 盲點推斷（骨架層的視覺展示） | Part 4 Step 2a-2b |
| confirmedByUser | AI 產出 = draft，人確認 = 生效（資料層→知識層通用） | Part 4 |
| Meta-Ontology | Schema 層：定義「ontology 應該長什麼樣」，全客戶共用一套 | Part 4「Ontology 的層次結構」 |
| Ontology ≠ 原始文件 | 存語意代理和結構，不存文件內容，降低機密風險 | Part 5 |
| BYOS | 每客戶一個 VM + 一個 Claude 訂閱，資料不過 ZenOS | Part 5 |
| 三層治理系統 | 事件源層（偵測 CRUD）→ 治理引擎層（AI 分析）→ 確認同步層（人確認 + 級聯更新） | Part 7 |
| Governance Daemon | Phase 2 常駐服務：事件佇列 + AI 分析 + 自動更新神經層 + 骨架層待確認 | Part 7 |
| Adapter 架構 | 統一介面 + 多生態系 Adapter（Git/Google/MS/Notion），文件留用戶端 | Part 7 |
| ZenOS Dashboard | 唯一自建 UI，做六件事：全景圖、確認佇列、Protocol viewer、Storage Map、任務看板、團隊設定。不做文件管理 | Part 7 |
| Who + Owner 分離 | Who = 多值（context 分發給哪些角色），Owner = 單值（治理問責誰來確認） | enterprise-governance.md |
| Who 三層模型 | 職能角色（ontology）→ 員工（公司層）→ agents（個人層）。ZenOS 管前兩層，第三層員工自理 | Part 0 + enterprise-governance.md |
| Pull Model | Agent 自宣告身份（在 skill 裡寫職能角色），透過 MCP query 帶 role filter 拉 context。ZenOS 不維護 agent registry | enterprise-governance.md |
| Action Layer | Ontology 的 output 路徑——任務管理。Ontology Context + 行動屬性（優先度/狀態/指派/期限/依賴/驗收）。UI 和 MCP 對稱 | Part 7.1 |
| Inbox / Outbox | 任務的雙視角——「派給我的」和「我派出的」。人和 agent 共用同一套模型 | Part 7.1 |
| confirmedByCreator | 任務驗收機制——執行者標記 review，派任者確認 done 或 rejected。與 confirmedByUser（知識確認）合併在確認佇列 | Part 7.1 |
| Conversation Adapter | AI 對話作為事件源——知識捕獲在產生點，透過 Skill + MCP 直接 propose ontology 更新 | Part 7 Adapter 架構 |

---

## 關鍵發現（2026-03-21 驗證）

1. **What/Who 是事實性維度，AI 高準確度；Why/How 是意圖性維度，必須人確認**
2. **老闆是 top-down 思維：先展示全景圖建立信任，再問他要什麼**
3. **行銷文件 ≠ 行銷夥伴能用的文件：marketing/ 裡放的是技術文件是常態**
4. **盲點推斷是核心差異化：從跨產品關係圖中推斷老闆沒注意到的問題**
5. **Ontology 建構的資訊來源不能依賴 codebase：真實場景老闆不會給**
6. **漸進式信任是 ZenOS 最關鍵的設計：決定 go-to-market 能不能走通**
7. **Ontology 是文件的語意代理，不是文件本身也不是索引：各部門不改習慣，ontology 在文件之上自動生長**
8. **骨架層 + 神經層的雙層治理：低頻結構（對話建）+ 高頻標籤（CRUD 觸發）互相餵養**
9. **Context Protocol 是 ontology 的 view，不是手寫文件：底層 ontology 變了，Protocol 自動更新**
10. **市場空白確認：碎片方案存在（Microsoft/Glean/Collibra），面向 SMB 的整合產品不存在**
11. **Markdown + Git 是最乾淨的事件源：git commit = CRUD 事件，自帶 who/what/when/diff，零基礎設施**
12. **Phase 0.5 立刻可用：git log + Claude Code session = 手動觸發的 ontology 治理，不需要任何基礎設施**
13. **ZenOS Dashboard ≠ 文件管理工具：是「公司知識的體檢報告」，不取代 Google Drive / Notion**
14. **「什麼都沒有」不是障礙：Stage 0 只需對話，不需要任何儲存層。漸進式信任的威力**
15. **Adapter 架構是擴展的關鍵：統一介面 + 多 Adapter，新增生態系 = 新增 Adapter，Engine 零改動**
16. **Conversation Adapter 是被 dogfooding 發現的：AI 對話產出的知識不在任何檔案系統裡，捕獲點必須在產生點**
17. **Who 不能寫死「角色是人還是 agent」：不同公司在 AI 採用光譜上位置不同，Who = 職能角色，消費端自行綁定**
18. **Agent 本質是 skill，靜態綁定不可行：Pull Model（agent 自宣告身份）而非 Push Model（ZenOS 推送 context）**
19. **任務是 ontology context + Who 三層模型 + 生命週期的交匯點：Action Layer 不只是功能，是驗證 ontology 品質的唯一手段**
20. **UI 和 MCP 必須對稱：自然語言對話容易遺失全貌，UI 補充 agent 低效的地方（全局總覽、批次操作、進度追蹤）**

---

## 開發閉環（未來進入開發時啟用）

角色定義在 `.claude/skills/` 下，但目前 Phase 0 還不需要。
進入 Phase 1 開始寫程式碼時再啟用。

| 角色 | 用途 |
|------|------|
| PM | 需求整理、Feature Spec |
| Architect | 技術設計、任務分配 |
| Developer | 實作、測試 |
| QA | Quality Gate |
| Coach | 週回顧、skill 優化 |
