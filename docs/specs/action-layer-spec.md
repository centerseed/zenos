# Action Layer — ZenOS 第一個 Application Layer

> 日期：2026-03-22
> 狀態：Draft
> 作者：PM
> 交付對象：Architect
> 前置依賴：Phase 1 Ontology MVP（已完成）

---

## 問題陳述

Ontology 底座已經在 Firestore + MCP 上運作，能捕獲知識、搜尋、推斷盲點。但 dogfooding 暴露了一個核心問題：**知識到了 ontology 之後，沒有人/agent 知道該拿它做什麼。**

具體痛點（2026-03-22 dogfooding 實測）：

1. PM 捕獲了 blindspot（severity=red），但 Architect 不知道有這件事
2. PM 寫了 ADR，但老闆不知道 PM 規劃了哪些任務
3. 要讓 Architect 開始工作，老闆必須手動說「去 ontology 找 ADR-003、ADR-004、然後看 blindspots...」——但老闆自己也不記得在哪
4. 任務散落在 5 個地方（Zentropy、memory、ADR、ontology blindspots、dev-log），沒有全局視圖

**根本原因：ontology 只有 input 路徑（capture），沒有 output 路徑（知識 → 行動）。**

Action Layer 是 ontology 的第一個消費者，也是驗證 ontology 治理品質的唯一手段：
- 任務引用 entity → 驗證 entity 粒度是否夠用
- 任務帶 blindspot context → 驗證 blindspot 描述是否 actionable
- 任務完成後反寫 ontology → 驗證雙向治理是否順暢

## 目標

- 形成 **ontology → action → validate → improve ontology** 的驗證回路
- 老闆能在一個地方看到「現在有哪些事需要做、誰負責、依據什麼知識」
- Agent（PM/Architect/Developer）收到任務時，自動獲得相關 ontology context
- Blindspot severity=red 能自動產生 draft action，不靠人記得

## 非目標（不在範圍內）

- 不做通用任務管理（日常雜務、修 bug 留給 Linear/Zentropy）
- 不做甘特圖、燃盡圖等專案管理 UI
- 不做 notification 系統（Phase 2）
- 不做跨公司/多租戶
- 不取代 Zentropy——Action Layer 只管「知識驅動的行動」

## 使用者故事

- 身為**老闆**，我想在一個地方看到所有從知識洞察產生的行動項目，以便知道公司知識治理的完整進度
- 身為 **PM**，我想在 capture 完知識後，直接建立帶 ontology context 的任務給 Architect，以便不用手動解釋「去哪裡找相關資料」
- 身為 **Architect**，我想收到任務時自動獲得相關的 entities、documents、blindspots，以便不用自己翻 ontology 找 context
- 身為 **AI agent**，我想查詢「跟我相關的待辦行動」，以便主動推進而不是被動等人指派

---

## 架構定位

```
┌─────────────────────────────────────┐
│     Application Layer: Actions      │  ← 本 spec
│  ┌─────────────────────────────┐    │
│  │  actions collection         │    │
│  │  + 狀態流轉                  │    │
│  │  + 指派 / 問責               │    │
│  │  + 期限 / 優先級             │    │
│  │  + ontology_refs（指針）     │    │
│  └──────────┬──────────────────┘    │
│             │ references            │
│  ┌──────────▼──────────────────┐    │
│  │  Context Layer: Ontology    │    │  ← 已有
│  │  entities / documents /     │    │
│  │  blindspots / protocols     │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

**Actions 引用 ontology，不住在 ontology 裡。** 各自的 data model 獨立，透過 `ontology_refs` 連結。

---

## 交付物 1：Firestore Schema

### actions/{actionId}

```
title           string      必填    動詞開頭（如「設計 ontology output 路徑機制」）
description     string      必填    做什麼、為什麼做、完成標準
status          string      必填    "draft" | "open" | "in_progress" | "blocked" | "done" | "cancelled"
priority        string      必填    "critical" | "high" | "medium" | "low"
assignee_role   string      必填    "pm" | "architect" | "developer" | "qa" | "barry"
created_by      string      必填    誰建立的（"pm" | "architect" | "system" | "barry"）
source_type     string      必填    "blindspot" | "capture" | "discussion" | "manual"

ontology_refs               map     必填    指向 ontology 的指針
  entity_ids    string[]    選填    相關的 entity IDs
  document_ids  string[]    選填    相關的 document IDs
  blindspot_ids string[]    選填    觸發這個 action 的 blindspot IDs
  protocol_ids  string[]    選填    相關的 protocol IDs

