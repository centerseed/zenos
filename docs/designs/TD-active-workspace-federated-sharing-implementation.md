---
type: TD
doc_id: TD-active-workspace-federated-sharing-implementation
title: 技術設計：Active Workspace 與 Federated Sharing 實作
ontology_entity: 身份與權限管理
status: approved
version: "1.0"
date: 2026-04-08
supersedes: null
---

# 技術設計：Active Workspace 與 Federated Sharing 實作

## 調查報告

### 已讀文件（附具體發現）
- `docs/specs/SPEC-identity-and-access.md`
  發現：SSOT 已正式收斂為 `home workspace + active workspace context + product(L1) sharing`，並明確要求 `Projects -> Products`。
- `docs/decisions/ADR-018-identity-access-runtime-alignment.md`
  發現：v2 已把決策面擴大到 workspace、ontology、navigation、route guard、visibility、application boundary。
- `docs/specs/TC-identity-and-access.md`
  發現：已經有可直接映射實作的 P0/P1 驗收場景，包含 `我的工作區`、picker 升級、guest subtree、Products rename。
- `dashboard/src/components/AppNav.tsx`
  發現：目前 nav 仍用 `workspaceRole` 直接切 `owner/member/guest`，且 guest 只有 `Projects / Tasks`。
- `dashboard/src/lib/partner.ts`
  發現：目前 runtime helper 只產出單一 `workspaceRole`，沒有表達 `home/shared workspace` 與 `active workspace context`。

### 搜尋但未找到
- 未找到既有 TD 完整定義 `workspace picker / 我的工作區 / Products rename / shared subtree query slicing`。
- 未找到既有 server contract 明確定義 `active workspace` 如何隨每次登入與切換傳遞到所有查詢。

### 我不確定的事（明確標記）
- [未確認] 目前 dashboard 的 workspace membership / switcher backend API 是否已存在可直接複用的欄位。
- [未確認] `project(L3)` 的多重隸屬查詢，目前 graph query 是否已有原生支援，或需在 application layer 補裁切。

### 結論
可以開始設計。核心工作不是單點修 nav，而是把 `active workspace context` 變成前後端一致的執行單位。

## Spec Compliance Matrix

| Spec 需求 ID | 需求描述 | 實作方式 | 預計 File:Line | 測試覆蓋 |
|-------------|---------|---------|---------------|---------|
| S1/S2 | 登入後自動回 home workspace | auth bootstrap 決定 active workspace fallback | `dashboard/src/lib/auth*`, server session context | 單元 + integration |
| S3/S4 | 單一 workspace 顯示我的工作區，多個時升級 picker | 新增 workspace entry component | `dashboard/src/components/*Workspace*` | UI test |
| S5/S6 | shared/home workspace 顯示不同 surface | nav 改讀 active workspace context | `dashboard/src/components/AppNav.tsx` | UI + route test |
| S7/S8/S14/S15 | guest 只見授權子樹與 public | server query slicing + graph rendering filter | server query layer + knowledge map page | permission regression |
| S9 | member 看整個 workspace | role-based server filter | server query layer | permission regression |
| S10/S11/S12/S13/S18 | guest 可建 task/L3，不可建 L1/L2 | create form + write guard | create flows + server write guard | integration |
| S16 | Projects 改名 Products | nav / route / copy surface 收斂 | dashboard copy + routes | UI snapshot |
| S17 | 非 active workspace 更新 badge | workspace switcher metadata | switcher component + API | UI test |
| S19 | 撤銷授權後移除 assignee | revoke flow server-side cleanup | membership/revoke service | integration |

## Component 架構

### 1. Workspace Context Layer

新增單一來源的 `ActiveWorkspaceContext`，提供：

- `activeWorkspaceId`
- `homeWorkspaceId`
- `workspaceRole`
- `authorizedEntityIds`
- `isHomeWorkspace`
- `availableWorkspaces`

前端所有 nav / route guard / page query 都只能讀這個 context，不可再直接讀裸 `partner.accessMode`。

### 2. Navigation Layer

`AppNav` 改為兩階段判斷：

1. 先判斷 `isHomeWorkspace`
2. 再判斷 `workspaceRole`

規則：

- `isHomeWorkspace=true` → 完整 app surface
- `isHomeWorkspace=false` 且 `workspaceRole in {member, guest}` → `Knowledge Map / Products / Tasks`
- `Products` 取代所有面向使用者的 `Projects` 文案

### 3. Workspace Entry Layer

新增統一入口元件：

- 單一 workspace → 顯示 `我的工作區`
- 多 workspace → 升級為 `workspace picker`
- picker item 支援更新 badge

此元件的位置固定，不因是否多 workspace 而改變區塊位置。

### 4. Query Slicing Layer

