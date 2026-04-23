---
type: TD
id: TD-service-architecture
status: Approved
ontology_entity: service-architecture
created: 2026-03-21
updated: 2026-04-23
---

# Technical Design: 服務架構 — Ontology 治理的落地實作

> 從 `docs/spec.md` Part 7 搬出。原始內容寫於 2026-03-21。
>
> **2026-04-23 Layering note（Grand Ontology Refactor）**：
> 本 TD 的早期服務架構概念（事件源 / 治理引擎 / 確認同步三層）仍保留為歷史設計記錄，但**schema / MCP contract / governance rule canonical** 已於 2026-04-23 由以下 SPECs 取代：
> - Schema canonical → `SPEC-ontology-architecture v2`
> - MCP tool contract → `SPEC-mcp-tool-contract`
> - Task / Plan 治理 → `SPEC-task-governance`
> - Document 治理 → `SPEC-doc-governance`
> - 治理規則分發 → `SPEC-governance-guide-contract`
>
> 本 TD 內任何具體 schema / status enum / error code 如與上述 SPECs 不一致，以 SPEC 為準。新服務設計請直接對齊 SPEC，不要沿用本 TD 的過時欄位敘述。

### 核心問題：文件 CRUD 怎麼被偵測、ontology 怎麼主動更新？

Ontology 的價值在「持續治理」，不在「建一次」。但持續治理需要兩個前提：
1. **知道文件變了**（事件源）
2. **知道要怎麼更新 ontology**（治理引擎）

不同公司的文件環境差異極大。ZenOS 的架構必須支持多種事件源，但從最簡單的開始。

### 架構總覽：三層治理系統

```
┌─────────────────────────────────────────────────────────────┐
│ 事件源層（Detection Layer）                                    │
│ 「文件 CRUD 怎麼被偵測到？」                                   │
│                                                              │
│ ┌──────────┐  ┌──────────────┐  ┌──────────────┐            │
│ │ Git Hook  │  │ File Watcher │  │ Cloud API    │            │
│ │ post-commit│  │ fswatch /    │  │ Google Drive │            │
│ │ pre-push  │  │ inotify      │  │ MS Graph     │            │
│ └─────┬─────┘  └──────┬───────┘  └──────┬───────┘            │
│       └───────────────┼─────────────────┘                    │
│                       ▼                                       │
│              統一事件格式（Unified Change Event）               │
│              { file, action, diff, author, timestamp }        │
└──────────────────────┬────────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 治理引擎層（Governance Engine）                                │
│ 「偵測到之後誰來分析、怎麼更新 ontology？」                     │
│                                                              │
│ ┌──────────────┐  ┌──────────────┐  ┌────────────────┐      │
│ │ 變更分類器    │  │ 影響分析器    │  │ 過時偵測器      │      │
│ │ 重大/小修/    │  │ 哪些 entry   │  │ 定期掃描       │      │
│ │ 新檔/刪除/   │  │ 受影響？     │  │ 跨實體活動度   │      │
│ │ 重命名       │  │              │  │ 異常           │      │
│ └──────┬───────┘  └──────┬───────┘  └───────┬────────┘      │
│        └─────────────────┼──────────────────┘                │
│                          ▼                                    │
│                 草稿產生器（Draft Generator）                   │
│                 提出 ontology 更新建議                          │
│                 神經層：自動生效                                │
│                 骨架層：draft → confirmedByUser                 │
└──────────────────────┬────────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ 確認與同步層（Confirmation & Sync）                            │
│ 「人怎麼介入？下游怎麼更新？」                                  │
│                                                              │
│ ┌──────────────┐  ┌──────────────┐  ┌────────────────┐      │
│ │ 待確認佇列    │  │ 級聯更新器    │  │ Protocol 重生器 │      │
│ │ 骨架層變更    │  │ 骨架→神經    │  │ ontology →     │      │
│ │ 需人確認      │  │ 自動聯動     │  │ Protocol 自動   │      │
│ │              │  │              │  │ 重新產出        │      │
│ └──────────────┘  └──────────────┘  └────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 事件源：不同環境的 CRUD 偵測方式

```
環境                    事件源                   CRUD 偵測機制              延遲
──────                 ──────                  ──────────               ────
Markdown + Git         git post-commit hook    git diff --name-status   即時（commit 觸發）
Markdown 無 Git        fswatch / inotify       檔案系統事件              即時（儲存觸發）
Google Workspace       Drive API webhook       Changes API (push)       ~秒級
Microsoft 365          MS Graph webhook        Change Notifications     ~秒級
Notion                 Notion API webhook      Search/Query delta       ~分鐘級
混合環境               多源歸一                 統一 Change Event 格式    依來源而異
```

**核心洞察：Markdown + Git 是最乾淨的事件源。**

Git commit 自帶完整的 CRUD 語意：
- **C**reate：`git diff --name-status` 顯示 `A`（Added）
- **R**ead：不觸發（讀不改 ontology）
- **U**pdate：`git diff --name-status` 顯示 `M`（Modified）+ `git diff` 顯示具體改了什麼
- **D**elete：`git diff --name-status` 顯示 `D`（Deleted）

而且 git 天然提供：author（誰改的）、timestamp（什麼時候改的）、message（為什麼改）、diff（改了什麼）。不需要額外 metadata。

### 分階段實作：從零基礎設施到完整自動化

#### Phase 0.5 — 手動觸發、零基礎設施（立刻可用）

**適用情境：** Barry 現在的狀態。一個人、幾個 git repo、用 Claude Code 開發。

**做法：** 不建任何基礎設施，利用已有的工具鏈。

```
觸發方式：Claude Code session 開始時手動觸發
             ↓
分析引擎：Claude 讀 git log --since="上次 ontology sync 時間"
             ↓
          Claude 讀變更的文件 + 現有 ontology
             ↓
          Claude 提出 ontology 更新建議
             ↓
確認方式：Barry 在對話中確認 → Claude 直接更新 .md 文件
             ↓
同步方式：git commit ontology 變更
```

**具體流程（每次 session 開始或結束前）：**

```bash
# 1. 看上次 ontology 更新之後改了什麼
git log --since="2026-03-21" --name-status --oneline

# 2. Claude 分析變更清單，對照現有 ontology
#    → 哪些 entry 需要更新？
#    → 有新文件需要建 entry 嗎？
#    → 有文件被刪需要歸檔嗎？

