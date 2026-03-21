# 官方工程 Skills 參考

來源：Anthropic knowledge-work-plugins / engineering

---

## 可直接安裝的官方 Skills

如果需要更完整的工程輔助，可以安裝官方 engineering plugin：
https://github.com/anthropics/knowledge-work-plugins/tree/main/engineering

包含的 skills：
- `architecture` — ADR 格式，技術選型決策
- `system-design` — 系統設計 5 步驟框架
- `testing-strategy` — 測試策略與測試計畫
- `code-review` — 代碼審查（安全、效能、正確性、可維護性）
- `debug` — 問題診斷框架
- `deploy-checklist` — 部署前檢查清單
- `incident-response` — 事故響應（SEV1-4 分級）
- `documentation` — 技術文件寫作
- `standup` — 站會更新
- `tech-debt` — 技術債管理

---

## 本 Architect skill 採用的官方框架

### system-design 的 5 步驟
1. Requirements Gathering（功能 + 非功能 + 限制）
2. High-Level Design（元件圖、資料流、API 合約）
3. Deep Dive（資料模型、API 設計、錯誤處理）
4. Scale & Reliability（擴展策略、監控）
5. Trade-off Analysis（讓取捨決策明確化）

### architecture 的 ADR 格式
Status → Context → Decision → Options → Trade-offs → Consequences → Action Items

### testing-strategy 的測試金字塔
Unit（多）→ Integration（中）→ E2E（少）
重點覆蓋：業務關鍵路徑、錯誤處理、邊界情況
