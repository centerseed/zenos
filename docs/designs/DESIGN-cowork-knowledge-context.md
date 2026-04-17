---
type: DESIGN
id: DESIGN-cowork-knowledge-context
doc_id: DESIGN-cowork-knowledge-context
title: 技術設計：Web Cowork 活用知識圖譜的欄位級漸進預填
spec: SPEC-cowork-knowledge-context
status: under_review
version: "0.1"
date: 2026-04-17
ontology_entity: TBD
---

# 技術設計：Web Cowork 活用知識圖譜的欄位級漸進預填

## 調查報告

### 已讀文件（附具體發現）

- `docs/specs/SPEC-cowork-knowledge-context.md` — 27 條 P0+P1 AC（AC-CKC-01~64）。核心：helper 主動遍歷（`AC-CKC-02`）、漸進預填（`AC-CKC-30~35`）、L1-only fallback（`AC-CKC-40~42`）、Paceriz 端到端 demo（`AC-CKC-60~64`）。
- `docs/decisions/ADR-034-web-cowork-local-helper-bridge.md` — helper 既定為「只透傳 prompt，不做模板引擎」；已有 SSE events: `capability_check / permission_request / permission_result`。context pack 既定欄位：`field_id / field_value / project_summary / current_phase / suggested_skill / related_context`。
- `dashboard/src/lib/cowork-helper.ts:16-42,230-363` — `streamCoworkChat` 只吃字串 prompt；SSE events 型別在 `CoworkStreamEvent`（需擴 `graph_context_loaded`）。
- `dashboard/public/installers/claude-code-helper/server.mjs:406-560` — `startStreamingRun` 已在 session 啟動時送 `capability_check`（line 448）；maxTurns 預設 6（line 629），需改為 10。helper 本身不打 MCP。
- `docs/specs/SPEC-marketing-automation.md` — 策略 7 欄位 / 文風 skill 三層組合 / 一鍵開聊 context pack 結構；AC-MKTG-STRATEGY-10~13 已引用本 spec。
- `docs/specs/SPEC-crm-intelligence.md` — briefing context pack 已列「產品現況」「累積洞察」；AC-CRM-BRIEF-20~22 已引用本 spec。

### 使用者確認的設計決策

- **決策 1**：graph_context 由**前端組**（走 Dashboard API `/api/cowork/graph-context`），不在 helper 端做。helper 維持 prompt-proxy 定位。
- **決策 2**：對話輪數統一 **10**（覆蓋既有 8 輪），取代新 spec 最初提的 12。SPEC `AC-CKC-35` 已更新。

### 不確定事項（標記並在實作階段實測）

- Token budget 1500 是否足夠 Paceriz 2 跳遍歷 → `[待實測]` S01 任務中需產出實測報告
- L3 summary 來源（entity.summary vs read_source 前 N 字）→ `[待決定]` S01 實作時優先用 entity.summary；不足 100 字則 fallback read_source 前 500 字
- 前端遍歷並行度 → `[待測試]` 目標 `AC-CKC-60` 10 秒內首輪；預計並行抓 L2 documents 需要 Promise.all

---

## AC Compliance Matrix

