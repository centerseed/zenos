---
name: dogfood-governance
description: >
  ZenOS 治理流程 Dogfooding 評估 skill。讓 agent 實際走完一條完整治理鏈，
  測量摩擦點、重試原因、回傳格式一致性、skill 肥大問題。
  當需要評估治理流程品質、優化 skill 設計、或發現 agent 常卡住的地方時使用。
  用法：「/dogfood」或「幫我評估一下治理流程」。
version: 1.0.0
---

# /dogfood-governance — 治理流程 Dogfooding 評估

讓 agent 自己跑過一條完整的治理鏈，邊跑邊記錄卡點，最後輸出評估報告。

## 核心目標（v3）

Dogfooding 不是「再跑一次流程」，而是要驗證四件事：
- agent 是否能用**乾淨 context** 拿到正確脈絡，而不是被上次測試 bias 帶走
- L2 / L3 治理是否真的達成 spec 目標，而不是退化成資料夾索引
- retrieval / planning / ticketing 是否真的走**知識圖譜路徑**，而不是退化成 keyword / full scan
- 整個 loop 是否**閉環**：發現問題 → 修 skill/runtime → 重跑同場景 → 驗證改善

### Dogfood 成功定義

一輪 dogfood 要證明的是：

1. **高效 retrieval**
   - 不只看 step 數，還要同時看：
     - MCP call 數
     - token 成本
     - 命中正確 L2 / L3 / source 的成功率
     - full-scan ratio
   - 若只是把全量搜尋壓成 1 個 call，不算高效
   - 每輪 scenario 必須先定義 `token_budget` 或低成本 proxy（例如 `payload_bytes.total_result_bytes`）
   - 若 monitor 顯示 `usage.total_tokens` 或 payload bytes 超過本輪 budget，整輪不得判定 PASS，只能標為 **token budget failure** 或 **token budget contaminated**
   - 若 token 被同一 top-level session 的固定上下文成本污染，必須改用真正乾淨 session 重跑；在重跑前不得用 call 數或 reject rate 代替 token gate

2. **L2 達成 spec 目標**
   - L2 必須代表跨角色公司共識概念
   - 至少有 1 條具體 `impacts`
   - 能回答「這個概念改了，哪些下游要跟著看」

3. **L3 達成 spec 目標**
   - L3 document 必須是從 L2 找正式文件的穩定入口
   - agent 能從 `L2 -> L3 bundle -> source` 快速命中，不必全文亂搜

4. **Task 品質因圖譜而變好**
   - 開票時能用 L2 / L3 / impacts chain 補齊背景、AC、相關模組
   - 不靠全量搜尋，不漏掉應該跟著看的 module / protocol / blindspot

## 紅線：先分清楚你在驗流程，還是在修資料

當用戶要的是：
- 找治理流程斷點
- 看 dogfood 為什麼沒過
- 看 MCP reject rate / top rejection reasons
- 驗證 skill / MCP contract / workflow 是否一致

這一輪預設是**流程評估模式**，不是 ontology data remediation。

流程評估模式下：
- 可以：`search/get/analyze`、讀 transcript / skill / spec、統計 reject rate、修 MCP runtime、修 skill、修 spec、補測試
- 不可以：直接 `write/confirm` 去修 ontology 資料、archive document、修改 entity/document 狀態、補資料欄位

只有在用戶**明確要求修資料**時，才可切換到資料治理模式。
若流程評估途中看到 Dogfood 子樹資料有髒污，應記錄為 observation / backlog，不得把它當作本輪完成條件。

---

## 評估目標

| 維度 | 問題 |
|------|------|
| **流程順暢度** | 每個步驟能否一次成功？有沒有需要猜測的地方？ |
| **重試率** | 哪些步驟容易失敗或需要修正後重送？ |
| **Skill 肥大** | 每個 governance 規則檔有多少行？有無重複內容？ |
| **回傳格式一致性** | MCP 工具回傳是否符合 Phase 1 統一格式？ |
| **治理閉環完整性** | task create → update → review → confirm 能否完整跑通？ |

