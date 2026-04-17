---
type: SPEC
id: SPEC-agent-integration-contract
status: Approved
ontology_entity: agent-integration
created: 2026-03-26
updated: 2026-04-10
---

# SPEC: ZenOS Agent Integration Contract

> PM: Codex | Date: 2026-03-26 | Status: Approved
> Layering note: direct ZenOS MCP 與 app-facing MCP facade 可並存。direct API key 模式是現行做法，但不是唯一長期模型；app-facing delegation 以 `SPEC-zenos-auth-federation` 為準。

## 問題

ZenOS 想做的是公司的共享 context layer，而不是某一個特定 agent 的 plugin。

但現實使用情境是：

- 用戶可能自行客製 system prompt、workflow、subagent 結構
- 不同 agent 的 skill 機制、prompt 習慣、slash command 文化不一致
- 若 ZenOS 的使用建立在「先學會某個 skill」之上，知識圖譜就只會被少數熟手使用
- 目前很多團隊以 CLI/UI 型 agent 為主，不想管理額外 API key
- 未來上層 application 可能以 app-facing MCP facade 代表 user 呼叫 ZenOS，而不是直接發放 ZenOS API key

因此需要一份明確的 integration contract，回答：

1. 哪些能力應放在 MCP tool 層，讓任何 agent 都能自然使用？
2. 哪些能力應放在 server 端，避免 caller skill / prompt 重複實作？
3. skill 應扮演什麼角色，才不會變成知識圖譜的唯一入口？
4. 在半自動情境下，如何讓 reviewer、editor、owner 協作而不靠人肉傳話？

> Detailed MCP tool payload / response / compatibility rules are governed by
> `SPEC-mcp-tool-contract`. 本文件只定義 agent integration 原則與分層，不再作為
> MCP tool 介面細節的權威來源。

---

## 目標

1. 讓任何掛上 ZenOS MCP 的 agent，都能在不大改工作習慣的前提下使用知識圖譜。
2. 讓知識圖譜的讀寫、治理、權限、context 組裝主要由 server 端負責，而不是散落在 skill。
3. 保留 skill 作為 onboarding 與批次流程加速器，但不讓 skill 成為日常操作的單點依賴。
4. 建立一套可跨 Claude Code、Codex、未來其他 agent host 重用的接入協議。
5. 在不依賴 API key 常駐 worker 的前提下，提供可運作的半自動審核閉環。
6. 讓 owner 可在一個 approval surface 一站式看到 draft、審核意見、最終確認入口。
7. 保留 `direct ZenOS MCP` 與 `app-facing MCP facade` 兩條接入路徑，但兩者都必須落到同一套 ZenOS authorization runtime。

---

## 非目標

- 不為每一種 agent host 寫一套獨立 workflow。
- 不要求所有用戶學新的 slash commands 才能使用 ZenOS。
- 不把日常知識讀寫綁死在某個 skill 上。
- 不把權限判斷、draft/confirm 邏輯下放到 caller prompt。
- 不承諾在無常駐 worker、無 API key 的前提下做到 24/7 全自動審核。

---

## 設計原則

### 1. MCP first

ZenOS 的主接點是 MCP tools，不是 skill。

只要 agent 能呼叫 MCP，就應能完成大部分知識圖譜操作。

### 2. Server-side intelligence

知識治理、權限過濾、context enrichment、draft semantics 應由 ZenOS server 強制執行。

caller 可以提供 hints，但不能承擔最終規則。

### 3. Skill is accelerator, not dependency

skill 可加速首次建構、增量同步、對話沉澱等高價值流程；
但 agent 查 context、寫 draft、驗收任務，不應依賴特定 skill 才能做到。

### 4. Prompt-light adoption

ZenOS 對 agent 的接入應只需要極短的使用慣例，不應要求大幅修改原有 prompt 或工作習慣。

### 5. Progressive trust

AI 產出永遠先是 draft；高風險變更仍需人確認。
integration contract 必須保留這個分界。

### 6. Role-queue first

跨廠牌協作必須以 role queue 為主，而非 agent 名稱硬綁定。

- 派工必須優先使用 `assignee_role_id`
- 允許各廠牌 agent 自主 claim 同一角色佇列
- 各廠牌 adapter 不得改變共享任務語意或生命週期

---

## 三層責任分工

### Layer A: MCP Tool Contract

這一層負責讓 agent 「自然知道什麼時候該用 ZenOS」。

應承擔：

- 能力切分
- tool 命名
- description 品質
- 輸入輸出 schema
- read / write / confirm / analyze 的心智模型

不應承擔：

- tenant-specific workflow
- 大量流程編排
- 對話級摘要策略

### Layer B: Server-side Orchestration

這一層負責讓 agent 「即使只做正常操作，也能得到 ZenOS 的加值」。

應承擔：

- 權限過濾
- project / tenant scope
- draft / confirm semantics
- 自動 context enrichment
- relationship / link inference
- task 與 ontology 的連結
- 治理檢查與風險控制

不應承擔：

- host-specific slash command UX
- 首次建構時的大量檔案掃描策略

### Layer C: Skills / Workflow Glue

這一層負責高成本但高價值的流程入口。

適合放：

- `/zenos-setup`
- `/zenos-capture`
- `/zenos-sync`
- 「把本次討論沉澱成 ZenOS draft」之類的快捷流程

不適合放：

- 日常讀取 context
- 一般知識寫入規則
- 權限與治理主邏輯

---

## 標準能力分配

