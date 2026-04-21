# Shared Rules — 建票與確認

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