# 3. Barry 確認後，Claude 更新 ontology .md 文件
# 4. git commit 更新後的 ontology
```

**優點：** 零成本、零基礎設施、今天就能開始。
**缺點：** 依賴人記得觸發、沒有自動提醒。

**Phase 0.5 的進化：在 CLAUDE.md 加入 ontology sync 提醒**

```markdown
# Session 結束前的 checklist
- [ ] 這次 session 有改到文件嗎？如果有，跑一次 ontology sync
- [ ] 骨架層有變嗎？（新產品、新目標、角色變動）
- [ ] 神經層有變嗎？（新文件、文件大改、文件刪除）
```

這就是 Phase 0 的「設計期觸發規則」的落地實作——不是系統自動觸發，是靠流程規範 + AI 提醒。

#### Phase 1 — Git Hook 自動偵測 + 待辦佇列

**適用情境：** 第一個客戶、或 Barry 覺得手動觸發不夠用時。

**新增基礎設施：** 一個 git post-commit hook + 一個 changelog 文件。

```bash
# .git/hooks/post-commit（每次 commit 自動觸發）
#!/bin/bash

# 取得這次 commit 改了什麼
CHANGES=$(git diff --name-status HEAD~1 HEAD -- '*.md' '*.pdf' '*.docx')

if [ -n "$CHANGES" ]; then
  # 寫入 ontology 待處理佇列
  echo "---" >> docs/ontology-pending.md
  echo "commit: $(git rev-parse --short HEAD)" >> docs/ontology-pending.md
  echo "date: $(date -Iseconds)" >> docs/ontology-pending.md
  echo "author: $(git log -1 --format='%an')" >> docs/ontology-pending.md
  echo "changes:" >> docs/ontology-pending.md
  echo "$CHANGES" | while read line; do
    echo "  - $line" >> docs/ontology-pending.md
  done
fi
```

**效果：** 每次 commit 之後，`ontology-pending.md` 自動累積變更清單。下次 Claude session 一打開，先讀 `ontology-pending.md`，一次處理所有待更新。

```
流程：
  開發者正常工作 → git commit → hook 自動記錄變更
        ↓
  下次 Claude session 開始
        ↓
  Claude 讀 ontology-pending.md
  「上次之後有 3 個 commit 改了 5 個文件，建議以下 ontology 更新…」
        ↓
  Barry 確認 → Claude 更新 ontology → 清空 pending
```

**加入定期掃描（過時偵測）：**

```bash
# crontab（每週一早上跑一次）
0 9 * * 1 cd /path/to/repo && ./scripts/ontology-staleness-check.sh
```

```bash
# ontology-staleness-check.sh
#!/bin/bash

# 找出超過 30 天沒修改但有關聯 ontology entry 的文件
echo "# Staleness Report $(date -I)" > docs/ontology-staleness-report.md
echo "" >> docs/ontology-staleness-report.md

find docs/ -name "*.md" -mtime +30 | while read file; do
  echo "- ⚠️ $file (last modified: $(stat -c %y "$file" | cut -d' ' -f1))" \
    >> docs/ontology-staleness-report.md
done
```

**優點：** CRUD 偵測自動化、不遺漏變更、有定期過時掃描。
**缺點：** AI 分析還是在 session 內手動觸發。

#### Phase 2 — 全自動治理（BYOS 部署）

**適用情境：** 付費客戶、BYOS 部署環境。

**架構：** 客戶的 VM 上跑一個常駐的 Governance Daemon。

```
┌─ 客戶的 VM ──────────────────────────────────────────────┐
│                                                          │
│  ┌──────────────┐     ┌──────────────┐                  │
│  │ File Watcher │     │ Git Hook     │                  │
│  │ (fswatch)    │     │ (post-commit)│                  │
│  └──────┬───────┘     └──────┬───────┘                  │
│         └───────────┬────────┘                           │
│                     ▼                                     │
│  ┌──────────────────────────────────┐                    │
│  │ Event Queue（本地 SQLite）        │                    │
│  │ { file, action, diff, ts }      │                    │
│  └──────────────┬───────────────────┘                    │
│                 ▼                                         │
│  ┌──────────────────────────────────┐                    │
│  │ Governance Daemon（Python/Node）  │                    │
│  │                                  │                    │
│  │ 1. 從 queue 讀事件               │                    │
│  │ 2. 分類：重大修改 / 小修 / 新增  │                    │
│  │ 3. 呼叫 Claude API 分析影響      │                    │
│  │ 4. 產出 ontology 更新草稿        │                    │
│  │ 5. 神經層 → 自動寫入             │                    │
│  │    骨架層 → 推入待確認佇列        │                    │
│  └──────────────┬───────────────────┘                    │
│                 ▼                                         │
│  ┌──────────────────────────────────┐                    │
│  │ 確認介面（Web UI / CLI / Slack） │                    │
│  │                                  │                    │
│  │ 「ACWR.md 更新了 → 建議更新      │                    │
│  │   acwr.md ontology entry 的      │                    │
│  │   '待決策' 為 '已修復'」          │                    │
│  │                                  │                    │
│  │  [確認] [修改] [忽略]             │                    │
│  └──────────────────────────────────┘                    │
│                                                          │
│  客戶的 Claude 訂閱（API key）← 全部在本地，不過 ZenOS    │
└──────────────────────────────────────────────────────────┘
```

**Phase 2 支持的事件源擴展：**

```
Markdown + Git     → git hook（Phase 1 已有）
非 Git 的本地文件  → fswatch / inotify → 偵測 .md/.docx/.pdf 的 create/modify/delete
Google Drive       → Drive Changes API（push notification 到本地 webhook endpoint）
Microsoft 365      → MS Graph Change Notifications（同上）
Notion             → Notion API polling（每 5 分鐘查詢 last_edited_time 變更）
Slack / Email      → 不主動監控，但可以手動「capture」一段對話進 ontology
```

**每個事件源都歸一到統一格式：**

```json
{
  "source": "git",
  "action": "modified",
  "file": "cloud/api_service/FIRESTORE_STRUCTURE.md",
  "diff_summary": "新增 `training_sessions` collection 定義",
  "author": "barry",
  "timestamp": "2026-03-21T14:30:00+08:00",
  "commit": "a1b2c3d"
}
```

**Governance Daemon 的決策邏輯：**

```
收到事件
  │
  ├─ action = "created" 且是非程式碼文件
  │   → 需要新建 ontology entry？
  │   → AI 分析文件內容，打 4D 標籤
  │   → 自動寫入神經層
  │   → 如果涉及新實體 → 建議骨架層更新（待確認）
  │
  ├─ action = "modified"
  │   → 變更量大嗎？（> 20% diff = 重大修改）
  │   │   ├─ 大：重新分析 4D 標籤，對比舊標籤
  │   │   │   → 標籤變了 → 更新神經層 entry
  │   │   │   → 標籤沒變 → 只更新 last_reviewed 時間戳
  │   │   └─ 小（typo/格式）：不觸發
  │   │
  │   → 影響骨架層嗎？（改了產品名、改了目標描述、改了依賴關係）
  │       → 是：推入待確認佇列
  │       → 否：神經層自動更新
  │
  ├─ action = "deleted"
  │   → ontology entry 標記 archived
  │   → 檢查有沒有其他 entry 依賴這個文件
  │       → 有：通知「依賴斷裂，需要 review」
  │
  └─ action = "renamed"
      → 更新 ontology entry 的路徑引用
      → 自動，不需確認
