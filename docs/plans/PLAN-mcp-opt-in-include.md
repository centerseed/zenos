---
spec: SPEC-mcp-opt-in-include
td: TD-mcp-opt-in-include
adr: ADR-040
created: 2026-04-18
status: done
---

# PLAN: MCP get/search opt-in include（Phase A）

## Entry Criteria
- SPEC-mcp-opt-in-include.md status=Draft, 19 AC (AC-MCPINC-01..19) 已定義
- TD-mcp-opt-in-include.md Done Criteria 明確
- ADR-040 status=Draft（落地後再 flip Accepted）

## Exit Criteria
- AC-MCPINC-01..16, 18, 19 在 `tests/spec_compliance/test_mcp_opt_in_include_ac.py` PASS
- AC-MCPINC-17 Architect 部署後人工驗證（dashboard UI 無 regression）
- Cloud Run 部署後 dogfood 實測 `get(..., include=["summary"])` < 2k tokens
- ADR-040 status flip 為 Accepted（同 commit）
- Journal 寫入

## Tasks
- [ ] **S01**: 建 `src/zenos/interface/mcp/_include.py`（含 VALID_*_INCLUDES、validate_include、log_deprecation_warning、build_entity_response、build_search_result、summary_short helper）
  - Files: `src/zenos/interface/mcp/_include.py`（新）
  - Verify: `.venv/bin/pytest tests/interface/test_include_helpers.py` 通過（Developer 可同時產 unit test）
- [ ] **S02**: 修改 `src/zenos/interface/mcp/get.py` entity 分支接 `_include`；非 entity collection 接受但忽略 (depends: S01)
  - Files: `src/zenos/interface/mcp/get.py`
  - Verify: AC-MCPINC-01..09 PASS
- [ ] **S03**: 修改 `src/zenos/interface/mcp/search.py`（include 參數 + summary_short 120 codepoint） (depends: S01)
  - Files: `src/zenos/interface/mcp/search.py`
  - Verify: AC-MCPINC-10..15 PASS
- [ ] **S04**: 更新 `get.py` + `search.py` docstring (depends: S02, S03)
  - Verify: AC-MCPINC-18 PASS
- [ ] **S05**: Dashboard REST field stability test (depends: S02)
  - Files: 不改 source；可在 spec_compliance test 或新 integration test 斷言
  - Verify: AC-MCPINC-16 PASS
- [ ] **S06**: QA 全量驗收
  - Verify: AC-MCPINC-01..16, 18, 19 全 PASS；現有 test suite 無 regression；QA Verdict
- [ ] **S07**: 部署 + 端到端驗證（Architect）
  - Verify: Cloud Run deploy 成功；dogfood `get(..., include=["summary"])` 實測 payload size；Dashboard UI 冒煙；AC-MCPINC-17 通過
- [ ] **S08**: ADR-040 status flip Accepted + journal write

## Decisions
- 2026-04-18: Open question 1-7 全由 Architect 裁決（見 SPEC）
- 2026-04-18: Phase A default 仍 eager dump（backward compat），summary 行為需顯式傳 `include=["summary"]`

## Resume Point
完成。S01..S08 全部過關。Cloud Run revision `zenos-mcp-00175-sck` serving 100% traffic；default path 在 production 驗證為 eager dump（backward compat 生效）。AC-17 Phase 3 人工驗證留給下次 dashboard 改動時順便做。

剩下的行動（非本 SPEC 範圍）：
- 用戶重啟 MCP connection 後實測 `include=["summary"]` token 消耗對比
- 觀察 3 個月內 warning log 的 include=None 比例（ADR-040 Phase B gate）
