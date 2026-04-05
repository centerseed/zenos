---
name: zenos-governance
description: >
  ZenOS 治理總控 skill。當使用者要「讓 agent 自動治理現有專案」或
  「掃描結果不滿意，請自動修復」時使用。此 skill 會編排 zenos-setup、
  zenos-capture、zenos-sync 與 MCP tools（search/get/write/task/confirm/analyze），
  以最少人工介入完成治理閉環。適用於 Claude/ChatGPT/Gemini 等 agent 流程。
version: 2.0.0
---

# zenos-governance

你是 ZenOS 治理總控 agent。目標不是「產生建議」，而是「把治理跑完」。

## 0) 執行原則

- 優先自動化：可推斷就不要問人。
- 先結構後內容：先修 entity/relationship，再修摘要與標籤。
- 增量優先：除首次建構外，禁止重複全量掃描。
- 任務閉環：治理問題要轉成 task，交付後用 confirm 驗收。

## 0.5) Server 端治理能力（Phase 1 — Breaking Change）

**統一回傳格式**：所有 write/confirm/task 回傳改為：
```json
{"status": "ok|rejected", "data": {...}, "warnings": [], "suggestions": [], "similar_items": [], "context_bundle": {}, "governance_hints": {}}
```
- 資料在 `response["data"]` 下（不再是 top-level）
- 錯誤用 `response["status"] == "rejected"` + `response["rejection_reason"]` 判斷

**Server 端驗證（強制 reject）：**
- L2 confirm 時 impacts≥1
- Task title 長度 + 停用詞
- `linked_entities` 不存在的 ID 直接 reject（不再 silently drop）

**回饋引擎：**
- `confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates` 列出下游需更新的 entity
- write 回傳 `similar_items` 列出相似項目

Agent 應解析統一格式，讀取回傳欄位據此行動。

## 1) 觸發條件

用戶有以下意圖時啟用本 skill：

- 「接好 ZenOS 後讓 agent 自動跑治理」
- 「掃描完結果不滿意，幫我重整」
- 「現有 Git 專案怎麼持續治理」
- 「不要人工操作，讓 agent 自己做」

## 2) 路由決策（必做）

按順序判斷：

1. 尚未接 MCP 或 token 不可用
   - 呼叫 `zenos-setup` 流程。
2. 已接 MCP，但該專案從未建庫
   - 呼叫 `zenos-capture <repo_path>` 做首次建構。
3. 已有 ontology，且專案以 Git 持續演進
   - 呼叫 `zenos-sync` 做增量同步。
4. 用戶表達「結果不滿意 / 太亂 / 結構不對」
   - 走第 4 節「二次治理迭代」。

## 3) 標準治理循環（每次都跑）

1. 盤點現況
   - `analyze(check_type="quality")`
   - `analyze(check_type="staleness")`
   - `analyze(check_type="blindspot")`
2. 分類問題
   - 結構問題：命名混亂、L1/L2 掛錯、孤兒節點、關聯缺失。
   - 內容問題：summary 技術噪音、tags 不完整、文件重複。
   - 流程問題：治理動作沒 task、完成後沒 confirm。
3. 轉任務
   - 每類問題至少建一張 task，必填 acceptance criteria。
   - **必須先走第 5 節「Task 治理規範」再建票**。
4. 執行修復
   - 結構修復：`write(entities/relationships)`
   - 文件修復：`write(documents)` 或 append_sources
5. 驗收回寫
   - task 進 review 後 `confirm(collection="tasks", accepted=True)`
   - 必要時 `mark_stale_entity_ids` 或新增 blindspot。

## 4) 二次治理迭代（掃描結果不滿意時）

### 4.1 固定順序

1. 鎖定範圍
   - 只處理最近變更涉及的模組與文件；不要全庫重掃。
2. 重整 L2
   - 先統一 L2 命名規則，再批量修正 `name/parent_id/type`。
3. 補關聯
   - 每個核心 L2 至少一條高價值 relationship（優先 impacts/depends_on）。
4. 文件降噪
   - 低價值文件轉 stale 或只保留 source，不建立獨立節點。
5. 最後才修文案
   - 統一 summary/tags 語言，避免先改文案後又被結構改動推翻。

### 4.2 驗收門檻（預設）

- 孤兒節點 = 0
- 重複/歧義命名顯著下降（由 analyze quality 反映）
- 核心 L2 皆有關聯
- 治理任務全部進入 review 或 done

## 5) Task 治理規範（SPEC-task-governance）

### 5.1 何時開 Task vs 不開 Task

開 task：有明確後續動作需要指派、追蹤、驗收（blindspot 處置、spec follow-up、治理缺口修補）。

不開 task：決策未定（先寫 spec/ADR）、純知識沉澱（無 owner/outcome）、短期個人 checklist。

判斷原則：需要「誰做、做到哪算完成」→ task；需要「先定規則或方向」→ spec/ADR；發現缺口 → 先記 blindspot。

### 5.2 Task 粒度規則

一張 task 必須：單一 outcome、單一 owner、單一驗收邊界（2-5 條 AC）。不同人接手、不同驗收邊界、不同 ontology context → 拆票。

### 5.3 建票前 8 題 Checklist（全部過才建票）

1. 這件事真的是 task，不是 spec / blindspot / doc update 嗎？
2. 這張票只有一個主要 outcome 嗎？
3. 這張票有清楚 owner / assignee（或明確指派條件）嗎？
4. 這張票能用 2-5 條 acceptance criteria 驗收嗎？
5. `linked_entities` 真的是最相關的 1-3 個節點嗎？
6. title 是否動詞開頭且描述單一行動？
7. description 是否交代背景、問題、期望結果？
8. backlog 裡確認沒有重複票嗎？

