---
type: ADR
id: ADR-046-document-entity-boundary
status: Superseded
ontology_entity: l3-document
created: 2026-04-22
updated: 2026-04-23
accepted_at: 2026-04-23
superseded_by: ADR-048-grand-ontology-refactor
supersede_reason: Document → Entity 收斂決策已完整落地為 SPEC-ontology-architecture v2 §8.1 的 L3DocumentEntity subclass + SPEC-doc-governance canonical
---

> **2026-04-23 Supersede note**：本 ADR 決定的「廢除獨立 Document collection」已於 Grand Refactor 完整落地：`L3DocumentEntity` 是主 SPEC v2 §8.1 的 entity subclass；治理規則見 `SPEC-doc-governance`。

# ADR-046: Document 完全併入 Entity，廢除獨立 Document collection

## Context

ZenOS 同時存在兩套描述「文件」的 model，兩套都是 production 路徑：

**Entity 路徑**（新流程）：
- `entities` table 的 `type='document'` row，`level=3`
- `Entity` dataclass 帶 doc-only 欄位：`doc_role`、`bundle_highlights`、`highlights_updated_at`、`change_summary`、`summary_updated_at`、`sources`
- Dashboard 新建文件走這條：`dashboard_api.py:3043` 註解明寫「Creates a type=document level=3 entity with a primary zenos_native source」、line 3099 直接 `type="document"` 建 entity
- 整個 `dashboard_api.py` 與 `marketing_dashboard_api.py` 用 `entity.type == "document"` 判斷文件
- `recent_updates.py:315`、`policy_suggestion_service.py:69`、`ontology_service.py:1054` 都以 `entity.type == "document"` 為主要判斷

**Document 路徑**（舊流程）：
- `documents` table 獨立存在，含 `title / source_json / tags_json / status / confirmed_by_user`
- `Document` dataclass、`DocumentTags` dataclass、`DocumentRepository`、`SqlDocumentRepository` 一整套
- M2M `document_entities` table 連結到 entities
- `application/knowledge/ontology_service.py:3301` 還在 `await self._documents.upsert(doc)`
- ADR-022 D1 明文「`Document` 保持單一 collection」、D3「`write(collection='documents')` 不新增 MCP tool」——舊路徑被刻意保留為 MCP 對外契約

**問題本質：** 重構從 Document → Entity 的方向已啟動但**停在半路**。新建流程已收斂到 Entity，舊 ingestion / write 路徑仍走 Document。`Entity` dataclass 同時承擔通用 entity 與 doc 專屬欄位（5 個 doc-only field），破壞「base entity 只放共通欄位」的直覺，但 Document 又沒撤——兩套 model 共同負責同一概念。

ADR-022 的「保留 documents collection」是針對 **MCP 對外 collection name**，不是針對 SQL table 結構（D1 反對的是「再開第二種 document_index collection」，不是反對 SQL 收斂）。所以這份 ADR 的邊界是：MCP API 名稱可保留，SQL / domain 模型必須收斂。

## Decision Drivers

- 重構已啟動但未完成，繼續放著只會讓兩套 model 持續分歧
- Dashboard 與多數 application 邏輯已用 `entity.type == 'document'` 為主，事實上的 source of truth 已轉移到 Entity
- ADR-022 的對外契約（`write(collection="documents")`、`read_source(doc_id, source_id?)`）必須保留
- ADR-022 的 source bundle 模型（`doc_role`、`is_primary`、source-aware schema）必須保留
- 重構成本要可控：data migration 必須有清楚的 forward / rollback 路徑

## Decision

### D1. 完成 Document → Entity 收斂，使用既有 Entity 欄位，**不新增 doc_* 欄位**

文件物件統一表達為 `entities` table 的 `type='document'` row。Document 的欄位**全部映射到 Entity 已有的同義欄位**，不在 Entity 上新增 doc-prefixed 欄位（例如 `doc_title / doc_source_json / doc_status` 一律拒絕）——那會把 documents vs entities 的雙軌變成 entity 通用欄位 vs entity doc_* 欄位的雙軌，違反本 ADR 目的。

**欄位對映表（拍板）：**

| Document 欄位 | Entity 對應欄位 | 備註 |
|---|---|---|
| `documents.title` | `entities.name` | 文件標題就是 entity 名稱；同義 |
| `documents.source_json` | `entities.sources_json` | Entity sources 是 list，document 既有 source 對應 sources[0]（is_primary=true）；ADR-022 Phase 1 已是 array 結構 |
| `documents.status` | `entities.status` | `EntityStatus` enum 已含 `current/stale/draft/conflict`，已對齊 `DocumentStatus`，唯一需處理：documents 有 `archived` 值，entities 缺，需擴 enum |
| `documents.tags_json` | `entities.tags_json` | 配合 D4 把 Tags / DocumentTags 合併為單一 `Tags` |
| `documents.confirmed_by_user` | `entities.confirmed_by_user` | 同義 |
| `documents.last_reviewed_at` | `entities.last_reviewed_at` | 同義 |
| `documents.created_at / updated_at` | `entities.created_at / updated_at` | 同義 |

