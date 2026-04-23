---
type: TD
id: TD-action-layer
status: Superseded
ontology_entity: l3-action
created: 2026-03-26
updated: 2026-04-23
superseded_by: SPEC-task-governance, SPEC-ontology-architecture v2 §9
---

# Transition Note: Action Layer TD（併入主 SPEC v2 §9 + SPEC-task-governance）

本 TD 為 Action Layer（task / plan / subtask / milestone）的早期技術設計。2026-04-23 Grand Refactor 後 Action Layer 併入 Knowledge Layer 成 L3-Action subclass：

- L3-Action schema / DDL / CHECK constraint → 主 SPEC v2 §9（目標態）
- Runtime task state machine / dispatcher / handoff / ownership（`product_id`）→ `SPEC-task-governance`
- ADR-028 (plan-primitive) / ADR-006 (entity-project-separation) 相應 supersede → ADR-048 master

## Migration Rule

不得在此新增內容。Task / Plan / Milestone / Subtask 新議題 → `SPEC-task-governance` + 對應 runtime 檔（`task_rules.py` / `plan_service.py`）。
