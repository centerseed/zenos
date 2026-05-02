---
doc_id: SPEC-governance-task-link-resilience
title: 功能規格：Governance task link inference resilience
type: SPEC
ontology_entity: 語意治理 Pipeline
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 功能規格：Governance task link inference resilience

## Background

2026-04-17 至 2026-05-01 的 MCP API log 調查顯示，`GovernanceAI.infer_task_links` 在兩週內 148 次 attempts 中有 88 次 structured output failure，失敗率約 59%。主要 spike 發生在 2026-04-24，根因是 `gemini-2.5-flash-lite` 面對大量 entity candidates 時輸出超過約 80k chars 後被截斷，導致 JSON parse fail。

同一 entity set 曾連續 retry 3 次都 truncated，代表現行策略沒有 bounded input / bounded output，也沒有有效降級。結果是 task ↔ entity 自動連結半癱，knowledge graph 品質受損。

## Scope

P0 只處理 `GovernanceAI.infer_task_links(...)` 的韌性：

- 將 entity candidates 分成 bounded chunks，避免單次 prompt/output 過大。
- 單 chunk LLM structured output 失敗時，不重試同一超大輸入；改記錄 error 並繼續其他 chunk。
- 全部 LLM chunk 都失敗時，使用 deterministic fallback 產生最多少量高信心 entity IDs。
- 回傳 entity IDs 必須去重、保序、且只包含 input candidates 裡存在的 IDs。

不包含：

- 更換 LLM provider。
- 改 task MCP schema。
- 改 `TaskService.create_task` API。
- 完整 per-tool latency observability。

## Acceptance Criteria

- `AC-GTLR-01` Given `infer_task_links` 收到超過單次 chunk 上限的 `existing_entities`，When 執行 inference，Then 必須分多次呼叫 `chat_structured`，每次 prompt 的 entity lines 不超過 chunk 上限。
- `AC-GTLR-02` Given 某一 chunk 的 `chat_structured` 因 JSON parse / ValidationError / RuntimeError 失敗，When 其他 chunk 成功，Then `infer_task_links` 回傳成功 chunk 的 entity IDs，且不因單 chunk 失敗回空陣列。
- `AC-GTLR-03` Given 所有 LLM chunks 都失敗，但 task title/description 與 candidate entity name 有明確 keyword overlap，When fallback 執行，Then 回傳最多 3 個 deterministic fallback entity IDs。
- `AC-GTLR-04` Given LLM 回傳不存在於 candidate set 的 entity ID 或重複 ID，When 結果合併，Then output 去重、保序，並過濾 unknown IDs。
- `AC-GTLR-05` Given chunked inference 發生失敗或 fallback，When audit/logging 執行，Then governance audit payload 至少包含 `model`、`task_title`、`candidate_entities_count`、`chunk_count`、`failed_chunk_count`、`fallback_used`。

## Notes

- fallback 是降級，不是替代 LLM。它只處理高信心 keyword overlap，寧可漏判，不可亂連。
- 本 SPEC 針對 task create 未帶 `linked_entities` 的自動連結品質；caller 明確傳入 linked_entities 時不受影響。
