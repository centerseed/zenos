---
type: ADR
id: ADR-012
status: Accepted
ontology_entity: ZenOS MCP Server
created: 2026-03-30
updated: 2026-03-30
---

# ADR-012: MCP Write Safety — Audit Log + Attribution

## 背景

2026-03-30 dogfooding 發現：paceriz 的 L2 entities 在 web Dashboard 上完全不見。
調查過程揭露兩個結構性問題：

1. **Firestore/SQL 雙寫不一致**：MCP production server 未完整切換到 SQL，Firestore
   仍有資料但 SQL 沒有，Dashboard 查 SQL 什麼都撈不到。

2. **MCP write 沒有 audit trail**：任何持有 API key 的 agent 都可以寫入 entity，
   不留下誰寫、寫什麼、寫之前是什麼的記錄。資料被寫壞時無從追查、無法 rollback。

資料不一致的直接觸發點是：某個 MCP write 操作在 Firestore 寫成功，但 SQL 沒有同步，
或者 production server 根本沒有連到 SQL。

## 問題分析

### 現有防護的邊界

目前 MCP write 有的防護：
- 格式驗證（三問、parent_id、impacts 等）
- partner_id 綁定（API key 對應特定 partner）

目前沒有的防護：
- **Write audit log**：每筆 write 沒有 before/after snapshot
- **寫入方身份**：不知道是哪個 agent session 寫的
- **跨儲存層一致性**：Firestore 和 SQL 沒有強制同步機制
- **Rollback 機制**：資料寫壞後只能靠人工修復

### 風險矩陣

| 風險 | 機率 | 影響 | 優先度 |
|------|------|------|--------|
| Agent 寫入錯誤 level/status | 高 | 中（顯示異常） | P1 |
| Agent 把正確資料覆蓋掉 | 中 | 高（資料遺失） | P0 |
| Firestore/SQL 不一致 | 已發生 | 高（整個 partner 看不到資料） | P0 |
| API key 洩漏後大量寫壞 | 低 | 極高（全毀） | P1 |

## 決策

**實作 Write Audit Log + Write Attribution。**

不選「write 需要人工 approve」（太高摩擦，破壞 AI 自動化）。
不選「只有 dashboard 能寫」（破壞 MCP 工具模型）。
選「寫就記錄，壞了能查能回」。

### 核心機制

1. **`entity_audit_log` 表**（新增）
   - 每次 entity upsert 之前，把當前值存一份 snapshot
   - 記錄：`partner_id`, `entity_id`, `operation` (create/update), `changed_by`,
     `before_json`, `after_json`, `created_at`
   - `changed_by` = MCP 呼叫方的標識（agent session id 或 tool call source）

2. **`write` MCP tool 新增 `caller` 參數**（optional）
   - Agent 可以傳 `caller="zenos-governance-agent"` 標明自己是誰
   - 不傳則記為 `"unknown-agent"`

3. **`get_audit_log` MCP tool**（新增，admin only）
   - 查詢特定 entity 的修改歷史
   - 返回 before/after diff

4. **`rollback_entity` admin script**（新增）
   - 非 MCP tool（不對外暴露）
   - 從 audit log 恢復 entity 到指定版本

### 不做的事

- 不實作 write queue / human approval（太重）
- 不限制哪些欄位可以改（太複雜）
- `rollback_entity` 只做成 admin script，**絕不暴露為 MCP tool**（見 ADR-008 紅線）

## 考慮過的替代方案

| 方案 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| Write approval queue | 人為把關，資料最安全 | AI 自動化完全中斷，無法用於 pipeline | 不選 |
| 只在 dashboard 允許 write | 有人在場才能改 | 破壞 MCP 工具模型，所有 agent 任務都不能寫 | 不選 |
| Audit log（本方案） | 低摩擦，事後可查可回 | 壞資料還是會寫進去 | 選 |
| 欄位級鎖定 | 精細控制 | 維護成本高，schema 每次改都要改鎖定規則 | 未來可選 |

## 後果

- 每次 entity write 多一次 INSERT（效能影響極小）
- Agent 需要傳 `caller` 參數（非強制，但建議）
- 資料被寫壞後可在 30 秒內查到是誰寫的、寫了什麼
- Audit log 需要定期清理（建議保留 90 天）

## 實作順序

1. 新增 `entity_audit_log` SQL migration
2. `sql_repo.py` 的 `upsert` 加 audit 邏輯
3. `tools.py` 的 `write` tool 加 `caller` 參數
4. 新增 `get_audit_log` MCP tool（admin only）
5. 新增 `scripts/rollback_entity.py` admin script
