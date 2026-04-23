---
type: SPEC
id: SPEC-task-governance
status: Under Review
ontology_entity: l3-action
created: 2026-03-26
updated: 2026-04-23
depends_on: SPEC-ontology-architecture v2 §9, SPEC-identity-and-access, SPEC-governance-framework
canonical_schema_from: SPEC-ontology-architecture v2 §9
supersedes_sections:
  - 2026-04-19 Action-Layer 升級
  - 2026-04-22 Task Ownership SSOT 收斂
  - 2026-03-31 狀態模型簡化 / Task 欄位定義
---

# Feature Spec: ZenOS L3-Action Governance

> **Layering note**：本 SPEC 只管 L3-Action subclass 的**治理規則**，不重新定義 schema。
> schema（欄位、型別、DDL、Python dataclass、CHECK constraint）canonical 在 `SPEC-ontology-architecture v2 §9`。
> 權限 / visibility canonical 在 `SPEC-identity-and-access`。
> 六維治理表 canonical 在 `SPEC-governance-framework`。

## 1. 定位與範圍

L3-Action 家族共四種概念：**Milestone / Plan / Task / Subtask**。

### 1.1 Runtime 實體模型（current，treat as canonical for callers）

| 概念 | 儲存 | 識別方式 |
|------|------|---------|
| Milestone | L3 entity（`entity_type='goal'` / milestone，見 `src/zenos/domain/knowledge/enums.py`）| outcome anchor |
| Plan | `zenos.plans` row（`src/zenos/infrastructure/action/sql_plan_repo.py`）| 獨立 plans table |
| Task | `zenos.tasks` row（`src/zenos/infrastructure/action/sql_task_repo.py`）| 獨立 tasks table |
| Subtask | `zenos.tasks` row 且 `parent_task_id IS NOT NULL` | **與 Task 同表**，靠 `parent_task_id` 區分 |

> **與主 SPEC v2 §9 的關係**：主 SPEC §9 把 Milestone / Plan / Task / Subtask 各自切成獨立 subclass table（`entity_l3_milestone / plan / task / subtask`），那是 **MTI migration 落地後的目標態**（Wave 9）。本節描述的是**今日 runtime**；caller、測試、migration 必須以本節為準，不要以主 SPEC §9 subclass table 為準。主 SPEC 與 runtime 的 schema 差距將隨 Wave 9 migration 一併收斂，屆時本節會改寫。

### 1.2 歸屬欄位（canonical，參見 runtime）

| 關係 | 欄位 | 規則（取自 `src/zenos/application/action/task_service.py:189-201` + `governance_rules.py:938`）|
|------|------|---------|
| Task / Plan → L1 Product | `product_id` (string, L1 UUID) | **唯一 ownership SSOT（ADR-047 D3 / `OWNERSHIP_SSOT_PRODUCT_ID`）**。新 caller 必傳 `product_id`；tool doc 明示「新 write path 應優先傳 product_id」（`src/zenos/interface/mcp/task.py:678`）|
| Task → Plan | `plan_id` (string, Plan UUID) | Task 所屬 Plan |
| Subtask → Task | `parent_task_id` (string, Task UUID, 自指) | 辨別 subtask 的唯一欄位 |
| Ontology 關聯 | `relationships` + `linked_entities` | 跨實體關聯（impacts / serves / depends_on 等）|

`project` 的語意：**legacy fallback hint**，不是 ownership 欄位。server 在 caller 沒傳 `product_id` 時，先解 `product_id`；失敗才 fallback 到 `project` / `partner.defaultProject` 去反推 L1 entity（`task_service.py:190-194`）。`project` 字串不代表 ownership；新 caller 不應依賴它。

Server-side 硬閘（以 `governance_rules.py:938-944` 為準）：
- `product_id` 未傳且 legacy fallback 也解析不出 L1 → reject `MISSING_PRODUCT_ID`
- `product_id` 指向不存在 entity 或非 L1 entity（level ≠ 1 或有 parent）→ reject `INVALID_PRODUCT_ID`
- `linked_entities` 含 L1 entity → server strip + warning `LINKED_ENTITIES_PRODUCT_STRIPPED`（歸屬已由 `product_id` 表達）
- `subtask.plan_id ≠ parent_task.plan_id` → reject `CROSS_PLAN_SUBTASK`
- `subtask.product_id ≠ parent_task.product_id` → reject `CROSS_PRODUCT_SUBTASK`
- `task.product_id ≠ plan.product_id`（task 有 `plan_id` 時）→ reject `CROSS_PRODUCT_PLAN_TASK`
- 直接傳入 `project_id` 參數 → reject `INVALID_INPUT`（ADR-047 D3）

