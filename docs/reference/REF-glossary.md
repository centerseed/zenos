---
type: REF
id: REF-glossary
status: Draft
ontology_entity: glossary
created: 2026-03-26
updated: 2026-04-23
---

# ZenOS 核心概念速查（2026-04-23 Grand Refactor 後）

> 本 REF 只提供快速對照；每個 term 的 canonical 定義以右欄 SPEC 為準。
> 舊 spec.md Part X 引用已於 2026-04-23 改為新 SPEC 對照。

## L1-L3 實體模型

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **L1 entity（root）** | workspace 內可獨立授權與分享的主軸 root（`product / company / customer / account` 等）；判定 = `level=1 AND parent_id IS NULL` | 主 SPEC v2 §6 + ADR-047 D1-D2 |
| **L2 entity（知識節點）** | 通過三問 + impacts gate 的持久知識概念 | 主 SPEC v2 §7 |
| **L3-Semantic** | `L3DocumentEntity / L3RoleEntity / L3ProjectEntity` — 文件語意代理 / 角色 / 工作容器 | 主 SPEC v2 §8 |
| **L3-Action** | `Milestone / Plan / Task / Subtask`，原 Action Layer 併入 Knowledge Layer | 主 SPEC v2 §9 + `SPEC-task-governance` |
| **L1 判定** | 由 `level` 欄位判定，不由 `entity_type`（舊 ADR-007 已 supersede） | ADR-047 |

## 基礎屬性

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **BaseEntity** | 所有 entity 共用：identity / permission / parent_id / owner / timestamps | 主 SPEC v2 §4 |
| **SemanticMixin** | L2 / L3-Semantic 共用：summary / tags / confirmed_by_user / last_reviewed_at | 主 SPEC v2 §5 |
| **四維標籤** | What / Why / How / Who，源自 Ranganathan PMEST | 主 SPEC v2 §5 tags spec |
| **`confirmed_by_user`** | AI 產出 = draft，人確認 = 生效；L2 升 confirmed 的 gate | 主 SPEC v2 §7.1 |
| **L2 lifecycle**（二維）| `confirmed_by_user × status`：Draft `(false, active)` → Confirmed `(true, active)` ↔ Stale `(true, stale)` | 主 SPEC v2 §7.2 |
| **三問** | q1_persistent / q2_cross_role / q3_company_consensus；三問全 true 才能升 L2 | 主 SPEC v2 §7.1 + `governance_rules` |
| **impacts gate** | L2 升 confirmed 必須 ≥1 條具體 `impacts` relationship | 主 SPEC v2 §7.1 + §10.2 |
| **EntityEntry** | L2 的結構化記憶條目（decision / insight / limitation / change / context）；1-200 字 | 主 SPEC v2 §7.3 |

## Ownership & 分層路由

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **Task ownership SSOT** | `product_id`（唯一，ADR-047 D3）；legacy `project` 字串只是 fallback hint；`project_id` 參數 reject | `governance_rules.py:938` `OWNERSHIP_SSOT_PRODUCT_ID` |
| **Subtask** | `tasks` row with `parent_task_id != null`（同表自指，不是獨立 subclass）；runtime target post-MTI 為 `entity_l3_subtask` | `SPEC-task-governance §1.1` |
| **分層路由** | 新輸入先判：governance 原則 → L2；正式文件 → L3-Document；可驗收工作 → L3-Task；低價值材料 → L2.sources | 主 SPEC v2 §7 + `SPEC-doc-governance §10` |
| **L2.sources 輕量參考**| 移除不影響 L2 語意的 uri；不升 L3 | `SPEC-doc-governance §10.1` |

## Task / Plan 治理

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **TaskStatus canonical** | `todo / in_progress / review / done / cancelled`；legacy `backlog / blocked / archived` server normalize | `task_rules.py:19-33` + `SPEC-mcp-tool-contract §9.2` |
| **Task terminal** | `cancelled` 是唯一真 terminal（無出站）；`done → todo` reopen 合法 | `task_rules.py:19-33` |
| **`review → done`** | 必須經 `confirm(collection="tasks", accepted=True)`；`task.update(status="done")` 會被擋 | `task_rules.py:36` `_UPDATE_FORBIDDEN_TARGETS` |
| **Dispatcher** | regex `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`；違反 `INVALID_DISPATCHER` | `governance_rules` |
| **HandoffEvent** | append-only log；caller 傳 → strip + warning `HANDOFF_EVENTS_READONLY`（不 reject） | `SPEC-task-governance §4.2` |
| **`entity_entries` 回饋** | `{entity_id, type, content}`；僅 `confirm(accepted=True)` 時寫入；target L2 必須在 task.linked_entities | `SPEC-task-governance §11` |
| **Plan lifecycle** | `draft → active → completed | cancelled`；completed 時下轄 task 須 snapshot-terminal | `SPEC-task-governance §3.2` |

