---
type: SPEC
id: SPEC-l2-entity-redefinition
status: Superseded
superseded_by: SPEC-ontology-architecture v2 §5, §7, §11
superseded_at: 2026-04-23
ontology_entity: l2-governance
created: 2026-03-25
updated: 2026-04-23
---

# SPEC: L2 Entity Redefinition（已合併）

> **本 SPEC 於 2026-04-23 合併進 [`SPEC-ontology-architecture v2`](./SPEC-ontology-architecture.md)。**
>
> - L2 的 schema 與 SemanticMixin → 主 SPEC §5 + §7
> - 三問 + impacts gate → 主 SPEC §7.1
> - L2 lifecycle state machine → 主 SPEC §7.2 + §11.2
> - L2 Entry 飽和管理（ADR-010） → 主 SPEC §7.3 引用 SPEC-entry-consolidation-skill
> - 治理客製化邊界（Server 硬性 vs 用戶軟性）→ 主 SPEC §15（禁止模式）+ SPEC-governance-framework
> - 分層路由規則（L2/L3/Task/sources） → 主 SPEC §3 分層模型
>
> 本檔案保留僅為歷史追溯，**不再作為 canonical 來源**。新規則請以主 SPEC 為準。

---

## 原始背景簡述

本 SPEC 原於 2026-03-25 提出，目的是把 L2 從「文件索引」重新定義為「公司共識概念」，並建立三問 + impacts gate 的治理門檻。經過 ADR-010（entity entries）、ADR-013（分散治理模型）、ADR-041（embedding）、ADR-045（protocol collection）等多份 ADR 演進後，於 2026-04-23 的 grand ontology refactor 中統整至主 SPEC v2，成為單一 canonical 來源。

## 超連結索引

| 原 SPEC 章節 | 新位置 |
|--------------|--------|
| 重新定義 L2 / 三問判斷標準 | `SPEC-ontology-architecture.md#71-三問--impacts-gate` |
| 硬規則：impacts ≥1 | `SPEC-ontology-architecture.md#71-三問--impacts-gate` |
| L2 生命週期 | `SPEC-ontology-architecture.md#72-l2-lifecycle` |
| L2 反饋路徑 | `SPEC-ontology-architecture.md#14-governance-對照` |
| Entity Entries 治理 | `SPEC-ontology-architecture.md#73-entity-entries` + `SPEC-entry-consolidation-skill` |
| Server 硬性底線 / 用戶可客製 | `SPEC-ontology-architecture.md#15-禁止模式` + `SPEC-governance-framework` |
| 全局統合演算法要求 | 移至 `PLAN-ontology-grand-refactor` 實作 wave |
| AC（PM 驗收） | 已化為主 SPEC §18 完成定義 + `ADR-048` acceptance criteria |
