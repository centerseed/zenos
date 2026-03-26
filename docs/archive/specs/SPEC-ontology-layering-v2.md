# SPEC: Ontology Layering v2

**狀態：** Proposal Candidate
**版本：** 1.0（2026-03-26）
**作者：** PM
**相關 Spec：** `docs/specs/SPEC-l2-entity-redefinition.md`
**審核定位：** 候選提案。此文件提出新的 layering full model 與 progressive layering 策略，供 review 使用；未審核通過前，不覆蓋 `docs/spec.md` 的現行定義。

**Reviewer 指引：**
- 如果你要看「現在有效的規格」，請先看 `docs/spec.md`
- 如果你要看「本次建議怎麼改分層」，看這份文件
- 審核時請聚焦：哪些內容應升格進 canonical，哪些只適合作為後續演化方向

---

## 背景與問題

ZenOS 目前已經重新定義 L2：L2 不是技術模組摘要，而是「公司共識概念」。

這個方向是對的，但 dogfooding 與規模推演暴露了新的結構問題：

1. 實際公司知識不只有 product / module / document / task 這幾種
2. 高頻更新（進度、素材、任務、會議）和低頻概念（L2）混在一起時，更新落點會變得模糊
3. 當文件數上升到數百甚至上千份時，如果缺少中介層，L2 會被錯當成文件桶或狀態桶
4. 使用者在面對一個「事情的更新」時，難以判斷該改 L2 還是改 L3

根本原因不是 L2 定義錯，而是**整體 ontology 分層還不夠完整**。

ZenOS 需要一個更清楚的 layering model，把：

- 原始來源
- 公司全景
- 共識概念
- 穩定知識物件
- 高頻變更與執行
- 歷史歸檔

切成不同層，避免一切都往 L2 擠。

---

## 核心目標

這份 spec 的目標是定義 ZenOS 的新分層模型，讓系統能同時承載：

- 少量但高價值的全景骨架
- 中量且可治理的知識物件
- 大量且高頻的執行與更新記錄
- 可追溯但不污染現況的歷史資料

一句話總結：

**L2 負責「公司長期要治理什麼」，L3 負責「公司知道了什麼」，L4 負責「公司最近做了什麼」。**

但這個模型是 **full model**，不是要求所有導入客戶第一天就把全部層級獨立落地。

ZenOS 需要同時滿足兩件事：

1. 小公司導入時足夠輕，不因分層過細而變成過度設計
2. 當導入成熟、知識與更新量持續累積時，可以有系統地從簡單分層升級到完整分層

因此，本 spec 同時定義：

- **完整分層模型（conceptual full model）**
- **漸進式折疊策略（progressive layering）**

---

## 新分層定義

### L0 — Source Layer

**定位：** 原始來源層

**回答的問題：**
- 原始內容在哪裡？
- 這份知識的來源系統是什麼？

**內容範例：**
- GitHub 檔案
- Google Drive 文件
- Notion 頁面
- 對話紀錄
- 會議錄音轉錄
- 圖片、投影片、素材檔
- 外部連結與參考資料

**特性：**
- 不直接承載治理語意
- 保留 `uri / adapter / metadata`
- 允許 transient 或無結構內容存在

**原則：**
L0 是來源，不是知識本體。

---

### L1 — Product / Business Domain Layer

**定位：** 公司或產品級全景層

**回答的問題：**
- 公司在做哪些產品、產品線、事業領域？
- 哪些是最上層的知識版圖？

**內容範例：**
- ZenOS
- Paceriz
- 顧問服務線
- Growth / Operations / Platform 這類公司級 domain

**特性：**
- 數量少
- 穩定
- 給老闆、PM、外部 agent 看全景入口

**原則：**
L1 是導航骨架，不承載細節。

---

### L2 — Company Consensus Concept Layer

**定位：** 公司共識概念層

**回答的問題：**
- 哪些概念是跨角色都承認存在的？
- 哪些概念改了，其他概念或角色必須跟著看？

**內容範例：**
- 計費模型
- 訓練閉環機制
- ACWR 安全機制
- 風控策略
- 分銷模式
- 客戶分群策略

