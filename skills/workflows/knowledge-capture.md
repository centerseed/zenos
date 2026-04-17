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
version: 2.3.1
---

# /zenos-capture — 知識捕獲 + 首次建構

你是 ZenOS 的知識治理 agent。根據引數自動選擇模式：

> **啟動前先讀 `skills/governance/bootstrap-protocol.md`，完成 Step 0: Context Establishment。**
> 跳過 Step 0 就開始寫入 ontology = 違規操作。
> 若 `skills/governance/bootstrap-protocol.md` 不存在：直接回報「ZenOS 安裝不完整，請先重新執行 /zenos-setup」，不要自行補 Step 0，也不要繼續 ideate。
> 完成 Step 0 後你會有：`PRODUCT_ID`、`PRODUCT_NAME`、`PROJECT_NAME`、`L2_ENTITIES`、`EXISTING_DOCS`。
> 後續所有 `search` / `write` 都帶 `product_id=PRODUCT_ID`。

| 引數 | 模式 | 速度 |
|------|------|------|
| 無引數 | 對話捕獲 | 快（秒） |
| 單一檔案路徑 | 檔案捕獲 | 快（秒） |
| 目錄路徑 | **首次建構模式** | 分鐘級（批量） |

## 意圖分流（新增）

以下情境**不要走 /zenos-capture 主流程**：
- 用戶要「直接改文件內容」「直接把 md 寫到 document」「不經 git 發布內容」。

改走：
- Document Delivery 內容寫入流程（`POST /api/docs/{doc_id}/content`）發布 snapshot。
- capture 只負責知識抽取（entity / entries / relationships / document metadata），不是文件內容編輯器。

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

### C0. 防重複 Gate（不可跳過）

Step 0 已載入 `L2_ENTITIES` 和 `EXISTING_DOCS`。檢查是否已有 ontology：

```python
if len(L2_ENTITIES) > 0 or len(EXISTING_DOCS) > 0:
    # 已有 ontology → 不是首次建構，停下來問用戶
    print(f"""
    ⚠️  產品「{PRODUCT_NAME}」已有 ontology：
      L2 entity：{len(L2_ENTITIES)} 個
      Documents：{len(EXISTING_DOCS)} 個

    選項：
    - 「增量」→ 只處理尚未建立的文件（跳過已有 document 對應的檔案）
    - 「重建」→ 清空後重建（危險，需二次確認）
    - 「取消」→ 改用 /zenos-sync 做增量同步
    """)
    # 等用戶選擇，不自動繼續
```

### C1. 掃描目錄，建立文件清單

```bash
find {目錄} -name "*.md" -not -path "*/.venv/*" -not -path "*/node_modules/*" \
  -not -path "*/__pycache__/*" -not -path "*/.git/*" | sort
```

**讀取專案結構配置（若有）：**

```bash
cat {目錄}/.zenos-project.json 2>/dev/null
```

若有 `.zenos-project.json`，使用其中的 `structure` 定義分組。
若無，使用以下**通用啟發式**（基於檔名 pattern，不依賴特定路徑結構）：

**P0 — 骨架層種子（必讀，用來建實體）**
檔名符合：`CLAUDE.md`、`README.md`、檔名含 `OVERVIEW`/`ARCHITECTURE`/`STRUCTURE`

**P1 — 規格文件（讀 + 建 document entry）**
檔名含 `SPEC`/`FRD`/`PLAN`，或在名為 `specs`/`plans`/`architecture` 的目錄下

**P2 — 功能/整合文件（建 document entry，選擇性讀）**
在名為 `api`/`guides`/`services`/`integrations`/`models` 的目錄下

**P3 — 其餘文件（只建 entry，不讀全文）**
其他 `.md`

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
- description 格式：「A 改了{什麼}→ B 的{什麼}要跟著看」
- 說不出具體場景的關係 = noise，不該建

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

Relationship 寫入時：
- `type` 可以是 `impacts`、`depends_on`、`part_of`、`enables`
- `description` 必須具體——不是「A 依賴 B」，是「A 改了{什麼}→ B 的{什麼}要跟著看」

