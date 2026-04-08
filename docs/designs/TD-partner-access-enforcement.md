---
type: TD
id: TD-partner-access-enforcement
status: Draft
ontology_entity: 夥伴身份與邀請
created: 2026-04-06
updated: 2026-04-06
---

# Technical Design: Partner Access Enforcement 對齊實作

## 對應 Spec

- `docs/specs/SPEC-partner-access-scope.md`
- `docs/specs/SPEC-permission-model.md`

## 問題本質

現況把兩個維度混在一起：

1. `sharedPartnerId` 被正確用來做 tenant routing
2. `authorizedEntityIds` 卻同時被拿來猜身份

結果是 `authorizedEntityIds=[]` 的 non-admin 被當成 internal member，繞過新 spec 要求的「未指派空間不可見任何 tenant 資料」。

本次修正的第一性原理是：

- tenant routing 與資料可見性必須分離
- scope list 只描述「被分享哪些 L1」
- partner 身份必須是明確狀態，不能再用空 scope 猜

## 最小必要改動

### 1. Partner model 新增 `access_mode`

在 `zenos.partners` 新增：

- `access_mode text not null default 'unassigned'`

允許值：

- `internal`
- `scoped`
- `unassigned`

語意：

- `internal`: 跨 tenant 內所有 L1 工作，仍受 visibility 規則限制
- `scoped`: 只能看到 `authorized_entity_ids` 對應的 L1 product 子樹
- `unassigned`: 可登入，但看不到任何 tenant data

保留既有欄位語意：

- `shared_partner_id`: tenant routing only
- `authorized_entity_ids`: 僅供 `access_mode='scoped'` 使用的 L1 分享清單
- `is_admin`: admin override；admin 永遠視為 full access，不依賴 `access_mode`

### 2. Server 端統一 Partner Access 判斷

新增一組共用 helper，輸出標準化 access context：

- `is_admin`
- `access_mode`
- `authorized_l1_ids`
- `is_internal_member`
- `is_scoped_partner`
- `is_unassigned_partner`

判斷規則：

- admin: 永遠 full access
- non-admin + `access_mode='internal'`: internal member
- non-admin + `access_mode='scoped'`: scoped partner
- non-admin + `access_mode='unassigned'`: unassigned partner
- 若舊資料尚未帶 `access_mode`：以相容策略推導
  - `authorized_entity_ids` 有值 → `scoped`
  - 否則 → `unassigned`

注意：不再存在「empty scope = internal」的 fallback。

### 3. Dashboard API / MCP / OntologyService 一起改

所有 server-side read path 必須共用同一套判斷，至少涵蓋：

- `src/zenos/interface/dashboard_api.py`
- `src/zenos/interface/tools.py`
- `src/zenos/application/ontology_service.py`

規則：

- `unassigned`:
  - entities/documents/relationships/tasks/blindspots/protocols 全部回空
  - by-id / by-entity 查詢回空或 404，不洩漏存在性
- `scoped`:
  - 先做 L1 subtree scope filter，再套 visibility
- `internal`:
  - 不做 L1 scope filter，但仍套 internal visibility 規則

### 4. Invite / Activate / Team Scope UI 對齊

後端 API：

- `POST /api/partners/invite`
  - 支援 `access_mode`
  - 預設 `unassigned`
  - 若 `access_mode='scoped'`，可帶 `authorized_entity_ids`
  - 若 `access_mode in ('internal', 'unassigned')`，server 會將 `authorized_entity_ids` 寫成空陣列
- `PUT /api/partners/{id}/scope`
  - 支援 `access_mode`
  - admin 可明確切換 `internal | scoped | unassigned`
  - `scoped` 才保留 L1 scopes；其他模式清空
- `POST /api/partners/activate`
  - 只改登入狀態與 API key，不變更 `access_mode`

前端 UI：

- 邀請表單：新增 access mode 選擇，預設 `unassigned`
- Team scope editor：從舊的 `isExternalClient` checkbox 改成明確三態
- AppNav：`unassigned` 不應沿用 internal base nav
- Tasks page：以 `accessMode === 'unassigned'` 顯示未設定空間提示

## Migration / 相容策略

### SQL migration

新增 migration：

