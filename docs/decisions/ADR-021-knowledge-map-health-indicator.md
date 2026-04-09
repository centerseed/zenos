---
doc_id: ADR-021-knowledge-map-health-indicator
title: 架構決策：知識地圖治理健康提示
type: ADR
ontology_entity: 語意治理-pipeline
status: Draft
version: "1.0"
date: 2026-04-09
supersedes: null
---

# ADR-021：知識地圖治理健康提示

## Context

### 問題

ADR-020 已在 server 端落地 health signal 計算（`GovernanceService.compute_health_signal()` → `compute_health_kpis()` 純函數），回傳 6 項 KPI + `overall_level`（green/yellow/red）+ `recommended_action`。但這個信號目前只流向 MCP tool response 的 `governance_hints`，面向 agent。

Dashboard 用戶——使用知識地圖管理 ontology 的業主——完全看不到健康狀態。用戶不知道 ontology 品質正在退化，直到 agent 給出的建議變差才發現。

SPEC-knowledge-map-health-indicator 要求：在知識地圖頁面顯示治理健康提示，引導用戶到 Claude Code 執行 `/zenos-governance`（C 路線），不在 Dashboard 觸發 AI agent。

### 現有基礎設施

| 元件 | 位置 | 狀態 |
|------|------|------|
| `compute_health_kpis()` 純函數 | `domain/governance.py:2114` | 已落地（ADR-020） |
| `GovernanceService.compute_health_signal()` | `application/governance_service.py:589` | 已落地（ADR-020） |
| `HEALTH_THRESHOLDS` + `BOOTSTRAP_OVERRIDES` | `domain/governance.py:2074` | 已落地（ADR-020） |
| Dashboard API（Starlette） | `interface/dashboard_api.py` | 已有 partner auth + scope 機制 |
| 知識地圖前端頁面 | `dashboard/src/app/knowledge-map/page.tsx` | 已有，頁面載入時呼叫 5 個 API |
| `getQualitySignals()` API 呼叫 | `dashboard/src/lib/api.ts` | 已有，走 `/api/data/quality-signals` |

### 關鍵約束

- C 路線：不需要 agent runtime、WebSocket、job queue。Dashboard 僅唯讀 + 引導。
- 用戶不看 KPI 數字、不看技術術語。只需知道「現在需不需要做什麼」。
- 健康狀態允許最多 24 小時延遲。
- Phase 0 規模約 300 entities，`compute_health_signal()` 含 DB 查詢目標 < 100ms。

## Decision

### D1：新增 Dashboard API endpoint `GET /api/data/governance-health`

新增一個專用 endpoint，回傳 `overall_level` 及必要的展示資訊。不復用 `/api/data/quality-signals`（那是 per-entity 品質信號，語意不同）。

**回傳格式：**

```json
{
  "overall_level": "yellow",
  "cached_at": "2026-04-09T10:30:00Z",
  "stale": false
}
```

- `overall_level`：`"green"` / `"yellow"` / `"red"` — 前端唯一需要的判斷依據。
- `cached_at`：最後一次計算時間 — 前端判斷資料新鮮度用。
- `stale`：server 端判斷是否超過 24 小時。若 `true`，server 會觸發重算後回傳。

**不回傳 KPI 明細。** Spec 明確排除向用戶顯示 KPI 數字和術語。回傳多餘欄位只會誘惑前端工程師顯示出來。

**理由：**

- 單一職責：此 endpoint 只服務「知識地圖頁面需不需要顯示提示」這一個問題。
- 最小介面：前端只需 `overall_level` 做 conditional rendering，不需要其他資訊。
- 與 MCP tool response 的 `governance_hints.health_signal`（包含完整 KPI）區隔——agent 需要細節，用戶不需要。

### D2：DB 快取 health signal，`zenos.governance_health_cache` 表

在 PostgreSQL schema `zenos` 新增一張表：

