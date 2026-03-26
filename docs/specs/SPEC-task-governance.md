---
type: SPEC
id: SPEC-task-governance
status: Draft
ontology_entity: action-layer
created: 2026-03-26
updated: 2026-03-26
---

# Feature Spec: ZenOS Task Governance

## 背景與動機

ZenOS 的 Action Layer 已經有資料模型、MCP function、狀態流與 priority recommendation。

但目前「怎麼開一張好票」仍缺少治理規範，造成幾個實際問題：

- agent 開票風格不一致，有的像 bug report，有的像設計 memo，有的只是一句提醒
- task 粒度不一致，有的過大像 epic，有的過小像 checklist item
- `linked_entities` 掛法不一致，有的完全沒掛，有的亂掛一串，導致 context summary 品質不穩
- 有些本來應先寫 spec / ADR / blindspot 的問題，被直接開成 implementation task
- backlog 容易出現重複票、孤兒票、無法驗收票

L2 治理已經定義「公司共識概念怎麼長成 stable ontology」；L3 文件治理也開始成形；但 Task Layer 目前仍停留在「有架構、缺規範」。

本 spec 的目標，是把任務管理從資料結構提升成治理規範，讓 agent 與人都能用一致方式開票、派工、驗收。

---

## 目標

1. 定義什麼情況應該開 task，什麼情況不應該。
2. 定義 task 的標準粒度，避免過大、過小或不可驗收。
3. 定義 agent 建票時的最小必填品質，涵蓋 `title`、`description`、`acceptance_criteria`、`linked_entities`、`priority`、`status`、`owner/assignee`、`result` 共八個欄位。
4. 讓 task 與 ontology 的連結穩定可用，而不是形式上有欄位、實際上沒有治理價值。
5. 讓 `task` MCP function 成為一致的治理入口，而不是各 agent 各自發明 ticket style。

---

## 非目標

- 不在這份 spec 裡重新定義 Kanban 狀態機本身。
- 不處理 sprint、工時、story point、velocity 等專案管理制度。
- 不要求 task 取代 spec、ADR、blindspot、document entity。
- 不處理 agent 內部私有 subtask 或個人 TODO 列表。

---

## Task 的治理定位

ZenOS 三層目前可簡化理解為：

- L2 治理：公司共識概念的穩定骨架
- L3 治理：文件與來源路徑、metadata、ontology linkage 的穩定治理
- Task 治理：從知識導出行動，並把行動結果再反饋回知識層

因此 task 不是一般待辦事項，而是：

- 有知識脈絡的行動單位
- 可被指派與驗收的工作邊界
- 驗證 ontology 是否真的能支撐行動的最小單位

Task 開得太鬆，Action Layer 會退化成雜項待辦清單；
Task 開得太硬，agent 會繞過 ZenOS 回到外部工具或私有筆記。

### 與 L2 / L3 的權責邊界（防重複治理）

本 spec 是 Action Layer 的權威規範，不重寫 L2 或 L3 規則。三層分工如下：

| 治理面向 | 權威文件 | 本 spec 行為 |
|---------|----------|--------------|
| L2 概念升級 / impacts gate | `SPEC-l2-entity-redefinition` | 僅引用，不重定義 |
| 文件分類 / frontmatter / supersede / archive | `SPEC-doc-governance` | 僅引用，不重定義 |
| Task 建票品質 / 粒度 / 去重 / 驗收 | `SPEC-task-governance` | 完整定義 |

任何「新治理原則」或「文件生命週期規則」若還在定義 what/why/boundary，必須先落到 SPEC/ADR/TD；Task 只承接可指派、可驗收的執行邊界。

---

## 什麼時候應該開 Task

應開 task 的情境：

- 已經有明確後續動作需要被指派、追蹤、驗收
- 某個 blindspot 需要形成具體處置
- 某份 spec / design / doc 已有明確 implementation follow-up
- 某個治理缺口需要人或 agent 實際修補
- 某項工作完成與否，會影響其他任務、文件或知識節點

不應直接開 task 的情境：

- 問題還停留在「要不要這樣做」的決策階段
- 內容本質上是新規格、新決策、新治理原則，應先寫 spec / ADR
- 內容只是知識沉澱，沒有具體 owner / outcome / verification boundary
- 內容只是執行者自己的短期 checklist，不需要跨人協作或驗收

判斷原則：

