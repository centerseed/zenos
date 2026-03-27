---
type: SKILL
id: l2-knowledge-governance
status: Draft
ontology_entity: l2-governance
created: 2026-03-27
updated: 2026-03-27
---

# L2 知識節點治理操作手冊

**定位：** Agent 在建立、升級、或審查 L2 entity 時的逐步執行指南——把 SPEC 的規則翻譯為可執行的動作序列。

---

## 適用場景

載入這個 skill，當你需要：

- 判斷一個候選概念是否應該寫入 L2（capture 流程）
- 把一個 `draft` L2 升為 `confirmed`（confirm 流程）
- 審查現有 L2 是否應該轉為 `stale` 或降級（review 流程）
- 撰寫或修改 L2 的 `impacts` 欄位（impacts 撰寫）
- 判斷新輸入應分流到哪一層（分層路由）

---

## 權威來源

本 skill 的所有規則均源自：

- `docs/specs/SPEC-l2-entity-redefinition.md`（版本 1.2，2026-03-27）

若本 skill 與上述 spec 有衝突，以 spec 為準，並在 Completion Report 中標記。

---

## 三問判斷 Checklist

**目的：** 逐問過濾，判斷候選概念是否值得進入 L2。

**使用方式：** 三問全部回答 Yes，才進入下一步（寫入 L2 draft）。任何一問回答 No，停在這裡，依後續指示分流。

---

### 問一：公司共識？

> 任何角色（工程師、行銷、老闆）都聽得懂這個概念，且在不同情境下都指向同一件事。

**測試方法：** 把概念名稱念給假想的行銷同事聽，她會說「我知道那是什麼」嗎？

| 回答 | 動作 |
|------|------|
| Yes | 繼續問二 |
| No | 這是技術細節或單一角色術語。走分層路由決策樹，通常落入 L3 document 或 sources |

**正例：** 「計費模型」、「訓練閉環機制」、「品質保證機制」

**反例：** 「API Rate Limiting middleware」、「staging 環境設定」、「FastAPI 服務架構」

---

### 問二：改了有下游影響（impacts）？

> 這個概念改變時，有其他概念必須跟著看。

**測試方法：** 完成這個句子：「如果 [概念] 改了，那麼 [至少一個其他概念] 的 [具體部分] 必須跟著更新。」

能填完嗎？

| 回答 | 動作 |
|------|------|
| Yes，能填完 | 繼續問三 |
| No，或填出來很模糊 | 這個概念不具備傳播價值。不適合做 L2。考慮降為 L3 document 或掛在既有 L2 底下的 sources |

**正例：**「ACWR 安全機制改了閾值 → 訓練計畫生成邏輯的週負荷上限計算必須更新」

**反例：**「這個改了會影響系統」（太模糊，不能過關）

---

### 問三：跨時間存活？

> 這個概念不會隨著某個 sprint 或某個文件結束而消失。

**測試方法：** 六個月後這個概念還會存在嗎？它有 V1、V2、V3 的延續性嗎？

| 回答 | 動作 |
|------|------|
| Yes | 三問全過，進入 L2 draft 寫入流程 |
| No | 這是一次性活動或短期工作。走分層路由決策樹，通常開 Task 或掛 sources |

**正例：** 「品質保證機制」（每個版本都有）、「訓練方法論體系」

**反例：** 「Q1 上線準備清單」、「本次 sprint 的修復計畫」

---

## 分層路由決策樹

**目的：** 快速判斷新輸入應該落在哪一層，避免路由錯誤。

**執行方式：** 從頂部開始，依序問每個問題，第一個 Yes 就停下來照該層流程走。

```
新輸入進來
│
├── 是治理規則、邊界定義、或跨角色共識？
│   Yes → 進 L2 候選，走三問 + impacts gate
│   No  ↓
│
├── 是正式文件（SPEC / ADR / TD / PB / SC / REF）？
│   Yes → 進 L3 document governance（見 SPEC-doc-governance）
│   No  ↓
│
├── 是可指派、可驗收的具體工作？
│   Yes → 開 Task（見 SPEC-task-governance）
│   No  ↓
│
└── 以上都否
    → 掛 entity.sources，不升級成節點
```

### 禁止路由

- 不能因為「內容重要」就直接升 L2；必須先過三問 + impacts gate。
- 不能用 Task 取代 SPEC / ADR / 文件治理。
- 不能把低價值草稿、會議記錄建成 document entity；應掛 sources。

### 路由衝突處理順序

1. 先依內容本質分層（L2 / L3 / Task / sources）
2. 再套用該層的權威 spec
3. 本 skill 不覆寫他層規範；衝突時以各層權威 spec 為準

---

## impacts 撰寫指南

**核心原則：** L2 的核心價值不是 summary（它是什麼），而是 impacts（改了它，誰要跟著動）。

### 格式要求

每條 impacts 必須能回答：「**A 的什麼改了 → B 的什麼要跟著看**」

```
[來源 L2] impacts [目標 L2 或概念]
具體：[來源] 的 [哪個面向] 改了 → [目標] 的 [哪個面向] 要跟著更新
```

