---
doc_id: DESIGN-governance-task-link-resilience
title: 技術設計：Governance task link inference resilience
type: DESIGN
ontology_entity: 語意治理 Pipeline
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 技術設計：Governance task link inference resilience

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-governance-observability.md` — 既有 observability 要求 LLM ValidationError audit 補 `error_type`、`input_context`、`raw_llm_output`；本輪落地到 `infer_task_links` 的 chunk/fallback audit summary。
- `src/zenos/application/knowledge/governance_ai.py:486` — `infer_task_links` 現行一次把所有 `existing_entities` join 成 entity_lines 後呼叫單次 `chat_structured`。
- `src/zenos/application/knowledge/governance_ai.py:521` — structured output 呼叫使用 `TaskLinkInference`；任何 exception 都直接 fallback 成 `[]`。
- `src/zenos/application/action/task_service.py:264` — `TaskService` 只在 caller 未提供 `linked_entities` 時呼叫 `infer_task_links`，因此本輪不影響明確傳入 linked_entities 的 task。
- `tests/application/test_governance_ai_context.py:215` — 既有測試只驗證 LLM failure 不 crash 且回 `[]`，未覆蓋 partial chunk success 或 deterministic fallback。
- `src/zenos/infrastructure/llm_client.py:71` — `chat_structured` 對 Gemini 會注入 JSON schema；parse 失敗會 raise，需由 caller 做 bounded degradation。

### 搜尋但未找到

- `docs/specs` / `docs/designs` 中搜尋 `infer_task_links chunk` → 無既有 executable spec。
- Open tasks 搜尋 `mcp write auto publish infer_task_links schema mismatch governance ai` → 無開放重複 task。

### 我不確定的事（明確標記）

- `[未確認]` 最佳 chunk size 需要 production token 觀測校準；本輪先以保守固定上限實作並測試行為。
- `[未確認]` 80k chars 截斷是否完全由 candidate list 過大造成；但 bounded chunks 能降低最主要風險。

### 結論

可以開始設計與派工。這是內部 inference resilience，不需要 schema migration 或 deploy approval。

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-GTLR-01 | large candidates 分 chunks，多次 chat_structured 且每次不超上限 | `src/zenos/application/knowledge/governance_ai.py:infer_task_links` | `test_ac_gtlr_01_infer_task_links_chunks_large_candidate_sets` | STUB |
| AC-GTLR-02 | 單 chunk 失敗不拖垮成功 chunk | `GovernanceAI.infer_task_links` | `test_ac_gtlr_02_partial_chunk_failure_keeps_successful_links` | STUB |
| AC-GTLR-03 | 全 LLM 失敗時 deterministic keyword fallback 最多回 3 個 | `GovernanceAI.infer_task_links` | `test_ac_gtlr_03_all_chunks_fail_uses_keyword_fallback` | STUB |
| AC-GTLR-04 | unknown / duplicate IDs 被過濾去重且保序 | `GovernanceAI.infer_task_links` | `test_ac_gtlr_04_filters_unknown_and_duplicate_entity_ids` | STUB |
| AC-GTLR-05 | audit payload 含 chunk/failure/fallback summary | `_audit_governance` call from `infer_task_links` | `test_ac_gtlr_05_audit_includes_chunk_failure_and_fallback_summary` | STUB |

## Component 架構

- `TaskService.create_task`：維持不變；只負責在未提供 linked_entities 時呼叫 GovernanceAI。
- `GovernanceAI.infer_task_links`：改為 orchestrator，負責 candidate chunking、per-chunk LLM call、結果合併、fallback、audit。
- `TaskLinkInference`：schema 維持 `{entity_ids: list[str]}`，避免更動 LLM client contract。
- deterministic fallback：根據 task title/description 與 candidate entity `name/type/summary/tags.what` 的 normalized token overlap 排序，最多回 3 個。

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `infer_task_links` | `title` | `str` | 是 | task title |
| `infer_task_links` | `description` | `str` | 是 | task description |
| `infer_task_links` | `existing_entities` | `list[dict]` | 是 | candidate entities；output 只能來自此集合 |
| `_infer_task_link_fallback` | `title` | `str` | 是 | deterministic fallback input |
| `_infer_task_link_fallback` | `description` | `str` | 是 | deterministic fallback input |
| `_infer_task_link_fallback` | `existing_entities` | `list[dict]` | 是 | candidate entities |

## DB Schema 變更

無。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 實作 chunked `infer_task_links` + fallback + audit summary | Developer | AC-GTLR-01~05 tests 從 FAIL 變 PASS；既有 failure test 維持 pass |
| S02 | QA 驗收 inference resilience | QA | 跑 AC tests、既有 governance AI tests、靜態檢查 prompt bounded 與 fallback |

## Done Criteria

1. 新增 `tests/spec_compliance/test_governance_task_link_resilience_ac.py`，AC-GTLR-01~05 每條一個 test function。
2. `infer_task_links` 對 large candidate sets 使用 bounded chunks；單次 prompt entity lines 不超 chunk 上限。
3. partial chunk failure 不導致整體回空；成功 chunk 結果仍保留。
4. all chunks failure 時 deterministic fallback 最多回 3 個 input candidate IDs。
5. 合併結果去重、保序、過濾 unknown IDs。
6. audit/log payload 含 chunk_count、failed_chunk_count、fallback_used。
7. 驗證指令至少包含：`.venv/bin/pytest tests/spec_compliance/test_governance_task_link_resilience_ac.py tests/application/test_governance_ai_context.py -q`。

## QA Scenario Matrix

| Scenario | Priority | AC IDs | Steps | Expected |
|----------|----------|--------|-------|----------|
| Large candidate set | P0 | AC-GTLR-01 | 以超過 chunk 上限的 fake entities 呼叫 `infer_task_links` | 多次 LLM call；每次 prompt bounded |
| Partial LLM failure | P0 | AC-GTLR-02 | fake LLM 第一 chunk raise、第二 chunk success | 回傳第二 chunk links |
| All LLM failure fallback | P0 | AC-GTLR-03 | fake LLM 全 raise，title 命中 candidate name | 回傳最多 3 個 fallback IDs |
| Bad LLM IDs | P0 | AC-GTLR-04 | fake LLM 回 duplicate / unknown IDs | output 過濾去重保序 |
| Audit summary | P1 | AC-GTLR-05 | patch `_audit_governance` 觀察 payload | payload 有 chunk/fallback summary |

## Risk Assessment

### 1. 不確定的技術點

- `[未確認]` chunk size 最佳值需 production telemetry；本輪用常數與 tests 鎖行為，之後可依 logs 調整。
- fallback 對中文斷詞有限；本輪只做明確 substring/token overlap，不宣稱語意召回。

### 2. 替代方案與選擇理由

- 選擇：chunked structured calls + deterministic fallback。理由：最小改動、不改外部 contract，直接降低 truncated JSON 風險。
- 不選：提高 model output limit。理由：不能消除大 prompt/output 風險，且 provider-specific。
- 不選：完全停用 LLM inference。理由：會讓 task↔entity 自動連結品質倒退。

### 3. 需要用戶確認的決策

無。這是內部 resilience fix，不涉及資料刪除、schema migration、正式 deploy 或產品行為分歧。

### 4. 最壞情況與修正成本

最壞情況是 fallback 漏判，task 沒自動連到最佳 entity；修正成本低，caller 仍可手動提供 linked_entities 或後續補關聯。比錯連更可接受。
