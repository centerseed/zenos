---
type: REF
id: REF-zenos-document-classification
status: Draft
ontology_entity: documentation-governance
created: 2026-03-26
updated: 2026-03-26
---

# Reference: ZenOS 現行文件分類盤點

## 目的

這份文件是 ZenOS 專案套用 `SPEC-doc-governance` 後的第一版分類盤點。
目的不是立即搬檔，而是先明確回答三個問題：

- 哪些文件已屬於正式治理範圍
- 哪些文件是 legacy working docs，需要後續整理
- 哪些文件應視為 archive、generated artifact、或排除項

---

## 專案層治理邊界

### 納入治理
- `docs/specs/`
- `docs/decisions/`
- `docs/playbooks/`
- `docs/scenarios/`
- `docs/reference/`
- `docs/archive/`
- `docs/spec.md`，作為 canonical 文件例外

### 暫不納入正式治理
- `docs/context-protocols/`
- `docs/ontology-instances/`
- `docs/demo/`

這些路徑目前保留，但視為工作素材、導入中間產物、或展示資產，不算正式治理文件。

---

## Canonical 例外

- `docs/spec.md`
  - 角色：ZenOS 現行有效的 canonical product spec
  - 狀態：保留原名與原位
  - 備註：不套用 `SPEC-` 檔名前綴，但屬正式治理文件

---

## 現有正式 SPEC 文件

以下為目前仍位於 active `docs/specs/` 的規格文件：

- `docs/specs/SPEC-agent-integration-contract.md`
- `docs/specs/SPEC-doc-governance.md`
- `docs/specs/SPEC-governance-observability.md`
- `docs/specs/SPEC-l2-entity-redefinition.md`
- `docs/specs/SPEC-partner-context-fix.md`

已收斂出 active spec surface，詳見 `docs/reference/REF-active-spec-surface.md`。

---

## 現有文件分類

### A. 正式治理文件

#### SPEC
- `docs/spec.md`  `canonical exception`
- `docs/specs/SPEC-agent-integration-contract.md`
- `docs/specs/SPEC-doc-governance.md`
- `docs/specs/SPEC-governance-observability.md`
- `docs/specs/SPEC-l2-entity-redefinition.md`
- `docs/specs/SPEC-partner-context-fix.md`

#### ADR
- `docs/decisions/ADR-001-marketing-automation-architecture.md`
- `docs/decisions/ADR-002-knowledge-ontology-north-star.md`
- `docs/decisions/ADR-003-governance-trigger-architecture.md`
- `docs/decisions/ADR-003-phase1-mvp-architecture.md`
- `docs/decisions/ADR-004-ontology-output-path.md`
- `docs/decisions/ADR-005-dashboard-graph-library.md`
- `docs/decisions/ADR-005-mcp-tool-consolidation.md`
- `docs/decisions/ADR-006-entity-project-separation.md`

#### TD
- `docs/designs/TD-action-layer-mcp-interface.md`
- `docs/designs/TD-dashboard-v1-implementation.md`
- `docs/designs/TD-foundation-p0-entity-schema.md`
- `docs/designs/TD-l2-entity-redesign.md`
- `docs/designs/TD-user-invitation-mvp.md`

#### PB
- `docs/playbooks/PB-zenos-shared-cloudsql.md`
- `docs/playbooks/PB-zenos-sql-cutover.md`

#### SC
- `docs/scenarios/SC-line-marketing.md`

#### REF
- `docs/reference/REF-zenos-document-classification.md`
- `docs/reference/REF-glossary.md`
- `docs/reference/REF-market-insights.md`
- `docs/reference/REF-enterprise-governance.md`
- `docs/reference/REF-marketing-one-pager.md`
- `docs/reference/REF-ontology-methodology.md`
- `docs/reference/REF-ontology-current-state.md`

### B. Legacy working docs

這些文件內容有價值，但目前命名、位置或性質不符合正式治理類型；應後續 rename、重分流、封存或排除。

