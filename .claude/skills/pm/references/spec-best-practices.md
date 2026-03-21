# 功能文件寫作最佳實踐

來源：Anthropic 官方 write-spec skill + 社群實踐整理

---

## 核心原則

### 1. P0 / P1 / P2 優先序
| 等級 | 定義 | 單一測試題 |
|------|------|-----------|
| P0 | 缺了這個，功能不成立 | 砍掉後無法解決核心問題 |
| P1 | 重要，但 v1 可以沒有 | 砍掉後功能還能用，只是體驗差 |
| P2 | 未來考慮 | 現在不做也沒關係 |

**規則：v1 只出 P0。這是防止 scope creep 最有效的方法。**

---

### 2. Given / When / Then 驗收條件

把需求寫成可測試的陳述句：

```
Given [使用者處於什麼狀態 / 系統在什麼條件下]
When  [使用者做了什麼動作 / 什麼事件發生]
Then  [系統應該有什麼可觀察的結果]
```

**壞的寫法：** 系統要快速回應
**好的寫法：**
```
Given 員工已輸入訂單內容
When  員工送出確認
Then  系統在 3 秒內回傳確認訊息，包含訂單摘要
```

---

### 3. 非目標（Non-Goals）一定要寫

非目標比目標更重要，因為它：
- 防止範圍蔓延
- 讓 Architect 知道不需要過度設計
- 讓未來的人理解當初的邊界決策

**範例：**
```
## 非目標
- 不支援批次訂單輸入（v1 只處理單筆）
- 不做庫存自動扣減（那是採購流程，不同場景）
- 不提供訂單修改功能（確認後不可改，錯了建新單）
```

---

### 4. 成功指標要可量測

區分短期訊號與長期結果：

```
短期（1-2 週）：員工開始用這個功能輸入訂單
長期（1-2 月）：訂單輸入錯誤率低於 5%
```

不要寫：「員工滿意度提升」（無法量測）
要寫：「員工不再用 Excel 或 LINE 群組確認訂單細節」（可觀察）

---

### 5. 問題陳述先於解法

先說清楚問題是什麼，再寫功能是什麼。
這樣做的好處：Architect 在實作時遇到技術困難，可以回頭看問題陳述，找到替代方案，而不是死守原始設計。

---

## 文件長度指引

| 文件類型 | 建議長度 | 原則 |
|----------|----------|------|
| Feature Spec | 1-2 頁 | 夠讓 Architect 實作，不超過 |
| Scene Spec | 半頁到 1 頁 | 聚焦在一個完整流程 |
| Decision Record | 半頁 | 決定了什麼 + 為什麼 + 影響 |

**超過這個長度，先問自己：哪些可以移到 Non-Goals？**

---

## 參考資源

- [Anthropic knowledge-work-plugins: write-spec](https://github.com/anthropics/knowledge-work-plugins/tree/main/product-management/skills/write-spec)
- [claude-code-spec-workflow](https://github.com/Pimzino/claude-code-spec-workflow)
- [awesome-claude-code: create-prd](https://github.com/hesreallyhim/awesome-claude-code)