context_summary string      必填    AI 從 ontology_refs 自動組裝的 context 摘要
                                    （讓收到任務的人/agent 不用自己去查）

blocked_reason  string      選填    status=blocked 時填寫
depends_on      string[]    選填    依賴的其他 action IDs
due_date        timestamp   選填

confirmedByUser boolean     必填    false = AI draft，true = 老闆或 PM 確認
createdAt       timestamp   必填
updatedAt       timestamp   必填
completedAt     timestamp   選填
```

### 狀態流轉

```
draft → open → in_progress → done
                    ↓
                 blocked → in_progress → done

open → cancelled
draft → cancelled
```

- `draft`：系統自動建立（如 blindspot 觸發），待人確認
- `open`：已確認，等待指派的角色開始做
- `in_progress`：角色已開始處理
- `blocked`：被擋住，需要填 blocked_reason
- `done`：完成，可觸發 ontology 反向更新
- `cancelled`：不需要做了

### 設計原則

- **`ontology_refs` 是核心欄位**——每個 action 都必須能追溯到 ontology 裡的知識來源
- **`context_summary` 是 agent 的快速入口**——收到任務不用自己跑 5 次 search_ontology
- **`confirmedByUser` 沿用 ontology 的信任機制**——AI 建的 action 都是 draft
- **`source_type` 記錄來源**——方便未來分析「哪種來源的 action 完成率最高」

---

## 交付物 2：MCP Tools

### 治理端（PM / Barry 用）

#### create_action

```
用途：建立一個知識驅動的行動項目
輸入：
  title: string
  description: string
  priority: "critical" | "high" | "medium" | "low"
  assignee_role: string
  ontology_refs: { entity_ids?, document_ids?, blindspot_ids?, protocol_ids? }
  source_type: "blindspot" | "capture" | "discussion" | "manual"
  depends_on?: string[]
  due_date?: timestamp
輸出：完整的 action（含自動組裝的 context_summary）

行為：
  1. 寫入 actions collection
  2. 自動從 ontology_refs 拉取相關 entries 的摘要，組裝 context_summary
  3. confirmedByUser = false（AI 建的），true（Barry 手動建的）
```

#### list_actions

```
用途：列出行動項目，可按狀態/角色/優先級過濾
輸入：
  status?: string
  assignee_role?: string
  priority?: string
  include_context?: boolean（是否展開 context_summary）
輸出：actions 列表
場景：老闆想看全局、PM 想看自己負責的、Architect 想看分配給自己的
```

#### update_action

```
用途：更新行動狀態或內容
輸入：
  id: string
  status?: string
  blocked_reason?: string
  description?: string（可補充進度）
輸出：更新後的 action
```

#### complete_action

```
用途：標記行動完成 + 觸發 ontology 反向更新
輸入：
  id: string
  outcome_summary: string（做了什麼、結果是什麼）
  ontology_updates?: {
    resolve_blindspot_ids?: string[]     關閉相關 blindspot
    update_entity_ids?: string[]          標記這些 entity 需要 review
    new_blindspot?: { description, severity }  過程中發現新盲點
  }
輸出：更新後的 action + ontology 更新結果

行為：
  1. action.status = "done"，記錄 completedAt
  2. 如有 resolve_blindspot_ids → 將 blindspot status 改為 "resolved"
  3. 如有 update_entity_ids → 將 entity 標記為 stale 待 review
  4. 如有 new_blindspot → add_blindspot
  這就是 ontology → action → validate → improve ontology 的回路閉合點
```

### 消費端（Agent 用）

#### get_my_actions

```
用途：取得指派給某角色的待辦 actions，含完整 context
輸入：
  role: string（"architect" | "developer" | "qa" | "pm"）
輸出：該角色的 open/in_progress actions，每個都帶 context_summary
場景：Architect 開新 session，第一步就是「我有什麼事要做？」
```

### 自動觸發（系統行為）

#### blindspot_to_action（內部邏輯，非 MCP tool）

```
觸發條件：add_blindspot() 被呼叫且 severity = "red"
行為：
  1. 自動建立 draft action
  2. title = "處理盲點：{blindspot.description 前 30 字}"
  3. ontology_refs.blindspot_ids = [blindspot.id]
  4. assignee_role = 從 blindspot 的 related_entity_ids 推斷 owner，
     推斷不了就 = "barry"（老闆兜底）
  5. source_type = "blindspot"
  6. confirmedByUser = false
