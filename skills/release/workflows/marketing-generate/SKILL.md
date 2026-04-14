---
name: marketing-generate
description: >
  主文案生成流程。依 strategy + per-topic intel + style composition + 產品知識，產生主體文案與圖片 brief。
version: 0.1.0
---

# /marketing-generate

## 目的

快速產出可審核的主文案（master post）與圖片 brief。

## 輸入

- `project_id`（必填）
- `topic`（必填）
- `platform_hint`（選填）
- `revision_note`（選填）

## 執行步驟

1. 讀 project strategy + 與 `topic` 最接近的 intel（優先 topic-specific intel，沒有才退回 project-level intel）
2. 組合文風：`product style + platform style + project style`
2. 生成：
- title
- preview/body
- CTA
- image_brief
3. 建立 L3 post entity（type=document, parent_id=project_id）
4. 設定 `details.marketing.workflow_status=draft_generated`
5. 回寫 entry（type=change）附上生成依據，需明確記錄使用的 intel 與 style 組合
