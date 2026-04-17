---
type: TD
id: TD-dashboard-frontend-design-patterns
status: Draft
ontology_entity: dashboard-frontend-architecture
created: 2026-04-16
updated: 2026-04-16
linked_spec: SPEC-dashboard-v2-ui-refactor
---

# 技術設計：Dashboard Frontend Design Patterns

## 結論

ZenOS Dashboard 前端不再允許「route page 同時扛 auth shell、資料 transport、頁面 orchestration、domain UI」的混合寫法。

正式 pattern 收斂成四層：

1. `app/(protected)/` route wrapper
2. protected layout shell
3. `features/<domain>/...Workspace.tsx`
4. `features/<domain>/use<Domain>Workspace.ts` + `lib/*-api.ts`

這份 TD 定義未來 dashboard 前端的固定切法、允許的例外、驗收方式，以及目前仍未完成的驗證邊界。

## 適用範圍

- `dashboard/src/app/(protected)/**`
- `dashboard/src/features/**`
- `dashboard/src/lib/api-client.ts`
- `dashboard/src/lib/api.ts`
- `dashboard/src/lib/crm-api.ts`
- `dashboard/src/lib/marketing-api.ts`

## 本次已落地的結構

### 1. Protected shell

- `dashboard/src/app/(protected)/layout.tsx`
  - `AuthGuard` 與 `AppNav` 的唯一 owner。
- `/tasks`、`/team`、`/clients`、`/knowledge-map`、`/marketing`、`/projects`、`/docs`、`/setup` 已收進 `(protected)` route group。

### 2. Shared transport

- `dashboard/src/lib/api-client.ts`
  - 統一 token header
  - 統一 `X-Active-Workspace-Id`
  - 統一 same-origin retry
  - 統一 JSON body / error detail / date hydration

### 3. Feature workspace

- `dashboard/src/features/marketing/MarketingWorkspace.tsx`
- `dashboard/src/features/team/TeamWorkspace.tsx`
- `dashboard/src/features/crm/ClientsWorkspace.tsx`
- `dashboard/src/features/crm/CompaniesWorkspace.tsx`
- `dashboard/src/features/crm/CompanyDetailWorkspace.tsx`
- `dashboard/src/features/crm/DealDetailWorkspace.tsx`

### 4. Page orchestration hook

- `dashboard/src/features/marketing/useMarketingWorkspace.ts`
- `dashboard/src/features/team/useTeamWorkspace.ts`
- `dashboard/src/features/crm/useClientsWorkspace.ts`

## Design Pattern

## 1. Route Wrapper Pattern

### 規則

- `app/(protected)` 下的 page 檔只負責 route entry。
- page 檔可以：
  - 直接 `export { default } from "@/features/..."`
  - 做極薄的 route-only glue
- page 檔不得：
  - 自己 render `AuthGuard`
  - 自己 render `AppNav`
  - 自己實作 page-level data loading / mutation orchestration

### 原因

這樣 auth shell、nav shell、route path、domain UI 才不會再糾纏在同一檔案。

### 驗證

- `app/(protected)` 下 page 檔不應再 import `AuthGuard` / `AppNav`
- protected page 能由 layout 正常包住並通過 `next build`

## 2. Protected Layout Pattern

### 規則

- 所有需要登入的 dashboard 頁面必須掛在 `app/(protected)/layout.tsx` 之下。
- `AuthGuard` 只處理：
  - auth 檢查
  - invited activation
  - suspended/no-partner/fetch-failed 的 blocking state
- `AppNav` 只在 protected layout 掛一次。

### 不允許

- 某個 page 因為特殊需求再次 mount `AuthGuard`
- 某個 domain 自己維護第二套 nav shell

### 驗證

- route group build 成功
- deep link `/tasks`、`/knowledge-map`、`/marketing`、`/clients` 不出現雙 nav / 雙 guard

## 3. Shared API Transport Pattern

### 規則

- 所有打 ZenOS dashboard backend 的 HTTP 呼叫，必須走 `apiRequest()`
- domain client 只允許包 domain path 與 response mapping，不重做 transport policy

### 允許例外

