---
type: SPEC
id: SPEC-document-bundle
status: Superseded
ontology_entity: l3-document
created: 2026-04-09
updated: 2026-04-23
superseded_by: SPEC-doc-governance
---

# Transition Note: Document Bundle（併入 SPEC-doc-governance）

本 SPEC 已於 2026-04-23 併入 [`SPEC-doc-governance`](./SPEC-doc-governance.md)。

自該日起，以下內容統一以 `SPEC-doc-governance` 為權威：

- `doc_role = single | index` 語意與 CHECK constraint
- `sources[]` 結構（`source_id / uri / type / label / doc_type / doc_status / source_status / note / is_primary`）
- Source mutation（`add_source / update_source / remove_source / batch_update_sources`）
- `bundle_highlights` + `change_summary` + `highlights_updated_at` / `summary_updated_at`
- Source platform contract（URI validation / type normalization / reader adapter / dead-link policy）
- Rollout 能力矩陣（github / gdrive / notion / wiki / url）
- `read_source(doc_id, source_id?)` 合約與 `setup_hint / alternative_sources`
- Capture/sync 路由決策樹
- L2 sources[] vs L3 doc entity 邊界

schema canonical 在 `SPEC-ontology-architecture v2 §8.1`（`entity_l3_document` table + CHECK constraint）。

## Migration Rule

- 任何新文件若仍引用本 SPEC 作為 SSOT，應改引用 `SPEC-doc-governance`
- 新增或修改 doc entity / source platform 規格，只能修改 `SPEC-doc-governance`
- 保留本檔僅為避免舊連結失效；不得在此新增內容
