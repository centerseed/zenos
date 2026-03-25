# ZenOS 治理路徑總覽

## 目的

這份文件用來收斂 ZenOS 目前有哪些治理路徑、各自在哪一層生效，以及哪些路徑會消耗 LLM。
重點不是列功能清單，而是回答三個問題：

1. 哪裡在做治理判斷？
2. 哪條治理路徑最重？
3. 哪些路徑適合高頻跑，哪些應該節制？

---

## 一張圖看治理路徑

| 路徑 | 入口 | 主要責任 | 是否打 LLM | 重量 |
|------|------|----------|-------------|------|
| Skill 層治理 | `/zenos-capture`、`/zenos-sync` | 編排流程、選文件、決定何時呼叫 MCP | 視 skill workflow 而定 | 重 |
| Write Path 治理 | `write()`、`task(create)` | 寫入前後的硬驗證、自動推斷、L2 hard gate | 有些會 | 中到重 |
| Analyze Path 治理 | `analyze()` | 品質檢查、過時檢查、盲點分析、backfill proposal | 目前不會 | 輕 |
| Confirm Path 治理 | `confirm()` | 人確認 draft / 任務驗收後生效 | 不會 | 輕 |

---

## 1. Skill 層治理

### `/zenos-capture`

用途：首次建構或從對話 / 單一文件捕獲知識。

責任：
- 掃描檔案並分級
- 在高價值情境下先做全局理解，再決定要寫哪些 entity / document / relationship
- 控制寫入節奏，而不是把所有判斷都丟給 server

特性：
- 這是最重的一條治理路徑，因為它通常要讀很多檔案
- 若 skill 已經知道 `type`、`parent_id`、`linked_entity_ids`，就應直接帶進 MCP，降低 server 端額外推斷

### `/zenos-sync`

用途：增量同步已有 ontology 的專案。

責任：
- 看 git 變更
- 篩掉噪音
- 判斷哪些變更值得進 ontology
- 決定是更新神經層、還是形成骨架層 proposal

特性：
- 比 `capture` 輕，因為它是增量
- 最理想的做法不是逐檔盲寫，而是先看 `analyze()` 產出的修補 proposal，再做少量精準 write

---

## 2. Write Path 治理

Write path 是 ZenOS 最核心的治理裁判。Skill 可以很聰明，但最後是否准寫、如何補推斷，還是由 server 決定。

### `write(collection="entities")`

治理內容：
- 名稱、type、status、tags、parent_id 的硬驗證
- L3 的 parent auto-infer
- 新 L2/module 的 hard gate：沒有 concrete impacts 就不准升成 L2
- 可選的 GovernanceAI 關聯推斷與 doc link 推斷

LLM 成本：
- 若 caller 沒給 `type`：最多 1 次 `infer_all`
- 若是新建 L2/module：再 1 次 `infer_all` 做 hard gate
- 存完後若要自動補 rel / doc link：再 0-1 次 `infer_all`

實務觀察：
- 完整資料寫入時：0-1 次
- 缺很多欄位又要升 L2 時：2-3 次

### `write(collection="documents")`

治理內容：
- `source.type`、`linked_entity_ids`、查重
- 若 caller 沒帶 `linked_entity_ids`，才會啟動自動推斷

LLM 成本：
- 0 或 1 次 `infer_doc_entities`

### `task(action="create")`

治理內容：
- 初始狀態驗證
- priority recommendation
- context_summary 組裝
- 若 caller 沒帶 `linked_entities`，則自動推斷 task 關聯

LLM 成本：
- 0 或 1 次 `infer_task_links`

### `task(action="update")`

治理內容：
- 狀態轉換驗證
- blocked / review / done 的規則
- 級聯解阻塞

LLM 成本：
- 0 次

---

## 3. Analyze Path 治理

`analyze()` 是最適合高頻跑的治理路徑，因為它目前主要是規則計算，不靠 LLM。

### `analyze(check_type="quality")`

治理內容：
- ontology 品質分數
- L2 可讀性、粒度、impacts 覆蓋率
- `l2_impacts_repairs`
- `l2_backfill_proposals`

### `analyze(check_type="staleness")`

治理內容：
- 找過時文件或結構落後

### `analyze(check_type="blindspot")`

治理內容：
- 推斷知識缺口

### `analyze(check_type="all")`

治理內容：
- 一次性輸出 quality / staleness / blindspots / KPI / repair proposals

特性：
- 很適合被 `/zenos-sync` 或治理 review 高頻使用
- 現在連 backfill proposal 都是在這層生成，所以它已不只是「看報表」，而是「產治理修補候選」

---

## 4. Confirm Path 治理

`confirm()` 是 ZenOS 的最後一道治理門。

治理內容：
- draft entity / protocol / blindspot 的確認
- review task 的驗收或打回

特性：
- 不打 LLM
- 是 AI draft 真正生效的分界線
- 這條路徑本身很輕，但對治理品質最重要

---

## 哪些路徑真的重

真正可能變重的只有三類：

1. `zenos-capture`
2. `write(collection="entities")`
3. `task(action="create")` 或 `write(collection="documents")` 在 caller 沒補足連結資訊時

其餘大部分 MCP function 都偏輕：
- `search`
- `get`
- `read_source`
- `confirm`
- `analyze`
- `task(update)`

---

## 目前最合理的治理策略

### 首次建構

用 `/zenos-capture`，允許比較重，但 skill 應盡量自己先全局理解，不要把每個欄位都丟給 write path 猜。

### 增量同步

用 `/zenos-sync` + `analyze()`：
- 先看 `analyze()` 的 repair / backfill proposal
- 再做少量精準 write
- 避免逐檔盲寫造成 LLM 重複消耗

### 日常治理

高頻跑 `analyze()`，低頻做 `confirm()` 與精準修補。

這樣能把重路徑留在「真正需要建立或重構知識」的時候，而不是每次更新都付出同樣成本。

---

## 結論

ZenOS 現在不是只有一條治理路徑，而是四條分工明確的治理路徑：
- Skill 層負責編排
- Write Path 負責硬治理與必要推斷
- Analyze Path 負責持續檢查與 backfill proposal
- Confirm Path 負責最後生效

如果要控制 LLM 成本，重點不是砍掉治理，而是把重判斷集中在：
- `/zenos-capture` 的全局建構
- 少量必要的 `write()` 推斷

並讓 `analyze()` 承擔高頻治理與存量修補發現。
