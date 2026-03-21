# ADR-001：行銷自動化技術架構

**狀態**：Accepted
**日期**：2026-03-20

---

## 背景

PM 交付了行銷自動化 Feature Spec（`docs/marketing-automation-spec.md`），包含兩個場景：
- 每日市場調查報告
- 每週行銷計劃

需要確認三個技術問題：
1. Threads 資料爬取可行性
2. Cloud 環境排程方案
3. 資料儲存架構

Barry 確認資料預計都在 Cloud 環境，不做本地 Markdown。

---

## 技術問題一：Threads 資料存取

### 結論：可行。使用 Meta 官方 Threads API。

**研究發現：**
- Meta 於 2024 年 6 月發布 Threads API，2025 年 7 月大幅擴充
- **Keyword Search API** 可搜尋所有公開貼文，支援按熱門度（TOP）或時間（RECENT）排序
- 端點：`GET /{threads_user_id}/threads_keyword_search`
- 每 24 小時最多 2,200 次查詢（每日市場調查只需 5-10 次，綽綽有餘）
- 返回欄位：id, text, media_type, permalink, timestamp, username, has_replies, is_quote_post
- 每次最多 100 筆結果

**需要的權限：**
- `threads_basic`
- `threads_keyword_search`

**限制：**
- Meta 會過濾敏感關鍵字（對我們的市場調查主題影響不大）
- 需要申請 Meta Developer App 並取得 access token

**在 ZenOS 中的實作方式：**

不用把 Threads API 包成 MCP tool。v1 的行銷自動化是 Claude Code CLI 排程任務，直接在 prompt 中指示 Claude 用 WebFetch 呼叫 Threads API 端點即可。

如果 Threads API 需要 OAuth token，則寫一個輕量 shell wrapper：
```bash
# 取得 Threads API 回應，存成暫存檔給 Claude 讀取
curl -s "https://graph.threads.net/v1.0/{user_id}/threads_keyword_search?\
  q=${KEYWORD}&access_token=${THREADS_TOKEN}" > /tmp/threads-search-result.json
```

### 考慮過的替代方案

| 方案 | 結論 |
|------|------|
| WebFetch 直接爬 Threads 網頁 | 不可行。Threads 是 SPA，需要 JS 渲染 |
| 第三方爬蟲 API（Apify 等） | 可行但不穩定，且多一層依賴 |
| 社群聆聽平台（Hootsuite 等） | 過度。我們只需要搜尋公開貼文 |
| 只用 WebSearch 不碰 Threads | **v1 備案**。如果 Threads API 申請耗時，先用 WebSearch 跑起來 |

### 決定

**主方案：Claude Code WebSearch + `site:threads.com`**

實測結果：
- `WebFetch` 直接爬 Threads 頁面 → **不行**，SPA 動態渲染，HTML 只有空殼
- `WebSearch` 用 `site:threads.com` 搜尋 → **可以**，Google 已索引 Threads 貼文，搜尋結果包含完整貼文文字、用戶名、URL

v1 直接用 WebSearch 就夠了。零依賴、不用申請 API、不用額外認證。Claude Code 原生能力直接搞定。

**備案：Threads Official API（Keyword Search）** — 如果未來需要更精確的搜尋（時間排序、用戶篩選）再申請。

---

## 技術問題二：Cloud 環境排程方案

### 結論：GCP Compute Engine VM + crontab。

**研究發現：**
- Claude Code CLI 支援非互動模式：`claude -p "prompt"` 直接輸出結果
- 支援 `--output-format json`、`--max-turns N`、`--allowedTools` 等控制參數
- 認證方式：`claude login`（OAuth，訂閱制）或 `ANTHROPIC_API_KEY`（按量制）

### 架構設計

```
GCP Compute Engine VM（e2-small，~$20/month）
├── /opt/zenos/
│   ├── marketing/
│   │   ├── prompts/
│   │   │   ├── daily-market-research.md    # 每日市場調查 prompt
│   │   │   └── weekly-marketing-plan.md    # 每週行銷計劃 prompt
│   │   ├── scripts/
│   │   │   ├── run-claude-task.sh          # 通用 wrapper（重試 + 日誌）
│   │   │   ├── daily-market-research.sh    # 每日觸發腳本
│   │   │   └── weekly-marketing-plan.sh    # 每週觸發腳本
│   │   └── output/                         # 暫存輸出（上傳 Firestore 後可清理）
│   └── CLAUDE.md                           # 專案上下文
├── /var/log/zenos/                         # 執行日誌
└── crontab:
    0 7 * * *   /opt/zenos/marketing/scripts/daily-market-research.sh
    0 8 * * 1   /opt/zenos/marketing/scripts/weekly-marketing-plan.sh
```

