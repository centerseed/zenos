---
type: REF
id: REF-active-spec-surface
status: Draft
ontology_entity: documentation-governance
created: 2026-03-26
updated: 2026-03-26
---

# Reference: ZenOS Active Spec Surface

## 目的

ZenOS 現階段不應讓 `docs/specs/` 同時承載：

- 現行產品規格
- 已交付的歷史 feature spec
- 尚未採納的 proposal
- 階段性 foundation spec

這份文件用來收斂「現在真正應該看的規格面」。

---

## Tier 0 — Canonical

- `docs/spec.md`

這是 ZenOS 現行有效的 canonical SSOT。若其他文件與它衝突，以這份為準。

---

## Tier 1 — Current Core Specs (2026-03-26 收斂版)

以下是目前仍屬 active decision surface 的核心規格：

- `docs/specs/SPEC-doc-governance.md`
- `docs/specs/SPEC-l2-entity-redefinition.md`
- `docs/specs/SPEC-partner-context-fix.md`
- `docs/specs/SPEC-agent-integration-contract.md`
- `docs/specs/SPEC-governance-observability.md`

判斷標準：

- 直接影響 ontology/document 治理安全性
- 仍在近期開發決策路徑上
- 若本週不看會造成行為偏差或回歸風險

---

## Archived Historical / Proposal

以下文件已移出 active spec surface：

- `docs/archive/specs/SPEC-enriched-task-dispatch.md`
- `docs/archive/specs/SPEC-governance-quality.md`
- `docs/archive/specs/SPEC-intra-company-permission.md`
- `docs/archive/specs/SPEC-ontology-layering-v2.md`
- `docs/archive/specs/SPEC-phase1-ontology-mvp.md`
- `docs/archive/specs/SPEC-zenos-eval.md`
- `docs/archive/specs/phase1-tasks.md`
- `docs/archive/specs/deferred-2026-03/SPEC-action-layer.md`
- `docs/archive/specs/deferred-2026-03/SPEC-agent-aware-permission-governance.md`
- `docs/archive/specs/deferred-2026-03/SPEC-audit-log.md`
- `docs/archive/specs/deferred-2026-03/SPEC-billing.md`
- `docs/archive/specs/deferred-2026-03/SPEC-company-onboarding-first-admin.md`
- `docs/archive/specs/deferred-2026-03/SPEC-dashboard-v1.md`
- `docs/archive/specs/deferred-2026-03/SPEC-knowledge-map-l2-expand.md`
- `docs/archive/specs/deferred-2026-03/SPEC-multi-tenant.md`
- `docs/archive/specs/deferred-2026-03/SPEC-task-dispatch-ui-redesign.md`
- `docs/archive/specs/deferred-2026-03/SPEC-user-invitation-mvp.md`
- `docs/archive/specs/deferred-2026-03/SPEC-zenos-sql-cutover.md`
- `docs/archive/specs/tasks-2026-03/`

分類原則：

- 已被新文件 supersede
- 已是完成階段的歷史規格
- 仍屬 proposal / candidate，尚未進入現行規格面

---

## 收斂原則

1. `docs/specs/` 應優先保留「現在會影響產品與實作決策」的規格。
2. 子功能 spec 若已被主規格吸收，應移出 active surface。
3. proposal candidate 不應和 current core specs 混放在同一層語意上。
4. delivered feature spec 若只剩追溯價值，應 archive。