```sql
alter table zenos.partners
  add column if not exists access_mode text not null default 'unassigned';

alter table zenos.partners
  drop constraint if exists chk_partners_access_mode;

alter table zenos.partners
  add constraint chk_partners_access_mode
  check (access_mode in ('internal', 'scoped', 'unassigned'));

update zenos.partners
set access_mode = case
  when is_admin then 'internal'
  when coalesce(array_length(authorized_entity_ids, 1), 0) > 0 then 'scoped'
  when status = 'active' then 'internal'
  else 'unassigned'
end
where access_mode is null
   or access_mode not in ('internal', 'scoped', 'unassigned');
```

### Runtime fallback

在 migration 未跑到所有環境前，runtime helper 仍要容忍缺欄位或舊 partner dict。

fallback policy：

- 有明確 `accessMode` / `access_mode` → 直接使用
- 無欄位但 `authorized_entity_ids` 有值 → `scoped`
- 無欄位且 `status='active'` → 視為舊 internal member，暫時 `internal`
- 其他 → `unassigned`

這個 fallback 只用於過渡期，目的是避免 migration 上線瞬間把既有 active internal 成員鎖在門外；新建立 partner 一律應寫入明確 `access_mode`。

## Spec 介面合約清單

本次必須對齊的介面與參數：

1. Partner API payload
   - `access_mode`
   - `authorized_entity_ids`
   - `shared_partner_id`
   - `is_admin`
2. Dashboard `/api/partner/me`
   - 必須回傳 `partner.accessMode`
3. Dashboard `/api/partners/invite`
   - 必須接受 `access_mode`
   - 必須在 `access_mode!='scoped'` 時清空 scope
4. Dashboard `/api/partners/{id}/scope`
   - 必須接受與回傳 `access_mode`
5. Dashboard data read APIs
   - `GET /api/data/entities`
   - `GET /api/data/entities/{id}`
   - `GET /api/data/tasks`
   - `GET /api/data/tasks/by-entity/{entityId}`
   - `GET /api/data/blindspots`
6. MCP read path
   - `search`
   - `get`
   - visibility helper 相關 path

## Done Criteria

| # | Criteria |
|---|----------|
| 1 | `partners` model 與 repository 能讀寫 `access_mode`，並有 migration 保證欄位存在與值合法 |
| 2 | Dashboard API 與 MCP tools 不再用 `bool(authorizedEntityIds)` 推導 partner 身份 |
| 3 | `access_mode='unassigned'` 的 non-admin 在所有 server-side read path 都拿不到 tenant data |
| 4 | `access_mode='internal'` 的 non-admin 仍可跨 L1 工作，但保持既有 visibility 限制 |
| 5 | `access_mode='scoped'` 只可見被分享的 L1 subtree，且 entity/document 仍受 visibility 規則限制 |
| 6 | 邀請、啟用、team scope UI/API 都能明確設定與顯示 `internal/scoped/unassigned` |
| 7 | 前端 unassigned UX 與 server enforcement 一致，不再只靠局部頁面提示 |
| 8 | 測試覆蓋 dashboard API、MCP、admin invite/scope API、frontend nav/tasks/team，證明空 scope 看不到資料 |

## 測試矩陣

### Backend

- Dashboard API
  - non-admin + `accessMode='unassigned'` + empty scope → entities/tasks/blindspots 空結果
  - non-admin + `accessMode='internal'` + empty scope → 可見 public cross-L1 data
  - non-admin + `accessMode='scoped'` + empty scope → 空結果
  - non-admin + `accessMode='scoped'` + one L1 → 僅該 subtree
- MCP tools
  - `search(collection='entities')` 對 unassigned 回空
  - `search(collection='tasks')` 對 unassigned 回空
  - `get(entity)` 對 out-of-scope / unassigned 不洩漏
- Admin API
  - invite 預設建立 `accessMode='unassigned'`
  - scope update 可切換三態
  - `internal/unassigned` 會清空 `authorizedEntityIds`

### Frontend

- AppNav
  - internal: full base nav
  - scoped: scoped nav
  - unassigned: restricted nav + setup only
- Tasks page
  - unassigned 顯示「尚未設定存取空間」
  - internal/scoped with scope 不顯示
- Team page
  - badge 與 editor 顯示明確 access mode
  - invite form 可選三態

## 風險與取捨

### 為什麼不是只改 helper、不加欄位？

因為只改 helper 仍無法分辨：

- internal member with empty scope
- unassigned partner with empty scope

這會把產品語意再度藏回推導邏輯，未來維護會持續歧義。

### 為什麼用 `access_mode` 而不是重用 `status`？

`status` 是帳號生命週期：

- invited
- active
- suspended

`access_mode` 是資料可見性身份，兩者是正交維度，不能混用。
