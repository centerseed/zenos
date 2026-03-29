---
type: TD
id: TD-action-layer
status: Superseded
superseded_by: SPEC-task-governance
ontology_entity: action-layer
created: 2026-03-22
updated: 2026-03-27
---

# Technical Design: Action Layer（任務管理）

> 本文件已被 `SPEC-task-governance` 取代。保留供歷史追溯。
> 從 `docs/spec.md` Part 7.1 搬出。

### 為什麼需要 Action Layer

Ontology 承載的是 context（知識），但知識本身不會產生行動。dogfooding 發現的核心缺口：ontology 缺少 output 路徑——從知識到任務派發的閉環不存在。

```
Ontology（知識）──→ 任務（行動）──→ 完成（反饋）
     ↑                                    │
     └────────────────────────────────────┘
     ontology 更新（完成的任務可能產出新知識）
```

Action Layer 不只是「任務管理功能」，它是驗證 ontology 治理品質的唯一手段：
- 任務引用 entity → 驗證 ontology 粒度是否夠用
- 任務帶 blindspot → 驗證盲點推斷是否可行動
- 任務完成反寫 → 驗證雙向治理是否成立

### 架構定位

```
ZenOS 分層架構：

Context Layer（ontology 底座）
  └─ 四維標籤、骨架層、神經層、治理引擎
       │
Application Layers（各 app 共用 ontology context，但有自己的 data model）
  ├─ Action Layer（任務管理）  ← 本章
  ├─ CRM Layer（未來）
  └─ 其他 app layers（未來）
```

每個 Application Layer 的共同特徵：
- 共用 ontology context（透過 linkedEntities / linkedProtocol 連結）
- 有自己的維度（任務加狀態/期限/優先度，CRM 加管線/金額）
- 透過同一套 MCP 介面操作

**Ontology 是底座不是容器——四維標籤是公約數，各 app 加自己的維度。**

### 任務的維度 = Ontology Context + 行動屬性

```
來自 Ontology（自動帶入）           任務自己的（行動屬性）
─────────────────────────           ─────────────────────
What: 跟什麼產品/模組有關            優先度
Why:  為什麼要做這件事               狀態
How:  在什麼專案脈絡下               指派對象（assignee）
Who:  跟哪些角色有關                 期限（dueDate）
                                    依賴關係（blockedBy / subtasks）
                                    驗收條件（acceptanceCriteria）
```

**AI 從 ontology context 推薦行動屬性，人做最終決定。** 例如：連結到 blindspot 的任務 → 建議高優先度。連結到 `status: paused` 的 entity → 建議低優先度。

### 任務模型

```yaml
task:
  id: "task-001"
  title: "寫 Paceriz Q2 社群貼文系列"
  description: "根據 Protocol 的 Why 和目標受眾，產出 4 篇社群貼文"

  # ── 來自 Ontology 的 Context（自動帶入）──
  linkedEntities: ["paceriz", "marketing-campaign-q2"]
  linkedProtocol: "paceriz-protocol"
  linkedBlindspot: "blindspot-003"        # 選填

  # ── 行動屬性 ──

  # 優先度
  priority: "high"              # critical / high / medium / low
  priorityReason: "Q2 行銷啟動在即，且此為盲點 #003 的解法"  # AI 建議理由

  # 狀態（Kanban 六欄）
  status: "in_progress"
  #   backlog      規劃中，還沒排進當前工作
  #   todo         已排定，等待開始
  #   in_progress  進行中
  #   review       等待驗證（做完了，等派任者確認）
  #   done         已完成確認
  #   archived     封存（不再顯示，但保留紀錄）

  # 指派
  createdBy: "barry"            # 人或 agent ID
  assignee: "xiaomei"           # 人（公司層）

  # 時間
  createdAt: "2026-03-22"
  dueDate: "2026-03-29"         # 選填
  completedAt: null

  # 依賴
  blockedBy: ["task-000"]       # 選填
  subtasks: ["task-002", "task-003"]  # 選填

  # 驗收
  acceptanceCriteria:            # 選填
    - "4 篇貼文草稿"
    - "每篇含 CTA 連結"
    - "經 Barry 確認語氣符合品牌"

  # 完成確認（雙向）
  completedBy: null              # 執行者標記完成
  confirmedByCreator: false      # 派任者確認驗收
  rejectionReason: null          # 打回時的原因
```

