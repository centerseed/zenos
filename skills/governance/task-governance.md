---
type: SKILL
id: task-governance
status: Draft
ontology_entity: task-governance
created: 2026-03-27
updated: 2026-03-27
---

# task-governance：Task 治理操作規範

任何 agent 使用 ZenOS task 工具建票、更新票、驗收票時的強制操作規範——把治理規則轉換成每一步可執行的動作。

---

## 適用場景

在以下情況，agent 必須載入本 skill 並照流程執行：

- 建立任何新的 ZenOS task
- 更新 task 狀態（特別是推進到 `review` 或 `done`）
- 驗收他人或 agent 產出的 task
- 判斷某件事是否應該開成 task

**不適用場景**：agent 內部私有 subtask、個人 TODO 清單、不需要跨人協作或驗收的短期備忘。

---

## 權威來源

本 skill 的所有規則均源自：`docs/specs/SPEC-task-governance.md`

發現本 skill 與 SPEC 有衝突時，SPEC 為準，並應在 Completion Report 或當次任務紀錄中標記差異。

---

## 建票前 8 題 Checklist

建立任何 task 前，逐題確認。**有 2 題以上答案為否 → 先處理缺口，不建票**：

1. 這件事真的是 task，不是 spec / blindspot / doc update 嗎？
2. 這張票只有一個主要 outcome 嗎？
3. 這張票有清楚 owner / assignee（或明確指派條件）嗎？
4. 這張票能用 2-5 條 acceptance criteria 驗收嗎？
5. `linked_entities` 真的是最相關的 1-3 個節點嗎？
6. title 是否動詞開頭且描述單一行動？
7. description 是否交代背景、問題、期望結果？
8. backlog 裡確認沒有重複票嗎？

---

## 建票流程（順序是死的）

```
1. search 去重
   search(collection="tasks", status="backlog,todo,in_progress,review,blocked")
   排除 cancelled / done；至少比對 title 關鍵字、核心問題詞、linked_entities

2. 確認是 task，不是 spec / blindspot / doc update
   - 問題還在「要不要這樣做」→ 先寫 spec / ADR
   - 尚無明確 owner / 執行方案 → 先記 blindspot
   - 本質只是知識沉澱 → document update，不開票

3. 選 1-3 個最合適的 linked_entities
   先少掛，不要亂掛；找不到對應節點時標注 [Ontology Gap: ...]

4. 寫出單一 outcome 的 title（動詞開頭）

5. 補齊 description（背景 / 問題 / 期望結果）
   與 acceptance_criteria（2-5 條可觀察條件）

6. 呼叫 task(action="create")
```

心法：先去重 → 再定類型 → 再選 context → 最後才建票。

---

## 建票最小欄位規範

| 欄位 | 要求 |
|------|------|
| `title` | 動詞開頭，單一行動邊界，不寫成抽象主題或會議紀錄 |
| `description` | 含背景、問題、期望結果（三件事缺一不可），不與 AC 重複 |
| `acceptance_criteria` | 2-5 條可觀察、可驗收的外顯結果；不寫過程性步驟或 roadmap 願景 |
| `linked_entities` | 1-3 個，掛最直接受影響節點；找不到時標注 `[Ontology Gap: ...]`，不亂掛湊數 |
| `priority` | 不傳則由 server 推薦；有明確商業理由（時程不可延誤 / 外部依賴）才覆蓋 |
| `status` | 建票只用 `backlog` 或 `todo`；不得在 create 時假設 `in_progress` / `review` / `done` |
| `assignee` | 直接填入，或在 description 明確記錄預期 owner + 指派條件；禁止 owner 未定且無指派條件 |
| `result` | 進入 `review` 前必須填寫，或在 description 末尾追加 `Result:` 區塊並附關聯文件或變更連結 |

---

## linked_entities 掛法原則

### 類型 A：單點實作修補

主要驗收在「程式或資料行為修補」。

- 掛直接受影響模組
- 如有必要，再加一個直接相關的治理或介面節點
- 不要為了「看起來完整」而附帶產品根節點

範例：修 MCP task update bug
- `MCP 介面設計`
- `Action Layer`（直接受影響模組）

### 類型 B：治理規則或治理流程

主要驗收在「治理規則、流程、文件契約變更」。

- 掛產品根節點
- 掛對應治理模組
- 如涉及接口，再加 MCP 模組

範例：規範文件治理 sync
- `ZenOS`
- `文件治理`
- `MCP 介面設計`

### 類型 C：跨層架構設計

- 掛上位產品 / 系統
- 掛最直接的 app layer / module
- 掛一個主要被 impacts 的治理或介面節點
- 不要同時塞一整串平級模組

範例：設計 L2 語意推導 → Task 優先度推薦演算法
- `ZenOS`（上位產品）
- `Action Layer`（最直接受影響的 module）
- `語意治理`（主要被 impacts 的治理節點）

### 邊界判斷

- 主要驗收在「程式/資料行為修補」→ Type A
- 主要驗收在「治理規則/文件契約變更」→ Type B
- 若同時成立且難以單票驗收 → 必須拆成兩張票

---

## 生命週期操作

### 狀態一覽