**本 SPEC 不定義**：DDL、欄位型別詳情（見 runtime repo files 與主 SPEC §9 目標態）、frontend UI、Zentropy 執行細節、application-specific checklist。

## 2. Task 的治理定位

Task 是「**需要跨角色驗收**」的最小工作單位。

| 不該開 Task | 該開 Task |
|-----------|---------|
| 個人 todo / 提醒事項 | 需要他人接手或驗收的工作 |
| bug 修復本身（走 code fix + PR）| 決定「要不要修、由誰修、怎麼驗收」時 |
| 臨時想法 / 未成形的方向 | 有明確 outcome + AC 的具體工作 |
| 純執行步驟（屬 checklist） | 跨 Spec / 跨模組的協調工作 |
| 文件內容本身（docs/designs/ 下的檔案）| 要求某份文件被審閱 / 發佈的治理動作 |

不滿足上述「跨角色驗收 + 明確 outcome」的，不得開 Task。Application-specific 的 routine / checklist / execution step 應留在應用層，不得污染 L3-Action。

## 3. Lifecycle State Machine

主 SPEC `§11.2` 已定義每個 subclass 合法 status 集合與 CHECK constraint。本節只規範**狀態轉換的治理閘**。

### 3.1 Task（`task_status`: todo / in_progress / review / done / cancelled）

| From → To | 觸發條件 | Server 強制 |
|----------|---------|-----------|
| `todo` → `in_progress` | dispatcher claim 或 caller 更新 | 必須有 `assignee` 或 `dispatcher`（非 null） |
| `in_progress` → `review` | handoff to `agent:qa` **或** caller 直接更新 | 必須附 `result`（CHECK constraint） |
| `review` → `done` | `confirm(collection="tasks", accepted=True)` 驗收通過 | caller 必須有 owner/member 權限；server append terminal handoff event（to=`human`, reason=`accepted`） |
| `review` → `in_progress` | `confirm(collection="tasks", accepted=False, rejection_reason=...)` 退回 | `rejection_reason` 必附；server append handoff event（`to_dispatcher = task.dispatcher or "human"`，**不自動改派回 developer**；切換角色需後續 handoff）|
| `*` → `cancelled` | caller 明確取消 | 必附 cancel reason；subtask 亦須連帶 cancelled |

> **Alias**：`confirm(..., accept=True)` 為 `accepted=True` 的 alias；server 自動改寫並回 warning。新 caller 一律用 `accepted`。

**禁止**：`done` / `cancelled` → 任何狀態（terminal immutable）。

### 3.2 Plan（`task_status`: draft / active / completed / cancelled）

| From → To | 觸發條件 | Server 強制 |
|----------|---------|-----------|
| `draft` → `active` | caller 更新 | 必須有 `entry_criteria` + `exit_criteria`（非空） |
| `active` → `completed` | caller 更新 | 必附 `result`；所有下轄 Task 必須處於 terminal（done/cancelled），違反 reject with `PLAN_HAS_UNFINISHED_TASKS`（訊息列前 5 個未 terminal task id） |
| `*` → `cancelled` | caller 明確取消 | 必附 cancel reason |

`completed` 後 Plan immutable。

### 3.3 Milestone（`task_status`: planned / active / completed / cancelled）

| From → To | 觸發條件 | Server 強制 |
|----------|---------|-----------|
| `planned` → `active` | caller 更新 | 無額外閘 |
| `active` → `completed` | caller 更新 | 必附 `completion_criteria` 檢核結果（於 `result`） |
| `*` → `cancelled` | caller 明確取消 | 必附 cancel reason |

### 3.4 Subtask

