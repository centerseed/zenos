---
doc_id: ADR-024-mcp-multi-workspace-context
title: 架構決策：MCP 多 Workspace Context — API Key 與 Workspace 解耦
type: ADR
ontology_entity: 身份與權限管理
status: Draft
version: "2.0"
date: 2026-04-09
supersedes: null
---

# ADR-024: MCP 多 Workspace Context — API Key 與 Workspace 解耦

## Context

SPEC-identity-and-access 與 ADR-018 v2 確立了 `active workspace context` 模型：一個 user 可加入多個 workspace，所有操作以 active workspace 為準。Dashboard API 已透過 `x-active-workspace-id` header 實現 workspace 切換（`dashboard_api.py`：`_requested_active_workspace_id` → `_resolve_active_workspace_id` → `_active_partner_view`）。

但 MCP 層（`tools.py` 的 `ApiKeyMiddleware`）尚未對齊這個模型：

1. **API key 綁死單一 workspace**：一筆 `partners` 記錄透過 `shared_partner_id` 指向一個 workspace。middleware 直接用 `sharedPartnerId or id` 設定 `current_partner_id` ContextVar，沒有 workspace 選擇機制。
2. **同一 user 多 workspace 需多把 key**：user 如果同時在 home workspace 和 shared workspace，MCP agent 必須持有兩把不同的 API key 並自行切換——這違反 ADR-018 v2 的「以 active workspace context 為準」原則。
3. **MCP tool 回傳不帶 workspace 資訊**：agent 無法從回傳結果辨別 entity 歸屬哪個 workspace，遇到同名 entity 時無法協助用戶判斷。

根源是 `partners` 表同時承擔了 identity（API key holder）和 workspace membership（`shared_partner_id` + `authorized_entity_ids`）兩個職責，且 MCP middleware 沒有像 dashboard 一樣提供 active workspace 選擇路徑。

### Transport 現實約束

ZenOS MCP server 支援三種 transport（`tools.py:3775`）：

| Transport | 部署場景 | HTTP header 可用 | Tool 參數可用 |
|-----------|---------|:---:|:---:|
| `stdio` | Claude Code / Codex 本地 | ✗ | ✓ |
| `sse` | 遠端 MCP client | ✓ | ✓ |
| `streamable-http` | Cloud Run 生產環境 | ✓ | ✓ |

**stdio 是當前 Claude Code / Codex 的預設 transport**（`MCP_TRANSPORT=stdio`），且 setup 流程（`skills/workflows/setup.md`、`skills/release/zenos-setup/SKILL.md`）只配置 `mcp.json` 的 URL query param，不配置自訂 header。如果 workspace 切換只建立在 HTTP header 上，stdio client 完全沒有可操作的切換入口。

因此，workspace 切換的正規入口必須是 **MCP tool 參數**——這是唯一跨所有 transport 都可用的通道。HTTP header 作為輔助路徑保留給 HTTP-based transport。

## Decision

### 1. Workspace 切換以 tool 參數 `workspace_id` 為正規入口

所有寫入類 MCP tool（`write`、`task`、`confirm`）增加 optional 參數 `workspace_id`：

```python
async def write(
    ...,
    workspace_id: str | None = None,  # 指定目標 workspace；省略 = active workspace
) -> dict:
```

Resolution 優先序：

1. Tool 參數 `workspace_id`（所有 transport 通用）
2. HTTP header `X-Active-Workspace-Id`（僅 HTTP transport，與 dashboard 一致）
3. **無指定時 default 到 home workspace**

第 3 點對齊 ADR-018 v2 第 60 行「每次登入後，系統一律先進入 home workspace」與 SPEC-identity-and-access 第 42 行「每次登入後，系統一律先進入自己的 home workspace」。Dashboard 的 `_resolve_active_workspace_id` 在無 header 時已經 return `home_id`，MCP 採用相同行為。