---

## 執行流程

### Step 0：初始化追蹤器

在記憶體建立一個追蹤表（用 markdown table 記錄，不寫檔案）：

```
| 步驟 | 操作 | 結果 | 重試次數 | 問題描述 |
|------|------|------|---------|---------|
```

每個步驟完成後立即填一行。

若本輪要留下可重跑 artifact，直接產：

```bash
python3 scripts/dogfood/build_l3_retrieval_artifacts.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --transcripts-dir <claude-transcripts-dir> \
  --session-file <target-session.jsonl> \
  --since-text DF-{YYYYMMDD}-{N} \
  --token-budget <TOKEN_BUDGET>
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/producer.jsonl`
- `/tmp/zenos-dogfood/{DF-ID}/monitor.json`
- `/tmp/zenos-dogfood/{DF-ID}/verdict.json`

用途：
- `producer.jsonl`：本輪 clean-room producer 的 MCP tool trace
- `monitor.json`：calls / rejected_count / reject_rate / top_rejection_reasons / usage.total_tokens / payload_bytes 的機器可讀摘要
- `verdict.json`：L3 retrieval 的 PASS / PARTIAL / FAIL 機器判定

`--since-text` 必須使用本輪 prompt 裡唯一的 DF id marker；marker 找不到時 script 會 fail，避免 monitor 把同一 session 其他任務的 MCP calls / token usage 算進來。此 wrapper 會自動檢查 `read_source.preview_chars`，不需要另外手動跑 verdict。

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

用途：
- `producer.jsonl`：本輪 clean-room producer 的 MCP tool trace
- `monitor.json`：calls / rejected_count / reject_rate / top_rejection_reasons / usage.total_tokens / payload_bytes 的機器可讀摘要

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

若已開 `--expect-read-source-preview`：
- `monitor.json` 也必須寫出 `tool_contract.schema_freshness_blocker`
- 若 transcript 內 `read_source` 仍沒帶 `preview_chars`
  - 一律記為 **schema freshness blocker**
  - 代表這輪 verifier 還沒吃到新的 MCP tool schema
  - 不得用這輪結果宣稱 preview contract 已完成 live 驗證
  - `build_monitor_report.py` 的 findings 也應直接顯示這個 blocker，避免 orchestrator 只看 summary 漏掉

若 monitor 要補上 per-entity-type health diff，再接著產：

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

補完後的 `monitor.json` 會同時包含：
- MCP traffic 摘要
- L2 / L3 document / task / blindspot 的 health summary
- findings（可直接給 orchestrator 做 fix 決策）

另外 monitor 必須同步看：
- `analyze(check_type="invalid_documents")`
- 若出現 `current_formal_entry_missing_delivery_snapshot` 或 `current_formal_entry_stale_delivery_snapshot`
  - 一律記為 **delivery/auth path friction**
  - 不可誤判成 **L3 routing failure**
  - 這代表 current formal-entry 文件的 full-content delivery coverage 不完整
- 若 controlled replay 之後已有 `source-repair-queue.json`
  - monitor 也必須把這批 `SOURCE_NOT_FOUND` 收進 `health.source_governance`
  - 這一類一律記為 **source governance friction**
- 若已有 `check_github_delivery_secret.py` 的 JSON 結果
  - monitor 也必須寫入 `health.delivery_auth`
  - 若 `status="rejected"` 且 `error="INVALID_GITHUB_TOKEN"`，一律記為 **delivery/auth blocker**

若要把這批 live issue 直接收成 repair queue，再跑：

```bash
python3 scripts/dogfood/build_snapshot_repair_queue.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --invalid-documents-json <analyze-invalid-documents-output.json>
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/snapshot-repair-queue.json`

用途：
- 列出哪些 current formal-entry 文件需要 `POST /api/docs/{docId}/publish`
- 區分 `missing` vs `stale` snapshot coverage

