---
spec: SPEC-docs-native-edit-and-helper-ingest.md
created: 2026-04-27
status: in-progress
---

# PLAN: MCP `write(collection="documents")` 加 `initial_content`

## 背景

SPEC-docs-native-edit-and-helper-ingest 新增 P0-5：MCP `write(collection="documents")` 接受 `initial_content` 參數，server 端建 doc entity 同時把 markdown 寫進 GCS revision，讓 zenos-capture skill / Helper / 任何 MCP caller 一次呼叫完成 entity 建立 + 內容 ingestion。

解決今天的 UX 缺口：MCP agent 沒有路徑把 markdown 寫進 GCS（只有 dashboard frontend 可以 POST `/api/docs/{doc_id}/content`），導致 zenos-capture 對 local md 檔只能用 `local` source + ≤10KB `snapshot_summary`，「Dashboard 點進去看不到完整內容」。

## Entry / Exit Criteria

- **Entry**：SPEC P0-5 已寫入、AC-DNH-29~33 已加入 SPEC、AC test stub 已生成於 `tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py`
- **Exit**：
  - AC-DNH-29 ~ AC-DNH-33 全部從 `FAIL` 變 `PASS`
  - 既有 AC-DNH-01 ~ AC-DNH-28 backend tests 不退化（`pytest tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py -v` 全綠）
  - QA Verdict = PASS
  - Architect 對 5 條 AC 逐條 sign-off

## Tasks

- [ ] **S01**：抽出 GCS write helper（從 `_publish_document_snapshot_internal` 分離出 `_write_native_snapshot(doc_id, content, partner_id)`，不依賴 GitHub adapter）
  - Files: `src/zenos/interface/dashboard_api.py`（重構抽 helper）
  - Verify: 既有 AC-DNH-02 / AC-DNH-05 GCS publish 路徑不退化

- [ ] **S02**：在 `write.py` 的 `documents` collection 加 `initial_content` 處理
  - Files: `src/zenos/interface/mcp/write.py`、`src/zenos/application/knowledge/ontology_service.py`（upsert_document 加 initial_content 流程）
  - 行為：
    - create + initial_content → 建 doc entity，自動加 zenos_native source（is_primary=true），呼叫 `_write_native_snapshot` 寫 GCS revision
    - create + initial_content + sources → reject 400 `INITIAL_CONTENT_REQUIRES_NO_SOURCES`
    - initial_content > 1MB → reject 413 `INITIAL_CONTENT_TOO_LARGE`
    - update + initial_content → reject 400 `INITIAL_CONTENT_CREATE_ONLY`
  - Verify: AC-DNH-29 ~ AC-DNH-33 PASS

- [ ] **S03**：write tool docstring 補上 `initial_content` 說明 + governance_rules.py["document"] 同步更新（SSOT 紀律）
  - Files: `src/zenos/interface/mcp/write.py` docstring、`src/zenos/interface/governance_rules.py`
  - Verify: `governance_guide(topic="document")` 回傳含 initial_content 段落

- [ ] **S04**：跑完整 backend test 確認沒退化
  - Verify: `.venv/bin/pytest tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py -v`

## Decisions

- 2026-04-27: `initial_content` **只支援 create**（新 doc）。Update 內容請走既有 `POST /api/docs/{doc_id}/content`，避免兩條路徑重複實作 revision conflict 邏輯
- 2026-04-27: `initial_content` 與 `sources` **互斥**。要混合外部 source 走後續 `add_source` 加入；避免 primary 衝突
- 2026-04-27: **1 MB 上限**。比 `snapshot_summary` 10 KB 上限大（這是真實 storage，不是摘要），但仍訂上限避免 GCS 濫用

## Risk

1. `_publish_document_snapshot_internal` 重構時不能讓既有 GitHub publish 路徑壞掉 → 抽 helper 函式時保留向後相容
2. GCS write 失敗時 entity 已建立 → 需要 rollback 或標記 delivery_status="error"，先以「先建 entity 再寫 GCS、寫失敗時 entity 不刪但回傳 error」處理
3. `partner_id` / workspace context 在 MCP context 內如何取得 → 看 `_current_partner.get()`

## Resume Point

Developer 交付完成（2026-04-27）：
- S01~S04 全部完成；AC-DNH-29~33 PASS；既有 test 不退化（17 passed in spec_compliance；2633 passed full suite）
- 偏離記錄：URI 兩段式更新（entity create 時無 doc_id → placeholder uri="" → entity 建立後第二次 upsert 補 uri="/docs/{doc_id}"）。Developer 已說明理由與失敗 fallback 行為。

下一步：派 QA 驗收。重點驗證項目：
1. URI 第二次 update 失敗時的 graceful degradation（GCS 內容已存但 source.uri="" → read_source 走 SNAPSHOT_UNAVAILABLE 分支）
2. GCS write 失敗時 entity 建立但 delivery_status=error 的回傳
3. governance_guide(topic="document") 回傳是否包含 initial_content 段（SSOT 紀律）
4. partner_id / workspace context 在 MCP 路徑正確傳遞

## Follow-up（不在本 PLAN）

- **zenos-capture skill 加 git remote 偵測 + 用戶選擇分支**：依賴 P0-5 完成才能整合，另開 PLAN