**特性：**
- 稀疏
- 可被跨角色理解
- 必須具備至少一條具體 `impacts`
- 應跨時間存活，不應隨單一 sprint 消失

**原則：**
L2 承載的是「長期要治理的概念」，不是文件集合，不是任務集合，也不是進度欄位。

---

### L3 — Knowledge Object Layer

**定位：** 穩定知識物件層

**回答的問題：**
- 支撐 L1/L2 的知識單位有哪些？
- 哪些內容值得被長期查詢、重用、引用？

**內容範例：**
- `document`
- `decision`
- `protocol`
- `goal`
- `role`
- `project`
- `asset`
- `evidence`

**各類型說明：**

- `document`
  規格、指南、研究報告、設計文件、操作手冊

- `decision`
  ADR、重大取捨、政策決定、策略定案

- `protocol`
  給特定角色或 agent 消費的人可讀 view

- `goal`
  中長期目標、治理目標、戰略目標

- `role`
  角色知識入口，例如行銷、產品、客服、銷售

- `project`
  有起訖、有負責人、有交付物的知識容器

- `asset`
  可重用素材，例如 FAQ、pitch deck、sales script、landing page copy

- `evidence`
  用研摘要、實驗結果、數據分析、客訴統計、績效佐證

**特性：**
- 數量中到大
- 可以被確認、搜尋、重用
- 通常掛在某個 L1/L2 之下，作為支撐材料或可治理物件

**原則：**
L3 承載的是「穩定且可引用的知識」，不是高頻即時狀態。

---

### L4 — Change / Execution Layer

**定位：** 變更與執行層

**回答的問題：**
- 最近發生了什麼？
- 有哪些事情正在做、剛做完、被卡住、需要追蹤？

**內容範例：**
- `task`
- `progress_update`
- `meeting_note`
- `campaign_run`
- `incident`
- `delivery_record`
- `review_record`
- `change_record`

**各類型說明：**

- `task`
  知識驅動的行動項目

- `progress_update`
  進度更新、里程碑變動、狀態摘要

- `meeting_note`
  會議決議、待辦、後續追蹤點

- `campaign_run`
  某次行銷或銷售活動的執行紀錄

- `incident`
  問題、事故、異常事件

- `delivery_record`
  上線、交付、發布、對客交件

- `review_record`
  審查、驗收、回饋紀錄

- `change_record`
  對任一 L1/L2/L3 物件的變更記錄，作為變更入口

**特性：**
- 高頻
- 數量大
- 容易過時
- 需要 lifecycle 與歸檔機制

**原則：**
L4 承載的是「發生過什麼與正在發生什麼」，不是公司的長期骨架。

---

### L5 — Archive / History Layer

**定位：** 歷史與歸檔層

**回答的問題：**
- 哪些東西已完成、已過時、僅供追溯？
- 現況為什麼會變成這樣？

**內容範例：**
- 已完成任務
- 舊版本 spec
- 舊素材
- 舊 campaign run
- 已失效決策
- 一次性記錄

**特性：**
- 持續增長
- 低頻查閱
- 對追溯有價值，但不該干擾現況判讀

**原則：**
L5 的存在是為了保留記憶，不是為了參與日常治理。

---

## 層與層之間的責任分工

| 層級 | 核心角色 | 回答的問題 |
|------|----------|-----------|
| L0 | Source | 原始內容在哪裡？ |
| L1 | Panorama | 我們在做什麼？ |
| L2 | Governance | 我們長期治理什麼概念？ |
| L3 | Knowledge | 我們知道了什麼？ |
| L4 | Execution | 我們最近做了什麼？ |
| L5 | History | 過去發生了什麼？ |

---

## Progressive Layering

### 核心原則

ZenOS 的分層不是一次性開滿，而是：

**概念先完整，落地先折疊。**

也就是說：

- 架構設計時，先承認完整模型最終會走到 `L0-L5`
- 初期導入時，只啟用當下必要的層
- 隨著文件量、更新量、使用角色、治理需求上升，再逐步拆層

這讓 ZenOS 避免兩種錯誤：

1. 一開始就 full-stack layering，對小公司過度設計
2. 一開始只做極簡模型，之後規模一上來整個 schema 與治理邏輯重做

---

