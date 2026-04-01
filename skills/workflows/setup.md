---
name: zenos-setup
version: 3.0.0
---

# ZenOS Setup 工作流程

## 前提條件

- 有效的 ZenOS API token（向 ZenOS 管理員取得）
- Claude Code 或支援 MCP 的 agent 環境

## 步驟

### Step 1：確認 MCP 連線狀態

呼叫任意 MCP tool 確認連線是否正常，例如：

```
mcp__zenos__search(collection="entities", query="test", limit=1)
```

- 若成功回傳：MCP 已連線，跳至 Step 2
- 若失敗：引導用戶完成 MCP 設定（填入 API token 至 MCP 設定檔），再重試

### Step 2：呼叫 setup 取得安裝指引

```
mcp__zenos__setup(platform="claude-code")
```

`platform` 可為：`claude-code`、`chatgpt`、`gemini`、`cursor`。

回傳內容包含：
- 最新治理 skills 的安裝路徑與指令
- 各 skill 的用途說明

### Step 3：安裝最新治理 skills

按照 Step 2 回傳的指引執行安裝。通常包含：

1. 從 GitHub 拉取最新 skills 到 `skills/` 目錄
2. 確認以下 skills 已安裝：
   - `skills/workflows/setup.md`（本文件）
   - `skills/workflows/knowledge-capture.md`
   - `skills/workflows/knowledge-sync.md`
   - `skills/workflows/governance-loop.md`
   - `skills/governance/l2-knowledge-governance.md`
   - `skills/governance/document-governance.md`
   - `skills/governance/task-governance.md`
   - `skills/governance/capture-governance.md`

### Step 4：驗證 agent 治理能力

執行一次輕量驗證，確認 agent 可正常使用 MCP tools：

```
mcp__zenos__search(collection="entities", query="", limit=5)
```

若回傳正常，setup 完成。

## MCP Tools 使用

- `mcp__zenos__setup(platform=...)` — 取得對應平台的安裝指引與最新 skills
- `mcp__zenos__search(...)` — 驗證 MCP 連線是否正常

## 注意事項

- 即使 MCP 已連線，每次執行 `/zenos-setup` 仍需完整走 Step 2–3，以拉取最新版 skills
- `platform` 參數影響回傳的安裝指令格式，務必填寫正確
- Skills 版本落後可能導致治理行為不一致，建議定期重新執行 setup