### C3.5 從核心文件識別 entry 候選

讀完 P0+P1 文件後，如果文件中包含具體的決策脈絡、已知限制、技術約束等 code 裡看不到的知識，按 Step 3.5 的撈→比對→寫入流程產出 entries，掛到對應的 L2 entity。

注意：首次建構時大部分知識會進 L2 summary 或 document，只有符合 entry 嚴格判斷標準（通過兩關）的才記成 entry。

### C4. 第三階段：P1 文件 — 建 document entry

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

知識條目（entries）：
  • {n} 個 entries（decision/insight/limitation/change/context）

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

### Step 0.5：查 Impact Chain 確定知識歸屬（如涉及具體模組）

**捕獲到的知識應該掛到哪個 entity？用 impact_chain 判斷：**

```python
# 先搜尋最可能相關的 entity
mcp__zenos__search(query="<知識相關關鍵字>", collection="entities")

# 取得候選 entity 的 impact_chain
mcp__zenos__get(collection="entities", name="<候選模組>")
```

**Impact chain 輔助歸屬判斷：**
- 如果知識涉及「A 改了影響 B」→ 查 A 的 impact_chain 確認 B 是否在下游；若是，知識掛到 A（source），不是 B
- 如果知識是 entry（decision/insight/change）→ 掛到 impact_chain 上最上游的相關 entity
- 如果知識涉及新 relation → 查兩端的 impact_chain 確認新 relation 不重複既有路徑

**例外：** MCP 不可用或知識不涉及具體模組時跳過。

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

**知識條目候選（自動寫入，不需確認）**：

對已存在的 L2 entity，識別對話/文件中 **code 裡不存在** 的知識：

| entry type | 識別信號 | 好的範例 |
|-----------|---------|---------|
| `decision` | 「決定用 X 不用 Y」「選擇了 A 方案」 | 「supersede 要先建新 entry 再更新舊的，因為 FK constraint 要求 superseded_by 指向已存在的 ID」 |
| `insight` | 「發現…」「原來…」「踩坑後的認知」 | 「Garmin 心率在跑步前 3 分鐘不穩定，選型指標時不能依賴早期心率數據」 |
| `limitation` | 「但是…」「限制是…」「已知問題」 | 「Weekly Summary LLM 呼叫偶爾回傳非法 JSON，目前靠 retry + fallback parser 處理」 |
| `change` | 「改成…」「從 X 改為 Y」「不再…」 | 「recovery week 從三級改兩級，因為舊的 light 級跟 weekly plan v2 定義衝突」 |
| `context` | 「當初是因為…」「背景是…」 | 「entity_entries 的 content 限制 200 字元是因為 100 中文字足夠表達一個知識點」 |

**判斷標準（必須同時通過兩關才記）：**

**第一關：排除** — 以下任一成立就不記：
- 已經寫在 ADR / spec / 文件裡 → 文件是 SSOT，entry 不重複文件
- 產品原則、願景、定位 → 屬於 entity summary 或 tags，不是具體知識點
- 實作事實（code / git history 看得到）→ agent 自己能拿到
- 太抽象的 insight（對具體工作沒有指引作用）→ 聽起來對但用不上

**第二關：確認價值** — entry 必須能回答這個問題：
「某個 agent 或同事下次碰到這個 L2 相關的工作時，看到這條 entry 會改變他的行為嗎？」
會 → 記。不會 → 不記。

若找不到任何候選，回覆：
> 這段對話/文件沒有發現值得捕獲的新知識。如果你認為有遺漏，告訴我哪個部分值得存入。

### Step 2：比對現有 ontology

每個候選寫入前先 `search(query=名稱或關鍵詞)` 避免重複：
- 找到且資訊吻合 → 跳過
- 找到但需更新 → 標記「更新」
- 找不到 → 標記「新增」

### Step 3：神經層自動寫入 draft

