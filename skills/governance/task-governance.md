# Task 治理規則 v2.1

> **Reference only.**
> SSOT: `governance_guide(topic="task", level=2)` via MCP.
> This file is a human-readable mirror and MAY LAG the SSOT.
> Agents must call governance_guide before acting on rules.

## Task 的定位

Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。

---

## 建票前去重（必做）

```python
mcp__zenos__search(
    query="任務關鍵字",
    collection="tasks",
    status="todo,in_progress,review",
    limit=20  # status 多值過濾有效，建議加 limit 避免大量回傳
)
```

有重複的票就 update，不要開新票。

> canonical task status 只有：`todo` / `in_progress` / `review` / `done` / `cancelled`。
> `backlog`、`blocked`、`archived` 是 legacy alias；server 目前會自動正規化，但 skill 不應再主動使用。

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
    assignee_role_id="role-entity-id",   # 建議：跨 agent / 跨廠牌協作時優先填
    dispatcher="agent:pm",               # 建議：顯性 handoff chain 起點
    plan_id="32-char-plan-uuid",         # 有 plan/group 時建議帶
    plan_order=1,                         # 同一 plan 的執行順序
    depends_on_task_ids=["task-id"],     # 非線性流程依賴
    blocked_by=["task-id"],              # 被哪些 task 卡住
    blocked_reason="等待前置資料",         # blocked_by 有值時必填
    linked_protocol="protocol-id",       # 有固定 SOP / intake protocol 時帶
    linked_blindspot="blindspot-id",     # 由盲點觸發時帶
    source_metadata={"created_via_agent": True, "agent_name": "pm"},  # 來源追溯
    # status 不要傳，default 是 todo
    # created_by 不要傳，server 依 API key 自動填
)
```

> **MCP SSOT：** 依 `docs/specs/SPEC-mcp-tool-contract.md`。
> 所有 MCP tool 都走統一 envelope：`{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints}`。
> 成功讀 `response["data"]`；輸入可修正錯誤看 `status=="rejected"` + `data.error` / `data.message`；系統故障看 `status=="error"`。

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

> **confirm 回傳：** `confirm` 成功後可從 `response["governance_hints"]` 讀後續知識回寫建議，不要再假設 top-level `suggested_actions`。

## 狀態流

```
todo → in_progress → review → (confirm) → done
任何活躍狀態 → cancelled
```

### 重要限制

- 改狀態到 `review` 時，**result 欄位為必填**（SQL schema 強制）
- **不能用 update 把 status 改成 done**，必須用 `confirm` 驗收

## Richer Task 欄位何時該用

不是每張 task 都要把所有欄位填滿，但以下情境不應再只用最小欄位集：

- `assignee_role_id`
  - 當任務責任落在「角色佇列」而不是特定個人時優先填。
  - 例如：`doc_reviewer`、`qa`、`designer`。
- `dispatcher`
  - 需要顯性 handoff chain 時必填。
  - PM 開始的 task 建議從 `agent:pm` 起。
- `plan_id` / `plan_order`
  - 同一交付目標下有多張 task，且順序重要時使用。
- `parent_task_id`
  - 需要 subtask，但仍要保留獨立驗收邊界時使用。
- `depends_on_task_ids`
  - 前置條件不是描述文字，而是真實 task 依賴時使用。
- `blocked_by` / `blocked_reason`
  - 不再用 `blocked` 狀態。被卡住就填 blocker IDs + 原因。
- `linked_protocol`
  - 任務有固定 intake / SOP / checklist 來源時使用。
- `linked_blindspot`
  - 任務是由治理盲點、風險或異常直接觸發時使用。
- `source_metadata`
  - 保留 agent / doc / chat provenance；不要拿這欄塞附件。
- `attachments`
  - 圖片 / 檔案 / link 一律走 `attachments`；不要混進 `source_metadata`。

一句話：

- 小型單點任務 → 最小欄位集可以
- 跨角色、跨階段、可阻塞、可 handoff 的任務 → 要用 richer task 欄位

## Dashboard / UI 對齊原則

- Dashboard 若已有 read model（例如 entity、blindspot），應提供選擇器，不要逼使用者手打。
- Dashboard 若暫時沒有 read model（例如 plan / protocol），也至少要保留穩定 ID 輸入口，**不得靜默忽略欄位**。
- UI 上看不到的 richer 欄位，不代表 agent 不該填；agent 仍應依治理需要帶入。

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

用 `accepted=True` / `accepted=False`。server 會相容 `accept` 舊參數，但 skill 不要再主動使用。

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
| QA | PASS | `confirm(accepted=True)` |
| QA | FAIL | `confirm(accepted=False, rejection_reason="退回原因")` |
