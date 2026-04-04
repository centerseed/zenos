---
doc_id: SPEC-batch-doc-governance
title: "功能規格：批次文件治理"
type: SPEC
ontology_entity: L3 文件治理
status: draft
version: "0.2"
date: 2026-04-04
supersedes: SPEC-doc-source-governance
---

# SPEC: 批次文件治理

## 背景與動機

在 ZenOS dogfooding 過程中，大範圍文件重構（如目錄搬移、批次 rename）暴露三個治理效率問題：

1. `write` tool 一次只能更新一個 document 的 source URI，10 個文件搬移需要 10 次 MCP call，對 agent 造成 10 倍 token 消耗與延遲。
2. `/zenos-sync` 偵測到 rename 後，修復流程不是原子操作——agent 仍須逐一呼叫 `write`，偵測與修復之間有多餘往返。
3. `skills/governance/*.md` 與 `governance_guide(topic=...)` 內容高度重疊，CLAUDE.md 維護兩套指引，SSOT 不清晰。

本 Spec 取代 `SPEC-doc-source-governance`，在其 source URI 治理規則基礎上，新增批次操作能力與 SSOT 去重。

## 目標用戶

**主要用戶：AI agent**（Architect、Developer skill 執行中的 Claude instance）
- 場景一：agent 執行大範圍目錄重構，需同步更新多個 document 的 source URI
- 場景二：agent 執行 `/zenos-sync`，偵測到 git rename，需一次確認修復所有 broken URI
- 場景三：agent 執行任意操作前查閱治理規則，應有唯一、明確的查閱路徑

**次要用戶：工程師**（人工操作 MCP tools 或審閱 sync 結果）

## P0 需求

### Feature 1：批次更新 document source URI（新增獨立 tool）

**描述：** 新增 `batch_update_sources` MCP tool，agent 可在單一 MCP call 中更新多個 document 的 source URI。不擴展現有 `write` tool，因為 partial failure 語意與 `write` 的單一成功/失敗語意不同。

**技術約束（Architect 確認）：**
- **獨立 tool**：不擴展 `write`，新增 `batch_update_sources`
- **atomic 參數**：`atomic=true` 時用 PostgreSQL transaction 包住整批（全成功或全失敗）；`atomic=false` 時逐筆獨立（partial failure）
- **批次上限**：單次最多 100 筆，超過 reject
- **冪等性**：若 doc_id 的 URI 已經是 new_uri，視為成功（不報錯）
- **權限**：每筆都走 partner-level scope 檢查

**Acceptance Criteria：**

- Given agent 有 N 個 document 需要更新 source URI（2 <= N <= 100），
  When agent 呼叫 `batch_update_sources(updates=[{doc_id, new_uri}], atomic=false)`，
  Then 所有指定 document 的 source URI 被更新，回傳 `{updated: [...], not_found: [...], errors: [...]}`，整個操作在單次網路往返完成。

- Given `atomic=true` 且批次中有任一筆失敗，
  When agent 發出批次更新請求，
  Then 整批回滾，無任何 document 被修改，回傳失敗原因。

- Given 批次更新中有部分 doc_id 不存在且 `atomic=false`，
  When agent 發出批次更新請求，
  Then 已存在的 doc_id 正常更新，不存在的 doc_id 在 `not_found` 列表中，不阻斷其他更新。

- Given doc_id 的 source URI 已經等於 new_uri，
  When agent 發出批次更新請求，
  Then 該筆視為成功（冪等），列入 `updated`。

### Feature 2：sync 偵測 rename 時回傳 proposed fixes

**描述：** `/zenos-sync` 偵測到 git rename 後，在 sync 結果中附帶 `proposed_fixes`。agent 審閱/修改後，呼叫 Feature 1 的 `batch_update_sources(atomic=true)` 套用修正。不需要新的 confirm 流程。

**技術約束（Architect 確認）：**
- **client-side**：rename 偵測與 proposed_fixes 產出在 sync skill 層完成（讀 git log + 比對 ontology），不需改 server
- **server-side**：套用修正用 Feature 1 的 `batch_update_sources(atomic=true)`
- **不擴展 confirm tool**：現有 confirm 是 entity/task draft 驗收，語意不同

**Acceptance Criteria：**

- Given repo 有 M 個文件發生 git rename，且在 ZenOS 有對應 document，
  When agent 執行 sync，
  Then sync 回應包含 `proposed_fixes`，每個條目含 `doc_id`、`old_uri`、`new_uri`。

- Given agent 收到 `proposed_fixes` 且全部正確，
  When agent 呼叫 `batch_update_sources(updates=proposed_fixes, atomic=true)`，
  Then 所有修正被原子性套用。

- Given agent 收到 `proposed_fixes` 但部分 new_uri 有誤，
  When agent 修改部分條目後呼叫 `batch_update_sources`，
  Then 以 agent 修改後的版本執行。

## P1 需求

### Feature 3：統一治理規則查閱路徑，消除 CLAUDE.md 矛盾指引

**描述：** CLAUDE.md 目前有兩段矛盾的治理指引（一段說呼叫 MCP governance_guide，一段說讀 local file）。統一為 **local 優先**：有 `skills/governance/` 的 agent 讀 local file（由 `/zenos-setup` 從 SSOT pull 更新）；MCP `governance_guide` 保留給無 local skill 的 client（如 ChatGPT、Gemini）。

**Acceptance Criteria：**

- Given CLAUDE.md 的治理指引，
  When agent 需要查閱治理規則，
  Then CLAUDE.md 只有一段指引：「讀 `skills/governance/*.md`」，不再同時指向 MCP `governance_guide`。

- Given 專案沒有 `skills/governance/` 目錄（未執行 `/zenos-setup`），
  When agent 需要查閱治理規則，
  Then CLAUDE.md 指引為「跳過治理流程」（與現有 fallback 行為一致）。

- Given 非 Claude Code 的 MCP client（如 ChatGPT plugin），
  When client 需要查閱治理規則，
  Then MCP `governance_guide` tool 仍可用，不受本變更影響。

## 明確不包含

- 不包含 document 內文（content 欄位）的批次更新，本 Spec 僅針對 source URI
- 不包含跨 collection 的批次操作（如同時更新 documents + entities）
- 不包含 sync 的自動執行（auto-sync on commit hook），confirm 仍由 agent 或人工主動觸發
- 不包含 governance_guide tool 的刪除或內容改寫，只統一 CLAUDE.md 的指引路徑
- 不包含 UI 層（Dashboard）的任何修改

## 開放問題

1. Feature 2 中，若 git rename 偵測結果對應不到任何 ZenOS document（文件從未被 write 過），sync 是否仍列入 `proposed_fixes` 讓 agent 決定是否新建？還是靜默略過？
2. Feature 3：`/zenos-setup` pull skill 的頻率是否足夠讓 local file 保持最新？若 MCP 端規則頻繁更新，需要提醒用戶重跑 setup 嗎？

## Architect 技術確認紀錄

- v0.2（2026-04-04）：Architect 確認可行，要求 4 項修訂已納入：
  1. Feature 1 用新 tool `batch_update_sources`（不擴展 write）
  2. 加 `atomic` 參數解決 F1/F2 原子性語意矛盾
  3. Feature 2 不需新 confirm 流程，直接用 batch tool
  4. 補 batch size 上限 100、冪等性定義、client/server 分工