若要做受控 repair replay，再跑：

```bash
python3 scripts/dogfood/apply_snapshot_repair_queue.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --queue-json /tmp/zenos-dogfood/{DF-ID}/snapshot-repair-queue.json \
  --partner-id <workspace-or-partner-id>
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/snapshot-repair-results.json`

若 controlled replay 命中 `SOURCE_NOT_FOUND`，再把這批 issue 收成 source repair queue：

```bash
python3 scripts/dogfood/build_source_repair_queue.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --repair-results-json /tmp/zenos-dogfood/{DF-ID}/snapshot-repair-results.json
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json`

用途：
- 把「缺 snapshot」再往下切成「source URI 漂移 / 失效」的正式 repair artifact
- 若有 `alternative_uris`，交給下一輪 analyzer / governance review 做 source drift 判讀
- 這一類一律記為 **source governance friction**，不是 **L3 routing failure**

若要把這批 source governance friction 直接整理成下一輪 fixer 的 task 草稿，再跑：

```bash
python3 scripts/dogfood/build_governance_review_task_draft.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --source-repair-queue-json /tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json \
  --product-id {PRODUCT_ID}
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/governance-review-task-drafts.json`

用途：
- 把 raw queue 轉成 graph-first 的治理 review task 草稿
- 讓下一輪 fixer / architect 不必人工重組 task title / description / AC

若要正式產出修前/修後 delta，再跑：

```bash
python3 scripts/dogfood/build_iteration_delta.py \
  --df-id DF-{YYYYMMDD}-{N} \
  --before-monitor /tmp/zenos-dogfood/<before-df-id>/monitor.json \
  --before-producer /tmp/zenos-dogfood/<before-df-id>/producer.jsonl \
  --after-monitor /tmp/zenos-dogfood/<after-df-id>/monitor.json \
  --after-producer /tmp/zenos-dogfood/<after-df-id>/producer.jsonl
```

輸出：
- `/tmp/zenos-dogfood/{DF-ID}/delta.json`

用途：
- 給 Architect 比較修前/修後 `calls`
- 比較 `reject_rate`
- 比較 `hit_rate`
- 比較 `full-scan ratio`
- 比較 `health.invalid_documents`（snapshot coverage）
- 比較 `health.source_governance`（`SOURCE_NOT_FOUND`）
- 比較 `health.delivery_auth`（`INVALID_GITHUB_TOKEN`）
- 若總 token 被 session 固定成本稀釋，補看 `payload_bytes.total_result_bytes / search_result_bytes / read_source_result_bytes`

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

用途：
- 給 orchestrator 挑 replayable producer scenario
- 統計 capture topic 分布、avg tokens、avg outputs
- 找出高頻 friction 熱區

---

### Step 0.5：Clean-Room Session Gate（必守）

dogfooding producer agent 的 context window 必須乾淨，避免沿用上次 dogfood 的偏見。

硬規則：
- **producer subagent 必須新開**，不得沿用上一輪 dogfood transcript
- 若本輪修補包含 **MCP tool contract / parameter schema** 變更（例如新增 `preview_chars`）：
  - **verifier 必須用新的 top-level chat session 重跑**
  - 同一個聊天內只重開 subagent 不算，因為 connector/tool schema 可能還沒刷新
  - 若 transcript 顯示 tool call 沒帶新參數，這一輪只能記為 **schema freshness blocker**，不得宣稱已驗到新 contract
- producer prompt 只給：
  - 本輪 scenario
  - `PRODUCT_ID` / `PRODUCT_NAME`
  - 允許使用的 skill / MCP
  - `Context Happy Path`
  - 本輪要驗證的假設（最多 3 條）
- 預設最小讀取集合：
  - producer / verifier 只讀這份 `/dogfood` workflow
  - 不要預載 `bootstrap-protocol.md`、`document-governance.md` 全文
  - 只有在定位 document routing 規則錯誤時，才額外加讀治理文件
