---
type: SPEC
id: SPEC-l2-entity-redefinition
status: Approved
ontology_entity: l2-governance
created: 2026-03-25
updated: 2026-03-27
---

# Feature Spec: L2 Entity 重新定義——從技術模組到公司共識概念

**版本：** 1.2（2026-03-27）
**作者：** PM
**相關 ADR：** ADR-002（Knowledge Ontology North Star）

---

## 背景與問題

### 發現問題

Dogfooding ZenOS（用 ZenOS 管 ZenOS 自己的知識）時，發現 ontology 退化成文件索引。

**症狀：**
- L2 entity 的 summary 像在描述技術模組的功能，不像在描述公司共識
- 跨角色消費者（行銷 agent、新人 agent）讀完 L2，仍然不知道「這對我有什麼影響」
- Relationship 幾乎只有 `contains`，幾乎沒有 `impacts`——知識地圖是靜態的，沒有傳播路徑

**根本原因：**

現有 capture 演算法是「逐檔掃描→逐檔產出」。一次處理一個文件，輸出的是該文件的技術摘要。這天生產出工程師語言的 L2（因為文件通常是工程師寫的），且無法識別跨文件的共識概念。

---

## 重新定義：什麼是 L2 Entity

### 核心定義

**L2 Entity = 公司共識概念。**

「公司共識概念」的意思是：這個概念如果被改變，不同角色（工程師、行銷、老闆）都會受到影響，且大家都點頭說「對，這個概念我知道」。

### 三問判斷標準（全三問過才是 L2）

**1. 公司共識？**
任何角色（工程師、行銷、老闆）都聽得懂這個概念，並且在不同情境下都指向同一件事。
✓ 「訓練計畫系統」——工程師說 API 設計，行銷說功能賣點，老闆說核心產品
✗ 「API Rate Limiting middleware」——只有工程師在乎

**2. 改了有下游影響（impacts）？**
這個概念改變時，有其他概念必須跟著看。
✓ 「ACWR 安全機制」改了閾值 → 訓練計畫生成邏輯要跟著改、行銷要更新安全保證說法
✗ 「staging 環境設定」改了 → 只影響開發流程，不影響其他概念

**3. 跨時間存活？**
這個概念不會隨著某個 sprint 或某個文件結束而消失。
✓ 「品質保證機制」——V1、V2、V3 都有，概念一直在
✗ 「Q1 上線準備清單」——做完就結束了

### 硬規則：沒有 impacts，就不應該存在於 L2

L2 不是「比較大的主題」，而是「值得被治理傳播追蹤的概念」。

因此 ZenOS 對 L2 的硬規則是：

- 每個 L2 entity 必須至少有 1 條具體 `impacts` relationship
- 這條 `impacts` 必須能說清楚「A 改了什麼 -> B 的什麼要跟著看」
- 如果一個候選概念說不出任何具體 impacts，代表它不是公司共識概念，而是以下其中一種：
  - L3 文件或來源材料
  - 某個 L2 底下的實作細節
  - 粒度切錯、需要重新拆分或合併
  - 一次性活動，不該進骨架層

結論很直接：**沒有 impacts 的點，不值得作為 L2 存在。**

---

## 治理收斂（2026-03-26）

L2 不再是「只放一個三層架構定義節點」的容器。隨著 L3 文件治理與 Task 治理成形，L2 應升級為可治理、可演化的**治理概念層**。

本 spec 僅負責 L2 的升降級閘與分層路由，不重寫 Action Layer 或 L3 文件治理細節。避免重複規範，採以下權責切分：

| 治理面向 | 權威文件 | 本 spec 的責任 |
|---------|----------|---------------|
| L2 概念升級 / 降級 | `SPEC-l2-entity-redefinition` | 定義三問 + impacts gate |
| L3 文件生命週期與 sync contract | `SPEC-doc-governance` | 只定義何時路由到 L3 |
| Task 開票品質 / 驗收 / supersede | `SPEC-task-governance` | 只定義何時路由到 Task |

