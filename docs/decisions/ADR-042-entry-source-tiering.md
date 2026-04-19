---
type: ADR
id: ADR-042
status: Proposed
ontology_entity: 語意治理 Pipeline
created: 2026-04-19
related:
  - docs/decisions/ADR-010-entity-entries.md
  - docs/decisions/ADR-014-journal-entry-distillation.md
  - docs/specs/SPEC-entry-distillation-quality.md
  - docs/specs/SPEC-entry-consolidation-skill.md
  - docs/plans/HANDOFF-2026-04-19-entry-governance-findings.md
---

# ADR-042: Entry Source Tiering — 依輸入訊號層級決定治理路徑

## Decision

**Entry 的寫入路徑由「輸入訊號的抽象層級」決定，而非由觸發方式（事件 vs 萃取）決定。**

具體：

1. Entry 必須宣告 `source_type`（DB 欄位 + MCP write 強制）。
2. 依 source_type 分為 **Tier 1 / Tier 2 / Tier 3** 三層，對應不同治理路徑。
3. Tier 1 來源自動 `active` 寫入；Tier 2 來源寫入 `review-needed` 狀態等待人確認；Tier 3 來源 **禁止** 寫入 entries，改走 L3 document / staleness / blindspot。
4. `zenos-sync` 從 entry 寫入路徑中**完全移除**（本質違反 ADR-010）。
5. `zenos-capture` 重新定位為「偵測決策訊號，引導用戶登記到正確來源」，不直接萃取低層對話為 entry。

## Context

### 2026-04-19 實證觸發

對「訓練計畫系統」entity 做手動稽核，53 active entries 中 10 條判定為退化 entry 並 archive。詳見 `docs/plans/HANDOFF-2026-04-19-entry-governance-findings.md`。

退化模式高度集中於：純 code path trace、實作細節、bug fix commit log、transient debug noise、短壽 supersede 鏈。這些全都可以追回到兩條輸入來源：

- `zenos-sync` 從 git log / commit diff 萃取
- `zenos-capture` 從對話 log 萃取

### 根本診斷

原先框架是「品質規則放哪裡」——skill prompt、server gate、analyze 工具。但這個框架預設「萃取精度是瓶頸」，實證不成立。

**真正的瓶頸是輸入訊號的抽象層級**：

| 輸入源 | 層級 | 天然 entry 品質 |
|---|---|---|
| ADR §Decision 區塊 | 高 | 高 |
| Task done 時人寫的 reflection | 高 | 高 |
| Spec 轉 accepted 的 confirmation | 高 | 高 |
| 會議結論紀錄 | 中-高 | 中-高 |
| 對話 log（debug / 實作討論） | 低 | 低 |
| Git commit diff | 極低 | 極低 |

對話和 git diff 本質是**執行層素材**。無論 prompt 多精、LLM 多強，執行層素材萃取不出決策層知識——這是米和飯的關係，不是烹飪技術問題。

### ADR-010 的原意被稀釋

ADR-010 §治理規則「skill 引導」明寫：

> - 這條知識是不是 code 裡已經有的？→ 有就不記
> - 100 字能不能講清楚？→ 不能就拆成多條，或者代表粒度太大

但 `zenos-sync` 的輸入**就是** git log — 它的整個存在前提就是記錄 code / git history 裡的變化。把它接到 entry 寫入路徑，等於從產品設計層面違反 ADR-010。

### 為什麼不是「事件驅動 vs 萃取驅動」

第一輪框架提過「entry 應該是事件驅動」。用戶反駁：capture/sync 被呼叫本身就是事件，「事件驅動」這個詞區分不出問題。

挑戰成立。真正的分類維度是**觸發時輸入訊號的層級**，不是觸發方式。ADR 寫入也可以當成事件，但它之所以產出好 entry，不是因為「它是事件」，而是因為它的 payload 已經是決策層內容。

## Source Tiers 定義

### Tier 1 — 高層決策事件（自動 active）

已被明確登記為決策的場合。Entry 在此產出時，輸入訊號已經過人類有意識的抽象化。

