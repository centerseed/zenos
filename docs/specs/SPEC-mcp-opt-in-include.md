---
type: SPEC
id: SPEC-mcp-opt-in-include
status: Draft
related_adr: ADR-040
ontology_entity: MCP 介面設計
created: 2026-04-18
updated: 2026-04-18
---

# Feature Spec: MCP get/search opt-in include（Phase A）

## 背景與動機

2026-04-18 dogfood 實測：agent 在 ZenOS 做一次「capture 決策」操作，`search` 回 ~4k tokens（10 個 entity full dump，皆與 query 無關），`get(collection="entities", name="MCP 介面設計")` 回 ~40k tokens（entity + 8 outgoing + 20 incoming relationships + 11 active entries + 11 hop impact_chain + 50+ reverse_impact_chain）。3 次 search + 1 次 get 燒掉 ~52k tokens，還沒開始 write。

Context window 限制讓 agent 無法多步推理——單一 `get` 就耗盡預算，agent 無法連續讀取多個 entity 後再決策。痛點根因：MCP read API 是 eager-dump，把「呼叫者可能想要的所有資料」一次塞滿 response。同一個 contract 同時服務 Dashboard（需要完整 graph payload 畫圖）與 agent（需要 token-economical）。

ADR-040 拍板走 opt-in include 模式。本 SPEC 定義 **Phase A** 可驗收範圍：加入 `include` 參數、**預設行為仍為 eager-dump** 以保 backward compat、log deprecation warning 以便追蹤遷移狀態。

## 目標用戶（Consumer）

**主 consumer：agent（MCP caller）**，三類場景：
- **capture 場景**：agent 讀取一個 entity 做 summary，只需 `include=["summary"]`
- **task 場景**：agent 要看一個模組影響誰才開任務，需 `include=["impact_chain"]`
- **query 場景**：agent 回答「跟 X 相關的 entity 有哪些」，只需 `search(..., include=["summary"])`（default post-Phase B）

**次 consumer：第三方 partner** 透過 MCP 呼叫（目前仍依賴 eager dump，Phase A 不能 break）。

**明確 non-consumer：Dashboard**——走 `dashboard_api.py` REST，不走 MCP，MCP 改動完全不影響其路徑。

## 需求

### P0（必須有）

#### R1: `get` 加 include 參數
- **描述**：`mcp__zenos__get` 的 signature 新增 `include: list[str] | None = None`。支援值：`summary`、`relationships`、`entries`、`impact_chain`、`sources`、`all`。
- **Acceptance Criteria**：
  - `AC-MCPINC-01`：Given collection=entities 且 name=已存在 entity，When 呼叫 `get(collection="entities", name=X)` 不傳 include，Then 回傳完整 eager dump payload（entity + outgoing + incoming + active_entries + impact_chain + reverse_impact_chain + 完整 sources 陣列），且 server log 輸出 deprecation warning 含「caller not using include, defaulting to full payload — this will change in ADR-040 Phase B」。
  - `AC-MCPINC-02`：Given collection=entities，When 呼叫 `get(..., include=["summary"])`，Then 回傳僅包含 entity 本體欄位（id、name、type、level、status、summary、tags、owner、confirmed_by_user、parent_id）+ `source_count`（integer），**不得包含** `sources`（陣列）、`outgoing_relationships`、`incoming_relationships`、`active_entries`、`impact_chain`、`reverse_impact_chain`。不 log deprecation warning。
  - `AC-MCPINC-03`：Given collection=entities，When 呼叫 `get(..., include=["summary", "relationships"])`，Then response 在 summary 基礎上加回 `outgoing_relationships` 與 `incoming_relationships` 兩個陣列（每筆含完整 description）。
  - `AC-MCPINC-04`：Given collection=entities，When 呼叫 `get(..., include=["summary", "entries"])`，Then response 加回 `active_entries`，**預設 limit=5**，按 `created_at` DESC（最新優先）。（註：EntityEntry domain model 僅有 `created_at`，Phase A 沿用；若未來需 `updated_at` 另開 task）
  - `AC-MCPINC-05`：Given collection=entities，When 呼叫 `get(..., include=["summary", "impact_chain"])`，Then response 加回 `impact_chain`（forward BFS）與 `reverse_impact_chain`（reverse BFS）兩欄位。
  - `AC-MCPINC-06`：Given collection=entities，When 呼叫 `get(..., include=["summary", "sources"])`，Then response 加回完整 `sources` 陣列（含所有 source URI、label、等欄位），**取代** summary mode 的 `source_count`。
  - `AC-MCPINC-07`：Given collection=entities，When 呼叫 `get(..., include=["all"])`，Then response 等同 Phase A default eager dump 的 payload（R1 AC-01），且**不 log deprecation warning**。
  - `AC-MCPINC-08`：Given collection=entities，When 呼叫 `get(..., include=["xyz"])`（未知值），Then **回傳錯誤**（tool 呼叫失敗 / structured error），錯誤訊息列出支援的 include values 清單。**決策：選 reject 而非 silent ignore**，因為 silent ignore 會讓 agent 誤以為拿到完整資料、產生隱性 bug；Phase A 嚴格校驗可及早捕捉 caller 端錯字。
  - `AC-MCPINC-09`：Given collection ≠ entities（例如 documents、tasks），When 呼叫 `get(..., include=[...])`，Then include 參數被**接受但忽略**（non-entity collection 不受 Phase A 影響），回傳原本 payload 且不 log warning。