| AC ID | AC 摘要 | 實作位置（預定） | Test Function | 負責任務 | 狀態 |
|-------|--------|----------------|---------------|---------|------|
| AC-CKC-01 | Helper session MCP 能力對等 CLI | `dashboard/public/installers/claude-code-helper/server.mjs:211-260`（既有 bootstrap）+ 驗證 | `test_ac_ckc_01_helper_mcp_parity` | S01 / S03 | STUB |
| AC-CKC-02 | Orchestrator 在首輪前完成圖遍歷 | `dashboard/src/app/api/cowork/graph-context/route.ts` + `dashboard/src/components/CoworkChatSheet.tsx` | `test_ac_ckc_02_pre_first_turn_traversal` | S01 / S03 | STUB |
| AC-CKC-03 | 無 seed_entity 不遍歷 | `dashboard/src/lib/graph-context.ts` | `test_ac_ckc_03_no_seed_no_traversal` | S02 | STUB |
| AC-CKC-04 | mcp_ok=false 時降級 | `dashboard/src/lib/graph-context.ts` + `CoworkChatSheet.tsx` | `test_ac_ckc_04_mcp_unavailable_fallback` | S02 / S03 | STUB |
| AC-CKC-05 | 部分遍歷失敗仍 partial=true | `dashboard/src/app/api/cowork/graph-context/route.ts` | `test_ac_ckc_05_partial_failure_resilience` | S01 | STUB |
| AC-CKC-10 | L2 鄰居 3+ 個完整欄位 | Dashboard API traversal 邏輯 | `test_ac_ckc_10_l2_neighbors_complete` | S01 | STUB |
| AC-CKC-11 | L3 SPEC metadata + summary ≤500 字 | Dashboard API L3 loader | `test_ac_ckc_11_l3_summary_included` | S01 | STUB |
| AC-CKC-12 | Draft/archived 不納入 | Dashboard API filter | `test_ac_ckc_12_status_filter` | S01 | STUB |
| AC-CKC-13 | Token budget 裁切 | Dashboard API budget enforcer | `test_ac_ckc_13_token_budget_truncation` | S01 | STUB |
| AC-CKC-14 | graph_context_loaded SSE event | `cowork-helper.ts` event 型別擴充 + `CoworkChatSheet` dispatch | `test_ac_ckc_14_graph_context_loaded_event` | S02 / S03 | STUB |
| AC-CKC-15 | Session 內快取 60s | `CoworkChatSheet` state | `test_ac_ckc_15_session_cache` | S03 | STUB |
| AC-CKC-20 | 「已讀取」預設收合 | `dashboard/src/components/GraphContextBadge.tsx` | `test_ac_ckc_20_badge_default_collapsed` | S04 | STUB |
| AC-CKC-21 | 展開顯示階層 | `GraphContextBadge.tsx` | `test_ac_ckc_21_badge_hierarchy` | S04 | STUB |
| AC-CKC-22 | Truncated 提示 | `GraphContextBadge.tsx` | `test_ac_ckc_22_truncation_notice` | S04 | STUB |
| AC-CKC-23 | 未載入/降級文案 | `GraphContextBadge.tsx` | `test_ac_ckc_23_fallback_notice` | S04 | STUB |
| AC-CKC-30 | 首輪引用具體節點 | Prompt template `dashboard/src/lib/cowork-prompt.ts` | `test_ac_ckc_30_first_turn_cites_nodes` | S05 | STUB |
| AC-CKC-31 | 無依據時標明 | Prompt template | `test_ac_ckc_31_no_fabrication` | S05 | STUB |
| AC-CKC-32 | 一輪一題追問 | Prompt template + `CoworkChatSheet` state | `test_ac_ckc_32_one_question_per_turn` | S05 | STUB |
| AC-CKC-33 | Pending 標記 | Apply flow | `test_ac_ckc_33_pending_marker` | S05 | STUB |
| AC-CKC-34 | 結構化摘要 target_field + value | `dashboard/src/lib/cowork-apply.ts` | `test_ac_ckc_34_apply_contract` | S05 | STUB |
| AC-CKC-35 | 10 輪上限提示 | `CoworkChatSheet` turn counter + helper maxTurns 調 10 | `test_ac_ckc_35_turn_limit_10` | S03 / S05 | STUB |
| AC-CKC-40 | fallback_mode = l1_tags_only | Dashboard API | `test_ac_ckc_40_l1_only_fallback_mode` | S01 | STUB |
| AC-CKC-41 | Fallback 明確提示 | Prompt template | `test_ac_ckc_41_l1_fallback_notice` | S05 | STUB |
| AC-CKC-42 | Fallback 仍可走完 + confidence=low | Apply flow | `test_ac_ckc_42_low_confidence_marker` | S05 | STUB |
| AC-CKC-50 | CRM Briefing 走本 flow | `dashboard/src/app/clients/deals/[id]/DealDetailClient.tsx` | `test_ac_ckc_50_crm_briefing_uses_flow` | S07 | STUB |
| AC-CKC-51 | Briefing 引用具體節點 + Badge | CRM briefing chat component | `test_ac_ckc_51_briefing_cites_nodes` | S07 | STUB |
| AC-CKC-55 | Marketing strategy seed = product | Marketing strategy 欄位「討論這段」wiring | `test_ac_ckc_55_strategy_seed_and_targets` | S06 | STUB |
| AC-CKC-56 | 套用後 3+ 欄位可追溯引用 | Apply writer → ZenOS strategy document | `test_ac_ckc_56_strategy_applied_traceable` | S06 | STUB |
| AC-CKC-60~64 | Paceriz 端到端 demo | E2E test / manual script | `test_ac_ckc_60_paceriz_e2e_happy` ~ `test_ac_ckc_64_fallback_path` | S08 | STUB |

