# ZenOS Skills

ZenOS 的治理能力與操作流程。任何 AI agent 都可以讀取這些 skill 來獲得 ZenOS 治理能力。

---

## 快速開始（任何專案、任何 agent 平台）

### Step 1：下載 skills 到你的專案

在專案根目錄執行：

```bash
curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz | \
  tar -xz --strip-components=1 "zenos-main/skills/"
```

完成後你的專案會多一個 `skills/` 目錄。

### Step 2：在專案的 agent 設定中加入載入指示

把以下內容加到你的 agent 設定檔（依平台不同）：

| 平台 | 加在哪裡 |
|------|---------|
| Claude Code | 專案根目錄的 `CLAUDE.md` |
| Codex | `AGENTS.md` 或 agent 的 system prompt |
| ChatGPT Custom GPT | Instructions |
| Gemini | System instruction |
| 自建 agent | System prompt |

**加入的內容：**

```markdown
## ZenOS 治理技能

寫文件前讀：skills/governance/document-governance.md
操作 L2 節點前讀：skills/governance/l2-knowledge-governance.md
建票/管票前讀：skills/governance/task-governance.md
```

### Step 3：設定 ZenOS MCP（若尚未設定）

參考 `skills/workflows/setup.md`，設定 MCP token 讓 agent 能讀寫 ontology。

### 更新 skills

SSOT 有新版時，重跑 Step 1 的 curl 指令即可覆蓋更新。

---

## Skill 索引

### governance/（治理規則）

| 檔案 | 用途 | 載入時機 |
|------|------|---------|
| `document-governance.md` | L3 文件治理合規流程、文件模板、生命週期 | 寫 SPEC / ADR / TD 或任何正式文件前 |
| `l2-knowledge-governance.md` | L2 三問判斷、impacts 撰寫、生命週期 | 建立或審查 L2 知識節點時 |
| `task-governance.md` | Task 建票品質、驗收、知識反饋閉環 | 建票、管票、驗收任務時 |

### workflows/（操作流程）

| 檔案 | 用途 | 載入時機 |
|------|------|---------|
| `knowledge-capture.md` | 從對話/檔案/目錄擷取知識寫入 ontology | 首次建構或捕獲新知識時 |
| `knowledge-sync.md` | 掃描 git log，增量同步 ontology | 專案有新 commit 後 |
| `setup.md` | MCP token 設定 + skill 安裝 | 第一次接上 ZenOS 時 |
| `governance-loop.md` | 全面治理掃描 + 自動修復 | 定期巡檢或品質不佳時 |

---

## 常見組合

| 場景 | 載入哪些 skill |
|------|--------------|
| PM 寫 spec | `document-governance` + `task-governance` |
| Architect 做技術設計 | `document-governance` + `l2-knowledge-governance` + `task-governance` |
| 首次建構 ontology | `knowledge-capture` + `l2-knowledge-governance` + `document-governance` |
| 日常 commit 後同步 | `knowledge-sync` |
| 治理巡邏 | `governance-loop` |

---

## 觸發關鍵字

Agent 遇到這些意圖時，應主動載入對應 skill：

| 關鍵字 / 意圖 | 對應 skill |
|--------------|-----------|
| 「寫 spec」「建文件」「開 ADR」「寫 TD」 | `document-governance` |
| 「這個概念是不是 L2」「三問」「impacts」 | `l2-knowledge-governance` |
| 「開票」「建 task」「驗收」 | `task-governance` |
| 「capture」「建構 ontology」「掃描專案」 | `knowledge-capture` |
| 「sync」「同步」「git 變更」 | `knowledge-sync` |
| 「設定 ZenOS」「接 MCP」 | `setup` |
| 「治理掃描」「品質分數」 | `governance-loop` |

---

## agents/（角色參考設定）

`skills/agents/` 存放角色 skill 的參考版本。這些**不是 SSOT**——SSOT 是你家目錄 `~/.claude/skills/` 的實際檔案。此處僅供備查和新機器初始化參考。

