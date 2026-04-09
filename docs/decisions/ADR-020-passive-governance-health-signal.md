---
doc_id: ADR-020-passive-governance-health-signal
title: 架構決策：被動治理 Health Signal
type: ADR
ontology_entity: 語意治理-pipeline
status: approved
version: "1.0"
date: 2026-04-09
supersedes: null
---

# ADR-020：被動治理 Health Signal 架構

## Context

### 問題

ZenOS 現有治理機制是「主動式」：agent 必須呼叫 `analyze(check_type="all")` 才能得知 ontology 健康狀態。這帶來兩個問題：

1. **偵測延遲**：品質退化發生在 sync/capture 之後，但在下一次主動 `analyze` 之前完全不可見。若 agent 不跑 analyze，退化就永遠沉默。
2. **治理成本高**：`analyze(check_type="all")` 是重量級操作——載入所有 entities、relationships、protocols、blindspots，跑 21 項 checklist + graph topology + L2 backfill proposals。Phase 0 約 300 個 entity 時尚可接受，但每次 sync 後都跑一次不合理。

SPEC-governance-feedback-loop P0-3 要求：server 在正常操作的 response 中**被動附帶** health signal，讓 agent 不需主動觸發就能感知品質變化。

### 現有基礎設施

- **`_unified_response`**（tools.py:561）：所有 MCP tool 的標準回傳格式，已有 `governance_hints` 欄位（dict）。
- **`_build_governance_hints`**（tools.py:537）：建構 governance_hints，目前包含 `duplicate_signals`、`stale_candidates`、`suggested_follow_up_tasks`、`similar_items`、`suggested_entity_updates`。尚無 `health_signal`。
- **`analyze` 函數**（tools.py:2754）：`check_type="all"` 時已計算完整 KPI（tools.py:3195-3208），包含 `unconfirmed_ratio`、`blindspot_total`、`duplicate_blindspot_rate`、`median_confirm_latency_days`、`active_l2_missing_impacts`。
- **`batch_update_sources`**（tools.py:3441）：sync 核心操作，目前回傳不含 governance_hints。
- **`GovernanceService`**（governance_service.py）：application 層，編排 entity_repo / relationship_repo / blindspot_repo 等，呼叫 domain 純函數。
- **`governance.py`**（domain 層）：純函數，包含 `run_quality_check`（21 項 checklist）、`compute_quality_correction_priority` 等。

### 與 ADR-003 的關係

ADR-003 定義了治理觸發的 Adapter 架構：事件來源不同但治理引擎共用。本 ADR 延續該架構，定義「治理引擎在回應操作時附帶 health signal」的具體實作方案。ADR-003 解決「何時觸發」，本 ADR 解決「觸發後回傳什麼、怎麼算」。

## Decision

### D1：Health signal 附帶在 `batch_update_sources` 和 `write entries` 的 response 中

在以下兩個退化觸發點的 `_unified_response` 中，透過 `governance_hints.health_signal` 附帶 KPI 快照：

- **`batch_update_sources` 完成後**：附帶完整 health_signal（6 項 KPI + overall_level + recommended_action）。
- **`write` entries 完成後**：附帶 entry saturation signal（active entries 數量 / 飽和門檻）。

不在以下操作附帶 health signal：
- `write entities/documents`：修復操作，附帶 signal 會產生誤導（「剛修完又說有問題」）。
- `task` 建立/更新：頻率太高，會造成噪音。
- `confirm`：品質提升操作。

**Session start 觸發點（SPEC 3.5.2「沉默腐化」）：降為 Phase 0.5 scope。**
SPEC 3.5.2 要求「session 開始時附帶輕量 health signal」以捕捉沉默腐化（長時間無操作導致的品質退化）。本 ADR 不實作此觸發點，理由：
- Phase 0 的 session start 由 agent 端 skill 控制（`journal_read`），server 無法區分「session 開始的 journal_read」和「一般的 journal_read」。
- 在 `journal_read` 或 `search` 中無差別附帶 health signal 會產生過多噪音。
- Phase 0.5 可透過 ADR-003 的 Claude Code hook 機制解決：session 結束時 hook 觸發 `analyze(check_type="health")`，間接覆蓋沉默腐化偵測。

