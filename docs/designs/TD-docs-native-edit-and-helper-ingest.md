---
type: DESIGN
id: TD-docs-native-edit-and-helper-ingest
status: Draft
ontology_entity: L3 文件治理
spec: SPEC-docs-native-edit-and-helper-ingest
created: 2026-04-20
updated: 2026-04-20
---

# 技術設計：Dashboard 原生文件編輯 + Helper Ingest Contract

## 調查報告

### 已讀文件（附具體發現）

#### Spec / ADR 層
- `docs/specs/SPEC-docs-native-edit-and-helper-ingest.md` — 本 TD 依據 SPEC。P0 4 項 / 22 AC（AC-DNH-01 ~ 22）、P1 4 項 / 6 AC（AC-DNH-23 ~ 28）
- `docs/specs/SPEC-document-bundle.md`（Draft）— 多源聚合、source_id、`read_source(doc_id, source_id?)`、bundle_highlights 已完整定義；§明確不包含 與 governance v2.2 矛盾，本 TD 沿用新 SPEC 的修訂結論
- `docs/specs/SPEC-document-delivery-layer.md`（Draft）— **P0-7 強制 `POST /api/docs/{doc_id}/content` 必帶 `base_revision_id` 做 optimistic concurrency**。本 TD 強制沿用
- `docs/decisions/ADR-022-document-bundle-architecture.md`（升 **Accepted** 2026-04-20）— doc_role / source schema / write 三 mutation / read_source 介面已決
- `docs/decisions/ADR-032-document-delivery-layer-architecture.md`（升 **Accepted** 2026-04-20）— Snapshot / Revision / ShareToken / Permalink 已決
- `docs/plans/PLAN-document-bundle-implementation.md`（done）— ADR-022 Phase 1+2 後端全部已落地

#### Schema 層
- `migrations/20260325_0001_sql_cutover_init.sql:49` — `entities.sources_json jsonb not null default '[]'::jsonb`。**sources 是 JSONB array，新欄位無需 DDL**，只需 application-layer 驗證
- `migrations/20260409_0015_document_bundle.sql` — `entities.doc_role`、`change_summary`、`summary_updated_at` 已加
- `migrations/20260411_0020_document_delivery_layer.sql` — `entities.canonical_path / primary_snapshot_revision_id / last_published_at / delivery_status` + `document_revisions` table + `document_share_tokens` table 全部已建
- `migrations/20260416_0021_document_bundle_highlights.sql` — bundle_highlights 已加

#### 實作層
- `src/zenos/interface/dashboard_api.py:2862-2868` — 全 7 個 delivery endpoints 已實作
- `dashboard_api.py:651-712, 2364-2440` — `expected_base_revision_id` 比對 `current_primary` → 409 `REVISION_CONFLICT` 已實作
- `src/zenos/application/knowledge/source_service.py:30-120` — `read_source` / `read_source_with_recovery` 含 dead link policy
- `src/zenos/interface/mcp/source.py:28-120` — `read_source(doc_id, source_id?)` 含 source_id 選取、`_SETUP_HINTS` mapping
- `src/zenos/interface/mcp/write.py` + `src/zenos/application/knowledge/ontology_service.py` — `add_source` / `update_source` / `remove_source` mutations 已落地
- `src/zenos/domain/source_uri_validator.py:34-138` — 覆蓋 github / notion / gdrive / wiki，其他 type（含 upload）pass-through
- `dashboard/src/app/(protected)/docs/page.tsx`（331 行） — **完全 hardcoded mock**，`DOC_TREE` 寫死、無 fetch / api import
- `dashboard/src/components/MarkdownRenderer.tsx` — 可直接重用作 Reader 渲染元件

#### 測試層
- `tests/interface/test_document_delivery_api.py` — 9/9 PASS（含 `test_save_document_content_requires_base_revision_id` + `test_save_document_content_returns_revision_conflict`）

### 搜尋但未找到
- `external_id` 在 `src/zenos/`：0 結果 → **Helper upsert 是全新需求**
- `last_synced_at` / `external_updated_at` 在 `src/zenos/`：0 結果
- `dashboard/src/app/(protected)/docs/[docId]/page.tsx`：不存在 → **Reader 路由需新建**