若條文衝突，處理順序必須是：
1. 先依內容本質分層（L2 / L3 / Task / sources）
2. 再套用該層的權威 spec
3. 本 spec 不得覆寫他層規範

### 常見錯誤判斷

| 判斷為 L2 | 問題 | 正確分類 |
|-----------|------|----------|
| 「FastAPI 服務架構」 | 技術實作細節，非共識概念 | L3 document / sources |
| 「使用者認證邏輯」 | 只有工程師關心 | L3 document |
| 「Stripe 付款整合」 | 是技術手段，不是公司共識 | L3 sources 掛在「計費模型」L2 下 |
| 「計費模型」 | 老闆/行銷/工程師都關心，改了有大量下游影響 | ✓ L2 |

### 一個技術模組 → 多個 L2 Entity

舊的錯誤做法：「訓練計畫系統」= 一個 L2
新的正確做法：「訓練計畫系統」可以拆成多個獨立 L2：
- 「訓練閉環機制」（資料怎麼流進來、課表怎麼調整）
- 「ACWR 安全機制」（如何防止過度訓練）
- 「訓練方法論體系」（不同目標對應什麼訓練策略）

**切割原則：可獨立改變。** 如果 A 改了不一定要改 B，它們就是兩個 L2。

---

## 新輸入資料的分層路由規則（L2 / L3 / Task / Sources）

### 一次判斷表

| 進來的內容 | 問題本質 | 應落層級 |
|-----------|----------|----------|
| 新治理原則、邊界定義、跨角色共識 | 定義「公司怎麼做判斷」且有下游 impacts | L2 entity |
| 正式文件（SPEC/ADR/TD/PB/SC/REF） | 需要文件生命週期與 metadata 治理 | L3 document entity |
| 可指派、可驗收的具體工作 | 需要 owner + acceptance criteria + status flow | Task collection |
| 一次性草稿、低價值參考、會議記錄 | 需要留引用但不值得成節點 | entity.sources |

### 關鍵判斷序

1. 先問「是否是治理規則或跨角色共識」：是 -> 進 L2 候選，走三問 + impacts gate。  
2. 否則問「是否是正式文件」：是 -> 進 L3 document governance 流程。  
3. 否則問「是否可指派且可驗收」：是 -> 開 task。  
4. 以上都否 -> 掛 sources，不升級成節點。

### 禁止路徑

- 不能因為內容重要就直接升 L2；先過「三問 + impacts」。
- 不能用 task 取代 spec / ADR / document governance。
- 不能把任何文件都建成 document entity；低價值材料應掛 sources。

---

## 核心價值：impacts 關聯

### 為什麼 impacts 比 summary 更重要

L2 entity 的核心價值不是它的 summary（描述它是什麼），而是它的 **impacts 關聯**（改了它，誰要跟著動）。

一個沒有 impacts 的 L2 只是一個文件摘要。一個有具體 impacts 路徑的 L2 是真正的知識代理。

### L2 的最低完整度

一個 L2 entity 要被視為「完成」，至少要同時滿足：

1. 三問全部通過
2. summary 能被跨角色理解
3. 至少一條具體 `impacts`

只要缺第 3 項，就不能算完成的 L2，只能：

- 降為 draft
- 降級為 L3/document source
- 或退回重新切割粒度

### impacts 的正確寫法

**錯誤：** `A impacts B`（太模糊，AI 不知道怎麼傳播）

**正確：** 每條 impacts 要能回答「A 的什麼改了 → B 的什麼要跟著看」

範例：
```
ACWR 安全機制 impacts 訓練計畫生成邏輯
具體：ACWR 閾值改了 → 訓練計畫生成時的週負荷上限計算要更新

訓練方法論體系 impacts 行銷話術
具體：新增或修改訓練方法論 → 行銷宣傳的「科學訓練」說法要同步更新
```

---

## L2 生命週期（Lifecycle State Machine）

### 狀態定義