```

---

## 交付物 3：工作流程

### 流程一：PM capture → 建 action → Architect 接手

```
PM session:
  ├── 對話中發現問題
  ├── /zenos-capture → 寫入 ontology（documents, blindspots）
  ├── create_action(
  │     title: "設計 MCP tool description 品質標準",
  │     assignee_role: "architect",
  │     ontology_refs: {
  │       document_ids: ["ADR-003的id", "ADR-004的id"],
  │       blindspot_ids: ["tool_description的blindspot_id"]
  │     }
  │   )
  └── action 建立，context_summary 自動組裝

Architect session:
  ├── get_my_actions(role="architect")
  │   → 看到任務 + 完整 context_summary
  │   → 不需要老闆手動解釋去哪裡找資料
  ├── update_action(status="in_progress")
  ├── ... 做事 ...
  └── complete_action(
        outcome_summary: "已定義 12 條 tool description 品質規則",
        ontology_updates: {
          resolve_blindspot_ids: ["tool_description的blindspot_id"],
          new_blindspot: { description: "需要自動檢測 tool description 品質", severity: "yellow" }
        }
      )
      → blindspot 被 resolved
      → 新 blindspot 被記錄
      → ontology 回路閉合
```

### 流程二：Blindspot 自動觸發 → 老闆確認 → 指派

```
任何 session:
  ├── add_blindspot(severity="red", ...)
  │   → 系統自動建 draft action
  │
老闆（Dashboard 或 Claude session）:
  ├── list_actions(status="draft")
  │   → 看到自動建的 action
  ├── 確認或修改
  │   → confirm(collection="actions", id=xxx)
  │   → 或 update_action 調整 assignee/priority
  └── action 變成 open，等角色接手
```

### 流程三：老闆查看全局

```
Barry session:
  ├── list_actions(include_context=true)
  │
  │   critical / open:
  │     [1] 設計 ontology output 路徑機制 → Architect
  │         context: ADR-004, 2個red blindspots
  │     [2] 實作 Claude Code PostToolUse hook → Architect
  │         context: ADR-003, governance trigger blindspot
  │
  │   in_progress:
  │     [3] Dashboard v0 前端建設 → Developer
  │         context: dashboard-v0 spec, partner collection
  │
  │   draft (待確認):
  │     [4] 處理盲點：ontology 缺少 application layer 消費者
  │         context: blindspot n5TpmrTunMj3...
  │
  └── 一個畫面，全局可見
```

---

## 成功條件

- [ ] PM 建立 action 時指定 ontology_refs，Architect 收到任務自動看到相關 context
- [ ] Blindspot severity=red 自動產生 draft action
- [ ] `complete_action` 能反向更新 ontology（resolve blindspot、標記 entity stale）
- [ ] `list_actions` 提供老闆全局視圖，不用去 5 個地方翻
- [ ] `get_my_actions` 讓角色一開 session 就知道自己該做什麼
- [ ] 回路驗證：建 action → 做完 → ontology 被更新 → 更新觸發新 action → 回路閉合

## 開放問題（待 Architect 決策）

- [ ] `context_summary` 的自動組裝邏輯：從 ontology_refs 拉多少資訊？全部摘要還是只拉標題？
- [ ] `get_my_actions` 在 MCP tool description 怎麼寫，才能讓 agent 在 session 開始時自然呼叫？（呼應「tool description 是唯一整合介面」的原則）
- [ ] Actions 要不要也有 `tags`（四維標籤）？或者透過 ontology_refs 繼承就夠了？
- [ ] `blindspot_to_action` 的 assignee 推斷邏輯：entity 的 Who 維度夠用嗎？
- [ ] Action 完成後的 ontology 更新，要不要也走 draft → confirm？還是直接生效？
- [ ] 與 Dashboard v0 的整合：actions 是否要在 Dashboard 上顯示？

---

## 與其他 spec 的關係

| 文件 | 關係 |
|------|------|
| Phase 1 Ontology MVP | Action Layer 的基礎——所有 ontology 功能已就緒 |
| ADR-003 (Governance Trigger) | Input 路徑。Action Layer = Output 路徑。未來共用 Governance Engine |
| ADR-004 (Ontology Output Path) | 本 spec 是 ADR-004 的實作方案 |
| Dashboard v0 spec | 待決策：actions 是否要在 Dashboard 顯示 |

---

*PM 交付。Architect 請基於此 spec 產出技術設計 + 實作任務拆分。*
*本 spec 的優先級高於 Dashboard v0 和 Governance Hook——因為它是驗證 ontology 品質的必要手段。*
