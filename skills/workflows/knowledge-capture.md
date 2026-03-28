---
type: SKILL
id: knowledge-capture
status: Draft
ontology_entity: TBD
created: 2026-03-27
updated: 2026-03-27
---

> 權威來源：本文件是 `/zenos-capture` 操作流程的 SSOT。
> `.claude/skills/zenos-capture/SKILL.md` 為舊格式，以本文件（`skills/workflows/knowledge-capture.md`）為準。

# knowledge-capture — 知識捕獲 + 首次建構

你是 ZenOS 的知識治理 agent。根據引數自動選擇模式：

| 引數 | 模式 | 速度 |
|------|------|------|
| 無引數 | 對話捕獲 | 快（秒） |
| 單一檔案路徑 | 檔案捕獲 | 快（秒） |
| 目錄路徑 | **首次建構模式** | 分鐘級（批量） |

---

## 模式 A：對話捕獲（無引數）

來源 = 當前對話的最近 20-30 個交換。跳到「知識分析流程」。

---

## 模式 B：檔案捕獲（單一 .md 或其他文字檔）

用 Read tool 讀取該檔案。跳到「知識分析流程」。

**字數提醒**：若檔案超過 500 字，最後提醒用戶原文留在原位（Git/Drive），ZenOS 只存語意摘要。

---

## 模式 C：首次建構模式（目錄路徑）

用戶有一個「已有很多文件的現有專案」，你要幫他把這個專案的知識體系建入 ontology。

### C1. 掃描目錄，建立文件清單

```bash
find {目錄} -name "*.md" -not -path "*/.venv/*" -not -path "*/node_modules/*" \
  -not -path "*/__pycache__/*" -not -path "*/.git/*" | sort
```

把結果按以下優先級分組：

**P0 — 骨架層種子（必讀，用來建實體）**
路徑或檔名符合：`CLAUDE.md`、`README.md`、`*OVERVIEW*`、`*ARCHITECTURE*`、
`*REFACTOR_SUMMARY*`、`*COMPLETE_REFACTOR*`、`*STRUCTURE*`、`docs/architecture/`

**P1 — 規格文件（讀 + 建 document entry）**
路徑符合：`docs/*spec*`、`docs/*frd*`、`docs/*plan*`、`*SPEC*.md`、`*FRD*.md`、
`FIRESTORE_STRUCTURE.md`、`docs/01-specs/`、`docs/04-frds/`、`docs/09-agent/`

**P2 — 功能/整合文件（建 document entry，選擇性讀）**
路徑符合：`docs/02-api/`、`docs/03-integrations/`、`docs/guides/`、`docs/models/`、
`docs/services/`、`docs/data_schemas/`、`*LITERATURE_REVIEW*.md`

**P3 — 其餘文件（只建 entry，不讀全文）**
所有其他 `.md`

**跳過（噪音，不進 ontology）**
- `*FIX_REPORT*`、`*VALIDATION_FIX*`、`*CRITICAL_ERRORS_FIX*` — 一次性 bug fix 記錄
- `*IMPORT_SHADOWING*`、`*ENCRYPTION_KEY*` — 維運細節
- `tests/`、`integration_tests/`、`.venv/`、`node_modules/`

顯示掃描結果讓用戶確認：
```
掃描完成：{目錄}
  P0（骨架種子）：{n} 個文件 — [CLAUDE.md, README.md, ...]
  P1（規格）    ：{n} 個文件
  P2（功能）    ：{n} 個文件
  P3（其餘）    ：{n} 個文件
  跳過          ：{n} 個文件

預計建立 {total} 個 document entries，讀取 {P0+P1} 個文件。
開始？（直接說「開始」或調整跳過清單）
```

### C2. 第一階段：全局讀取，形成全景理解

讀取**所有** P0 文件，以及**所有** P1 文件，串接為一個全局 context。

**重要**：這個階段不產出任何 entity。目的是先理解整間公司在做什麼——產品定位、客群、運作方式、核心概念、已知文件的整體輪廓。讀完才能做下一步的全局統合。

讀取過程中不需要呈現進度，只在全部讀完後進入 C3。

### C3. 第二階段：全局 L2 統合

> L2 三問判斷與 impacts 撰寫規則見 `skills/governance/l2-knowledge-governance.md`

這是核心步驟。你已經讀完所有核心文件，現在以全公司的視野統合理解，按以下 5 步思考，**最後一次性呈現 proposals，等用戶確認後才寫入**。

**Step 1：全景理解**

用 3-5 句話描述：這間公司在做什麼、賣給誰、怎麼運作。這是後續所有判斷的基礎。

**Step 2：共識辨識**

