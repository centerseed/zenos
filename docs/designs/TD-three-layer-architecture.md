---
type: TD
id: TD-three-layer-architecture
status: Superseded
ontology_entity: ontology-architecture
created: 2026-03-26
updated: 2026-04-23
superseded_by: SPEC-ontology-architecture v2, SPEC-zenos-core
---

# Transition Note: Three Layer Architecture（併入主 SPEC v2 + SPEC-zenos-core）

本 TD 為 2026 年初的「Knowledge Layer / Action Layer / Document Layer」三層架構設計紀錄。2026-04-23 Grand Ontology Refactor 後，Action Layer 已併入 Knowledge Layer（L3-Action subclass），Document Layer 亦併入 Knowledge Layer（L3-Document subclass）：

- 原三層改為 **BaseEntity + subclass** 單一 MTI 體系 → 主 SPEC v2 §3-§9
- Knowledge / Action / Document 的 canonical 邊界 → 主 SPEC v2 §3 + `SPEC-zenos-core §3.1`
- 舊 ADR-025 / ADR-027（Core layering / Layer contract）部分 supersede → ADR-048 master

## Migration Rule

不得在此新增內容。新的分層議題 → 改 `SPEC-zenos-core` 或主 SPEC v2，並在 refactor-index 登記。