### 正確範例

```
ACWR 安全機制 impacts 訓練計畫生成邏輯
具體：ACWR 閾值改了 → 訓練計畫生成時的週負荷上限計算要更新

訓練方法論體系 impacts 行銷話術
具體：新增或修改訓練方法論 → 行銷宣傳的「科學訓練」說法要同步更新

計費模型 impacts 合約條款
具體：計費週期或定價方式改了 → 合約範本中的計費條款段落要重新審閱
```

### 錯誤範例（不合格）

```
A impacts B                          ← 沒有具體傳播路徑，不合格
系統 A 改了可能影響系統 B             ← 「可能」不算具體
計費模型改了會影響整個公司             ← 範圍太廣，不算具體 impacts
```

### impacts 數量

- Server 硬性底線：≥1 條具體 impacts
- 如果想不出任何一條具體 impacts：不要寫入 L2，重新走分層路由決策樹
- 每條必須含 `→` 符號；Server 的 `_is_concrete_impacts_description()` 會驗證

---

## 生命週期操作

### 狀態圖

```
          三問 + impacts 全過
  draft ──────────────────────→ confirmed
    ↑                              │
    │  三問不再成立                 │  impacts 過時 / review 發現退化
    │                             ↓
    └──────────────────────── stale
              重新補齊 impacts
```

### 操作一：建立 L2 draft

**前提：** 三問全過。

**MCP 呼叫：**

```
mcp__zenos__write({
  "level": "L2",
  "name": "<概念名稱>",
  "summary": "<跨角色都能讀懂的說明>",
  "status": "draft",           // 永遠從 draft 開始，Server 強制
  "relationships": [
    {
      "type": "impacts",
      "target": "<目標概念名稱>",
      "description": "<A 的什麼改了 → B 的什麼要跟著看>"
    }
  ]
})
```

**注意：**

- `status` 不需要手動設 `draft`，Server 會強制覆寫為 `draft`；但明確寫出來是好習慣
- `summary` 要用工程師和行銷都能讀懂的語言，不要用技術術語
- `relationships` 中的 impacts 描述必須包含 `→`

---

### 操作二：draft → confirmed（impacts gate）

**前提：** 三問全過 + summary 跨角色可讀 + ≥1 條具體 impacts 已寫入。

**MCP 呼叫：**

```
mcp__zenos__confirm({
  "entity_id": "<entity 的 id>",
  "reason": "<為什麼這個概念通過了三問和 impacts gate>"
})
```

**Server 此時會自動驗證：**

- relationships 中是否存在 ≥1 條 `impacts` type 的關係
- impacts 描述是否含有 `→`（具體傳播路徑）

**如果 confirm 失敗：**

1. 先確認 impacts 已寫入 entity（用 `mcp__zenos__get` 檢查）
2. 確認 impacts 描述含 `→` 且有具體的「A 的什麼 → B 的什麼」結構
3. 修正後重試 confirm

---

### 操作三：confirmed → stale（觸發條件）

**何時應該把 confirmed L2 標為 stale：**

| 觸發事件 | 說明 |
|---------|------|
| impacts 目標已被刪除或大幅重構 | 原本 impacts 的對象不再存在或已改名 |
| 概念本身已發生重大語意變化 | summary 描述的概念和現實已不符 |
| 治理 review 發現 impacts 失效 | 季度 review 時發現傳播路徑斷掉 |
| analyze 工具偵測到 impacts 斷鏈 | 自動偵測，人工確認後執行 |

**MCP 呼叫：**

```
mcp__zenos__write({
  "entity_id": "<entity 的 id>",
  "status": "stale",
  "stale_reason": "<說明為什麼 impacts 過時或失效>"
})
```

**stale 後的動作：**

1. 通知（Phase 0 人工、Phase 1+ 自動）掛載此 L2 的所有 L3 documents 與 tasks
2. 評估是否能補齊新的有效 impacts（能 → 走 stale → confirmed 路徑）
3. 若三問本身不再成立 → 降回 draft 等待重新評估或降級

---

### 操作四：stale → confirmed（修復路徑）

**前提：** 重新補齊有效 impacts 路徑。

步驟：

1. 用 `mcp__zenos__write` 更新 relationships，加入新的有效 impacts
2. 用 `mcp__zenos__confirm` 重新觸發 impacts gate

---

### 操作五：降級（移出骨架層）

**何時降級：**

- 長期（依公司定義的時間，預設建議 30 天）無法通過三問
- 補不出任何具體 impacts
- 概念本身只是技術實作細節

**降級路徑：**

```
1. 確定降級目標（L3 document / sources）
2. 用 mcp__zenos__write 更新原 L2 的掛載關係
3. 把原 L2 的 L3 掛載重新分配到正確的上位 L2
4. 從骨架層移除原 entity（或標記為 archived）
```

---

## 客製化邊界速查

### 不可動：Server 硬性底線

