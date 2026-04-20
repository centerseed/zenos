---
spec: SPEC-docs-native-edit-and-helper-ingest.md
td: TD-docs-native-edit-and-helper-ingest.md
created: 2026-04-20
status: in-progress
---

# PLAN: Dashboard 原生文件編輯 + Helper Ingest Contract

## Entry Criteria

- ADR-022 / ADR-032 已升 Accepted（debt 已還，2026-04-20）
- SPEC-docs-native-edit-and-helper-ingest Under Review（PM 階段已交付）
- TD-docs-native-edit-and-helper-ingest 已寫完
- AC test stubs（22 條 P0 Test）已建立、預設 FAIL

## Exit Criteria

- 所有 22 條 P0 AC test 從 FAIL 變 PASS（11 backend / 12 frontend，含 AC-DNH-18 mixed）
- `tests/interface/test_document_delivery_api.py` 9 條 regression 維持 PASS
- 部署後 Dashboard `/docs` 與 `/docs/[docId]` 端到端可用
- SPEC status：Draft → Under Review → Approved
- SPEC-document-bundle exclusions amendment 生效
- journal 寫入

## Tasks

- [ ] **S00**: SPEC-document-bundle exclusions amendment（governance pre-flight）
  - Files: `docs/specs/SPEC-document-bundle.md`
  - Owner: Architect 代行
  - Verify: §明確不包含 已移除 3 條矛盾項目，加入 2026-04-20 amendment note
  - Depends on: 無

- [x] **S01**: Schema + Helper Upsert Backend ✅ 2026-04-20 (task 8dcbc50233ac4470930f10d2820ab20a review)
  - Files:
    - `migrations/20260420_0001_helper_ingest.sql`（新）
    - `src/zenos/domain/source_uri_validator.py`
    - `src/zenos/application/knowledge/source_service.py`
    - `src/zenos/application/knowledge/ontology_service.py`
    - `src/zenos/interface/mcp/write.py`
    - `src/zenos/interface/mcp/source.py`
    - `tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py`
  - Owner: Developer (subagent)
  - Verify:
    - `.venv/bin/pytest tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py -x`（11 條 PASS）
    - `.venv/bin/pytest tests/interface/test_document_delivery_api.py -x`（regression 9 條 PASS）
    - `.venv/bin/pytest tests/application/ -x`（不引入新 FAIL）
  - AC: AC-DNH-05, 06, 08, 09, 10, 11, 12, 13, 14, 17, 18-backend
  - Depends on: S00

- [x] **S02 + S03 合併**: Dashboard 原生編輯 UI + Re-sync UX ✅ 2026-04-20 (task e10af29436b1412484878da33fb3ca60 review). 12/12 frontend AC PASS、build OK、native textarea editor、揭發 backend gap → S01b
- [x] **S01b**: POST /api/docs endpoint ✅ 2026-04-20 (task ffac1594eb41426f9404428f0f68201e review). 12/12 PASS（含 3 個新 test：null base_revision、create entity、missing name 400）
  - Files:
    - `dashboard/src/app/(protected)/docs/page.tsx`（重寫）
    - `dashboard/src/app/(protected)/docs/[docId]/page.tsx`（新）
    - `dashboard/src/features/docs/{DocListSidebar,DocEditor,DocOutline,DocSourceList}.tsx`
    - `dashboard/src/lib/api.ts`
    - `dashboard/src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx`（部分）
  - Owner: Developer (subagent, frontend)
  - Verify:
    - `cd dashboard && npx vitest run src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx`（編輯器 + 列表 AC PASS）
    - `npm run build` 無 TS error
    - 手動 dev server：+新 → 編輯 → 自動儲存（有 base_revision_id）→ Reader 顯示
  - AC: AC-DNH-01, 02-frontend, 03, 04, 07, 20, 21, 22
  - Depends on: S01（共用 schema 與 read_source 升級）

- [x] **S03**: 已併入 S02 完成（見上）
  - Files:
    - `dashboard/src/features/docs/ReSyncPromptDialog.tsx`（新）
    - `dashboard/src/features/docs/DocSourceList.tsx`（與 S02 共享，補 stale badge）
    - 共用 `dashboard/src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx`（補 re-sync AC）
  - Owner: Developer (subagent, frontend)
  - Verify:
    - 上述 vitest 跑 re-sync 部分 PASS
    - 手動：開啟有 stale source 的 doc → 看到黃標 → 點「重新同步」→ prompt 可複製
  - AC: AC-DNH-15, 16, 18-frontend, 19
  - Depends on: S01（用 staleness_hint 欄位）；可與 S02 並行（協調 DocSourceList 不衝突）

