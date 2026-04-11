---
type: SPEC
id: SPEC-document-delivery-layer
status: Draft
ontology_entity: L3 文件治理
created: 2026-04-11
updated: 2026-04-11
---

# Feature Spec: ZenOS Document Delivery Layer (Lightweight Doc System)

> Layering note: 本 spec 定義 ZenOS 的「文件發布與閱讀層」，不取代 Google Drive/Git 的重編輯能力。文件編輯面以外部系統為主，ZenOS 提供穩定 permalink、權限控管、跨專案分享與 Markdown 閱讀體驗。

## 1. 背景與問題

目前文件分享主要依賴 Git 路徑與 branch 狀態，造成三個問題：

1. 分享必須等 commit + push + merge，協作節奏被主線流程綁死。
2. 文件只存在非 main branch 時，branch 清理後連結會 404。
3. 某些文件是跨專案共同知識，但 repo 邊界會限制共享與授權模式。

## 2. 目標

1. 提供穩定文件連結（`/docs/{doc_id}`），不受 branch/path 變動影響。
2. 建立 private snapshot 儲存層（GCS），確保來源文件失效時仍可閱讀。
3. 由 ZenOS 應用層統一控管 ACL，不依賴 GCS 公開網址。
4. 提供輕量 Web Reader（Markdown 渲染）與最小管理能力（權限與分享）。
5. 支援跨專案共享同一份文件，不需複製內容。

## 3. 非目標

1. 不在 ZenOS 內重建 Google Drive 等級的多人編輯器。
2. 不做雙向同步回寫（ZenOS -> Drive/Git）作為 v1 需求。
3. 不開放 GCS object public URL 作為正式分享機制。

## 4. 核心定位與邊界

1. **Authoring Layer（外部）**：Google Drive / Git，負責重編輯與協作。
2. **Delivery Layer（ZenOS）**：穩定發布、閱讀、授權、分享、快照追溯。
3. **Storage Layer（GCS private bucket）**：僅存內容快照，不直接暴露公開連結。

原則：

- `source_uri` 是來源參考，不是終端分享入口。
- 對外分享一律使用 ZenOS permalink（`/docs/{doc_id}` 或 share link）。
- GCS 只接受 server account 存取；終端使用者無直接 bucket 權限。

## 5. 需求

### P0-1 穩定 Permalink

- 每份文件必須有永久 `doc_id` 與固定路由 `/docs/{doc_id}`。
- 來源改名、搬移、branch 刪除，不得讓 permalink 失效。
- 若來源不可讀但有 snapshot，Reader 仍可正常載入最近可用版本。

AC:

1. Given `doc_id=SPEC-abc` 已建立且有 snapshot，When Git branch 被刪除，Then `/docs/SPEC-abc` 仍可讀。
2. Given 文件來源 URI 變更，When 更新 source metadata，Then permalink 不變。

### P0-2 私有 Snapshot 儲存

- 文件內容快照存於 GCS private bucket。
- Bucket 必須啟用：
  - Uniform bucket-level access
  - Public access prevention
- 不允許在 DB 保存長效 signed URL。

AC:

1. Given 任一文件 revision，When 檢查 metadata，Then 僅存在 `snapshot_object_path`，不存在永久可公開 URL。
2. Given 未通過 ZenOS API 驗權，When 請求文件內容，Then 不可直接從 GCS 讀取成功。

### P0-3 ACL 由 ZenOS 應用層主控

- 文件可見性採 `public | restricted | confidential`。
- 權限判斷輸入至少包含：`active_workspace`, `workspace_role`, `doc visibility`, `doc grants`。
- 實體內容下載由 ZenOS endpoint 驗權後串流，或發放短效 signed URL（1-5 分鐘）。

AC:

1. Given `visibility=confidential`，When 非 owner/member 請求，Then 回傳 403。
2. Given 使用者在授權 workspace 但不在 doc grants，When 讀取文件，Then 回傳 403。
3. Given 已授權使用者，When 呼叫 download endpoint，Then 可成功取得內容。

### P0-4 Share Link（可撤銷、可過期）

- 支援建立文件分享 token，至少包含：
  - `token_id`
  - `doc_id`
  - `expires_at`
  - `max_access_count`（選填）
  - `revoked_at`（可撤銷）
- token 不可直接映射 GCS object path。

AC:

1. Given token 已過期，When 存取分享連結，Then 回傳 410/401（由 API contract 定義固定碼）。
2. Given token 已撤銷，When 存取分享連結，Then 回傳 401 且不可讀內容。

### P0-5 Web Reader（Markdown 優先）

- 建立 `/docs/{doc_id}` Reader 頁面，預設渲染 Markdown。
- 至少提供：
  - Heading anchor
  - TOC
  - Code block highlight
  - 文件 metadata（來源、更新時間、visibility）
- 權限不足時顯示明確拒絕狀態，不可退化為空白頁。

AC:

1. Given markdown 文件含 `#` 與 code block，When 開啟 Reader，Then 正確渲染 TOC 與 code highlighting。
2. Given 使用者無權限，When 開啟 `/docs/{doc_id}`，Then 顯示拒絕訊息與返回入口。

### P1-1 Reader 內權限管理

- 在 Reader 右側或管理面板提供：
  - visibility 切換
  - workspace/project/role/user grant 編輯
  - share token 建立與撤銷

AC:

1. Given owner 調整 visibility，When 儲存，Then 新規則立即影響後續讀取請求。
2. Given owner 撤銷 share token，When 舊連結再次存取，Then 立即失效。

### P1-2 Edit-in-Source 導向

