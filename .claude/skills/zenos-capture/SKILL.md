---
name: zenos-capture
description: >
  從當前對話、單一文件、或整個專案目錄擷取知識並寫入 ZenOS ontology。
  三種模式：(1) 無引數 = 從最近對話捕獲；(2) 單一檔案 = 讀該檔案；
  (3) 目錄路徑 = 首次建構模式，自動掃描目錄內所有文件並批量建構 ontology。
  當使用者說「存進 ontology」「記到 ZenOS」「capture 這段」「/zenos-capture」，
  或說「把這個專案加入 ZenOS」「幫我建這個服務的 ontology」「把這個 repo 的文件掃進去」，
  或在討論完某個設計決策後想保存到知識層時，一定要使用這個 skill。
  引數範例：無引數、path/to/file.md、/Users/me/project/（目錄）
version: 2.0.0
---

# /zenos-capture — 知識捕獲 + 首次建構

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

### C2. 第一階段：讀 P0，建骨架層

逐一讀取所有 P0 文件，從中提取：
- 產品名稱、模組名稱、角色
- 技術架構（框架、資料庫、AI 服務）
- 核心業務概念（如 ACWR、Training Plan、Rizo AI）
- 服務之間的依賴關係

彙整後，**一次性**呈現骨架層 proposals（見下方確認 UI），等用戶確認後寫入 Firestore。

### C3. 第二階段：P1 文件 — 讀 + 建 document entry

逐一讀取 P1 文件，為每份建立 document entry：

```
進度：P1 規格文件
  [1/{n}] docs/01-specs/plan-overview-v2.md → 讀取中...
    → upsert_document() ✅  (id: xxx)
  [2/{n}] docs/01-specs/SPEC-weekly-plan-v2.md → ...
```

每份 document entry 包含：
- `title`：從路徑或文件 H1 標題取得
- `source.uri`：如果是 git repo 且有 remote，構建 GitHub URL；否則用 `file://{絕對路徑}`
- `tags.what`：關聯的實體（從文件內容或路徑推斷）
- `tags.why`：這份文件為什麼存在（一句話）
- `tags.how`：文件類型（spec/frd/guide/architecture）
- `tags.who`：目標讀者（開發/PM/行銷）
- `summary`：2-3 句語意摘要——這份文件在知識體系中的定位，不是全文節錄
- `confirmed_by_user = false`（全部先 draft）

### C4. 第三階段：P2/P3 文件 — 快速建 entry（不讀全文）

對 P2/P3 文件，用路徑推斷 metadata，**不讀全文**（速度優先）：

```
進度：P2/P3 文件（快速）
  [1/{n}] docs/02-api/... → entry ✅
  [2/{n}] ...
```

### C5. Summary

```
✅ 首次建構完成：{目錄名稱}

骨架層（entities）：
  • 確認 {n} 個實體（你逐一確認的）
  • Draft {n} 個實體（你略過的，待後續確認）

神經層（documents）：
  • P1 精讀 entry：{n} 個
  • P2/P3 快速 entry：{n} 個

下一步：
  → 呼叫 list_unconfirmed() 查看所有待確認 drafts
  → 呼叫 run_quality_check() 評估 ontology 品質
  → 呼叫 run_blindspot_analysis() 推斷知識盲點
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

每個候選寫入前先 `search_ontology(query=名稱或關鍵詞)` 避免重複：
- 找到且資訊吻合 → 跳過
- 找到但需更新 → 標記「更新」
- 找不到 → 標記「新增」

### Step 3：神經層自動寫入 draft

```
upsert_document(
  title, source, tags, summary,
  linked_entity_ids,
  confirmed_by_user = False
)
```

文件 entry 的 `source.uri`：
- 如果是 GitHub 上的檔案 → 用 GitHub URL
- 如果是本地 git repo 且有 remote → 構建 GitHub URL
- 否則 → `file://{絕對路徑}`

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
  Paceriz → depends_on → Firebase/Firestore
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
待確認：呼叫 list_unconfirmed() 查看
```

---

## 核心原則

- **Why/How 是意圖性維度**：AI 填的 Why/How 一律 draft，不直接 confirmed
- **What/Who 是事實性維度**：AI 準確度高，可直接填入
- **不存原始內容**：只存語意摘要，原文留在來源（Git/Drive）
- **首次建構先骨架後神經**：先確認實體結構，再大量建文件 entry
- **快**：核心價值是在知識產生點捕獲，速度比完美更重要
