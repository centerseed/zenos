---
name: zenos-sync
description: >
  掃描 git log 找出最近變更的文件，比對 ZenOS ontology，批量 propose 更新。
  支援兩種使用情境：(1) 無引數 = 同步當前專案；(2) 目錄路徑 = 同步指定的外部專案。
  輔助知識同步 skill——定期執行或在大量文件變更後使用，讓 ontology 跟上 codebase 節奏。
  當使用者說「同步 ontology」「sync ZenOS」「掃 git 變更」「更新 ontology」「/zenos-sync」，
  或在一批 commits 後想讓 ontology 跟上，或說「幫我同步 {專案名}」時使用。
  注意：第一次為某個專案建立 ontology 請用 /zenos-capture {目錄}，
  /zenos-sync 是為已有 ontology 的專案做增量同步。
version: 3.1.0
---

# /zenos-sync — Git 增量同步

你是 ZenOS 的知識治理 agent。任務：從 **git log** 找出最近的文件變更，
比對現有 ontology，批量 propose 更新，讓 ontology 和 codebase 保持同步。

**適用時機**：已有 ontology 的專案，需要跟上最近的 commits。
**首次建構**：請改用 `/zenos-capture {目錄路徑}`。

---

## Step 0：Source Audit（預設執行）

每次執行 `/zenos-sync` 時先跑 Source Audit。若使用者執行 `/zenos-sync --audit` 或 `/zenos-sync audit`，則只跑 Step 0，不執行後續步驟。

### 0.1 拉取所有有 sources 的項目

```python
mcp__zenos__search(collection="entities", limit=500)
mcp__zenos__search(collection="documents", limit=500)
```

過濾出 `sources` 欄位非空的所有 entity 和 document。

### 0.2 逐項檢查 sources[]

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

### 0.3 產出稽核報告

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

### 0.4 自動修正

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

### 0.5 顯示修正結果摘要

```
修正完成：
  ✅ bad_label 已修正：N 筆
  ✅ broken 已清除：N 筆（其中 M 筆 document 已標記為 archived）
  ✅ renamed 已更新：N 筆
  ⚠️  duplicate 需人工確認：N 筆（見上方清單）
```

---

## Step 0.5：確認目標專案和上次 sync 時間

**確認目標路徑：**
- 有引數（目錄路徑）→ `TARGET = {引數路徑}`，在該目錄執行 git 指令
- 無引數 → `TARGET = 當前工作目錄`

**讀取上次 sync 狀態：**

```bash
cat {TARGET}/.zenos-sync-state.json  # 優先找專案目錄
# 若不存在，找當前目錄的 .zenos-sync-state.json
```

**如果找不到 .zenos-sync-state.json：**
> 這個專案還沒有 sync 記錄。
>
> 選項：
> - 輸入天數（如 `7`）→ 掃最近 N 天的 commits
> - 輸入 `首次建構` → 改用 /zenos-capture 模式掃整個目錄
> - 輸入日期（如 `2026-01-01`）→ 從那天開始掃

**如果找到：**
```
目標專案：{TARGET}
上次 sync：{last_sync}（{距今 N 天前}）
```

---

## Step 1：取得 git 變更清單

```bash
cd {TARGET} && git log --since="{SINCE}" --name-only --pretty=format:"---commit %H%n%s" -- .
```

**過濾掉噪音（不需要 propose）：**
- `.venv/`、`__pycache__/`、`*.pyc`、`node_modules/`、`dist/`
- `*.lock`、`package-lock.json`、`poetry.lock`
- `tests/fixtures/`、`integration_tests/fixtures/`
- `.claude/skills/pm-workspace/`（skill eval 資料）
- `*FIX_REPORT*`、`*VALIDATION_FIX*`、`*CRITICAL_ERRORS_FIX*`（bug fix 記錄）

**如果沒有任何有效變更：**
> 自 {SINCE} 以來沒有影響知識層的新 commits。Ontology 已是最新。

