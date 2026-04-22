---
spec: SPEC-task-governance.md (§2026-04-22 Task Ownership SSOT 收斂)
adr: ADR-044-task-ownership-ssot-convergence.md
created: 2026-04-22
status: in-progress
plan_id: c646d3c91374466baa92c6e03d6a4b37
---

# PLAN: Task Ownership SSOT 收斂（product_id 必填）

## Goal
把 task / plan 對 product 的歸屬語意從多軌（project 字串 / project_id / linked_entities 偷塞）
收斂為單一 SSOT `product_id` (FK to L1 product entity, NOT NULL)，並補齊 write/read 兩端。

## Entry Criteria
- ADR-044 status = Accepted（用戶確認本 PLAN 後 Architect 改 status）
- AC stubs 已產出（`tests/spec_compliance/test_task_ownership_ssot_ac.py`、
  `dashboard/src/__tests__/task_ownership_ssot_ac.test.tsx`）
- staging Cloud SQL 可進行 backfill dry-run

## Exit Criteria
- 25 條 AC（AC-TOSC-01..25）全部 PASS
- staging migration backfill 0 NULL，governance:review_product_assignment 兜底數量 < 5%
- production 部署後端到端驗證：從產品頁建 task 出現在產品頁 + 全域 /tasks 同步
- spec / governance_rules.py / skills 三處 SSOT 同步
- Codex 描述的 bug（agent 派工只填 project，產品頁看不到）實際走 agent flow 驗證消失

## Tasks（依執行順序）

### Phase 1: Schema Migration（最先做，影響後續所有 phase）

- [ ] **S01**: 寫 schema migration `migrations/20260422_NNNN_task_product_id_rename.sql`
  - Rename `tasks.project_id` → `tasks.product_id`，重建 index、FK、constraint
  - Rename `plans.project_id` → `plans.product_id`，同上
  - **不加 NOT NULL**（留給 S03 backfill 後再加）
  - Files: `migrations/20260422_NNNN_task_product_id_rename.sql`
  - Verify: `psql -c "\d zenos.tasks" | grep product_id`，無 project_id 欄位

- [ ] **S02**: 寫 backfill migration `migrations/20260422_NNNN_task_product_id_backfill.sql`
  - 按 ADR-044 D8 Step 2 順序：task_entities → project string → partner.defaultProject → first product entity 兜底
  - 兜底 task 插入 `governance:review_product_assignment` tag（透過 entity_tags 或 audit log，視 schema 而定）
  - Files: `migrations/20260422_NNNN_task_product_id_backfill.sql`
  - Verify: staging 跑完後 `SELECT COUNT(*) FROM zenos.tasks WHERE product_id IS NULL = 0`

- [ ] **S03**: 寫 cleanup + NOT NULL migration `migrations/20260422_NNNN_task_product_id_finalize.sql`
  - 從 task_entities 移除已升格為 product_id 的 product entity（D8 Step 3）
  - 加 `tasks.product_id NOT NULL`、`plans.product_id NOT NULL`
  - 加 type check（透過 trigger 或 application-level；FK 不夠）
  - Files: `migrations/20260422_NNNN_task_product_id_finalize.sql`
  - Verify: `SELECT product_id FROM tasks LIMIT 1` 無 NULL 行為，AC-TOSC-04 PASS

  **AC**: AC-TOSC-01, 02, 03, 04

### Phase 2: Domain / Repo（用 product_id 名稱重寫）

- [ ] **S04** (depends: S01): 改 domain models
  - `src/zenos/domain/action/models.py`: `Task.project_id` → `Task.product_id`，
    `Plan.project_id` → `Plan.product_id`，註解更新
  - Files: `src/zenos/domain/action/models.py`
  - Verify: `grep "project_id" src/zenos/domain/action/models.py` 無結果

- [ ] **S05** (depends: S04): 改 SQL repo
  - `sql_task_repo.py`、`sql_plan_repo.py`: column 名稱、UPSERT、SELECT、search 全部改 `product_id`
  - search query 移除 `OR t.project_id = $X` fallback，純走 `product_id`
  - Files: `src/zenos/infrastructure/action/sql_task_repo.py`,
    `src/zenos/infrastructure/action/sql_plan_repo.py`
  - Verify: 既有 unit tests 全 PASS（schema 已對齊）

  **AC**: 為 S07 鋪路