狀態機同 Task。額外強制：
- `parent_task_id` 必須指向 Task row（`task_service.py:204-210` 確認 parent 存在；`PARENT_NOT_FOUND` on miss）
- **Governance 建議**：subtask 不應再有 subtask（agent 派工單位只有一層）；目前 **client-side 紀律**，server 未擋（`task_service.py:204-224` 只驗 parent 存在 / 跨 plan / 跨 product）。若未來要硬擋需新增 server check
- subtask terminal 不自動關閉 parent task；parent task 終結由 handoff / confirm 決定

## 4. Dispatcher & Handoff Chain

### 4.1 Dispatcher Namespace

正則（server-enforced）：`^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`

| 值 | 意義 |
|---|------|
| `human` | 泛指人類（未指定具體 assignee）|
| `human:<partner_id>` | 具體人類 |
| `agent:pm` | 產出 SPEC |
| `agent:architect` | 技術設計、拆 subtask |
| `agent:developer` | 實作 |
| `agent:qa` | 驗收 |
| `agent:<role>` | 自行擴充（小寫 + underscore）|

不合格值 → `write` / `task(action="handoff")` reject，`error_code = INVALID_DISPATCHER`。

### 4.2 Handoff 流程

唯一入口：`task(action="handoff", id=X, data={...})`

```
data = {
  to_dispatcher: string,    # 必填，通過 namespace 驗證
  reason: string,           # 必填
  output_ref: string|null,  # 強烈建議（commit SHA / SPEC path / ADR id）
  notes: string|null        # 選填
}
```

Server 原子操作：
1. append `HandoffEvent{at, from_dispatcher, to_dispatcher, reason, output_ref, notes}` to `handoff_events`
2. update `task.dispatcher = to_dispatcher`
3. 若 `to_dispatcher == "agent:qa"` 且當前 status=`in_progress` → 自動升 `status=review`

**約束**：
- `handoff_events` append-only；caller 若於 `task(action="create" | "update")` 的 data 中帶 `handoff_events`，**server 強制 strip 該欄位 + 回 warning `HANDOFF_EVENTS_READONLY`**（不 reject，但變更不會生效）。唯一合法 append 入口：`task(action="handoff", ...)` 由 server 原子操作 append。
- handoff 只改 dispatcher 與 handoff_events；**不會**改 assignee、不會幫 caller 認領票、不會把 `todo` 升成 `in_progress`。Claim 是 agent 啟動後自己做的第一步。

### 4.3 Agent Claim 規則

Agent 接手 task 後，第一步：
```
task(action="update", id=X, status="in_progress")
```
如需填 assignee（例如 `human:<partner_id>` 之外的 agent），一併更新。

**禁止**：agent 在未 claim 的情況下直接 handoff（reason 不是自己的工作結論）。

### 4.4 標準 handoff chain

```
PM ── spec approved ──► Architect ── TD + AC stubs ──► Developer ── commit + test green ──► QA ── confirm(accept) ──► human
                                                                                     └── confirm(reject) ──► Developer
```

每一棒 handoff 必附 `output_ref` 讓下游 cold-start 可追；QA accept 由 `confirm` 觸發，不走 handoff。

## 5. Plan 層治理

### 5.1 entry_criteria / exit_criteria

| 欄位 | 用途 |
|------|------|
| `entry_criteria` | 這個 Plan 什麼時候才能開始？（例：`SPEC Approved` + `linked_entities ready`） |
| `exit_criteria` | 這個 Plan 什麼時候才算收口？（例：所有 P0 AC 綠 + 部署驗證） |

兩者皆非空字串；`active` 態要求已填。

### 5.2 Plan 關閉（閉環責任）

責任人：**發起 Plan 的角色**。
- PM 發起 feature → PM 關 Plan
- Architect 發起 refactor / tech debt / incident → Architect 關 Plan

關 Plan 時：
```
plan(action="update", id=P, status="completed", result="<交付摘要 + commit + 部署 + 驗證>")
```

`result` 必填非空字串；空字串 reject。Server 檢查所有下轄 Task 是 terminal，違反 reject。

### 5.3 Subtask 與 Plan 歸屬

Subtask 透過 `parent_task_id` 指向 parent Task，parent Task 透過 `plan_id` 指向 Plan。
Server 強制 `subtask.plan_id == parent_task.plan_id`，違反 reject `CROSS_PLAN_SUBTASK`；`subtask.product_id == parent_task.product_id` 違反 reject `CROSS_PRODUCT_SUBTASK`。

