# /debug — Bug 修復流程

多角色協同的根因導向修復流程。任何一個角色都不能跳過自己的步驟。

---

## 觸發條件

用戶說「有 bug」「這個壞了」「為什麼不正常」「修這個錯誤」時啟動。

---

## Phase 1：Debugger 分析

叫起 Debugger agent（依照 Debugger skill 流程）：
- Phase 0：拉 backend log（自動偵測部署平台）
- Phase 1-4：症狀收集 → code path → 假設驗證
- 輸出：根因假設（含 file:line，信心度）

Debugger 輸出格式：
```
根因假設：{描述，含 file:line}
信心度：高 / 中 / 低
支撐證據：{log 截圖 / code / 測試結果}
```

---

## Phase 2：Architect 第一性原理驗證

叫起 Architect agent，傳入 Debugger 的根因假設：

**Architect 要回答：**
1. 這是真根因還是 symptom？（「如果只改這裡，根本問題還在嗎？」）
2. 是架構問題嗎？（需要重設計，不只修一行 code）
3. 修這裡會影響哪些其他地方？（blast radius）

**結論分支：**
- 根因正確，是局部 bug → 繼續 Phase 3
- 根因正確，是架構問題 → 停止，開 ADR，走 /feature 流程重設計
- 根因有疑問 → 退回 Debugger 繼續分析

---

## Phase 3：QA 設計重現測試

叫起 QA agent：
- 根據 Debugger 的根因假設，**設計一個會 FAIL 的測試**
- 測試在修復前必須 FAIL（否則測試本身沒意義）
- 測試格式依照 QA skill 的回歸測試格式

```python
# Regression: BUG-描述 — {什麼壞了}
# Confirmed FAIL before fix by QA on {date}
def test_regression_{bug}():
    # exact precondition setup
    # triggering action
    # specific assert
```

**QA 確認：**「測試已執行，結果：FAIL ✅（符合預期，bug 可重現）」

---

## Phase 4：Developer 修復

叫起 Developer agent：
- 讀取 Debugger 的根因 + Architect 的確認 + QA 的測試
- **只修根因，不修 symptom**
- 修復後測試必須 PASS
- 更新 task result，status → review

---

## Phase 5：Architect 最終確認

Architect 確認：
1. 測試 PASS（開發人員提供輸出）
2. 根因確實被移除（不是繞過）
3. 無新的 regression
4. 執行 `mcp__zenos__confirm(collection="tasks", id="...", accept=True)`

---

## 完成條件

- [ ] 根因有 file:line 定位
- [ ] 回歸測試存在且在修復前 FAIL、修復後 PASS
- [ ] Architect 執行 confirm
