---
doc_id: ADR-028-plan-primitive
title: 決策紀錄：Plan Primitive — Action Layer 的 Orchestration 實體化
type: DECISION
ontology_entity: action-layer
status: Draft
version: "1.2"
date: 2026-04-10
updated: 2026-04-23
supersedes: null
superseded_sections:
  - "project_id 欄位命名（2026-04-22 由 ADR-044 rename 為 product_id；2026-04-23 由 ADR-047 定義為指向任何 L1 entity）"
---

> **2026-04-23 update：**
> - 欄位命名：`project_id` 已於 ADR-044 重新命名為 `product_id`（本 ADR 原文保留歷史命名，實作請以最新命名為準）
> - 指向語意：`product_id` 指向任何 **L1 entity**（`level=1 AND parent_id=null`），type 是 UI label，不再限定 `type=product`（ADR-047）

# ADR-028: Plan Primitive — Action Layer 的 Orchestration 實體化

## Context

SPEC-zenos-core 5.2 定義 Plan 是 ZenOS Core 的標準 orchestration primitive，ADR-025 D3 鎖定 Plan 只負責 grouping、sequencing、ownership、completion boundary 四件事。SPEC-task-governance 進一步定義 Plan 的強制欄位（plan_id、goal、owner、entry_criteria、exit_criteria、status）與行為規則。

但 code 裡 Plan 完全不存在。現狀：

1. **Task model 已有 plan_id / plan_order / depends_on_task_ids 欄位**——migration 0002 加了 plan_id、plan_order 和 depends_on_task_ids_json，index 與 unique constraint 都已建好。
2. **DB 沒有 plans table**——migration 0002 的註解寫「no separate plan table in this phase」。plan_id 是一個沒有外鍵指向的懸空 text 欄位。
3. **TaskService 已支援 plan_id 的 CRUD**——create_task / update_task / list_tasks 都處理 plan_id 和 plan_order，但不驗證 plan_id 是否真的存在。
4. **MCP tool 沒有 plan 操作**——agent 無法建立、查詢、更新 Plan。

這導致兩個問題：

- **Plan 的四個 Core 職責無法履行**。沒有 goal、owner、entry/exit criteria 的 Plan 只是一個字串 ID，無法做 completion boundary 判定。
- **plan_id 是無約束的自由文字**。agent 可以填任意字串，沒有驗證、沒有治理閉環。

ADR-026 已定義 Plan 相關 code 的目標位置：`domain/action/models.py`、`domain/action/repositories.py`、`application/action/`、`infrastructure/action/`。本 ADR 在 ADR-026 的 module boundary 框架內，鎖定 Plan 的資料模型、lifecycle、service 架構與 MCP 介面。

## Decision Drivers

- SPEC-zenos-core 5.2 和 SPEC-task-governance 已定義 Plan 的語意，code 必須跟上 spec
- Plan 必須足夠薄——只做 ADR-025 D3 鎖定的四件事，不承擔 PM methodology
- 既有 task 的 plan_id 欄位已在 production 使用，遷移必須向後相容
- 中小企業團隊使用場景：一個 Plan 通常包含 3-15 個 tasks，不需要複雜的 DAG 引擎

## Decision

### D1. Plan DB schema

建立 `plans` table，放在 `zenos` schema：

```sql
create table if not exists zenos.plans (
    id          text        not null,
    partner_id  text        not null references zenos.partners(id),
    goal        text        not null,
    owner       text,                       -- simple name string, Phase 0
    status      text        not null default 'draft',
    entry_criteria text,
    exit_criteria  text,
    project     text        not null default '',
    project_id  text,                       -- link to product/project entity
    created_by  text        not null,
    updated_by  text,
    result      text,                       -- completion summary
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now(),
    primary key (partner_id, id)
);

create index idx_plans_partner_status on zenos.plans(partner_id, status);
create index idx_plans_partner_project on zenos.plans(partner_id, project) where project != '';

-- 加外鍵讓 task.plan_id 指向 plans
alter table zenos.tasks
  add constraint fk_tasks_plan_id
  foreign key (partner_id, plan_id) references zenos.plans(partner_id, id);
```

**為什麼 primary key 是 (partner_id, id) 而非只有 id：** 與 tasks table 保持一致的 multi-tenant isolation pattern。partner_id 是 partition key，確保跨 tenant 查詢不可能洩漏資料。

**為什麼不加 linked_entities：** Plan 的 ontology linkage 透過其下轄 tasks 的 linked_entities 間接建立。Plan 本身不是 knowledge anchor（ADR-025 D4 的延伸——Plan 和 Task 一樣不是 entity）。如果 Plan 也有 linked_entities，會產生 Plan-level 和 Task-level 的雙重 linkage，增加維護成本但不增加資訊量。

