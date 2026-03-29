---
type: PB
id: PB-onboarding-strategy
status: Approved
ontology_entity: TBD
created: 2026-03-21
updated: 2026-03-27
---

# Playbook: ZenOS 導入策略

> 從 `docs/spec.md` Part 6 搬出。原始內容寫於 2026-03-21。


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
  產出：文件索引表（見 REF-ontology-current-state.md）

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
