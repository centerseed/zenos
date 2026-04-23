---
type: REF
id: REF-ontology-current-state
status: Draft
ontology_entity: ontology-current-state
created: 2026-03-26
updated: 2026-04-23
version: v2.0 (Grand Ontology Refactor 2026-04-23)
---

# ZenOS Ontology — 當前狀態（2026-04-23）

> 本 REF 是「今日 ZenOS ontology 實際長什麼樣」的快照，不是 canonical SPEC。
> Canonical 定義見 `SPEC-ontology-architecture v2`；治理細則見 `SPEC-task-governance` / `SPEC-doc-governance` / `SPEC-identity-and-access` / `SPEC-governance-framework`。
> 本檔定期與 `git log` 對齊，落後於 SPEC / runtime 時以後者為準。

## 1. 六 Axioms（鎖定）

1. **Entity = graph node**：L1 / L2 / L3 一律是 `entities_base` row
2. **BaseEntity 強制繼承**：identity / permission / parent_id / owner / timestamps 共用
3. **無 ad-hoc unschemed JSON blob**：允許 typed JSON 欄位（有明確 domain type），禁 `details: dict` catch-all
4. **由內而外繼承擴充**：subclass 只能加欄位，不能改父層語意
5. **Schema 結構強制**：違反 DDL CHECK 或 enum → server reject
6. **MCP tool agent 語意最小化**：tool surface 穩定、參數收斂；caller 記憶負擔小

## 2. L1 / L2 / L3 分層現況

| 層 | 實體種類 | Runtime 存儲 | Canonical SPEC |
|----|---------|------------|-------------|
| **L1** | product / company / customer / account（任何 level=1、parent_id=null 的 collaboration root）| `entities_base`（level=1）| 主 SPEC v2 §6 |
| **L2** | 知識節點（三問 + impacts gate 通過的持久知識）| `entities_base`（level=2）+ `entity_l2`（SemanticMixin: summary / tags / confirmed_by_user）+ `entity_entries` sidecar | 主 SPEC v2 §7 |
| **L3-Semantic** | Document / Role / Project | `entity_l3_document` / `entity_l3_role` / `entity_l3_project` | 主 SPEC v2 §8 |
| **L3-Action** | Milestone / Plan / Task / Subtask | **（目標態）**`entity_l3_milestone / plan / task / subtask`；**（runtime 今日）**仍為 `zenos.tasks` + `zenos.plans` 獨立 table，ownership 由 `product_id` 表達 | 主 SPEC v2 §9（目標態）+ `SPEC-task-governance §1.1`（runtime）|

> **L1 判定**：由 `level=1 AND parent_id IS NULL` 決定，**不**由 `entity_type` 判定（ADR-047 D1-D2 canonical；runtime `src/zenos/infrastructure/level_based_l1.py`）。

## 3. Ownership SSOT 今日現況

| 對象 | 歸屬欄位 | Server gate |
|------|---------|-----------|
| L1 | `parent_id = null` | 非 null → 非 L1 |
| L2 | `parent_id` 指向 L1 或另一 L2 | `SPEC-l2-parent` 規則 |
| L3-Semantic | `parent_id` 指向 L1 / L2 | — |
| L3-Action (Task/Plan) | `product_id` 為**唯一 ownership SSOT**（ADR-047 D3；`governance_rules.py:938` `OWNERSHIP_SSOT_PRODUCT_ID`）| `MISSING_PRODUCT_ID` / `INVALID_PRODUCT_ID` |
| Subtask | `parent_task_id`（同表自指）+ 繼承 parent 的 `plan_id` / `product_id` | `CROSS_PLAN_SUBTASK` / `CROSS_PRODUCT_SUBTASK` |

Legacy `project` 字串僅為 partner-default fallback hint，不代表 ownership；`project_id` 參數 reject（`INVALID_INPUT`）。

## 4. Task Status State Machine（runtime canonical）

Canonical: `src/zenos/domain/task_rules.py:19-33 _VALID_TRANSITIONS`

```
todo ─► in_progress ─► review ─► done ─► todo (reopen)
  │         │          │        
  │         ▼          │         
  ├────── todo ◄───────┘
  │
  └────► cancelled（唯一 terminal）
```

- `cancelled` 是唯一真 terminal（無出站）
- `done → todo` reopen 合法
- `review → done` **必須**經 `confirm(accepted=True)`（`task_rules.py:36 _UPDATE_FORBIDDEN_TARGETS`）；`task.update(status="done")` 被擋
- Legacy aliases `backlog / blocked / archived` 由 server normalize（`SPEC-mcp-tool-contract §9.2`）

