---
name: dogfood
description: >
  ZenOS 治理流程的 clean-room dogfooding workflow。當使用者說「/dogfood」
  「跑一輪 dogfooding」「找治理流程斷點」「reject rate 為什麼高」時啟動。
  流程：Architect 定義 scenario → Developer clean-room producer 跑流程 →
  Monitor 收集摩擦點 → Developer 修 skill/runtime/tests → QA clean-room verifier 重跑 →
  Architect 比較修前修後 delta。
version: 1.0.0
---

# /dogfood - ZenOS 治理流程閉環驗證

目的不是修 Dogfood 資料，而是驗證 ZenOS 是否真的比資料夾全文搜尋更高效，並在發現流程斷點後形成可驗證的修正閉環。

---

## 成功目標

一輪 dogfood 必須同時證明：

1. **高效 retrieval**
   - 衡量不是只有 step，而是：
     - MCP call 數
     - token 成本
     - 命中正確 L2 / L3 / source 的成功率
     - full-scan ratio
   - 把全量搜尋濃縮成 1 個 call，不算成功。
   - 每輪 scenario 必須先定義 `token_budget` 或低成本 proxy（例如 `payload_bytes.total_result_bytes`）。
   - 若 monitor 顯示 `usage.total_tokens` 或 payload bytes 超過本輪 budget，整輪不得判定 PASS，只能標為 **token budget failure** 或 **token budget contaminated**。
   - 若 token 被同一 top-level session 的固定上下文成本污染，必須改用真正乾淨 session 重跑；在重跑前不得用 call 數或 reject rate 代替 token gate。

2. **L2 達成 spec 目標**
   - 是跨角色共識概念
   - 至少有 1 條具體 `impacts`
   - 能回答「這個概念改了，哪些下游要跟著看」

3. **L3 達成 spec 目標**
   - L3 document 是從 L2 找正式文件的穩定入口
   - agent 能用 `L2 -> L3 bundle -> source` 命中正確 context
   - 不需要 keyword flooding 或大量讀本地 MD

4. **Task 品質因圖譜而變好**
   - 開票前先走 L2 / L3 / impacts chain
   - `linked_entities`、acceptance criteria、受影響模組更完整
   - 不靠全域文件亂搜補票

補充判讀：
- 若 `search(collection="documents", entity_name=...)` 已命中正確 L3 bundle，且 `primary_source` / `source_count` 合理，
  但 `read_source` 只回 `document_summary` fallback，這一輪要先記為 **source delivery degraded**
- 只有在 agent 無法用 `L2 -> L3 bundle` 命中正確文件入口時，才記為 **L3 routing failure**
- `setup_hint` 若明確指向 GitHub token / repo 權限 / zenos_native snapshot，問題屬於 **delivery/auth path**

---

## 紅線

- 預設是**流程評估模式**，不是資料治理模式
- 可以修：skill / MCP contract / runtime / tests / spec
- 不可以直接用 `write` / `confirm` 修 ontology data，除非使用者明確要求
- coverage audit / existence audit 一律禁用 `search(query="關鍵字", collection="documents")` 當主路徑

---

## 閉環流程

### Phase 1：Architect 定義 scenario

Architect 要明確寫出：
- 本輪 scenario
- 目標 product / L2 範圍
- 要驗證的假設（最多 3 條）
- 預期 graph-first path

預期 path：

```text
recent_updates -> tasks -> L2 entity -> L3 documents -> read_source
```

**預設取樣上限**
- clean-room producer / verifier 在沒有明確理由時：
  - `search(collection="entities", ...)` 用 `limit<=5`
  - `search(collection="documents", entity_name=...)` 用 `limit<=3`
  - 且優先用 `include=["summary_compact"]`
  - `read_source(...)` 先用 `preview_chars=1200`
- 目的不是省步數，而是避免把低相關候選與多餘 L3 bundle 一次灌進 context
- `read_source` preview 已足夠判斷時，不要立刻再讀 full content
- 若需要更多候選，必須在回報中說明為什麼 `3` 不夠

