---
type: SPEC
id: SPEC-task-governance
status: Approved
ontology_entity: action-layer
created: 2026-03-26
updated: 2026-04-21
---

# Feature Spec: ZenOS Task Governance

> Layering note: 本 spec 只定義 `ZenOS Core` 中的 Action Layer 治理規則。
> `Task` 與 `Plan` 的平台定位以 `SPEC-zenos-core` 為準；application-specific subtask / checklist / execution step 不在本 spec 範圍。

## 2026-04-19 Action-Layer 升級：Subtask / Dispatcher / Handoff（最新覆寫）

本節在既有 Task schema 上增補三個正交維度，同時把 **milestone** 落位到既有 L3 Goal entity，不新增 entity type。

### 模型定位

```
Milestone (= EntityType.GOAL，不新增 type)      ← L3 entity，outcome anchor
    ▲ rel/linked_entities
Plan (string id grouper，維持現狀)                ← 不升 entity（見 ADR-028 Draft）
    ▲ plan_id
Task (加三欄)                                     ← 主角
    ▲ parent_task_id（自指）
Subtask (= Task with parent_task_id ≠ null)      ← 同表、任意深度
```

### Schema 增補（三欄）

| 欄位 | 型別 | 必填 | 定義 | 治理規則 |
|------|------|------|------|---------|
| `parent_task_id` | string \| null | 否 | Subtask 的父 task ID（自指） | 若設，subtask 必須繼承 parent 的 `plan_id`；Server 強制一致否則 reject |
| `dispatcher` | string \| null | 否 | 當前派工角色，namespace 格式 `^(human(:<id>)?\|agent:[a-z_]+)$` | Server 強制 enum prefix 驗證；不合格 reject |
| `handoff_events` | HandoffEvent[] | 系統產生 | 派工履歷（append-only） | Caller 不可直接 write；只能透過 `task(action="handoff")` 由 server append |

### `HandoffEvent` 結構

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `at` | datetime | 系統產生 | 事件時間（UTC） |
| `from_dispatcher` | string | 系統產生 | 事件前的 dispatcher |
| `to_dispatcher` | string | 是 | 事件後的 dispatcher（通過 namespace 驗證） |
| `reason` | string | 是 | 為什麼 handoff（驗收通過 / 需架構 / 遇阻 / cancel） |
| `output_ref` | string \| null | 建議 | 該階段產出引用（commit SHA / ADR id / entry id / file path） |
| `notes` | string \| null | 否 | 補充說明 |

**DB 儲存**：handoff_events 作為 JSONB 欄位存於 tasks table，append-only 由 server 層保證（write 不允許覆寫整個欄位）。

### Dispatcher Namespace

| 值 | 意義 | 備註 |
|---|------|------|
| `human` | 泛指任何人類 | 未指定具體 assignee 時使用 |
| `human:<partner_id>` | 具體人類 | 通常跟 assignee 一致 |
| `agent:pm` | PM agent | 寫 Feature Spec |
| `agent:architect` | Architect agent | 技術設計、拆任務 |
| `agent:developer` | Developer agent | 實作 |
| `agent:qa` | QA agent | 驗收 |
| `agent:<role>` | 未來擴充 | 小寫 + underscore |

**Server 驗證**：正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`。不合格的 dispatcher 值 → `write` / `task(action="handoff")` reject，error_code=`INVALID_DISPATCHER`。

### Handoff 流程（Action-Layer 原生）

**MCP tool**：`task(action="handoff", id=X, data={...})`

```
task(action="handoff", id="...", data={
    to_dispatcher: "agent:architect",        # 必填，通過 namespace 驗證
    reason: "spec ready, needs tech design", # 必填
    output_ref: "docs/specs/SPEC-foo.md",    # 建議
    notes: "..."                             # 選填
})
→ Server 原子操作：
  1. append {at: now, from: <current dispatcher>, to: <to_dispatcher>, ...} to handoff_events
  2. update task.dispatcher = to_dispatcher
  3. 若 to_dispatcher 為 "agent:qa" 且當前 status=in_progress，自動升 status=review
  4. 若 reason 為 "accepted" 且 confirm 同步觸發，升 status=done
  5. audit log: ontology.task.handoff
```

**Append-only 保證**：`write(collection="tasks", data={handoff_events: [...]})` 忽略 handoff_events 欄位並回傳 warning。唯一入口是 `task(action="handoff")`。

### Agent Claim / Handoff 摘要規則（2026-04-21 新增）

`handoff` 是治理與派工履歷，不是 runtime claim。任何 agent 接到 task 後，必須先完成 claim，再開始做事。

#### Claim 規則

1. 接單第一步必須讀 task 脈絡，至少確認 `status`、`dispatcher`、`assignee`
2. 只有當 `dispatcher` 已指向自己時，agent 才能 claim 該 task；若 `dispatcher` 不符，應回報，不得默默開工
3. 真正開始執行前，agent 必須顯式把 task 更新為 `in_progress`
4. `handoff` 不會自動填 `assignee`；若流程要求責任落點，agent / orchestrator 必須顯式確認或更新

一句話：`handoff` 只代表「現在輪到誰」，`claim` 才代表「有人真的開始做」。

#### Handoff 摘要規則

所有 `task(action="handoff")` 都必須帶可驗收摘要，不得只寫空泛的 `"ready"` / `"done"`。

- `reason`：為什麼現在要交棒
- `output_ref`：本階段主要產出（spec path / TD path / commit SHA / report path / artifact）
- `notes`：handoff 摘要，至少包含：
  - `summary`: 做了什麼
  - `verify`: 怎麼驗證
  - `risk`: 已知風險、限制或未完成項

建議格式：

```python
task(action="handoff", id="...", data={
    to_dispatcher: "agent:qa",
    reason: "implementation complete, ready for verification",
    output_ref: "<commit SHA>",
    notes: "summary: 改了 A/B/C；verify: pytest tests/x.py -q；risk: 已知限制或無"
})
```

#### 相容性說明

- 新流程：QA 驗收失敗時，建議用 `task(action="handoff", to_dispatcher="<上一 dispatcher>", reason="rejected: ...", notes="summary: ...; verify: ...; risk: ...")`
- legacy 相容：`confirm(collection="tasks", accepted=false, rejection_reason="...")` 仍可用於舊 caller；server 會把 task 回到 `in_progress` 並補 rejection handoff event
- Agent / workflow skill 一律以新流程為準，不再把 `confirm(accepted=false)` 當主要交接手段

### Subtask 規則

| 規則 | 強制等級 |
|------|---------|
| **subtask 必須有 `parent_task_id`（parent 必為現存 task）** | **Server reject `PARENT_NOT_FOUND`**（2026-04-22 起） |
| subtask 必須繼承 parent 的 `plan_id`（不能跨 plan） | **Server reject `CROSS_PLAN_SUBTASK`** |
| subtask 必須繼承 parent 的 `product_id`（不能跨 product） | **Server reject `CROSS_PRODUCT_SUBTASK`**（2026-04-22 起） |
| subtask 可任意深度（A → B → C → ...） | 允許，但建議 ≤ 2 層 |
| subtask 的 `linked_entities` 可獨立於 parent | 允許，但仍不可含 product entity |
| subtask 完成 ≠ parent 完成 | Parent 完成需自行 confirm（不自動 cascade） |

**「subtask」是 derived concept**：同一張 tasks 表，`parent_task_id ≠ null` 的 task 就是 subtask。要建 subtask 就必須給 parent_task_id——給不出來就不是 subtask，是獨立 task。

**粒度原則繼續適用**：subtask 仍必須單一 outcome、2-5 條 AC、單一 assignee。subtask 不是「parent 的 checklist」——是「同 plan 同 product 下獨立可驗收的子單位」。

### Milestone（= Goal entity）掛法

1. 建 milestone：`write(collection="entities", data={type: "goal", level: 3, name: "Q2 Launch", ...})`
2. Task 連到 milestone：`linked_entities` 包含 milestone 的 entity id
3. 查 milestone 下所有 task：
   ```
   search(collection="tasks", linked_entity=<milestone_id>)
   ```
4. Milestone 跨 plan 的聚合靠反查 task 的 plan_id（client 端 group），**不在 milestone entity 上存 plan_ids 列表**（避免雙向寫）。

### Inbox / Kanban Query Pattern

```
# 某 agent role 的工作 inbox
search(tasks, dispatcher="agent:architect", status="todo,in_progress")

# 某 product 底下的 milestone 列
search(entities, type="goal", product_id=X)

