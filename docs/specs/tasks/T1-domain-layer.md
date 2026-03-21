# T1 — Domain Layer

> 指派：Developer | 預估：半天
> 依賴：無
> 技術設計：`docs/decisions/ADR-003-phase1-mvp-architecture.md`

---

## 目標

實作純業務邏輯層，**不依賴任何外部系統**（無 Firestore import、無 HTTP）。

## 產出檔案

```
src/zenos/domain/
  models.py          # 資料模型（dataclass）
  governance.py      # 治理規則
  search.py          # 搜尋邏輯
  repositories.py    # 抽象介面（Protocol）
```

---

## models.py — 資料模型

用 Python dataclass 定義，對應 Firestore schema（見 PRD 交付物 1）：

### Entity（骨架層）
```python
@dataclass
class Tags:
    what: str
    why: str
    how: str
    who: str

@dataclass
class Entity:
    id: str | None
    name: str
    type: str          # "product" | "module" | "goal" | "role" | "project"
    parent_id: str | None
    status: str        # "active" | "paused" | "completed" | "planned"
    summary: str
    tags: Tags
    details: dict | None
    confirmed_by_user: bool
    created_at: datetime
    updated_at: datetime
```

### Relationship（骨架層）
```python
@dataclass
class Relationship:
    id: str | None
    source_entity_id: str
    target_id: str
    type: str          # "depends_on" | "serves" | "owned_by" | "part_of" | "blocks" | "related_to"
    description: str
    confirmed_by_user: bool
```

### Document（神經層）
```python
@dataclass
class Source:
    type: str          # "github" | "gdrive" | "notion" | "upload"
    uri: str
    adapter: str

@dataclass
class DocumentTags:
    what: list[str]
    why: str
    how: str
    who: list[str]

@dataclass
class Document:
    id: str | None
    title: str
    source: Source
    tags: DocumentTags
    linked_entity_ids: list[str]
    summary: str
    status: str        # "current" | "stale" | "archived" | "draft" | "conflict"
    confirmed_by_user: bool
    last_reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

### Protocol（View）
```python
@dataclass
class Gap:
    description: str
    priority: str      # "red" | "yellow" | "green"

@dataclass
class Protocol:
    id: str | None
    entity_id: str
    entity_name: str
    content: dict      # { what: {}, why: {}, how: {}, who: {} }
    gaps: list[Gap]
    version: str
    confirmed_by_user: bool
    generated_at: datetime
    updated_at: datetime
```

### Blindspot（治理產出）
```python
@dataclass
class Blindspot:
    id: str | None
    description: str
    severity: str      # "red" | "yellow" | "green"
    related_entity_ids: list[str]
    suggested_action: str
    status: str        # "open" | "acknowledged" | "resolved"
    confirmed_by_user: bool
    created_at: datetime
```

---

## repositories.py — 抽象介面

用 Python Protocol（typing）定義，Infrastructure 層實作：

```python
class EntityRepository(Protocol):
    async def get_by_id(self, entity_id: str) -> Entity | None: ...
    async def get_by_name(self, name: str) -> Entity | None: ...
    async def list_all(self, type_filter: str | None = None) -> list[Entity]: ...
    async def upsert(self, entity: Entity) -> Entity: ...
    async def list_unconfirmed(self) -> list[Entity]: ...

class RelationshipRepository(Protocol):
    async def list_by_entity(self, entity_id: str) -> list[Relationship]: ...
    async def add(self, rel: Relationship) -> Relationship: ...

class DocumentRepository(Protocol):
    async def get_by_id(self, doc_id: str) -> Document | None: ...
    async def list_all(self) -> list[Document]: ...
    async def upsert(self, doc: Document) -> Document: ...
    async def list_by_entity(self, entity_id: str) -> list[Document]: ...
    async def list_unconfirmed(self) -> list[Document]: ...

class ProtocolRepository(Protocol):
    async def get_by_entity(self, entity_id: str) -> Protocol | None: ...
    async def get_by_entity_name(self, name: str) -> Protocol | None: ...
    async def upsert(self, protocol: Protocol) -> Protocol: ...
    async def list_unconfirmed(self) -> list[Protocol]: ...

