---
type: ADR
id: ADR-040
status: Accepted
ontology_entity: MCP 介面設計
created: 2026-04-18
updated: 2026-04-18
phase_a_landed: 2026-04-18
---

# ADR-040: MCP get/search — 從 eager-dump 轉為 opt-in include

## Context

### 實測觸發（2026-04-18 session dogfood）

Agent 在 capture 一個決策進 ontology 時的實測：

- **`search(query="治理 架構 server")`** 回傳 ~4,000 tokens（10 個 entity 完整 dump，其中包含 `心理哲學與教育` 的 16 個 Google Doc sources 陣列）——且**沒有任何一個 entity 與 query 語意相關**
- **`get(collection="entities", name="MCP 介面設計")`** 回傳 ~40,000 tokens：entity 本體 + 8 個 outgoing + 20 個 incoming relationships + 11 個 active entries（decision/insight 原文）+ 11 hops 的 impact_chain + 50+ 個 reverse_impact_chain（遞迴上游）
- Agent 做 3 次 search + 1 次 get = ~52,000 tokens，**還沒開始 write**

### 為什麼現狀是這樣

當前 `get`（`src/zenos/interface/mcp/get.py:74-152`）對 entity collection 的行為是 **eager dump**：
- Line 119-142：展開 outgoing + incoming relationships（每筆含完整 description）
- Line 146-147：`active_entries = list_by_entity(eid)` 把所有 active entries 塞進來
- Line 148-150：`compute_impact_chain` forward + reverse 各跑一次 BFS

`search`（`src/zenos/interface/mcp/search.py`）同樣對 each match 呼叫 `_serialize(entity)` 含所有欄位。

### 這個設計有兩個 root cause

1. **假設「呼叫者想要所有相關資訊」**——但實際上 agent 每次只需要其中 10-20%（例如 capture 時只要 entity summary + 最相關的 3 條 relationship）
2. **沒有分辨 consumer 類型**——Dashboard UI 需要完整 graph expansion 去畫圖，但 MCP agent 需要 token-economical 回傳。同一個 API 同樣的 contract 服務兩種需求，結果偏向「最重」的一方

### 約束條件

- **Dashboard 已 production**（Firebase Hosting），現有讀取邏輯依賴完整 payload（見 `dashboard/src/app/(protected)/knowledge-map/page.tsx:229-230` 讀 `impact_chain`、`dashboard/src/components/NodeDetailSheet.tsx:266` 讀 `reverse_impact_chain`）
- **MCP server 已部署 Cloud Run**，第三方 partner 可能在呼叫
- Context window 限制讓 agent 無法多步推理——改動這個 API 直接影響 session 能做多少工作

### 相關證據

- 2026-04-18 session journal：修 Bug 1/2（coverage algo + analyze schema）+ 砍 verb/topology（-1006 行）+ 移除 server-side governance_ssot（-49 行）
- 早上 session 對比 Karpathy Wiki 範式，結論：ZenOS 做了 Graph RAG 的 Pillar B schema，但 Pillar A (semantic retrieval) 缺位，加上 eager-dump API，agent 體驗斷裂

---

## Decision

**改變 `mcp__zenos__get` 和 `mcp__zenos__search` 的預設行為，從 eager-dump 改為 opt-in include。**

### 具體規則

1. **`get(collection="entities", name=..., include=[...])`**
   - Default（`include` 不傳 或 `include=["summary"]`）：**只回 entity 本體**（id、name、type、level、status、summary、tags、owner、confirmed_by_user、parent_id、source count——**不是 sources 陣列全文**）
   - 選 `include=["relationships"]`：加回 `outgoing_relationships` + `incoming_relationships`
   - 選 `include=["entries"]`：加回 `active_entries`（且預設 `limit=5`，最新優先）
   - 選 `include=["impact_chain"]`：加回 `impact_chain` + `reverse_impact_chain`
   - 選 `include=["sources"]`：加回完整 sources 陣列（含所有 URI）
   - 選 `include=["all"]`：現行 eager dump 行為（給 dashboard 用）

2. **`search(collection="entities", query=..., include=[...])`**
   - Default：每筆 result 只回 `{id, name, type, level, summary_short（最多 120 字）, score}`——**不回 tags、sources、details**
   - 選 `include=["tags"]`：加回 tags
   - 選 `include=["full"]`：現行 eager dump

3. **Dashboard 專用路徑維持現狀**——Dashboard 直接呼叫 `src/zenos/interface/dashboard_api.py`（REST），**不走 MCP**。MCP contract 改動**不 break dashboard**。已驗證：`dashboard/src/lib/api.ts` 的所有讀取都走 `/api/entities/...` REST endpoint，不呼叫 MCP tools。

### 分階段落地

1. **Phase A（本 ADR 範圍）**：加入 `include` 參數，預設值**暫時保持 eager dump**（backward compat），log warning「caller not using include, defaulting to full payload — this will change in ADR-040 Phase B」
2. **Phase B（3 個月後）**：切換預設值為 `["summary"]`——agent 不傳 include 會拿到精簡 payload。dashboard 繼續用 REST 不受影響
3. **Phase C（6 個月後）**：移除 warning 和 legacy 路徑

