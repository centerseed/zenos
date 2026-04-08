---
doc_id: SPEC-agent-context-summary
title: 功能規格：Agent Session 啟動 Context 摘要
type: SPEC
ontology_entity: action-layer
status: under_review
version: "0.1"
date: 2026-04-06
supersedes: null
---

# Feature Spec: Agent Session 啟動 Context 摘要

## 背景與動機

ZenOS 的核心命題是「建一次 ontology，每個 AI agent 都共享同一套 context」。然而現況是 agent 每次啟動新對話，都必須依賴用戶手動給背景，或者自行呼叫 `mcp__zenos__search` 探索——這讓「agent 不問背景就做出正確決定」的目標無法自然達成。

成功標準很具體：**agent 開啟新對話，不向用戶詢問任何背景，第一次回應就已掌握企業決策與設計原則**。用戶親眼觀察到 agent 沒有問背景就做對了決定，這就是這個功能要解決的問題。

---

## 目標用戶

**主要用戶：AI agent**

- 場景：agent 開始新對話（session 開始）時，自動取得企業脈絡，不需要用戶或 agent 自行觸發
- 這不是一個「人去查資訊」的功能——而是讓 agent 在開口說話前就已具備必要的公司知識

**次要用戶：人（ZenOS Dashboard 使用者）**

- 場景：人想預覽「ZenOS 會給 agent 什麼 context」，用來驗證 ontology 的品質是否符合預期

---

## 需求

### P0（必須有）

#### 1. Session 啟動時自動注入企業脈絡

- **描述**：agent 啟動新對話時，在第一次回應前自動取得該專案的決策紀錄與設計原則摘要，不需要 agent 手動呼叫 `mcp__zenos__search`，也不需要用戶提供背景說明。
- **Acceptance Criteria**：
  - Given agent 開啟新對話，When 對話開始，Then agent 在第一次回應前已擁有企業決策與設計原則摘要，無需向用戶詢問背景
  - Given 企業 ontology 已有 ADR 與設計原則，When session 啟動，Then agent 取得的摘要包含這些內容而非空白或泛用提示

#### 2. 決策摘要格式標準化

- **描述**：context 摘要有固定的三區塊格式，讓 agent 能一致地解析與使用，且每個區塊數量有上限，避免 context 過長。
- **Acceptance Criteria**：
  - Given context 摘要被生成，Then 格式包含三個明確區塊：[近期決策]、[影響鏈]、[設計原則]
  - Given 每個區塊，Then 每區塊條目數量不超過 5 條
  - Given [近期決策] 區塊，Then 內容來自最近的 ADR 或決策紀錄，不是任意文件
  - Given [影響鏈] 區塊，Then 內容來自相關模組的 impact_chain，顯示「A 改了 → B 要跟著看」的關聯
  - Given [設計原則] 區塊，Then 內容來自企業層級的核心約束，是跨 agent 共識的原則

---

### P1（應該有）

#### 3. Dashboard 可視化摘要預覽

- **描述**：人在 Dashboard 開啟任一模組（節點）時，能看到「ZenOS 會給 agent 什麼 context」的預覽，讓使用者可以驗證 ontology 品質是否達到預期。
- **Acceptance Criteria**：
  - Given 使用者在 Dashboard 點開任一節點，When 查看節點詳情，Then 能看到「Agent Context 預覽」區塊，顯示 agent 啟動時會收到的摘要格式
  - Given Agent Context 預覽，Then 格式與 P0 的三區塊格式一致，不是另一套展示方式

---

## 明確不包含

- 不包含 open tasks 清單（tasks 透過 `mcp__zenos__task` 另行管理）
- 不包含 work journal 原文（journal 詳細內容透過 `mcp__zenos__journal_read` 按需取用）
- 不包含 Slack / GitHub 整合
- 不定義觸發機制的實作方式（CLAUDE.md system prompt injection vs 新 MCP tool，由 Architect 決定）

---

## 技術約束（給 Architect 參考）

- **現有工具可支援資料來源**：`journal_read`（近期決策）、`search` + `get`（影響鏈、設計原則）已可支援，重點是「標準化觸發時機」和「輸出格式」，不是新的資料能力
- **影響 MCP 介面設計**：若以新 MCP tool（如 `mcp__zenos__session_start`）實現，需更新 MCP 介面設計（`GAWPNrvdToJGHTtYC2W2`）；若以 CLAUDE.md system prompt injection 實現，則不影響 MCP 介面
- **影響 Action Layer**：context 摘要組裝邏輯依賴 L2 entity schema（`ZBvuFhT2aUOqGUVIXhya` L2 知識節點治理），schema 若調整，context 組裝需重新驗收
- **Dashboard P1 影響範圍**：節點詳情頁（Dashboard 知識地圖 `jN076EgEmQcUrOLrtAwd`）需新增 Agent Context 預覽區塊

---

## 開放問題

1. **觸發機制選擇**：session 啟動機制透過 CLAUDE.md system prompt injection 還是新的 `mcp__zenos__session_start` MCP tool 實現？這是 Architect 的決策，但選擇會影響 MCP 介面 spec 是否需要更新
2. **摘要範圍**：[近期決策] 的「近期」定義——是最近 N 條，還是最近 N 天？預設值建議為何？
3. **摘要觸發對象**：摘要是針對「整個公司」的全局脈絡，還是針對「特定專案」？agent 是否需要傳入 project context？
