# Shared Rules — 建票與確認

> **Reference only.**
> SSOT: `governance_guide(topic="task", level=2)` via MCP.
> This file is a human-readable mirror and MAY LAG the SSOT.
> Agents must call governance_guide before acting on rules.

> **2026-04-22 更新（ADR-044）**：task / plan 建立時 `product_id` 為必填 SSOT。

## Product Scope（所有操作必帶）

所有治理操作開始前必須完成 [Step 0: Context Establishment](bootstrap-protocol.md)。
完成後取得 `PRODUCT_ID`，後續**所有操作都要帶 product_id**：

```python
# 查重、搜尋、列表——都帶 product scope
mcp__zenos__search(query="...", collection="tasks", product_id=PRODUCT_ID)

# 寫入 document / 其他 collection——關聯到正確產品
mcp__zenos__write(collection="documents", data={..., "linked_entity_ids": [...]})

# 建 task / plan——product_id 必填
mcp__zenos__task(action="create", title="...", product_id=PRODUCT_ID, ...)
mcp__zenos__plan(action="create", goal="...", product_id=PRODUCT_ID, ...)
```

**禁止：**
- 不帶 product scope 的 search/write
- 建 task / plan 不給 product_id（server 會 reject `MISSING_PRODUCT_ID`；fallback 只能救回 partner.defaultProject 解析到的情境，其他都會失敗）

---

## 建票前去重（必做）

```python
# canonical status：todo / in_progress / review / done / cancelled
# backlog / blocked / archived 是 legacy alias，不要主動使用
mcp__zenos__search(
    query="任務關鍵字",
    collection="tasks",
    product_id=PRODUCT_ID,
    status="todo,in_progress,review",
    limit=20
)
```

比對：
- `title` 是否描述同一主要 outcome
- `description` 是否處理同一問題邊界
- `linked_entities` 是否指向同組核心節點

有重複就 update，不要開新票。

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
- **Subtask 必須有 parent_task_id**——subtask 不能是孤兒，要建 subtask 就必填 parent
- `subtask.product_id` = `parent.product_id`（server reject `CROSS_PRODUCT_SUBTASK`）
- `subtask.plan_id` = `parent.plan_id`（server reject `CROSS_PLAN_SUBTASK`）
- `task.product_id` = `plan.product_id`（若 task 有 plan_id，server reject `CROSS_PRODUCT_PLAN_TASK`）
- Milestone = `type=goal, level=3` 的 L3 entity，透過 task.linked_entities 引用

---

## 三條繩子原則（Task 對外關聯）

| 繩子 | 欄位 | Cardinality | 必填 | 語意 |
|------|------|-------------|------|------|
| **歸屬** | `product_id` | 1:1 | ✅ 必填 | 「屬於哪個產品」唯一 SSOT |
| **編組** | `plan_id` + `parent_task_id` | 1:1 | 選填 | 「在哪個 plan / 是誰的 subtask」 |
| **知識** | `linked_entities` | N:N, 0-3 | 建議 | 「跟哪些 L2 module / L3 milestone 關聯」，**禁止含 product entity** |

`project` 字串欄位已 deprecated，caller 不再傳入；server 自動從 product entity.name 派生。

---

## linked_entities 使用規則

先 search 找到節點 ID，再填入：

```python
# 只找 L2 / L3 entity（不要 L1 product，放進 linked_entities 會被 strip）
mcp__zenos__search(query="節點名稱", collection="entities", entity_level="L2")
# 或
mcp__zenos__search(query="milestone 名稱", collection="entities", entity_level="all")  # 看 L3 goal
# 取回 id 後填入 linked_entities
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