### Phase 3: Application Service（核心 validation 集中地）

- [ ] **S06** (depends: S05): TaskService / PlanService 加 product_id validation
  - `task_service.py`: create_task / update_task 處理 product_id；實作 D5 全部 validation：
    - product_id 存在性 + type=product 檢查
    - linked_entities strip product entity
    - subtask cross-product check（呼叫 parent.product_id 比對）
    - plan cross-product check（呼叫 plan.product_id 比對）
  - `plan_service.py`: 同樣加 type validation；create/update 處理 product_id
  - 加 fallback 解析（D6）：caller 沒傳 product_id → 呼 EntityRepo 找 partner.defaultProject 對應 entity
  - Files: `src/zenos/application/action/task_service.py`,
    `src/zenos/application/action/plan_service.py`
  - Verify: AC-TOSC-05..11 全 PASS

  **AC**: AC-TOSC-05, 06, 07, 08, 09, 10, 11

### Phase 4: Interface 層（MCP + Dashboard API + ext）

- [ ] **S07** (depends: S06): MCP task / plan tool 接通 product_id
  - `mcp/task.py`: `_task_handler` 加 `product_id: str | None = None` 參數，傳遞給 service
  - `mcp/plan.py`: 既有 project_id 參數改名 product_id（既有 caller 立即壞掉，改 release-note）
  - `mcp/search.py`: tasks search 的 `product_id` filter 純走 product_id 欄位（移除 fallback）
  - Files: `src/zenos/interface/mcp/task.py`, `mcp/plan.py`, `mcp/search.py`
  - Verify: AC-TOSC-12, 13, 17 PASS

  **AC**: AC-TOSC-12, 13, 17

- [ ] **S08** (depends: S06): Dashboard API 接通 product_id
  - `dashboard_api.py:2316, 2387`: create_task / update_task 白名單加 `product_id`
  - `dashboard_api.py:1812`: list_tasks_by_entity 改造（D7）：
    - 先 fetch entity，若 type=product → 走 `WHERE product_id = $entityId`
    - 否則保留 task_entities join（給 milestone / module 用）
  - `dashboard_api.py:1919`: 同樣邏輯（projects/{id} 內 aggregation）
  - Files: `src/zenos/interface/dashboard_api.py`
  - Verify: AC-TOSC-14, 16 PASS

  **AC**: AC-TOSC-14, 16

- [ ] **S09** (depends: S06): ext_ingestion_api 接通
  - `ext_ingestion_api.py:38, 237`: 加 product_id 參數傳遞 + validation
  - Files: `src/zenos/interface/ext_ingestion_api.py`
  - Verify: AC-TOSC-15 PASS

  **AC**: AC-TOSC-15

### Phase 5: Frontend（接通 + 移除 hack）

- [ ] **S10** (depends: S08): Dashboard types + API client
  - `dashboard/src/lib/api.ts`: createTask / updateTask 型別加 `product_id: string`（必填）
  - 既有 `project_id` 用法搜尋並改名為 `product_id`
  - Files: `dashboard/src/lib/api.ts`, `dashboard/src/types/index.ts`
  - Verify: TypeScript build 無 error

- [ ] **S11** (depends: S10): /projects/[id] 建 task 改用 product_id
  - `dashboard/src/app/(protected)/projects/page.tsx:823, 826`: handleCreateTask 改傳
    `product_id=entity.id`，**移除** linked_entities 偷塞 entity.id 的 hack
  - Files: `dashboard/src/app/(protected)/projects/page.tsx`
  - Verify: AC-TOSC-19 PASS；UI 從產品頁建 task 不再 push entity.id 進 linked_entities

  **AC**: AC-TOSC-19, 20

- [ ] **S12** (depends: S10): /tasks 全域頁 filter 改 product_id
  - `dashboard/src/app/(protected)/tasks/page.tsx:307`: filter logic 從 `task.project` 改為
    `task.product_id`，顯示用 product entity name (從 cache 取)
  - `dashboard/src/features/tasks/taskHub.ts:129, 211`: `plan.project_id` → `plan.product_id`
  - Files: `dashboard/src/app/(protected)/tasks/page.tsx`,
    `dashboard/src/features/tasks/taskHub.ts`
  - Verify: AC-TOSC-18 PASS

  **AC**: AC-TOSC-18

