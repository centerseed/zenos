---
type: SPEC
id: SPEC-entry-consolidation-skill
status: Draft
ontology_entity: TBD
created: 2026-03-29
updated: 2026-03-29
---

# Feature Spec: Entry Consolidation Skill

## 背景與動機

Server 端的 `analyze` tool 在偵測到某個 entity 的 active entries >= 20 時，會產出一份 consolidation proposal（由 LLM 分析哪些 entries 可合併）。但目前沒有任何 skill 定義「如何引導 agent 走完確認→執行」這段流程。

結果是：
- `write(collection="entries")` 在第 20 條被擋住時，agent 不知道下一步
- `analyze` 產出的 proposal 沒有標準執行路徑
- 每個 agent 各自解讀、各自執行，容易出錯（例如先 archive 再 write，若 write 失敗則知識消失）

本 spec 定義 **client agent 執行 entry 壓縮的標準 workflow**，包含：呈現 proposal、人工確認、執行順序、驗證結果。

## 目標用戶

任何 ZenOS client agent（zenos-capture、zenos-governance、Architect agent 等），在遇到 entry 飽和時使用。

## 需求

### P0（必須有）

#### 1. 從 analyze 讀取 proposal

- **描述**：skill 從 `analyze` 回傳的 `quality.entry_saturation` 陣列中讀取 consolidation proposal，每個 proposal 對應一個飽和的 entity。
- **Acceptance Criteria**：
  - Given `analyze` 回傳 `entry_saturation` 非空陣列，skill 能正確解析每個 proposal 的 `entity_id`、`entity_name`、`active_count`、`consolidation_proposal`
  - Given `entry_saturation` 為空，skill 告知用戶無需壓縮並結束

#### 2. 以可讀格式呈現 proposal 給用戶

- **描述**：skill 把每個 entity 的合併計畫整理成人類可讀的格式，讓用戶能判斷是否同意合併。
- **呈現格式**：
  ```
  ── Entry 壓縮提案：{entity_name}（{active_count} 條 active）──────

  合併計畫 1：
    合併以下 {n} 條 → 新 entry（{type}）
    舊 entries：
      - [{id}] {content}
      - [{id}] {content}
    合併後：{merged_content}
    （context：{context}）

  保留不動：
    - [{id}] {content}
  ...

  確認執行？ (y/n)
  ```
- **Acceptance Criteria**：
  - Given proposal 包含 3 組合併計畫 + 2 條保留，呈現時清楚區分「要合併的」和「要保留的」
  - 每條 entry 顯示 id + content，讓用戶能辨識

#### 3. 人工確認後才執行（硬規則）

- **描述**：必須取得用戶明確確認，才能執行任何 write 操作。不得自動執行。
- **Acceptance Criteria**：
  - Given 用戶回答 n 或未回應，skill 中止並記錄「用戶未確認，本次壓縮跳過」
  - Given 用戶回答 y，才進入執行階段
  - 不存在「靜默執行」路徑

#### 4. 執行順序：先寫新 entry，再 archive 舊 entries

- **描述**：每組合併計畫的執行順序固定：先建新 merged entry，成功後才 archive 舊 entries。若新 entry 建立失敗，跳過本組、不 archive 舊 entries。
- **設計理由**：若先 archive 再 write 且 write 失敗，舊 entries 消失但新 entry 不存在，造成不可逆的知識損失。
- **Acceptance Criteria**：
  - Given 新 entry write 成功，執行舊 entries 的 archive（`status="archived"`, `archive_reason="merged"`）
  - Given 新 entry write 失敗，本組所有舊 entries 保持 active，並回報錯誤
  - Given archive 過程中某條失敗，記錄失敗的 entry id，繼續處理其他條，最後彙報未完成項

#### 5. 執行後驗證 active count < 20

- **描述**：全部合併計畫執行完後，對每個 entity 呼叫 `get` 確認 `active_entries` 數量 < 20。
- **Acceptance Criteria**：
  - Given 所有計畫執行完，`active_entries` < 20，回報「壓縮完成，active entries: {n}」
  - Given 執行後仍 >= 20（部分失敗），回報「壓縮未完全，仍有 {n} 條 active，請人工處理以下未完成項」

### P1（應該有）

#### 6. 單 entity 模式：只對指定 entity 壓縮

- **描述**：skill 可接受 `entity_id` 或 `entity_name` 參數，只對該 entity 執行壓縮，不跑全域 analyze。適用於用戶點名某個 entity 已快飽和的情境。
- **Acceptance Criteria**：
  - Given skill 收到 entity 參數，直接用 `get` 取 active entries，跳過 analyze，自行送 LLM 產出 proposal
  - Given 指定 entity 的 active count < 15，回報「目前 {n} 條，尚未飽和，不需壓縮」

#### 7. 執行摘要

- **描述**：壓縮執行完後，輸出一份摘要，讓用戶知道本次做了什麼。
- **格式**：
  ```
  ── 壓縮完成 ────────────────────────────────
  Entity: {entity_name}
  合併前 active: {before_count} 條
  合併後 active: {after_count} 條
  新建 entry: {n} 條
  Archived: {n} 條（reason: merged）
  未完成: {n} 條（見下方）
  ```

### P2（可以有）

#### 8. 用戶可修改 merged_content 再確認

- **描述**：在確認步驟前，允許用戶直接編輯 proposal 裡的 `merged_content` 和 `context`。
- **Acceptance Criteria**：
  - Given 用戶輸入修改後的內容，使用修改後版本執行 write

## 明確不包含

- **自動執行**：不得在無人確認的情況下執行任何 archive 或 write
- **刪除 entries**：只能 archive，不可實際刪除（不丟失原則）
- **修改 active entries 的 content**：本 skill 只做 create（新 merged entry）+ archive（舊 entries），不做 update content
- **觸發 L2 拆分**：若 analyze proposal 建議拆分 L2（而非合併 entries），不在本 skill 範圍，需走 L2 治理流程

## 技術約束（給 Architect 參考）

- **MCP 呼叫序列**（執行每組合併時）：
  1. `write(collection="entries", data={entity_id, type, content, context, author="consolidation-skill"})` → 取得新 entry id
  2. 對每條舊 entry：`write(collection="entries", id=<old_id>, data={status="archived", archive_reason="merged"})`
  3. `get(name=<entity_name>)` 驗證 `active_entries` 數量
- **proposal 來源**：`analyze(check_type="quality")` 回傳的 `quality.entry_saturation[*].consolidation_proposal`
- **LLM 依賴**：P1 單 entity 模式需要自行呼叫 LLM 產出 proposal，應複用 `governance_ai.consolidate_entries` 的 prompt 格式

## 開放問題

- P1 單 entity 模式中，skill 端自行呼叫 LLM 的方式：是呼叫 `analyze(check_type="quality", entity_id=<id>)` 讓 server 做，還是 skill 自己組 prompt？建議優先讓 server 端提供接口，保持智慧邏輯中心化。

## 相關文件

- `docs/decisions/ADR-010-entity-entries.md`（Entry 資料結構與治理規則）
- `docs/specs/SPEC-l2-entity-redefinition.md`（Entry 治理規則）
- `docs/specs/SPEC-governance-feedback-loop.md`（治理品質回饋迴路）
- `docs/specs/SPEC-governance-framework.md`（治理功能索引）
