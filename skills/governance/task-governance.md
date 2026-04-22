# Task 治理規則 v2.2

> **Reference only.**
> SSOT: `governance_guide(topic="task", level=2)` via MCP.
> This file is a human-readable mirror and MAY LAG the SSOT.
> Agents must call governance_guide before acting on rules.

> **2026-04-22 重大更新（ADR-044）**：task ownership 收斂為 `product_id` 必填 SSOT。
> 詳見 `docs/specs/SPEC-task-governance.md` §2026-04-22 章節與 ADR-044。

## Task 的定位

Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。

---

## 任務層級結構（嚴格四層）

```
Milestone (= Goal entity, L3)     ← outcome anchor，用 type=goal 的 L3 entity 表達
    ↑ linked_entities (選填)
Plan (action layer primitive)      ← 任務群組，grouping + sequencing + completion boundary
    ↑ plan_id (選填，task 可無 plan)
Task (action layer)                 ← 主角
    ↑ parent_task_id (必填 for subtask)
Subtask (= Task with parent_task_id ≠ null)
```

**硬規則：**

| 層級 | 規則 |
|------|------|
| Subtask | **必須有 parent_task_id**（parent 必為現存 task）——subtask 不能是孤兒 |
| Subtask | `subtask.plan_id` 必須等於 `parent.plan_id`（server reject `CROSS_PLAN_SUBTASK`） |
| Subtask | `subtask.product_id` 必須等於 `parent.product_id`（server reject `CROSS_PRODUCT_SUBTASK`） |
| Task in plan | `task.product_id` 必須等於 `plan.product_id`（server reject `CROSS_PRODUCT_PLAN_TASK`） |
| Task | 可無 plan（ad-hoc task 允許），但仍需 product_id |
| Plan | 可無 milestone（直接屬於 product），milestone 是選配 outcome anchor |

**「subtask」這個概念是 derived**：同一張 tasks 表，`parent_task_id ≠ null` 的 task 就是 subtask。要建 subtask 就必須給 parent_task_id，給不出來就不是 subtask，是獨立 task。

---

## 三條繩子原則（Task 對外關聯）

Task 對外有且只有三條關聯繩子，各管各的：

| 繩子 | 欄位 | Cardinality | 必填 | 語意 |
|------|------|-------------|------|------|
| **歸屬繩** | `product_id` (FK to L1 product entity) | 1:1 | ✅ **必填** | 「這 task 屬於哪個產品」唯一 SSOT |
| **編組繩** | `plan_id` + `parent_task_id` | 1:1 | 選填 | 「在哪個 plan / 是誰的 subtask」 |
| **知識繩** | `linked_entities` (N:N) | 0..3 | 建議 | 「跟哪些 L2 module / L3 milestone 有 ontology 關聯」|

**絕對不要混用**：
- ❌ 不要把 product entity 放進 `linked_entities`（會被 server strip + warning）
- ❌ 不要只填 `project` 字串欄位不填 `product_id`（deprecated，寫入會被 ignore）
- ❌ 不要給 subtask 空的 `parent_task_id`（不是 subtask，就是普通 task）

---

## 建票前去重（必做）

```python
mcp__zenos__search(
    query="任務關鍵字",
    collection="tasks",
    product_id=PRODUCT_ID,               # 必帶，避免跨 product 誤判
    status="todo,in_progress,review",
    limit=20
)
```

有重複的票就 update，不要開新票。

> canonical task status 只有：`todo` / `in_progress` / `review` / `done` / `cancelled`。
> `backlog`、`blocked`、`archived` 是 legacy alias；server 目前會自動正規化，但 skill 不應再主動使用。

---

## 建票 (action="create")

### 建普通 task（ad-hoc / 屬於 plan）

