---
type: INDEX
id: refactor-index-ontology-grand-2026-04-23
status: active
plan_id: a251aac4433f42e4939fec993675718f
created: 2026-04-23
---

# Ontology Grand Refactor — Spec Index

一切以 **SPEC 為出發**。SPEC 改完，ADR 隨之 supersede，TD/PLAN 跟著對齊。

**Axioms（鎖定後不再重述）**：Entity=graph node / Base=identity+permission+parent+owner / 無 JSON blob / 繼承擴充 / Schema 強制 / MCP tool 最小化。

**架構決策**：Action Layer 併入 Knowledge Layer / Goal 消失統一 Milestone / Subtask 保留（agent 派工用）。

---

## Core SPECs（必改，依序）

| # | Spec | Action | 核心動作 |
|---|------|--------|---------|
| 1 | `SPEC-ontology-architecture` | ✅ **REWRITTEN v2** + R1 修正 | 6 axioms 骨幹 / BaseEntity + SemanticMixin / 5 subclass / MTI DDL。Axiom 3 措辭改（禁 unschemed blob、允許 typed JSON）；§7.2 L2 lifecycle 改兩維模型（confirmed_by_user + status）；§11.2 每 subclass status 表補齊 CHECK constraint |
| 2 | `SPEC-l2-entity-redefinition` | ✅ **SUPERSEDED stub** → 主 SPEC §5/§7/§11 | 三問 + impacts gate + lifecycle 合併進主 SPEC |
| 3 | `SPEC-identity-and-access` | ✅ **PATCHED** + R1 修正 | frontmatter updated / canonical_schema_from；Layering note 引主 SPEC §4+§13；§3.2 task/plan/milestone/subtask 標 L3-Action subclass；§4.1 Visibility 引主 SPEC §13 為 canonical |
| 4 | `SPEC-governance-framework` | ✅ **PATCHED** + R1 修正 | frontmatter 更新；六維表格改列 L2 / L3-Document / L3-Action；所有 `SPEC-l2-entity-redefinition` 引用替換為主 SPEC |
| 5 | `SPEC-zenos-core` | ✅ **PATCHED** + §5 整節改寫 | §3.1 更新；§5 整節廢止舊 Task/Plan/Subtask「不是 entity」敘述，改為 L3-Action subclass 邊界宣告 + 指向主 SPEC §9 |
| — | `REF-active-spec-surface` | ✅ **UPDATED** | Tier 1 加主 SPEC、governance-framework、IAM、zenos-core、mcp-tool-contract；SPEC-l2-entity-redefinition 移出 |

---

## L3 subclass SPECs（改行為，不改存在）

| # | Spec | Action | 核心動作 |
|---|------|--------|---------|
| 6 | `SPEC-task-governance` | ✅ **REWRITTEN** | 1339 → 約 280 行；砍掉所有 schema 重定義，治理規則 only；status state machine 指回主 SPEC §11.2；補 AC-TASK-01..10；Subtask 明確為 agent 派工單位；Plan 閉環 + Milestone completion 閘齊 |
| 7 | `SPEC-doc-governance` | ✅ **REWRITTEN** + absorb | 613 行收斂為單一權威；吸收 SPEC-document-bundle（doc_role/sources/bundle_highlights/source platform/rollout）與 SPEC-doc-source-governance；schema canonical 指回主 SPEC §8.1；補 AC-DOC-01..25 |
| 8 | `SPEC-doc-source-governance` | ✅ **MERGED** → redirect stub | 重定向到 SPEC-doc-governance（原指向 SPEC-document-bundle）|
| 9 | `SPEC-document-bundle` | ✅ **MERGED** → redirect stub | 664 行內容併入 SPEC-doc-governance；保留 stub 避免舊連結失效 |
| 10 | `SPEC-document-delivery-layer` | ✅ **KEPT + aligned** | frontmatter 對齊；補 sidecar 定位聲明（revision / share_token 是 L3-Document 的 sidecar tables，不動 canonical schema）|
| 11 | `SPEC-batch-doc-governance` | ✅ **REVISED** | frontmatter 格式修正（doc_id→id / version 移除 / date→created/updated）；supersedes 指向改 SPEC-doc-governance；加 Layering note 聲明不重定義 source schema |

---

## L2 / Entry / Relationship 補強 SPECs

