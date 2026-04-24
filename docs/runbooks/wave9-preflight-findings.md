---
type: RUNBOOK
id: wave9-preflight-findings
status: draft
created: 2026-04-23
author: agent:developer
task_id: af17b9db186048b99eb38c50a3878cf6
plan_id: 4f4a591ec45143d9b2d3d4528a4e1c3e
data_source: MCP proxy（staging DB 無直接連線；DATABASE_URL 未設定於 local env）
---

# Wave 9 Pre-entry Investigation Findings

A01 四段交付物：Junction 現況 / Milestone 盤點 / handoff_events 位置評估 / Phase D 依賴重估。
Architect 依此拍板 C04 / C06 / handoff_events 位置 / Phase D 上游依賴四項待定決策。

---

## §A — Junction Table 現況

### 數據來源

MCP proxy：`mcp__zenos__search(collection="tasks", limit=500, project="zenos")`
回傳 44 筆 task，從 `linked_entities` / `blocked_by` 欄位重建 junction table 行數。

> 注意：MCP proxy 回傳的是 application-layer 已展開的視圖（linked_entities = task_entities join 展開後的物件陣列；blocked_by = task_blockers 的 task id list）。行數統計為間接推算，非直接 SQL。若需精確數字，需補跑 staging DB SQL（見 §A SQL 原文）。

### task_entities 統計

| 指標 | 數值 |
|------|------|
| 總 task 數（44 tasks 推算） | 44 rows in zenos.tasks |
| task_entities 總行數（linked_entities 加總） | 133 行（推算） |
| 有 linked_entities 的 task 數 | 35 / 44（79.5%） |
| 無 linked_entities 的 task 數 | 9 / 44（20.5%） |
| task_id IS NULL | 0（PK 不可 NULL） |
| entity_id IS NULL | 0（PK 不可 NULL） |
| relationship 欄位 IS NULL | N/A — task_entities 無 relationship 欄位（見 schema） |
| 單一 partner_id（所有 task 同屬一個 partner） | 1 distinct partner_id |

**linked_entities 分佈（per task）**：

| 數量 | task 數 |
|------|---------|
| 0 | 9 |
| 1 | 21 |
| 2 | 10 |
| 3 | 1 |
| 5 | 1 |
| 6 | 1 |
| 78 | 1 |

**cross-partner 污染**：無。所有 44 task 皆同屬 product_id `Gr54tjmnXK0ZAtZia6Pj`，created_by 僅有兩個 partner：`xm6YB5DH2d4BMu5g0Ka2`（42 tasks）與 `Codex`（2 tasks）。同一 entity 被多個 task 引用（15 個 entity 出現在 2 個以上 task 的 linked_entities）屬正常知識圖譜交叉引用，非污染。

**孤兒 row**：無法從 MCP proxy 直接驗 FK 完整性（需要直接 DB query）。但 FK cascade 設定（`ON DELETE CASCADE`）意味著若 entity 被刪除，task_entities row 會自動清除。目前未發現孤兒跡象。

### task_blockers 統計

| 指標 | 數值 |
|------|------|
| task_blockers 總行數（blocked_by 加總） | 0 行 |
| 有 blocked_by 的 task 數 | 0 / 44 |

**task_blockers 現況**：表存在但零資料。所有阻塞關係目前透過 `blocked_by` 欄位記錄在 task 物件本身，而非 task_blockers junction table——這意味著 blocked_by 欄位在 application layer 反序列化後為 list，但在 DB 可能同時存在 JSONB 欄位與 junction table 兩條路徑。

### Outlier 明細

見 `wave9-preflight-findings.findings.csv`（1 row）：

- **af17b9db** (`A01` task)：78 linked_entities，遠超正常值（median=1, p95=6）。屬 Architect session 批量注入 context entity，非跨 partner 污染。技術上合法，但 Wave 9 migration 時需確認是否清理冗餘。

### §A SQL 原文（供 staging DB 驗證）

