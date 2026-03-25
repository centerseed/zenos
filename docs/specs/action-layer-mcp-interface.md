# Action Layer — MCP 介面技術規格

> 日期：2026-03-22
> 狀態：**Superseded by implementation** — 見 ADR-005
> 作者：Architect
> 交付對象：Developer
> 前置依賴：Phase 1 Ontology MVP、Action Layer PRD（spec.md Part 7.1）
>
> **重要更新**：原規格定義 4 個獨立的 Action Layer MCP tools。
> 經 MCP 品質研究後，決定將整個 MCP server 從 17+4=21 tools 合併為 7 tools。
> 見 `ADR-005-mcp-tool-consolidation.md` 和實際程式碼 `src/zenos/interface/tools.py`。
> 本文件的 Architect 決策（D1-D6）仍然有效，Firestore schema 和狀態轉換矩陣仍為 SSOT。

---

## Architect 決策記錄

### D1：assignee 填 UID，不填 role

**決策：** `assignee` 欄位填具體人的 UID（如 `"barry"`），不填職能角色（如 `"marketing"`）。

**理由：**
- Who 三層模型明確規定 ZenOS 管到「人」就結束。角色→人的解析在公司層完成，不是 MCP server 的責任。
- 填 role 會產生「派給 marketing 但沒人接」的曖昧狀態，SMB 場景通常一個角色就一個人，直接指名更清楚。
- Dashboard 的 Inbox/Outbox 需要按人過濾，UID 是直接可用的 filter key。
- 未來需要 role→person 解析時，加在 Dashboard 的「團隊設定」頁面，不影響 MCP 介面。

**例外：** `assignee` 可以為 `null`（未指派），由老闆在 Dashboard 或 MCP 手動指派。

### D2：blockedBy 級聯 — 自動解除 + 狀態回 todo

**決策：** task-A 狀態變為 `done` 或 `cancelled` 時，自動檢查所有 `blockedBy` 包含 task-A 的任務。如果該任務的 `blockedBy` 全部解除（所有 blocking task 都是 done/cancelled），自動將狀態從 `blocked` 改為 `todo`。

**理由：**
- SMB 場景人少，手動解阻塞容易遺忘。
- 純通知不夠——通知被忽略後任務會永遠卡在 blocked。
- 自動回 `todo`（而非 `in_progress`）是安全的——給執行者一個重新開始的機會。
- 級聯更新在 `update_task` 的 server-side logic 中統一處理，不需要 client 參與。

### D3：優先度 AI 推薦 — create_task 時同步計算

**決策：** 在 `create_task` 時同步計算 `priorityReason`，並填入建議的 `priority`。人在呼叫時可以傳入 `priority` 覆蓋。

**理由：**
- 推薦邏輯是規則引擎（rule-based），不需要 LLM 呼叫，延遲可忽略（< 50ms）。
- 同步計算讓呼叫者立刻看到建議理由，可以當場決定是否覆蓋。
- 異步補上會導致建立後再查詢時 priority 還是空的，UX 差。

### D4：action-layer-spec.md vs spec.md Part 7.1 的差異對齊

**決策：** 以 spec.md Part 7.1 為 SSOT（因為它是最後更新的，且更完整）。主要對齊：

| 維度 | action-layer-spec.md | spec.md Part 7.1（採用） |
|------|---------------------|------------------------|
| Collection 名稱 | `actions` | `tasks` |
| 狀態 | 6 個（draft~cancelled） | 7 個（backlog~archived + blocked） |
| 指派 | `assignee_role`（角色） | `assignee`（人 UID） |
| Ontology 連結 | `ontology_refs` map | `linkedEntities` / `linkedProtocol` / `linkedBlindspot`（平鋪） |
| 確認機制 | `confirmedByUser` | `confirmedByCreator`（派任者驗收） |
| Context 自動組裝 | `context_summary` | 保留，但作為 optional 欄位 |

**注意：** action-layer-spec.md 的 `complete_action` 反寫 ontology 邏輯（resolve blindspot、標記 entity stale）合併到 `update_task` 的 `done` 狀態處理中。

