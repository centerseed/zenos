# 知識捕獲分層路由規則 v1.0（完整版）

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
   - **強制要求**：開 Task 時必須填入 `source_metadata`。
   - 將引發此任務的「對話原文」或「設計決策片段」填入 `provenance[].snippet`。
   - 包含 `type` (chat/doc) 與 `label` (來源標題)。
   - 此舉確保 UI 上的「來源追溯」功能生效，並讓後續處理者獲得完整 context。
4. 以上皆否：掛 entity.sources（不建 entity）

## 寫入 L2 的強制要求（Server 端硬性規則）
write(collection=\"entities\", data={type=\"module\", ...}) 時必須附帶 layer_decision：
- q1_persistent: true/false（跨時間存活？）
- q2_cross_role: true/false（跨角色共識？）
- q3_company_consensus: true/false（公司共識？）
- impacts_draft: [\"A 改了 X → B 的 Y 要跟著看\"] （至少 1 條）

三問未全通過 → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問通過 but impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

## 錯誤路徑處理

收到 LAYER_DOWNGRADE_REQUIRED 時：
1. 找出哪問沒通過（q1/q2/q3 哪個是 false）
2. 重新考慮是否真的是公司共識概念
3. 如果確實不是 L2 → 改為 L3 document 或 sources
4. 如果認為判斷錯誤 → 在 layer_decision 中補充說明後重試

收到 IMPACTS_DRAFT_REQUIRED 時：
1. 問自己：「這個概念改了，哪個其他概念要跟著看？」
2. 如果真的想不出任何 impacts → 強烈訊號此概念不夠 L2
3. 補充至少一條具體 impacts 後重試

## 增量捕獲 vs 全局統合模式

增量模式（日常使用）：
- 一次捕獲 1-3 個概念
- 適合：開完會、看完一份文件、做完一個 task
- 流程：識別概念 → 三問 → 如通過直接 write

全局統合模式（冷啟動 / 大型 review）：
- 一次處理整個 codebase 或一批文件
- 適合：首次接手專案、季度 ontology review
- 流程：先讀全局，再識別，再統一 write
- 重點：不要邊讀邊 write，等全局視野建立後再決定 L2 邊界

## Impacts 推斷策略

問法 1（改變傳播）：「如果這個概念的定義改了，哪些文件/流程/系統要更新？」
問法 2（依賴關係）：「哪些東西的正確性依賴於這個概念是穩定的？」
問法 3（跨角色影響）：「工程師改了這個，行銷/法務/客服需要知道什麼？」

如果三個問法都問不出答案 → 此概念不是 L2。

## 降級流程細節

降為 L3 document：
- 建 document entity，設 type 和 source.uri
- ontology_entity 指向最相關的 L2
- 適合：有正式文件形式的內容

降為 sources：
- 不建 entity，直接加到現有 L2 的 sources 陣列
- 適合：參考資料、草稿、一次性輸入
- sources 格式：{uri: \"...\", type: \"document|github|notion\", synced_at: \"...\"}