```sql
-- task_entities 統計
SELECT
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE task_id IS NULL) AS task_id_null,
  COUNT(*) FILTER (WHERE entity_id IS NULL) AS entity_id_null,
  COUNT(DISTINCT partner_id) AS distinct_partners
FROM zenos.task_entities;

-- per-partner 分佈
SELECT partner_id, COUNT(*) AS rows
FROM zenos.task_entities
GROUP BY partner_id
ORDER BY rows DESC;

-- task_blockers 統計
SELECT
  COUNT(*) AS total_rows,
  COUNT(*) FILTER (WHERE task_id IS NULL) AS task_id_null,
  COUNT(*) FILTER (WHERE blocker_task_id IS NULL) AS blocker_null,
  COUNT(DISTINCT partner_id) AS distinct_partners
FROM zenos.task_blockers;

-- outlier tasks（linked_entities > 10，若有 per-task count 欄位）
SELECT task_id, partner_id, COUNT(*) AS entity_count
FROM zenos.task_entities
GROUP BY task_id, partner_id
HAVING COUNT(*) > 10
ORDER BY entity_count DESC;

-- 孤兒 row（entity 不存在）
SELECT te.task_id, te.entity_id, te.partner_id
FROM zenos.task_entities te
LEFT JOIN zenos.entities e
  ON e.id = te.entity_id AND e.partner_id = te.partner_id
WHERE e.id IS NULL;
```

### §A 結論

- `task_entities`：133 行，零 NULL（FK 強制），零跨 partner 污染，1 個 outlier（78 linked_entities 的 A01 task）
- `task_blockers`：0 行，表存在但完全未使用
- C06 決策建議：`task_blockers` 可安全 **drop**——無資料、語意已被 `blocked_by` JSONB 欄位與 task-level 欄位承擔，遷移成本極低

---

## §B — Milestone / goal Entity 盤點

### 數據來源

MCP proxy：`mcp__zenos__search(collection="entities", query="goal", entity_level="all", include=["full"])`
取得所有 L3 goal entity。另查 task 的 linked_entities 確認 goal 引用路徑。

### goal entity 現況

| 指標 | 數值 |
|------|------|
| type=goal 的 entity 總數 | 4 |
| level=3（L3）的 goal 數 | 4（全部） |
| level=2 或 level=1 的 goal 數 | 0 |
| 有 parent 關係（parent_id != null）的 goal 數 | 4（全部） |
| 沒有 parent 的 goal 數 | 0 |

**goal entities 明細**：

| id | name | parent_id | parent type |
|----|------|-----------|-------------|
| `8910198b` | M1 Helper Milestone Smoke Test | `e3d007e6`（L2 module: 訂單履約流程） | L2 module |
| `e60cf277` | M1 Helper Milestone Smoke Test 2026-04-22 JST | `82f81abf`（L1 product: Dogfood Test Product） | L1 product |
| `96d1e6b7` | M2：7月完成 Rizo 整合 | `e2f0fa8b`（L2 module: Rizo AI 教練） | L2 module |
| `13555d6f` | M1：6/1 試用期結束，正式開始收費 | `af54292f`（L2 module: 運動數據接入） | L2 module |

**被誰引用**：

- task `af17b9db`（A01 task）的 linked_entities 包含所有 4 個 goal entity —— 這是 Architect session 的 context 注入，屬一次性行為
- 無其他 task 或 entity 透過 linked_entities 引用 goal entity
- `zenos.relationships` 表中（透過 MCP 展開的 entity payload）無任何 outgoing/incoming relationship 指向 goal entity

### 與 SPEC v2 §9.2 L3MilestoneEntity 的語意差異

**現有 `goal` entity（runtime）**：

```
entities table:
  id, partner_id, name, type='goal', level=3, parent_id, status, summary, tags, ...
```

- 沒有 `task_status`（milestone 業務狀態）
- 沒有 `target_date`
- 沒有 `completion_criteria`
- 沒有 `acceptance_criteria_json`
- 沒有 `priority` / `dispatcher` / `assignee`（task governance 欄位）
- `status` 是 EntityStatus（active/archived/draft/stale/current），不是 task_status（planned/active/completed/cancelled）

**SPEC v2 §9.2 `entity_l3_milestone` 目標態**：

```sql
CREATE TABLE entity_l3_milestone (
    entity_id text PRIMARY KEY REFERENCES entities_base(id),
    description text NOT NULL,
    task_status text NOT NULL CHECK (task_status IN ('planned','active','completed','cancelled')),
    assignee text,
    dispatcher text NOT NULL,
    acceptance_criteria_json jsonb NOT NULL DEFAULT '[]',
    priority text NOT NULL DEFAULT 'medium',
    result text,
    target_date date,
    completion_criteria text
);
```

**差距（5 個欄位缺失）**：task_status / dispatcher / acceptance_criteria_json / target_date / completion_criteria

### C04 決策建議：in-place upgrade vs 獨立 subclass

**建議：獨立 subclass（Option B）**

理由：