**產品 scope（已知時必帶）**
- 若 scenario 已知產品名稱，先 resolve `PRODUCT_ID`
- 後續 `recent_updates`、`search(collection="entities", ...)`、`search(collection="documents", entity_name=...)`
  都必須帶同一個 `product_id`
- 目的：避免跨 workspace / 跨產品噪音把 seed entity 拉歪

### Phase 2：Developer clean-room producer

Producer 必須是**新 session / 新 subagent**：
- 不讀上一輪 dogfood transcript
- 不灌入長篇舊分析
- 只拿 scenario、product、允許 skill/MCP、Context Happy Path
- 若本輪 fix 涉及 **MCP tool contract / parameter schema**（例如新增 `preview_chars`）：
  - verifier 必須改用 **新的 top-level chat session**
  - 同一個聊天內只重開 subagent 不算驗證完成
  - 若 transcript 看不到新參數，該輪只能記為 **schema freshness blocker**

**最小讀取集合（預設）**
- producer / verifier 預設只讀這份 `/dogfood` release skill
- 不要預載 `bootstrap-protocol.md`、`document-governance.md` 全文
- 只有在定位 document routing 規則錯誤時，才額外加讀治理文件

理由：
- clean-room dogfood 要量的是 graph-first path 與流程摩擦
- 不是先把治理手冊整份塞進 context
- 否則 token 成本會先被 pre-read 吃掉，後面的 retrieval delta 失真

硬規則：
- 若 producer 用 keyword search 做 coverage audit，本輪直接 fail
- 若 producer 跳過 L2 直接全量掃 documents，記為 full-scan failure

### Phase 3：Monitor 記錄摩擦點

至少記：
- MCP calls
- reject rate
- token hot spots
- 哪一步偏離 graph-first path
- 是否因 context bias 才成功

若要為本輪留下 machine-readable artifact，直接產：

```bash
python3 scripts/dogfood/build_l3_retrieval_artifacts.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --transcripts-dir <claude-transcripts-dir> \
  --session-file <target-session.jsonl> \
  --since-text DF-{YYYYMMDD}-{N} \
  --token-budget <TOKEN_BUDGET>
```

`--since-text` 必須使用本輪 prompt 裡唯一的 DF id marker；marker 找不到時 script 會 fail，避免 monitor 把同一 session 其他任務的 MCP calls / token usage 算進來。此 wrapper 會自動檢查 `read_source.preview_chars` 並產 `verdict.json`。

若是重放真實歷史 transcript 做 before/after replay，必須加 filter，避免把無關 document path 混進 delta：

```bash
python3 scripts/dogfood/build_iteration_artifacts.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --transcripts-dir <claude-transcripts-dir> \
  --session-file <target-session.jsonl> \
  --since-text DF-{YYYYMMDD}-{N} \
  --call-filter documents_broad

python3 scripts/dogfood/build_iteration_artifacts.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --transcripts-dir <claude-transcripts-dir> \
  --session-file <target-session.jsonl> \
  --since-text DF-{YYYYMMDD}-{N} \
  --call-filter documents_targeted
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/producer.jsonl`
- `/tmp/zenos-dogfood/{DF-ID}/monitor.json`
- `/tmp/zenos-dogfood/{DF-ID}/verdict.json`

`monitor.json` 會包含：
- `total_mcp_calls`
- `rejected_count`
- `reject_rate`
- `top_rejection_reasons`
- `usage.total_tokens`
- `tool_contract.schema_freshness_blocker`

若只跑底層 artifact builder，L3 retrieval scenario 必須接著產機器 verdict，不得只靠人工讀 monitor：

```bash
python3 scripts/dogfood/build_l3_retrieval_verdict.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --monitor-json /tmp/zenos-dogfood/DF-{YYYYMMDD}-{N}/monitor.json \
  --producer-jsonl /tmp/zenos-dogfood/DF-{YYYYMMDD}-{N}/producer.jsonl \
  --token-budget <TOKEN_BUDGET>
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/verdict.json`

