---
type: PLAN
id: PLAN-zenos-dogfooding-loop
status: Active
created: 2026-04-19
related:
  - docs/decisions/ADR-010-entity-entries.md
  - docs/decisions/ADR-042-entry-source-tiering.md
  - docs/plans/HANDOFF-2026-04-19-entry-governance-findings.md
  - skills/release/governance/
  - skills/release/zenos-governance/SKILL.md
---

# PLAN: ZenOS Dogfooding Loop — 自我治理與改進閉環

## 目標

建立一個 agent 自驅的治理/改進閉環，讓 MCP + skill 能透過「真實使用→偵測缺口→修補→驗證」持續迭代，逐步逼近三大目標：

1. Agent 更快、更少 token 拿到有用 context
2. 主動治理讓知識圖譜越來越完整（支持 #1）
3. 跨用戶/跨 agent 同一套 context 可用（CRM/marketing 已達標，繼續守住）

## 硬約束（不可動）

- **Capture/治理入口必須保留人為觸發**（`/zenos-capture`、`/zenos-governance`）
- **毀滅性操作不得暴露為 MCP tool**
- **部署後必須端到端驗證**
- 本 loop 的「producer agent」也必須走 human-trigger 路徑（由 orchestrator 當人）

## 四種被治理的 entity 類型

（假設四種 = L2 entity + L3 document + L3 task + L3 blindspot。如需調整請更新此節。）

### Type 1: L2 entity（module，含 entries）

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| summary 準確度 | 反映當前實作，不超過 300 字 | 漂移偵測 → review task |
| 四維 tags 完整 | domain/role/time/impact 各至少 1 | 缺欄位 → review task |
| relationships | ≥ 2 條（通常 impacts / depends_on） | 孤兒節點 → propose 關聯 |
| entries per partner+dept | ≤ 20 active | saturation → consolidate（ADR-010） |
| entries 品質 | 無 9 類 anti-pattern（capture-governance） | 手動稽核 protocol |
| entity 粒度 | 主題數 ≤ 3 | entries ≥ 30 或主題 ≥ 5 → 拆分建議 |

**產生路徑**：L2 三問通過 → `write(entity)` → `confirm`
**更新路徑**：summary 或 tag 漂移 → architect review
**消亡路徑**：merged into another entity（status=archived + merge_target）

### Type 2: L3 document

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| source.uri | 真實可達 | 定期驗證 → stale |
| linked_entity_ids | ≥ 1 個合法 L2 | 孤兒 document → propose 關聯或 archive |
| 新鮮度 | source 檔案 last-modified 無巨幅落差 | sync 偵測 → mark stale |
| 去重 | 同 URI 無多筆 | write 時 query by uri 先 |

**產生路徑**：capture 發現值得建語意代理 → `write(document, confirmed_by_user=false)` → user confirm
**更新路徑**：source 變更 → sync mark stale → 重 capture
**消亡路徑**：source 刪除 或 linked_entity 全 archived → archived

### Type 3: L3 task

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| owner / assignee | 至少一方有值 | 缺 → reject 建立 |
| AC | 2-5 條可觀察 | 不符 → reject |
| 狀態流動 | todo → in_progress → review → done 不卡 | 7 天無進展 → stale flag |
| linked_entities | 1-3 個合法 L2 | 缺 → `[Ontology Gap]` 標記 |
| review→done | 走 `confirm(accepted=True)` | 直接 update 到 done → reject |

**產生路徑**：8 題 checklist → `write(task, status=todo)`
**更新路徑**：`task(action=update)` 改狀態；`confirm` 驗收
**消亡路徑**：done（confirm accepted）或 cancelled（帶 reason）

### Type 4: L3 blindspot

| 維度 | 健康狀態 | 治理路徑 |
|---|---|---|
| severity | red/yellow/green 合理 | LLM / 手動判斷 |
| related_entity_ids | ≥ 1 | 缺 → 不得建立 |
| suggested_action | 可執行（非抽象口號） | 太抽象 → review |
| 狀態流動 | open → acknowledged → resolved | resolved 後存查，不刪 |

