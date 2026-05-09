---
type: RUNBOOK
id: wave10-governance-dogfood-findings
status: draft
created: 2026-05-02
author: agent:codex
data_source: repo static audit（skills / specs / MCP runtime / tests）
---

# Wave 10 Governance Dogfooding Findings

這份文件只記錄「已在 repo 內直接驗到」的治理問題。
範圍聚焦在 MCP tool contract、skill 發佈/安裝流程、repo 內治理指令一致性、以及 agent 會讀到但實際無效或有副作用的資料。

---

## F01 — release manifest 與實際 skill frontmatter 大量漂移

**結論**：`skills/release/manifest.json` 不是可信的版本 SSOT，現在已經和多個實際 skill frontmatter 不一致。

### 證據

- manifest 宣告：
  - `zenos-sync` = `3.2.2`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:59)
  - `zenos-governance` = `2.1.2`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:66)
  - `architect` = `0.14.1`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:73)
  - `developer` = `0.5.1`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:87)
  - `pm` = `0.6.1`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:101)
  - `qa` = `0.5.1`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:108)
  - `feature` = `1.1.2`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:122)
  - `debug` = `1.0.1`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:129)
  - `brainstorm` = `1.0.1`，[skills/release/manifest.json](/Users/wubaizong/clients/ZenOS/skills/release/manifest.json:157)
- 實際 frontmatter：
  - `zenos-sync` = `3.2.1`，[skills/release/zenos-sync/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/zenos-sync/SKILL.md:11)
  - `zenos-governance` = `2.1.1`，[skills/release/zenos-governance/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/zenos-governance/SKILL.md:8)
  - `architect` = `0.12.1` / `0.14.0`，[skills/release/architect/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/architect/SKILL.md:7) [skills/release/architect/SKILL.codex.md](/Users/wubaizong/clients/ZenOS/skills/release/architect/SKILL.codex.md:8)
  - `developer` = `0.5.0`，[skills/release/developer/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/developer/SKILL.md:7)
  - `pm` = `0.6.0`，[skills/release/pm/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/pm/SKILL.md:7)
  - `qa` = `0.4.1`，[skills/release/qa/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/qa/SKILL.md:7)
  - `feature` = `1.1.1`，[skills/release/workflows/feature/SKILL.md](/Users/wubaizong/clients/ZenOS/skills/release/workflows/feature/SKILL.md:7)

### 影響

- `setup` / installer / version tracking 會以 manifest 為準，但使用者拿到的實際 skill 內容不是那個版本。
- `SPEC-skill-release-management` 要求 manifest version 與 SKILL frontmatter 一致，現在直接違規，[docs/specs/SPEC-skill-release-management.md](/Users/wubaizong/clients/ZenOS/docs/specs/SPEC-skill-release-management.md:49)
- 任何「只更新過期 skill」的邏輯都會被錯版號污染。

### 建議修法

- 先把 release skill frontmatter 全部補齊到 manifest 一致。
- 再加一條 CI / pytest：逐一比對 `manifest.skills[*].version` 與對應檔案 frontmatter。

---

## F02 — `/zenos-setup` 的「當前目錄安裝」仍會偷偷做全域安裝

**結論**：setup workflow 讓使用者選「當前目錄」或「家目錄」，但 Step 4 無論如何都執行同步腳本，把內容寫進 `~/.claude` 和 `~/.codex`，實際違反使用者選擇。

### 證據

- setup workflow 先要求使用者選安裝目標，[skills/workflows/setup.md](/Users/wubaizong/clients/ZenOS/skills/workflows/setup.md:215)
- 但 Step 4 又直接要求執行 `python3 scripts/sync_skills_from_release.py`，[skills/workflows/setup.md](/Users/wubaizong/clients/ZenOS/skills/workflows/setup.md:245)
- 該腳本 `main()` 固定同步到：
  - `~/.claude/skills`
  - `~/.codex/skills`
  - `~/.claude/agents`
  - `~/.codex/agents`
  [scripts/sync_skills_from_release.py](/Users/wubaizong/clients/ZenOS/scripts/sync_skills_from_release.py:183)

### 影響

- 使用者以為只改專案內設定，實際把全域 agent 行為一起改掉。
- 這會讓 dogfood 結果失真：看起來像是「project-local 安裝成功」，其實是 home-dir skill 在兜底。
- 多專案共用同一台機器時，會造成跨專案污染。

### 建議修法

- `setup.md` 要把「project-local」和「home-dir」拆成不同執行路徑。
- `sync_skills_from_release.py` 不應是 current-directory flow 的必要步驟。

---

## F03 — repo 明說 `skills/agents` deprecated，但同步腳本仍持續發佈 `.agents` 舊路徑