### D5：agent-routing.yaml — ZenOS 不定義 schema

**決策：** `~/.zenos/agent-routing.yaml` 純粹是用戶端的私有設定，ZenOS 不定義 schema、不讀取、不驗證。

**理由：**
- Who 三層模型的第三層（員工→agents）明確標記「ZenOS 不管」。
- 定義 schema 等於承擔維護責任，違反 Pull Model 的設計原則。
- 用戶端的 agent 技術棧多樣（Claude Code skill、GPT、自建 agent），統一 schema 會過早收斂。
- enterprise-governance.md 已經提供了範例 YAML 格式作為「指引」，足矣。

### D6：confirm 佇列合併 — 統一型別欄位

**決策：** 確認佇列用統一的查詢介面，透過 `type` 欄位區分知識確認和任務驗收。

詳見下方「交付物 3：確認佇列合併設計」。

---

## 交付物 1：MCP Tools 介面定義

### 總覽

| Tool | 類別 | 用途 |
|------|------|------|
| `create_task` | 治理端 | 建立任務（含 ontology 連結 + priority 推薦） |
| `update_task` | 治理端 | 更新狀態 / 指派 / 內容（含狀態流合法性驗證） |
| `confirm_task` | 治理端 | 派任者驗收（accepted / rejected） |
| `list_tasks` | 消費端 | 查詢任務（多維度過濾 + Inbox/Outbox 視角） |

---

### create_task

```
用途：建立一個知識驅動的任務
類別：治理端（PM / Barry / Agent）

輸入參數：
  title             string      必填    動詞開頭（如「設計 ontology output 路徑機制」）
  description       string      選填    做什麼、為什麼做、完成標準
  assignee          string?     選填    被指派者 UID（null = 未指派）
  priority          string?     選填    "critical" | "high" | "medium" | "low"
                                        不傳時由 AI 根據 ontology context 推薦
  status            string?     選填    初始狀態，預設 "backlog"
                                        合法值："backlog" | "todo"（只能以這兩個起始）
  linked_entities   string[]?   選填    關聯的 entity IDs
  linked_protocol   string?     選填    關聯的 Protocol ID
  linked_blindspot  string?     選填    觸發這個任務的 blindspot ID
  due_date          string?     選填    ISO-8601 日期字串（如 "2026-03-29"）
  blocked_by        string[]?   選填    阻塞此任務的其他 task IDs
  acceptance_criteria string[]? 選填    驗收條件列表
  created_by        string      必填    建立者 UID（如 "barry"、"pm-agent"）

輸出：
  {
    "task": {                           完整的 task 物件
      "id": "auto-generated",
      "title": "...",
      "description": "...",
      "status": "backlog",
      "priority": "high",
      "priorityReason": "連結到 severity=red 的 blindspot，建議高優先度",
      "assignee": "barry",
      "createdBy": "pm-agent",
      "linkedEntities": ["entity-001"],
      "linkedProtocol": null,
      "linkedBlindspot": "blindspot-003",
      "dueDate": null,
      "blockedBy": [],
      "acceptanceCriteria": ["..."],
      "confirmedByCreator": false,
      "rejectionReason": null,
      "result": null,
      "completedBy": null,
      "contextSummary": "相關實體：Paceriz（active）...",  // 自動組裝
      "createdAt": "2026-03-22T10:00:00Z",
      "updatedAt": "2026-03-22T10:00:00Z",
      "completedAt": null
    }
  }

Server-side 行為：
  1. 驗證 status 只能是 backlog 或 todo
  2. 驗證 linked_entities 中的 entity IDs 存在（不存在 → 警告但不阻止）
  3. 驗證 blocked_by 中的 task IDs 存在
  4. 如果 blocked_by 非空且 status 不是 backlog → 自動設為 blocked，且 blocked_reason 必填
  5. AI 優先度推薦（規則引擎）：
     a. 讀取 linked_entities 的 status 和 linked_blindspot 的 severity
     b. 套用推薦規則（見下方「優先度推薦規則」）
     c. 填入 priorityReason
     d. 如果呼叫者沒傳 priority → 用推薦值；有傳 → 用呼叫者的值
  6. 自動組裝 contextSummary：
     a. 從 linked_entities 拉取 name + summary（最多 3 個）
     b. 從 linked_protocol 拉取 entity_name
     c. 從 linked_blindspot 拉取 description
     d. 拼接成 2-3 句話的摘要
  7. 寫入 Firestore tasks collection
```

