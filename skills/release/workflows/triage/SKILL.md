---
name: triage
description: >
  快速盤點所有未完成任務，找出需要決策的項目。
  當使用者說「看一下現在有哪些任務」「盤點任務」「任務盤點」「/triage」時使用。
  輸出 Triage Report，標記卡住、需確認、高優先未動、等待驗收的項目。
version: 1.0.0
---

# /triage — 任務盤點

快速盤點所有未完成任務，找出需要決策的項目。

---

## 執行步驟

### Step 1：撈出所有未完成任務

```python
mcp__zenos__search(collection="tasks", status="todo,in_progress,review")
```

### Step 2：分類整理

依狀態分組：

| 狀態 | 代表 | 需要誰處理 |
|------|------|-----------|
| `review` | 等待驗收 | QA 或 Architect |
| `in_progress` | 進行中 | Developer 或 Debugger |
| `todo` | 待啟動 | 確認優先順序 |

### Step 3：找出需要決策的項目

標記以下情況：
- ⏸️ **卡住**：in_progress 但超過 2 天沒更新（updated_at 距今 > 48h）
- ❓ **需要確認**：todo 但沒有 linked_entities 或 acceptance_criteria
- 🔴 **高優先未動**：priority=critical/high 且 status=todo
- 👀 **等待驗收**：status=review 且沒有指定 QA

### Step 4：輸出報告

```
── Triage Report ──────────────────────────────

📋 總計：{n} 個未完成任務

🔴 需要立即處理（{n} 個）
  - [task title] — {原因}

⏸️ 卡住（{n} 個）
  - [task title] — 停滯 {n} 天

👀 等待驗收（{n} 個）
  - [task title]

📝 待啟動（{n} 個，依優先級）
  - [task title] — {priority}

─────────────────────────────────────────────

建議下一步：
1. {最優先的行動}
2. {次優先的行動}
```