**產生路徑**：capture / analyze(blindspot) 推斷 → `write(blindspot, status=open)`
**更新路徑**：ack / resolve 時附 linked_task_id 或 resolution_note
**消亡路徑**：resolved；或 stale（30 天未動且 severity=green）

## Dogfooding Loop 架構

三個角色 + 閉環機制：

```
┌─────────────────────────────────────────────────────────────────┐
│  Orchestrator (main Claude session) — 監控閉環、決定停/修/續      │
│                                                                 │
│   ┌───────────────────┐             ┌───────────────────┐      │
│   │ Producer subagent │  → writes → │  ZenOS Ontology   │      │
│   │  扮演用戶觸發      │             │  (MCP server)     │      │
│   │  capture/task     │             └───────────────────┘      │
│   └───────────────────┘                      ↑                 │
│            ↑                                 │                 │
│            │ 任務場景                        │ reads            │
│            │ (從 journal log                 │                 │
│            │  + git log 抽)                  │                 │
│            │                         ┌───────────────────┐    │
│            └─────────────────────────│ Monitor subagent  │    │
│                                      │ 跑 per-type 健康  │    │
│                                      │ 檢查 + diff       │    │
│                                      └───────────────────┘    │
│                                              ↓                 │
│                                      health report            │
│                                              ↓                 │
│            ┌──────────────────────────────────────────┐        │
│            │ Orchestrator 決策：                       │        │
│            │ - 健康 → 進下一 iteration                 │        │
│            │ - 缺口 → 定位 MCP/skill，修、部署、重測   │        │
│            │ - 改動寫回 ADR/journal                    │        │
│            └──────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### Producer subagent

**職責**：模擬真實用戶觸發 capture / task confirm。不得直接 write ontology（必須走 skill 入口，維持 human-trigger 約束）。

**輸入**：
- 場景（orchestrator 指定，例如「CRM agent 剛完成一通客戶電話的摘要」）
- 來自 journal log 的真實 capture 歷史（抽樣重放）
- 來自 git log 的真實 commit 主題（不直接產 entry，但提供場景素材）

**輸出**：
- 觸發 `/zenos-capture` 或 `confirm(task, entity_entries=...)` 的 session
- Session log（tools called、tokens、timeouts）

**關鍵紀律**：必須用 release skills 同一份 SSOT，不自寫內部規則。

### Monitor subagent

**職責**：對四種 entity 類型跑健康檢查，產出 diff report。

**檢查項（per iteration 全跑）**：

| 檢查 | 實作 |
|---|---|
| L2 entries saturation | `search(collection=entries, entity_id=X)` 逐 entity（需 MCP 支援，iteration 1 要補） |
| L2 孤兒 | `analyze(check_type=quality)` 或自定 SQL |
| L3 document staleness | `analyze(check_type=staleness)` |
| Task stuck | `search(collection=tasks, status=todo)` + age filter |
| Blindspot 過期 | `search(collection=blindspots, severity=green)` + 30d filter |
| Anti-pattern entries | 遍歷 entries + 9 類判準 matcher |

**輸出**：結構化 diff report（JSON），對照 producer 這一輪的輸入預期與實際產出。

### Orchestrator（我）

**職責**：
1. 啟動 producer（指定場景）
2. 讓 producer 跑完
3. 啟動 monitor
4. 讀 monitor report，比對「預期」與「實際」
5. 若缺口：
   - 定位缺口在 MCP（tool 缺 / 參數缺 / 行為錯）還是 skill（prompt 不對 / 判斷規則過時）
   - 最小改動 + 本地測試 + deploy（走 `./scripts/deploy_mcp.sh` 或 `./scripts/deploy.sh`）
   - 端到端驗證：同場景重跑 producer → monitor 應通過
   - 寫 ADR（結構決策）或 journal（戰術調整）
6. 若健康：紀錄 baseline，進下一 iteration

**停機條件**：
- 連續 3 個 iteration 同一缺口修不好 → 升級為人工介入 task
- 部署失敗 → 停，通知用戶
- 改動觸到硬約束（改 capture 觸發模型、毀滅性 tool）→ 停，require 確認

## 基線：過去一個月 capture 紀錄

**收集方式**：
```
journal_read(flow_type="capture", since="2026-03-19")
→ 統計：總次數、平均 tokens、每次產出 entries/documents/blindspots 數
→ 分類主題（CRM / marketing / zenos-core / paceriz / 其他）
```

**用途**：
1. Producer 的「場景庫」來源（重放真實場景）
2. 測量 loop 改進後，同場景 token/call 降多少
3. 找出過去 1 個月反覆踩的 friction（例如今天發現的 `get(entries) 5 條上限`）

## Iteration 協議

```
每個 iteration 有唯一 ID：DF-{YYYYMMDD}-{N}