```

### 特別回答你的問題：只有 markdown、沒有 Google Docs，怎麼主動治理？

你的情境其實是最理想的，因為：

```
你的優勢                           為什麼是優勢
──────                            ──────────
全 markdown                       AI 讀寫零成本，不需解析 binary 格式
全在 git                          CRUD 歷史完整，免費的 audit trail
用 Claude Code 開發               治理引擎就是 Claude，不需另建 AI pipeline
CLAUDE.md 慣例已建立               AI 入口已存在，ontology 只是擴展
一個人                            confirmedByUser 就是你自己，沒有跨部門審批問題
```

**你現在就能用的「主動治理」流程：**

```
1. 工作日常態（Phase 0.5）
   ├── 每次 Claude Code session 結束前
   │   Claude 自動問：「這次 session 有影響 ontology 的變更嗎？」
   │   ├── 有 → 提出更新建議 → Barry 確認 → 直接更新 .md
   │   └── 沒有 → 跳過
   │
   ├── 每週一次（手動或 cron）
   │   跑 staleness check：哪些文件超過 30 天沒動但關聯實體活躍？
   │   → 產出 staleness report → Barry 花 5 分鐘 review
   │
   └── 每次大方向調整時
       手動觸發全量 ontology sync
       → Claude 重新掃描所有文件 vs 現有 ontology
       → 提出批量更新建議

2. 加入 Git Hook 之後（Phase 1）
   ├── 每次 git commit 自動記錄變更到 pending 佇列
   ├── 下次 session 開始時 Claude 自動讀 pending
   └── 不再依賴「人記得觸發」

3. 最終形態（Phase 2）
   ├── Governance Daemon 常駐
   ├── 文件改了 → 秒級偵測 → AI 自動更新神經層
   ├── 骨架層變更 → 推通知 → Barry 在手機上確認
   └── Context Protocol 自動重生
```

### 技術選型決策

```
                    Phase 0.5           Phase 1              Phase 2
                    ──────────          ──────────           ──────────
事件偵測            手動（git log）     git hook              git hook + fswatch + Cloud API
事件佇列            不需要              ontology-pending.md   SQLite（本地）
治理引擎            Claude Code session Claude Code session   Governance Daemon + Claude API
Ontology 儲存       .md 文件（git）     .md 文件（git）       SQLite → PostgreSQL（可選）
確認介面            Claude 對話         Claude 對話           Web UI / CLI / Slack bot
過時偵測            手動 review         cron + shell script   Daemon 內建定期掃描
部署               無                  git hook 安裝         BYOS VM
成本               $0                  $0                    Claude API 用量
```

### Ontology 儲存的演化路線

```
Phase 0~1: Markdown 文件（現在）
  ├── 優點：零成本、人可讀、git 版本控制、AI 直接讀寫
  ├── 缺點：無法做結構化查詢、關聯性靠文件內文字引用
  └── 適用：< 50 份 ontology 文件、單人/小團隊

Phase 2: SQLite（單客戶 BYOS）
  ├── 優點：結構化查詢、關聯性靠 foreign key、仍是單文件部署
  ├── 缺點：人不能直接讀、需要工具層
  ├── 遷移：.md 是 view，SQLite 是 source of truth
  └── 適用：50~200 份 entry、中型公司

Phase 3: PostgreSQL + Graph Extension（規模化）
  ├── 優點：圖查詢（找三跳內的關聯）、全文搜索、多 agent 並發
  ├── 缺點：需要 DB 維運
  └── 適用：200+ entry、多產品線、需要跨公司 meta 分析
```

**關鍵設計原則：.md 永遠可以作為 export 格式。** 即使底層遷移到 SQLite/PostgreSQL，用戶看到的 ontology 仍然可以是 .md 文件（由 DB 自動生成）。這保持了人類可讀性和 git 版本控制。

### 多角色協作：非技術成員的事件源策略

現實中一間公司不會所有人都用 git。關鍵區分：**誰是 ontology 的生產者，誰是消費者？**

```
角色                 跟 ontology 的關係          事件源策略
──────              ────────────────          ──────────
開發者 / 技術人員    生產者 + 消費者             Git hook（最乾淨）
老闆 / 決策者        主要是消費者（看全景圖）     對話觸發（Stage 0）
                     偶爾是生產者（改方向時）     Governance Daemon 推確認
行銷 / 非技術成員    主要是消費者（讀 Protocol）  Protocol 推送（被動接收）
                     偶爾是生產者（寫素材時）     Cloud Docs API / 共享資料夾監控
外部顧問 / 客戶      純消費者                    不觸發事件，只讀 Protocol
```

**核心洞察：行銷夥伴的文件變更不需要跟開發者走同一套偵測機制。**

行銷夥伴的痛點不是「她的文件沒被偵測到」，而是「她沒有可用的素材」。所以流向是反的：

```
開發者改了程式碼/文件
  → git hook 偵測
  → ontology 更新
  → Context Protocol 自動重生
  → 推送給行銷夥伴（email / Slack / 共享資料夾）
  → 行銷夥伴看到最新的產品 context，直接產素材

行銷夥伴基於 Protocol 寫了素材
  → 素材存在共享資料夾 / Google Docs
  → Cloud API 偵測到
  → ontology 記錄「行銷素材已更新」
  → 閉環
```

**針對不同非技術成員的事件源方案：**

```
情境 A — 行銷夥伴用 Google Docs
  偵測：Google Drive Changes API（push notification）
  觸發：Docs 被編輯 → Governance Daemon 讀取 → 更新神經層 entry
  延遲：秒級
  成本：Google API 免費額度足夠

