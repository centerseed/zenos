---
type: SKILL
id: setup
status: Draft
ontology_entity: TBD
created: 2026-03-27
updated: 2026-03-28
---

# setup — ZenOS 初始化與更新

> ⚠️ **即使 MCP 已連線，仍然必須從 Step 1 開始走完整流程。**
> MCP 已通 = 跳過 1b（token 設定），但 Step 2（拉 skills）和 Step 3（設定 agent）必須執行。
> 不要看到 MCP 已通就自行結束。

本 skill 讓任何 AI agent（Claude Code、Codex、Gemini、ChatGPT、自建 agent）
在任何專案中啟用 ZenOS 治理能力。

**設計原則**：本文件定義「要達成什麼」，不綁死「怎麼做」。
各平台的 agent 足夠聰明，能根據原則自行完成平台特定的設定。

---

## 執行路徑（自動判斷）

| 路徑 | 觸發條件 | 做什麼 |
|------|---------|--------|
| **首次設定** | MCP 連不上 | Step 1 → Step 2 → Step 3 → Step 4 |
| **更新模式** | MCP 已通 | Step 2 → Step 3（檢查）→ Step 4 |

設定一次後，之後跑 setup 就只會 pull 最新 skills。

---

## Step 1：MCP 連線

### 1a. 先探測

嘗試呼叫 ZenOS MCP（Cloud Run 有冷啟動，最多重試 3 次，間隔 5-10 秒）：

```
mcp__zenos__search(query="ZenOS", collection="entities")
```

| 結果 | 下一步 |
|------|--------|
| 正常回應 | MCP 已通 → **跳到 Step 2** |
| 連續超時或連線錯誤 | 進入 1b |
| 401 / 403 | token 無效，進入 1b |

### 1b. 設定 MCP（僅在 1a 未通時）

**問用戶要 API token**，然後把 MCP endpoint 設定寫入當前平台的 MCP 設定位置。

MCP endpoint 資訊：

```
URL:  https://zenos-mcp-165893875709.asia-east1.run.app/mcp
認證: URL query parameter ?api_key={TOKEN}
協定: HTTP (Streamable HTTP MCP)
```

**設定原則（不綁平台）：**

1. 找到當前平台存放 MCP server 設定的位置
2. 新增一個名為 `zenos` 的 MCP server，類型 HTTP，URL 如上
3. Token 不可進 git——確認該設定檔在 `.gitignore` 中
4. 設定完成後可能需要重啟 agent 環境才生效

**Claude Code 參考**：設定檔為 `.claude/mcp.json`（專案）或 `~/.claude/mcp.json`（全域）：

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

**本地開發模式**（僅 ZenOS 開發者）：需要 GCP project ID + GitHub token，用 `scripts/setup.py --local` 設定。

---

## Step 2：拉取 SSOT Skills

從 ZenOS GitHub repo 拉最新的治理 skill 到當前專案根目錄：

```bash
curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz | \
  tar -xz --strip-components=1 "zenos-main/skills/"
```

**若 agent 執行 curl 被沙箱權限擋住**（常見於 Claude Code 等平台）：

不要卡住。直接請用戶在終端機手動執行：

```
上面的 curl 指令被平台安全限制擋住了。
請你在終端機直接執行以下指令：

curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz | \
  tar -xz --strip-components=1 "zenos-main/skills/"

完成後告訴我，我繼續下一步。
```

用戶執行完後，驗證 `skills/governance/` 和 `skills/workflows/` 存在再繼續。

完成後專案根目錄會有：

```
skills/
  governance/          ← 治理規則（L2 / L3 文件 / Task）
  workflows/           ← 操作流程（capture / sync / setup / governance-loop）
  agents/              ← 角色參考設定（architect / pm / developer / qa / designer / marketing）
  README.md            ← 索引 + 使用指南
```

**驗證**：確認 `skills/governance/` 有 3 個檔案、`skills/workflows/` 有 4 個檔案。

**更新**：重跑同一行 curl 即可覆蓋更新到最新版。

---

## Step 3：讓 Agent 載入治理能力

這是最關鍵的一步。用戶需要決定**哪些 agent 要啟用哪些 ZenOS 能力**。

### 3a. 問用戶要啟用什麼

