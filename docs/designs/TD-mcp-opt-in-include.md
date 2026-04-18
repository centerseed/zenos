---
type: TD
id: TD-mcp-opt-in-include
spec: SPEC-mcp-opt-in-include
adr: ADR-040
status: Ready
created: 2026-04-18
---

# TD: MCP get/search opt-in include（Phase A）

## 調查報告

### 已讀文件
- `docs/decisions/ADR-040-mcp-read-api-opt-in-include.md` — Decision: 加 `include` 參數，Phase A backward compat default eager dump + warning，Phase B 切換 default，Phase C 移除 legacy。
- `docs/specs/SPEC-mcp-opt-in-include.md` — 19 條 AC，明確 Phase A 範圍，out-of-scope 清楚列出。
- `src/zenos/interface/mcp/get.py` — entity 分支 line 74-152 為 eager dump 的實作位置：`_serialize(result)` + outgoing/incoming split（line 119-144）+ `active_entries` list_by_entity（line 146-147）+ impact_chain forward/reverse（line 148-150）。
- `docs/plans/HANDOFF-2026-04-18-governance-refactor.md` — Dashboard 不走 MCP 已確認；實作只影響 MCP interface 層。

### 未讀但不影響 Phase A
- `src/zenos/interface/mcp/search.py` 完整內容：Developer 實作時需讀
- `src/zenos/interface/mcp/_common.py` `_serialize` 細節：Developer 實作 `_build_entity_response` 需讀

### 我不確定的事
- `_serialize(entity)` 既有行為是否已區分 eager/non-eager——需 Developer 在實作時確認並回報
- MCP partner `caller_id` 的取得方式——`_current_partner.get()` 是否含 id 欄位可寫入 structured log？若無需退而標 `caller_id=None`

## AC Compliance Matrix

| AC ID | 描述 | 實作位置 | Test Function | 狀態 |
|-------|------|---------|---------------|------|
| AC-MCPINC-01 | get default eager + warning | `get.py` entity 分支 | `test_ac_mcpinc_01_get_no_include_eager_dump_with_warning` | STUB |
| AC-MCPINC-02 | get summary-only | `get.py` + `_include.py:_build_entity_response` | `test_ac_mcpinc_02_get_summary_only` | STUB |
| AC-MCPINC-03 | summary + relationships | 同上 | `test_ac_mcpinc_03_get_summary_plus_relationships` | STUB |
| AC-MCPINC-04 | summary + entries limit=5 | 同上 | `test_ac_mcpinc_04_get_summary_plus_entries_limit_5` | STUB |
| AC-MCPINC-05 | summary + impact_chain | 同上 | `test_ac_mcpinc_05_get_summary_plus_impact_chain` | STUB |
| AC-MCPINC-06 | summary + sources（取代 source_count） | 同上 | `test_ac_mcpinc_06_get_summary_plus_sources_array` | STUB |
| AC-MCPINC-07 | include=["all"] eager no warning | `get.py` | `test_ac_mcpinc_07_get_include_all_eager_no_warning` | STUB |
| AC-MCPINC-08 | 未知 include value reject | `_include.py:validate_include` | `test_ac_mcpinc_08_get_unknown_include_rejected` | STUB |
| AC-MCPINC-09 | non-entity collection ignore | `get.py` 分支頂層 | `test_ac_mcpinc_09_get_non_entity_collection_include_ignored` | STUB |
| AC-MCPINC-10 | search default eager + warning | `search.py` | `test_ac_mcpinc_10_search_no_include_eager_dump_with_warning` | STUB |
| AC-MCPINC-11 | search summary shape + summary_short 120 codepoint | `search.py` + `_include.py` | `test_ac_mcpinc_11_search_summary_shape` | STUB |
| AC-MCPINC-12 | search summary + tags | 同上 | `test_ac_mcpinc_12_search_summary_plus_tags` | STUB |
| AC-MCPINC-13 | search include=["full"] eager no warning | `search.py` | `test_ac_mcpinc_13_search_include_full_eager_no_warning` | STUB |
| AC-MCPINC-14 | search 未知 value reject | `_include.py:validate_include` | `test_ac_mcpinc_14_search_unknown_include_rejected` | STUB |
| AC-MCPINC-15 | search non-entity ignore | `search.py` | `test_ac_mcpinc_15_search_non_entity_collection_include_ignored` | STUB |
| AC-MCPINC-16 | dashboard REST fields unchanged | 不修改 dashboard_api.py | `test_ac_mcpinc_16_dashboard_rest_payload_fields_unchanged` | STUB |
| AC-MCPINC-17 | dashboard UI no regression | Architect Phase 3 人工驗證 | `test_ac_mcpinc_17_dashboard_ui_no_regression` | STUB（Phase 3） |
| AC-MCPINC-18 | tool docstring 含 include 範例 | `get.py` + `search.py` docstring | `test_ac_mcpinc_18_tool_docstring_has_include_examples` | STUB |
| AC-MCPINC-20 | docstring 每個 include 值有 use case 對應 | `get.py` + `search.py` docstring | `test_ac_mcpinc_20_docstring_include_use_case_mapping` | STUB |
| AC-MCPINC-19 | warning 結構化 log | `_include.py:log_deprecation_warning` | `test_ac_mcpinc_19_warning_log_structured` | STUB |

## Component 架構

