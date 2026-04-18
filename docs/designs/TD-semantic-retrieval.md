---
type: TD
id: TD-semantic-retrieval
spec: SPEC-semantic-retrieval
adr: ADR-041
status: Ready
created: 2026-04-18
---

# TD: Semantic Retrieval（Pillar A, Phase 1）

## 調查報告

### 已讀
- `docs/decisions/ADR-041-pillar-a-semantic-retrieval.md` — 架構決策
- `docs/specs/SPEC-semantic-retrieval.md` — 37 AC + Architect 裁決
- `src/zenos/application/knowledge/ontology_service.py:1840-1920` — 現行 `compute_impact_chain` BFS 實作
- `src/zenos/infrastructure/llm_client.py` — litellm wrapper，可加 `embed()` method
- `migrations/` — 現有 migration naming convention `YYYYMMDD_NNNN_description.sql`
- `src/zenos/infrastructure/knowledge/` — entity_repo 位置（Developer 實作時讀）

### 未確認
- Gemini embedding API 透過 litellm 的實際 response shape → Developer 實作時查 litellm docs
- `zenos.entities` 的 entity_repo 是否已有 `update_partial` method 支援 embedding 欄位 partial update → Developer 實作時確認

## AC Compliance Matrix

| AC ID | 描述 | 實作位置 | Test Function |
|-------|------|---------|---------------|
| AC-SEMRET-01 | entities 加 4 欄 | migration | `test_ac_semret_01_migration_adds_columns` |
| AC-SEMRET-02 | pgvector extension | migration | `test_ac_semret_02_pgvector_enabled` |
| AC-SEMRET-03 | HNSW index | migration | `test_ac_semret_03_hnsw_index_exists` |
| AC-SEMRET-04 | 既有 row 四欄 null | migration | `test_ac_semret_04_existing_rows_null` |
| AC-SEMRET-05 | documents 不動 | migration | `test_ac_semret_05_documents_untouched` |
| AC-SEMRET-06 | compute_and_store 寫入 4 欄 | `embedding_service.py` | `test_ac_semret_06_compute_and_store` |
| AC-SEMRET-07 | needs_reembed by hash | 同上 | `test_ac_semret_07_needs_reembed_on_summary_change` |
| AC-SEMRET-08 | other fields 不觸發 | 同上 | `test_ac_semret_08_no_reembed_on_other_fields` |
| AC-SEMRET-09 | write/confirm async embed | write/confirm hook | `test_ac_semret_09_async_embed_on_write` |
| AC-SEMRET-10 | 3 次 retry 失敗 | `embedding_service.py` | `test_ac_semret_10_failed_marker` |
| AC-SEMRET-11 | API 不可用 → null | 同上 | `test_ac_semret_11_api_unavailable_null` |
| AC-SEMRET-12 | embed_query | 同上 | `test_ac_semret_12_embed_query` |
| AC-SEMRET-13 | intent ranking | `ontology_service.py` | `test_ac_semret_13_intent_ranking` |
| AC-SEMRET-14 | root-self ranking | 同上 | `test_ac_semret_14_root_self_ranking` |
| AC-SEMRET-15 | fallback alphabetical | 同上 | `test_ac_semret_15_fallback_alphabetical` |
| AC-SEMRET-16 | top_k=None 不剪 | 同上 | `test_ac_semret_16_no_pruning` |
| AC-SEMRET-17 | root no embed + no intent | 同上 | `test_ac_semret_17_all_fallback` |
| AC-SEMRET-18 | relevance_score 欄位 | 同上 | `test_ac_semret_18_relevance_score_field` |
| AC-SEMRET-19 | search semantic | `search.py` + `search_service` | `test_ac_semret_19_search_semantic` |
| AC-SEMRET-20 | search hybrid | 同上 | `test_ac_semret_20_search_hybrid` |
| AC-SEMRET-21 | keyword backward compat | 同上 | `test_ac_semret_21_keyword_compat` |
| AC-SEMRET-22 | empty query → keyword | 同上 | `test_ac_semret_22_empty_query_fallback` |
| AC-SEMRET-23 | default hybrid | 同上 | `test_ac_semret_23_default_hybrid` |
| AC-SEMRET-24 | API fail → keyword fallback | 同上 | `test_ac_semret_24_api_fail_fallback` |
| AC-SEMRET-25 | get kwargs intent/top_k | `get.py` | `test_ac_semret_25_get_kwargs` |
| AC-SEMRET-26 | no impact_chain ignore kwargs | 同上 | `test_ac_semret_26_kwargs_ignored_without_chain` |
| AC-SEMRET-27 | search mode signature | `search.py` | `test_ac_semret_27_search_mode_signature` |
| AC-SEMRET-28 | docstring 更新 | get/search docstring | `test_ac_semret_28_docstrings` |
| AC-SEMRET-29 | backfill dry-run | `scripts/backfill_embeddings.py` | `test_ac_semret_29_backfill_dry_run` |
| AC-SEMRET-30 | backfill full | 同上 | `test_ac_semret_30_backfill_full` |
| AC-SEMRET-31 | --only-reembed | 同上 | `test_ac_semret_31_only_reembed` |
| AC-SEMRET-32 | rate limit | 同上 | `test_ac_semret_32_rate_limit` |
| AC-SEMRET-33 | stats output | 同上 | `test_ac_semret_33_stats_output` |
| AC-SEMRET-34 | impact_chain < 5KB | integration | Architect Phase 3 dogfood |
| AC-SEMRET-35 | backfill < 2min | deploy | Architect Phase 3 |
| AC-SEMRET-36 | write latency +50ms p95 | integration | Architect Phase 3 |
| AC-SEMRET-37 | coverage ≥ 95% | deploy | Architect Phase 3 |

