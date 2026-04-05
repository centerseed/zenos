---
name: zenos-setup
description: >
  ZenOS 初始化與更新設定——偵測 MCP 連線狀態，安裝/更新 skills，設定專案。
  當使用者明確說「/zenos-setup」「初次設定 ZenOS」「我還沒設定 MCP token」
  「幫我連接 ZenOS 服務」「更新 ZenOS skills」時使用。
version: 2.0.0
---

# /zenos-setup — ZenOS 初始化與更新

整個過程大約 2 分鐘。

---

## Step 0：自我更新 global skill

**每次執行都先更新自己**，確保下次執行永遠是最新版本：

```bash
mkdir -p ~/.claude/skills/zenos-setup
curl -sL https://raw.githubusercontent.com/centerseed/zenos/main/skills/release/zenos-setup/SKILL.md \
  > ~/.claude/skills/zenos-setup/SKILL.md
```

> 這一步不影響當前執行（skill 已載入記憶體），但確保其他專案下次執行時拿到最新版。

---

## Step 1：偵測 mcp.json（決定模式）

讀取 `.claude/mcp.json`：

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

```bash
python .claude/skills/zenos-setup/scripts/setup.py --token TOKEN
```

> 不帶 `--project`，先完成連線。

提示用戶：

```
設定完成！請重啟 Claude Code（Cmd+Shift+P → Reload），重啟後再次執行 /zenos-setup 繼續安裝 skills。
```

**重啟後再次執行 /zenos-setup 時，Step 1 會偵測到 mcp.json 存在，自動進入 Step 3。**

---

## Step 3：取 manifest + 安裝 skills

呼叫：

```python
mcp__zenos__setup(platform="claude_code", skip_overview=True)
```

從回傳的 `manifest.skills` 取得 skill 清單。

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

`zenos-setup` 額外下載 setup.py（安裝後才能執行 --update --project）：

```bash
mkdir -p .claude/skills/zenos-setup/scripts
curl -sL https://raw.githubusercontent.com/centerseed/zenos/main/skills/release/zenos-setup/scripts/setup.py \
  > .claude/skills/zenos-setup/scripts/setup.py
```

### Governance 檔案

Governance 檔案（`skills/governance/`）每次都重新下載，不比對版本。
從 response 的 `payload.claude_md_addition` 取得 CLAUDE.md 應加入的治理段落。

### Addon-aware merge

安裝 skill 到 `.claude/skills/{role}/SKILL.md` 時：

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

將 response 的 `payload.slash_commands` 中每個 key-value 寫入 `.claude/commands/` 目錄。
只寫 project-level（`.claude/commands/`），絕對不寫 `~/.claude/commands/`。

### 自我更新 global skill

安裝完成後，將最新版 `zenos-setup/SKILL.md` 複製到 global：

```bash
cp .claude/skills/zenos-setup/SKILL.md ~/.claude/skills/zenos-setup/SKILL.md
```

確保下次從任何專案執行 `/zenos-setup` 都使用最新版本。

### 寫入版本記錄

安裝完成後，將所有 skill 的 name → version 寫入 `.claude/zenos-versions.json`。

---

## Step 4：Agent 安裝 + Project 設定

### 列出可用 projects

```python
mcp__zenos__search(collection="entities", entity_level="L1")
```

| 結果 | 處理 |
|------|------|
| 有結果 | 顯示清單讓用戶選擇 → 執行 `python .claude/skills/zenos-setup/scripts/setup.py --update --project 選擇的名稱` |
| 無結果 | 告知：「目前沒有專案，先跳過。建立第一個專案後再執行 /zenos-setup 設定 project。」 |

### 安裝 agents

將 `skills/agents/*.md` 複製到 `~/.claude/agents/`（generic，不注入 project name）：

```bash
mkdir -p ~/.claude/agents
cp skills/agents/*.md ~/.claude/agents/
```

> Agents 是 generic 的，不需要注入 project name。

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

---

## 注意事項

- **token 不進 git**：`.claude/mcp.json` 應在 `.gitignore` 中
- **更新模式不問 token**：token 已在 mcp.json 中，只更新 skills 和 project
- **重啟才生效**：MCP 設定變更後需重啟 Claude Code
