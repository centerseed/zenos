---
type: ADR
id: ADR-041-pillar-a-semantic-retrieval
status: Approved
ontology_entity: mcp-interface
related_specs: SPEC-semantic-retrieval
created: 2026-04-18
updated: 2026-04-23
phase_1_landed: 2026-04-18
related: ADR-048-grand-ontology-refactor
partially_superseded_sections:
  - "embedding 欄位內聯到 entities 表（已改為 entity_embeddings sidecar，主 SPEC v2 §12）"
retained_canonical_sections:
  - "Retrieval 行為：hybrid mode / neighbor ranking / backfill（Phase 1 已 ship，仍以 SPEC-semantic-retrieval 為 canonical）"
---

> **2026-04-23 Status note**：frontmatter 合法 enum 只有 `Draft / Under Review / Approved / Superseded / Archived`（`SPEC-doc-governance §7`），因此保留 `Approved`；章節級收斂以 `partially_superseded_sections` / `retained_canonical_sections` 顯式列出。embedding schema 改以主 SPEC v2 §12 sidecar table 為權威；retrieval 行為以 `SPEC-semantic-retrieval` 為權威。

# ADR-041: Pillar A — Semantic Retrieval 架構

## Context

### 觸發

2026-04-18 session，落地 ADR-040（get/search opt-in include）後實測：

- `get(include=["summary", "impact_chain"])` 回傳 ~27 KB，95+ 筆 chain（forward 11 + reverse 90+）
- 原因：`compute_impact_chain` 是無排序 BFS。hub entity（如 `MCP 介面設計`）往回走會扇出到 `Dashboard 知識地圖`（15+ part_of）、`資料權限治理`（18+ related_to）、`L3 文件治理`（7+ part_of），逐層膨脹
- 現行 `search` 是純關鍵字，298 entity 規模下 noise 高；Agent 做「找跟 X 相關」的 query 常常拿到無關結果

### 更深層問題：ZenOS 缺 Pillar A

比對 Microsoft GraphRAG 範式，ZenOS 做了 **Pillar B（schema-rich graph）**，但缺 **Pillar A（semantic retrieval）**：
- 無 embedding 儲存層
- 無 vector search
- 無語意相關度評分
- Graph traversal 靠結構邊盲抓，不管語意相關

結果：結構邊越豐富，BFS 越爆炸；agent 越難從 graph 得到精煉 context。

### 約束

- **PostgreSQL 已在 Cloud SQL**（`zentropy-4f7a5:asia-east1:zentropy-db`，schema `zenos`），可加 pgvector extension
- **LLM Client**（litellm）已整合，呼叫 embedding API 零額外 infra cost
- **Corpus 規模小**（~298 entities + L3 文件）——不需要 ANN（HNSW/IVFFlat），pgvector 線性 L2 dozen-ms 內
- **Dashboard 走 REST，不走 MCP**——本 ADR 改動不直接影響 dashboard（除非 dashboard 也想用 semantic search，另案）
- **ADR-040 Phase A 已上線**——本 ADR 的 neighbor ranking 應該從 `impact_chain` include 出發，與 ADR-040 的 opt-in include 協同

### 相關證據

- 2026-04-18 session journal（MCP 介面設計 get 回 ~40k 的實測）
- `src/zenos/application/knowledge/ontology_service.py:1840` — `compute_impact_chain` 無排序 BFS
- Karpathy Wiki / Microsoft GraphRAG 範式對比（本 session 對話）

---

## Decision

**建立 Pillar A semantic retrieval 層：entities 與 documents 的 summary 以 embedding 儲於 pgvector，作為 `impact_chain` neighbor ranking 與 `search` semantic mode 的相關度來源；ranking 支援兩種 context——root entity 自身語意（預設）或 agent 帶入的 `intent` query（顯式）。**

### 具體規則

#### 1. 儲存層：pgvector + inline embedding 欄位

- 啟用 pgvector extension on schema `zenos`
- **Phase 1 範圍：只 `zenos.entities`**。`zenos.documents` 延後（scope 裁決見 Alternatives 末）。新增欄位：
  - `summary_embedding vector(768)` — nullable
  - `embedding_model text` — 記錄模型名（例：`gemini/gemini-embedding-001`）
  - `embedded_at timestamptz` — 上次 embed 時間
  - `embedded_summary_hash text` — embed 時 summary 內容的 sha256（用於 re-embed 偵測）
- 建 HNSW index（`CREATE INDEX ... USING hnsw (summary_embedding vector_cosine_ops)`）即使 298 entity 不急需，留給 scale

#### 2. Embedding 模型：`gemini/gemini-embedding-001` (768 dim)