- **不得**把上一輪完整追蹤表、長篇錯誤分析、舊 transcript 原文灌進 producer context
- 若需要比較修前/修後，只允許 monitor / orchestrator 保留比較資料；producer 仍保持 clean-room

理由：
- token 成本不能先被 pre-read 吃掉
- 否則 dogfood 量到的是治理文件載入成本，不是 graph-first retrieval 成本

### Deploy Gate（delivery health）

若本輪修補包含 MCP runtime deploy，部署後除了 revision / traffic 外，還必須驗：

```bash
python3 scripts/check_github_delivery_secret.py \
  --project-id zenos-naruvia \
  --secret-name github-token
```

判讀：
- `status="ok"`：GitHub direct delivery path 可用
- `status="rejected"` 且 `error="INVALID_GITHUB_TOKEN"`：記為 **delivery/auth blocker**
- 此時不要再把 `read_source -> summary_fallback` 誤判為 routing 問題

預設取樣上限：
- `search(collection="entities", ...)` 預設 `limit<=5`
- `search(collection="documents", entity_name=...)` 預設 `limit<=3`
- 若 producer / verifier 抓超過 `3` 筆，需明說原因

產品 scope（已知時必帶）：
- 若 scenario 已知產品名稱，先 resolve `PRODUCT_ID`
- 後續 `recent_updates`、`search(collection="entities", ...)`、`search(collection="documents", entity_name=...)`
  都必須帶同一個 `product_id`
- 否則容易被 workspace 內其他 L1/L2 噪音拉歪 seed entity

最小 prompt 骨架：

```text
你是本輪 dogfood producer。這是全新 session，不要假設知道任何上一輪內容。
你的目標：用最少 MCP calls 完成指定 scenario，並記錄每一步為什麼成功/失敗。
Context 載入順序只能走：recent_updates -> tasks -> L2 entity -> L3 documents -> read_source。
若你開始用 keyword search 做 coverage audit，視為本輪失敗。
`read_source` 預設先用 `preview_chars=1200`；只有 preview 不足，才升級成 full read。
```

---

### Step 0.6：Subagent 拆分（建議預設）

同一輪 dogfooding，至少拆成以下 4 個子角色：

1. **Producer subagent**
   - 用乾淨 context 真跑 scenario
   - 不讀舊 dogfood transcript
2. **Monitor subagent**
   - 收集 MCP calls / reject rate / tool sequence / token hot spots
   - 對照預期 graph-first path 是否被遵守
3. **Fixer subagent**
   - 只根據 monitor findings 改 skill / runtime / tests
   - 不直接修 ontology data
4. **Verifier subagent**
   - 用另一個乾淨 session 重跑同 scenario
   - 預設沿用同一套最小讀取集合，不預載長篇治理文件
   - 判斷修後是否真的改善，而不是只在原 session 剛好成功
   - 若 fix 牽涉 MCP tool schema，Verifier 必須改成 **新的 top-level session**，不能只在同聊天重開 subagent

若只有 1 個 agent 從頭做到尾，容易把「學到的 workaround」帶進下一次測試，dogfood 失真。

對應到 repo 現有角色：
- **Planner / Orchestrator** = Architect
- **Producer / Fixer** = Developer
- **Verifier** = QA
- **Monitor** = dogfood workflow + governance-loop gates + reject-rate scanner

除非有充分理由，不要額外發明第五種常駐角色；先沿用現有 `Architect -> Developer -> QA -> Architect` 閉環。

---

### Step 1：環境確認

```python
# 確認 MCP 可用
mcp__zenos__search(query="test", collection="entities")
```

- 若失敗 → 記錄「MCP 不可用」，中止並回報。
- 若成功 → 記錄回傳格式是否符合 `{status, data, warnings, ...}`。

---

### Step 1.5：L3 Graph Retrieval Gate（必測）

