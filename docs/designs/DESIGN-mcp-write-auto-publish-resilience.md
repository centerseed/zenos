---
doc_id: DESIGN-mcp-write-auto-publish-resilience
title: 技術設計：MCP write auto-publish resilience
type: DESIGN
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 技術設計：MCP write auto-publish resilience

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-document-delivery-layer.md` — P0-6 要求 current formal-entry GitHub doc auto-publish；來源讀取失敗時必須保留最後可用 revision 並標記 stale，不得清空 Reader。
- `docs/specs/SPEC-mcp-tool-contract.md` — `write(documents)` 已定義 unified response rejection shapes；`read_source` adapter unavailable 是 structured error，不應以 traceback 破壞 MCP contract。
- `docs/specs/SPEC-governance-observability.md` — 既有 observability 要求 error event 補 input context；本輪只要求 auto-publish warning/log 帶 `doc_id` 與 exception context。
- `src/zenos/interface/mcp/write.py:719` — `_maybe_auto_publish_document(serialized)` 是 current formal-entry GitHub docs 的 best-effort auto-publish path。
- `src/zenos/interface/mcp/write.py:754` — auto-publish 呼叫 `zenos.interface.dashboard_api._publish_document_snapshot_internal(effective_id, doc_id)`。
- `src/zenos/interface/mcp/write.py:759` — 現行工作樹已在 `_maybe_auto_publish_document` 內 catch `Exception` 並 return warning；需由 Developer 補 regression test 確認 deployed incident class 不再回歸。

### 搜尋但未找到

- `docs/specs` / `docs/designs` 中搜尋 `auto-publish traceback` → 無專用 incident spec。
- ZenOS open task 中搜尋 `mcp write auto publish infer_task_links schema mismatch governance ai` → 無開放重複 task。

### 我不確定的事（明確標記）

- `[未確認]` production tracebacks 來自目前工作樹之前的版本，或仍有另一條 write path 會繞過 `_maybe_auto_publish_document` catch。
- `[未確認]` `/api/docs/{id}/content` 4 個 500 stack trace 尚未撈，不納入本輪 P0。

### 結論

可以開始設計與派工。第一輪目標是用 regression test 鎖住 `write` 主流程不被 auto-publish exception 拖死；若 Developer 發現另一條未 catch path，需在同 scope 修正。

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-WAPR-01 | auto-publish exception 不冒到 MCP layer，write 仍 ok 並帶 warning/suggestion | `src/zenos/interface/mcp/write.py:_maybe_auto_publish_document` / write response assembly | `test_ac_wapr_01_write_survives_auto_publish_failure` | STUB |
| AC-WAPR-02 | auto-publish 失敗 log 含 doc_id 與 stack context | `src/zenos/interface/mcp/write.py:_maybe_auto_publish_document` | `test_ac_wapr_02_auto_publish_failure_logs_doc_id` | STUB |
| AC-WAPR-03 | 不符合條件的 document 不觸發 auto-publish 且無 warning | `src/zenos/interface/mcp/write.py:_maybe_auto_publish_document` | `test_ac_wapr_03_non_formal_document_skips_auto_publish` | STUB |
| AC-WAPR-04 | explicit preflight hard invalid 仍 reject，不被 resilience 放寬 | `src/zenos/interface/mcp/write.py:_preflight_document_remote_visibility` | `test_ac_wapr_04_preflight_hard_invalid_still_rejects` | STUB |

## Component 架構

- `write(collection="documents")`：主流程，負責 upsert document metadata/source，成功後合併 delivery suggestions/warnings。
- `_preflight_document_remote_visibility(data)`：upsert 前 hard rejection gate；維持原語意。
- `_maybe_auto_publish_document(serialized)`：upsert 後 best-effort delivery 補齊；任何 publish exception 都必須降級。
- `_publish_document_snapshot_internal(effective_id, doc_id)`：dashboard delivery publish implementation；本輪不改其內部行為。

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `write` | `collection` | `str` | 是 | 本輪只處理 `documents` |
| `write` | `data` | `dict` | 是 | document payload；不可接受 JSON string |
| `write` | `id` | `str | None` | 否 | 既有 entity id |
| `write` | `id_prefix` | `str | None` | 否 | write ops 若使用 prefix 仍應 reject |
| `write` | `workspace_id` | `str | None` | 否 | active workspace override |
| `write` | `source` | `str | None` | 否 | batch patch provenance |
| `_maybe_auto_publish_document` | `serialized` | `dict` | 是 | upsert 後 serialized document |
| `_publish_document_snapshot_internal` | `effective_id` | `str` | 是 | partner/effective identity |
| `_publish_document_snapshot_internal` | `doc_id` | `str` | 是 | document id |

## DB Schema 變更

無。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 補 regression tests 並修正任何仍會讓 auto-publish exception 冒泡的 write path | Developer | AC-WAPR-01~04 tests 從 FAIL 變 PASS；最小 pytest 通過 |
| S02 | 驗收 regression 與 code path | QA | 跑 AC tests、grep 驗證 catch/log/preflight，Verdict PASS |

## Done Criteria

1. `tests/spec_compliance/test_mcp_write_auto_publish_resilience_ac.py` 中 AC-WAPR-01~04 全部由 FAIL 改為 PASS。
2. `write(collection="documents")` 在 post-upsert auto-publish exception 時回 `status="ok"`，並在 response warnings/suggestions 中告知 publish 失敗。
3. auto-publish failure log 保留 `doc_id` 並使用 `exc_info=True` 或等價 stack context。
4. 非 current formal-entry GitHub doc 不呼叫 `_publish_document_snapshot_internal`。
5. `_preflight_document_remote_visibility` hard failure 行為不被放寬。
6. 驗證指令至少包含：`.venv/bin/pytest tests/spec_compliance/test_mcp_write_auto_publish_resilience_ac.py -q`。

## QA Scenario Matrix

| Scenario | Priority | AC IDs | Steps | Expected |
|----------|----------|--------|-------|----------|
| GitHub 404 during auto-publish after document upsert | P0 | AC-WAPR-01, AC-WAPR-02 | Mock document upsert success, mock publish raising `FileNotFoundError`, call `write(collection="documents")` | Response ok; warning/suggestion present; logger sees doc_id + stack |
| Non formal-entry document write | P0 | AC-WAPR-03 | Call `_maybe_auto_publish_document` or write with `status=draft` / no GitHub source | Publish internal not called; warnings empty |
| Hard invalid remote preflight | P0 | AC-WAPR-04 | Mock `_check_github_source_remote_visibility` hard failure before upsert | Response rejected; upsert not called |

## Risk Assessment

### 1. 不確定的技術點

- `[未確認]` production traceback 是否來自部署落後於目前工作樹；Developer 需用 regression test 確認現行分支已覆蓋。
- `[未確認]` 是否還有 patches/sync path 直接呼叫 publish helper 而未經 `_maybe_auto_publish_document`。

### 2. 替代方案與選擇理由

- 選擇：維持 auto-publish best-effort，exception 降級為 warning。理由：符合 write 主流程與 delivery 輔助流程分層。
- 不選：GitHub 404 時 reject write。理由：會重現 incident 類型，metadata/source 治理被 delivery 補齊拖死。
- 不選：停用 auto-publish。理由：違反 `SPEC-document-delivery-layer` current formal-entry 預設補 delivery 的方向。

### 3. 需要用戶確認的決策

無。這是 incident resilience fix，不涉及正式 deploy、schema migration、資料刪除或產品語意改變。

### 4. 最壞情況與修正成本

最壞情況是 auto-publish 仍失敗但 write 成功，delivery snapshot 未補齊。修正成本低：重新 publish 或修 GitHub source 後再次 sync/write；ontology metadata 不會遺失。