### update_task

```
用途：更新任務的狀態或內容
類別：治理端（任何有權限的人/agent）

輸入參數：
  id                string      必填    任務 ID
  status            string?     選填    目標狀態（需通過合法性驗證）
  assignee          string?     選填    重新指派
  priority          string?     選填    更新優先度
  description       string?     選填    補充或修改描述
  blocked_by        string[]?   選填    更新阻塞依賴
  blocked_reason    string?     選填    status=blocked 時必填
  due_date          string?     選填    更新期限
  result            string?     選填    status=review 時填寫完成產出
  acceptance_criteria string[]? 選填    更新驗收條件

輸出：
  {
    "task": { ... },                    更新後的完整 task 物件
    "cascadeUpdates": [                 級聯更新結果（如有）
      {
        "taskId": "task-002",
        "change": "blocked → todo",
        "reason": "blockedBy task-001 已完成"
      }
    ]
  }

Server-side 行為：
  1. 讀取現有 task
  2. 狀態轉換合法性驗證（見下方「狀態轉換矩陣」）
  3. 如果新 status = "blocked" → blocked_reason 必填
  4. 如果新 status = "review" → result 必填（SQL schema 強制）
  5. 如果新 status = "done" 或 "cancelled" → 執行級聯解阻塞：
     a. 查詢所有 blockedBy 包含此 task ID 的其他 tasks
     b. 對每個 blocked task：移除此 task ID from blockedBy
     c. 如果 blockedBy 變為空 → 自動將 status 從 blocked 改為 todo
     d. 回傳 cascadeUpdates 列表
  6. 如果新 status = "done" 且 linkedBlindspot 存在 → 將 blindspot 標記為 resolved
  7. 更新 updatedAt
  8. 如果新 status = "done" → 記錄 completedAt
```

### confirm_task

```
用途：派任者驗收已完成的任務
類別：治理端（僅限 createdBy 本人或 admin）

輸入參數：
  id                string      必填    任務 ID
  accepted          boolean     必填    true = 驗收通過，false = 打回
  rejection_reason  string?     選填    accepted=false 時必填

輸出：
  {
    "task": { ... },                    更新後的完整 task 物件
    "ontologyUpdates": [                ontology 反向更新結果（如有）
      {
        "collection": "blindspots",
        "id": "blindspot-003",
        "change": "status: open → resolved"
      }
    ]
  }

Server-side 行為：
  1. 讀取 task，驗證 status = "review"（其他狀態不可驗收）
  2. 驗證呼叫者 = createdBy 或 admin（Phase 1 不做嚴格權限，記錄呼叫者即可）
  3. 如果 accepted = true：
     a. task.status = "done"
     b. task.confirmedByCreator = true
     c. task.completedAt = now
     d. 執行級聯解阻塞（同 update_task 的邏輯）
     e. 如果 linkedBlindspot 存在 → blindspot.status = "resolved"
     f. 回傳 ontologyUpdates
  4. 如果 accepted = false：
     a. 驗證 rejection_reason 非空
     b. task.status = "in_progress"（退回重做）
     c. task.rejectionReason = rejection_reason
     d. task.confirmedByCreator = false
```

### list_tasks

