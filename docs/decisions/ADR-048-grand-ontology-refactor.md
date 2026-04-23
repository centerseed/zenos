---
type: ADR
id: ADR-048-grand-ontology-refactor
status: Approved
ontology_entity: ontology-architecture
created: 2026-04-23
updated: 2026-04-23
accepted_at: 2026-04-23
supersedes:
  - ADR-006-entity-project-separation
  - ADR-007-entity-architecture
  - ADR-010-entity-entries
  - ADR-022-document-bundle-architecture
  - ADR-025-zenos-core-layering
  - ADR-027-layer-contract
related:
  - ADR-028-plan-primitive (runtime plans table 仍活)
  - ADR-032-document-delivery-layer-architecture (sidecar tables 仍 canonical)
  - ADR-041-pillar-a-semantic-retrieval (retrieval 行為仍 canonical)
  - ADR-044-task-ownership-ssot-convergence (runtime ownership canonical)
  - ADR-046-document-entity-boundary (runtime Document dataclass 仍活；spec 目標態已在 canonical SPEC 落地)
  - ADR-047-l1-level-ssot (runtime L1 enforcement 仍 canonical)
related_index: docs/refactor-index.md
---

# ADR-048: Grand Ontology Refactor（Master）

## 狀態

Approved，2026-04-23。統合本次 Grand Ontology Refactor 的 9 個 Wave，取代（或部分取代）上述 9+ 份 ADR。

## Context

2026-03-19 以來 ZenOS ontology 經歷多次迭代：entity 分層（ADR-007）、project 分離（ADR-006）、L2 entries（ADR-010）、document bundle（ADR-022）、Core layering（ADR-025）、Layer contract（ADR-027）、plan primitive（ADR-028）、document delivery（ADR-032）、semantic retrieval embedding（ADR-041）、task ownership（ADR-044）、document/entity 邊界（ADR-046）、L1 level SSOT（ADR-047）。

結果是多個 ADR 的決策**彼此部分重疊、部分互相 supersede**，且與 runtime 的實際 schema（`zenos.tasks` / `zenos.plans` / `zenos.relationships` / `zenos.entity_embeddings`）出現漸進 drift：

- SPEC 與 runtime 對「Task 是不是 entity」描述不一致
- 多份 SPEC 各自定義 bundle / source / highlights，sibling 文件重複
- L2 lifecycle 在三份文件用三種不同語言描述
- MCP tool contract 散在 fixes + 各 SPEC 示意片段

本 ADR **不是新的架構決策**，是對現存分散決策的**最終收斂聲明**，配合 `refactor-index.md`（Wave 0-9 master index）+ 六份 canonical SPEC 落地。

## Decision

### 1. 鎖定 6 個 Axioms（主 SPEC v2 §1）

1. Entity = graph node（L1/L2/L3 皆為 `entities_base` row）
2. BaseEntity 強制繼承（identity / permission / parent_id / owner / timestamps）
3. 無 ad-hoc unschemed JSON blob（允許 typed JSON；禁 `details: dict` catch-all）
4. 由內而外繼承擴充（subclass 只加欄位，不改父層語意）
5. Schema 結構強制（DDL CHECK + enum server reject）
6. MCP tool agent 語意最小化

### 2. 鎖定六份 canonical SPEC

| 主題 | Canonical |
|------|-----------|
| Schema / 分層 / status enum / state machine | `SPEC-ontology-architecture v2` |
| ZenOS Core 邊界與應用層界線 | `SPEC-zenos-core` |
| Identity / workspace / visibility | `SPEC-identity-and-access` |
| 治理框架六維表 | `SPEC-governance-framework` |
| MCP tool 統一 SSOT | `SPEC-mcp-tool-contract` |
| L3-Action 治理細則 | `SPEC-task-governance` |
| L3-Document 治理細則（含 bundle / source） | `SPEC-doc-governance` |
| 治理規則分發契約 | `SPEC-governance-guide-contract` |

### 3. 目標態 vs Runtime 現況

主 SPEC v2 §9 的 **L3-Action subclass table**（`entity_l3_milestone / plan / task / subtask`）為 **Post-MTI migration 目標**（refactor-index Wave 9）；**runtime 今日仍為 `zenos.tasks` + `zenos.plans` 獨立 table**，caller 以 `SPEC-task-governance §1` 為 runtime contract。

ADR-028（plan-primitive）與 ADR-044（task-ownership）因此**保留為 current runtime canonical**——直到 Wave 9 migration 完成前，它們仍是活的決策，不是 superseded。

### 4. 取代清單

**完全 supersede**（決策已完整由新 SPEC 取代，spec-level 無殘留）：

- ADR-006 entity-project-separation → 主 SPEC v2 §8.3 L3ProjectEntity
- ADR-007 entity-architecture → 主 SPEC v2 §3-§9
- ADR-010 entity-entries → 主 SPEC v2 §7.3 + `SPEC-entry-distillation-quality` + `SPEC-entry-consolidation-skill`
- ADR-022 document-bundle-architecture → 主 SPEC v2 §8.1 + `SPEC-doc-governance §3`
- ADR-025 zenos-core-layering → `SPEC-zenos-core` + 主 SPEC v2 §3
- ADR-027 layer-contract → `SPEC-zenos-core` + `SPEC-mcp-tool-contract`

