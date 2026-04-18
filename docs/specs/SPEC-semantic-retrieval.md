---
type: SPEC
id: SPEC-semantic-retrieval
status: Draft
ontology_entity: MCP 介面設計
related_adr: ADR-041
related_prerequisite: ADR-040
created: 2026-04-18
updated: 2026-04-18
---

# SPEC: Semantic Retrieval（Pillar A, Phase 1）

## 背景與動機

ADR-040 Phase A 落地後實測（2026-04-18 session）顯示：

- `get(collection="entities", name="MCP 介面設計", include=["summary","impact_chain"])` 回傳仍達 **~27 KB**，`impact_chain` 含 95+ 筆 neighbor（forward 11 + reverse 90+）。根因：`compute_impact_chain`（`src/zenos/application/knowledge/ontology_service.py:1840`）是**無排序 BFS**，hub entity 往外 2-3 hop 扇出爆炸
- 298 entity 規模下，純關鍵字 `search` noise 比例過高；agent 的口語化 query（例：「治理怎麼做」）常命不中精確字串，也無法語意近似召回
- 根本缺口是 Pillar A（semantic retrieval）：沒有 embedding、沒有 vector search、沒有相關度分數。Graph traversal 只能結構盲抓，越豐富的 schema 越放大 noise

ADR-041 拍板解法：pgvector + inline embedding 欄位 + 雙模 neighbor ranking + search hybrid mode。本 SPEC 將 ADR-041 的 Phase 1 範圍 AC 化，交由 Architect 做技術設計。

## Scope

### In scope（P0）

- **R1** zenos.entities embedding schema：pgvector extension + 四欄位 migration + HNSW index
- **R2** Entity embedding pipeline：compute_and_store、needs_reembed、write/confirm 觸發 async embed、query embedding API
- **R3** `compute_impact_chain` neighbor ranking：intent 模式、root-self 預設模式、fallback alphabetical、`top_k_per_hop` 剪枝
- **R4** `search` 新增 `mode` 參數：`keyword`（backward compat）/ `semantic` / `hybrid`（預設，0.7 semantic + 0.3 keyword boolean）
- **R5** MCP interface：`get` impact_chain 接 intent/top_k_per_hop、`search` signature 加 mode、docstring 更新
- **R6** `scripts/backfill_embeddings.py` batch backfill script（dry-run、needs_reembed filter、rate limit、統計輸出）

### Out of scope（明確排除，留給 ADR-042 / Phase 2+）

- `zenos.documents` embedding schema 與 pipeline
- Re-ranking 權重實作（`type_prior` / `recency` / `confirmed_by_user` 僅預留 interface，P0 不算入 final score）
- Community detection、hierarchical summary（GraphRAG 風格）
- Dashboard 走 semantic search（dashboard 仍走 REST，不受本 SPEC 影響）
- BM25 升級（Phase 2 可能取代 keyword boolean）
- 跨 embedding model 的 re-embed 管理 UI

## Consumer

- **主要**：MCP agent
  - ZenOS dogfood 自用（PM/Architect/Developer/QA skill 都會 call `get` / `search`）
  - 第三方 partner agent（已部署 Cloud Run，用 partner key 走 MCP）
- **次要**：Admin / Operator
  - 初次建置與週期性補齊跑 `scripts/backfill_embeddings.py`

## Acceptance Criteria

> 每條帶 `AC-SEMRET-NN` ID。Given/When/Then 格式。

### R1 — Migration & Schema

**AC-SEMRET-01**
Given 乾淨 `zenos` schema，When 執行新 migration，Then `zenos.entities` 增加四欄：
- `summary_embedding vector(768)`（nullable）
- `embedding_model text`（nullable）
- `embedded_at timestamptz`（nullable）
- `embedded_summary_hash text`（nullable）

**AC-SEMRET-02**
Given migration 已跑，When 查詢 `pg_extension`，Then 看到 `vector` extension 已啟用於 `zenos` schema。

**AC-SEMRET-03**
Given migration 已跑，When 查詢 `pg_indexes`，Then `summary_embedding` 有 HNSW index 使用 `vector_cosine_ops`。