# 某 milestone 下的 plan 聚合
search(tasks, linked_entity=<goal_id>)   → group_by plan_id

# 某 plan 的 task 看板
search(tasks, plan_id=Y)                  → group_by status

# 某 task 的 subtask 列
search(tasks, parent_task_id=Z)

# 某 task 的 handoff 履歷
get(tasks, id=Z).handoff_events
```

需要 MCP 新增 filter：`search(tasks, dispatcher=..., parent_task_id=..., linked_entity=...)`。三者均為 server-side AND 過濾。

### Migration

| 現有資料 | 新欄位預設 |
|---------|-----------|
| 所有現存 task | `parent_task_id = null`、`dispatcher = null`、`handoff_events = []` |
| `source_metadata.agent_name` 已存在 | **不自動回填** dispatcher；新寫入才強制 dispatcher 格式 |
| 現有 plan_id 分組 | 不動 |

**向下相容**：舊 caller 不傳 dispatcher / parent_task_id 都能繼續 work；只在主動使用新欄位時才套用新驗證。

### 驗收條件（給 Developer / QA）

每條 AC 帶唯一 ID `AC-TASK-UPG-NN`，對應 test stub 於
`tests/spec_compliance/test_task_action_upgrade_ac.py`。

- **AC-TASK-UPG-01**：tasks table 加 `parent_task_id TEXT`、`dispatcher TEXT`、`handoff_events JSONB DEFAULT '[]'`，並有 index on `parent_task_id` 與 `dispatcher`。
- **AC-TASK-UPG-02**：`write(collection="tasks")` 在 `parent_task_id` 存在且 `parent.plan_id ≠ self.plan_id` 時 reject，`error_code=CROSS_PLAN_SUBTASK`。
- **AC-TASK-UPG-03**：`write(collection="tasks")` 或 `task(action="handoff")` 傳入的 `dispatcher` / `to_dispatcher` 若不符合正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`，reject，`error_code=INVALID_DISPATCHER`。
- **AC-TASK-UPG-04**：`write(collection="tasks", data={handoff_events: [...]})` 忽略該欄位並回傳 warning `HANDOFF_EVENTS_READONLY`；DB 內原值不變。
- **AC-TASK-UPG-05**：`task(action="handoff", id, data={to_dispatcher, reason, ...})` 原子完成：append HandoffEvent 到 `handoff_events`、更新 `task.dispatcher = to_dispatcher`、`to_dispatcher="agent:qa"` 且 status=in_progress 時連帶升 status=review、寫 audit log `ontology.task.handoff`。
- **AC-TASK-UPG-06**：`search(collection="tasks")` 支援新 filter `dispatcher`、`parent_task_id`、`linked_entity`（任一 match 即保留），三者 server-side AND 可組合。
- **AC-TASK-UPG-07**：既有 `search(tasks, product_id=X)` 過濾（DF-20260419-7 F12）與 AC-TASK-UPG-06 三個新 filter 可同時套用，彼此 AND。
- **AC-TASK-UPG-08**：`confirm(collection="tasks", id, accepted=true)` 呼叫後，`handoff_events` 自動 append 一條 `to_dispatcher="human"` + `reason="accepted"` 的結束事件，status 升 `done`。
- **AC-TASK-UPG-09**：SPEC-task-communication-sync / SPEC-task-view-clarity / SPEC-task-kanban-operations 經審查無衝突描述，或已補更。
- **AC-TASK-UPG-10**：任何 agent-based workflow 在接單時都必須先確認 `status` / `dispatcher` / `assignee`，且在真正開始執行前顯式 `update(status="in_progress")`；不得把 handoff 視為自動 claim。
- **AC-TASK-UPG-11**：所有 `task(action="handoff")` 範例與 workflow 都必須包含 handoff 摘要；`notes` 至少含 `summary` / `verify` / `risk`，`output_ref` 在存在產出時必填。

### 下游 SSOT 同步清單（Implementation 必做）

Action-Layer 升級不是只改 schema 就完——MCP tool docstring、governance rules SSOT、四個 Agent skill、workflow skill 都要跟著一致。**以下 14 項任一未同步，不得轉交驗收**：

#### MCP 介面層（3 項）

| # | 檔案 | 具體改動 |
|---|------|---------|
| 1 | `src/zenos/interface/mcp/task.py` | 加 `action="handoff"` 分支；docstring 新增 `handoff` action + `to_dispatcher` / `reason` / `output_ref` / `notes` 欄位說明；audit event `ontology.task.handoff` |
| 2 | `src/zenos/interface/mcp/search.py` | tasks collection docstring 加 `dispatcher` / `parent_task_id` / `linked_entity` 三個 filter；實作三個 server-side AND 過濾 |
| 3 | `src/zenos/interface/mcp/write.py` | tasks write docstring 加 `parent_task_id` / `dispatcher` 兩個欄位說明；明示 `handoff_events` 是 readonly 於 write 路徑 |

#### Governance SSOT（1 項）

| # | 檔案 | 具體改動 |
|---|------|---------|
| 4 | `src/zenos/interface/governance_rules.py["task"]` | 加三條硬約束規則（level 2 內容）：`DISPATCHER_NAMESPACE`（正則驗證）、`CROSS_PLAN_SUBTASK`（subtask 必須繼承 plan_id）、`HANDOFF_EVENTS_READONLY`（write 不可直接改 handoff_events） |
| 4a | `src/zenos/interface/governance_rules.py["task"]` | 補 claim / handoff 摘要治理規則：`handoff` 不是 runtime claim；agent 接單先確認 `status/dispatcher/assignee` 再 `in_progress`；handoff 摘要至少含 `summary/verify/risk` |

#### Agent Role Skills（4 項）

| # | 檔案 | 具體改動 |
|---|------|---------|
| 5 | `skills/release/pm/SKILL.md` | 建 task 時 `dispatcher="agent:pm"`；完成 Feature Spec 後呼叫 `task(action="handoff", to_dispatcher="agent:architect", output_ref=<spec 檔名>)` |
| 6 | `skills/release/architect/SKILL.md` | 接 handoff 後若需 subtask 必須帶 `parent_task_id` + 繼承 parent.plan_id；完成技術設計後 handoff to `agent:developer`，output_ref 為 TD/ADR path |
| 7 | `skills/release/developer/SKILL.md` | 實作完成後 handoff to `agent:qa`，output_ref 為 commit SHA；status 自動升 review |
| 8 | `skills/release/qa/SKILL.md` | 驗收通過走 `confirm(collection="tasks", accepted=true, entity_entries=[...])`；驗收 reject 走 `task(action="handoff", to_dispatcher=<上一個 dispatcher>, reason="rejected: ...")` 把球打回去 |

#### Governance Task Skill（1 項）

| # | 檔案 | 具體改動 |
|---|------|---------|
| 9 | `skills/release/governance/task-governance.md` | 8-題 checklist 擴 10 題，新增：「這張是不是該開 subtask 而不是新 task？」「dispatcher 有沒有依 namespace 規則填對？」；建票範例加一個 dispatcher="agent:pm" 的例子 |

#### Workflow Skills（3 項）

| # | 檔案 | 具體改動 |
|---|------|---------|
| 10 | `skills/release/workflows/feature.md` | 流程章節把「PM → Architect → Developer → QA」從隱性 subagent chain 改為顯性 handoff chain；每個階段指明 `task(action="handoff", ...)` 呼叫 |
| 11 | `skills/release/workflows/debug.md` | 同上（Debugger → Architect → QA → Developer → Architect 鏈條） |
| 12 | `skills/release/workflows/implement.md` | 同上（Spec → Architect → Developer → QA） |

#### 相關 Spec 審查（2 項）

| # | 檔案 | 動作 |
|---|------|------|
| 13 | `docs/specs/SPEC-task-communication-sync.md` | **讀一遍**，若有「task 狀態流轉」或「agent 互通」描述與 handoff_events 衝突，改；沒衝突直接加 reference |
| 14 | `docs/specs/SPEC-task-view-clarity.md` + `SPEC-task-kanban-operations.md` | 同上——視圖層要不要顯示 handoff 履歷 / subtask 樹 / dispatcher 過濾 inbox，在這兩份 spec 決定 UI 契約 |

### 不納入本次升級（defer）

| 項目 | 延後理由 |
|------|---------|
| `kind` enum (milestone/plan/task/subtask) | parent_task_id 存在與否 + goal entity 足以分層 |
| task `nature` tags (dev/review/research) | tags 或 description 可表達，優先級低 |
| Plan 升格 entity | 另走 ADR-028 Draft，不在本升級範圍 |
| Task template / recipe | 獨立討論 |
| Handoff 反向 rollback / revert 履歷 | 若需修正派工錯誤，append 新事件（reason="revert"），不刪除 |

