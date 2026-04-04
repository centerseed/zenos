---
name: zenos-sync
version: 3.1.0
---

# Git 增量同步工作流程

## 前提條件

- MCP 已連線（`mcp__zenos__search` 可正常呼叫）
- 當前目錄是 git repo，或已指定外部專案路徑
- 專案已有初始 ontology（首次建構請用 `/zenos-capture {目錄}`）

## 步驟

Step 0 預設在每次執行時先跑。若使用者執行 `/zenos-sync --audit` 或 `/zenos-sync audit`，則只跑 Step 0，不執行後續 Step 1–6。

### Step 0：Source Audit（預設執行）

#### 0.1 拉取所有有 sources 的項目

```python
mcp__zenos__search(collection="entities", limit=500)
mcp__zenos__search(collection="documents", limit=500)
```

過濾出 `sources` 欄位非空的所有 entity 和 document。

#### 0.2 逐項檢查 sources[]

對每個項目的每一筆 source，依序做三項檢查：

**a. label 檢查（bad_label）**

條件：`label == "github"` 或 `label` 為空字串或 null

修正方式：從 URI 尾段提取正確檔名。
- 例：`https://github.com/.../blob/main/docs/SPEC-agent-system.md` → `SPEC-agent-system.md`
- 例：`github:docs/SPEC-agent-system.md` → `SPEC-agent-system.md`

分類為 `bad_label`，記錄原 label 和建議修正值。

**b. URI 有效性檢查（broken / renamed）**

僅對 `type=github` 且本地有對應 repo 的 source 執行。

```bash
# 從 URI 提取 path 部分，然後檢查是否存在
git ls-files -- {path}

# 若不存在，嘗試找改名記錄
git log --follow --diff-filter=R --summary -- {path}
```

- 檔案存在 → 跳過
- 檔案不存在，且 `git log --follow` 找到新路徑 → 分類為 `renamed`，記錄舊 URI 和新路徑
- 檔案不存在，且找不到改名記錄 → 分類為 `broken`

**c. 重複 source 檢查（duplicate）**

在同一 parent entity 的所有 document 中，找出多筆 source 指向相同 URI 的情況。
分類為 `duplicate`，列出所有重複項（entity id + document id + URI）。

#### 0.3 產出稽核報告

直接輸出到用戶：

```
Source Audit 結果
─────────────────────────────────
🔴 broken:    N 筆 — URI 指向已刪除的檔案（將自動清除）
🟡 bad_label: N 筆 — label 將自動修正
🟠 renamed:   N 筆 — URI 將自動更新為新路徑
🟠 duplicate: N 筆 — 列出重複項供參考（不自動處理）
✅ healthy:   N 筆
```

重複項列表範例：
```
duplicate 清單：
  - entity "定價模型" → documents [doc-uuid-A, doc-uuid-B] 均指向 docs/SPEC-pricing.md
```

#### 0.4 自動修正

依序執行修正，每筆修正後記錄結果：

**bad_label**：更新 source 的 label 為從 URI 提取的檔名
```python
mcp__zenos__write(
  collection="documents",  # 或 "entities"
  data={
    "id": "{item-id}",
    "sources": [/* 更新後的 sources 陣列，label 已修正 */]
  }
)
```

**broken**：移除該 source
- 若該 source 是 document 的唯一 source → 同時將 document status 改為 `archived`
- 若 document 還有其他 source → 僅移除該筆 source

```python
mcp__zenos__write(
  collection="documents",
  data={
    "id": "{doc-id}",
    "sources": [/* 移除 broken source 後的陣列 */],
    "status": "archived"  # 僅在唯一 source 被移除時加入
  }
)
```

**renamed**：更新 URI 和 label 為新路徑
```python
mcp__zenos__write(
  collection="documents",
  data={
    "id": "{doc-id}",
    "sources": [/* URI 更新為新路徑，label 更新為新檔名 */]
  }
)
```

**duplicate**：只報告，不自動處理。

#### 0.5 顯示修正結果摘要