| 狀態 | 意義 | 進入條件 |
|------|------|----------|
| `draft` | 候選概念，尚未通過完整治理門檻 | 新建立時的唯一合法初始狀態 |
| `confirmed` | 通過三問 + impacts gate，正式納入骨架層 | 三問全過 + summary 跨角色可讀 + ≥1 條具體 impacts |
| `stale` | 概念仍存在但 impacts 路徑已過時或失效 | 下游 impacts 目標已不存在、已被重構、或超過治理 review 週期未驗證 |

### 合法轉換路徑

```
          三問 + impacts 全過
  draft ──────────────────────→ confirmed
    ↑                              │
    │  impacts 補不出來             │  impacts 過時 / review 發現退化
    │  或三問不再成立               ↓
    └──────────────────────── stale
              重新補齊 impacts
              stale → confirmed
```

- `draft → confirmed`：三問全過 + 至少 1 條具體 impacts + summary 跨角色可讀。由 capture 流程或人工 review 觸發。
- `confirmed → stale`：定期治理 review 發現 impacts 目標已不存在或已大幅重構；或 analyze 偵測到 impacts 斷鏈。
- `stale → confirmed`：重新補齊有效 impacts 路徑後，經 review 確認可回到 confirmed。
- `stale → draft`：三問本身不再成立（概念已不是公司共識），降回 draft 等待重新評估或降級。
- `draft → 降級/刪除`：長期無法通過三問或補出 impacts，應降級為 L3 document / sources，或從骨架層移除。

### 終態

L2 沒有硬性終態（不像文件有 Archived）。概念可以在 `confirmed ↔ stale` 之間循環演化。若概念徹底失去存在價值，應降級或移除，而不是留在任何狀態。

### 治理 review 週期

- 所有 `confirmed` 狀態的 L2 entity，應至少每季（或每次重大 ontology 重構時）檢查 impacts 是否仍有效。
- review 由 analyze 工具輔助偵測，人工確認最終判定。
- review 未執行不會自動觸發狀態變更，但累積未 review 的 entity 數量應作為治理健康度指標。

---

## L2 反饋路徑（Feedback Triggers）

### 觸發事件與反饋動作

| 觸發事件 | 反饋對象 | 反饋動作 | 自動/人工 |
|---------|---------|---------|----------|
| L2 的 impacts 目標被修改或刪除 | 本 L2 entity | 標記為待 review，可能轉 stale | Phase 0 人工；Phase 1+ analyze 自動偵測 |
| L2 從 draft 升為 confirmed | 下游 L3 documents 掛載此 L2 的 | 檢查是否需更新 ontology_entity 對應 | 人工確認 |
| L2 從 confirmed 轉為 stale | 掛載此 L2 的所有 L3 documents 與 tasks | 通知相關文件與任務 owner：上游概念已過時，需評估影響 | Phase 0 人工；Phase 1+ 自動通知 |
| L2 被降級（移出骨架層） | 原掛載的 L3 documents | 重新掛載到正確的上位 L2，或降級為 sources | 人工處理 |
| L2 的 summary 或 impacts 被實質修改 | 引用此 L2 的下游 specs 與 tasks | 檢查引用是否仍正確 | Phase 0 人工；Phase 2 自動 lint |
| 新 L2 從既有 L2 拆分而出 | 原 L2 的所有下游關聯 | 重新分配 L3 掛載與 impacts 路徑 | 人工處理 |

### 反饋完整性規則

1. **impacts 變動必須雙向檢查**：A impacts B，若 B 被修改或刪除，A 必須被通知；若 A 被修改，B 必須被通知。
2. **L2 狀態變更不得靜默發生**：任何 confirmed → stale 或降級動作，必須有可追溯的觸發原因與處理紀錄。
3. **反饋未完成不得視為治理完成**：與 Task 治理的知識反饋閉環一致——L2 的狀態變更若影響下游，下游未處理完就不算治理閉環完成。

### 與傳播契約的關係

本節定義的是 L2 entity 自身的反饋路徑。當 L2 治理**規則本身**被修改（例如三問標準調整、impacts 最低數量改變），則適用憲法（`docs/spec.md`）第四節的傳播契約，必須同步更新 MCP tools、skills、analyze 等執行層。

