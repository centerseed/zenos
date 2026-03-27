---
type: SKILL
id: knowledge-sync
status: Draft
ontology_entity: TBD
created: 2026-03-27
updated: 2026-03-27
---

> 權威來源：本文件是 `/zenos-sync` 操作流程的 SSOT。
> `.claude/skills/zenos-sync/SKILL.md` 為舊格式，以本文件（`skills/workflows/knowledge-sync.md`）為準。

# knowledge-sync — Git 增量同步

你是 ZenOS 的知識治理 agent。任務：從 **git log** 找出最近的文件變更，
比對現有 ontology，批量 propose 更新，讓 ontology 和 codebase 保持同步。

**適用時機**：已有 ontology 的專案，需要跟上最近的 commits。
**首次建構**：請改用 `knowledge-capture`（`/zenos-capture {目錄路徑}`）。

---

## Step 0：確認目標專案和上次 sync 時間

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

利用 **commit message** 推斷變更的 why/how，比讀全文快：
- `feat: add ACWR safety check` → 新功能，影響 ACWR module entry
- `refactor: split WeeklyPlan into v2/v3` → 架構變更，可能需要新實體
- `fix: correct ACWR calculation` → bug fix，不需要 propose

---

## Step 4：神經層 — 批量自動寫入 draft

> 文件 entry 的治理合規規則見 `skills/governance/document-governance.md`

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

**何時讀全文**：commit message 不夠清楚 + 這是高價值文件時，才讀全文。

---

## Step 5：骨架層 — 列出等待確認

> L2 概念判斷標準與 impacts 撰寫規則見 `skills/governance/l2-knowledge-governance.md`

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
- **commit message 優先**：先用 message 推斷，讀全文是最後手段
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
- `type`：`product` / `module` / `goal` / `role` / `project`
- `status`：`active` / `paused` / `completed` / `planned`
- `tags` 必須含四維：`what` / `why` / `how` / `who`
- **Module 的 `parent_id` 強制必填**，且指向的 entity 必須已存在

### Relationship / Blindspot / Document / Protocol
- Relationship：source/target entity 必須存在，type 必須是合法 enum
- Blindspot：severity 必須是 `red` / `yellow` / `green`，related_entity_ids 必須都存在
- Document：source.type 必須是 `github` / `gdrive` / `notion` / `upload`。linked_entity_ids 盡量帶上（你掃描時知道屬於誰）。寫入前用 source.uri 查重，已存在就跳過
- Protocol：entity_id 必須存在，content 必須含 what/why/how/who

### 寫入順序（建議）
1. 先建 product entity → 2. 建 module（帶 parent_id）→ 3. 建 relationships → 4. 建 documents（帶 linked_entity_ids + source.uri 查重）