```
Skills 已同步。接下來選擇你要啟用的治理能力：

[A] 完整治理（推薦）
    包含：L2 知識治理 + L3 文件治理 + Task 治理
    適合：核心開發團隊

[B] 文件 + Task 治理
    包含：L3 文件治理 + Task 治理
    適合：PM、一般開發者

[C] 僅 Task 治理
    包含：Task 建票品質、驗收、知識反饋
    適合：只需要任務管理的團隊成員

[D] 自選
    你指定要啟用哪些

請選擇：
```

### 3b. 設定原則（跨平台通用）

不論選了什麼，agent 的設定必須達成以下效果：

**原則 1：Agent 必須知道治理 skill 的位置**

Agent 在執行受治理操作前，能找到並讀取 `skills/governance/` 下的對應檔案。
具體做法因平台而異（system prompt、CLAUDE.md、AGENTS.md、Instructions 等），
但效果必須等價於以下指示：

```
## ZenOS 治理技能

{根據用戶選擇的能力組合，列出對應的載入指示}
```

能力對照表：

| 能力 | 載入指示 |
|------|---------|
| L2 知識治理 | 操作 L2 節點前讀：`skills/governance/l2-knowledge-governance.md` |
| L3 文件治理 | 寫文件前讀：`skills/governance/document-governance.md` |
| Task 治理 | 建票/管票前讀：`skills/governance/task-governance.md` |

**原則 2：條件式載入**

指示中應包含條件判斷——若 `skills/governance/` 不存在（專案未安裝 ZenOS skills），
agent 應跳過治理流程，不報錯。這樣同一份 agent 設定可以用在有 ZenOS 和沒有 ZenOS 的專案。

**原則 3：角色 skill 也需要更新（如適用）**

如果當前平台支援角色 skill（如 Claude Code 的 `~/.claude/skills/`），
角色的 skill 定義中也應加入治理載入表。參考設定見 `skills/agents/`。

各角色建議的治理載入：

| 角色 | 建議能力 |
|------|---------|
| Architect | A（完整） |
| PM | B（文件 + Task） |
| Developer | C（Task） |
| QA | C（Task） |
| Designer | 文件治理（寫正式設計文件時） |
| Marketing | 文件治理（寫正式行銷文件時） |

### 3c. 平台特定的 slash command / 快捷指令（如適用）

某些平台支援 slash command 或快捷指令（如 Claude Code 的 `/zenos-capture`）。
若當前平台支援，應建立對應的指令入口，指向 `skills/workflows/` 的 SSOT 檔案：

| 指令 | SSOT |
|------|------|
| `/zenos-capture` | `skills/workflows/knowledge-capture.md` |
| `/zenos-sync` | `skills/workflows/knowledge-sync.md` |
| `/zenos-setup` | `skills/workflows/setup.md` |
| `/zenos-governance` | `skills/workflows/governance-loop.md` |

指令入口應為薄殼——只指向 SSOT 路徑，不包含實際邏輯。

**不支援 slash command 的平台**：跳過此步驟。用戶直接對 agent 說「同步 ontology」等關鍵字即可觸發。

---

## Step 4：驗證

### MCP 連線驗證

```
mcp__zenos__search(query="ZenOS", collection="entities")
```

### 治理 skill 安裝驗證

確認 `skills/governance/` 和 `skills/workflows/` 下的檔案數量正確。

### Agent 設定驗證

確認當前平台的 agent 設定中已包含治理載入指示。

### 輸出

```
✅ ZenOS Setup 完成

  MCP 連線：{✅ 已通 / ⏳ 需重啟後驗證}
  Skills：{N} 個治理 + {N} 個 workflow
  治理能力：{用戶選擇的組合}
  Agent 設定：{✅ 已更新 / 📝 請手動更新}

可以開始使用了：
  捕獲知識    → 告訴 agent「capture 這段對話」或「掃描這個專案」
  同步變更    → 告訴 agent「同步 ontology」或「掃 git 變更」
  治理巡檢    → 告訴 agent「治理掃描」
```

---

## 注意事項

- **Token 安全**：MCP token 只存在本機設定檔，不可進 git
- **冪等安全**：本 skill 可重複執行——MCP 已通跳過、skills 覆蓋更新、設定已存在不重複加入
- **多專案**：每個專案獨立的 MCP 設定和 skills 目錄
- **更新頻率**：ZenOS 治理規則更新時，重跑 Step 2 的 curl 即可拉到最新版
- **離線可用**：skills 拉到本地後不依賴網路（MCP 操作除外）