```python
mcp__zenos__task(
    action="create",
    title="動詞開頭的標題",               # 必填，動詞開頭（實作、修復、設計、調查…）
    product_id=PRODUCT_ID,                # ✅ 必填——這 task 屬於哪個產品
    description="markdown 格式描述",       # 選填；server 會自動格式化
    acceptance_criteria=["AC1", "AC2"],   # list[str]
    linked_entities=["l2-module-id"],     # 0-3 個 L2/L3 entity，禁止含 product entity
    priority="critical|high|medium|low",  # 選填
    assignee_role_id="role-entity-id",    # 跨 agent 協作建議填
    dispatcher="agent:pm",                # 顯性 handoff chain 起點
    plan_id="32-char-plan-uuid",          # 屬於 plan 時帶；task.product_id 必須等於 plan.product_id
    plan_order=1,
    depends_on_task_ids=["task-id"],
    blocked_by=["task-id"],
    blocked_reason="等待前置資料",
    linked_protocol="protocol-id",
    linked_blindspot="blindspot-id",
    source_metadata={"created_via_agent": True, "agent_name": "pm"},
    # status 不要傳，default 是 todo
    # created_by 不要傳，server 依 API key 自動填
    # project 字串不要傳，deprecated，server 從 product entity.name 自動派生
)
```

### 建 subtask（必須有 parent_task_id）

```python
mcp__zenos__task(
    action="create",
    title="動詞開頭的 subtask 標題",
    product_id=PRODUCT_ID,                # 必須等於 parent.product_id
    parent_task_id="parent-task-id",      # ✅ 必填——subtask 的 parent 必為現存 task
    plan_id="parent-plan-id",             # 必須等於 parent.plan_id（若 parent 有 plan）
    acceptance_criteria=["AC1"],          # subtask 也要有獨立 AC
    dispatcher="agent:developer",
    # 其他欄位同普通 task
)
```

**Subtask 粒度原則**：
- subtask 仍必須單一 outcome、2-5 條 AC、單一 assignee
- subtask 不是「parent 的 checklist」——是「同 plan 同 product 下獨立可驗收的子單位」
- 建議深度 ≤ 2 層（避免 subtask 的 subtask 的 subtask...）
- subtask 完成 ≠ parent 完成（parent 需自行 confirm，不自動 cascade）

### 建 milestone（= Goal entity）

Milestone 不是 task，是 L3 goal entity：

```python
mcp__zenos__write(
    collection="entities",
    data={
        "type": "goal",
        "level": 3,
        "name": "Q2 Launch",
        "parent_id": PRODUCT_ID,
        # ...
    }
)

# Task 掛 milestone：
mcp__zenos__task(
    action="create",
    title="...",
    product_id=PRODUCT_ID,
    linked_entities=[MILESTONE_GOAL_ID],  # goal entity 放這裡
)
```

### 建 plan

```python
mcp__zenos__plan(
    action="create",
    goal="plan 目標描述",
    owner="agent:architect",
    product_id=PRODUCT_ID,                # ✅ 必填
    entry_criteria="何時算可以啟動",
    exit_criteria="何時算達成目標",
)
```

---

## Server-side 寫入驗證（2026-04-22）

| 違規 | 處置 | error_code |
|------|------|------------|
| 沒傳 `product_id` 也無 `partner.defaultProject` 可解析 | reject | `MISSING_PRODUCT_ID` |
| `product_id` 指向不存在 / 非 product 類 entity | reject | `INVALID_PRODUCT_ID` |
| `linked_entities` 含 type=product 的 entity | strip + warning | `LINKED_ENTITIES_PRODUCT_STRIPPED` |
| 同時傳 `project` 字串和 `product_id` 但對不上 | 以 `product_id` 為準 + warning | `PROJECT_STRING_IGNORED` |
| `subtask.product_id` ≠ `parent.product_id` | reject | `CROSS_PRODUCT_SUBTASK` |
| `subtask.plan_id` ≠ `parent.plan_id` | reject | `CROSS_PLAN_SUBTASK` |
| `task.product_id` ≠ `plan.product_id`（task 有 plan_id） | reject | `CROSS_PRODUCT_PLAN_TASK` |
| `parent_task_id` 指向不存在 task | reject | `PARENT_NOT_FOUND` |
| `linked_entities` 含不存在 entity ID | reject | 錯誤列表 |
| title 長度 <4 字元或停用詞開頭 | reject | 錯誤訊息 |
| `handoff_events` 直接寫入 | ignore + warning | `HANDOFF_EVENTS_READONLY` |
| `dispatcher` 不符合正則 `^(human(:<id>)?\|agent:[a-z_]+)$` | reject | `INVALID_DISPATCHER` |

---

## MCP SSOT

依 `docs/specs/SPEC-mcp-tool-contract.md`。所有 MCP tool 都走統一 envelope：
`{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints}`

