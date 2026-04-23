---
plan_id: 266ac873db944681ac9aa07646edf554
adr_refs:
  - ADR-045-protocol-collection-vs-view
  - ADR-046-document-entity-boundary
created: 2026-04-22
status: draft
owner: architect
project: zenos
---

# PLAN: Knowledge Layer 資料模型收斂

## Goal

完成 ZenOS Knowledge Layer 資料模型收斂——落實 ADR-045（Protocol 收斂為 derived collection）+ ADR-046（Document 完全併入 Entity），並清除 dead Identity 抽象，讓 base entity / 權限 / 衍生物的邊界回到「graph + 繼承」這個原本應有的乾淨直覺。

## Entry Criteria

ADR-045 與 ADR-046 兩份均由用戶 review 通過、status 由 Draft 升為 Accepted。

## Exit Criteria

| # | 條件 | 驗證方式 |
|---|------|---------|
| 1 | `documents` table、`document_entities` table、`Document` / `DocumentTags` dataclass、`DocumentRepository` Protocol 與兩個實作全部刪除 | grep `src/` 確認無殘留 import；migration 確認 table 已 drop |
| 2 | `Tags` 統一為單一 dataclass，`DocumentTags` 刪除 | grep `DocumentTags` 0 hit |
| 3 | `EntityStatus` enum 新增 `archived` 值，SQL `chk_entities_status` 同步 | enum 與 SQL 對齊驗證 |
| 4 | Protocol 文件 amendment 完成（SPEC/REF 全文無「Protocol 是 view」殘留） | `grep -r "Protocol.*view" docs/` 0 hit |
| 5 | `AccessPolicy` / `AgentScope` / `UserPrincipal` / `AgentPrincipal` 四個 dead dataclass 刪除 | grep `src/` 0 hit |
| 6 | ADR-045 D3 Protocol.version 語意調查 task 完成並執行拍板結論 | task status = done + result 非空 |
| 7 | ADR-046 歷史 doc entity primary_parent 後補機制有獨立 TD 或小 ADR 落地 | docs/designs/ 或 docs/decisions/ 下文件存在且 status=Accepted |
| 8 | MCP 對外契約端到端 e2e 驗證行為不變 | `write(collection="documents")` + `read_source` + `batch_update_sources` partner key e2e 測試通過 |

## Tasks

依賴關係：
- 獨立可並行：S01、S05、S08
- 依賴 ADR-045 amendment 落地：S02
- 依賴 ADR-046 接受：S03 → S04
- 依賴 backfill 完成：S06、S09
- 依賴 caller 遷移穩定：S07

```
ADR-045 Accepted ──→ S01 ──→ S02
                      │
ADR-046 Accepted ──→ S03 ──→ S04 ──┬──→ S06 ──(穩定 1 週)──→ S07
                      │            │
                     S05 ──────────┤
                      │            │
                      └──→ S09 ────┘

independent: S08
```