| 檔案 | 角色 | 治理載入 |
|------|------|---------|
| `architect.md` | 技術架構 + subagent 調度 | document + task + l2 |
| `pm.md` | 需求定義 + Feature Spec | document + task |
| `developer.md` | 實作 + 測試 | task |
| `qa.md` | 驗收 + QA Verdict | task |
| `designer.md` | UI/UX 設計 | document（寫正式設計文件時） |
| `marketing.md` | 行銷內容 | document（寫正式行銷文件時） |

---

## 讓你的 Agent 遵守 ZenOS 治理

### 原理

ZenOS 治理不綁定角色——**治理是能力，不是身份**。任何 agent 只要能讀到 `skills/governance/` 的檔案，就能遵守治理規則。

啟用治理有三層機制，越多層越強：

| 層級 | 機制 | 覆蓋範圍 | 設定方式 |
|------|------|---------|---------|
| ① 角色 skill | 角色 SKILL.md 開頭的「ZenOS 治理」表 | 該角色啟動時 | 在家目錄 `~/.claude/skills/` 的角色 SKILL.md 加入治理表（見 `agents/` 參考） |
| ② 專案 prompt | CLAUDE.md / AGENTS.md / system prompt | 所有對話，不限角色 | 在專案設定加入載入指示（見下方） |
| ③ 治理 skill 本身 | `skills/governance/*.md` 開頭的「適用場景」 | agent 讀到 skill 時 | 由 `/zenos-setup` 自動安裝 |

**建議至少啟用①+②**。只有②也能運作，但角色 skill 提供更精準的觸發時機。

### 對 Claude Code 用戶的完整設定步驟

```
1. 執行 /zenos-setup
   → MCP 連線（或跳過已通）
   → 拉最新 skills/
   → 生成 .claude/skills/ 薄殼
   → 加入 CLAUDE.md 載入指示

2. 確認家目錄角色有治理表
   → 檢查 ~/.claude/skills/architect/SKILL.md 開頭有 「ZenOS 治理」段落
   → 沒有就參考 skills/agents/architect.md 補上

3. 完成。之後更新只需重跑 /zenos-setup
```

### 對其他平台（Codex / ChatGPT / Gemini / 自建 agent）

```
1. 拉 skills：
   curl -sL https://github.com/centerseed/zenos/archive/refs/heads/main.tar.gz | \
     tar -xz --strip-components=1 "zenos-main/skills/"

2. 在 agent 的 system prompt / Instructions 加入：

   ## ZenOS 治理技能
   寫文件前讀：skills/governance/document-governance.md
   操作 L2 節點前讀：skills/governance/l2-knowledge-governance.md
   建票/管票前讀：skills/governance/task-governance.md

3. 設定 MCP（若需要連 ontology）：見 skills/workflows/setup.md
```

### 條件式啟動

角色 skill 中的治理表使用**條件式**設計：

```
若當前專案有 skills/governance/ 目錄 → 載入治理規則
若沒有 → 跳過，正常工作
```

這表示同一個角色 skill 可以用在「有 ZenOS」和「沒有 ZenOS」的專案，不會因為找不到治理檔案而報錯。

---

## Skill vs Spec

| | Spec（`docs/specs/`） | Skill（`skills/`） |
|---|---|---|
| **回答** | 應該做什麼、為什麼 | 怎麼做、步驟是什麼 |
| **讀者** | PM、Architect、人類審查者 | Agent（任何 LLM） |
| **衝突時** | 以 Spec 為準 | Skill 是 Spec 的操作翻譯 |

---

## 新增 skill 規範

1. 放在 `governance/`（治理規則）或 `workflows/`（操作流程）
2. 必須有 frontmatter：`type: SKILL`、`id`、`status`、`ontology_entity`、`created`、`updated`
3. 開頭標明「權威來源」指向對應的 Spec
4. 具備「適用場景」段落，讓 agent 知道何時該載入
5. 功能與現有 skill 重疊時，修改現有 skill，不另開新 skill