- [ ] **S04**: QA 整體驗收 + 部署 + 端到端驗證
  - Owner: QA (subagent) → Architect 監督部署
  - Verify:
    - `pytest tests/ -x` 全過、`vitest` 全過
    - `./scripts/deploy.sh`（dashboard）+ 必要時 `./scripts/deploy_mcp.sh`（backend）
    - 部署後 `curl https://<dashboard>/docs/<docId>` 200，瀏覽器走完 +新 → 編輯 → reload (`base_revision_id` 衝突) → 重新同步流程
    - QA Verdict: PASS
  - Depends on: S02 + S03

## Decisions

- 2026-04-20: 採方案 B（schema 先行）—— S01 sequential，S02+S03 並行 after S01
- 2026-04-20: 還清治理債——ADR-022 / ADR-032 升 Accepted；SPEC-document-bundle / SPEC-document-delivery-layer 留 Draft（UI 工作未交付，由本 plan 完成後一併升 Approved）
- 2026-04-20: zenos_native source.type 新增；URI 用 `/docs/{doc_id}`（同 canonical_path）
- 2026-04-20: snapshot_summary 是 helper 產的**語意摘要**（不是 raw 全文 mirror），10KB 硬上限，超出 → 413 SNAPSHOT_TOO_LARGE reject。理由：對齊 ZenOS「語意索引層、不存內容倉」定位；強迫 helper 做 meaningful compression
- 2026-04-20: Helper upsert 與 Delivery Revision 兩條路徑分離；helper 不切 primary_snapshot_revision_id
- 2026-04-20: S01 migration 原設計 `USING gin (partner_id, sources_json)` 需要 btree_gin extension（未啟用）→ Architect 修為 `GIN(sources_json) only`，partner_id 依賴既有 btree bitmap scan
- 2026-04-20: S01 Developer Completion 自揭 3 個次級風險（try/except 吞錯、dead code `upsert_source_in_sources`、migration 未 live 跑）→ 全部列入 S04 QA checklist

## Resume Point

**進度：**

- ✅ S00（Architect 代行）— SPEC-document-bundle exclusions amendment
- ✅ S01（Developer）— 12/12 backend AC PASS、9/9 delivery regression PASS。Architect 修 migration btree_gin 缺失
- ✅ S02+S03（Developer 合併）— 12/12 frontend AC PASS、build OK、native textarea editor。揭發 POST /api/docs gap
- ✅ S01b（Developer）— POST /api/docs endpoint。12/12 PASS（9 既有 + 3 新含 first-save null base_revision_id、create entity、missing name 400）
- ✅ S04 QA（PASS_WITH_NOTES）— 23/23 P0 AC PASS、pytest 2221/0、vitest 606/0、build OK
- ✅ Deploy（2026-04-20）
  - Migration applied: `20260420_0001_helper_ingest.sql`
  - MCP Cloud Run: revision `zenos-mcp-00195-vgq`, 100% traffic, URL `https://zenos-mcp-s5oifosv3a-de.a.run.app`
  - Dashboard Firebase: `https://zenos-naruvia.web.app` (299 files)
- ✅ Post-deploy smoke: `/docs` 200、MCP 401（auth-guarded running）、新 `POST /api/docs` CORS 204 / unauth 401（端點確認存在）
- ⏳ **E2E UI walkthrough（+新→編輯→Reader）待用戶在瀏覽器實測**

**待 QA 處理的已知次級風險清單**：
1. S01: cross-doc duplicate `try/except` 靜默吞錯（QA 應壞掉 repo 確認 warning 仍出現）
2. S01: dead code `source_service.upsert_source_in_sources`（QA 確認可砍）
3. S01: migration 未 live 跑
4. S01b: canonical_path UPDATE 與 entity upsert 非同 transaction（罕見，但 entity 存在卻 canonical_path=null 會讓 GET /api/docs/{id} 回 null）
5. S02: 4 條 pre-existing test failures（TaskCard ×3、EntityTree ×1，不是本次新引入）
6. S02: deriveScope 永遠回「個人」是 placeholder（不影響 AC-DNH-07）
