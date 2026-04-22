---
name: zenos-setup
description: >
  ZenOS 初始化與更新設定——偵測 MCP 連線狀態，安裝/更新 skills，設定專案。
  當使用者明確說「/zenos-setup」「初次設定 ZenOS」「我還沒設定 MCP token」
  「幫我連接 ZenOS 服務」「更新 ZenOS skills」時使用。
version: 2.1.0
---

# /zenos-setup — ZenOS 初始化與更新

> 這是正式安裝 / 更新流程。
> 首次 bootstrap 由 `setup(platform=...)` 先把 `zenos-setup` 放進來；
> 之後首次完整安裝與所有後續更新，一律走 `/zenos-setup`。

整個過程大約 2 分鐘。

---

## Step 0：先確認安裝目標

先確認這次要裝到哪裡：

| 選項 | 推薦時機 |
|------|---------|
| 當前目錄 | 正在設定某個 repo，想讓治理規則與專案一起版本化 |
| 家目錄 | 想讓多個專案共用同一套 agent / workflow skills |

若使用者沒有特別指定，**預設推薦當前目錄**。

安裝完成後，要用一句話補充這四個 skill 的用法：
- `/zenos-setup`：安裝後首次完整安裝，或之後更新治理 / agent skills
- `/zenos-capture`：第一次把專案或文件寫進 ontology
- `/zenos-sync`：專案已有 ontology 後，跟著 git 變更做日常同步
- `/zenos-governance`：做治理掃描、找缺口、要求 agent 自動修補

---

## Step 1：先判斷平台，再偵測 MCP 設定檔

先判斷當前 agent 平台：

- Claude Code / Claude Desktop 類：讀 `.claude/mcp.json`
- Codex / ChatGPT 類：讀 `.mcp.json`

> 不要把 Claude 路徑套到 Codex。Codex 用 `.mcp.json`。

| 狀態 | 模式 | 下一步 |
|------|------|--------|
| 不存在 | 初次設定 | → Step 2 |
| 存在，有 zenos server | 更新模式 | 從 URL 解析 project（不問 token）→ 跳到 Step 3 |

---

## Step 2：初次設定（僅初次）

問用戶要 API token：

```
請輸入你的 ZenOS API token：
（從 ZenOS 管理員取得）
```

收到 token 後執行：

1. 讀取對應平台的 MCP 設定檔
2. 若檔案不存在，先建立基礎結構：

```json
{
  "mcpServers": {}
}
```

3. 設定或覆蓋 `mcpServers.zenos` 為：

```json
{
  "type": "http",
  "url": "https://zenos-mcp-165893875709.asia-east1.run.app/mcp?api_key=<URL-encoded TOKEN>"
}
```

4. 寫回對應檔案
5. 立刻讀回驗證：
   - `mcpServers.zenos` 存在
   - `url` 含 `api_key=`
   - `url` 不含 `project=`

提示用戶：

```
設定完成！請重啟 Claude Code（Cmd+Shift+P → Reload），重啟後再次執行 /zenos-setup 繼續安裝 skills。
```

**重啟後再次執行 /zenos-setup 時，Step 0 會偵測到 mcp.json 存在，自動進入 Step 2。**

---

## Step 3：取 manifest + 安裝 skills

呼叫：

```python
mcp__zenos__setup(platform="<claude_code|claude_web|codex>", skip_overview=True)
```

先從 `response["data"]` 取 payload，不要讀 top-level：

```python
resp = mcp__zenos__setup(platform="<claude_code|claude_web|codex>", skip_overview=True)
payload = resp["data"]
```

從 `payload["manifest"]["skills"]` 取得 skill 清單。

### 版本比對

讀取 `.claude/zenos-versions.json`（若存在）：

```json
{
  "zenos-setup": "1.0.0",
  "zenos-capture": "2.1.0"
}
```

- 存在 → 只更新版本號有變的 skills
- 不存在 → 全部安裝

### 下載 skills

對每個需要更新的 skill，用 Bash curl 從 GitHub raw URL 下載：

```bash
curl -sL https://raw.githubusercontent.com/centerseed/zenos/main/skills/release/{skill.path}/SKILL.md
```

Codex 角色 skill 例外：
- 若 `skills/release/{role}/SKILL.codex.md` 存在，Codex 安裝時必須下載那個檔案，並寫成目標路徑的 `SKILL.md`
- Claude Code 維持下載 `skills/release/{role}/SKILL.md`

> 不下載 `setup.py`。MCP 設定與後續 project 更新都直接透過讀寫對應平台的 MCP 設定檔完成。

### Governance 檔案

Governance 檔案（`skills/governance/`）每次都重新下載，不比對版本。
Workflow 檔案（`skills/workflows/`）也必須寫到**專案根目錄**，因為 slash command 與治理 skill 會直接讀這些本地檔案。