### 通用 Wrapper 設計（run-claude-task.sh）

```bash
#!/bin/bash
# 通用 Claude Code CLI 任務執行器
# 用法：run-claude-task.sh <prompt-file> <output-dir> [max-turns]

PROMPT_FILE="$1"
OUTPUT_DIR="$2"
MAX_TURNS="${3:-25}"
MAX_RETRIES=3
RETRY_DELAY=60
DATE=$(date +%F)
LOG_FILE="/var/log/zenos/claude-task-${DATE}.log"

for i in $(seq 1 $MAX_RETRIES); do
  echo "[$(date)] Attempt $i — Running: $PROMPT_FILE" >> "$LOG_FILE"

  claude -p "$(cat $PROMPT_FILE)" \
    --max-turns "$MAX_TURNS" \
    --output-format json \
    >> "${OUTPUT_DIR}/${DATE}.json" 2>> "$LOG_FILE"

  if [ $? -eq 0 ]; then
    echo "[$(date)] Success on attempt $i" >> "$LOG_FILE"
    exit 0
  fi

  echo "[$(date)] Failed, retrying in ${RETRY_DELAY}s..." >> "$LOG_FILE"
  sleep $RETRY_DELAY
done

echo "[$(date)] All $MAX_RETRIES attempts failed" >> "$LOG_FILE"
# TODO: 發通知（Slack webhook 或 email）
exit 1
```

### 認證方案

**主方案：Claude Max 訂閱（OAuth）**
- 在 VM 上執行一次 `claude login`，credentials 存在 `~/.claude/`
- BYOS 模型下每個客戶已有訂閱，邊際成本為零
- 風險：OAuth token 可能過期，需要監控

**備案：API Key**
- 設定 `ANTHROPIC_API_KEY` 環境變數
- 存在 GCP Secret Manager，由腳本在執行時注入
- 按量付費，每日市場調查 ~$0.05/次，成本極低

### 中斷恢復機制

1. **重試**：wrapper 腳本內建 3 次重試，間隔 60 秒
2. **補跑**：每日腳本啟動時檢查前一天的輸出是否存在，不存在則補跑
3. **監控**：Cloud Monitoring 設定 alert，若 `/var/log/zenos/` 中出現連續失敗則通知 Barry
4. **冪等**：prompt 設計為冪等（同一天重跑產出相同結構的報告，覆蓋而非累加）

### 考慮過的替代方案

| 方案 | 複雜度 | 成本 | 可靠性 | 結論 |
|------|--------|------|--------|------|
| VM + crontab | Low | ~$20/month（已含在 BYOS） | High | **選這個** |
| Cloud Run Jobs | Mid | Pay-per-run（更便宜） | Mid（cold start、auth 麻煩） | 過度 |
| Cloud Functions | High | Pay-per-run | Low（timeout 限制） | 不適合 |
| Cloud Scheduler + Pub/Sub | Mid | 類似 crontab | Mid（多一層） | 不需要 |

### 決定

**VM crontab，簡單直接。** BYOS 模型下 VM 已經存在，不增加基礎設施成本。

---

## 技術問題三：Cloud 資料儲存架構

### 結論：Firestore `campaigns` subcollection，報告內容存 document 內。

### Schema 設計

現有 `campaigns` collection 的 `type` 欄位只有 `leads` / `assets`，粒度不夠。新增 `subtype` 欄位：

```
tenants/{tenantId}/campaigns/
  - campaignId: string (auto)
  - name: string                    # "市場調查-2026-03-20" / "週行銷計劃-2026-W12"
  - type: string                    # "assets"（行銷素材類，沿用原設計）
  - subtype: string                 # 新增：market_research / weekly_plan / thread_brief / article_brief / card_brief
  - status: string                  # draft / active / completed
  - targetAudience: string | null
  - content: map                    # 報告/計劃的結構化內容（見下方）
  - metadata: map                   # 執行元資料
  - sourceText: string              # 原始 prompt 輸出（完整保留）
  - confirmedByUser: boolean        # Barry 是否已審閱
  - tags: string[]                  # 自由標籤，用於搜尋和去重
  - parentId: string | null         # 素材 brief 指向所屬的週計劃
  - createdAt: timestamp
  - updatedAt: timestamp
```

### `content` 欄位結構（依 subtype 不同）

**market_research（每日市場報告）：**
```json
{
  "date": "2026-03-20",
  "highlights": [
    { "title": "...", "summary": "...", "url": "...", "source": "..." }
  ],
  "trends": ["..."],
  "contentGaps": [
    { "topic": "...", "opportunityScore": "high/mid/low", "reason": "..." }
  ],
  "contentIdeas": ["..."],
  "rawSources": ["url1", "url2"]
}
```