---

## Component 架構

```
Dashboard (Next.js)
├── src/app/api/cowork/graph-context/route.ts  ← 新：遍歷 API
├── src/lib/graph-context.ts                   ← 新：client 封裝
├── src/lib/cowork-prompt.ts                   ← 新：prompt template
├── src/lib/cowork-apply.ts                    ← 新：apply 契約驗證
├── src/lib/cowork-helper.ts                   ← 改：event 型別擴 graph_context_loaded
├── src/components/CoworkChatSheet.tsx         ← 改：pre-fetch + inject + 10 輪
├── src/components/GraphContextBadge.tsx       ← 新：可展開清單
├── src/app/marketing/projects/[id]/...       ← 改：strategy 欄位 wiring
└── src/app/clients/deals/[id]/...            ← 改：briefing 欄位 wiring

helper (dashboard/public/installers/claude-code-helper/)
└── server.mjs                                 ← 改：maxTurns 預設 10
```

**Flow（使用者按「討論這段」）**：

```
1. UI 呼叫 prepareGraphContext({seed_entity_id, seed_entity_type})
2. client 打 GET /api/cowork/graph-context?seed_id=...&hops=2
3. Dashboard API 內部：
   a. mcp__zenos__get(collection="entities", id=seed_id) → seed
   b. mcp__zenos__search(collection="entities", query="", parent_id=seed_id, status="active,approved")
      → L2 鄰居（上限 10 個，依 updated_at desc）
   c. Promise.all 針對每個 L2：search(collection="documents", entity_name=l2.name, status="approved,current")
      → L3 documents（每 L2 上限 3 個，總 20 個）
   d. 執行 token budget 裁切（預算 1500），填 truncated / fallback_mode
   e. 回傳 GraphContext JSON
4. UI 建立 context pack（含 graph_context 欄位）並組 prompt：
   <graph_context>...</graph_context>
   <project_summary>...</project_summary>
   <target_fields>[...]</target_fields>
   <instructions>漸進式預填規則</instructions>
   {使用者首輪訊息}
5. 呼叫 streamCoworkChat({mode:"start", prompt, maxTurns:10})
6. helper spawn claude CLI → 首輪 SSE 事件序列：
   capability_check → graph_context_loaded → message (AI 回覆) → done
7. UI 首輪回覆前已渲染 GraphContextBadge（收合）
8. 使用者追問 → streamCoworkChat({mode:"continue"}) 每輪遞增 turnCount
9. AI 輸出結構化摘要 → cowork-apply 驗證 target_field/value → 寫回 ZenOS
```

---

## 介面合約清單

### `GET /api/cowork/graph-context`

| 參數 | 型別 | 必填 | 說明 |
|------|------|:----:|------|
| `seed_id` | string | ✓ | ZenOS entity ID（L1 product / company / project） |
| `hops` | number | | 1 或 2，預設 2 |
| `budget_tokens` | number | | 預設 1500，實測後可調 |
| `include_docs` | boolean | | 預設 true；false 時只取 L2 鄰居不遞迴 L3 |

