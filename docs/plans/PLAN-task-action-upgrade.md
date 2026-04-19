---
spec: docs/specs/SPEC-task-governance.md
ac_test: tests/spec_compliance/test_task_action_upgrade_ac.py
created: 2026-04-19
status: in-progress
---

# PLAN: Task Action-Layer 升級（subtask / dispatcher / handoff）

實施 SPEC-task-governance §2026-04-19 Action-Layer 升級。9 條 AC + 14 項下游 SSOT 同步。

## Tasks

- [ ] **S01 — Schema + Domain migration**
  - Files: `src/zenos/domain/action/models.py`、`src/zenos/infrastructure/knowledge/sql_task_repo.py`（或 action dir）、`migrations/20260419_0001_task_action_layer_upgrade.sql`
  - 加 Task dataclass 三欄：`parent_task_id`、`dispatcher`、`handoff_events`
  - 加 HandoffEvent dataclass
  - Migration SQL：`ALTER TABLE tasks ADD COLUMN parent_task_id TEXT`、`ADD COLUMN dispatcher TEXT`、`ADD COLUMN handoff_events JSONB DEFAULT '[]'::jsonb`、兩個 index
  - Repo load/save 包含新欄位
  - Verify: `pytest tests/spec_compliance/test_task_action_upgrade_ac.py::test_ac_task_upg_01* -x`
  - Covers: AC-TASK-UPG-01

- [ ] **S02 — Validators（cross_plan / dispatcher namespace / handoff_events readonly）**
  - Files: `src/zenos/application/action/task_service.py` 或現有 validator 位置、`src/zenos/interface/mcp/write.py`
  - 實作三個 reject 條件
  - 加 error codes: `CROSS_PLAN_SUBTASK`、`INVALID_DISPATCHER`、warning `HANDOFF_EVENTS_READONLY`
  - Dispatcher 正則集中定義在 domain 層
  - Verify: `pytest tests/spec_compliance/test_task_action_upgrade_ac.py::test_ac_task_upg_0[234] -x`
  - Covers: AC-TASK-UPG-02, 03, 04

- [ ] **S03 — MCP `task(action="handoff")`**
  - Files: `src/zenos/interface/mcp/task.py`
  - 新 action branch：原子 append event + update dispatcher + auto status bump (to agent:qa 且 in_progress → review) + audit log
  - Input validation：`to_dispatcher` 必填 + namespace 檢查、`reason` 必填
  - Verify: `pytest tests/spec_compliance/test_task_action_upgrade_ac.py::test_ac_task_upg_05 -x`
  - Covers: AC-TASK-UPG-05
  - Depends: S01, S02

- [ ] **S04 — search(tasks) 新 filter**
  - Files: `src/zenos/interface/mcp/search.py`（tasks collection branch）
  - 加三個 filter：`dispatcher`、`parent_task_id`、`linked_entity`（後者掃 linked_entities array）
  - 驗證與 product_id filter 可 AND 組合
  - Verify: `pytest tests/spec_compliance/test_task_action_upgrade_ac.py::test_ac_task_upg_0[67] -x`
  - Covers: AC-TASK-UPG-06, 07
  - Depends: S01

- [ ] **S05 — `confirm(tasks, accepted=true)` append final handoff event**
  - Files: `src/zenos/interface/mcp/confirm.py` 或 `src/zenos/application/action/task_service.py` confirm path
  - `accepted=True` 時 auto-append `{to_dispatcher:"human", reason:"accepted", output_ref:entity_entries ids or null}`
  - `accepted=False` 時 append `{to_dispatcher:<原值>, reason:"rejected: <reason>"}` 並讓 status 回 `in_progress`
  - Verify: `pytest tests/spec_compliance/test_task_action_upgrade_ac.py::test_ac_task_upg_08 -x`
  - Covers: AC-TASK-UPG-08
  - Depends: S03

- [ ] **S06 — MCP docstrings（Downstream 1-3）**
  - Files: `src/zenos/interface/mcp/task.py` docstring、`src/zenos/interface/mcp/search.py` docstring、`src/zenos/interface/mcp/write.py` docstring
  - task.py：加 handoff action 說明 + 4 個 data 欄位
  - search.py：tasks collection docstring 加 3 個新 filter
  - write.py：tasks write 加 parent_task_id / dispatcher 欄位，明示 handoff_events readonly
  - Verify: Read 三檔 docstring 比對 spec 條文
  - Depends: S03, S04