## Document 治理

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **Document status** | `draft / current / stale / archived / conflict` | 主 SPEC v2 §8.1 + `ontology_service._DOCUMENT_STATUSES` |
| **`doc_role`** | `single`（單檔例外）/ `index`（**預設**，聚合多 source） | `SPEC-doc-governance §3.1` |
| **`bundle_highlights`** | index entity 必填 1-5 筆，至少 1 筆 `priority=primary` | `SPEC-doc-governance §3.4` |
| **Source** | `{source_id, uri, type, label, doc_type, source_status, is_primary, ...}`；per-source CRUD | `SPEC-doc-governance §3.2` |
| **`read_source` error** | helper types 走 `SNAPSHOT_UNAVAILABLE / LIVE_RETRIEVAL_REQUIRED`；adapter 走 `SOURCE_UNAVAILABLE / ADAPTER_ERROR` | `SPEC-mcp-tool-contract §8.3` |
| **`doc_type` 泛用類別** | `SPEC / DECISION / DESIGN / PLAN / REPORT / CONTRACT / GUIDE / MEETING / REFERENCE / TEST / OTHER` | `SPEC-doc-governance §5` |

## Relationship & Graph Traversal

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **Relationship type** | `depends_on / serves / owned_by / part_of / blocks / related_to / impacts / enables` | 主 SPEC v2 §10.1 |
| **`impact_chain`（forward）** | 從此節點出發，沿 outgoing edges 的 5 跳影響鏈 | 主 SPEC v2 §10.4 |
| **`reverse_impact_chain`（backward）** | 誰改了會影響我；同 5 跳上限 + cycle 防呆 | 主 SPEC v2 §10.4（shipped `commit 0ede9cf`）|
| **`verb` on relationship** | 2026-04-18 REJECTED（填寫率 8.8%），DDL 欄位保留避免 migration risk，不作治理評分依據 | 主 SPEC v2 §10.5 |

## Identity & Access

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **`visibility`** | `public / restricted / confidential`；`confidential` = owner + 明確授權（不是 owner-only） | 主 SPEC v2 §13 + `SPEC-identity-and-access §4.1` |
| **白名單提權** | `visible_to_members / visible_to_roles / visible_to_departments`；member 可被提權讀 `confidential`；guest 不被提權 | `SPEC-identity-and-access §4.1` |
| **Workspace** | partner 的獨立 tenant scope；subtree authorization 可跨 workspace 共享 | `SPEC-identity-and-access` |
| **Federation** | 外部 app end-user 映射到 ZenOS principal；`identity_link` + delegated credential | `SPEC-zenos-auth-federation` |

## MCP Tool Surface

| 概念 | 一句話 | Canonical |
|------|--------|-----------|
| **Unified envelope** | `{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints, workspace_context}` | `SPEC-mcp-tool-contract §6.1` |
| **Status**（rejected 三 shape）| A 結構化 `data.error:str + data.message`；B 只 `rejection_reason`；C 巢狀 `data.error:{code,...}`（僅 doc linkage） | `SPEC-mcp-tool-contract §6.2` |
| **`governance_guide`** | 7 topics：`entity / document / bundle / task / capture / sync / remediation`；3 levels | `SPEC-governance-guide-contract` + `mcp/governance.py:15 _VALID_TOPICS` |
| **`id_prefix`** | 僅 lookup 支援（≥4 字元 hex）；write / confirm / handoff **不接受**（`id_prefix_not_allowed_for_write_ops`） | `SPEC-mcp-id-ergonomics` + `SPEC-mcp-tool-contract §8.12` |
| **`include` (opt-in)** | `get` / `search` 的 response 欄位控制；未傳 → eager full + deprecation warning | `SPEC-mcp-opt-in-include` |

## 歷史概念映射（v0.7 → v2.0）

| 舊術語（v0.7 及更早）| 新 canonical |
|----------------------|-------------|
| 骨架層 / Skeleton Layer | L1 + L2 entity graph |
| 神經層 / Neural Layer | L3-Document subclass（舊 `documents` collection 已合併進 entity）|
| Meta-Ontology | 主 SPEC v2（axioms + DDL canonical）|
| Context Protocol（獨立產出）| 不再獨立；`impact_chain` + `bundle_highlights` + `summary` 組合提供 agent context |
| 雙層互動 | `impacts gate` + L2 lifecycle + `analyze(check_type="impacts")` |
| 過時推斷 | `analyze(check_type="staleness"|"document_consistency")` |
| 三層治理系統（事件源 / 引擎 / 確認同步）| server-side governance + MCP + client skills；見 `SPEC-governance-framework` |
| Task ≠ Entity | 過時；Task 在主 SPEC v2 §9 已為 L3-Action subclass（runtime 今日仍獨立 `zenos.tasks` table，post-MTI 會統一）|
| Entity ≠ Project | 過時；project 已為 `L3ProjectEntity`（主 SPEC v2 §8.3）|
| Entity.sources | 改名 `sources_json`（typed JSON，主 SPEC v2 §8.1）|

## Dashboard 用語（UI layer）

| UI 名稱 | 內部 entity |
|--------|------------|
| 專案 | L1 Product（或 Company / Customer / Account）|
| 模組 | L2 module / governance concept |
| 知識地圖 | L1 + L2 + relationships graph |
| 節點 | Entity（UI 永不直接稱 entity / ontology）|
| 文件 | L3-Document bundle |
| 任務 | L3-Task |

## 產品哲學（仍 canonical）

| 概念 | 一句話 |
|------|--------|
| 漸進式信任 | 不要求資料，先用對話展示價值，信任是賺來的（`SPEC-progressive-trust`）|
| BYOS | 每客戶一個 VM + 一個 Claude 訂閱，資料不過 ZenOS |
| Who + Owner 分離 | Who = 多值（context 分發）；Owner = 單值（治理問責）|
| Pull Model | Agent 自宣告身份，透過 MCP query 帶 role filter 拉 context；ZenOS 不維護 agent registry |