```
# 寫入前雙重查重（兩種都要查，任一命中就跳過）：
# 1. 用 source.uri 查：search(collection="documents", query="{source.uri}", product_id=PRODUCT_ID)
# 2. 用檔名查：search(collection="documents", query="{檔名}", product_id=PRODUCT_ID)
# 所有查重都必須帶 product_id，避免跨產品誤判。兩種查重都沒命中才建立新 document。
write(collection="documents", data={
  title, source, tags, summary,
  doc_role: "index",   # ← 新建預設一律 index
  linked_entity_ids,   # ← 必填，不可省略（見下方說明）
  confirmed_by_user: False
})
```

> **linked_entity_ids 必帶，不可省略**：你在掃描時已經知道這份文件跟哪個 entity 相關，直接帶上。
> 如果不確定歸屬，**必須先 `search(collection="entities", query="{文件關鍵字}")` 找最相關的 L2 entity**，選最佳匹配。
> 真的找不到任何相關 entity → 停下來告知用戶，不要建立 `parent_id: null` 的孤兒 document。

> **bundle-first 規則**：新建 document 時，預設必須用 `doc_role="index"`，即使目前只有 1 份 source 也一樣。
> 只有在你能明確說出為什麼這份文件應獨立治理、而不是成為某個 L2 的文件入口時，才可建立 `single`。

建立或更新 index document 後，**同輪必做**：

```python
write(collection="documents", data={
  "doc_id": "...",
  "bundle_highlights": [
    {
      "source_id": "<primary-source-id>",
      "headline": "這是這個主題最先該讀的文件",
      "reason_to_read": "一句話說明這份文件的角色，例如 SSOT / 最新決策 / AC 定義",
      "priority": "primary"
    }
  ]
})
```

**最低要求**：
- 至少 1 筆 `priority="primary"`
- `headline` 要回答「這份文件最值得看的點」
- `reason_to_read` 要回答「為什麼現在先讀它」
- 不得只建立 document metadata 而不補 `bundle_highlights`

若找到同主題既有 document：
- 已是 `index` → `add_source` 到既有 bundle，並更新 `bundle_highlights`
- 是 `single` 且屬同一主題 → 優先升級為 `index`，不要再新增平行 single

文件 entry 的 `source.uri`（**必須嚴格遵守**）：

構建 GitHub URL 的步驟（**每個檔案都必須獨立執行，不可共用結果**）：

```bash
# 必須先 cd 到檔案所在目錄——不同子目錄可能屬於不同 git repo
cd "$(dirname "$FILE_PATH")"

# 1. 取 remote URL
git remote get-url origin

# 2. 從 remote URL 解析 owner/repo
#    例：https://github.com/centerseed/havital.git → centerseed/havital

# 3. 取 git root（必須在檔案目錄內執行，不可在 capture 目標目錄或父目錄）
GIT_ROOT=$(git rev-parse --show-toplevel)

# 4. 算相對路徑
#    FILE_PATH - GIT_ROOT = 相對路徑

# 5. 取預設分支
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null  # fallback → main

# 6. 組合
#    https://github.com/{owner}/{repo}/blob/{branch}/{相對路徑}

# 7. 驗證檔案在 git 追蹤中（防止寫入指向未 push 檔案的 URL）
git ls-files --error-unmatch "{相對路徑}" 2>/dev/null || echo "WARNING: 檔案未被 git 追蹤"

# 8. 驗證 remote 可見性（防止「本地有、別人找不到」）
#    先檢查 remote 預設分支是否已存在該 path
git cat-file -e "origin/{branch}:{相對路徑}" 2>/dev/null || echo "INFO: remote 預設分支尚未看到這個檔案"
#    若檔案不在 remote 預設分支，至少還要確認本地 HEAD 是否已 push 到 upstream
git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "INFO: 目前分支沒有 upstream"
git merge-base --is-ancestor HEAD @{u} 2>/dev/null || echo "INFO: 本地 HEAD 尚未完整 push 到 upstream"
```

**禁止**：
- 從目錄名推斷 repo 名稱
- 在批量處理時對所有檔案共用同一個 git root（子目錄可能是 submodule 或獨立 repo）
- 省略 `cd` 步驟直接用 capture 目標目錄的 git context

若無 git remote → `file://{絕對路徑}`（並在 summary 中標記）

