---
spec: SPEC-document-bundle.md
created: 2026-04-09
status: done
---

# PLAN: Document Bundle 實作

## Tasks

- [x] S01: 收斂 ADR-022 Phase 1 已落地但不一致的實作
  - Files: `src/zenos/application/ontology_service.py`, `src/zenos/application/source_service.py`, `src/zenos/interface/tools.py`, `src/zenos/infrastructure/sql_repo.py`, `tests/application/test_document_bundle.py`, `tests/application/test_source_service.py`, `tests/interface/test_read_source_selection.py`
  - Verify: `.venv/bin/pytest tests/application/test_document_bundle.py tests/application/test_source_service.py tests/interface/test_read_source_selection.py -x`

- [x] S02: 補齊 ADR-022 Phase 2 契約缺口
  - Files: `src/zenos/application/source_service.py`, `src/zenos/application/ontology_service.py`, `src/zenos/interface/tools.py`, `src/zenos/domain/search.py`, `tests/application/test_adr022_review_fixes.py`, `tests/interface/test_tools.py`
  - Verify: `.venv/bin/pytest tests/application/test_adr022_review_fixes.py tests/interface/test_tools.py -x`

- [x] S03: QA 驗收 ADR-022 實作
  - Files: 測試與驗收為主，不預設產品 code 變更
  - Verify: `.venv/bin/pytest tests/ -x`

## Decisions

- 2026-04-09: 不把 ADR-022 視為全新功能。先收斂既有半完成實作，再補 Phase 2 缺口，避免重複改動與測試漂移。
- 2026-04-09: migration 以 `migrations/20260409_0015_document_bundle.sql` 為準，不沿用舊 task 文案中的 `scripts/migrations/` 路徑。
- 2026-04-09: `source_status` 與 JSON payload 內既有 `status` 命名存在落差，先以契約一致性為驗收重點，若需全面 rename 另立後續整理票。
- 2026-04-09: S01 以最小修改完成。實作層已有 `status/source_status` alias 讀寫 helper；本輪補的是回歸測試，正式固定 tool selection 與 recovery 對 alias 的相容行為。
- 2026-04-09: S02 經既有 ADR-022 review-fix 測試與 tool 測試驗證，可視為已落地；本輪未再補產品 code，主要是確認現有契約已通過測試。
- 2026-04-09: S03 完成。Firestore Naruvia E2E 改為在缺少 emulator / credentials / opt-in 時快速 skip，避免外部環境未滿足時卡死整體 QA gate。

## Resume Point

全部完成。ADR-022 repo 層實作已通過對應測試與全套 QA gate；若要做真實 Naruvia Firestore E2E，需先設好 `FIRESTORE_EMULATOR_HOST`、`GOOGLE_APPLICATION_CREDENTIALS`，或顯式 `RUN_FIRESTORE_E2E=1`。