### 不確定的事項（已於本 TD 決策解決）
1. ~~SPEC-document-delivery-layer 為何 Draft？~~ → 因為 Reader UI（P0-5）未交付。本工作補上後可升 Approved。
2. ~~`zenos_native` 是否新 source.type？~~ → **決定**：新增 `zenos_native` source.type；URI 格式 `/docs/{doc_id}`（同 canonical_path），讓多 source 並存時 UI 有穩定 badge，且 read_source 可走統一路徑
3. ~~Helper upsert 與 base_revision_id 的協作模型？~~ → **決定**：兩條路徑分離
   - Helper upsert 走 `write(update_source, external_id, snapshot_summary)`，只動 `sources_json` 的該 source row，**不建** `document_revisions`、**不切** `primary_snapshot_revision_id`
   - Dashboard 原生編輯走 `POST /api/docs/{doc_id}/content` with `base_revision_id`，建 revision、切 primary。兩者不互相干擾
4. ~~`canonical_path=/docs/{doc_id}` 但 dashboard 路由不存在？~~ → 確認只是 frontend 缺 wiring，需於 S02 新建

---

## Spec Compliance Matrix

> 一條 AC = 一個 test function。Test file path 是 Spec → 實作的唯一追蹤機制。
> 後端：`tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py`
> 前端：`dashboard/src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx`

| AC ID | Layer | 實作位置（預計） | Test Function | 狀態 |
|-------|-------|-----------------|---------------|------|
| AC-DNH-01 | Frontend | `dashboard/src/app/(protected)/docs/page.tsx` + new hook `useCreateDoc` | `test_ac_dnh_01_new_doc_creates_index_entity_with_zenos_native_source` | STUB |
| AC-DNH-02 | Mixed | `dashboard_api.py:save_document_content`（已實作）+ frontend editor auto-save client | `test_ac_dnh_02_autosave_posts_content_with_base_revision_id` | STUB |
| AC-DNH-03 | Frontend | new `DocOutline` component（client-side markdown AST） | `test_ac_dnh_03_outline_generated_from_markdown_headings` | STUB |
| AC-DNH-04 | Frontend | `docs/page.tsx` → `DocLeftSidebar` grouping logic | `test_ac_dnh_04_doc_list_grouped_pinned_personal_team_project` | STUB |
| AC-DNH-05 | Backend | `src/zenos/application/knowledge/source_service.py:read_source` + new `zenos_native` adapter | `test_ac_dnh_05_read_source_returns_zenos_native_content_from_gcs` | STUB |
| AC-DNH-06 | Backend | `ontology_service.py` archive state transition | `test_ac_dnh_06_archived_doc_hidden_from_default_list` | STUB |
| AC-DNH-07 | Frontend | `DocCenter` header rendering with L2 breadcrumb | `test_ac_dnh_07_editor_header_shows_l2_breadcrumb_and_doctype` | STUB |
| AC-DNH-08 | Backend | `source_service.add_source` + external_id uniqueness | `test_ac_dnh_08_first_helper_push_creates_source_with_external_id` | STUB |
| AC-DNH-09 | Backend | `source_service.add_source / update_source` upsert logic | `test_ac_dnh_09_second_push_same_external_id_updates_existing_source` | STUB |
| AC-DNH-10 | Backend | upsert diff check | `test_ac_dnh_10_unchanged_payload_returns_noop` | STUB |
| AC-DNH-11 | Backend | cross-doc uniqueness detector（warning-only） | `test_ac_dnh_11_duplicate_external_id_across_bundles_returns_warning` | STUB |
| AC-DNH-12 | Backend | `source_service.read_source` → zenos_native / helper snapshot branching | `test_ac_dnh_12_read_source_returns_snapshot_summary_when_present` | STUB |
| AC-DNH-13 | Backend | `read_source` setup_hint branch | `test_ac_dnh_13_read_source_returns_unavailable_with_setup_hint` | STUB |
| AC-DNH-14 | Backend | external_id format validator | `test_ac_dnh_14_invalid_external_id_format_rejected_400` | STUB |
| AC-DNH-14a | Backend | snapshot_summary size check (≤10KB) | `test_ac_dnh_14a_oversized_snapshot_summary_rejected_413` | STUB |
| AC-DNH-15 | Frontend | `DocSourceList` stale badge renderer | `test_ac_dnh_15_source_older_than_14d_shows_stale_badge` | STUB |
| AC-DNH-16 | Frontend | `ReSyncPromptDialog` | `test_ac_dnh_16_resync_button_opens_copyable_helper_prompt` | STUB |
| AC-DNH-17 | Backend | `read_source` 回 `staleness_hint` | `test_ac_dnh_17_read_source_stale_returns_staleness_hint` | STUB |
| AC-DNH-18 | Mixed | helper upsert clears stale | `test_ac_dnh_18_helper_resync_clears_stale_badge` | STUB |
| AC-DNH-19 | Frontend | inverted timestamp warning | `test_ac_dnh_19_inverted_timestamps_display_warning` | STUB |
| AC-DNH-20 | Frontend | mixed source badges in `DocSourceList` | `test_ac_dnh_20_mixed_source_types_render_correct_badges` | STUB |
| AC-DNH-21 | Frontend | router navigate internal for zenos_native | `test_ac_dnh_21_zenos_native_source_opens_in_dashboard_reader` | STUB |
| AC-DNH-22 | Frontend | `target="_blank"` for external types | `test_ac_dnh_22_external_source_opens_new_tab` | STUB |
| AC-DNH-23 | P1 Manual | 不產 auto test（參考實作） | — | — |
| AC-DNH-24 ~ 28 | P1 Frontend | 延後至 P1 排程 | — | — |