- signed URL 上傳
- 外部 helper / SSE bridge
- 非 ZenOS backend 的外站請求

### 不允許

- 在 page / workspace 內直接 `fetch("/api/...")`
- 各模組各自複製 workspace header、retry、error parsing

### 驗證

- `api.ts`、`crm-api.ts`、`marketing-api.ts` 都以 `api-client.ts` 為底
- workspace-aware mutation 在切換 workspace 後不應漏 header

## 4. Feature Workspace Pattern

### 規則

- domain 主要 UI 容器放在 `features/<domain>/...Workspace.tsx`
- Workspace 可以組合：
  - 展示元件
  - domain child components
  - hook 回傳的 state / handler
- Workspace 不應擁有跨 domain transport policy

### 邊界

- `app/` 可以 import `features/`
- `features/` 不得 import `app/(protected)/`
- route tree 是 entry，feature tree 才是可重用實作

### 目前實例

- marketing page wrapper → `features/marketing/MarketingWorkspace.tsx`
- team page wrapper → `features/team/TeamWorkspace.tsx`
- clients / companies / deal detail wrapper → `features/crm/*Workspace.tsx`

### 驗證

- `rg "@/app/(protected)" dashboard/src/features` 應為空
- feature child component 與 Workspace 可以被 route wrapper 以 re-export 方式掛回 app tree

## 5. Page Hook Pattern

### 規則

- 下列情況必須抽 `use<Domain>Workspace()`：
  - page orchestration state 超過一個 async flow
  - 同時有 list/detail/save/review/load 兩種以上 mutation/read path
  - route guard、mutation、toast、reload 流程混在一起

### hook 責任

- auth user / partner context
- route guard
- list/detail loading
- mutation handler
- optimistic update / rollback
- page-level derived state

### Workspace 責任

- render
- handler wiring
- domain-specific layout

### 目前實例

- `useMarketingWorkspace`
  - campaign list/detail/save/review/copilot entry state
- `useTeamWorkspace`
  - invite/member scope/department CRUD
- `useClientsWorkspace`
  - CRM list loading、DnD stage update、modal/settings state

## 6. Domain Child Component Pattern

### 規則

- feature 的 child component 也應 co-locate 在 `features/<domain>/`
- route-specific 檔案可以 re-export feature component，但不應反向成為 feature 依賴

### 目前實例

- `features/crm/CrmAiPanel.tsx`
- `features/crm/DealInsightsPanel.tsx`
- `app/(protected)/clients/deals/[id]/CrmAiPanel.tsx`
  - 只保留 re-export wrapper
- `app/(protected)/clients/deals/[id]/DealInsightsPanel.tsx`
  - 只保留 re-export wrapper

## 7. Testing Pattern

### 必跑檢查

- `npm run lint`
- `npm test`
- `npm run build`

### 建議測試切面

- `src/lib/__tests__`
  - transport / API client 行為
- `src/__tests__`
  - route / page action / wrapper 行為
- feature co-located tests
  - domain-specific UI 或 pure logic

### 不接受的結案方式

- 只有 typecheck 過
- 只有單檔 smoke test
- 只靠人工點過一頁

## 規則矩陣

| 項目 | 必須 | 不得 |
|---|---|---|
| Protected 頁面 | 放在 `app/(protected)` | 在 page 內再包 `AuthGuard` |
| Shell | 由 layout 擁有 | domain 自建第二套 nav/auth shell |
| Backend transport | 經 `apiRequest()` | 在 page/workspace 裡直接打 ZenOS API |
| Domain UI | 放 `features/<domain>` | 讓 `app/` 變成實作主體 |
| Page orchestration | 放 `use<Domain>Workspace()` | UI 與 async flow 長期混在同頁 |
| Feature 依賴 | `app -> features -> lib` | `features -> app` |

## Spec Compliance Matrix