---

## 2026-04-22 Task Ownership SSOT 收斂（最新覆寫）

> Decision source：ADR-044。本節是治理規則的人讀權威；runtime SSOT 在 `src/zenos/interface/governance_rules.py["task"]`。

### 層級結構（嚴格四層）

```
Milestone (= Goal entity, L3)     ← outcome anchor，type=goal 的 L3 entity
    ↑ linked_entities（選填）
Plan                              ← action layer primitive（grouping + sequencing + completion boundary）
    ↑ plan_id（選填）
Task                              ← action layer primitive
    ↑ parent_task_id（必填 for subtask）
Subtask                           ← Task with parent_task_id ≠ null
```

- **Milestone** = `type=goal, level=3` 的 L3 entity，透過 task.linked_entities 引用（不新增 entity type）
- **Plan** 是 action layer primitive，不是 entity
- **Task** 可以有 plan（屬於 plan 內的有序單位）或無 plan（ad-hoc task），但都必須有 product
- **Subtask** 必須有 parent task——不是孤兒，不能自行存在

### 三條繩子原則

Task 對外有且只有三條關聯繩子，各管各的，不可混用：

| 繩子 | 欄位 | Cardinality | 必填 | 語意 | 變更來源 |
|------|------|-------------|------|------|----------|
| **歸屬繩** | `product_id` (FK to L1 product entity) | 1:1 | ✅ **必填** | 「這 task 屬於哪個 **產品**」唯一 SSOT | caller 顯式傳入或 server 從 partner default 解析 |
| **編組繩** | `plan_id` + `parent_task_id` | 1:1 | 選填 | 「這 task 在哪個 plan / 是誰的 subtask」 | caller 傳入，subtask 必須繼承 parent.plan_id 與 parent.product_id |
| **知識繩** | `linked_entities` (N:N) | 0..3 | 建議 | 「這 task 跟哪些 L2 module / L3 milestone 有 ontology 關聯」純 context | caller 傳入，**禁止包含 type=product 的 entity** |

`product_id` 取代既有 `project_id` 欄位（schema rename，非新增）。Plans 表對齊改名為 `plans.product_id`。

### Schema 變更

| 欄位 | 型別 | 必填 | 變更 |
|------|------|------|------|
| `tasks.product_id` | text | ✅ NOT NULL | 從 `tasks.project_id` 改名而來；FK 指向 `entities(partner_id, id)` |
| `plans.product_id` | text | ✅ NOT NULL | 從 `plans.project_id` 改名而來；FK + 同樣 type 約束 |
| `tasks.project` | text | deprecated | 過渡期由 server 從 product entity.name 派生；caller 寫入會被 ignore + warning |
| `plans.project` | text | deprecated | 同上 |

### Server-side 寫入驗證（write / task action=create/update / handoff）

| 違規 | 處置 | error_code |
|------|------|------------|
| 沒傳 `product_id` 也無 `partner.defaultProject` 可解析 | reject | `MISSING_PRODUCT_ID` |
| `product_id` 指向不存在 entity | reject | `INVALID_PRODUCT_ID` |
| `product_id` 指向 type ≠ product 的 entity | reject | `INVALID_PRODUCT_ID` |
| `linked_entities` 包含 type=product 的 entity | strip + warning | `LINKED_ENTITIES_PRODUCT_STRIPPED` |
| 同時傳 `project` 字串和 `product_id` 但對不上 | 以 `product_id` 為準 + warning | `PROJECT_STRING_IGNORED` |
| subtask.product_id ≠ parent.product_id | reject | `CROSS_PRODUCT_SUBTASK` |
| task.product_id ≠ plan.product_id（若 task 有 plan_id） | reject | `CROSS_PRODUCT_PLAN_TASK` |
| subtask 的 parent_task_id 指向不存在 task | reject | `PARENT_NOT_FOUND` |

### Fallback 解析鏈（caller 沒傳 product_id 時）

按順序，全部失敗才 reject `MISSING_PRODUCT_ID`：

1. **partner.defaultProject 字串解析**：在當前 partner 範圍內找 `type='product'` 且 `LOWER(name) = LOWER(defaultProject)` 的 entity；取第一筆
2. **失敗** → reject。**不再 fallback first product entity**——猜錯比 reject 更危險

### linked_entities 的正確掛法（語意收緊）

`linked_entities` 僅放 **L2 module entity** 或 **L3 entity**（goal=milestone / document / role）：

- 1-3 個，不可超過
- 至少包含一個最相關的 L2 module（最強建議）
- Milestone 沿用 `Milestone (= Goal entity)` 規則，掛在這裡
- **不可包含 type=product entity**——歸屬已由 product_id 表達，重複放會被 server strip

### 查詢 Pattern（取代 linked_entities join）

| 場景 | Query |
|------|-------|
| 某 product 底下所有 task | `search(tasks, product_id=<product_id>)` 或 SQL `WHERE product_id = $1` |
| 某 milestone 下的所有 task | `search(tasks, linked_entity=<goal_id>)`（goal 在 linked_entities 內） |
| 某 plan 下的所有 task | `search(tasks, plan_id=<plan_id>)` |
| 某 task 的 subtask | `search(tasks, parent_task_id=<task_id>)` |
| 某 product 下的某 milestone 進度 | `search(tasks, product_id=X, linked_entity=<goal_id>)` |

`/projects/[id]` 產品頁的「任務」分頁 → 走 `product_id = entity_id`，**不再用 linked_entities join**。

### Migration（一次性 cut-over）

詳見 ADR-044 D8。要點：

1. Schema rename `project_id → product_id`
2. Backfill 順序：task_entities 中的 product entity → project 字串 entity name lookup → partner.defaultProject 解析 → first product entity 兜底（標 governance review）
3. 從 task_entities 移除已升格為 product_id 的 product entity（解除誤掛）
4. 加 NOT NULL constraint
5. 加 server-side validation
6. Deploy code changes

Backfill 兜底的 task 會 insert 一筆 `governance:review_product_assignment` tag，後台撈出來人工 review。

### 驗收條件（給 Developer / QA）

每條 AC 帶唯一 ID `AC-TOSC-NN`，對應 test stub 於：
- `tests/spec_compliance/test_task_ownership_ssot_ac.py`（backend）
- `dashboard/src/__tests__/task_ownership_ssot_ac.test.tsx`（frontend）

共 25 條 AC（AC-TOSC-01..25），涵蓋 Schema/Migration、Server Validation、Write Path、Read Path、Frontend、Deprecation、文件同步。

#### Schema / Migration（P0）

- **AC-TOSC-01**：migration 完成後，`tasks.product_id` 欄位存在（取代 `project_id`），有 `idx_tasks_partner_product_id` index 與 FK to `entities(partner_id, id)`。
- **AC-TOSC-02**：`plans.product_id` 同 AC-TOSC-01 完成改名，FK 與 index 對齊。
- **AC-TOSC-03**：migration 完成後，`SELECT COUNT(*) FROM tasks WHERE product_id IS NULL = 0`，且所有兜底 task 有 `governance:review_product_assignment` tag。
- **AC-TOSC-04**：`tasks.product_id` 與 `plans.product_id` 加上 `NOT NULL` constraint，違反時 DB 直接 reject。

#### Server Validation（P0）

- **AC-TOSC-05**：`task(action="create")` / `write(collection="tasks")` 沒傳 `product_id`，且 `partner.defaultProject` 解析無結果時，reject `MISSING_PRODUCT_ID`。
- **AC-TOSC-06**：`product_id` 指向不存在 entity 或 type ≠ product 的 entity 時，reject `INVALID_PRODUCT_ID`。
- **AC-TOSC-07**：`linked_entities` 含 type=product entity 時，server strip 並回傳 warning `LINKED_ENTITIES_PRODUCT_STRIPPED`，DB 不會寫入該關聯。
- **AC-TOSC-08**：同時傳 `project` 字串與 `product_id` 且 product entity.name ≠ project 字串時，以 `product_id` 為準並回傳 warning `PROJECT_STRING_IGNORED`。
- **AC-TOSC-09**：subtask 的 `product_id` ≠ parent task `product_id` 時，reject `CROSS_PRODUCT_SUBTASK`。
- **AC-TOSC-10**：task 有 `plan_id` 且 `task.product_id` ≠ `plan.product_id` 時，reject `CROSS_PRODUCT_PLAN_TASK`。
- **AC-TOSC-11**：caller 沒傳 `product_id` 但 `partner.defaultProject` 解析成功時，server 自動填入並回傳 task；audit log 記錄 `auto_resolved_product_id`。