```
用途：列出任務，支援多維度過濾 + Inbox/Outbox 視角
類別：消費端（任何人/agent）

輸入參數：
  assignee          string?     選填    按被指派者過濾（Inbox 視角）
  created_by        string?     選填    按建立者過濾（Outbox 視角）
  status            string?     選填    按狀態過濾（支援逗號分隔多值，如 "todo,in_progress"）
  priority          string?     選填    按優先度過濾
  linked_entity     string?     選填    按關聯的 entity ID 過濾
  include_context   boolean?    選填    是否展開 contextSummary，預設 false
  include_archived  boolean?    選填    是否包含 archived 任務，預設 false
  limit             int?        選填    回傳筆數上限，預設 50，最大 200
  order_by          string?     選填    排序欄位，預設 "updatedAt"
                                        合法值："updatedAt" | "createdAt" | "priority" | "dueDate"

輸出：
  {
    "tasks": [
      {
        "id": "task-001",
        "title": "...",
        "status": "in_progress",
        "priority": "high",
        "assignee": "barry",
        "createdBy": "pm-agent",
        "linkedEntities": ["entity-001"],
        "dueDate": "2026-03-29",
        "confirmedByCreator": false,
        "contextSummary": "...",        // 只在 include_context=true 時包含
        "createdAt": "...",
        "updatedAt": "..."
      }
    ],
    "count": 1,
    "hasMore": false
  }

Server-side 行為：
  1. 建構 Firestore query，依序套用 filters
  2. 如果 include_archived = false → 自動排除 status = "archived"
  3. 如果 status 包含逗號 → 拆分為多值 OR 查詢
  4. 如果 priority 排序 → 自定義排序（critical > high > medium > low）
  5. 如果 include_context = false → 回傳時移除 contextSummary 欄位（省流量）

特殊查詢模式：
  - Inbox 查詢：list_tasks(assignee="barry", status="todo,in_progress,blocked")
  - Outbox 查詢：list_tasks(created_by="barry", status="review")
  - 全局看板：list_tasks(include_context=true)
  - 關聯實體的待辦：list_tasks(linked_entity="entity-001", status="todo,in_progress")
```

---

### 狀態轉換矩陣

只有以下轉換是合法的，其他會被 server 拒絕：

| 目前狀態 ↓ \ 目標狀態 → | backlog | todo | in_progress | review | done | archived | blocked | cancelled |
|--------------------------|---------|------|-------------|--------|------|----------|---------|-----------|
| **backlog** | - | ✅ | ✅ | ✗ | ✗ | ✗ | ✅ | ✅ |
| **todo** | ✅ | - | ✅ | ✗ | ✗ | ✗ | ✅ | ✅ |
| **in_progress** | ✗ | ✅¹ | - | ✅ | ✗ | ✗ | ✅ | ✅ |
| **review** | ✗ | ✗ | ✅² | - | ✅³ | ✗ | ✗ | ✅ |
| **done** | ✗ | ✗ | ✗ | ✗ | - | ✅ | ✗ | ✗ |
| **archived** | ✗ | ✅⁴ | ✗ | ✗ | ✗ | - | ✗ | ✗ |
| **blocked** | ✗ | ✅⁵ | ✗ | ✗ | ✗ | ✗ | - | ✅ |
| **cancelled** | ✗ | ✗ | ✗ | ✗ | ✗ | ✅ | ✗ | - |

註：
1. in_progress → todo：允許暫停手上的工作
2. review → in_progress：被打回重做（透過 `confirm_task(accepted=false)`）
3. review → done：驗收通過（只能透過 `confirm_task(accepted=true)`，不能用 `update_task`）
4. archived → todo：重新啟用封存的任務
5. blocked → todo：阻塞解除（通常是系統級聯自動觸發）

**重要限制：**
- `update_task` 不能將 status 設為 `done`（必須走 `confirm_task`）
- `update_task` 可以設 `review`（執行者標記完成等驗收）
- `create_task` 只能用 `backlog` 或 `todo` 起始
- `status='review'` 時 `result` 必填
- `status='blocked'` 時 `blocked_reason` 必填
- 若 `blocked_by` 非空且 create 時不是 `backlog`，任務會進入 `blocked`，此時也必須提供 `blocked_reason`
- `linked_protocol`、`linked_blindspot`、`assignee_role_id`、`linked_entities` 受資料庫外鍵約束，必須引用同租戶已存在的資料