### D2：KPI 計算放在 domain 層純函數，GovernanceService 負責編排

新增 domain 純函數 `compute_health_kpis`，接收預先查詢好的資料，回傳 KPI dict。此函數必須是純函數（無 I/O），確保可測試且與基礎設施解耦。

```
domain/governance.py
  compute_health_kpis(
      entities, documents, blindspots, relationships,
      entries_by_entity, confirmed_items_with_timestamps
  ) -> HealthKPIs

application/governance_service.py
  GovernanceService.compute_health_signal() -> dict
    # 查詢 repos → 呼叫 compute_health_kpis → 附加門檻判定 → 回傳
```

理由：
- domain 純函數可單獨 unit test，不需 mock repo。
- GovernanceService 負責查詢資料、呼叫純函數、附加門檻判定——這是 application 層的職責。
- 現有 `analyze` 中的 KPI 計算（tools.py:3146-3208）必須重構為呼叫此純函數，消除重複。

### D3：`analyze(check_type="health")` 復用 GovernanceService，不新增方法

在 `analyze` 函數中新增 `check_type="health"` 分支：

- 呼叫 `GovernanceService.compute_health_signal()`。
- 回傳完整 KPI + levels + recommended_actions 清單。
- 不跑 quality checklist、不跑 graph topology、不跑 blindspot 推斷——只算 KPI。
- 執行時間必須控制在 100ms 以內（Phase 0，~300 entities）。

不新增獨立的 MCP tool。理由：`analyze` 已是 agent 熟悉的治理入口，加 check_type 比加新 tool 的認知成本低。

### D4：門檻定義存在 domain 層常量

門檻定義為 domain 常量（`governance.py`），不使用設定檔。

```python
# governance.py
HEALTH_THRESHOLDS = {
    "quality_score":              {"green": 70, "yellow": 50},
    "unconfirmed_ratio":          {"green": 0.30, "yellow": 0.60},
    "blindspot_total":            {"green": 20, "yellow": 50},
    "median_confirm_latency_days":{"green": 3, "yellow": 7},
    "active_l2_missing_impacts":  {"green": 0, "yellow": 3},
    "duplicate_blindspot_rate":   {"green": 0.05, "yellow": 0.15},
}

# Phase 0 bootstrap 覆寫（SPEC 3.5.1）
BOOTSTRAP_OVERRIDES = {
    "unconfirmed_ratio": {"green": 0.50, "yellow": 0.70},
}
```

理由：
- Phase 0 單一部署，不需要 per-partner 設定。
- 門檻是業務規則，屬於 domain 層。
- 硬編常量最簡單、最可測試、最不容易出錯。
- Phase 1 多租戶時再考慮移到設定檔或 DB。

### D5：每次計算，不做 cache

Phase 0 不引入 cache 機制。每次 `batch_update_sources` 完成後即時計算 KPI。

理由：
- Phase 0 規模（~300 entities）下，KPI 計算的主要成本是 DB 查詢，不是計算本身。
- `compute_health_kpis` 純函數本身是 O(n) 掃描，n=300 時在毫秒級。
- DB 查詢（`list_all` entities/blindspots/relationships）是已有操作的延伸，加一次 round-trip 在可接受範圍。
- 引入 cache 會帶來一致性問題（cache 何時 invalidate？write 後要不要清 cache？），Phase 0 不值得。
- 若 Phase 1 規模增長導致 100ms 超標，再加 materialized view 或 cache。

## Alternatives

### Alt-A：Health signal 作為獨立 MCP tool（`check_health`）

建一個新的 MCP tool `check_health`，agent 在每次 sync 後主動呼叫。

**放棄原因**：
- 違反 SPEC 設計原則「治理是操作的副作用，不是獨立的功能」。
- agent 必須記得呼叫 → 回到「靠人/agent 記得」的問題，跟現有 `analyze` 一樣。
- 多一個 tool = 多一個 agent 需要理解的介面。