---

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **(A) 完全重設計：把 get 拆成多個 tools**（get_entity、get_relationships、get_entries、get_impact_chain） | API 語意極其清楚；每個 tool 單一職責 | MCP tool 數量爆炸（原本 8 個，變 15+）；agent 需要更多 prompt 空間記住 tool 清單；增加 cognitive overhead | tool sprawl 是 ADR-005「17→7」想解決的反向問題，不走回頭路 |
| **(B) 在 get 加 per-field filter（fields=["summary","tags"]）** | 最細粒度控制 | agent prompt 要列欄位名；欄位變動會 break caller；太底層 | 不適合 agent-facing API，過度技術化 |
| **(C) 保留 eager dump，只做 response compression（例如 sources 縮寫成 count）** | 最小改動 | 沒解決根本問題：relationships 和 impact_chain 還是全展開；token 只降 30%，不夠 | 半解決 = 沒解決 |
| **(D) 本 ADR 選項：opt-in include 參數** | 對齊 GraphQL / REST 領域的 sparse fieldsets 慣例；agent 可按需取；default 可漸進切換 | 需要 3 階段 migration；短期 backward compat 增加 code 複雜度 | **選這個**——成熟慣例 + 漸進遷移 + 可回頭 |

---

## Consequences

### 正面

- **Agent 單次 get token 消耗從 ~40k 降至 ~1-2k**（default summary mode）—— 20x 改善
- **Search 回傳 noise 大幅降低**——每 result 從 ~400 tokens 降至 ~50 tokens，10 筆 result 從 4k 降至 500 tokens
- **為 Pillar A（semantic retrieval）鋪路**——search 回傳格式精簡後，加 embedding score 和 re-ranking 不會讓 payload 再爆炸
- **Agent 可做多步推理**——釋放 context 讓 agent 能連續 get 3-5 個 entity + 做 capture/task 建立，目前 1 個 get 就耗盡預算
- **API 對齊業界慣例**——GraphQL / JSON:API 的 sparse fieldsets、Stripe / Linear 的 `expand` 參數，都是同樣模式

### 負面

- **MCP contract 在 Phase B 會 break 沒傳 include 的第三方 partner**——需要提前溝通，且 Phase A 的 warning log 可追蹤誰還沒遷移
- **Dashboard 如果未來要從 REST 改走 MCP，必須傳 `include=["all"]`**——文件化這個 convention
- **implementation 複雜度增加**：get.py 要處理 include 的條件展開邏輯，serialize 層要支援部分欄位回傳
- **Phase A 的 backward compat 短期讓兩份 path 共存**——code smell，要確保 Phase B 真的執行切換

### 後續處理

- ADR-040 Phase B 的具體切換時機需要新 ADR 或 task（「統計已遷移 caller 百分比」）
- **不在本 ADR 範圍**：semantic retrieval（另寫 SPEC-semantic-retrieval）
- **不在本 ADR 範圍**：是否把 dashboard 從 REST 搬到 MCP（另案）
- 需要為 `include` 寫 tool description 讓 agent 自然學會使用

---

## Implementation

### 檔案變動預估

1. **`src/zenos/interface/mcp/get.py`**
   - 在 `async def get(...)` signature 加 `include: list[str] | None = None`
   - entity 分支（line 74-152）按 include 條件展開 response
   - 加 deprecation warning：`if include is None: logger.warning(...)`

2. **`src/zenos/interface/mcp/search.py`**
   - 同上，加 `include` 參數
   - 各 collection 的 `_serialize` 改用 include-aware helper

3. **`src/zenos/interface/mcp/_common.py`** 或新檔 `_include.py`
   - 新 helper：`_build_entity_response(entity, include: list[str])` 集中 include 邏輯

4. **Tool description 更新**（重要）
   - `get.py:36-56` docstring 加 include 範例
   - `search.py` docstring 同樣
   - 預期 agent 讀 docstring 自然學會使用

5. **Tests**
   - `tests/interface/test_tools.py` 加 include 的 parametrized test
   - 驗證 default（backward compat Phase A）+ `include=["summary"]`（Phase B 預期） + `include=["all"]` 三種行為

6. **Dashboard 不改**——已驗證走 REST 不走 MCP

### 追蹤指標（Phase A → B 切換前要滿足）

- Agent tool call log 顯示 >= 80% 的 get/search 呼叫有帶 include 參數
- 追蹤 `include is None` 的 warning log 頻率，降到 session 平均 < 1 次
- 平均 get response size（透過 Cloud Run log）回落到 < 5,000 tokens

---

## Reference

- 2026-04-18 session dogfood data：見 session journal
- ADR-005: MCP Tool 合併 17→7（同樣是 API economy 的上一步）
- `src/zenos/interface/mcp/get.py:116-150`（eager dump 實作位置）
- `dashboard/src/app/(protected)/knowledge-map/page.tsx:229`（dashboard consumer，不走 MCP）
