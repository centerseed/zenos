---
doc_id: SPEC-mcp-tool-contract-fixes
title: 功能規格：MCP 工具行為契約修正集
type: SPEC
ontology_entity: MCP 介面設計
status: approved
version: "0.1"
date: 2026-04-05
supersedes: null
---

## 背景

2026-04-05 透過 `/dogfood` skill 對治理流程端到端評估，發現 MCP 工具的行為與 skill 文件描述之間存在 5 個可量化的不一致點。
本 SPEC 作為修正依據，定義正確行為，並作為後續 server 修正與 skill 文件更新的驗收基準。

## 問題範圍

### P0：直接導致 agent 操作失敗

#### Issue 1 — `confirm` tool 參數名稱錯誤

**現況**：`skills/governance/task-governance.md`（及 release SSOT 對應版本）在驗收範例中使用 `accept=True`。

**正確行為**：`mcp__zenos__confirm` 的參數名稱為 `accepted`，不是 `accept`。

```python
# 正確
mcp__zenos__confirm(collection="tasks", id="task-id", accepted=True, result="...")
# 錯誤（目前 skill 文件所示）
mcp__zenos__confirm(collection="tasks", id="task-id", accept=True, result="...")
```

**驗收條件**：
- SSOT 的 `task-governance.md` 所有 `confirm` 範例改為 `accepted=True` / `accepted=False`
- governance-loop.md 的 confirm 範例同步更新

---

#### Issue 2 — `search` 回傳不符合 Phase 1 統一 envelope ✅ Implemented

**現況**：`search(collection="entities")` 直接回傳 `{"entities": [...]}` 頂層結構。

**定義正確行為**：`search` 應與 `write/confirm/task` 一致，包裝為 Phase 1 統一格式：

```json
{
  "status": "ok",
  "data": [...],
  "warnings": [],
  "suggestions": [],
  "context_bundle": {}
}
```

`data` 為陣列，元素結構不變。

**Backward Compatibility（重要）**：
- 目前 Dashboard 不直接呼叫 search；admin_api.py 確認無外部 REST caller 依賴此格式
- 上線前確認：`grep -r '"entities"' dashboard/src` 無結果後才部署
- 若有外部 caller，需雙軌期（v1 舊格式繼續支援、v2 新 envelope 並行）或版本化 API

**驗收條件**：
- `search` 任意 collection 回傳均包裝為 Phase 1 envelope
- skill 文件中關於「Phase 1 統一格式」適用範圍的描述，明確包含 `search`
- 任何說「資料在 `response["data"]` 下」的 skill 說明，對 `search` 也成立
- 部署前確認 Dashboard 無舊格式依賴

---

### P1：影響流程品質

#### Issue 3 — `linked_entities=[]` 靜默接受但缺少提示

**現況**：task create/update 帶 `linked_entities=[]` 不回傳任何 warning，但 governance 規則明確要求每張票都應掛 entities。

**定義正確行為**：
- `linked_entities` 為空陣列或未傳時，server 在 `warnings` 欄位回傳提示訊息：
  `"linked_entities 為空：任務缺少 ontology context，governance_hints 將無法產生有效建議"`
- 不 reject（建票仍然成功），只 warn

**驗收條件**：
- `task(action="create", linked_entities=[])` 回傳中 `warnings` 包含上述提示
- `task(action="create", linked_entities=[...])` 回傳 `warnings` 不包含此提示
- SPEC-task-governance.md 補充「linked_entities 為空時會有 warning」的說明

---

#### Issue 4 — Task description 被 server 自動 reformat 未記錄

**現況**：task create/update 時，server 會將純文字 description 解析並重新格式化為結構化 Markdown（加標題、分段）。此行為未在任何文件中說明。

**定義正確行為**（不改 server 行為，只補文件）：
- SPEC-task-governance.md 在 `description` 欄位說明中補充：
  `"description 傳入後 server 會自動解析並格式化為結構化 Markdown。若需保留原始格式，在 description 開頭加上 [RAW] 標記（Phase 2 功能，Phase 1 只做文件補充）。"`

**驗收條件**：
- SPEC-task-governance.md 的 `description` 欄位說明包含 reformat 行為描述
- task-governance.md（skill 版）同步更新

---

#### Issue 5 — `search` 的 `status` 多值過濾行為未文件化

**現況**：dogfood 觀察到 `status="todo,in_progress,review,blocked"` 回傳 73,925 字元，誤判為過濾失效。

**Architect 調查結論**：多值過濾**已正確實作**（`tools.py:1117` 拆分逗號後傳入 SQL `IN` 子句）。大量回傳是因為 ZenOS 任務確實多，與過濾無關。

**定義正確行為**（只補文件）：
- task-governance.md 的去重搜尋範例加上 `limit=20` 建議，說明多值 status 有效但可能回傳大量資料
- SPEC 明確說明：`status` 支援逗號分隔多值，server 端已處理

**驗收條件**：
- task-governance.md 去重搜尋範例加上 `limit=20` 說明
- SPEC-task-governance.md 補充 `status` 多值過濾的說明

---

### P1（續）：Dogfood Round 2 發現

#### Issue 6 — `search` CJK 關鍵字命中率低

**現況**：搜尋 "ZenOS 治理" 未命中 "語意治理 Pipeline"、"Action Layer" 等包含 "治理" 的 entity。

**根因**：`src/zenos/domain/search.py` 的 `_tokenize()` 將中文字串視為單一 token。"語意治理" 是一個 token，"治理" 是另一個 token，兩者不相等，只能拿到 substring bonus +0.5。

**��義正確行為**：
- `_tokenize()` 對含 CJK 字元的 token，額外產出 bigram（二元組）。例："語意治理" → `["語意治理", "語意", "意治", "治理"]`
- `_score_match()` 對 query token 在 entity text 中的 substring 出現，給予 0.7 分（現為 0）

**驗收條件**：
- `search(query="治理", collection="entities")` 能命中 name/summary/tags 含 "治理" 的 entity
- `search(query="ZenOS 治理")` 能命中 "語意治理 Pipeline"
- 新增 CJK 搜尋測試案例

---

#### Issue 7 — `linked_entities` 回傳型別不一致

**現況**：
- `task(action="create/update")` 回傳 `linked_entities` 為 ID 字串陣列 `["id1", "id2"]`
- `confirm(collection="tasks")` 回傳 `linked_entities` 為完整物件陣列 `[{id, name, summary, ...}]`

**定義正確行為**：所有 task 回傳路徑統一使用 `_enrich_task_result()` 展開 linked_entities 為完整物件。

**驗收條件**：
- `task(action="create")` 回傳的 `linked_entities` 為物件陣列
- `task(action="update")` 回傳的 `linked_entities` 為物件陣列
- 與 `confirm` 回傳格式一致

---

## 不包含

- Dashboard UI 相關改動

---

## 驗收門檻（全部通過才關閉）

1. `confirm` 範例全部改為 `accepted`，且在 release SSOT 已合入
2. ~~`search` 回傳包裝 Phase 1 envelope（server 部署到 Cloud Run）~~ ✅ 已完成（dogfood 驗證通過）
3. `linked_entities=[]` 時 task create 回傳 warning
4. SPEC-task-governance.md 補充 description reformat 說明
5. `status` 多值行為有文件且行為符合文件描述
6. 有 integration test 覆蓋 Issue 1–3（至少各一條）
7. `search` CJK bigram tokenizer 實作並通過測試
8. `task` 所有回傳路徑的 `linked_entities` 為統一物件格式