#### Write Path 接通（P0）

- **AC-TOSC-12**：MCP `task(action="create", product_id=...)` 接受參數並寫入 DB；`task(action="update", id=..., product_id=...)` 同樣可用。
- **AC-TOSC-13**：MCP `plan(action="create", product_id=...)` 已存在，verify 改名後仍可用，且加上 type validation。
- **AC-TOSC-14**：Dashboard `POST /api/data/tasks` 接受 body 內 `product_id` 並寫入；`PATCH /api/data/tasks/{id}` 同樣可用。
- **AC-TOSC-15**：`ext_ingestion_api` 的 task 寫入路徑接受並驗證 `product_id`。

#### Read Path 改造（P0）

- **AC-TOSC-16**：`GET /api/data/tasks/by-entity/{entityId}` 當 entity.type=product 時走 `WHERE product_id = $entityId`；當 entity.type 為其他（goal / module）時走 task_entities join。
- **AC-TOSC-17**：MCP `search(tasks, product_id=X)` 純走 `product_id` 欄位，不再 fallback `project` 字串 match。
- **AC-TOSC-18**：Frontend 全域 `/tasks` 的 product filter 改用 `product_id`，顯示 product entity name。

#### Frontend（P0）

- **AC-TOSC-19**：UI 從產品頁 `/projects/[id]` 建 task 時，傳遞 `product_id = entity.id`，**不再** 偷塞 entity.id 進 `linked_entities`。
- **AC-TOSC-20**：`createTask` client 型別定義 `product_id: string` 為必填欄位（TypeScript 強制）。

#### Deprecation（P1）

- **AC-TOSC-21**：caller 寫入 `project` 字串欄位被 server ignore 並回傳 warning `PROJECT_STRING_IGNORED`；DB 內 project 字串由 server 從 product entity.name 自動派生。
- **AC-TOSC-22**：`src/zenos/interface/governance_rules.py["task"]` runtime SSOT 同步加上三條繩子原則 + 七條 server validation 規則（AC-TOSC-05..11）的 level 2 內容。

#### 文件 / 治理（P0）

- **AC-TOSC-23**：本節（2026-04-22 Task Ownership SSOT 收斂）已落入 `SPEC-task-governance.md`，且 `governance_guide(topic="task", level=2)` 回傳內容包含三條繩子原則與七條 validation 規則。
- **AC-TOSC-24**：`skills/governance/task-governance.md`、`skills/governance/shared-rules.md` 同步加註對齊本節（reference-only）。
- **AC-TOSC-25**：`SPEC-task-surface-reset`、`SPEC-project-progress-console` 加註腳對齊 product_id query contract，無語意衝突。

### 下游 SSOT 同步清單

| # | 位置 | 變更 |
|---|------|------|
| 1 | `src/zenos/infrastructure/action/sql_task_repo.py` | UPSERT / SELECT / search 改 `product_id` 命名；加 type validation 步驟（透過 service 層） |
| 2 | `src/zenos/infrastructure/action/sql_plan_repo.py` | 同上 |
| 3 | `src/zenos/domain/action/models.py` | `Task.project_id` → `Task.product_id`；`Plan.project_id` → `Plan.product_id` |
| 4 | `src/zenos/application/action/task_service.py` | create/update 處理 product_id；加 server validation 全集 |
| 5 | `src/zenos/application/action/plan_service.py` | 同上 |
| 6 | `src/zenos/interface/mcp/task.py` | `_task_handler` signature 加 `product_id` 參數；docstring 更新 |
| 7 | `src/zenos/interface/mcp/plan.py` | 改名 `project_id` 參數為 `product_id`，docstring 更新 |
| 8 | `src/zenos/interface/mcp/search.py` | tasks search 的 product/product_id 過濾純走 `product_id` |
| 9 | `src/zenos/interface/dashboard_api.py` | create_task / update_task 白名單加 `product_id`；`list_tasks_by_entity` 改造 |
| 10 | `src/zenos/interface/ext_ingestion_api.py` | 接受並驗證 `product_id` |
| 11 | `src/zenos/interface/governance_rules.py["task"]` | 加三條繩子原則 + 七條 validation level 2 內容 |
| 12 | `dashboard/src/lib/api.ts` | createTask / updateTask 型別加 `product_id` 必填 |
| 13 | `dashboard/src/app/(protected)/projects/page.tsx` | 建 task 改傳 `product_id`，移除 linked_entities 偷塞 hack |
| 14 | `dashboard/src/app/(protected)/tasks/page.tsx` | filter 改 `product_id` |
| 15 | `dashboard/src/features/tasks/taskHub.ts` | `plan.project_id` 引用改 `plan.product_id` |
| 16 | `skills/governance/task-governance.md` | 同步治理規則 v2.2（reference-only） |
| 17 | `skills/governance/shared-rules.md` | 同上 |

---

## 2026-03-31 Task 附件支援（最新增補）

Task 支援在建立與更新時附加三種媒體類型，統一存於 `attachments` 欄位。

### 附件資料模型

每個附件為一個 object，schema 如下：

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `id` | string | 系統產生 | 附件唯一識別碼 |
| `type` | enum | 是 | `"image"` / `"file"` / `"link"` |
| `name` | string | 是 | 顯示名稱（圖片/檔案用原始檔名，連結用標題） |
| `gcs_path` | string | `image`/`file` 必填 | GCS object path，格式：`tasks/{task_id}/attachments/{id}/{filename}` |
| `external_url` | string | `link` 必填 | 外部連結 URL |
| `mime_type` | string | `image`/`file` 必填 | MIME type（如 `image/png`、`application/pdf`） |
| `size_bytes` | number | `image`/`file` 選填 | 檔案大小（bytes） |
| `uploaded_by` | string | 系統產生 | 上傳者 `partner.id`，由 server 從 auth context 覆寫，不信任 caller 傳入 |
| `created_at` | datetime | 系統產生 | 附件建立時間 |

`attachments` 欄位掛在 task 根層，型別為 `attachment[]`，預設空陣列。
DB（Cloud SQL）以 **JSONB 欄位**存於 `tasks` table，需補 migration：`ALTER TABLE tasks ADD COLUMN attachments JSONB DEFAULT '[]'`。

### 儲存與存取規則

- `type = "image"` 或 `type = "file"`：DB 存 `gcs_path`（永久有效）。前端**不直接存取 GCS**，一律透過 ZenOS server proxy 取得檔案。
- `type = "link"`：只存 `external_url` metadata，不存 GCS。
- **嚴禁**在 DB 存 GCS signed URL。

### 檔案存取：ZenOS Server Proxy

所有 `image` / `file` 類附件的存取統一走 ZenOS proxy endpoint：

```
GET /attachments/{attachment_id}
  → server 驗證 caller 對該 task 的讀取權限
  → 從 GCS 串流回傳檔案內容
  → URL 永不過期，存取控制完全在 ZenOS 手上
```

前端顯示圖片時使用 `/attachments/{attachment_id}` 作為 `src`，不使用 GCS URL。

### 上傳路徑

#### `type = "link"`（直接帶入）

`task(action="create/update")` 可直接在 `attachments` 陣列中帶入：

```json
{ "type": "link", "name": "設計稿參考", "external_url": "https://..." }
```

#### `type = "image"` / `type = "file"`（兩條路徑）

**路徑一：Agent（MCP inline upload，≤ 5 MB）**

agent 將檔案 base64 編碼後，呼叫 `upload_attachment` MCP tool：

```
輸入：
  task_id: string          目標 task ID（必須已存在，不支援 pending）
  filename: string
  mime_type: string
  base64_content: string   原始 binary 的 base64 編碼
輸出：
  attachment_id: string
  proxy_url: string        /attachments/{attachment_id}（永久有效）
```

server 收到後解碼並上傳至 GCS，回傳 proxy URL。

> 超過 5 MB 的檔案 agent 無法透過 MCP 上傳，需由用戶在 Dashboard UI 操作。

**路徑二：UI（前端直傳 GCS，任意大小）**

Step 1：呼叫 `upload_attachment` MCP tool 或等價 API，不帶 `base64_content`，取得 signed upload URL：

```
輸入：task_id, filename, mime_type, size_bytes
輸出：attachment_id, upload_url（GCS signed PUT URL，15 分鐘有效）, proxy_url
```