**來源**：
- ADR create / status 轉 Accepted（從 §Decision / §Consequences 區塊萃取）
- Task `confirm(accepted=True)` 時附帶的 `entity_entries`（現有機制，continue）
- Spec status 轉 Accepted（從 §Acceptance Criteria / §Decision 區塊萃取）
- 明確標記為「決策紀錄」的會議摘要（`journal_write(flow_type="decision_log")`）

**治理行為**：
- `status="active"` 直接寫入
- `source_type` 欄位記錄來源（`adr` / `task_done` / `spec_accepted` / `decision_log`）
- `source_ref` 欄位記錄來源 ID（ADR id / task id / spec id / journal id）

### Tier 2 — 中層反思事件（review-needed）

人在反思、但反思尚未被登記為正式決策的場合。Entry 候選在此產出時，需要人確認是否值得固化。

**來源**：
- 用戶明確說「記一條這個」觸發的 capture（顯式 opt-in）
- Task reflection 但未帶 entity_entries 時的 LLM 候選萃取
- Retrospective / post-mortem 類 journal

**治理行為**：
- 新增 `status="review-needed"`（需要 server 端 enum 擴充）
- 候選進 review 池，TTL 7 天自動 archive
- 用戶 confirm → 轉 active；reject 或過期 → archived(reason=manual)

### Tier 3 — 低層素材（禁止寫入 entries）

執行層素材，無論觸發方式為何，禁止產出 entry。改走其他知識層。

**來源**：
- Git log / commit diff（sync 本質來源）
- 自動萃取的對話 log（capture 目前的主要路徑）
- Code file diff

**治理行為**：
- MCP `write(collection="entries")` 收到 Tier 3 source_type 時 `reject`
- 改走：
  - 概念層變更 → 更新 L2 entity summary
  - 文件有更新 → 更新 L3 document pointer + mark stale
  - 發現新問題 → 建 blindspot
  - 有待處理動作 → 建 task

## Schema 變更

```sql
ALTER TABLE zenos.entity_entries
  ADD COLUMN source_type text NOT NULL DEFAULT 'legacy',
  ADD COLUMN source_ref text,
  ADD CONSTRAINT chk_entry_source_type CHECK (
    source_type IN (
      'adr', 'task_done', 'spec_accepted', 'decision_log',  -- Tier 1
      'user_explicit', 'task_reflection', 'retrospective',   -- Tier 2
      'legacy'                                               -- migration
    )
  );

-- status enum 擴充
ALTER TABLE zenos.entity_entries
  DROP CONSTRAINT chk_entry_status,
  ADD CONSTRAINT chk_entry_status CHECK (
    status IN ('active', 'review-needed', 'superseded', 'archived')
  );

CREATE INDEX idx_entries_review_needed
  ON zenos.entity_entries(partner_id, created_at)
  WHERE status = 'review-needed';
```

**Migration 策略**：既有 52 個 partner 的 entries 全部 `source_type='legacy'`，不影響現有行為。新寫入強制 Tier 分流。

## MCP 介面變更

### `write(collection="entries")`

- 新增必填欄位：`source_type`
- Tier 1 source_type：正常寫入 `status="active"`
- Tier 2 source_type：強制 `status="review-needed"`，即使 caller 傳 active 也改寫
- Tier 3 source_type：`status="rejected"` + suggestion 引導走其他層

### 新增 `confirm(collection="entries", id=..., accept=True)`

review-needed → active 的轉換入口。已有 confirm tool 擴充 collection 支援即可。

### `search(collection="entries")`

- 新增 filter：`tier=1|2|3`、`source_type=...`
- Default 排除 `review-needed` 除非 `status="review-needed"` 明指

## Skill 變更

### `zenos-sync`

- **移除所有 entry 寫入能力**（今天 SKILL.md 已口頭宣告「不主動產出 entries」，本 ADR 落實為實作層移除）
- Sync 遇到疑似決策訊號 → `journal_write(flow_type="decision_signal", context=...)` 留給 capture 接手

### `zenos-capture`

**核心轉變**：從「skill 決定什麼是知識並自動寫入」改為「skill 偵測決策訊號，user 決定登記處」。