先驗證 L3 文件入口是不是走知識圖譜，而不是退化成全文亂搜。

```python
# 1. 先找最相關 L2
mcp__zenos__search(
    collection="entities",
    query="{模組或主題}",
    entity_level="L2",
    include=["summary"],
    product_id="{PRODUCT_ID}",
    limit=5
)

# 2. 再從 L2 枚舉其 L3 documents
mcp__zenos__search(
    collection="documents",
    entity_name="{最相關 L2}",
    include=["summary_compact"],
    product_id="{PRODUCT_ID}",
    limit=3
)
mcp__zenos__read_source(
    doc_id="{DOC_ID}",
    source_id="{SOURCE_ID}",
    preview_chars=1200
)
```

評估點：
- 是否能在 **2-3 個 MCP calls** 內定位正確 doc bundle？
- `summary` / `change_summary` / `bundle_highlights` 是否足夠讓 agent 決定下一步要讀哪個 source？
- `read_source` preview 是否已足夠支撐判斷；若不夠，再升級成 full read
- 若為了做「覆蓋率 / 存在性清查」而改用 `search(query="關鍵字", collection="documents")`，直接記為 **L3 retrieval failure**。
- 若 `search(documents)` 已回到正確 L3 bundle，且 `primary_source` / `source_count` 合理，但 `read_source` 回 `document_summary` fallback：
  - 先記為 **source delivery degraded**
  - 不要直接判成 **L3 routing failure**
  - 尤其當 `setup_hint` 指向 GitHub token / repo 權限 / delivery snapshot 時，應把問題歸類在 **delivery/auth path**，不是 graph-first path 本身

硬規則：
- **keyword search 只能做 discovery，不可拿來做完整覆蓋率、存在性清查或 bundle 枚舉。**
- **coverage audit 必須從 L2 開始，用 `entity_name` 拉 documents。**
- 若 agent 需要逐一打開大量本地 MD 才知道 bundle 裡有什麼，記為 **L3 bundle routing 失效**，不得判定 dogfood 通過。

---

### Step 2：去重搜尋（Task 治理鏈起點）

讀取 `skills/governance/task-governance.md` 開頭的建票前去重規則。

```python
mcp__zenos__search(
    query="dogfood 評估測試任務",
    collection="tasks",
    status="todo,in_progress,review"
)
```

評估點：
- 搜尋指令是否清楚？（status 過濾參數格式對不對）
- 有沒有既有重複票？

---

### Step 2.5：Graph-Assisted Ticketing Gate（必測）

開票前，先驗證 agent 能不能靠知識圖譜補齊 ticket context，而不是全文亂搜後自己猜。

```python
# 1. 找最相關的 L2 / L3
mcp__zenos__search(
    collection="entities",
    query="{任務主題}",
    entity_level="all",
    include=["summary"]
)

# 2. 讀主要 L2 的 relationships / entries
mcp__zenos__get(
    collection="entities",
    name="{最相關 L2}",
    include=["summary", "relationships", "entries"]
)

# 3. 從 L2 找 L3 文件入口
mcp__zenos__search(
    collection="documents",
    entity_name="{最相關 L2}",
    include=["summary"],
    limit=10
)
```

評估點：
- ticket description / acceptance criteria 是否反映主要 impacts 與受影響模組？
- `linked_entities` 是否來自真正相關的 L2 / L3，而不是隨便關鍵字命中？
- 是否避免為了開票去做全量文件搜尋？

失敗條件：
- 票只描述局部改動，完全沒提到 impacts chain 指向的下游模組
- 為了補 ticket context 直接做 `search(collection="documents", query="...")` 全域亂搜
- `linked_entities` 只是手感亂掛，和 description / AC 沒有對應

---

### Step 3：找 linked_entities 的 entity ID

```python
mcp__zenos__search(query="ZenOS 治理", collection="entities")
```

- 記錄：是否找到合理的 entity 可掛？
- 記錄：search 回傳結構是否讓人容易取出 ID？（`data[0].id` vs 其他路徑）