### 狀態流

```
backlog ──→ todo ──→ in_progress ──→ review ──→ done ──→ archived
                         │              │         │
                         ↓              ↓         ↓
                      blocked        rejected   (自動 archive
                         │              │        after N days)
                         ↓              ↓
                      (解除後)       in_progress
                      回 todo         (重做)
```

| 狀態 | 意義 | 誰觸發 | Dashboard 顯示 |
|------|------|--------|----------------|
| backlog | 規劃中，未排入當前工作 | 建立者 | 規劃池 |
| todo | 已排定，等待開始 | 建立者排定 / AI 建議 | 待辦欄 |
| in_progress | 正在做 | 執行者開始 | 進行中欄 |
| review | 做完了，等派任者確認 | 執行者標記完成 | 等待驗證欄 |
| done | 派任者確認通過 | 派任者確認 | 已完成欄 |
| archived | 封存 | 自動（N 天後）/ 手動 | 隱藏，可查詢 |
| blocked | 被其他任務阻塞 | 執行者標記 | 進行中欄（紅色標記） |

### 優先度的 AI 推薦邏輯

AI 從 ontology context 推薦優先度，人永遠可以覆蓋：

| 訊號（來自 ontology） | 建議優先度 | 理由 |
|----------------------|-----------|------|
| 連結到 blindspot | high+ | 盲點 = 沒人注意到的問題 |
| 連結到 `status: active` 的 entity | medium+ | 正在運作的東西 |
| 連結到 `status: paused` 的 entity | low | 暫停中的東西 |
| 有 dueDate 且 < 3 天 | critical | 快到期 |
| blockedBy 其他任務 | 降一級 | 現在做不了 |
| 被其他任務 blockedBy | 升一級 | 別人在等你 |
| 連結到多個 entity（高 context 交叉度） | 升一級 | 影響範圍大 |

### 任務的雙視角：Inbox / Outbox

每個使用者（人或 agent）看到兩個視角：

**Outbox — 我派出的任務**
```
┌─────────────────────────────────────────────┐
│  📤 我派出的任務                              │
│                                              │
│  🔄 進行中                                   │
│  ├─ 寫 Paceriz 社群貼文 → 小美 (3天前)        │
│  └─ 更新產品頁 SEO → analytics-agent (1小時前) │
│                                              │
│  ✅ 待確認（對方說做完了）                      │
│  └─ 整理客戶回饋 → 小美 ← 點擊確認或打回       │
│                                              │
│  📦 已完成                                    │
│  └─ ...                                      │
└─────────────────────────────────────────────┘
```

**Inbox — 派給我的任務**
```
┌─────────────────────────────────────────────┐
│  📥 派給我的任務                              │
│                                              │
│  🆕 新任務（待接受）                           │
│  └─ 設計 Q2 行銷策略 ← Barry 派的             │
│                                              │
│  🔄 我在做的                                  │
│  └─ 寫技術文件 ← Barry 派的 (進行中)           │
│                                              │
│  ✅ 我完成的（等對方確認）                      │
│  └─ 更新報價單 → 等 Barry 確認                 │
└─────────────────────────────────────────────┘
```

### 任務的 Kanban View（Dashboard）

```
/projects/:id/tasks

┌──────────┬──────────┬──────────┬──────────┬──────────┐
│ Backlog  │   Todo   │ 進行中   │ 等待驗證  │  已完成   │
│          │          │          │          │          │
│ [低]     │ [高]     │ [高]     │ [中]     │ ✅       │
│ 研究競品  │ 寫社群   │ 更新SEO  │ 整理回饋  │ 報價單   │
│ → 未指派  │ →小美    │ →agent-1 │ →小美     │ →小美    │
│          │ 3/29到期  │          │ 等Barry確認│         │
│          │          │ 🔴blocked│          │          │
│          │          │ by task-0│          │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘

切換視角：[全部] [我派出的] [我的任務]
篩選：[角色▼] [優先度▼] [關聯產品▼] [指派對象▼]
```

### 任務與 Who 三層模型的關係

任務的 assignee 是 Who 三層模型的路由終點：

```
建立任務（指定 assignee）
    │
    ├─ 派給角色（marketing）
    │   → 公司層解析成員工（小美）
    │   → 小美自己決定：親自做 or 轉給 agent
    │
    ├─ 派給特定人（barry）
    │   → Barry 的個人層決定：親自做 or 丟給哪個 agent
    │
    └─ Agent 間互派（完全在個人層內部）
        → ZenOS 不管
```

