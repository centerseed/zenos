---
type: SPEC
id: SPEC-agent-setup
status: Draft
ontology_entity: agent-runtime
created: 2026-03-29
updated: 2026-04-23
depends_on: SPEC-mcp-tool-contract, SPEC-agent-integration-contract
---

# Feature Spec: Agent 自助安裝

## 背景與動機

現在用戶（內部同事或外部夥伴）要開始用 ZenOS 治理模式，需要手動完成三個步驟：設定 MCP 連線、從 git 抓 skill 並設定、設定 GitHub 存取。這個流程需要人工協助，無法自助完成。

目標：用戶只要完成 MCP 連線（取得 API key），就能呼叫一個 MCP tool，自助完成剩下的安裝流程，讓 agent 具備 ZenOS 治理能力並能存取資料。安裝完成後，同一個 tool 也可以用來更新 skill 到最新版。

## 目標用戶

兩類用戶，同一個 tool：

1. **內部同事**：公司內部新成員，MCP 連線後第一次設定，或想更新 skill
2. **外部夥伴**（Partner key 持有者）：自助接上 ZenOS，不需人工協助

使用場景：用戶在自己的 AI agent 環境中呼叫 `setup` tool，tool 詢問使用哪個平台，依平台輸出對應的安裝步驟或檔案內容，用戶跟著做完即可開始使用。

## 需求

### P0（必須有）

#### 平台偵測與引導
- **描述**：呼叫 tool 時，tool 先詢問用戶使用哪個 AI agent 平台（Claude Code、Claude Web UI、OpenAI Codex、其他），再執行對應流程
- **Acceptance Criteria**：
  - Given 用戶呼叫 `setup` tool，When tool 執行，Then tool 提問平台選擇，不直接假設
  - Given 用戶回答不在清單內的平台，When tool 收到，Then 回傳「目前不支援，請聯繫管理員」

#### Claude Code 安裝流程
- **描述**：輸出 skill 檔案內容 + settings.json 設定，讓 agent 可以直接寫入用戶本機
- **Acceptance Criteria**：
  - Given 用戶選擇 Claude Code，When tool 執行，Then 回傳最新版 skill 檔案內容與 `~/.claude/` 目錄結構指引
  - Given 用戶已安裝過，When 重新執行，Then 回傳完整覆蓋內容，讓 skill 更新到最新版

#### Claude Web UI 安裝流程
- **描述**：輸出對應的 Project Instructions 或 Custom Instructions 文字，讓用戶貼入
- **Acceptance Criteria**：
  - Given 用戶選擇 Claude Web UI，When tool 執行，Then 回傳可直接貼入的指令文字，附帶操作說明

#### OpenAI Codex 安裝流程
- **描述**：輸出對應的 system prompt 或 instructions 文字
- **Acceptance Criteria**：
  - Given 用戶選擇 OpenAI Codex，When tool 執行，Then 回傳可直接使用的 system prompt，附帶設定位置說明

#### 更新 skill
- **描述**：已安裝的用戶重新執行同一個 tool，可取得最新版 skill 內容
- **Acceptance Criteria**：
  - Given 用戶已完成安裝，When 再次呼叫 tool，Then 回傳當前最新版內容，用戶可判斷是否需要覆蓋更新

### P1（應該有）

#### 安裝後驗證提示
- **描述**：安裝步驟完成後，告訴用戶如何確認安裝成功（例如呼叫某個 tool 測試連線）
- **Acceptance Criteria**：
  - Given 安裝流程結束，When tool 回傳，Then 包含一個驗證指令，用戶執行後可確認是否設定正確

#### 治理概要說明
- **描述**：安裝流程中（或完成後），向用戶說明 ZenOS 治理模式的核心概念：ontology 是什麼、skill 的作用、agent 如何與 ZenOS 協作
- **Acceptance Criteria**：
  - Given 安裝流程任一階段，When tool 執行，Then 包含一段簡短的治理概要（不超過一個閱讀段落），讓用戶知道「裝好之後能做什麼」
  - Given 用戶已熟悉 ZenOS，When 執行更新，Then 可跳過說明直接取得更新內容（提供 skip 選項）

### P2（可以有）

#### 版本標記
- **描述**：回傳的 skill 內容附帶語意版本號（semantic versioning），讓用戶知道目前安裝的是哪個版本，版本號由 ZenOS 統一維護

## 明確不包含

- MCP 連線本身的設定（取得 API key、填入 MCP server URL）——這是安裝的前置條件，不在此 tool 範圍內
- 用戶的 AI agent 環境安裝（例如安裝 Claude Code CLI 本身）
- 自動寫入用戶本機檔案（tool 只輸出內容與指引，實際寫入由 agent 或用戶操作）
- 多租戶權限管理（誰可以安裝、誰不行）

## 技術約束（給 Architect 參考）

- Skill 內容的 SSOT 必須在 ZenOS repo 中維護（`skills/` 目錄），tool 從 server 端取得最新版並回傳，不能 hardcode 在 tool 邏輯裡
- Tool 必須透過現有 MCP 連線呼叫，不需額外認證

## 開放問題

- 各平台的 skill 格式差異有多大？Claude Code 是 markdown 檔案，Web UI 是 prompt 文字——是否同一份 skill 能跨平台複用，還是需要各自維護版本？
