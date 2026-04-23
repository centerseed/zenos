---
type: SPEC
id: SPEC-doc-source-governance
status: Superseded
ontology_entity: l3-document
created: 2026-03-29
updated: 2026-04-23
superseded_by: SPEC-doc-governance
---

# Transition Note: Document Source Governance（併入 SPEC-doc-governance）

本 SPEC 已於 2026-04-23 併入 [`SPEC-doc-governance`](./SPEC-doc-governance.md)（同日 `SPEC-document-bundle` 亦併入 `SPEC-doc-governance`）。

自該日起，以下內容統一以 `SPEC-doc-governance` 為權威：

- `doc entity` 的 `single` / `index` 模型
- `sources[]` 結構與 `source_id`
- `source_status` 的定義與生命週期
- source platform contract
- rollout 能力矩陣
- `read_source(doc_id, source_id?)` 合約
- 各平台 URI validation 與 dead-link policy

schema canonical 在 `SPEC-ontology-architecture v2 §8.1`。

保留本檔的目的只有兩個：

1. 提供既有引用的過渡導向，避免舊連結失效
2. 記錄「source governance 已併入主 SPEC」這個架構決議

## Migration Rule

- 新增或修改 doc entity / source platform 規格時，只能修改 `SPEC-doc-governance`
- 任何新文件若仍引用本 SPEC 作為 SSOT，應改為引用 `SPEC-doc-governance`
- 不得在此新增內容