**向後相容影響**：現有 MCP client 的 key 若 `shared_partner_id` 非空，原本預設進 shared workspace；改為 default home 後會改變預設行為。這是刻意的——原行為違反 SPEC，屬於 bug 修正而非 breaking change。遷移期間在 tool 回傳的 `workspace_context` 中明確標示 active workspace，讓 agent 可立即發現並切換。

**驗證非法值**：若 `workspace_id` 不在合法 workspace 列表中，回傳 `{"error": "FORBIDDEN_WORKSPACE", "available_workspaces": [...]}`，讓 agent 可自動修正。

### 2. 讀取類 tool 回傳附帶 workspace context

所有 MCP tool 的回傳結果在頂層增加 `workspace_context` 欄位：

```json
{
  "workspace_context": {
    "workspace_id": "partner-abc",
    "workspace_name": "Barry 的工作區",
    "is_home_workspace": true,
    "available_workspaces": [
      {"id": "partner-abc", "name": "我的工作區"},
      {"id": "partner-xyz", "name": "Alice 的工作區"}
    ]
  },
  "entities": [ ... ]
}
```

規則：
- `workspace_id` + `workspace_name`：當前 active workspace 的 ID 與顯示名稱。agent 應在回覆用戶時帶上 workspace 名稱，讓用戶知道資料來自哪個空間。
- `is_home_workspace`：讓 agent 知道目前是否在自己的 workspace。
- `available_workspaces`：完整列表。當 agent 搜尋到可能存在於多個 workspace 的相似 entity 時，應列出 workspace 選項讓用戶確認目標。
- 每筆 entity 回傳不重複附加 workspace 資訊——workspace context 在頂層已足夠。

### 3. Agent 多 workspace 辨別與確認策略

Agent 辨別 entity 歸屬的流程：

1. **單一 workspace**：`available_workspaces` 只有一筆，agent 直接操作，無需額外確認。
2. **多 workspace，無歧義**：agent 在 home workspace 操作，回傳結果帶 `workspace_name` 讓用戶知情。
3. **多 workspace，有歧義**：agent 搜尋到類似 entity、或用戶指令不明確時：
   - 列出 `available_workspaces` 的名稱與 ID。
   - 詢問用戶「你要更新到哪個工作區的 [entity 名稱]？」
   - 用戶選定後，agent 在後續 tool call 帶上 `workspace_id` 參數。
4. **跨 workspace 操作**：agent 不能在同一個 request 中存取多個 workspace。需分兩次 tool call，各帶不同的 `workspace_id`。

### 4. 與現有 `partners` 表的相容策略

**不拆表。** 現階段不需要引入新的 `workspace_memberships` 表。

理由：
- 當前 `partners` 表的 `shared_partner_id` 已隱含「一個 user 最多參與兩個 workspace（home + shared）」的模型。
- Dashboard API 已用 `_active_partner_view` 證明：同一筆 `partners` 記錄可依 active workspace 投射出不同的 partner context。
- MCP middleware 複用同一套投射邏輯即可。

**未來考量**：當產品支援 3+ workspace 時，`shared_partner_id` 單值模型會不足。屆時需引入 `workspace_memberships` 表（多對多），但那是獨立的 ADR scope。

### 5. 抽取共用 workspace resolution 模組

Dashboard API 中 `_resolve_active_workspace_id`、`_active_partner_view`、`_build_available_workspaces` 目前寫死在 `dashboard_api.py`。抽到 `src/zenos/application/workspace_context.py`：

- `resolve_active_workspace_id(partner, requested_id) -> str`
- `active_partner_view(partner, active_workspace_id) -> (dict, str)`
- `build_available_workspaces(partner) -> list[dict]`
- `build_workspace_context(partner, active_workspace_id) -> dict` — 組裝 tool 回傳用的 `workspace_context` 欄位

Dashboard API 和 MCP middleware 都 import 這個模組，避免邏輯分叉。

### 6. Setup 流程與 skill 文件更新

MCP client 配置與 agent skill 文件必須同步更新，否則 ADR 只是 server-side 設計，沒有端到端可操作路徑：