### 1. 日常查詢能力 → MCP

日常 context retrieval 應完全經由 MCP tool 完成：

- `search`: 找候選知識
- `get`: 取完整結構化資訊
- `read_source`: 讀原始內容

### 2. 日常知識寫入 → MCP + server governance

日常 knowledge write 應由 `write` 完成，並由 server 處理：

- 欄位驗證
- draft 預設
- link inference
- duplicate / stale 提示
- L2 hard gate

### 3. 批次建構 / 增量同步 → skill

下列流程適合 skill：

- 從整個 repo 首次建構 ontology
- 從 git log 做增量同步
- 從最近對話批量沉澱知識

### 4. 知識驅動行動 → MCP + server enrichment

任務建立、更新、驗收應走：

- `task`
- `confirm`

並由 server 保證：

- task 會帶 ontology refs
- context summary 由 linked entities / protocol / blindspot 組裝
- review / acceptance 流程維持 progressive trust

### 5. 治理檢查 → MCP

品質、過時、盲點分析應由 `analyze` 提供。

---

## Agent 使用慣例（最小協議）

### Read path

- 開始陌生領域任務前，先用 `search`
- 找到候選後，用 `get`
- 只有在需要原文時才用 `read_source`

### Write path

- 穩定、可重用、跨時間存活的知識，才用 `write`
- AI 產出一律視為 draft
- 需要正式生效時再用 `confirm`

### Action path

- 發現後續工作、風險、交接事項時，用 `task`
- 發現知識缺口或治理問題時，用 `analyze`
- 每次會話啟動時，先查自己角色可處理的 queue（pull model）

---

## 半自動跨廠牌審核契約

### 1. Draft 進 queue

- 新 draft 文件被納管時，系統必須建立或更新一張審核 task
- task 必須帶 `assignee_role_id`（例如 `doc_reviewer`）
- task 必須可追溯來源文件（doc id / title / source uri）

### 2. Reviewer claim

- 任一廠牌 reviewer agent 均可讀取同一角色 queue
- claim 後必須更新任務狀態與責任落點，避免重複審核
- 未 claim 的任務不得假設已有 reviewer 接手

### 3. Review 輸出

- reviewer 完成後必須把審核意見寫入 `result`（若工具限制，使用 `description` 的 `Result:` 區塊）
- 審核輸出必須包含摘要、主要發現、建議結論、關聯文件連結
- 任務狀態改為 `review` 後，視為待 owner 最終確認

### 4. Editor 跟進

- editor agent 可讀取待修正文件與 review 輸出
- editor 修改後應在同任務或關聯任務補上修正證據
- reviewer 二次檢查通過後，才可送 owner 最終確認

### 5. Owner 最終確認

- owner 必須在一個 owner-facing approval surface 完成最終確認
- 確認通過後，文件離開 draft 狀態
- 確認退回時，必須保留退回原因與下一步責任人

---

## Approval Surface 要求

owner-facing approval surface 至少必須提供三個可操作視角：

1. `Draft Inbox`
- 顯示所有 draft 文件、關聯節點、目前任務狀態
- 標示是否已有 reviewer claim

2. `Review Queue`
- 依角色顯示待審、審核中、待補件
- 顯示每張任務最近審核輸出與最後更新時間

3. `Approval Center`
- 顯示待 owner 最終確認項目
- 顯示最終摘要、審核結論、文章連結
- 支援通過 / 退回並寫入原因

---

## 推薦接入模式

### Mode 1: Zero-customization

適用：一般用戶、自帶 agent、最低導入阻力

### Mode 0.5: Human-triggered semi-automation

適用：以 Claude CLI / Codex UI 為主，且已具備 app-facing delegated credential 路徑的團隊

做法：

- MCP-first
- 人工啟動 agent session
- agent 啟動即先拉 role queue 再執行審核
- owner 在 approval surface 完成最終確認

限制：

- 此模式不是目前 direct MCP 的零設定基線
- 若團隊沒有 API key，則必須先完成 app-facing federation / delegated credential 接入，才能成立

完成條件：

- 新 draft 在 `Draft Inbox` 可見
- reviewer 可從 queue 撿單並回寫審核輸出
- owner 可在 `Approval Center` 一次完成最終確認

### Mode 2: Productivity mode

適用：願意裝 skill 的重度使用者

### Mode 3: Deep integration

適用：ZenOS 自家或高度客製化 agent

---

## 漸進式導入路線

### Phase 1: MCP-first baseline

### Phase 2: Server enrichment

### Phase 3: Skill refinement

### Phase 3.5: Approval surface control tower

完成條件：

- 三個面板（Draft Inbox / Review Queue / Approval Center）可追蹤同一文件的狀態流
- 任何最終確認都有對應審核輸出與來源連結

### Phase 4: Event-driven automation

---

## 決策

ZenOS 的 agent integration 採用以下原則：

- `MCP tools` 是主接點
- `server-side intelligence` 是無縫體驗核心
- `skills` 是 onboarding 與 batch workflow 加速器
- 半自動情境以 role queue + owner-facing approval surface 建立跨廠牌協作

---

## 後續工作

1. 將 setup 文案更新為 `會話先拉 queue` 的最小慣例。
2. 補齊 task queue 的可見欄位與審核輸出格式定義。
3. 補一份 approval surface 規格，定義三個面板欄位與操作事件。
4. 設計 reviewer/editor/owner 的責任邊界與驗收標準。
5. 規劃從半自動模式升級到事件驅動模式的遷移路徑。
