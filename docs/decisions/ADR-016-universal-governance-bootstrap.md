---
type: ADR
id: ADR-016
status: Approved
l2_entity: 語意治理 Pipeline
created: 2026-04-08
updated: 2026-04-08
approved: 2026-04-08
---

# ADR-016: 通用治理啟動協議——讓不同用戶得到同樣的治理效果

## Context

ZenOS 的治理 skill（capture / sync / governance）在「Barry 的 Mac 操作自己的專案」時運作良好，但當其他用戶在不同電腦使用時，出現系統性治理缺失：

**已發生的事故：**
- 不同電腦 capture 同一專案，產出錯誤的 GitHub source URI（git root 判斷錯誤）
- 同一份文件被兩次 capture 各建一個 document（URI 不同導致查重失敗）
- Document 被建立時缺少 `linked_entity_ids`，產生 `parent_id: null` 的孤兒節點

**根因分析：** 問題不是個別 bug，而是 skill 的設計假設只適用於單一用戶、單一裝置：

| 隱含假設 | 多用戶現實 |
|----------|-----------|
| 只有一台電腦操作 | 多裝置、多用戶，可能同時操作 |
| 本地 git = 真實狀態 | 本地可能沒 pull/push，branch 不同 |
| 操作者知道 ontology 全貌 | 新用戶不知道已有哪些 entity |
| 專案結構跟 Havital 類似 | 每個專案的目錄結構不同 |
| 一個 workspace 一個產品 | 多產品共存，需要 scope 隔離 |
| 操作是循序的 | 不同用戶可能同時 capture/sync |

**ADR-013（分散治理模型）** 解決了 Agent vs Server 的職責劃分，但沒有處理「不同 Agent 實例之間的一致性」——不同電腦上的 Agent 各自獨立執行 skill，沒有共用的啟動協議確保它們從同一個 context 出發。

## Decision

### 1. 所有治理 skill 共用「Step 0: Context Establishment」

在 capture / sync / governance 的實際操作開始前，**必須先完成以下啟動序列**。這不是建議，是強制前置步驟——跳過任何一項就不可以開始寫入 ontology。

```
Step 0: Context Establishment
├── 0a. 確認目標產品（product entity 必須存在）
├── 0b. 載入該產品的現有 ontology 快照
├── 0c. 確認本地環境與 remote 一致性
└── 0d. 設定本次操作的 scope 參數
```

**0a. 確認目標產品**

```python
# 搜尋目標產品（從目錄名、CLAUDE.md、或用戶指定）
mcp__zenos__search(collection="entities", query="{產品名}", entity_level="L1")

# 必須找到一個 type=product 的 entity
# 找到 → 記下 product_id，後續所有操作帶入
# 找不到 → 停下來問用戶：
#   「找不到產品 {名稱}，要先建立嗎？」
#   用戶確認後才建立 product entity
```

**0b. 載入現有 ontology 快照**

```python
# 拉該產品下所有 L2 entity（用於後續查重和 parent 歸屬）
mcp__zenos__search(collection="entities", product_id="{product_id}", entity_level="L2")

# 拉該產品下所有 documents（用於查重）
mcp__zenos__search(collection="documents", product_id="{product_id}")

# 讀最近 journal（用於了解其他 session 的進度）
mcp__zenos__journal_read(limit=10, project="{專案名}")
```

**目的：** 讓 Agent 在開始操作前，就知道「這個產品已經有什麼」。不載入就開始操作 = 盲目操作。

**0c. 確認本地環境一致性**（僅對需要讀取本地 git 的操作——capture Mode B/C、sync）

```bash
# 在目標目錄執行
cd {TARGET}

# 確認 git 狀態
git fetch origin 2>/dev/null  # 先拉最新 ref（不 pull，不改本地）
git status --short             # 檢查是否有未 commit 的變更

# 記錄 remote 和 branch 資訊（供 source URI 構建使用）
GIT_REMOTE=$(git remote get-url origin)
GIT_BRANCH=$(git symbolic-ref --short HEAD)
GIT_ROOT=$(git rev-parse --show-toplevel)
```

**目的：** 確保後續的 `git ls-files` 檢查和 source URI 構建基於最新的 remote 狀態。

**0d. 設定本次操作的 scope 參數**

所有後續的 `search` / `write` 都必須帶以下參數：

```python
SCOPE = {
    "product_id": "{0a 確認的 product entity ID}",
    "product": "{產品名稱}",
    "project": "{專案名}"
}

# 每次 search 都帶 product scope
mcp__zenos__search(query="...", product_id=SCOPE["product_id"])

# 每次 journal_write 都帶 project
mcp__zenos__journal_write(summary="...", project=SCOPE["project"])
```