### Step 3.5：知識條目 — 撈、比對、寫入

對 Step 1 識別的每個知識條目候選，執行以下流程：

**3.5a. 撈現有 entries**

```
# 確認目標 L2 entity 存在
search(collection="entities", query="{相關 L2 名稱}")

# 撈該 L2 的所有 active entries
search(collection="entries", entity_id="{L2 entity ID}", status="active")
```

**3.5b. LLM 比對候選 vs 現有 entries**

拿到現有 entries 後，逐條比對候選內容：

| 比對結果 | 判斷標準 | 動作 |
|---------|---------|------|
| **完全重複** | 現有 entry 已說了同樣的事（語意相同，不只是字面相同） | 跳過，不寫 |
| **同主題有新資訊** | 現有 entry 講同一件事，但候選包含更完整/更新的描述 | supersede 舊 entry + 寫新 entry |
| **矛盾（決策被推翻）** | 現有 decision 說用 A，候選 decision 說改用 B | supersede 舊 entry + 寫新 entry |
| **全新知識** | 現有 entries 裡沒有相關內容 | 直接寫入新 entry |

**3.5c. 執行寫入**

```
# 情況 1：全新 → 直接寫
write(collection="entries", data={
  entity_id: "{L2 entity ID}",
  type: "decision",
  content: "選 VDOT 不選心率區間，因為 Garmin 心率前幾分鐘不穩",
  context: "在評估了三種方案後做出的決定",  # 可選
  author: "{發言者或 agent}"
})

# 情況 2：supersede → 先建新的（拿到 ID），再更新舊的
new_entry = write(collection="entries", data={
  entity_id: "{L2 entity ID}",
  type: "decision",
  content: "改用方案 B，因為方案 A 在大流量下效能不足",
  author: "{發言者或 agent}"
})
write(collection="entries", id="{舊 entry ID}", data={
  status: "superseded",
  superseded_by: new_entry.id
})
```

**寫入規則**：
- 一條 entry 只掛一個 entity。如果一個決策影響多個 L2，為每個 L2 各寫一條，從該 L2 的角度描述
- 語意比對由 client LLM 執行（server 小模型無法可靠判斷語意重複）

**呈現格式**（在 Step 4 骨架層 proposals 之前列出，不需要用戶確認）：

```
── 知識條目 ────────────────────────────────────
  [E1] 新增 limitation → 訓練閉環分析
    「Weekly Summary LLM 偶爾回傳非法 JSON，靠 retry + fallback parser 處理」
  [E2] supersede decision → 跑步科學指標
    舊：「用三級 recovery week」→ 新：「改兩級，舊的 light 級跟 weekly plan v2 衝突」
  [--] 跳過 1 條重複（訓練閉環分析 已有相同 limitation）
────────────────────────────────────────────────
```

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

知識條目（自動寫入）：
  • [decision] {content 摘要} → {L2 entity 名稱}
  • [insight] {content 摘要} → {L2 entity 名稱}
神經層（自動 draft）：• {文件標題} → documents/{id}
骨架層（你確認的）：• {實體名稱} → entities/{id}
待確認：呼叫 search(confirmed_only=false) 查看
```

**寫入 Work Journal（模式 A/B/C 完成後都要做）：**

先查：
```python
mcp__zenos__journal_read(limit=20, project="{專案名}")
# 同來源/同產品是否已有 capture 筆記
# → 有：新 summary 整合兩次的知識狀態，讓舊筆記變冗餘
# → 沒有：正常新增
```

```python
mcp__zenos__journal_write(
    summary="capture {來源描述}：{捕獲的關鍵知識點或概念}；{待補建的 entity 或遺留 TBD}",
    project="{專案名}",
    flow_type="capture",
    tags=["{產品名}"]
)
```

> 不要只寫數量（`{n} 個 entities`）——下次讀到沒有 context。寫「捕獲了什麼」和「還缺什麼」。

**compressed 觸發蒸餾（journal_write 有回傳 `compressed: true` 時執行）：**

**Step A：取 summary journal**
```python
mcp__zenos__journal_read(project="{專案名}", limit=5)
# 找 is_summary=true 的最新一筆（即剛產生的 summary journal）
```

**Step B：對 summary journal 執行 Step 3.5 蒸餾**

以 summary journal 的 `summary` 欄位內容為輸入，執行本 skill 的「Step 3.5：知識條目 — 撈、比對、寫入」流程（判斷標準與步驟完全相同，輸入來源改為 summary journal）。

**Step C：呈現蒸餾結果**

呈現格式如下（不需要用戶確認，直接執行）：

```
── Entry 蒸餾（journal 壓縮觸發）────────────────
  [E1] 新增 {type} → {L2 entity 名稱}
    「{content}」
  [E2] ...
  [--] 跳過 {n} 條（重複或不符兩關標準）
