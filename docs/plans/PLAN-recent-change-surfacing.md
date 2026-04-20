---
spec: SPEC-recent-change-surfacing.md
created: 2026-04-20
status: in-progress
---

# PLAN: Recent Change Surfacing

## Tasks
- [ ] S01: 補 workflow recent-change 寫入規則
  - Files: `skills/workflows/knowledge-capture.md`, `skills/workflows/knowledge-sync.md`
  - Verify: `pytest tests/spec_compliance/test_recent_change_surfacing_ac.py -q`
- [ ] S02: 新增 MCP `recent_updates` tool 與 aggregation contract
  - Files: `src/zenos/interface/mcp/recent_updates.py`, `src/zenos/interface/mcp/__init__.py`
  - Verify: `pytest tests/spec_compliance/test_recent_change_surfacing_ac.py -q`
- [ ] S03: 補 spec compliance tests / validator gaps
  - Files: `tests/spec_compliance/test_recent_change_surfacing_ac.py`, relevant validator/query files
  - Verify: `pytest tests/spec_compliance/test_recent_change_surfacing_ac.py -q`

## Decisions
- 2026-04-20: recent changes 查詢採新 MCP tool `recent_updates`，不塞進既有 `search(mode=...)`。
- 2026-04-20: dashboard feed 不納入本輪派工，先完成 workflow + MCP contract。

## Resume Point
已完成調查與 TD。下一步：建 Architect plan/task，dispatch S01~S03 給 Developer。