判讀：
- `PASS`：routing / source delivery / token gate 全過
- `PARTIAL`：routing 過，但 source delivery 或 token gate 未過
- `FAIL`：路徑錯、0 calls、call 數不符、keyword/full-scan、缺 preview、或 tool/schema/rejection blocker

若已開 `--expect-read-source-preview`，但 transcript 內 `read_source` 仍沒帶 `preview_chars`：
- 一律記為 **schema freshness blocker**
- 代表 verifier 還沒吃到新的 MCP tool schema
- 不得用這輪結果宣稱 preview contract 已完成 live 驗證
- `build_monitor_report.py` 的 findings 也應直接顯示這個 blocker，避免 orchestrator 只看 summary 漏掉

Monitor 也要同步看：
- `analyze(check_type="invalid_documents")`
- 若出現 `current_formal_entry_missing_delivery_snapshot` / `current_formal_entry_stale_delivery_snapshot`
  - classify as **delivery/auth path friction**
  - not **L3 routing failure**

若要把這批 live issue 收成 repair queue：

```bash
python3 scripts/dogfood/build_snapshot_repair_queue.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --invalid-documents-json <analyze-invalid-documents-output.json>
```

若要做受控 repair replay：

```bash
python3 scripts/dogfood/apply_snapshot_repair_queue.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --queue-json /tmp/zenos-dogfood/{DF-ID}/snapshot-repair-queue.json \
  --partner-id <workspace-or-partner-id>
```

若 replay 結果命中 `SOURCE_NOT_FOUND`，接著跑：

```bash
python3 scripts/dogfood/build_source_repair_queue.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --repair-results-json /tmp/zenos-dogfood/{DF-ID}/snapshot-repair-results.json
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json`

分類：
- `SOURCE_NOT_FOUND` on current formal-entry replay = **source governance friction**
- 不是 **L3 routing failure**
- 不是單純 **delivery/auth friction**

若要把這批 source governance friction 整理成下一輪 fixer 的 task 草稿：

```bash
python3 scripts/dogfood/build_governance_review_task_draft.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --source-repair-queue-json /tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json \
  --product-id {PRODUCT_ID}
```

若要把 monitor 補成 per-type health diff，接著跑：

```bash
python3 scripts/dogfood/build_monitor_report.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --existing-monitor /tmp/zenos-dogfood/DF-{YYYYMMDD}-{N}/monitor.json \
  --quality-json <analyze-quality-output.json> \
  --staleness-json <analyze-staleness-output.json> \
  --invalid-documents-json <analyze-invalid-documents-output.json> \
  --source-repair-queue-json /tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json \
  --github-delivery-secret-health-json <github-delivery-secret-health.json> \
  --tasks-json <search-tasks-output.json> \
  --blindspots-json <search-blindspots-output.json>
```

若 controlled replay 已產出 `source-repair-queue.json`：
- monitor 也要把這批 `SOURCE_NOT_FOUND` 寫進 `health.source_governance`
- classify as **source governance friction**

若已有 `check_github_delivery_secret.py` 的 JSON 結果：
- monitor 也要把這批 secret health 寫進 `health.delivery_auth`
- `INVALID_GITHUB_TOKEN` = **delivery/auth blocker**

若要比較修前/修後 delta，再跑：

```bash
python3 scripts/dogfood/build_iteration_delta.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --before-monitor /tmp/zenos-dogfood/<before-df-id>/monitor.json \
  --before-producer /tmp/zenos-dogfood/<before-df-id>/producer.jsonl \
  --after-monitor /tmp/zenos-dogfood/<after-df-id>/monitor.json \
  --after-producer /tmp/zenos-dogfood/<after-df-id>/producer.jsonl
```

delta 現在除了 `calls / tokens / reject_rate / hit_rate / full-scan ratio`，也要比較：
- `health.invalid_documents`
- `health.source_governance`
- `health.delivery_auth`
- `payload_bytes.total_result_bytes`
- `payload_bytes.search_result_bytes`
- `payload_bytes.read_source_result_bytes`

