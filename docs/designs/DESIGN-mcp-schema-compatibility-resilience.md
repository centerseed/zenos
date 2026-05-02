---
doc_id: DESIGN-mcp-schema-compatibility-resilience
title: 技術設計：MCP schema compatibility resilience
type: DESIGN
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 技術設計：MCP schema compatibility resilience

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-mcp-tool-contract.md` — MCP tools 應回 unified response；可修正錯誤應是 `status="rejected"` 或 warnings，不應讓 client 只看到 ValidationError。
- `src/zenos/interface/mcp/write.py` — `write` 目前 type hint `data: dict`，docstring 告知 JSON string 是錯誤，但 server function body 尚未自行 coercion。
- `src/zenos/interface/mcp/journal.py` — `journal_write` 已有 `tags` JSON string / CSV string coercion；需補 AC regression。
- `src/zenos/interface/mcp/source.py` — `read_source` 只收 `doc_id`，舊 `uri` 參數會在 schema layer 失敗。
- `src/zenos/interface/mcp/task.py` — docstring 說 `updated_by` 不接受 caller 直接傳入，但 function signature 無 alias，舊 client 會 schema fail。
- `src/zenos/interface/mcp/get.py` — `collection` 是必填 positional；缺 collection 會在 schema layer 失敗，無 structured guidance。

### 搜尋但未找到

- `tests/spec_compliance` 中無 schema compatibility 專用 AC tests。
- Open task 搜尋 schema mismatch 相關無重複進行中 task。

### 我不確定的事（明確標記）

- `[未確認]` FastMCP 對 unknown kwargs 是否會在 Python function 之前攔截；本輪透過加入 explicit legacy parameters 降低風險。

### 結論

可以開始派工。改動限定在 MCP boundary normalizers 與 release skill/docstring，不涉及 DB schema。

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-MSCR-01 | `write.data` JSON object string coerces to dict with warning | `src/zenos/interface/mcp/write.py` | `test_ac_mscr_01_write_accepts_json_string_data_with_warning` | STUB |
| AC-MSCR-02 | `journal_write.tags` string normalizes to list | `src/zenos/interface/mcp/journal.py` | `test_ac_mscr_02_journal_write_normalizes_string_tags` | STUB |
| AC-MSCR-03 | `read_source(uri=...)` alias maps to doc_id with warning | `src/zenos/interface/mcp/source.py` | `test_ac_mscr_03_read_source_uri_alias_warns_and_reads_doc` | STUB |
| AC-MSCR-04 | `task.updated_by` ignored with warning | `src/zenos/interface/mcp/task.py` | `test_ac_mscr_04_task_updated_by_audit_echo_is_ignored_with_warning` | STUB |
| AC-MSCR-05 | `get()` missing collection returns structured rejection | `src/zenos/interface/mcp/get.py` | `test_ac_mscr_05_get_missing_collection_returns_structured_rejection` | STUB |

## Component 架構

- MCP boundary functions own legacy alias/coercion.
- Domain/application services remain canonical and do not accept legacy audit echo fields.
- Release skill text is updated to prevent new clients from learning deprecated shapes.

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `write` | `data` | `dict | str` | 是 | `str` only accepted when valid JSON object; deprecated warning |
| `read_source` | `doc_id` | `str | None` | 是 unless `uri` alias used | canonical |
| `read_source` | `uri` | `str | None` | 否 | deprecated alias for doc_id or `/docs/{doc_id}` |
| `task` | `updated_by` | `str | None` | 否 | deprecated audit echo; ignored with warning |
| `get` | `collection` | `str | None` | 是 | missing returns structured rejection |

## DB Schema 變更

無。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 實作 MCP schema compatibility normalizers 與 AC tests | Developer | AC-MSCR-01~05 tests pass；相關既有 interface tests pass |
| S02 | QA 驗收 schema mismatch fix | QA | 跑 AC tests、靜態檢查 signature/docstring/release skill |

## Done Criteria

1. 新增 `tests/spec_compliance/test_mcp_schema_compatibility_resilience_ac.py`，AC-MSCR-01~05 每條一個 test function。
2. `write(data="<json object>")` 成功 coercion；invalid/non-object JSON structured reject。
3. `read_source(uri=...)` alias 可用且 warning 指向 `doc_id`。
4. `task(updated_by=...)` 不會 schema fail，且 warning 說明 ignored。
5. `get(collection=None)` structured reject `MISSING_COLLECTION`。
6. 更新 `skills/release` 相關文案，canonical examples 使用 dict/list/doc_id，並標出 deprecated aliases。
7. 驗證指令至少包含：`.venv/bin/pytest tests/spec_compliance/test_mcp_schema_compatibility_resilience_ac.py tests/interface/test_journal_tools.py tests/interface/test_read_source_selection.py -q`。

## QA Scenario Matrix

| Scenario | Priority | AC IDs | Steps | Expected |
|----------|----------|--------|-------|----------|
| JSON string write data | P0 | AC-MSCR-01 | call `write(collection="entities", data="{...}")` | ok + warning |
| string journal tags | P0 | AC-MSCR-02 | call `journal_write(tags="a,b")` | repo receives list |
| read_source uri alias | P0 | AC-MSCR-03 | call `read_source(uri="/docs/doc-1")` | reads doc-1 + warning |
| task audit echo | P0 | AC-MSCR-04 | call `task(..., updated_by="old")` | no validation failure; warning |
| get missing collection | P0 | AC-MSCR-05 | call `get(collection=None, id="x")` | structured rejection |

## Risk Assessment

### 1. 不確定的技術點

- `[未確認]` MCP framework 對 old unknown parameters 的攔截順序；explicit params are used to avoid that path.

### 2. 替代方案與選擇理由

- 選擇：boundary compatibility with warnings。理由：降低 agent workflow 斷點，同時保留 canonical schema guidance。
- 不選：只更新 skills。理由：舊 client 已在流量中，server 仍會遇到舊 shape。

### 3. 需要用戶確認的決策

無。這是 backward-compatible boundary hardening，不涉及資料 migration 或 deploy。

### 4. 最壞情況與修正成本

最壞情況是某個 alias 太寬導致誤解；透過 warning 與 only-safe coercion 限制 blast radius，可快速收窄。
