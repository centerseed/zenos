# T2 — Infrastructure Layer

> 指派：Developer | 預估：半天
> 依賴：T1（models + repositories 介面）
> 技術設計：`docs/decisions/ADR-003-phase1-mvp-architecture.md`

---

## 目標

實作 Domain Layer 定義的 Repository 抽象介面，連接 Firestore 和 GitHub API。

## 產出檔案

```
src/zenos/infrastructure/
  firestore_repo.py    # Firestore 實作所有 Repository
  github_adapter.py    # GitHub API 實作 SourceAdapter
```

---

## firestore_repo.py

實作 `domain/repositories.py` 定義的所有 Repository Protocol。

### Firestore 連線
```python
from google.cloud import firestore

db = firestore.AsyncClient(project="zenos-naruvia")
```

### Collection 對應

| Repository | Collection | Sub-collection |
|-----------|------------|---------------|
| EntityRepository | `entities` | — |
| RelationshipRepository | `entities/{id}/relationships` | ✅ |
| DocumentRepository | `documents` | — |
| ProtocolRepository | `protocols` | — |
| BlindspotRepository | `blindspots` | — |

### 序列化規則

- dataclass ↔ Firestore dict 的轉換
- `datetime` ↔ Firestore `Timestamp`
- `None` 欄位不寫入 Firestore（而不是寫 null）
- 讀取時缺漏欄位填 None
- `id` 欄位 = Firestore document ID，不存在 document 內部

### 關鍵實作

```python
class FirestoreEntityRepository:
    async def get_by_name(self, name: str) -> Entity | None:
        """用 where("name", "==", name) 查詢，回傳第一筆"""

    async def upsert(self, entity: Entity) -> Entity:
        """
        id 為 None → 新增（auto ID）
        id 有值 → 更新（merge=True）
        自動設定 updated_at = now
        新增時自動設定 created_at = now
        """

    async def list_unconfirmed(self) -> list[Entity]:
        """where("confirmedByUser", "==", False)"""
```

### Firestore 欄位命名

Python 用 snake_case，Firestore 用 camelCase（跟 PRD schema 一致）：

| Python | Firestore |
|--------|-----------|
| `confirmed_by_user` | `confirmedByUser` |
| `parent_id` | `parentId` |
| `created_at` | `createdAt` |
| `updated_at` | `updatedAt` |
| `linked_entity_ids` | `linkedEntityIds` |
| `last_reviewed_at` | `lastReviewedAt` |
| `related_entity_ids` | `relatedEntityIds` |
| `suggested_action` | `suggestedAction` |
| `source_entity_id` | `sourceEntityId` |
| `target_id` | `targetId` |
| `entity_id` | `entityId` |
| `entity_name` | `entityName` |
| `generated_at` | `generatedAt` |

---

## github_adapter.py

實作 `domain/repositories.py` 的 `SourceAdapter` Protocol。

### 介面
```python
class GitHubAdapter:
    async def read_content(self, uri: str) -> str:
        """
        輸入：GitHub URL（如 https://github.com/havital/cloud/blob/main/CLAUDE.md）
        輸出：文件的文字內容

        流程：
        1. 解析 URL → owner, repo, path, ref
        2. GET /repos/{owner}/{repo}/contents/{path}?ref={ref}
        3. Base64 decode content
        4. 如果 > 1MB → 用 blob API
        """
```

### 認證
```python
# 從環境變數讀取
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_DEFAULT_OWNER = os.environ.get("GITHUB_DEFAULT_OWNER", "havital")

headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
```

### URL 解析
```python
def parse_github_url(uri: str) -> tuple[str, str, str, str]:
    """
    https://github.com/havital/cloud/blob/main/api_service/CLAUDE.md
    → ("havital", "cloud", "api_service/CLAUDE.md", "main")
    """
```

### 錯誤處理

| 情境 | HTTP Status | 回傳 |
|------|-------------|------|
| 檔案不存在 | 404 | raise FileNotFoundError(uri) |
| 權限不足 | 403 | raise PermissionError(uri) |
| Repo 不存在 | 404 | raise FileNotFoundError(repo) |
| 檔案太大（>100MB） | 403 | raise ValueError("file too large") |
| Rate limit | 429 | raise RuntimeError("rate limited") |

### HTTP Client
用 `httpx.AsyncClient`，不用 requests（async 友好）。

---

## Done Criteria

- [ ] FirestoreEntityRepository 實作 + 能讀寫 `zenos-naruvia` Firestore
- [ ] FirestoreRelationshipRepository 實作
- [ ] FirestoreDocumentRepository 實作
- [ ] FirestoreProtocolRepository 實作
- [ ] FirestoreBlindspotRepository 實作
- [ ] snake_case ↔ camelCase 自動轉換正確
- [ ] GitHubAdapter 實作 + 能讀 havital repo 的文件
- [ ] GitHub URL 解析正確（含 blob/tree/raw 格式）
- [ ] 錯誤處理覆蓋所有情境
- [ ] 整合測試：對真實 Firestore 讀寫
- [ ] /simplify 執行完畢