**P0 Test 覆蓋：22 / 22（100%）。P1 stub 先不產，等用戶確認 P0 通過再開。**

---

## Component 架構

```
┌─────────────────── Dashboard (Next.js) ───────────────────┐
│                                                             │
│  /docs                       /docs/[docId]                  │
│    DocsPage                    DocReaderPage                │
│    ├─ DocLeftSidebar           ├─ DocHeader (breadcrumb)   │
│    │   └─ (fetch group list)   ├─ MarkdownRenderer (exist) │
│    ├─ DocCenter (editor)       ├─ DocOutline (auto)        │
│    │   ├─ ProseMirror/tiptap   └─ DocSourceList            │
│    │   └─ useAutoSave          (reuses /docs/[docId]/content)│
│    │       └─ POST /api/docs/{id}/content (base_revision_id)│
│    └─ DocRightRail                                          │
│        ├─ DocOutline (auto)                                 │
│        ├─ AgentSuggestions (ref SPEC-dashboard-ai-rail)    │
│        ├─ DocSourceList     ← stale badge (P0-3)           │
│        └─ ReSyncPromptDialog ← P0-3                         │
│                                                             │
└──────────────────── ZenOS Dashboard API ──────────────────┘
       │  (existing, 7 endpoints for delivery)
       ▼
┌─────────────────── ZenOS Backend (Python) ────────────────┐
│                                                             │
│  interface/dashboard_api.py    interface/mcp/{source,write}│
│  ├─ GET  /api/docs/{id}        ├─ write(add_source)        │
│  ├─ GET  /api/docs/{id}/content├─ write(update_source) ← 擴│
│  ├─ POST /api/docs/{id}/content│   └─ external_id upsert   │
│  ├─ POST /api/docs/{id}/publish├─ write(remove_source)     │
│  ├─ PATCH/api/docs/{id}/access └─ read_source(id,src_id?) ←│
│  ├─ POST /api/docs/{id}/share-links  └─ staleness_hint    │
│  └─ DELETE /api/docs/share-links/{token}                   │
│                                                             │
│  application/knowledge/                                     │
│  ├─ ontology_service.py        ← archive transition (AC-06)│
│  ├─ source_service.py          ← upsert + snapshot branch  │
│  └─ source_uri_validator.py    ← + zenos_native / local    │
│                                  + external_id format check│
│                                                             │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────── Postgres (zenos) ───────────────────┐
│  entities (sources_json JSONB)  document_revisions         │
│  + canonical_path               document_share_tokens      │
│  + primary_snapshot_revision_id                             │
│  + delivery_status                                          │
│                                                             │
│  sources_json[] 新 JSON keys（無 DDL）：                    │
│    external_id / external_updated_at /                     │
│    last_synced_at / snapshot_summary                       │
└─────────────────────────────────────────────────────────────┘

┌────────────────── GCS (private buckets) ──────────────────┐
│  GCS_DOCUMENTS_BUCKET:                                      │
│    docs/{doc_id}/revisions/{revision_id}.md (native only)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 介面合約清單

### 新／擴展 MCP `write(collection="documents")` payloads

| Payload key | 型別 | 必填 | 說明 |
|------------|------|------|------|
| `add_source.external_id` | string? | no | `^[a-z_]+:[A-Za-z0-9_\-./]+$`；同 doc unique |
| `add_source.external_updated_at` | ISO-8601? | no | helper 從外部系統取得的該 source 原文最後修改時間 |
| `add_source.snapshot_summary` | text? | no | **max 10KB**；helper 在外部 LLM 產出的**語意摘要**（不是 raw 全文 mirror）；agent 直接消費 |
| `update_source.external_id` | string? | no | 若傳入 → upsert by external_id（match → update; no match → error，必須用 add_source） |
| `update_source.external_updated_at` | ISO-8601? | no | 同上 |
| `update_source.snapshot_summary` | text? | no | 同上；傳 `null` 可清空 |

新/擴展語意：
- `add_source` 含 `external_id` 且同 doc 已有同 external_id → **update**（同 source_id 保留）
- `add_source` 含 `external_id` 且跨 doc 已有同 external_id → 成功但 response `warnings=[{code:"DUPLICATE_EXTERNAL_ID_ACROSS_BUNDLES", ...}]`
- `update_source` 含 `external_id` 但該 doc 找不到 matching source → 400 + 建議改用 `add_source`
- Every successful upsert → server 自動設 `last_synced_at = now()`
- 若 `external_updated_at` 與既存值相同且 `snapshot_summary` 未變 → response 含 `data.noop=true`

### 新 `source.type`

| type | URI 格式 | 驗證 | reader adapter |
|------|---------|------|---------------|
| `zenos_native` | `/docs/{doc_id}` | regex `^/docs/[a-zA-Z0-9_\-]+$` | 讀 `primary_snapshot_revision_id` 對應的 GCS object |
| `local` | `local:{sha256_hex}` | regex `^local:[a-f0-9]{64}$` | 讀 `snapshot_summary` inline（無外部 uri） |

### `read_source(doc_id, source_id?)` 擴展回傳

現有：`content` / `error` / `source_status` / `setup_hint`。
新增欄位：

| 欄位 | 型別 | 出現條件 |
|------|------|---------|
| `staleness_hint` | object? | 當 `last_synced_at` 超過閾值，或 `external_updated_at > last_synced_at` |
| `staleness_hint.reason` | `"outdated" \| "inverted_timestamps"` | — |
| `staleness_hint.suggested_helper_prompt` | string | 給 agent 可直接轉述給用戶 |

### Dashboard 端現有 API（**不需要新增，直接使用**）

- `POST /api/docs/{doc_id}/content`（帶 `base_revision_id`，409 on conflict）— AC-DNH-02 依據；本 endpoint 已支援 `base_revision_id=null` 的首次寫
- `GET /api/docs/{doc_id}` / `GET /api/docs/{doc_id}/content`
- `POST /api/docs/{doc_id}/publish`
- 其他 share-link / access endpoints — 本 TD 暫不碰

### Dashboard 端**新增** API（2026-04-20 amendment — S01b）

S02 落地後 Architect 發現 gap：AC-DNH-01「+新」需要先建 doc entity，但既有 `dashboard_api.py` 只提供 `GET /api/data/entities*`，沒有 entity 建立 endpoint。新增：

| Method | Path | Body | Returns | 行為 |
|--------|------|------|---------|------|
| POST | `/api/docs` | `{name: str, doc_role?: "index"\|"single"=index, status?: str=draft, product_id?: str}` | `{doc_id, base_revision_id: null, entity}` | 建 type=document level=3 entity；UUID 為 doc_id；自動加 primary `source.type=zenos_native, uri=/docs/{doc_id}`；**不**建初始 revision（首次 `POST /content` with `base_revision_id=null` 才建 rev-1）|

S01b 任務在現有 plan 下追加，由同一 backend Developer 補。

---

## DB Schema 變更

### Migration `migrations/20260420_0001_helper_ingest.sql`

```sql
-- SPEC-docs-native-edit-and-helper-ingest
-- Phase 1: Helper Ingest Contract + zenos_native source type
--
-- Notes:
--   sources is JSONB array on entities.sources_json. New per-source JSON keys
--   (external_id / external_updated_at / last_synced_at / snapshot_summary)
--   do NOT require DDL. Validation + uniqueness enforced in application layer.
--
-- This migration adds ONLY:
--   1. Partial expression index on (partner_id, external_id) for cross-doc
--      duplicate detection query performance.
--   2. No constraints (we use warnings, not rejections, for cross-doc duplicates).

