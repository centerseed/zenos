---
spec: ADR-030-mcp-authorization-hardening.md
created: 2026-04-10
status: done
---

# PLAN: MCP Authorization Hardening

## Tasks

- [x] S01: 收斂 workspace contract 與 JWT middleware 前置驗證 (2026-04-10, PASS)
  - Files: `src/zenos/application/identity/workspace_context.py`, `src/zenos/interface/mcp/_auth.py`, `tests/application/test_workspace_context.py`, `tests/interface/test_api_key_auth.py`, `tests/interface/test_workspace_tools.py`
  - Verify: `.venv/bin/pytest tests/application/test_workspace_context.py tests/interface/test_api_key_auth.py tests/interface/test_workspace_tools.py -x`

- [x] S02: 補齊 JWT credential integration 與 workspace authorization matrix (2026-04-10, PASS)
  - Files: `tests/interface/test_mcp_jwt_auth.py`, `tests/interface/test_mcp_workspace_authorization_matrix.py`
  - Verify: `.venv/bin/pytest tests/interface/test_mcp_jwt_auth.py tests/interface/test_mcp_workspace_authorization_matrix.py -x`

- [x] S03: 補齊 guest mutation contract 與 cross-surface consistency 測試 (2026-04-10, PASS)
  - Files: `tests/interface/test_mcp_guest_mutation_contract.py`, `tests/interface/test_permission_isolation.py`, `tests/interface/test_dashboard_api.py`
  - Verify: `.venv/bin/pytest tests/interface/test_mcp_guest_mutation_contract.py tests/interface/test_permission_isolation.py tests/interface/test_dashboard_api.py -x`

- [x] S04: QA 驗收 ADR-030 實作 (2026-04-10, PASS)
  - Files: 測試與驗收為主，不預設產品 code 變更
  - Verify: `.venv/bin/pytest tests/application/test_workspace_context.py tests/interface/test_api_key_auth.py tests/interface/test_workspace_tools.py tests/interface/test_mcp_jwt_auth.py tests/interface/test_mcp_workspace_authorization_matrix.py tests/interface/test_mcp_guest_mutation_contract.py tests/interface/test_permission_isolation.py tests/interface/test_dashboard_api.py -x`

## Decisions

- 2026-04-10: 本輪以 `ADR-030` 作為實作與驗收依據；若和既有測試假設衝突，以 `SPEC-identity-and-access`、`ADR-024`、`ADR-029` 的正式契約為準。
- 2026-04-10: 優先補真正的 middleware/tool integration 測試，不再把新增案例堆進 `test_permission_isolation.py`。
- 2026-04-10: QA 驗收要以 principal 視角驗證 home/shared workspace 切換，不接受只靠單 workspace fixture 的 coverage 宣稱。
- 2026-04-10: `_apply_workspace_override()` 必須保留 raw authenticated partner，否則從 home projection 切回 shared workspace 會丟失 guest/member 視角。
- 2026-04-10: delegated JWT 的 `workspace_ids` 限制不只要擋 header path，也要擋 tool-level `workspace_id` override path。

## Resume Point

已完成。Developer 補齊 JWT integration、workspace authorization matrix、guest mutation contract 與 cross-surface consistency 測試；QA Verdict = PASS。後續若要再提高信心，可補一組 repo-backed guest mutation integration，降低 interface-side mock 比例。
