---
type: SPEC
id: SPEC-ingestion-governance-v2
status: Draft
ontology_entity: mcp-interface
created: 2026-04-12
updated: 2026-04-23
depends_on: SPEC-zentropy-ingestion-contract, SPEC-mcp-tool-contract, SPEC-ontology-architecture v2 §7, SPEC-task-governance
---

# Feature Spec: Ingestion 治理分工（v2）

> 前置文件：`SPEC-zentropy-ingestion-contract`（v1, Approved）、`ADR-031`（Accepted）。
>
> 本文件不取代 v1 contract，而是記錄一個關鍵的範圍決策：v1 定義的 ingestion facade 暫緩實作，Zentropy 改用 ZenOS 現有 MCP tools 跑通完整沉澱路徑。

## 背景

Zentropy v5.1 需要三種輸入沉澱能力（task、idea/reflection、discussion），但目前 ZenOS 的 ingestion 治理骨架（v1 contract 的四個 endpoint）尚無真實 caller。同時有 10 項結構性缺口需要補齊才能支撐 v5.1 的治理品質。

原方案是在 ZenOS server 端建立完整的 ingestion pipeline（ingest → distill → commit → review）。但實際評估後發現：

1. **沉澱路徑很長**：從 raw input 到最終寫入知識層，需要經過分類、蒸餾、映射、升級判斷等多個步驟。
2. **跨兩端開發不可行**：Zentropy（TypeScript/Flutter）和 ZenOS（Python）分屬不同 repo 和部署，初期同時在兩端開發會讓 iteration 速度降到接近零。
3. **v1 facade 沒有真實流量**：四個 `/api/ext/*` endpoint 尚未被任何 caller 使用，在上面建第二版設計是過度工程。

## 決策

**Zentropy 先在自己的 codebase 跑通整條沉澱路徑，ZenOS 維持現有治理能力不動。**

### ZenOS 的角色（維持現狀）

ZenOS 已有三條 API 通道可供 Zentropy 使用，不需要新增任何 endpoint：

| 通道 | Auth 方式 | 適合場景 |
|------|----------|---------|
| **Dashboard REST API** (`/api/data/*`, `/api/docs/*`) | Firebase ID token | Zentropy app 直接呼叫（最自然，用戶已有 Firebase Auth） |
| **MCP tools** | Partner API key | Agent 場景（Claude Code / 外部 AI） |
| **Federation + ext API** (`/api/ext/*`) | Delegated JWT | v1 contract 定義的正式路徑（已實作但暫無 caller） |

Zentropy 可用的 ZenOS 能力：

| ZenOS 能力 | Dashboard API | MCP Tool | Zentropy 用途 |
|-----------|---------------|----------|--------------|
| 建 task | `POST /api/data/tasks` | `task` | 從討論/靈感中萃取出的 task |
| 寫 entries | — | `write(entries)` | decision/insight/context 寫入知識層 |
| 文件管理 | `POST /api/docs/{id}/content` | `write(documents)` | 文件 metadata 和內容 |
| 確認/驗收 | `POST /api/data/tasks/{id}/confirm` | `confirm` | 高風險項目的人工驗收 |
| 查詢節點 | `GET /api/data/entities` | `search` / `get` | entity mapping（既有節點比對） |
| 治理回饋 | — | `analyze` | 長期治理品質 |

ZenOS **不新增** ingestion-specific 的 API 或治理邏輯。v1 contract 的四個 `/api/ext/*` endpoint 保持 Approved 狀態但暫緩推進，待 Zentropy 在自己端跑通並穩定後，再評估是否需要將通用邏輯抽回 ZenOS server。

### Zentropy 的角色（承擔完整沉澱路徑）

Zentropy 在自己的 codebase 內實作以下能力：

1. **discussion_input 類型**：Discussion Mode 的多輪對話作為輸入源
2. **Signal 收集與結構化**：thread_id、session_id、input_modality 等 context 的組裝
3. **Distill 萃取邏輯**：從 signal bundle 萃取 task/entry/L2-update 候選
4. **Candidate evidence model**：supporting_signals、occurrence_count、days_span 等
5. **既有節點映射**：透過 ZenOS `search`/`get` 做 scope 內 retrieval 和 match
6. **L2 穩定主題判斷**：unmatched concept 累積後的升級建議
7. **Candidate lifecycle**：holding/stale/superseded/merged 等狀態管理
8. **Quality metrics**：link_stability、promotion_survival 等指標
9. **Review queue**：mapping/promotion/decision/conflict 四類審查
10. **延遲治理**：觀察窗口、re-distill、completion/reflection 聯動

