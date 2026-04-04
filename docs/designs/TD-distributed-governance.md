---
type: TD
status: Draft
linked_spec: SPEC-distributed-governance
created: 2026-04-04
updated: 2026-04-04
---

# Technical Design: 分散治理——Server 端能力評估

## 背景

PM 提出將治理責任分散到 Agent 端和 Server 端的方向：
- Agent 端（需 LLM）：語意判斷、三問、summary/impacts 撰寫
- Server 端（不需 LLM）：結構驗證、去重、狀態機、原子操作、建議引擎

本文件評估 Server 端五項新能力在現有架構上的技術可行性。

## 現有架構摘要

```
interface/tools.py（MCP 入口，8 tools）
    ↓
application/（service 層：OntologyService, TaskService, GovernanceService）
    ↓
domain/（純邏輯：governance.py, task_rules.py, models.py）
    ↓
infrastructure/（sql_repo.py, llm_client.py）
```

**已有的 Server 端治理機制：**
- Entity upsert 已有 name 長度/格式驗證、L2 layer_decision 三問 gate、GovernanceAI 去重推斷
- Task 已有狀態機（`task_rules.py`）、priority 推薦引擎、cascade unblock
- Write 回傳已有 `warnings`、`governance_hints`、`context_bundle`
- `_build_governance_hints()` 已有 duplicate_signals、suggested_follow_up_tasks 結構

**關鍵發現：大量基礎建設已存在，新增能力主要是擴充而非重建。**

---

## 逐項技術評估

### 1. 結構驗證（write 時 reject）

**現狀：** `OntologyService.upsert_entity()` 已有 name 驗證、L2 三問 gate。Task 已有狀態機驗證。但缺少：
- L2 的 impacts≥1 強制（目前只檢查 `impacts_draft` 非空，不驗 relationship 是否真的建了）
- L3 document 的 frontmatter 驗證（目前無）
- Task 動詞開頭驗證（目前無）
- `linked_entities` 存在性驗證（目前 TaskService 會 `get_by_id` 但不 reject 找不到的）

**技術方案：**

| 驗證項 | 實作位置 | 改動量 |
|--------|---------|--------|
| L2 impacts≥1（confirm 時） | `OntologyService` 或 `confirm` handler | 小：在 confirm entity 時查 relationship_repo，count impacts type |
| L2 verb 非空 | `OntologyService.upsert_entity()` 的 relationship 建立處 | 小：加一行 if check |
| L3 document frontmatter 驗證 | `OntologyService.upsert_document()` | 中：新增 `_validate_document_structure()` 函式 |
| Task 動詞開頭 | `TaskService.create_task()` | 小：regex check on title |
| Task linked_entities 存在性 | `TaskService.create_task()` | 小：已有 get_by_id 迴圈，加 raise |
| Task review 時 result 必填 | `TaskService.update_task()` | 小：已在 SQL schema 強制，加 application 層 check |

**結論：全部可快速實作（Phase 0.5）。都是在現有 service 方法裡加幾行驗證邏輯。**

**風險：**
- 動詞開頭的驗證規則對中文/英文混用需謹慎（中文沒有明確的動詞型態標記）
- 建議用「title 長度≥4 且不以名詞性停用詞開頭」取代嚴格的動詞判斷

---

### 2. 智慧去重（write 時回傳 similar_items）

**現狀：**
- `governance.py` 已有 `_jaccard_similarity()` 函式
- `GovernanceAI.infer_all()` 已有 `duplicate_of` 判斷（需 LLM）
- `_build_governance_hints()` 已有 `duplicate_signals` 欄位

**技術方案：**

在 `domain/governance.py` 新增純函式：

```python
def find_similar_items(
    name: str,
    existing_items: list[dict],  # [{id, name, summary}]
    threshold: float = 0.4,
    limit: int = 3,
) -> list[dict]:
    """Token-level Jaccard + prefix matching, no LLM needed."""
```

呼叫位置：`OntologyService.upsert_entity()` 和 `upsert_document()` 在 upsert 前呼叫，結果塞進回傳的 `warnings` 或新欄位 `similar_items`。

**改動量：** 小。`_jaccard_similarity` 已存在，只需包裝成 `find_similar_items` 並接入 write 流程。

**Phase 分配：Phase 0.5。**

