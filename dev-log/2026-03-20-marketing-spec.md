# ZenOS — 行銷自動化 Spec 產出紀錄

> 日期：2026-03-20
> 角色：Barry（產品負責人）、Claude（PM）

---

## 本次 Session 決策

1. **場景一確認**：從行銷業務開始，不走客服/訂單
   - 原因：Barry 是唯一用戶，不需要導入、信任曲線，立刻能驗證
   - Agent 層直接用 Claude Code，不走 naru_agent

2. **行銷平台選擇**：先以 Threads 為主
   - 台灣是 Threads 全球流量第二大市場，目前無廣告，是累積有機受眾的黃金期
   - B2B 顧問適合口語化、有立場的觀點分享

3. **市場調查範圍**：台灣中文市場為主
   - 關鍵字：AI 落地、中小企業數位轉型、CRM/ERP

4. **行銷方法論**：Content Pillar + Repurposing（GAPS Framework）
   - 每週 1 篇核心長文 → 拆分成 Threads 短文 + 圖卡
   - 從市場調查的內容缺口中選題

## 產出

- `docs/marketing-automation-spec.md` — 行銷自動化 Feature Spec（含兩個場景）

## 下一步

1. Architect 確認技術設計：Threads 爬取可行性、cron 排程方案、campaigns schema 調整
2. Developer 實作場景一（每日市場調查）的 Claude Code prompt + cron job
3. 跑通一週後，再啟動場景二（每週行銷計劃）

---

*紀錄自 2026-03-20 與 Barry 的對話*