更新 last_sync 後結束。

**顯示掃描摘要：**
```
找到 {N} 個 commits，{M} 個有效文件變更：
  *.md 文件    ：{n} 個
  源碼（*.py等）：{n} 個
  配置文件     ：{n} 個（跳過）
```

---

## Step 2：判斷每個變更對 ontology 的影響

### 高影響（必須處理）

| 路徑模式 | 可能影響 |
|----------|----------|
| `CLAUDE.md`、`README.md` | 骨架層整體描述 |
| `docs/01-specs/`、`docs/*spec*`、`*SPEC*.md` | 功能規格 → 可能新模組/目標 |
| `docs/04-frds/`、`*FRD*.md` | 功能需求 → 可能新 entity |
| `docs/architecture/`、`*ARCHITECTURE*.md` | 架構決策 → 關係圖 |
| `docs/09-agent/`、`naru_agent/` | AI agent 設計 |
| `FIRESTORE_STRUCTURE.md`、`docs/data_schemas/` | 資料結構 |
| `*COMPLETE_REFACTOR*`、`*REFACTOR_SUMMARY*` | 大規模架構變更 |
| `domains/`（新增檔案） | 可能新 domain/module |

### 中影響（選擇性處理）

| 路徑模式 | 處理建議 |
|----------|----------|
| `docs/02-api/`、`api/` 新路由 | 更新 API module entry |
| `docs/guides/`、`docs/services/` | 更新文件 entry |
| `domains/{name}/` 修改 | 更新對應 module entry |

### 低影響（跳過）

- `tests/`、`integration_tests/` — 測試代碼不影響知識層
- `deployment/`、`Dockerfile`、`*.yaml` — 基礎設施
- `requirements.txt`、`pyproject.toml` — 依賴管理

---

## Step 3：比對現有 ontology

對高/中影響文件：

```
search(query=文件路徑關鍵詞 或 commit message 關鍵詞)
→ 找到 entry → 判斷 summary 是否還準確
→ 找不到 → 需要新建 entry
→ commit message 暗示新模組 → 標記為骨架層 proposal
```

commit message 只作輔助訊號，不可取代讀全文；高影響文件必讀全文後再寫入：
- `feat: add ACWR safety check` → 新功能，影響 ACWR module entry
- `refactor: split WeeklyPlan into v2/v3` → 架構變更，可能需要新實體
- `fix: correct ACWR calculation` → bug fix，不需要 propose

---

## Step 4：神經層 — 批量自動寫入 draft

```
進度：神經層更新中...
  [1/5] CLAUDE.md（更新）→ ✅
  [2/5] docs/01-specs/SPEC-weekly-plan-v3.md（新增）→ ✅
  [3/5] domains/training_plan/service.py（跳過，源碼）
  ...
```

**高價值文件（spec/架構/PRD）→ 建 document entity：**
```
write(collection="documents", data={
  title: 從路徑或文件 H1 取得（映射為 entity.name）,
  source: {type: "github", uri: GitHub URL, adapter: "github"},
  tags: {what: [關聯實體名稱], why: "文件目的", how: "spec/frd/guide", who: ["開發", "PM"]},
  summary: 語意摘要,
  linked_entity_ids: [所屬 entity ID]（第一個映射為 parent_id）,
  confirmed_by_user: false
})
```

**低價值文件（guides/雜項）→ 追加到 entity.sources：**
```
write(collection="entities", id={parent_entity_id}, data={
  ...existing fields...,
  append_sources: [{uri: GitHub URL, label: 檔名, type: "github"}]
})
```

**何時讀全文**：高影響文件一律讀全文；中影響文件若 commit message 無法準確判斷才讀全文。

---

## Step 5：骨架層 — 列出等待確認