Step 2：前端直接 `HTTP PUT` binary 至 `upload_url`（不過 ZenOS server）。
Step 3：上傳成功後，將 `{ type, name, attachment_id }` 帶入 `task(action="create/update")` 的 `attachments`。

> GCS bucket 須設定 CORS，允許 Dashboard origin 的 PUT 請求。

### 更新與刪除附件

- **更新**：`task(action="update")` 的 `attachments` 採**全量覆寫**語意——傳入陣列完整取代現有內容；需保留舊附件時，caller 必須在陣列中包含舊附件 objects（含原始 `id`）。
  - **Known limitation（Phase 1）**：並發寫入可能導致後者覆蓋前者。用戶量小可接受，Phase 2 加 patch 語意（`add` / `remove`）。
- **刪除**：從陣列移除對應 object 後呼叫 update；server 在 update handler 內同步刪除 GCS 物件（失敗只 log warning，不阻擋 task update）。

### UI 行為

1. 建立 task 時，可上傳圖片、上傳檔案、貼入外部連結。
2. 建立後，task 詳情頁可新增、替換、移除任一附件。
3. 圖片類附件 inline preview（src 指向 `/attachments/{id}`）；非圖片檔案顯示下載連結；外部連結顯示可點擊標題。
4. 附件操作（新增 / 移除）須即時反映在 `updated_at`。

### 限制（Phase 1）

- 單一 task 附件數量上限：**20 個**。
- MCP inline upload 上限：**5 MB**（超過需走 UI 路徑）。
- 圖片單檔大小上限：**10 MB**。
- 一般檔案單檔大小上限：**50 MB**。
- 不支援附件版本歷程（Phase 2 再議）。

---

## 2026-03-31 狀態模型簡化（最新覆寫）

本節覆寫舊版 `backlog/blocked/archived` 設計，從即日起 task 狀態以以下五態為準：

- `todo`
- `in_progress`
- `review`
- `done`
- `cancelled`

語義調整：

- `backlog` 併入 `todo`
- `blocked` 移除（阻塞資訊保留在 `blocked_by` / `blocked_reason`，不再作為狀態）
- `archived` 併入 `done`

治理規則同步調整：

- 建票初始狀態只能是 `todo`
- 驗收通過後進入 `done`
- `done` / `cancelled` 為終態（需重做請開新票）

## 2026-03-31 Task 欄位定義（最新覆寫）

本節為 Task schema 的欄位權威定義，覆寫本文件其餘舊描述中的衝突內容。

| 欄位 | 型別 | 必填 | 定義 | 備註 |
|------|------|------|------|------|
| `id` | string | 系統產生 | task 識別碼 | create 不需傳 |
| `title` | string | 是 | 任務標題，動詞開頭 | 單一 outcome |
| `description` | string | 建議 | 背景/問題/期望結果 | Server 會自動解析並重新格式化為結構化 Markdown，原始格式不保留 |
| `status` | enum | 是 | `todo`/`in_progress`/`review`/`done`/`cancelled` | create 初始只能 `todo` |
| `priority` | enum | 是 | `critical`/`high`/`medium`/`low` | 不傳由 server 推薦 |
| `acceptance_criteria` | string[] | 建議 | 驗收條件（2-5 條） | 可觀察、可驗收 |
| `linked_entities` | string[] | 建議 | ontology 關聯節點 IDs | 建議 1-3 個 |
| `assignee` | string \| null | 否 | 執行責任人（partner.id） | 可用 `assignee_role_id` 輔助 |
| `assignee_role_id` | string \| null | 否 | 角色節點 ID | 用於角色責任落點 |
| `owner` | string | 衍生欄位 | 任務治理 owner | 由 `created_by` 對應，不另存欄位 |
| `created_by` | string | 是 | 建立者 partner.id（= owner） | MCP 以 API key partner 覆寫 |
| `source_metadata.created_via_agent` | bool | 建議 | 是否由 agent 代開 | UI 顯示 `agent (by <owner>)` |
| `source_metadata.agent_name` | string | 建議 | agent 名稱 | `created_via_agent=true` 建議帶入 |
| `plan_id` | string \| null | 條件必填 | 所屬 plan 識別 | 有 plan task 時必填 |
| `plan_order` | int \| null | 條件必填 | plan 內順序（>=1） | `plan_id` 存在時必填 |
| `depends_on_task_ids` | string[] | 否 | 前置依賴 task IDs | 非線性流程用 |
| `blocked_by` | string[] | 否 | 阻塞來源 task IDs | 阻塞資訊，不是狀態 |
| `blocked_reason` | string \| null | 否 | 阻塞說明 | 與 `blocked_by` 搭配 |
| `result` | string \| null | 條件必填 | 完成產出摘要 | 進 `review` 前必填 |
| `created_at` | datetime | 系統產生 | 建立時間 | UTC |
| `updated_at` | datetime | 系統產生 | 最後更新時間 | UTC |
| `updated_by` | string \| null | 否（預留） | 最後更新人 partner.id | 現階段可由 audit log 補足；後續可升級為正式欄位 |
| `completed_at` | datetime \| null | 否 | 完成時間 | `done` 時應有值 |
| `attachments` | attachment[] | 否 | 附件列表（圖片 / 檔案 / 連結） | 詳見「Task 附件支援」章節 |

> **治理定位：External（Task 治理模組）**
> 本 spec 定義 agent 和用戶在建立與管理 task 時必須遵循的規則。屬於可疊加的 Task 治理模組，可獨立於 Doc 治理模組啟用。
> 規則內容透過 `governance_guide("task")` 提供給任何 MCP client。
>
> **SSOT note（ADR-038）：** Agent runtime 取得治理規則的 SSOT 是 `governance_guide(topic="task", level=2)` MCP tool。本 spec 是人讀權威；`skills/governance/task-governance.md` 和 `skills/governance/shared-rules.md` 已降為 reference-only（可能落後於 SSOT）。Spec 修訂必須同步更新 `src/zenos/interface/governance_rules.py["task"]`，否則不得轉 `Approved`（見 `SPEC-governance-guide-contract` AC-P0-4-*）。
> 內部智慧邏輯（task 信號→blindspot 轉換、linked_entities 推薦、anti-pattern 偵測）不在本 spec 範圍，見 `SPEC-governance-feedback-loop`。
> 框架歸屬見 `SPEC-governance-framework` 治理功能索引。
>
> **分散治理模型（ADR-013）：** 本 spec 的規則分兩層執行——Agent 端負責撰寫 title / description / AC；Server 端負責動詞開頭檢查（reject）、AC 數量提醒（warning）、去重（回傳 similar）、linked_entities 存在性（reject）、狀態機強制（reject）、review 時 result 必填（reject）、知識反饋建議（suggested_feedback）。Server 端執法無法被 Agent 繞過。

## 背景與動機

ZenOS 的 Action Layer 已經有資料模型、MCP function、狀態流與 priority recommendation。

但目前「怎麼開一張好票」仍缺少治理規範，造成幾個實際問題：

- agent 開票風格不一致，有的像 bug report，有的像設計 memo，有的只是一句提醒
- task 粒度不一致，有的過大像 epic，有的過小像 checklist item
- `linked_entities` 掛法不一致，有的完全沒掛，有的亂掛一串，導致 context summary 品質不穩
- 有些本來應先寫 spec / ADR / blindspot 的問題，被直接開成 implementation task
- backlog 容易出現重複票、孤兒票、無法驗收票

L2 治理已經定義「公司共識概念怎麼長成 stable ontology」；L3 文件治理也開始成形；但 Task Layer 目前仍停留在「有架構、缺規範」。

本 spec 的目標，是把任務管理從資料結構提升成治理規範，讓 agent 與人都能用一致方式開票、派工、驗收。

---

## 目標

1. 定義什麼情況應該開 task，什麼情況不應該。
2. 定義 task 的標準粒度，避免過大、過小或不可驗收。
3. 定義 agent 建票時的最小必填品質，涵蓋 `title`、`description`、`acceptance_criteria`、`linked_entities`、`priority`、`status`、`owner/assignee`、`result` 共八個欄位。
4. 讓 task 與 ontology 的連結穩定可用，而不是形式上有欄位、實際上沒有治理價值。
5. 讓 `task` MCP function 成為一致的治理入口，而不是各 agent 各自發明 ticket style。

---

## 非目標

- 不在這份 spec 裡重新定義 Kanban 狀態機本身。
- 不處理 sprint、工時、story point、velocity 等專案管理制度。
- 不要求 task 取代 spec、ADR、blindspot、document entity。
- 不處理 agent 內部私有 subtask 或個人 TODO 列表。

