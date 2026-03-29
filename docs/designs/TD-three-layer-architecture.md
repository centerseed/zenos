---
type: TD
id: TD-three-layer-architecture
status: Approved
ontology_entity: TBD
created: 2026-03-19
updated: 2026-03-27
---

# Technical Design: 三層架構（資料層 / Agent 層 / 展示層）

> 從 `docs/spec.md` Part 3 搬出。


### Layer 1 — 資料層（Firestore）

**原則：** 最穩定、最少變動、AI 可直接讀寫

**公版 Schema（五大 Collection）**

```
contacts/
  - contactId
  - name
  - aliases[]           # 「王大明」「王先生」「大明」同一人
  - type                # lead / partner / customer
  - phone / email
  - sourceText
  - confirmedByUser
  - createdAt

finances/
  - financeId
  - type                # income / expense
  - amount
  - category
  - relatedOrderId      # ref to orders（如適用）
  - dueDate
  - paidAt              # null = 未收付款
  - status              # pending / overdue / paid
  - sourceText
  - confirmedByUser
  - createdAt

projects/
  - projectId
  - name
  - status              # planning / active / on_hold / completed
  - roadmap             # 方向描述
  - sourceText
  - confirmedByUser
  - createdAt

projects/{projectId}/tasks/
  - taskId
  - title
  - assignee
  - status              # todo / in_progress / done
  - dueDate
  - sourceText
  - confirmedByUser

campaigns/
  - campaignId
  - name
  - type                # leads / assets
  - status              # draft / active / completed
  - targetAudience
  - sourceText
  - confirmedByUser
  - createdAt

orders/
  - orderId
  - contactId           # ref to contacts
  - status              # pending / confirmed / in_production / shipped / closed
  - dueDate
  - paymentTerms
  - sourceText          # 原始輸入，保留供 debug
  - sourceChannel       # line / email / form
  - confirmedByUser     # false = draft，true = 正式寫入
  - createdAt
  - createdBy

orders/{orderId}/items/
  - itemId
  - productId           # ref to products
  - productName
  - quantity
  - unitPrice           # null = 待補
  - status

orders/{orderId}/payments/
  - paymentId
  - amount
  - dueDate
  - paidAt              # null = 未收款
  - status              # pending / overdue / paid

products/
  - productId
  - name
  - aliases[]
  - safetyStock
  - currentStock
  - unit
```

**所有 Collection 共用原則：**
- `sourceText` 必存，保留原始輸入供 debug 和重新解析
- `confirmedByUser` 控制 draft / 正式狀態，防止 AI 誤判直接污染資料
- `aliases[]` 處理同義詞對應問題，由 AI 在寫入前比對
- null 優於猜測，缺漏欄位留 null 並觸發補充提醒

**客製部分（20~30%，依產業調整）**

| 產業 | 額外 Collection |
|------|----------------|
| 製造業 | `workOrders` / `bom` |
| 服務業 | `contracts` / `milestones` |
| 貿易商 | `customs` / `exchangeRates` |

---

### Layer 2 — Agent 層

**原則：** 中介人與資料庫之間，承擔所有翻譯與主動邏輯

Agent 有四種角色，共用同一個 Firestore：

#### 2a. 輸入 Agent（被動）
自然語言 → 結構化資料寫入 Firestore

```
流程：
1. 解析自然語言，抽出實體（客戶、品項、數量、交期）
2. 實體對應：查 Firestore 比對 name + aliases
3. 缺漏偵測：有標準答案的自動帶入，沒有的留 null
4. 產生確認訊息回給員工
5. 員工確認後正式寫入（confirmedByUser: true）
```

#### 2b. 查詢 Agent（被動）
任何角色用自然語言問，AI 撈對應資料回答

```
範例：
「王大明的訂單出了嗎？」→ 查 orders，filter by contactId
「這個月還有哪些款沒收？」→ 查 finances，filter status = overdue
「A零件還剩多少？」→ 查 products.currentStock
「行銷活動的 leads 有多少？」→ 查 campaigns
「開發進度到哪了？」→ 查 projects + tasks
```

#### 2c. 監控 Agent（主動）
定期掃描或 onWrite 觸發，主動推播異常

**兩種觸發機制：**

| 類型 | 機制 | 範例 |
|------|------|------|
| 事件驅動 | Firestore onWrite + Cloud Functions | 訂單確認 → 立刻通知採購 |
| 狀態監控 | 排程觸發（每日） | 每早檢查逾期帳款 |

**公版預設通知規則（預設開啟）：**

```
庫存類    currentStock < safetyStock + 有未完成訂單
訂單類    dueDate 剩 3 天，status != shipped
          訂單確認後 24hr，status 仍 pending
財務類    finances.dueDate 已過，paidAt = null
採購類    採購單發出後 X 天未收到供應商回覆
專案類    task.dueDate 已過，status != done
```

#### 2d. 簽核 Agent（主動）
條件觸發，發起決策對話，等待回應後推進狀態

```
觸發條件範例（自然語言定義，存在 Firestore）：
「採購金額超過 10 萬要我點頭」
「報價單出去之前讓我看一眼」

流程：
1. 偵測到觸發條件
2. 發訊息給指定角色，附上完整資訊
3. 等待回應（好 / 不行 / 修改）
4. 更新 Firestore 狀態，通知發起人繼續或退回
```

**通知路由設計：**

不用設定規則，改用「責任描述」：
```
採購：「我負責所有跟料件有關的事」
業務：「我負責我自己的客戶訂單」
老闆：「我要看所有逾期和異常」
```
Agent 根據責任描述決定通知路由，員工事後可調整：「這種通知不用給我」

---

### AI 驅動核心能力

Agent 層之下，支撐四種 Agent 運作的核心能力：

| 能力 | 說明 |
|------|------|
| **排程自動化** | 定期觸發監控、狀態檢查、主動推播 |
| **責任路由** | 根據自然語言描述的職責，自動決定通知和簽核路由 |
| **信任曲線管理** | confirmedByUser 機制、draft 狀態、漸進式授權 |
| **知識沉澱** | sourceText 保留、aliases 累積、業務規則自然語言化存入 Firestore |

---

### Layer 3 — 展示層

**原則：** 補充 Agent 低效的部分，不是主要操作介面

適合用 UI 而非 Agent 處理的場景：

| 場景 | 原因 |
|------|------|
| 儀表板 | 全局總覽，圖表比文字直觀 |
| 批次操作 | 一次改十張訂單狀態，自然語言很慢 |
| 通知規則管理 | 查看 / 修改現有規則 |
| 權限設定 | 誰可以看什麼，需要明確的設定介面 |
| 報表分析 | 跨業務的趨勢分析、視覺化比較 |

---