| Refactor 目標 | Pattern | 現在的落點 | 驗證證據 |
|---|---|---|---|
| 1. workspace-aware API 收斂 | Shared API Transport | `src/lib/api-client.ts` + 三個 domain client 共用 | `lint` / `test` / `build` 綠 |
| 2. marketing 單檔系統拆分 | Feature Workspace + Page Hook | `features/marketing/MarketingWorkspace.tsx` + `useMarketingWorkspace.ts` | route wrapper 改為薄入口 |
| 3. protected shell 收斂 | Protected Layout Pattern | `app/(protected)/layout.tsx` | protected pages build 正常 |
| 4. team / clients page 變胖 | Page Hook Pattern | `useTeamWorkspace.ts`、`useClientsWorkspace.ts` | page orchestration 自 UI 抽離 |
| 5. API client 三套漂移 | Shared API Transport | `api.ts` / `crm-api.ts` / `marketing-api.ts` 共用 transport | client tests + build 通過 |

## 未驗風險點

以下風險在這次重構後仍未做完整驗證，不能假設已經沒事：

### R1. 真實瀏覽器的 workspace switch → read/write 鏈

- 尚未用 e2e 驗證使用者切 workspace 後：
  - `/tasks` 讀資料
  - `/team` invite / scope save
  - `/clients` stage 更新
  - `/marketing` create / save / review
- 目前只有 unit/integration + build，沒有真實 network trace 證明每條 mutation 都帶對 workspace header。

### R2. auth state 轉場

- 尚未 e2e 驗證：
  - invited 自動啟用
  - suspended 阻擋
  - `NO_PARTNER`
  - hard reload deep link 到 protected route
- layout 收斂後，這些流程雖然能編譯，但仍需要真實瀏覽器驗收。

### R3. CRM 拖曳與 modal flow

- `ClientsWorkspace` 的 DnD stage 更新目前只有程式級驗證。
- 尚未驗：
  - 真實拖曳手勢
  - rollback 視覺回退
  - modal 建單後看板即時更新

### R4. Marketing / CRM AI flow

- 尚未驗：
  - helper health check
  - permission request / result
  - resume / retry
  - structured apply
  - artifact mode 在真 helper 上的行為
- 現在通過的是靜態與單元層，不是完整人工/瀏覽器/本機 helper 串接驗收。

### R5. 附件與 signed URL

- `uploadToSignedUrl` 仍是允許的 raw fetch 例外。
- 尚未做完整 e2e：
  - attachment upload
  - delete
  - 權限與 stale UI 更新

### R6. bundle / 首屏效能

- 尚未量測：
  - route group 後的 bundle split
  - marketing workspace 拆分後的 chunk 大小
  - protected layout 對首屏 hydration 的影響

## 推薦驗證矩陣

### P0 驗證

1. owner 身分切 workspace，依序驗 `/tasks`、`/team`、`/clients`、`/marketing` 的 read + write
2. invited / suspended / no-partner 三種帳號狀態各自 deep-link 進 protected route
3. `/clients` 真實拖曳 stage，觀察成功與 rollback
4. `/marketing` 建 campaign、save strategy、save plan、review post
5. 任務附件 upload / delete 全流程

### P1 驗證

1. helper 連上本機後跑 marketing apply flow
2. helper 連上本機後跑 CRM briefing / debrief flow
3. 量測 `/marketing`、`/clients` 首屏與 chunk 大小

## 後續新增頁面必須遵守

### 新 page 開發

- 先建 `features/<domain>/...Workspace.tsx`
- route page 只做 wrapper
- 若需要 page-level orchestration，第一時間建 hook，不等 page 長胖才拆

### 新 API client

- 只能新增 domain adapter
- 不可再新增第四套 transport helper

### 新 protected route

- 直接掛到 `app/(protected)` 下
- 不可自己做 auth shell

## Done Criteria

要宣稱 dashboard frontend pattern 落地完成，至少必須同時滿足：

1. protected route 統一由 `app/(protected)/layout.tsx` 管 shell
2. 所有 ZenOS backend transport 經 `api-client.ts`
3. `features/` 不反向 import `app/(protected)`
4. page orchestration 已從 marketing、team、clients 三個高風險頁抽出 hook
5. `npm run lint`、`npm test`、`npm run build` 全綠
6. 未驗風險點已被明確列入驗證矩陣，而不是默默忽略