| # | Spec | Action |
|---|------|--------|
| 12 | `SPEC-entry-consolidation-skill` | ✅ **REVISED** | frontmatter 對齊（ontology_entity: TBD→l2, depends_on）；加 Layering note 指主 SPEC §7.3 canonical；相關文件改指主 SPEC |
| 13 | `SPEC-entry-distillation-quality` | ✅ **REVISED** | frontmatter 修正（l2_entity→ontology_entity, depends_on）；Layering note 區隔「寫入前品質閘」vs「飽和後 consolidation」；Spec 相容性章節重寫，`SPEC-l2-entity-redefinition` 引用改指主 SPEC §7 |
| 14 | `SPEC-impact-chain-enhancement` | ✅ **MERGED** → redirect stub | canonical 移至主 SPEC §10.4（forward/reverse impact chain, 5 跳, cycle防呆, truncated flag）；保留 Implementation 歷史 |
| 15 | `SPEC-knowledge-graph-semantic` | ✅ **MERGED** → redirect stub | P0.2 shipped → 主 SPEC §10.4；P0.1/P1.3/P1.4/P1.5 REJECTED 歷史保留；拓撲偵測邊界留在 §10.5 |
| 16 | `SPEC-semantic-retrieval` | ✅ **KEPT + aligned** | frontmatter depends_on 指主 SPEC §10.4 + §12；Layering note 聲明 embedding schema canonical 已進主 SPEC，本 SPEC 只管行為層 |
| 17 | `SPEC-knowledge-map-health-indicator` | ✅ **KEPT + aligned** | frontmatter 對齊；Layering note 聲明 UI-only，計算邏輯與拓撲邊界指向 governance 系列 + 主 SPEC §10.5 |

---

## Governance 延伸 SPECs（revise）

| # | Spec | Action |
|---|------|--------|
| 18 | `SPEC-governance-feedback-loop` | ✅ **REVISED** | frontmatter 對齊（ontology_entity: TBD → governance-framework, depends_on）；`SPEC-l2-entity-redefinition` 引用改指主 SPEC v2 §7.1 |
| 19 | `SPEC-governance-guide-contract` | ✅ **REVISED** | frontmatter 對齊 + runtime_canonical；topic 對照表加 runtime `_VALID_TOPICS` 與 `mcp/governance.py:71-79` 版本映射；`entity` 改指主 SPEC §7，`bundle` 改指 SPEC-doc-governance §3；P0-4 gate 描述同步 |
| 20 | `SPEC-governance-observability` | ✅ **REVISED** | 補 frontmatter（原檔無）；`SPEC-document-bundle` 兩處引用改指 SPEC-doc-governance §3/§3.4 |
| 21 | `SPEC-governance-audit-log` | ✅ **KEPT + aligned** | 原檔無 frontmatter，補齊；depends_on 補 governance-framework / observability |
| 22 | `SPEC-progressive-trust` | ✅ **KEPT + aligned** | frontmatter ontology_entity: TBD → governance-framework；depends_on 補 IAM |

---

## MCP tool SPECs（Axiom 6 主戰場）

| # | Spec | Action | 核心動作 |
|---|------|--------|---------|
| 23 | `SPEC-mcp-tool-contract` | ✅ **UPGRADED** | 重新定位為 runtime-verified SSOT：frontmatter 加 runtime_canonical；§4 tool roster 升級為 `file:line` 對照表（19 tools）；§8 補齊 `search / get / task / confirm` 完整 contract + 新增 §8.9 `plan` / §8.10 `batch_update_sources` / §8.11 `recent_updates` / §8.12 共通約束；新增 §13 `AC-MCP-01..32` 32 條 AC，每條附 runtime file:line；`SPEC-document-bundle` 引用全改 SPEC-doc-governance。未按原計畫做 polymorphic 合併（runtime 仍是分開 tool，那是未來 breaking change） |
| 24 | `SPEC-mcp-tool-contract-fixes` | ✅ **MERGED** → redirect stub | 保留 Issue → 新位置對照表；指向 SPEC-mcp-tool-contract canonical |
| 25 | `SPEC-mcp-opt-in-include` | ✅ **KEPT + aligned** | frontmatter 對齊；depends_on 補主 SPEC §10.4 + mcp-tool-contract |
| 26 | `SPEC-mcp-id-ergonomics` | ✅ **KEPT + aligned** | frontmatter ontology_entity: zenos-mcp → mcp-interface；depends_on 補 mcp-tool-contract |

---

## Agent contract SPECs

