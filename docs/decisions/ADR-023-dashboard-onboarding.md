---
doc_id: ADR-023-dashboard-onboarding
title: 架構決策：Dashboard Onboarding — 空知識地圖引導流程
type: ADR
ontology_entity: Dashboard 知識地圖
status: Draft
version: "1.1"
date: 2026-04-09
supersedes: null
---

# ADR-023：Dashboard Onboarding — 空知識地圖引導流程

## Context

### 問題

用戶完成帳號建立和 MCP 連線後，進入 Dashboard 看到空的知識地圖，不知道如何開始。`/setup` 只處理 MCP 連線，不涵蓋「如何使用」的引導。

SPEC-dashboard-onboarding 定義了 4 步 Checklist 引導流程，本 ADR 處理架構決策。

### Onboarding 四步流程

1. **導向知識庫** — 引導 agent 導向現有知識庫（本地資料夾/Google Drive）
2. **設定 MCP + 安裝 Skills** — 設定 agent MCP，然後安裝 ZenOS skill
3. **捕捉知識** — 用 `/zenos-capture` 捕捉知識到知識地圖
4. **體驗 AI 角色** — 體驗 AI 角色，如果沒有角色引導用戶安裝 ZenOS agent

### 現有基礎設施

| 元件 | 位置 | 狀態 |
|------|------|------|
| `/setup` 頁面 | `dashboard/src/app/setup/page.tsx` | 已落地 |
| 知識地圖頁面 | `dashboard/src/app/knowledge-map/page.tsx` | 已落地 |
| `getAllEntities()` | `dashboard/src/lib/api.ts` | 已落地 — 可取得 entity count |
| `getPartnerMe()` | `dashboard/src/lib/api.ts` | 已落地 — auth 已自帶 partner |
| `partners` SQL table | `src/zenos/infrastructure/sql_repo.py` | 已落地 — 有 preferences JSONB 欄位 |
| `PLATFORMS` 列表 | `/setup/page.tsx` | 已落地 — 有平台選擇但未持久化 |

## Decision

### D1：Onboarding 狀態 — 純前端計算 + server 持久化手動標記

**不新增 server 端 onboarding endpoint。** 四步的完成狀態分兩類：

| 步驟 | 完成判定 | 資料來源 |
|------|---------|---------|
| Step 1: 導向知識庫 | 用戶手動標記 | server 端 `partner_preferences` JSONB |
| Step 2: 設定 MCP + Skills | 帳號存在即完成 | `partner` 已在 auth context |
| Step 3: 捕捉知識 | entity count > 0 | `getAllEntities()` 結果（知識地圖頁已載入） |
| Step 4: 體驗 AI 角色 | 用戶手動標記 | server 端 `partner_preferences` JSONB |

**理由：** Step 2/3 的判定資料已在頁面內——partner 已登入、entities 已載入。不需要額外 API call。手動標記必須持久化到 server（換裝置不丟失），用 partner 表的 JSONB 欄位。

### D2：Partner Preferences JSONB 欄位

在 `partners` 表使用 `preferences` JSONB 欄位，儲存 onboarding 手動標記和用戶偏好。

JSONB 結構：
```json
{
  "onboarding": {
    "step1_done": true,
    "step4_done": true,
    "dismissed": false,
    "platform_type": "technical"
  }
}
```

**理由：** 比建新表更簡單。Partner 表已是用戶級配置的自然落點。JSONB 可擴展，未來其他偏好也放這裡。

### D3：新增 Dashboard API endpoints

新增兩個 endpoints：

```
GET  /api/partner/preferences      → 回傳 preferences JSONB
PATCH /api/partner/preferences     → 合併更新 preferences（shallow merge）
```

PATCH body 範例：
```json
{"onboarding": {"step1_done": true}}
```

Server 端做 shallow merge（`preferences || $1`），前端不需要讀-改-寫。

### D4：文案分流 — 平台類型持久化

用戶在 `/setup` 選擇平台後，將平台類型寫入 `preferences.onboarding.platform_type`：

- `"technical"`: Claude Code, Codex, Gemini CLI
- `"non_technical"`: Claude.ai/Cowork, ChatGPT, Antigravity

Checklist 讀 `preferences.onboarding.platform_type`，預設 `"non_technical"`。

### D5：前端架構 — OnboardingChecklist 組件

```
knowledge-map/page.tsx
  └── OnboardingChecklist (overlay)
        ├── ChecklistStep (Step 1-4)
        └── 進度條
```

**觸發邏輯在 `knowledge-map/page.tsx`：**
1. entities 載入後，若 L1+L2 count = 0 且未 dismiss → 顯示「開始使用」按鈕
2. 按鈕點擊 → 開啟 Checklist 面板
3. entities > 0 → 自動隱藏 Checklist，顯示正常知識地圖

**不獨立成 page、不用 route。** Checklist 是知識地圖的空狀態 overlay。

### D6：/setup 完成後導向知識地圖

`/setup` 頁面底部的 `<Link href="/">Back to projects</Link>` 改為 `<Link href="/knowledge-map">前往知識地圖</Link>`。同時在選擇平台時呼叫 PATCH preferences 存下 platform_type。

## Implementation Tasks

### Task 1: DB Migration + Backend API

1. 建 migration：`partners` 加 `preferences JSONB DEFAULT '{}'`
2. `SqlPartnerRepository` 新增 `get_preferences` / `update_preferences` 方法
3. `dashboard_api.py` 新增 `GET/PATCH /api/partner/preferences` endpoints
4. `_row_to_partner_dict` 加上 `preferences` 欄位
5. `get_partner_me` 回傳加上 `preferences`

### Task 2: Frontend — OnboardingChecklist 組件

1. `dashboard/src/lib/api.ts` 加 `getPreferences` / `updatePreferences`
2. 建 `dashboard/src/components/OnboardingChecklist.tsx`
   - 4 步 Checklist UI（可展開/收合）
   - 進度條
   - 「不再顯示」按鈕
3. 知識地圖 `page.tsx` 整合：空狀態 → 顯示「開始使用」→ Checklist
4. 文案分流：根據 `platform_type` 顯示技術/非技術文案

### Task 3: /setup 頁面改動

1. 選擇平台時存 `platform_type` 到 preferences
2. 底部連結改為「前往知識地圖」

### Task 4: 測試

1. OnboardingChecklist 單元測試（各步驟狀態、顯示/隱藏邏輯）
2. /setup 導向測試

## Consequences

**正面：**
- 用戶進入空知識地圖有明確引導，從「知識在哪」→「連上工具」→「匯入知識」→「體驗角色」的完整路徑
- 手動標記持久化到 server，跨裝置一致
- 文案分流讓技術/非技術用戶都有適合的指引
- Step 4 缺失角色時提示安裝 ZenOS Agent，避免用戶卡住

**負面：**
- 需要一個 DB migration（但只是加欄位，零風險）
- 新增 2 個 API endpoints（但極簡單）

**風險與不確定性：**

1. **不確定的技術點：** 無。全部使用既有 pattern。
2. **替代方案：** 考慮過用 localStorage 存手動標記（更簡單，但換裝置丟失）。考慮過建獨立 `onboarding_state` 表（過度設計）。
3. **最壞情況：** preferences JSONB 欄位未來膨脹——但 onboarding 資料很小（< 100 bytes），可忽略。
