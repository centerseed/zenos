---
type: ADR
id: ADR-034
status: Draft
ontology_entity: 行銷定位與競爭策略
created: 2026-04-13
updated: 2026-04-14
supersedes: null
---

# ADR-034: Web 直連 Claude Cowork 的 Local Helper Bridge

## Context

`SPEC-marketing-automation` 已定義雙介面流程（Web + cowork + runner），但現況仍有落差：

1. Web 能引導指令，卻不能直接在頁面內與 cowork 討論。
2. 若走雲端 LLM API，會要求 API key 與額外成本，不符合「使用者已有 Claude 訂閱」前提。
3. scheduler/runner 需要可批次消費任務，但不能直接依賴 claude.ai 網頁互動。

需要一條可落地、可審計、可逐步擴充的 runtime 路徑。

## Decision

1. **採用 Local Helper Bridge（v1）**
   - Web 發送請求到本機 `http://127.0.0.1:<port>` helper。
   - helper 以 child process 啟動本機 `claude -p`，並把串流輸出轉成 SSE 回傳 Web。
   - conversation 以 `conversationId -> sessionName` 映射，續聊走 `--resume`。

2. **不用前端 API key，不直連雲端 LLM API**
   - 使用者只需本機已登入 Claude Code 訂閱。
   - helper 啟動 CLI 時清除 `ANTHROPIC_API_KEY`，避免誤走 API 計費路徑。

3. **scheduler 不直接讀 DB，改走 Dispatcher**
   - scheduler 只負責產生任務事件（topic/plan/generate/adapt/publish）。
   - Dispatcher 將事件投遞到對應執行端（local helper 或 runner worker），並回寫執行結果。

4. **安全邊界強制啟用**
   - helper 只監聽 `127.0.0.1`。
   - 允許來源採 allowlist（公司網域）。
   - 所有請求需帶本機配對 token。
   - `cwd` 只能來自 helper 白名單，不接受前端任意路徑。

## Alternatives

| 方案 | 優點 | 缺點 | 為何不選 |
|------|------|------|---------|
| Web 直接呼叫 Anthropic API | 實作快 | 需要 API key，成本與治理切換 | 不符合訂閱優先目標 |
| Web 操控 claude.ai 頁面 session | 看似零後端 | 極不穩定、合規風險高、不可測 | 不可做正式產品路徑 |
| 全部改雲端 runner 執行 | 運維集中 | 失去本機 cowork/MCP 上下文與彈性 | 不符合現有使用情境 |

## Consequences

- 正面：
  - 使用者不需要管理 API key。
  - 可在 Web 內完成策略討論與多輪對話，降低流程摩擦。
  - 架構上保留 scheduler/dispatcher/worker 擴充空間。
- 負面：
  - 需安裝本機 helper，首次上手多一步。
  - 需處理 local service 可用性、版本升級與相容性。
  - 跨平台（macOS/Windows）安裝與 PATH 差異需補教學與檢查。

## Implementation

1. 新增 `tools/claude-cowork-helper/`：
   - `POST /v1/chat/start`
   - `POST /v1/chat/continue`
   - `POST /v1/chat/cancel`
   - `GET /health`
2. Dashboard `/marketing` 新增「AI 討論（Beta）」抽屜，透過 SSE 串流呈現回覆並可回填策略 JSON。
3. 新增 helper 配對與狀態檢查文案（未啟動/未登入/origin 被拒）。
4. v1 先支援單機單使用者；v1.1 再擴充 runner + cloud dispatcher 消費鏈。

---

## 補充決策（2026-04-14，對齊 SPEC-marketing-automation 改版）

### 5. Context 注入兩層模型

helper 啟動 `claude -p` 時，自動注入固定底層 context：

```bash
claude -p \
  --mcp-config /path/to/zenos-mcp-config.json \
  --cwd /path/to/project  # 含 CLAUDE.md + .claude/settings.json + marketing skill 定義
```

- Layer 1（helper 固定）：MCP config + cwd（專案目錄）
- Layer 2（前端動態）：每次請求的 prompt 中帶入 context pack（欄位值、項目摘要、階段）

**權限白名單唯一來源：`.claude/settings.json` 的 `allowedTools`。**
helper 不使用 CLI `--allowedTools` 參數。Claude CLI 啟動時會自動讀取 cwd 下的 `.claude/settings.json`，以此為唯一 SSOT。前端負責組裝 context pack，helper 只透傳 prompt，不做模板引擎。

### 6. Capability Probe（Session 初始化檢查）

helper 在 `POST /v1/chat/start` 初始化 session 後，執行一次輕量 probe：

```
嘗試呼叫 mcp__zenos__search(query="health-check", limit=1)
```

結果透過 SSE 新增 event type 回報前端：

```
event: capability_check
data: { "mcp_ok": true, "skills_loaded": ["marketing-intel", ...] }
```

- `mcp_ok: false` → 前端顯示「ZenOS 連線失敗：AI 仍可對話但無法讀寫資料」
- `skills_loaded` 缺項 → 前端顯示「部分 skill 未載入」警告
- probe 失敗不中斷 session，對話功能繼續可用（降級模式）

### 7. 權限確認完整流程

```
AI 呼叫 tool
  → 在 allowedTools 白名單內？
    → Yes: 自動放行
    → No: 權限請求出現在 helper terminal console
      → helper 送 SSE event: permission_request
      → Web 顯示「等待本機確認中」
      → 60 秒 timeout？
        → Yes: helper 自動拒絕該 tool call，AI 繼續對話
        → No: console 確認/拒絕 → 結果回傳 AI
```

新增 SSE event types：

| event | data | 說明 |
|-------|------|------|
| `capability_check` | `{ mcp_ok, skills_loaded }` | session 初始化後回報 |
| `permission_request` | `{ tool_name, timeout_seconds }` | 等待本機確認 |
| `permission_result` | `{ tool_name, approved, reason }` | 確認結果（含 timeout 拒絕） |

- v1 不支援 Web 端代理權限確認（Web 只顯示提示，不提供確認按鈕）
- daemon 模式（無人看 console）等同 timeout → 自動拒絕
- helper 不使用 `--dangerously-skip-permissions`

### 8. 欄位級一鍵開聊的 Context Pack 結構

前端組裝的 context pack 統一結構：

```json
{
  "field_id": "strategy",
  "field_value": "{ ... 現有策略 JSON ... }",
  "project_summary": "Paceriz / 官網 Blog / 長期經營 / 策略：...",
  "current_phase": "strategy",
  "suggested_skill": "/marketing-plan",
  "related_context": "上輪情報摘要：..."
}
```

- 整體 ≤2000 字，超過按優先序截斷
- 敏感欄位（API key、token）不帶入
- helper 只透傳，不解析 context pack 結構