### 2. 首次建構防重複 Gate（capture Mode C）

在 Mode C 的 C1 階段（掃描目錄前），插入檢查：

```python
# 0b 已載入的 entity 列表
existing_l2_count = len(existing_l2_entities)
existing_doc_count = len(existing_documents)

if existing_l2_count > 0 or existing_doc_count > 0:
    # 已有 ontology → 不是首次建構
    print(f"""
    ⚠️ 產品「{product_name}」已有 ontology：
      L2 entity：{existing_l2_count} 個
      Documents：{existing_doc_count} 個

    選項：
    - 「繼續」→ 增量模式（只處理尚未建立的文件）
    - 「重建」→ 清空後重建（危險，需二次確認）
    - 「取消」→ 改用 /zenos-sync 做增量同步
    """)
```

### 3. Sync State 移至 Ontology

**廢棄** `.zenos-sync-state.json` 本地檔案，改用 journal 記錄 sync 狀態。

```python
# sync 完成後
mcp__zenos__journal_write(
    summary=f"sync {project}: scanned {n} commits since {since}, "
            f"updated {m} documents, {k} entities",
    project=SCOPE["project"],
    flow_type="sync",
    tags=[SCOPE["product"], f"since:{since}", f"until:{now}"]
)

# 下次 sync 啟動時，從 journal 恢復上次時間
result = mcp__zenos__journal_read(project=SCOPE["project"])
# journal_read 回傳 {entries: [...], count: int, total: int}
last_sync_entry = next(
    (j for j in result["entries"] if j["flow_type"] == "sync"),
    None
)
# 從 tags 中提取 "until:..." 或用 created_at 作為本次的 since
```

**好處：** 任何裝置都能讀到上次 sync 時間，不再因為本地檔案不同步而重複處理。

### 4. Source Audit 改為「標記 + 確認」模式

**現狀：** Step 0.4 自動刪除 broken source，可能誤殺其他裝置新增的合法檔案。

**改為：**

```
Source Audit 結果
─────────────────────────────────
🔴 broken:    N 筆 — URI 指向不存在的檔案
🟡 bad_label: N 筆
🟠 renamed:   N 筆
─────────────────────────────────

自動修正：bad_label（風險低，直接修）、renamed（有明確新路徑，直接更新）
需確認：  broken（列出清單，用戶確認後才刪除）

是否刪除 broken sources？（列出清單 / 全部刪除 / 跳過）
```

**規則：**
- `bad_label` → 自動修正（只改 label，不影響資料）
- `renamed` → 自動更新（有 git 追蹤的明確新路徑）
- `broken` → **列出清單，等用戶確認**（可能是未 push、未 pull、或真的刪除）
- `duplicate` → 報告，不自動處理（同現狀）

### 5. 專案結構分類改為可配置

**現狀：** P0/P1/P2/P3 的路徑模式硬編碼在 skill 中（`docs/01-specs/`、`domains/`...），只適用於 Havital 的目錄結構。

**改為：** 在啟動時嘗試讀取專案的結構配置，fallback 到通用啟發式。

```bash
# 優先讀取專案自定義配置
cat {TARGET}/.zenos-project.json 2>/dev/null
```

```jsonc
// .zenos-project.json（可選，放在專案根目錄）
{
  "product": "Paceriz",
  "structure": {
    "p0_seeds": ["CLAUDE.md", "README.md", "*OVERVIEW*", "*ARCHITECTURE*"],
    "p1_specs": ["docs/specs/**", "docs/plans/**", "**/*SPEC*.md"],
    "p2_features": ["docs/api/**", "docs/guides/**"],
    "skip": ["tests/**", "node_modules/**", ".venv/**"]
  }
}
```

**若無 `.zenos-project.json`：** 使用通用啟發式（基於檔名 pattern 而非路徑）：

```
P0: CLAUDE.md, README.md, 檔名含 OVERVIEW/ARCHITECTURE/STRUCTURE
P1: 檔名含 SPEC/FRD/PLAN，或在任何名為 specs/plans/architecture 的目錄下
P2: 在 api/guides/services/integrations 目錄下
P3: 其餘 .md
Skip: tests/ integration_tests/ .venv/ node_modules/ *FIX_REPORT* *VALIDATION_FIX*
```

**差異：** 不再依賴 `docs/01-specs/`、`docs/04-frds/` 這類 Havital 特定路徑，改為基於語意的檔名/目錄名 pattern。