情境 B — 行銷夥伴用 Word + 共享資料夾
  偵測：Dropbox / Google Drive / OneDrive 同步監控
  觸發：本地 fswatch 監控同步資料夾 → 偵測 .docx 變更
  延遲：秒~分鐘級（取決於同步速度）
  成本：零（fswatch 是免費工具）

情境 C — 行銷夥伴用 Notion
  偵測：Notion API polling（每 5 分鐘查詢 last_edited_time）
  觸發：頁面被編輯 → 讀取內容 → 更新神經層 entry
  延遲：分鐘級
  成本：Notion API 免費

情境 D — 行銷夥伴沒有固定工具（最常見的中小企業現實）
  策略：不監控她的文件，監控 ontology 的消費端
  → Protocol 更新時通知她
  → 她寫完素材後手動「提交」（上傳到指定資料夾 / 發 Slack 訊息）
  → Governance Daemon 被動接收
  延遲：不即時，但夠用
  成本：零
```

**Phase 0.5 的行銷夥伴方案（立刻可用）：**

行銷夥伴不需要任何技術工具。流程：
1. Barry 更新了 ontology → Context Protocol（paceriz.md）自動更新
2. Barry 把更新後的 Protocol 用 email / LINE / Slack 傳給行銷夥伴
3. 行銷夥伴讀 Protocol → 寫素材 → 回傳給 Barry review
4. Barry 把素材放進 repo → git 偵測 → ontology 記錄

這不優雅，但零成本、今天就能開始。等 Phase 2 有 Governance Daemon 和 Web UI 之後，行銷夥伴才會有自己的「確認介面」。

### 跨生態系整合策略：ZenOS 的 Adapter 架構

ZenOS 的核心定位是「語意層」，不是「儲存層」。文件留在用戶自己的工具裡，ZenOS 透過 Adapter 讀取事件和內容。

#### 四種 SMB 環境的整合方式

```
環境                Adapter 策略              事件偵測                   內容讀取                免費可行性
──────             ──────────              ──────────                ──────────             ──────────
Google Drive       Google Drive API         Changes API push webhook   files.get + export     ✅ 免費額度夠用
Microsoft 365      MS Graph API             Change subscriptions       driveItem /content     ✅ 標準 Graph 配額
Wiki（Notion）     Notion API               Webhooks（page/db 事件）    Page query 取內容      ✅ 免費
Wiki（Confluence） Atlassian REST API       Webhooks（page CRUD 事件）  REST 取頁面內容        ✅ 免費雲版
Git（技術團隊）    Git hooks                 post-commit hook           git diff / git show    ✅ 完全免費
什麼都沒有         → 見下方專門討論
```

#### 「什麼都沒有」的產品策略（最關鍵的決策）

**核心問題：沒有儲存層，語意層就沒有東西可以代理。ZenOS 該怎麼辦？**

三個選項的分析：

```
選項 A — ZenOS 自建文件管理 + UI
  ✓ 完整體驗控制
  ✗ 你在重新發明 Notion / Google Drive
  ✗ 開發成本巨大（6~12 個月）
  ✗ 偏離 North Star：ZenOS 是 ontology，不是文件管理
  ✗ 跟免費的 Google Drive / Notion 競爭 = 死路

選項 B — ZenOS 推薦用戶先用現有免費工具，自己只做語意層
  ✓ 不偏離定位
  ✓ 零儲存層開發成本
  ✗ 「什麼都沒有」的用戶可能連 Google Drive 都不想學
  ✗ 導入多一步 = 流失率高

選項 C — ZenOS Dashboard：最小 UI，只做 Ontology 消費介面（✅ 選這個）
  ✓ 不競爭文件管理
  ✓ 用戶有一個「看到知識全貌」的地方
  ✓ 文件在哪不影響 — Google Drive / 本地 / 什麼都沒有
  ✓ 完美對齊漸進式信任模型
  → 儲存層可以後來再接（或不接）
```

**選項 C 的核心思路：ZenOS Dashboard 是「公司知識的體檢報告」，不是「公司文件的管理工具」。**

```
類比：
  醫院 ≠ 你家               → ZenOS ≠ 文件儲存
  你在家裡吃飯睡覺           → 文件在 Google Drive / 本地 / Git
  你去醫院看體檢報告          → 你在 ZenOS Dashboard 看全景圖 + Protocol
  醫生告訴你哪裡有問題        → ZenOS 告訴你哪些知識過時/矛盾/缺漏
  你決定要不要治療            → confirmedByUser
  你不會因為醫院好就搬去住    → 用戶不會因為 ZenOS 好就把文件搬過來
```

#### ZenOS Dashboard 做六件事

```
┌─────────────────────────────────────────────────────────────┐
│  ZenOS Dashboard（唯一自建的 UI）                             │
│                                                              │
│  1. 展示全景圖                                               │
│     骨架層視覺化 + 盲點推斷 + 跨實體依賴圖                     │
│     → 老闆來這裡「看全貌」                                    │
│                                                              │
│  2. 收集確認                                                  │
│     ontology 變更 + 任務完成的 confirm 佇列                    │
│     → 老闆來這裡「做決定」                                    │
│     （兩種確認合併：知識確認 confirmedByUser +                  │
│      任務驗收 confirmedByCreator）                             │
│                                                              │
│  3. 提供 Protocol                                            │
│     給行銷/非技術成員的可讀 view                               │
│     → 行銷夥伴來這裡「找 context」                            │
│                                                              │
│  4. 資料存放點地圖（Storage Map）                              │
│     公司知識散落在哪些地方的視覺化總覽                          │
│     → 老闆來這裡「看知識散落在哪」                             │
│                                                              │
│     Git repo (paceriz)        ████████████  38 entries       │
│     Google Drive              ██████        15 entries       │
│     Firestore（對話產出）      ████          10 entries       │
│     未連結                     ██             5 entries       │
│                                                              │
│  5. 任務看板（Action Layer）                                  │
│     Kanban 五欄 + Inbox/Outbox 雙視角                         │
│     → 所有人來這裡「看任務、追進度、確認完成」                  │
│     （詳見 Part 7.1 — Action Layer）                          │
│                                                              │
│  6. 團隊設定（角色→員工對應）                                  │
│     設定職能角色由哪些員工擔任                                  │
│     → 老闆/主管來這裡「設定 Who 的公司層綁定」                  │
│     + Agent 身份宣告指引（教員工設定 agent 的職能角色）          │
│     （詳見 docs/reference/REF-enterprise-governance.md「Who 的三層消費模型」）      │
│                                                              │
│  它 不做：                                                    │
│  ✗ 文件編輯                                                   │
│  ✗ 文件儲存                                                   │
│  ✗ 文件上傳（只有 Stage 1 的 Drop Zone，讀完就丟）             │
│  ✗ 搜尋（那是 Glean 的事）                                    │
│  ✗ 協作（那是 Notion / Google Docs 的事）                     │
│  ✗ Agent 管理（員工→agent 的綁定在員工自己的環境）              │
└─────────────────────────────────────────────────────────────┘
```

#### Dashboard 頁面架構

```
/login                          ← Google OAuth
/                               ← 專案列表
/projects/:id                   ← 全景圖（EntityTree + Blindspots + 依賴圖）
/projects/:id/tasks             ← 任務看板（Kanban + Inbox/Outbox）
/projects/:id/confirm           ← 確認佇列（知識確認 + 任務驗收）
/projects/:id/protocol          ← Protocol Viewer
/projects/:id/map               ← Storage Map
/projects/:id/team              ← 角色→員工設定
/setup                          ← MCP 設定引導 + Agent 身份宣告指引
```

#### 「什麼都沒有」的漸進式導入路徑

```
Stage 0 — 只有對話（什麼儲存工具都不需要）
  老闆跟 ZenOS 聊 30 分鐘
  → 全景圖出現在 ZenOS Dashboard 上
  → 老闆第一次看到自己公司的知識結構
  → 不需要任何文件、任何工具
  → 這就夠了。信任從這裡開始。