---

## Task 的治理定位

ZenOS 三層目前可簡化理解為：

- L2 治理：公司共識概念的穩定骨架
- L3 治理：文件與來源路徑、metadata、ontology linkage 的穩定治理
- Plan 治理：同一目標下 task 群的執行脈絡與進度治理
- Task 治理：從知識導出行動，並把行動結果再反饋回知識層

因此 task 不是一般待辦事項，而是：

- 有知識脈絡的行動單位
- 可被指派與驗收的工作邊界
- 驗證 ontology 是否真的能支撐行動的最小單位

Task 開得太鬆，Action Layer 會退化成雜項待辦清單；
Task 開得太硬，agent 會繞過 ZenOS 回到外部工具或私有筆記。

---

## Plan 層定義（新增）

Plan 是 `ZenOS Core Action Layer` 中的 task 群治理容器，不是額外的長文件層，也不是 application-specific PM UX。

定位：

- `SPEC`：定義 what/why/boundary
- `PLAN`：把同一交付目標下的多張 task 綁成可管理的執行脈絡
- `TASK`：可指派、可驗收的最小行動單位

Plan 必須至少定義以下欄位（可透過 task metadata 或等價方式表達）：

1. `plan_id`：同一計畫群組唯一識別
2. `goal`：計畫目標（一句話）
3. `owner`：計畫責任人
4. `entry_criteria`：何時可啟動
5. `exit_criteria`：何時可結案
6. `status`：計畫狀態（例如 draft / active / completed / cancelled）

Plan 強制規則：

1. 每張 task 必須可追溯到所屬 `spec_id`（或等價治理節點）。
2. 需要跨多張 task 才能交付的工作，必須掛在同一 `plan_id` 下，不得散落為孤兒票。
3. Plan 狀態不得由單張 task 直接隱式推斷，必須有明確 owner 判定。
4. Plan 完成時必須提供彙總證據（至少包含完成範圍、未完成項、風險與後續建議）。
5. Plan 不得取代 task 驗收；task 仍需逐張滿足 acceptance criteria。

### 派工邊界（新增）

為避免跨 agent 派工歧義，必須採用以下邊界：

1. Plan 不可直接派工，Task 才是唯一可 claim 的執行單位。
2. agent 不得直接接收「執行某 Plan」指令；必須接收具體 task。
3. task 若屬於某 plan，必須可回查同 plan 的上下文與順序資訊。
4. owner / dispatcher 不得用 plan 狀態取代 task 驗收結果。

---

## Task Schema 擴充要求（新增）

為支援 Plan 層協作與正確執行順序，Task 層資料定義必須擴充：

### 必填（當 task 屬於某 plan 時）

- `plan_id`：所屬 task group 識別
- `plan_order`：同一 plan 內的執行順序（整數，從小到大）

### 選填（建議）

- `depends_on_task_ids`：明確前置依賴（用於非線性流程）

### 行為規則

1. agent 領到 task 後，若有 `plan_id`，必須能拉出同組 task。
2. agent 執行前必須先檢查順序與依賴是否滿足。
3. 前置未完成時，不得把後續 task 推進到可執行狀態。
4. 同一 plan 內不得存在衝突順序（重複 `plan_order` 且語意互斥）。
5. 缺少順序資訊的 plan task，不得自動派發給 execution agent。

### 與 L2 / L3 的權責邊界（防重複治理）

本 spec 是 `ZenOS Core Action Layer` 的權威規範，不重寫 L2 或 L3 規則。三層分工如下：

| 治理面向 | 權威文件 | 本 spec 行為 |
|---------|----------|--------------|
| L2 概念升級 / impacts gate | `SPEC-l2-entity-redefinition` | 僅引用，不重定義 |
| 文件分類 / frontmatter / supersede / archive | `SPEC-doc-governance` | 僅引用，不重定義 |
| Task 建票品質 / 粒度 / 去重 / 驗收 | `SPEC-task-governance` | 完整定義 |

任何「新治理原則」或「文件生命週期規則」若還在定義 what/why/boundary，必須先落到 SPEC/ADR/TD；Task 只承接可指派、可驗收的執行邊界。application-specific subtask / checklist / private execution step 不得直接擴張本 spec 的 Task 定義。

---

## Task 生命週期（Lifecycle State Machine）

本 spec 不重新發明 Kanban 狀態集，但必須定義每個狀態轉換的**治理條件**——不是「技術上可以轉」，而是「治理上允許轉」。

### 狀態定義

| 狀態 | 意義 | 是否可接受為初始狀態 |
|------|------|---------------------|
| `todo` | 已排入執行，等待認領 | ✅ |
| `in_progress` | 有人正在執行 | ❌（不得在建票時直接設定） |
| `review` | 執行完成，等待驗收 | ❌ |
| `done` | 驗收通過，工作完成 | ❌ |
| `cancelled` | 不再需要執行 | ❌ |

### 合法轉換與治理條件

```
  todo ──────────────→ in_progress ──────────────→ review
   │                      │                           │
   │                      └─────────────→ cancelled   ├────────→ done
   └────────────────────────────────────→ cancelled   └────────→ in_progress（退回修正）
```

| 轉換 | 治理條件 |
|------|---------|
| `todo → in_progress` | 有明確 assignee |
| `in_progress → review` | `result` 或 `Result:` 區塊已填寫完成輸出 |
| `review → done` | AC 逐條驗收通過 + 知識反饋已完成（若適用） |
| `review → in_progress` | 驗收未通過，退回修正，記錄退回原因 |
| 任何活躍狀態 → `cancelled` | 記錄取消原因；若有替代票，標記 `[Superseded by: TASK-XXX]` |

### 終態

- `done`：工作完成且驗收通過。
- `cancelled`：不再執行。不可復活，若需重做應開新票。

---

## 衝突仲裁（Conflict Resolution）

### 跨 Spec 衝突

本 spec 治理 Task（Action Layer）。當與其他治理 spec 發生衝突時：

1. 依憲法（`docs/spec.md`）第二節第⑥維度的通用仲裁順序處理。
2. 本 spec 不得覆寫 L2 升降級規則（`SPEC-l2-entity-redefinition` 權威）。
3. 本 spec 不得覆寫 L3 文件生命週期與 sync contract（`SPEC-doc-governance` 權威）。
4. 若 task 的 linked_entities 指向某 L2，而該 L2 的治理狀態與 task 預期矛盾（例如 task 要修改一個已 stale 的 L2），應先處理 L2 狀態，再執行 task。

### 與 Plan 層的衝突

- Plan 完成判定不得覆蓋 task 逐張驗收結果。
- Task 驗收標準（AC）以本 spec 為準，Plan 的 exit_criteria 不得放寬 task 驗收。

---

## 什麼時候應該開 Task

應開 task 的情境：

- 已經有明確後續動作需要被指派、追蹤、驗收
- 某個 blindspot 需要形成具體處置
- 某份 spec / design / doc 已有明確 implementation follow-up
- 某個治理缺口需要人或 agent 實際修補
- 某項工作完成與否，會影響其他任務、文件或知識節點

不應直接開 task 的情境：

- 問題還停留在「要不要這樣做」的決策階段
- 內容本質上是新規格、新決策、新治理原則，應先寫 spec / ADR
- 內容只是知識沉澱，沒有具體 owner / outcome / verification boundary
- 內容只是執行者自己的短期 checklist，不需要跨人協作或驗收

判斷原則：

- 如果內容需要「誰來做、做到哪裡算完成」，開 task
- 如果內容需要「先定義規則或方向」，先寫 spec / ADR
- 如果內容是「系統看到一個缺口」，先記 blindspot，再視情況轉成 task

---

## Task 粒度規則

一張 task 必須同時滿足以下三點：

1. **單一主要 outcome**
   同一張 task 應對應一個主要產出或狀態改變，不應混多個彼此可獨立驗收的結果。

2. **單一主要 owner**
   雖然可以協作，但 task 應有一個主要 assignee 或可明確指派的責任落點。

3. **單一驗收邊界**
   驗收者應能用 2-5 條 acceptance criteria 判斷是否完成，而不是再拆解整個專案。

過大的 task：

- 橫跨 spec、implementation、migration、QA 全流程
- 同時包含多個子系統或多種 deliverable
- acceptance criteria 寫成 roadmap

過小的 task：

- 只是某張 task 的內部一步
- 只是「查一下」「看一下」「想一下」且沒有穩定產出
- 完成後不需要任何人驗收

實務準則：

