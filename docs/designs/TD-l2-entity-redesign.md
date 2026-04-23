---
type: TD
id: TD-l2-entity-redesign
status: Superseded
ontology_entity: l2
created: 2026-03-26
updated: 2026-04-23
superseded_by: SPEC-ontology-architecture v2 §7
---

# Transition Note: L2 Entity Redesign（已由主 SPEC v2 §7 取代）

本 TD 為 L2 entity 重新設計的早期實作紀錄，2026-04-23 Grand Refactor 後：

- L2 schema / SemanticMixin / `confirmed_by_user × status` 二維 lifecycle → 主 SPEC v2 §5 + §7
- 三問 + impacts gate 規則 → 主 SPEC v2 §7.1
- Entry sidecar 結構 → 主 SPEC v2 §7.3
- 舊 `SPEC-l2-entity-redefinition` 已併入主 SPEC

## Migration Rule

不得在此新增內容。L2 相關治理新議題 → 走 ADR + 修改 `SPEC-ontology-architecture v2 §7`。
