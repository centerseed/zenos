---
type: TD
id: TD-marketing-automation-implementation
status: Draft
linked_spec: SPEC-marketing-automation
created: 2026-04-12
updated: 2026-04-14
---

# 技術設計：Marketing Automation Spec Alignment

## 結論

舊版 `PLAN-marketing-automation-delivery` 已完成的是第一輪 POC：`campaign` read model、基本 workflow skills、package 安裝、Postiz v1 契約。

2026-04-14 的 spec/ADR refresh 把核心 contract 改為：

1. `campaign` → `project`
2. Dashboard overview 改為 **按產品分組**
3. strategy 欄位改為 **6 必填 + 3 選填**
4. 新增 **文風三層 document + CRUD API**
5. 新增 **欄位級一鍵開聊 / context pack / 對話 state machine**
6. helper 需補 **capability probe / permission timeout / 新 SSE event**

所以這不是補小功能，是第二輪 **spec alignment delta**。舊 TD 已不再能指導實作，必須以本文件取代。

## Spec Review

### 可行性

`✅ 可行`

- 不需要改 Core schema；仍可落在既有 `entities / documents / entries / tasks`
- 需要改的是 Application/BFF contract、前端 state 與 helper protocol
- 舊 plan 已有 `行銷自動化模組` L2 entity，可直接作為 delta task 的 linked entity

### 衝突列表

- `[資訊架構]` 現行 API/UI 仍以 `campaign` 為主 → 必須全面對齊 `project`
- `[策略 schema]` 現行 strategy 只有 5 欄 → 與新 spec/ADR-035 衝突
- `[文風]` 現行系統只有 prompt SSOT，沒有 style documents → 與 ADR-036 衝突
- `[cowork helper]` 現行 helper 還沒有 capability probe / permission timeout / context pack SSE → 與 ADR-034 衝突
- `[TD]` `docs/designs/TD-marketing-automation-implementation.md` 仍描述舊 `campaign` contract → 本次已重寫

### 結論

Spec 可進入實作，但需採以下假設，避免被開放問題卡住。

## 實作假設（Architect 裁決）

### A1. 美編工作流

P0 只做到 **AI 生成圖片 brief + Web 顯示 brief**。  
不做圖片上傳、審圖流程、跨角色 task dispatch；這些留到 P1 的附件/發佈深化。

### A2. 文風初始版本

P0 不要求系統預塞完整 style content。  
工程只提供 CRUD、三層組合與預覽；初始內容由行銷 owner 依既有 `Paceriz` 指引建立。

### A3. 圖片附件發佈

不納入 P0。  
`/marketing-publish` P0 只處理文字內容與排程 metadata；圖片附件上傳/綁定留到 P1。

### A4. 文風預覽的範例主題

沿用 ADR-036：**優先取最近一個排程主題，否則使用者手動輸入**。

### A5. 長期項目排程自動延展

P0 不做自動延展。  
使用者重新執行 `/marketing-plan` 取得新一輪建議，避免 scheduler 偷改已確認排程。

## 目標架構

### 1. Project Model

```text
Product (L1)
  └── Marketing Project (L2 module)
        ├── details.marketing.project_type
        ├── details.marketing.date_range
        ├── strategy document + summary entry
        ├── style documents (product/platform/project scope)
        └── post/topic documents
```

- `project_type`: `long_term | short_term`
- `date_range`: 只對 `short_term` 必填
- overview API 直接回傳 `groups[]`，前端不自行拼分組

### 2. API Contract

#### `GET /api/marketing/projects`

```json
{
  "groups": [
    {
      "product": { "id": "prod_1", "name": "Paceriz" },
      "projects": [
        {
          "id": "proj_1",
          "name": "官網 Blog",
          "project_type": "long_term",
          "date_range": null,
          "status": "active",
          "stats": {}
        }
      ]
    }
  ]
}
```

#### `POST /api/marketing/projects`

```json
{
  "product_id": "prod_1",
  "name": "早鳥促銷",
  "project_type": "short_term",
  "date_range": { "start": "2026-05-01", "end": "2026-05-14" }
}
```

#### `GET /api/marketing/projects/{projectId}`

回傳：

- project meta
- strategy summary + latest strategy document metadata
- style aggregation（product/platform/project）
- schedule
- posts
- current workflow phase / CTA hints

#### `PUT /api/marketing/projects/{projectId}/strategy`

strategy schema：

- required: `audience[]`, `tone`, `core_message`, `platforms[]`
- required for `long_term`: `frequency`, `content_mix`
- optional: `campaign_goal`, `cta_strategy`, `reference_materials[]`

寫入策略時同時：

1. 更新 project entity `details.marketing.strategy_summary`
2. 寫 strategy document（全文）
3. 寫 summary entry（<=200 字）

### 3. Style CRUD

新增 API：

- `GET /api/marketing/projects/{projectId}/styles`
- `POST /api/marketing/styles`
- `PUT /api/marketing/styles/{styleDocId}`

style 存法：

- product-level: 掛 product entity
- platform-level: 掛 product entity，帶 `style_platform`
- project-level: 掛 project entity，帶 `style_project_id`

預覽測試不經後端，前端直接打 helper。

### 4. Cowork Helper / UI Contract

helper 需支援：

- `capability_check` SSE event
- `permission_request` SSE event
- `permission_result` SSE event
- 60 秒 permission timeout 後自動拒絕
- 只用 `.claude/settings.json` 的 `allowedTools`

前端需補：

- context pack 組裝
- redaction rules 單一來源
- 7-state state machine
- structured apply flow
- `updated_at` 衝突偵測

