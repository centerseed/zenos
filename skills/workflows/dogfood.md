---
name: dogfood-governance
description: >
  ZenOS 治理流程 Dogfooding 評估 skill。讓 agent 實際走完一條完整治理鏈，
  測量摩擦點、重試原因、回傳格式一致性、skill 肥大問題。
  當需要評估治理流程品質、優化 skill 設計、或發現 agent 常卡住的地方時使用。
  用法：「/dogfood」或「幫我評估一下治理流程」。
version: 1.0.0
---

# /dogfood-governance — 治理流程 Dogfooding 評估

讓 agent 自己跑過一條完整的治理鏈，邊跑邊記錄卡點，最後輸出評估報告。

---

## 評估目標

| 維度 | 問題 |
|------|------|
| **流程順暢度** | 每個步驟能否一次成功？有沒有需要猜測的地方？ |
| **重試率** | 哪些步驟容易失敗或需要修正後重送？ |
| **Skill 肥大** | 每個 governance 規則檔有多少行？有無重複內容？ |
| **回傳格式一致性** | MCP 工具回傳是否符合 Phase 1 統一格式？ |
| **治理閉環完整性** | task create → update → review → confirm 能否完整跑通？ |

---

## 執行流程

### Step 0：初始化追蹤器

在記憶體建立一個追蹤表（用 markdown table 記錄，不寫檔案）：

```
| 步驟 | 操作 | 結果 | 重試次數 | 問題描述 |
|------|------|------|---------|---------|
```

每個步驟完成後立即填一行。

---

### Step 1：環境確認

```python
# 確認 MCP 可用
mcp__zenos__search(query="test", collection="entities")
```

- 若失敗 → 記錄「MCP 不可用」，中止並回報。
- 若成功 → 記錄回傳格式是否符合 `{status, data, warnings, ...}`。

---

### Step 2：去重搜尋（Task 治理鏈起點）

讀取 `skills/governance/task-governance.md` 開頭的建票前去重規則。

```python
mcp__zenos__search(
    query="dogfood 評估測試任務",
    collection="tasks",
    status="todo,in_progress,review,blocked"
)
```

評估點：
- 搜尋指令是否清楚？（status 過濾參數格式對不對）
- 有沒有既有重複票？

---

### Step 3：找 linked_entities 的 entity ID

```python
mcp__zenos__search(query="ZenOS 治理", collection="entities")
```

- 記錄：是否找到合理的 entity 可掛？
- 記錄：search 回傳結構是否讓人容易取出 ID？（`data[0].id` vs 其他路徑）

---

### Step 4：建立測試 Task

依照 `skills/governance/task-governance.md` 建票規範，用以下最小合規資料建一張測試票：

```python
mcp__zenos__task(
    action="create",
    title="[DOGFOOD] 驗證治理流程端到端可用性",
    description="這是 dogfood 評估用的測試任務。背景：需要確認治理鏈完整可跑。問題：目前無自動驗證機制。期望結果：確認 create→update→review→confirm 全程無異常。",
    acceptance_criteria=[
        "task 建立成功，回傳有效 task ID",
        "update(status=in_progress) 成功",
        "update(status=review, result=...) 成功",
        "confirm(accepted=True) 成功，任務進入 done"
    ],
    linked_entities=[]  # Step 3 找到的 ID 填入，找不到就留空並記錄
)
```

評估點：
- `linked_entities=[]` 時 server 是否接受？還是強制要求？
- 回傳的 `data.id` 路徑是否直觀？
- `warnings` 或 `suggestions` 有無有用資訊？
- title 長度驗證是否讓人困惑？

**記錄重試次數**：如果第一次 call 被 reject，記錄原因後修正重送。

---

### Step 5：更新狀態 → in_progress

```python
mcp__zenos__task(
    action="update",
    id="<Step 4 取得的 task ID>",
    status="in_progress"
)
```