BEGIN;

SET search_path TO zenos, public;

-- Optional performance index; queries of form:
--   SELECT id FROM entities
--   WHERE partner_id = $1 AND sources_json @> jsonb_build_array(jsonb_build_object('external_id', $2));
-- benefit from this expression index.
CREATE INDEX IF NOT EXISTS idx_entities_partner_source_external_ids
  ON entities USING gin (
    partner_id,
    (sources_json)
  );

-- Note: snapshot_summary size is enforced in application (reject > 10KB in write handler).
-- Postgres's TOAST handles large JSONB rows but we don't want to balloon them here.

COMMIT;
```

### Schema 層零 DDL change（只新增 GIN index for query）。所有新欄位是 JSONB 內 key，由 application 驗證。

---

## 任務拆分

> **策略**：user 選 B — schema + helper upsert 先行（S01），前端 wiring + re-sync UX 並行（S02 & S03）。

### S00: SPEC-document-bundle exclusions amendment（governance 前置）
- **角色**：PM（或 Architect 代行）
- **Files**: `docs/specs/SPEC-document-bundle.md`（§明確不包含 移除「儲存文件內容」「文件編輯器」「檔案託管」三條；加註 amendment 2026-04-20 by SPEC-docs-native-edit-and-helper-ingest）
- **Done**: 修訂生效、journal 記錄

### S01: Schema + Helper Upsert Backend（sequential; 先行）
- **角色**：Developer
- **Files**:
  - `migrations/20260420_0001_helper_ingest.sql`（新）
  - `src/zenos/domain/source_uri_validator.py`（加 zenos_native / local / external_id 驗證）
  - `src/zenos/application/knowledge/source_service.py`（擴 add_source / update_source upsert + snapshot_summary branching）
  - `src/zenos/application/knowledge/ontology_service.py`（upsert coordination + duplicate detection warning）
  - `src/zenos/interface/mcp/write.py`（payload 擴充欄位路由）
  - `src/zenos/interface/mcp/source.py`（read_source 加 staleness_hint）
  - `tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py`（填 AC-DNH-05, 06, 08, 09, 10, 11, 12, 13, 14, 17, 18_backend）
- **Done Criteria**（每條可獨立驗證）：
  - `pytest tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py -x` 12 條 backend test 全 PASS
  - `pytest tests/interface/test_document_delivery_api.py -x` 9 條 regression 全 PASS（保證沒壞既有）
  - `pytest tests/application/ -x` 不引入新 FAIL
  - Migration idempotent（重跑二次不報錯）
  - 以下 AC test 必須從 FAIL 變 PASS：AC-DNH-05, 06, 08, 09, 10, 11, 12, 13, 14, 17, 18（backend）

### S02: Dashboard 原生編輯 UI（frontend; parallel after S01）
- **角色**：Developer（frontend）
- **Files**:
  - `dashboard/src/app/(protected)/docs/page.tsx`（**完全改寫**，砍 DOC_TREE mock，改接真實 API）
  - `dashboard/src/app/(protected)/docs/[docId]/page.tsx`（新建 Reader 路由）
  - `dashboard/src/features/docs/DocListSidebar.tsx`（新）
  - `dashboard/src/features/docs/DocEditor.tsx`（新；editor + auto-save with `base_revision_id`）
  - `dashboard/src/features/docs/DocOutline.tsx`（新；client-side markdown AST）
  - `dashboard/src/features/docs/DocSourceList.tsx`（新；支援 stale badge + resync button）
  - `dashboard/src/lib/api.ts`（加 docs CRUD hooks）
  - `dashboard/src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx`（填前端 AC）
- **Done Criteria**：
  - `npx vitest run dashboard/src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx` 前端 AC 全 PASS
  - `npm run build` 無 TS error
  - 手動跑 dev server 驗證：+新 → 編輯 → 自動儲存 → Reader 顯示、409 衝突時提示 reload
  - 以下 AC test 必須從 FAIL 變 PASS：AC-DNH-01, 02（frontend 部分）, 03, 04, 07, 20, 21, 22

### S03: Re-sync UX + staleness_hint 整合（frontend + thin backend; parallel after S01）
- **角色**：Developer（前後端）
- **Files**:
  - `dashboard/src/features/docs/ReSyncPromptDialog.tsx`（新）
  - `dashboard/src/features/docs/DocSourceList.tsx`（S02 共享；這裡補 stale badge 顯示 + warning）
  - 部分測試可能 overlap S02；Architect 協調避免 merge conflict
- **Done Criteria**：
  - 以下 AC test 必須從 FAIL 變 PASS：AC-DNH-15, 16, 18（frontend 部分）, 19
  - 手動驗證：打開有 stale source 的 doc → 看到黃標 → 點「重新同步」→ prompt 可複製

### S04: QA 整體驗收 + 部署驗證
- **角色**：QA（subagent）
- **Done Criteria**：
  - `pytest tests/ -x` 全過
  - `npx vitest run` 全過
  - 部署後 `curl https://<dashboard>/docs/<doc_id>` 200 + 實際 UI 驗證
  - 所有 22 P0 AC 從 FAIL 變 PASS 記錄

