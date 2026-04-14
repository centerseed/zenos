---
name: crm-debrief
description: >
  會後自動分析 Activity 摘要，產出洞察和 follow-up 草稿（LINE + Email 雙版本），
  並回寫 crm_debrief 與 crm_commitment entries 到 ZenOS deal entity。
version: 0.1.0
---

# /crm-debrief

1. 讀 deal entity context（`get entities`）
2. 分析 activity summary，提取決策、顧慮、承諾、下一步
3. 生成 follow-up 草稿（LINE ≤300 字 + Email ≤500 字）
4. 回寫 crm_debrief entry（整體洞察）到 deal entity
5. 每個承諾事項獨立寫為 crm_commitment entry（含 owner/deadline/status=open）