後端查詢必須以 `active workspace context` 為條件進行過濾：

- `owner` → active workspace 全域
- `member` → active workspace 全域 + visibility
- `guest` → `authorizedEntityIds` 對應的 `product(L1)` 子樹 + `public`

知識圖譜查詢需補：

- 未授權節點不回傳
- 未授權 impact / relation 不回傳
- 多重隸屬 L3 若命中任一授權 L1，可回傳節點本身；但 relation expansion 僅回傳授權範圍部分

### 5. Write Guard Layer

建立與更新路徑需統一走 server guard：

- `guest` 可建 `task`
- `guest` 可建 `L3`
- `guest` 建 `L3` 時必須提供至少一個授權範圍內的 `L2`
- `guest` 不可建 `L1 / L2`
- `guest` 新建 `L3` 預設 `visibility=public`

### 6. Application Boundary Layer

shared workspace 先只暴露：

- `Knowledge Map`
- `Products`
- `Tasks`

以下模組在 shared workspace 一律不顯示：

- CRM
- Team
- Setup
- 其他 application layer

未來若要擴充企業版共享面，需新增 feature flag 或 workspace policy，不能直接在現有 role 上疊例外。

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `resolveActiveWorkspace()` | user/session | object | 是 | 決定 home workspace 與 active workspace |
| `listAvailableWorkspaces()` | user_id | string | 是 | 回傳 switcher 所需 workspace 清單與 badge metadata |
| `getWorkspaceSurface()` | active_workspace_id, workspace_role, is_home_workspace | string/bool | 是 | 前端 surface 決策輸入 |
| `filterKnowledgeGraph()` | active_workspace_id, workspace_role, authorized_entity_ids | object | 是 | server-side graph/data slicing |
| `validateEntityCreate()` | workspace_role, active_workspace_id, linked_l2_ids, entity_type | object | 是 | 驗證 guest 建立 L3 / 禁止 L1/L2 |
| `revokeWorkspaceAccess()` | member_id, revoked_l1_ids | string/list | 是 | 撤銷授權並清理 task assignee |

## DB Schema 變更

目前暫定無硬性 schema 變更；優先確認現有 membership / partner 欄位是否足以承載：

- `home workspace`
- `active workspace`
- `authorized_entity_ids`
- workspace 更新 badge 所需 metadata

若現有 schema 不足，再另開 migration：

- 儲存 last active workspace
- 儲存 workspace-level unread/update counters

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|---------------|
| 1 | 收斂 active workspace context contract | Developer | 前後端可一致取得 `isHomeWorkspace / workspaceRole / authorizedEntityIds` |
| 2 | 重做 nav 與 workspace entry | Developer | 單一 workspace 顯示 `我的工作區`，多 workspace 顯示 picker，nav 完成 `Products` rename |
| 3 | 補 server-side query slicing | Developer | guest/member/owner 在 graph、task、doc 查詢上符合新授權規則 |
| 4 | 補 write guard | Developer | guest 可建 L3/task，不可建 L1/L2 |
| 5 | 補 route guard | Developer | 所有頁面依 active workspace context 裁切 |
| 6 | 補 QA 驗收 | QA | `TC-identity-and-access` P0 全通過 |

## 風險

1. 現有前端大量直接依賴 `workspaceRole`，若不先建立 `ActiveWorkspaceContext`，會在各頁留下分叉邏輯。
2. `Projects -> Products` 可能不只影響 copy，也影響 route naming、analytics 與測試快照。
3. 多重隸屬 L3 的裁切若做在前端而不是 server，容易洩漏未授權關聯。
4. shared workspace 的 application boundary 若只做 UI 隱藏、不做 server guard，會留下越權風險。

## 驗證策略

- Permission regression：owner / member / guest 對同一組資料的 graph / task / doc 可見性
- UI regression：單一 workspace、雙 workspace、shared workspace guest/member
- Route regression：直接打 `/clients`、`/setup`、`/team` 在 shared workspace 下的阻擋行為
- Copy regression：所有主導航與頁面標題不再使用 `Projects` 作為主語意

## 驗收記錄

- 日期：2026-04-08
- 版本：1.0
- QA Verdict：PASS
- TC-identity-and-access P0 場景：S1–S16 全部通過
- Regression：Backend 540 passed（S08 相關範圍） / Frontend 191 passed，無新增 failure
- [未確認] 項目解決狀態：
  - workspace membership/switcher backend API：確認 `sharedPartnerId` 欄位可承載 home/shared workspace 判斷
  - project(L3) 多重隸屬查詢：確認 server-side 裁切在 `ontology_service._is_entity_visible_for_partner` 實作（`_collect_subtree_ids` 對所有授權 L1 取聯集）
