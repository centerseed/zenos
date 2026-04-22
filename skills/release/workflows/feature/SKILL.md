---
name: feature
description: >
  從需求討論到任務建立的完整功能開發流程。PM 和 Architect 互相確認 Spec 後，才交付開發。
  當使用者說「我有新功能要做」「幫我規劃這個功能」「寫 spec 然後開任務」「/feature」時使用。
  流程：PM 訪談 → PM ↔ Architect 交叉確認 → Spec Reviewer 審查 → 用戶確認 → Architect 建任務。
version: 1.1.0
---

# /feature — 功能開發流程

從需求討論到任務建立的完整流程。PM 和 Architect 互相確認 Spec 後，才交付開發。

---

## Phase 1：PM 需求訪談

叫起 PM agent（依照 PM skill 流程）：
- 與用戶訪談，釐清目標、用戶、範圍、優先級
- 草擬 Feature Spec 各章節
- 逐章讓用戶確認

---

## Phase 2：PM ↔ Architect 交叉確認 Spec

PM 完成初稿後，**必須找 Architect 做技術確認**，再回 PM 修訂，直到雙方無異議。

**PM 發給 Architect 的問題：**
```
請確認以下 Spec 內容：
1. 技術可行性：有沒有不可行或成本極高的需求？
2. 衝突偵測：與現有系統或其他 Spec 有無矛盾？
3. 遺漏的技術約束：有沒有 PM 沒想到的技術邊界？
```

**Architect 回覆 PM 的格式：**
```
✅ 可行 / ⚠️ 有問題 / ❌ 不可行

問題列表：
- [章節] 問題描述 → 建議修法

結論：Spec 可進入用戶確認 / 需要 PM 修訂後再確認
```

若 Architect 有問題 → PM 修訂 Spec → 再送 Architect 確認
直到 Architect 回覆「Spec 可進入用戶確認」為止。

---

## Phase 2.5：Spec Reviewer 品質與衝突審查

PM 與 Architect 確認無技術異議後，**在呈給用戶之前**，執行一次自動審查。

### 步驟

**1. 搜尋相關既有 Spec**
```python
mcp__zenos__search(query="{功能關鍵字}", collection="documents")
```

**2. 逐一比對，找出衝突或重疊**

| 檢查項目 | 說明 |
|----------|------|
| 功能重疊 | 這個需求是否已有其他 Spec 覆蓋？ |
| 行為衝突 | 與既有 Spec 的 AC 有無矛盾？ |
| 術語不一致 | 同一概念是否用了不同名稱？ |
| 範圍蔓延 | 是否有隱含依賴未被標記為 P0？ |

**3. 品質審查**

| 檢查項目 | 標準 |
|----------|------|
| AC 格式 | 每條需求都有 Given/When/Then |
| PM 紅線 | 無技術決策混入（不寫 schema/API/框架） |
| 明確不包含 | 有列出範圍邊界 |
| 開放問題 | 不確定的地方有標記 |

**4. 輸出審查結果**

```
SPEC REVIEW
══════════════════════════════════════
Spec：     {SPEC-slug}
衝突：     ✅ 無 / ⚠️ {衝突描述，含相關 Spec 連結}
品質問題： ✅ 無 / ⚠️ {問題描述，含章節位置}
結論：     PASS → 進入用戶確認
           NEEDS_FIX → 列出必修項，退回 PM
══════════════════════════════════════
```

若 NEEDS_FIX → PM 修訂後重跑 Phase 2.5。
若 PASS → 進入 Phase 3。

---

## Phase 3：用戶最終確認

PM 將完整 Spec 呈給用戶逐章確認。
用戶確認後，Spec 狀態改為 `Approved`。

---

## Phase 4：PM → Architect Handoff + 建實作 PLAN

> 建票前必讀 `skills/governance/shared-rules.md` 的去重與 linked_entities 規則。
> 2026-04-19 Action-Layer 升級：派工必須同時包含顯性 handoff chain 與真實 agent 調度。`handoff` 是治理記錄，不是 runtime claim。

### 4.0 PM 先建 Plan entity（SSOT）

`plan_id` 必須是 real Plan 的 UUID，不能塞 slug 字串。PM 在建第一張 task 之前先建 Plan：

```python
plan = mcp__zenos__plan(action="create",
    goal="{一句話 feature 目標}",
    product_id="{product_entity_id}",   # 必填（ADR-044）— plan/task 歸屬 SSOT
    entry_criteria="Spec Approved + linked_entities ready",
    exit_criteria="所有 P0 AC green + 部署驗證通過")
# plan["data"]["id"] 是 32-char UUID，下面所有 task 的 plan_id 都用這個 id
```

### 4.1 PM 建 task + 交棒

