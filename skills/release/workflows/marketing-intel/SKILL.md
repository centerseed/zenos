---
name: marketing-intel
description: >
  行銷情報蒐集流程。整理社群高互動內容、競品訊號與選題方向，
  並回寫到 ZenOS project entity（document + entry）。
version: 0.1.0
---

# /marketing-intel

## 目的

用最少手動整理成本，為 project 建立本輪情報摘要。

## 輸入

- `project_id`（必填）
- `keywords[]`（必填）
- `topics[]`（選填，若有則逐篇整理 per-topic intel）
- `time_window`（選填，預設 14d）

## 執行步驟

1. 讀取 project context：
```python
mcp__zenos__get(collection="entities", id="{project_id}")
```
2. 依 `keywords` 蒐集平台訊號（Threads/IG/FB/Blog），整理：
- 高互動主題
- 主要痛點
- 可切入 hook
3. 若提供 `topics[]`，針對每個 topic 額外整理：
- topic-specific hook
- audience angle
- CTA 建議
4. 回寫 document（intel report）
4. 回寫 entry（insight 摘要，<=200 字）

## 回寫規範

- document：放完整情報；若有 `topics[]`，需能清楚區分每個 topic 的 intel 區塊
- entry：放「本輪關鍵洞察」一句話
- 不新增 MCP tool，只用既有 `get/write`
