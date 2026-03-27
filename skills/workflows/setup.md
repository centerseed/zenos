---
type: SKILL
id: setup
status: Draft
ontology_entity: TBD
created: 2026-03-27
updated: 2026-03-27
---

> 權威來源：本文件是 `/zenos-setup` 操作流程的 SSOT。
> `.claude/skills/zenos-setup/SKILL.md` 為舊格式，以本文件（`skills/workflows/setup.md`）為準。

# setup — ZenOS 初始化與更新

本 skill 有兩種執行路徑，自動判斷：

| 路徑 | 觸發條件 | 執行步驟 |
|------|---------|---------|
| **首次設定** | MCP 連不上 | Step 0 → Step 1（MCP 設定）→ 重啟 → Step 2 → Step 3 |
| **更新模式** | MCP 已通 | Step 0 → Step 2（pull 最新 skills + 薄殼）→ Step 3（檢查 prompt） |

設定一次 MCP 後，之後只要跑 `/zenos-setup` 就會自動走更新模式，pull 最新治理 skill 到本地專案。

---

## Step 0：探測 MCP 連線

**嘗試呼叫 MCP：**

```
mcp__zenos__search(query="ZenOS", collection="entities")
```

Cloud Run 有冷啟動延遲，第一次可能超時。**最多重試 3 次，每次間隔 5-10 秒**。

**判斷結果：**

| 結果 | 下一步 |
|------|--------|
| 收到正常回應（有結果或空列表） | MCP 已通 → **跳到 Step 2（更新模式）** |
| 連續 3 次超時或連線錯誤 | MCP 未設定 → **進入 Step 1（首次設定）** |
| 回傳 401 / 403（認證失敗） | token 過期或無效 → **進入 Step 1** |

**若 MCP 已通（更新模式），告知用戶：**

```
✅ MCP 已連線，進入更新模式。
正在為你 pull 最新的治理 skill...
```

---

## Step 1：MCP 連線設定（僅在 Step 0 未通時執行）

### 確認使用模式

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

### Cloud 模式（選 1）

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
✅ MCP 設定完成！

已寫入 .claude/mcp.json：
  zenos (Cloud) → https://zenos-mcp-xxx.run.app/mcp

需要重啟 Claude Code 才能生效（Cmd+R 或關掉重開）。
重啟後再執行一次 /zenos-setup，會自動跳到 skill 同步步驟。
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

### 本地開發模式（選 2）

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

## Step 2：同步 SSOT Skills（首次設定 + 更新模式都執行）

### 2a. 從 GitHub 拉最新 skills

從 ZenOS GitHub repo 拉最新的治理 skill 到當前專案：

```bash
curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz | \
  tar -xz --strip-components=1 "zenos-main/skills/"
```

這會在專案根目錄建立（或更新）`skills/` 資料夾：

```
skills/
  governance/
    l2-knowledge-governance.md   ← L2 知識節點治理
    document-governance.md       ← L3 文件治理
    task-governance.md           ← Task 治理
  workflows/
    knowledge-capture.md         ← 知識擷取
    knowledge-sync.md            ← 增量同步
    setup.md                     ← 本文件
    governance-loop.md           ← 治理閉環
  README.md                      ← 索引 + 使用說明
```

**驗證安裝成功：**

```bash
ls skills/governance/ skills/workflows/
```

應看到 3 個 governance + 4 個 workflow 檔案。

### 2b. 生成 Claude Code Slash Command 薄殼（僅 Claude Code 適用）

如果當前平台是 Claude Code，需要在 `.claude/skills/` 建立 slash command 的薄殼檔案，讓 `/zenos-capture`、`/zenos-sync` 等指令可用。

**逐一建立以下 4 個薄殼：**

```bash
mkdir -p .claude/skills/zenos-capture .claude/skills/zenos-sync .claude/skills/zenos-setup .claude/skills/zenos-governance
```

**`.claude/skills/zenos-capture/SKILL.md`**

```markdown
---
name: zenos-capture
description: >
  從當前對話、單一文件、或整個專案目錄擷取知識並寫入 ZenOS ontology。
  當使用者說「存進 ontology」「記到 ZenOS」「capture 這段」「/zenos-capture」，
  或說「把這個專案加入 ZenOS」「幫我建這個服務的 ontology」時使用。
version: 2.0.0
---
# /zenos-capture
**本 skill 的 SSOT 位於 `skills/workflows/knowledge-capture.md`。**
請先用 Read tool 讀取 `skills/workflows/knowledge-capture.md` 的完整內容，然後嚴格按照該文件的流程執行。
```

**`.claude/skills/zenos-sync/SKILL.md`**

```markdown
---
name: zenos-sync
description: >
  掃描 git log 找出最近變更的文件，比對 ZenOS ontology，批量 propose 更新。
  當使用者說「同步 ontology」「sync ZenOS」「掃 git 變更」「/zenos-sync」時使用。
  注意：第一次為某個專案建立 ontology 請用 /zenos-capture。
version: 2.0.0
---
# /zenos-sync
**本 skill 的 SSOT 位於 `skills/workflows/knowledge-sync.md`。**
請先用 Read tool 讀取 `skills/workflows/knowledge-sync.md` 的完整內容，然後嚴格按照該文件的流程執行。
```

**`.claude/skills/zenos-setup/SKILL.md`**

