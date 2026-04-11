---
type: ADR
id: ADR-032
status: Draft
ontology_entity: L3 文件治理
created: 2026-04-11
updated: 2026-04-11
---

# ADR-032: Document Delivery Layer 架構（Snapshot + Permalink + Share Token）

## Context

`SPEC-document-delivery-layer` 已定義 ZenOS 文件發布層需求，但現況仍有結構缺口：

1. 文件可從 source 讀取（`read_source`），但沒有穩定發布層；分享仍依賴 source URL 與 branch 存活。
2. Dashboard 目前有 Task 附件的 GCS proxy 模式，沒有文件專屬的 revision/snapshot 模型。
3. 權限 runtime 已有 `active workspace + role + visibility`，但文件分享（外部連結）尚無可撤銷 token 機制。
4. 前端已有 Markdown renderer，但沒有 `/docs/{doc_id}` 內建閱讀路由。

目標是讓「編輯」和「發布」分層：
- Google Drive/Git：編輯層
- ZenOS：發布與權限層

## Decision

我們統一採用以下架構決策：

1. **統一為 Snapshot-first Delivery。**  
   文件發布一律改為「source -> snapshot -> permalink」。ZenOS Reader 讀 snapshot，不直接讀 branch URL。

2. **新增 Document Revision 模型。**  
   每次 publish 會建立 revision 記錄（含 `doc_id`、`source_id`、`source_version_ref`、`snapshot_object_path`、`content_hash`）。

3. **新增 Share Token 模型。**  
   外部分享一律使用 ZenOS token（可過期、可撤銷、可次數限制），不暴露 GCS object URL。

4. **Bucket 一律 private，授權在應用層。**  
   GCS 只存 snapshot；所有讀取都經 ZenOS server 驗權或 token gate。

5. **Reader 路由固定 `/docs/{doc_id}`。**  
   `doc_id` 成為穩定分享鍵。source 改名、搬移、branch 刪除不改 permalink。

6. **Delivery 先對齊既有 visibility runtime。**  
   文件可見性直接沿用 `public/restricted/confidential` 與 workspace context；不引入第二套 ACL 引擎。

7. **Phase 1 先支援 Markdown。**  
   先交付 markdown content 與 metadata；WYSIWYG/雙向回寫不在本輪。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| 直接分享 Git/Drive URL | 不需新增後端模型 | branch/source 生命週期直接導致 404；無統一 ACL | 無法滿足穩定 permalink 與跨專案分享 |
| 只做 signed URL，不做 token table | 開發快 | 無撤銷與審計能力；signed URL 不適合長期分享 | 與治理需求衝突 |
| 在 ZenOS 內建完整 editor | 使用者體驗完整 | 範圍過大、與 Drive 重疊、交付風險高 | 不符合「輕量文件系統」定位 |

## Consequences

- 正面：
  - 文件分享從 source URL 轉為穩定 permalink，跨分支/跨來源仍可讀。
  - 權限與分享可被統一審計（token lifecycle + access logs）。
  - 可重用現有 attachment proxy/GCS 能力，加速落地。
  - 前端可快速重用 MarkdownRenderer，縮短 Reader 開發週期。

- 負面：
  - 需要新增 migration（revisions/share tokens + entity delivery 欄位）。
  - publish 流程會增加一次 snapshot 寫入成本。
  - 非 github source 的 publish/read 仍受 adapter 能力限制。

- 後續處理：
  - [未確認] 是否分離 documents bucket 與 attachments bucket。
  - [未確認] 分享過期碼（401 vs 410）最終一致規格。

## Implementation

1. 新增 migration：`entities` delivery 欄位 + `document_revisions` + `document_share_tokens`。
2. 新增 Dashboard API：
   - `POST /api/docs/{doc_id}/publish`
   - `GET /api/docs/{doc_id}`
   - `GET /api/docs/{doc_id}/content`
   - `PATCH /api/docs/{doc_id}/access`
   - `POST /api/docs/{doc_id}/share-links`
   - `DELETE /api/docs/share-links/{token_id}`
   - `GET /s/{token}`
3. 以既有 visibility/workspace runtime 實作文檔讀取授權。
4. 擴充 GCS helper，加入 documents bucket 與 snapshot 讀寫路徑。
5. 前端新增 Reader 路由：
   - `/docs/[docId]`（登入後）
   - `/s/[token]`（分享入口）
6. 補測試：
   - dashboard API 文檔路由 mock tests
   - share token create/revoke/expire 路徑
   - Reader 基本渲染與授權失敗狀態
