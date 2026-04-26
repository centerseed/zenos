# 知識捕獲治理規則

> **前置條件：** 所有捕獲操作開始前必須完成 [Step 0: Context Establishment](bootstrap-protocol.md)。
> 這確保不同用戶在不同裝置上執行 capture 時，都從同一個 product scope 出發。

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
| Work Journal | journal | 只有實際新增/更新知識，或留下 TBD/盲點需要下輪接續時才寫 |

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

## Anti-pattern 負面範例（2026-04-19 實證）

訓練計畫系統 entity 一度累到 53 active entries，手動稽核後發現以下退化模式反覆出現。**下筆前自我檢查這 9 類，命中任一就不該寫 entry**：

| Anti-pattern | 反例（archived ID） | 為什麼不該記 |
|---|---|---|
| 純 code path trace | `SlotDistributionSection._get_slot_distribution()（:633）... Call path: get_plan_run → ...` | grep 5 秒可得 |
| 實作細節 + 函式內行為 | `_extract_types` 遞迴解析必須處理 dict/string；`hr_target_percent 會覆蓋 pace_zone` | 讀函式即知 |
| Fallback / 默認行為 | `_convert_stages_to_v2() 對未知 stage_id 默默 fallback 到 base` | code 可驗 |
| 配置事實 | `complete_10k 沒有 LSD slot` | YAML 可查 |
| Bug fix commit log | `auto_fill_heart_rate() 的 easy_zone[0] 是 index bug`；entry 帶 commit SHA | git log 範疇 |
| Transient debug noise | `V1 endpoint 404 P3 noise`、特定時間點的現象 | 短壽事件 |
| 已被解決的 limitation | limitation A 已被 decision B 修掉仍留 active | 應 supersede |
| 重複主題未合併 | 兩條 entry 講同一件事（粒度相似） | 應 consolidate |
| 短壽 supersede 鏈 | 同主題 3 天內寫 3 版（df580c91→4afdfbfe→cb407680） | 設計未收斂就下筆 |

**根本測試**：寫 entry 前先問——「這條知識 agent 讀 code 或 git log 五分鐘內能推導出來嗎？」能 → 不記。

**entry 本質是 code 讀不出來的東西**：決策取捨、業務規則、架構層 tradeoff、語言陷阱。不是 bug fix 紀錄、不是 changelog、不是 code navigation 備忘。

---

## Work Journal 規範

`/zenos-capture` 只有在有實際新增/更新知識、或留下 TBD/盲點需要下輪接續時才寫 journal。純掃描無變更不要寫。

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