抽象化動作（把執行層素材提煉為決策層知識）本質上只有 user 能做，skill 能做的只是摘要。過去的 zero-friction 設計讓 skill 能寫就寫，是 entry 品質差的主因。新 capture 加入**刻意的摩擦**，讓低價值候選在 user 選擇「不是決策」時自然過濾掉。

#### 引導式互動 flow

```
user: /zenos-capture

skill: [讀對話 / journal / task result]
       [偵測決策訊號：架構選擇、tradeoff、限制發現、概念定義變更]
       [不自動寫 entry]

skill → user:
  「對話裡偵測到 N 個疑似決策訊號：

   1. <訊號摘要>
   2. <訊號摘要>
   ...

   每個訊號請選擇登記路徑：
     A) 已涵蓋於既有 ADR/spec → 無需另記（skill 出示最相似 ADR id）
     B) 這是新決策 → 引導寫 ADR，accept 後 Tier 1 自動產 entry
     C) 這是已完成的 task reflection → 引導 confirm(task, entity_entries=...)
     D) 這是反思、尚未收斂 → Tier 2 review-needed
     E) 不是決策，是實作筆記/待辦 → 改建 task 或更新 L3 doc/blindspot
     F) 不是知識，跳過」

user: [逐條選 A-F，或一次批次選擇]

skill: [按選擇執行對應路徑]
       - B → open ADR template，user 填完 → write(ADR) → accept 時 Tier 1 entry
       - C → write(entries) via confirm(task), source_type=task_done
       - D → write(entries, source_type=user_explicit, status=review-needed)
       - E → write(task / document / blindspot), 不走 entries
       - F → 無動作
       - A → 無動作，記在 journal「已識別但已存在」
```

#### 輕量模式（降低 UX 負擔）

若訊號數量多（如 compressed journal 觸發場景），skill 改為**批次提案模式**：

```
skill: 偵測到 15 個候選訊號。已自動分類：
  - Tier 1 候選（你有 task done 引用）：3 條
  - Tier 2 候選（需你確認）：5 條
  - 建議走 L3 document：4 條
  - 建議跳過（實作細節）：3 條

  要逐條檢視 / 批次 confirm Tier 2 全部 / 或只處理 Tier 1？
```

用戶可一鍵 confirm 整批 Tier 2 進 review-needed（寫入成本低，錯了 7 天後自動過期），或只精挑 Tier 1。

#### Anti-pattern 防護

新 capture 仍會在每個候選帶 ADR-010 / capture-governance.md 的 9 類 anti-pattern 檢查，但**不在 skill 側強制 reject**——只作為 hint 標在候選旁：

```
候選 3：「_extract_types 遞迴解析必須處理 dict 和 string」
  ⚠️ anti-pattern 命中：實作細節 + 函式內行為
  建議：E（改為 task 或跳過）
```

Anti-pattern 命中的候選預設建議走 E / F，但 user 仍可覆蓋選 D。最終決定權在 user。

#### compressed journal 觸發

當 `journal_write` 回傳 `compressed: true`（ADR-014）時，capture 自動跑一次批次提案模式，**不自動寫 entry**——summary journal 本身是 Tier 2 級素材（中抽象層），需要 user 確認才能升 active。

這改變了 ADR-014 原本「壓縮自動蒸餾為 entry」的隱含行為，需要 ADR-014 標記為 superseded-by-this 或更新 §蒸餾觸發定義。

### `zenos-governance`

- §6 Entry 手動稽核 protocol 新增 `source_type` 稽核維度
- 低品質 entry 追溯來源：Tier 3 直接 archive；Tier 2 review-needed 過期 archive；Tier 1 走 supersede 鏈

## 考慮過的替代方案

### 方案 A：Server-side LLM quality gate

在 `write(entries)` 時跑 LLM 品質檢查，reject 低品質 entry。