**AC-SEMRET-04**
Given 既有 entity row（migration 前已存在），When migration 跑完，Then 該 row 的 `summary_embedding` / `embedding_model` / `embedded_at` / `embedded_summary_hash` 皆為 `null`（不破壞既有資料、不 block migration）。

**AC-SEMRET-05**
Given migration 已跑，When 檢視 `zenos.documents` schema，Then **無** embedding 四欄（P0 不動 documents，留給 ADR-042）。

### R2 — Embedding Pipeline

**AC-SEMRET-06**
Given entity E 存在且 summary 非空，When 呼叫 `EmbeddingService.compute_and_store(entity_id=E.id)`，Then：
- 觸發一次 Gemini `gemini-embedding-001` API call
- `E.summary_embedding` 被寫入 768 維 vector
- `E.embedding_model = "gemini/gemini-embedding-001"`
- `E.embedded_at` = now (UTC)
- `E.embedded_summary_hash` = `sha256(E.summary)` hex

**AC-SEMRET-07**
Given entity E 已經 embed 過，When `E.summary` 被改寫，Then `needs_reembed(E)` 回 `True`（因 `sha256(current_summary) != embedded_summary_hash`）。

**AC-SEMRET-08**
Given entity E 已經 embed 過且 summary 未改，When 其他欄位（例：tags / owner）變動，Then `needs_reembed(E)` 回 `False`。

**AC-SEMRET-09**
Given MCP `write` 或 `confirm` 成功建立 / 更新 entity，When 回應回到 caller，Then：
- caller latency 不因 embed 增加 > 50ms p95（embed async、不 block）
- 背景 job 呼叫 `compute_and_store`，成功則 entity 有 embedding

**AC-SEMRET-10**
Given 背景 embed job 呼叫 Gemini API 連續失敗 3 次，When retry 耗盡，Then `entity.embedded_summary_hash = 'FAILED'`、`embedded_at = null`、`summary_embedding = null`，並記 WARNING log（不中斷 write 流程，entity 本體仍寫入成功）。

**AC-SEMRET-11**
Given Gemini API 不可用（connection error / quota exceeded），When `write`/`confirm` 呼叫進來，Then entity 寫入成功但 embedding 留 `null`，log WARNING。

**AC-SEMRET-12**
Given 需要 query embedding（供 R3 intent / R4 semantic query），When 呼叫 `EmbeddingService.embed_query(text: str)`，Then 回傳單筆 768 維 vector（不寫 DB，純 in-memory）。

### R3 — Neighbor Ranking（`compute_impact_chain`）

**AC-SEMRET-13**
Given root entity R 及多層 neighbor 皆有 embedding，When 呼叫 `compute_impact_chain(R.id, direction="forward", max_depth=3, intent="治理 audit", top_k_per_hop=3)`，Then：
- intent 先 embed 成 query_vec
- 每 hop 候選 neighbor 按 `cosine(neighbor.summary_embedding, query_vec)` 降序排
- 每 hop 只保留前 3 名
- 每筆結果含 `relevance_score: float`（0..1）

**AC-SEMRET-14**
Given root R 有 embedding、intent=None，When 呼叫 `compute_impact_chain(R.id, max_depth=3, top_k_per_hop=3)`，Then 用 `R.summary_embedding` 當 query_vec，其餘行為同 AC-SEMRET-13（「離 root 語意最近的 neighbor 優先」）。

**AC-SEMRET-15**
Given 某 neighbor N 無 embedding（`summary_embedding is null`），When ranking 該 hop，Then N 以 `relevance_score = null` 插入該 hop **尾端**，同一批 null 的 neighbor **按 `entity.name` 字母序** 排列。

**AC-SEMRET-16**
Given `top_k_per_hop = None`（未傳），When 呼叫 `compute_impact_chain`，Then 不剪枝（保留所有 neighbor，行為向前相容 ADR-040），但每筆仍附 `relevance_score`（有 embedding 則填分、無則 null）。

**AC-SEMRET-17**
Given root R **無 embedding 且無 intent**，When 呼叫 `compute_impact_chain(R.id, top_k_per_hop=3)`，Then 整條 chain 全部 fallback alphabetical、`relevance_score=null`、`top_k_per_hop` 按字母序前 3 取（不 call embedding API）。