Stage 1 — 老闆願意給文件（但文件散落各處）
  ZenOS Dashboard 提供 Drop Zone：
  「把你覺得重要的文件拖進來，我看一看就好，不會留下。」
  → ZenOS 讀取 → 建 ontology → 文件不儲存在 ZenOS
  → 或者老闆授權 Google Drive / 本地資料夾
  → Ontology 充實 → Protocol 產出

Stage 2 — 需要持續治理（這時才需要儲存層）
  ZenOS 問：「你們想把文件集中管理嗎？」
  → 老闆決定用 Google Drive（免費、最低摩擦）
  → ZenOS 自動設定 Adapter
  → 從此 CRUD 事件自動偵測
  → 或者老闆決定不用 → ZenOS 定期掃描（手動 + cron）也行
```

**「什麼都沒有」不是障礙，因為 Stage 0 本來就不需要儲存層。** 這正是漸進式信任的威力——ZenOS 從零開始也能展示價值。

#### Adapter 架構設計

```
                    ZenOS Ontology Engine
                           │
                    ┌──────┴──────┐
                    │ Adapter Hub │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │ Google    │   │ Microsoft │   │ Notion    │
    │ Adapter   │   │ Adapter   │   │ Adapter   │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │                │                │
    統一介面：
    ┌────────────────────────────────────────┐
    │ interface StorageAdapter {              │
    │   watchChanges() → Stream<ChangeEvent> │
    │   readContent(fileId) → string         │
    │   getMetadata(fileId) → FileMetadata   │
    │   listFiles(folder) → File[]           │
    │ }                                      │
    └────────────────────────────────────────┘

    每個 Adapter 實作同一個介面。
    Ontology Engine 不關心文件在哪——它只跟 Adapter 介面互動。
    新增一個生態系 = 新增一個 Adapter，Engine 零改動。
```

**Adapter 的開發優先順序（基於 SMB 市場調查）：**

```
優先順序    Adapter              理由
──────    ──────────          ──────
1         Git                  已有（Phase 0.5）+ 技術客群起步
2         Conversation         MCP + Skill，知識捕獲在產生點，不需檔案系統
3         Google Drive         80%+ SMB 使用 Google Workspace
4         本地檔案 (fswatch)   搭配 BYOS，零雲端依賴
5         Notion               知識工作者常用
6         Microsoft Graph      企業客群（Phase 2+）
7         Confluence           大企業/轉型客群
```

### Conversation Adapter：AI 對話作為事件源（2026-03-21 dogfooding 發現）

**來源：ZenOS 創辦人自身的 dogfooding。** 在 Claude Cowork session 中產出了 Paceriz 的 Threads 發文策略（20 篇排程 + 4 篇草稿 + 語感備忘 + v2 鋪路時間線），但這份知識不在任何檔案系統裡——只存在對話中。手動匯出、上傳、分類是不會發生的事。

**核心洞察：知識的捕獲點必須在產生知識的地方。** 現有的所有 Adapter（Git / Google / MS / Notion）都假設知識的載體是「檔案」，事件源是「檔案 CRUD」。但 AI 時代有一種新的知識載體——**對話**。AI 對話產出的策略、決策、分析，品質經常比正式文件更高，但它們不會自動變成檔案。

#### 跟其他 Adapter 的差別

```
                    傳統 Adapter              Conversation Adapter
──────              ──────────              ──────────────────
觸發方式            自動（file CRUD 事件）     人主動觸發（呼叫 skill）
事件源              檔案系統                   AI 對話 session
內容來源            檔案內容                   對話 context
觸發頻率            高頻（每次存檔）           低頻（人覺得值得時才觸發）
四維標籤            AI 從檔案內容推斷          AI 從對話 context 推斷（更準確，因為有完整討論脈絡）
```

**意外的優勢：對話 context 比檔案更適合推斷 Why 和 How。** 檔案只有結果，但對話有完整的推導過程。AI 從對話推斷 Why/How 的準確度應該顯著高於從檔案推斷。（待驗證）

#### 技術流程

```
用戶在任何 AI session 中產出有價值的內容
    ↓
呼叫 skill（例如 /zenos-update）
    ↓
Skill 做三件事：
  1. 讀取當前 session 的對話 context
  2. AI 推斷四維標籤 + 關聯的骨架層實體
  3. 呼叫 ZenOS MCP Server：
     - propose_update()  → 更新既有 entry
     - propose_new()     → 建立新 entry
     - 或兩者都有（例如：新建「發文策略」entry + 更新「Paceriz」骨架層實體的關聯）
    ↓
ZenOS Governance Service 收到 proposal → 建 draft entry
    ↓
用戶在 Dashboard 確認佇列 or 直接在 skill 中確認 → confirmedByUser → 生效
    ↓