---

### Step 4：建立測試 Task

依照 `skills/governance/task-governance.md` 建票規範，用以下最小合規資料建一張測試票：

```python
mcp__zenos__task(
    action="create",
    title="驗證治理流程端到端可用性",
    description="這是 dogfood 評估用的測試任務。背景：需要確認治理鏈完整可跑。問題：目前無自動驗證機制。期望結果：確認 create→update→review→confirm 全程無異常。",
    acceptance_criteria=[
        "task 建立成功，回傳有效 task ID",
        "update(status=in_progress) 成功",
        "handoff(to_dispatcher=agent:qa) 後 task 自動進入 review",
        "confirm(accepted=True) 成功，任務進入 done"
    ],
    linked_entities=["<Step 3 找到的 entity ID>"],
    product_id="<測試 L1 ID>"
)
```

評估點：
- title 不要用 `Task to ...` / `This task ...` / `這個任務 ...` 這類前綴。
- `linked_entities` 盡量至少帶 1 個測試 L1 底下 entity；若真的找不到，記錄 warning，但不要亂掛正式資料。
- 回傳的 `data.id` 路徑是否直觀？
- `warnings` 或 `suggestions` 有無有用資訊？
- 若不是在某個既有 plan 底下，不要亂帶 `plan_id`。

**記錄重試次數**：如果第一次 call 被 reject，記錄原因後修正重送。

---

### Step 5：更新狀態 → in_progress

```python
mcp__zenos__task(
    action="update",
    id="<Step 4 取得的 task ID>",
    status="in_progress"
)
```

評估點：
- 是否需要額外欄位？
- 回傳格式是否一致？

---

### Step 6：Developer → QA handoff（server 自動升 review）

```python
mcp__zenos__task(
    action="handoff",
    id="<task ID>",
    to_dispatcher="agent:qa",
    reason="dogfood execution complete",
    output_ref="dogfood-run",
    notes="Dogfood 執行完成。已驗證 create/update/handoff 流程可跑。"
)
```

評估點：
- `to_dispatcher=agent:qa` 且 task 目前為 `in_progress` 時，server 是否自動升為 `review`？
- handoff 回傳中有沒有有用的 next step 提示？

---

### Step 7：Confirm 驗收

```python
mcp__zenos__confirm(
    collection="tasks",
    id="<task ID>",
    accepted=True
)
```

評估點：
- 只能在 task 已是 `review` 狀態時呼叫 confirm。
- `result` 要在進入 review 前就寫入 task，不是 confirm 時再帶。
- confirm 回傳的 `governance_hints.suggested_entity_updates` 有無內容？
- 若 linked_entities 為空，hints 是否還有意義？

---

### Step 7.5：MCP Reject Rate Gate（每次 iteration 結束前執行）

```bash
python3 scripts/dogfood/scan_mcp_reject_rate.py \
  --transcripts-dir ~/.claude/projects/<project-slug>/ \
  --format markdown
```

判斷標準：
- **reject rate ≤ 5%**：正常，繼續
- **reject rate > 5%**：必須寫進 iteration report，分析原因
- **top_rejection_reasons 出現新類別**：必須寫進 iteration report，評估是否需要 skill 更新

若 reject-rate 超標或出現新 rejection 類別，**不得跳過**直接進下一輪——先在追蹤表記錄，再決定是立即修復還是列入 backlog。

---

### Step 7.6：閉環驗證 Gate（必守）

一輪 dogfood 只有在以下 4 步都完成後，才算結束：

1. **Producer** 找到真問題
2. **Fixer** 改 skill / runtime / tests
3. **Verifier** 用全新 session 重跑同 scenario
4. **Monitor** 比較修前/修後差異

