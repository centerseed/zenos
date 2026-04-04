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

## Phase 3：用戶最終確認

PM 將完整 Spec 呈給用戶逐章確認。
用戶確認後，Spec 狀態改為 `Approved`。

---

## Phase 4：Architect 建立實作計畫

叫起 Architect agent（依照 Architect skill 流程）：
- 讀取剛確認的 Spec
- 技術設計
- 建立 tasks（`mcp__zenos__task(action="create", ...)`）
- 分配 plan_id + plan_order

---

## 完成條件

- [ ] Spec 狀態為 `Approved`
- [ ] 所有 P0 需求都有對應 task（status: todo）
- [ ] 每個 task 有 linked_entities + acceptance_criteria