```
── 骨架層 Proposals（需要你確認）────────────────

[1] 新增實體
  名稱：Weekly Plan V3
  類型：module
  觸發：SPEC-weekly-plan-v3.md 新增（commit: "feat: add v3 weekly plan")
  摘要：第三版週訓練計劃，解決 V2 的 ACWR 衝突問題

[2] 更新實體：ACWR Safety Module
  變更：how 從「計算訓練負荷比值」更新為「整合 V3 衝突解決器」
  觸發：domains/acwr/ 的 3 個 commits

────────────────────────────────────────────────
輸入要確認的編號，或「全部」，或「略過」：
```

---

## Step 6：更新 last_sync

```json
{
  "project": "{TARGET 的絕對路徑}",
  "last_sync": "2026-03-21T10:30:00+08:00",
  "stats": {
    "commits_scanned": 15,
    "files_processed": 8,
    "neural_layer_updated": 6,
    "skeleton_confirmed": 2,
    "skeleton_drafted": 1
  }
}
```

存到 `{TARGET}/.zenos-sync-state.json`（若 TARGET 是外部專案）或 `.zenos-sync-state.json`（當前目錄）。

---

## Step 7：Summary

```
✅ /zenos-sync 完成

專案：{TARGET}
掃描範圍：{SINCE} → 現在（{N} 個 commits，{M} 個有效文件）

神經層（自動 draft）：新增 {n} + 更新 {n}
骨架層：確認 {n} + Draft {n}

下次 sync 從：{現在時間}
→ 呼叫 search(confirmed_only=false) 查看待確認 drafts
→ 呼叫 analyze(check_type="staleness") 偵測過時 entry
```

---

## 注意事項

- **增量，不是全量**：只看 `--since` 以後的變更，避免重複處理
- **commit message 僅輔助**：高影響文件必讀全文；中影響文件可先看 message 再決定是否讀全文
- **外部專案支援**：引數是目錄路徑時，所有 git/file 操作都在那個目錄執行
- **Why/How 一律 draft**：意圖性維度不自動確認
- **首次建構不適用**：沒有 last_sync 記錄時，引導用戶用 `/zenos-capture {目錄}` 代替

---

## MCP Server 驗證規則（違反會被阻擋）

以下規則由 MCP Server 強制執行，write 操作違反時會回傳 ValueError 並告知正確值。

### Entity 命名規則
- **禁止括號標註**：不可用 `"訓練計畫 (Training Plan)"` 或 `"Training Plan Module (iOS)"`
- 長度 2-80 字元，前後空白自動 strip
- 同 type + name 不可重複（Server 會回傳既有 ID，改用 update）

### Entity 必填驗證
- `type`：`product` / `module` / `goal` / `role` / `project` / `document`
- `status`：`active` / `paused` / `completed` / `planned`
- `tags` 必須含四維：`what` / `why` / `how` / `who`
- **Module 的 `parent_id` 強制必填**，且指向的 entity 必須已存在

### Relationship / Blindspot / Document / Protocol / Entry
- Relationship：source/target entity 必須存在，type 必須是合法 enum
- Blindspot：severity 必須是 `red` / `yellow` / `green`，related_entity_ids 必須都存在
- Document：source.type 必須是 `github` / `gdrive` / `notion` / `upload`。linked_entity_ids 盡量帶上（你掃描時知道屬於誰）。寫入前用 source.uri 查重，已存在就跳過
- Protocol：entity_id 必須存在，content 必須含 what/why/how/who
- Entry：entity_id 必須存在，type 必須是 `decision` / `insight` / `limitation` / `change` / `context`，content 上限 200 字元，沒有 confirmed_by_user

### 寫入順序（建議）
1. 先建 product entity → 2. 建 module（帶 parent_id）→ 3. 建 relationships → 4. 建 documents（帶 linked_entity_ids + source.uri 查重）→ 5. 建 entries（帶 entity_id 指向已存在的 L2）

### Sync 不主動產出 entries
Entries 記的是「code 裡沒有的知識」。Sync 的來源是 git log（code 變更），agent 讀 git log 就能看到。Entry 由 `/zenos-capture`（對話捕獲）或 task 完成流程產出。
