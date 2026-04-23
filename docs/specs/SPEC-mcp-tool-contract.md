---
type: SPEC
id: SPEC-mcp-tool-contract
status: Under Review
ontology_entity: mcp-interface
created: 2026-04-15
updated: 2026-04-23
supersedes: SPEC-mcp-tool-contract-fixes
depends_on: SPEC-ontology-architecture v2, SPEC-task-governance, SPEC-doc-governance, SPEC-identity-and-access, SPEC-governance-guide-contract
runtime_canonical:
  - src/zenos/interface/mcp/*.py
  - src/zenos/interface/governance_rules.py
---

# Feature Spec: MCP Tool Contract SSOT

## 1. 定位

本文件是 **ZenOS 所有 agent-facing MCP tools 的唯一權威來源（SSOT）**。

凡是下列內容，一律以本文件為準：

- tool 名稱與職責邊界
- 輸入參數 contract
- 回傳 envelope
- 狀態碼語意
- backward compatibility 規則
- skill / setup / workflow 可依賴的 machine-readable 欄位

若與其他文件衝突，優先順序如下：

1. 本文件
2. 各 tool 對應的專用規格（`SPEC-task-governance` / `SPEC-doc-governance` / `SPEC-identity-and-access` / `SPEC-governance-guide-contract`）
3. 其他 SPEC 中的示意片段
4. ADR / TD / reference
5. skills / workflow 文件

skills 可以編排流程，但 **不得重新定義 MCP tool 的 payload、回傳形狀或狀態模型**。

> **Runtime canonical**：本 SPEC 描述的 tool 簽名、error code、enum 合法值，**以 `src/zenos/interface/mcp/*.py` 與 `src/zenos/interface/governance_rules.py` 為 canonical**。SPEC 修訂必須同步 runtime；反之亦然。不一致 → 以 runtime 為準、SPEC 補齊。

---

## 2. 目標

1. 讓 agent 對 ZenOS MCP surface 只需要記住一套穩定 contract。
2. 消除「同樣是 MCP tool，回傳格式卻不同」造成的 parsing 失敗。
3. 消除 task 舊狀態模型（`backlog` / `blocked` / `archived`）殘留造成的呼叫失敗。
4. 讓 setup / lookup / mutation tools 都能被同一套 caller 處理邏輯消費。

## 3. 非目標

- 不在本文件重寫所有 domain 細節；task lifecycle 仍以 `SPEC-task-governance` 為主，document / source / bundle 細節以 `SPEC-doc-governance` 為主（2026-04-23 後 `SPEC-document-bundle` 已併入）。
- 不在本文件定義 Dashboard REST API。
- 不在本文件定義治理 observability 的完整分析模型；那由 `SPEC-governance-observability` 承接。

---

## 4. 適用範圍

本 SSOT 覆蓋目前公開的 ZenOS MCP tools（以 `src/zenos/interface/mcp/*.py` 為準）：

| Tool | 檔案 | async def 位置 |
|------|------|--------------|
| `search` | `mcp/search.py` | `:145` |
| `get` | `mcp/get.py` | `:139` |
| `read_source` | `mcp/source.py` | `:57` |
| `batch_update_sources` | `mcp/source.py` | `:449` |
| `write` | `mcp/write.py` | `:264` |
| `confirm` | `mcp/confirm.py` | `:24` |
| `task` | `mcp/task.py` | `:577` |
| `plan` | `mcp/plan.py` | `:198` |
| `analyze` | `mcp/analyze.py` | `:18` |
| `governance_guide` | `mcp/governance.py` | `:29` |
| `find_gaps` | `mcp/governance.py` | `:106` |
| `common_neighbors` | `mcp/governance.py` | `:146` |
| `suggest_policy` | `mcp/suggest_policy.py` | `:12` |
| `setup` | `mcp/setup.py` | `:15` |
| `journal_read` | `mcp/journal.py` | `:81` |
| `journal_write` | `mcp/journal.py` | `:14` |
| `list_workspaces` | `mcp/workspace.py` | `:6` |
| `upload_attachment` | `mcp/attachment.py` | `:16` |
| `recent_updates` | `mcp/recent_updates.py` | `:190` |

新增 tool 必須同步本表與 §8 的 tool-specific 規則。

---

## 5. 核心設計原則

### 5.1 Single Envelope

**所有 MCP tools 必須回傳同一個 envelope。**

不得因為 tool 屬於 read path 或 setup path，就改成 top-level raw payload。

### 5.2 Stable Intent

每個 tool 必須對應單一、穩定、可描述的 agent 意圖。

- `search` = 找候選
- `get` = 取單一完整項目
- `task` = 管理行動項
- `confirm` = 正式批准 / 驗收

skills 不得把這些 intent 再拆成另一套 caller-side contract。

### 5.3 Server-side Compatibility

只要是已知的歷史遺留 caller 錯誤，且可安全 normalize，server 應提供 backward compatibility，而不是把容錯成本丟回 skill。

本期至少包含：

- task legacy status alias normalize
- confirm `accept` alias

### 5.4 Machine-readable First

agent 要依賴的是 machine-readable 欄位，不是長篇 prose。

因此所有 tool response 中，真正可被 parser 依賴的資訊必須放在：

- `status`
- `data`
- `warnings`
- `suggestions`
- `similar_items`
- `context_bundle`
- `governance_hints`
- `workspace_context`

---

## 6. Canonical Response Envelope

### 6.1 統一格式

所有 MCP tools 都必須回傳：

```json
{
  "status": "ok | rejected | error",
  "data": {},
  "warnings": [],
  "suggestions": [],
  "similar_items": [],
  "context_bundle": {},
  "governance_hints": {},
  "workspace_context": {}
}
```

補充規則：

- `data` 必填；可為 object 或 array，但不得缺省。
- `warnings` / `suggestions` / `similar_items` / `context_bundle` / `governance_hints` 必填；沒有內容時回空集合。
- 有 authenticated partner context 時，必須回 `workspace_context`。
- `governance_guide` 這類不需 auth 的工具，可省略 `workspace_context`。

### 6.2 `status` 語意

#### `status="ok"`

代表工具成功執行，caller 可直接讀 `data`。

#### `status="rejected"`

代表 caller 請求可被理解，但 **輸入不合法、狀態不允許、或缺少必要前提**。

**Runtime reality（三種 shape 並存；以 `_common.py:207` 的 `_error_response` 為預期 canonical）**：

| Shape | 產生路徑 | `data` 結構 | 典型範例 |
|-------|---------|------------|---------|
| A. 結構化錯誤 | `_error_response(error_code, message, extra_data)` → `_common.py:219-233` | `data = {"error": "<CODE>", "message": "<text>", ...extra}`（**flat**）+ `rejection_reason = message` | `UNKNOWN_TOPIC`（`mcp/governance.py:58-63`）、`SOURCE_UNAVAILABLE`（`mcp/source.py:380`）、`MISSING_PRODUCT_ID` / `INVALID_PRODUCT_ID`（`mcp/write.py:290-312`、`task.py` TaskValidationError path）|
| B. 純 `rejection_reason` | `_unified_response(status="rejected", data={}, rejection_reason=str(e))` | `data = {}`；只有 `rejection_reason` 帶訊息（含或不含 code 字串）| `plan_service` 的 `ValueError` 被 `_plan_handler:194-195` 包裝；大多數 doc / bundle `ValueError` 路徑（`ontology_service.py:2485,2815,2817,...`）|
| C. 巢狀 error object | `_document_linkage_rejection`（`mcp/write.py:50-66`）| `data = {"error": {"code": "...", "missing_entity_ids": [...]}, "message": "..."}`（**nested**，目前僅 document linkage 用）| `LINKED_ENTITY_IDS_REQUIRED` / `LINKED_ENTITY_NOT_FOUND` |

**Caller 解析規則**：
- 先讀 `rejection_reason`（一律存在）
- 再試讀 `data.error`：若為 string → Shape A；若為 object（`{code, ...}`）→ Shape C；若缺失 → Shape B
- `data.error.code` **只有 Shape C** 才有；其他路徑不要依賴此 key

**SPEC 改動約束**：未來 server 端應把 Shape B 路徑升級為 Shape A（帶 error_code），Shape C 收斂成 Shape A。但本 SPEC 不強制 migration 時程；本 SPEC 只描述當前 runtime 合法形狀。

#### `status="error"`

代表系統或外部依賴錯誤，caller 不應盲目重試同樣 payload。

**`data` 結構**（`_error_response` 產生，flat）：
- `data.error: str`（error code）
- `data.message: str`

適用例：

- auth failure
- adapter failure（`ADAPTER_ERROR`，`mcp/source.py:443-446`）
- permission denied
- unexpected internal exception

---

## 7. Tool Family Contract

### 7.1 Lookup Tools

包含：`search` / `get` / `read_source` / `list_workspaces` / `governance_guide` / `find_gaps` / `common_neighbors` / `suggest_policy` / `recent_updates` / `journal_read`。

規則：

1. 成功時一律 `status="ok"`。
2. payload 一律包在 `data`，不得回 top-level raw object。
3. 不得再使用 `{error, message}` top-level 格式。

### 7.2 Mutation Tools

包含：`write` / `confirm` / `task` / `plan` / `batch_update_sources` / `upload_attachment` / `journal_write`。

規則：

1. 全部走統一 envelope。
2. 所有 validation failure 必須走 `status="rejected"`。
3. mutation 成功後回傳的 canonical object 必須放在 `data`。

### 7.3 Analysis / Setup Tools

包含：`analyze` / `setup`。

規則：

1. 即使是 install/setup payload，也必須走統一 envelope。
2. `setup` 的 machine-readable install metadata 一律放在 `data`。

---

## 8. Tool-specific Canonical Rules

### 8.1 `search`

`search` 的 `data` 必須維持 collection-keyed 結構：

```json
{
  "status": "ok",
  "data": {
    "entities": [...],
    "tasks": [...],
    "count": 3,
    "total": 10
  }
}
```

規則：

- `collection="all"` 時，`data` 可同時包含 `results` / `entities` / `tasks` / `entries` 等鍵。
- `collection="entities"` 等單一 collection 時，仍然回 collection-keyed object，不回裸 array。

**`mode` 參數**（canonical: `mcp/search.py:166`）：
- `"keyword"`：純關鍵字 substring
- `"semantic"`：query embedding + cosine（pgvector）
- `"hybrid"`（**預設**）：0.7 semantic + 0.3 keyword

**`include` 參數**（僅對 `collection="entities"`）：`summary` / `tags` / `full`。未傳 → 等同 `full` + deprecation warning（ADR-040 Phase B 將改預設為 `summary`）。

**Filter 欄位**（canonical: `mcp/search.py:145-169`）：
`status` / `severity` / `entity_name` / `assignee` / `created_by` / `dispatcher` / `parent_task_id` / `linked_entity` / `confirmed_only` / `project` / `plan_id` / `product_id` / `product` / `entity_level` / `entity_id` / `id_prefix`。

**Legacy status normalize**（見 §9.2）：`status=backlog|blocked|archived` → 自動改寫為 canonical，附 warning。

### 8.2 `get`

`get` 的 `data` 必須是單一 canonical object，不得放在 top-level。

**`include` 參數**（僅對 `collection="entities"`；canonical: `mcp/get.py:145,164-177`）：
`summary` / `relationships` / `impact_chain` / `sources` / `entries` / `all`。可多值組合。不傳 → 等同 `all` + deprecation warning。

**`intent` / `top_k_per_hop`**（僅對 `include=["impact_chain" | "all"]` 有效；canonical: `mcp/get.py:146-147,179-183`）：
- `intent: str | None` — 自然語言描述，對 neighbor 按語意 embedding 排序
- `top_k_per_hop: int | None` — 每層 BFS 保留前 K 筆 neighbor

**`id_prefix`**：lookup 專用，至少 4 字元 hex。唯一命中 → 完整回傳；多筆 → `rejected` + `AMBIGUOUS_PREFIX` + candidates。write / confirm / handoff **不接受 `id_prefix`**（見 §8.6 / §8.12）。

### 8.3 `read_source`

`read_source` 成功時：

```json
{
  "status": "ok",
  "data": {
    "doc_id": "...",
    "source_id": "...",
    "content": "...",
    "content_type": "snapshot_summary | ..."
  }
}
```

**不可讀時的 error_code 矩陣**（canonical: `mcp/source.py`）：

| Source 類型 | Retrieval mode | 情境 | `status` | `data.error` | 行號 |
|------------|--------------|------|---------|-------------|------|
| `_HELPER_SOURCE_TYPES` = `{notion, gdrive, local, upload, wiki, url}` | 非 `per_user_live` | 無 `snapshot_summary` | `error` | `SNAPSHOT_UNAVAILABLE` | `source.py:243-258` |
| 同上 | `per_user_live` 且 `content_access != "full"` | 無 `snapshot_summary` | `error` | `SNAPSHOT_UNAVAILABLE` | `source.py:270-283` |
| 同上 | `per_user_live` | server 未實作 live reader | `error` | `LIVE_RETRIEVAL_REQUIRED` | `source.py:287-299` |
| 非 helper（含 github 等正式 adapter）| — | adapter 回 unavailable | `error` | `SOURCE_UNAVAILABLE` | `source.py:380` |
| 任意 | — | adapter 拋 `RuntimeError` | `error` | `ADAPTER_ERROR` | `source.py:443-446` |

**補充欄位**（平鋪於 `data`，Shape A）：
- `data.setup_hint: str`（建議 caller 的修復動作，如「用 Notion MCP 同步這份文件」）
- `data.alternative_sources: list`（同 bundle 內其他可用 source）
- `data.staleness_hint`（若有）
- `data.retrieval_mode`、`data.content_access`、`data.source_type` 等診斷欄位

### 8.4 `setup`

`setup` 一律回統一 envelope；實際 install payload 置於 `data`。

最低保證欄位：

- `data.action`
- `data.platform`（若已知）
- `data.bundle_version`
- `data.payload`
- `data.instructions`

若 `platform="codex"`：

- canonical project prompt 欄位是 `data.payload.agents_md_addition`
- 不得要求 caller 去讀 `claude_md_addition`

若 `platform="claude_code"`：

- canonical project prompt 欄位是 `data.payload.claude_md_addition`

### 8.5 `task`

**Actions**（canonical: `mcp/task.py:577-616`）：`create` / `update` / `handoff`。

**Ownership SSOT**（canonical: `governance_rules.py:938-944`）：
- `product_id` 為唯一 ownership 欄位；`project` 僅為 legacy fallback hint
- `project_id` 參數 → reject `INVALID_INPUT`（ADR-047 D3）
- 未解出 L1 → reject `MISSING_PRODUCT_ID`
- 非 L1 entity（level ≠ 1 或有 parent）→ reject `INVALID_PRODUCT_ID`
- `linked_entities` 含 L1 → server strip + warning `LINKED_ENTITIES_PRODUCT_STRIPPED`

**Subtask 驗證**（canonical: `task_service.py:204-224`）：
- `parent_task_id` 不存在 → reject `PARENT_NOT_FOUND`
- `subtask.plan_id ≠ parent.plan_id` → reject `CROSS_PLAN_SUBTASK`
- `subtask.product_id ≠ parent.product_id` → reject `CROSS_PRODUCT_SUBTASK`
- `task.product_id ≠ plan.product_id`（當 task 有 `plan_id`）→ reject `CROSS_PRODUCT_PLAN_TASK`

**Dispatcher namespace**（canonical: `governance_rules.py:DISPATCHER_PATTERN`）：
正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`；違反 → reject `INVALID_DISPATCHER`。

**`handoff_events` 是 server-managed**：caller 於 `create` / `update` 的 `data` 中傳入 → server strip + warning `HANDOFF_EVENTS_READONLY`（**不 reject**；canonical: `mcp/task.py:259-262`）。唯一合法 append 入口：`task(action="handoff", to_dispatcher, reason, output_ref?, notes?)`。

**Handoff 副作用**：
- `to_dispatcher="agent:qa"` 且當前 `status="in_progress"` → 自動升 `status="review"`
- handoff 只改 `dispatcher` + append `handoff_events`，**不改 `assignee`、不升 `todo→in_progress`**（claim 為 agent 自己做）

**Response 一致性**：
- `create` / `update` / `handoff` / `confirm(tasks)` 回傳的 `data.linked_entities` 一律為 expanded objects（`_enrich_task_result`）
- `done` 不可經由 `task(update)` 直接設置，只能經 `confirm(collection="tasks", accepted=True)`

### 8.6 `confirm`

**Actions**：驗證 `collection in {"entities", "documents", "protocols", "blindspots", "tasks"}`。

**Canonical 參數**：`accepted: bool`。server 必須接受 `accept` alias（canonical: `mcp/confirm.py:83-86`）：
- 若 caller 傳 `accept` 且未同時傳 `accepted` → 以 `accept` 視為 `accepted` + `warnings` 附 alias normalization 訊息
- 兩者同時傳 → 以 `accepted` 為準

**`id_prefix` 不接受**（canonical: `mcp/confirm.py:72-79`）→ reject `id_prefix_not_allowed_for_write_ops`；confirm 需完整 32-char id 避免 prefix 碰撞誤觸破壞性操作。

**Tasks collection 特化**：
- `accepted=False` 必附 `rejection_reason`；server 將 `task_status="review" → "in_progress"`，append HandoffEvent（`to_dispatcher = task.dispatcher or "human"`；**不自動改派回 developer**，canonical: `task_service.py:669-676`）
- `accepted=True` + `entity_entries=[...]`：每個 entry 型別 `{entity_id, type, content}`；`type` enum: `decision / insight / limitation / change / context`；`content` 1-200 字

**`mark_stale_entity_ids` / `new_blindspot` / `entity_entries`**：僅 tasks collection + `accepted=True` 時生效。

### 8.7 `governance_guide`

本 tool 為治理規則分發的 SSOT（ADR-038）。完整 contract 見 `SPEC-governance-guide-contract`。

- **輸入**：
  - `topic: str`（必填）— 合法值：`entity` / `document` / `bundle` / `task` / `capture` / `sync` / `remediation`
  - `level: int`（選填，預設 `2`）— 合法值：`1` / `2` / `3`
  - `since_hash: str | null`（選填）— client 端快取 hash，用於未變更時省略 content
- **輸出 `data`**：
  - `topic: str`、`level: int`
  - `content: str`（markdown；若 `since_hash` 命中則省略）
  - `content_version: str`（server rules 最後更新時間 ISO8601）
  - `content_hash: str`（內容 SHA256）
  - `unchanged: bool`（僅 hash 命中時為 true）
- **錯誤**：
  - 未知 topic → `status="rejected"` + `data.error="UNKNOWN_TOPIC"`（Shape A flat）+ `data.message` + `data.available_topics: list[str]`（平鋪於 `data` root）
  - 非法 level → `status="rejected"` + `data.error="INVALID_LEVEL"`（Shape A flat）
- **無需 auth**：可省略 `workspace_context`（見 6.1 規則）
- **Server 端不得依賴 LLM**：本 tool 的實作必須是純 dispatch，不得在關鍵路徑呼叫 LLM

### 8.8 `write(collection="documents")`

`linked_entity_ids` 為建立 document 時的必填欄位（ADR-038 + `SPEC-doc-governance §13.1`）：

- 缺少或空陣列 → `status="rejected"` + `data.error = {"code": "LINKED_ENTITY_IDS_REQUIRED"}`（**Shape C nested**；僅 document linkage 路徑走這個 shape，見 `write.py:50-66`）
- 任一 ID 不存在 → `status="rejected"` + `data.error = {"code": "LINKED_ENTITY_NOT_FOUND", "missing_entity_ids": [...]}`（Shape C；`missing_entity_ids` 在 `data.error` 內）
- 型別問題（非 list / 逗號字串）走 ValueError → Shape B（`rejection_reason` 攜帶訊息，不保證 `data.error`）

**Doc role**（canonical: `SPEC-doc-governance §3.1`，schema: 主 SPEC v2 §8.1）：
- 未傳 `doc_role` → 預設 `index`
- `doc_role=single` 若新增第 2 個 source → 目前 runtime 以 `ValueError` 字串 reject（Shape B `rejection_reason`；無 typed error code）。Governance target：升級為 Shape A typed code `SINGLE_CANNOT_HAVE_MULTIPLE_SOURCES`
- `doc_role=index` 需 `bundle_highlights` 非空（DDL CHECK，主 SPEC §8.1）

**`bundle_highlights_suggestion`**（吸收自舊 SPEC-document-bundle P0-12；現位於 `SPEC-doc-governance §3.4`）：

- `write(add_source)` / `write(update_source)` / `write(sources=[...])` 成功後，server 必須在 `suggestions` 回傳 deterministic highlight suggestion
- 計算規則為純 deterministic，不依賴 LLM
- Server 端必須在 LLM provider 全部故障時仍能完成 write 並回傳 suggestion

**`ontology_entity=TBD` × `status=Approved`**（`SPEC-doc-governance §6.4`）→ **runtime 尚未實作此檢查**（grep `ONTOLOGY_ENTITY_REQUIRED_ON_APPROVED` 於 src/ hit 0）；為 governance 目標，未來補上時走 `_error_response` Shape A。

### 8.9 `plan`

**Actions**（canonical: `mcp/plan.py:198-275`）：`create` / `update` / `get` / `list`。

**狀態機**（canonical: `mcp/plan.py:225-230` + `SPEC-task-governance §3.2`）：
- `draft → active`（任一下轄 task 進入 `in_progress` 時自動推進，或 caller 明確設）
- `draft → cancelled`
- `active → completed`：需所有下轄 task 在 terminal state（`done` / `cancelled`）+ `result` 非空。Runtime 違反行為：`plan_service.py:155-160` 拋 `ValueError`（含「Cannot complete plan: N task(s) not in terminal state. Pending task IDs (first 5): ...」），由 `_plan_handler:194-195` 包成 Shape B `rejection_reason=str(e)`；**無 typed error code**（未來可升級為 Shape A `PLAN_HAS_UNFINISHED_TASKS`）
- `active → cancelled`
- `completed` / `cancelled` **terminal immutable**

**Ownership 同 `task`**：`product_id` 為 SSOT；`project_id` → reject `INVALID_INPUT`。
- 建議 caller 用 `plan(action="create", product_id="<L1 UUID>", goal="...", entry_criteria="...", exit_criteria="...")`
- `action="get"` 額外回傳 `tasks_summary`（terminal / in_progress / todo 計數）

### 8.10 `batch_update_sources`

Canonical: `mcp/source.py:449-471`。

**輸入**：
- `updates: list[{document_id, new_uri}]` — 上限 100 筆；超過 reject
- `atomic: bool = false` — true 時 PostgreSQL transaction 包住整批

**冪等性**：若 `document_id` 的 URI 已等於 `new_uri` → 視為成功（列入 `updated`）。

**回傳 data**：`{updated: [...], not_found: [...], errors: [...]}`。

**Health signal 副作用**（canonical: `mcp/source.py:494-499`）：批次完成後會觸發 `compute_health_signal`，寫入 health cache 供 Dashboard 消費。

### 8.11 `recent_updates`

Canonical：`mcp/recent_updates.py:190`（signature）+ `mcp/recent_updates.py:498-514`（return shape）。

純 Lookup tool：回傳 workspace 近期變更的**異質清單**（`results` 是 heterogeneous array，不依 collection 分 key）。

**`data` shape**（與 `search` 不同；**不是** collection-keyed）：

```json
{
  "scope": {
    "product": "...",
    "product_id": "...",
    "resolved_product": "..."
  },
  "since": "2026-04-16T...",
  "topic": "...",
  "limit": 50,
  "count": 12,
  "fallback_used": false,
  "governance_gap": false,
  "results": [{...}, {...}]
}
```

**Root 欄位型別**（canonical: `recent_updates.py:498-513`）：
- `scope: object` / `since: ISO8601 str` / `topic: str | null` / `limit: int` / `count: int`
- `fallback_used: bool`（當主查詢無結果、改由 journal fallback 提供時為 true）
- `governance_gap: bool`（當所有結果都是 journal fallback 時為 true；提示 document 治理層未產生 change_summary 等信號）

**`results[].kind`**（canonical，目前僅兩值；**無** `task` 類型）：
- `document_change`（`recent_updates.py:296`）：L3-Document entity 的 `change_summary` 變化
- `entity_change`（`recent_updates.py:373`）：`change`-type entry 驅動的 L2 變化
- `entity_change` + `fallback_used=true` + `entry_type="journal"`（`recent_updates.py:468-484`）：journal fallback 路徑

caller 不應假設：
- 按 collection 分組（runtime 沒有）
- 出現 `task`-kind 紀錄（runtime 沒產生）
- `governance_gap` 是 object（runtime 是 bool）

> 與 `search` 的差異：`search` 是 collection-keyed `{entities, tasks, documents, ...}`；`recent_updates` 是 timeline-keyed `{scope, since, results}`。前者用於探索同類資料，後者用於「workspace 最近文件 / 知識變化」（task 變化請用 `search(collection="tasks", status=...)`）。

### 8.12 `write` / `confirm` / `task(handoff)` 共通約束

**`id_prefix` 不接受於破壞性操作**（canonical: `mcp/confirm.py:72-79`，write / task handoff 同理）：
- 這些操作需完整 32-char lowercase hex UUID
- 傳入 `id_prefix` → reject `id_prefix_not_allowed_for_write_ops`
- 設計理由：避免 prefix 碰撞誤觸寫入 / 驗收 / 派工

**`workspace_id`**：所有 tool 都接受；server 以 `_apply_workspace_override` 驗證 caller 對該 workspace 有權限，無權限 → reject。

---

## 9. Task Status SSOT

### 9.1 Canonical Status Set

自本文件起，task canonical status 只有：

- `todo`
- `in_progress`
- `review`
- `done`
- `cancelled`

### 9.2 Legacy Alias Compatibility

為了降低舊 skill / 舊 agent 失敗率，MCP tool surface 必須接受以下 legacy 輸入並自動 normalize：

| Legacy | Canonical |
|--------|-----------|
| `backlog` | `todo` |
| `blocked` | `todo` |
| `archived` | `done` |

適用範圍：

- `task(action="create", status=...)`
- `task(action="update", status=...)`
- `search(collection="tasks", status=...)`

規則：

1. normalize 後繼續執行，不直接 reject。
2. 回傳 `warnings`，明確指出 alias 已被改寫。
3. response payload 一律只回 canonical status，不回 legacy status。

---

## 10. Compatibility Boundary

### 10.1 可以做的 backward compatibility

- 參數 alias normalize
- legacy status normalize
- 舊回傳欄位的 additive 保留

### 10.2 不可以做的 backward compatibility

- 讓 top-level raw response 與 unified envelope 長期並存
- 讓 skill 自己決定哪個 tool 用哪種回傳格式
- 讓 setup payload key 對不同 caller 靠猜測

---

## 11. 與其他文件的關係

### 11.1 本文件吸收的歷史內容

- `SPEC-mcp-tool-contract-fixes`：dogfood 發現的 contract drift（`confirm` alias / `search` envelope / `linked_entities` 展開一致性 / legacy status normalize / CJK tokenizer）
- 舊 `SPEC-document-bundle` P0-12 `bundle_highlights_suggestion` 的 MCP-surface 部分（schema 已併入 `SPEC-doc-governance`）

### 11.2 其他文件改為引用，不再自定義 contract

下列文件若需要提到 MCP tools，只能引用本文件，不得再定義獨立 payload / envelope：

- `SPEC-agent-integration-contract`
- `SPEC-agent-setup`
- `SPEC-zenos-setup-redesign`
- `TD-agent-setup`
- `TD-action-layer-mcp-interface`

### 11.3 Domain-specific 細節仍由專用 spec 決定

- Schema canonical（entity / relationship / status enum / embedding sidecar）：`SPEC-ontology-architecture v2`
- task 欄位與治理細則：`SPEC-task-governance`
- document / source / bundle：`SPEC-doc-governance`（2026-04-23 已吸收 `SPEC-document-bundle` + `SPEC-doc-source-governance`）
- identity / visibility：`SPEC-identity-and-access`
- governance runtime 規則分發：`SPEC-governance-guide-contract`
- observability / audit：`SPEC-governance-observability`

---

## 12. 本期驗收門檻

本文件對應的本期實作至少必須滿足：

1. `search` / `get` / `read_source` / `setup` / `governance_guide` / `suggest_policy` / `upload_attachment` / `recent_updates` 全部走統一 envelope。
2. `task` / `search(tasks)` 接受 legacy status 並 normalize。
3. `confirm` 接受 `accept` alias。
4. 所有成功回傳都把主要 payload 放在 `data`。
5. 所有 rejected / error 回傳都不再使用 top-level `{error, message}` 作為唯一格式。

---

## 13. Acceptance Criteria

**Envelope & Status**（reality-aligned，不宣稱 runtime 未實作的 shape）：
- `AC-MCP-01` Given 任何 mutation / lookup tool 成功執行，When response 產生，Then `status="ok"` + `data` 非 null + `warnings / suggestions / similar_items / context_bundle / governance_hints` 必須存在（空集合 OK）；authenticated partner context 下必須回 `workspace_context`
- `AC-MCP-02` Given validation failure，When server 處理，Then `status="rejected"` + `rejection_reason`（一律存在）；**另**符合 §6.2 三種 shape 之一：
  - Shape A：`data.error: str`（code）+ `data.message: str`（走 `_error_response`）
  - Shape B：`data = {}`（走 `_unified_response` + ValueError catch，僅 `rejection_reason` 攜帶訊息）
  - Shape C：`data.error: object`（僅 document linkage 路徑）
- `AC-MCP-03` Given auth / adapter / unexpected exception，When server 處理，Then `status="error"` + `data.error: str` + `data.message: str`（走 `_error_response`，`_common.py:207`），caller 不應盲目重試同 payload

**`confirm` alias & id_prefix**：
- `AC-MCP-04` Given caller 傳 `confirm(accept=True)` 且未傳 `accepted`，When server 處理，Then 以 `accept` 值為 `accepted`，`warnings` 附 alias normalization 訊息（`mcp/confirm.py:83-86`）
- `AC-MCP-05` Given caller 對 `confirm` 傳 `id_prefix`，When server 處理，Then reject with `id_prefix_not_allowed_for_write_ops`（`mcp/confirm.py:72-79`）

**`task` ownership & handoff**：
- `AC-MCP-06` Given `task(action="create" | "update")` 的 `data` 含 `handoff_events`，When server 處理，Then strip 該欄位 + `warnings` 附 `HANDOFF_EVENTS_READONLY`，task 仍正常寫入（**不 reject**，`mcp/task.py:259-262`）
- `AC-MCP-07` Given caller 傳 `project_id` 於 `task` / `plan`，When server 處理，Then reject with `INVALID_INPUT`（ADR-047 D3；`mcp/plan.py:250-257` + `governance_rules.py:944`）
- `AC-MCP-08` Given `task` / `plan` 未傳 `product_id` 且 legacy `project` / `partner.defaultProject` 解不出 L1 entity，When server 處理，Then reject with `MISSING_PRODUCT_ID`
- `AC-MCP-09` Given `task(action="handoff")` 的 `to_dispatcher` 不符正則 `^(human(:[a-zA-Z0-9_-]+)?|agent:[a-z_]+)$`，When server 處理，Then reject with `INVALID_DISPATCHER`
- `AC-MCP-10` Given `task(action="handoff", to_dispatcher="agent:qa")` 且當前 `task_status="in_progress"`，When server 處理，Then 原子：append HandoffEvent + `dispatcher=to_dispatcher` + `task_status="review"`
- `AC-MCP-11` Given `confirm(collection="tasks", accepted=False, rejection_reason="...")`，When server 處理，Then `task_status: review→in_progress` + append HandoffEvent 且 `to_dispatcher = task.dispatcher or "human"`（**不自動改派 developer**，`task_service.py:669-676`）

**`plan` lifecycle**（**註**：plan 的 validation 走 `plan_service` 的 `ValueError` → `_plan_handler:194-195` 包成 **Shape B rejected**，`rejection_reason=str(e)` 攜帶完整訊息；**runtime 目前不 emit 結構化 error_code**）：
- `AC-MCP-12` Given `plan(action="update", status="completed")` 但下轄 task 仍有非 terminal，When server 處理（`plan_service.py:155-160`），Then `status="rejected"` + `rejection_reason` 含「Cannot complete plan: N task(s) not in terminal state. Pending task IDs (first 5): ...」字串。**不保證 `data.error` 欄位存在**（Shape B）
- `AC-MCP-13` Given `plan(action="update", status="completed")` 無 `result` 或 `result=""`，When server 處理，Then `status="rejected"` + `rejection_reason` 含 `result` 必填訊息（Shape B）
- `AC-MCP-14` Given plan status `completed | cancelled`，When caller 再 `update` 任何欄位，Then reject（terminal immutable；Shape B）

**`governance_guide`**（走 `_error_response` → **Shape A flat**；`mcp/governance.py:58-63,64-69`）：
- `AC-MCP-15` Given `governance_guide(topic=X)` 且 `X ∉ _VALID_TOPICS`，When server 處理，Then `status="rejected"` + `data.error="UNKNOWN_TOPIC"` + `data.message=...` + `data.available_topics: list[str]`（**flat 於 data root，不是巢狀 `data.error.available_topics`**）+ `rejection_reason=data.message`
- `AC-MCP-16` Given `level ∉ {1, 2, 3}`，When server 處理，Then `status="rejected"` + `data.error="INVALID_LEVEL"`（Shape A）
- `AC-MCP-17` Given `since_hash` 與 server 當前 content hash 相同，When server 處理，Then `data.unchanged=true` + 省略 `content`

**`write(documents)`**：
- `AC-MCP-18` Given `write(collection="documents")` 缺 `linked_entity_ids` 或空陣列，When server 處理（`ontology_service.py:751` raise `DocumentLinkageValidationError` → `write.py:50-66` `_document_linkage_rejection`），Then `status="rejected"` + `data.error = {"code": "LINKED_ENTITY_IDS_REQUIRED"}` + `data.message`（**Shape C nested**）
- `AC-MCP-19` Given `linked_entity_ids` 含不存在 ID，When server 處理（`ontology_service.py:763`），Then `status="rejected"` + `data.error = {"code": "LINKED_ENTITY_NOT_FOUND", "missing_entity_ids": [...]}`（Shape C nested，`missing_entity_ids` 在 `data.error` 內）

> **Gap note**：以下 doc-governance AC 在本 SPEC v2 被我早先誤標為 runtime-emit 結構化 error code，實際 runtime 只拋 `ValueError` 走 Shape B。先保留 governance intent，但 AC 降級為「rejected with reason 字串」，等對應 runtime 升級為 typed error 再恢復 code 比對：
>
> - `AC-MCP-20`（原 `SINGLE_CANNOT_HAVE_MULTIPLE_SOURCES`）：Given `doc_role=single` entity 試新增第 2 個 source，Then runtime 應 reject（Shape B，`rejection_reason` 含說明）
> - `AC-MCP-21`（原 `ONTOLOGY_ENTITY_REQUIRED_ON_APPROVED`）：Given `status=Approved` + `ontology_entity=TBD`，Then runtime 應 reject；目前 runtime **尚未實作此檢查**，是 governance 目標而非現行強制
> - `AC-MCP-22` Given `write(add_source | update_source | sources=[...])` 成功，Then `suggestions` 包含 deterministic `bundle_highlights_suggestion`（LLM provider 全故障時仍必須成功）

**`search` / `get`**：
- `AC-MCP-23` Given `search(status="backlog" | "blocked" | "archived")`，When server 處理，Then normalize 為 canonical（`todo / todo / done`）+ `warnings` 附 alias normalization
- `AC-MCP-24` Given `search(collection="all" | "entities" | ...)` 成功，When response 產生，Then `data` 為 collection-keyed object（不得回裸 array）
- `AC-MCP-25` Given `get(include=["impact_chain"], top_k_per_hop=3, intent="...")`，When server 處理，Then 每層 BFS 只保留前 3 名 neighbor，依 intent embedding 排序
- `AC-MCP-26` Given 破壞性操作（write / confirm / task handoff）傳 `id_prefix`，When server 處理，Then reject `id_prefix_not_allowed_for_write_ops`

**`batch_update_sources`**：
- `AC-MCP-27` Given `batch_update_sources(updates=[...101 筆...])`，When server 處理，Then reject（超過 100 筆）
- `AC-MCP-28` Given `batch_update_sources(atomic=true)` 且中有一筆失敗，When server 處理，Then 整批回滾，無任何 document 被修改
- `AC-MCP-29` Given 某筆的 URI 已等於 `new_uri`，When server 處理，Then 視為冪等成功，列入 `updated`

**`read_source`**（helper vs adapter 路徑 error code 矩陣見 §8.3）：
- `AC-MCP-30a` Given `_HELPER_SOURCE_TYPES` source（notion / gdrive / local / upload / wiki / url）且無 `snapshot_summary`，When `read_source` 執行，Then `status="error"` + `data.error="SNAPSHOT_UNAVAILABLE"`（Shape A，`mcp/source.py:243-258`）+ `data.setup_hint` + `data.alternative_sources`
- `AC-MCP-30b` Given helper source 且 `retrieval_mode="per_user_live"`、但 server 未裝 `read_source_live`，When `read_source` 執行，Then `status="error"` + `data.error="LIVE_RETRIEVAL_REQUIRED"`（Shape A，`mcp/source.py:287-299`）
- `AC-MCP-30c` Given 非 helper adapter（含 github）回 unavailable，When `read_source` 執行，Then `status="error"` + `data.error="SOURCE_UNAVAILABLE"`（Shape A，`mcp/source.py:380`）
- `AC-MCP-30d` Given adapter 拋 `RuntimeError`，When `read_source` 執行，Then `status="error"` + `data.error="ADAPTER_ERROR"`（Shape A，`mcp/source.py:443-446`）

**`recent_updates`**（`mcp/recent_updates.py:498-514`）：
- `AC-MCP-33` Given `recent_updates(...)` 成功，Then `data` 必含 `scope / since / topic / limit / count / fallback_used / governance_gap / results`；`fallback_used` 與 `governance_gap` 皆為 `bool`（非 object）；`results` 是 heterogeneous array（不依 collection 分 key）
- `AC-MCP-34` Given caller 依 `search` 習慣嘗試讀 `data.entities / data.tasks / data.documents`，Then 這些 key **不存在**；caller 必須改讀 `data.results[]`
- `AC-MCP-35` Given caller 讀 `data.results[].kind`，Then 合法值僅 `document_change`（`recent_updates.py:296`）與 `entity_change`（`recent_updates.py:373,468`）；**無** `task` 類型；task 變動請改用 `search(collection="tasks")`

**`find_gaps`**：

> **Gap note**：原 `AC-MCP-31` 宣稱 unknown `gap_type` 會 reject，但 runtime 無 validation：`ontology_service.py:2246` 以 `if gap_type in (...)` 條件式選分支，未匹配就 fall-through，caller 最終收到 `status="ok"` + 空結果。未來若要強制檢查，應在 `governance.py:106` 加 allowlist。目前合法值以 docstring（`governance.py:129`）為準：`all / orphan_entities / weak_semantics / underconnected`。

**`analyze`**：
- `AC-MCP-32` Given `analyze(check_type=X)` 且 `X` 不落在任何合法分支（即執行完 `results` dict 仍為空），When server 處理（`analyze.py:687-697`），Then `status="rejected"` + `data.error="INVALID_INPUT"` + `data.message` 含「Unknown check_type 'X'. Use: all, health, quality, staleness, blindspot, impacts, document_consistency, permission_risk, invalid_documents, orphaned_relationships, llm_health」（**Shape A flat**；非巢狀）
- `AC-MCP-32b` Given `analyze(check_type="consolidate")` 未帶 `entity_id`，When server 處理（`analyze.py:238-243`），Then `status="rejected"` + `data.error="INVALID_INPUT"` + `data.message` 要求先用 `quality` 列 saturated entity
