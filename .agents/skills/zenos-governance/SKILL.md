---
name: zenos-governance
description: >
  ZenOS 治理總控 skill。當使用者要「讓 agent 自動治理現有專案」或
  「掃描結果不滿意，請自動修復」時使用。此 skill 會編排 zenos-setup、
  zenos-capture、zenos-sync 與 MCP tools（search/get/write/task/confirm/analyze），
  以最少人工介入完成治理閉環。適用於 Codex/ChatGPT/Gemini 等 agent 流程。
version: 2.0.0
---

# /zenos-governance

**本 skill 的 SSOT 位於 `skills/workflows/governance-loop.md`。**

請先用 Read tool 讀取 `skills/workflows/governance-loop.md` 的完整內容，然後嚴格按照該文件的流程執行。

相關治理規則（按需載入）：
- L2 治理：`skills/governance/l2-knowledge-governance.md`
- L3 文件治理：`skills/governance/document-governance.md`
- Task 治理：`skills/governance/task-governance.md`
