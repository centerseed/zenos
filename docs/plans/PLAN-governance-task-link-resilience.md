---
spec: SPEC-governance-task-link-resilience.md
created: 2026-05-01
status: done
entry_criteria: "2026-04-17 to 2026-05-01 MCP API logs identified infer_task_links structured-output failure rate around 59%."
exit_criteria: "AC-GTLR-01 through AC-GTLR-05 pass QA, and QA Verdict is PASS."
---

# PLAN: Governance task link inference resilience

## Tasks

- [x] S01: Implement chunked infer_task_links with fallback and audit summary
  - Files: `src/zenos/application/knowledge/governance_ai.py`, `tests/spec_compliance/test_governance_task_link_resilience_ac.py`, `tests/application/test_governance_ai_context.py`
  - Verify: `.venv/bin/pytest tests/spec_compliance/test_governance_task_link_resilience_ac.py tests/application/test_governance_ai_context.py -q`
- [x] S02: QA acceptance for AC-GTLR-01 through AC-GTLR-05
  - Files: QA reads `docs/specs/SPEC-governance-task-link-resilience.md`, `docs/designs/DESIGN-governance-task-link-resilience.md`, `docs/tests/TEST-governance-task-link-resilience.md`
  - Verify: QA Verdict PASS

## Decisions

- 2026-05-01: Second incident fix targets #1 because `infer_task_links` failure rate directly damages task↔entity graph quality.
- 2026-05-01: Keep external task API unchanged; implement resilience inside `GovernanceAI.infer_task_links`.
- 2026-05-01: MCP Plan `97bca05903a34030bf3d31490d4f712d` and task `2b1fadeeaffc4af2bcbe974486c15f35` created; task handed off to `agent:developer`.
- 2026-05-01: Architect rejected first completion because fallback only handled ASCII token overlap; Developer added CJK n-gram fallback regression and reran tests.
- 2026-05-01: S01 accepted for QA after Architect reran `.venv/bin/pytest tests/spec_compliance/test_governance_task_link_resilience_ac.py tests/application/test_governance_ai_context.py -q` → 15 passed, 13 warnings.
- 2026-05-01: QA failed CJK fallback due single-character substring over-link (`金` matching `金流`); Developer added `_is_single_cjk` guard and regression.
- 2026-05-01: Re-QA PASS; task confirmed done and MCP Plan marked completed. Final verification: 16 tests passed, 14 warnings.

## Resume Point

Done. External review package prepared in Architect final response. No deploy performed.