---

### 優先度推薦規則

規則引擎在 `create_task` 時同步執行，結果寫入 `priorityReason`：

```python
def recommend_priority(task_data, ontology_context):
    """規則引擎：根據 ontology context 推薦優先度。

    回傳 (priority: str, reason: str)
    """
    score = 0  # 基礎分 = medium
    reasons = []

    # Rule 1: 連結到 blindspot → +2
    if task_data.linked_blindspot:
        blindspot = get_blindspot(task_data.linked_blindspot)
        if blindspot and blindspot.severity == "red":
            score += 2
            reasons.append(f"連結到 severity=red 的盲點：{blindspot.description[:30]}")
        elif blindspot and blindspot.severity == "yellow":
            score += 1
            reasons.append(f"連結到 severity=yellow 的盲點")

    # Rule 2: 連結到 active entity → +1
    for eid in (task_data.linked_entities or []):
        entity = get_entity(eid)
        if entity and entity.status == "active":
            score += 1
            reasons.append(f"連結到 active 實體：{entity.name}")
            break  # 只算一次

    # Rule 3: 連結到 paused entity → -1
    for eid in (task_data.linked_entities or []):
        entity = get_entity(eid)
        if entity and entity.status == "paused":
            score -= 1
            reasons.append(f"連結到 paused 實體：{entity.name}，建議降低優先度")
            break

    # Rule 4: due_date < 3 天 → +3（直接 critical）
    if task_data.due_date:
        days_left = (task_data.due_date - now()).days
        if days_left < 3:
            score += 3
            reasons.append(f"距離到期日只剩 {days_left} 天")

    # Rule 5: blockedBy 非空 → -1
    if task_data.blocked_by:
        score -= 1
        reasons.append("被其他任務阻塞中，現在做不了")

    # Rule 6: 被其他任務 blockedBy（別人在等我）→ +1
    blocking_count = count_tasks_blocked_by(task_data.id)
    if blocking_count > 0:
        score += 1
        reasons.append(f"有 {blocking_count} 個任務在等這個完成")

    # Rule 7: 連結到多個 entity → +1（影響範圍大）
    if len(task_data.linked_entities or []) >= 3:
        score += 1
        reasons.append("跨多個實體，影響範圍大")

    # Score → Priority 映射
    if score >= 3:
        priority = "critical"
    elif score >= 2:
        priority = "high"
    elif score >= 0:
        priority = "medium"
    else:
        priority = "low"

    return priority, "；".join(reasons) if reasons else "無特殊訊號，預設 medium"
```

---

## 交付物 2：Firestore Schema + Security Rules

### Firestore Schema

```
tasks/{taskId}
  title               string      必填
  description         string      選填    ""
  status              string      必填    "backlog" | "todo" | "in_progress" | "review"
                                          | "done" | "archived" | "blocked" | "cancelled"
  priority            string      必填    "critical" | "high" | "medium" | "low"
  priorityReason      string      選填    AI 推薦理由
  assignee            string?     選填    被指派者 UID（null = 未指派）
  createdBy           string      必填    建立者 UID
  linkedEntities      string[]    選填    []  連結到 ontology 的 entity IDs
  linkedProtocol      string?     選填    連結到 Protocol ID
  linkedBlindspot     string?     選填    連結到 blindspot ID
  contextSummary      string      選填    從 ontology refs 自動組裝的 context 摘要
  dueDate             timestamp?  選填
  blockedBy           string[]    選填    []  阻塞此任務的其他 task IDs
  blockedReason       string?     選填    blocked 狀態的原因說明
  subtasks            string[]    選填    []  子任務 IDs（Phase 2）
  acceptanceCriteria  string[]    選填    []  驗收條件
  completedBy         string?     選填    執行者標記完成時的 UID
  confirmedByCreator  boolean     必填    false = 待驗收，true = 驗收通過
  rejectionReason     string?     選填    打回原因
  result              string?     選填    完成時的產出描述
  createdAt           timestamp   必填
  updatedAt           timestamp   必填
  completedAt         timestamp?  選填
```