- 成功讀 `response["data"]`
- 輸入可修正錯誤看 `status=="rejected"` + `data.error` / `data.message`
- 系統故障看 `status=="error"`

---

## linked_entities 使用規則

- **禁止含 type=product 的 entity**（歸屬由 product_id 表達，放這裡會被 server strip）
- 上限 1-3 個（4+ 通常代表粒度太大）
- 只放 **L2 module / L3 entity**（goal=milestone / document / role）
- 先 search 找到 entity ID 再填
- Server 會 reject 不存在的 ID

```python
# 先找 L2/L3 entity ID（排除 L1 product）
mcp__zenos__search(
    query="功能關鍵字",
    collection="entities",
    entity_level="L2"  # 或 "all" 看 L3
)
# 再填進建票
```

---

## 狀態流

```
todo → in_progress → review → (confirm) → done
任何活躍狀態 → cancelled
```

### 重要限制

- 改狀態到 `review` 時，**result 欄位為必填**（SQL schema 強制）
- **不能用 update 把 status 改成 done**，必須用 `confirm` 驗收
- **subtask 完成不 cascade parent**——parent 需要自己 confirm

---

## Richer Task 欄位何時該用

- `product_id`（2026-04-22 起必填）：歸屬 SSOT
- `assignee_role_id`：責任落在「角色佇列」而不是個人時
- `dispatcher`：顯性 handoff chain
- `plan_id` / `plan_order`：同一 plan 多張 task 需要順序
- `parent_task_id`：建 subtask（**建 subtask 就必填，否則不是 subtask**）
- `depends_on_task_ids`：真實 task 依賴
- `blocked_by` / `blocked_reason`：被卡住就填（不用 `blocked` 狀態）
- `linked_protocol`：有 intake / SOP / checklist 來源
- `linked_blindspot`：由治理盲點觸發
- `source_metadata`：agent / doc / chat provenance（不塞附件）
- `attachments`：圖片 / 檔案 / link（不塞 source_metadata）

---

## Dashboard / UI 對齊原則

- Dashboard 若已有 read model，應提供選擇器，不要逼使用者手打
- Dashboard 若暫時沒有 read model，也至少要保留穩定 ID 輸入口
- UI 上看不到的 richer 欄位，不代表 agent 不該填

---

## 更新票 (action="update")

```python
mcp__zenos__task(
    action="update",
    id="task-id",           # 必填
    status="in_progress",   # 要改什麼就傳什麼
    result="交付說明",      # update to review 時必填
    # product_id 理論上 immutable（changing 會觸發 CROSS_PRODUCT_* 檢查）
)
```

---

## 派工 (action="handoff")

```python
mcp__zenos__task(
    action="handoff",
    id="task-id",
    to_dispatcher="agent:qa",             # 必填，通過 namespace 驗證
    reason="implementation complete, ready for verification",  # 必填
    output_ref="<commit SHA or file path>",
    notes="summary: ...; verify: ...; risk: ..."
)
```

**handoff ≠ runtime claim**：handoff 只代表「現在輪到誰」，接單 agent 必須顯式 `update(status="in_progress")` 才算開工。

---

## 驗收票 (confirm)

用 `accepted=True` / `accepted=False`（server 會相容 `accept` 舊參數，但 skill 不要再主動使用）。

```python
# QA PASS（result 已在 Developer 的 update(status=review, result=...) 填入）
mcp__zenos__confirm(
    collection="tasks",
    id="task-id",
    accepted=True
)

# QA FAIL（退回原因寫在 rejection_reason）
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
| PM | 開 Feature Spec 完 | `task(action="create", product_id=X, dispatcher="agent:pm")` |
| Architect | 拆 subtask | `task(action="create", parent_task_id=parent, product_id=X, plan_id=parent.plan_id, dispatcher="agent:architect")` |
| Developer | 拿到任務 | `task(action="update", id=X, status="in_progress")` |
| Developer | 完成實作 | `task(action="update", id=X, status="review", result="Completion Report")` |
| Developer → QA | handoff | `task(action="handoff", to_dispatcher="agent:qa", reason="...", output_ref="...")` |
| QA | PASS | `confirm(collection="tasks", id=X, accepted=True)` |
| QA | FAIL | `confirm(collection="tasks", id=X, accepted=False, rejection_reason="...")` |