## 5. Document Status（L3-Document）

Canonical: `ontology_service._DOCUMENT_STATUSES`

- `draft / current / stale / archived / conflict`
- `conflict` 由 caller / agent 顯式寫入，server 不自動偵測雙 `current`（見 `SPEC-doc-governance §18` Gap note）
- Bundle-first：新建 doc entity 預設 `doc_role=index`；`doc_role=single` 需理由

## 6. Relationships（Core graph edge）

Canonical: 主 SPEC v2 §10 + `zenos.relationships` table

- 合法 type：`depends_on / serves / owned_by / part_of / blocks / related_to / impacts / enables`
- 舊 `task_entities` junction **已廢止**，一律走 `relationships` 表
- L2 `impacts gate`：至少 1 條具體 `impacts` relationship 才能升 `confirmed_by_user=true`
- `impact_chain` / `reverse_impact_chain` 雙向遍歷（5 跳上限，cycle 防呆），shipped `commit 0ede9cf`

## 7. Embedding（sidecar）

Canonical: 主 SPEC v2 §12 + `zenos.entity_embeddings` table

- `summary_embedding vector(768)`（pgvector + HNSW）
- L2 / L3-Semantic 可選擇性 embed；L1 / L3-Action 通常不 embed
- search hybrid mode 預設 `0.7 semantic + 0.3 keyword`（`SPEC-mcp-tool-contract §8.1`）

## 8. MCP Tool Surface（19 tools）

Canonical: `SPEC-mcp-tool-contract §4` + `src/zenos/interface/mcp/*.py`

`write / get / search / confirm / task / plan / analyze / governance_guide / find_gaps / common_neighbors / read_source / batch_update_sources / journal_read / journal_write / list_workspaces / upload_attachment / setup / suggest_policy / recent_updates`

## 9. 治理層

Canonical: `SPEC-governance-framework` 六維表 + `SPEC-governance-feedback-loop`

六維：Quality Gate / Lifecycle / Relation / Feedback / 衝突仲裁 / 治理路徑（`SPEC-governance-guide-contract`）。

## 10. 關鍵 ADR 狀態（2026-04-23）

| ADR | 主題 | 狀態 |
|-----|------|------|
| ADR-044 | Task ownership SSOT = `product_id` | **KEEP**（current canonical） |
| ADR-047 | L1 由 level 判定 | **Partial supersede**（axiom 保留，細節進主 SPEC） |
| ADR-006 / 007 / 010 / 022 / 025 / 027 / 032 / 041 / 046 | 已由主 SPEC 吸收 | **SUPERSEDED**（見 ADR-048 master）|
| ADR-028 | Plan primitive | **Partial**（目標態 SUPERSEDED，runtime 現行仍為獨立 table）|

## 11. 與歷史版本差異

本 REF 於 2026-04-23 從 v0.7（2026-03-21 描述的「骨架/神經/meta-ontology」概念模型）升級為 v2.0，對齊 Grand Ontology Refactor 後的 schema + runtime。舊版中的「骨架層 / 神經層 / Context Protocol」等概念改用以下新術語描述：

| v0.7 術語 | v2.0 術語 / canonical |
|----------|--------------------|
| 骨架層（Skeleton Layer） | L1 + L2 entity graph（主 SPEC v2 §6-§7）|
| 神經層（Neural Layer） | L3-Document（主 SPEC v2 §8.1）+ 舊 `documents` collection 已合併進 entity |
| Context Protocol | 不再是獨立產出；`impact_chain` + `bundle_highlights` + `summary` 組合提供 agent context |
| 雙層互動 | `impacts gate` + L2 lifecycle（主 SPEC v2 §7.2）|
| 過時推斷 | `analyze(check_type="staleness" / "document_consistency")`（`mcp/analyze.py:606-620`）|
| 漸進式信任 | `SPEC-progressive-trust`（仍 canonical）|
| confirmedByUser | `BaseEntity.confirmed_by_user`（主 SPEC v2 §4）|
| 三層治理系統 | server-side governance + MCP + client skills；見 `SPEC-governance-framework` |

## 12. 下一次更新

本 REF 應在下列事件後更新：
- Wave 9 MTI migration 完成（§2 L3-Action 的 runtime 欄改為 subclass table）
- 新 L3 subclass 落地（例如 L3-Campaign）
- 重要 ADR 取代關係變更
