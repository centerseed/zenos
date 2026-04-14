---
type: ADR
id: ADR-035
status: Draft
ontology_entity: 行銷定位與競爭策略
created: 2026-04-14
updated: 2026-04-14
supersedes: null
---

# ADR-035: 行銷項目資訊架構重構

## Context

`SPEC-marketing-automation` 在 2026-04-14 的改版中，將頂層概念從「行銷活動（campaign）」改為「按產品分組的行銷項目」。這帶來三個架構變動：

1. **產品分組**：行銷項目必須掛在 ZenOS 已有的產品 entity 下，Dashboard 總覽按產品分組展示。
2. **項目類型**：區分「長期經營」（如官網 Blog、Threads 社群）和「短期活動」（如早鳥促銷），兩者在策略欄位、排程行為上有差異。
3. **策略欄位擴充**：原有 Strategy 只有 audience / tone / frequency / content_mix / month_goal 五欄位，新 SPEC 定義了必填 6 欄位 + optional 3 欄位，且長期/短期有不同欄位組合。

現有實作（ADR-033 + TD）假設扁平 campaign list，API response 沒有 product grouping，Strategy 欄位定義已不符合。

## Decision

### 1. 行銷項目 = L2 entity，parent 指向 product entity

```
Product（L1 entity，已存在）
  └── 行銷項目（L2 entity, type=module）
        ├── details.marketing.project_type: "long_term" | "short_term"
        ├── details.marketing.date_range: { start: date, end: date } | null
        └── children: Post（L3 entity, type=document）
```

- 使用者在 Dashboard「啟用產品」= 在該 product entity 下建立第一個行銷項目
- 不修改 product entity 本身，不新增 `details.marketing_enabled` 之類的 flag
- 有無行銷項目 = `search(collection="entities", query="marketing", product_id=X)` 是否有結果

### 2. API 改為 product-grouped response

```
GET /api/marketing/projects
→ {
    groups: [
      {
        product: { id, name },
        projects: [
          { id, name, project_type, date_range, status, stats }
        ]
      }
    ]
  }

GET /api/marketing/projects/{projectId}
→ { id, name, project_type, date_range, strategy, schedule, posts, ... }
```

- 原 `/api/marketing/campaigns` 改為 `/api/marketing/projects`
- Response 頂層改為 `groups[]`，每個 group 包含 product 和其下的 projects

### 3. Strategy 欄位擴充

| 欄位 | 型別 | 長期經營 | 短期活動 | 說明 |
|------|------|:-------:|:-------:|------|
| `audience` | string[] | 必填 | 必填 | 目標受眾，可多組 |
| `tone` | string | 必填 | 必填 | 品牌語氣 |
| `core_message` | string | 必填 | 必填 | 核心訊息 |
| `platforms` | string[] | 必填 | 必填 | 發文平台 |
| `frequency` | string | 必填 | 不適用 | 發文頻率；短期由活動排程決定，欄位不顯示 |
| `content_mix` | object | 必填 | 不適用 | 內容比例；短期不顯示 |
| `campaign_goal` | string | 選填 | 選填 | 活動目標（如「早鳥 100 人報名」） |
| `cta_strategy` | string | 選填 | 選填 | CTA 策略 |
| `reference_materials` | string[] | 選填 | 選填 | 參考素材 |

驗證規則：
- 「必填」= API 儲存時驗證非空，否則回 400
- 「選填」= 可為 null 或空字串，不阻擋儲存
- 「不適用」= 該 project_type 不顯示此欄位，API 忽略傳入值

全文存 strategy document；entry 只存 ≤200 字摘要（沿用 ADR-033 雙軌決策）。

### 4. 建立行銷項目的最小欄位

```
POST /api/marketing/projects
body: {
  product_id: string,       // 必填：掛在哪個產品下
  name: string,             // 必填：項目名稱
  project_type: "long_term" | "short_term",  // 必填
  date_range?: { start: date, end: date }    // short_term 必填
}
```

其他欄位（策略、文風等）留到後續步驟設定。

## Alternatives

| 方案 | 優點 | 缺點 | 為何不選 |
|------|------|------|---------|
| 維持扁平 campaign list，前端自行按 product 分組 | 後端不改動 | 分組邏輯散在前端；product 關聯只靠 tag，不穩定 | 不符合 SPEC 要求的資料模型 |
| 在 product entity 上加 marketing config | 集中管理 | 污染 Core entity model；product 不應知道行銷細節 | 違反 ADR-025 layering 約束 |
| 新建 marketing_project table | 自由 schema | 脫離 ZenOS entity 模型，Dashboard/MCP 查詢需雙路徑 | 違反 SPEC「不改 Core 資料模型」約束 |

## Consequences

- 正面：
  - 資訊架構對齊使用者心智模型（產品 → 行銷項目）
  - API response 結構清晰，前端不需要多次 round-trip 組裝分組
  - project_type 區分讓策略表單和排程邏輯可以條件渲染
- 負面：
  - 現有 campaign API 和前端需全面改名和重構
  - 既有測試（`test_marketing_dashboard_api.py`）需對應更新
  - 如果 product entity 數量很多，projects API 需支援分頁或 lazy load

## Implementation

1. 修改 `src/zenos/interface/marketing_dashboard_api.py`：
   - `/api/marketing/campaigns` → `/api/marketing/projects`，response 改為 product-grouped
   - 新增 `POST /api/marketing/projects`（建立行銷項目）
   - 新增 `POST /api/marketing/projects/{id}/strategy`（更新策略，欄位擴充）
2. 修改 `dashboard/src/lib/marketing-api.ts`：對齊新 API contract
3. 修改 `dashboard/src/app/marketing/page.tsx`：改為產品分組 UI
4. 更新 5 個 marketing skill 的 input contract：`campaign_id` → `project_id`