#### Working implementation plans
- `docs/archive/specs/tasks-2026-03/T1-domain-layer.md`
- `docs/archive/specs/tasks-2026-03/T2-infrastructure-layer.md`
- `docs/archive/specs/tasks-2026-03/T3-application-layer.md`
- `docs/archive/specs/tasks-2026-03/T4-mcp-tools.md`
- `docs/archive/specs/tasks-2026-03/T5-scaffold-deploy.md`
- `docs/archive/specs/tasks-2026-03/T6-e2e-validation.md`
- `docs/archive/specs/tasks-2026-03/TD1-task-dispatch-ui-redesign.md`

建議：
- 不視為正式治理文件類型
- 保留作為執行 artifacts 時，可集中到 `docs/archive/implementation/` 或專案另定 working-docs 區

#### Working coordination / Q&A
- `docs/archive/specs/tasks-2026-03/PM-answers-zenos-sync-skill.md`
- `docs/archive/specs/tasks-2026-03/PM-questions-zenos-sync-skill.md`
- `docs/reference/REF-governance-paths-overview.md`

建議：
- 若結論已被正式文件吸收，直接 archive 或刪除
- 若仍有參考價值，可整理為 `REF-*.md`

### C. Archive

以下已位於 archive，可視為封存歷史：

- `docs/archive/company-pulse-dashboard.md`
- `docs/archive/dashboard-redesign-panorama.md`
- `docs/archive/dashboard-redesign-tech-design.md`
- `docs/archive/dashboard-v0-technical-design.md`
- `docs/archive/dashboard-v0.md`
- `docs/archive/marketing-automation-spec.md`
- `docs/archive/open-questions.md`
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

### D. Excluded / generated / asset

#### Context protocol
- `docs/context-protocols/paceriz.md`
- `docs/context-protocols/zenos.md`

定位：
- 導入前理解素材
- 暫不視為正式治理文件類型

#### Ontology instance artifacts
- `docs/ontology-instances/paceriz/index.md`
- `docs/ontology-instances/paceriz/blindspots.md`
- `docs/ontology-instances/paceriz/neural-layer.md`
- `docs/ontology-instances/paceriz/modules/acwr.md`
- `docs/ontology-instances/paceriz/modules/data-integration.md`
- `docs/ontology-instances/paceriz/modules/rizo-ai.md`
- `docs/ontology-instances/paceriz/modules/training-plan.md`
- `docs/ontology-instances/paceriz-v0-single-file.md.bak`

定位：
- ontology 建構或輸出產物
- 不納入正式文件治理；應改由 ontology 資料層治理

#### Demo asset
- `docs/demo/naruvia-panorama.html`

定位：
- 展示素材
- 不納入正式 Markdown 文件治理

#### Backup / noise
- `docs/specs/SPEC-governance-observability.md.bak`
- `docs/specs/SPEC-zenos-sql-cutover.md.bak-review`
- `docs/ontology-instances/paceriz-v0-single-file.md.bak`

建議：
- 刪除，不進 archive

---

## 當前主要整理結論

### 已成形的正式治理系統
- `SPEC`: 5 份 active + 18 份 archived/deferred
- `ADR`: 8 份
- `TD`: 5 份
- `PB`: 2 份
- `SC`: 1 份
- `REF`: 7 份含本文件
- `Canonical exception`: 1 份

### 需要後續整理的重點
- ADR 編號仍有重複：`ADR-003`、`ADR-005`
- 多數正式文件仍未補齊治理 frontmatter
- `docs/archive/specs/tasks-2026-03/` 僅保留追溯，不再視為 active spec surface
- 本次文件分類調整尚未同步回 ontology 的 L2 / L3 entity
- `docs/specs/` 仍需持續壓縮，避免 supporting spec 再膨脹回主規格面

---

## 下一步建議

1. 先處理低風險整理：
   - 刪除 `.bak` 類檔案
   - 修正 ADR 重複編號

2. 再處理正式文件 metadata：
   - 補齊正式文件 frontmatter
   - 為 canonical / superseded / archived 文件補 metadata

3. 最後處理 working docs 分流：
   - phase/task implementation plans
   - PM/Architect 協調問答
   - 是否建立 `working-docs` 或 `archive/implementation` 慣例

4. 每一批文件整理完成後，同步更新 ontology：
   - 更新 `documentation-governance` 等相關 L2 entity
   - 更新受影響文件對應的 L3 document entity
   - 補上 superseded / archived / renamed 的追溯關係
