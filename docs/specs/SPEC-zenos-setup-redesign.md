---
type: SPEC
id: SPEC-zenos-setup-redesign
status: Draft
ontology_entity: agent-runtime
created: 2026-04-05
updated: 2026-04-23
depends_on: SPEC-agent-setup, SPEC-mcp-tool-contract, SPEC-agent-integration-contract
version_note: v3 — 補入安裝 target 選擇與安裝後使用說明（2026-04-21）
---

# Feature Spec: /zenos-setup Redesign

## 背景與動機

現有的 `/zenos-setup` skill 在一個線性流程裡承擔了四項職責：MCP 連線設定、skill 安裝、agent 安裝、project name 注入。每一項都有獨立的失敗模式，任何一項失敗就中斷整個流程，且失敗後沒有清楚的恢復路徑。

同時，server 端的 `mcp__zenos__setup` MCP tool 也做 skill 安裝，但兩者的「setup」範圍定義不一致，用戶和 agent 需要搞清楚哪個工具做什麼、何時用哪個，這是不必要的認知負擔。

另一個具體問題是 **bootstrap 悖論**：`/zenos-setup` skill 要靠 `zenos-skills setup` 更新，但 `zenos-skills setup` 需要先安裝好才能執行，而 `/zenos-setup` 又是最先被用到的 skill。這意味著 setup skill 自身的版本可能永遠落後。

當前最常見的失敗場景：
- 用戶在沒有 Python 的環境下執行 setup，`setup.py` 失敗，fallback 要用戶手動改 JSON 檔案
- `sed` 注入 `{ZENOS_PROJECT}` 後沒有驗證，template 字串未被替換的情況無法被察覺
- MCP 設定完成後需要重啟 Claude Code，但 skill 安裝步驟（Step 3）在重啟前就執行，重啟後狀態不可預測

## 目標用戶

兩類用戶，同一個入口：

1. **新用戶（第一次設定）**：只有 API token，需要從零完成 MCP 連線設定 + skill 安裝 + agent 安裝
2. **已設定用戶（更新 skill）**：MCP 連線已正常，需要把 skill/agent 更新到最新版本

## 需求

### P0（必須有）

#### 職責切分：MCP 設定 vs Skill 安裝分離

- **描述**：`/zenos-setup` 做 MCP 連線設定，完成後明確告知用戶「重啟 Claude Code，重啟後執行 `/zenos-install` 繼續」。Skill 安裝、agent 安裝、project name 注入移到獨立的 `/zenos-install` skill（或整合進 `mcp__zenos__setup` MCP tool）執行，在 MCP 連線確認正常後才執行
- **Acceptance Criteria**：
  - Given 用戶第一次執行 `/zenos-setup`，When MCP 設定完成，Then `/zenos-setup` 不執行 skill 安裝，而是明確指引用戶下一步
  - Given 用戶已有 MCP 連線，When 執行 `/zenos-setup`，Then skill 偵測到 MCP 已設定，直接跳轉到 skill 安裝流程（而不是重新設定 MCP）
  - Given `/zenos-setup` 和 `mcp__zenos__setup` 兩者，When 用戶需要安裝/更新 skill，Then 應有唯一明確的建議入口，兩者不能給出矛盾的指引

#### MCP 設定：不依賴 Python script

- **描述**：MCP 設定步驟不應依賴外部 Python script 執行，agent 應能直接寫入 `.claude/mcp.json`（或 `~/.claude/mcp.json`），不需要 fallback 手動說明
- **Acceptance Criteria**：
  - Given 用戶貼上 API token，When 執行設定，Then agent 直接生成並寫入正確格式的 mcp.json，不呼叫外部 script
  - Given mcp.json 寫入失敗（權限問題等），When 失敗發生，Then 提供具體的錯誤訊息和精確的修復指令，不是泛用的「手動設定」說明
  - Given 完成寫入，When 驗證步驟，Then agent 讀回 mcp.json 確認內容正確，才算完成

#### Agent 安裝：注入驗證

- **描述**：安裝 agent files 到 `~/.claude/agents/` 時，必須驗證 `{ZENOS_PROJECT}` placeholder 確實被替換
- **Acceptance Criteria**：
  - Given agent files 已寫入，When 驗證，Then agent 讀取每個安裝的 .md 檔案，確認其中不存在字串 `{ZENOS_PROJECT}`
  - Given 驗證發現有未替換的 placeholder，When 失敗，Then 報告哪個檔案的哪個 placeholder 未被替換，並提供修復步驟
  - Given project name 包含特殊字元（空格、slash 等），When 注入，Then 應正確處理，不破壞 markdown 格式

