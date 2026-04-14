---
name: crm-briefing
description: >
  商談前 AI 簡報流程。依 deal context pack 生成結構化簡報，
  並回寫到 ZenOS deal entity（type: crm_briefing）。
version: 0.1.0
---

# /crm-briefing

1. 讀 deal entity context（`get entities`）
2. 依可用資料分層產出：客戶背景、互動回顧、產品現況、本次建議
3. 回寫 crm_briefing entry 到 deal entity
