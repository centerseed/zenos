---
name: marketing-publish
description: >
  發佈流程。把已核准平台文案送到 Postiz（或 dry-run），再回寫排程結果與狀態。
version: 0.1.0
---

# /marketing-publish

## 目的

把文案從審核狀態推進到可追蹤的已排程/已發佈狀態。

## 輸入

- `post_id`（必填）
- `schedule_at`（必填，ISO datetime）
- `channel_account_id`（必填）
- `dry_run`（選填，預設 true）

## 執行步驟

1. 讀 post entity 與其所屬 project，確認 `workflow_status in {platform_confirmed, scheduled}`
2. 組 Postiz payload（content/schedule/account）
3. dry-run=true：只輸出 payload 預覽，不呼叫外部 API
4. dry-run=false：呼叫 Postiz API
5. 回寫 `details.marketing`：
- `workflow_status` -> `scheduled` 或 `published`
- `postiz_job_id`
- `published_at`（若已發）
6. 補 entry（type=change）保存發佈結果
