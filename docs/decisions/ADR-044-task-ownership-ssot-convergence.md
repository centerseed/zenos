---
type: ADR
id: ADR-044
status: Draft
ontology_entity: action-layer
created: 2026-04-22
updated: 2026-04-22
supersedes: null
---

# ADR-044：Task Ownership SSOT 收斂（product_id 必填）

## Context

Task 對外的歸屬語意目前在 schema、domain model、application、interface、frontend 五層之間分裂，沒有單一 SSOT：

1. **DB schema 從 day 1（migration `20260325_0001_sql_cutover_init.sql:230-263`）就有 `tasks.project_id` 欄位**，FK 指向 entities，並有 `idx_tasks_partner_project_id` index。Plans 表（ADR-028 落地）也對齊有 `project_id`。
2. **Domain 與 repo 完整支援**：`Task.project_id` 是 first-class field（`src/zenos/domain/action/models.py:89`），`SqlTaskRepo` UPSERT/SELECT 完整接通（`sql_task_repo.py:80, 218, 251, 268`），search SQL 已支援 `project_id` 過濾（`sql_task_repo.py:361`）。
3. **但 application + interface 的 write path 全部斷線**：
   - `TaskService.create_task` 只設 `project` 字串，不設 `project_id`（`task_service.py:279`）
   - `TaskService.update_task` 白名單沒有 `project_id`（`task_service.py:368`）
   - MCP `_task_handler` signature 沒有 `project_id` 參數（`mcp/task.py:122-156`）
   - Dashboard `create_task` / `update_task` 白名單沒有 `project_id`（`dashboard_api.py:2316, 2387`）
   - `ext_ingestion_api` 同樣沒接通
4. **Read path 各走各的**：
   - `/projects/[id]` 產品頁靠 `WHERE task_entities.entity_id = $product_id` 過濾（`dashboard_api.py:1812`）
   - 全域 `/tasks` 頁靠 `task.project` 字串前端比對（`tasks/page.tsx:307`）
5. **Frontend 用 hack 兜**：UI 從產品頁建 task 偷塞 `entity.id` 進 `linked_entities`（`projects/page.tsx:826`）；agent 派工那條路沒有同樣保底，導致「全域 /tasks 看得到，產品頁看不到」。

結果：
- `linked_entities` 被誤用成「歸屬」，違反 `SPEC-task-governance:771-789` 對它「ontology context、上限 1-3 個、找不到對應節點時應留空」的定義
- `project` 字串成為事實上的 partner-level grouping，但缺乏 FK 保證，容易飄移（`"zenos"` vs `"ZenOS"` vs `"zenos-platform"`）
- `project_id` 欄位資源浪費：schema/domain/repo/search 全部就緒，write path 不接通等於不存在

`SPEC-task-governance:22-29` 早就定義正確的層級結構（Milestone L3 → Plan → Task → Subtask），`SPEC-task-governance:195` 的 AC-TASK-UPG-07 早就要求 `search(tasks, product_id=X)` 過濾要存在，但實作從未對齊。

## Decision Drivers

- 治理 SSOT 必須單一，沒有 SSOT 等於沒治理
- 命名必須直接表達語意：使用者要知道的是「這 task 屬於哪個 **產品**」，schema 命名要對齊
- 既有 `linked_entities` 的 ontology context 語意必須守住，不可被歸屬語意污染
- 遷移必須一刀切到 NOT NULL，過渡期允許但不可永久共存
- Frontend 與 backend 命名必須一致，不再容忍 `project_id` 在 UI / `project` 在 schema 的雙軌

## Decision

### D1. tasks.project_id → tasks.product_id（完整改名）

把 `tasks.project_id` 欄位改名為 `tasks.product_id`，並把 plans 對應欄位 `plans.project_id` 同步改名為 `plans.product_id`，**整個 codebase 不留 fallback alias**。改名後：

- DB column、index、FK constraint、check constraint 全部用 `product_id`
- Domain model `Task.product_id`、`Plan.product_id`
- Repo / service / MCP / dashboard API / frontend types 全部用 `product_id`
- entity table 的 `entities.project_id` **不在本 ADR 範圍**（那是 entity tree root self-reference，與 task 歸屬是不同維度的概念，名稱保留）

### D2. product_id 必填，FK 指向 type=product 的 L1 entity

`tasks.product_id` 加 `NOT NULL` constraint，FK 指向 `entities(partner_id, id)`。

Server-side 額外驗證（單純 FK 不夠）：
- `product_id` 指向的 entity 必須 `type = 'product'`
- Phase 0 不接受 `type = 'project'` 的 entity（ADR-006 規定 Phase 0 沒有 projects collection；若未來 Phase 1 加，再放寬此 check）

`plans.product_id` 同樣 NOT NULL + FK + type check。

### D3. linked_entities 收回 ontology context 本意