```sql
CREATE TABLE zenos.governance_health_cache (
    partner_id   TEXT NOT NULL PRIMARY KEY,
    overall_level TEXT NOT NULL,  -- 'green' / 'yellow' / 'red'
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**寫入時機：**
- `batch_update_sources` 完成後（ADR-020 已在此處計算 health signal，順手寫入）。
- `analyze(check_type="health")` 完成後。
- Dashboard API endpoint 被呼叫且快取過期（>24h）時，觸發一次計算並寫入。

**讀取時機：**
- Dashboard API endpoint 被呼叫時，先讀快取。若 < 24h，直接回傳；若過期，重算。

**不使用 Redis / in-memory cache。** 理由：
- Phase 0 單一 Cloud Run 實例，DB 表就是最簡單的持久化方案。
- Cloud Run 可能 cold start，in-memory cache 不可靠。
- 一張表、一個 partner_id primary key、一個 UPSERT，複雜度極低。

### D3：前端以 conditional rendering 實現三級提示

知識地圖頁面載入時，在現有的 `Promise.all` 中加入 `getGovernanceHealth(token)` 呼叫。根據 `overall_level` 做 conditional rendering：

| overall_level | 行為 |
|--------------|------|
| `green` | 不顯示任何提示（沉默 = 正常） |
| `yellow` | 頁面頂部顯示溫和 banner：淺黃色背景，文字「知識地圖有些內容可能需要整理」，附引導文字 |
| `red` | 頁面頂部顯示稍強 banner：淺紅色背景，文字「知識地圖的品質可能正在影響 agent 的建議準確度」，附更強語氣引導 |

**引導文字：**
- yellow：「請在 Claude Code 中執行 `/zenos-governance` 進行自動治理」
- red：「建議儘快在 Claude Code 中執行 `/zenos-governance`」

**指令可複製：** `/zenos-governance` 文字包在 inline code 樣式的 `<button>` 中，點擊複製到剪貼簿。

**元件設計：** 新增 `GovernanceHealthBanner` 元件，接收 `level: "green" | "yellow" | "red"` 作為 props。元件放在 `<AppNav />` 下方、graph 容器上方。

**理由：**
- Banner 不遮蓋主要內容（Spec AC）。
- 不使用 modal / toast — 那些是中斷性的，不符合 Spec「不要求立即行動」的要求。
- 不提供「已讀」/ 關閉按鈕 — Spec 定義持續顯示直到狀態回 green。

### D4：不引入 GovernanceService 到 dashboard_api.py，使用輕量直接查詢

dashboard_api.py 現有模式是直接使用 repository（`_entity_repo`、`_blindspot_repo` 等），不注入 service 層。新 endpoint 遵循相同模式：

1. 先查 `governance_health_cache` 表 — 如果 < 24h，直接回傳。
2. 若過期或不存在，呼叫 `GovernanceService.compute_health_signal()`，寫入快取後回傳。

為 step 2 需要 `GovernanceService`，在 `_ensure_repos()` 中一併初始化（lazy-init，與其他 repo 相同模式）。

**理由：**
- 快取命中時只需一次 DB 查詢（讀 cache 表），不需要建構 GovernanceService。
- 快取未命中時才需要完整計算，此時付出初始化成本合理。
- 保持 dashboard_api.py 的 lazy-init 一致性。

## Alternatives

### Alt-A：不做 DB 快取，每次 API 呼叫都重算

**放棄原因：**
- `compute_health_signal()` 需要 3-4 次 DB round-trip + `run_quality_check()` 計算。Phase 0 規模下約 100ms，但知識地圖頁面已有 5 個平行 API 呼叫，再加一個 100ms 的可接受，但如果用戶頻繁刷新會產生不必要的 DB 壓力。
- DB 快取讓 happy path（< 24h 內有人做過 sync）只需一次 SELECT，遠快於重算。
- 快取實作極簡（一張表 + UPSERT），邊際成本低。

### Alt-B：復用 `/api/data/quality-signals` endpoint，附加 health level

在現有 `get_quality_signals` response 中加入 `governance_health` 欄位。

**放棄原因：**
- `quality-signals` 是 per-entity 的品質信號（search_unused、summary_poor），語意是「哪些節點有問題」。
- governance health 是 ontology-wide 的整體健康狀態，語意是「整體需不需要治理」。
- 混在一起違反單一職責，前端也需要不同的呈現邏輯。

### Alt-C：前端直接呼叫 MCP `analyze(check_type="health")`

讓前端透過某個 proxy endpoint 呼叫 MCP tool。

**放棄原因：**
- Dashboard 走 Firebase ID token auth，MCP 走 partner API key auth。架構不同。
- MCP tool response 包含完整 KPI 明細，回傳給前端就誘惑顯示，違反 Spec「不顯示 KPI」。
- Dashboard API 應該是 Dashboard 唯一的後端，不應繞路走 MCP。

### Alt-D：用 polling 或 WebSocket 推送健康狀態更新

**放棄原因：**
- C 路線明確排除 WebSocket。
- Polling 在 Phase 0 沒有價值——用戶不會長時間停留在知識地圖頁面等狀態變化。
- 頁面載入時取一次就夠了。下次打開頁面自然會取到最新值。

## Implementation

### Step 1：DB schema — 新增 `governance_health_cache` 表

在 `infrastructure/sql_repo.py` 的 schema init 中新增表。

```sql
CREATE TABLE IF NOT EXISTS zenos.governance_health_cache (
    partner_id    TEXT NOT NULL PRIMARY KEY,
    overall_level TEXT NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

新增兩個 repository 方法（放在現有 `SqlEntityRepository` 或獨立的 helper 中）：
- `get_cached_health(partner_id) -> dict | None`：回傳 `{overall_level, computed_at}` 或 None。
- `upsert_health_cache(partner_id, overall_level)`：UPSERT 一筆。

**Done Criteria：**
- 表在 `_ensure_schema()` 中建立。
- `get_cached_health` 回傳正確格式。
- `upsert_health_cache` UPSERT 行為正確（新增 + 更新都測）。
- Unit test 覆蓋。

### Step 2：後端 API — `GET /api/data/governance-health`

在 `dashboard_api.py` 新增 `get_governance_health` endpoint。

邏輯流程：
1. Firebase auth + partner scope（復用 `_auth_and_scope`）。
2. 讀 `governance_health_cache`。
3. 若快取存在且 `computed_at` < 24h → 回傳 `{overall_level, cached_at, stale: false}`。
4. 若快取不存在或過期 → 建構 `GovernanceService`，呼叫 `compute_health_signal()`，寫入快取，回傳 `{overall_level, cached_at: now, stale: false}`。
5. 若計算失敗 → 回傳快取值（即使過期）+ `stale: true`。若完全沒有快取 → 回傳 `{overall_level: "green", cached_at: null, stale: true}`（安全降級為沉默）。

Route 註冊：
```python
Route("/api/data/governance-health", get_governance_health, methods=["GET", "OPTIONS"]),
```

**Done Criteria：**
- 快取命中時回傳正確。
- 快取過期時觸發重算、寫入快取、回傳正確。
- 完全無快取時安全降級。
- `compute_health_signal()` 拋異常時不 500，回傳降級結果。
- Partner scope 正確（只讀自己 scope 的健康狀態）。

### Step 3：快取寫入整合 — `batch_update_sources` 後寫入

在 MCP tool 的 `batch_update_sources` 完成 health signal 計算後（ADR-020 已實作），將 `overall_level` 寫入 `governance_health_cache`。

同理，`analyze(check_type="health")` 完成後也寫入。

**Done Criteria：**
- `batch_update_sources` 完成後，`governance_health_cache` 有對應 partner_id 的記錄。
- `analyze(check_type="health")` 完成後同上。
- 寫入失敗不影響主操作（catch + log）。

### Step 4：前端 API 函數 — `getGovernanceHealth`

在 `dashboard/src/lib/api.ts` 新增：

```typescript
export async function getGovernanceHealth(token: string): Promise<{
  overall_level: "green" | "yellow" | "red";
  cached_at: string | null;
  stale: boolean;
}> {
  return apiFetch("/api/data/governance-health", token);
}
```

**Done Criteria：**
- 函數型別正確。
- 呼叫後回傳解析正確。

### Step 5：前端元件 — `GovernanceHealthBanner`

新增 `dashboard/src/components/GovernanceHealthBanner.tsx`。

Props：`{ level: "green" | "yellow" | "red" }`

| level | 樣式 | 主文字 | 引導文字 |
|-------|------|--------|---------|
| green | 不 render（return null） | — | — |
| yellow | 淺黃背景，amber 文字 | 知識地圖有些內容可能需要整理 | 請在 Claude Code 中執行 `/zenos-governance` 進行自動治理 |
| red | 淺紅背景，red 文字 | 知識地圖的品質可能正在影響 agent 的建議準確度 | 建議儘快在 Claude Code 中執行 `/zenos-governance` |

`/zenos-governance` 包在可點擊的 inline code 樣式元素中，點擊觸發 `navigator.clipboard.writeText("/zenos-governance")`，顯示短暫的「已複製」提示。

**Done Criteria：**
- green 時不 render 任何 DOM。
- yellow / red 各自顯示正確文字和樣式。
- 點擊指令文字可複製到剪貼簿。
- 不包含任何 KPI 術語、數字。
- Banner 不遮蓋知識地圖主要內容（位於 graph 容器上方，不是 overlay）。
- 符合 Dashboard 現有 dark theme 設計語言（使用 Tailwind `bg-amber-500/10`、`bg-red-500/10` 等）。

### Step 6：前端整合 — 知識地圖頁面載入 health signal

在 `knowledge-map/page.tsx` 的 `KnowledgeMapContent` 中：

1. 新增 state：`const [healthLevel, setHealthLevel] = useState<"green" | "yellow" | "red">("green")`。
2. 在 `Promise.all` 中加入 `getGovernanceHealth(token).catch(() => ({ overall_level: "green" as const, cached_at: null, stale: true }))`。
3. `setHealthLevel(fetchedHealth.overall_level)`。
4. 在 `<AppNav />` 下方、graph 容器上方插入 `<GovernanceHealthBanner level={healthLevel} />`。

**Done Criteria：**
- 頁面載入時呼叫 `/api/data/governance-health`。
- API 失敗時安全降級為 green（沉默）。
- Banner 位置在 AppNav 下方、graph 上方。
- 不影響現有頁面功能和載入時間（平行呼叫）。

### 執行順序

```
Step 1（DB schema）
    ↓
Step 2（後端 API）+ Step 3（快取寫入整合）— 可平行
    ↓
Step 4（前端 API 函數）
    ↓
Step 5（前端元件）+ Step 6（前端整合）— 可平行
```

### 效能預算

| 操作 | 目標 | 說明 |
|------|------|------|
| `GET /api/data/governance-health`（快取命中） | < 20ms | 一次 SELECT |
| `GET /api/data/governance-health`（快取未命中） | < 200ms | compute_health_signal + UPSERT |
| `GovernanceHealthBanner` render | < 5ms | 純 conditional render，無副作用 |
| 知識地圖頁面載入增加的延遲 | 0ms | 平行呼叫，不在 critical path |

### UI 術語對照

| 禁用術語 | 使用術語 |
|---------|---------|
| entity | 節點 |
| ontology | 知識地圖 |
| KPI | （不顯示） |
| quality_score | （不顯示） |
| governance | 整理 / 治理（僅在引導到 Claude Code 時出現） |