- Reader 顯示 `Edit in source`，導回 Google Drive/Git 原始位置。
- ZenOS 保持輕量編輯定位，不在 v1 導入完整 WYSIWYG。

AC:

1. Given doc source 是 Google Drive，When 點擊 Edit in source，Then 導向該 Drive 文件。
2. Given doc source 是 GitHub blob，When 點擊 Edit in source，Then 導向對應 blob 頁。

## 6. 資料模型（新增欄位）

在既有 document entity / source model 之上，新增 delivery 欄位：

- `canonical_path`: `/docs/{doc_id}`
- `primary_snapshot_revision_id`: 目前 Reader 預設 revision
- `last_published_at`
- `delivery_status`: `ready | stale | blocked`

新增 revision 記錄（可獨立 table 或 nested collection）：

- `revision_id`
- `doc_id`
- `source_id`（來源追溯）
- `source_version_ref`（例如 git commit SHA / drive revision id）
- `snapshot_object_path`
- `content_hash`
- `render_format`（v1 固定 `markdown`）
- `created_at`
- `created_by`

新增 share token 記錄：

- `token_id`
- `doc_id`
- `scope`（`read`）
- `expires_at`
- `max_access_count`（nullable）
- `used_count`
- `revoked_at`
- `created_by`
- `created_at`

## 7. API Contract（v1）

1. `GET /api/docs/{doc_id}`
   - 回傳文件 metadata + ACL 判斷結果 + Reader 所需 rendering payload。
2. `GET /api/docs/{doc_id}/content`
   - 驗權後回傳 markdown 原文（或 HTML，視前端渲染策略）。
3. `PATCH /api/docs/{doc_id}/access`
   - 更新 visibility 與 grants。
4. `POST /api/docs/{doc_id}/share-links`
   - 建立 share token。
5. `DELETE /api/docs/share-links/{token_id}`
   - 撤銷 token。
6. `GET /s/{token}`
   - 匿名/外部分享入口，經 token 驗證後導到受限 Reader。

## 8. 發布流程（Ingest -> Publish）

1. 從 source 讀取內容（Git/Drive adapter）。
2. 產生 snapshot（寫入 GCS private）。
3. 建立 revision metadata（含 source_version_ref/hash）。
4. 更新 `primary_snapshot_revision_id` 與 `last_published_at`。
5. Reader 路由使用 doc_id 載入最新可用 revision。

若來源讀取失敗：

- 保留最後可用 revision 作為 fallback。
- 將 `delivery_status` 標為 `stale`，並在 Reader 顯示來源同步警告。

## 9. Plan Layer（交付邊界）

- `plan_id`: `plan_document_delivery_layer_v1`
- `goal`: 建立 ZenOS 輕量文件發布層，提供穩定分享與權限控制。
- `owner`: TBD（由 Architect 指派）
- `entry_criteria`:
  - Document bundle source model 已可穩定讀取 `github` 與 `gdrive`。
  - Identity/workspace ACL runtime 已可在 API 層取得判斷結果。
- `exit_criteria`:
  - `/docs/{doc_id}` 可讀 markdown 且通過 ACL
  - share token 可建立、過期、撤銷
  - branch/source 失效時 permalink 仍可讀 fallback snapshot
  - 產生端到端測試證據（含 403 與 token revoke case）

## 10. 與既有 Spec 關係

- `SPEC-document-bundle`: 本 spec 延伸其 multi-source 架構，補上 delivery/reader/sharing contract。
- `SPEC-identity-and-access`: 文件 ACL 語義與 workspace role 邊界以該 spec 為準。
- `SPEC-doc-governance`: 文件分類、狀態、supersede 流程仍沿用，不被本 spec 覆寫。

## 11. 風險與緩解

1. **風險：** 誤把 GCS signed URL 當長期分享連結。  
   **緩解：** 產品層只顯示 permalink/share token URL；signed URL 僅短效內部流程使用。
2. **風險：** ACL 判斷散落前端導致旁路。  
   **緩解：** server 強制授權，前端僅顯示授權後結果。
3. **風險：** snapshot 與來源長期偏離。  
   **緩解：** sync job + `delivery_status` + Reader 警示 + manual republish。

## 12. Open Questions

1. v1 是否需要支援附件（圖片/檔案）在 markdown 中的 proxy rewrite？
2. `confidential` 是否允許 owner 產生一次性外部 share token（break-glass）？
3. `GET /api/docs/{doc_id}/content` 應回 markdown 原文還是 server-side HTML（需統一 XSS 防護策略）？

## 13. Ontology Sync Implications（強制對齊）

本 spec 涉及 L3 文件治理，以下變更不得只改 UI 或 API，必須同步更新 ontology metadata：

1. 文件 `source_uri` 改名/搬移時，必須更新對應 document source（含 `source_status`）。
2. 來源不可達且確認永久失效時，若有 snapshot 可保留 `delivery_status=stale`；若無可用內容則需走 archived 流程。
3. 文件被新版取代時，仍沿用既有 supersede 規範，不得以「新 permalink」取代追溯關係。

## 14. Rollout Phases

### Phase 1（MVP）

1. `/docs/{doc_id}` markdown reader
2. GCS private snapshot 儲存
3. server-side ACL enforcement
4. share token create/revoke/expire

### Phase 1.5

1. Reader 管理面板（visibility + grants）
2. `Edit in source` 導向
3. fallback snapshot 與 stale 提示一致化

### Phase 2

1. revision 比對視圖（diff）
2. fine-grained share policy（一次性 / 次數限制策略完善）
3. Markdown 附件 proxy rewrite（若 Open Question #1 決議需要）