所有 Who 角色的 AI agent 在下次讀 context 時拿到更新
```

#### 介面設計：擴展 StorageAdapter 還是新介面？

Conversation Adapter 跟 StorageAdapter 的介面不完全一樣——它沒有 `watchChanges()`（不是自動偵測）、沒有 `listFiles()`（沒有檔案系統）。

```
建議：新介面 ConversationAdapter，不強行塞進 StorageAdapter

interface ConversationAdapter {
  extractContext(sessionId) → ConversationContext    // 讀取對話 context
  proposeEntries(context) → OntologyProposal[]      // AI 推斷 ontology entries
  confirm(proposalId) → void                        // 用戶確認
}

ConversationAdapter 的 output 跟 StorageAdapter 一樣：
  都是 OntologyProposal → 進入 Governance Service → confirmedByUser → 生效

差別只在 input：一個是檔案事件，一個是對話 context。
```

#### Skill 的實作要素

```
1. ZenOS MCP Server 先跑起來（Phase 1）
2. Cowork skill 檔案：
   - 讀取 session context（Cowork API 或 transcript）
   - 呼叫 ZenOS MCP 的 propose_update / propose_new
   - 顯示 proposal 讓用戶確認
3. 認證：skill 帶 token，對應用戶的 role mapping
4. 跨平台：同一套 MCP，Claude Code / Cowork / 任何 MCP client 都能用
```

#### PM 交付清單

這個概念交付給 PM 寫 PRD 時，需要回答的問題：

```
必答：
  - Skill 的觸發 UX：用戶怎麼呼叫？呼叫時需要提供什麼？
  - Proposal 的確認 UX：在 skill 裡直接確認，還是導去 Dashboard？
  - Session context 的讀取範圍：整段對話，還是用戶標記的片段？
  - 骨架層 vs 神經層的 propose 規則：對話可以直接 propose 新的骨架層實體嗎？
  - 錯誤處理：MCP 連不上 / 推斷結果用戶不滿意怎麼辦？

可延後：
  - 自動觸發建議：AI 偵測到「這段對話產出了有價值的東西」主動問要不要存
  - 批次處理：一次 propose 多個 entry
  - 衝突處理：propose 的 entry 跟既有 entry 矛盾
```

#### 雙動作設計：Ontology 更新 + 原始內容存放

Conversation Adapter 的 skill 觸發時，做兩件事而不是一件：

```
/zenos-update 觸發：

動作 1 — 更新 ontology（via MCP propose_update / propose_new）
  → 結構化的知識索引：What/Why/How/Who + 關聯
  → 這是 ZenOS 核心職責

動作 2 — 存放原始內容（follow 用戶習慣）
  → 用戶習慣存 git → agent 幫你 commit markdown
  → 用戶習慣存 Google Drive → agent 幫你建文件
  → 什麼都沒有 → 存進 Firestore（ZenOS 託管）
  → ontology entry 的「原始位置」欄位指向這份內容
```

**為什麼需要動作 2：** Ontology 是語意代理，不是原始內容。Agent 未來接手工作時（例如寫第 5 篇草稿），需要讀到前 4 篇的完整文字——這不在 ontology 裡，在原始文件裡。

**關鍵原則：用戶習慣存到哪就存到哪，skill 順帶把 ontology 更新處理掉。** ZenOS 不規定內容該存在哪。

#### Adapter 事件去重（Dedup）

當 Conversation Adapter 和 Storage Adapter 同時觸發時，需要去重：

```
情境：用戶在 Cowork 討論完 → 呼叫 /zenos-update → agent 同時把內容存進 Google Drive

兩個事件同時發生：
  A. Conversation Adapter → propose entry（有完整 Why/How，來自對話 context）
  B. Google Drive Adapter → 偵測到新檔案 → 也想 propose entry（只有 What/Who）

去重規則：
  - Conversation Adapter 產出的 entry 標記 source: "conversation"
  - Storage Adapter 偵測到同一份檔案時（標題/內容 hash 比對）：
    → 如果已存在 source: "conversation" 的 entry → 不重複建立
    → 而是把檔案位置補進既有 entry 的「原始位置」欄位
  - 如果用戶沒呼叫 /zenos-update，直接存檔：
    → 只有 Storage Adapter 觸發 → 正常建 entry（Why/How 品質較低）
```

**為什麼 Conversation Adapter 的 entry 品質更高：** 檔案只有結果，對話有完整的推導過程、否決的替代方案、決策脈絡。AI 從對話推斷 Why/How 比從檔案推斷準確得多。

#### Dogfooding 案例：Paceriz 發文策略

這是第一個被發現的 Conversation Adapter 使用案例：

```
對話內容：Paceriz Threads 發文策略 v2 鋪路版
產生位置：Claude Cowork session（不在任何檔案系統中）

應該產生的 ontology 更新：

骨架層：
  新實體 → 「Paceriz Go-to-Market」（之前不存在）
  新關係 → Paceriz Go-to-Market ↔ Rizo AI（Phase 3 揭幕依賴 v2 功能）
  新關係 → Paceriz Go-to-Market ↔ ACWR（#7 和 #19 交叉引用安全閘門）

神經層：
  新 entry → Threads 發文策略
    What: 20 篇發文排程 + 4 篇草稿 + 語感備忘 + 成效追蹤指標
    Why:  用知識內容建立跑步圈信任 → 自然導入 v2 AI 教練定位
    How:  三階段鋪路（養信任→埋種子→揭幕），5-6 週，每週 3-4 hr
    Who:  marketing, product
    關聯: Paceriz、Rizo AI、ACWR、training-plan
