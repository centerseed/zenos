---
spec: ADR-024-mcp-multi-workspace-context.md
created: 2026-04-09
status: done
---

# PLAN: MCP 多 Workspace Context 實作

## Tasks

- [x] S01: 抽取 workspace_context.py 共用模組 + 改 ApiKeyMiddleware + tool 參數 + _unified_response 注入
  - Files:
    - `src/zenos/application/workspace_context.py` (新建)
    - `src/zenos/interface/dashboard_api.py` (改為 import 共用模組)
    - `src/zenos/interface/tools.py` (ApiKeyMiddleware workspace resolution + write/task/confirm 加 workspace_id 參數 + _unified_response 注入 workspace_context)
    - `src/zenos/infrastructure/context.py` (可能需加 ContextVar)
  - Verify: `.venv/bin/pytest tests/ -x` + `cd dashboard && npx vitest run`
- [x] S02: QA 驗收 S01 — PASS (2026-04-09)
  - Verify: 靜態檢查 + 全套測試 + 場景驗證
- [x] S03: 更新 tool docstrings + setup skill 文件
  - Files:
    - `src/zenos/interface/tools.py` (tool description 加 workspace_id 說明)
    - `skills/release/zenos-setup/SKILL.md` (system prompt 模板加 workspace 指引)
  - Verify: 文件內容審查

## Decisions

- 2026-04-09: S01+S02 合併為一次 Developer dispatch，因為模組抽取和 middleware 改動邏輯緊密耦合，分開會增加不必要的 context switching 成本。

## Resume Point

全部完成。S01 Developer PASS → S02 QA PASS → S03 文件更新完成。待部署。