```markdown
---
name: zenos-setup
description: >
  ZenOS 初始化設定——探測 MCP 連線、安裝 SSOT skills、設定 agent prompt。
  當使用者說「設定 ZenOS」「初始化 ZenOS」「setup ZenOS」「/zenos-setup」時使用。
version: 2.0.0
---
# /zenos-setup
**本 skill 的 SSOT 位於 `skills/workflows/setup.md`。**
請先用 Read tool 讀取 `skills/workflows/setup.md` 的完整內容，然後嚴格按照該文件的流程執行。
注意：setup script 位於 `.claude/skills/zenos-setup/scripts/setup.py`，路徑不變。
```

**`.claude/skills/zenos-governance/SKILL.md`**

```markdown
---
name: zenos-governance
description: >
  ZenOS 治理總控。當使用者要「讓 agent 自動治理現有專案」或
  「掃描結果不滿意，請自動修復」時使用。
version: 2.0.0
---
# /zenos-governance
**本 skill 的 SSOT 位於 `skills/workflows/governance-loop.md`。**
請先用 Read tool 讀取 `skills/workflows/governance-loop.md` 的完整內容，然後嚴格按照該文件的流程執行。

相關治理規則（按需載入）：
- L2 治理：`skills/governance/l2-knowledge-governance.md`
- L3 文件治理：`skills/governance/document-governance.md`
- Task 治理：`skills/governance/task-governance.md`
```

**冪等檢查**：建立前先確認 `.claude/skills/zenos-*/SKILL.md` 是否已存在。若已存在且內容與上方模板一致，跳過；若內容不同（舊版），覆蓋更新。

**非 Claude Code 平台**：跳過此步驟。其他平台直接透過 Step 3 的 prompt 指示讓 agent 讀取 `skills/` 目錄。

---

## Step 3：設定 Agent Prompt（讓 agent 載入治理 skill）

Skills 拉下來後，需要在 agent 的設定中加入載入指示，agent 才會在對應場景自動讀取治理規則。

**先檢查是否已設定過：**

```
Grep(pattern="ZenOS 治理技能", path="CLAUDE.md")  # 或 AGENTS.md 等
```

- 已有 `## ZenOS 治理技能` 段落 → 告知「Agent prompt 已設定，跳過」→ 進入 Step 4
- 沒有 → 繼續引導

**告知用戶：**

```
Skills 已同步完成。接下來需要讓你的 agent 知道這些 skill 的存在。

請在你的 agent 設定檔中加入以下內容：

┌─────────────────────────────────────────────────┐
│ ## ZenOS 治理技能                                │
│                                                  │
│ 寫文件前讀：skills/governance/document-governance.md  │
│ 操作 L2 節點前讀：skills/governance/l2-knowledge-governance.md │
│ 建票/管票前讀：skills/governance/task-governance.md    │
└─────────────────────────────────────────────────┘

要加在哪裡？依你的平台：

  Claude Code  → 專案根目錄的 CLAUDE.md
  Codex        → AGENTS.md 或 agent 的 system prompt
  ChatGPT      → Custom GPT 的 Instructions
  Gemini       → System instruction
  自建 agent   → System prompt

要我幫你自動加到 CLAUDE.md 嗎？（y/n）
```

**若用戶回答 y（且當前專案有 CLAUDE.md）：**

1. 讀取現有 CLAUDE.md
2. 檢查是否已有 `## ZenOS 治理技能` 段落
   - 已有 → 告知「已經設定過了，跳過」
   - 沒有 → 在檔案末尾追加載入指示
3. 顯示變更確認

**若用戶回答 n 或其他平台：**

```
沒問題，請手動把上面那段文字貼到你的 agent 設定中。
完成後你的 agent 就會在對應場景自動載入治理規則。
```

---

## Step 4：驗證

**若 MCP 已通（Step 0 通過或 Step 1 設定後重啟）：**

```
設定完成！來快速驗證一下：

1. 搜尋 ontology 確認連線...
```

執行：
```
mcp__zenos__search(query="ZenOS", collection="entities")
```

若有回應：
```
✅ 一切正常！

  MCP 連線：✅
  Skills 安裝：✅（{N} 個 governance + {N} 個 workflow）
  Agent Prompt：✅（已加入 / 請手動加入）

你可以開始使用了：
  /zenos-capture               ← 從當前對話捕獲知識
  /zenos-capture /path/to/dir  ← 掃描專案目錄建構 ontology
  /zenos-sync                  ← 同步 git 變更到 ontology
```

**若 MCP 未通（Step 1 剛設定，還沒重啟）：**

```
MCP 設定已寫入，但需要重啟 Claude Code 才能生效。

  1. 重啟 Claude Code（Cmd+R 或關掉重開）
  2. 重啟後再執行 /zenos-setup 驗證連線
```

---

## 注意事項

- **token 不進 git**：`.claude/mcp.json` 應在 `.gitignore` 中（如果用戶有 git repo）
- **token 安全**：token 只存在本機的 mcp.json，不會傳到其他地方
- **多專案**：每個 Claude Code 專案可以有自己的 `.claude/mcp.json`，token 各自獨立
- **全域設定**：如果要在所有專案都能用，把 mcp.json 放到 `~/.claude/mcp.json`
- **skills 更新**：`skills/` 目錄從 ZenOS repo 拉取，重跑 Step 2 的 curl 指令即可更新到最新版
- **冪等安全**：本 skill 可重複執行。MCP 已通時自動跳過設定，skills 拉取為覆蓋更新，prompt 已存在時不重複加入