```python
mcp__zenos__task(action="create",
    title="實作 {feature_slug}", dispatcher="agent:pm",
    product_id="{product_entity_id}",   # 必填，必須等於 plan.product_id
    linked_entities=[...],              # 只放 L2 module / L3 goal(milestone)，禁止放 product entity
    plan_id="{plan.id}",                 # ← Plan UUID，非 slug
    acceptance_criteria=[...])
mcp__zenos__task(action="handoff", id="{task_id}",
    to_dispatcher="agent:architect", reason="spec ready",
    output_ref="docs/specs/SPEC-{slug}.md")
```

### 4.2 Architect 接手

- 讀 task + `handoff_events` 取完整脈絡
- 技術設計
- 必要時拆 subtask（`parent_task_id=<parent>` 必填 + `product_id=parent.product_id` + `plan_id=parent.plan_id`；server 強制跨 product/plan reject）
- 每張 task ready → handoff to `agent:developer`

---

## Phase 5：Handoff Chain 實作

每張 task 走完整 PM → Architect → Developer → QA handoff 鏈條：

### 5.1 Architect → Developer
```python
mcp__zenos__task(action="handoff", id=X,
    to_dispatcher="agent:developer",
    reason="TD ready, implementation dispatched",
    output_ref="docs/designs/TD-{slug}.md")
```
接著立刻叫起 Developer subagent，傳入 task description + AC + TD 引用。

注意：
- 只做這個 handoff，task 只會更新 `dispatcher`
- server 不會自動改成 `in_progress`
- server 不會自動填 `assignee`
- 必須真的有 Developer agent 起來認領，後續 `in_progress` 才會成立

### 5.2 Developer 接手 + 實作
- 讀 task + handoff_events 取完整脈絡（PM 原意 + Architect 設計）
- 啟動第一步就更新：`task(action="update", id=X, status="in_progress")`
- 實作完成後 handoff to QA：
```python
mcp__zenos__task(action="handoff", id=X,
    to_dispatcher="agent:qa",
    reason="implementation complete, tests green",
    output_ref="{commit SHA}",
    notes="交付摘要 / 驗證指令 / 已知風險")
```
Server 自動升 `status=review`。

### 5.3 QA 驗收
叫起 QA subagent，讀 task + handoff_events（看整條履歷）：
- **PASS**：`confirm(collection="tasks", id=X, accept=True, entity_entries=[...])`
  - Server 自動 append 結束 HandoffEvent（to="human", reason="accepted"）+ status=done
- **FAIL**：
  ```python
  mcp__zenos__task(action="handoff", id=X,
      to_dispatcher="agent:developer",
      reason="rejected: {instance_fix}; class_fix: {class_fix}")
  ```
  退回 Developer，重走 5.2。

每張 task 走完 5.1→5.2→5.3 才進入下一張。整條履歷沉澱在 `task.handoff_events`，任何時刻 `get(task)` 都能看完整派工軌跡。

---

## Phase 6：Plan 閉環（必做）

所有 task 進入 terminal state（done / cancelled）後，PM 把 Plan 收口：

```python
mcp__zenos__plan(action="update",
    id="{plan.id}",
    status="completed",
    result="交付摘要：{功能描述}；commit：{SHA}；部署：{URL 或 Cloud Run revision}；驗證：{E2E 測試結果}")
```

副作用與約束：
- Server 會檢查所有下轄 task 是否 terminal，任一未完成 → reject（訊息會列前 5 個未 terminal task id）
- `result` 必填；空字串也會 reject
- completed 後 Plan immutable，不可再改欄位
- 若 feature 中途棄置 → `status="cancelled"` + 寫 `result` 說明原因

責任人：PM（feature 發起人）。Architect / Developer / QA 不負責關 Plan。

---

## Phase 7：寫入 Work Journal（必做）

**寫入前先查：**
```python
mcp__zenos__journal_read(limit=20, project="{專案名}")
# 找同功能/同 module 的近期筆記
# → 延續同一件事：新 summary 包含完整脈絡，讓舊筆記變冗餘
# → 新的不相關工作：正常新增
```

```python
mcp__zenos__journal_write(
    summary="完成 {功能名稱}（{Spec slug}）：{不可從 code 重建的關鍵決策或洞察}；下一步：{next 或 無}",
    project="{專案名}",
    flow_type="feature",
    tags=["{功能關鍵字}"]
)
```

> 不要重複 commit message。寫「為什麼這樣設計」和「接下來要做什麼」。

---

## 完成條件

- [ ] Spec 狀態為 `Approved`
- [ ] Plan entity 已建立（real UUID，非 slug）
- [ ] 所有 P0 需求都有對應 task（status: todo，`plan_id` = Plan UUID）
- [ ] 每個 task 有 linked_entities + acceptance_criteria
- [ ] 所有 task 走完 handoff chain 到 terminal state
- [ ] Plan status = completed 且 result 非空
- [ ] Work journal 已寫入