---

## Done Criteria（整體）

1. ✅ S01 所有 backend AC test 從 FAIL 變 PASS
2. ✅ S02 所有 frontend AC test 從 FAIL 變 PASS
3. ✅ S03 所有 re-sync AC test 從 FAIL 變 PASS
4. ✅ `tests/interface/test_document_delivery_api.py` 9 條 regression 維持 PASS（未壞既有）
5. ✅ Migration idempotent
6. ✅ 部署後 Dashboard `/docs` 能新建、編輯、Reader `/docs/{doc_id}` 可讀
7. ✅ MCP `write(add_source, external_id="notion:...")` 二次呼叫 = upsert（手動驗證 + test）
8. ✅ SPEC-docs-native-edit-and-helper-ingest status Draft → Under Review → Approved
9. ✅ SPEC-document-bundle exclusions amendment 生效
10. ✅ journal 記錄

---

## Risk Assessment

### 1. 不確定的技術點

- **`zenos_native` source read_source 路徑**：目前 `source_service.read_source` 只走 `_adapter.read_content(uri)` 分支（GitHub adapter）。新 type 需要新 adapter 路由「讀 entity.primary_snapshot_revision_id → GCS object」。Architect 建議採 strategy pattern，不在 `read_source` 主方法塞 if-else
- **`snapshot_summary` 10KB 上限**：application-layer 檢查 byte length。超出時 **reject with 413 SNAPSHOT_TOO_LARGE**，不截斷。理由：snapshot_summary 是**語意摘要紀律**（helper 必須做 meaningful compression），不是技術防爆——10KB ≈ 2.5K tokens，足夠表達一份文件的 TLDR + 關鍵段落 + headings。截斷會讓 helper 不自覺地「以為塞進去了」結果 agent 拿到半截語意。
- **external_id 跨 doc duplicate 的 GIN index**：寫的 migration 用 `(partner_id, sources_json)` GIN index。**[未確認]** 查詢效能是否需要 JSON path index；先用 GIN，Developer 實測後可調整