**為什麼有 project / project_id：** 與 Task 對齊。Plan 和其下轄 tasks 通常屬於同一 project。project 是 partner-level 的 grouping label，project_id 是指向 product/project entity 的 optional link。

### D2. Plan domain model

Plan dataclass 放在 `domain/action/models.py`（ADR-026 module boundary 已定義此位置）：

```python
@dataclass
class Plan:
    goal: str
    status: str  # PlanStatus value
    created_by: str
    id: str | None = None
    owner: str | None = None
    entry_criteria: str | None = None
    exit_criteria: str | None = None
    project: str = ""
    project_id: str | None = None
    updated_by: str | None = None
    result: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

Plan 的 enum：

```python
class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
```

**欄位與 SPEC-task-governance 的對照：**

| SPEC 定義欄位 | Plan dataclass | 說明 |
|--------------|----------------|------|
| plan_id | id | 命名對齊 Task 的 id 欄位 |
| goal | goal | 一句話描述計畫目標 |
| owner | owner | 計畫責任人 |
| status | status | PlanStatus enum |
| entry_criteria | entry_criteria | 何時可啟動 |
| exit_criteria | exit_criteria | 何時可結案 |

額外欄位（project、project_id、created_by、updated_by、result、timestamps）是 Task 已有的 operational 欄位，Plan 對齊使用。

### D3. Plan repository protocol

放在 `domain/action/repositories.py`：

```python
class PlanRepository(Protocol):
    async def get_by_id(self, plan_id: str) -> Plan | None: ...
    async def upsert(self, plan: Plan, *, conn: Any = None) -> Plan: ...
    async def list_all(
        self,
        *,
        status: list[str] | None = None,
        project: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Plan]: ...
