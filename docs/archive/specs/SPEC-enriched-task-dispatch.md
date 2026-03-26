# Feature Spec: 富文本派工（Enriched Task Dispatch）

## 狀態
Delivered — commit 58aa815 (feat) + 15d61c1 (simplify), 2026-03-24

## 背景與動機

ZenOS 的核心主張是「讓 AI agent 在執行任務時自動獲得公司 context」。但目前的派工流程只傳遞任務文字，有三個斷裂：

1. **任務→知識斷裂**：`linked_entities` 只存 entity ID，執行者拿到任務後還要自己再查一次 entity 內容
2. **任務→執行者斷裂**：`assignee` 是純字串，不連結 Role entity，執行者無法自動獲得「我作為這個角色應該知道什麼」
3. **context_summary 是空白支票**：欄位存在但沒有自動填充機制，完全靠建任務的人手動填

結果：派工的本質仍是「派文字任務」，而不是「派知識包」。

## 目標用戶

- **任務執行者（人或 agent）**：收到任務時，不需要額外查詢就能理解背景
- **任務建立者（PM / Architect / agent）**：建任務時不需要手動填 context，系統自動組裝

## 需求

### P0（必須有）

#### 取任務時展開 linked entity 內容
- **描述**：當執行者呼叫 `get(collection="tasks", id="...")` 時，回傳的 task 中，`linked_entities` 應該包含每個 entity 的完整摘要（name、summary、tags、status），而不只是 ID。
- **Acceptance Criteria**：
  - Given 一個 linked_entities 有 2 個 entity ID 的 task，When 執行者呼叫 get task，Then 回傳結果中 linked_entities 是展開的 entity 物件（含 name、summary、tags、status），不是只有 ID
  - Given linked_entities 為空，When 執行者呼叫 get task，Then 回傳正常，linked_entities 為空陣列

#### 建任務時自動生成 context_summary
- **描述**：當 `linked_entities` 不為空時，系統應自動根據這些 entity 的內容，生成一段給執行者看的 context 摘要，填入 `context_summary`。摘要應說明「這個任務跟哪些知識節點有關、各節點目前狀態如何」。
- **Acceptance Criteria**：
  - Given 建任務時帶了 linked_entities，When 任務建立完成，Then `context_summary` 被自動填入，內容提到各 entity 的 name 和 summary
  - Given 建任務時沒有帶 linked_entities，When 任務建立完成，Then `context_summary` 保持空白（不強制）
  - Given 建任務時手動填了 context_summary，When 任務建立完成，Then 保留手動填入的值，不被覆蓋

### P1（應該有）

#### assignee 支援 Role entity 連結
- **描述**：任務的 `assignee` 除了現有的自由字串外，新增 `assignee_role_id` 欄位，可選地指向一個 `type: role` 的 entity。取任務時，若有 assignee_role_id，一併展開該 role entity 的內容（name、summary、who 標籤說明的職責範圍）。
- **Acceptance Criteria**：
  - Given 建任務時帶了 assignee_role_id，When 執行者呼叫 get task，Then 回傳中有 `assignee_role` 物件含 name、summary
  - Given 沒有 assignee_role_id，When 執行者呼叫 get task，Then assignee_role 欄位不出現（向後相容）
  - Given assignee_role_id 指向不存在的 entity，When 執行者呼叫 get task，Then 不中斷，回傳 task 時 assignee_role 為 null

#### 取任務時帶出 linked_blindspot 摘要
- **描述**：若任務有 `linked_blindspot`，取任務時一併展開 blindspot 的 description 和 severity。
- **Acceptance Criteria**：
  - Given task 有 linked_blindspot，When get task，Then 回傳中有 `blindspot_detail` 含 description、severity、suggested_action

### P2（可以有）

#### 執行者 pull 任務時按 role 過濾
- **描述**：執行者呼叫 `search(collection="tasks", assignee_role="PM")` 時，能找到指定給 PM 角色的所有任務。
- **Acceptance Criteria**：
  - Given 有 3 個 task 的 assignee_role 是 "PM"，When search tasks by assignee_role="PM"，Then 回傳這 3 個 task

## 明確不包含

- 不做 assignee 的用戶帳號系統（Phase 1+）
- 不做 role entity 的自動建立或推薦
- 不做 context_summary 的 LLM 生成（Phase 0 用模板拼接即可）
- 不改變現有任務的 status 流程

## 技術約束（給 Architect 參考）

- **向後相容**：現有 task schema 不能 breaking change，assignee_role_id 是新增欄位
- **效能**：get task 展開 entity 最多 N 次 Firestore read，不能讓 latency 超過 1 秒
- **context_summary 生成**：Phase 0 用模板拼接（不需要 LLM call），格式：「任務關聯節點：[名稱] — [摘要]」

## 開放問題

1. `linked_entities` 展開的深度：只展 entity 本身，還是也帶出它的 relationships？
2. `assignee_role_id` 的 Role entity 由誰建？需要預先在 ontology 裡有 role entity 才能用。
3. context_summary 自動生成後，建任務的 agent 應不應該被告知「系統自動填了這段」？