## Component 架構

```
migrations/
└── 20260418_0001_pgvector_entity_embedding.sql        # NEW

src/zenos/infrastructure/
├── llm_client.py                                       # MODIFIED — add embed() method
└── knowledge/
    └── entity_repo.py                                  # MODIFIED — support embedding columns

src/zenos/application/knowledge/
├── embedding_service.py                                # NEW
│   ├── class EmbeddingService:
│   │   ├── compute_and_store(entity_id) -> bool
│   │   ├── embed_query(text) -> list[float]
│   │   ├── needs_reembed(entity) -> bool
│   │   └── batch_embed_missing() -> BackfillStats
├── ontology_service.py                                 # MODIFIED — compute_impact_chain + intent/top_k
└── search_service.py                                   # NEW or MODIFIED
    └── hybrid scoring helper

src/zenos/interface/mcp/
├── get.py                                              # MODIFIED — intent/top_k kwargs
├── search.py                                           # MODIFIED — mode param
└── _include.py                                         # MODIFIED — impact_chain build passes kwargs

scripts/
└── backfill_embeddings.py                              # NEW

tests/
├── spec_compliance/test_semantic_retrieval_ac.py       # NEW (37 AC)
├── application/test_embedding_service.py               # NEW
├── application/test_compute_impact_chain_ranking.py    # NEW
└── interface/test_search_semantic.py                   # NEW
```

**設計原則**：
- `EmbeddingService` 是唯一 embedding SSOT。ontology_service 與 search_service 透過 DI 注入使用
- write/confirm 的 async embed 用 `asyncio.create_task(...)` fire-and-forget + try/except 包住，確保 embedding 失敗不影響業務流程
- fallback 邏輯一律在 service 層，interface 不做判斷

## 介面合約

### `EmbeddingService`（新）
```python
class EmbeddingService:
    async def compute_and_store(self, entity_id: str) -> bool:
        """回傳是否成功寫入。失敗時寫 FAILED marker。"""

    async def embed_query(self, text: str) -> list[float] | None:
        """純 in-memory embed，None 表 API 不可用。"""

    def needs_reembed(self, entity: Entity) -> bool:
        """比對 sha256(summary) 與 embedded_summary_hash。summary 為空視為不需要 embed。"""

    async def batch_embed_missing(
        self,
        dry_run: bool = False,
        only_reembed: bool = False,
        rate_limit_per_min: int = 1500,
    ) -> BackfillStats:
        """給 backfill script 用。"""
```

### `compute_impact_chain`（修改）
```python
async def compute_impact_chain(
    self,
    entity_id: str,
    max_depth: int = 5,
    direction: str = "forward",
    intent: str | None = None,              # NEW
    top_k_per_hop: int | None = None,       # NEW
) -> list[dict]:
    """Each hop dict 新增 relevance_score: float | null"""
```

### `search` MCP signature（修改）
```python
async def search(
    ...,
    mode: str = "hybrid",                    # NEW，預設 hybrid
    ...,
) -> dict:
    """mode ∈ {keyword, semantic, hybrid}"""
```

### `get` MCP signature（修改）
```python
async def get(
    ...,
    intent: str | None = None,               # NEW（僅在 include=["impact_chain"] 生效）
    top_k_per_hop: int | None = None,        # NEW
    ...,
) -> dict:
```

## DB Schema 變更

```sql
-- migrations/20260418_0001_pgvector_entity_embedding.sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE zenos.entities
    ADD COLUMN summary_embedding vector(768),
    ADD COLUMN embedding_model text,
    ADD COLUMN embedded_at timestamptz,
    ADD COLUMN embedded_summary_hash text;

CREATE INDEX idx_entities_summary_embedding_hnsw
    ON zenos.entities
    USING hnsw (summary_embedding vector_cosine_ops);
```

## 任務拆分（多 shot，建 PLAN）

**S01: Migration + infrastructure repo 支援 embedding 欄位**
- Files: migration SQL 新檔、`infrastructure/knowledge/entity_repo.py`
- Done: migration 可 apply + rollback；entity_repo 的 read/write 不破壞既有行為，新增 `update_embedding(entity_id, vector, model, hash)` method
- AC: 01-05
- Verify: `.venv/bin/pytest tests/spec_compliance/test_semantic_retrieval_ac.py -k "AC-SEMRET-0[1-5]"` + 現有 infra test 無 regression