| # | Spec | Action |
|---|------|--------|
| 27 | `SPEC-agent-integration-contract` | ✅ **REVISED** | frontmatter 對齊（ontology_entity: agent-integration → agent-runtime），depends_on 補齊 MCP + governance + doc + task + auth-federation |
| 28 | `SPEC-agent-context-summary` | ✅ **KEPT + aligned** | 舊 frontmatter 格式修正（doc_id / version / date / lowercase status → 標準格式） |
| 29 | `SPEC-agent-setup` | ✅ **KEPT + aligned** | frontmatter ontology_entity: TBD → agent-runtime；depends_on 補 MCP + agent-integration |
| 30 | `SPEC-agent-skill-addon` | ✅ **KEPT + aligned** | frontmatter ontology_entity: TBD → agent-runtime；depends_on 補齊 |

---

## Task UI SPECs（subclass 後 UI 分工可能變）

| # | Spec | Action |
|---|------|--------|
| 31 | `SPEC-task-view-clarity` | ✅ **REVISED** | frontmatter 標準化（`l2_entity` → `ontology_entity: l3-action`，補 runtime_canonical 三條：`dashboard/src/types/index.ts:191` / `lib/task-risk.ts` / `SPEC-mcp-tool-contract §9`）；**legacy status enum 全清**：`backlog / blocked / archived` → canonical 5-state；§名詞重寫 `open / closed / overdue / upcoming / idle_todo`（對齊 `task-risk.ts`）；AC-R1/R2/R4/R9/R10 全部改用 canonical 5-state |
| 32 | `SPEC-task-kanban-operations` | ✅ **REVISED** | frontmatter 標準化；R6 Review：Approve 必走 `confirm(accepted=True)` 而非 `task.update status=done`（`SPEC-mcp-tool-contract §8.5`）；Reject 的 `rejection_reason` 改必填（`task_service.py:664-665`），退回 dispatcher = `task.dispatcher or "human"`（**不自動派 developer**）；**R8 drop-target matrix 改以 `task_rules.py:19-33` 為準**：`cancelled` 是唯一 terminal，`done → todo` reopen 合法；`todo → review` 不存在（必須經 `in_progress`）|
| 33 | `SPEC-task-surface-reset` | ✅ **KEPT + aligned**（撤回原 DELETE 判斷）| frontmatter 從 mixed（`doc_id / title / version / date / l2_entity`）收斂為標準格式；加 Layering note 說明本 SPEC 是 UI screen boundary，**與 task-governance 正交**；舊索引判斷本檔被 task-governance 取代不成立（該 SPEC 2026-04-22 新建晚於索引） |
| 34 | `SPEC-task-communication-sync` | ✅ **REVISED** | frontmatter `ontology_entity: action-layer → l3-action`；補 Layering note + depends_on |

---

## Feature SPECs（不主動改，只掃 grep 舊術語替換）

