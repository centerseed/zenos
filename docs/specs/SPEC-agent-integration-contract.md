# SPEC: ZenOS Agent Integration Contract

> PM: Codex | Date: 2026-03-26 | Status: Draft

## 問題

ZenOS 想做的是公司的共享 context layer，而不是某一個特定 agent 的 plugin。

但現實使用情境是：

- 用戶可能自行客製 system prompt、workflow、subagent 結構
- 不同 agent 的 skill 機制、prompt 習慣、slash command 文化不一致
- 若 ZenOS 的使用建立在「先學會某個 skill」之上，知識圖譜就只會被少數熟手使用

因此需要一份明確的 integration contract，回答：

1. 哪些能力應放在 MCP tool 層，讓任何 agent 都能自然使用？
2. 哪些能力應放在 server 端，避免 caller skill / prompt 重複實作？
3. skill 應扮演什麼角色，才不會變成知識圖譜的唯一入口？

---

## 目標

1. 讓任何掛上 ZenOS MCP 的 agent，都能在不大改工作習慣的前提下使用知識圖譜。
2. 讓知識圖譜的讀寫、治理、權限、context 組裝主要由 server 端負責，而不是散落在 skill。
3. 保留 skill 作為 onboarding 與批次流程加速器，但不讓 skill 成為日常操作的單點依賴。
4. 建立一套可跨 Claude Code、Codex、未來其他 agent host 重用的接入協議。

---

## 非目標

- 不為每一種 agent host 寫一套獨立 workflow。
- 不要求所有用戶學新的 slash commands 才能使用 ZenOS。
- 不把日常知識讀寫綁死在某個 skill 上。
- 不把權限判斷、draft/confirm 邏輯下放到 caller prompt。

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

這些能力不需要 skill。

### 2. 日常知識寫入 → MCP + server governance

日常 knowledge write 應由 `write` 完成，並由 server 處理：

- 欄位驗證
- draft 預設
- link inference
- duplicate / stale 提示
- L2 hard gate

caller 可以提供較完整欄位，但不應被要求自行重做治理邏輯。

### 3. 批次建構 / 增量同步 → skill

下列流程適合 skill：

- 從整個 repo 首次建構 ontology
- 從 git log 做增量同步
- 從最近對話批量沉澱知識

原因是這類工作需要：

- 掃描多檔案
- 分批讀取
- 先全局理解再決定寫入
- 與使用者做中途確認

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

skill 可以選擇性包裝，但不應成為唯一入口。

---

## Agent 使用慣例（最小協議）

這是一份給任意 agent 的最小 usage convention，可放在 setup 文案、starter prompt、partner onboarding。

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

這份慣例應保持簡短，不超過 8-10 行，避免 prompt 污染。

---

## 對 skill 的正式定位

### skill 應保留的角色

1. Setup
2. Batch capture
3. Incremental sync
4. High-value shortcuts

### skill 不應承擔的角色

1. 成為知識圖譜的唯一入口
2. 重做 server 端治理判斷
3. 維護權限規則
4. 決定哪些資料可被某個 agent 看見

---

## Server 端必須提供的無縫能力

若要做到低侵入接入，server 至少要補齊以下能力：

### 1. Context assembly

當 agent 建 task 或查某個 entity 時，server 應能回傳：

- 相關 entities
- protocol
- 相關 documents
- blindspots
- 必要的 context summary

agent 不需要知道如何手動拼裝這些關聯。

### 2. Permission filtering

所有可見性判斷都應在 server 端完成：

- tenant boundary
- user / agent scope
- classification
- inheritance / propagation

agent 只看到自己該看到的結果。

### 3. Draft-by-default

AI 產生的新知識、關聯、blindspot、任務草案預設為 draft 或 review；
不可要求 caller 自己記住哪些情況該先草稿。

### 4. Output path enrichment

當知識產生行動時，server 應自動把 ontology pointer 帶進 task：

- `linked_entities`
- `linked_protocol`
- `linked_blindspot`
- `context_summary`

這是 ADR-004 所指出的 output path 核心。

### 5. Governance hints

在 write / task / confirm 的回應中，server 可回傳：

- 建議補 confirm 的項目
- 建議標記 stale 的 entities
- 建議建立的 blindspot / task
- 可能的 duplicate / overexposure / isolation risk

這些 hints 應由 server 產生，而非 skill 自行猜測。

---

## 對 MCP Tool Description 的要求

如果 ZenOS 要跨 agent host 生效，tool description 本身就是產品表面。

每個 tool description 應包含：

1. Purpose
2. 使用時機
3. 不要用的情境
4. 參數說明
5. 與其他 tool 的邊界

此外還應滿足：

- 命名符合 agent 心智模型，不是內部術語
- 減少「要先懂 ZenOS 才會用」的描述
- 明示何時該先 `search`、何時該 `get`、何時該 `write`

---

## 推薦接入模式

### Mode 1: Zero-customization

適用：一般用戶、自帶 agent、最低導入阻力

做法：

- 掛上 ZenOS MCP
- 提供極短 usage convention
- 不要求安裝 skill

能做的事：

- 查 context
- 寫 draft
- 建 task
- 跑 analyze

### Mode 2: Productivity mode

適用：願意裝 skill 的重度使用者

做法：

- 掛上 ZenOS MCP
- 安裝 `zenos-setup` / `zenos-capture` / `zenos-sync`

額外獲得：

- 首次建構
- git 增量同步
- 對話沉澱快捷流程

### Mode 3: Deep integration

適用：ZenOS 自家或高度客製化 agent

做法：

- 掛上 ZenOS MCP
- 在 agent runtime 中加入 event hooks

例如：

- tool use 後檢查是否值得 capture
- 任務完成後建議 stale / blindspot 更新
- repo 變更後自動 propose sync

---

## 漸進式導入路線

### Phase 1: MCP-first baseline

完成條件：

- 7 個 consolidated tools 維持穩定
- description 針對 agent 決策優化
- setup 頁提供最小 usage convention

### Phase 2: Server enrichment

完成條件：

- task response 自動附 ontology context
- write / confirm response 帶治理 hints
- 權限模型對 agent scope 生效

### Phase 3: Skill refinement

完成條件：

- capture / sync skill 只負責 batch orchestration
- 不再承擔日常知識讀寫主邏輯

### Phase 4: Event-driven automation

完成條件：

- git / task / confirm 等事件可觸發治理建議
- output path 不只靠人工記得去建 task

---

## 決策

ZenOS 的 agent integration 採用以下原則：

- `MCP tools` 是主接點
- `server-side intelligence` 是無縫體驗核心
- `skills` 是 onboarding 與 batch workflow 加速器

不採用「以 skill 為主、MCP 為輔」的模式，因為那會讓 ZenOS 對不同 agent host 的可攜性下降，且把核心知識邏輯散落到 caller 端。

---

## 後續工作

1. 將這份 contract 濃縮為 setup 頁可用的「最小 usage convention」。
2. 審查 `src/zenos/interface/tools.py` 的 tool descriptions，確認是否已符合本 spec。
3. 定義 `task/get/search` 的 server-side context enrichment 回傳格式。
4. 將 `zenos-capture` / `zenos-sync` 定位文件更新為「batch workflow」，避免誤導成日常操作入口。
5. 設計 event-driven hook，補齊 ADR-004 所指出的 output path。
