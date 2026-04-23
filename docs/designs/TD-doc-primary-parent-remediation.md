---
doc_id: TD-doc-primary-parent-remediation
title: 技術設計：歷史 doc entity primary parent 後補機制
type: DESIGN
ontology_entity: L3 文件治理
status: Accepted
version: "1.0"
date: 2026-04-23
supersedes: null
---

# TD: 歷史 doc entity primary parent 後補機制

## 背景

ADR-046 已拍板：歷史 `document_entities` 在 backfill 時只能完整保留「有關聯」，無法可靠恢復「哪一個是 primary parent」，因為舊 schema 根本沒有順序欄位。

所以 migration 的正確策略不是瞎猜，而是：
- 所有歷史關聯先收斂成 `relationships(type='related_to')`
- 所有歷史 doc entity 先落成 `parent_id = NULL`
- 額外留下可追蹤、可補件、可驗收的 remediation metadata

## 決策

### D1. 載體：直接寫在 document entity 的 `details.primary_parent_remediation`

不新增新表，也不復用 blindspot / entry。

理由：
- 這是單一 document entity 的補件狀態，不是新的治理 primitive
- migration 當下就能原地寫入，不需要再維護第二份 state
- 後續 Dashboard / governance loop / MCP 都能直接從 entity 本身撈出 pending 清單

建議結構：

```json
{
  "primary_parent_remediation": {
    "status": "pending",
    "reason": "historical_document_entities_lacked_order",
    "candidate_parent_ids": ["entity_a", "entity_b"],
    "backfilled_at": "2026-04-23T00:00:00Z",
    "resolved_at": null,
    "resolved_by": null
  }
}
```

### D2. 後補 UX：沿用既有 document update 流程，不另開 wizard

操作方式：
1. 治理工具先列出 `type='document' and parent_id is null and details.primary_parent_remediation.status='pending'`
2. 人或 agent 用既有 document update / entity upsert 流程補 `parent_id`
3. 同步把 remediation 狀態改成 `resolved`

理由：
- 問題本質是「先把待補清單穩定撈出」，不是缺一個新 UI
- 已有文件編輯流程本來就能處理 parent/linked entity 變更，重做只會製造第二套路徑

### D3. SLA：migration 後 7 天內補完

SLA：
- `pending` 7 天內應補完 primary parent
- 超過 7 天列為 yellow risk
- 超過 14 天列為 red risk，不能宣稱此波 document/entity consolidation 已完整收口

理由：
- 這批資料是有限集合，不是長期常態 queue
- 沒有 SLA，`parent_id = NULL` 很容易變成永久半成品

## 執行流程

### Migration 階段

對每一筆歷史 document：
1. backfill 成 `entities(type='document')`
2. `parent_id = NULL`
3. 原 `document_entities` 全寫成 `relationships(type='related_to')`
4. `details.primary_parent_remediation.status = 'pending'`
5. `candidate_parent_ids =` 歷史相關 entity ids

### Remediation 階段

1. 治理掃描列出 pending 文件
2. 人或 agent 判定 primary parent
3. 更新 document entity：
   - `parent_id = chosen_parent_id`
   - `details.primary_parent_remediation.status = 'resolved'`
   - `details.primary_parent_remediation.resolved_at = now`
   - `details.primary_parent_remediation.resolved_by = actor`

## 驗證

- migration 後能穩定 query 出所有 pending 文件
- 補 parent 後，不會丟失既有 `related_to` 關聯
- governance loop 能依 SLA 標出逾期 pending 文件

## 不做的事

- 不新增新 SQL table
- 不在 migration 當下自動猜 primary parent
- 不把這個狀態塞進 blindspot 或 entity entry