#### R2: `search` 加 include 參數
- **描述**：`mcp__zenos__search` 的 signature 新增 `include: list[str] | None = None`。支援值：`summary`、`tags`、`full`。
- **Acceptance Criteria**：
  - `AC-MCPINC-10`：Given collection=entities，When 呼叫 `search(collection="entities", query=Q)` 不傳 include，Then 回傳完整 eager dump（每筆 result 含所有 entity 欄位 + sources + details），且 server log 輸出與 R1 同格式的 deprecation warning（一次 call 一次 warning，不是 per-result）。
  - `AC-MCPINC-11`：Given collection=entities，When 呼叫 `search(..., include=["summary"])`，Then 每筆 result 僅包含 `{id, name, type, level, summary_short, score}`，其中 `summary_short` 為 entity.summary 前 120 字元（含）且以 codepoint 計算（非 byte），超過則截斷加省略號「…」。**不得包含** `tags`、`sources`、`details`、`status`、`owner`。
  - `AC-MCPINC-12`：Given collection=entities，When 呼叫 `search(..., include=["summary", "tags"])`，Then 每筆 result 在 summary 基礎上加回 `tags` 陣列。
  - `AC-MCPINC-13`：Given collection=entities，When 呼叫 `search(..., include=["full"])`，Then 每筆 result 等同 Phase A default eager dump payload，且**不 log warning**。
  - `AC-MCPINC-14`：Given collection=entities，When 呼叫 `search(..., include=["xyz"])`，Then 回傳錯誤並列出支援值（同 AC-MCPINC-08 決策）。
  - `AC-MCPINC-15`：Given collection ≠ entities，When 呼叫 `search(..., include=[...])`，Then include 被接受但忽略，不 log warning。

#### R3: Dashboard REST 路徑不受影響
- **描述**：Dashboard 讀取 entity 透過 `src/zenos/interface/dashboard_api.py` 的 `/api/entities/*` REST endpoint，不走 MCP，因此 MCP contract 改動對 Dashboard 為零影響。
- **Acceptance Criteria**：
  - `AC-MCPINC-16`：Given Phase A 已部署 Cloud Run，When Dashboard 呼叫 `/api/entities/{id}`、`/api/entities/search`、`/api/entities/{id}/impact-chain` 等現有 REST endpoint，Then response payload 的**欄位集合與巢狀結構與 Phase A 部署前相同**（含 `impact_chain`、`reverse_impact_chain`、完整 `sources` 陣列）；JSON key ordering 不做斷言。
  - `AC-MCPINC-17`：Given Phase A 已部署，When `dashboard/src/app/(protected)/knowledge-map/page.tsx` 與 `dashboard/src/components/NodeDetailSheet.tsx` 渲染 knowledge map 與 node detail sheet，Then UI 顯示結果與部署前一致（無 regression、無 missing field、無 console error）。

#### R4: Tool docstring 更新
- **描述**：`get.py` 與 `search.py` 的 tool docstring 必須包含 `include` 參數說明 + 至少一個使用範例，讓 agent 透過 tool description 自然學會使用。
- **Acceptance Criteria**：
  - `AC-MCPINC-18`：Given Phase A 部署，When agent 透過 MCP 拉 tool list，Then `get` 與 `search` 的 description 文字中出現關鍵字 `include` 並附至少一組 `include=["summary"]` 與 `include=["all"]` 的 usage example。
  - `AC-MCPINC-20`：Given Phase A 部署，When agent 讀 `get` 的 docstring，Then docstring 必須明示每個 include 值對應的 use case，至少涵蓋：`summary` → 快速辨識 / capture、`relationships` → 沿圖找鄰居、`impact_chain` → 影響範圍分析、`sources` → 找 L3 關聯文件、`entries` → 最近 decision / insight、`all` → 完整 payload。`search` 的 docstring 同樣須對其三個 include 值（`summary`、`tags`、`full`）各附一句 use case 說明。

