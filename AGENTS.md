# ZenOS Agent Instructions

## ZenOS 治理技能

寫文件前讀：skills/governance/document-governance.md  
操作 L2 節點前讀：skills/governance/l2-knowledge-governance.md  
建票/管票前讀：skills/governance/task-governance.md

## ZenOS Workflow 技能（依意圖載入）

設定 ZenOS / 接 MCP / 初始化前讀：skills/workflows/setup.md  
capture / 建構 ontology / 掃描專案前讀：skills/workflows/knowledge-capture.md  
sync / 同步 / git 變更前讀：skills/workflows/knowledge-sync.md  
治理掃描 / 品質修復前讀：skills/workflows/governance-loop.md

## Antigravity 角色切換機制

當使用者指定以下角色或使用相關 Slash Command 意圖時，請強制第一時間閱讀並嚴格遵守該角色設定檔的所有紅線（Red Lines）與工作流程：
- /architect（或說「扮演/你是 Architect/架構師」）→ 讀：skills/release/architect/SKILL.md
- /pm（或說「扮演/你是 PM/產品經理」）→ 讀：skills/release/pm/SKILL.md
- /developer（或說「扮演/你是 Developer/工程師」）→ 讀：skills/release/developer/SKILL.md
- /qa（或說「扮演/你是 QA/測試」）→ 讀：skills/release/qa/SKILL.md
- /designer（或說「扮演/你是 Designer/設計師」）→ 讀：skills/release/designer/SKILL.md
- /marketing（或說「扮演/你是 Marketing/行銷」）→ 讀：skills/release/marketing/SKILL.md
- /debugger（或說「扮演/你是 Debugger/除錯者」）→ 讀：skills/release/debugger/SKILL.md
- /challenger（或說「扮演/你是 Challenger/挑戰者」）→ 讀：skills/release/challenger/SKILL.md

## Deployment Red Lines

- 禁止手動部署 `firebase deploy`、`npx firebase-tools deploy`、或任何直接指定 Hosting project 的 deploy 指令。
- 部署 ZenOS Dashboard 時，只能走 `scripts/deploy.sh`；不得繞過腳本。
- `scripts/deploy.sh` 失敗時，禁止補做手動 deploy；必須先修腳本或修 build/deploy 問題。
- Dashboard 的 Done Criteria 不接受「本地 build 過」；必須以正式站驗收。
- 正式站驗收至少包含：`/`、`/tasks`、`/knowledge-map`、目標功能頁（例如 `/marketing`）。
- 若部署後正式站任一路徑異常，先查 script / hosting / static export / rewrite；不要用 preview route 或繞過 auth 當 hotfix 結案。
