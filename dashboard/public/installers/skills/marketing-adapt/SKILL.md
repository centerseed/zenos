---
name: marketing-adapt
description: >
  平台適配流程。把已確認主文案轉成各平台版本，並各自進入 `platform_adapted` 待確認狀態。
version: 0.1.0
---

# /marketing-adapt

## 目的

讓單一主文案可在不同平台快速重用，並維持平台語氣一致。

## 輸入

- `master_post_id`（必填）
- `project_id`（選填；若未提供則從 master post parent 推回）
- `platforms[]`（必填，例如 Threads/IG/FB/Blog）

## 執行步驟

1. 讀 master post，並取得其所屬 project
2. 逐平台組合文風：`product style + 對應 platform style + project style`
3. 逐平台生成 variant
4. 每個 variant 以 document 回寫（parent_id=master post 的 project）
5. `workflow_status=platform_adapted`
6. 回寫 entry（type=change）記錄適配批次與使用的 style 組合