- 如果內容需要「誰來做、做到哪裡算完成」，開 task
- 如果內容需要「先定義規則或方向」，先寫 spec / ADR
- 如果內容是「系統看到一個缺口」，先記 blindspot，再視情況轉成 task

---

## Task 粒度規則

一張 task 必須同時滿足以下三點：

1. **單一主要 outcome**
   同一張 task 應對應一個主要產出或狀態改變，不應混多個彼此可獨立驗收的結果。

2. **單一主要 owner**
   雖然可以協作，但 task 應有一個主要 assignee 或可明確指派的責任落點。

3. **單一驗收邊界**
   驗收者應能用 2-5 條 acceptance criteria 判斷是否完成，而不是再拆解整個專案。

過大的 task：

- 橫跨 spec、implementation、migration、QA 全流程
- 同時包含多個子系統或多種 deliverable
- acceptance criteria 寫成 roadmap

過小的 task：

- 只是某張 task 的內部一步
- 只是「查一下」「看一下」「想一下」且沒有穩定產出
- 完成後不需要任何人驗收

實務準則：

- 需要不同人接手時，拆票
- 需要不同驗收邊界時，拆票
- 需要不同 ontology context 才講得清楚時，拆票

---

## Task 與 Spec / Blindspot / Document 的分工

| 類型 | 用途 | 何時先做 |
|------|------|----------|
| `SPEC` / `ADR` / `TD` | 定義規則、方向、設計 | 還在定義 what / why / boundary 時 |
| `Blindspot` | 記錄缺口、風險、未知問題 | 還沒有明確 owner / 執行方案時 |
| `Task` | 指派可驗收的行動 | 已知道要做什麼、誰應接手、怎麼算完成 |
| `Document update` | 沉澱或修正文檔本身 | 本質只是更新知識而非派工時 |

轉換關係：

- blindspot 可以產生 task
- spec / design 可以產生 implementation task
- task 完成可能反寫 document / blindspot / entity 狀態

但 task 不應拿來取代 spec 或 blindspot 本身。

---

## 建票最小規範

### 1. title

必須：

- 動詞開頭
- 單一行動邊界
- 不寫成會議紀錄或抽象主題

好例子：

- `修復 documents.update 的 merge 語意`
- `設計文件治理 sync API`
- `補上 task.update 對 linked_entities 的覆寫支援`

差例子：

- `documents 問題`
- `Barry 說這個怪怪的`
- `整理一下治理`

### 2. description

至少應包含三件事：

- 背景：為什麼需要這張票
- 問題：現在缺什麼或壞在哪
- 期望結果：完成後應解決什麼

不要把 description 寫成 acceptance criteria 的重複版本，也不要只寫一句模糊摘要。

### 3. acceptance_criteria

應為 2-5 條可觀察、可驗收的完成條件。

每條都應該是：

- 外顯結果
- 可測試或可確認
- 與該 task 的主要 outcome 直接相關

不要寫成：

- 純過程性步驟
- roadmap 願景
- 模糊願望句

### 4. linked_entities

`linked_entities` 不是裝飾欄位。它決定：

- task 的 ontology context
- priority recommendation 的輸入
- context summary 的品質
- 後續 search / routing / governance review 的可用性

因此 agent 建票時應遵循以下規則：

1. 至少掛 **1 個主要治理節點**，最多通常 **3 個**。
2. 第一優先掛「最直接受影響的概念」，不是隨便掛產品根節點湊數。
3. 若工作同時涉及產品層與子模組層，可掛：
   - 一個產品 / 上位模組
   - 一個直接受影響模組
   - 一個治理或介面節點（如文件治理、MCP 介面設計）
4. 不要把所有看過的節點都塞進去。
5. 若目前找不到穩定對應節點，應先承認 ontology gap，而不是亂掛。此時應在 description 中標注 `[Ontology Gap: 缺少 XXX 對應節點]`，若問題較嚴重可另記 blindspot；linked_entities 維持最少掛點或暫不填，不要為了填滿而亂掛。

推薦上限：

- 1 個：單點修補
- 2 個：主要功能 + 治理/依賴面
- 3 個：跨層但仍可清楚說明的工作
- 4 個以上：通常表示粒度太大或理解未收斂

### 5. priority

若沒有強理由，優先讓 server 推薦。

`task(action="create")` 未傳 `priority` 時，應由 server recommendation 寫入最終 priority。
caller 不應預設會是固定值（如永遠 `medium`）。