| ID | Title | Owner | Depends | Files | Verify |
|----|-------|-------|---------|-------|--------|
| **S01** | Protocol view → derived collection 文件 amendment（ADR-045 D1+D2+D4） | Developer | ADR-045 Accepted | `docs/specs/SPEC-ontology-architecture.md`、`docs/reference/REF-ontology-current-state.md`、所有提及 Protocol 為 view 的文件 | `grep -r "Protocol.*view" docs/` 0 hit；SPEC line 250 段落已重寫 |
| **S02** | Protocol.version 語意調查 + 後續執行（ADR-045 D3 follow-up） | Architect (調查) → Developer (執行) | S01 | 視拍板結論而定。涵蓋 `src/zenos/domain/search.py:82`、`src/zenos/application/knowledge/ontology_service.py:3157`、`src/zenos/infrastructure/knowledge/sql_protocol_repo.py:20`、`src/zenos/infrastructure/firestore_repo.py:296` | 拍板結論 + 同步修正並交付 |
| **S03** | Migration prep — preflight + EntityStatus.archived（ADR-046 Phase 1a） | Developer | ADR-046 Accepted | 新 migration file、`src/zenos/domain/knowledge/enums.py`、`migrations/*entity_status*` | `EntityStatus.ARCHIVED` 存在；preflight dry-run query 證明 0 conflicts |
| **S04** | Migration execution — backfill documents → entities + document_entities → relationships（ADR-046 Phase 1b） | Developer | S03 | 新 migration file | `documents` 全部 row 在 `entities` 找到對應 type='document' row 且欄位內容一致；`document_entities` 全部寫入 `relationships`；`documents` / `document_entities` 表保留但標 deprecated |
| **S05** | Tags / DocumentTags 合併（ADR-046 D4） | Developer | ADR-046 Accepted | `src/zenos/domain/knowledge/models.py:16,88`、所有 `DocumentTags` import site | grep `DocumentTags` 0 hit；`apply_tag_confidence` signature 簡化 |
| **S06** | Caller migration to EntityRepository（ADR-046 Phase 2） | Developer + QA e2e | S04, S05 | `src/zenos/application/knowledge/ontology_service.py:3301`、`src/zenos/interface/mcp/write.py`、`src/zenos/interface/mcp/source.py`、所有 `_documents.` / `DocumentRepository` caller | MCP `write(collection="documents")` 端到端不變；partner key e2e 通過；dashboard 顯示一致；KPI 對齊 |
| **S07** | Drop documents / document_entities + 刪 Document* code（ADR-046 Phase 3） | Developer | S06 stable for 1 week | 新 migration file（drop tables）、`src/zenos/domain/knowledge/models.py`（刪 Document、DocumentTags）、`src/zenos/domain/knowledge/repositories.py`（刪 DocumentRepository）、`src/zenos/infrastructure/knowledge/sql_document_repo.py`、`src/zenos/infrastructure/firestore_repo.py`（刪 FirestoreDocumentRepository） | grep `src/` 無 `Document` / `DocumentRepository` 殘留 import；migration drop 成功 |
| **S08** | 刪除 dead Identity dataclass | Developer | （獨立） | `src/zenos/domain/identity/models.py`、`src/zenos/domain/identity/__init__.py`、`src/zenos/domain/__init__.py`、`tests/domain/test_models.py` | grep `AccessPolicy\|AgentScope\|UserPrincipal\|AgentPrincipal` 0 hit；測試移除；test suite 通過 |
| **S09** | TD 設計 — 歷史 doc entity primary_parent 後補機制 | Architect | S04 | `docs/designs/TD-doc-primary-parent-remediation.md`（新檔） | TD 包含：(a) 載體選擇與理由 (b) 後補 UX (c) SLA；status=Accepted |

## Decisions

- **2026-04-22**: 採方案 A（Entity 為主，Document 撤掉）而非方案 B/C/D。理由詳見 ADR-046 Alternatives。
- **2026-04-22**: 採方案 B（Protocol 收斂為 collection）而非方案 A（廢 table 改 view）。理由：4 caller 已綁、quality KPI 已用 confirmed_by_user，廢表下游成本 > 改文件。
- **2026-04-22**: 不新增 `doc_*` prefixed 欄位到 Entity（會在 column 層級復刻雙軌），改用既有 Entity 同義欄位對映。
- **2026-04-22**: 歷史 `document_entities` 沒有順序欄位，無法可靠恢復 primary parent，backfill 一律 `parent_id=NULL` + 由治理流程後補。
- **2026-04-22**: Migration 去重採 preflight assert 0 conflicts，不開自動衝突表。
- **2026-04-22**: ADR-045 D3（Protocol.version）不在 ADR 拍板，建獨立 task 做語意調查再決定。
- **2026-04-22**: 歷史 doc entity primary_parent 後補載體不在 ADR-046 拍板，留給獨立 TD（S09）。

## Resume Point

**目前狀態**：尚未開始。Plan 與 ADR-045/ADR-046 已建立為 Draft。

**下一步**：等用戶 review ADR-045 + ADR-046 並升 Accepted。Accepted 後 Architect 立即用 `mcp__zenos__task` 建立 S01-S09 共 9 張 task，各自 link 到本 Plan（plan_id=`266ac873db944681ac9aa07646edf554`）。

**斷點對話脈絡**：用戶從 data model audit 一路問到 ADR draft，已經連續 review 兩輪，目前 ADR-045 + ADR-046 內部一致性已收乾淨。Plan 階段不再做設計討論，只做執行追蹤。