---

## L2 治理客製化邊界

L2 治理規則由三層機制執行，每層的可客製化程度不同。本節明確劃分**硬性底線**（Server 強制）與**軟性標準**（用戶可調整），讓不同公司在共用同一套 MCP 服務的前提下，仍能定義符合自身需求的 L2 治理規則。

### 不可客製化：Server 硬性底線

以下規則由 MCP Server 程式碼強制執行，是所有公司共用的治理底線，不可透過 ontology 資料或 skill 設定繞過：

| 硬性規則 | 執行方式 | 設計理由 |
|---------|---------|---------|
| L2 新建一律為 `draft` | write 時強制覆寫 status | 確保所有 L2 都經過治理門檻審查 |
| `draft → active` 必須走 `confirm` | write 路徑禁止直接升級 | 強制人工確認，防止自動化跳過治理 |
| `confirm` 要求 ≥1 條具體 impacts | confirm 時檢查 relationship | 沒有 impacts 的 L2 不具備骨架層價值 |
| impacts 描述必須含傳播路徑（`→`） | `_is_concrete_impacts_description()` | 防止模糊 impacts（如「A impacts B」無具體路徑） |
| `force=true` 必須附 `manual_override_reason` | write 時驗證 | 確保繞過治理門檻有可追溯的理由 |
| confirmed entity 保護（merge-only） | write 時阻擋覆寫 | 防止已確認的知識被意外覆寫 |

### 可客製化：用戶可調整的軟性標準

以下規則的最低門檻由 Server 保障，但**超過門檻的品質標準**可由用戶透過 ontology protocol 或公司 spec 自行定義。Agent 在 capture/write 時會讀取 ontology context，自然遵循公司特有規則。

#### ① 三問的寬嚴度

Server 不驗證三問——它只驗證 impacts 存在。三問的判斷完全依賴 LLM + 人工判斷，天然隨公司 ontology 內容而調整。

- **公司共識門檻**：5 人公司與 500 人公司的「共識」定義天然不同
- **跨時間存活定義**：年度計畫型公司 vs 快速迭代型新創，「存活」的時間尺度不同
- **客製方式**：寫進 ontology protocol，描述本公司的三問判斷標準

#### ② impacts 的深度與廣度

Server 硬性要求 ≥1 條。用戶可自訂更高標準：

- 「每個 L2 至少 3 條 impacts」
- 「impacts 必須跨部門（不能只影響同一角色）」
- 「impacts 必須描述雙向影響」
- **客製方式**：寫進 ontology protocol；超過 1 的部分由人工 review 執行

#### ③ summary 的語言和格式

Server 完全不驗證 summary 品質。用戶可自訂：

- 語言要求（繁中/英文/雙語）
- 字數限制（如 50-200 字）
- 結構要求（如必須包含「對各角色的影響」段落）
- **客製方式**：寫進 ontology protocol，agent 在 capture 時自動遵循

#### ④ review 週期

本 spec 建議「每季」，但 Server 沒有計時器。用戶可自訂：

- 每月 / 每季 / 每次重大版本後
- 特定 entity 類型有不同週期
- **目前限制**：沒有自動提醒機制，靠人工紀律或外部排程

#### ⑤ 降級判斷時機

「draft 長期未 confirm 應降級」中的「長期」無硬定義。用戶可自訂：

- 「draft 超過 30 天未 confirm → 標記需降級 review」
- 「stale 超過一季未修復 → 降為 L3」
- **目前限制**：沒有自動執行，靠人工

#### ⑥ 公司專屬排除清單

每間公司的知識結構不同。用戶可透過 protocol 定義：

- 「以下類型概念在本公司不視為 L2：一次性專案、外部工具名稱、...」
- 「以下領域強制為 L2：法規遵循相關概念、核心產品功能」
- **客製方式**：寫進 ontology protocol，agent 在 capture 路由時自動參考

### 客製化光譜總覽