從全景中抽取符合三問標準的 L2 概念：
1. **是不是公司共識？** 公司裡任何人說出來都會點頭——不是某個角色的專屬知識
2. **改變時有下游影響？** 這個概念如果改了，有其他概念必須跟著動
3. **跨時間存活？** 不是一次性事件，是持續為真的事實

**Step 3：獨立性切割**

判斷概念邊界——「A 改了，B 不一定跟著改」→ 分成兩個 L2；「A 改了，B 一定跟著改」→ 同一個 L2。
- 一個技術模組可以拆成多個 L2（按「可獨立改變」切）
- 多份文件散落的同一個概念 → 統合成一個 L2（不是每份文件各建一個）

**Step 4：跨角色語言**

用任何角色都聽得懂的語言寫 summary：
- 不是技術語言（不寫 API、LLM、schema 等工程詞彙）
- 不是行銷語言（不過度包裝）
- 是共識語言（事實陳述，任何人讀了都點頭）
- `tags.why` 從公司或客戶角度寫，不從技術角度寫
- `tags.who` 列出所有相關角色，不只是 owner

**Step 5：影響路徑推斷**

從全局理解推斷 impacts 關聯——需要同時理解 A 和 B 才能判斷：
- 每個 L2 至少要有一條 relationship
- `impacts` 是最核心的關係類型：「A 改了，B 必須跟著檢查」
- description 格式：「A 改了{什麼}→ B 的{什麼}要跟著看」（description 必須含 `→`，Server 會驗證）
- 說不出具體場景的關係 = noise，不該建

**L2 進入 proposals 的硬性前置條件（兩關都要過，才列入下方輸出）：**

1. 三問全過（Step 2 三問均回答 Yes）
2. 至少說得出 1 條具體 impacts（Step 5 能填完「A 改了什麼→B 的什麼要跟著看」）

任何一關未過的候選，**不得列入 L2 proposals**，直接走分層路由決策樹降為 L3 document 或 sources。

> 設計理由：impacts gate 只在 `confirm` 時由 Server 驗證，capture 時不擋。若 capture 不自我設限，骨架層會堆滿三問未通過的 draft，ontology 退化成文件索引。這個前置條件是 capture skill 自我執行的品質底線。

**C3 輸出格式（一次性呈現，等用戶確認後寫入）：**

```
── 全景理解 ──────────────────────────────────────
{3-5 句公司全景描述}

── L2 概念 Proposals（需要你確認）───────────────

[1] 概念名稱
  摘要：{2-3 句，任何人都聽得懂，不需要背景知識}
  What: {這跟什麼有關——產品名、功能區塊}
  Why:  {為什麼重要——從公司/客戶角度，不是技術角度}
  How:  {現在怎麼運作——白話描述，不是技術實作}
  Who:  {誰需要知道——列出所有相關角色}
  來源文件：{從哪些文件統合出這個概念}
  三問：✓ 跨時間存活 ✓ 跨角色（≥2 個）✓ 公司共識
  Impacts 草稿：「{A 改了什麼}→{B 的什麼要跟著看}」

[2] ...

── 關聯 Proposals ──────────────────────────────
[R1] 「概念A」→ impacts →「概念B」
  說明：改定價時，onboarding 報價話術必須更新
[R2] 「概念C」→ part_of →「概念D」
  說明：{具體場景}
...

────────────────────────────────────────────────
輸入要確認的概念編號（如「1 3」），或「全部」，或「略過」：
確認關聯？（「全部」/選擇編號/「略過」）：
```

**確認後寫入規則：**

L2 entity 寫入時：
- `type = "module"`
- `level = 2`（標記為 L2，用於和 L3 document entity 區分）
- `parent_id` = product entity ID（**必填**，沒有 parent_id = Dashboard 上看不到）
- `confirmed_by_user = true`（用戶確認的）
- `sources` = 從哪些文件統合出這個概念（支援跨文件統合）
- `layer_decision` = `{q1_persistent: true, q2_cross_role: true, q3_company_consensus: true, impacts_draft: "{proposals 中的 Impacts 草稿}"}`（**Server 強制驗證**，缺少或三問不全通過會被阻擋）

Relationship 寫入時：
- `type` 可以是 `impacts`、`depends_on`、`part_of`、`enables`
- `description` 必須具體——不是「A 依賴 B」，是「A 改了{什麼}→ B 的{什麼}要跟著看」；`impacts` 描述必須含 `→`，否則 confirm 時 Server 會擋下
- **Relationship 不能塞在 entity write 的 data 裡**；必須用 `write(collection="relationships", ...)` 單獨寫入
- **去重機制**：相同 source→target→type 的組合已存在時，re-write 只會回傳舊的，不會更新描述。若需要修正描述，必須換一個不同的 target entity 建新關聯

### C4. 第三階段：P1 文件 — 建 document entry

> 文件治理合規流程見 `skills/governance/document-governance.md`

