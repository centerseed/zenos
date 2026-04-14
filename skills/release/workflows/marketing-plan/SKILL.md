---
name: marketing-plan
description: >
  內容排程流程。根據 project 策略、近期成效與逐篇情報，產出未來兩週排程並回寫 ZenOS。
version: 0.1.0
---

# /marketing-plan

## 目的

產出可審核的兩週內容計畫，明確每篇主題、平台與理由。

## 輸入

- `project_id`（必填）
- `horizon_days`（選填，預設 14）

## 執行步驟

1. 讀 project：
```python
mcp__zenos__get(collection="entities", id="{project_id}")
```
2. 讀最近成效（published posts metrics）與近期 intel entries/documents
3. 若已有 topic 級 intel，排程時優先引用對應 topic 的洞察，不要只用整包摘要
3. 產出兩週排程：
- day/platform/topic/status(suggested)
- ai_note（為何這樣排）
4. 回寫 project `details.marketing.content_plan`
5. 補一筆 entry（type=insight）說明本輪排程邏輯