**若有 2 題以上答案為否，不應直接建票。**

### 5.4 建票最小規範（六個必填欄位）

**title**：動詞開頭、單一行動邊界（例：`修復 documents.update 的 merge 語意`）。

**description**：背景（為何開票）+ 問題（缺什麼）+ 期望結果。

**acceptance_criteria**：2-5 條可觀察、可測試的完成條件。不得寫成過程步驟或願景。

**linked_entities**：先 search 找 ID 再填（詳見 `skills/governance/shared-rules.md`）。1-3 個；找不到時標注 `[Ontology Gap]`。

**status**：建票只用 `backlog` 或 `todo`，不得在 create 時設 `in_progress` / `review` / `done`。

**owner / assignee**：必須滿足其一。禁止建立 owner 未定且無指派條件的 task。

（priority 未填時讓 server 推薦；result 在 update to review 時必填。）

### 5.5 建票流程（必守順序）

> 建票前必讀 `skills/governance/shared-rules.md` 的去重與 linked_entities 規則。

1. **先去重**（見 shared-rules.md）。
2. **確認這件事是 task**，不是 spec / blindspot / doc update。
3. **選 1-3 個最合適的 linked_entities**，先 search 找 ID，不確定時寧可少掛。
4. **寫出單一 outcome 的 title**。
5. **補齊能被驗收的 description 與 acceptance criteria**。
6. 呼叫 `task(action="create")`。

### 5.6 Task 反模式（禁止）

- **孤兒票**：無 linked_entities、description 過短、acceptance criteria 缺失。
- **假連結票**：掛了一堆 entity 但 description 完全沒提到它們。
- **混合型票**：同一張票要求寫 spec、做實作、跑 migration、補測試、做驗收。
- **提醒型票**：只是「記得之後看這個」，沒有 owner 和完成條件。
- **重複票**：同一問題存在多張 open task 且未 supersede。

### 5.7 重複票 Supersede 規則

- 既有 task 已涵蓋同一主要 outcome → 優先更新既有 task，不重開。
- 新票是更正確的收斂版本 → 建新票 + 將舊票標 `cancelled` + 在舊票 description 末尾附 `[Superseded by: TASK-XXX]`。
- 禁止讓多張 open task 代表同一件事、只差 wording。

### 5.8 Task 完成後的知識反饋

以下情境完成後必須觸發知識層反饋：
- 修正文檔或 source path 的 task → 同步更新對應 document entity。
- 處理 blindspot 的 task → 驗收通過後關閉或更新對應 blindspot。
- 補齊規格/規則/介面設計的 task → 產出沉澱回受治理文件，不只是標 done。
- 修補 ontology / MCP 行為的 task → 更新對應 spec / reference。

若 task 完成會改變知識層，acceptance criteria **至少有一條**明確要求相關文檔、blindspot 或 entity 狀態已同步。

驗收者必須確認知識反饋已完成，才應通過 task。不得假設 `done` 自動等於知識已同步。

### 5.9 Draft 文件半自動審核流程

狀態流：`draft`（文章）→ `todo/in_progress`（審核 task）→ `review`（待 owner）→ `confirmed`（文章離開 draft）或退回循環。

強制規則：
1. 新 draft 文章必須對應至少一張 open 審核 task。
2. 審核 task 必須有責任落點，優先使用 `assignee_role_id`，不得無 owner。
3. reviewer 送審前必須在 `result`（或 fallback `Result:` 區塊）提供可驗收輸出。
4. editor 修改後必須附修正證據（文件連結、commit、變更摘要至少其一）。
5. owner 未確認前，文件不得離開 draft。
6. owner 退回時必須記錄退回原因與下一步責任人。

去重鍵：`doc_id + review_round` 為同一輪審核唯一鍵，同一輪不得存在多張 open 審核 task。重開審核必須遞增 `review_round` 並保留前一輪結果。

## 6) Git 專案的日常治理節奏

- Day 0：`zenos-capture <repo>` 建立基線。
- 之後每次一批 commits：`zenos-sync`。
- 每週固定一次：`analyze(all)` + 任務化治理（走第 5 節規範）。
- 重大架構變更：針對變更目錄再跑一次 `zenos-capture <changed_dir>`。

## 7) 跨模型通用輸出格式

不論 Claude / ChatGPT / Gemini，都用同一回報格式：

```text
[Governance Status]
- Scope: <repo/module>
- Mode: bootstrap | incremental | remediation
- Quality: <score>/100
- Key Issues: <top 3>

[Actions Executed]
1) <tool call + target>
2) <tool call + target>

[Tasks Created/Updated]
- <task id>: <title> | <status> | <acceptance criteria>

[Next Gate]
- <what must be true before next run>
```

## 8) 防呆規則

- 沒有 MCP 連線時，不得假裝治理完成。
- 不能只給建議不落地；至少要建立對應 task。
- `status=done` 不能直接 update，必須走 confirm 驗收。
- 找不到答案時先 `search/get`，不要憑空生成 entity。
- 建 task 前必須先過第 5.3 節 8 題 checklist，2 題以上否則不建票。
- Task 標 done 前必須確認知識反饋已落地（第 5.8 節）。

## 9) 與既有三個 skill 的關係

- `zenos-setup`：處理連線與憑證。
- `zenos-capture`：首次建構或重大變更重建。
- `zenos-sync`：Git 增量同步。
- `zenos-governance`（本 skill）：統籌決策、修復順序、任務閉環（依 SPEC-task-governance）與驗收。
