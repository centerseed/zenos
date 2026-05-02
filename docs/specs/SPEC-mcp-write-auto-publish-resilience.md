---
doc_id: SPEC-mcp-write-auto-publish-resilience
title: 功能規格：MCP write auto-publish resilience
type: SPEC
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 功能規格：MCP write auto-publish resilience

## Background

2026-04-17 至 2026-05-01 的 MCP API log 調查顯示，`write(collection="documents")` 在 auto-publish current formal-entry GitHub documents 時，若 GitHub source 已 rename/delete 或不可讀，auxiliary publish path 會造成主 write workflow 失敗。

`write` 是治理主流程；auto-publish 是 delivery 補齊輔助流程。輔助流程失敗不得阻斷 ontology metadata/source 寫入。

## Scope

P0 只處理 MCP `write(collection="documents")` 的 auto-publish resilience：

- auto-publish exception 必須降級為 structured warning / suggestion。
- `write` 主流程必須維持 `status="ok"`。
- 失敗 log 必須保留 `doc_id` 與 exception context，供 incident 後續追查。
- 不改變 explicit preflight hard rejection：current formal-entry GitHub source 在 create/update 前被判定 hard invalid 時，仍可 reject。

不包含：

- 新增完整 per-tool latency observability。
- 改寫 GitHub adapter。
- 實作 governance AI chunking。
- 修復 client schema aliasing。

## Acceptance Criteria

- `AC-WAPR-01` Given `write(collection="documents")` 已成功 upsert 一份 `status=current`、`doc_role=index`、含 GitHub source 且尚無 `primary_snapshot_revision_id` 的 formal-entry document，When `_publish_document_snapshot_internal` 因 GitHub 404 / `FileNotFoundError` / `RuntimeError` 失敗，Then `write` 回傳 `status="ok"`，且 `warnings` 或 `suggestions` 包含 auto-publish 失敗原因，不可把 exception 冒到 MCP layer。
- `AC-WAPR-02` Given auto-publish 失敗，When server logging 執行，Then log event/message 必須包含 `doc_id` 與 stack context，讓 engineer 可從 Cloud Logging 追到失敗文件。
- `AC-WAPR-03` Given document 不符合 current formal-entry GitHub auto-publish 條件，When `write(collection="documents")` 成功，Then 不呼叫 `_publish_document_snapshot_internal`，且不新增 auto-publish warning。
- `AC-WAPR-04` Given explicit preflight 判定 current formal-entry GitHub source remote hard invalid，When `write(collection="documents")` 在 upsert 前處理該 payload，Then 仍可回 `status="rejected"`；本 resilience 不得放寬 preflight hard rejection。

## Notes

- 本 SPEC 延伸 `SPEC-document-delivery-layer` P0-6：來源讀取失敗時保留最後可用 revision / stale delivery，不得清空 Reader。
- 本 SPEC 針對 MCP write runtime：即使沒有既有 snapshot，auto-publish 失敗也只能阻斷 delivery 補齊，不得阻斷 write 主流程。