| # | Spec | Action |
|---|------|--------|
| 35 | `SPEC-crm-core` | ✅ frontmatter | ontology_entity: crm-客戶管理 → crm；depends_on 補齊 |
| 36 | `SPEC-crm-intelligence` | ✅ frontmatter | 舊格式（doc_id/title/version/date/l2_entity）→ 標準；updated 日期同步 |
| 37 | `SPEC-marketing-automation` | ✅ frontmatter | 同上；ontology_entity → marketing-automation |
| 38 | `SPEC-dashboard-ai-rail` | ✅ frontmatter | 同上；ontology_entity: TBD → dashboard |
| 39 | `SPEC-dashboard-onboarding` | ✅ frontmatter | l2_entity: Dashboard 知識地圖 → ontology_entity: dashboard |
| 40 | `SPEC-dashboard-v2-ui-refactor` | ✅ frontmatter | 原無 frontmatter block，補齊 type/id/status/ontology_entity/created/updated/depends_on |
| 41 | `SPEC-client-portal` | ✅ frontmatter | ontology_entity: TBD → dashboard |
| 42 | `SPEC-zen-ink-real-data` | ✅ frontmatter | 補 ontology_entity + updated + extends：SPEC-zen-ink-redesign |
| 43 | `SPEC-zen-ink-redesign` | ✅ frontmatter | 補 ontology_entity + updated |
| 44 | `SPEC-federation-auto-provisioning` | ✅ frontmatter | doc_id/title/version/date 舊格式清理 |
| 45 | `SPEC-home-workspace-bootstrap` | ✅ frontmatter | ontology_entity: 夥伴身份與邀請 → identity-and-access |
| 46 | `SPEC-cowork-knowledge-context` | ✅ frontmatter + content | SPEC-knowledge-graph-semantic 三處引用改指主 SPEC §10.4 / §10.5 |
| 47 | `SPEC-partner-context-fix` | ✅ frontmatter | 原無 frontmatter block，補齊 |
| 48 | `SPEC-user-department` | ✅ frontmatter | l2_entity → ontology_entity: identity-and-access |
| 49 | `SPEC-recent-change-surfacing` | ✅ frontmatter | ontology_entity: MCP 介面設計 → mcp-interface；補 depends_on |
| 50 | `SPEC-project-progress-console` | ✅ frontmatter + content | 同上；line 78 的 legacy status enum `backlog,blocked` → canonical 5-state |
| 51 | `SPEC-docs-native-edit-and-helper-ingest` | ✅ frontmatter + content | SPEC-document-bundle 全部引用改指 SPEC-doc-governance §3；Layering note 加入 |
| 52 | `SPEC-ingestion-governance-v2` | ✅ frontmatter + content | SPEC-l2-entity-redefinition → 主 SPEC v2 §7 |
| 53 | `SPEC-zentropy-ingestion-contract` | ✅ frontmatter + content | 多處 SPEC-l2-entity-redefinition 改指主 SPEC v2 §7 |
| 54 | `SPEC-google-workspace-per-user-retrieval` | ✅ frontmatter | ontology_entity 規範化 |
| 55 | `SPEC-skill-packages` | ✅ frontmatter | l2_entity → ontology_entity: agent-runtime |
| 56 | `SPEC-skill-release-management` | ✅ frontmatter | ontology_entity: agent-integration → agent-runtime |
| 57 | `SPEC-zenos-external-integration` | ✅ frontmatter | 同上 |
| 58 | `SPEC-zenos-auth-federation` | ✅ frontmatter | updated + depends_on |
| 59 | `SPEC-zenos-setup-redesign` | ✅ frontmatter | ontology_entity: TBD → agent-runtime；version_note 抽出 |
| 60 | `SPEC-product-vision` | ✅ frontmatter | ontology_entity: TBD → product-vision |
| 61 | `SPEC-aha-moment` | ✅ frontmatter | 舊格式（doc_id/title/version/lowercase status）→ 標準 |

---

## ADRs（supersede / keep / delete）

### 被新 master ADR-048 supersede（舊決策失效）
| ADR | 原議題 | 如何處理 | 2026-04-23 標記狀態 |
|-----|--------|---------|------|
| ADR-006 entity-project-separation | project vs entity 分離 | SUPERSEDE | ✅ marked |
| ADR-007 entity-architecture | Entity 分層模型 | SUPERSEDE | ✅ marked |
| ADR-010 entity-entries | L2 entries 結構 | SUPERSEDE | ✅ marked |
| ADR-022 document-bundle-architecture | doc_role / bundle | SUPERSEDE | ✅ marked |
| ADR-025 zenos-core-layering | Knowledge / Action Layer 分離 | SUPERSEDE | ✅ marked |
| ADR-027 layer-contract | Layer 契約 | SUPERSEDE | ✅ marked |
| ADR-028 plan-primitive | Plan 獨立 collection | **SUPERSEDED** — Wave 9 已將 Plan 落地為 L3-Action subclass | ✅ superseded_by ADR-048 |
| ADR-032 document-delivery-layer-architecture | delivery 方案 | **Partial**（doc bundle 部分併入 SPEC-doc-governance §3；sidecar tables 仍 canonical）| ✅ status=Approved，章節級收斂用 `partially_superseded_sections` / `retained_canonical_sections` frontmatter field 表達；避免非 enum 的 `Partial Supersede` status |
| ADR-041 pillar-a-semantic-retrieval | embedding 放 entities 表 | **Partial** — embedding 改為 sidecar table（主 SPEC v2 §12）；retrieval 行為仍 canonical | ✅ 同上 frontmatter 處理 |
| ADR-044 task-ownership-ssot | task.project_id → product_id | **SUPERSEDED** — storage 已收斂到 `entities_base.parent_id` tree；API contract 留在 SPEC-task-governance | ✅ superseded_by ADR-048 |
| ADR-045 protocol-collection-vs-view | Protocol 是 collection 非 view | KEEP — Protocol 判定仍有效 | 未加 marker |
| ADR-046 document-entity-boundary | Document 合併 Entity | **Spec 目標態已落地，runtime 尚未** — 仍保留 Approved | status=Approved；runtime `Document` dataclass 仍活於 `src/zenos/domain/knowledge/models.py:88`，治理邏輯雙路徑（`governance.py:223-230`）；由 `PLAN-data-model-consolidation` 收口後再改 Superseded |
| ADR-047 l1-level-ssot | L1 由 level 判定 | **SUPERSEDED** — axiom 與 runtime enforcement 收斂進主 SPEC v2 + ADR-048 | ✅ superseded_by ADR-048 |