```

不加 `delete`——Plan 只能 cancel，不能物理刪除。這與 Task 的設計一致（Task 也沒有 delete，只有 cancelled）。

### D4. 獨立 PlanService，不整合進 TaskService

**決策：** Plan 有獨立的 `PlanService`，放在 `application/action/plan_service.py`。

**考慮過的替代方案：**

**替代方案：整合進 TaskService。** 理由是「Plan 和 Task 是同一個 Action Layer，放在一起更直覺」。問題：TaskService 已經 540 行（create、update、confirm、list、enrich、cascade unblock），加上 Plan 的 CRUD + lifecycle + completion 判定會讓它膨脹到 800+ 行。更根本的問題是 **Plan 和 Task 的操作語意不同**：Task 有複雜的 status transition + confirm gate + cascade unblock，Plan 有不同的 lifecycle（draft → active → completed/cancelled）和不同的 completion 判定邏輯。把兩者混在一起會產生大量的 `if is_plan / if is_task` 分支。

**PlanService 的職責：**

1. Plan CRUD（create、update、list、get）
2. Plan lifecycle transition validation
3. Plan completion 判定——檢查所有下轄 tasks 是否滿足 exit criteria
4. 與 TaskService 的協作點：PlanService 需要查詢 plan 下的 tasks（透過 TaskRepository 的 list_all(plan_id=...)），但不直接操作 Task

**PlanService 依賴 TaskRepository（讀），不依賴 TaskService。** 理由：PlanService 只需要讀 task 狀態來判定 completion，不需要觸發 task 的 mutation。如果依賴 TaskService，會產生 PlanService ↔ TaskService 的雙向依賴（TaskService.create_task 驗證 plan_id 存在 → 需要 PlanRepository，PlanService 判定 completion → 需要 TaskService.list_tasks）。讓 PlanService 直接讀 TaskRepository 切斷循環。

**TaskService 增加 Plan 驗證：** TaskService.create_task 在有 plan_id 時，透過注入的 PlanRepository 驗證 plan_id 存在。不依賴 PlanService，只依賴 PlanRepository（Protocol）。

### D5. 獨立 plan MCP tool，不擴展 task tool

**決策：** 新增獨立的 `plan` MCP tool，不在 task tool 裡加 plan 操作。

**考慮過的替代方案：**

**替代方案：擴展 task tool，加 action="create_plan" / "update_plan" / "list_plans"。** 理由是「減少 agent 需要學習的 tool 數量」。問題：task tool 已經承擔 create、update、list、get 四個 action，每個 action 有不同的參數 schema。再加 plan 的三個 action 會讓 tool description 膨脹到 agent 難以消化的長度，且 Plan 和 Task 的參數完全不同（Plan 沒有 assignee、acceptance_criteria、linked_entities），混在同一個 tool 裡會產生大量「這個參數只在 action=create_plan 時有效」的條件描述。

**plan tool 的 action：**

```
plan(action="create", goal=..., owner=..., ...)   → 建立 Plan
plan(action="update", id=..., status=..., ...)     → 更新 Plan
plan(action="get", id=...)                         → 取得 Plan + 下轄 tasks 摘要
plan(action="list", status=..., project=..., ...)  → 列出 Plans
```

**plan(action="get") 回傳內容：** Plan 本身的欄位 + 下轄 tasks 的摘要統計（total、by status breakdown、next actionable task）。這讓 agent 用一次呼叫就能掌握 Plan 的全貌，不需要先 get plan 再 list tasks。

### D6. Plan lifecycle

```
draft → active → completed
draft → active → cancelled
draft → cancelled
```

**各狀態語意：**

| 狀態 | 語意 | 可轉移到 |
|------|------|----------|
| draft | 規劃中，tasks 尚未開始 | active, cancelled |
| active | 執行中，至少一張 task 已開始 | completed, cancelled |
| completed | 所有下轄 tasks 滿足 exit criteria | 終態 |
| cancelled | 計畫取消 | 終態 |

**完成判定邏輯：手動 confirm，server 做前提檢查。**

**考慮過的替代方案：**

**替代方案 A：自動判定——所有 tasks done 時自動 completed。** 問題：SPEC-task-governance 明確規定「Plan 狀態不得由單張 task 直接隱式推斷，必須有明確 owner 判定」。自動判定違反此規則。此外，Plan 完成時「必須提供彙總證據」，自動判定無法觸發彙總。

**替代方案 B：純手動，不做任何前提檢查。** 問題：允許在所有 tasks 都是 todo 時就 mark completed，失去治理意義。

**選擇：手動觸發 + server 前提檢查。** Owner 呼叫 `plan(action="update", id=..., status="completed", result="彙總證據")` 時，server 檢查：

1. 所有下轄 tasks 是否都在 terminal state（done 或 cancelled）
2. result 欄位不為空（彙總證據）

若未滿足前提，回傳錯誤訊息說明哪些 tasks 尚未完成。owner 可以選擇先把剩餘 tasks cancel，再 complete plan。

**active 的自動推進：** Plan 從 draft → active 可手動觸發，也可在第一張下轄 task 被推進到 in_progress 時由 TaskService 自動推進。自動推進是 convenience，不是強制——owner 也可以手動先 activate plan 再開始 tasks。

### D7. 既有 plan_id 遷移策略

**決策：auto-create placeholder plans，但 placeholder plan 必須是合法的 `draft` plan，而不是直接標成 `active`。**

**考慮過的替代方案：**

**替代方案：set plan_id = null。** 把既有 tasks 的 plan_id 清空。問題：破壞現有的 grouping 資訊——production 裡已經有 agent 用 plan_id 把 tasks 組織成 groups，清空會丟失這些資訊。

**遷移步驟：**

1. 建立 plans table（無外鍵）
2. 掃描 tasks table，對每個唯一的 (partner_id, plan_id) 組合，建立一筆 placeholder plan：
   ```sql
   INSERT INTO zenos.plans (
       id, partner_id, goal, owner, status,
       entry_criteria, exit_criteria, created_by, project
   )
   SELECT DISTINCT
       t.plan_id,
       t.partner_id,
       '（自動遷移）' || t.plan_id,
       'system:migration',
       'draft',
       'Legacy plan grouping imported from existing tasks. Owner must review and complete plan metadata before activation.',
       'Owner defines explicit completion boundary after reviewing imported tasks.',
       COALESCE(
           (SELECT created_by FROM zenos.tasks t2
            WHERE t2.partner_id = t.partner_id AND t2.plan_id = t.plan_id
            ORDER BY t2.created_at LIMIT 1),
           'system'
       ),
       COALESCE(
           (SELECT project FROM zenos.tasks t2
            WHERE t2.partner_id = t.partner_id AND t2.plan_id = t.plan_id
            AND t2.project != ''
            ORDER BY t2.created_at LIMIT 1),
           ''
       )
   FROM zenos.tasks t
   WHERE t.plan_id IS NOT NULL;
   ```
3. 加外鍵 constraint

Placeholder plans 的 goal 以「（自動遷移）」前綴標記，並由 migration 補上最小合法欄位：`owner = system:migration`、預設的 `entry_criteria` / `exit_criteria` 說明、`status = draft`。這些 plans 保留既有 grouping 資訊，但明確表示「尚未完成 owner review，不可視為正式啟動中的 plan」。

**Tradeoff：** 自動建立的 plans 品質仍不高（goal 只是 plan_id 的複製，criteria 是 migration placeholder）。但保住了既有的 grouping 資訊，同時不違反 Core 對 Plan 最小欄位與 lifecycle 的要求。owner 之後可透過 plan tool 補正內容並手動轉為 `active`。

## Consequences

### Positive

- **Plan 從字串 ID 變成一等公民**。有自己的 schema、lifecycle、治理規則，SPEC 定義的四個 Core 職責（grouping、sequencing、ownership、completion boundary）全部可以落地。
- **plan_id 有外鍵約束**。agent 不能再填不存在的 plan_id，data integrity 有 DB 層保證。
- **獨立 PlanService 和 plan tool**。職責清晰，不膨脹 TaskService，agent 操作語意明確。
- **向後相容**。既有 task 的 plan_id 不需要改動，遷移自動建立合法但未啟動的 placeholder plans。

### Negative

- **多一張 table、多一個 service、多一個 MCP tool。** 增加了 code 量和維護面積。但 Plan 是 SPEC 已定義的 Core primitive，不是可選功能——不落地等於 spec 與實作永遠脫節。
- **Placeholder plans 品質差。** 自動遷移建立的 plans 仍需要 owner 補充真正的 goal 與 criteria，migration 只保證它們先符合 Core contract。
- **PlanService 依賴 TaskRepository。** 這是跨 primitive 的讀依賴（Plan 需要知道 tasks 的狀態來判定 completion）。依賴方向是 Plan → Task（Plan 消費 Task 狀態），符合 ADR-025 的設計意圖（Plan 是 Task 的治理容器）。

### Risks

**最大風險：Plan completion 判定與 application-specific 需求衝突。**

Core 定義的 completion 前提是「所有下轄 tasks 都在 terminal state」，但某些 application 可能允許「80% tasks done + 剩餘 tasks 移到下一期」就算 complete。**緩解：** 目前的 check 是 server-side validation，不是自動判定。如果未來有更靈活的需求，可以放寬 check 條件（例如允許 cancelled tasks 不阻擋 completion），或在 Application Layer 加 override。Core 的 check 是 guardrail，不是 straitjacket。

**中等風險：外鍵 constraint 阻擋 Task 建立。**

加了 fk_tasks_plan_id 後，create_task 帶 plan_id 但 plan 不存在時會 DB error。既有的 agent skill 如果用硬編碼的 plan_id 建 task，會立刻失敗。**緩解：** 遷移先建 placeholder plans（D7），再加外鍵。上線後 TaskService 在 DB 操作前先驗證 plan_id 存在並給出清楚的錯誤訊息，而非讓 agent 看到 raw FK violation error。

**低風險：plan_order unique constraint 與 concurrent task creation 衝突。**

已有的 uq_tasks_partner_plan_order 在多 agent 同時建 task 時可能衝突。這是既有問題（migration 0002 就已經加了這個 constraint），不是 Plan primitive 新引入的。緩解方式是 application 層 retry 或自動遞增 plan_order。

## Implementation Impact

### 新增檔案

| 檔案 | 內容 |
|------|------|
| `migrations/YYYYMMDD_NNNN_plans_table.sql` | D1 的 DDL + D7 的遷移 SQL |
| `src/zenos/domain/action/models.py` | Plan dataclass + PlanStatus enum（ADR-026 定義的位置）|
| `src/zenos/domain/action/repositories.py` | PlanRepository protocol |
| `src/zenos/application/action/plan_service.py` | PlanService |
| `src/zenos/infrastructure/action/sql_plan_repo.py` | SqlPlanRepository |
| `src/zenos/interface/mcp/plan.py`（或 tools.py 內新增 plan section） | plan MCP tool |
| `tests/domain/action/test_plan_model.py` | Plan model 單元測試 |
| `tests/application/action/test_plan_service.py` | PlanService 單元測試 |

### 修改檔案

| 檔案 | 變更 |
|------|------|
| `src/zenos/application/task_service.py`（或遷移後的 `application/action/task_service.py`） | create_task / update_task 加 plan_id 存在性驗證 |
| `src/zenos/interface/tools.py`（或遷移後的 `interface/mcp/__init__.py`） | 註冊 plan tool，PlanService 初始化 |

### 與 ADR-026 的關係

本 ADR 假設 ADR-026 的 module boundary 拆分已完成或同步進行。如果 ADR-026 尚未落地，Plan 的 code 暫時放在現有的平面結構中（`domain/models.py`、`application/plan_service.py`、`infrastructure/sql_repo.py`），待 ADR-026 遷移時一起搬到正確位置。兩種路徑的 domain model 和 API contract 完全相同，差異只在檔案位置。

### 執行順序建議

1. 先寫 migration（建 plans table + placeholder plans + 外鍵）
2. 再寫 domain model + repository protocol
3. 再寫 infrastructure（SqlPlanRepository）
4. 再寫 PlanService
5. 修改 TaskService 加 plan_id 驗證
6. 最後寫 MCP plan tool
7. 全程測試先行——每一步先寫測試再實作