Step 1. Orchestrator 選場景（from 基線庫）
Step 2. Producer 執行，log to /tmp/zenos-dogfood/{DF-ID}/producer.jsonl
Step 3. Monitor 執行，log to /tmp/zenos-dogfood/{DF-ID}/monitor.json
Step 4. Orchestrator 產 decision：
   {
     "df_id": "DF-20260419-1",
     "gap": "search(entries) 無 entity_id filter",
     "fix": "src/zenos/interface/mcp/search.py 加 entity_id 參數",
     "deploy": "scripts/deploy_mcp.sh",
     "verify_scenario": "重跑 audit 訓練計畫系統 entries",
     "outcome": "keep|revert"
   }
Step 5. 若 keep，寫 entry via `confirm(task, entity_entries=[...])` 走 Tier 1
         若 revert，寫 journal(flow_type=governance, summary="tried X, reverted because Y")
Step 6. 回 Step 1
```

**每 iteration 預算**：
- Producer：≤ 5 tool calls
- Monitor：≤ 10 tool calls
- Orchestrator 修補：≤ 15 min 或跨 session

## 成功指標

### 短期（iteration 1-10）

- 每 iteration 至少解一個 friction 或驗證一個假設
- 今天列出的三大 friction（A/B/C）全部解掉
- 基線庫建好

### 中期（iteration 10-30）

- 重放過去 1 個月任一 capture 場景 → token 降 30%+
- Monitor 可偵測 4 種 entity 的全部健康維度
- 至少一次「發現 ADR 規則過時 → 更新 ADR」

### 長期（iteration 30+）

- 新用戶接 ZenOS 後，第一週 agent 自動完成 5 次以上治理閉環（不需人工 debug）
- 跨用戶 Tier 1 entry 共享機制啟用（ADR-042 延伸議題）

## 與現有 skill 的邊界

- `zenos-capture` / `zenos-governance`：保留人觸發，producer 透過 subagent spawn 當作「人」
- `zenos-sync`：不在 loop 內直接用（entries 已退出其路徑）
- 新 MCP tool：如果 iteration 發現需要，走 ADR → implement → deploy → 回 loop

## 啟動前缺的東西

本 loop 跑起來前要先補：

1. **Per-entity-type 健康檢查 API**（Monitor 用）
   - `search(collection=entries, entity_id=X, limit=200)` ← 今天發現缺
   - `analyze(check_type="entity_audit", entity_id=X, dry_run=True)` 單 entity 模式
2. **session log hook**（producer / monitor 都要）
3. **Baseline 庫建構**（journal_read 抽過去 1 個月）

這三項是 iteration 1-3 的工作。

## Open Questions

1. Monitor 偵測到缺口時，orchestrator 自動修 vs 先 escalate？目前設計是「明顯缺陷自動修，結構性改動 escalate」——但邊界需要實跑幾次才能畫清
2. 四種 entity 是否涵蓋完整？relationships / protocols / project 要不要也納入？
3. Producer 需要多真實？完全重放歷史 vs 合成場景 vs 混合？
4. Orchestrator 跨 session 記憶：每次 iteration 重開 session 還是長跑？長跑有 context bleed，短跑缺連續性