## 6. Milestone 治理

Milestone（= 合併後的 Goal）提供 **outcome anchor**：

- `completion_criteria`：什麼條件下這個 milestone 算達成？（text，必填當 `status=active`）
- `result`：達成時的證據摘要
- Milestone 本身不直接執行，靠下游 Plan / Task 收斂到它（以 `relationships.type='serves'` 表達指向，Plan / Task 用 `product_id` 對齊同一 L1）

## 7. Task 必要欄位規範

schema canonical 在主 SPEC v2 §9.4；本節規範**治理要求**。

| 欄位 | 治理要求 |
|------|---------|
| `title` | 單一 outcome，10–80 字，避免「更新 X」「處理 Y」這類動作名詞堆疊 |
| `description` | 背景 / 範圍 / 相關脈絡；不寫重複資訊（讀 linked_entities 就知道的不寫） |
| `acceptance_criteria` | `list[str]`，每條 Given/When/Then 或同效語法；必須可獨立驗證 |
| `linked_entities` | 透過 `relationships` 表掛；規則見 §8 |
| `priority` | `critical / high / medium / low`；critical 僅 owner 可設 |
| `assignee` | `partner.id` 或 `agent:<role>`；空值代表「尚未認領」 |
| `result` | `review` / `done` 必填；空字串 reject（`RESULT_REQUIRED_ON_REVIEW`） |
| `attachments` | 見 §10 |

## 8. linked_entities 掛法

**規則**（與主 SPEC §10.3 禁止清單一致）：
- 只掛「這張 task 真的會動到 / 真的驗收」的 entity；不掛背景知識
- 嚴禁掛 L1 自己（task 本來就屬 L1，透過 `product_id` 表達；違反 server strip + warning `LINKED_ENTITIES_PRODUCT_STRIPPED`）
- 嚴禁重複：同一 entity 不得 list 兩次
- 關係型用 `relationships.type`：`impacts / depends_on / serves / related_to / blocks`；選不到就別硬塞

**正確掛法分類**：

| 類型 | 範例 |
|------|------|
| A. 單點實作修補 | linked_entities=[{entity: L3-Document, type: impacts}] |
| B. 治理規則流程 | linked_entities=[{entity: L2, type: impacts}, {entity: SPEC doc, type: serves}] |
| C. 跨層設計 | linked_entities=[{entity: L2, type: impacts}, {entity: L3-Document, type: impacts}, {entity: Milestone, type: serves}] |

## 9. Confirm / Accept 流程

```
confirm(collection="tasks", id=X, accepted=True, entity_entries=[...])
```

Server 原子操作：
1. 驗證 caller 對 task 有 accept 權限（owner 或 被指定的 reviewer）
2. status review → done
3. append terminal HandoffEvent（to=`human`, reason=`accepted`）
4. 若 `entity_entries` 非空，寫入對應 L2 的 entries（見 §11）

`confirm(collection="tasks", accepted=False, rejection_reason="...")`：
1. status review → in_progress
2. append HandoffEvent：`from_dispatcher = task.dispatcher`，`to_dispatcher = task.dispatcher or "human"`，`reason = "rejected: {rejection_reason}"`（見 `task_service.py:669-676`）。server **不會**自動改派回 `agent:developer`；下一棒 dispatcher 以當前 `task.dispatcher` 為準（為 null 時 fallback `"human"`），要切換角色需後續 `task(action="handoff")` 明確設定
3. `task.confirmed_by_creator = false`、`task.rejection_reason = rejection_reason`
4. `result` 保留為歷史快照；下輪 review 時由下游覆寫

> Caller 仍可傳 `accept=True|False` alias；server 自動改寫成 `accepted` 並回 warning。

## 10. Task 附件

附件統一掛在 `attachments` typed JSON 欄位，每筆為 typed object，三種 `type`：`image / file / link`。

| 規則 | 內容 |
|------|------|
| 儲存 | `image/file` 存 `gcs_path`（永久），前端**不直接存取 GCS** |
| 存取 | 一律走 `GET /attachments/{attachment_id}` server proxy，URL 永不過期 |
| link type | 只存 `external_url` metadata |
| 禁止 | DB 存 signed URL |
| uploaded_by | server 從 auth context 覆寫；不信任 caller |