必須寫入：
- `skills/governance/bootstrap-protocol.md`
- `skills/governance/shared-rules.md`
- `skills/governance/document-governance.md`
- `skills/governance/l2-knowledge-governance.md`
- `skills/governance/task-governance.md`
- `skills/workflows/knowledge-capture.md`
- `skills/workflows/knowledge-sync.md`
- `skills/workflows/setup.md`

驗證方式：
- `skills/governance/bootstrap-protocol.md` 必須存在，否則 `/zenos-capture`、`/zenos-sync` 不可繼續
- `skills/governance/shared-rules.md` 必須存在，否則建票/治理流程不完整

平台 payload key：

- `claude_code` → `payload["payload"]["claude_md_addition"]`
- `claude_web` → `payload["payload"]["project_instructions"]`
- `codex` → `payload["payload"]["agents_md_addition"]`

不要再假設所有平台都有 `claude_md_addition`。

### Addon-aware merge

安裝 role skill 時：

- Claude Code：來源用 `skills/release/{role}/SKILL.md`，目標寫到 `.claude/skills/{role}/SKILL.md`
- Codex：若存在 `skills/release/{role}/SKILL.codex.md`，來源用該檔，目標仍寫到 `.codex/skills/{role}/SKILL.md`

1. 檢查目標檔案是否存在
2. 若存在：找 `<!-- ZENOS_ADDON_SECTION_START -->` 標記
   - 找到 → 保留該標記到檔案結尾的所有內容（addon section）
   - 未找到 → addon section 視為不存在
3. 將新版 SKILL.md 內容 + 保留的 addon section 合併寫入
4. 若目標檔案不存在：寫入新版內容 + 標準 addon loading section：

```markdown
<!-- ZENOS_ADDON_SECTION_START -->
## 專案 Addon Skills

若 `skills/addons/{role}/` 目錄存在，在開始任何任務前，
用 Read tool 讀取該目錄下所有 .md 文件，按各 addon 的 `trigger` 條件套用。

若 `skills/addons/all/` 目錄存在，也讀取其中所有文件。
<!-- ZENOS_ADDON_SECTION_END -->
```

### Slash commands

若使用者選「當前目錄」：
- 將 `payload["payload"]["slash_commands"]` 中每個 key-value 寫入 `.claude/commands/`
- 將 governance / workflow 檔案寫到專案根目錄下的 `skills/`

若使用者選「家目錄」：
- 角色 skills 寫到 `~/.claude/skills/` 或 `~/.codex/skills/`
- 不要假裝這是專案內安裝；回覆時要明說這會影響其他專案

### 寫入版本記錄

安裝完成後，將所有 skill 的 name → version 寫入 `.claude/zenos-versions.json`。

> **自我更新 global skill 不在此流程**——那是 bootstrap 流程的職責，
> 定義在 `skills/release/zenos-setup/SKILL.md`（見 ADR-017 D1）。

---

## Step 4：Agent 安裝 + Project 設定

### 列出可用 projects

```python
mcp__zenos__search(collection="entities", entity_level="L1")
```

| 結果 | 處理 |
|------|------|
| 有結果 | 顯示清單讓用戶選擇 → 讀取對應平台的 MCP 設定檔，保留既有 `api_key`，只更新 `mcpServers.zenos.url` 的 `project` query param，寫回後再讀回驗證 |
| 無結果 | 告知：「目前沒有專案，先跳過。建立第一個專案後再執行 /zenos-setup 設定 project。」 |

### 安裝 agents

執行 release 同步腳本，將 `skills/release/*` 安裝到 `~/.claude/skills/` 與 `~/.codex/skills/`：

```bash
python3 scripts/sync_skills_from_release.py
```

> Agent skills 是 generic 的，不需要注入 project name；workflow skills 也一併由 release 安裝。

---

## Step 5：完成摘要

顯示：

```
ZenOS Setup 完成！

已更新 skills：
- zenos-capture: 2.1.0 → 2.2.0
- zenos-sync: 3.1.0 → 3.2.0
（未變更的不顯示）

Project: {選擇的專案名稱 或 「未設定」}

可用指令：
  /zenos-capture    — 捕獲知識
  /zenos-sync       — 同步變更
  /zenos-governance — 治理掃描
```

完成摘要後，再用白話補一句：
`/zenos-setup` 用來安裝或更新；`/zenos-capture` 用來第一次建庫；`/zenos-sync` 用來日常同步；`/zenos-governance` 用來治理掃描。

---

## 注意事項

- **token 不進 git**：`.claude/mcp.json` / `.mcp.json` 都不應進 git
- **更新模式不問 token**：token 已在 mcp.json 中，只更新 skills 和 project
- **重啟才生效**：MCP 設定變更後需重啟 Claude Code
