---
type: TD
id: TD-action-layer-mcp-interface
status: Superseded
ontology_entity: mcp-interface
created: 2026-03-26
updated: 2026-04-23
superseded_by: SPEC-mcp-tool-contract, SPEC-task-governance
---

# Transition Note: Action Layer MCP Interface（併入 SPEC-mcp-tool-contract）

本 TD 為 Action Layer 專屬 MCP interface 的早期技術設計。2026-04-23 Grand Refactor 後：

- MCP tool surface canonical 統一於 `SPEC-mcp-tool-contract`（19 tools + 統一 envelope + 結構化 error shapes）
- `task` / `plan` / `confirm` 的 per-tool contract → `SPEC-mcp-tool-contract §8.5-§8.9`
- task lifecycle / handoff / dispatcher 語意 → `SPEC-task-governance`

## Migration Rule

不得在此新增內容。MCP tool 新議題 → `SPEC-mcp-tool-contract` + 對應 runtime 檔（`src/zenos/interface/mcp/*.py`）。