**風險：**
- Jaccard 對短文本（2-3 字）準確度低，可能誤報
- 中文需要做分詞或改用字元 n-gram（jieba 太重，建議用 2-gram）
- 效能：全量比對 O(N)，N<1000 時可接受；超過後需考慮倒排索引或 trigram index

**建議：Phase 0.5 用 Jaccard + 前綴匹配；Phase 1 加 PostgreSQL pg_trgm 擴充做 DB 層去重。**

---

### 3. 原子操作（supersede）

**現狀：**
- Entity entries 已有 supersede 流程，但是兩步操作（先建新 entry → 再改舊 entry status）
- Document entity 沒有 supersede 的原子操作
- `write` tool 的 `sync_mode="supersede"` 已存在但只處理 document sync

**技術方案：**

在 `OntologyService` 新增：

```python
async def supersede_document(
    self, old_entity_id: str, new_data: dict
) -> SupersedeResult:
    """Atomic: create new doc entity + mark old as superseded + create traceability relationship."""
```

內部用一個 DB transaction（或 service 層 try/rollback）確保三個操作一起成功或失敗。

**改動量：** 中。需要：
1. `OntologyService` 新增 `supersede_document()` 方法
2. `EntityStatus` 加 `SUPERSEDED` 值（或複用 `COMPLETED`）
3. `write` tool 新增 `sync_mode="supersede"` 的 entity 版本處理
4. `RelationshipType` 確認有 `SUPERSEDES` 或複用 `RELATED_TO`

**Phase 分配：Phase 0.5（核心流程），Phase 1（完整追溯 UI）。**

**風險：**
- 目前 `sql_repo` 沒有 explicit transaction 支援——需確認 asyncpg pool 的 transaction 行為
- 如果 transaction 不可用，改用「先寫新、再改舊、失敗時 compensate」的 saga 模式

---

### 4. 建議引擎（回傳 suggested_actions）

**現狀：**
- `_build_governance_hints()` 已有 `suggested_follow_up_tasks` 結構
- `_build_context_bundle()` 已回傳關聯 entity 資訊
- `GovernanceService` 已有 `detect_staleness()`、`run_quality_check()` 等分析能力

**技術方案：**

擴充 `_build_governance_hints()` 為：

```python
def _build_governance_hints(
    *,
    warnings: list[str] | None = None,
    suggested_follow_up_tasks: list[dict] | None = None,
    suggested_entity_updates: list[dict] | None = None,  # NEW
    stale_candidates: list[dict] | None = None,  # ENRICH
) -> dict:
```

具體場景：
- **confirm task 時**：查 `linked_entities`，找出這些 entity 的 downstream impacts，回傳 `suggested_entity_updates`
- **write entity 時**：已有，擴充 `stale_candidates`（查 entity 的 last_reviewed_at）
- **write document 時**：回傳 `linked_entities` 中可能需要更新 summary 的 entity

**改動量：** 小-中。邏輯可以漸進式加入，不影響現有回傳結構（新增欄位，不改舊欄位）。

**Phase 分配：Phase 0.5（basic warnings）→ Phase 1（confirm task 回饋 entity updates）。**

**風險：** 低。純粹是 additive 改動，不改變現有行為。

---

### 5. 豐富化 MCP 回傳值

**現狀：**
- `write` 的 entity 路徑已回傳 `warnings`、`governance_hints`、`context_bundle`、`policy_suggestion`
- `write` 的 document/protocol/blindspot 路徑回傳較簡陋
- `task` 回傳只有 task 本體 + `cascade_updates`
- 失敗時 raise ValueError，被 tools.py catch 轉成 `{"error": str}`

**技術方案：**

統一所有 write/task 回傳結構：

```python
{
    "status": "ok" | "rejected",
    "data": { ... },           # 主要回傳物件
    "warnings": [...],         # 非阻塞警告
    "suggestions": [...],      # 建議動作
    "similar_items": [...],    # 去重結果（write 時）
    "context_bundle": {...},   # 關聯上下文
    "rejection_reason": "...", # rejected 時的具體原因
}
```

**改動量：** 中。需要：
1. 統一 `tools.py` 中各 collection 的回傳格式
2. `TaskService` 的 `TaskResult` 加 `warnings` 和 `suggestions` 欄位
3. Error handling 從 `raise ValueError` 改為回傳 `{"status": "rejected", "rejection_reason": ...}`（部分場景）