只有在以下情境建議 caller 明示覆蓋：

- 已知商業時程不可延誤
- 已知外部依賴要求更高或更低優先度
- 需要刻意保留某張票在 backlog，不讓規則引擎升級

### 6. status

建票時只應使用：

- `backlog`
- `todo`

Agent 不應在 create 時直接假設：

- `in_progress`
- `review`
- `blocked`
- `done`

除非是工具在合法規則下自動推導。

### 7. owner / assignee

`assignee` 在 schema 中可為選填，但治理上不得沒有責任落點。

建票時必須滿足其一：

- 直接填入 `assignee`
- 未能立即指派時，在 `description` 明確記錄預期 owner（人名或角色）與指派條件

禁止建立「owner 未定且無指派條件」的 task。

### 8. result（完成輸出落點）

進入 `review` 前，必須有可供驗收的完成輸出。

- 若流程有 `result` 欄位：在 `result` 明確記錄產出、影響範圍、知識反饋
- 若當前工具流尚未穩定使用 `result`：在 `description` 末尾追加 `Result:` 區塊，並附關聯文件或變更連結

驗收者必須能在 task 上直接找到這份完成輸出，否則不應通過。

---

## Agent 建票流程

所有 agent 開票前，必須遵循這個順序：

1. 先查是否已有同類 open task
   用 `search(collection="tasks", status="backlog,todo,in_progress,review,blocked")` 避免重複票（排除 cancelled / done）。

2. 確認這件事是 task，不是 spec / blindspot / doc update

3. 選 1-3 個最合適的 `linked_entities`
   不確定時，寧可少掛，不要亂掛。

4. 寫出單一 outcome 的 title

5. 補齊能被驗收的 description 與 acceptance criteria

6. 再呼叫 `task(action="create")`

標準心法：

- 先去重
- 再定類型
- 再選 context
- 最後才建票

---

## 推薦的 linked_entities 掛法

### 類型 A：單點實作修補

掛：

- 直接受影響模組
- 如有必要，再加上一個直接相關的治理或介面節點

不要為了「看起來比較完整」而附帶產品根節點。

例：

- 修 MCP task update bug
  - `MCP 介面設計`
  - `Action Layer` / `Task dispatch` 類直接受影響模組（若 ontology 已有）

### 類型 B：治理規則或治理流程

掛：

- 產品根節點
- 對應治理模組
- 如涉及接口，再加 MCP 模組

例：

- 規範文件治理 sync
  - `ZenOS`
  - `文件治理`
  - `MCP 介面設計`

Type A / B 的判斷原則：

- 主要驗收在「程式或資料行為修補」時，歸類 Type A
- 主要驗收在「治理規則、流程、文件契約變更」時，歸類 Type B
- 若同時成立且難以單票驗收，必須拆成兩張票

### 類型 C：跨層架構設計

掛：

- 上位產品 / 系統
- 最直接的 app layer / module
- 一個主要被 impacts 的治理或界面節點

不要同時塞一整串平級模組。

例：

- 設計 L2 語意推導 → Task 優先度推薦演算法
  - `ZenOS`（上位產品）
  - `Action Layer`（最直接受影響的 module）
  - `語意治理`（主要被 impacts 的治理節點）

---

## 不一致與反模式

以下都是需要避免的 task 反模式：

### 1. 孤兒票

- 沒有 `linked_entities`
- description 太短，無法知道上下文
- acceptance criteria 缺失

### 2. 假連結票

- `linked_entities` 只是為了填欄位而掛
- 掛一堆 entity 但 description 根本沒提到它們

### 3. 混合型票

- 同一張票同時要求寫 spec、做實作、跑 migration、補測試、做驗收

### 4. 提醒型票

- 內容只是「記得之後看這個」
- 沒有 owner、沒有邊界、沒有完成條件

### 5. 重複票

- 同一問題開了多張 backlog
- 舊票沒取消、沒標 superseded，就直接再開一張

---

## 重複票與 supersede 規則

當發現既有 task 已涵蓋同一主要 outcome：

- 優先更新既有 task，而不是重開

當新票是更正確的收斂版本：

- 建新票
- 將舊票標記 `cancelled`
- 在 description 末尾附註 `[Superseded by: TASK-XXX]`
- 若後續 MCP schema 支援正式欄位，應改用 `superseded_by`