| 狀態 | 意義 | 可作為初始狀態 |
|------|------|---------------|
| `backlog` | 已識別但尚未排入執行 | 是 |
| `todo` | 已排入執行，等待認領 | 是 |
| `in_progress` | 有人正在執行 | 否 |
| `review` | 執行完成，等待驗收 | 否 |
| `blocked` | 執行受阻，等待外部條件 | 否 |
| `done` | 驗收通過，工作完成 | 否 |
| `cancelled` | 不再需要執行 | 否 |
| `archived` | 歷史保留，不再活躍 | 否 |

### 合法轉換與治理條件

```
                  認領 / 指派
backlog → todo ──────────────→ in_progress
  │                                │
  │  不再需要                       ├─→ blocked（外部依賴未滿足）
  ↓                                │      │
cancelled                          │      └─→ in_progress（依賴解除）
                                   ↓
                                 review
                                   │
                        ┌──────────┼──────────┐
                        ↓          ↓          ↓
                      done    in_progress  cancelled
                        │    （退回修正）
                        ↓
                     archived
```

| 轉換 | 治理條件 |
|------|---------|
| `backlog → todo` | 去重規則通過，確認不是重複票 |
| `todo → in_progress` | 有明確 assignee |
| `in_progress → review` | `result` 或 `Result:` 區塊已填寫完成輸出 |
| `in_progress → blocked` | description 或 comment 記錄阻塞原因與等待條件 |
| `blocked → in_progress` | 阻塞條件已解除，有紀錄 |
| `review → done` | AC 逐條驗收通過 + 知識反饋已完成（若適用） |
| `review → in_progress` | 驗收未通過，退回修正，記錄退回原因 |
| `done → archived` | 歷史保留，無治理條件限制 |
| 任何活躍狀態 → `cancelled` | 記錄取消原因；若有替代票，附 `[Superseded by: TASK-XXX]` |

### 終態說明

- `done`：驗收通過。可進一步轉 `archived`。
- `cancelled`：不再執行。不可復活，需重做應開新票。
- `archived`：歷史保留。不可復活。

---

## 驗收與知識反饋閉環

### `review → done` 的必要條件

1. acceptance criteria 逐條檢查通過
2. 知識反饋已完成（如適用）：
   - 修正文檔或 source path → 同步更新對應 document entity 或文件治理狀態
   - 處理 blindspot → 驗收通過後關閉或更新對應 blindspot
   - 補齊規格 / 規則 / 介面設計 → 產出沉澱回受治理文件，不只把 task 標 done
   - 修補 ontology / MCP 行為 → 若改變了規則或 contract，更新對應 spec / reference

### 責任分工

- **執行者**：在 `result` 或 `Result:` 區塊說明產出與受影響知識
- **驗收者**：確認知識反饋已完成，才通過 task；不得假設 `done` 自動等於知識已同步
- 純行動類 task（不改變知識層，如訪談客戶、確認外部 quota）：在 `result` 記錄結論摘要即可，不強制更新文件或 entity

### 若 task 完成會改變知識層

acceptance criteria 中應至少有一條明確要求相關文檔、blindspot 或 entity 狀態已同步。

---

## 常見反模式

建票前確認沒有以下情況：

| 反模式 | 識別特徵 | 正確處置 |
|--------|---------|---------|
| **孤兒票** | 沒有 `linked_entities`，description 太短，缺 AC | 補齊三欄後再建票 |
| **假連結票** | `linked_entities` 有填但 description 完全沒提到這些節點 | 移除無關連結，或補充說明為何相關 |
| **混合型票** | 同一張票要求寫 spec + 實作 + migration + QA | 拆成多張票，各有獨立 AC |
| **提醒型票** | 「記得之後看這個」，沒有 owner / 邊界 / 完成條件 | 若無 owner 就先記 blindspot |
| **重複票** | 舊票未取消就再開一張，描述同一主要 outcome | 優先更新既有票；若新票是正確收斂版本，舊票標 `cancelled` 並附 `[Superseded by: TASK-XXX]` |

---

## MCP 呼叫速查

```python
# 建票前去重（必須）
mcp__zenos__search(collection="tasks", status="backlog,todo,in_progress,review,blocked", q="<關鍵字>")

# 建票
mcp__zenos__task(action="create", title="<動詞開頭>", description="<背景/問題/期望結果>",
    acceptance_criteria=["<條件1>", "<條件2>"],
    linked_entities=["<節點1>", "<節點2>"],
    status="backlog",  # 或 "todo"
    assignee="<角色或人名>")

# 更新狀態
mcp__zenos__task(action="update", task_id="<id>", status="<新狀態>")

# 進入 review 前補 result
mcp__zenos__task(action="update", task_id="<id>",
    result="<產出說明>",
    status="review")

# 取消並標記 supersede
mcp__zenos__task(action="update", task_id="<舊票id>",
    status="cancelled",
    description="<原描述> [Superseded by: TASK-XXX]")

# 查詢同一 plan 的所有 task
mcp__zenos__search(collection="tasks", plan_id="<plan_id>")
```

---

## Plan 層補充規則

當 task 屬於某個 Plan 時，額外注意：

- task 必須有 `plan_id` 與 `plan_order`，才能被正確排序派發
- 領到 task 後，必須拉出同 plan 的所有 task，確認順序與依賴是否滿足
- 前置 task 未完成時，不得把後續 task 推進到可執行狀態
- Plan 不可直接派工，Task 才是唯一可 claim 的執行單位
- Plan 完成判定不得覆蓋 task 逐張驗收結果