**保留 Approved（非 Superseded），等待 Wave 9 migration 實際落地**：

- **ADR-046 document-entity-boundary**：spec 目標態已寫在主 SPEC v2 §8.1 + `SPEC-doc-governance`，但 runtime 尚未完成——`src/zenos/domain/knowledge/models.py:88` 仍有獨立 `Document` dataclass；`src/zenos/domain/governance.py:223-230` 治理邏輯明確雙路徑（Document 與 Entity 並行）；`zenos.documents` / `task_entities` 舊 table 仍活著。Wave 9 migration 完成前**本 ADR 是活的決策**，不標 Superseded

**部分 supersede**（核心決策收斂，但保留部分為 canonical）：

- ADR-032 document-delivery-layer-architecture：doc bundle 部分 → `SPEC-doc-governance §3`；revision / share_token sidecar 仍在 `SPEC-document-delivery-layer`
- ADR-041 pillar-a-semantic-retrieval：embedding 改為 sidecar table（主 SPEC v2 §12）；retrieval 行為仍以 `SPEC-semantic-retrieval` 為 canonical
- ADR-047 l1-level-ssot：level-based L1 判定 axiom 進主 SPEC v2 §6；runtime enforcement 仍在 ADR-047 canonical，product_id 為 ownership SSOT

**保留為 current runtime canonical**（Wave 9 migration 後才會被取代）：

- ADR-028 plan-primitive（runtime 仍為獨立 `zenos.plans` table）
- ADR-044 task-ownership-ssot-convergence（`product_id` 為唯一 ownership 欄位）
- ADR-045 protocol-collection-vs-view（Protocol collection 判定仍有效）

## Consequences

### 正面

- **單一 canonical 入口**：caller / developer 只需查 6 份 SPEC + 1 份 ADR-048 master，不需在 20+ 份 ADR 間猜優先級
- **runtime 對齊**：SPEC 明文區分「目標態」vs「當前 runtime」，避免以為 schema 已改卻沒改
- **Wave 9 migration 路徑清晰**：主 SPEC §9 subclass DDL + governance canonical 在 `SPEC-task-governance`；migration 時只需把 runtime 的 `zenos.tasks` / `zenos.plans` 欄位對應搬進 subclass table

### 負面

- 歷史 ADR 的設計脈絡分散在各 supersede note；要完整理解某個決策演進仍需順著 supersede chain 走
- Post-MTI 目標態 vs 當前 runtime 的**雙 canonical 視角**在 Wave 9 前持續存在；caller 需要意識到這個分裂

### 後續處理

- Wave 9（code + migration）：按本 ADR + `refactor-index.md` 的 migration 計畫執行 MTI + Action Layer 併入，讓 runtime 真正對齊主 SPEC v2 §9
- 本 ADR 的 supersede 清單是**終態清單**，未來新 ADR 若要推翻本次決策應明確 supersede ADR-048 而非個別舊 ADR

## Implementation

本 ADR 不帶新的實作步驟——它是**已完成的 Wave 0-8 spec refactor 的終態聲明**：

1. Wave 0：refactor-index + 本 ADR（本檔）
2. Wave 1：Core SPECs 定 canonical（主 SPEC v2 / IAM / governance-framework / zenos-core）
3. Wave 2：L3 subclass SPECs（task-governance / doc-governance 合併 bundle/source）
4. Wave 3：L2/Entry/Relationship 補強（impact-chain / knowledge-graph-semantic 收斂）
5. Wave 4：Governance / MCP / Agent（mcp-tool-contract + governance-guide-contract）
6. Wave 5：Task UI SPECs（state machine 對齊 runtime）
7. Wave 6：Feature SPEC patch sweep（27 份 frontmatter + 引用修正）
8. Wave 7：REF + TD 收尾
9. Wave 8：ADR supersede 標記 + 本 master ADR

完整執行軌跡見 `docs/refactor-index.md` 的 ✅ 標記。

## 相關文件

- `docs/refactor-index.md`（Wave 0-9 master index）
- 主 canonical SPEC：`SPEC-ontology-architecture v2`、`SPEC-zenos-core`、`SPEC-identity-and-access`、`SPEC-governance-framework`、`SPEC-mcp-tool-contract`、`SPEC-task-governance`、`SPEC-doc-governance`、`SPEC-governance-guide-contract`
- 完全 superseded ADR（status=Superseded）：`ADR-006` / `ADR-007` / `ADR-010` / `ADR-022` / `ADR-025` / `ADR-027`
- 保留 Approved，等 Wave 9 runtime migration 落地後再收口：`ADR-028-plan-primitive`（runtime plans table 仍活）/ `ADR-032-document-delivery-layer-architecture`（bundle 部分併入 SPEC，sidecar 仍 canonical）/ `ADR-041-pillar-a-semantic-retrieval`（embedding 改 sidecar，retrieval 行為仍 canonical）/ `ADR-044-task-ownership-ssot-convergence`（`product_id` runtime 仍唯一 SSOT）/ `ADR-045-protocol-collection-vs-view` / `ADR-046-document-entity-boundary`（runtime `Document` dataclass 仍活）/ `ADR-047-l1-level-ssot`