#### Agent 安裝：Project 選擇

- **描述**：安裝 agent 時，呼叫 MCP 列出當前用戶 token 能看到的 L1 entities（products/projects），讓用戶從清單中選擇要注入的 project。若帳號尚無任何 L1 entity，跳過 project 設定，mcp.json 不帶 project param；當用戶建立第一個 L1 entity 後，自動提示更新 project 設定
- **Acceptance Criteria**：
  - Given 用戶執行 agent 安裝，When MCP 回傳至少一個 L1 entity，Then 顯示清單供用戶選擇，選擇結果注入 agent files
  - Given 用戶執行 agent 安裝，When MCP 回傳零個 L1 entity（新帳號），Then 跳過 project 設定，完成安裝，mcp.json 不帶 project param，並告知用戶「建立第一個 project 後可執行 /zenos-setup 更新設定」
  - Given 用戶已完成安裝但 project param 為空，When 用戶建立第一個 L1 entity 後，Then 自動提示用戶重新執行安裝以更新 project 設定

#### Setup Skill 自我更新機制

- **描述**：`/zenos-setup` skill 自身必須能夠更新到最新版，不依賴 `zenos-skills setup`（避免 bootstrap 悖論）
- **Acceptance Criteria**：
  - Given 用戶執行 `/zenos-setup`，When skill 啟動，Then skill 從 manifest SSOT 查詢自身的最新版本，若本機版本落後則提示用戶更新
  - Given manifest 無法存取（網路問題等），When 版本查詢失敗，Then skill 繼續正常執行，不因無法取得版本資訊而中斷
  - Given 用戶確認更新，When 執行更新，Then `/zenos-setup` skill 以 `curl` + 直接寫入方式完成自我更新，不依賴其他工具

### P1（應該有）

#### 清楚的進度回饋

- **描述**：整個 setup 流程分步驟完成時，用戶能看到每一步的完成狀態，不是一個大塊的輸出
- **Acceptance Criteria**：
  - Given 多步驟流程，When 每步完成，Then 輸出獨立的完成確認，格式一致（例如：`[1/4] MCP 設定 — 完成`）
  - Given 某步驟失敗，When 失敗，Then 輸出顯示哪一步失敗，其他已完成的步驟不需要重新執行

#### Cloud 模式 vs 本地開發模式的邊界清晰

- **描述**：兩種模式的設定步驟應明確分開，本地開發模式的設定不應出現在 Cloud 模式的說明中
- **Acceptance Criteria**：
  - Given 用戶選擇 Cloud 模式，When 完成設定，Then 用戶不看到任何與 GCP 或 GitHub token 相關的說明
  - Given 用戶選擇本地開發模式，When 完成設定，Then 用戶不需要輸入 ZenOS API token

#### 多專案支援的明確說明

- **描述**：用戶可能在多個專案下工作，setup 說明中應清楚解釋 project-level mcp.json vs global mcp.json 的差異和使用場景
- **Acceptance Criteria**：
  - Given 用戶詢問「我有兩個專案」，When setup 說明，Then 說明中明確告知每個 Claude Code 專案可以有獨立的 `.claude/mcp.json`
  - Given 用戶選擇全域設定，When 執行，Then mcp.json 寫入 `~/.claude/mcp.json`，並說明這會影響所有 Claude Code 專案

#### 安裝目標選擇：當前目錄 vs 家目錄

- **描述**：MCP 接通後，agent 必須主動詢問使用者要安裝到當前目錄還是家目錄；若使用者未指定，預設推薦當前目錄
- **Acceptance Criteria**：
  - Given agent 呼叫 `setup(platform=...)`，When 準備安裝，Then 回傳內容必須能讓 agent 清楚列出「當前目錄」與「家目錄」兩種 target
  - Given 使用者沒有明確指定，When agent 引導安裝，Then 預設推薦當前目錄，而不是直接做全域安裝
  - Given 使用者選擇家目錄，When 安裝完成，Then agent 必須明確說明這會影響其他專案

#### 安裝完成後的 skill 使用說明