### 三種運行模式

#### Mode A — Initial / Small-company Mode

**適用情境：**

- 文件量小於約 `200`
- 活躍產品少於 `3`
- 核心決策者少於 `5`
- 主要知識仍可被少數人心智掌握
- 導入目的以「先讓 ontology 有用」為主

**實際啟用層：**

- `L1`
- `L2`
- `L3/4 folded layer`
- `archive status`

**落地方式：**

- 保留產品全景（L1）
- 保留共識概念（L2）
- 將穩定知識與高頻更新先合併到同一個 operational layer
- 歷史資料先用 `archived` 狀態處理，不強制獨立成 L5

**一句話：**

初期導入時，ZenOS 實際上以三層運作就夠：

1. 全景層
2. 共識概念層
3. 其餘一切的工作層

---

#### Mode B — Growing / Folded-to-Split Mode

**適用情境：**

- 文件與行動項目持續累積
- 同一層裡開始同時塞滿 spec、素材、任務、進度、會議紀錄
- 使用者開始常常問「這個到底是知識還是進度？」
- agent 或 dashboard 消費場景開始分化

**實際啟用層：**

- `L1`
- `L2`
- `L3`
- `L4`
- `archive status`

**落地方式：**

- 將 folded 的工作層拆成：
  - 穩定知識物件層（L3）
  - 高頻變更與執行層（L4）
- L5 仍可先用 status + retention policy 處理

**一句話：**

當「知識」和「執行」開始互相污染時，就該拆開 L3 / L4。

---

#### Mode C — Mature / Full Layering Mode

**適用情境：**

- 文件數進入數百到上千
- 多產品、多角色、多 agent 同時消費 ontology
- 追溯、稽核、歸檔與 lifecycle 管理成為真需求
- 現況判讀與歷史追溯需要明確分離

**實際啟用層：**

- `L0`
- `L1`
- `L2`
- `L3`
- `L4`
- `L5`

**落地方式：**

- source layer 被視為正式治理對象的一部分
- archive/history 被獨立處理，而不是只靠狀態欄位
- retention、review、query、permission 都按層演化

---

## Folded Layer 設計

### 初期為什麼可以折疊

對小公司來說，真正不能混的是：

- `L2` 與下層

但 `L3` 與 `L4` 在初期可以暫時共存於同一個 physical layer。

原因是小公司初期常見情況：

- 文件量還不大
- 任務量還不大
- 同一批人同時消費知識與進度
- 最主要的需求是「不要讓 L2 被污染」

因此初期不必一開始就獨立：

- `decision`
- `asset`
- `evidence`
- `progress_update`
- `meeting_note`
- `change_record`

它們可以先共存在同一層，只靠 `type` 與 `status` 區分。

---

### Folded Layer 的硬規則

即使在 folded mode，下列規則仍必須成立：

1. `L2` 不可直接承接任務、進度、一次性事件
2. 所有更新都必須以某種下層物件存在，不可只改 L2 summary
3. folded layer 內每筆資料都必須帶 `type`
4. folded layer 內每筆資料都必須可連回 L1/L2
5. folded layer 內每筆資料都必須有 lifecycle 狀態

換句話說：

**初期可以折層，但不能失去型別、關聯與生命週期。**

---

## 升層觸發條件

ZenOS 不應靠感覺決定什麼時候拆層，而應有明確 trigger。

### 從 Initial Mode 升級到 Growing Mode

符合下列任一組訊號時，應考慮將 folded layer 拆成 L3 / L4：

1. 同一個層內的高頻更新量明顯高於穩定知識量
2. 使用者經常無法判斷某項內容是「知識」還是「進度」
3. dashboard / agent 開始需要分開看：
   - 穩定知識
   - 執行現況
4. folded layer 中超過一定比例的內容屬於一次性更新
5. 任務、會議、進度類物件開始快速膨脹

可作為初版治理門檻的量化訊號：

- 文件總量超過 `200`
- 活躍 task / update 類物件超過 `100`
- 單一 L2 下同時掛載大量 document 與 task/update，導致閱讀混亂

---

### 從 Growing Mode 升級到 Mature Mode

符合下列任一組訊號時，應考慮正式獨立 L5 與更完整的 L0 管理：