Bundle 相關欄位（`doc_role / bundle_highlights_json / highlights_updated_at / change_summary / summary_updated_at`）**已存在 entities table**（見 `sql_entity_repo.py:28` 的 `_ENTITY_COLS`），這次不變。它們本來就是 entities 的欄位，只是只在 `type='document'` 時有意義——這個半 type-specific 性質維持現狀，這次 ADR 不處理「entity 通用欄位該不該物理隔離 doc-only 欄位」這個更大的議題。

**Status enum 需要 follow-up：** 目前 `EntityStatus` 與 `DocumentStatus` 兩個 enum 部分重疊（current / stale / draft / conflict 兩邊都有，archived 只在 DocumentStatus）。本 ADR 的 D2 backfill 必須先把 `EntityStatus` 加上 `archived`，並在 SQL `chk_entities_status` constraint 補入。

### D2. 廢除 `documents` table、`Document` dataclass、`DocumentRepository`

執行序：

1. **Phase 1（Backfill）**：寫 migration 把 `documents` table 所有 row 遷移到 `entities` table（type='document'）；`document_entities` M2M 關係依 **D3 規則**處理（歷史資料 `parent_id=NULL`、全部寫入 `relationships`）
2. **Phase 2（Code refactor）**：
   - `OntologyService.upsert_document()` 內部改寫到 `EntityRepository.upsert(entity)`
   - `MCP write(collection="documents")` handler 維持對外 API 不變，內部轉派到 entity upsert
   - `SqlDocumentRepository` / `FirestoreDocumentRepository` 標 deprecated，所有 caller 改走 `SqlEntityRepository`
3. **Phase 3（Drop）**：所有 caller 遷移完成後，刪 `documents` table、`document_entities` table、`Document` dataclass、`DocumentTags` dataclass、`DocumentRepository` Protocol、`SqlDocumentRepository` 與 `FirestoreDocumentRepository` 實作

### D3. M2M「文件連到多個 entity」改用 `relationships` 表達；歷史資料的 primary parent 不可恢復

現況：`document_entities` 是 M2M bridge，schema 為 `(document_id, entity_id, partner_id, created_at)` — primary key `(document_id, entity_id)`，**沒有順序欄位**。「`linked_entity_ids` 第一個 = primary parent」是寫入 API 的執行慣例，但寫入後資料就丟失順序，無法事後恢復。

收斂後（區分歷史資料 vs 新寫入）：

**歷史資料 backfill 規則（不可從 document_entities 推 primary parent）：**
- 所有 `document_entities` row → 全部寫入 `relationships` table，`source_entity_id = doc_entity_id`、`target_entity_id = related_entity_id`、`type = 'related_to'`（複用既有 RelationshipType，不新增）
- `entities.parent_id` 對被遷移的 doc entity 一律設為 `NULL`
- **要求**：backfill 後產生的所有 `parent_id IS NULL` 且 `type='document'` 的 entity，必須可被後續治理流程**查詢撈出並補派 primary parent**。具體載體（新表 / 復用 blindspot / 復用 entries / dashboard 視圖）**不在本 ADR 拍板**——這屬於 remediation workflow 設計議題，由獨立 TD 或小 ADR 處理。本 ADR 的責任邊界止於「產生可撈出的待補資料 + 文件化此責任」

**新寫入規則（保留 ADR-022 D3 對外 API 行為）：**
- `MCP write(collection="documents")` API 仍接受 `linked_entity_ids: list[str]`
- Handler 內部規則：`linked_entity_ids[0]` → 寫入 `entities.parent_id`；`linked_entity_ids[1:]` → 寫入 `relationships`
- 對 caller 而言外部行為不變

**不新增 RelationshipType：** 初版 draft 提議新增 `documents` 類型，但複用既有 `related_to` 已能表達「文件記錄關於 entity 的內容」，新增類型只增加 enum 維護成本。如果未來治理流程要區分「記錄關於」vs 「依賴於」，那時再開新類型。

### D4. 合併 `Tags` 與 `DocumentTags`

`Tags` (knowledge/models.py:16) 與 `DocumentTags` (knowledge/models.py:88) 兩個 dataclass 結構幾乎一樣，差別僅在 what/who 的型別寫法（Tags 寫 `list[str] | str`、DocumentTags 寫 `list[str]`）。

