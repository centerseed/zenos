---
doc_id: TEST-mcp-schema-compatibility-resilience
title: 測試場景：MCP schema compatibility resilience
type: TEST
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 測試場景：MCP schema compatibility resilience

## P0 Scenarios

- AC-MSCR-01: `write` accepts valid JSON object string `data`, warns, and rejects invalid/non-object strings.
- AC-MSCR-02: `journal_write` accepts CSV and JSON-array string tags and stores list tags.
- AC-MSCR-03: `read_source(uri="/docs/doc-1")` works as `doc_id="doc-1"` and warns.
- AC-MSCR-04: `task(updated_by="...")` ignores audit echo with warning and does not pass it into service data.
- AC-MSCR-05: `get(collection=None, id="x")` returns structured `MISSING_COLLECTION` rejection.