1. **`skills/release/zenos-setup/SKILL.md`**：setup 產生的 system prompt 加入 workspace 使用指引，告知 agent 如何讀取 `workspace_context`、何時帶 `workspace_id` 參數。
2. **MCP tool description**：每個 tool 的 docstring 加入 `workspace_id` 參數說明與使用時機。
3. **stdio transport 不需額外配置**：workspace 切換完全透過 tool 參數完成，`mcp.json` 不需改動。

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **每個 workspace 發一把獨立 API key** | 零改動 | 違反 ADR-018 的 active workspace 模型；agent 管理多把 key 不合理 | 架構方向錯誤 |
| **只用 HTTP header 切換 workspace** | 與 dashboard 一致 | stdio transport 無法使用；當前 setup 流程不配置自訂 header；Claude Code / Codex client 無操作入口 | 無法覆蓋主要 client 路徑 |
| **立即拆 partners 表為 users + workspace_memberships** | 架構最乾淨 | 所有 query 都要改 JOIN；與「最多 2 個 workspace」的產品現實不匹配 | 過度設計 |
| **Default fallback 保持 `sharedPartnerId or id`（向後相容優先）** | 現有 client 行為不變 | 違反 ADR-018 / SPEC 的「預設進 home workspace」規則；MCP 與 dashboard 預設行為不一致 | 延續已知 bug |

## Consequences

### 正面

- MCP agent 只需一把 API key 即可操作用戶所有 workspace，符合 ADR-018 的 active workspace 模型。
- Tool 參數 `workspace_id` 跨所有 transport 通用（stdio / SSE / streamable-http），不依賴 HTTP header。
- Agent 從 `workspace_context` 可明確告知用戶「目前在哪個 workspace 操作」，遇到歧義可主動確認。
- Default 行為對齊 SPEC：無指定 → home workspace，MCP 與 dashboard 一致。
- Workspace resolution 統一到 `application/workspace_context.py`，不分叉。

### 負面

- **預設 workspace 行為變更**：原本 `sharedPartnerId or id` 的 fallback 改為 home workspace。已配置 `shared_partner_id` 的 partner 如果不帶 `workspace_id`，預設進入 home 而非 shared workspace。這是刻意的 bug 修正，但 agent skill 需要更新以配合。
- MCP tool 回傳格式增加 `workspace_context` 外層欄位：既有 hardcode 解析 tool output 的邏輯需要適配。
- 寫入類 tool 多了一個 optional 參數：tool description 需要清楚說明何時該帶、何時可省略。

### 後續處理

1. 抽取 `src/zenos/application/workspace_context.py` 共用模組。
2. 修改 `ApiKeyMiddleware`：先解析 tool 參數或 header 中的 workspace_id，再投射 partner view。
3. 寫入類 tool 增加 `workspace_id` optional 參數。
4. 所有 tool output 注入 `workspace_context`。
5. 更新 setup skill 與 MCP tool description，加入 workspace 使用指引。
6. 當產品需要支援 3+ workspace 時，另開 ADR 處理 `workspace_memberships` 表拆分。

## Implementation

| 步驟 | 檔案 | 說明 |
|------|------|------|
| 1 | `src/zenos/application/workspace_context.py` | 新建，從 `dashboard_api.py` 抽取 workspace resolution 邏輯 + 新增 `build_workspace_context` |
| 2 | `src/zenos/interface/dashboard_api.py` | 改為 import `workspace_context` 模組，移除本地實作 |
| 3 | `src/zenos/interface/tools.py` | `ApiKeyMiddleware` 增加 workspace resolution（tool param > header > home default） |
| 4 | `src/zenos/interface/tools.py` | 寫入類 tool（`write`、`task`、`confirm`）增加 `workspace_id` optional 參數 |
| 5 | `src/zenos/interface/tools.py` | 所有 tool output wrapper 注入 `workspace_context` |
| 6 | `skills/release/zenos-setup/SKILL.md` | 更新 system prompt 模板，加入 workspace 切換指引 |
| 7 | MCP tool docstrings | 更新 tool description，說明 `workspace_id` 參數用法 |
