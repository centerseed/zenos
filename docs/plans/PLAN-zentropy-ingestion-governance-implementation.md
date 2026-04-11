---
spec: SPEC-zentropy-ingestion-contract.md
created: 2026-04-11
status: completed
---

# PLAN: Zentropy Ingestion Governance Implementation

## Tasks
- [x] S01: 實作 ext ingestion API 介面層（4 endpoints + scope/workspace gate）
  - Files: `src/zenos/interface/ext_ingestion_api.py`, `src/zenos/interface/mcp/__main__.py`
  - Verify: `pytest tests/interface/test_ext_ingestion_api.py -q`
- [x] S02: 實作 ingestion application services（ingest/distill/commit/review queue）
  - Files: `src/zenos/application/ingestion/*.py`
- [x] S03: commit 收斂 canonical mutation（TaskService + entry path）
  - Files: `src/zenos/interface/ext_ingestion_api.py`, `src/zenos/application/ingestion/service.py`
  - Verify: `pytest tests/application/test_ingestion_service.py -q`
- [x] S04: 新增 ingestion SQL schema 與 repository
  - Files: `migrations/20260411_0021_ext_ingestion_tables.sql`, `src/zenos/infrastructure/ingestion/sql_ingestion_repo.py`
  - Verify: `pytest tests/application/test_ingestion_service.py -q`
- [x] S05: 整合測試（scope、forbidden mutation、e2e flow）
  - Files: `tests/interface/test_ext_ingestion_api.py`, `tests/application/test_ingestion_service.py`
  - Verify: `pytest tests/application/test_ingestion_service.py tests/interface/test_ext_ingestion_api.py tests/interface/test_mcp_jwt_auth.py -q`
- [x] S06: 文件與 ontology 同步（TD 註冊、跨 L2 關聯、spec compliance evidence）
  - Files: `docs/designs/TD-zentropy-ingestion-governance-implementation.md`, `docs/specs/SPEC-zentropy-ingestion-contract.md`, `docs/decisions/ADR-031-zentropy-ingestion-governance-boundary.md`
  - Verify: `mcp get/search evidence`

## Decisions
- 2026-04-11: 採用「Ingestion Facade API + Core Governance API」雙層模型，commit 僅可透過 canonical mutation path（依 ADR-031）。
- 2026-04-11: scope gate 採 candidate-type 檢查（task candidates 需 `task`; entry candidates 需 `write`; mixed 需兩者）。

## Resume Point
Plan 已完成（id: `3392c25502ce40eb81a9a34ebda550a9`）。下一步：若要進入 v1.1，可補 `commit atomic=true` 的 transaction rollback 策略與 integration 測試。