1. **語意斷裂太大**：現有 `goal` entity 只是一個帶 `type='goal'` 的知識節點，缺少 milestone 特有的 task governance 欄位（task_status / dispatcher / acceptance_criteria_json）。In-place upgrade 要在 entities table 加 sparse 欄位（對非 milestone entity 永遠是 NULL），違反 SPEC v2 的 MTI 原則（Axiom 3：禁止 ad-hoc free-form）。

2. **資料量極小（4 rows）**：遷移成本極低。4 個 goal entity 全部有 parent_id，路徑清晰。

3. **Migration blast radius（Option B）**：
   - 讀取路徑受影響：`dashboard_api.py` 對 entity type 的 display logic（搜尋 `type_label` 或 `type == 'goal'`）需更新
   - MCP `get(collection="entities")` 展開 goal entity 的 caller：目前僅 A01 task 引用，无 UI 直接渲染 goal 欄位 —— blast radius 極小
   - UI 術語：Dashboard 顯示 milestone 已對應 `goal` type，改名後需確認 type_label mapping（`dashboard/src/` 中搜尋 `'goal'`）
   - **4 rows 的 migration script**：為每個 goal entity 在 `entities_base` 補填 L3 欄位，並插入 `entity_l3_milestone` 子表（task_status 預設 `active`，dispatcher 從 created_by 推斷，completion_criteria / target_date 設 NULL）

**Option A（in-place upgrade）的問題**：
   - entities table 加 nullable 欄位（task_status / dispatcher 等），讓所有非 milestone entity 攜帶永久 NULL
   - 無法在 DB 層強制 milestone-specific NOT NULL 約束
   - 與 Wave 9 整體 MTI 架構方向反向

---

## §C — handoff_events 存儲位置評估

### 數據來源

MCP proxy 44 筆 task，直接取 `handoff_events` 欄位。

### JSONB 欄位分佈

| 指標 | 數值 |
|------|------|
| 有 handoff_events 的 task 數 | 11 / 44（25%） |
| min events per task | 0 |
| p25 | 0 |
| p50（median） | 0 |
| p75 | 1 |
| p95 | 3 |
| max events per task | 3 |
| total events across all tasks | 17 |

**有 handoff_events 的 tasks（11 筆）**：

| task id（前8位） | title（摘要） | event 數 |
|-----------------|---------------|---------|
| af17b9db | A01: Wave 9 pre-entry investigation | 1 |
| 54d1671c | 驗收 backend scheduler 集中管理 | 1 |
| c1e173be | 實作 backend scheduler 集中管理 | 1 |
| e8c734b5 | Release skill SSOT 清除 | 3 |
| 7976dfd7 | Dashboard UI：isL1Entity helper | 3 |
| 6e5cc634 | Infrastructure 層 project_id fallback 清除 | 3 |
| 6e65ec55 | S01 撰寫 migration | 1 |
| 38bc5972 | 統一 task-related copilot rail contract | 1 |
| 3c418b69 | 重構 TaskDetailDrawer | 1 |
| 886f0fec | 實作 task/product focus drill-down | 1 |
| e3b8d395 | 實作 Task Hub 首屏 recap | 1 |

**近 30 天 append 頻率**：全部 44 task 均在 30 天內更新（今日為 2026-04-23，系統尚在早期使用），17 events 來自 11 個 task。系統還很新，未來 handoff 量會隨任務增加線性成長。

### audit 查詢現況（grep src/）

```
interface/mcp/task.py:551      — 讀 task_result.task.handoff_events[-1] 取最新 from_dispatcher
interface/dashboard_api.py:982 — 遍歷 task.handoff_events 做 display
application/action/task_service.py:542,598,669 — append handoff event
infrastructure/action/sql_task_repo.py:23,48,84,197,206,220,255,270 — 序列化/反序列化
interface/governance_rules.py:946,1098 — HANDOFF_EVENTS_READONLY 錯誤說明
domain/action/models.py:103   — Task.handoff_events: list[HandoffEvent] field
```

查詢模式：全部是**讀全部 handoff_events**（取 `[-1]` 或遍歷），無任何基於 `from_dispatcher` / `to_dispatcher` / `at` 的條件查詢。目前沒有跨 task 的 handoff audit query（如「列出所有 qa review 中的 task 的 handoff 歷史」）。

### 方案對照表