- **描述**：安裝完成後，agent 必須用白話簡單解釋核心 workflow skills 什麼時候用，避免用戶只看到檔案被裝好，不知道接下來怎麼操作
- **Acceptance Criteria**：
  - Given 安裝完成，When agent 回覆完成摘要，Then 至少說明 `/zenos-setup`、`/zenos-capture`、`/zenos-sync`、`/zenos-governance` 的使用時機
  - Given 用戶是首次安裝，When agent 完成回覆，Then 說明中必須指出 `/zenos-setup` 是後續更新的唯一入口

### P2（可以有）

#### 設定狀態快照

- **描述**：setup 完成後，輸出一個可複製的「設定摘要」，記錄安裝了什麼版本的什麼 skill，以便日後排查問題
- **Acceptance Criteria**：
  - Given setup 完成，When 輸出，Then 包含每個已安裝 skill 的名稱和版本號
  - Given 用戶重新執行 setup（更新），When 輸出，Then 顯示哪些 skill 從哪個版本更新到哪個版本，哪些已是最新版未動

## 明確不包含

- MCP server URL 的管理（server 端的部署和維護）
- API token 的申請流程（這是 admin 功能，不在 setup 範圍）
- 非 Claude Code 平台（Web UI、Codex）的安裝流程——這由 `mcp__zenos__setup` MCP tool 負責，不在 `/zenos-setup` skill 範圍
- `zenos-skills` CLI 工具的功能改動

## 技術約束（給 Architect 參考）

- **不依賴 Python**：mcp.json 寫入必須透過 agent 直接操作，不呼叫 `setup.py`
- **不依賴 `zenos-skills` CLI**：setup skill 的自我更新路徑必須只用 `curl` 和 agent 的 Write/Edit 能力
- **MCP tool 和 skill 的職責邊界**：`mcp__zenos__setup` tool 只做 skill 內容分發（輸出 skill 文字讓 agent 安裝），`/zenos-setup` skill 做 MCP 設定和本機檔案寫入。兩者不應重複定義「安裝流程」
- **MCP 設定完成需要重啟**：Claude Code 載入 MCP 設定需要重啟，因此 MCP 設定和 skill 安裝必然是兩個分離的 session，設計上需要接受這個約束
- **Manifest SSOT**：自我更新的版本來源必須是 `skills/release/manifest.json`，URL 為 `https://raw.githubusercontent.com/centerseed/zenos/main/skills/release/manifest.json`
- **本地版本紀錄格式**：版本比對使用 `.claude/zenos-versions.json`，格式為 `{"bundle_version": "...", "skills": {"skill-name": "version", ...}, "last_updated": "YYYY-MM-DD"}`。不解析 skill 檔案的 frontmatter 來判斷版本
- **Governance 檔案不做版本比對**：每次安裝或更新都重新下載 `skills/governance/` 目錄下的所有檔案，不與本地版本比對
- **Skill 安裝範圍固定為 full**：不提供 skill 選擇介面，每次安裝/更新都安裝完整 skill 集合

## 開放問題

- `/zenos-install` 是獨立 skill 還是整合進 `mcp__zenos__setup` MCP tool 的執行邏輯？如果是後者，`/zenos-setup` 需要在完成 MCP 設定後告知用戶「執行 `mcp__zenos__setup`」而非 `/zenos-install`，但這要求用戶在沒有 MCP 連線的狀態下就知道 tool 名稱——需確認 UX 是否合理
- ~~Agent 安裝的「注入 project name」步驟——用戶從哪裡選 project？~~ **已解決**：呼叫 MCP 列出 L1 entities 供用戶選擇；無 L1 entity 時跳過，mcp.json 不帶 project param；建立第一個 L1 entity 後自動提示更新
- ~~Skill 安裝是否要讓用戶選擇安裝哪些 skill？~~ **已解決**：永遠安裝 full，不提供選擇
- ~~版本比對的資料來源——解析 frontmatter 還是另立版本檔？~~ **已解決**：用 `.claude/zenos-versions.json` 存版本紀錄，不解析 frontmatter
- ~~Governance 檔案是否也做版本比對？~~ **已解決**：每次安裝/更新都重新下載，不做版本比對
- 若用戶有多個 ZenOS 專案（不同 org/tenant），agent files 的 project name 是否也需要支援多值？目前每個 agent 檔案只能注入一個 project name
