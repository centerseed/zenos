# Architect → PM：/zenos-sync Skill PRD 待確認事項

> 日期：2026-03-21
> 來源：Architect 審查 spec Part 7 Conversation Adapter 章節後提出
> 需要：PM 回答以下 6 個問題，Architect 才能開始技術設計

---

## 背景

Phase 1 MCP Server 已部署完成（Cloud Run + 17 個 tools + API key 認證）。
下一步是把 ontology 建構/更新流程包成 Claude Code skill，讓 Barry 能在日常開發中觸發 ontology 同步。

Spec 中有兩個相關設計：
1. **Phase 0.5 session-level sync**（spec line 1417-1444）— 每次 session 結束前自動問
2. **Conversation Adapter + `/zenos-update` skill**（spec line 1727-1838）— 從對話擷取知識

兩者有重疊，需要 PM 釐清 Phase 1 的範圍。

---

## 必答問題

### Q1：一個 skill 還是多個？

Spec 提到的功能其實是兩件事：
- **A. Ontology sync**：掃 git 變更 → 更新 ontology（Phase 0.5 的延伸）
- **B. 對話知識擷取**：從當前對話中提取有價值的知識 → propose 到 ontology

Phase 1 要做 A + B 合成一個 `/zenos-sync`？還是拆成兩個 skill？
還是 Phase 1 只做 A？

### Q2：Session context 讀取範圍

Claude Code skill 觸發時，AI 能讀到當前 session 的完整對話。
但如果對話很長（幾千行），全部讀會很慢且浪費 token。

選項：
- **a.** 全部讀（簡單但貴）
- **b.** 只讀最近 N 則訊息
- **c.** 用戶先說「這段值得存」，skill 只讀標記的部分
- **d.** AI 自己判斷哪些有價值（最聰明但最不可控）

PM 建議？

### Q3：Proposal 確認 UX

Phase 1 沒有 Dashboard。Skill 提出 ontology 更新建議後，用戶怎麼確認？

選項：
- **a.** 在對話中逐一列出，用戶說「確認」或「跳過」
- **b.** 全部列出，用戶說「全部確認」或挑著改
- **c.** 神經層自動生效（draft），骨架層才需要確認

Architect 建議選 **c**（跟 spec 的設計一致：神經層 AI 自動，骨架層人確認）。

### Q4：骨架層 propose 權限

Spec 標記這是「必答」但沒回答：**對話可以直接 propose 新的骨架層實體嗎？**

例如 Barry 在對話中說「我們決定做一個新產品叫 XYZ」，skill 可以直接 propose 新的 Entity 嗎？

Architect 建議：**可以 propose，但一律 draft，需要 confirm()。**

### Q5：動作 2（存放原始內容）Phase 1 要做嗎？

Spec 設計了「雙動作」：
1. 更新 ontology（核心）
2. 存放原始內容到用戶習慣的地方（git commit / Google Drive / Firestore）

Phase 1 要做動作 2 嗎？如果不做，對話中產出的知識只有 ontology entry 的摘要，沒有原始全文。

Architect 建議：**Phase 1 不做動作 2。** 原因：
- 簡化範圍
- ontology entry 的 summary 已經夠行銷 agent 用了
- 如果需要原始內容，用戶自己手動存就好

### Q6：跟 Phase 0.5 ontology sync 的關係

Spec 描述的 Phase 0.5 流程是：
> session 結束前 Claude 自動問：「這次 session 有影響 ontology 的變更嗎？」

這個 skill 是**取代** Phase 0.5（用戶主動呼叫 `/zenos-sync`），還是**共存**（skill + session 結束前自動提醒）？

Architect 建議：**取代。** 用 skill 統一入口，不要兩套觸發機制。

---

## Architect 的預設方案（如果 PM 沒意見就照這個做）

```
/zenos-sync 觸發時：
  1. 讀 git log --since="上次 sync" → 找出變更的文件
  2. 讀當前對話 context（全部）→ 找出有價值的新知識
  3. 對照 Firestore 現有 ontology → 產出 proposals
     - 神經層：直接寫入 draft（confirmedByUser: false）
     - 骨架層：列出讓用戶當場確認（在對話中 confirm）
  4. 不做動作 2（不存原始內容）
  5. 取代 Phase 0.5 的 session 結束提醒
```

---

*PM 請回覆每個問題的決定。如果同意 Architect 預設方案，回「照預設」即可。*
