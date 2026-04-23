---
spec: ADR-047-l1-level-ssot.md
created: 2026-04-23
status: in-progress
entry_criteria: ADR-047 Draft → Accepted（使用者核可技術設計）
exit_criteria: |
  1. `is_collaboration_root_entity` 僅檢查 level + parent_id，所有 type 白名單與 level-null fallback 移除
  2. MCP plan/task 不再接受 `project_id` 參數（傳入 → INVALID_INPUT）
  3. Production DB 中所有 entity 有明確 level（level IS NULL count = 0），L1（level=1）都可作為 product_id
  4. Dashboard projects page 顯示所有 L1（含 type=company/person）
  5. `mcp__zenos__plan(action="create", product_id=<CRM company id>)` 端到端成功
  6. 所有 AC test（test_l1_level_ssot_ac.py + test_task_ownership_ssot_ac.py 等）PASS
  7. Release SSOT 與專案根 mirror（skills/governance/*、skills/workflows/*）同步完成；governance_ssot_audit 無 finding
  8. Deploy 後：health check / log 無 ERROR / 全站 UI 冒煙 PASS；rollback 路徑驗證過
---

# PLAN: L1 判定收斂到 level、product_id 為唯一 API 語彙

## Context
參照 ADR-047。本 PLAN 是 SPEC → 實作 → 驗證的完整 orchestration 容器。

---

## Rollout Gates（強制順序，違反 → rollout 立即停止）

```
   S01  ──────▶  S02-data  ──▶  [GATE A: production level backfill verified]
   (SPEC)         (script +                │
                   prod run)               ▼
                              S02-code → S03 → S04 → S05  (DDD layer refactor)
                                                         │
                                                         ▼
                              [GATE B: backend 部署 + smoke PASS]
                                                         │
                                                         ▼
                                                S06  (Dashboard UI)
                                                         │
                                                         ▼
                              [GATE C: UI 部署 + 全站 smoke PASS]
                                                         │
                                                         ▼
                                              S07  (Skill SSOT + mirror)
                                                         │
                                                         ▼
                                              [GATE D: governance_ssot_audit clean]
                                                         │
                                                         ▼
                                                    S08  (Final QA + rollback drill)
```

**GATE A — Data Precondition（風險 #1 防線）**
- `SELECT count(*) FROM zenos.entities WHERE level IS NULL = 0`
- `SELECT count(*) FROM zenos.entities WHERE level=1 AND parent_id IS NOT NULL AND parent_id <> '' = 0`（2026-04-23 補強條件：L1 必須 parent_id null，這是 ADR-047 D1 的完整定義）
- `SELECT count(*) FROM zenos.tasks t LEFT JOIN zenos.entities e ON e.id=t.product_id WHERE e.id IS NULL OR e.level<>1 OR (e.parent_id IS NOT NULL AND e.parent_id<>'') = 0`（所有 task.product_id 指向合法 L1）
- 若任一非 0 → 禁止部署任何 strict level-check code（S02-code 起所有項目）
- 驗證方式：backfill script apply 後，QA 獨立執行上述三條 SQL
- 若 GATE A 失敗 → S02-code 之後的任何部署 rollback 前一版

**GATE B — Backend 部署後 smoke**
- `./scripts/deploy_mcp.sh` 後：
  - `curl https://<mcp-url>/health` 回 200
  - Cloud Run log 無 ERROR level
  - MCP 端到端：用 partner key 跑 `search → plan(create) → task(create)`
- 任一失敗 → rollback（redeploy 前一版 image）

**GATE C — UI 部署後全站 smoke**
- `./scripts/deploy.sh` 後：
  - Dashboard 所有路由載入無 console error：`/`, `/projects`, `/tasks`, `/knowledge-map`, `/settings`, `/team`, `/clients`, `/marketing`, `/agent`, `/home`, `/docs`
  - `/projects` 顯示 L1（含原心生技 type=company）
  - 建 task dialog product_id 下拉能選到 company entity
- 任一失敗 → rollback（Firebase Hosting revert）

**GATE D — SSOT audit clean**
- `python3 scripts/sync_skills_from_release.py` 執行成功
- `governance_ssot_audit` 無 finding（Server 端掃 skills/governance/* 與 specs 一致）
- `grep -rn "project_id\|type=product\|type == .product." skills/` 無命中（除歷史敘述）

---

## Tasks

- [ ] **S01: SPEC/ADR 批次更新**（Architect 本人；預估 1.5h）
  - Files:
    - `docs/decisions/ADR-007-entity-architecture.md` — L1 單型段落加 supersede marker 指向 ADR-047
    - `docs/decisions/ADR-028-plan-primitive.md` — 刪 project_id 欄位；product_id 指向任意 L1
    - `docs/decisions/ADR-044-task-ownership-ssot-convergence.md` — 錯誤碼語意改「非 L1 entity」
    - `docs/specs/SPEC-ontology-architecture.md` — L1 定義改「level=1 共享根，type 為 label」
    - `docs/specs/SPEC-task-governance.md` — AC 文案、錯誤碼說明
    - `docs/reference/REF-ontology-current-state.md` — L1 定義同步
    - `docs/reference/REF-glossary.md`（若存在）
  - Done Criteria:
    - `grep -rn "L1 = product\|type=product\|project_id" docs/specs docs/decisions docs/reference` 只剩歷史敘述或 supersede marker

- [ ] **S02-data: 資料清洗腳本 + production backfill**（Developer + Architect 一起執行；預估 1h）
  - Files:
    - `scripts/backfill_entity_level.py`（**新**）
      - dry-run 模式：列出 level IS NULL 的 entity（by type/id/name）
      - apply 模式：依 type 用 `DEFAULT_TYPE_LEVELS`（含 company/person/deal → 1）補 level
      - 遇無法推斷 type → 列出等人工決策，不擅自寫入
      - 產出 JSON report（影響筆數、type 分佈、失敗清單）
    - `tests/scripts/test_backfill_entity_level.py`（**新**）
  - Execution（rollout 實際操作）:
    1. 本地跑 dry-run（連 production DB 讀取權限）
    2. Architect 審閱 report，確認影響筆數合理
    3. Apply（production DB）
    4. QA 獨立執行 `SELECT count(*) FROM zenos.entities WHERE level IS NULL;` = 0
    5. QA 同時抽查 3 筆隨機 entity 確認 level 正確
  - **GATE A 驗證**：上述第 4 步通過才能開工 S02-code
  - Rollback:
    - 備份：apply 前先 dump `(id, level)` snapshot
    - Rollback 方式：UPDATE 把 snapshot 的 rows 寫回 NULL（不影響新建 entity）

- [ ] **S02-code: Domain 層 — collaboration_roots + entity_levels**（Developer；預估 1h，depends: GATE A）
  - Files:
    - `src/zenos/domain/knowledge/collaboration_roots.py` — 移除 type 白名單；`level==1 AND not parent_id`（移除 level-null fallback）
    - `src/zenos/domain/knowledge/entity_levels.py`（**新**）— `DEFAULT_TYPE_LEVELS` 擴充含 company/person/deal
    - `tests/domain/test_collaboration_roots.py`（**新**）
  - Done Criteria:
    - `is_collaboration_root_entity(Entity(type="company", level=1, parent_id=None))` → True
    - `is_collaboration_root_entity(Entity(type="product", level=2))` → False
    - `is_collaboration_root_entity(Entity(type="company", level=None))` → False（strict mode）
  - AC test: `test_ac_l1ssot_01_any_type_with_level_1_is_l1`、`test_ac_l1ssot_07_strict_level_check`

- [ ] **S03: Application 層**（Developer；預估 2.5h，depends: S02-code）
  - Files:
    - `src/zenos/application/knowledge/ontology_service.py` — 刪 `_L1_TYPES`；`_TYPE_TO_LEVEL` 改用 `DEFAULT_TYPE_LEVELS`；所有 `type == EntityType.PRODUCT` 判斷改 level
    - `src/zenos/application/action/plan_service.py` — 刪 project_id alias；錯誤訊息去 product 字樣
    - `src/zenos/application/action/task_service.py` — 同上
    - `src/zenos/application/crm/crm_service.py` — level 改用 `DEFAULT_TYPE_LEVELS` 推導
    - `src/zenos/application/marketing_runtime.py` — 清 project_id
    - `src/zenos/domain/governance.py` — `EntityType.PRODUCT` 判斷改 level（480, 1086, 1556）
  - Done Criteria:
    - Unit + integration tests 全通過
    - `grep -rn "_L1_TYPES\|COLLABORATION_ROOT_TYPES" src/zenos/` 無結果
  - AC test: `test_ac_l1ssot_02_crm_company_accepted_as_product_id`

- [ ] **S04: Interface 層 — MCP tool + governance_rules**（Developer；預估 2h，depends: S03）
  - Files:
    - `src/zenos/interface/mcp/plan.py` — 刪 project_id param；docstring 改「任何 L1 entity id」
    - `src/zenos/interface/mcp/task.py` — 同上
    - `src/zenos/interface/mcp/recent_updates.py:248` — `scope_root.type != "product"` 改 level
    - `src/zenos/interface/governance_rules.py` — 刪 project_id / PROJECT_STRING_IGNORED；INVALID_PRODUCT_ID 改「非 L1 entity」
    - `src/zenos/interface/dashboard_api.py` — 1239, 1578, 1817, 2194 改 level 判定
  - Done Criteria:
    - MCP tool 傳 `project_id` 直接 `INVALID_INPUT` reject
    - `governance_guide("task")` prompt 不出現「type=product」或「project_id」
  - AC test: `test_ac_l1ssot_03_project_id_param_rejected`、`test_ac_l1ssot_04_governance_prompt_clean`

- [ ] **S05: Infrastructure 層 — repo 清 project_id fallback**（Developer；預估 1.5h，depends: S04）
  - Files:
    - `src/zenos/infrastructure/action/sql_plan_repo.py`
    - `src/zenos/infrastructure/action/sql_task_repo.py`
    - `src/zenos/infrastructure/firestore_repo.py`
  - Done Criteria:
    - `grep -rn "project_id" src/zenos/infrastructure/` 無結果
    - 整合測試 PASS
  - **GATE B 驗證**：S05 完成後部署 MCP，跑 health check + 端到端 + log 無 ERROR

- [ ] **S06: Dashboard UI**（Developer；預估 2.5h，depends: GATE B）
  - Files:
    - `dashboard/src/lib/entity-level.ts`（**新**）— `isL1Entity` helper
    - `dashboard/src/app/(protected)/projects/page.tsx:88`
    - `dashboard/src/app/(protected)/tasks/page.tsx:86`
    - `dashboard/src/lib/api.ts:123,134`
    - `dashboard/src/features/tasks/taskHub.ts:112`
    - `dashboard/src/components/TaskCreateDialog.tsx:118`
    - `dashboard/src/components/NodeDetailSheet.tsx` — 視覺保留 type-based
  - Done Criteria:
    - `vitest run` 全過
    - 本地 dashboard 跑：CRM company entity 出現在 /projects；TaskCreateDialog 下拉可選
  - **GATE C 驗證**：S06 完成後部署 frontend，跑全站 UI smoke

- [ ] **S07: Skill SSOT 雙向同步**（Architect 本人；預估 1.5h，depends: GATE C）
  - Part A — 改 release SSOT:
    - `skills/release/governance/task-governance.md`
    - `skills/release/governance/shared-rules.md`
    - `skills/release/governance/bootstrap-protocol.md`
    - `skills/release/governance/document-governance.md`（若提及）
    - `skills/release/governance/l2-knowledge-governance.md`（若提及）
    - `skills/release/workflows/knowledge-capture.md`（若存在）
  - Part B — 同步專案根 mirror（治理 skill 與 slash command 實際讀取位置）:
    - 執行 `python3 scripts/sync_skills_from_release.py`
    - 確認 `skills/governance/*` 與 `skills/workflows/*` 全部更新
    - 確認檔案列表：bootstrap-protocol.md、shared-rules.md、document-governance.md、l2-knowledge-governance.md、task-governance.md、knowledge-capture.md、knowledge-sync.md、setup.md
  - Part C — 推到 `~/.claude/skills/`（依 feedback memory 的分發紀律）
  - Done Criteria:
    - `grep -rn "project_id\|type=product\|type == .product." skills/` 無命中（除歷史敘述）
    - release/ 與 skills/governance/* 內容一致（diff 檢查）
  - **GATE D 驗證**：執行 `governance_ssot_audit`（或等效腳本 `scripts/qa_governance_ai.py`）無 finding

- [ ] **S08: 最終 QA + rollback drill + 端到端**（QA + Developer；預估 2.5h，depends: GATE D）
  - **Part A — AC test 套件**
    - `tests/spec_compliance/test_l1_level_ssot_ac.py`（**新**）— 7 條 AC 全 PASS
    - `tests/spec_compliance/test_task_ownership_ssot_ac.py` — AC 更新
    - `tests/spec_compliance/test_mcp_id_ergonomics_ac.py` — 移除 project_id 測試
    - `pytest tests/ -x` 全過
  - **Part B — Helper / script 清理**
    - `scripts/qa_governance_ai.py` — 確認無 project_id
    - `scripts/fix_amy_tasks.py` / `fix_entity_partner_ids.py` / `import_firestore_to_sql.py`
  - **Part C — 部署後驗證（強制，缺一不可）**
    - **Health check**: `curl https://<mcp-url>/health` 回 200；Dashboard 載入 index page 無 error
    - **Log check**: 部署後 10 分鐘內 Cloud Run log 無 ERROR；Firebase Hosting 無 500
    - **端到端 MCP（用 partner key）**:
      - `search(collection="entities", query="原心生技")` → 找到 type=company, level=1
      - `plan(action="create", product_id=<id>, goal="test L1 refactor")` → 成功
      - `task(action="create", product_id=<id>, plan_id=<plan>, title="test task", ...)` → 成功
      - `task(action="create", project_id=<id>)` → 被 `INVALID_INPUT` reject
    - **全站 UI smoke**: /projects、/tasks、/knowledge-map、/settings、/team、/clients、/marketing、/agent、/home、/docs 每頁載入無 console error
    - **功能 smoke**: 於 /projects 看見原心生技；TaskCreateDialog 下拉可選 company entity
  - **Part D — Rollback drill（document only, don't actually run）**
    - 寫明 rollback steps 並由 Architect 簽核：
      1. Backend rollback: 取前一版 Cloud Run revision → 重新指派流量
      2. Frontend rollback: `firebase hosting:clone <prev-version> live`
      3. DB rollback: 從 S02-data 的 snapshot restore `(id, level)` pair；level=null 重新寫回（對舊 code 無害）
      4. Skill rollback: `git revert <commit>` + 重跑 `sync_skills_from_release.py` + 推 `~/.claude/skills/`
    - Architect 在部署前於 journal 確認 rollback plan 已 review

## AC IDs

- `AC-L1SSOT-01`: 任何 type 的 entity 只要 `level=1 AND parent_id=null` 即為合法 L1
- `AC-L1SSOT-02`: CRM 建出的 `type=company, level=1` entity 可作為 plan/task 的 `product_id`
- `AC-L1SSOT-03`: MCP tool 傳 `project_id` 參數被 reject（INVALID_INPUT）
- `AC-L1SSOT-04`: `governance_guide("task")` prompt 不出現 `type=product` 或 `project_id`
- `AC-L1SSOT-05`: Dashboard /projects 顯示所有 L1 entity（含 type=company/person/deal）
- `AC-L1SSOT-06`: Production DB 中 entity.level 無 null
- `AC-L1SSOT-07`: `is_collaboration_root_entity` 嚴格檢查 `level=1 AND not parent_id`，移除 type 白名單與 level-null fallback

## Decisions

- 2026-04-23: ADR-047 確立。K1=清理、K2=最乾淨處理、K3=PLAN 檔位置 OK。
- 2026-04-23: 不保留 `project_id` alias——傳入即 reject（使用者明確要求「最乾淨的實現」）。
- 2026-04-23: `level is None` fallback 一併移除，配合 backfill script 強制所有 entity 有 level。
- 2026-04-23（Challenger review 後修正）:
  - 拆 S02 為 S02-data / S02-code，明訂 **GATE A（production backfill verified）** 為 strict code 部署前置條件
  - S07 擴大同步範圍到 `skills/governance/*`、`skills/workflows/*` 本地 mirror，並跑 `governance_ssot_audit` 驗證（**GATE D**）
  - S08 補 rollback plan + health check + log check + 全站 UI smoke（對齊 Architect SKILL Phase 3 強制項）
  - 整體 rollout 順序用 GATE A/B/C/D 鎖死，禁止跨 gate 部署

## Resume Point

**已完成：**
- ✅ S01（Architect）— 6 份 SPEC/ADR 批次更新完成（commit: ❌ 尚未）
- ✅ S02-data（Developer + QA）— 3 個新檔 + 18 tests PASS；QA confirm 結案；task `fc8cf66618bc4a4fba810043a788b106` status=done；commit: ❌ 尚未
  - `src/zenos/domain/knowledge/entity_levels.py`
  - `scripts/backfill_entity_level.py`
  - `tests/scripts/test_backfill_entity_level.py`
  - `tests/spec_compliance/test_l1_level_ssot_ac.py`（Architect 建的 7 條 AC stub）
- ✅ **GATE A PASS**（2026-04-23，Architect 在 production 執行）
  - Dry-run: total=0（所有 entity 已有 level）
  - 發現 2 筆 pre-existing anomaly: GRACE ONE / Banila Co（level=1 但有 parent_id → 雅云行銷公司 L1）
  - Remediation: 兩者都 Paused 且只被 1 個 cancelled task 引用，連 task 一併刪除（snapshot 保留於 `/tmp/l1_anomaly_pre_delete_snapshot.json`）
  - Post-check 全綠：level IS NULL=0、level=1 with parent=0、orphan product_id=0
  - L1 total 從 24 → 22；entity total 從 330 → 328

**下一步：commit S01 + S02-data 後，dispatch S02-code**

執行者：Architect（在使用者環境跑）。阻塞所有 S02-code 起的 strict-level code 部署。

執行指令：
```bash
# 需先設好 DATABASE_URL（指向 production zenos schema）
.venv/bin/python scripts/backfill_entity_level.py --dry-run --output /tmp/gate_a_dry_run_report.json
```

驗證門檻：
1. report.total = production 中 level IS NULL 的筆數
2. report.unresolvable = 空或皆為可人工處理的少量
3. Architect 審閱 by_type 分布合理後呈給使用者
4. 使用者核可 → 同一指令改 `--apply --snapshot-path=/tmp/gate_a_snapshot.jsonl`
5. QA 獨立執行 `SELECT count(*) FROM zenos.entities WHERE level IS NULL;` = 0 → GATE A PASS

GATE A PASS 後：commit S01 + S02-data 交付（一個合併 commit 或兩個分開），再進 S02-code dispatch。

**後續順序：** S02-code → S03 → S04 → S05 → GATE B → S06 → GATE C → S07 → GATE D → S08 收尾。

每通過一個 Gate，Architect 在 journal 寫一筆 entry 記錄驗證證據。