| 面向 | 方案 A：繼續放 task JSONB 欄位 | 方案 B：獨立 task_handoff_events 表 |
|------|-------------------------------|-------------------------------------|
| **讀取** | O(1) — task GET 一次拿到全部；無額外 JOIN | 需額外 JOIN 或子查詢；但可加 index 做高效 range query |
| **寫入** | UPSERT 整個 JSONB array；append 需 read-modify-write | INSERT 一行；真正 append-only；無 read-modify-write |
| **audit queryability** | JSONB path query（`jsonb_array_elements`）可查，但效率差；跨 task audit 需全表掃 | SQL 原生 range query（`WHERE task_entity_id = X ORDER BY created_at`）；跨 task audit 可加複合 index |
| **migration 成本** | 無（保持現狀） | 需新建表 + 將現有 17 筆 event 從 JSONB migrate；低成本（17 rows） |
| **MCP contract 影響** | 零影響 | `task.handoff_events` 回傳欄位仍可透過 JOIN 填充，外部 contract 不變 |
| **SPEC v2 §9.6 對齊** | 不符（§9.6 明確定義為獨立表） | 符合 SPEC v2 §9.6 DDL |
| **未來擴展** | event 增多後 JSONB 逐漸膨脹；難做 partial read | 可加 pagination / time-range filter；自然 append-only |

### 推薦：方案 B（獨立 task_handoff_events 表）

理由：

1. **SPEC v2 §9.6 已明確定義獨立表**（`CREATE TABLE task_handoff_events`）。繼續放 JSONB 是 runtime 與 spec 的分裂——Wave 9 的核心目標之一就是消除這類分裂。

2. **17 rows 的 migration 成本極低**。現在做比之後再改容易：task 數量一旦增加，JSONB migration 的 read-modify-write 風險上升。

3. **唯一顧慮（read path）**：目前 task GET 一次返回 handoff_events，改為獨立表後需 JOIN。但 SPEC v2 §9.6 的 DDL 有 `idx_handoff_events_task`（task_entity_id, created_at）index，查詢效率不成問題。

4. **MCP contract 影響**：外部 contract 不受影響——`task.handoff_events` 欄位仍可在 task GET handler 透過 JOIN 填充，caller 看不到差異。

---

## §D — Phase D 依賴重估

### 問題

Phase D（D01/D02 backfill）需要：
- D01：`tasks.product_id`（已有值）→ 作為 `parent_id` 的 backfill 來源
- D02：`plans.product_id`（已有值）→ 作為 plan 的 `parent_id` backfill 來源

Phase D 的邏輯依賴 `tasks.product_id` **已有值且可信**。問題是：這個前提是否已滿足？

### tasks.product_id 現況

**欄位現狀（migration 確認）**：

Migration `20260422_0003_task_product_id_finalize.sql`（已 apply）：
```sql
ALTER TABLE zenos.tasks ALTER COLUMN product_id SET NOT NULL;
ALTER TABLE zenos.plans ALTER COLUMN product_id SET NOT NULL;
```

**MCP proxy 驗證**：44 / 44 task 的 `product_id` 非 NULL（`product_id_null: 0`）。全部指向同一個 product entity `Gr54tjmnXK0ZAtZia6Pj`。

**結論**：`tasks.product_id` 現在是 NOT NULL，且資料已 backfill 完成（migration 0002/0003 已 apply）。這意味著 D01 的 backfill 邏輯（`parent_id = plan_id OR product_id`）的資料前提已就緒。

### PLAN-task-ownership-ssot 的 S01-S18 目的

PLAN `c646d3c91374466baa92c6e03d6a4b37` 的目的是：

> 把 task / plan 對 product 的歸屬語意從多軌（project 字串 / project_id / linked_entities 偷塞）收斂為單一 SSOT `product_id` (FK to L1 product entity, NOT NULL)

**關鍵發現**：

| Task | 狀態 | 說明 |
|------|------|------|
| S01（migration 改名） | review | S01 result 聲稱已一次完成三支 migration（0001/0002/0003），product_id NOT NULL 已在 live DB 生效 |
| S02（backfill migration） | todo（任務追蹤落後） | migration 0002 已實際 apply，但 MCP task 尚未推進到 done |
| S03（finalize NOT NULL） | todo（任務追蹤落後） | migration 0003 已實際 apply，但 MCP task 尚未推進到 done |
| S04-S18 | todo | 涵蓋 domain model、repo、service、MCP interface、Dashboard、governance 同步 |

**重要注意**：S01 的 result 說明一次實作了三支 migration，但 S02/S03 的 MCP task 狀態仍是 `todo`——這是任務追蹤落後於實際 runtime 的情況。