### Firestore Security Rules

```javascript
// ── tasks collection ──
match /tasks/{taskId} {
  // 所有已認證用戶可讀取所有 tasks（Phase 1 不做 row-level 過濾）
  allow read: if request.auth != null;

  // 寫入只能透過 Admin SDK（MCP server）
  // Phase 1 的權限控制在 MCP server 的 application layer
  allow write: if false;
}
```

**設計說明：**

Phase 1 的 Firestore security rules 沿用 ontology 的模式：client 只讀，所有寫入透過 MCP server（Admin SDK）。權限邏輯在 MCP server 的 application layer 處理。

**Application-layer 權限控制（在 MCP server 端實作）：**

| 操作 | 誰可以 | 驗證邏輯 |
|------|--------|---------|
| create_task | 任何人 | 記錄 `createdBy` |
| update_task（改 status） | `assignee` 或 `createdBy` 或 admin | 比對呼叫者 UID |
| update_task（改 assignee） | `createdBy` 或 admin | 只有派任者能重新指派 |
| confirm_task | `createdBy` 或 admin | 只有派任者能驗收 |
| list_tasks | 任何人 | 無限制 |

**Phase 1 簡化：** 由於 MCP server 目前用 API key 認證（不是 user-level auth），Phase 1 先記錄 `createdBy` / `assignee` 但不做嚴格的 UID 驗證。等 Dashboard 加入 Firebase Auth 後再啟用 user-level 權限。

---

## 交付物 3：確認佇列合併設計

### 問題

Dashboard 的「確認佇列」頁面需要同時顯示兩種確認：
1. **知識確認**（`confirmedByUser`）— AI 產出的 ontology entry 等人確認
2. **任務驗收**（`confirmedByCreator`）— 執行者完成的任務等派任者確認

兩者的共同點：都是「某個東西等人做決定」。差異在於決定的性質和後續動作。

### 解法：統一查詢介面 + 前端 type 分組

#### Unified Confirmation Item 資料結構

```typescript
interface ConfirmationItem {
  // 統一欄位
  id: string;                     // 原始物件的 ID
  type: "knowledge" | "task";     // 區分兩種確認
  collection: string;             // 來源 collection（entities/documents/tasks...）
  title: string;                  // 顯示標題
  summary: string;                // 摘要描述
  createdAt: string;              // 建立時間

  // Knowledge 確認專有
  confirmedByUser?: boolean;      // ontology entry 的確認狀態

  // Task 驗收專有
  confirmedByCreator?: boolean;   // 任務的驗收狀態
  assignee?: string;              // 執行者（顯示「誰做完了」）
  result?: string;                // 完成產出（供派任者審閱）
}
```

#### MCP 查詢介面

現有的 `list_unconfirmed` tool 擴展為支援 tasks：

```
list_unconfirmed(collection?: string)

collection 參數新增合法值：
  - "entities" | "documents" | "protocols" | "blindspots"  ← 知識確認
  - "tasks"                                                 ← 任務驗收
  - null                                                    ← 全部（含 tasks）

tasks 的「未確認」定義：
  status = "review" AND confirmedByCreator = false
```

回傳格式不變——按 collection 分組：

```json
{
  "entities": [...],
  "documents": [...],
  "tasks": [
    {
      "id": "task-001",
      "title": "寫 Paceriz 社群貼文",
      "status": "review",
      "assignee": "xiaomei",
      "result": "已完成 4 篇草稿，見 Google Doc 連結",
      "confirmedByCreator": false,
      "createdAt": "..."
    }
  ]
}
```

#### Dashboard UI 設計