最少要回收這些證據：
- 修前 MCP call 序列
- 修後 MCP call 序列
- 修前/修後 reject rate 或 top rejection bucket
- 修前/修後是否仍需 keyword search / full scan
- 修前/修後是否能在 2-3 個 calls 內命中正確 L3 bundle
- 修前/修後 `usage.total_tokens`、`cache_read_input_tokens`、`payload_bytes.total_result_bytes` 是否低於本輪 `token_budget`

若只有「已修改檔案」但沒有 verifier 重跑證據，不算閉環。
若 token gate 沒有明確通過，即使 routing 和 reject rate 都正常，也只能判定 PARTIAL。

---

### Step 8：Skill 肥大分析（靜態）

不呼叫 MCP，直接分析 skill 檔案大小：

```bash
wc -l skills/governance/*.md skills/workflows/*.md .claude/skills/*/index.md 2>/dev/null | sort -rn | head -20
```

評估標準：
- **≤ 80 行**：合理
- **81–150 行**：偏長，考慮抽出子規則
- **> 150 行**：肥大，需要拆分或提取摘要版

同時用 Grep 找重複內容：

```bash
# 找在兩個以上文件都出現的段落
grep -l "建票前去重\|去重\|linked_entities 不存在" skills/governance/*.md skills/workflows/*.md
```

記錄哪些規則在多個 skill 裡重複出現。

---

### Step 9：輸出評估報告

```
══════════════════════════════════════════════
  ZenOS 治理流程 Dogfooding 評估報告
══════════════════════════════════════════════

## 執行摘要
  - 測試日期：{date}
  - 完整鏈測試：PASS / PARTIAL / FAIL
  - 總重試次數：{n}

## 步驟追蹤表
| 步驟 | 操作 | 結果 | 重試次數 | 問題描述 |
|------|------|------|---------|---------|
| Step 1 | MCP 環境確認 | ... | ... | ... |
| Step 1.5 | L3 Graph Retrieval Gate | ... | ... | ... |
| Step 2 | 去重搜尋 | ... | ... | ... |
| Step 3 | Entity 搜尋 | ... | ... | ... |
| Step 4 | Task 建立 | ... | ... | ... |
| Step 5 | → in_progress | ... | ... | ... |
| Step 6 | → review | ... | ... | ... |
| Step 7 | confirm | ... | ... | ... |

## 摩擦點清單（卡住或需修正的地方）
{按嚴重程度排列}

## Skill 肥大報告
| 檔案 | 行數 | 評級 | 重複內容 |
|------|------|------|---------|
| task-governance.md | ... | ... | ... |
| governance-loop.md | ... | ... | ... |
| ... | ... | ... | ... |

## 回傳格式一致性
  - 統一格式符合率：{n}/{total} 個 call
  - 不符合項目：{list}

## 具體改善建議
1. {最高優先：直接影響 agent 操作的問題}
2. {次優先：skill 結構或重複問題}
3. {長期：架構層級的改善}

## 閉環驗證
  - Producer（修前）: {主要失敗點}
  - Fixer: {改了哪些 skill/runtime/test}
  - Verifier（修後）: {是否改善}
  - Delta: {calls / rejects / token / path}

══════════════════════════════════════════════
```

---

## 評估後的後續動作

若發現問題，**不要直接在本 skill 裡修改 governance 規則**。
問題應該：
1. 先記到 dogfood plan / task result，保留可追蹤的觀察與驗收結果
2. 若需要修改 SSOT skill → 直接改 `skills/release/` 與對應治理 SSOT，再跑同步
3. 只有跨 session 仍需要接續、且不適合放 task/result 時，才寫 `journal_write`
4. 若是緊急 workaround → 在本 `skills/workflows/` 下建立臨時補丁 skill，標注 `[TEMP]`

---

## 注意事項

- 本 skill 建立的測試任務標題會以 `[DOGFOOD]` 開頭，評估後應手動 cancel
- 本 skill 是 **project-local**，不屬於 SSOT，不需要部署或同步
- 若 MCP 連線失敗，仍可執行 Step 8（Skill 肥大分析）並輸出部分報告