**AC-SEMRET-18**
Given `compute_impact_chain` 回傳，When 檢視每筆 neighbor 的 keys，Then 在 ADR-040 既有欄位之上**新增** `relevance_score: float | null` 欄位（不移除任何既有欄位）。

### R4 — Search Hybrid Mode

**AC-SEMRET-19**
Given collection="entities"、query="治理"、mode="semantic"，When 呼叫 `search`，Then：
- query 被 embed 成 query_vec
- 以 pgvector cosine 排序取 top N（N = 現行 default limit）
- 每筆 result 含 `score: float`（= semantic cosine）

**AC-SEMRET-20**
Given mode="hybrid"（**P0 預設**）、query="治理"，When 呼叫 `search`，Then：
- `final_score = 0.7 * semantic_cosine + 0.3 * keyword_boolean`
- `keyword_boolean = 1.0` if query 子字串出現於 `entity.name` / `summary` / `tags` 任一，else `0.0`
- 每筆 result 含 `score: float`（= final_score）與 `score_breakdown: {semantic: float, keyword: float}`

**AC-SEMRET-21**
Given mode="keyword"（顯式傳），When 呼叫 `search`，Then 行為與現行完全一致（backward compat），`score` 欄位保留現行意義，不 call embedding API。

**AC-SEMRET-22**
Given mode="hybrid"、query=""（空字串），When 呼叫 `search`，Then 退化為 `mode="keyword"` 行為（列出全部、不 call embedding API），每筆 result 的 `score_breakdown.semantic = null`。

**AC-SEMRET-23**
Given 未傳 `mode` 參數，When 呼叫 `search(collection="entities", query="X")`，Then 使用 `mode="hybrid"` 作為預設（ADR-041 拍板）。

**AC-SEMRET-24**
Given mode="semantic" 或 "hybrid"、query 非空、但 Gemini API 不可用，When 呼叫 `search`，Then 自動 fallback 到 `mode="keyword"`、log WARNING，回應仍可用（不 raise 到 caller）。

### R5 — MCP Interface

**AC-SEMRET-25**
Given MCP `get` 被呼叫，When 參數為 `get(collection="entities", name="X", include=["impact_chain"], intent="...", top_k_per_hop=3)`，Then 新增 `intent` / `top_k_per_hop` 作為**平行 kwarg** 傳入（**見 Open Question OQ-1**，由 Architect 裁決最終傳遞形式），並透傳到 `compute_impact_chain`。

**AC-SEMRET-26**
Given `get` 未傳 `include=["impact_chain"]`，When 呼叫帶有 `intent` / `top_k_per_hop`，Then 忽略這兩個參數（不影響非 impact_chain 路徑）。

**AC-SEMRET-27**
Given MCP `search` tool signature，When 檢視，Then 新增 `mode: str = "hybrid"` 參數（預設 hybrid，向後相容透過 caller 顯式傳 `mode="keyword"`）。

**AC-SEMRET-28**
Given MCP tool docstring / description，When 由 agent 讀取，Then：
- `search` docstring 列出 `mode` 可接值 `keyword | semantic | hybrid` 及各自語意
- `get` docstring 在 `include=["impact_chain"]` 範例處標注 `intent` / `top_k_per_hop` 用法

### R6 — Batch Backfill

**AC-SEMRET-29**
Given `scripts/backfill_embeddings.py --dry-run`，When 執行，Then 印出「將處理 N 筆 entity」但**不**呼叫 embedding API、不寫 DB。

**AC-SEMRET-30**
Given 正式執行 `scripts/backfill_embeddings.py`（無 flag），When 跑完，Then 所有 `summary_embedding is null` 或 `needs_reembed=true` 的 entity 被 embed 並寫入。

**AC-SEMRET-31**
Given `scripts/backfill_embeddings.py --only-reembed`，When 執行，Then 僅處理 `needs_reembed=true` 的 entity（跳過已 null 但從未 embed 過的）。

**AC-SEMRET-32**
Given 批次執行，When 同時併發 API call，Then 遵守 Gemini AI Studio rate limit（≤ 1500 req/min），實作上用 token bucket / async semaphore（具體由 Architect 選擇）。

**AC-SEMRET-33**
Given 批次執行結束，When 腳本退出，Then stdout 印出統計：
```
total:    N
embedded: N
skipped:  N   (already fresh)
failed:   N
duration: Xs
```