- 需要不同人接手時，拆票
- 需要不同驗收邊界時，拆票
- 需要不同 ontology context 才講得清楚時，拆票

---

## Task 與 Spec / Blindspot / Document 的分工

| 類型 | 用途 | 何時先做 |
|------|------|----------|
| `SPEC` / `ADR` / `TD` | 定義規則、方向、設計 | 還在定義 what / why / boundary 時 |
| `Blindspot` | 記錄缺口、風險、未知問題 | 還沒有明確 owner / 執行方案時 |
| `Task` | 指派可驗收的行動 | 已知道要做什麼、誰應接手、怎麼算完成 |
| `Document update` | 沉澱或修正文檔本身 | 本質只是更新知識而非派工時 |

轉換關係：

- blindspot 可以產生 task
- spec / design 可以產生 implementation task
- task 完成可能反寫 document / blindspot / entity 狀態

但 task 不應拿來取代 spec 或 blindspot 本身。

---

## Draft 文件半自動審核流程（新增）

本流程適用於「不用 API key 常駐 worker、以 CLI/UI agent 為主」的半自動模式。

### 角色與責任

- `reviewer`：找出待審文章、輸出審核意見、做通過/退回判定
- `editor`：依審核意見修改文章並回填修正證據
- `owner`：最終確認是否離開 draft

### 標準狀態流

`draft`（文章） -> `todo/in_progress`（審核 task） -> `review`（待 owner） -> `confirmed`（文章離開 draft）或退回循環

### 強制規則

1. 新 draft 文章必須對應至少一張 open 審核 task。
2. 審核 task 必須有責任落點，優先使用 `assignee_role_id`，不得無 owner。
3. reviewer 送審前必須在 `result`（或 fallback `Result:` 區塊）提供可驗收輸出。
4. editor 修改後必須附修正證據（文件連結、commit、變更摘要至少其一）。
5. owner 未確認前，文件不得離開 draft。
6. owner 退回時必須記錄退回原因與下一步責任人。

---

## 建票最小規範

### 1. title

必須：

- 動詞開頭
- 單一行動邊界
- 不寫成會議紀錄或抽象主題

好例子：

- `修復 documents.update 的 merge 語意`
- `設計文件治理 sync API`
- `補上 task.update 對 linked_entities 的覆寫支援`

差例子：

- `documents 問題`
- `Barry 說這個怪怪的`
- `整理一下治理`

### 2. description

至少應包含三件事：

- 背景：為什麼需要這張票
- 問題：現在缺什麼或壞在哪
- 期望結果：完成後應解決什麼

不要把 description 寫成 acceptance criteria 的重複版本，也不要只寫一句模糊摘要。

### 3. acceptance_criteria

應為 2-5 條可觀察、可驗收的完成條件。

每條都應該是：

- 外顯結果
- 可測試或可確認
- 與該 task 的主要 outcome 直接相關

不要寫成：

- 純過程性步驟
- roadmap 願景
- 模糊願望句

### 4. linked_entities

`linked_entities` 不是裝飾欄位。它決定：

- task 的 ontology context
- priority recommendation 的輸入
- context summary 的品質
- 後續 search / routing / governance review 的可用性

因此 agent 建票時應遵循以下規則：

1. 至少掛 **1 個主要治理節點**，最多通常 **3 個**。
2. 第一優先掛「最直接受影響的概念」，不是隨便掛產品根節點湊數。
3. 若工作同時涉及產品層與子模組層，可掛：
   - 一個產品 / 上位模組
   - 一個直接受影響模組
   - 一個治理或介面節點（如文件治理、MCP 介面設計）
4. 不要把所有看過的節點都塞進去。
5. 若目前找不到穩定對應節點，應先承認 ontology gap，而不是亂掛。此時應在 description 中標注 `[Ontology Gap: 缺少 XXX 對應節點]`，若問題較嚴重可另記 blindspot；linked_entities 維持最少掛點或暫不填，不要為了填滿而亂掛。

推薦上限：

- 1 個：單點修補
- 2 個：主要功能 + 治理/依賴面
- 3 個：跨層但仍可清楚說明的工作
- 4 個以上：通常表示粒度太大或理解未收斂

### 5. priority

若沒有強理由，優先讓 server 推薦。

`task(action="create")` 未傳 `priority` 時，應由 server recommendation 寫入最終 priority。
caller 不應預設會是固定值（如永遠 `medium`）。

只有在以下情境建議 caller 明示覆蓋：

- 已知商業時程不可延誤
- 已知外部依賴要求更高或更低優先度
- 需要刻意保留某張票在 backlog，不讓規則引擎升級

### 6. status

建票時只應使用：`todo`

Agent 不應在 create 時直接假設：

- `in_progress`
- `review`
- `done`

除非是工具在合法規則下自動推導。

### 7. owner / assignee

`assignee` 在 schema 中可為選填，但治理上不得沒有責任落點。

建票時必須滿足其一：

- 直接填入 `assignee`
- 未能立即指派時，在 `description` 明確記錄預期 owner（人名或角色）與指派條件

禁止建立「owner 未定且無指派條件」的 task。

### 9. 建立者顯示與身份追溯（簡化版）

為避免建立者顯示混亂，統一採兩層語意：

1. `created_by`：永遠是 owner 的 `partner.id`（不是 agent 名稱）。
2. `source_metadata.created_via_agent` + `source_metadata.agent_name`：只描述是否由 agent 代開與 agent 身份。

硬性規則（server side）：

1. MCP `task(action="create")` 進入時，若可解析 partner context，`created_by` 最終值必須是該 `partner.id`。
2. partner context 存在時，server 忽略 caller 傳入的任意 `created_by`。
3. 無 partner context 時，不得建立 task。
4. `created_via_agent=true` 時，應寫入 `agent_name`（可用 `"agent"` 兜底）。

前端顯示規則（固定）：

- 永遠顯示 owner 名稱（由 `created_by -> partner.display_name` 解析）。
- 若 `created_via_agent=true`，顯示：`agent (by <owner_name>)`。

### 8. result（完成輸出落點）

進入 `review` 前，必須有可供驗收的完成輸出。

- 若流程有 `result` 欄位：在 `result` 明確記錄產出、影響範圍、知識反饋
- 若當前工具流尚未穩定使用 `result`：在 `description` 末尾追加 `Result:` 區塊，並附關聯文件或變更連結

驗收者必須能在 task 上直接找到這份完成輸出，否則不應通過。

---

## Agent 建票流程

所有 agent 開票前，必須遵循這個順序：

1. 先查是否已有同類 open task
   用 `search(collection="tasks", status="todo,in_progress,review")` 避免重複票（排除 cancelled / done）。

2. 確認這件事是 task，不是 spec / blindspot / doc update

3. 選 1-3 個最合適的 `linked_entities`
   不確定時，寧可少掛，不要亂掛。

4. 寫出單一 outcome 的 title

5. 補齊能被驗收的 description 與 acceptance criteria

6. 再呼叫 `task(action="create")`

標準心法：

- 先去重
- 再定類型
- 再選 context
- 最後才建票

---

## 推薦的 linked_entities 掛法

### 類型 A：單點實作修補

掛：

- 直接受影響模組
- 如有必要，再加上一個直接相關的治理或介面節點

不要為了「看起來比較完整」而附帶產品根節點。

例：

- 修 MCP task update bug
  - `MCP 介面設計`
  - `Action Layer` / `Task dispatch` 類直接受影響模組（若 ontology 已有）

### 類型 B：治理規則或治理流程

掛：

- 產品根節點
- 對應治理模組
- 如涉及接口，再加 MCP 模組

例：

- 規範文件治理 sync
  - `ZenOS`
  - `文件治理`
  - `MCP 介面設計`

Type A / B 的判斷原則：

- 主要驗收在「程式或資料行為修補」時，歸類 Type A
- 主要驗收在「治理規則、流程、文件契約變更」時，歸類 Type B
- 若同時成立且難以單票驗收，必須拆成兩張票

### 類型 C：跨層架構設計

掛：

- 上位產品 / 系統
- 最直接的 app layer / module
- 一個主要被 impacts 的治理或界面節點

不要同時塞一整串平級模組。

例：

- 設計 L2 語意推導 → Task 優先度推薦演算法
  - `ZenOS`（上位產品）
  - `Action Layer`（最直接受影響的 module）
  - `語意治理`（主要被 impacts 的治理節點）

---

## 不一致與反模式

以下都是需要避免的 task 反模式：

### 1. 孤兒票

- 沒有 `linked_entities`
- description 太短，無法知道上下文
- acceptance criteria 缺失