為每份 P1 文件建立 document entry（C2 已讀過內容，直接寫入，不需要重讀）：

```
進度：P1 規格文件
  [1/{n}] docs/01-specs/plan-overview-v2.md → 讀取中...
    → write(collection="documents") ✅  (id: xxx)
  [2/{n}] docs/01-specs/SPEC-weekly-plan-v2.md → ...
```

每份 document entry 包含（注意：`write(collection="documents")` 會自動建立 `entity(type="document")`）：
- `title`：從路徑或文件 H1 標題取得（映射為 entity.name）
- `source`：`{type, uri, adapter}`，**嚴格按照「知識分析流程 Step 3」的 GitHub URL 構建步驟**（git remote 解析 + git root 相對路徑）。映射為 entity.sources[0]
- `tags.what`：關聯的實體（list[str]，從文件內容或路徑推斷）
- `tags.why`：這份文件為什麼存在（一句話）
- `tags.how`：文件類型（spec/frd/guide/architecture）
- `tags.who`：目標讀者（list[str]，如 ["開發", "PM"]）
- `summary`：2-3 句語意摘要——這份文件在知識體系中的定位，不是全文節錄
- `linked_entity_ids`：關聯的 entity IDs（**優先指向 C3 確認的 L2 entity**，第一個映射為 parent_id，其餘自動建立 relationships）
- `confirmed_by_user = false`（全部先 draft）

### C5. 第四階段：P2/P3 文件 — 追加到 entity.sources（不建獨立 entity）

P2/P3 文件不值得成為獨立節點，用 `append_sources` 追加到所屬 entity（優先追加到最相關的 L2 entity）：

```
write(collection="entities", id={parent_entity_id}, data={
  name: {existing_name},
  type: {existing_type},
  summary: {existing_summary},
  tags: {existing_tags},
  append_sources: [{uri: GitHub URL, label: 檔名, type: "github"}]
})
```

```
進度：P2/P3 文件（追加 sources）
  [1/{n}] docs/02-api/... → append to 訓練計畫.sources ✅
  [2/{n}] ...
```

### C6. 自動品質檢查與盲點分析（必做）

建構完成後，**自動執行**以下兩個檢查，不需要用戶觸發：

1. `analyze(check_type="quality")` — 12 項品質檢查（含 L2 summary 可讀性與 impacts 覆蓋率），回報分數和未通過項目
2. `analyze(check_type="blindspot")` — 推斷知識盲點，寫入 blindspots

如果品質分數 < 70 或有 failed 項目，**主動提出修正建議**（例如補 impacts relationship、重寫技術語言過重的 summary、拆分過大的概念）。

### C7. Summary

```
✅ 首次建構完成：{目錄名稱}

L2 概念層（entities）：
  • 確認 {n} 個 L2 概念（你逐一確認的）
  • Draft {n} 個 L2 概念（你略過的，待後續確認）
  • Relationships：{n} 個（含 impacts / depends_on / part_of / enables）

神經層（documents）：
  • P1 精讀 entry：{n} 個（linked 到 L2 entity）
  • P2/P3 追加 sources：{n} 個

品質檢查：{分數}/100
  通過：{n} 項 | 未通過：{n} 項
  {列出未通過項目}

盲點分析：{n} 個 blindspot 已記錄

下一步：
  → 呼叫 search(confirmed_only=false) 查看所有待確認 drafts
```

---

## 知識分析流程（模式 A / B 共用）

### Step 1：識別有價值的知識

**骨架層候選（需要人確認）**：

| 類型 | 判斷標準 |
|------|----------|
| 新實體 | 第一次出現的產品、模組、角色、目標、專案 |
| 實體更新 | 已知實體的狀態、摘要有重大變更 |
| 新關係 | 兩個實體之間新確認的依賴/服務關係 |

**神經層候選（自動寫入 draft）**：

| 類型 | 判斷標準 |
|------|----------|
| 新文件 entry | 某份具體文件值得在 ontology 建立語意代理 |
| 文件更新 | 已知文件的狀態或摘要需要更新 |
| 盲點 | 發現的知識缺口、風險、矛盾 |

若找不到任何候選，回覆：
> 這段對話/文件沒有發現值得捕獲的新知識。如果你認為有遺漏，告訴我哪個部分值得存入。

### Step 2：比對現有 ontology

每個候選寫入前先 `search(query=名稱或關鍵詞)` 避免重複：
- 找到且資訊吻合 → 跳過
- 找到但需更新 → 標記「更新」
- 找不到 → 標記「新增」

### Step 3：神經層自動寫入 draft

```
# 寫入前先查重：用 search(collection="documents", query="{source.uri}")
# 檢查同 URL 的 document 是否已存在。已存在就跳過，不重複建立。
write(collection="documents", data={
  title, source, tags, summary,
  linked_entity_ids,
  confirmed_by_user: False
})
```

