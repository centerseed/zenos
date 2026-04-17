---
type: SPEC
id: SPEC-mcp-tool-contract
status: Under Review
ontology_entity: MCP 介面設計
created: 2026-04-15
updated: 2026-04-17
supersedes: SPEC-mcp-tool-contract-fixes
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
2. 各 tool 對應的專用規格（例如 `SPEC-task-governance`、`SPEC-document-bundle`）
3. 其他 SPEC 中的示意片段
4. ADR / TD / reference
5. skills / workflow 文件

skills 可以編排流程，但 **不得重新定義 MCP tool 的 payload、回傳形狀或狀態模型**。

---

## 2. 目標

1. 讓 agent 對 ZenOS MCP surface 只需要記住一套穩定 contract。
2. 消除「同樣是 MCP tool，回傳格式卻不同」造成的 parsing 失敗。
3. 消除 task 舊狀態模型（`backlog` / `blocked` / `archived`）殘留造成的呼叫失敗。
4. 讓 setup / lookup / mutation tools 都能被同一套 caller 處理邏輯消費。

## 3. 非目標

- 不在本文件重寫所有 domain 細節；task lifecycle 仍以 `SPEC-task-governance` 為主，document/source 細節仍以 `SPEC-document-bundle` 為主。
- 不在本文件定義 Dashboard REST API。
- 不在本文件定義治理 observability 的完整分析模型；那由 `SPEC-governance-observability` 承接。

---

## 4. 適用範圍

本 SSOT 覆蓋目前公開的 ZenOS MCP tools：

- `search`
- `get`
- `read_source`
- `write`
- `confirm`
- `task`
- `analyze`
- `governance_guide`
- `find_gaps`
- `common_neighbors`
- `suggest_policy`
- `setup`
- `journal_read`
- `journal_write`
- `plan`
- `list_workspaces`
- `batch_update_sources`
- `upload_attachment`

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

必須同時回：

- `rejection_reason`
- `data.error`
- `data.message`

適用例：

- invalid input
- transition illegal
- task title validation failed
- missing required field
- entity / task / source_id not found

#### `status="error"`

代表系統或外部依賴錯誤，caller 不應盲目重試同樣 payload。

必須同時回：

- `data.error`
- `data.message`

適用例：

- auth failure
- adapter failure
- permission denied
- unexpected internal exception

---

## 7. Tool Family Contract

### 7.1 Lookup Tools

包含：

- `search`
- `get`
- `read_source`
- `list_workspaces`
- `governance_guide`
- `find_gaps`
- `common_neighbors`
- `suggest_policy`

規則：

1. 成功時一律 `status="ok"`。
2. payload 一律包在 `data`，不得回 top-level raw object。
3. 不得再使用 `{error, message}` top-level 格式。

### 7.2 Mutation Tools

包含：

- `write`
- `confirm`
- `task`
- `plan`
- `batch_update_sources`
- `upload_attachment`
- `journal_write`

規則：

1. 全部走統一 envelope。
2. 所有 validation failure 必須走 `status="rejected"`。
3. mutation 成功後回傳的 canonical object 必須放在 `data`。

### 7.3 Analysis / Setup Tools

包含：

- `analyze`
- `setup`
- `journal_read`

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

### 8.2 `get`

`get` 的 `data` 必須是單一 canonical object，不得放在 top-level。

### 8.3 `read_source`

`read_source` 成功時：

```json
{
  "status": "ok",
  "data": {
    "doc_id": "...",
    "source_id": "...",
    "content": "..."
  }
}
```

若 source 不可讀：

- 用 `status="error"` 回覆
- `data.error` 使用 `SOURCE_UNAVAILABLE` / `ADAPTER_ERROR`
- 保留 `alternative_sources`、`setup_hint` 等 machine-readable 補充資訊於 `data`

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

`task(create/update)` 成功後：

- `data.linked_entities` 必須回 expanded objects，不得有些路徑回 ID array、有些回 object array
- `done` 不可經由 `task(update)` 直接設置

### 8.6 `confirm`

`confirm` 的 canonical 參數名稱是 `accepted`。

server 必須提供 backward compatibility：

- 若 caller 傳 `accept`
- 且未同時傳 `accepted`
- 則以 `accept` 視為 `accepted`
- 並在 `warnings` 回覆 alias normalization

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
  - 未知 topic → `status="rejected"`，`data.error.code="UNKNOWN_TOPIC"`，`data.error.available_topics` 列出合法值
  - 非法 level → `status="rejected"`，`data.error.code="INVALID_LEVEL"`
- **無需 auth**：可省略 `workspace_context`（見 6.1 規則）
- **Server 端不得依賴 LLM**：本 tool 的實作必須是純 dispatch，不得在關鍵路徑呼叫 LLM

### 8.8 `write(collection="documents")`

`linked_entity_ids` 為建立 document 時的必填欄位（ADR-038 / SPEC-doc-governance amendment 2026-04-17）：

- 缺少或空陣列 → `status="rejected"`，`data.error.code="LINKED_ENTITY_IDS_REQUIRED"`
- 任一 ID 不存在 → `status="rejected"`，`data.error.code="LINKED_ENTITY_NOT_FOUND"`，`data.error.missing_ids` 列出
- 型別必須為 `list[str]`；逗號字串不接受 → `status="rejected"`，`data.error.code="LINKED_ENTITY_FORMAT_INVALID"`

`bundle_highlights_suggestion`（SPEC-document-bundle P0-12）：

- `write(add_source)` / `write(update_source)` / `write(sources=[...])` 成功後，server 必須在 `suggestions` 回傳 deterministic highlight suggestion
- 計算規則為純 deterministic，不依賴 LLM
- Server 端必須在 LLM provider 全部故障時仍能完成 write 並回傳 suggestion

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

- `SPEC-mcp-tool-contract-fixes` 中已確認的 contract 問題與修正方向

### 11.2 其他文件改為引用，不再自定義 contract

下列文件若需要提到 MCP tools，只能引用本文件，不得再定義獨立 payload / envelope：

- `SPEC-agent-integration-contract`
- `SPEC-agent-setup`
- `SPEC-zenos-setup-redesign`
- `TD-agent-setup`
- `TD-action-layer-mcp-interface`

### 11.3 Domain-specific 細節仍由專用 spec 決定

- task 欄位與治理細則：`SPEC-task-governance`
- document/source bundle：`SPEC-document-bundle`
- observability / audit：`SPEC-governance-observability`

---

## 12. 本期驗收門檻

本文件對應的本期實作至少必須滿足：

1. `search` / `get` / `read_source` / `setup` / `governance_guide` / `suggest_policy` / `upload_attachment` 全部走統一 envelope。
2. `task` / `search(tasks)` 接受 legacy status 並 normalize。
3. `confirm` 接受 `accept` alias。
4. 所有成功回傳都把主要 payload 放在 `data`。
5. 所有 rejected / error 回傳都不再使用 top-level `{error, message}` 作為唯一格式。
