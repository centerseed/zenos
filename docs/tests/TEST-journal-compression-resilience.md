---
doc_id: TEST-journal-compression-resilience
title: 測試場景：Journal compression resilience
type: TEST
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 測試場景：Journal compression resilience

## P0 Scenarios

| Scenario | Given | When | Then | AC |
|----------|-------|------|------|----|
| LLM failure fallback | More than 20 original journal rows and structured summary parse fails | `_compress_journal` runs | Summary row is created, originals are deleted, return value is `True` | AC-JCR-01 |
| No traceback on LLM failure | LLM summary step raises | `_compress_journal` logs | Warning has no `exc_info=True` traceback | AC-JCR-02 |
| LLM success path | LLM returns a non-empty summary | `_compress_journal` runs | Summary row uses LLM text | AC-JCR-03 |
| Tool-level success | `journal_write` triggers compression | LLM summary fails but fallback succeeds | Tool response is ok and `compressed=True` | AC-JCR-04 |