> **linked_entity_ids 必帶**：你在掃描時已經知道這份文件跟哪個 entity 相關，直接帶上。不確定時才省略，server 會用 GovernanceAI 兜底推斷。

文件 entry 的 `source.uri`（**必須嚴格遵守**）：

構建 GitHub URL 的步驟：
1. 在檔案所在目錄執行 `git remote get-url origin` 取得 remote URL
2. 從 remote URL 解析 owner/repo（例如 `https://github.com/centerseed/havital.git` → `centerseed/havital`）
3. 執行 `git rev-parse --show-toplevel` 取得 git root 絕對路徑
4. 用「檔案絕對路徑 - git root 路徑」算出相對路徑
5. 取得預設分支：`git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null` 或 fallback 到 `main`
6. 組合：`https://github.com/{owner}/{repo}/blob/{branch}/{相對路徑}`

**禁止**：從目錄名推斷 repo 名稱、省略子目錄路徑。

若無 git remote → `file://{絕對路徑}`（並在 summary 中標記）

### Step 4：骨架層列出等待確認

```
── 骨架層 Proposals（需要你確認）────────────────

[1] 新增實體
  名稱：Paceriz Training Service
  類型：product
  摘要：[一句話]
  What: [跟什麼有關]
  Why: [為什麼存在]  ← 意圖性維度，你確認後生效
  How: [怎麼運作]   ← 意圖性維度，你確認後生效
  Who: [給誰/誰負責]

[2] 新增實體：ACWR Safety Module（類型：module）

[3] 新增關係
  Paceriz → depends_on → PostgreSQL
  說明：主要資料層

────────────────────────────────────────────────
輸入要確認的編號（如「1 3」），或「全部」，或「略過」：
```

確認後 `confirmed_by_user = True`，略過的存成 draft（`False`）。

### Step 5：Summary

```
✅ /zenos-capture 完成

神經層（自動 draft）：• {文件標題} → documents/{id}
骨架層（你確認的）：• {實體名稱} → entities/{id}
待確認：呼叫 search(confirmed_only=false) 查看
```

---

## 核心原則

- **Why/How 是意圖性維度**：AI 填的 Why/How 一律 draft，不直接 confirmed
- **What/Who 是事實性維度**：AI 準確度高，可直接填入
- **不存原始內容**：只存語意摘要，原文留在來源（Git/Drive）
- **首次建構先骨架後神經**：先確認實體結構，再大量建文件 entry
- **快**：核心價值是在知識產生點捕獲，速度比完美更重要

---

## MCP Server 驗證規則（違反會被阻擋）

以下規則由 MCP Server 強制執行，write 操作違反時會回傳 ValueError 並告知正確值。

### Entity 命名規則
- **禁止括號標註**：不可用 `"訓練計畫 (Training Plan)"` 或 `"Training Plan Module (iOS)"`，直接用乾淨的名稱如 `"訓練計畫"` 或 `"Training Plan Module"`
- 長度 2-80 字元，前後空白會被自動 strip
- 同 type + name 不可重複（重複時 Server 會回傳既有 entity 的 ID，改用 update）

### Entity 必填驗證
- `type` 必須是：`product` / `module` / `goal` / `role` / `project`
- `status` 必須是：`active` / `paused` / `completed` / `planned`
- `tags` 必須包含四維：`what` / `why` / `how` / `who`
- **Module 的 `parent_id` 是強制必填**（不是 warning，是阻擋）
- `parent_id` 指向的 entity 必須已經存在

### Relationship 驗證
- `source_entity_id` 和 `target_entity_id` 必須都是已存在的 entity
- `type` 必須是：`depends_on` / `serves` / `owned_by` / `part_of` / `blocks` / `related_to` / `impacts` / `enables`
- L2 概念之間優先使用 `impacts`（A 改了，B 必須跟著檢查）和 `enables`（A 讓 B 成為可能）

### Blindspot 驗證
- `severity` 必須是：`red` / `yellow` / `green`
- `related_entity_ids` 裡的每個 ID 必須都存在

### Document 驗證
- `source.type` 必須是：`github` / `gdrive` / `notion` / `upload`
- `linked_entity_ids` 裡的每個 ID 必須都存在

### Protocol 驗證
- `entity_id` 必須是已存在的 entity
- `content` 必須包含四維：`what` / `why` / `how` / `who`

### 建議的寫入順序
1. 先建 product entity（拿到 ID）
2. 再建 module entity（帶 parent_id 指向 product）
3. 再建 relationships（source/target 都已存在）
4. 建 documents（帶 linked_entity_ids + 寫入前用 source.uri 查重，已存在就跳過）