1. 已完成資料大量累積，影響現況檢索
2. 使用者常常需要追溯「當時為何如此決策」
3. 稽核、權限、歷史查詢成為正式需求
4. agent 在查詢時需要明確隔離 current vs historical

可作為初版治理門檻的量化訊號：

- 文件總量超過 `500`
- archived / historical 物件超過 current 物件的顯著比例
- 多角色消費同一知識庫，且查詢需求明顯分為 current / history

---

## 更新落點規則

### 最上位原則

不要直接問：

> 這個更新要放 L2 還是 L3？

要改問兩件事：

1. 這次更新改變的是「概念本身」還是「概念的當前狀態 / 證據 / 執行」？
2. 這次更新本身屬於哪一種物件？

---

### 什麼情況更新 L2

只有當變更影響下列任一項時，才允許更新 L2：

1. 概念定義改變
2. 概念邊界改變
3. 概念與其他概念的 `impacts` 傳播路徑改變
4. 概念的生命週期地位改變
   - 新升成 L2
   - 從 L2 降級
   - 與其他 L2 合併
   - 從一個 L2 拆成多個 L2

**判斷句：**

如果半年後新同事加入，公司仍然需要知道這個「更新後的概念版本」，這個變更才有資格回寫 L2。

---

### 什麼情況進 L3

下列內容原則上進 L3，而不是 L2：

1. 新 spec、文件、研究、報告
2. ADR、正式決策
3. 可重用素材
4. 實驗結果與證據
5. 角色導向 view
6. 長期目標、專案知識容器

**判斷句：**

如果這個東西未來會被查詢、引用、重用，但不是公司的共識概念本身，它應該進 L3。

---

### 什麼情況進 L4

下列內容原則上進 L4：

1. 任務建立與進度變化
2. 某次會議的新決議
3. 某次 campaign 的執行結果
4. 某次發布或交付
5. 某個 incident 與修復歷程
6. 任一物件的 change log

**判斷句：**

如果這個更新在描述「最近發生了什麼」，而不是「公司長期治理什麼」，它應該進 L4。

---

### 什麼情況進 L5

當 L3/L4 的內容符合下列條件時，應進入 L5：

1. 已完成且不再活躍
2. 已失效但需追溯
3. 對現在沒有操作價值，但保有歷史價值

---

## Change-first 原則

為了降低更新落點模糊，ZenOS 採用以下治理原則：

**任何更新，先落一份 `change_record` 到 L4，再判斷是否需要反映到 L2/L3。**

流程：

1. 新變更發生
2. 先建立 `change_record`
3. 連結到受影響的 L1/L2/L3 物件
4. 判斷是否改變了概念定義或 impacts
5. 若有，回寫 L2
6. 若沒有，只更新 L3/L4，不動 L2

這條規則的目的，是讓 L2 從「吸收所有更新的地方」變成「只有在概念真的被改變時才被更新的穩定骨架」。

---

## Architecture Reservation

### 核心要求

ZenOS 初期可以只跑三層，但**初期的 schema、tool、service 設計必須預留未來拆層能力**。

也就是說：

- runtime 可以先簡化
- type system 不能太早寫死

---

### 初期建立時應預留的結構

#### 1. 每筆下層資料都要有 `type`

即使一開始所有 L3/L4 內容都存在同一個 collection / repository，也必須保留可擴張的 type system。

最低要求：

- `document`
- `decision`
- `protocol`
- `goal`
- `role`
- `project`
- `task`
- `progress_update`
- `meeting_note`
- `asset`
- `evidence`
- `change_record`

初期可以只實作其中部分 type，但 schema 不應假設世界上永遠只有 `document + task`。

#### 2. 每筆下層資料都要有 `layer_intent`

即使 physical storage 折疊，也應能標示它在 conceptual model 中屬於：

- `knowledge`
- `execution`
- `history`

這個欄位可以讓未來拆層時不需要重新判斷全部舊資料。

#### 3. 每筆下層資料都要能連回 L1/L2

最低要求：

- `linked_entity_ids`
- 或更一般化的 `ontology_refs`

未來不論拆成 L3 或 L4，這條關聯都不能消失。