```
/confirm 頁面

┌──────────────────────────────────────────────────────┐
│  確認佇列                                    [12 待確認]│
│                                                       │
│  ── 知識確認（8 項）──                                 │
│  📝 Entity: Paceriz AI 教練模組      [確認] [修改]      │
│  📝 Document: ACWR 安全機制文件       [確認] [修改]      │
│  📝 Blindspot: 缺少競品分析          [確認] [忽略]      │
│  ...                                                   │
│                                                        │
│  ── 任務驗收（4 項）──                                  │
│  ✅ 寫 Paceriz 社群貼文 (小美完成)    [通過] [打回]      │
│  ✅ 更新 SEO 關鍵字    (agent-1完成)  [通過] [打回]      │
│  ...                                                   │
└──────────────────────────────────────────────────────┘
```

**操作對應：**
- 知識確認「確認」→ `confirm(collection, id)`（現有 tool）
- 任務驗收「通過」→ `confirm_task(id, accepted=true)`
- 任務驗收「打回」→ `confirm_task(id, accepted=false, rejection_reason="...")`

---

## 交付物 4：Domain Model 擴展

### 新增 Enums

```python
class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    ARCHIVED = "archived"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

### 新增 Dataclass

```python
@dataclass
class Task:
    """Action Layer task: knowledge-driven action item."""
    title: str
    status: str  # TaskStatus value
    priority: str  # TaskPriority value
    created_by: str
    id: str | None = None
    description: str = ""
    priority_reason: str = ""
    assignee: str | None = None
    linked_entities: list[str] = field(default_factory=list)
    linked_protocol: str | None = None
    linked_blindspot: str | None = None
    context_summary: str = ""
    due_date: datetime | None = None
    blocked_by: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    subtasks: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    completed_by: str | None = None
    confirmed_by_creator: bool = False
    rejection_reason: str | None = None
    result: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
```

---

## 實作任務拆分

### Task 1：Domain Layer（1hr）

- 在 `domain/models.py` 新增 `TaskStatus`、`TaskPriority`、`Task`
- 在 `domain/repositories.py` 新增 `TaskRepository` abstract class
- 新增 `domain/task_rules.py`：狀態轉換矩陣 + 優先度推薦規則

### Task 2：Infrastructure Layer（2hr）

- 在 `infrastructure/firestore_repo.py` 新增 `FirestoreTaskRepository`
- 實作 CRUD + 多維度查詢（compound queries）
- 實作級聯解阻塞查詢（query tasks where blockedBy contains X）

### Task 3：Application Layer（2hr）

- 新增 `application/task_service.py`
- 實作 `create_task`：含優先度推薦 + context 組裝
- 實作 `update_task`：含狀態驗證 + 級聯解阻塞
- 實作 `confirm_task`：含 ontology 反向更新
- 實作 `list_tasks`：含多維度過濾

### Task 4：Interface Layer（1hr）

- 在 `interface/tools.py` 新增 4 個 MCP tools
- 擴展 `list_unconfirmed` 支援 tasks collection
- 更新 Firestore security rules

### Task 5：整合測試（1hr）

- 完整流程測試：create → update → confirm → 級聯解阻塞
- 優先度推薦規則測試
- 狀態轉換矩陣的邊界測試
- list_tasks 多維度過濾測試

---

## 附錄：與現有 MCP Tools 的關係

新增 4 個 tools 後，ZenOS MCP server 總計 21 個 tools：

| 類別 | 數量 | Tools |
|------|------|-------|
| Consumer（唯讀） | 7 | get_protocol, list_entities, get_entity, list_blindspots, get_document, read_source, search_ontology |
| Governance（讀寫） | 7 + **4** = 11 | upsert_entity, add_relationship, upsert_document, upsert_protocol, add_blindspot, confirm, list_unconfirmed, **create_task**, **update_task**, **confirm_task**, **list_tasks** |
| Governance Engine | 3 | run_quality_check, run_staleness_check, run_blindspot_analysis |

`list_tasks` 同時是消費端和治理端——agent 用它查詢自己的任務（Inbox），PM 用它查看全局。歸類在 Governance 是因為它可以看到所有人的任務。

---

*Architect 交付。Developer 可直接依此規格實作。*
*如有任何介面不清楚的地方，先看 spec.md Part 7.1 的 PRD 作為參考。*