### P1（應該有）

#### R5: Deprecation warning 可追蹤
- **描述**：Phase A → Phase B 切換需要數據支撐（ADR-040 要求 >= 80% 呼叫已帶 include）。Warning log 需有結構化欄位便於 Cloud Run log query。
- **Acceptance Criteria**：
  - `AC-MCPINC-19`：Given 任一 get/search 呼叫觸發 deprecation warning，Then log entry 為結構化格式（JSON）含欄位 `{tool: "get"|"search", collection, caller_id_if_available, timestamp}`，便於後續用 Cloud Run log explorer 做 aggregation。

### P2（可以有）

（本 Phase 暫不列 P2；所有 P2 行為延至 Phase B/C。）

## 明確不包含（Out of Scope）

- **Phase B default 切換**：把 default 從 eager dump 改為 `["summary"]` 是 Phase B 範圍，另開 SPEC。
- **Phase C 移除 legacy**：刪除 eager dump code path 與 warning log 是 Phase C 範圍。
- **Dashboard 從 REST 搬到 MCP**：另案討論。
- **Semantic retrieval (Pillar A)**：search 的 embedding / vector / hybrid re-ranking 是 SPEC-semantic-retrieval 的範圍，本 SPEC **僅做結構精簡**，不改排序邏輯。
- **Per-field fieldsets**（如 `fields=["summary","tags"]`）：ADR-040 明確拒絕，不做。
- **新增 get_entity / get_relationships 等拆分 tool**：ADR-040 明確拒絕，不做。
- **非 entities collection 的 include 支援**（documents、tasks、entries 等）：Phase A 僅支援 entities collection。
- **Response compression**（例如 sources 縮寫）：ADR-040 alternative C 已拒絕，不做。

## 技術約束（給 Architect 參考）

- **Backward compat 硬要求**：Phase A 不傳 include 的 payload 必須與 Phase A 部署前 byte-level 相同，以免第三方 partner 爆炸。
- **實作檔案**：`src/zenos/interface/mcp/get.py`、`src/zenos/interface/mcp/search.py`、`src/zenos/interface/mcp/_common.py`（或新 `_include.py`）。
- **集中 include 邏輯**：ADR-040 建議 `_build_entity_response(entity, include)` helper 集中條件展開，避免 get/search 兩處 drift。
- **智慧邏輯只放 server 端**（ZenOS Hard Constraint #5）：include 處理不得 leak 到 caller skill。
- **Dashboard 不走 MCP 已驗證**：`dashboard/src/lib/api.ts` 所有讀取走 `/api/entities/*` REST。

## Non-functional 需求

- **`get(..., include=["summary"])` response size**：對 degree-50+ 的 hub entity（如 `MCP 介面設計`），payload 必須 **≤ 2,000 tokens**（以 Claude tokenizer 估算；ADR-040 推估 default summary mode 應為 ~1-2k tokens）。
- **`search(..., include=["summary"])` per-result size**：每筆 result **≤ 100 tokens**；10 筆 result total **≤ 500 tokens + envelope overhead**。
- **Default eager dump path 效能不退化**：Phase A 新增 include 判斷邏輯不得讓 default 路徑的 latency 比 Phase A 前 p50 / p95 增加 > 10%。
- **Warning log 噪音**：每次 get/search 呼叫最多 log 一次 warning（不是 per-entity / per-result）。

## Architect 裁決（2026-04-18）

1. **Warning 頻率**：Phase A 全 log，不做 sampling。
2. **欄位命名**：`source_count`（singular-count，對齊 ZenOS 既有 convention）。
3. **`summary_short` 120 字**：codepoint（Python `len(str)`），超過截斷加「…」。
4. **Non-entity collection**：接受但忽略（見 AC-MCPINC-09/15）。Phase B 再評估是否收緊。
5. **Tool description**：docstring 只放 `include=["summary"]` 與 `include=["all"]` 兩範例。
6. **include 順序與重複**：內部 `set()` dedup，任意順序。
7. **AC-16**：欄位集合 + 巢狀結構相同；JSON key ordering 不斷言。
