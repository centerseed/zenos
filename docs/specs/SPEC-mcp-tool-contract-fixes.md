---
type: SPEC
id: SPEC-mcp-tool-contract-fixes
status: Superseded
ontology_entity: mcp-interface
created: 2026-04-05
updated: 2026-04-23
superseded_by: SPEC-mcp-tool-contract
---

# Transition Note: MCP Tool Contract Fixes（併入 SPEC-mcp-tool-contract）

本 SPEC 已併入 [`SPEC-mcp-tool-contract`](./SPEC-mcp-tool-contract.md)。

自 2026-04-15 起，MCP tool 的唯一權威為 `SPEC-mcp-tool-contract`；2026-04-23 進一步補齊 runtime canonical（tool 清單表、error code 對應 `file:line`、完整 AC `AC-MCP-01..32`），本 fixes SPEC 不再獨立存在。

## 原 Issue 歸屬

| 原 Issue | 結論 | 新位置 |
|---------|------|--------|
| Issue 1 `confirm` 參數 alias | canonical = `accepted`；`accept` 為 server 自動改寫 alias | `SPEC-mcp-tool-contract §8.6` + `AC-MCP-04` |
| Issue 2 `search` envelope | ✅ shipped；所有 lookup tools 統一 envelope | `SPEC-mcp-tool-contract §6 / §8.1` + `AC-MCP-01 / AC-MCP-24` |
| Issue 3 `linked_entities=[]` warning | `warnings` 必含治理提示 | `SPEC-task-governance §8`；本 SPEC AC-MCP-01（warnings 必存在） |
| Issue 4 description reformat | 文件補充 | `SPEC-task-governance §7` |
| Issue 5 `status` 多值 | server `IN` 子句；文件補充 | `SPEC-mcp-tool-contract §8.1`（filter 欄位） |
| Issue 6 CJK bigram tokenizer | ✅ shipped | 實作歷史；Search 行為歸 `SPEC-mcp-tool-contract §8.1` |
| Issue 7 `linked_entities` 展開一致 | 統一 expanded objects | `SPEC-mcp-tool-contract §8.5`（task response 一致性） |

## Migration Rule

- 新增或修改 MCP tool contract，只能修改 `SPEC-mcp-tool-contract`
- 本 SPEC 不得再新增內容；任何新文件引用 MCP 契約應指向 `SPEC-mcp-tool-contract`
