---
spec: SPEC-mcp-id-ergonomics.md
td: TD-mcp-id-ergonomics.md
created: 2026-04-20
status: done
---

# PLAN: MCP ID Ergonomics & Dogfood Reject-Rate Metric

## Entry Criteria

- SPEC-mcp-id-ergonomics AC-MIDE-01..08 已定稿
- TD-mcp-id-ergonomics Compliance Matrix 填完
- AC test stubs 已產出

## Exit Criteria

- 所有 AC test PASS（`.venv/bin/pytest tests/spec_compliance/test_mcp_id_ergonomics_ac.py -x`）
- 全測試套無 regression
- scanner 可對現有 `~/.claude/projects/*/*.jsonl` 跑出正確統計
- 部署後 smoke 驗證新 error msg 與 id_prefix 端到端可用
- journal 寫完總結

## Tasks

- [x] **S01**: `_common.py` helper + 全部 not-found 端點升級 ✓ developer done，待 QA
  - Files: `src/zenos/interface/mcp/_common.py`, `write.py`, `get.py`, `analyze.py`, `source.py`, `attachment.py`
  - AC 覆蓋: AC-MIDE-01, AC-MIDE-02
  - Verify: `.venv/bin/pytest tests/spec_compliance/test_mcp_id_ergonomics_ac.py::test_ac_mide_01 tests/spec_compliance/test_mcp_id_ergonomics_ac.py::test_ac_mide_02 -x`

- [x] **S02**: Repo `find_by_id_prefix` + get/search `id_prefix` 參數 + write 類拒絕 id_prefix ✓ developer done，待 QA
  - Files: `src/zenos/infrastructure/knowledge/{sql_entity_repo,sql_entity_entry_repo,sql_task_repo,sql_document_repo,sql_blindspot_repo}.py`, `src/zenos/interface/mcp/{get,search,write,confirm,task}.py`
  - AC 覆蓋: AC-MIDE-03, AC-MIDE-04, AC-MIDE-05
  - Verify: AC-MIDE-03/04/05 對應 test PASS

- [x] **S03**: Dogfood reject-rate scanner ✓ done（AC-MIDE-06 PASS）
  - Files: `scripts/dogfood/scan_mcp_reject_rate.py`, `tests/spec_compliance/test_mcp_id_ergonomics_ac.py`（scanner test）
  - AC 覆蓋: AC-MIDE-06
  - Verify: `python3 scripts/dogfood/scan_mcp_reject_rate.py --since 7d --transcripts-dir tests/fixtures/transcripts/ --format json`

- [x] **S04**: Dogfood workflow gate + agent skills ID 紀律 + S01/S02 minor fixes ✓ done
- [x] **S05**: EntityEntryRepository Protocol + scanner `--since` + `same_input_retries` ✓ done
  - Files: `skills/workflows/dogfood.md`, `skills/release/{pm,architect,developer,qa,coach}/SKILL.md`, run `scripts/sync_skills_from_release.py`
  - AC 覆蓋: AC-MIDE-07, AC-MIDE-08
  - Verify: grep test 確認文字段落存在

## Decisions

- 2026-04-20: write/confirm/handoff 不支援 id_prefix（見 TD Risk Assessment §2，避免破壞性誤觸）
- 2026-04-20: prefix 最小長度 4，候選上限 10（query 11 偵測超量）
- 2026-04-20: not-found 錯誤格式：`{resource} '{id}' not found — {format-hint or search-hint}`

## Resume Point

全部完成。21 AC tests PASS（含 5 個 QA 補的邊界 test），2188 tests 無 regression。
Scanner 對 real transcripts 已跑過：624 sessions / 2307 MCP calls / 9.3% reject rate。

剩餘：
1. 寫 journal
2. 用戶決定 commit / deploy 時機
3. EntityEntryRepository domain Protocol 缺（後續 backlog）