### 2. 替代方案與選擇理由

| 決策點 | 選項 | 選擇 | 理由 |
|-------|------|------|------|
| zenos_native 表達 | A. 新 source.type / B. 只用 entity-level delivery metadata | **A** | 多 source 並存時 UI 需要穩定 badge；read_source 路徑統一 |
| snapshot_summary 存儲 | A. inline JSONB / B. 獨立 table / C. GCS bucket | **A** | summary ≤10KB 適合 inline；大於 10KB **不是技術防爆，是語意紀律 reject**——helper 沒做 compression |
| snapshot_summary 語意 | A. raw 全文快取 / B. helper 產的語意摘要 | **B** | 對齊 ZenOS「語意索引層、不存內容倉」定位；helper 強迫 distill = 推給對的層做對的事 |
| Helper upsert 與 Delivery Revision | A. 共用 primary_snapshot / B. 雙路徑分離 | **B** | Helper = metadata-only；Delivery = authored content；共用會讓治理語意混淆 |
| 派工順序 | A. 三條並行 / B. schema 先行 / C. 小步走 helper 先 | **B**（用戶選） | schema 是共用 dependency；並行前先鎖基礎 |
| Migration 範圍 | A. 加 4 個 column / B. JSONB key-only | **B** | sources 本來就是 JSONB array，新增 key 零 DDL；只加 1 個查詢 index |

