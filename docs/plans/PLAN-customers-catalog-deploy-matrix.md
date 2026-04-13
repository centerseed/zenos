---
spec: task-jJGLj584E7rKqqm43ZdA
created: 2026-04-12
status: done
---

# PLAN: Customers Catalog + Deploy Matrix

## Tasks
- [x] S01: 建立 `docs/customers.yml` 並讓 GitHub Actions `deploy.yml` 讀取客戶清單做 matrix deploy
  - Files: `docs/customers.yml`, `.github/workflows/deploy.yml`, `scripts/deploy.sh`（若需參數化）
  - Verify: `act/gh workflow dry-run` 或 `yamllint` + workflow syntax check（由 Developer/QA 提供實際證據）

- [x] S02: QA 驗收（規格符合 + workflow/部署規則符合 + 風險說明）
  - Files: 測試與驗收為主，不預設產品 code 變更
  - Verify: QA Verdict（PASS / CONDITIONAL PASS / FAIL）

## Decisions
- 2026-04-12: 優先處理確定未完成且可直接交付的 `jJGLj584E7rKqqm43ZdA`，避免在已落地但 task 狀態過期的項目上重工。
- 2026-04-12: deploy workflow 的 dashboard 主路徑改為 `scripts/deploy.sh`，並用 `docs/customers.yml` 建 matrix。
- 2026-04-12: QA 首輪發現 `docs/customers.yml` 單獨變更不會觸發 dashboard deploy；已補 `detect-changes` gate（`^docs/customers.yml$` -> dashboard=true）。

## Resume Point
全部完成。Task `jJGLj584E7rKqqm43ZdA` 可推進到 `review`；後續可選優化：把 load-customers 手寫 parser 升級為更穩定的 YAML parser。
