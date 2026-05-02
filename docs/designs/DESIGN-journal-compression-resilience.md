---
doc_id: DESIGN-journal-compression-resilience
title: 技術設計：Journal compression resilience
type: DESIGN
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 技術設計：Journal compression resilience

## Problem

`_compress_journal` treated LLM structured summary parsing as part of the critical compression path. The outer catch prevented a tool crash, but the traceback still entered prod Error Reporting and compression was skipped.

## Design

- Add `_fallback_journal_compression_summary(entries)` in `src/zenos/interface/mcp/__init__.py`.
- Compute fallback summary before invoking LLM.
- Wrap only `create_llm_client().chat_structured(...)` in a narrow `try/except`.
- On LLM failure, log a warning with `error_type`, `partner_id`, and `entry_count`, without `exc_info=True`.
- Continue `create_summary(...)` and `delete_by_ids(...)` using fallback summary.
- Keep the outer `_compress_journal` catch for non-LLM failures.

## Spec Compliance Matrix

| AC | Implementation |
|----|----------------|
| AC-JCR-01 | LLM failure falls back and still creates/deletes journal rows |
| AC-JCR-02 | LLM failure warning omits traceback `exc_info` |
| AC-JCR-03 | Successful LLM summary overrides fallback |
| AC-JCR-04 | `journal_write` reports compressed success when fallback compression succeeds |

## Done Criteria

- Focused AC tests pass.
- Existing journal tool tests pass.
- No prod deploy is performed in this task.
