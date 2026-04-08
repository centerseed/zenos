# Shared Rules — 建票與確認

## 建票前去重（必做）

```python
# 狀態集合依 SPEC-task-governance 2026-03-31 簡化版：
# backlog 已併入 todo，blocked 已移除（改用 blocked_by/blocked_reason 欄位）
mcp__zenos__search(
    query="任務關鍵字",
    collection="tasks",
    status="todo,in_progress,review"
)
```

比對：title 是否描述同一主要 outcome、description 是否處理同一問題邊界、
linked_entities 是否指向同組核心節點。有重複就 update，不要開新票。

## linked_entities 使用說明

先 search 找到節點 ID，再填入：

```python
mcp__zenos__search(query="節點名稱", collection="entities")
# 取回 id 後填入 linked_entities
```

Server 會 reject 不存在的 ID（不會 silently drop）。
找不到穩定對應節點時，在 description 標注 `[Ontology Gap: 缺少 XXX 對應節點]`，不要亂掛。
推薦上限：1–3 個。4 個以上通常代表粒度太大。

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