```

### 開放問題（新增）

- [ ] Git hook 的跨平台安裝方式（Windows 客戶怎麼辦）
- [ ] Governance Daemon 的最小技術棧選擇（Python? Node? Go?）
- [ ] 變更分類器的「重大修改」閾值如何設定（20% diff? 語意判斷?）
- [ ] 多 repo 客戶的事件歸一機制（Paceriz 和 ZenOS 在不同 repo）
- [ ] Cloud API webhook 的 BYOS 部署方式（客戶 VM 需要暴露 endpoint 嗎？用 polling 替代？）
- [ ] 確認介面的最小可行形式（Slack bot 最低成本？CLI 最簡單？）
- [ ] 非技術成員的最低摩擦 Protocol 推送方式（email / Slack / 共享資料夾 / Web UI）
- [x] 「什麼都沒有」的產品策略 → Dashboard（ontology 消費介面）+ Drop Zone + 漸進式引導至免費工具
- [ ] ZenOS Dashboard 的技術棧選擇（SSR? SPA? PWA?）
- [x] Dashboard 的最小可行功能定義 → 四件事：全景圖 + 確認佇列 + Protocol viewer + Storage Map
- [ ] Drop Zone 的隱私設計（文件讀完即丟的技術保證）
- [ ] Adapter Hub 的 plugin 機制（第三方能不能寫 adapter？）
- [ ] Conversation Adapter 的 session context 讀取方式（全段對話 vs 用戶標記片段）
- [ ] Conversation Adapter 是否支援自動觸發建議（AI 主動問「要不要存？」）

### Adapter 整合成本估算（2026-03-21 研究）

```
Adapter              開發天數        最大風險                            SDK 節省
                    （資深工程師）
──────              ──────────     ──────────────────────            ────────
Notion               10-16 天      Webhook 不保證送達                   ~40%
Google Drive         12-20 天      Changes API 只保留 ~4000 筆歷史      ~30%
Confluence           11-18 天      Webhook 連續失敗 5 次自動停用         ~35%
Microsoft Graph      14-22 天      Subscription 過期需主動續期           ~30%

四個全做（考慮共用模式）：35-50 天，約 2-3 個月 for 1 資深工程師
```

每個 Adapter 的必要工程工作：
1. OAuth/Auth 流程（各平台不同）
2. 變更偵測（webhook + polling 兜底 — 所有平台的 webhook 都不可靠）
3. 內容讀取 + 格式轉換（各平台的 rich text → 純文字/markdown）
4. 權限處理（不能讀用戶沒權限的文件）
5. Rate limiting + 指數退避 + 重試
6. 生產環境審核（Google 3-5 天、Microsoft 需 tenant admin 同意）

**結論：整合成本明確可控。不是探索性研究，是已知的工程工作。** 建議先做第一個 Adapter（含所有共用模式），後續 Adapter 可節省 40-50% 工時。

### 「什麼都沒有」的完整產品架構

**核心洞察：「什麼都沒有」的公司，問題不是「文件沒地方放」，而是「知識在老闆腦袋裡出不來」。**

ZenOS 的價值不是幫他管文件（那是 Google Drive 的事），而是幫他把隱性知識結構化。

#### ZenOS 需要自建什麼 vs 不建什麼

```
必建（ZenOS 核心）：
  ✅ Dashboard UI — 全景圖 + 確認佇列 + Protocol viewer + Storage Map + Drop Zone
  ✅ Ontology 儲存 — 骨架層 + 神經層（ZenOS 自己的核心資料）
  ✅ 引導式對話引擎 — Stage 0 的結構化訪談（核心體驗）
  ✅ Auth — Google OAuth / GitHub OAuth（不自建帳號系統）
  ✅ 金流 — Stripe（標準方案，月費制）
  ✅ Adapter Hub — 統一介面 + 多生態系 Adapter

不建（借用現有工具）：
  ❌ 文件儲存 — 留在用戶的 Google Drive / Notion / 自己的系統
  ❌ 文件編輯 — Google Docs / Notion / Word
  ❌ 搜尋引擎 — 那是 Glean 的事
  ❌ 協作工具 — 那是 Notion / Google Docs 的事
  ❌ 帳號系統 — Google OAuth / GitHub OAuth
  ❌ 訊息推送 — email + 現有 Slack/LINE（不自建通訊）
```

#### 三條路線的分析與選擇

```
路線 A — Pure SaaS（全自建）
  ZenOS 自建一切：Dashboard + 文件儲存 + 帳戶 + 金流
  開發量：3-6 個月
  風險：重新發明 Notion/Google Drive
  結論：❌ 偏離定位

路線 B — 寄生現有平台（做成 Notion 整合 / Google Add-on）
  不自建 UI，依附平台
  開發量：1-2 個月
  風險：被平台綁架、功能受限
  結論：❌ 受限太大

路線 C — 最小 Dashboard + 引導選擇儲存層（✅ 選這個）
  自建極簡 Dashboard + 借用 OAuth + Stripe
  開發量：1.5-3 個月
  風險：Dashboard 夠不夠好
  結論：✅ 專注語意層，不重發明文件管理
```

#### 「什麼都沒有」的用戶旅程

```
老闆看到 ZenOS（可能從介紹、口碑、廣告）
  │
  ├── 登入（Google OAuth — 台灣幾乎人人有 Google 帳號）
  │
  ├── Stage 0：引導式對話（核心體驗，不需任何文件）
  │   ZenOS 問：「你公司做什麼？有幾個產品？目標是什麼？」
  │   30 分鐘後 → 全景圖出現在 Dashboard 上
  │
  │   此時 ZenOS 儲存的內容：
  │   ✅ 骨架層 ontology（從對話建立）
  │   ✅ 全景圖 + 盲點推斷
  │   ❌ 沒有任何用戶的原始文件
  │
  │   → 老闆已經看到價值了。Zero file, zero risk.
  │   → 這就是 freemium 的轉化入口
  │
  ├── Stage 1：老闆想深入（觸發付費轉化）
  │   ZenOS：「想讓我看看相關的文件嗎？」
  │
  │   → 有 Google Drive → 授權 → Adapter 讀取 → 建 ontology
  │   → 有散落文件 → Drop Zone 上傳 → 讀完建 ontology → 文件不留
  │   → 什麼都沒有 → 繼續對話補充 → 產出 Context Protocol
  │
  │   → 老闆拿到第一份 Context Protocol，可以分享給團隊
  │   → 這是付費牆的自然位置
  │
  └── Stage 2：持續治理
      ZenOS：「要不要接上你們的文件系統？」

      → 有 Google Drive → 接 Adapter，自動監控
      → 什麼都沒有 → ZenOS 建議「Google Drive 免費，我幫你設定好」
      → 資料敏感 → BYOS 方案（每客戶一個 VM）
```

### 架構模式比較與最終決策（2026-03-21 收斂）

「全公司同一套 context」只有三種根本架構模式：

```
模式 A — 分散 agents + 共享 context（✅ 選這個）
  每個人用自己的 AI（Claude / ChatGPT / Gemini / Cursor）
  所有 agents 透過 MCP 讀同一套 ontology
  ZenOS = context 層（Firestore + MCP + 治理服務）