### Alt-B：KPI 全部在 interface 層計算（現有 analyze 模式）

維持現狀：KPI 計算邏輯直接寫在 `tools.py` 的 `analyze` 函數內（tools.py:3146-3208）。

**放棄原因**：
- 違反 DDD 分層：業務規則（門檻判定、KPI 定義）寫在 interface 層。
- 無法獨立 unit test：測試必須 mock 整個 MCP 環境。
- 重複：`batch_update_sources` 需要同樣的 KPI 計算，如果不抽出來就會在 interface 層再寫一次。

### Alt-C：門檻存在 DB / 設定檔，支援 per-partner 自訂

門檻值存在 PostgreSQL 的 partner settings 表，允許每個 partner 自訂門檻。

**放棄原因**：
- Phase 0 只有一個部署，per-partner 設定是 YAGNI。
- 增加 DB schema + migration + 讀取邏輯的複雜度。
- 門檻值在 Phase 0 需要頻繁調整（SPEC 第六章開放問題 4），硬編常量改起來最快。

## Implementation

### Step 1：Domain 層——新增 `compute_health_kpis` 純函數

在 `src/zenos/domain/governance.py` 新增：

1. `HEALTH_THRESHOLDS` 和 `BOOTSTRAP_OVERRIDES` 常量。
2. `HealthKPIs` dataclass（或 TypedDict），包含 6 項 KPI 值 + overall_level + per-KPI levels。
3. `compute_health_kpis()` 純函數：接收 entities、protocols、blindspots、quality_score（int）、l2_repairs_count（int）→ 回傳 `HealthKPIs`。不需要 relationships（由 `run_quality_check` 內部處理）。
4. `determine_recommended_action(overall_level: str) -> str | None` 純函數：green→None、yellow→"review_health"、red→"run_governance"。

Done Criteria：
- 純函數，零 I/O 依賴。
- Unit test 覆蓋 green/yellow/red 三個級別。
- 門檻值與 SPEC 3.5.1 表格一致。

### Step 2：Application 層——GovernanceService 新增 `compute_health_signal`

在 `src/zenos/application/governance_service.py` 新增 `compute_health_signal()` 方法。

**資料來源與 repository 映射**：

GovernanceService 已注入 `entity_repo`、`relationship_repo`、`blindspot_repo`、`protocol_repo`。各 KPI 所需資料來源如下：

| KPI | 需要的資料 | Repository / 取得方式 |
|-----|----------|---------------------|
| quality_score | entities + relationships + protocols | 復用現有 `run_quality_check()`，僅取 `.score` |
| unconfirmed_ratio | entities + protocols + blindspots 的 `confirmed_by_user` 欄位 | `entity_repo.list_all()` + `protocol_repo.list_all()` + `blindspot_repo.list_all()`（已有注入） |
| blindspot_total | blindspots 數量 | `blindspot_repo.list_all()` |
| duplicate_blindspot_rate | blindspots 的 description/severity/action 組合 | 同上，domain 純函數計算 signature 去重 |
| median_confirm_latency_days | confirmed items 的 `created_at` 與 `updated_at` 差值 | entities/protocols/blindspots 的 confirmed subset，從 list_all() 結果中過濾 `confirmed_by_user=True` 的項目 |
| active_l2_missing_impacts | active L2 entities 缺少 impacts | 復用現有 `run_quality_check()` 結果中的 `l2_impacts_repairs` |

**不需要額外注入新 repository**：所有 6 項 KPI 都可從已注入的 4 個 repo 計算。`document_repo`（已 deprecated）和 `task_repo` / `tool_event_repo` 不需要。

**現有 KPI 計算在 tools.py:3146-3208 的重構映射**：
- `total_items` / `unconfirmed_items`：遷移到 domain 純函數，輸入為 entities + protocols + blindspots 清單
- `duplicate_blindspot_rate`：遷移到 domain 純函數，輸入為 blindspots 清單
- `median_confirm_latency_days`：遷移到 domain 純函數，輸入為 confirmed items 清單（含 `created_at` / `updated_at`）
- `active_l2_missing_impacts`：從 `run_quality_check()` 結果取值，不重複計算