**S02: EmbeddingService + llm_client.embed()**
- Files: `infrastructure/llm_client.py`（add `embed(texts)` method），`application/knowledge/embedding_service.py`（新）
- Done: compute_and_store / embed_query / needs_reembed / batch_embed_missing 實作完
- AC: 06-08, 10-12
- Verify: AC 06/07/08/10/11/12 test PASS；新 unit test `tests/application/test_embedding_service.py` 全 PASS

**S03: write/confirm async embed hook**
- Files: `application/knowledge/ontology_service.py`（write/confirm 處加 `asyncio.create_task(embedding_service.compute_and_store(eid))`）
- Done: write/confirm 回應不因 embed 增加 latency > 50ms；embed 在背景跑；失敗不影響主流程
- AC: 09
- Verify: AC-09 test PASS

**S04: compute_impact_chain ranking**
- Files: `application/knowledge/ontology_service.py:1840`
- Done: 新增 intent/top_k_per_hop 參數；fallback 邏輯完整；每筆 hop 附 relevance_score；ADR-040 既有 shape 不破壞
- AC: 13-18
- Verify: AC 13-18 test PASS

**S05: search mode + hybrid**
- Files: `application/knowledge/search_service.py`（可能新建 or 在 ontology_service 加 method）、`interface/mcp/search.py`
- Done: mode kwarg、hybrid 公式、score_breakdown、empty query fallback、API fail fallback
- AC: 19-24
- Verify: AC 19-24 test PASS

**S06: MCP interface 更新 get/search docstring + kwargs**
- Files: `interface/mcp/get.py`、`interface/mcp/search.py`、可能 `_include.py`
- Done: get 新 kwargs、search mode、兩者 docstring 列出新參數 + 範例
- AC: 25-28
- Verify: AC 25-28 test PASS

**S07: Backfill script**
- Files: `scripts/backfill_embeddings.py`
- Done: --dry-run / --only-reembed flags、rate limit、stats output
- AC: 29-33
- Verify: AC 29-33 test PASS

**S08: QA 全量驗收**
- 跑所有 AC test、現有 test suite 無 regression、integration smoke
- 必測 edge cases：summary=null、entity 被刪除中途、concurrent write 同時觸發 embed

**S09: Deploy + Migration + Backfill + Dogfood (Architect Phase 3)**
- Cloud SQL 執行 migration
- 跑 backfill 298 entity
- 部署 Cloud Run
- 實測 `get(include=["impact_chain"], intent="治理", top_k_per_hop=3)` 驗 AC-34 (<5KB)
- 實測 `search(query="治理", mode="hybrid")` 回傳品質
- 驗 AC-35 / 36 / 37

## Done Criteria（全量交付）

1. Migration apply 成功，rollback script 可用（defensive）
2. 全部 37 AC test PASS（AC-34/35/36/37 Phase 3 人工驗證）
3. 現有 test suite 無 regression
4. backfill_embeddings.py 可用，298 entity cold-start < 2min
5. docstring 更新，agent 讀完能正確使用 intent / top_k / mode
6. 部署後 dogfood：impact_chain p50 < 5KB 驗證
7. Simplify：EmbeddingService 單一 SSOT，search/ontology 不重複 embedding 邏輯

## Risk Assessment

### 1. 不確定的技術點
- litellm 的 Gemini embedding response shape — Developer 查 doc 自行確認
- Cloud SQL 是否已允許 CREATE EXTENSION vector — 可能需要 `gcloud sql instances patch` 加 `cloudsql.enable_pgvector`；Architect Phase 3 前確認，否則 migration 會 fail

### 2. 替代方案與選擇理由
- 新建 `search_service.py` vs 在 ontology_service 加 method：選新建，scope 明確且未來 re-ranking 也有去處
- Async embed 用 `asyncio.create_task` vs background queue：選前者，298 entity 小規模不需要 queue；Phase 2 scale 後再升

### 3. 需要用戶確認的決策
無（OQ 已全 resolve）。

### 4. 最壞情況與修正成本
- **Worst**：Cloud SQL 不支援 pgvector → migration fail → 整個 feature blocker
  - 緩解：S01 前先驗證 `gcloud sql flags list | grep vector`
  - 修正成本：patch instance flag，約 10min downtime
- **Second**：Gemini API 流量尖峰 quota exceeded → backfill 中斷
  - 緩解：rate limit + retry；script 可續跑（skip 已 embed 的）
  - 修正成本：重跑
- **Third**：Embedding 品質差 → ranking 亂 → agent 體驗下降
  - 緩解：dogfood 實測驗證；必要時回退為 keyword mode（fallback 已內建）
  - 修正成本：改 model 或加 re-ranking signal
