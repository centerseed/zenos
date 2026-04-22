# Shared Rules — 建票與確認

> **2026-04-22 更新（ADR-044）**：task / plan 建立時 `product_id` 為必填 SSOT。

## 接單 / 交接共通規則（所有 agent 都要遵守）

只要 agent 接到 task 派工，就要先做 claim，不能只讀內容就開始做事。

### 接到 task 的第一步

1. 讀 `get(task)` 或等價脈絡，確認目前 `status`、`dispatcher`、`assignee`
2. 確認這張票現在真的派給自己；若 `dispatcher` 不對，先回報，不要偷偷做
3. 開工前顯式更新狀態為 `in_progress`
4. 若流程要求責任落點，顯式確認 / 更新 `assignee`，不要假設 handoff 會自動填

重點：
- `handoff` 只會更新 `dispatcher` 與 `handoff_events`
- `handoff` **不會**自動 claim task
- `handoff` **不會**自動把 `todo` 升成 `in_progress`
- `handoff` **不會**自動填 `assignee`

### 要交接時

所有 handoff 都必須帶可驗收摘要，至少包含：
- 做了什麼
- 交付物在哪裡（`output_ref`）
- 驗證怎麼做
- 已知風險 / 未完成項

`reason` 要講交接原因，`notes` 要放 handoff 摘要；不要只寫空泛的 `"done"` / `"ready"`。

建議格式：

```python
mcp__zenos__task(
    action="handoff",
    id="{task_id}",
    to_dispatcher="agent:{next_role}",
    reason="{為什麼現在要交棒}",
    output_ref="{doc path | commit SHA | artifact}",
    notes="summary: {做了什麼}; verify: {驗證指令/場景}; risk: {已知風險或無}"
)
```

一句話：**接單先 claim；交棒留摘要。**

---

## Product Scope（所有操作必帶）

所有治理操作開始前必須完成 Step 0: Context Establishment。完成後取得 `PRODUCT_ID`，後續**所有操作都要帶 product_id**：

```python
# 查重、搜尋、列表
mcp__zenos__search(query="...", collection="tasks", product_id=PRODUCT_ID)

# 建 task / plan——product_id 必填
mcp__zenos__task(action="create", title="...", product_id=PRODUCT_ID, ...)
mcp__zenos__plan(action="create", goal="...", product_id=PRODUCT_ID, ...)
```

**禁止：**
- 不帶 product scope 的 search/write
- 建 task / plan 不給 product_id（server 會 reject `MISSING_PRODUCT_ID`；fallback 只能救回 partner.defaultProject 解析到的情境）

---

## 任務層級規則（2026-04-22）

```
Milestone (L3 goal entity)
    ↑ linked_entities
Plan
    ↑ plan_id
Task
    ↑ parent_task_id (必填 for subtask)
Subtask
```

**硬規則：**
- **Subtask 必須有 parent_task_id**——subtask 不能是孤兒
- `subtask.product_id` = `parent.product_id`（server reject `CROSS_PRODUCT_SUBTASK`）
- `subtask.plan_id` = `parent.plan_id`（server reject `CROSS_PLAN_SUBTASK`）
- `task.product_id` = `plan.product_id`（task 有 plan_id 時，reject `CROSS_PRODUCT_PLAN_TASK`）
- Milestone = `type=goal, level=3` 的 L3 entity，透過 task.linked_entities 引用

---

## 三條繩子原則（Task 對外關聯）

| 繩子 | 欄位 | Cardinality | 必填 | 語意 |
|------|------|-------------|------|------|
| **歸屬** | `product_id` | 1:1 | ✅ 必填 | 「屬於哪個產品」唯一 SSOT |
| **編組** | `plan_id` + `parent_task_id` | 1:1 | 選填 | 「在哪個 plan / 是誰的 subtask」 |
| **知識** | `linked_entities` | N:N, 0-3 | 建議 | 「跟哪些 L2 module / L3 milestone 關聯」，**禁止含 product entity** |

`project` 字串欄位已 deprecated，server 自動從 product entity.name 派生。

---

## 建票前去重（必做）

```python
# canonical status：todo / in_progress / review / done / cancelled
mcp__zenos__search(
    query="任務關鍵字",
    collection="tasks",
    product_id=PRODUCT_ID,
    status="todo,in_progress,review"
)
```

比對：title 是否描述同一主要 outcome、description 是否處理同一問題邊界、
linked_entities 是否指向同組核心節點。有重複就 update，不要開新票。

---

## linked_entities 使用說明

先 search 找到節點 ID，再填入：

```python
# 只找 L2 / L3 entity（不要 L1 product）
mcp__zenos__search(query="節點名稱", collection="entities", entity_level="L2")
```

- **禁止含 type=product entity**（server 會 strip + warning `LINKED_ENTITIES_PRODUCT_STRIPPED`）
- Server 會 reject 不存在的 ID（不會 silently drop）
- 找不到穩定對應節點時，在 description 標注 `[Ontology Gap: 缺少 XXX 對應節點]`，不要亂掛
- 推薦上限：1-3 個。4 個以上通常代表粒度太大

---

## confirm 參數格式

用 `accepted=True` / `accepted=False`，**不是** `accept`：

```python
# 通過（result 已在 update(status=review, result=...) 填入，confirm 不重複傳）
mcp__zenos__confirm(collection="tasks", id="task-id", accepted=True)

# 退回（原因寫在 rejection_reason，不是 result）
mcp__zenos__confirm(collection="tasks", id="task-id", accepted=False,
    rejection_reason="FAIL。Critical: {問題描述}，退回 Developer 修復。")
```

`accepted=False` 會把 task 退回 `in_progress`。