實作步驟：

1. 查詢 `entity_repo.list_all()`、`blindspot_repo.list_all()`、`protocol_repo.list_all()`——共 3 次 DB round-trip。
2. 呼叫 `run_quality_check()` 取 quality_score 和 l2_repairs——此方法內部已查詢 relationships，不需額外查詢。
3. 呼叫 domain `compute_health_kpis(entities, protocols, blindspots, quality_score, l2_repairs_count)`。
4. 組裝回傳 dict（KPI 值 + levels + recommended_action + red 指標的具體修復建議）。

Done Criteria：
- 單次呼叫 DB round-trip 不超過 4 次。
- 回傳格式符合 SPEC P0-3 AC 定義。
- 不新增任何 repository 注入。

### Step 3：Interface 層——`_build_governance_hints` 擴充 + `batch_update_sources` 整合

1. `_build_governance_hints` 新增 `health_signal: dict | None` 參數。
2. `batch_update_sources` 完成後呼叫 `GovernanceService.compute_health_signal()`，將結果傳入 `_build_governance_hints(health_signal=...)`。
3. `write` entries 分支完成後附帶 entry saturation signal（active entries count / 飽和門檻 20）。

Done Criteria：
- `batch_update_sources` response 的 `governance_hints.health_signal` 包含完整 KPI。
- `write entries` response 的 `governance_hints.health_signal` 包含 `entry_saturation`。
- 現有 `batch_update_sources` 測試不 break。

### Step 4：Interface 層——`analyze(check_type="health")` 分支

1. 在 `analyze` 函數新增 `"health"` check_type。
2. 呼叫 `GovernanceService.compute_health_signal()`。
3. 附加 per-red-KPI 的具體修復行動映射（SPEC 3.5.3 表格）。
4. 不跑任何重量級分析。

Done Criteria：
- `analyze(check_type="health")` 回傳完整 KPI + levels + recommended_actions。
- 執行時間 < 100ms（Phase 0 規模）。

### Step 5：重構——消除 `analyze(check_type="all")` 中的 KPI 重複計算

1. `analyze(check_type="all")` 的 KPI 計算（tools.py:3146-3208）改為呼叫 `GovernanceService.compute_health_signal()`。
2. 回傳格式保持向後相容（`results["kpis"]` 結構不變）。

Done Criteria：
- 現有 `analyze(check_type="all")` 測試全部通過。
- tools.py 中不再有 KPI 計算邏輯的直接實作。

### 執行順序

Step 1 → Step 2 → Step 3 + Step 4（可平行）→ Step 5。

### 效能預算

| 操作 | 目標 | 說明 |
|------|------|------|
| `compute_health_kpis`（純計算） | < 5ms | O(n) 掃描，n~300 |
| `GovernanceService.compute_health_signal`（含 DB） | < 100ms | 3-4 次 DB round-trip |
| `batch_update_sources` 附帶 health signal 的額外延遲 | < 100ms | 在原有 response time 上增加 |
| `analyze(check_type="health")` 總時間 | < 100ms | 等同 compute_health_signal |

### Health Signal 回傳格式

```json
{
  "governance_hints": {
    "health_signal": {
      "kpis": {
        "quality_score": {"value": 65, "level": "yellow"},
        "unconfirmed_ratio": {"value": 0.42, "level": "yellow"},
        "blindspot_total": {"value": 12, "level": "green"},
        "median_confirm_latency_days": {"value": 2.5, "level": "green"},
        "active_l2_missing_impacts": {"value": 5, "level": "red"},
        "duplicate_blindspot_rate": {"value": 0.03, "level": "green"}
      },
      "overall_level": "red",
      "recommended_action": "run_governance",
      "red_reasons": [
        {
          "kpi": "active_l2_missing_impacts",
          "value": 5,
          "threshold": 3,
          "repair": "補 impacts 或降級 L2 到 L3"
        }
      ]
    }
  }
}
```
