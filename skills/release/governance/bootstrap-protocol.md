# Step 0: Context Establishment Protocol

> **ADR-016** 定義。所有治理 skill（capture / sync / governance）在開始操作前**必須完成此協議**。
> 跳過任何一步就不可以開始寫入 ontology。

---

## 0a. 確認目標產品

```python
# 從目錄名、CLAUDE.md、README.md、或用戶指定推斷產品名稱
mcp__zenos__search(collection="entities", query="{產品名}", entity_level="L1")
```

- 找到 level=1 且無 parent 的 L1 entity → 記下 `PRODUCT_ID` 和 `PRODUCT_NAME`
- 找不到 → **停下來問用戶**：「找不到產品 {名稱}，要先建立嗎？」
- 用戶確認後才建立 product entity，拿到 `PRODUCT_ID`

**禁止**：在沒有確認 product entity 的情況下開始建立 L2/document/entry。

---

## 0b. 載入現有 Ontology 快照

```python
# 拉該產品下所有 L2 entity（查重 + parent 歸屬用）
L2_ENTITIES = mcp__zenos__search(
    collection="entities",
    product_id=PRODUCT_ID,
    entity_level="L2"
)

# 拉該產品下所有 documents（查重用）
EXISTING_DOCS = mcp__zenos__search(
    collection="documents",
    product_id=PRODUCT_ID
)

# 讀產品近期變更；journal 只作 fallback
RECENT_UPDATES = mcp__zenos__recent_updates(product_id=PRODUCT_ID, limit=10)
RECENT_JOURNALS = mcp__zenos__journal_read(limit=5, project=PROJECT_NAME)  # optional fallback only
```

**目的：** 讓 Agent 在開始操作前就知道「這個產品已經有什麼」。不載入就開始操作 = 盲目操作。

### Context Happy Path（不要猜查法）

當使用者只給「功能 / 模組 / 問題」關鍵字時，照以下順序拿 context：

```python
# 1. 近期變更：先看最近真正改過什麼
mcp__zenos__recent_updates(product_id=PRODUCT_ID, topic="{關鍵字}", limit=10)

# 2. 任務：若是交付/修復/驗收，先找可執行單位
mcp__zenos__search(collection="tasks", query="{關鍵字}", status="todo,in_progress,review", product_id=PRODUCT_ID)

# 3. L2：找穩定概念入口
mcp__zenos__search(collection="entities", query="{關鍵字}", product_id=PRODUCT_ID, entity_level="L2", include=["summary", "tags"])

# 4. L2 詳情：拿 relationships / entries，確認上下游與 durable knowledge
mcp__zenos__get(collection="entities", name="{最相關 L2}", include=["summary", "relationships", "entries"])

# 5. L3 文件入口：從 L2 找文件群 summary，不直接亂搜全文
mcp__zenos__search(collection="documents", entity_name="{最相關 L2}", include=["summary"], limit=10)

# 6. 需要原文時才讀 source
mcp__zenos__get(collection="documents", id="{doc_id}")
mcp__zenos__read_source(doc_id="{doc_id}")
```

只在以上來源仍不足以恢復脈絡時，才讀 `journal_read(limit=5, project=PROJECT_NAME)`。

**載入後輸出摘要（可選，建議對新用戶顯示）：**

```
產品：{PRODUCT_NAME}（ID: {PRODUCT_ID}）
現有 L2 entity：{n} 個
現有 Documents：{n} 個
近期變更：{recent_updates 摘要；若不足再看 journal fallback}
```

---

## 0c. 確認本地環境一致性

**僅對需要讀取本地 git 的操作執行**（capture Mode B/C、sync）。
對話捕獲（capture Mode A）跳過此步。

```bash
cd {TARGET}

# 1. 拉最新 ref（不 pull，不改本地 working tree）
git fetch origin 2>/dev/null

# 2. 檢查本地狀態
git status --short

# 3. 記錄環境參數（後續 source URI 構建使用）
GIT_REMOTE=$(git remote get-url origin 2>/dev/null)
GIT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
```

**檢查項：**