**weekly_plan（每週行銷計劃）：**
```json
{
  "weekNumber": 12,
  "dateRange": "2026-03-16 ~ 2026-03-22",
  "contentPillar": "...",
  "selectionReason": {
    "marketSignals": ["引用哪幾天的報告"],
    "contentGap": "...",
    "businessConnection": "..."
  },
  "articleBrief": {
    "titleCandidates": ["...", "..."],
    "audience": "...",
    "outline": ["H2...", "H2..."],
    "keywords": ["..."],
    "cta": "..."
  },
  "threadBriefs": [
    { "hook": "...", "corePoint": "...", "hashtags": ["..."], "suggestedDay": "週二" }
  ],
  "cardBriefs": [
    { "title": "...", "pages": ["..."], "ctaText": "..." }
  ],
  "weeklyReview": null
}
```

### 文件大小考量

- 每日市場報告預估 2-5 KB JSON → Firestore 單 document 上限 1 MB，綽綽有餘
- 每週行銷計劃預估 5-15 KB JSON → 同上
- `sourceText`（完整 AI 輸出）可能 10-30 KB → 仍在 document 上限內
- **結論：全部存 Firestore document 內，不需要 Cloud Storage**

### 去重機制

每日報告需要避免重複報導。設計：
- 每份報告的 `tags` 欄位存主題關鍵字
- 產出新報告時，prompt 中附帶過去 7 天報告的 `highlights[].title` + `tags`
- Claude 在 prompt 中被指示：「以下主題已在過去 7 天報導過，除非有重大更新否則跳過」

每週計劃同理：
- prompt 中附帶過去 4 週計劃的 `contentPillar` + `threadBriefs[].corePoint`

### Firestore 查詢模式

| 查詢 | 索引需求 |
|------|----------|
| 取得過去 7 天的市場報告 | `subtype == "market_research" && createdAt > 7d ago` → 複合索引 |
| 取得過去 4 週的行銷計劃 | `subtype == "weekly_plan" && createdAt > 28d ago` → 同上 |
| 取得某週計劃下的所有素材 brief | `parentId == planId` → 單欄索引 |
| Barry 尚未審閱的報告 | `confirmedByUser == false` → 單欄索引 |

### 決定

- **新增 `subtype` 欄位**：區分 market_research / weekly_plan / thread_brief / article_brief / card_brief
- **新增 `content` map 欄位**：結構化儲存報告/計劃內容
- **新增 `metadata` map 欄位**：執行元資料（執行時間、重試次數、模型版本等）
- **新增 `parentId` 欄位**：素材 brief 指向所屬週計劃
- **新增 `tags` 欄位**：去重和搜尋用
- **全部存 Firestore**，不需要 Cloud Storage

---

## 整體架構圖

```
                        ┌─────────────────┐
                        │  Cloud Scheduler │  ← 未來如需更複雜排程
                        │  (optional)      │
                        └────────┬────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────┐
│  GCP Compute Engine VM (e2-small)                                │
│                                                                  │
│  crontab ──→ daily-market-research.sh ──→ run-claude-task.sh     │
│          ──→ weekly-marketing-plan.sh ──→ run-claude-task.sh     │
│                                                                  │
│  run-claude-task.sh:                                             │
│    1. 從 Firestore 讀取過去 N 天的報告（去重用）                    │
│    2. 從 Threads API 搜尋關鍵字（如已啟用）                        │
│    3. 組合 prompt → claude -p "..." --max-turns 25               │
│    4. 解析 Claude 輸出 → 寫入 Firestore campaigns collection     │
│    5. 記錄日誌 → /var/log/zenos/                                 │
│                                                                  │
│  認證：                                                           │
│    - Claude: ~/.claude/ (OAuth) 或 ANTHROPIC_API_KEY             │
│    - Firestore: Service Account Key (GCP IAM)                    │
│    - Threads API: THREADS_ACCESS_TOKEN (Secret Manager)          │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │  Firestore             │
                     │  tenants/{id}/         │
                     │    campaigns/          │
                     │      - market_research │
                     │      - weekly_plan     │
                     │      - thread_brief    │
                     └───────────────────────┘
```

---

## PM Spec 開放問題回覆