評估點：
- 是否需要額外欄位？
- 回傳格式是否一致？

---

### Step 6：更新狀態 → review（result 必填測試）

```python
mcp__zenos__task(
    action="update",
    id="<task ID>",
    status="review",
    result="Dogfood 執行完成。已驗證 create/update/confirm 流程可跑。"
)
```

評估點：
- 是否有清楚的錯誤訊息提示 result 必填？（如果忘記填）
- 回傳中有沒有有用的 next step 提示？

---

### Step 7：Confirm 驗收

```python
mcp__zenos__confirm(
    collection="tasks",
    id="<task ID>",
    accepted=True,
    result="Dogfood PASS：完整治理鏈 create→review→confirm 無異常。"
)
```

評估點：
- confirm 回傳的 `governance_hints.suggested_entity_updates` 有無內容？
- 若 linked_entities 為空，hints 是否還有意義？

---

### Step 8：Skill 肥大分析（靜態）

不呼叫 MCP，直接分析 skill 檔案大小：

```bash
wc -l skills/governance/*.md skills/workflows/*.md .claude/skills/*/index.md 2>/dev/null | sort -rn | head -20
```

評估標準：
- **≤ 80 行**：合理
- **81–150 行**：偏長，考慮抽出子規則
- **> 150 行**：肥大，需要拆分或提取摘要版

同時用 Grep 找重複內容：

```bash
# 找在兩個以上文件都出現的段落
grep -l "建票前去重\|去重\|linked_entities 不存在" skills/governance/*.md skills/workflows/*.md
```

記錄哪些規則在多個 skill 裡重複出現。

---

### Step 9：輸出評估報告

```
══════════════════════════════════════════════
  ZenOS 治理流程 Dogfooding 評估報告
══════════════════════════════════════════════

## 執行摘要
  - 測試日期：{date}
  - 完整鏈測試：PASS / PARTIAL / FAIL
  - 總重試次數：{n}

## 步驟追蹤表
| 步驟 | 操作 | 結果 | 重試次數 | 問題描述 |
|------|------|------|---------|---------|
| Step 1 | MCP 環境確認 | ... | ... | ... |
| Step 2 | 去重搜尋 | ... | ... | ... |
| Step 3 | Entity 搜尋 | ... | ... | ... |
| Step 4 | Task 建立 | ... | ... | ... |
| Step 5 | → in_progress | ... | ... | ... |
| Step 6 | → review | ... | ... | ... |
| Step 7 | confirm | ... | ... | ... |

## 摩擦點清單（卡住或需修正的地方）
{按嚴重程度排列}

## Skill 肥大報告
| 檔案 | 行數 | 評級 | 重複內容 |
|------|------|------|---------|
| task-governance.md | ... | ... | ... |
| governance-loop.md | ... | ... | ... |
| ... | ... | ... | ... |

## 回傳格式一致性
  - 統一格式符合率：{n}/{total} 個 call
  - 不符合項目：{list}

## 具體改善建議
1. {最高優先：直接影響 agent 操作的問題}
2. {次優先：skill 結構或重複問題}
3. {長期：架構層級的改善}

══════════════════════════════════════════════
```

---

## 評估後的後續動作

若發現問題，**不要直接在本 skill 裡修改 governance 規則**。
問題應該：
1. 記入 Journal（`mcp__zenos__journal_write`）作為觀察紀錄
2. 若需要修改 SSOT skill → 提醒用戶走 SSOT 修改流程（改 `release/` 目錄）
3. 若是緊急 workaround → 在本 `skills/workflows/` 下建立臨時補丁 skill，標注 `[TEMP]`

---

## 注意事項

- 本 skill 建立的測試任務標題會以 `[DOGFOOD]` 開頭，評估後應手動 cancel
- 本 skill 是 **project-local**，不屬於 SSOT，不需要部署或同步
- 若 MCP 連線失敗，仍可執行 Step 8（Skill 肥大分析）並輸出部分報告