**結論**：治理規則要求以 `skills/release/` 為唯一可發佈來源，但 repo 仍保留並同步 `.agents/skills` / `skills/agents` 舊物件，會讓 agent 有機會讀到錯的角色版本。

### 證據

- README 明寫 `skills/agents/` 已 deprecated，[skills/README.md](/Users/wubaizong/clients/ZenOS/skills/README.md:138)
- 專案 AGENTS 也明確要求角色從 `skills/release/*/SKILL.md` 讀，[AGENTS.md](/Users/wubaizong/clients/ZenOS/AGENTS.md:18)
- 但 repo 內仍存在 `.agents/skills/*` 舊技能檔。
- 同步腳本仍把 `skills/agents/*.md` 與部分 release 平台 skill 一起寫到 `~/.claude/agents` / `~/.codex/agents`，[scripts/sync_skills_from_release.py](/Users/wubaizong/clients/ZenOS/scripts/sync_skills_from_release.py:154)

### 影響

- 同一角色可能同時存在 `release` 版與 legacy `.agents` 版，agent 端載入順序一變就會漂。
- repo 自己違反「不要再新增重複 skills 到專案 `.agents/skills`」這條治理規則。

### 建議修法

- 明確決定 `.agents/skills` 是否完全淘汰。
- 若要淘汰，先停用 `sync_agents_to()` 的 legacy source，再清理 repo 內重複檔。

---

## F04 — `get_skill_files()` 已變成 dead surface，但測試和設計文件還在護這條舊路

**結論**：`setup` payload 已不再回傳 `skill_files`，但 `setup_content.get_skill_files()` 還在讀整包治理文件，測試也花大量篇幅維護這個舊 helper。這是典型「取得的資料沒用」。

### 證據

- `setup` adapter 現在只回傳 `manifest`、`slash_commands`、`claude_md_addition` / `agents_md_addition` 等欄位，沒有 `skill_files`，[src/zenos/interface/setup_adapters.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/setup_adapters.py:245)
- `get_skill_files()` 仍會把 governance / workflow / role skills 全部讀進記憶體，[src/zenos/interface/setup_content.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/setup_content.py:197)
- 測試仍大量驗 `get_skill_files()` 的檔案內容與數量，[tests/interface/test_setup_tool.py](/Users/wubaizong/clients/ZenOS/tests/interface/test_setup_tool.py:173)
- 同一份測試又明確驗證 response 不該再有 `skill_files`，[tests/interface/test_setup_tool.py](/Users/wubaizong/clients/ZenOS/tests/interface/test_setup_tool.py:329)
- 設計文件仍保留 `payload.skill_files` 舊契約，[docs/designs/TD-agent-setup.md](/Users/wubaizong/clients/ZenOS/docs/designs/TD-agent-setup.md:459)

### 影響

- runtime 有死碼，測試卻還在守它，會稀釋真正有價值的 contract coverage。
- 新 agent 或新維護者會被舊設計文件誤導，以為 setup 還回整包 skill 內容。

### 建議修法

- 若 `get_skill_files()` 已不再被任何正式入口使用，應標 deprecated 或刪除。
- 把測試重心移到 manifest / instructions / ssot lists / install target side effects。
- 清掉 `TD-agent-setup` 中仍聲稱 `payload.skill_files` 的段落。

---

## F05 — `search` / `get` 會把 `workspace_context` 重複塞進 `data` 和 top-level

**結論**：read path 已由 `_unified_response()` 在 top-level 注入 `workspace_context`，但 `search` / `get` 又先對 `data` 呼叫 `_inject_workspace_context()`。這會製造一份內層重複欄位，對 caller 沒新資訊，只增加 payload 噪音。

### 證據

- `_unified_response()` 已在 top-level 注入 `workspace_context`，[src/zenos/interface/mcp/_common.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/mcp/_common.py:250)
- `_inject_workspace_context()` 會直接把同名欄位塞進傳入的 `data` object，[src/zenos/interface/mcp/_common.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/mcp/_common.py:293)
- `search` 仍在 `_unified_response(data=...)` 前先呼叫 `_inject_workspace_context(results)`，[src/zenos/interface/mcp/search.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/mcp/search.py:544) [src/zenos/interface/mcp/search.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/mcp/search.py:976)
- `get` 也有同樣 pattern，[src/zenos/interface/mcp/get.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/mcp/get.py:373)

### 影響

- caller 需要處理兩個位置的 `workspace_context`，而其中一份不屬於 canonical envelope。
- payload 變大，對 token-budget 敏感的 agent 沒好處。
- 這屬於「回傳的資料有一部分其實沒用」。

### 建議修法

- read path 統一只保留 top-level `workspace_context`。
- 補測試禁止 `data.workspace_context` 出現。