- 理由：
  - Google AI Studio 免費 tier（1500 req/min，298 entity 批次 backfill 1 分鐘內完成）
  - 298 entity × ~500 字 = ~150k 字元，Vertex AI fallback 時一次性成本 ~$0.002
  - 768 dim 對 298 entity 規模已足夠，儲存與 index 成本比 1536 dim 省一半
  - litellm 已支援
- 不綁 vendor——`embedding_model` 欄位保留 + Matryoshka 同家族可無痛切換

#### 3. Ingest pipeline：write/confirm 觸發，asynchronous

- Entity / Document `write`、`confirm`、`update` 成功後，**非同步**計算 summary embedding（不 block caller）
- 失敗 retry 3 次，失敗後標記 `embedded_at = null, embedded_summary_hash = 'FAILED'`（不中斷業務流程）
- Re-embed 觸發條件：**`sha256(summary) != embedded_summary_hash`**——summary 改了才 re-embed。其他欄位變動不觸發
- 首次建置：admin script 批次 embed 所有現存 entity + document

#### 4. Neighbor ranking for `compute_impact_chain`

- Signature 擴充：`compute_impact_chain(entity_id, direction, max_depth, intent: str | None = None, top_k_per_hop: int | None = None)`
- **intent 模式**（agent 顯式傳）：
  - 對 intent 呼叫 embedding API → `query_vec`
  - 每層 BFS 候選鄰居按 `cosine(neighbor.summary_embedding, query_vec)` 排序
  - 若 `top_k_per_hop` 設定，僅保留前 K 名
- **預設模式**（intent=None）：
  - 用 root entity 的 `summary_embedding` 作為 query_vec
  - 相當於「離 root 語意最近的鄰居優先」
- **Fallback**（neighbor 沒 embedding）：按 `entity.name` 字母序排序並記 `relevance_score=null`（不是 0，避免與真實低分混淆）
- 結果 dict 新增 `relevance_score: float | null` 欄位（0..1 或 null）
- 現有 `max_depth` 參數保留，但 `top_k_per_hop` 是新剪枝手段

#### 5. `search` semantic mode

- `search(collection="entities", query=..., mode: str = "keyword")`——新增 `mode` 參數
- `mode="keyword"`（預設，backward compat）：現行行為
- `mode="semantic"`：query → embedding → pgvector cosine 排序 → top N
- `mode="hybrid"`（**P0 範圍，預設模式**）：semantic + keyword 加權
  - 公式：`final = semantic_cosine * 0.7 + keyword_match * 0.3`
  - `keyword_match` = 1 if query 子字串出現於 entity.name/summary/tags，else 0（簡單布林，Phase 2 可升級 BM25）
  - 若 caller 顯式傳 `mode`，覆蓋預設
  - 若 query 為空字串，hybrid 退化為純 keyword（列出全部）
- 回傳 result 每筆加 `score: float`（semantic 或 hybrid 的最終 score）、`score_breakdown: {semantic, keyword}`（debug 用，可透過 include 控制）

#### 6. Re-ranking（Phase 2 預留，本 ADR 不強制 P0）

- 預留 boost 欄位：`type_prior`（product > module > document）、`recency`（updated_at recency score）、`confirmed_by_user`（已確認+0.1）
- `final_score = hybrid * 0.7 + type_prior * 0.1 + recency * 0.1 + confirmed * 0.1`
- P0 實作**不含**這層；但 score 函式架構要能後續無痛加 signal

---

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **(A) 只做 impact_chain 排序，不碰 search** | Scope 窄、快 | Embedding infra（80% 工）不得不做，search 還是噪音 | 事倍功半；infra 都建了不讓 search 用是浪費 |
| **(B) 用外部 vector DB（Qdrant / Pinecone）** | 專門工具，效能最強 | 新依賴、新 infra 要 deploy、auth；298 entity 殺雞用牛刀 | 規模配不上；pgvector 在 100k entity 以內都夠 |
| **(C) 另建 embedding table，不 inline 到 entities** | schema 乾淨、embedding 生成獨立可重算 | JOIN 成本、應用層多一層抽象；小規模沒 benefit | 小 corpus 下 inline 更簡單 |
| **(D) 用 TF-IDF / BM25 取代 embedding** | 無 LLM 成本、無外部 API | 中文語意處理差、無法跨語言；agent query 口語化常打不到 keyword | ZenOS 目標是繁中 SMB，BM25 不夠 |
| **(E) 本 ADR 選項：pgvector + inline + 雙模 ranking** | 與現有 PostgreSQL 整合、小 delta、hybrid ranking 擴展空間 | 需要 migration + re-embed pipeline | **選這個** |

---

## Consequences

### 正面