**ZenOS 管到「派給人」就結束。人怎麼分給 agent 是個人層的事。**

### MCP 介面（與 UI 對稱）

UI 能做的事，MCP 都能做。Agent 用 MCP，人用 UI，操作同一份資料：

| 動作 | UI 操作 | MCP 呼叫 |
|------|---------|----------|
| 建任務 | 表單 / 快速建立 | `create_task(title, assignee, linkedEntities, ...)` |
| 改狀態 | 拖卡片到下一欄 | `update_task(id, status: "in_progress")` |
| 標記完成 | 點「完成」 | `update_task(id, status: "review", result: "...")` |
| 確認驗收 | 確認佇列點「確認」 | `confirm_task(id, accepted: true)` |
| 打回重做 | 點「打回」+ 填原因 | `confirm_task(id, accepted: false, reason: "...")` |
| 查我的任務 | Inbox/Outbox 頁籤 | `list_tasks(assignee: "me")` / `list_tasks(createdBy: "me")` |
| 查全部任務 | Kanban 全覽 | `list_tasks(projectId: "...")` |

### 通知機制

| 事件 | 通知誰 | 方式 |
|------|--------|------|
| 任務被指派 | assignee | Dashboard 通知 + MCP event（agent 可訂閱） |
| 狀態變為 review | createdBy | 確認佇列出現 + 通知 |
| 被打回（rejected） | assignee | Dashboard 通知 + rejectionReason |
| 被阻塞解除 | assignee | 任務自動回到 todo |
| 逾期未完成 | createdBy + assignee | Dashboard 高亮 + 通知 |

Phase 0-1 通知只在 Dashboard 內（notification badge）。Phase 2 可擴展到 Slack / email / LINE。

### Firestore Schema（Action Layer）

```
tasks/{taskId}
  title           string    必填
  description     string    選填
  linkedEntities  string[]  選填    連結到 ontology 的 entity ID
  linkedProtocol  string?   選填    連結到 Protocol ID
  linkedBlindspot string?   選填    連結到 blindspot ID
  priority        string    必填    "critical" | "high" | "medium" | "low"
  priorityReason  string    選填    AI 建議理由
  status          string    必填    "backlog" | "todo" | "in_progress" | "review" | "done" | "archived" | "blocked"
  createdBy       string    必填    建立者 UID
  assignee        string?   選填    被指派者 UID（null = 未指派）
  dueDate         timestamp 選填
  blockedBy       string[]  選填    阻塞此任務的其他 task ID
  subtasks        string[]  選填    子任務 task ID
  acceptanceCriteria string[] 選填  驗收條件列表
  completedBy     string?   選填    執行者標記完成時的 UID
  confirmedByCreator boolean 必填   false = 待確認，true = 驗收通過
  rejectionReason string?   選填    打回時的原因
  result          string?   選填    完成時的產出描述或連結
  createdAt       timestamp 必填
  updatedAt       timestamp 必填
  completedAt     timestamp 選填
```

### 它不做什麼

- ✗ 不做 Sprint 管理（SMB 不跑 Scrum）
- ✗ 不做工時追蹤（那是 HR / PM 工具的事）
- ✗ 不做 Gantt 圖（過度工程化，SMB 不需要）
- ✗ 不管 agent 的內部任務拆分（個人層的事）
- ✗ 不做自動指派（AI 建議，人決定）

### 實作優先級

| 優先級 | 功能 | Phase |
|--------|------|-------|
| P0 | 任務 CRUD（建/改/查） + 狀態流 | Phase 1 |
| P0 | Inbox / Outbox 雙視角 | Phase 1 |
| P0 | 確認佇列（review → done / rejected） | Phase 1 |
| P0 | MCP 介面（agent 可操作任務） | Phase 1 |
| P1 | 優先度 AI 推薦 | Phase 1 |
| P1 | Kanban 視覺化 | Phase 1 |
| P1 | 依賴關係（blockedBy） | Phase 1 |
| P2 | 子任務 | Phase 2 |
| P2 | 外部通知（Slack / email） | Phase 2 |
| P2 | 任務模板（重複性任務） | Phase 2 |

---
