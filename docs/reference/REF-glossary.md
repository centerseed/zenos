---
type: REF
id: REF-glossary
status: Draft
ontology_entity: glossary
created: 2026-03-26
updated: 2026-03-26
---

# ZenOS 核心概念速查

| 概念 | 一句話 | 在 spec 的哪裡 |
|------|--------|---------------|
| 語意代理 | Entity = 知識的代理人，承載 context 讓 AI 不用讀原始文件就能判斷相關性 | Part 4「Ontology 的形式與治理架構」 |
| Entity 分層 | 三層：product（基礎）→ L2 治理概念（module + governance concepts）→ document/goal/role/project（應用層）。全部在 entities/ collection | Part 7.2「Entity 分層模型」 |
| Entity 邊界 | 三個判斷：跨時間存活？有四維可描述？能當錨點？→ 是 entity。否則是 task 或 entity.sources | Part 7.2「Entity 的邊界定義」 |
| Entity.sources | entity 身上掛的文件參考連結 [{uri, label, type}]。低價值文件不建 entity，掛 sources 就好 | Part 7.2 |
| Task ≠ Entity | Task 有自己的 collection 和生命週期（backlog→done），透過 linkedEntities 連到 ontology，是消費者不是節點 | Part 7.2 |
| 骨架層 | Layer 1（product）+ Layer 2（L2 治理概念）+ goal/role/project，從對話建立，低頻變動 | Part 4「雙層治理架構」 |
| 分層路由規則 | 新輸入先判斷本質：治理原則進 L2、正式文件進 L3、可驗收工作進 Task、低價值材料掛 sources | docs/specs/SPEC-l2-entity-redefinition.md |
| 神經層 | Layer 3 的 document entity + entity.sources，CRUD 自動觸發（Adapter），高頻變動 | Part 4「雙層治理架構」 |
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
| Adapter 架構 | 統一介面 + 多生態系 Adapter（Git/Google/MS/Notion），文件留用戶端 | Part 7 |
| ZenOS Dashboard | 唯一自建 UI，做六件事：全景圖、確認佇列、Protocol viewer、Storage Map、任務看板、團隊設定。不做文件管理 | Part 7 |
| Who + Owner 分離 | Who = 多值（context 分發給哪些角色），Owner = 單值（治理問責誰來確認） | docs/reference/REF-enterprise-governance.md |
| Who 三層模型 | 職能角色（ontology）→ 員工（公司層）→ agents（個人層）。ZenOS 管前兩層，第三層員工自理 | Part 0 + docs/reference/REF-enterprise-governance.md |
| Pull Model | Agent 自宣告身份，透過 MCP query 帶 role filter 拉 context。ZenOS 不維護 agent registry | docs/reference/REF-enterprise-governance.md |
| Action Layer | Ontology 的 output 路徑——任務管理。Ontology Context + 行動屬性。UI 和 MCP 對稱 | Part 7.1 |
| Entity ≠ Project | Entity(project) 是短期工作容器，Entity(product/L2 governance concept) 是長期知識。知識不跟著專案死 | Part 7.2 + ADR-006 |
| Dashboard 用語 | UI 不出現 entity/ontology。Product→專案、Module→模組、Knowledge Graph→知識地圖、Entity→「節點」 | Part 7.3 |
| 權限模型 | 三層：來源層→ Ontology 層（entity.visibility + role）→ 消費層。Phase 0: admin/member/agent | Part 7.6 |

---

## 關鍵發現（2026-03-21 驗證）

1. What/Who 是事實性維度，AI 高準確度；Why/How 是意圖性維度，必須人確認
2. 老闆是 top-down 思維：先展示全景圖建立信任，再問他要什麼
3. 盲點推斷是核心差異化：從跨產品關係圖中推斷老闆沒注意到的問題
4. Ontology 建構的資訊來源不能依賴 codebase：真實場景老闆不會給
5. 漸進式信任是 ZenOS 最關鍵的設計：決定 go-to-market 能不能走通
6. Ontology 是文件的語意代理，不是文件本身也不是索引
7. 骨架層 + 神經層的雙層治理：低頻結構（對話建）+ 高頻標籤（CRUD 觸發）互相餵養
8. Context Protocol 是 ontology 的 view，不是手寫文件
9. 市場空白確認：面向 SMB 的整合產品不存在
10. Conversation Adapter 是被 dogfooding 發現的：AI 對話產出的知識捕獲點必須在產生點
11. Agent 本質是 skill，Pull Model 而非 Push Model
12. 任務是 ontology context + Who 三層模型 + 生命週期的交匯點：驗證 ontology 品質的唯一手段
13. 知識地圖是 demo killer：展示 entity 關係圖給客戶全新視角，差異化在「原來我的公司知識長這樣」
14. Entity 對外不叫 entity：UI 用「節點」或具體 type 名稱
