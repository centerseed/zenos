---
type: SPEC
id: SPEC-doc-source-governance
status: Superseded
ontology_entity: L3 文件治理
created: 2026-03-29
updated: 2026-04-09
superseded_by: SPEC-document-bundle
---

# Transition Note: Document Source Governance

本文件不再作為 doc entity / source platform 的主規格。

自 2026-04-09 起，以下內容統一以 [`SPEC-document-bundle`](./SPEC-document-bundle.md) 為準：

- `doc entity` 的 `single` / `index` 模型
- `sources[]` 結構與 `source_id`
- `source_status` 的定義與生命週期
- source platform contract
- rollout capability matrix
- `read_source(doc_id, source_id?)` 合約
- 各平台 URI validation 與 dead-link policy

保留本文件的目的只有兩個：

1. 提供既有引用的過渡導向，避免舊連結失效
2. 記錄「source governance 已併入主 spec」這個架構決議

## Migration Rule

- 新增或修改 doc entity / source platform 規格時，只能修改 [`SPEC-document-bundle`](./SPEC-document-bundle.md)
- 任何新文件若仍引用本 spec 作為 SSOT，應改為引用 [`SPEC-document-bundle`](./SPEC-document-bundle.md)
- 若未來需要補 implementation note，應以 amendment 或附錄方式加到主 spec，而不是重建第二份平行 spec
