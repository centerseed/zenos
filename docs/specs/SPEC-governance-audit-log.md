# SPEC: Ontology 治理審計日誌（Governance Audit Log）

> PM: Claude (PM role) | Date: 2026-03-25 | Status: Draft

## 問題

ZenOS 的 GovernanceAI 會在每次寫入時自動推斷 type、parent、impacts、關聯，
但這些決策過程完全沒有持久化紀錄。用戶無法回答：

- 「這個節點的 type 是誰在什麼時候改的？」
- 「GovernanceAI 幫我自動建了哪些關聯？」
- 「過去一週 ontology 有哪些變動？」

對於需要對 AI 決策負責的中小企業場景，這是信任缺口。

## 目標

1. **所有 ontology 變動都有結構化審計日誌**，寫入 Cloud Logging
2. **固定欄位 schema**，讓查詢簡單到一行 filter
3. **未來可直接在 Dashboard 顯示**（透過 Cloud Logging API 查詢）

## 非目標

- 不做 Firestore subcollection 儲存（用 Cloud Logging 就好，省成本）
- 不做即時 streaming（先做查詢拉取）
- 不做 rollback（先有紀錄，回滾是未來功能）

---

## 事件類型（Event Types）

| event_type | 觸發時機 | 說明 |
|---|---|---|
| `entity.created` | 新建 entity | 含 GovernanceAI 推斷結果 |
| `entity.updated` | 更新 entity | 含 changed_fields diff |
| `entity.confirmed` | 用戶確認 entity | 信任等級變更 |
| `entity.deleted` | 刪除 entity | 軟刪除紀錄 |
| `relationship.created` | 新建關聯 | 含 auto/manual 來源 |
| `relationship.deleted` | 刪除關聯 | |
| `document.created` | 新建 document | 含自動 entity 連結 |
| `document.updated` | 更新 document | |
| `task.created` | 新建 task | 含自動 entity/blindspot 連結 |
| `task.status_changed` | 任務狀態變更 | 含 from → to |
| `governance.auto_classify` | AI 自動分類 | type/parent 推斷 |
| `governance.auto_relate` | AI 自動建關聯 | 推斷的 relationships |
| `governance.auto_link_doc` | AI 自動連結文件 | 推斷的 doc↔entity 連結 |
| `governance.quality_check` | 品質檢查執行 | 結果摘要 |
| `governance.blindspot_found` | 發現盲點 | severity + 描述 |

---

## 結構化欄位 Schema

每筆 audit log 是一個 structured JSON payload，寫入 Cloud Logging：

```json
{
  "severity": "INFO",
  "message": "entity.created: 客戶管理系統",
  "logging.googleapis.com/labels": {
    "service": "zenos-mcp",
    "partner_id": "abc123"
  },
  "jsonPayload": {
    "event_type": "entity.created",
    "timestamp": "2026-03-25T10:30:00Z",
    "partner_id": "abc123",
    "project": "zenos",
    "actor": {
      "type": "agent|user|system",
      "id": "claude-code-session-xyz",
      "label": "Claude Code (PM)"
    },
    "target": {
      "collection": "entities",
      "id": "entity-123",
      "name": "客戶管理系統",
      "type": "product"
    },
    "changes": {
      "field": "type",
      "before": null,
      "after": "product"
    },
    "governance": {
      "auto_inferred": true,
      "model": "gemini-2.0-flash-lite",
      "confidence": 0.93,
      "reasoning": "名稱含『系統』，現有 ontology 無同名 entity"
    },
    "context": {
      "tool": "write",
      "caller_hint": "zenos-capture skill",
      "related_entities": ["entity-456", "entity-789"]
    }
  }
}
```

### 欄位說明

| 欄位 | 必填 | 說明 |
|---|---|---|
| `event_type` | Y | 事件類型（見上表） |
| `timestamp` | Y | ISO-8601 UTC |
| `partner_id` | Y | 租戶 ID |
| `project` | N | 專案識別碼 |
| `actor.type` | Y | `agent`（AI caller）/ `user`（人類）/ `system`（自動治理） |
| `actor.id` | Y | 操作者 ID（agent session / user UID / "governance-ai"） |
| `actor.label` | N | 人類可讀名稱 |
| `target.collection` | Y | entities / relationships / documents / tasks / blindspots |
| `target.id` | Y | 目標 ID |
| `target.name` | N | 人類可讀名稱 |
| `target.type` | N | entity type 等 |
| `changes` | N | `{ field, before, after }` 或陣列（多欄位變更） |
| `governance` | N | AI 治理決策詳情（僅 governance.* 事件） |
| `governance.auto_inferred` | N | 是否為 AI 自動推斷 |
| `governance.model` | N | 使用的 LLM model |
| `governance.confidence` | N | 信心分數 |
| `governance.reasoning` | N | 推斷理由 |
| `context.tool` | N | 觸發的 MCP tool 名稱 |
| `context.caller_hint` | N | caller 傳入的來源提示 |
| `context.related_entities` | N | 關聯的 entity IDs |

---

## 查詢模式

### Cloud Logging Filter 範例

```
# 查某個 partner 過去 7 天所有 entity 變動
resource.type="cloud_run_revision"
jsonPayload.partner_id="abc123"
jsonPayload.event_type=~"^entity\."
timestamp>="2026-03-18T00:00:00Z"

# 查所有 GovernanceAI 自動決策
jsonPayload.governance.auto_inferred=true
jsonPayload.partner_id="abc123"

# 查某個 entity 的完整歷史
jsonPayload.target.id="entity-123"

# 查某個 project 的任務狀態變更
jsonPayload.event_type="task.status_changed"
jsonPayload.project="zenos"
```

### Dashboard 查詢 API（未來）

Dashboard 透過 backend API proxy 查詢 Cloud Logging，不直接暴露 GCP credentials：

```
GET /api/audit-log?partner_id=abc123&event_type=entity.*&days=7
GET /api/audit-log?target_id=entity-123
GET /api/audit-log?governance_only=true&days=30
```

回傳分頁 JSON，前端用 timeline 組件顯示。

---

## 驗收條件

1. **所有 ontology 寫入操作**（entity/relationship/document/task CRUD）都產出結構化 audit log
2. **所有 GovernanceAI 推斷**都記錄 model、confidence、reasoning
3. **Cloud Logging filter** 可用上述範例一行查到結果
4. **不影響寫入延遲** — logging 是 fire-and-forget，不阻塞 MCP response
5. **本地開發** 時 audit log 輸出到 stdout（JSON 格式），不依賴 GCP

---

## 用戶故事

1. **作為公司負責人**，我想看「過去一週 AI 幫我做了哪些 ontology 決策」，這樣我能信任 AI 的判斷
2. **作為 Architect**，我想查「某個 entity 被修改的完整歷史」，這樣我能追蹤問題根因
3. **作為 PM**，我想看「任務狀態變更 timeline」，這樣我能了解專案進度
4. **作為 DevOps**，我想用 Cloud Logging 的標準工具查 audit log，不用學新工具

---

## 備註

- Cloud Run 上 Python 的 `print()` / `logging` 輸出會自動被 Cloud Logging 收集
- 只要輸出格式是 JSON 且包含 `severity` 和 `message` 欄位，Cloud Logging 會自動解析為 structured log
- 不需要安裝 `google-cloud-logging` SDK，只需要 JSON 格式化的 stdout logger
- 保留期限用 Cloud Logging 預設（30 天），如需更長可設 Log Sink → BigQuery
