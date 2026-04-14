---
name: marketing-publish
description: >
  發佈流程。把已核准平台文案送到 Postiz（或 dry-run），再回寫排程結果與狀態。
version: 0.1.0
---

# /marketing-publish

1. 讀 post 並驗證 `workflow_status in {platform_confirmed, scheduled}`
2. 建 Postiz payload（支援 dry-run）
3. 回寫 `workflow_status/postiz_job_id/published_at`
