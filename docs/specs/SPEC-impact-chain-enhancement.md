---
type: SPEC
id: SPEC-impact-chain-enhancement
status: Superseded
ontology_entity: l2
created: 2026-04-05
updated: 2026-04-23
superseded_by: SPEC-ontology-architecture v2 §10.4
---

# Transition Note: Impact Chain Enhancement（併入主 SPEC §10.4）

本 SPEC 已於 2026-04-23 併入 [`SPEC-ontology-architecture v2 §10.4`](./SPEC-ontology-architecture.md)。

自該日起，下列內容統一以主 SPEC §10 為權威：

- `impact_chain`（forward）與 `reverse_impact_chain`（backward）雙向語意
- 最大 5 跳深度、循環防呆、`truncated=true` flag
- MCP `get(include=["impact_chain"])` 回傳 shape
- `top_k_per_hop` / intent ranking 的 interface（細節見 `SPEC-semantic-retrieval`）
- 與 `SPEC-governance-feedback-loop` 的關係

## Implementation 狀態（保留歷史）

- **P0 Reverse Impact Chain**：ACCEPTED，shipped commit `0ede9cf` (2026-04-03)
- **P1 Dashboard 多跳顯示**：仍未落地，移交至 Dashboard 功能 SPEC 處理（`SPEC-task-view-clarity` / UI wave）
- **P2 變更推送通知**：defer；若未來重啟，新 SPEC 需引主 SPEC §10.4 為基礎

## Migration Rule

- 新增或修改 impact chain / graph traversal 規格，只能修改主 SPEC §10
- 任何新文件若仍引用本 SPEC 作為 SSOT，應改為引用 `SPEC-ontology-architecture v2 §10.4`
- 不得在此新增內容