| 狀況 | 處理 |
|------|------|
| `git fetch` 失敗（無網路） | 警告用戶：Source Audit 和 URI 驗證可能不準確 |
| 有大量未 commit 的變更 | 警告：這些檔案不在 git 追蹤中，capture 產生的 URI 可能指向不存在的檔案 |
| HEAD 是 detached | 警告：不在任何 branch 上，source URI 的 branch 部分可能不正確 |
| 無 git remote | source URI 使用 `file://` 格式，在 summary 中標記 |

---

## 0d. 設定 Scope 參數

所有後續的 `search` / `write` / `journal_write` 都必須帶以下參數：

```python
SCOPE = {
    "product_id": PRODUCT_ID,      # 0a 確認的
    "product": PRODUCT_NAME,        # 0a 確認的
    "project": PROJECT_NAME         # 從目錄名或用戶指定
}
```

**使用方式：**

```python
# search 帶 product scope
mcp__zenos__search(query="...", product_id=SCOPE["product_id"])

# write document 帶 linked_entity_ids（從 0b 載入的 L2 entities 中匹配）
mcp__zenos__write(collection="documents", data={
    ...,
    "linked_entity_ids": [best_matching_l2_entity_id]
})

# journal 帶 project
mcp__zenos__journal_write(summary="...", project=SCOPE["project"])
```

**禁止：** 在 Step 0 完成前呼叫任何 `write` 操作。

---

## 首次建構防重複 Gate（capture Mode C 專用）

在 Mode C 的掃描目錄前，根據 0b 載入的快照判斷：

```python
if len(L2_ENTITIES) > 0 or len(EXISTING_DOCS) > 0:
    # 已有 ontology → 不是首次建構
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

---

## Sync State 恢復（sync 專用）

**廢棄** `.zenos-sync-state.json`，從 journal 恢復上次 sync 時間：

```python
result = mcp__zenos__journal_read(project=SCOPE["project"])
# journal_read 回傳 {entries: [...], count: int, total: int}
last_sync_journal = next(
    (j for j in result["entries"]
     if j.get("flow_type") == "sync"),
    None
)

if last_sync_journal:
    # 從 tags 中提取 "until:..." 或用 created_at
    SINCE = last_sync_journal["created_at"]
else:
    # 無 sync 記錄 → 問用戶
    print("這個專案還沒有 sync 記錄。輸入天數、日期、或「首次建構」。")
```

**遷移：** 若發現本地 `.zenos-sync-state.json` 存在，讀取其 `last_sync`，寫入 journal 後刪除。

---

## 專案結構配置

capture Mode C 掃描時，優先讀取專案自定義配置：

```bash
cat {TARGET}/.zenos-project.json 2>/dev/null
```

```jsonc
// .zenos-project.json（可選）
{
  "product": "Paceriz",
  "structure": {
    "p0_seeds": ["CLAUDE.md", "README.md", "*OVERVIEW*", "*ARCHITECTURE*"],
    "p1_specs": ["docs/specs/**", "**/*SPEC*.md", "**/*FRD*.md"],
    "p2_features": ["docs/api/**", "docs/guides/**"],
    "skip": ["tests/**", "node_modules/**", ".venv/**"]
  }
}
```

**若無配置檔，使用通用啟發式**（基於檔名 pattern，不依賴特定路徑結構）：

| 分類 | 匹配規則 |
|------|---------|
| P0 種子 | `CLAUDE.md`、`README.md`、檔名含 `OVERVIEW`/`ARCHITECTURE`/`STRUCTURE` |
| P1 規格 | 檔名含 `SPEC`/`FRD`/`PLAN`，或在名為 `specs`/`plans`/`architecture` 的目錄下 |
| P2 功能 | 在名為 `api`/`guides`/`services`/`integrations`/`models` 的目錄下 |
| P3 其餘 | 其他 `.md` 檔案 |
| Skip | `tests/`、`integration_tests/`、`.venv/`、`node_modules/`、`*FIX_REPORT*`、`*VALIDATION_FIX*` |

---

## 引用方式

各 skill 在開頭加上：

```markdown
> **啟動前先讀 `skills/governance/bootstrap-protocol.md`，完成 Step 0: Context Establishment。**
> 跳過 Step 0 就開始寫入 ontology = 違規操作。
```