**Response (200)**：
```typescript
interface GraphContextResponse {
  seed: {
    id: string; name: string; type: string; level: 1|2|3;
    tags: { what: string[]; why: string; how: string; who: string[] };
    summary: string;
  };
  fallback_mode: "normal" | "l1_tags_only";
  neighbors: Array<{
    id: string; name: string; type: string; level: 2; distance: 1;
    tags: { what: string[]; why: string; how: string; who: string[] };
    summary: string;
    documents: Array<{
      doc_id: string; title: string; doc_type: string;
      status: string; summary: string;  // ≤500 chars
    }>;
  }>;
  truncated: boolean;
  truncation_details?: { dropped_l2: number; dropped_l3: number; summary_truncated: number };
  partial: boolean;
  errors?: string[];
  estimated_tokens: number;
  cached_at: string;  // ISO
}
```

**Error (400/500)**：`{ status: "error", message: string }`。前端看到 error 時視為 `graph_context_unavailable`，對應 `AC-CKC-04`。

### `CoworkStreamEvent` 型別擴充（`dashboard/src/lib/cowork-helper.ts`）

新增成員：
```typescript
| { type: "graph_context_loaded"; payload: { l2_count: number; l3_count: number; truncated: boolean; fallback_mode: string } }
```

（注：此事件由 UI 在 traversal 完成後自行 dispatch，不由 helper 送 SSE——helper 仍 prompt-proxy。event 型別統一收在 `CoworkStreamEvent` 便於消費端。）

### `streamCoworkChat` 參數擴充

| 參數 | 型別 | 必填 | 說明 |
|------|------|:----:|------|
| `maxTurns` | number | | 預設改為 10（既有 6） |

（prompt 仍是字串；圖譜資料由 UI 組進 prompt，helper 不知情。）

### Apply 契約（`dashboard/src/lib/cowork-apply.ts`）

```typescript
interface ApplyPayload {
  target_field: "strategy" | "topic" | "style" | "schedule" | "draft" | "platform_draft" | "briefing";
  value: object | string | Array<object>;  // 依 target_field schema 驗證
  confidence?: "high" | "medium" | "low";  // fallback 模式時帶 low
  source_citations?: Array<{ node_id: string; node_name: string }>;  // 可追溯性
}
```

---

## DB Schema 變更

**無**。本功能不動 DB。相關寫回（strategy document / briefing insights）走既有 SPEC-marketing-automation / SPEC-crm-intelligence 定義的 ZenOS document / `crm.ai_insights` 路徑，不新增 table/column。

---

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|---------------|
| **S01** | 實作 `/api/cowork/graph-context` 遍歷 API + token budget | Developer | `AC-CKC-05, 10, 11, 12, 13, 40` 對應 test 從 FAIL → PASS；實測 Paceriz seed 的回傳大小與 token 數寫入 PR description |
| **S02** | 前端 `graph-context.ts` client + session cache + `cowork-helper.ts` event 型別擴充 | Developer | `AC-CKC-03, 04, 14, 15` test PASS；型別 compile；CoworkStreamEvent 新增成員無 breaking |
| **S03** | `CoworkChatSheet` 改裝：pre-fetch + prompt inject + 10 輪上限 + helper maxTurns 調 10 | Developer | `AC-CKC-01, 02, 35` test PASS；helper server.mjs line 629 預設改 10 |
| **S04** | `GraphContextBadge` component（收合展開 / truncation / 降級文案） | Developer | `AC-CKC-20, 21, 22, 23` test PASS；Storybook 或 vitest snapshot |
| **S05** | Prompt template（`cowork-prompt.ts`）+ apply 契約驗證（`cowork-apply.ts`）+ 漸進規則（一輪一題、pending、fallback 提示、confidence）| Developer | `AC-CKC-30, 31, 32, 33, 34, 41, 42` test PASS |
| **S06** | Marketing 策略「討論這段」wiring + apply 寫回 ZenOS strategy | Developer | `AC-MKTG-STRATEGY-10~13, AC-CKC-55, 56` test PASS；手動端到端可完成 7 欄位 |
| **S07** | CRM Briefing「產品現況」走本 flow + Badge 顯示 | Developer | `AC-CRM-BRIEF-20~22, AC-CKC-50, 51` test PASS |
| **S08** | Paceriz demo 端到端驗收 + 錄影 | QA | `AC-CKC-60~64` 全數 PASS；demo 影片 3 分鐘以內涵蓋 AC-CKC-63 四項可視證據 |
| **S09** | 整體 QA：spec compliance 雙階段審查 + 部署後驗證 | QA | `pytest tests/spec_compliance/test_cowork_knowledge_context_ac.py -x` 全過；部署 Firebase Hosting 後 /health 200 且 Paceriz 項目「討論這段」可打通 |