### 保留（未被取代）
| ADR | 議題 |
|-----|------|
| ADR-001 marketing-automation-architecture | Marketing 架構，不動 |
| ADR-002 knowledge-ontology-north-star | 北極星 |
| ADR-003 (both) | Governance trigger / Phase 1 MVP |
| ADR-004 ontology-output-path | |
| ADR-005 (both) | Dashboard graph lib / MCP tool consolidation |
| ADR-008 dashboard-multi-view | |
| ADR-009 permission-model | 被 SPEC-identity-and-access 擴充但 ADR 保留 |
| ADR-011 crm-module-architecture | |
| ADR-012 mcp-write-safety | |
| ADR-013 distributed-governance | |
| ADR-014 journal-entry-distillation | |
| ADR-015 auth-enhancement | |
| ADR-016 universal-governance-bootstrap | |
| ADR-017 skill-agent-install-architecture | |
| ADR-018 identity-access-runtime-alignment | |
| ADR-019 active-workspace-federated-sharing | |
| ADR-020 passive-governance-health-signal | |
| ADR-021 knowledge-map-health-indicator | |
| ADR-023 dashboard-onboarding | |
| ADR-024 mcp-multi-workspace-context | |
| ADR-026 module-boundary | DDD 四層仍有效 |
| ADR-029 auth-federation-runtime | |
| ADR-030 mcp-authorization-hardening | |
| ADR-031 zentropy-ingestion-governance-boundary | |
| ADR-033 marketing-automation-runtime-and-packages | |
| ADR-034 web-cowork-local-helper-bridge | |
| ADR-035 marketing-project-information-architecture | |
| ADR-036 writing-style-skill-storage-and-composition | |
| ADR-037 crm-intelligence-architecture | |
| ADR-038 governance-ssot-convergence | |
| ADR-039 l3-bundle-llm-dependency-removal | |
| ADR-040 mcp-read-api-opt-in-include | |
| ADR-042 entry-source-tiering | |
| ADR-043 multi-tenant-deployment-architecture | |

### ✅ 已建立（2026-04-23）
| ADR | 議題 |
|-----|------|
| **[ADR-048 Grand Ontology Refactor（master）](decisions/ADR-048-grand-ontology-refactor.md)** | ✅ 已建立 — 整體 refactor 總宣告 + supersede 9+ 份舊 ADR 清單 + 鎖定 6 axioms + 6 份 canonical SPEC |

---

## TDs（technical design）

**Action**：TD 屬實作歷史紀錄，新 master ADR 落地後可選擇刪除或改「superseded by PLAN-a251aac4」。

| TD | Action |
|----|--------|
| TD-foundation-p0-entity-schema | ✅ **SUPERSEDED stub** → SPEC-ontology-architecture v2 |
| TD-l2-entity-redesign | ✅ **SUPERSEDED stub** → 主 SPEC v2 §7 |
| TD-three-layer-architecture | ✅ **SUPERSEDED stub** → 主 SPEC v2 + SPEC-zenos-core |
| TD-action-layer | ✅ **SUPERSEDED stub** → SPEC-task-governance + 主 SPEC v2 §9 |
| TD-action-layer-mcp-interface | ✅ **SUPERSEDED stub** → SPEC-mcp-tool-contract + SPEC-task-governance |
| TD-service-architecture | ✅ **REVISED** — 保留歷史內容，補 2026-04-23 Layering note 指向六份 canonical SPEC |
| TD-doc-primary-parent-remediation | KEEP — 歷史 remediation |
| TD-distributed-governance | KEEP |
| 其餘 TD（CRM / marketing / dashboard / federation / ingestion / semantic-retrieval / opt-in / id-ergonomics / recent-change / partner-access / invitation / zentropy）| KEEP — feature-level 實作細節 |

---

## REFs