- **`impact_chain` 回傳量從 ~27 KB 降到 top_k_per_hop × hop × ~0.5 KB**（例：top_k=3, max_depth=3 → ~5 KB，5x 降）
- **Search 相關度大躍升**——語意 query（「治理怎麼做？」）能命中 `governance_guide`、`document-governance` 等，而非僅靠 keyword
- **Pillar A 到位**——後續 GraphRAG 風格的多跳推理、community detection 等有基礎
- **Agent 多步推理釋放**——ADR-040 省 response size + ADR-041 省 graph noise，組合拳讓 agent 可連續 3-5 次 graph walk
- **預留擴展**——re-ranking、re-embed 觸發、hybrid 模式都可後續加 signal 不重構

### 負面

- **Migration 複雜度**：pgvector extension 需 superuser grant；embedding 欄位 + 首次 batch embed 約 298 次 API call（~$0.01 一次性）
- **Embedding API 成本近乎零**：Gemini AI Studio 免費 tier 覆蓋日常 write 流量；Vertex AI fallback 每月預估 <$0.10
- **Re-embed race condition**：summary 連續改時可能多次 embed，需設計 throttle
- **Embedding 失敗的 degradation path**：無 embedding 的 entity 不能參與 semantic ranking——需定義 fallback（keyword? skip?）
- **本地測試複雜度**：vitest / pytest 需 mock embedding client；integration test 需 local pgvector（docker）

### 後續處理

- **SPEC-semantic-retrieval**：本 ADR 落地的 AC 化（必備）
- **ADR-042 (potential)**：Re-ranking 權重實驗後調整（Phase 2）
- **文件 embedding pipeline**：P0 **僅做 entity**。`zenos.documents` 的 embedding 欄位 schema 先不加，另開 ADR-042（含 document）決定觸發條件與 Bundle highlights 互動
- **不在本 ADR 範圍**：Document embedding、Community detection、hierarchical summary、dashboard 用 semantic、Re-ranking 權重（僅預留 interface）

---

## Implementation

### 檔案變動預估

1. **Migration 新檔**：`migrations/20260418_0001_pgvector_entity_embedding.sql`
   - `CREATE EXTENSION IF NOT EXISTS vector;`
   - `ALTER TABLE zenos.entities ADD COLUMN summary_embedding vector(768), embedding_model text, embedded_at timestamptz, embedded_summary_hash text;`
   - `CREATE INDEX ... USING hnsw (summary_embedding vector_cosine_ops);`
   - **不動 `zenos.documents`**（ADR-042 另案）

2. **`src/zenos/infrastructure/llm_client.py`**：加 `embed(texts: list[str]) -> list[list[float]]` method

3. **`src/zenos/application/knowledge/embedding_service.py`**（新檔）：
   - `compute_and_store_embedding(entity_id)`、`needs_reembed(entity)`、`batch_embed_all()` admin

4. **`src/zenos/application/knowledge/ontology_service.py`**：
   - `compute_impact_chain` 新增 `intent` / `top_k_per_hop` 參數
   - 若 neighbor 有 embedding 則用 cosine 排序，否則 fallback 到 alphabetical by name

5. **`src/zenos/interface/mcp/search.py`**：新增 `mode` 參數

6. **`src/zenos/interface/mcp/get.py`**：`include=["impact_chain"]` 可選傳 `intent` / `top_k_per_hop`（via 新增 kwarg 或獨立 include value）

7. **`scripts/backfill_embeddings.py`**（新檔，admin-only）：批次 embed 所有現存 entity

8. **Tests**：
   - `tests/spec_compliance/test_semantic_retrieval_ac.py` — AC 驗收
   - `tests/application/test_embedding_service.py`
   - `tests/interface/test_search_semantic_mode.py`

### 分階段

1. **Phase 1**：Migration + embedding_service + batch backfill script
2. **Phase 2**：ontology_service.compute_impact_chain 排序 + search semantic mode
3. **Phase 3**：MCP interface 接 intent / top_k_per_hop
4. **Phase 4**：部署 + dogfood + journal 總結

### 追蹤指標

- `impact_chain` 回傳量 p50 < 5 KB（相對 ADR-040 的 27 KB）
- Semantic search 命中率（主觀標準：實測 5 個代表 query，至少 3 個回傳第一筆是「相關」）
- Embedding 覆蓋率 > 95%（entity 有 `summary_embedding not null` 的比例）
- Re-embed 正確觸發：hash 變動 24 hr 內 re-embed

---

## Reference

- ADR-040: MCP get/search opt-in include（本 ADR 的前置工作）
- Microsoft GraphRAG paper（範式對齊）
- pgvector docs：https://github.com/pgvector/pgvector
- `src/zenos/application/knowledge/ontology_service.py:1840` — 現行 BFS 實作
- 2026-04-18 session journal（~40k / ~27k 實測）
