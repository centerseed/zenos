# Task 治理規則 v2.0

## Task 的定位

Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。

---

## 建票前去重（必做）

```python
mcp__zenos__search(
    query="任務關鍵字",
    collection="tasks",
    status="todo,in_progress,review,blocked",
    limit=20  # status 多值過濾有效，建議加 limit 避免大量回傳
)
```

有重複的票就 update，不要開新票。

---

## 建票 (action="create")

```python
mcp__zenos__task(
    action="create",
    title="動詞開頭的標題",            # 必填，動詞開頭（實作、修復、設計、調查…）
    description="markdown格式描述",     # 選填；傳入後 server 會自動解析並格式化為結構化 Markdown（分段、加標題）
    acceptance_criteria=["AC1", "AC2"], # list[str]，不是字串
    linked_entities=["entity-id-1"],    # list[str]，先 search 找到 ID 再填
    priority="critical|high|medium|low", # 選填，不填 AI 自動推薦
    # status 不要傳，default 是 todo
    # created_by 不要傳，server 依 API key 自動填
)
```

> **Phase 1 統一回傳格式：** 所有回傳改為 `{status, data, warnings, suggestions, ...}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

> **Server 端驗證：** Server 驗證 title 長度（≥4 字元）並拒絕停用詞開頭。`linked_entities` 不存在的 ID 會被 reject（不再 silently drop）。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates`。

### linked_entities 很重要

- 每張票都應該掛 linked_entities，讓收到票的人/agent 自動獲得 context
- linked_entities 必須是存在的 entity ID（先 search 找到 ID 再填）

> **Server 端驗證（Phase 1 強化）：** `linked_entities` 中不存在的 ID 直接 reject（`status: "rejected"`），不再靜默忽略。建票前務必先 search 確認 ID 存在。

```python
# 先找 entity ID
mcp__zenos__search(query="功能關鍵字", collection="entities")
# 再填進建票
```

---

> **confirm 回傳：** `confirm` 成功後回傳包含 `suggested_actions` 欄位，列出建議的後續動作（如通知相關 entity owner、更新下游任務）。可參考執行，非強制。

## 狀態流

```
todo → in_progress → review → (confirm) → done
任何活躍狀態 → cancelled
```

### 重要限制

- 改狀態到 `review` 時，**result 欄位為必填**（SQL schema 強制）
- **不能用 update 把 status 改成 done**，必須用 `confirm` 驗收

---

## 更新票 (action="update")

```python
mcp__zenos__task(
    action="update",
    id="task-id",         # 必填
    status="in_progress", # 要改什麼就傳什麼
    result="交付說明",    # update to review 時必填
)
```

---

## 驗收票 (confirm)

```python
# QA PASS（result 已在 Developer 的 update(status=review, result=...) 填入，confirm 不傳 result）
mcp__zenos__confirm(
    collection="tasks",
    id="task-id",
    accepted=True
)

# QA FAIL（退回原因寫在 rejection_reason，不是 result）
mcp__zenos__confirm(
    collection="tasks",
    id="task-id",
    accepted=False,
    rejection_reason="退回原因：AC2 未達標，缺少錯誤路徑測試"
)
```

---

## 各角色操作時機速查

| 角色 | 時機 | 操作 |
|------|------|------|
| Architect | 開票時 | `create`，掛 linked_entities |
| Developer | 拿到任務 | `update(status="in_progress")` |
| Developer | 完成實作 | `update(status="review", result="Completion Report 摘要")` |
| QA | PASS | `confirm(accepted=True, result="QA 摘要")` |
| QA | FAIL | `confirm(accepted=False, result="退回原因")` |