```
不可動（Server 硬性底線）        可調整（用戶透過 ontology 客製化）
├── impacts ≥1                  ├── impacts 深度/廣度標準
├── draft 唯一初始態             ├── 三問寬嚴度
├── confirm 才能升級             ├── summary 格式/語言
├── impacts 必須含 →             ├── review 週期
├── force 需要 reason            ├── 降級時機判斷
└── confirmed 保護               └── 公司專屬排除/強制清單
```

**設計原則**：Server 硬編碼的是「最低治理底線」——確保任何 L2 都有 impacts、都經過 confirm 流程。超過底線的品質標準，交由用戶透過 ontology protocol 自行定義，讓同一套 MCP 服務能服務不同治理需求的公司。

---

## 演算法要求：全局統合模式

### 現有演算法（禁止繼續用）

```
for each document:
    analyze(document) → produce L2 entity
```

**問題：** 文件是局部視角，無法識別跨文件的共識概念。

### 新演算法要求

```
step 1: 讀取所有文件 → 形成全景理解
step 2: 從全景中辨識公司共識概念（三問過濾）
step 3: 切割為獨立的 L2 entities（可獨立改變原則）
step 4: 推斷 impacts 關聯（具體的傳播路徑）
step 5: 若說不出 impacts，退回 Step 2/3，代表這個點不值得存在於 L2
step 6: 用任何人都懂的語言寫 summary
```

**關鍵約束：** Step 1 必須在 Step 2 之前。不能邊讀邊切，必須先有全景再切割。

### Prompt 設計要點（給 Architect）

1. **先建全景，再切概念：** Prompt 第一步讓 LLM 讀完所有輸入並用自然語言描述公司全貌，第二步才切 L2
2. **三問做篩選閘：** 每個候選 L2 必須過三問，不過就丟棄或降為 L3
3. **獨立性切割：** 提示 LLM 問「這個和那個能獨立改嗎？能 → 拆開」
4. **跨角色語言：** 提示 LLM「用工程師和行銷都能看懂的語言寫 summary」
5. **impacts 路徑推斷：** 提示 LLM 「改了 X，哪些其他概念的哪些部分要跟著看？」
6. **無 impacts 則淘汰：** 如果候選概念無法產出具體 impacts，就不要升成 L2

---

## Acceptance Criteria（PM 驗收標準）

1. **L2 是公司共識概念：** 任何角色讀完 L2 summary 都點頭，不需要技術背景
2. **模組可拆：** Paceriz 的「訓練計畫系統」module 能被拆成至少 3 個獨立的 L2 概念
3. **summary 通用：** 每個 L2 entity 的 summary 不需要技術背景就能理解
4. **impacts 具體：** 每條 impacts relationship 能具體說出「A 改了什麼→B 的什麼要跟著看」
5. **無 impacts 不升 L2：** 任一候選概念若沒有至少 1 條具體 impacts，不能被寫成 L2
6. **行銷 agent 可用：** 行銷 agent 只用 MCP query L2，30 秒內能回答「能宣傳什麼功能」
7. **演算法全局：** capture 先讀完所有文件再切概念，不是逐檔掃描

---

## 明確不包含

- L1（product 層）不受影響，定義不變
- 不在本 spec 內重寫 L3 文件治理與 Task 治理細節（細節以各自 spec 為準）
- 本 spec 只定義 L2 如何承接上述治理軸的邊界與路由規則
- 現有已確認的 L2 entity 若缺 impacts，應在治理 review 中補齊；補不出來就應降級或重切
- 不定義 Task 的欄位級規則（`linked_entities`、`acceptance_criteria`、`result`、duplicate/supersede 等）

---

## 相關文件

- `docs/spec.md` Part 4（Ontology 技術路線）、Part 7.2（Entity 分層模型）
- `docs/reference/REF-glossary.md`（L2 定義速查）
- `docs/designs/TD-l2-entity-redesign.md`（Architect 技術交接）
- `docs/specs/SPEC-doc-governance.md`（L3 文件治理）
- `docs/specs/SPEC-task-governance.md`（Task 治理）
