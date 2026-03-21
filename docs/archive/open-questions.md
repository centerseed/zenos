# ZenOS — 待決策項目

*由 PM skill 維護，每次討論後同步更新*

---

## 🔴 高優先（影響下一步開發）

- [x] ~~第一個真實業務場景的完整輸入輸出規格~~ — 已確認：行銷自動化（每日市場調查 + 每週行銷計劃），見 `docs/marketing-automation-spec.md`
- [ ] Threads 資料爬取可行性 — Threads 是否有公開 API？Claude Code 能否爬取？（待 Architect 確認）
- [ ] Claude Code CLI cron 排程方案 — 穩定性、中斷恢復機制（待 Architect 確認）

## 🟡 中優先（影響架構完整性）

- [ ] 五大 Collection 的欄位細節確認（由場景倒推收斂，目前 spec 中為粗估）
- [ ] LINE webhook 接入方式（Cloud Functions vs 長駐 server）
- [ ] 多租戶資料隔離（Firestore 的 collection path 策略）
- [ ] 簽核 Agent 的逾時處理

## 🟢 低優先（未來再處理）

- [ ] 排程 Agent 的觸發頻率與成本控制
- [ ] 與 Zentropy 個人版的架構共用程度
- [ ] 展示層技術選型（儀表板、報表分析）

---

*最後更新：2026-03-20*