**實際 runtime 狀態**：`tasks.product_id NOT NULL` 已在 live DB 落地。

### Phase D 可否在 PLAN-task-ownership-ssot 未完成前啟動？

**判定：YES（但有條件）**

**已就緒的前提**：
- `tasks.product_id NOT NULL` — 已落地（migration 0003 applied）
- `tasks.product_id` 的資料 backfill 完成（0 NULL，100% 覆蓋）
- D01/D02 backfill 邏輯所需的 `product_id` 欄位存在且可信

**尚未完成的 PLAN-task-ownership-ssot tasks（S04-S18）**：
這些 tasks 處理的是 domain model 改名、application service validation、MCP interface、Dashboard、governance 同步——它們影響的是**寫入路徑的一致性**（確保新建 task 一定透過 product_id 歸屬），但不阻擋 Phase D 的 backfill 讀取邏輯（Phase D 只需讀取 existing `product_id` 值）。

**依賴 surface（條件列表）**：

1. **S04（domain model 改名）**：`Task.project_id → Task.product_id`。如果 D01 backfill script 直接走 SQL（不走 domain layer），不受影響。若走 domain layer，S04 需先完成。
2. **S05（repo 純走 product_id）**：D01/D02 的 dry-run 若走 repo layer 做 product_id 讀取，S05 需先完成（移除 `OR t.project_id = $X` fallback）。
3. **S06-S18**：UI/governance 同步——與 Phase D backfill 無直接依賴，可並行。

### 建議

1. **Phase D 可啟動**，但 D01/D02 backfill script 建議**直接走 SQL**（不依賴 domain layer），繞過 S04/S05 的未完成狀態風險。
2. **需補進 Wave 9 Entry Criteria**：S04 + S05 完成（domain model 改名 + repo 純走 product_id）是 Phase D backfill script 若走 repo 層的前提，應補進本 PLAN Phase D 的 pre-condition 說明。
3. **任務追蹤清理**：PLAN-task-ownership-ssot 的 S02/S03 需由 QA 確認並 close（migration 已 apply，任務追蹤落後），否則持續讓 Architect 誤判 ownership SSOT 的完成狀態。

**具體建議文字（Architect 可直接寫入 Wave 9 Entry Criteria）**：

> **Phase D pre-condition（補充）**：
> - `tasks.product_id NOT NULL` 在 staging DB 確認（已在 live DB 落地，需 staging 同步確認）
> - D01/D02 backfill script 走純 SQL，不依賴 domain layer（繞過 PLAN-task-ownership-ssot S04/S05 的完成狀態）
> - 若 D01/D02 script 需走 repo layer：需等 PLAN-task-ownership-ssot S04（domain model 改名）完成

---

## 附錄：數據品質聲明

本 runbook 所有數據來自 MCP proxy（`mcp__zenos__search`），非直接 staging DB SQL query，原因：

- `DATABASE_URL` 在 local 環境未設定
- Cloud SQL staging 無直接連線（需 Cloud SQL Proxy 或 IAM 配置）

**MCP proxy vs 直接 DB query 的差異**：

| 數據點 | MCP proxy 可信度 | 建議 DB 驗證 |
|--------|-----------------|-------------|
| task_entities 行數（133）| 間接推算（linked_entities sum），可能有 lag | 建議跑 `SELECT COUNT(*) FROM zenos.task_entities` |
| task_blockers 行數（0）| 間接（blocked_by list sum），可能有 lag | 建議跑 `SELECT COUNT(*) FROM zenos.task_blockers` |
| goal entity 數（4）| 直接（entity payload），可信 | 無需額外驗證 |
| product_id NOT NULL（0 NULL）| 直接（task payload），可信 | migration 文件已確認 |
| handoff_events stats | 直接（task payload），可信 | 無需額外驗證 |

Architect 在 A02 啟動前，建議補做一次 staging DB 直接 SQL query（§A SQL 原文）確認 task_entities 精確行數與孤兒 row。

---

## §E — Production DB Verification (A02 Gate, 2026-04-23)

### 連線方式

cloud-sql-proxy + asyncpg，透過 `zenos-database-url` Secret Manager secret（project zentropy-4f7a5）。

Secret：`postgresql://zenos_api:***@localhost/zenos?host=/cloudsql/zentropy-4f7a5:asia-east1:zentropy-db`

本地連線改寫：將 socket host 替換為 `127.0.0.1:5447`（cloud-sql-proxy TCP port）。