────────────────────────────────────────────────
```

壓縮未觸發（`compressed: false`）時跳過以上步驟，行為與現有完全相同。

---

## 核心原則

- **意圖性 vs 事實性維度**：Why/How 是意圖性維度，AI 填的一律 draft；What/Who 是事實性維度，AI 可直接填入
- **Documents 預設不存原始內容（metadata-first）**：capture 預設只存 document metadata 與語意摘要，原文留在來源（Git/Drive）
- **例外：Delivery 直寫模式可存 markdown snapshot**：若用戶明確要求直接發布內容，可走 Document Delivery 內容寫入流程（GCS private revision）
- **current 文件改成 delivery-first**：若某份 L3 document 是正式入口或會被直接分享，應補 ZenOS Reader / snapshot，不要只留 GitHub URL
- **GitHub source 要驗 remote 可見性**：本地存在、git tracked 都還不夠；若檔案或 commit 尚未 push，其他人依舊找不到，不能宣稱 source 可分享
- **agent 自動判斷 git / gcs**：這不是給用戶選的；capture 預設先走 `git`，但對 `current formal-entry` 自動補 `gcs snapshot`
- **首次建構先骨架後神經**：先確認實體結構，再大量建文件 entry
- **快，且只記 code 裡沒有的知識**：速度比完美重要。Entry 記決策脈絡、已知限制、重要變更——agent 讀 code 拿不到的東西
- **100 字一個知識點**：entry content 上限 200 字元（~100 中文字）。寫不下代表要拆或粒度太大
- **Entry 不需要確認**：建了就是 active，沒有 draft→confirmed。品質靠 server 端 Internal 治理 API

---

## MCP Server 驗證規則（違反會被阻擋）

以下規則由 MCP Server 強制執行，write 操作違反時會回傳 ValueError 並告知正確值。

### Entity
- **命名**：禁止括號標註，長度 2-80 字元，同 type+name 不可重複（重複時回傳既有 ID）
- **必填**：`type`（product/module/goal/role/project）、`status`（active/paused/completed/planned）、`tags`（四維 what/why/how/who）
- **Module 的 `parent_id` 強制必填**，指向的 entity 必須已存在

### Relationship
- source/target entity 必須存在，`type`：`depends_on`/`serves`/`owned_by`/`part_of`/`blocks`/`related_to`/`impacts`/`enables`
- L2 概念之間優先用 `impacts` 和 `enables`

### Document / Blindspot / Protocol
- Document：`source.type`（github/gdrive/notion/upload）必填，`linked_entity_ids` 盡量帶，寫入前用 `source.uri` 查重；若 status=`current` 且作為正式入口，應補 delivery snapshot
- Document（github）：若文件要被其他人直接從 source 讀取，還必須確認 remote 可見；未 push 時要明講 `local-only`，不得把該 URL 當正式可分享入口
- Blindspot：`severity`（red/yellow/green）必填，`related_entity_ids` 必須都存在
- Protocol：`entity_id` 必須存在，`content` 必須含四維 what/why/how/who

### Entry
- `entity_id` 必須存在，`type`：decision/insight/limitation/change/context
- `content` 必填（上限 200 字元），`context` 可選（上限 200 字元）
- `status`：active/superseded/archived（superseded 時 `superseded_by` 必填）
- 沒有 `confirmed_by_user`，建了就是 active