Zentropy 最終透過 ZenOS 既有 API 做 mutation（Dashboard REST API 或 MCP tools 均可）——這條路徑已驗證可用（Brain Dump 現在就是這樣做的）。

## 分治邊界

```
Zentropy（完整沉澱路徑）
  raw input → signal 收集 → distill 萃取 → candidate 生成
  → evidence 組裝 → entity mapping（via ZenOS search/get）
  → review queue → 人工/自動判斷
  → mutation（via ZenOS Dashboard REST API 或 MCP tools）

ZenOS（現有能力，不變）
  Dashboard REST API: /api/data/* (entities, tasks, docs)
  MCP tools: task / write / confirm / search / get / analyze
  Core governance: scope gate / workspace gate / L2 治理規範
  Auth: Firebase ID token / Partner API key / delegated JWT
```

### 硬邊界（不可違反）

1. Zentropy **不可**繞過 ZenOS MCP 直接寫 entities/relationships/documents。
2. Zentropy **不可**自行實作 L2 升級——最終升級仍走 ZenOS `confirm` + `SPEC-ontology-architecture v2 §7.1` 的三問 + impacts gate（舊 `SPEC-l2-entity-redefinition` 已於 2026-04-23 併入主 SPEC）。
3. ZenOS Core mutation gate（scope/workspace/欄位白名單）維持不變，Zentropy 端的治理判斷不能取代 server 端的 hard gate。

### 預期遷移路徑

當以下條件同時成立時，考慮將 Zentropy 的沉澱邏輯部分遷回 ZenOS：

1. Zentropy 端的沉澱路徑已穩定運行 3+ 個月
2. 出現第二個 ZenOS client 需要類似的 ingestion 能力
3. 沉澱規則已收斂，不再頻繁調整

屆時 v1 contract 的 `/api/ext/*` endpoint 可作為遷移的 API 介面，distill/mapping/promotion 邏輯搬入 ZenOS server。

## 對 ZenOS 的影響

### 不需要做的事

- 不建 `/api/ext/signals/ingest`、`/api/ext/signals/distill`、`/api/ext/candidates/commit`、`/api/ext/review-queue`
- 不擴充 ingestion service（`src/zenos/application/ingestion/`）
- 不新增 DB table（external_signals、ingestion_batches、ingestion_candidates、ingestion_review_queue）
- 不修改既有 MCP tools 的行為

### 可能需要確認的事

1. **MCP tools 的呼叫頻率**：Zentropy 的 distill 可能會密集呼叫 `search`/`get` 做 entity mapping，需確認 rate limit 是否足夠。
2. **Batch write 效率**：一次 distill 可能產生多個 entries，是否需要 batch write API 或逐筆寫入即可。
3. **Entry content 長度限制**：現有 `write(entries)` 的 content 限制 200 chars，discussion 場景可能需要更長的 content。

## 與既有文件關係

- `SPEC-zentropy-ingestion-contract`（v1）：維持 Approved，暫緩實作。本文件不修改 v1 的任何定義。
- `ADR-031`：維持 Accepted。本文件的決策在 ADR-031 的框架內——雙層 API 模型不變，只是 Zentropy 暫時用 MCP tools 而非 ext facade API 做 mutation。
- `TD-zentropy-ingestion-governance-implementation`：暫緩。待遷移時再啟動。

## Done Criteria

1. 本文件 Approved 後，ZenOS 團隊不排入 ingestion v2 的開發任務
2. Zentropy 團隊確認可用現有 MCP tools 完成沉澱路徑的 mutation 需求
3. 若 Zentropy 發現現有 MCP tools 有能力缺口（如 batch write、content 長度），回報並以最小變更解決

## 開放問題

1. **Entry content 200 chars 限制是否需要放寬？** Discussion 場景的 decision/insight 可能需要更長的描述。
2. **Zentropy 是否需要 ZenOS 的 `analyze` tool 做品質指標計算？** 或者品質指標完全在 Zentropy 端計算。
3. **v1 contract 的 TD 和 DB migration 是否應該 archive？** 避免未來開發者誤以為需要實作。