### Non-functional AC

**AC-SEMRET-34**
Given 現行 298 entity corpus、`top_k_per_hop=3` / `max_depth=3`，When 呼叫 `get(include=["impact_chain"])`，Then 回傳 payload 大小 p50 < 5 KB（相對 ADR-040 的 ~27 KB，目標 5x 降）。

**AC-SEMRET-35**
Given 298 entity 的 cold-start backfill，When 執行 `scripts/backfill_embeddings.py`，Then 完成時間 < 2 分鐘。

**AC-SEMRET-36**
Given 觸發 async embed 的 `write` / `confirm` 流程，When 測量 caller 端 latency，Then p95 增加不超過 50ms（embed 不 block caller）。

**AC-SEMRET-37**
Given backfill 執行完畢，When 檢視 `zenos.entities`，Then `summary_embedding is not null` 的比例 ≥ 95%（對齊 ADR-041 追蹤指標）。

## Architect 裁決（2026-04-18）

- **OQ-1 → 平行 kwarg**：`get(..., intent=..., top_k_per_hop=...)`。`include` 管「要不要回」，kwarg 管「怎麼算」。AC-SEMRET-25/26 不改。
- **OQ-2 → 預設回傳 `score_breakdown`**（payload cost 極小，debug 價值高）
- **OQ-3 → skip embed + `embedded_summary_hash='EMPTY'`**（summary=null 視為治理缺陷，不由 retrieval 補救）
- **OQ-4 → flatten + substring**：`keyword_boolean = any(query_lower in value_lower for value in flatten_tag_values ∪ {name, summary})`。tags 結構 `{what: [str], why: str, how: str, who: [str]}` → 把 what/who 展開、why/how 直接納入，組成字串集合比對

---

## 原 Open Questions（已 resolved，保留紀錄）

**OQ-1：`intent` / `top_k_per_hop` 的 MCP 傳遞形式**

ADR-041 Implementation §6 寫「via 新增 kwarg **或** 獨立 include value」，PM 傾向「平行 kwarg」（見 AC-SEMRET-25），理由：
- `include` 語意是「要不要回這段」，不適合承載 query params（intent/top_k 是**如何**算 impact_chain，不是 whether）
- kwarg 可明確預設值與型別（`intent: str | None = None`, `top_k_per_hop: int | None = None`）
- agent 讀 docstring 時 kwarg 比 `include=["impact_chain:intent=xxx"]` 這類編碼直覺

但有反對理由（請 Architect 評估）：
- 平行 kwarg 會讓 `get` signature 膨脹；若未來 `entries` 也想要 limit / order，會再加 kwarg
- 統一用 structured `include`（如 `include=[{"kind":"impact_chain","intent":"...","top_k":3}]`）可擴展性更好，但 agent 使用成本上升

**請 Architect 在 TD 階段裁決最終形式，本 SPEC 的 AC 以「平行 kwarg」為假設；若改 structured include，AC-SEMRET-25/26 對應更新。**

**OQ-2：`score_breakdown` 是否預設回傳**

AC-SEMRET-20 要求 hybrid mode 每筆附 `score_breakdown`。ADR-041 §5 寫「debug 用，可透過 include 控制」。PM 建議 P0 **預設回傳**（debug 價值高於幾 byte payload），Phase 2 再考慮收到 `include=["score_debug"]` 後才附。由 Architect 決定。

**OQ-3：entity summary 為空字串 / null 時 embed 行為**

AC-SEMRET-06 假設「summary 非空」。實際 corpus 中可能存在 summary=null 的 entity。選項：
- (a) skip embed、`embedded_summary_hash='EMPTY'`
- (b) 用 `entity.name + tags` 組合當 embed source
- (c) 留 null、視同未 embed

PM 傾向 (a)，避免污染語意空間。請 Architect 確認。

**OQ-4：Hybrid keyword boolean 的比對範圍**

AC-SEMRET-20 定義 `keyword_boolean = 1.0` 當 query 子字串出現於 `name` / `summary` / `tags`。但 `tags` 是 list of string，比對語意是「任一 tag 包含 query 子字串」還是「query 整段 == 某 tag」？PM 傾向前者（子字串 in 任一 tag）。請 Architect 在 TD 中明確化。
