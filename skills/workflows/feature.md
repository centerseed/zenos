---
name: feature
description: >
  從需求討論到任務建立的完整功能開發流程。PM 和 Architect 互相確認 Spec 後，才交付開發。
  當使用者說「我有新功能要做」「幫我規劃這個功能」「寫 spec 然後開任務」「/feature」時使用。
  流程：PM 訪談 → PM ↔ Architect 交叉確認 → Spec Reviewer 審查 → 用戶確認 → Architect 建任務。
version: 1.0.0
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

## Phase 4：Architect 建立實作計畫

> 建票前必讀 `skills/governance/shared-rules.md` 的去重與 linked_entities 規則。

叫起 Architect agent（依照 Architect skill 流程）：
- 讀取剛確認的 Spec
- 技術設計
- 建立 tasks（`mcp__zenos__task(action="create", ...)`）—— 建票前先去重
- 分配 plan_id + plan_order

---

## Phase 5：Architect 調度實作與驗收

Architect 是實作階段的主控角色，按 plan_order 逐張 task 執行：

### 5.1 派工 Developer
- 叫起 Developer subagent，傳入 task 的 description + acceptance_criteria
- Developer 更新狀態：`task(action="update", id=X, status="in_progress")`
- Developer 完成後：`task(action="update", id=X, status="review", result="完成摘要")`

### 5.2 Architect 驗證交付
- 逐條比對 acceptance_criteria，確認實作符合要求
- 確認無 regression、blast radius 可控
- PASS → 交 QA 驗收；FAIL → 退回 Developer，附具體不符合的 AC

### 5.3 QA 驗收
叫起 QA subagent：
- 依照 acceptance_criteria 執行測試
- PASS：`confirm(collection="tasks", id=X, accepted=True)`
- FAIL：`confirm(collection="tasks", id=X, accepted=False, rejection_reason="退回原因")` → 退回 Developer，重走 5.1

每張 task 走完 5.1→5.2→5.3 才進入下一張。

---

## Phase 6：寫入 Work Journal（重大 feature 才寫）

只有 feature 真的完成一個跨 session 需要復盤的決策或交付邊界時才寫。一般任務完成狀態留在 task.result / PLAN log，不寫 journal。

```python
mcp__zenos__journal_write(
    summary="完成 {功能名稱}：{1-2 句摘要，含 Spec slug 和關鍵決策}",
    project="{專案名}",
    flow_type="feature",
    tags=["{功能關鍵字}"]
)
```

---

## 完成條件

- [ ] Spec 狀態為 `Approved`
- [ ] 所有 P0 需求都有對應 task（status: todo）
- [ ] 每個 task 有 linked_entities + acceptance_criteria
- [ ] Work journal 已寫入