```
src/zenos/interface/mcp/
├── _include.py          # NEW — include 邏輯集中
│   ├── VALID_ENTITY_INCLUDES = {"summary", "relationships", "entries",
│   │                              "impact_chain", "sources", "all"}
│   ├── VALID_SEARCH_INCLUDES = {"summary", "tags", "full"}
│   ├── validate_include(include, valid_set) -> set[str] | ErrorResponse
│   ├── log_deprecation_warning(tool: str, collection: str, caller_id)
│   ├── build_entity_response(entity, relationships, entries, impact,
│   │                          reverse_impact, sources, include_set) -> dict
│   │   # 根據 include_set 條件組裝 response
│   └── build_search_result(entity, score, include_set) -> dict
├── get.py               # MODIFIED — 呼叫 _include helpers
└── search.py            # MODIFIED — 呼叫 _include helpers
```

**設計原則：**
- `_include.py` 是唯一 SSOT——`get` 與 `search` 絕不獨立判斷 include
- validate_include 回傳 `set[str]` 讓 caller 用 set ops
- summary_short 的 120 字元截斷 helper 放在 `_include.py`（test AC-11 會檢查中文長度）

## 介面合約

### `get`
| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| collection | str | Y | 既有 |
| name / id | str? | 擇一 | 既有 |
| workspace_id | str? | N | 既有 |
| **include** | **list[str] \| None** | **N** | **新增。None → Phase A eager + warning；set → 條件展開；未知值 → reject** |

### `search`
| 參數 | 型別 | 必填 | 說明 |
|------|------|------|------|
| （既有參數不變） | | | |
| **include** | **list[str] \| None** | **N** | **新增，同上** |

### Deprecation warning（structured log）
```json
{
  "event": "mcp_include_deprecation",
  "tool": "get" | "search",
  "collection": "entities" | ...,
  "caller_id": "<partner_id or null>",
  "timestamp": "<ISO 8601>",
  "message": "caller not using include, defaulting to full payload — this will change in ADR-040 Phase B"
}
```

## DB Schema 變更

無。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | 建 `_include.py`（helpers + validate + log + build_entity_response + build_search_result） | Developer | 新檔存在；`validate_include` 對未知值回 ErrorResponse；unit test（非 spec_compliance）覆蓋 happy path + unknown |
| S02 | 修改 `get.py`：entity 分支呼叫 `_include.build_entity_response`，non-entity ignore，未知 value reject | Developer | AC-01~09 test 從 FAIL 變 PASS |
| S03 | 修改 `search.py`：同樣邏輯 + summary_short 120 codepoint 截斷 | Developer | AC-10~15 test 從 FAIL 變 PASS |
| S04 | 更新 `get.py` + `search.py` docstring，含 include=["summary"] 與 include=["all"] 範例 | Developer | AC-18 PASS |
| S05 | Dashboard REST 驗證（不改 dashboard_api.py，只在 test 斷言 fields unchanged） | Developer | AC-16 PASS |
| S06 | QA 跑 AC test + 現有 regression + 冒煙 | QA | 全 PASS；Architect 取得 QA Verdict |
| S07 | 部署 + 端到端 dogfood 驗證（Architect） | Architect | Cloud Run deployed；`get(..., include=["summary"])` 實測 < 2k tokens；AC-17 UI 冒煙通過 |

## Done Criteria（Developer 交付時必須全過）

1. `_include.py` 已建立且 validate_include / build_entity_response / build_search_result 可被 import
2. `get.py` 與 `search.py` 已接受 `include` 參數（signature 更新）
3. 未知 include value 回 structured error（含支援值清單）
4. default（include=None）路徑與 Phase A 部署前 **欄位集合 + 巢狀結構相同**（非 byte-level）
5. docstring 含 `include=["summary"]` 與 `include=["all"]` 兩個具體範例
6. **以下 AC test 必須從 FAIL 變 PASS**：AC-MCPINC-01~16、18、19、20（共 19 條）。AC-MCPINC-17 為 Phase 3 驗證，Developer 不負責。
7. 跑 `.venv/bin/pytest tests/spec_compliance/test_mcp_opt_in_include_ac.py -x` 全 PASS
8. 跑 `.venv/bin/pytest tests/interface/test_tools.py tests/interface/ -x` 無 regression
9. Simplify 階段：確認 `_include.py` 無死 code、get/search 沒重複 include 判斷邏輯
10. Completion Report：列出改動檔案、test 結果、任何 deviation 說明

## Risk Assessment

### 1. 不確定的技術點
- `_serialize(entity)` 的既有行為是否已經抽共用欄位——若是則 `build_entity_response` 可重用；若否需抽
- `caller_id` 能否從 `_current_partner.get()` 取得——Developer 確認後若無可寫 `None`
- `summary_short` codepoint 截斷對 emoji / combining char 是否需要 grapheme 處理——Phase A 先用 `str[:120]`，若 QA 測 regression 再評估

### 2. 替代方案與選擇理由
- **新檔 `_include.py`**：vs 直接塞進 `_common.py`。選新檔，因為 include 邏輯有明確語意邊界，未來 Phase B 刪除 legacy 方便。
- **validate_include 回傳 set**：vs list。選 set，dedup 自動 + O(1) membership check + 任意順序符合 SPEC 裁決。
- **structured log 用 `logger.warning` + extra dict**：vs 自建 log entry。選前者，Cloud Run 會自動 parse。

### 3. 需要用戶確認的決策
無（7 條 open questions 已全部 Architect 裁決）。

### 4. 最壞情況與修正成本
- **Worst case**：default path payload 結構意外變動 → 第三方 partner 爆炸。
  - 緩解：AC-01 + AC-10 明確斷言 eager payload shape 不變。
  - 修正成本：若真爆，revert MCP deploy 約 5 分鐘。
- **Second**：summary_short 中文截斷產生亂碼（emoji grapheme 切一半）。
  - 緩解：Phase A 接受風險；QA 測若發現則升級到 grapheme 處理（`grapheme` 套件或手寫）。
  - 修正成本：小 patch。