#### 4. 每筆下層資料都要有 lifecycle

至少要保留：

- `draft`
- `active/current`
- `stale`
- `archived`

這是未來拆出 L5 的必要前提。

#### 5. Query 介面要先支援按 type / status / parent scope 過濾

即使初期資料量不大，也要避免 API 被寫死成：

- 全抓所有資料
- 無 type filter
- 無 status filter
- 無 scope filter

否則之後拆層時，API 與 dashboard 會一起重寫。

---

### Physical Layer 與 Conceptual Layer 分離

ZenOS 應明確接受一件事：

**conceptual layer 不等於 physical collection。**

例子：

- conceptual 上有 `L3` 與 `L4`
- 初期 physical 上仍可共存在同一個 collection
- 只要 type、intent、relation、lifecycle 都保留，之後就能平滑拆開

這是 ZenOS 避免過度設計與避免未來重做的關鍵。

---

## 對現有 ZenOS 的直接影響

### 1. L2 定義不推翻，反而被保留

現有 `SPEC-l2-entity-redefinition` 的方向保留不變：

- L2 仍然是公司共識概念
- L2 仍然必須有具體 impacts
- 無 impacts 的點不應存在於 L2

這份新 spec 做的不是否定 L2，而是補齊其上下游分層。

### 2. L3 不能再等同於單純 document

ZenOS 現有的 `document / goal / role / project` 只是 L3 的第一版。
未來 L3 應擴成完整的 knowledge object layer。

### 3. L4 需要被獨立承認

Action Layer 不應只被視為任務系統。
它應升級為更一般化的 `Change / Execution Layer`，任務只是其中一種。

### 4. Archive 不能只是 status

隨著規模增長，歷史沉積不該只靠 `archived` 狀態混在現役集合裡。
ZenOS 需要更明確的歷史治理觀。

### 5. 初期產品模式應以三層為預設

ZenOS 的導入預設應是：

1. `L1` 全景層
2. `L2` 共識概念層
3. `Folded L3/L4` 工作層

而不是一開始就要求客戶理解完整 `L0-L5`。

完整 layering 是系統的上位架構，不是初期 onboarding 的操作負擔。

---

## 規模推演

對於文件數約 1,000 份的公司，較合理的量級大致如下：

- `L1`：3-10
- `L2`：15-40
- `L3`：200-800
- `L4`：500-5000
- `L5`：持續增長

這表示：

- L2 不應線性跟著文件數變大
- 文件量增加時，主要增長應發生在 L3/L4/L5
- 如果 L2 開始承接大量文件與進度，代表分層已經失真

對應到導入路徑：

- 小公司初期：三層就夠
- 知識與更新開始堆積：拆 L3 / L4
- 歷史沉積開始干擾現況：拆 L5

ZenOS 的演化不應該是「重做 ontology」，而是「逐步把原本折疊的層打開」。

---

## Acceptance Criteria

1. 使用者面對一個更新時，可以先判斷它是概念變更、知識新增，還是執行事件
2. L2 不再被當作文件桶、任務桶或進度桶
3. L3 被明確定義為 knowledge object layer，而不只是一堆 documents
4. L4 被明確定義為 change/execution layer，而不只是一個 tasks collection
5. 任何高頻更新都可以先落 `change_record`，再決定是否反映到 L2
6. 一家有數百到上千份文件的公司，L2 仍可保持稀疏與可讀
7. 小公司初期可只用三層運行，不造成過度設計
8. 系統在初期建立時已預留未來拆分 L3 / L4 / L5 的架構

---

## 明確不包含

- 這份 spec 不直接定義資料庫 schema 欄位
- 這份 spec 不直接決定 MCP tool 介面修改方式
- 這份 spec 不直接決定 dashboard 的 UI 呈現
- 這份 spec 不推翻既有 L2 定義，只補齊整體 layering

---

## 後續工作

這份 spec 確認後，應衍生至少三份後續文件：

1. `Schema Spec`
   定義 L3/L4 新 type 與欄位

2. `Governance Spec`
   定義 update routing、change_record 流程、archive 規則

3. `Consumption Spec`
   定義 dashboard / MCP / agent 如何按層消費知識