### 2. 假連結票

- `linked_entities` 只是為了填欄位而掛
- 掛一堆 entity 但 description 根本沒提到它們

### 3. 混合型票

- 同一張票同時要求寫 spec、做實作、跑 migration、補測試、做驗收

### 4. 提醒型票

- 內容只是「記得之後看這個」
- 沒有 owner、沒有邊界、沒有完成條件

### 5. 重複票

- 同一問題開了多張 backlog
- 舊票沒取消、沒標 superseded，就直接再開一張

---

## 重複票與 supersede 規則

當發現既有 task 已涵蓋同一主要 outcome：

- 優先更新既有 task，而不是重開

當新票是更正確的收斂版本：

- 建新票
- 將舊票標記 `cancelled`
- 在 description 末尾附註 `[Superseded by: TASK-XXX]`
- 若後續 MCP schema 支援正式欄位，應改用 `superseded_by`

禁止：

- 讓多張 open task 代表同一件事，只差 wording

---

## Governance 檢查清單

建立 task 前，至少過這 8 題：

1. 這件事真的是 task，不是 spec / blindspot / doc update 嗎？
2. 這張票只有一個主要 outcome 嗎？
3. 這張票有清楚 owner / assignee（或明確指派條件）嗎？
4. 這張票能用 2-5 條 acceptance criteria 驗收嗎？
5. `linked_entities` 真的是最相關的 1-3 個節點嗎？
6. title 是否動詞開頭且描述單一行動？
7. description 是否交代背景、問題、期望結果？
8. backlog 裡確認沒有重複票嗎？

若有 2 題以上答案為否，不應直接建票。

---

## 去重規則

`search(collection="tasks", status="todo,in_progress,review")` 不是形式上的前置步驟，應至少檢查以下三個面向（搜尋範圍排除 `cancelled` / `done`）：

1. `title` 是否描述同一主要 outcome
2. `description` 是否在處理同一問題邊界
3. `linked_entities` 是否指向同一組核心治理節點

實務判斷順序：

- 先用主要名詞或模組名搜 title 關鍵字
- 再用核心問題詞搜 description
- 最後比對候選票的 `linked_entities` 與 acceptance criteria

可視為重複票的最小條件：

- 主要 outcome 相同
- 核心 ontology context 高度重疊
- 驗收邊界相近

若只是同一大主題下的不同驗收邊界，不算重複票。

draft 審核任務另加去重鍵：

- `doc_id + review_round` 為同一輪審核唯一鍵
- 同一輪不得存在多張 open 審核 task
- 重開審核必須遞增 `review_round` 並保留前一輪結果

---

## Task 完成後的知識反饋

Task 治理不是單向派工。以下情境完成後，應觸發知識層反饋：

- 修正文檔或 source path 的 task
  - 應同步更新對應 document entity 或文件治理狀態
- 處理 blindspot 的 task
  - 驗收通過後應關閉或更新對應 blindspot
- 補齊規格 / 規則 / 介面設計的 task
  - 應將產出沉澱回受治理文件，而不是只把 task 標 done
- 修補 ontology / MCP 行為的 task
  - 若改變了規則或 contract，應更新對應 spec / reference

責任分工：

- 執行者負責在 `result` 或 `description` 的 `Result:` 區塊中說明產出與受影響知識
- 驗收者負責確認這些知識反饋已完成，才應通過 task
- server 後續可逐步自動化部分反寫，但在機制完整前，不得假設 `done` 自動等於知識已同步

因此，若 task 的完成會改變知識層，acceptance criteria 應至少有一條明確要求相關文檔、blindspot 或 entity 狀態已同步。

若 task 屬於不改變知識層的純行動類（如訪談客戶、確認外部 quota），知識反饋可簡化為：在 result 或 description 的 `Result:` 區塊記錄結論摘要，無需強制更新文件或 entity。

針對 draft 文件審核，知識反饋必須包含：

- 審核摘要（可給 owner 快速判斷）
- 審核結論（建議通過 / 建議退回）
- 文章連結與審核證據連結
- 若需修改，列出必修項目

---

## Task 治理客製化邊界

與 L2 治理一致，Task 治理的規則分為 **server 硬編碼**（不可由用戶調整）與 **用戶可客製**（可由 partner 或 agent 調整的參數）。

### Server 硬編碼（不可調整）

| 規則 | 原因 |
|------|------|
| 建票初始狀態只能是 `todo` | 防止 agent 跳過排程直接推進狀態 |
| `linked_entities` 至少 1 個 | 確保 task 有 ontology context，priority recommendation 才有輸入 |
| 去重搜尋為建票前必要步驟 | 防止 backlog 重複膨脹；search 由 caller 執行，server 提供 API |
| `review → done` 需 AC 逐條通過 | 驗收是治理閉環的最小保證 |
| 終態（`done` / `cancelled`）不可復活 | 需重做應開新票，保留歷史完整性 |
| Plan 不可直接派工，Task 是唯一可 claim 的執行單位 | 派工粒度必須可驗收 |

### 用戶可客製（建議範圍）

| 維度 | 預設 | 可調範圍 | 調整方式 |
|------|------|---------|---------|
| AC 條數範圍 | 2-5 條 | 1-10 條 | agent 層級設定 |
| `linked_entities` 上限 | 3 個（建議） | 1-5 個 | agent 層級設定；超過 5 個通常意味粒度太大 |
| 8 題 checklist 嚴格度 | ≥6 題通過才建票 | ≥4 題即可（寬鬆模式） | agent 層級設定 |
| priority 覆蓋策略 | 不傳則 server 推薦 | 永遠由 caller 指定 | agent 層級設定 |
| 知識反饋強制度 | 改變知識層的 task 必須有反饋 AC | 所有 task 都強制 | partner 層級設定 |
| Draft 審核角色分工 | reviewer + editor + owner 三角色 | reviewer + owner 兩角色（合併 editor） | partner 層級設定 |

### 客製化光譜

```
不可調                                                    可調
├──────────────────────────────────┤
│ 初始狀態限制  終態不復活  去重必要 │  AC 條數  掛點上限  checklist 門檻
│ 至少 1 linked  AC 逐條驗收       │  priority 策略  反饋強制度  審核角色
│ Plan 不派工                      │
└──────────────────────────────────┘
  server 強制                         agent / partner 可配
```

---

## 對 MCP 與未來實作的要求

若要讓 task 治理真正成立，後續實作應支援：

- `task(update)` 能可靠更新 `linked_entities`
- server 可提供更好的 duplicate detection
- search / list task 能支援更清楚的 ontology-context 篩選
- 後續可考慮增加 task governance lint 或 analyze check

這些屬於後續實作，不影響本規範先行成立。

---

## 完成定義

以下條件都可被客觀檢查時，才可視為 Task 治理規範已建立：

1. spec surface 納管完成
   - `REF-active-spec-surface` 已列入 `SPEC-task-governance`，且狀態為 active。

2. 開票品質可被實例驗證
   - 至少一張 2026-03-26 之後新建的 task（提供 task ID）符合：
     - title 為動詞開頭且單一 outcome
     - description 含背景/問題/期望結果
     - `linked_entities` 為 1-3 個且無湊數掛法
     - `acceptance_criteria` 為 2-5 條可觀察條件

3. 邊界規則可被 reviewer 直接判斷
   - reviewer 能依本 spec 的 8 題 checklist，判定至少一張候選項目應開 task，且至少一張候選項目不應直接開 task（應先走 spec / blindspot / doc update）。
   - 「候選項目」來源必須明示：至少 1 項來自 `search(collection="tasks", status="todo,in_progress,review")` 的現有任務候選，且至少 1 項來自當次需求中的非 task 候選（spec / blindspot / doc update）。

4. action -> knowledge 反饋有落地證據
   - 至少一張完成任務在 `result` 或關聯文件中明確記錄知識反饋結果（document / blindspot / entity 至少其一），且驗收者據此通過。

5. 半自動審核閉環可被證據驗證
   - 至少一篇 draft 文件有完整紀錄：建立審核 task -> reviewer 輸出 -> editor 修正（可選）-> owner 最終確認。
   - reviewer 輸出可在 task `result` 或 fallback `Result:` 區塊直接查到。
   - owner 可在 WebUI 一處看到審核摘要與文章連結並完成最終確認。

6. 建立者身份可追溯
   - 至少一張本次變更後建立的 task 可驗證 `created_by` = 呼叫當下 API key 對應的 `partner.id`。
   - 以該 `partner.id` 查詢 Outbox（`created_by` filter）可命中此 task。