### 3. 需要用戶確認的決策

以下在 Phase 1.5 Gate 呈現用戶確認（完成後才 dispatch S01）：

1. **zenos_native URI 格式**：`/docs/{doc_id}`（同 canonical_path）—— 或用 `zenos://docs/{doc_id}` scheme？建議前者，URL-safe 且 Dashboard route 可直接用
2. ~~snapshot_summary 10KB 上限~~ → **已決議**：10KB hard reject (413 SNAPSHOT_TOO_LARGE)；snapshot_summary 是語意摘要不是 raw mirror，helper 必須做 compression
3. **S00 governance amendment 由誰做**：Architect 代 PM 直接改 SPEC-document-bundle exclusions（小改動），還是呼 PM subagent？建議 Architect 代行（純治理文字修訂，無產品決策）
4. **P1 AC-DNH-23~28 延後排程**：不進 Phase 1 的 Done Criteria；用戶同意延後嗎？

### 4. 最壞情況與修正成本

| 情境 | 發生機率 | 修正成本 | 緩解 |
|-----|---------|---------|------|
| zenos_native reader adapter 沒接上 → Reader 白屏 | 中 | S02 後端回滾 1–2h | E2E test 必跑；先做 `read_source(zenos_native)` python test 再動前端 |
| Helper upsert 兩次寫入 race → 創出雙 source | 低 | 補 application-layer lock，1h | 用 `SELECT FOR UPDATE` on entity row in transaction |
| base_revision_id 衝突時前端未正確重載 → 用戶改的內容消失 | 中 | 補 UX，4h | S02 必須做衝突時的 reload dialog，不能靜默吞掉 |
| JSONB external_id 查詢效能隨 source 增多變慢 | 低 | 加真正的 expression index，2h | 監測 `EXPLAIN ANALYZE`；SMB dogfood 量級不會先遇到 |
| 現有 `test_document_delivery_api.py` 被動壞 | 低 | 立刻 revert，<1h | S01 必須 regression 9 條綠 |

---

## Spec Compliance Files

- **Backend AC stubs**: `tests/spec_compliance/test_docs_native_edit_and_helper_ingest_ac.py`
- **Frontend AC stubs**: `dashboard/src/__tests__/docs_native_edit_and_helper_ingest_ac.test.tsx`
- **PLAN**: `docs/plans/PLAN-docs-native-edit-and-helper-ingest.md`