模式 B — 全公司一個 super agent
  開一台 server 跑一個 AI，所有人跟同一個 AI 互動
  Context 天然統一（只有一個 agent）
  ZenOS = 就是這個 AI 本身

模式 C — 中央 orchestrator + 衛星 agents
  一個中央 agent 持有 context，各部門 agent 需要時問中央
  ZenOS = 中央 orchestrator
```

**選 A 的理由：**

```
1. 用戶用自己偏好的 AI — 不跟 Claude/ChatGPT/Copilot 正面競爭
2. ZenOS 不付 AI 費用 — 用戶自己的訂閱，ZenOS 只收 context 服務費
3. MCP 是跨平台標準 — Claude、ChatGPT、Gemini、Cursor 都支持
4. 專注做 context 層 — 護城河在方法論和 ontology，不在 AI 能力
5. 最符合 BYOS 原則 — 資料在客戶環境，AI 在客戶的訂閱
```

**不選 B 的理由：**

```
1. 產品定位衝突 — 變成 AI 聊天產品，跟巨頭競爭
2. AI 費用由 ZenOS 承擔 — 成本結構不健康
3. 用戶被鎖在 ZenOS 的 AI 裡 — 無法用偏好的工具
4. 需要做完整 Chat UI + Session 管理 + 併發 — 開發量大增
```

**不選 C 的理由：**

```
1. A2A 不成熟 — Anthropic/OpenAI 還沒採納
2. 架構最複雜 — 既要中央 agent 又要衛星 agent
3. 沒有比 A 明顯的好處 — MCP 已經能解決 context 共享
```

### 最終技術棧（Phase 1）

```
┌─────────────────────────────────────────────────────────────┐
│ 用戶的 AI agents（Claude / ChatGPT / Gemini / Cursor）       │
│ 每個人用自己偏好的 AI 工具                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ MCP（唯讀：讀 context）
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ ZenOS MCP Server                                             │
│                                                              │
│ read_context(company, role?)    → 回傳該角色的 context        │
│ get_panorama(company)           → 回傳全景圖                  │
│ list_blindspots(company)        → 回傳盲點推斷                │
│ propose_update(entity, changes) → 提議更新（進入治理流程）     │
│                                                              │
│ ⚠️ 不提供直接寫入 ontology 的 tool                            │
│ → agents 只能「提議」，不能「直接改」                          │
│ → 防止 AI 幻覺污染 ontology                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ 讀 / 提議寫入
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Firestore（Ontology SSOT）                                    │
│                                                              │
│ 骨架層：公司實體關係圖                                        │
│ 神經層：文件級 ontology entries + 4D 標籤                     │
│ 待確認佇列：agents 的 propose_update 進這裡                   │
│ 版本歷史：每次確認的 snapshot                                 │
└──────────────────────┬──────────────────────────────────────┘
                       ↑ 唯一寫入入口
┌─────────────────────────────────────────────────────────────┐
│ ZenOS 治理服務                                                │
│                                                              │
│ Step 2 方法論：全景圖 → 迭代收斂 → confirmedByUser            │
│ 事件源接收：git hook / Google Drive API / 對話觸發             │
│ 治理引擎：變更分類 → 影響分析 → 草稿產生                      │
│ 確認流程：骨架層需人確認 / 神經層自動 + 可覆寫                 │
│                                                              │
│ → 這是 ontology 品質的唯一守門員                              │
│ → AI agents 提議更新，治理服務決定是否採納                     │
└─────────────────────────────────────────────────────────────┘
```

**為什麼 MCP 只提供「提議」而不提供「直接寫入」：**

```
已知風險 #1：AI 標籤幻覺
  → 如果 agent 可以直接寫 ontology，幻覺會直接污染全公司 context
  → 一個 agent 的幻覺 × 全公司共享 = 災難性擴散

ZenOS 的治理流程就是為了解決這個問題：
  Agent 提議 → 治理服務驗證 → confirmedByUser → 才寫入
  這跟 git 的 PR review 是同一個邏輯
```

**跨 agent context 共享的方法論比較（完整研究記錄）：**

```
方法              跨平台？   多 agent？  即時？   非技術用戶？  成熟度      ZenOS 適用？
──────           ────────  ────────  ──────  ─────────  ──────    ──────────
MCP              ✅ 50+    ✅        即時    ❌ 需設定   Production  ✅ 主要接口
Claude Projects  ❌ Claude  ❌        即時    ✅ 最簡單   Production  ❌ 不能程式更新
RAG（向量 DB）   ✅        ✅        即時    ❌ 需建置   Production  ⚠️ Phase 2+ 補充
Google A2A       ⚠️ Google  ✅        即時    ❌         Beta       ❌ 不成熟
API 中間件       ✅        ✅        即時    ❌         風險高     ❌ 安全問題
Mem0 / Zep       ⚠️ 部分    ✅        即時    ⚠️ 部分    Production  ❌ vendor lock-in
檔案（CLAUDE.md）⚠️ 部分    ✅        批次    ❌ 需 git   Production  ✅ Phase 0.5
OpenAI GPTs      ❌ OpenAI  ❌        批次    ✅         即將淘汰   ❌

結論：MCP 是唯一同時滿足「跨平台 + 多 agent + 即時 + Production」的方案。
     RAG 可作為 Phase 2 的語意搜尋補充層，當 ontology 規模超出 context window 時啟用。
     但 SMB 的 ontology 規模不會塞爆 context window（Paceriz 完整 ontology = 7 檔 < 500 行）。
     會有那種規模的公司是 Palantir 的客群，不是 ZenOS 的。
```

### 員工資料：ZenOS 不做 HR，只做 role mapping

ZenOS 不管理員工資料（那是 Google Workspace / Microsoft Teams / ERP 的事）。ZenOS 只需要知道一件事：**這個人是什麼角色 → 決定他的 agent 拿到什麼 context。**

```
ZenOS 需要的（Firestore /companies/{id}/members/）：
  { uid, email, role, confirmedBy, createdAt }
  → role 是唯一重要的欄位

ZenOS 不需要的：
  員工編號、薪資、出勤、績效、組織架構圖
  → 那是 HR 系統 / ERP 的事

Who 維度存的是角色，不是個人：
  ontology 說「這跟行銷有關」，不說「這跟小美有關」
  小美離職、小明接手 → ontology 不用改，只改 role mapping
  角色是穩定的，人是流動的
```

Phase 0 概念驗證階段不需要實作此功能。Phase 1 只需 Google OAuth + 簡單 role 欄位。

---