**上傳**：
- link：直接帶入 `attachments` 陣列
- image/file ≤5MB：`upload_attachment` MCP tool（inline base64）
- image/file >5MB：UI 取 signed PUT URL 後直傳 GCS

**限制（Phase 1）**：單 task ≤20 附件；MCP inline ≤5MB；圖片單檔 ≤10MB；一般檔案 ≤50MB。

**Phase 1 已知限制**：`attachments` update 為全量覆寫（並發寫入後者覆蓋前者；Phase 2 加 patch 語意）。

## 11. Task 完成後的知識回饋

Task 驗收通過時，若產生新知識，必須回饋至 L2：

```
confirm(collection="tasks", id=X, accepted=True, entity_entries=[
  {entity_id: <L2-id>, type: "decision", content: "..."},
  {entity_id: <L2-id>, type: "insight", content: "..."}
])
```

每個 entry 的欄位：
- `entity_id`：目標 L2 UUID（必填）
- `type`：`decision | insight | limitation | change | context`（必填，enum）
- `content`：1–200 字敘述（必填）

Server 將 entries append 到對應 L2 的 entries sidecar table。僅在 `accepted=True` 時生效。若驗收時沒有新知識，傳 `entity_entries=[]` 明確宣示，不得靜默略過。

**治理閘**：L2 必須在 task 的 `linked_entities` 中，否則 reject with `ENTRY_TARGET_NOT_LINKED`。

## 12. 粒度與反模式

### 12.1 粒度標準

| 指標 | 目標 |
|------|------|
| 單 task 完成時間 | 0.5 – 3 工作日 |
| AC 數量 | 2–6 條；超過建議拆 subtask |
| 涉及 spec | ≤3 份；超過通常意味著跨層，考慮開 Plan 而非放進一張 task |

### 12.2 反模式（server / reviewer 標記為警告）

| 名稱 | 徵兆 | 正確做法 |
|------|------|---------|
| 孤兒票 | `product_id` 解析失敗或 plan/subtask 的 chain 中斷 | 補 `product_id`（`MISSING_PRODUCT_ID` / `INVALID_PRODUCT_ID`）或修正 `plan_id` / `parent_task_id` |
| 假連結票 | linked_entities 有但無實質 impacts | 要嘛不連、要嘛開 impacts relationship |
| 混合型票 | 一張票混治理 + 實作 | 拆 handoff chain |
| 提醒型票 | title 是「別忘了 …」| 改走 journal 或 calendar，不開 task |
| 重複票 | 同 outcome 已有未 terminal 票 | 走 §13 supersede |

## 13. 去重與 supersede

建票前必做：
```
search(collection="tasks", status="todo,in_progress,review",
       linked_entities=<target-entity-id>)
```

若找到相似 open task：
- **補強**：直接 update 現票（title / description / AC）
- **取代**：新票建立時在 description 標 `Supersedes: <old-task-id>`，並對舊票 `task(action="update", status="cancelled", result="superseded by <new-id>")`

## 14. 衝突仲裁

| 衝突類型 | 仲裁 |
|---------|------|
| Task AC 與 SPEC 原意不符 | SPEC 勝；回頭改 task AC |
| Task 涉及多 Plan | 拆票；一張 task 只屬一個 Plan |
| Subtask status 與 parent Task 不一致 | parent Task 的 dispatcher 決定；subtask 跟隨 |
| Application subtask 與 Core subtask 混用 | Core Subtask 勝；application 自己的 checklist 留應用層 |

## 15. Governance 客製化邊界

### 15.1 Server 硬編碼（不可調整）

- `task_status` enum 合法值與狀態機（主 SPEC §11.2）
- Dispatcher namespace 正則
- CHECK constraints（`review` 必附 result、subtask 不得跨 plan、Plan completed 前所有 Task 必須 terminal）
- `handoff_events` append-only 語意
- `linked_entities` 禁止清單（主 SPEC §10.3）

### 15.2 用戶可客製（在 workspace settings）

- AC 語法 lint 規則（Given/When/Then 是否強制）
- Task 粒度警告閾值（超時 / 過多 AC）
- 提醒型 / 孤兒票的警示等級
- 預設 `priority` 與 sort order