**Phase 分配：Phase 1。** 因為改回傳格式是 breaking change，需要配合 agent skill 更新。

**風險：**
- 回傳格式變更可能影響所有 caller agent 的 skill 解析邏輯
- 建議用 additive approach：先加新欄位，不改舊欄位；Phase 2 再統一格式

---

## 實作順序建議

### Phase 0.5（快速交付，1-2 sprint）

專注在「不改回傳結構、只加驗證和警告」的改動：

1. **結構驗證**：L2 impacts gate 強化、Task title/linked_entities 驗證
2. **智慧去重**：`find_similar_items()` 純函式 + 接入 entity/document write
3. **supersede 原子操作**：`OntologyService.supersede_document()`
4. **建議引擎 v1**：擴充 `_build_governance_hints()` 加 stale_candidates

**新增/修改檔案：**
| 檔案 | 改動 |
|------|------|
| `src/zenos/domain/governance.py` | 新增 `find_similar_items()`、`validate_task_title()` |
| `src/zenos/application/ontology_service.py` | 在 upsert_entity/document 中加 similar_items 查詢、confirm 時加 impacts count 驗證、新增 `supersede_document()` |
| `src/zenos/application/task_service.py` | create_task 加 title 驗證、linked_entities 存在性 reject |
| `src/zenos/interface/tools.py` | write/task 回傳加 `similar_items`、supersede entry point |
| `tests/domain/test_governance.py` | 新增 find_similar_items 測試 |
| `tests/application/test_task_service.py` | 新增驗證測試 |

### Phase 1（架構改動，2-3 sprint）

1. **統一回傳格式**：所有 write/task 回傳 `{status, data, warnings, suggestions}`
2. **confirm task 回饋引擎**：查 linked_entities 的 downstream impacts，回傳 `suggested_entity_updates`
3. **pg_trgm 去重**：DB 層 trigram index 支援大量 entity 的高效去重
4. **Document frontmatter 驗證**：完整的 L3 document 結構驗證

### Phase 2（長期）

1. **DB transaction 支援**：asyncpg explicit transaction for supersede 等原子操作
2. **傳播觸發**：entity 變更時自動觸發 downstream staleness check
3. **Agent-side SDK**：封裝 Server 回傳的 suggestions 為 agent 可直接執行的 action

---

## 風險與不確定性

### 我不確定的地方
- asyncpg pool 的 transaction 支援程度——需要驗證 `sql_repo.py` 是否已封裝 transaction，還是每次都是獨立 connection
- 中文去重的準確度——Jaccard 對中文短文本效果未知，可能需要字元 2-gram 而非 token-level

### 可能的替代方案
- **去重**：可以不做 Server 端去重，完全依賴 GovernanceAI（LLM）。但這違反「分散治理」的方向——LLM 去重成本高且不穩定
- **原子操作**：可以繼續用兩步操作 + agent 端保證。但 agent 中途斷掉就會留下不一致狀態
- **回傳格式統一**：可以不統一，各 collection 各自回傳。但會增加 agent skill 的解析複雜度

### 需要用戶確認的決策
- 無。所有方案都是 additive，不影響現有行為，可以漸進式推進。

### 最壞情況
- Phase 0.5 的驗證邏輯過嚴，導致現有 agent skill 的 write 請求被 reject。修正成本低：放寬驗證條件或加 `strict=false` 參數即可。

---

## 結論

五項 Server 端新能力在現有架構上**全部可行**，且大部分是擴充而非重建：

| 能力 | 可行性 | Phase | 風險 |
|------|--------|-------|------|
| 結構驗證 | 高（基礎已在） | 0.5 | 低 |
| 智慧去重 | 高（Jaccard 已有） | 0.5 | 中（中文準確度） |
| 原子操作 | 中-高（需 transaction） | 0.5 core / 1 完整 | 中（transaction 支援） |
| 建議引擎 | 高（hints 結構已在） | 0.5 basic / 1 完整 | 低 |
| 豐富化回傳 | 中（breaking change） | 1 | 中（caller 相容性） |

現有 DDD 架構天然支援這些擴充——驗證邏輯放 domain、orchestration 放 application、回傳格式放 interface，不違反依賴方向。