- [ ] **S07 — governance_rules SSOT（Downstream 4）**
  - Files: `src/zenos/interface/governance_rules.py`（path TBC via search）
  - `rules["task"]` level=2 加三條：`DISPATCHER_NAMESPACE`、`CROSS_PLAN_SUBTASK`、`HANDOFF_EVENTS_READONLY`
  - 每條附 example + rationale
  - Verify: `governance_guide(topic="task", level=2)` 的 output 含三條新規則

- [ ] **S08 — Agent role skills（Downstream 5-8）**
  - Files: `skills/release/pm/SKILL.md`、`skills/release/architect/SKILL.md`、`skills/release/developer/SKILL.md`、`skills/release/qa/SKILL.md`
  - PM: 建 task 時 `dispatcher="agent:pm"`，完成 spec 後呼叫 task(handoff, to="agent:architect", output_ref=spec path)
  - Architect: 需 subtask 時必含 parent_task_id + 繼承 plan_id；完成 TD 後 handoff to agent:developer
  - Developer: 完成後 handoff to agent:qa，output_ref=commit SHA
  - QA: 驗收 PASS 走 confirm(accepted=true)；FAIL 走 task(handoff, to=<prev dispatcher>, reason="rejected: ...")
  - 四份 skill 加「handoff 呼叫範例」節
  - Verify: Read 四個 skill 比對有無 handoff 範例

- [ ] **S09 — Governance task-governance.md checklist（Downstream 9）**
  - Files: `skills/release/governance/task-governance.md`
  - 8-題 checklist 擴 10 題：+「是否該開 subtask 而非新 task？」+「dispatcher 有沒有依 namespace 規則填對？」
  - 建票範例加 dispatcher="agent:pm"

- [ ] **S10 — Workflow skills（Downstream 10-12）**
  - Files: `skills/release/workflows/feature.md`、`skills/release/workflows/debug.md`、`skills/release/workflows/implement.md`
  - 把 subagent chain 描述改為顯性 handoff chain
  - 每階段明示 `task(action="handoff", ...)` 呼叫

- [ ] **S11 — Related-spec review（Downstream 13-14, AC-TASK-UPG-09）**
  - Files: `docs/specs/SPEC-task-communication-sync.md`、`docs/specs/SPEC-task-view-clarity.md`、`docs/specs/SPEC-task-kanban-operations.md`
  - 逐份讀，若有 task 狀態流轉 / agent 互通 / 視圖 / kanban 描述與新升級衝突，改；無衝突加 reference
  - 每份 spec 的 updated 欄位調至 2026-04-19，含 changelog 條目

- [ ] **S12 — End-to-end smoke test + deploy**
  - 跑 `pytest tests/ -x --ignore=tests/integration`（2139+ test 全 PASS）
  - `./scripts/deploy_mcp.sh` Cloud Run
  - 實跑一次 full handoff chain：create PM task → handoff architect → developer → qa → confirm accepted
  - 驗證 get(task).handoff_events 有 4 條事件
  - 驗證 search(tasks, dispatcher="agent:qa") 正確過濾
  - Covers: End-to-end validation of all 9 AC on production

## Decisions

- **2026-04-19**：Milestone = `EntityType.GOAL`，不新增 entity type（避免 schema 膨脹）
- **2026-04-19**：Plan 維持 string grouper，不升 entity（ADR-028 Draft 不在本次範圍）
- **2026-04-19**：Subtask 硬強制繼承 parent.plan_id（cross-plan reject）— 確保 subtask 範圍夠小
- **2026-04-19**：handoff_events append-only — caller 不可直接 write，唯一入口是 `task(action="handoff")`
- **2026-04-19**：Dispatcher 正則集中在 domain 層，server 端強制驗證（rejects INVALID_DISPATCHER）
- **2026-04-19**：QA accept 時 auto-append 結束 handoff event — 閉環完整
- **iOS / Dashboard UI** 改造不納入本次 dispatch（用戶另外評估）

## Dispatch Order

```
Batch 1（可 parallel）: S01 schema + S02 validator 基礎
Batch 2（Batch 1 done）: S03 handoff action + S04 search filter
Batch 3（Batch 2 done）: S05 confirm integration + S06 docstrings
Batch 4（parallel with Batch 3）: S07 governance_rules + S09 task-governance checklist
Batch 5（parallel）: S08 role skills + S10 workflow skills + S11 related-spec review
Batch 6: S12 E2E + deploy + verify + commit
```

## Resume Point

尚未開始 dispatch。下一步：dispatch **Batch 1 (S01 + S02)** 給 Developer subagent。

## Post-Delivery

- 寫 journal（flow_type="feature"）
- 更新 PLAN status → `done`
- 關 task 記錄到 ZenOS `mcp__zenos__task`
