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
| 18 | `SPEC-governance-feedback-loop` | **REVISE** 跨新 subclass 的 feedback 路徑 |
| 19 | `SPEC-governance-guide-contract` | **REVISE** governance_guide topic 對齊新 subclass 集合 |
| 20 | `SPEC-governance-observability` | **REVISE** |
| 21 | `SPEC-governance-audit-log` | **KEEP** |
| 22 | `SPEC-progressive-trust` | **KEEP** |

---

## MCP tool SPECs（Axiom 6 主戰場）

| # | Spec | Action | 核心動作 |
|---|------|--------|---------|
| 23 | `SPEC-mcp-tool-contract` | **REWRITE** | 新 tool shape：`write(entity)` / `get(id)` / `search(...)` polymorphic；task / plan MCP tool 合併為 `write(entity, type=task)`；參數從 36+23 減到個位數 |
| 24 | `SPEC-mcp-tool-contract-fixes` | **MERGE** → SPEC-mcp-tool-contract |
| 25 | `SPEC-mcp-opt-in-include` | **KEEP** include 參數設計保留 |
| 26 | `SPEC-mcp-id-ergonomics` | **KEEP** id_prefix 設計保留 |

---

## Agent contract SPECs

| # | Spec | Action |
|---|------|--------|
| 27 | `SPEC-agent-integration-contract` | **REVISE** 新 MCP tool shape |
| 28 | `SPEC-agent-context-summary` | **KEEP** |
| 29 | `SPEC-agent-setup` | **KEEP** |
| 30 | `SPEC-agent-skill-addon` | **KEEP** |

---

## Task UI SPECs（subclass 後 UI 分工可能變）

| # | Spec | Action |
|---|------|--------|
| 31 | `SPEC-task-view-clarity` | **REVISE** per-subclass 顯示規則 |
| 32 | `SPEC-task-kanban-operations` | **REVISE** |
| 33 | `SPEC-task-surface-reset` | **DELETE** 已完成 + 內容被新 SPEC-task-governance 取代 |
| 34 | `SPEC-task-communication-sync` | **REVISE** |

---

## Feature SPECs（不主動改，只掃 grep 舊術語替換）

| # | Spec | Action |
|---|------|--------|
| 35 | `SPEC-crm-core` | **PATCH** 術語：type=company → L1 entity（label=company） |
| 36 | `SPEC-crm-intelligence` | **PATCH** |
| 37 | `SPEC-marketing-automation` | **PATCH** |
| 38 | `SPEC-dashboard-ai-rail` | **PATCH** |
| 39 | `SPEC-dashboard-onboarding` | **PATCH** |
| 40 | `SPEC-dashboard-v2-ui-refactor` | **PATCH** |
| 41 | `SPEC-client-portal` | **PATCH** |
| 42 | `SPEC-zen-ink-real-data` | **PATCH** |
| 43 | `SPEC-zen-ink-redesign` | **PATCH** |
| 44 | `SPEC-federation-auto-provisioning` | **PATCH** |
| 45 | `SPEC-home-workspace-bootstrap` | **PATCH** |
| 46 | `SPEC-cowork-knowledge-context` | **PATCH** |
| 47 | `SPEC-partner-context-fix` | **PATCH** |
| 48 | `SPEC-user-department` | **PATCH** |
| 49 | `SPEC-recent-change-surfacing` | **PATCH** |
| 50 | `SPEC-project-progress-console` | **PATCH** |
| 51 | `SPEC-docs-native-edit-and-helper-ingest` | **PATCH** |
| 52 | `SPEC-ingestion-governance-v2` | **PATCH** |
| 53 | `SPEC-zentropy-ingestion-contract` | **PATCH** |
| 54 | `SPEC-google-workspace-per-user-retrieval` | **PATCH** |
| 55 | `SPEC-skill-packages` | **PATCH** |
| 56 | `SPEC-skill-release-management` | **PATCH** |
| 57 | `SPEC-zenos-external-integration` | **PATCH** |
| 58 | `SPEC-zenos-auth-federation` | **PATCH** |
| 59 | `SPEC-zenos-setup-redesign` | **PATCH** |
| 60 | `SPEC-product-vision` | **KEEP** 願景層，不動 |
| 61 | `SPEC-aha-moment` | **KEEP** |

