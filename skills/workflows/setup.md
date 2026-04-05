---
name: zenos-setup
description: >
  ZenOS 初始化設定——引導用戶輸入 API token，自動寫入 MCP 設定檔，
  完成後即可使用 /zenos-capture 和 /zenos-sync。
  僅在使用者明確說「/zenos-setup」「初次設定 ZenOS」「我還沒設定 MCP token」
  「幫我連接 ZenOS 服務」時使用。
  注意：「更新 skill」「同步 skill」「修改 skill」不應觸發此 skill。
version: 1.0.0
---

# /zenos-setup — ZenOS 初始化設定

歡迎使用 ZenOS！這個 skill 會幫你完成 MCP 連線設定，
設定完成後你就能用 `/zenos-capture` 把任何專案的知識建入 ontology。

整個過程大約 2 分鐘。

---

## Step 0：偵測 MCP 連線狀態

**在問用戶任何設定問題之前，先偵測 MCP 是否已設定。**

執行：
```python
mcp__zenos__search(query="ZenOS", collection="entities")
```

**結果判斷：**

| 結果 | 代表 | 下一步 |
|------|------|--------|
| 成功回傳（不論有無資料）| MCP 已設定且連線正常 | 跳過 Step 1–2，直接進 **Step 3** |
| 失敗（connection error / timeout）| 可能是 server 冷啟動 | 告知用戶「稍等 5 秒，ZenOS server 啟動中...」，等待 5 秒後再試一次 |
| 重試仍失敗 | MCP 尚未設定或 token 錯誤 | 繼續 Step 1 |

> MCP 第一次連線可能因 Cloud Run 冷啟動而需要 5-10 秒，不要立刻判定「未設定」。

---

## Step 1：確認使用模式

先問用戶：

```
你要設定哪種模式？

[1] Cloud 模式（推薦）
    連到 ZenOS 雲端服務，需要 API token
    適合：一般用戶、行銷夥伴、客戶

[2] 本地開發模式
    在本機跑 ZenOS MCP server，需要 GCP + GitHub 憑證
    適合：ZenOS 開發者

請輸入 1 或 2：
```

---

## Step 2A：Cloud 模式設定

**問用戶要 API token：**

```
請輸入你的 ZenOS API token：
（從 ZenOS 管理員或 https://zenos.app/settings 取得）
```

等用戶貼上 token 後，執行：

```bash
python .claude/skills/zenos-setup/scripts/setup.py --token {用戶輸入的 token}
```

**如果 script 成功：**
```
✅ 設定完成！

已寫入 .claude/mcp.json：
  zenos (Cloud) → https://zenos-mcp-xxx.run.app/mcp

下一步：
1. 重啟 Claude Code（Cmd+R 或關掉重開）
2. 重啟後輸入 /zenos-capture 開始使用
```

**如果 script 失敗（Python 不在路徑等）：**
手動引導用戶建立 `.claude/mcp.json`：

```json
{
  "mcpServers": {
    "zenos": {
      "type": "http",
      "url": "https://zenos-mcp-165893875709.asia-east1.run.app/mcp?api_key={TOKEN}"
    }
  }
}
```

把 `{TOKEN}` 替換成用戶輸入的 token，存到專案根目錄的 `.claude/mcp.json`。

---

## Step 2B：本地開發模式設定

依序問用戶：

```
1. Google Cloud Project ID（如 zenos-naruvia）：
2. GitHub Personal Access Token（ghp_ 開頭）：
3. Python venv 路徑（預設 .venv/bin/python，直接 Enter 跳過）：
```

收集完後執行：

```bash
python .claude/skills/zenos-setup/scripts/setup.py \
  --local \
  --gcp-project {GCP_PROJECT} \
  --github-token {GITHUB_TOKEN} \
  --venv-python {VENV_PYTHON}
```

---

## Step 3：驗證設定

設定完成後，詢問用戶是否要立刻驗證：

```
要現在驗證設定是否正確嗎？（需要先重啟 Claude Code）

重啟後輸入：
  /zenos-capture               ← 從當前對話捕獲知識（快速測試）
  /zenos-capture /path/to/dir  ← 掃描整個專案目錄建構 ontology
```

---

## 注意事項

- **token 不進 git**：`.claude/mcp.json` 應在 `.gitignore` 中（如果用戶有 git repo）
- **token 安全**：token 只存在本機的 mcp.json，不會傳到其他地方
- **多專案**：每個 Claude Code 專案可以有自己的 `.claude/mcp.json`，token 各自獨立
- **全域設定**：如果要在所有專案都能用，把 mcp.json 放到 `~/.claude/mcp.json`
