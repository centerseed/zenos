---
spec: SPEC-mcp-schema-compatibility-resilience.md
created: 2026-05-01
status: done
entry_criteria: "2026-04-17 to 2026-05-01 MCP API logs identified 51 schema mismatch ValidationErrors."
exit_criteria: "AC-MSCR-01 through AC-MSCR-05 pass QA, and QA Verdict is PASS."
---

# PLAN: MCP schema compatibility resilience

## Tasks

- [x] S01: Implement MCP schema compatibility normalizers
  - Files: `src/zenos/interface/mcp/write.py`, `src/zenos/interface/mcp/source.py`, `src/zenos/interface/mcp/task.py`, `src/zenos/interface/mcp/get.py`, `src/zenos/interface/mcp/journal.py`, `skills/release/**`, `tests/spec_compliance/test_mcp_schema_compatibility_resilience_ac.py`
  - Verify: `.venv/bin/pytest tests/spec_compliance/test_mcp_schema_compatibility_resilience_ac.py tests/interface/test_journal_tools.py tests/interface/test_read_source_selection.py -q`
- [x] S02: QA acceptance for AC-MSCR-01 through AC-MSCR-05
  - Verify: QA Verdict PASS

## Decisions

- 2026-05-01: Third incident fix targets #2 because schema mismatch breaks agent workflows even when server behavior is otherwise correct.
- 2026-05-01: Only safe compatibility aliases are accepted; canonical schema remains documented and warnings guide migration.
- 2026-05-01: MCP Plan `be7cc91ee59d4c80b5b35c2d1db3fee5` and task `ee47785b86ad4577b487faba5559d921` created; task handed off to `agent:developer`.
- 2026-05-01: Developer completed S01; Architect reran `.venv/bin/pytest tests/spec_compliance/test_mcp_schema_compatibility_resilience_ac.py tests/interface/test_journal_tools.py tests/interface/test_read_source_selection.py -q` → 33 passed, 20 warnings.
- 2026-05-01: QA failed `read_source(uri=...)` because alias accepted arbitrary URL/path; Developer narrowed parser and added negative tests.
- 2026-05-01: Re-QA PASS; task confirmed done and MCP Plan marked completed. Final verification: 37 passed, 22 warnings.

## Resume Point

Done. External review package prepared in Architect final response. No deploy performed.
