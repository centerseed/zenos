---
type: SPEC
id: SPEC-knowledge-graph-semantic
status: Superseded
ontology_entity: l2
created: 2026-04-03
updated: 2026-04-23
superseded_by: SPEC-ontology-architecture v2 §10
---

# Transition Note: Knowledge Graph Semantic（併入主 SPEC §10）

本 SPEC 已於 2026-04-23 併入 [`SPEC-ontology-architecture v2 §10`](./SPEC-ontology-architecture.md)。

## Implementation 狀態（保留歷史）

| 原需求 | 狀態 | 後續處置 |
|--------|------|---------|
| P0.1 關聯語意動詞 `verb` | **REJECTED** 2026-04-18（填寫率 8.8%，`description` 已承擔語意）| DDL 欄位保留避免 migration risk；停止治理評分依據。本條歷史說明已併入主 SPEC §10.5 |
| P0.2 影響鏈遍歷 API | **ACCEPTED** shipped commit `0ede9cf` (2026-04-03) | canonical 移至主 SPEC §10.4（forward/reverse impact chain）|
| P1.3 圖拓撲 Blindspot | **REJECTED** 2026-04-18（89% false positive）| 拓撲偵測語意留在 `SPEC-governance-feedback-loop` / `SPEC-governance-observability`，不進 core schema。主 SPEC §10.5 已明確邊界 |
| P1.4 AI 建議動詞 | **REJECTED**（依附 P0.1 一併移除）| 無 |
| P1.5 治理評分納入 verb 完整度 | **REJECTED**（依附 P0.1 一併移除）| 無 |
| P2.6 依動詞篩選 | **DEFERRED**（依附 P0.1）| 無 |
| P2.7 節點間路徑查詢 | **DEFERRED** | 若重啟，新 SPEC 需引主 SPEC §10.4 為基礎 |

## Migration Rule

- 新增或修改 graph traversal / relationship semantics，只能修改主 SPEC §10
- 拓撲分析 / blindspot 偵測 → `SPEC-governance-feedback-loop` / `SPEC-governance-observability`
- 不得在此新增內容