### 5. Skills Contract Alignment

五個 workflow skill 改動：

- `campaign_id` → `project_id`
- `marketing-intel` 改逐篇 topic / post context，不再用 campaign 級 intel
- `marketing-generate` / `marketing-adapt` 生成前需查 style composition
- 文件內術語一律改成 project / style / context pack 新語意

## Spec Compliance Matrix

| ID | 需求 | 實作方式 | 主要檔案 | 驗證 |
|----|------|---------|---------|------|
| MA2-P0-01 | product-grouped project overview | 新 `/api/marketing/projects` + grouped DTO | `src/zenos/interface/marketing_dashboard_api.py` | `tests/interface/test_marketing_dashboard_api.py` |
| MA2-P0-02 | project create/detail contract | project create/detail API + detail phase hints | `src/zenos/interface/marketing_dashboard_api.py` | API tests |
| MA2-P0-03 | strategy schema refresh | 6+3 欄位驗證 + project_type gating + dual-write | `src/zenos/interface/marketing_dashboard_api.py` | API tests |
| MA2-P0-04 | style CRUD + aggregation | style documents + GET/POST/PUT styles | `src/zenos/interface/marketing_dashboard_api.py` | API tests |
| MA2-P0-05 | overview/detail frontend 對齊 project | `marketing-api.ts` + `/marketing` page 改讀新 contract | `dashboard/src/lib/marketing-api.ts`, `dashboard/src/app/marketing/page.tsx` | vitest/build |
| MA2-P0-06 | 文風管理與預覽 UI | style editor + helper preview entry | `dashboard/src/app/marketing/page.tsx`, `dashboard/src/lib/cowork-helper.ts` | vitest/build |
| MA2-P0-07 | helper capability / permission flow | helper probe + timeout + SSE events | `tools/claude-cowork-helper/server.mjs` | helper tests/manual verification |
| MA2-P0-08 | 欄位級開聊 / state machine / apply contract | context pack + apply flow + conflict detection | `dashboard/src/app/marketing/page.tsx` | vitest/manual verification |
| MA2-P0-09 | workflow skill contract refresh | 5 個 skills 改 `project_id` + style composition | `skills/release/workflows/marketing-*/SKILL.md` | `rg` + sync tests |

## 任務拆分

### D01. 技術設計與文件對齊

- 更新本 TD
- 新增 delta plan 文件
- 以本文件作為後續 task acceptance 的 SSOT

### D02. Data/API Alignment

- `campaigns` → `projects`
- grouped response
- create/detail/strategy validation
- styles CRUD + aggregation
- 補 API tests

### D03. Frontend Alignment

- `marketing-api.ts` 型別與路徑更新
- `/marketing` overview/detail 改為 product-grouped
- strategy form 對齊新 schema
- style 管理 UI

### D04. Cowork Deep Integration

- helper capability probe / timeout / SSE events
- context pack / redaction / state machine
- structured apply / conflict detection

### D05. Skill Alignment

- 5 個 workflow skill input/output contract 更新
- generate/adapt 注入 style composition

### D06. QA / Build / Smoke

- pytest marketing API
- dashboard vitest + build
- helper/manual smoke
- `/marketing` 正式站驗收走 `scripts/deploy.sh`

## 驗收 Gate

這次 drift 的根因不是「spec 不清楚」，而是過去把 build / smoke 當成 spec 驗收。

從這版 TD 開始，marketing 功能一律分三層驗收：

1. **Tech Verify**
   - 單元測試、API mock test、build、deploy smoke
   - 只證明技術切片能運作
   - 不能單獨作為 `review` 依據

2. **Spec Compliance**
   - `tests/spec_compliance/test_marketing_ac.py`
   - 每條 `AC-MKTG-*` 必須是：
     - `pass`：已有 executable contract
     - `xfail`：明確尚未完成 / 缺 E2E / partial
     - 禁止用 `pytest.fail("NOT IMPLEMENTED")` 當假紅燈清單

3. **Release Gate**
   - task 進 `review` 前，必須列出自己的 AC 範圍
   - 該範圍內不允許有未知 `fail`
   - 允許 `xfail` 的前提是：task status 不得宣稱「spec complete」，只能宣稱「engineering slice complete」

## AC Mapping 原則

- D02: `AC-MKTG-01~08`, `16`, `18~21`, `24`, `44~48`
- D03: `AC-MKTG-04`, `09~15`, `18~19`, `69~102`
- D04: `AC-MKTG-22~23`, `53~68`, `73~88`, `99`
- D05: `AC-MKTG-25~52`
- D06: 將上述 AC 補成正式站 / E2E / smoke 驗收

重點：之後若新增實作，必須先把改動掛回 AC，而不是只掛檔案路徑。

## 風險

### 1. 最大風險

前端頁面目前高度耦合舊 `campaign` DTO；若不先切清 DTO adapter，改名容易一路炸到 page state。

### 2. 控制策略

- 先改 API contract 與 TS type，不直接在 page 內散改字串
- style CRUD 與 helper deep integration 分成不同 task，避免同一張票同時改 BFF/UI/helper
- 對話 apply flow 一律走 `target_field` 映射，不做自由格式回填

### 3. 不做的事

- 不做圖片附件發佈
- 不做長期排程自動延展
- 不做 server-side analytics 回收
- 不做多人 reviewer/approval

## Resume Point

下一步應建立新的 Action Layer delta plan，名稱建議：

`Marketing Automation Spec Alignment Delta`

第一張要開工的是 `D02 Data/API Alignment`，因為它會決定前端、helper、skill 全部的 contract。
