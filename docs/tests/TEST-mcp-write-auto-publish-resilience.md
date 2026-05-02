---
doc_id: TEST-mcp-write-auto-publish-resilience
title: 測試場景：MCP write auto-publish resilience
type: TEST
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 測試場景：MCP write auto-publish resilience

## P0 Scenarios

### P0-1 Auto-publish failure does not fail write

- AC IDs: AC-WAPR-01, AC-WAPR-02
- Given document upsert succeeds for a current formal-entry GitHub document without snapshot
- When auto-publish raises `FileNotFoundError` or `RuntimeError`
- Then `write(collection="documents")` returns `status="ok"`
- And response contains an auto-publish failure warning or suggestion
- And the failure log includes `doc_id` plus stack context

### P0-2 Non-target documents skip auto-publish

- AC IDs: AC-WAPR-03
- Given a document is not current, not formal-entry, or has no GitHub source
- When write/delivery suggestion flow runs
- Then `_publish_document_snapshot_internal` is not called
- And no auto-publish failure warning is added

### P0-3 Preflight hard invalid remains rejected

- AC IDs: AC-WAPR-04
- Given explicit payload is current formal-entry with GitHub source
- And remote visibility check returns hard failure
- When `write(collection="documents")` handles the payload
- Then response is `status="rejected"`
- And document upsert is not called

## P1 Scenarios

### P1-1 Existing snapshot skips publish

- AC IDs: AC-WAPR-03
- Given the document already has `primary_snapshot_revision_id`
- When `_maybe_auto_publish_document` runs
- Then it returns no warning and does not call publish internal