依賴：S02 依賴 S01；S03 依賴 S01, S02；S04 可並行；S05 依賴 S03；S06, S07 依賴 S05；S08, S09 依賴 S06, S07。

---

## Risk Assessment

### 1. 不確定的技術點

- **Token budget 1500 實測**：Paceriz 2 跳實際 JSON 大小未測。S01 任務含實測任務，若溢出需退回裁切更狠或砍 L3。
- **L3 summary 來源**：entity.summary 可能過短（100 字）或過長（>500 字需裁）。fallback 策略寫進 S01。
- **並行遍歷延遲**：抓 L2（1 次）→ 並行抓每個 L2 的 documents（5-10 次 API call）。若 ZenOS API 延遲高，可能違 `AC-CKC-60` 10 秒。必要時在 S01 加 `mcp__zenos__search` 的 `limit` 收斂或拆步驟。

### 2. 替代方案與選擇理由

- **Helper 端做遍歷**（被否決）：需在 node helper 內嵌 MCP client，破壞現行授權邊界；helper v1 定位為 prompt-proxy。使用者決策：前端做。
- **AI 被動讀 MCP**（被否決）：不穩定，首輪常不觸發 tool call；違 `AC-CKC-02`「首輪前必須有 graph_context」。
- **影響鏈遍歷 API**（延後）：SPEC-knowledge-graph-semantic 的 P0.2。本 spec 用 `search(parent_id=)` 足夠，不阻塞。

### 3. 需要用戶確認的決策

（已於 Phase 1.5 確認：前端組 graph_context、對話輪數統一 10。）剩下無需用戶再確認。

### 4. 最壞情況與修正成本

- **Token budget 1500 大量溢出**：裁切後 L3 全砍 → AI 草案只到 L2 層級 → demo 效果打折但仍可走完。修正：改 budget 為百分比（15% context window）。
- **遍歷延遲超 10 秒**：首輪 UX 退化。修正：S01 拆兩階段——seed + L2 先返回（`graph_context_loaded` 部分資料），L3 async lazy load。這是 P2 優化，P0 不做。
- **Apply 契約 AI 輸出不符 schema**：SPEC-marketing-automation 已有負向處理（`AC-CKC` 未列 apply parse 失敗，但 SPEC-marketing-automation 的「格式異常，請重新整理」既有處理）。沿用現行 UX。

---

## Done Criteria（整體）

1. 所有 AC test stub 檔案（`tests/spec_compliance/test_cowork_knowledge_context_ac.py` + vitest 對應）從 `FAIL` 變 `PASS`
2. `pytest tests/spec_compliance/test_cowork_knowledge_context_ac.py -x` 全過
3. `cd dashboard && npx vitest run tests/spec_compliance/cowork_knowledge_context_ac.test.ts` 全過
4. Paceriz「官網 Blog」項目手動端到端：按「討論策略」→ 10 秒內首輪 + Badge 展開有 Rizo AI 教練 / 付費分級系統 / 三層本體論等 L2 → 走完 7 欄位漸進對話 → 套用後 ZenOS 刷新可見
5. 切換到只有 L1 的產品（例如「SME 製造業自動化橋樑」）驗證 fallback 提示文字
6. Firebase Hosting 部署後 `/api/cowork/graph-context?seed_id={paceriz-id}` 回應 200 + 非空 neighbors
7. Spec 與實作一致性雙階段審查（Architect Phase 3.A + 3.B）通過
8. PLAN 檔 Resume Point 更新為 done，journal 已寫