**否決原因**：
- 每次 write 加 LLM call，寫入路徑延遲 / 成本全面惡化
- 「品質」LLM 判斷主觀，agent 會學會 game check（寫短句、加抽象詞）
- 不解根因：低層素材就算過 gate 也只是「通順的低品質 entry」
- 即使配合本 ADR，Tier 3 在 server 層已 reject，Tier 1 素材本身就高品質，LLM gate 沒有發力空間

### 方案 B：不分 Tier，純粹加強 capture prompt

只改 `capture-governance.md` anti-pattern 說明，不改 schema / MCP。

**否決原因**：
- 今天的 HANDOFF 已經證明 anti-pattern 說明在 prompt 文字，runtime 零強制
- `zenos-sync` 的反向選擇問題無解——輸入本質就是 git log
- 不做 schema 變更就無法在 DB 層看出「這 entry 從哪來」，未來 audit 工具無處著力

### 方案 C：取消 entry，全部走 journal + L3 document

激進方案：entry 本質就是 L3 document 的 fine-grained 版本，可以統一。

**否決原因**：
- ADR-010 的 Palantir 類比成立——entity 需要 time series 層，不只是 document pointer
- Task done 回寫 entries 已在實作中 work，取消會破壞現有機制
- 真正壞的只有 Tier 3 來源，不是 entry 這個概念

## Consequences

### 正面

- Entry 品質從源頭管控，不再依賴 skill prompt 自覺
- `zenos-sync` 不再強行產出違反 ADR-010 的 entry
- Entry source 在 DB 可追溯，未來 audit / analyze 可按 tier / source_type 切片
- Task-done 回寫路徑（現有 Tier 1）不變，向下相容
- 不用實作 server-side LLM quality gate，寫入延遲不受影響

### 負面

- Schema 變更需要 migration（既有 entries 全部 `legacy`）
- `review-needed` 狀態 + TTL 機制要實作
- `zenos-capture` 的引導式流程比「直接萃取」UX 重，用戶要學新互動
- Tier 2 / Tier 3 的分類判斷需要 server 端驗證 source_type 真實性（防止 agent 偽造 `source_type="adr"` 繞過 tier check）→ 需要在 write 時 server 檢查 source_ref 是否真的指向一個存在的 ADR/task/spec

### 未解 / 後續

- **Source_type 偽造防護**：server 端如何驗證 `source_type="task_done"` 的 source_ref 確實是一個 `status=done` 的 task？下一個 TD 要處理
- **Entity 粒度偵測**（原議題 #3）：本 ADR 不處理 entity 太大的偵測，留給獨立 ADR（saturation 不只看數量，也看主題分群）
- **Analyze 拆分**（原議題 #2）：本 ADR 降低了 analyze 被觸發的頻率（Tier 3 直接擋、Tier 2 review-needed 不算 active），但未完全解 timeout。單 entity 模式的 `consolidate_entity(entity_id=...)` 仍需獨立做

## 實施順序

1. **Phase 1（低風險）**：Schema migration 加 `source_type` + `source_ref`，default `legacy`。MCP write 接受新欄位但不強制（backward compat）
2. **Phase 2（sync 退出）**：`zenos-sync` 實作層移除 entry 寫入能力；改走 journal `decision_signal`
3. **Phase 3（Tier 3 reject）**：MCP write 對 Tier 3 source_type reject
4. **Phase 4（review-needed）**：status enum 擴充 + confirm 支援 + TTL 過期 job
5. **Phase 5（capture 重定位）**：`zenos-capture` 改為引導式互動

Phase 1-3 是本 ADR 的最小可行路徑（可獨立上線）。Phase 4-5 視產品體驗回饋再決定是否做。

## 相關文件

- `ADR-010-entity-entries`（資料結構與生命週期 — 本 ADR 的基礎）
- `ADR-014-journal-entry-distillation`（journal 壓縮觸發 — 本 ADR 會影響其觸發後的路徑）
- `SPEC-entry-distillation-quality`（品質標準 — 本 ADR 補上 source tiering 維度）
- `SPEC-entry-consolidation-skill`（飽和壓縮 — 本 ADR 降低觸發頻率）
- `HANDOFF-2026-04-19-entry-governance-findings`（實證稽核紀錄）
