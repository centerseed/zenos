# PM → Architect：/zenos-sync Skill 問題回覆

> 日期：2026-03-21
> 回覆對象：PM-questions-zenos-sync-skill.md

---

## 回覆摘要

| 問題 | 決定 |
|------|------|
| Q1 | **拆兩個 skill** |
| Q2 | **不讀完整 context** |
| Q3 | 同意 (c)：神經層自動 draft，骨架層對話確認 |
| Q4 | 同意：可 propose 骨架層，一律 draft + confirm |
| Q5 | 同意 Phase 1 不做動作 2，加「原文過長提醒」 |
| Q6 | 同意取代 Phase 0.5 |

---

## 詳細回覆

### Q1：拆兩個 skill

Barry 的主要使用場景是**中途隨時存**——對話中產出有價值的東西，立刻觸發存入 ontology。

這跟 A（git 變更掃描）的節奏完全不同，所以拆成：

- **`/zenos-capture`**（或類似命名）— 輕量、快速，從當前對話片段擷取知識 → propose 到 ontology。這是 Phase 1 的主力。
- **`/zenos-sync`** — 較重，掃 git log → 比對 ontology → 批量 propose。Phase 1 可以做但優先級較低。

命名建議供 Architect 參考，最終命名由 Architect 決定。

### Q2：不讀完整 context

因為使用場景是「中途隨時存」，不需要讀整個 session context。兩種典型觸發情境：

1. **對話中剛討論完一段** → skill 只需要讀最近的對話片段（不是整個 session）
2. **用戶已經請 agent 寫成檔案** → skill 讀那份檔案就好，不需要讀對話

具體的 context 範圍裁切方式由 Architect 決定技術實作。核心原則是：**快，不要讓用戶等。**

### Q3：同意 (c)

神經層自動生效（draft, confirmedByUser: false），骨架層在對話中列出讓用戶確認。跟 spec 設計一致。

### Q4：同意

對話可以 propose 骨架層新實體，一律 draft，需要 confirm()。

### Q5：同意，加提醒

Phase 1 不做動作 2（不存原始內容）。

追加一條 UX 規則：**如果 skill 偵測到擷取的知識原文超過 500 字，提醒用戶自行存檔。** 這不是實作動作 2，只是一行提醒文字，避免大量「只有 summary 沒有原文」的 entry 累積。

### Q6：取代

`/zenos-capture`（和 `/zenos-sync`）統一取代 Phase 0.5 的 session 結束提醒機制。不共存。

---

## 修正後的預設方案

```
/zenos-capture 觸發時（輕量，主力）：
  1. 讀最近對話片段 or 用戶指定的檔案 → 找出有價值的新知識
  2. 對照 Firestore 現有 ontology → 產出 proposals
     - 神經層：直接寫入 draft（confirmedByUser: false）
     - 骨架層：列出讓用戶當場確認
  3. 不存原始內容（但原文 >500 字時提醒用戶自存）

/zenos-sync 觸發時（較重，輔助）：
  1. 讀 git log --since="上次 sync" → 找出變更的文件
  2. 對照 Firestore 現有 ontology → 產出 proposals
     - 神經層：直接寫入 draft
     - 骨架層：列出讓用戶確認
  3. 不存原始內容
```

---

*Architect 可以開始技術設計了。如有追問歡迎回來。*
