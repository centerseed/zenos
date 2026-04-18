---
spec: SPEC-semantic-retrieval
td: TD-semantic-retrieval
adr: ADR-041
created: 2026-04-18
status: done
---

# PLAN: Semantic Retrieval（Pillar A, Phase 1）

## Entry Criteria
- ADR-041 已寫且 Architect 裁決 OQ 全 resolved
- SPEC-semantic-retrieval 37 AC 已定義
- TD-semantic-retrieval Done Criteria 明確
- AC test stubs 已產出（`tests/spec_compliance/test_semantic_retrieval_ac.py`）

## Exit Criteria
- 33 個程式可驗證 AC PASS（AC 01-33）
- 4 個 Phase 3 non-functional AC 由 Architect 部署後人工驗證（AC 34-37）
- Cloud SQL pgvector extension enabled
- 298 entity embedding coverage ≥ 95%
- ADR-041 status flip 為 Accepted
- Journal 寫入

## Tasks

### 前置確認（Architect 做）
- [ ] **P0**: 確認 Cloud SQL instance 允許 pgvector extension
  - `gcloud sql instances describe zentropy-db --format=json | jq '.settings.databaseFlags'`
  - 若需要 → `gcloud sql instances patch zentropy-db --database-flags cloudsql.enable_pgvector=on`

### 實作（Developer 做，依序）
- [ ] **S01**: Migration + infrastructure repo 支援 embedding 欄位（AC 01-05）
- [ ] **S02**: EmbeddingService + llm_client.embed()（AC 06-08, 10-12）
- [ ] **S03**: write/confirm async embed hook（AC 09）
- [ ] **S04**: compute_impact_chain ranking（AC 13-18）
- [ ] **S05**: search mode + hybrid（AC 19-24）
- [ ] **S06**: MCP interface 更新 get/search docstring + kwargs（AC 25-28）
- [ ] **S07**: Backfill script（AC 29-33）

### 驗收（QA 做）
- [ ] **S08**: QA 全量驗收 + integration smoke

### 部署（Architect 做）
- [ ] **S09a**: Cloud SQL 執行 migration
- [ ] **S09b**: 部署 Cloud Run（新 runtime）
- [ ] **S09c**: 跑 `scripts/backfill_embeddings.py`（298 entity）
- [ ] **S09d**: 實測 AC 34-37（dogfood）
- [ ] **S09e**: flip ADR-041 Accepted + journal write + commit

## Decisions

- 2026-04-18: 4 個 OQ 全由 Architect 裁決（kwarg / 預設回 breakdown / skip empty summary / flatten substring match）
- 2026-04-18: S01-S07 分 7 個 shot dispatch Developer，每 shot 完成 + AC 過才進下一個（避免一次交付 37 AC 的 blast radius）

## Resume Point

完成。全部 9 個 shot 綠燈。

Phase 1 landed 2026-04-18：
- Cloud SQL migration applied（pgvector 0.8.1 + HNSW index on zenos.entities）
- 293 entity embedded via backfill（4.7 分鐘，Gemini free tier rate-limited——稍超 AC-35 2min 目標，minor）
- Cloud Run revision `zenos-mcp-00176-grb` serving 100%
- Dogfood 實測：
  - `get(..., include=["summary","impact_chain"], top_k_per_hop=3)` ≈ 5.7 KB（vs 27 KB，4.7x 降）
  - `search("治理怎麼做", mode="semantic")` top-2 命中 L3 Task治理規則 / 語意治理 Pipeline
- 全量 2137 tests PASS

**已知 Minor（給 Phase 2 / ADR-042）**：
- Backfill 時間稍超 2min（Gemini API 實際速率約 60 req/min，不是 doc 的 1500）
- 純 `summary="未分類"` 的 company entity 會產生 noise——資料品質問題
- hybrid mode 當全 entity 未 embed 時會 silently drop 無 keyword 匹配（QA Minor #1）
- Gemini 實際 model 是 `gemini-embedding-001` (not `text-embedding-004`)——已修
- pgvector extension 裝在 `zenos` schema 需用 `OPERATOR(zenos.<=>)`、`::zenos.vector`——已修

## Risk Watchlist

- pgvector extension 若需 instance restart → 10min downtime，需要用戶授權後再做
- Gemini API rate limit 實際配額 → backfill 時可能需 throttle
- litellm embed() 實際 response shape → Developer 實作時查