禁止：

- 讓多張 open task 代表同一件事，只差 wording

---

## Governance 檢查清單

建立 task 前，至少過這 8 題：

1. 這件事真的是 task，不是 spec / blindspot / doc update 嗎？
2. 這張票只有一個主要 outcome 嗎？
3. 這張票有清楚 owner / assignee（或明確指派條件）嗎？
4. 這張票能用 2-5 條 acceptance criteria 驗收嗎？
5. `linked_entities` 真的是最相關的 1-3 個節點嗎？
6. title 是否動詞開頭且描述單一行動？
7. description 是否交代背景、問題、期望結果？
8. backlog 裡確認沒有重複票嗎？

若有 2 題以上答案為否，不應直接建票。

---

## 去重規則

`search(collection="tasks", status="backlog,todo,in_progress,review,blocked")` 不是形式上的前置步驟，應至少檢查以下三個面向（搜尋範圍排除 cancelled / done）：

1. `title` 是否描述同一主要 outcome
2. `description` 是否在處理同一問題邊界
3. `linked_entities` 是否指向同一組核心治理節點

實務判斷順序：

- 先用主要名詞或模組名搜 title 關鍵字
- 再用核心問題詞搜 description
- 最後比對候選票的 `linked_entities` 與 acceptance criteria

可視為重複票的最小條件：

- 主要 outcome 相同
- 核心 ontology context 高度重疊
- 驗收邊界相近

若只是同一大主題下的不同驗收邊界，不算重複票。

---

## Task 完成後的知識反饋

Task 治理不是單向派工。以下情境完成後，應觸發知識層反饋：

- 修正文檔或 source path 的 task
  - 應同步更新對應 document entity 或文件治理狀態
- 處理 blindspot 的 task
  - 驗收通過後應關閉或更新對應 blindspot
- 補齊規格 / 規則 / 介面設計的 task
  - 應將產出沉澱回受治理文件，而不是只把 task 標 done
- 修補 ontology / MCP 行為的 task
  - 若改變了規則或 contract，應更新對應 spec / reference

責任分工：

- 執行者負責在 `result` 或 `description` 的 `Result:` 區塊中說明產出與受影響知識
- 驗收者負責確認這些知識反饋已完成，才應通過 task
- server 後續可逐步自動化部分反寫，但在機制完整前，不得假設 `done` 自動等於知識已同步

因此，若 task 的完成會改變知識層，acceptance criteria 應至少有一條明確要求相關文檔、blindspot 或 entity 狀態已同步。

若 task 屬於不改變知識層的純行動類（如訪談客戶、確認外部 quota），知識反饋可簡化為：在 result 或 description 的 `Result:` 區塊記錄結論摘要，無需強制更新文件或 entity。

---

## 對 MCP 與未來實作的要求

若要讓 task 治理真正成立，後續實作應支援：

- `task(update)` 能可靠更新 `linked_entities`
- server 可提供更好的 duplicate detection
- search / list task 能支援更清楚的 ontology-context 篩選
- 後續可考慮增加 task governance lint 或 analyze check

這些屬於後續實作，不影響本規範先行成立。

---

## 完成定義

以下條件都可被客觀檢查時，才可視為 Task 治理規範已建立：

1. spec surface 納管完成
   - `REF-active-spec-surface` 已列入 `SPEC-task-governance`，且狀態為 active。

2. 開票品質可被實例驗證
   - 至少一張 2026-03-26 之後新建的 task（提供 task ID）符合：
     - title 為動詞開頭且單一 outcome
     - description 含背景/問題/期望結果
     - `linked_entities` 為 1-3 個且無湊數掛法
     - `acceptance_criteria` 為 2-5 條可觀察條件

3. 邊界規則可被 reviewer 直接判斷
   - reviewer 能依本 spec 的 8 題 checklist，判定至少一張候選項目應開 task，且至少一張候選項目不應直接開 task（應先走 spec / blindspot / doc update）。
   - 「候選項目」來源必須明示：至少 1 項來自 `search(collection="tasks", status="backlog,todo")` 的現有任務候選，且至少 1 項來自當次需求中的非 task 候選（spec / blindspot / doc update）。

4. action -> knowledge 反饋有落地證據
   - 至少一張完成任務在 `result` 或關聯文件中明確記錄知識反饋結果（document / blindspot / entity 至少其一），且驗收者據此通過。