### 6. 查重一律帶 Product Scope

所有查重操作（capture Step 2/3、sync Step 3）的 `search` 必須帶 `product` 或 `product_id`：

```python
# 之前（無 scope，可能跨產品誤判）
mcp__zenos__search(query="行銷策略", collection="documents")

# 之後（product-scoped）
mcp__zenos__search(
    query="行銷策略",
    collection="documents",
    product_id=SCOPE["product_id"]
)
```

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| Server 端強制 product scope | 從根本杜絕跨產品污染 | 需要改 MCP Server 所有 search/write 介面，破壞性大 | Phase 2 可考慮，但 Phase 0 先在 Skill 端解決 |
| 每個用戶一個 workspace | 完全隔離 | 違背 ZenOS「一個 workspace 共享 context」的核心定位 | 與產品方向矛盾 |
| 不改 skill，只加 Server 端驗證 | Skill 不用動 | Server 小模型無法判斷 product 歸屬（語意問題，見 ADR-013） | Agent 端必須在寫入前就做好 scope 設定 |
| 繼續按 case 修補 | 改動小 | Skill 越來越長且碎片化，agent 遵循度下降；新用戶每次都踩同樣的坑 | 目前路線已證明不可持續 |

## Consequences

**正面：**
- 不同用戶在不同電腦上執行 capture/sync，會得到一致的治理效果
- 孤兒 document、重複 entity、錯誤 URI 等問題從結構上被防止
- 新用戶 onboarding 不需要了解 skill 的隱含假設
- Source Audit 不再誤殺合法 source

**負面：**
- 每次 capture/sync 多了 3-5 個 MCP 呼叫的啟動開銷（約 2-3 秒）
- `.zenos-project.json` 是新的配置檔，需要教育用戶（但它是可選的，有 fallback）
- 廢棄 `.zenos-sync-state.json` 需要遷移（一次性，遇到舊檔案時自動遷移即可）

**後續處理：**
- Phase 2：考慮將 product scope 移入 Server 端強制（所有 write 操作自動帶 partner 的 default product）
- `.zenos-sync-state.json` → journal 遷移：sync 啟動時若發現本地檔案存在，讀取後寫入 journal，再刪除本地檔案

## Implementation

### 影響的 SSOT 檔案

| 檔案 | 變更 |
|------|------|
| `skills/release/zenos-capture/SKILL.md` | 加入 Step 0；Mode C 加防重複 Gate；P0/P1 改通用啟發式 |
| `skills/release/zenos-sync/SKILL.md` | 加入 Step 0；廢棄 `.zenos-sync-state.json`；Source Audit 改標記+確認 |
| `skills/release/governance/bootstrap-protocol.md` | **新增**：Step 0 完整規範（單一 SSOT） |
| `skills/release/governance/capture-governance.md` | 加入 bootstrap protocol 引用 |
| `skills/release/governance/shared-rules.md` | 加入 product scope 規則；修正 task status 集合 |
| `skills/release/governance/document-governance.md` | relationship 欄位名稱修正；查重 + git sync 加 product_id；broken source 改標記+確認 |
| `skills/workflows/knowledge-capture.md` | 同步 capture 的 Step 0、通用啟發式、journal write 規範、compressed 蒸餾 |
| `skills/workflows/knowledge-sync.md` | 同步 sync 的 Step 0、journal 恢復、Source Audit 安全模式 |
| `skills/governance/bootstrap-protocol.md` | **新增**：Step 0 完整規範（本地副本） |
| `skills/governance/capture-governance.md` | 加入 bootstrap protocol 引用 |
| `skills/governance/shared-rules.md` | 加入 product scope 規則；修正 task status 集合 |
| `skills/governance/document-governance.md` | relationship 欄位名稱修正；查重 + git sync 加 product_id；broken source 改標記+確認 |

### 新增檔案

| 檔案 | 用途 |
|------|------|
| `skills/governance/bootstrap-protocol.md` | Step 0 的完整規範（單一 SSOT，各 skill 引用） |

### 實作順序

1. 寫 `bootstrap-protocol.md`（Step 0 的完整規範）
2. 改 `zenos-capture/SKILL.md`（加 Step 0 引用 + Mode C Guard + 通用啟發式）
3. 改 `zenos-sync/SKILL.md`（加 Step 0 引用 + sync state 遷移 + Source Audit 改標記模式）
4. 改 `knowledge-capture.md`（同步 capture 變更）
5. 改 `shared-rules.md`（加 product scope 規則）
6. 改 `capture-governance.md`（引用 bootstrap protocol）