```
修正完成：
  ✅ bad_label 已修正：N 筆
  ✅ broken 已清除：N 筆（其中 M 筆 document 已標記為 archived）
  ✅ renamed 已更新：N 筆
  ⚠️  duplicate 需人工確認：N 筆（見上方清單）
```

---

### Step 1：掃描 git log 找最近變更

**1a. 一般變更（新增/修改）**

```bash
git log --name-only --since="30 days ago" -- "docs/**/*.md" "src/**/*.py"
```

列出最近 30 天修改過的文件清單。若指定外部專案路徑，先 `cd` 至該目錄再執行。

**1b. 搬移/改名偵測（rename/move）**

```bash
git log --since="30 days ago" --diff-filter=R -M --summary -- "docs/**/*.md"
```

找出被搬移或改名的文件。特別注意以下模式：

- **搬入 `archive/` 或 `docs/archive/`** → 該文件已被歸檔，ontology document 必須同步：
  1. 將 document status 改為 `archived`
  2. 清除該 document 的 sources（因為原路徑已失效）
  3. 如果 document 有 linked entity，entity 的 sources 中指向該檔案的條目也要清除

- **搬移到其他目錄（非 archive）** → 更新 source URI 和 label 為新路徑

```python
# 歸檔範例
mcp__zenos__write(
  collection="documents",
  id="{doc-id}",
  data={
    "status": "archived",
    "sources": []
  }
)
```

### Step 2：讀取變更文件

對每個變更文件：
1. 讀取文件內容（或 frontmatter）
2. 取得 `doc_id`、`type`、`status` 等欄位
3. 識別文件中新出現的概念

### Step 3：比對現有 ontology

```python
# 查詢文件是否已有對應 entity
mcp__zenos__search(collection="documents", query="doc_id:ADR-001-postgresql")

# 查詢概念是否已存在
mcp__zenos__search(collection="entities", query="定價模型")
```

比對規則：
- git 有修改 + ZenOS status=draft → 建議更新為 `under_review`
- git 有新文件 + ZenOS 無 entity → 建議建立新 entity
- git 文件已刪除 + ZenOS status=approved → 建議改為 `archived`
- git 有新概念 + ZenOS 無對應 L2 → 走分層路由判斷（見 `knowledge-capture.md`）

### Step 4：取得現有 entity 詳情

```python
mcp__zenos__get(collection="entities", id="entity-uuid-here")
mcp__zenos__get(collection="documents", id="doc-uuid-here")
```

確認現有內容後，決定更新範圍。

### Step 5：批量 propose 更新

```python
# 更新 document entity 狀態
mcp__zenos__write(
  collection="documents",
  data={
    "doc_id": "ADR-001-postgresql",
    "status": "under_review"
  }
)

# 建立新 L3 document（文件新增）
mcp__zenos__write(
  collection="documents",
  data={
    "doc_id": "SPEC-pricing-v2",
    "title": "定價模型規格 v2",
    "type": "SPEC",
    "ontology_entity": "定價模型",
    "status": "draft",
    "source": {"uri": "docs/SPEC-pricing-v2.md"}
  }
)

# 更新 L2 entity summary（概念有重大變更時）
mcp__zenos__write(
  collection="entities",
  data={
    "id": "entity-uuid-here",
    "summary": "更新後的概念描述"
  }
)
```

### Step 6：confirm 提交

```python
mcp__zenos__confirm(batch_id="...", action="approve")
```

## MCP Tools 使用

- `mcp__zenos__search(collection=..., query=...)` — 查詢現有 entity，比對 ontology
- `mcp__zenos__get(collection=..., id=...)` — 取得單一 entity 詳情
- `mcp__zenos__write(collection=..., data=...)` — 批量 propose 更新
- `mcp__zenos__confirm(batch_id=..., action=...)` — 確認或拒絕批量操作

## 注意事項

- 本 workflow 是增量同步，不是全量重建；首次建構 ontology 請用 `/zenos-capture {目錄}`
- 只處理 git 追蹤的文件，不掃描未 commit 的變更
- 同步範圍預設 30 天；若距上次同步超過 30 天，需手動調整 `--since` 參數
- 若指定外部專案路徑，確認該路徑是 git repo 且有足夠讀取權限