| 規則 | 執行機制 |
|------|---------|
| L2 新建一律為 `draft` | write 時 Server 強制覆寫 status |
| `draft → confirmed` 必須走 `confirm` | write 路徑禁止直接升級 |
| `confirm` 要求 ≥1 條具體 impacts | confirm 時 Server 檢查 relationships |
| impacts 描述必須含 `→` | `_is_concrete_impacts_description()` 驗證 |
| `force=true` 必須附 `manual_override_reason` | write 時 Server 驗證 |
| confirmed entity 只能 merge，不能覆寫 | write 時 Server 阻擋覆寫 |

這六條是所有公司共用的底線，不可透過 ontology 資料或 skill 設定繞過。

---

### 可調整：透過 ontology protocol 客製

| 面向 | 最低底線 | 可客製的方向 |
|------|---------|------------|
| impacts 數量 | ≥1 條 | 可要求 ≥3 條、或跨部門 impacts |
| 三問寬嚴度 | 無 Server 驗證，靠 LLM + 人工 | 可在 protocol 定義公司專屬「共識」門檻 |
| summary 格式 | 無驗證 | 可要求雙語、字數範圍、必含角色影響段落 |
| review 週期 | 無自動計時，建議每季 | 可定義每月 / 每版本 / 每次重大重構後 |
| 降級時機 | 無硬定義 | 可定義「draft 超過 30 天未 confirm → 標記降級」|
| 排除 / 強制清單 | 無 | 可在 protocol 定義本公司不視為 L2 的概念類型 |

**客製方式：** 把公司專屬規則寫進 ontology protocol entity，Agent 在 capture/write 時自動讀取並遵循。

---

## 常見錯誤

### 錯誤一：把技術模組直接升 L2

**症狀：** L2 summary 像在描述技術元件功能，只有工程師看得懂。

**正確做法：** 問一必須回答 Yes（行銷也能懂）。技術模組通常落入 L3 document 或 sources。若技術模組底下有多個跨角色共識概念，應拆成多個獨立 L2。

**範例：**
- 錯誤：「FastAPI 服務架構」做成 L2
- 正確：拆出「服務可用性保證」（跨角色共識）做 L2，「FastAPI 服務架構」掛 L3 sources

---

### 錯誤二：impacts 太模糊

**症狀：** impacts 描述是「A 影響 B」或「A 改了可能有影響」，沒有具體路徑。

**正確做法：** 每條 impacts 必須能填入「A 的 [什麼面向] 改了 → B 的 [什麼面向] 要跟著看」。填不出來就是太模糊，Server 的 `_is_concrete_impacts_description()` 也會擋下來。

---

### 錯誤三：跳過三問直接寫入

**症狀：** 看到重要概念就直接 write，沒有先走三問。

**後果：** 骨架層堆滿沒有 impacts 的點，知識地圖退化成文件索引。

**正確做法：** 三問全過才走 write。三問中任何一問 No，先走分層路由決策樹。

---

### 錯誤四：一個技術模組 = 一個 L2

**症狀：** L2 entity 的名字是模組名（如「訓練計畫系統」），底下塞了所有相關知識。

**正確做法：** 問「這個概念的各個部分能獨立改嗎？」能獨立改的拆成獨立 L2，互相用 `impacts` 連結。

**範例：**
- 錯誤：「訓練計畫系統」= 一個 L2
- 正確：拆成「訓練閉環機制」、「ACWR 安全機制」、「訓練方法論體系」三個 L2，各自有獨立 impacts

---

### 錯誤五：只有 draft，永遠不走 confirm

**症狀：** L2 建立後就停在 draft，從未走 confirm 流程。

**後果：** 骨架層全是未驗證的候選概念，沒有可信的知識。

**正確做法：** 寫完 impacts 後立刻走 `mcp__zenos__confirm`，讓 Server 驗證 impacts gate。

---

### 錯誤六：impacts 變動不雙向檢查

**症狀：** 修改了 B，但沒有回頭看「哪些 L2 impacts 了 B」，讓 A 的 impacts 描述過時。

**正確做法：** 任何 L2 被修改或刪除時，必須同時：
1. 更新該 L2 自身的 impacts
2. 搜尋哪些其他 L2 的 impacts 指向這個 L2，通知那些 L2 的 owner 檢查

---

## 快速參考

### MCP 呼叫一覽

| 動作 | MCP Tool | 關鍵參數 |
|------|----------|---------|
| 建立 L2 draft | `mcp__zenos__write` | level=L2, status=draft, relationships（含 impacts） |
| 升為 confirmed | `mcp__zenos__confirm` | entity_id, reason |
| 標為 stale | `mcp__zenos__write` | entity_id, status=stale, stale_reason |
| 查詢現有 L2 | `mcp__zenos__get` | entity_id |
| 搜尋相關概念 | `mcp__zenos__search` | query |
| 分析 impacts 斷鏈 | `mcp__zenos__analyze` | target=entity_id |
| 強制覆寫（需理由） | `mcp__zenos__write` | force=true, manual_override_reason |

### impacts 快速判斷

- 含 `→`？Yes → 格式合格
- 能說出「A 的什麼」和「B 的什麼」？Yes → 語意合格
- 上面兩個都 Yes → 可以 confirm