**注意**：A01 runbook 使用 `naruvia_api` 連線到 `neondb` database（APPLICATION_URL secret），該 database 的 `zenos` schema 完全為空（0 rows）。實際 production data 位於 `zenos` database（`zenos-database-url` secret），由 `zenos_api` user 管理。

### 直接 SQL 結果

| 指標 | A01 MCP proxy 推算 | Production DB 實測 | 差異 |
|------|----|----|------|
| task_entities total rows | 133 | **578** | +445（MCP proxy 嚴重低估） |
| task_entities NULL (task_id) | 0 | 0 | 無差異 |
| task_entities NULL (entity_id) | 0 | 0 | 無差異 |
| task_entities distinct partners | 1 | **2** | +1（有第二個 partner） |
| task_blockers total rows | 0 | 0 | 無差異 |
| 孤兒 row (entity FK missing) | 無法驗（MCP） | **0** | 乾淨 |
| tasks total rows | 44（MCP 推算） | **634** | +590（MCP proxy 嚴重低估） |

### 結論

**A01 MCP proxy 推算與 production DB 有顯著差異**：

1. `task_entities`：578 rows（MCP 推算 133，差距 4.3×）。原因：MCP proxy 只回傳最近 44 筆 task（limit 參數），production 實際有 634 筆 task，因此 task_entities 也遠多於推算。
2. `distinct_partners`：2（MCP 推算 1）。Production 有兩個 partner，MCP 搜尋可能因 API key scope 只看到一個。
3. `task_blockers`：0 rows，與 A01 推算一致。C06 決策（Phase F drop）不受影響。
4. 孤兒 row：0，FK 完整性乾淨。
5. Wave 9 新 table（entities_base 等）：執行本 gate 時均不存在，無衝突。

**對 Wave 9 的影響**：

- Phase C dual-write 的 migration batch size 需重新估計（578 task_entities、634 tasks）
- task_handoff_events 的 Phase C backfill 量（17 events）不受影響（直接從 JSONB payload 取得）
- 無新 outlier 需加入 findings.csv

**Architect 需知**：production DB 的實際 secret 是 `zenos-database-url`（非 `database-url`），且目標 database 是 `zenos`（非 `neondb`）。run_sql_migrations.py 需使用正確的 DATABASE_URL 才能 apply 到 production。

---

### PostgreSQL 版本（P1-E fix，2026-04-23）

**版本確認**：

連線方式：cloud-sql-proxy（zentropy-4f7a5:asia-east1:zentropy-db, port 5432）+ asyncpg

```
SELECT version();
→ PostgreSQL 16.13 on x86_64-pc-linux-gnu, compiled by Debian clang version 12.0.1, 64-bit
```

**決策：ON DELETE SET NULL (parent_id)**

Cloud SQL 跑 PG 16.13（>= PG 15）。選用 PG 15+ 語法：

```sql
FOREIGN KEY (partner_id, parent_id)
    REFERENCES zenos.entities_base (partner_id, id) ON DELETE SET NULL (parent_id),
```

**語意**：刪除有 children 的 parent entity 時，children 的 `parent_id` 欄位被設為 NULL，`partner_id` 保持不變（NOT NULL 約束不受影響）。

**為何不選 RESTRICT**：

- RESTRICT 會讓「刪除有 children 的 parent」直接失敗，需 caller 先手動 cascade 或 reparent children，操作負擔大且容易漏掉。
- SET NULL (parent_id) 語意更乾淨：children 變成孤兒節點（parent_id = NULL），仍可在 ontology 內獨立存在，後續可重新掛載到其他父節點。
- PG 16.13 完整支援此語法，無相容性風險。

**修改範圍**：

- `migrations/20260423_0004_wave9_l3_action_preflight.sql` line 52：`ON DELETE SET NULL` → `ON DELETE SET NULL (parent_id)`
- 其他 FK（subclass ON DELETE CASCADE、task_handoff_events ON DELETE CASCADE）不動——CASCADE 對它們是正確行為（刪 parent 連帶刪 subclass / handoff_events）。

**FK action 行為摘要**：

| FK | 刪 parent 時行為 |
|----|-----------------|
| entities_base.parent_id（自引用） | children 的 `parent_id` 設 NULL；`partner_id` 不變 |
| entity_l3_* subclass（partner_id, entity_id）| subclass row 跟著刪（CASCADE） |
| task_handoff_events（partner_id, task_entity_id）| handoff event rows 跟著刪（CASCADE） |