`linked_entities` 僅放 L2 module entity 或 L3 entity（goal=milestone / document / role）：
- 上限維持 SPEC-task-governance 的 1-3 個原則
- **嚴禁包含 type=product 的 entity**——server 寫入時自動 strip 並回傳 warning `LINKED_ENTITIES_PRODUCT_STRIPPED`
- Milestone 沿用既有設計（goal L3 entity 透過 linked_entities 引用），不新增欄位

### D4. project 字串欄位 deprecated

過渡期保留 `tasks.project`、`plans.project` 字串欄位，由 server 從 `product_id` 自動派生 `entity.name`。
- Caller 寫入 `project` 字串會被忽略 + warning `PROJECT_STRING_IGNORED`
- 一個 release cycle 後物理刪除欄位（單獨一份 ADR / migration 處理）
- Frontend 顯示用的「產品名稱」直接從 product entity 取，不再依賴 task.project

### D5. Server-side 寫入驗證

| 違規 | 處置 | error_code |
|------|------|------------|
| 沒傳 product_id 也無 partner.defaultProject 可解析 | reject | `MISSING_PRODUCT_ID` |
| product_id 指向不存在 entity | reject | `INVALID_PRODUCT_ID` |
| product_id 指向 type ≠ product 的 entity | reject | `INVALID_PRODUCT_ID` |
| linked_entities 含 type=product entity | strip + warning | `LINKED_ENTITIES_PRODUCT_STRIPPED` |
| 同時傳 project 字串和 product_id 但對不上 | 以 product_id 為準 + warning | `PROJECT_STRING_IGNORED` |

### D6. Fallback 解析鏈（caller 沒傳 product_id 時）

按順序嘗試，全部失敗才 reject：

1. **partner.defaultProject 字串解析**：`SELECT id FROM entities WHERE partner_id = $X AND type = 'product' AND project_id = id AND LOWER(name) = LOWER($defaultProject) LIMIT 1`
2. **若步驟 1 無結果** → reject `MISSING_PRODUCT_ID`，不再 fallback first product entity（避免靜默歸到錯的 product）

不在 server 層做「自動猜」，因為猜錯比 reject 更危險。

### D7. Read path 改造

| 端點 | 現狀 | 改造後 |
|------|------|--------|
| `GET /api/data/tasks/by-entity/{entityId}` | `WHERE task_entities.entity_id = $entityId`（join） | 當 entity.type=product → `WHERE product_id = $entityId`；否則保留 join（給 milestone / module 用） |
| `GET /api/data/projects/{id}` 內聚合 | `_task_repo.list_all(linked_entity=project_id)` | 同上邏輯 |
| MCP `search(tasks, product_id=X)` | 已存在但 fallback project 字串 | 純走 product_id，不再 fallback project 字串 |
| Frontend 全域 `/tasks` filter | `normalizeProjectKey(task.project)` 字串比對 | 改用 `product_id` 過濾，顯示用 product entity name |

### D8. Migration 順序（一次性 cut-over）

```
Step 1: schema migration
  - ALTER TABLE tasks RENAME COLUMN project_id TO product_id
  - ALTER TABLE plans RENAME COLUMN project_id TO product_id
  - 重建 index、FK、constraint（PostgreSQL 會自動 rename，但驗證後重建為 product_id 命名）

Step 2: backfill product_id（NULL 的 task）
  Step 2a: 從 task_entities 找 type=product 的 entity → 取第一個寫入 product_id
           若有多個 → 取第一個 + insert 一筆 entity-tag 標 governance review
  Step 2b: 上一步無結果 → 從 task.project 字串做 entity name lookup
  Step 2c: 上一步無結果 → 從 partner.defaultProject 字串解析
  Step 2d: 上一步仍無結果 → 標 governance review；用 partner 的 first product entity 兜底
           （以保持遷移可進，不阻擋 NOT NULL）

Step 3: 從 task_entities 移除已升格為 product_id 的 product entity（解除誤掛）

Step 4: 驗證 0 NULL 後加 NOT NULL constraint

Step 5: 加 server-side validation（D5）

Step 6: deploy code changes（write path / read path / frontend）

Step 7: 監測一個 release cycle 後物理刪除 task.project / plan.project 字串欄位
        （獨立 migration，不在本 ADR 範圍）
```

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| Codex 提案：強制 agent 派工塞 entity.id 進 linked_entities | 改動最小，agent skill 改一行 | linked_entities 被永久拉去兼任歸屬，違反 SPEC-task-governance §771-789；不解決全域 /tasks 仍靠 project 字串分類；治理 SSOT 仍分裂 | band-aid，不是 SSOT 解 |
| 保留 project_id 名稱不改名，只接通 write path | schema 不動，遷移面最小 | 命名與語意脫節（project ≠ product），UI 叫「產品」但 schema 叫 project，未來新人困惑 | 用戶明確要求改名讓語意清楚 |
| 把 task 升格為 L3 entity，沿用 entity 的 ownership tree | ontology 統一 | ADR-025:114 已明確拒絕——task 的 assignee-based 授權與 L3 entity 的 subtree-based 授權衝突 | 違反既有 ADR |
| 加新欄位 `owner_entity_id` 取代既有 project_id | 命名更通用 | 既有 schema/domain/repo 已就位，新增欄位是浪費；ADR-006/028 命名語意已正確 | 不必要的並列欄位 |
| 不必填 product_id，保留 fallback 機制 | 漸進遷移風險低 | 等於現狀，治理沒 SSOT 就沒治理 | 違反「SSOT 必須單一」driver |