---

## ADRs（supersede / keep / delete）

### 被新 master ADR-048 supersede（舊決策失效）
| ADR | 原議題 | 如何處理 |
|-----|--------|---------|
| ADR-006 entity-project-separation | project vs entity 分離 | SUPERSEDE — Action 併入 Knowledge，不再分家 |
| ADR-007 entity-architecture | Entity 分層模型 | SUPERSEDE — 新主 SPEC 重寫 |
| ADR-010 entity-entries | L2 entries 結構 | SUPERSEDE — entries 成 L2 subclass own 的 sidecar table |
| ADR-022 document-bundle-architecture | doc_role / bundle | SUPERSEDE — bundle 欄位進 L3-document subclass |
| ADR-025 zenos-core-layering | Knowledge / Action Layer 分離 | SUPERSEDE — Layer 合併 |
| ADR-027 layer-contract | Layer 契約 | SUPERSEDE |
| ADR-028 plan-primitive | Plan 獨立 collection | SUPERSEDE — Plan 成 L3-action subclass |
| ADR-032 document-delivery-layer-architecture | delivery 方案 | SUPERSEDE 部分（doc 部分）|
| ADR-041 pillar-a-semantic-retrieval | embedding 放 entities 表 | SUPERSEDE — embedding 獨立 sidecar table |
| ADR-044 task-ownership-ssot | task.project_id → product_id | SUPERSEDE（Task 成 entity 後，parent_id 取代 product_id） |
| ADR-045 protocol-collection-vs-view | Protocol 是 collection 非 view | KEEP — Protocol 判定仍有效，但其 schema 納入新 Base |
| ADR-046 document-entity-boundary | Document 合併 Entity | SUPERSEDE — 新 SPEC 完整實作 |
| ADR-047 l1-level-ssot | L1 由 level 判定 | SUPERSEDE 部分 — axiom 保留，細節被新主 SPEC 覆蓋 |

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

### 待建立
| ADR | 議題 |
|-----|------|
| **ADR-048 Grand Ontology Refactor（master）** | 整體 refactor 總宣告 + supersede 上表清單 |

---

## TDs（technical design）

**Action**：TD 屬實作歷史紀錄，新 master ADR 落地後可選擇刪除或改「superseded by PLAN-a251aac4」。

| TD | Action |
|----|--------|
| TD-foundation-p0-entity-schema | DELETE — 由新 master SPEC 取代 |
| TD-l2-entity-redesign | DELETE |
| TD-three-layer-architecture | DELETE — Action Layer 併入後整體重寫 |
| TD-action-layer | DELETE |
| TD-action-layer-mcp-interface | DELETE |
| TD-service-architecture | REVISE 新 polymorphic service split |
| TD-doc-primary-parent-remediation | KEEP — 歷史 remediation |
| TD-distributed-governance | KEEP |
| 其餘 TD（CRM / marketing / dashboard / federation / ingestion / semantic-retrieval / opt-in / id-ergonomics / recent-change / partner-access / invitation / zentropy）| KEEP — feature-level 實作細節 |

---

## REFs

| REF | Action |
|-----|--------|
| REF-ontology-current-state | **REWRITE** 依新主 SPEC 實況更新 |
| REF-ontology-methodology | **REVISE** |
| REF-glossary | **REVISE** 新術語（L3-action / subclass 等）|
| REF-active-spec-surface | **REVISE** 納入 master SPEC |
| REF-zenos-document-classification | KEEP |
| REF-governance-paths-overview | **REVISE** |
| REF-open-decisions | KEEP |
| 其餘 REF（competitive / market / positioning / enterprise）| KEEP |

---

## PLANs

| PLAN | Action |
|------|--------|
| PLAN-l1-level-ssot-refactor | 已完成（ADR-047），保留歷史 |
| PLAN-data-model-consolidation | **OBSOLETE** — 由 new master plan 取代；task 歸檔 |
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
