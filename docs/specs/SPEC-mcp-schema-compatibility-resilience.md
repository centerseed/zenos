---
doc_id: SPEC-mcp-schema-compatibility-resilience
title: 功能規格：MCP schema compatibility resilience
type: SPEC
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 功能規格：MCP schema compatibility resilience

## Background

2026-04-17 至 2026-05-01 MCP API log 調查顯示，agent client 因舊 schema 或 audit echo 造成 51 件 client-side ValidationError。主要類型包含 `task(updated_by=...)`、`write(data="<json string>")`、`journal_write(tags="a,b")`、`get()` 缺 collection、`read_source(uri=...)`。

## Scope

- Server 對可安全修正的舊參數提供 graceful alias/coercion。
- Server 對不可推斷的缺參數提供 structured rejection，而不是 framework-level ValidationError。
- Release skill / tool docstring 必須明確說明 canonical shape 與相容 alias。

## Acceptance Criteria

- `AC-MSCR-01` Given `write(..., data="<valid JSON object string>")`, When server handles the call, Then it coerces `data` to dict, proceeds normally, and returns a warning about deprecated JSON string payload.
- `AC-MSCR-02` Given `journal_write(tags="a,b")` or `journal_write(tags="[\"a\",\"b\"]")`, When server handles the call, Then tags are normalized to list and journal write succeeds with normalized tags.
- `AC-MSCR-03` Given `read_source(uri="<doc id or /docs/doc id>")` and no `doc_id`, When server handles the call, Then it treats `uri` as legacy alias for `doc_id`, proceeds, and returns a warning telling callers to use `doc_id`.
- `AC-MSCR-04` Given `task(..., updated_by="...")`, When server handles the call, Then it ignores caller-supplied `updated_by`, returns a warning, and still uses actor context for actual updated_by.
- `AC-MSCR-05` Given `get()` omits `collection`, When server handles the call, Then response is `status="rejected"` with `data.error="MISSING_COLLECTION"` and guidance listing valid collections.

## Notes

- Compatibility does not mean silently accepting unsafe writes. `id_prefix` write restrictions, `project_id` rejection, and readonly `handoff_events` behavior remain unchanged.