收斂為單一 `Tags` dataclass：
- what: `list[str]`（強制 list，舊 `str` 在 read 層自動 wrap）
- why: `str`
- how: `str`
- who: `list[str]`

`DocumentTags` import 全改為 `Tags`，dataclass 定義刪除。

### D5. MCP `write(collection="documents")` 對外契約保留

ADR-022 D3 的 MCP 對外契約完全保留：
- `write(collection="documents")` 仍然是合法 collection name
- 內部實作改為「轉派到 entity upsert，type 強制為 'document'」
- `read_source(doc_id, source_id?)` 對外語意不變
- `batch_update_sources` 對外語意不變

對使用 MCP 的 agent/skill 而言，這次重構是**透明的**——他們繼續用 `write(collection="documents")` 不需要改。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **A. Entity 為主，Document 撤掉（本 ADR 採用）** | 完成已啟動的重構、消除雙軌、`Entity` dataclass 不再背 doc 欄位的責任分歧、新加入者只看一條路徑 | 需 data migration、需保留 MCP collection name 對外 alias、需設 type-specific column constraint | （採用） |
| **B. Document 為主，Entity 不放 doc 欄位** | Entity 純化為「知識地圖節點」 | 跟現況反向——dashboard / 多數 application 已用 `entity.type == 'document'`，要全部改回 `Document` lookup。重構成本最高，方向也跟過去六個月演化反向 | 跟事實上的演化方向矛盾 |
| **C. 明文劃邊界，兩套並存** | 不需 data migration | 「Entity 是知識地圖節點 / Document 是物理文件」這個邊界很難劃清——dashboard 有時候要看「文件」有時要看「節點」，總是會有跨界需求。並存只是把「合併或分割」的選擇延後 | 治理債務不消失，只是延後 |
| **D. 維持現狀** | 零工 | 兩套 model 持續演化、新加入者持續困惑、`Entity` dataclass 持續混 doc 欄位 | 不解決問題 |

## Consequences

### Positive
- `Entity` dataclass 邊界清晰：通用欄位 + type-specific 欄位（type='document' 時生效），不再「混了 doc 欄位但又有 Document 在旁邊」
- 一個概念一個 model，新加入者學習曲線下降
- M2M 關係統一走 `relationships` graph edge，不再有專屬 bridge 表
- Tags 統一，四維標籤體系不再雙軌
- 為 ADR-022 後續演化（per-source schema、source platform contract）提供乾淨基礎
- MCP 對外契約零變更，agent/skill 不用改

### Negative
- Data migration 是中度風險工作（要處理 documents table 全量資料 + document_entities M2M + 去重檢查）
- `EntityStatus` enum 要加 `archived`，需更新 SQL constraint 與既有 status filter 邏輯
- 歷史資料 backfill 後 `parent_id=NULL`，知識地圖在治理流程跑完前會出現「漂浮的 doc entity」現象，影響短期視覺品質
- ADR-022 之後寫的 spec 與 skill 文件可能需要 review，確認沒誤把「Document table」寫成永久概念

### Risks
- Migration 過程若未仔細處理 partner_id 範圍，可能漏遷或重複；去重檢查若覆蓋率不足，會有衝突 row 被靜默處理
- 對外 MCP 介面雖然名稱不變，但 underlying record 從 documents 變 entities，response payload 結構若不嚴格保持兼容，會破壞 agent 端解析
- 既有 `documents.tags_json` 與 `entities.tags_json` 雖然都是 jsonb，但 Tags / DocumentTags 兩套 dataclass 的型別差異（list[str] | str vs list[str]）要在 D4 合併時處理乾淨，否則 backfill 後 entity tags 會出現混雜型別
- `parent_id=NULL` 的歷史 doc entity 若沒有後補機制，會長期沒有 primary parent，影響知識地圖完整性。後補機制的具體載體與 SLA 由獨立 follow-up 拍板（見 D3 與 Follow-up 段）

## Implementation Notes

實作切片：

1. **Migration（最重的一步）**：
   - **不新增**任何 `doc_*` prefixed column。Document 欄位映射到 Entity 既有同名/同義欄位（見 D1 對映表）
   - 擴 `EntityStatus` enum：加入 `archived`，並更新 SQL `chk_entities_status` constraint
   - 把 `documents` row 全部 INSERT 進 `entities`，依 D1 對映表填欄位（`title → name`、`source_json → sources_json`、`status → status`、`tags_json → tags_json`、`confirmed_by_user`、`last_reviewed_at`、`created_at`、`updated_at`），固定 `type='document'`、`level=3`、`parent_id=NULL`
   - **去重 preflight（必跑，不開新表）**：backfill 開始前必須執行 dry-run query，證明：(a) `documents.id` 與 `entities.id` 無交集；(b) `documents.title` 與既有 `entity(type='document').name`（同 partner_id 範圍）無衝突。**preflight 結果必須是 0 conflicts 才允許 migration 進行**；若非 0，migration 中止並交回人工處理。**本 ADR 不定義自動衝突表**——這是一次性收斂工作，不該為極小機率付永久維護成本
   - 把 `document_entities` M2M 全部寫入 `relationships`（`type='related_to'`），`parent_id` 維持 NULL
   - 確保被遷移後 `parent_id IS NULL` 且 `type='document'` 的 entity 可被後續治理流程查詢撈出（具體載體不在本 ADR 拍板，見 D3）
   - **保留** `documents` 與 `document_entities` 表，標 deprecated 但不 drop（Phase 3 才 drop）
