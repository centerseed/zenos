# 知識捕獲治理規則

## 捕獲的定位

`/zenos-capture` 是 ZenOS 知識層的唯一寫入入口。
捕獲的目的是把「只存在對話或人腦中、code 裡看不到的知識」固化到 ontology，讓下一個 agent 或同事不需要重新發現。

捕獲不是：
- 文件備份（文件留在 Git/Drive，ZenOS 只存語意代理）
- 會議記錄（流水帳不進 ontology）
- 系統操作日誌（code 和 git history 看得到的，不捕獲）

---

## 知識分層

| 層次 | 儲存位置 | 捕獲條件 |
|------|---------|---------|
| L2 骨架層 | entity（module/product/goal） | 公司共識概念，改了有下游影響，跨時間存活 |
| L3 神經層 | document entity | 某份具體文件值得在 ontology 建立語意代理 |
| 知識條目 | entry（decision/insight 等） | 通過兩關判斷標準的具體知識點 |
| Work Journal | journal | 每次捕獲完都寫，記錄捕獲狀態與待補 TBD |

---

## entry 兩關判斷標準

**第一關：排除**（以下任一成立就不記）：
- 已寫在 ADR / spec / 文件裡 → 文件是 SSOT，entry 不重複文件
- 產品原則、願景、定位 → 屬於 entity summary 或 tags
- 實作事實（code / git history 看得到）→ agent 自己能拿到
- 太抽象的 insight（對具體工作沒有指引作用）→ 聽起來對但用不上

**第二關：確認價值**：
> 某個 agent 或同事下次碰到這個 L2 相關的工作時，看到這條 entry 會改變他的行為嗎？

會 → 記。不會 → 不記。

---

## Work Journal 規範

每次 `/zenos-capture` 完成後**必須**寫 journal：

- `flow_type = "capture"`
- `summary` 寫「捕獲了什麼」和「還缺什麼（TBD）」，不寫數量
- 同來源/同產品有舊筆記時，新 summary 整合兩次狀態，讓舊筆記變冗餘

### journal compressed 觸發時機

當 `journal_write` 回傳 `compressed: true` 時，代表後端已將 raw journals 壓縮為 summary journal。此時 capture skill 會立即對 summary journal 執行 entry 蒸餾（Step 3.5），確保壓縮的知識精華被固化到 entries 層，不因 journal rotation 流失。

觸發頻率：約每累積 20 筆 raw journal 觸發一次（由後端 journal 壓縮邏輯決定）。

---

## L2 三問標準

建立新 L2 entity 前，必須通過以下三問：
1. **是不是公司共識？** 公司裡任何人說出來都會點頭
2. **改變時有下游影響？** 這個概念改了，有其他概念必須跟著動
3. **跨時間存活？** 不是一次性事件，是持續為真的事實

三問都是 → 可建 L2。否則進 entry 或不捕獲。

---

## 自動 vs 需確認

| 操作 | 是否需要用戶確認 |
|------|--------------|
| 寫入 entry | 自動（不需確認） |
| 寫入 document（神經層） | 自動 draft（confirmed_by_user=false） |
| 新增 L2 entity | 需確認 |
| 新增 relationship | 需確認 |
| compressed 觸發蒸餾 | 自動（不需確認） |
