---
type: ADR
id: ADR-014
status: Accepted
l2_entity: 語意治理 Pipeline
created: 2026-04-06
updated: 2026-04-06
---

# ADR-014: Journal 壓縮觸發 Entry 蒸餾

## 決策

當 `journal_write` 回傳 `compressed: true`（後端自動壓縮觸發），capture skill 立即執行 entry 蒸餾步驟：從本次產生的 summary journal 萃取 decision/insight/limitation/change/context，寫入對應 L2 entity 的 entries。

**核心原則：後端壓縮 journal → 前端（skill）蒸餾 entries，兩步驟順序執行。**

## 背景

### 問題

ZenOS entries 層幾乎空白。以 paceriz 為例，11 筆 journal、9 個 L2 entity，但只有 4 筆 entries，且多為手動寫入。

根因：
1. Entry 蒸餾需要明確呼叫 `/zenos-capture`
2. `/zenos-capture` 執行後只寫 journal，不寫 entries
3. 「把 journal 決策升層為 entry」的動作從未被觸發

結果：知識停留在短命的 journal（流水帳）或靜態的 L2 summary，entries 作為中間層形同虛設。

### 現有機制

後端 `journal_write` 已實作壓縮邏輯：同一 project 的 raw journal 超過 20 筆時，自動合併為一筆 `is_summary: true` 的 summary journal，並在回傳值中標記 `compressed: true`。

這個機制解決了 journal 無限增長問題，但**壓縮後沒有觸發任何 entry 蒸餾**，知識仍然流失。

## 決策理由

### 為什麼在 `compressed: true` 時觸發

壓縮時機是最佳蒸餾時機，原因：

1. **信號意義明確**：後端壓縮代表「這段時間的工作已成形，值得回顧」
2. **輸入品質最高**：蒸餾從 summary journal（已壓縮的精華）進行，而非 20 筆雜訊
3. **零額外觸發成本**：不需要用戶記得另外呼叫，壓縮時自動執行
4. **頻率適當**：每 20 筆 raw journal 觸發一次，以用戶日均 10-25 次 capture 的節奏，約每 1-2 天蒸餾一次

### 為什麼是 skill 端執行而非 server 端

Entry 蒸餾本質是**語意判斷**（哪些值得固化、歸屬哪個 L2），符合 ADR-013 的分散治理原則：

- **Server 端**：結構執法（壓縮計算、is_summary 標記）→ 已實作
- **Agent/Skill 端**：語意判斷（蒸餾什麼、掛到哪個 entity）→ 本 ADR 新增

在 server 端做語意判斷需要 LLM，延遲不可控，且缺乏 agent 已有的 session context。

### 為什麼不需要額外的蒸餾閾值

PM 評估確認：entry 隨時都可以蒸餾，頻率不是問題。每次壓縮後立即蒸餾，確保 entries 始終反映最新狀態。

## 實作規格

### 觸發條件

```
journal_write() 回傳 { compressed: true }
```

### 執行步驟

**Step A：取得 summary journal**

```python
# 拿剛產生的 summary journal（最新一筆 is_summary=true）
journal_read(project="{專案名}", limit=5)
# 找 is_summary=true 的最新一筆，這就是蒸餾的來源
```

**Step B：對 summary journal 執行 Step 3.5 蒸餾**

對 summary journal 的內容，執行現有 capture skill 的 Step 3.5 流程：

1. 從 summary 識別 entry 候選（decision/insight/limitation/change/context）
2. 通過兩關判斷標準：
   - **排除關**：已在文件/ADR 裡、實作事實、太抽象
   - **價值關**：「下次 agent 看到這條 entry 會改變行為嗎？」
3. 比對現有 entries（避免重複）
4. 寫入或 supersede

**Step C：呈現蒸餾結果（不需要用戶確認）**

```
── Entry 蒸餾（journal 壓縮觸發）────────────────
  [E1] 新增 decision → {L2 entity 名稱}
    「{content}」
  [E2] 新增 insight → {L2 entity 名稱}
    「{content}」
  [--] 跳過 {n} 條（重複或不符標準）
────────────────────────────────────────────────
```

### 修改範圍

**唯一需要修改的文件：`skills/release/zenos-capture/SKILL.md`**

在現有的「寫入 Work Journal」章節（Step 5 / 模式 A/B/C 完成後都要做）的 `journal_write` 呼叫後，加入：

```
journal_write() 完成後：
  → 若回傳 compressed: true
  → 執行 Entry 蒸餾（Step A-C）
```

**不需要 backend 變更**：後端壓縮機制已存在，`compressed` 回傳值已有，`is_summary` 欄位已有。

## Spec 衝突檢查

- 與 ADR-013（分散治理）：相容。蒸餾是語意判斷（skill 端），壓縮是結構執法（server 端）
- 與 ADR-010（entity entries）：相容。entry 類型、判斷標準、寫入規則沿用現有定義
- 與現有 capture skill Step 3.5：直接複用，無衝突

## 考慮過的替代方案

### 方案 A：獨立的蒸餾閾值（每 N 筆 summary journal 蒸餾一次）

否決原因：增加複雜度，且 PM 確認不需要控制頻率。

### 方案 B：Server 端自動蒸餾（壓縮時 server 呼叫 LLM）

否決原因：語意判斷成本在 server 端不可控，且違反 ADR-013 分散治理原則。

### 方案 C：獨立的 `/zenos-distill` skill

否決原因：需要用戶記得呼叫，沒有解決根本問題（entries 空白的原因就是缺乏自動觸發）。

## 影響範圍

- `skills/release/zenos-capture/SKILL.md`：加入 compressed 觸發邏輯（唯一修改）
- `skills/governance/capture-governance.md`：更新說明 compressed 觸發時機

## 相關文件

- `ADR-010-entity-entries`（entries 設計原則）
- `ADR-013-distributed-governance`（agent 端語意 vs server 端結構）
- `skills/release/zenos-capture/SKILL.md`（實作目標）