Token gate：
- 每輪 dogfood report 必須列出 `usage.total_tokens`、`cache_read_input_tokens`、`payload_bytes.total_result_bytes`，以及本輪 `token_budget`
- 若 `usage.total_tokens` 超過 `token_budget`，但 `cache_read_input_tokens` 顯示大部分成本來自舊 session context，分類為 **token budget contaminated**，必須用新的 top-level chat session 重跑 verifier
- 若乾淨 session 仍超過 `token_budget`，分類為 **token budget failure**，不得宣稱 dogfood 通過
- 若只通過 calls / reject_rate / routing，但 token gate 未過，總結只能寫 **routing PASS；token FAIL/PARTIAL**

若要先建立 scenario baseline，從 `journal_read(flow_type="capture")` 匯出的 JSON 產：

```bash
python3 scripts/dogfood/build_baseline_library.py \
  --journal-json <journal-read-output.json>
```

輸出：
- `/tmp/zenos-dogfood/baseline-library.json`

reject-rate 可搭配：

```bash
python3 scripts/dogfood/scan_mcp_reject_rate.py --since YYYY-MM-DD --format markdown
```

### Phase 4：Developer fixer 修流程

只修：
- workflow skill
- governance skill
- MCP runtime
- tests

不要修 ontology data。

### Phase 5：QA clean-room verifier 重跑

Verifier 必須是**另一個新 session / 新 subagent**，不得沿用 producer context。

Verifier 預設沿用同一套最小讀取集合：
- 只讀 `/dogfood` release skill
- 除非要 debug 某條治理規則，否則不加載額外治理文件全文

Verifier 要回答：
- 修後是否真的減少 calls / tokens / full-scan ratio
- 是否更容易命中正確 L2 / L3 / source
- 開票品質是否因圖譜而更完整

若本輪有 MCP deploy，deploy 後除了 revision / traffic，也要補做：

```bash
python3 scripts/check_github_delivery_secret.py \
  --project-id zenos-naruvia \
  --secret-name github-token
```

若回 `INVALID_GITHUB_TOKEN`，本輪應記為 **delivery/auth blocker**，不要把 GitHub full-content fallback 誤判成 routing 失敗。

### Phase 6：Architect 比較 delta

Architect 只收這 4 類結果：
- 修前 vs 修後 `calls`
- 修前 vs 修後 `tokens`
- 修前 vs 修後 `hit rate`
- 修前 vs 修後 `full-scan ratio`
- 修前 vs 修後 `usage.total_tokens`、`cache_read_input_tokens`、`payload_bytes.total_result_bytes` 是否低於本輪 `token_budget`

若 `tokens` 變化被 clean-room session 固定成本淹沒，仍要看：
- 修前 vs 修後 `payload_bytes.total_result_bytes`
- 修前 vs 修後 `payload_bytes.search_result_bytes`
- 修前 vs 修後 `payload_bytes.read_source_result_bytes`

只有 verifier clean-room rerun 也變好，才算這輪通過。
若 token gate 沒有明確通過，即使 routing 和 reject rate 都正常，也只能判定 PARTIAL。

---

## L3 Graph Retrieval Gate

L3 覆蓋率與存在性清查只能走：

```python
mcp__zenos__search(collection="entities", query="{主題}", entity_level="L2", include=["summary"])
mcp__zenos__search(collection="documents", entity_name="{L2 名稱}", include=["summary_compact"], limit=3, product_id="{PRODUCT_ID}")
mcp__zenos__read_source(doc_id="{DOC_ID}", source_id="{SOURCE_ID}", preview_chars=1200)
```

規則：
- keyword search 只能做 discovery
- 完整 coverage audit 必須從 L2 開始，用 `entity_name` 枚舉 documents
- `read_source` 預設先走 preview；只有 preview 不足，才升級成 full read
- 如果要逐一打開大量 MD 才知道 bundle 內容，代表 L3 routing 失效

---

## Graph-Assisted Ticketing Gate

開票前必須先：
1. 找相關 L2 / L3
2. 看 relationships / entries / impacts chain
3. 再找相關 documents
4. 才建立 task

若 ticket context 主要來自全域 keyword/full scan，記為 ticket-quality failure。