| REF | Action |
|-----|--------|
| REF-ontology-current-state | ✅ **REWRITTEN** v2.0（2026-04-23）— 完整重寫為 Grand Refactor 後的 ontology 快照；舊 v0.7「骨架/神經層」概念模型改為 L1-L3 subclass canonical 引用 |
| REF-ontology-methodology | ✅ **REVISED** — 加 Layering note 指向主 SPEC + 各 canonical SPEC；方法論思想部分保留 |
| REF-glossary | ✅ **REVISED** — 重寫對照表，新 canonical 結構（L1/L2/L3 + Axioms + MCP + error shapes）；加「歷史概念映射」章節 |
| REF-active-spec-surface | ✅ 已於 Wave 1 更新（Tier 1 加主 SPEC / governance-framework / IAM / zenos-core / mcp-tool-contract；l2-redefinition 移出）|
| REF-zenos-document-classification | KEEP |
| REF-governance-paths-overview | ✅ **REVISED** — frontmatter 對齊；line 214 SPEC-l2-entity-redefinition 改指主 SPEC v2 §7 |
| REF-open-decisions | KEEP |
| 其餘 REF（competitive / market / positioning / enterprise）| KEEP |

---

## PLANs

| PLAN | Action |
|------|--------|
| PLAN-l1-level-ssot-refactor | 已完成（ADR-047），保留歷史 |
| PLAN-data-model-consolidation | ✅ **ACTIVE — 與 Wave 9 PLAN 並行**（2026-04-23 修正，撤回先前 OBSOLETE 判斷）。原 OBSOLETE 是假設單一 master plan 吸收全部；實際 `PLAN-ontology-grand-refactor-wave9-migration §Scope` 明確把 Document / Protocol / Tags / dead-identity 切給本 PLAN。本 PLAN 的 S03（EntityStatus.archived + preflight）是 Wave 9 Plan Phase A 的上游依賴 |
| PLAN-ontology-grand-refactor-wave9-migration | ✅ **COMPLETED 2026-04-24** — L3-Action MTI + ownership tree + legacy task tables drop 已落地；與 PLAN-data-model-consolidation 平行 |
| PLAN-task-ownership-ssot | 已完成（ADR-044），保留歷史 |
| PLAN-governance-ssot-convergence | 保留 |
| PLAN-identity-access-consolidation | 保留 |
| 其餘 feature PLAN | KEEP |
| **NEW**：PLAN-ontology-grand-refactor（對應 Plan `a251aac4...`）| 主 plan，含所有 execution waves |

---

## 執行順序（按依賴）

1. **Wave 0 — 索引 + Master ADR**
   - 本檔（refactor-index.md）
   - ADR-048-grand-ontology-refactor（宣告 supersede 上表 + 引用本索引）

2. **Wave 1 — Core SPECs（定 canonical）**
   - SPEC-ontology-architecture REWRITE（#1）
   - SPEC-l2-entity-redefinition MERGE（#2）
   - SPEC-identity-and-access REVISE（#3）
   - SPEC-governance-framework REVISE（#4）
   - SPEC-zenos-core REVISE（#5）

3. **Wave 2 — L3 subclass SPECs**
   - SPEC-task-governance REWRITE（#6）
   - SPEC-doc-governance REWRITE（#7）
   - SPEC-doc-source-governance / SPEC-document-bundle MERGE（#8, #9）
   - SPEC-document-delivery-layer KEEP-verify（#10）
   - SPEC-batch-doc-governance REVISE（#11）

4. **Wave 3 — L2/Entry/Relationship 補強 SPECs**
   - #12–17

5. **Wave 4 — Governance + MCP + Agent SPECs**
   - #18–22 Governance 延伸
   - #23–26 MCP tool shape
   - #27–30 Agent contract

6. **Wave 5 — Task UI SPECs**
   - #31–34

7. **Wave 6 — Feature SPEC patch sweep**
   - #35–61 批次 grep/replace 舊術語

8. **Wave 7 — REF + TD 收尾**
   - REF rewrite
   - TD delete / revise

9. **Wave 8 — ADR supersede 標記**
   - 依本索引為每個被 superseded 的 ADR 加標記

10. **Wave 9 — code + migration**
    - 按 master ADR 執行 MTI + 併 Action Layer
    - 這是實作工作，獨立 PLAN 管理

---

## Index 狀態追蹤

每完成一個 SPEC 動作後，回頭在本檔的對應行標記 ✅。