class BlindspotRepository(Protocol):
    async def list_all(self, entity_id: str | None = None, severity: str | None = None) -> list[Blindspot]: ...
    async def add(self, blindspot: Blindspot) -> Blindspot: ...
    async def list_unconfirmed(self) -> list[Blindspot]: ...

class SourceAdapter(Protocol):
    async def read_content(self, uri: str) -> str: ...
```

---

## governance.py — 治理規則

編碼 `docs/ontology-methodology.md` 的規則：

### 1. 拆分粒度檢查
```python
def check_split_criteria(entity: Entity, related_docs: list[Document],
                         dependencies: list[Relationship]) -> SplitRecommendation:
    """
    檢查一個實體是否值得獨立成模組。
    滿足任 2 條件 → 建議獨立：
    - 有 3+ 份文件關聯
    - 有獨立的依賴鏈
    - 有不同的讀者群
    - 有獨立的目標或待決策項
    - 複雜度超過一段話能說清楚

    回傳：SplitRecommendation(should_split: bool, reasons: list[str], score: int)
    """
```

### 2. 4D 標籤自動化規則
```python
def apply_tag_confidence(tags: Tags | DocumentTags) -> TagConfidence:
    """
    What/Who → confirmed_by_ai = True（高準確）
    Why/How → confirmed_by_ai = False（需人確認）
    回傳哪些 tag 是 draft 狀態
    """
```

### 3. 過時推斷
```python
def detect_staleness(entities: list[Entity], documents: list[Document],
                     relationships: list[Relationship]) -> list[StalenessWarning]:
    """
    實作 ontology-methodology.md 的 4 種過時推斷模式：
    - 功能更新但文件沒跟
    - 目標完成但沒關閉
    - 依賴方更新但被依賴方沒反應
    - 角色消失
    """
```

### 4. 盲點分析
```python
def analyze_blindspots(entities: list[Entity], documents: list[Document],
                       relationships: list[Relationship]) -> list[Blindspot]:
    """
    實作 ontology-methodology.md 的 7 種盲點推斷：
    - 文件放錯位置
    - 核心功能文件不足
    - 已確認問題未排時程
    - 一次性文件佔比過高
    - 時間線斷裂
    - 缺少非技術入口
    - 目標優先級不明
    """
```

### 5. 品質檢查
```python
def run_quality_check(entities: list[Entity], documents: list[Document],
                      protocols: list[Protocol], blindspots: list[Blindspot],
                      relationships: list[Relationship]) -> QualityReport:
    """
    實作 ontology-methodology.md 的 9 項品質檢查清單：
    1. 老闆能否 2 分鐘讀完全景？
    2. 依賴關係有無遺漏？
    3. 待確認欄位都有標記？
    4. 盲點是從文件交叉比對推斷的？
    5. 每份文件都有關聯模組？
    6. 歸檔建議有判斷依據？
    7. 目標有明確優先級？
    8. 有角色在骨架層但神經層無文件？
    9. 拆分粒度合理（每模組 3~10 份文件）？

    回傳：QualityReport(score: int, passed: list, failed: list, warnings: list)
    """
```

---

## search.py — 搜尋邏輯

```python
def search_ontology(query: str, entities: list[Entity],
                    documents: list[Document],
                    protocols: list[Protocol]) -> list[SearchResult]:
    """
    MVP 關鍵字匹配：
    1. 將 query 拆成 tokens
    2. 在 name, summary, tags 欄位中匹配
    3. 按匹配度排序
    4. 回傳 SearchResult(type, id, name, summary, score)
    """
```

---

## Done Criteria

- [ ] 所有 dataclass 定義完成，型別正確
- [ ] 所有 Repository Protocol 定義完成
- [ ] governance.py 的 5 個函數全部實作
- [ ] search.py 的搜尋邏輯實作
- [ ] 單元測試覆蓋 governance.py 所有規則
- [ ] 單元測試覆蓋 search.py
- [ ] 零外部依賴（不 import firestore、不 import httpx）
- [ ] /simplify 執行完畢
