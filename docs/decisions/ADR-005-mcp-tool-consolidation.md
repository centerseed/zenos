# ADR-005：MCP Tool 合併 — 17 → 7

**狀態**：Accepted
**日期**：2026-03-22

## 背景

ZenOS MCP server 在加入 Action Layer 後將達到 21 個 tools。
學術研究顯示 97.1% 的 MCP tool description 有品質缺陷，且 20+ tools 會消耗大量 context window（~7,350 tokens 光 metadata），導致 agent 選錯 tool、幻覺參數。

如果 agent 無法正確理解和選用 MCP tools，ZenOS 的 ontology 治理層就會斷鏈。

## 決定

將 17 個現有 tools + 4 個新 Action Layer tools = 21 → 合併為 7 個 tools。
每個 tool 對應一個 agent 的心智模型問題。

## 合併對應

| 新 Tool | 問 agent 什麼問題 | 取代的舊 tools |
|---------|------------------|---------------|
| `search` | 我要找東西 | search_ontology, list_entities, list_blindspots, list_unconfirmed, list_tasks |
| `get` | 我知道要什麼，給我完整資訊 | get_entity, get_document, get_protocol |
| `read_source` | 我要讀原始文件 | read_source（不變） |
| `write` | 我要記錄/更新知識 | upsert_entity, upsert_document, upsert_protocol, add_blindspot, add_relationship |
| `confirm` | 我要批准/驗收 | confirm（知識）, confirm_task（任務） |
| `task` | 我要管理行動 | create_task, update_task |
| `analyze` | 知識健不健康？ | run_quality_check, run_staleness_check, run_blindspot_analysis |

## 考慮過的選項

| 選項 | Tool 數量 | 風險 |
|------|-----------|------|
| A. 不合併，靠 tags 過濾 | 21 | agent 仍看到很多 tool，description 互相混淆 |
| B. 拆成 2 個 MCP server | 21 (分 8+13) | 用戶要掛 2 個 server，複雜度沒降 |
| **C. 合併為 7 個（採用）** | 7 | `write` 的 collection 參數需要清楚的 description |
| D. 極端合併為 3 個 | 3 | 單一 tool 參數過多，agent 幻覺率上升 |

## 取捨分析

**選 C 的理由：**
- 7 個 tool 各對應一個明確的 agent 意圖，不會搞混
- `write` 用 collection 參數區分，比 5 個 upsert 工具更自然
- `search` 統一入口避免 agent 不知道該用 list_entities 還是 search_ontology
- `confirm` 統一處理知識確認和任務驗收，一致性好

**`write` 的 `data: dict` 風險：**
研究指出 agent 對 dict 結構幻覺率較高。透過在 description 中列出每個 collection 的必填欄位來緩解。未來可考慮用 FastMCP 3.0 的 Input Schema Transforms 動態切換 schema。

## 後果

- 變得更容易的事：agent 選 tool 的準確率提升；context window 消耗降低 60%+
- 變得更困難的事：`write` 工具需要 agent 理解 collection-specific 的欄位
- 未來需要重新評估的事：如果 `write` 的幻覺率高，考慮把 entities 拆回獨立 tool

## Description 品質改善

基於研究（arxiv 2602.14878v2），每個 tool description 包含：
1. Purpose — 做什麼
2. 使用時機 — 什麼場景用
3. 不要用的情境 — 避免混淆（交叉引用其他 tool）
4. 限制 — 已知約束
5. 參數說明 — 每個參數的含義

同時加入 FastMCP annotations（`readOnlyHint`, `idempotentHint`）和 tags（`read`, `write`）。