### Phase 6: Governance SSOT 同步 + Deprecation

- [ ] **S13** (depends: S06): Runtime governance SSOT 同步
  - `src/zenos/interface/governance_rules.py["task"]`: 加三條繩子原則 + 七條 server validation
    規則的 level 2 內容（對齊 SPEC-task-governance §2026-04-22 章節）
  - Files: `src/zenos/interface/governance_rules.py`
  - Verify: AC-TOSC-22, 23 PASS

  **AC**: AC-TOSC-22, 23

- [ ] **S14** (depends: S07): project 字串欄位 deprecation
  - 在 service 層加 logic：caller 傳 project 字串 → ignore + warning PROJECT_STRING_IGNORED
  - DB 內 project 欄位由 server 從 product entity.name 自動派生（寫入時自動填）
  - Files: `src/zenos/application/action/task_service.py`,
    `src/zenos/application/action/plan_service.py`
  - Verify: AC-TOSC-21 PASS

  **AC**: AC-TOSC-21

- [ ] **S15** (depends: S13): Skills SSOT 同步
  - `skills/governance/task-governance.md`: 補三條繩子原則章節（reference-only）
  - `skills/governance/shared-rules.md`: 對齊更新
  - Files: `skills/governance/task-governance.md`, `skills/governance/shared-rules.md`
  - Verify: AC-TOSC-24 PASS（Architect review）

  **AC**: AC-TOSC-24

- [ ] **S16** (depends: S15): 相關 SPEC 加註腳對齊
  - `SPEC-task-surface-reset`: 加註腳對齊 product_id query contract
  - `SPEC-project-progress-console`: 同上
  - Files: `docs/specs/SPEC-task-surface-reset.md`,
    `docs/specs/SPEC-project-progress-console.md`
  - Verify: AC-TOSC-25 PASS（Architect review）

  **AC**: AC-TOSC-25

### Phase 7: 驗證與部署

- [ ] **S17** (depends: S03 + S06 + S07 + S08 + S09 + S11 + S12): staging 端到端驗證
  - 跑 backfill migration on staging
  - 走完整 agent flow：agent 用 MCP `task(action="create", product_id=...)` 建 task
  - 驗證 task 出現在 `/projects/[id]` 與全域 `/tasks` 兩處
  - 驗證 `governance:review_product_assignment` 兜底比例 < 5%
  - Verify: 產出 staging verification report

- [ ] **S18** (depends: S17): production 部署
  - 走 `./scripts/deploy.sh`（dashboard）+ `./scripts/deploy_mcp.sh`（backend）
  - 部署後 curl 端點驗證；端到端 UI 驗證
  - Verify: production 端到端通過

## Decisions（更新中）

- 2026-04-22: 改名 `project_id → product_id`，schema 大遷移（用戶決策，ADR-044 D1）
- 2026-04-22: backfill 多 product 的 task 取第一個 + 標 governance review（用戶決策，ADR-044 D8 Step 2a）
- 2026-04-22: Milestone 沿用 SPEC-task-governance §Milestone 既有定義，不另開欄位（用戶決策）
- 2026-04-22: 不 fallback 到 first product entity（D6）——猜錯比 reject 更危險

## Resume Point

**目前狀態**: 文件落地完成 + ZenOS plan 建立 + S01 已派工給 Developer（待 Codex session 認領）。

- **Plan id**: `c646d3c91374466baa92c6e03d6a4b37`
- **S01 task id**: `6e65ec5564c4472ca9a54b151fa20a36`（dispatcher=agent:developer, todo, plan_order=1）
- Plan status = draft（S01 進入 in_progress 後 server 自動推進為 active）

**下一步**:
1. Codex session 以 Developer 角色認領 S01：
   - `mcp__zenos__task(action="update", id="<S01_TASK_ID>", status="in_progress")`
   - 寫 migration → 走 AC 驗證 → `task(action="handoff", to_dispatcher="agent:qa", ...)` 交 QA
2. S01 QA PASS 後 Architect 建 S02 task，繼續推進 Phase 1
3. 每張 sub-task 完成後即時更新本 Resume Point

**handoff note**: 見對話紀錄（給 Codex 的完整 context 打包）