2. **Domain refactor**：
   - **不新增** doc-specific 欄位到 `Entity` dataclass（依 D1 拍板）。Domain 改動只有兩件事：
     a. `EntityStatus` enum 加 `archived` 值（配合 D1 對映表 status 欄位收斂）
     b. 配合 D4 把 `Tags` / `DocumentTags` 合併、`DocumentTags` 刪除
3. **Application refactor**：
   - `OntologyService.upsert_document` 內部改走 EntityRepository
   - `MCP write(collection="documents")` handler 改派到 entity upsert
   - `read_source` / `batch_update_sources` 改走 entity
4. **Caller cleanup**：
   - Grep `DocumentRepository` / `_documents.` 所有 caller，全部改走 EntityRepository
   - Grep `Document(` instantiation site，全部改 Entity
5. **Drop（最後一步）**：
   - `Document` / `DocumentTags` / `DocumentRepository` / `SqlDocumentRepository` / `FirestoreDocumentRepository` 全部刪除
   - Migration drop `documents` 與 `document_entities` table

## Rollout

### Phase 1（資料遷移，不改 dataclass）
- Migration 擴 `EntityStatus` enum 加 `archived`
- Migration 把 documents 資料搬到 entities，依 D1 對映表填欄位（不新增 column）
- Migration 把 document_entities 全部寫入 relationships，`parent_id` 維持 NULL
- 確保歷史 doc entity 的 `parent_id=NULL` 後補需求可被治理流程撈出（載體另案）
- Tags 合併（D4，純 dataclass refactor）
- 兩套程式碼路徑並存，新建文件繼續走 entity（已是現況）、舊 caller 繼續走 document
- 驗證：documents 表的每一 row 都能在 entities 找到對應 type='document' row、欄位內容一致；M2M 全部進 relationships；KPI 與 Dashboard 顯示一致

### Phase 2（Caller 收斂）
- 把所有 `_documents.upsert` / `DocumentRepository` caller 改走 EntityRepository
- MCP `write(collection="documents")` handler 內部改派
- 驗證：MCP 對外 contract 端到端不變、dashboard 不變、partner key e2e 測試通過

### Phase 3（Drop）
- 確認 Phase 2 上線且穩定 1 週後
- Migration drop `documents` table 與 `document_entities` table
- 刪 `Document` / `DocumentTags` / `DocumentRepository` 與兩個實作
- 驗證：grep 整個 src/ 確認沒有 Document 殘留 import

## Follow-up

- ADR-022 的 D1（「Document 保持單一 collection」）需要 amendment 註明：「『單一 collection』指的是 MCP 對外 collection name（`write(collection='documents')`），不是 SQL table。SQL 層由 ADR-046 收斂為 entities + type='document'」
- `SPEC-ontology-architecture` 的「Entity 分層模型」段落（line 70-89）需要 amendment，明文寫 document 已經是 entity 的一種，不再有獨立 Document model
- `Tags` 統一後，`apply_tag_confidence(tags: Tags | DocumentTags)`（governance.py:150）的雙型別 signature 要簡化為 `Tags`
- 若 ADR-045（Protocol collection）也通過，Protocol 與 Document 兩個收斂方向需確認 derived collection vs entity-as-document 的命名與分類一致
- **歷史 doc entity 的 primary parent 後補機制**：ADR-046 backfill 後，所有歷史 doc entity 的 `parent_id` 是 NULL。需要獨立 TD 或小 ADR 設計治理流程：(a) 載體（新表 / 復用 blindspot / 復用 entries / dashboard 視圖）、(b) 後補 UX、(c) SLA。本 ADR 不在此拍板
- **M2M ordering 教訓**：document_entities 沒有順序欄位，導致 backfill 時 primary parent 不可恢復。未來新增任何「list semantic」的 M2M 關係（例如「文件的 sources 順序」、「entity 的 tag 順序」），SQL schema 必須包含 `position int` 或 `is_primary boolean` 欄位，否則一旦寫入就無法恢復順序語意