## Consequences

### Positive

- **治理層終於有歸屬 SSOT**：product_id 是唯一答案，server FK + type check + NOT NULL 三重保證
- **`linked_entities` 回到語意本意**：純 ontology context，治理規則終於可以 enforce「上限 3 個」「最相關 L2 module 必須在內」等規則
- **命名直白**：`product_id` 直接表達「這 task 屬於哪個產品」，UI / schema / domain / API 全鏈路一致
- **Codex 描述的 bug 自動消失**：agent 派工不需要任何 hack，只要傳 product_id 就會出現在產品頁與全域頁
- **plan / task 命名對齊**：plan 也改成 product_id，避免 plan 用 product_id / task 用 project_id 的雙軌命名

### Negative

- **遷移面廣**：DB 改名 + domain + repo + service + MCP + dashboard API + ext_ingestion + frontend 五層全部要改
- **既有 caller 立即壞掉**：所有沒傳 product_id 的 agent skill 在加 NOT NULL + server validation 後會立即 reject。緩解：partner.defaultProject fallback 在 D6 兜住絕大多數情境，剩餘的明確 reject 比靜默歸錯更安全
- **過渡期 `project` 字串 deprecated 警告噪音**：caller 短期內仍會傳 project 字串導致 warning。緩解：deprecation warning 一個 release cycle，期間同步更新所有 agent skill 範例

### Risks

**最大風險：backfill 失敗的 task 兜底到 first product entity 可能歸錯**

D8 Step 2d 用「partner 的 first product entity」兜底，是為了讓 NOT NULL constraint 可以加上去，但這會導致少量舊 task 被歸到不正確的 product。

**緩解**：
- 兜底時插入一筆 entity-tag 標 `governance:review_product_assignment`，後台可以撈出來人工 review
- 遷移後跑一份 audit script 列出所有兜底 task，由 owner 確認

**中等風險：`partner.defaultProject` 字串解析誤判**

defaultProject 是字串，靠 LOWER(name) match product entity。若 partner 同時有兩個 product 名稱大小寫相同會誤判（極端情況）。

**緩解**：解析 SQL 加 `LIMIT 1` 並按 `created_at` 排序，且 audit log 記錄解析結果供事後追蹤。長期建議 Phase 1 加 `partner.defaultProductId` 欄位（獨立 ADR）。

**低風險：plan_id / parent_task_id 的 product_id 一致性**

子 task 的 product_id 是否必須等於 parent.product_id？plan 的 product_id 是否必須等於下轄 task 的 product_id？

**Decision**：是。本 ADR Server 加同 plan / 同 parent 約束：
- subtask.product_id 必須等於 parent.product_id（reject `CROSS_PRODUCT_SUBTASK`）
- task.product_id 必須等於 task.plan.product_id（若有 plan）（reject `CROSS_PRODUCT_PLAN_TASK`）

緩解：與既有 `CROSS_PLAN_SUBTASK` 同一個驗證 hook，實作成本低。

## Implementation

詳細實作步驟、檔案清單、AC test stub 路徑見 `docs/plans/PLAN-task-ownership-ssot.md`。

執行原則：
1. 先 migration（schema rename + backfill + NOT NULL），用 Cloud SQL staging 驗證 backfill rate
2. 再 domain / repo / service（含驗證 logic）
3. 再 interface（MCP + dashboard API + ext_ingestion）
4. 最後 frontend
5. 全程測試先行——AC stub 在 `tests/spec_compliance/test_task_ownership_ssot_ac.py` 與 `dashboard/src/__tests__/task_ownership_ssot_ac.test.tsx`

### 同步更新文件

- `SPEC-task-governance` 加 2026-04-22 章節（D1-D8 規則明文化）
- `src/zenos/interface/governance_rules.py["task"]` runtime SSOT 同步加 D5 三條硬約束
- `skills/governance/task-governance.md`、`skills/governance/shared-rules.md` 同步（reference-only）
- `SPEC-task-surface-reset` 註腳對齊 product_id query contract
- `SPEC-project-progress-console` 註腳對齊
