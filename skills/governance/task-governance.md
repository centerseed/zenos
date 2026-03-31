# Task 治理規則 v1.0（含完整範例）

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。

## 建票範例：好 vs 不好的對比

### 不好的建票
```
title: auth 修改
description: 改一下 auth 相關的東西
acceptance_criteria: 完成
linked_entities: []
```
問題：title 沒動詞、description 缺三段結構、AC 不可驗收、linked_entities 空

### 好的建票
```
title: 實作 JWT refresh token 自動輪換
description: |
  背景：目前 JWT token 有效期 24 小時，用戶需要頻繁重新登入。
  問題：長期有效的 token 如果被竊取，攻擊視窗過大。
  期望結果：access token 有效期縮短為 1 小時，refresh token 自動輪換，
           用戶體驗不受影響。
acceptance_criteria:
  - access token 有效期為 1 小時，超過後自動使用 refresh token 換新
  - refresh token 使用後立即失效（one-time use）
  - 前端無感刷新（用戶不需要重新登入）
  - 所有 token 輪換操作有 audit log
linked_entities: ["用戶認證架構", "資安合規要求"]
plan_id: "plan-q1-security"
plan_order: 3
```

## 知識反饋範例（從 result 萃取 entry 的流程）

完成後的 result：
```
實作了 JWT refresh token 輪換。遇到問題：Redis 在 Cloud Run 無狀態環境下
需要特別處理 token 黑名單。最終採用 short-lived token + DB 記錄已用 token 方案。
性能影響：每次 refresh 多一次 DB 查詢，p99 增加 20ms，可接受。
```

從 result 萃取並寫回 ontology：

insight entry：
```
write(
  collection="entity_entries",
  data={
    "entity_name": "用戶認證架構",
    "type": "insight",
    "content": "Cloud Run 無狀態環境不適合 Redis token 黑名單，改用 DB 記錄已用 token，p99 增加 20ms"
  }
)
```

limitation entry：
```
write(
  collection="entity_entries",
  data={
    "entity_name": "用戶認證架構",
    "type": "limitation",
    "content": "每次 token refresh 需 DB 查詢，高頻刷新場景需要監控"
  }
)
```

## Plan 結構範例

計畫通常對應一個 milestone，tasks 按 plan_order 排序：

```
plan_id: "plan-q1-security"
plan_name: Q1 資安強化

plan_order 1: 審查現有 auth 流程（linked: 用戶認證架構）
plan_order 2: 建立資安 checklist（linked: 資安合規要求）
plan_order 3: 實作 JWT refresh token 輪換（linked: 用戶認證架構, 資安合規要求）
plan_order 4: 滲透測試與修復（linked: 資安合規要求）
plan_order 5: 更新 auth 架構文件（linked: 用戶認證架構）
```

## 禁止行為（含說明）

| 禁止行為 | 原因 |
|---------|------|
| title 不動詞開頭 | 無法快速判斷要做什麼 |
| description 缺三段結構 | 執行者缺少背景，容易做錯方向 |
| linked_entities 為空 | 切斷 task 與知識層的連結，失去 ontology 價值 |
| 完成後不更新 result | 知識無法流回 ontology，形成知識黑洞 |
| 直接 write status=done | 繞過驗收流程，AC 可能未達成 |

## 建立者顯示規則（強制簡化）

- `created_by` 必須是 owner 的 `partner.id`（不是 `architect`/`pm` 這類角色字串）。
- `updated_by` 必須是最後一次更新該 task 的 `partner.id`（create 時預設等於 `created_by`）。
- `assignee` 應填實際執行者的 `partner.id`；若暫時未知，需在 `description` 明確寫出預期 owner 與指派條件。
- 若任務是 agent 代開，寫入：
  - `source_metadata.created_via_agent = true`
  - `source_metadata.agent_name = "<agent-name>"`
- UI 一律顯示：
  - 非 agent：`<owner_name>`
  - agent 代開：`agent (by <owner_name>)`

## 狀態模型（2026-03-31）

- 允許狀態：`todo` / `in_progress` / `review` / `done` / `cancelled`
- `backlog` 併入 `todo`
- `blocked` 移除（仍可用 `blocked_by` + `blocked_reason` 描述阻塞）
- `archived` 併入 `done`
- 建票初始狀態只能是 `todo`