### 15.3 應用層延伸（不入 Core）

- CRM 的 activity log / deal pipeline stage
- Zentropy 的 daily execution checklist
- Marketing 的 campaign step
- 任何「提醒自己」「私人 todo」類流程

應用層可讀 Core L3-Action，但不得**改寫** Core subclass 的 lifecycle 或 confirm 閘。

## 16. MCP 行為要求

主 SPEC v2 §9 + `SPEC-mcp-tool-contract` 為 canonical；本節列出治理相關的行為契約：

- `task(action="create")` → 強制 title / AC / linked_entities 最小集
- `task(action="handoff")` → 唯一入口改 dispatcher 與 handoff_events
- `task(action="create" | "update")` → `handoff_events` 為 server-managed；caller 傳入 → strip + warning `HANDOFF_EVENTS_READONLY`（不 reject）
- `confirm(collection="tasks")` → 唯一 accept 入口；`entity_entries` 若提供則寫 L2 entries
- `plan(action="update", status="completed")` → 檢查所有下轄 task terminal；`result` 必填
- 毀滅性操作（bulk cancel / purge）**不暴露為 MCP tool**；僅限 admin script

## 17. 驗收 Criteria（本 SPEC 自身 AC）

- `AC-TASK-01` Given caller create task with status=`review` 但無 `result`，When server process，Then reject with `RESULT_REQUIRED_ON_REVIEW`
- `AC-TASK-02` Given caller handoff 用不合法 dispatcher（如 `robot`），When server validate，Then reject with `INVALID_DISPATCHER`
- `AC-TASK-03` Given subtask 的 `parent_task_id` 指向另一 Plan 下的 Task（即 `subtask.plan_id ≠ parent_task.plan_id`），When server validate，Then reject with `CROSS_PLAN_SUBTASK`
- `AC-TASK-04` Given Plan 下仍有 `in_progress` Task，When `plan(action="update", status="completed")`，Then reject with `PLAN_HAS_UNFINISHED_TASKS`（訊息含前 5 個未 terminal task id）
- `AC-TASK-05` Given task 驗收時傳 `entity_entries` 但 L2 不在 `linked_entities`，When server write，Then reject with `ENTRY_TARGET_NOT_LINKED`
- `AC-TASK-06` Given caller 於 `task(action="create" | "update")` 於 data 中帶 `handoff_events`，When server process，Then **strip 該欄位 + response 附 warning `HANDOFF_EVENTS_READONLY`**；task 仍正常寫入但該欄位不生效
- `AC-TASK-07` Given task handoff to `agent:qa` 且 status=`in_progress`，When server atomic，Then status 自動升 `review` 且 append HandoffEvent
- `AC-TASK-08` Given `confirm(collection="tasks", id=X, accepted=True)`，When server process，Then status → `done` + append terminal HandoffEvent(to=`human`, reason=`accepted`)
- `AC-TASK-08b` Given caller 傳 `accept=True` alias，When server process，Then 行為等同 `accepted=True`，response 附 warning「參數 alias 'accept' 已自動改寫為 'accepted'」
- `AC-TASK-09` Given Milestone `active` → `completed`，When server process，Then `result` 必須非空字串（含 completion_criteria 檢核結果）
> **Gap note**：舊 draft 的 AC-TASK-10（`SUBTASK_NESTING_DISALLOWED`）runtime 未實作——`task_service.py:204-224` 只驗 `PARENT_NOT_FOUND` / `CROSS_PLAN_SUBTASK` / `CROSS_PRODUCT_SUBTASK`，**不阻擋 `parent_task_id` 指向已經是 subtask 的 row**。治理上仍建議 subtask 只有一層（agent 派工單位），但這是 client-side 紀律，不是 server enforcement。若未來要硬擋，需新增一條 server check 並補 AC。

## 18. 相關文件

- `SPEC-ontology-architecture v2 §9` — L3-Action schema / DDL / CHECK（canonical）
- `SPEC-ontology-architecture v2 §11.2` — status state machine（canonical）
- `SPEC-identity-and-access` — visibility / permission
- `SPEC-governance-framework` — 六維治理表
- `SPEC-mcp-tool-contract` — tool shape（task / plan / confirm）
- `SPEC-doc-governance` — L3-Document subclass 的對應治理