| PM 的問題 | Architect 結論 |
|-----------|---------------|
| ⚠️ Threads 是否有公開 API？ | **可行**。v1 直接用 Claude Code WebSearch `site:threads.com`（已實測，能取得完整貼文）。官方 API 作為備案。 |
| ⚠️ Claude Code CLI cron 排程穩定性？ | **可行**。VM crontab + wrapper 腳本（3 次重試 + 補跑 + 監控）。BYOS 模型下零邊際成本。 |
| ⚠️ campaigns schema 需要調整？ | **需要**。新增 subtype / content / metadata / parentId / tags 欄位。 |
| ❓ Barry 回饋如何輸入？ | **v1：Firestore document 的 `weeklyReview` 欄位**。Barry 可透過 Claude Code 對話輸入，AI 寫入。 |
| ❓ 品牌語氣指南？ | **v1 不預先定義**。先跑起來，從實際產出中收斂語氣，第 3-4 週再固化成 prompt 指令。 |

---

## Developer 任務拆分

### Task 1：建立排程基礎設施

**範圍**：Shell scripts + crontab + 日誌結構

**Done Criteria：**
- [ ] `run-claude-task.sh` 通用 wrapper 完成（重試邏輯、日誌記錄、失敗通知）
- [ ] `daily-market-research.sh` 觸發腳本完成
- [ ] `weekly-marketing-plan.sh` 觸發腳本完成
- [ ] crontab 設定完成（每日 07:00、每週一 08:00）
- [ ] 日誌輸出到 `/var/log/zenos/`，格式含時間戳和狀態
- [ ] 手動觸發測試通過（`./daily-market-research.sh` 能成功執行 Claude CLI 並產出輸出）

### Task 2：撰寫每日市場調查 Prompt

**範圍**：Prompt engineering，產出 `prompts/daily-market-research.md`

**Done Criteria：**
- [ ] Prompt 包含：搜尋策略（關鍵字 + 來源偏好）、輸出結構（符合 spec 定義的 6 個區塊）、去重指令
- [ ] Prompt 接受動態注入：今日日期、過去 7 天報告摘要（用於去重）
- [ ] 單獨執行 `claude -p "$(cat prompt)" --max-turns 25` 能產出符合結構的報告
- [ ] 輸出可被 JSON 解析（配合 `--output-format json`）
- [ ] 連續 3 天手動測試，報告品質穩定、不重複

### Task 3：撰寫每週行銷計劃 Prompt

**範圍**：Prompt engineering，產出 `prompts/weekly-marketing-plan.md`

**Done Criteria：**
- [ ] Prompt 包含：Content Pillar 選題邏輯、Repurposing 拆分規則、輸出結構（符合 spec）
- [ ] Prompt 接受動態注入：本週日期範圍、過去 7 天市場報告、過去 4 週主題（去重）、Barry 回饋（選用）
- [ ] 單獨執行能產出完整週計劃（含長文 brief + 5-7 則 Threads brief + 2-3 組圖卡 brief）
- [ ] Threads brief 的 Hook 具體到可直接修改後發布
- [ ] 手動測試 2 次，計劃品質穩定

### Task 4：Firestore 讀寫整合

**範圍**：Shell script 或 Python 輔助腳本，負責 Firestore 讀寫

**Done Criteria：**
- [ ] 能從 Firestore 讀取過去 N 天的 campaigns documents（指定 subtype）
- [ ] 能將 Claude 輸出解析並寫入 Firestore campaigns collection（符合 schema 設計）
- [ ] Service Account 認證正常運作
- [ ] 寫入的 document 包含所有必要欄位（subtype、content、sourceText、tags、confirmedByUser: false）
- [ ] 讀寫腳本可被 `run-claude-task.sh` 調用

### Task 5（P2，暫不需要）：Threads API 整合

> v1 用 WebSearch `site:threads.com` 已實測可行，能取得完整貼文。
> 只有在 WebSearch 無法滿足需求（例如需要精確時間排序、用戶篩選）時才啟動此任務。

**範圍**：申請 Meta Developer App + 整合 Keyword Search API

**Done Criteria：**
- [ ] Meta Developer App 申請通過，取得 `threads_keyword_search` 權限
- [ ] 能用 access token 搜尋關鍵字並取得公開貼文
- [ ] 搜尋結果可注入每日市場調查 prompt 作為額外資料來源
- [ ] Token 刷新機制設計完成

---

## 建議執行順序

```
Task 1（排程基礎設施）
    ↓
Task 2（每日市場調查 Prompt）+ Task 4（Firestore 讀寫）← 可平行
    ↓
整合測試：每日報告跑通 3 天
    ↓
Task 3（每週行銷計劃 Prompt）
    ↓
整合測試：週計劃跑通 1 次
    ↓
Task 5（Threads API，P1 延後）
```

---

*本文件由 Architect 於 2026-03-20 產出，回應 PM 的行銷自動化 Feature Spec*