---

## F06 — `governance_guide()` 回傳的 machine-readable version 已經落後內容版本

**結論**：`governance_guide()` 用硬編碼 `_topic_versions` 回傳版本；至少 `task` 已經落後，目前內容明顯是 v2.2，但 tool 還回 `2.0`。

### 證據

- `governance.py` 硬編碼 `task: "2.0"`，[src/zenos/interface/mcp/governance.py](/Users/wubaizong/clients/ZenOS/src/zenos/interface/mcp/governance.py:71)
- 實際 task governance mirror 標題是 `Task 治理規則 v2.2`，[skills/governance/task-governance.md](/Users/wubaizong/clients/ZenOS/skills/governance/task-governance.md:1)

### 影響

- agent 若依 machine-readable version 做 cache / drift 檢查，會誤判內容版本。
- 這會破壞「MCP guide 是 SSOT，local skill 只是 mirror」的可信度。

### 建議修法

- 不要在 runtime 手寫 `_topic_versions`。
- 改成從 SSOT source 派生，或至少由測試保證與 mirror / governance_rules 同步。

---

## F07 — setup / release 測試目前沒有守住真正會壞的地方

**結論**：目前 setup / release 相關測試大多驗 payload key 是否存在，但沒有擋住 manifest-version drift、current-directory 實際變成 global install、或 duplicated workspace_context 這種真實治理問題。

### 證據

- `test_setup_tool.py` 有很多 helper / key existence 測試，但沒有 manifest 與 frontmatter 一致性測試，也沒有 current-directory side effect 測試，[tests/interface/test_setup_tool.py](/Users/wubaizong/clients/ZenOS/tests/interface/test_setup_tool.py:320)
- `test_skills_installer.py` 驗 installer 行為，但不驗 repo 真實 `manifest.json` 與 `skills/release/**` 是否一致，[tests/application/test_skills_installer.py](/Users/wubaizong/clients/ZenOS/tests/application/test_skills_installer.py:1)

### 影響

- repo 可以在測試全綠的情況下，持續累積 release drift。
- 這些問題只有到 agent 真正 dogfood 時才爆。

### 建議修法

- 新增 repo-level governance audit tests：
  - manifest version ↔ frontmatter consistency
  - `setup.md` current-directory flow 不得要求 home-dir sync
  - `search/get` response 不得把 `workspace_context` 重複塞進 `data`

---

## F08 — 版本追蹤只寫 `.claude/zenos-versions.json`，Codex 沒有自己的 ledger

**結論**：setup / sync 目前把版本記錄硬綁在 `.claude/zenos-versions.json`，這和 Codex 安裝路徑不一致，會讓 Codex 的「只更新過期 skills」缺少可靠依據。

### 證據

- setup workflow 的版本比對讀 `.claude/zenos-versions.json`，[skills/workflows/setup.md](/Users/wubaizong/clients/ZenOS/skills/workflows/setup.md:120)
- setup workflow 的版本記錄也只寫 `.claude/zenos-versions.json`，[skills/workflows/setup.md](/Users/wubaizong/clients/ZenOS/skills/workflows/setup.md:225)
- release sync script 同樣只更新 `.claude/zenos-versions.json`，[scripts/sync_skills_from_release.py](/Users/wubaizong/clients/ZenOS/scripts/sync_skills_from_release.py:171)
- 但 release management spec 的官方入口預設目標是 `~/.codex/skills`，[docs/specs/SPEC-skill-release-management.md](/Users/wubaizong/clients/ZenOS/docs/specs/SPEC-skill-release-management.md:69)

### 影響

- Codex 路徑可能每次都被當成首次安裝，或只能靠本地 `SKILL.md` 自己猜版本。
- `.claude` 與 `.codex` 的安裝狀態會分裂，debug 時很難確認哪一份才是實際生效版本。

### 建議修法

- 把 version ledger 跟安裝 target 綁定。
- 至少分成 `.claude/zenos-versions.json` 與 `.codex/zenos-versions.json` 兩份，或改成直接以 target skill dir 的 frontmatter 為真實來源。

---

## 優先順序建議

1. 先修 `F01 manifest/version drift`
2. 再修 `F02 current-directory install 實際做全域寫入`
3. 然後清 `F03 legacy agents source`、`F04 dead setup surface`、`F08 version ledger split`
4. 最後補 `F05/F06/F07` 的 contract 與測試治理

---

## 本輪未完成項目

- 還沒驗 DB / live MCP 回傳是否真的出現 `data.workspace_context`，目前是從 runtime code path 判定。
- 還沒把以上 findings 轉成正式 task / plan。
- 還沒掃 `docs/specs/` 之外更多歷史設計文件是否還有舊 contract 殘留。
