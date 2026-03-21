# T3 — Application Layer

> 指派：Developer | 預估：半天
> 依賴：T1, T2
> 技術設計：`docs/decisions/ADR-003-phase1-mvp-architecture.md`

---

## 目標

編排 Domain + Infrastructure，實作所有 Use Case。

## 產出檔案

```
src/zenos/application/
  ontology_service.py     # CRUD 用例
  governance_service.py   # 治理用例（quality check, staleness, blindspot）
  source_service.py       # read_source 用例
```

---

## ontology_service.py

每個方法對應一個 MCP tool 的業務邏輯。

```python
class OntologyService:
    def __init__(self, entity_repo, relationship_repo, document_repo,
                 protocol_repo, blindspot_repo):
        ...

    # 消費端
    async def get_protocol(self, entity_name: str) -> Protocol | None
    async def list_entities(self, type_filter: str | None) -> list[Entity]
    async def get_entity(self, entity_name: str) -> EntityWithRelationships
    async def list_blindspots(self, entity_name: str | None, severity: str | None) -> list[Blindspot]
    async def get_document(self, doc_id: str) -> Document | None
    async def search(self, query: str) -> list[SearchResult]

    # 治理端
    async def upsert_entity(self, data: dict) -> Entity
    async def add_relationship(self, source_id: str, target_id: str, type: str, desc: str) -> Relationship
    async def upsert_document(self, data: dict) -> Document
    async def upsert_protocol(self, data: dict) -> Protocol
    async def add_blindspot(self, data: dict) -> Blindspot
    async def confirm(self, collection: str, id: str) -> dict
    async def list_unconfirmed(self, collection: str | None) -> dict
```

### 關鍵邏輯

**upsert_entity 的治理邏輯：**
1. 寫入 entity
2. 呼叫 `governance.apply_tag_confidence()` 判斷哪些 tag 是 draft
3. 呼叫 `governance.check_split_criteria()` 檢查是否建議拆分
4. 回傳 entity + 治理建議（如有）

**confirm 的邏輯：**
1. 讀取指定 collection + id 的 document
2. 設定 `confirmedByUser = true`
3. 設定 `updatedAt = now`
4. 寫回 Firestore

**list_unconfirmed 的邏輯：**
1. 依序查詢各 collection 的 unconfirmed
2. 按 collection 分組回傳

---

## governance_service.py

```python
class GovernanceService:
    def __init__(self, entity_repo, document_repo, relationship_repo,
                 protocol_repo, blindspot_repo):
        ...

    async def run_quality_check(self) -> QualityReport:
        """撈全部資料 → 呼叫 domain.governance.run_quality_check()"""

    async def run_staleness_check(self) -> list[StalenessWarning]:
        """撈全部資料 → 呼叫 domain.governance.detect_staleness()"""

    async def run_blindspot_analysis(self) -> list[Blindspot]:
        """撈全部資料 → 呼叫 domain.governance.analyze_blindspots()"""
```

---

## source_service.py

```python
class SourceService:
    def __init__(self, document_repo, source_adapter):
        ...

    async def read_source(self, doc_id: str) -> str:
        """
        1. 從 document_repo 取得 document
        2. 從 document.source.uri 取得 URI
        3. 透過 source_adapter.read_content(uri) 讀取內容
        4. 回傳文字內容
        """
```

---

## Done Criteria

- [ ] OntologyService 所有方法實作完成
- [ ] GovernanceService 三個治理方法實作完成
- [ ] SourceService read_source 實作完成
- [ ] upsert_entity 包含治理邏輯（tag confidence + split check）
- [ ] confirm 方法能正確更新任何 collection
- [ ] list_unconfirmed 能跨 collection 查詢
- [ ] /simplify 執行完畢
