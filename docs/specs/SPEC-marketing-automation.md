---
type: SPEC
id: SPEC-marketing-automation
doc_id: SPEC-marketing-automation
title: Feature Spec: ZenOS 行銷自動化模組
status: draft
version: "0.4"
date: 2026-04-14
supersedes: null
l2_entity: 行銷定位與競爭策略
created: 2026-04-12
updated: 2026-04-14
---

# Feature Spec: ZenOS 行銷自動化模組

## 背景與動機

ZenOS 的核心定位是中小企業的 AI Context 層。行銷是最直接能展示這個價值的場景——行銷工作天然需要跨部門 context（產品狀態、受眾定義、歷史成效），而這些 context 目前散落在各處。

Paceriz 的行銷現況（REF-paceriz-marketing-before）記錄了一條 12 步手工鏈：選題→對齊產品→選受眾→想 hook→查證據→寫內容→渠道改寫→安排 CTA→回互動→追轉換→蒐集案例→回寫下輪。問題不是「沒內容」，而是**整條鏈過度手工**。

ADR-001 已驗證技術可行性（WebSearch 可搜 Threads、Claude CLI 非互動模式可行），但當時的架構假設是「一人使用、CLI 操作、Firestore 儲存」。隨著需求演進，我們需要一個**可視化、策略驅動**的行銷自動化模組，且資料走 ZenOS 正軌（PostgreSQL + MCP）。

**核心理念：AI 自動做繁瑣的事（情報蒐集、文案生成、平台適配），人只做判斷（策略設定、審核確認）。**

---

## 目標用戶

| 角色 | 場景 | 頻率 |
|------|------|------|
| **老闆 / 行銷負責人** | 管理多個產品的行銷項目，設定策略、審核文案、確認發佈。v1 可能一人身兼所有角色 | 每天 |
| **美編**（未來擴充） | 收到 AI 生成的圖片 brief（構圖、風格、元素描述），製作對應圖片後回傳 | 每週 2-3 次 |

**關鍵假設：**

- v1 先支援單人操作（一人身兼策略、執行、審核）
- 底層資料結構保留多人協作和角色分工的擴充性（reviewer、assignee 等欄位）
- 使用者已有多個產品在 ZenOS，需要為不同產品各自規劃行銷
- 美編不一定有 Claude Code，透過 Dashboard 看圖片 brief 就好

---

## 資訊架構

### 頂層結構：產品分組的行銷項目

```
Dashboard 行銷總覽（按產品分組，可展開收合）
  ├── Paceriz
  │     ├── 官網 Blog          ← 長期經營
  │     ├── Threads 社群經營    ← 長期經營
  │     └── 早鳥促銷活動        ← 短期活動（有起訖日）
  ├── ZenOS
  │     └── 技術部落格          ← 長期經營
  └── ...
```

- **產品**從 ZenOS 已有的產品 entity 拉取，使用者只需「啟用」哪些產品要做行銷
- **行銷項目**是最核心的工作單位，每個項目各自獨立（各自策略、排程、文案）
- 行銷項目不跨產品共用策略；不同產品、不同項目各自管理

### 建立行銷項目

建立時的最小欄位：

| 欄位 | 必填 | 說明 |
|------|:----:|------|
| 名稱 | ✓ | 例如「官網 Blog」「早鳥促銷」 |
| 類型 | ✓ | 長期經營 / 短期活動 |
| 起訖日 | 短期必填 | 僅短期活動需要 |

其他所有設定（受眾、語氣、頻率、平台...）留到策略設定再跟 AI 討論。

---

## 操作入口分工

這個行銷系統是**雙介面工作流**，不是單一 Web App。

### Web UI（Dashboard）負責什麼

- 看行銷項目總覽：按產品分組、狀態、待確認數
- 啟用產品、建立行銷項目
- 看項目詳情：策略摘要、排程、貼文列表
- 提供單一路徑引導：先完成策略設定再進入排程和主題
- 提供「本機 cowork 討論入口」：可直接在 Web 發訊息給本機 helper，由 helper 呼叫本機 Claude CLI
- 提供「欄位級一鍵開聊」：在策略、主題、文風、排程區塊按一鍵即可開啟對話，並自動帶入該欄位上下文
- 做審核確認：v1 自己確認即可發佈
- 對話結果可一鍵套回對應欄位，減少手動複製貼上
- 管理文風 skill：編輯、預覽測試
- 看 AI 產出的圖片 brief

### Claude Code cowork 負責什麼

- 執行 `/marketing-intel`：針對主題蒐集情報
- 執行 `/marketing-plan`：產生排程與主題規劃
- 執行 `/marketing-generate`：生成主文案與圖片 brief
- 執行 `/marketing-adapt`：產生各平台版本
- 執行 `/marketing-publish`：送出排程發佈
- 討論和更新策略、文風 skill

### 專用 runner / scheduler 負責什麼

- 定時執行情報蒐集
- 需要時執行排程發佈與失敗重試

### 不應期待在 Web UI 直接完成的事

- 不在 Dashboard 雲端側直接跑 AI skill（可透過本機 helper 代理到使用者本機 Claude CLI）
- 不在 Web UI 直接編輯完整文案內容
- 不在 Web UI 管理 Postiz OAuth 或社群帳號憑證

---

## 使用方式（v1 單人流程）

### 初次設定

1. 在 Dashboard 行銷總覽，啟用要做行銷的產品（從 ZenOS 產品列表選）
2. 為產品建立行銷項目（名稱 + 類型）
3. 進入項目，跟 AI 討論策略設定（受眾、語氣、平台、頻率...）
4. 設定文風 skill（產品級 + 平台級），用預覽測試確認效果

### 日常工作（每週）

1. 跑 `/marketing-plan` 規劃未來 1-2 週的排程和主題（滾動調整，隨時可增刪改）
2. 發文前 1-2 天，針對該主題跑 `/marketing-intel` 蒐集情報（關鍵字熱度、爆款文、內容方向）
3. 跑 `/marketing-generate` 生成主體文案（套用文風 skill）
4. 跑 `/marketing-adapt` 產生各平台版本（套用平台文風 skill）
5. 在 Web UI 逐一確認每個平台版本
6. 確認後跑 `/marketing-publish` 透過 Postiz 排程發佈

### 持續優化

- 隨時調整策略設定和文風 skill
- 根據發文效果調整排程和主題方向

---

## Spec 相容性

已比對的既有文件：

| 文件 | 關係 | 處理 |
|------|------|------|
| **ADR-001 行銷自動化技術架構** | **有衝突** | ADR-001 假設 Firestore + VM crontab + 一人使用。新方案改為 ZenOS PostgreSQL + MCP write + Claude Code cowork。ADR-001 的技術驗證仍有效，但儲存層和觸發機制需更新。**建議：ADR-001 標記為 superseded，由新 ADR 取代** |
| **ADR-033 Marketing Automation Runtime 與 Skill Packages 決策** | 已銜接 | Dashboard 讀取走 `/api/marketing/*` 聚合 read model；發佈 v1 走 skill-driven Postiz 整合；package 採可選安裝 |
| **SPEC-zenos-core** | 無衝突 | 行銷模組屬於 Application Layer，不改 Core。使用 Core 的 Knowledge Layer 和 Action Layer |
| **SPEC-product-vision** | 無衝突，高度契合 | 行銷場景完美驗證「AI Context Layer」價值 |
| **Paceriz v1.2.0 行銷計畫** | 需銜接 | 已有 4 週 Threads 發文計劃和受眾分層，可作為初始策略輸入 |
| **Paceriz Blog 文章寫作指引** | 需整合 | 已有 24 項發文前 Checklist 和 AI 禁用詞彙，應納入 Blog 平台的文風 skill |
| **Paceriz 官網發文策略 v2.0** | 需銜接 | 已有 6 篇 Blog 排程，應匯入內容計畫 |

**核心衝突處理：** ADR-001 的 Firestore 儲存架構與 ZenOS 正軌分裂。本 spec 選擇走 ZenOS 現有的 entity/entry/document 模型：

- 行銷項目 = L2 entity（type: module，掛在產品下）
- 每篇貼文 = L3 entity（type: document，掛在項目下）
- 策略設定 = strategy document（全文）+ entry（摘要，掛在項目 entity 上）
- 文風 skill = L3 document（markdown），掛在對應層級（產品級/平台級/項目級）
- 審核紀錄 = entry（掛在貼文 entity 上）

---

## 需求

### P0（必須有）

#### 內容生命週期狀態機（單一定義）

- **描述**：行銷內容從主題規劃到發佈必須遵循單一狀態流，避免各區塊使用不同語意
- **狀態定義**：

| 狀態 | 觸發時機 | 可回退 |
|------|---------|--------|
| `topic_planned` | `/marketing-plan` 產生主題 | 可回 `topic_planned`（重排程） |
| `intel_ready` | `/marketing-intel` 完成主題情報 | 可回 `topic_planned` |
| `draft_generated` | `/marketing-generate` 產生主文案 | 可回 `intel_ready`（補情報） |
| `draft_confirmed` | 使用者確認主文案 | 可回 `draft_generated`（重寫） |
| `platform_adapted` | `/marketing-adapt` 產生平台版本 | 可回 `draft_confirmed` |
| `platform_confirmed` | 所有平台版本確認完成 | 可回 `platform_adapted`（重適配） |
| `scheduled` | `/marketing-publish` 建立排程成功 | 可回 `platform_confirmed`（改期重排） |
| `published` | 平台已實際發佈 | 不回退（僅可補救） |
| `failed` | 任一關鍵步驟不可恢復失敗 | 可回上一穩定狀態重試 |

- **Acceptance Criteria**：
  - Given 任一貼文在流程中，When 顯示於 UI 或回寫 ZenOS，Then 狀態名稱必須來自上述唯一狀態集合，不得出現同義重複狀態
  - Given 狀態轉移發生，When 寫回資料，Then 必須同步保存 `from_status`、`to_status`、`timestamp`、`actor`
  - Given 使用者嘗試跨階段跳轉（例如未確認就發佈），When 觸發操作，Then 系統必須拒絕並提示合法下一步

#### 行銷項目管理

- **描述**：使用者可以啟用產品、建立行銷項目、管理項目列表。產品從 ZenOS 已有的產品 entity 拉取，不需另外建立
- **Acceptance Criteria**：
  - Given 使用者進入行銷總覽，When 尚未啟用任何產品，Then 顯示「選擇要做行銷的產品」引導，從 ZenOS 產品列表選擇
  - Given 使用者已啟用產品，When 查看總覽，Then 行銷項目按產品分組顯示，可展開收合
  - Given 使用者在某產品下按「建立行銷項目」，When 填入名稱和類型（長期經營/短期活動），Then 項目建立成功並進入項目詳情頁
  - Given 使用者建立短期活動類型的項目，When 填入表單，Then 必須設定起訖日
  - Given 使用者建立長期經營類型的項目，When 填入表單，Then 不需要起訖日

#### 首次成功流程（First Success Flow）

- **描述**：新項目進入後，使用者只能看到一條主流程引導。不允許同層並列多個起點造成猶豫
- **Acceptance Criteria**：
  - Given 使用者第一次進入某行銷項目，When 畫面載入，Then 主畫面只提供一個主 CTA：「開始設定策略」
  - Given 策略設定尚未完成，When 使用者停留在項目頁，Then 排程和主題區塊預設收合或置後，不得與主 CTA 並列為第一步
  - Given 使用者完成策略設定並執行 `/marketing-plan`，When 結果回寫，Then 狀態明確轉為「排程已建立，可開始產出內容」
  - Given 使用者未完成上一階段就嘗試下一步，When 觸發操作，Then UI 必須給出阻擋原因與可執行下一步
  - Given 使用者在任一步失敗，When 顯示錯誤，Then 必須同時顯示「目前階段」「失敗原因」「下一個可執行動作」
  - Given 新使用者開始第一輪流程，When 10 分鐘內操作，Then 能完成「策略 → 排程 → 確認 1 個主題」最小成功閉環

#### 發文策略設定

- **描述**：使用者設定行銷項目的發文策略。可透過 AI 對話討論或直接填寫。策略存在 ZenOS，Claude Code 讀取同一份
- **策略欄位定義**：

| 欄位 | 必填 | 長期經營 | 短期活動 | 說明 |
|------|:----:|:-------:|:-------:|------|
| 目標受眾 | ✓ | ✓ | ✓ | 對誰說話，可多組 |
| 品牌語氣 | ✓ | ✓ | ✓ | 文字調性描述 |
| 核心訊息 | ✓ | ✓ | ✓ | 這個項目要傳達什麼 |
| 發文平台 | ✓ | ✓ | ✓ | 使用哪些管道 |
| 發文頻率 | ✓ | ✓ | ✗ | 例如「一週 3 篇」；短期由活動排程決定 |
| 內容比例 | ✓ | ✓ | ✗ | 教學 40% / 產品 30% / 互動 30% |
| 活動目標 | | ✗ | ✓ | 具體轉換目標，如「早鳥 100 人報名」 |
| CTA 策略 | | ✓ | ✓ | 每篇結尾引導什麼動作 |
| 參考素材 | | ✓ | ✓ | 競品連結、爆款文範例、內部素材 |

- **Acceptance Criteria**：
  - Given 使用者進入新項目的策略設定，When 透過 AI 對話討論並套用結果，Then 系統解析結構化資料並填入策略欄位
  - Given 使用者直接手動填寫策略欄位，When 儲存，Then 寫入 ZenOS（strategy document + summary entry）
  - Given 策略被更新，When 下次 AI 生成文案時，Then 自動使用最新版策略
  - Given 長期經營項目，When 顯示策略表單，Then 顯示發文頻率和內容比例欄位
  - Given 短期活動項目，When 顯示策略表單，Then 隱藏發文頻率和內容比例，顯示活動目標欄位

#### 文風 Skill 體系

- **描述**：文風 skill 是可組合、可覆寫的多層樣式定義，控制 AI 生成文案的語氣和風格。存在 ZenOS（知識圖譜 + L3 文件），可透過 AI 對話修改或直接編輯，有獨立的預覽測試功能
- **三層組合模型**：

| 層級 | 範圍 | 範例 |
|------|------|------|
| 產品級 | 該產品所有行銷項目共用 | 「Paceriz 的品牌語氣：像教練朋友」 |
| 平台級 | 特定平台共用 | 「Threads 文風：150 字內、口語、emoji」 |
| 項目級 | 特定行銷項目專用 | 「早鳥促銷：急迫感但不低俗」 |

生成文案時，自動按層級組合：產品級 + 平台級 + 項目級 = 最終文風指令。

- **Acceptance Criteria**：
  - Given 使用者建立文風 skill，When 選擇層級（產品/平台/項目），Then 文風存入 ZenOS 對應層級的 L3 document
  - Given 使用者編輯文風，When 透過 AI 對話修改或直接編輯 markdown，Then 儲存後立即生效
  - Given 使用者修改文風後，When 按「預覽測試」，Then 系統用當前文風 + 範例主題即時生成一段測試文案供檢視
  - Given 預覽結果不滿意，When 使用者繼續調整，Then 可反覆「修改 → 預覽」直到滿意
  - Given 使用者要透過外部 AI 調整文風，When 在外部調好後貼回，Then 系統接受手動貼入的文風內容
  - Given `/marketing-generate` 執行時，When 組合文風，Then 自動疊加產品級 + 平台級 + 項目級（若有）文風 skill
  - Given `/marketing-adapt` 執行時，When 產生平台版本，Then 套用該平台的平台級文風 skill
  - Given 某一層級未設定文風，When 組合文風，Then 跳過該層級，不報錯

#### 內容排程與主題規劃

- **描述**：AI 根據策略設定一次產出「時間 + 主題 + 選題理由」的完整排程。排未來 1-2 週，滾動調整，隨時可增刪改。排程和內容一體規劃，排程會影響內容方向
- **Acceptance Criteria**：
  - Given 已有策略設定，When 使用者執行 `/marketing-plan` skill，Then AI 產出未來 1-2 週的排程表，每筆包含：日期、平台、主題名稱、選題理由
  - Given 排程表產出後，When 使用者在 Web UI 查看，Then 可調整主題、順序、日期，也可新增或刪除
  - Given 使用者確認排程，When 儲存回 ZenOS，Then 每個主題自動變成一個待生成的項目（draft 狀態）
  - Given 已有歷史排程，When 使用者再次執行 `/marketing-plan`，Then AI 基於既有排程做增量建議，不覆蓋已確認的主題
  - Given 排程中某個主題已進入文案生成階段，When 使用者嘗試刪除該主題，Then UI 提示該主題已有進行中的工作

#### 情報蒐集

- **描述**：發文前 1-2 天，AI 針對特定主題蒐集情報——搜尋相關關鍵字熱度、找各平台同主題的爆款文、整理建議的內容方向和角度。情報為逐篇主題服務，不是全域定時掃描
- **Acceptance Criteria**：
  - Given 排程中某個主題即將到期（1-2 天內），When 使用者執行 `/marketing-intel` skill 並指定主題，Then AI 回傳：(1) 該主題的關鍵字熱度 (2) 各平台同主題的高互動內容 (3) 建議的內容方向和切角
  - Given 情報蒐集完成，When 結果寫回 ZenOS，Then 該主題的詳情頁可看到最新情報摘要
  - Given 行銷主管設定了 scheduler，When 排程時間到，Then 由專用的行銷 runner 以非互動模式觸發 `/marketing-intel` 並寫回 ZenOS
  - Given 排程的情報蒐集失敗，When runner 完成錯誤處理，Then 至少重試 3 次；若仍失敗，則將失敗原因寫回 ZenOS，且不覆蓋上一輪成功情報

#### AI 文案生成

- **描述**：AI 根據情報、策略設定和產品知識，套用文風 skill 生成主體文案。逐篇觸發，每次只處理一個主題。同時生成圖片描述（brief）供美編使用
- **Acceptance Criteria**：
  - Given 已有情報摘要和策略設定，When 使用者執行 `/marketing-generate` skill 指定主題，Then AI 生成：(1) 主體文案（標題、內文、CTA）(2) 圖片 brief（風格、構圖、元素描述）
  - Given AI 生成文案時，When 組合文風 skill，Then 自動疊加產品級 + 項目級文風，確保文案自然、無 AI 感、符合品牌調性
  - Given AI 生成文案時，When 讀取知識地圖中的產品資訊，Then 文案中的功能描述、定價、試用規則與產品現況一致
  - Given 使用者對文案不滿意，When 跟 AI 討論修改意見，Then AI 讀取修改意見並生成新版本

#### 多平台適配

- **描述**：主體文案確認後，AI 根據各平台的格式要求，套用平台級文風 skill，自動生成平台特定版本。每個平台版本各自需要確認
- **Acceptance Criteria**：
  - Given 主體文案已確認，When 使用者執行 `/marketing-adapt` skill，Then AI 為策略中每個啟用的平台生成對應版本，並套用平台級文風 skill
  - Given 各平台版本生成完成，When 寫回 ZenOS，Then Dashboard 上每個平台版本獨立顯示為「待確認」
  - Given 某個平台版本需要修改，When 使用者跟 AI 討論修改，Then 不影響其他平台版本的狀態

#### 文案審核確認

- **描述**：v1 採自己確認模式——使用者確認即可進入下一階段。底層資料結構保留 reviewer、timestamp 等欄位，供未來多人審核擴充
- **Acceptance Criteria**：
  - Given AI 生成文案完成，When 寫回 ZenOS，Then Dashboard 顯示該文案為「待確認」狀態
  - Given 使用者在 Dashboard 按「確認」，Then 狀態變為「已確認」，可進入平台適配或發佈
  - Given 使用者對文案不滿意，When 跟 AI 討論修改，Then AI 根據意見調整後生成新版本
  - Given 任一確認動作被提交，When 系統寫回 ZenOS，Then 必須保存 reviewer、comment（可選）、timestamp 與當前狀態
  - Given v1 為單人操作，When 確認流程執行，Then 不需要指派 reviewer 或多層簽核，自己確認即完成

#### 排程發佈（透過 Postiz）

- **描述**：已確認的貼文透過 Postiz API 排程發佈到對應平台。Postiz 支援 32+ 平台（Threads、IG、FB、LinkedIn、X、TikTok 等），自架 Docker 部署。v1 即打通自動發佈
- **Acceptance Criteria**：
  - Given 所有平台版本已確認且設定排程時間，When 使用者執行 `/marketing-publish` skill，Then 透過 Postiz API 建立排程貼文
  - Given Postiz 排程發佈成功，When 狀態回傳，Then ZenOS 更新該貼文狀態為「已排程」或「已發佈」
  - Given `/marketing-publish` 需要連接 Postiz，When 讀取憑證時，Then 應由 Postiz 專用部署與 secret 管理提供，不由 Dashboard 保存或代管社群平台帳號憑證
  - Given Postiz 回傳 429 或 5xx，When 發佈流程執行，Then runner 至少重試 3 次並採退避；若仍失敗，則將失敗狀態與原因寫回 ZenOS，不得靜默吞掉

#### Web 直連 cowork 討論（Local Helper）

- **描述**：在不要求使用者輸入 API key 的前提下，Web 可以透過本機 helper 對接本機 Claude Code CLI，完成策略討論和多輪續聊。helper 啟動時自動載入 ZenOS MCP 設定和 marketing skill，讓每次對話一開始就是一個懂 ZenOS、會用行銷 skill 的 agent
- **Acceptance Criteria**：
  - Given 使用者已在本機完成 Claude Code 登入，When 在 Web 點「AI 討論」送出訊息，Then 前端可收到串流回覆
  - Given 同一項目持續討論，When 送出下一則訊息，Then helper 使用同一 conversation 對應的 Claude session 續聊（resume）
  - Given helper 不可用或未啟動，When 使用者送出訊息，Then UI 顯示可執行修復指引（啟動 helper / 檢查本機登入）
  - Given helper 收到跨來源請求，When Origin 或本機配對 token 不符，Then 拒絕請求且不執行 Claude CLI
  - Given 使用者要求停止生成，When Web 送出 cancel，Then helper 可中止當前 CLI process
  - **Context 注入（兩層模型）**：
  - Given helper 啟動 Claude CLI，When 初始化 session，Then 必須自動帶入：(1) `--mcp-config` 指向 ZenOS MCP 設定 (2) `cwd` 指向含 CLAUDE.md 和 `.claude/settings.json` 的專案目錄（預載 marketing skill 定義 + allowedTools 白名單）。權限白名單唯一來源為 `.claude/settings.json`，helper 不另外傳 CLI `--allowedTools` 參數
  - Given helper 已正確載入設定，When AI 收到第一則訊息，Then AI 已具備 ZenOS 讀寫能力和所有 `/marketing-*` skill，使用者無需手動指定
  - **Capability 檢查與降級**：
  - Given helper 啟動 Claude CLI session，When session 初始化完成，Then helper 必須執行 capability probe：嘗試呼叫 `mcp__zenos__search(query="health-check", limit=1)` 驗證 MCP 連線，並在 SSE 串流中回傳 `capability_check` 事件（含 `mcp_ok: boolean`、`skills_loaded: string[]`）
  - Given capability probe 發現 MCP 不可用，When 回報前端，Then UI 顯示「ZenOS 連線失敗：AI 仍可對話但無法讀寫資料」降級提示，對話功能不中斷
  - Given capability probe 發現 skill 未載入，When 回報前端，Then UI 顯示「部分 skill 未載入」警告，列出缺失項目
  - **權限確認策略（白名單 + console fallback）**：
  - Given 專案 `.claude/settings.json` 已設定 allowedTools 白名單（涵蓋 marketing skill 所需的 MCP tool），When AI 執行白名單內的 tool，Then 自動放行，Web 使用者無感
  - Given AI 觸發白名單外的 tool，When 需要權限確認，Then 權限請求出現在 helper 的 terminal console 中，由啟動 helper 的本機使用者在 console 確認；Web 端不卡住，但顯示「等待本機確認中」狀態提示
  - Given console 權限確認等待超過 60 秒，When timeout 觸發，Then helper 自動拒絕該 tool call，AI 收到拒絕後繼續對話（不中斷 session），Web UI 顯示「本機權限確認逾時，該操作已跳過」
  - Given 本機無人可確認（例如 helper 以 daemon 模式運行），When 觸發白名單外的 tool，Then 等同 timeout 處理——自動拒絕，AI 繼續對話
  - Given v1 不支援 Web 端代理權限確認，When 使用者在 Web 看到「等待本機確認」，Then UI 提示「請到本機 terminal 確認」，不提供 Web 確認按鈕
  - Given helper 不使用 `--dangerously-skip-permissions`，When 任何 tool 被呼叫，Then 安全邊界始終生效，白名單外的操作必須經過人工確認

#### 欄位級一鍵開聊（Auto Context Launch）

- **描述**：每個核心欄位都提供「討論這段」按鈕，點擊後自動彈出對話視窗，預載該欄位需要的背景與建議 skill，使用者不需手動補背景。前端負責組裝動態上下文（欄位值、項目摘要、階段），helper 端負責固定底層（MCP + skill + CLAUDE.md）
- **Acceptance Criteria**：
  - **Context Pack 結構定義**：
  - 每個欄位的 context pack 由前端組裝，結構如下：

    | 欄位 | 必帶 | 說明 |
    |------|:----:|------|
    | `field_id` | ✓ | 欄位識別（strategy / topic / style / schedule / review） |
    | `field_value` | ✓ | 欄位目前值（無值時為 null） |
    | `project_summary` | ✓ | 項目名稱 + 產品 + 類型 + 策略摘要（≤500 字） |
    | `current_phase` | ✓ | 目前流程階段（strategy / schedule / intel / generate / adapt / publish） |
    | `suggested_skill` | ✓ | 建議的 skill 名稱 |
    | `related_context` | | 相關情報摘要、審核意見等（≤1000 字） |

  - context pack 整體上限 2000 字。超過時按優先序截斷：field_value > project_summary > related_context
  - 欄位值中的敏感資訊（API key、token、密碼）不得帶入 context pack；前端在組裝時需過濾已知敏感欄位
  - 敏感欄位規則來源統一為 `dashboard/src/config/ai-redaction-rules.ts`（pattern + key 名單）；不得在各頁各自硬寫
  - 每次 redaction 規則調整必須增加 `redaction_rules_version`，並在 helper capability 事件回傳目前版本，供前端顯示與追查
  - Given 使用者輸入未知格式的疑似敏感字串，When 命中 redaction pattern，Then 必須以 `[REDACTED]` 取代後再送入 context pack
  - **Prompt 組裝（前端動態上下文）**：
  - Given 使用者在策略、主題、文風、排程區塊按下「討論這段」，When 對話視窗開啟，Then 前端依 context pack 結構組裝首輪 prompt
  - Given 欄位**尚無值**（新建模式，field_value = null），When 前端組裝 prompt，Then 使用引導式模板（例：「幫我設定這個項目的 XXX，以下是項目背景：...」）
  - Given 欄位**已有值**（修正模式，field_value 有內容），When 前端組裝 prompt，Then 使用修正式模板（例：「以下是目前的 XXX：{現有值}。我想調整，請提供修改建議」），使用者不需手動複製貼上現有內容
  - Given 對話視窗開啟，When 系統完成預載，Then UI 顯示「已載入上下文清單」（可展開）而不是要求使用者自行敘述背景
  - Given 使用者從不同欄位發起討論，When 視窗初始化，Then 系統需產生新的 context pack，不得沿用上一欄位內容
  - Given 欄位對應 workflow，When 對話開始，Then 系統需預選建議 skill（策略對應 `/marketing-plan`；主題/文案對應 `/marketing-generate`；平台版本對應 `/marketing-adapt`；發佈對應 `/marketing-publish`）
  - **對話結果回寫（三階段流程 + 回寫契約）**：
  - Given 使用者與 AI 完成自然對話，When 使用者認為結果可接受，Then 使用者可透過自然語言（如「就這樣」「確定」）或 UI 上的「整理結果」按鈕觸發 AI 整理
  - Given 使用者觸發整理，When AI 收到整理請求，Then AI 將對話結論整理為結構化摘要，以約定格式呈現在對話中，供使用者預覽
  - 回寫契約：AI 輸出的結構化摘要必須包含 `target_field`（目標欄位 ID）和 `value`（結構化內容）。前端依 `target_field` 映射到對應 UI 欄位：

    | target_field | 對應 UI 欄位 | 值型別 |
    |-------------|-------------|--------|
    | `strategy` | 策略設定各子欄位 | JSON object |
    | `topic` | 主題名稱 + 描述 | JSON object |
    | `style` | 文風 skill 內容 | markdown string |
    | `schedule` | 排程項目 | JSON array |
    | `draft` | 主體文案 | JSON object |
    | `platform_draft` | 平台版本文案 | JSON object |

  - `value` 必填 schema（最小集合）：

    | target_field | `value` 必填鍵 |
    |-------------|----------------|
    | `strategy` | `audience`, `tone`, `core_message`, `platforms` |
    | `topic` | `title`, `brief` |
    | `style` | `content` |
    | `schedule` | 每筆需有 `date`, `platform`, `topic`, `reason` |
    | `draft` | `title`, `body`, `cta` |
    | `platform_draft` | `platform`, `title`, `body`, `cta` |
  - Given 結構化摘要缺少對應 target_field 的必填鍵，When 前端驗證，Then 不顯示「套用到欄位」，改顯示缺漏鍵清單

  - Given AI 已輸出結構化摘要，When 前端偵測到約定格式且 `target_field` 合法，Then 顯示「套用到欄位」按鈕並預覽變更差異
  - Given 使用者按下「套用到欄位」，When 系統執行套用，Then 前端解析結構化資料 → 立即更新 UI 欄位 → 同步寫回 ZenOS，並保留「來源：AI 對話」紀錄
  - 覆蓋規則：套用時比對欄位的 `updated_at`，若欄位在對話期間被其他來源更新，則顯示衝突提示讓使用者選擇「覆蓋」或「放棄」，不靜默覆蓋
  - Given 使用者未觸發整理就關閉對話，When 視窗關閉，Then 不更新任何欄位，對話紀錄保留在 session 中可續聊
  - **負向案例處理**：
  - Given AI 輸出的結構化摘要 JSON 不可解析，When 前端嘗試 parse，Then 不顯示「套用」按鈕，改顯示「格式異常，請重新整理」提示，使用者可再次觸發整理
  - Given AI 回覆中途被 helper 中斷（crash / timeout），When 串流意外結束，Then UI 顯示「對話中斷」+ 重試按鈕，不丟失已收到的對話內容
  - Given ZenOS MCP 暫時不可用，When 套用寫回失敗，Then UI 顯示「寫入失敗，稍後重試」，已更新的前端 state 保留不丟棄，使用者可手動重試寫回
  - **Helper 不可用時的降級**：
  - Given helper 不可用，When 使用者按「討論這段」，Then 視窗仍彈出但主動作改為「啟動 helper」，且顯示修復步驟

#### AI 對話視窗狀態機

- **描述**：AI 對話視窗有明確的狀態轉移模型，確保 UI 在各狀態下行為一致、可預測
- **狀態定義**：

| 狀態 | 說明 | UI 行為 |
|------|------|---------|
| `idle` | 視窗開啟，等待使用者輸入 | 顯示輸入框 + 已載入上下文清單 |
| `loading` | 等待 helper 回應（session 初始化 / capability probe） | 顯示 loading 指示器，禁用輸入 |
| `streaming` | AI 正在串流回覆 | 即時顯示文字，顯示「停止」按鈕 |
| `awaiting-local-approval` | 等待本機 console 權限確認 | 顯示「等待本機確認中」提示 |
| `apply-ready` | AI 輸出了結構化摘要，可套用 | 顯示「套用到欄位」按鈕 + 變更預覽 |
| `applying` | 正在寫回 ZenOS | 顯示寫入中指示器 |
| `error` | helper 不可用 / 串流中斷 / 寫回失敗 | 顯示錯誤訊息 + 可執行的修復動作 |

- **狀態轉移**：

```
idle → loading（送出訊息）
loading → streaming（收到首個 SSE event）
loading → error（helper 無回應 / 連線失敗）
streaming → idle（AI 回覆完成，一般對話）
streaming → apply-ready（AI 輸出結構化摘要）
streaming → awaiting-local-approval（收到 permission_request SSE event）
streaming → error（串流中斷）
awaiting-local-approval → streaming（console 確認通過）
awaiting-local-approval → streaming（timeout 後 AI 繼續對話）
apply-ready → applying（使用者按套用）
apply-ready → idle（使用者按取消或繼續對話）
applying → idle（寫回成功）
applying → error（寫回失敗，前端 state 保留）
error → idle（使用者按重試 / 重新連線）
```

- **Acceptance Criteria**：
  - Given 對話視窗處於任一狀態，When 狀態轉移發生，Then UI 必須即時反映新狀態，不得出現無回饋的空白等待
  - Given 狀態為 `streaming`，When 使用者按「停止」，Then 送出 cancel → 狀態回到 `idle`
  - Given 狀態為 `error`，When 顯示錯誤，Then 必須同時顯示可執行的下一步（重試 / 啟動 helper / 檢查連線）

#### Dashboard 可視化

- **描述**：Dashboard 提供產品分組的行銷項目總覽，點進項目看到策略、排程、貼文列表及其狀態
- **Acceptance Criteria**：
  - Given 多個產品有行銷項目，When 使用者打開行銷總覽，Then 看到按產品分組的行銷項目列表，可展開收合
  - Given 點進某個行銷項目，When 載入詳情，Then 看到：(1) 策略摘要 (2) 排程（未來 1-2 週主題列表）(3) 待確認的貼文 (4) AI 準備中的貼文 (5) 已發佈的貼文
  - Given Dashboard 載入 marketing 頁，When 使用者查看總覽或詳情，Then 畫面資料必須來自 ZenOS 聚合 read model，而不是前端本地 mock
  - Given 桌機（>=1024px）進入項目詳情，When 畫面渲染，Then 採雙欄版面：主內容區（流程與貼文）+ 右側常駐 AI 討論區
  - Given 手機（<1024px）進入項目詳情，When 畫面渲染，Then AI 討論區改為浮動按鈕開啟全高對話抽屜，不遮擋主流程
  - Given 項目有待確認貼文，When 詳情頁載入，Then 「待你確認」區塊必須位於可視區上半部（優先於歷史列表）
  - Given 項目尚未有任何貼文，When 詳情頁載入，Then 顯示空狀態與唯一下一步按鈕，不得同時出現多個同優先級入口
  - Given 頁面處於 loading 或錯誤，When 顯示狀態，Then 必須明確標示目前階段與可執行下一步

#### 操作入口清楚

- **描述**：使用者必須看得出每一步應在哪個介面完成，避免把 Web UI 誤認為完整內容工作台
- **Acceptance Criteria**：
  - Given 使用者第一次進入 Dashboard 行銷頁，When 查看畫面，Then 先看到單一路徑（先啟用產品、建項目）而不是多入口並列
  - Given 進入項目詳情頁，When 頁首渲染，Then 必須有「流程階段列（策略→排程→情報→生成→確認→發佈）」與單一主 CTA
  - Given 使用者在任一階段停留，When 查看畫面，Then 必須看到目前階段（討論中/待套用/已套用/可產排程/可建主題）
  - Given 任一欄位需要討論，When 使用者點「討論這段」，Then 對話視窗直接進入該欄位上下文，不要求補背景說明
  - Given 使用者確認排程中某個主題，When 主題進入 draft，Then UI 必須明確提示下一步是執行 `/marketing-intel` 或 `/marketing-generate`
  - Given 使用者完成主文案確認，When 留在 Web UI，Then UI 必須明確提示下一步是執行 `/marketing-adapt`
  - Given 所有平台版本確認完成，When 留在 Web UI，Then UI 必須明確提示下一步是執行 `/marketing-publish`
  - Given 使用者用鍵盤操作，When 在頁面切換主 CTA、討論按鈕、確認按鈕，Then 全流程可達且有明確 focus 樣式（不可只靠顏色提示）

### P1（應該有）

#### 成效追蹤

- **描述**：貼文發佈後，透過 Postiz 內建 analytics 或各平台 API 回收成效數據，寫回 ZenOS 供 Dashboard 顯示和供 AI 作為下輪選題依據
- **Acceptance Criteria**：
  - Given 貼文已發佈，When 定期執行成效回收，Then 該貼文的成效數據（按讚、留言、分享、點擊）更新到 ZenOS
  - Given 成效數據已更新，When AI 生成下一輪內容計畫時，Then 引用上輪成效作為選題依據
  - Given 貼文狀態為 `scheduled` 或 `published`，When 定時成效同步執行，Then 由行銷 runner 定期拉取 Postiz analytics，回寫 likes、comments、shares、clicks、saves、captured_at 到 ZenOS
  - Given 本輪成效同步失敗，When runner 結束，Then 保留上一輪成功 metrics，並將 sync failure 寫回 ZenOS

#### Prompt 模板管理

- **描述**：各環節的 prompt 模板可以被檢視和編輯。模板有版本紀錄，可以回滾。存在 ZenOS 而非各人的 Claude Code
- **邊界定義（避免和文風 skill 重疊）**：

| 項目 | 文風 skill（P0） | Prompt 模板（P1） |
|------|------------------|-------------------|
| 目的 | 定義品牌語氣與寫作風格 | 定義 workflow 指令骨架與欄位契約 |
| 主要維護者 | 行銷使用者 | 系統管理者/進階使用者 |
| 變更頻率 | 高（可每週調整） | 低（有版本審核） |
| 對日常 UI | 直接可見可編輯 | 預設隱藏在進階設定 |

- **組合優先序**：`Prompt 模板（系統骨架）` → `文風 skill（語氣風格）` → `欄位 context pack（當次情境）`
- **Acceptance Criteria**：
  - Given 使用者在日常流程調整語氣，When 編輯設定，Then 只能影響文風 skill，不得直接改寫 prompt 模板骨架
  - Given 管理者更新 prompt 模板，When 套用到執行流程，Then 文風 skill 仍以變數插槽方式注入，不被模板覆蓋
  - Given 使用者要調整某個 skill 的 prompt，When 透過 Claude Code 修改並寫回 ZenOS，Then 下次 AI 生成都使用新版 prompt
  - Given prompt 被更新，When 查看版本紀錄，Then 看到歷次修改和對應的效果變化

#### Postiz 整合深化

- **描述**：串接 Postiz 更多功能，包括自動讀取平台帳號列表、支援圖片附件上傳、讀取 Postiz 內建 analytics 回寫 ZenOS
- **Acceptance Criteria**：
  - Given Postiz 已連接多個社群帳號，When 執行 `/marketing-adapt`，Then 自動列出可用平台供選擇
  - Given 美編上傳圖片到 ZenOS，When 執行 `/marketing-publish`，Then 圖片一併透過 Postiz API 發佈

### P2（可以有）

#### 社群互動 AI 輔助

- **描述**：AI 監控各平台留言和 DM，對簡單問題建議回覆，複雜問題標記給人處理。公開留言回覆需人工確認後才送出
- **Acceptance Criteria**：
  - Given 有新留言，When AI 判斷可回覆，Then 建議回覆內容，待人確認後送出
  - Given 留言內容複雜或負面，When AI 無法處理，Then 標記並通知對應人員

#### A/B 測試

- **描述**：同一主題可生成多個版本的文案，分別發佈後比較成效
- **Acceptance Criteria**：
  - Given 同一主題生成 A/B 兩個版本，When 分別發佈並追蹤，Then Dashboard 並排顯示兩版成效

---

## Rollout 與 Migration

### 與既有 AI 討論入口的關係

Dashboard 現有的 cowork helper 整合（`cowork-helper.ts`）是通用的 AI 對話橋接。新的「欄位級一鍵開聊」建立在相同的 helper 基礎設施上，差異在於自動注入 context pack。

| 入口 | 觸發方式 | context 注入 | 狀態 |
|------|---------|-------------|------|
| 通用 AI 對話 | 右側常駐討論區直接輸入 | 無自動注入，使用者自行描述 | 保留，作為自由對話入口 |
| 欄位級一鍵開聊 | 欄位旁「討論這段」按鈕 | 自動注入 context pack | 新增 |

兩者共用同一個 helper 連線和 session 管理，不衝突。通用入口不會被移除——使用者仍可自由對話而不綁定特定欄位。

### Migration 計畫

- Phase 1：新增「討論這段」按鈕到所有核心欄位，通用對話入口保持不變
- Phase 2：觀察使用數據，若「討論這段」覆蓋率足夠，可考慮簡化通用入口的 UI 露出（但不移除功能）
- 無需資料 migration——兩種入口寫回同一個 ZenOS entity，資料格式一致

### Rollout 成功與回退判準

- **Phase 1 成功條件（連續 7 天）**：
  - `欄位級一鍵開聊啟用率 >= 60%`（在可討論欄位中，至少 60% 是從「討論這段」發起）
  - `對話後一鍵套用成功率 >= 85%`
  - `helper 連線失敗率 < 5%`
  - `權限確認 timeout 率 < 10%`
- **Phase 2 進入條件**：
  - Phase 1 成功條件全部達成，且無 P0 blocker bug
- **回退條件（任一成立即回退 UI 露出）**：
  - 一鍵開聊相關錯誤導致無法完成主流程（策略→排程→生成）超過 3 次/日
  - 套用回寫錯誤率連續 2 日超過 15%
  - helper 能力探測異常（`mcp_ok=false`）連續 2 日超過 20%
- **回退策略**：
  - 保留通用 AI 對話入口為主入口
  - 欄位級按鈕改為次要入口（可隱藏）
  - 已有資料不回滾，僅回退互動入口與導引

---

## 明確不包含

- **不做內容編輯器**：文案編輯在 Claude Code cowork 中完成，Dashboard 只做顯示和確認操作
- **不做雲端 Web 版 skill 執行器**：`/marketing-*` 工作流仍在 Claude Code cowork 或專用 runner 執行；Web 僅可呼叫「使用者本機 helper」代理本機 Claude CLI
- **不做圖片生成**：AI 產出圖片 brief，圖片製作由美編在外部工具完成
- **不做社群帳號管理**：帳號 OAuth 在 Postiz 上管理，ZenOS 不處理
- **不做即時聊天機器人**：不做 DM 自動回覆
- **不做通用行銷工具**：依賴 ZenOS 知識地圖，不是獨立 SaaS
- **不新增 MCP tool**：用現有 search/get/write/confirm/task/journal_write 組合
- **不改 ZenOS Core 資料模型**：用現有 entity/entry/document 模型
- **v1 不做成效追蹤**：先跑通策略→排程→生成→確認→發佈的主線，成效追蹤留 P1
- **v1 不做多人審核流程**：自己確認即可，底層資料結構保留擴充性

---

## 技術約束（給 Architect 參考）

| 約束 | 原因 |
|------|------|
| 資料走 ZenOS MCP，不走 Firestore | 統一資料層，避免 ADR-001 的 Firestore 方案與 ZenOS 正軌分裂 |
| AI 呼叫用 Claude 訂閱額度，不用 API key | 客戶已有 Claude Code 訂閱，避免額外費用 |
| Skill 結構存 repo，策略和文風存 ZenOS | 不常改的走 git 同步；常改的走 MCP 即時同步 |
| 文風 skill 存 ZenOS L3 document（markdown） | 支援三層組合（產品/平台/項目）、即時修改、預覽測試 |
| Dashboard 不直連雲端 LLM API | Web 只連本機 helper，AI 運算在使用者本機 Claude CLI |
| helper 只監聽 localhost + 驗證 Origin/token | 防止任意網站濫用本機 Claude 能力 |
| 用現有 entity/entry/document/details 模型 | 行銷項目=L2 entity、貼文=L3 entity、策略全文=document + 摘要entry、文風=L3 document |
| 產品 entity 從 ZenOS 拉取，不另建 | 使用者只需「啟用」已有產品，不重複建立 |
| 情報蒐集 v1 用 WebSearch | ADR-001 已驗證 WebSearch site:threads.com 可行 |
| scheduler 不跑在 Dashboard 或 MCP server | 情報蒐集 / 發佈由專用行銷 runner 觸發，避免靜態站與核心 API 承擔 AI runtime |
| 發佈走 Postiz（獨立部署） | Postiz 支援 32+ 平台，開源自架；與 ZenOS API 分開部署可隔離 OAuth、升級與故障面 |
| Postiz 憑證由基礎設施層管理 | 社群帳號 OAuth 與 API token 由 Postiz + secret manager 管理，rotation 不在 Dashboard 內處理 |
| review 併發 v1 採 last-write-wins | 先保留完整 audit trail，不在 P0 導入 optimistic locking |
| v1 審核 = 自己確認 | 底層保留 reviewer/timestamp 欄位供未來多人擴充 |
| 5 個 skill 封裝所有複雜度 | `/marketing-intel`、`/marketing-plan`、`/marketing-generate`、`/marketing-adapt`、`/marketing-publish` |

---

## Skill 清單

| Skill | 做什麼 | 主要使用介面 | 觸發方式 |
|-------|--------|-------------|---------|
| `/marketing-intel` | 情報蒐集：針對特定主題搜社群、找爆款、整理方向建議，寫回 ZenOS | Claude cowork / runner | 手動 or 專用 runner scheduler |
| `/marketing-plan` | 排程與主題規劃：根據策略產出 1-2 週「時間+主題+理由」排程，寫回 ZenOS | Claude cowork | 手動 |
| `/marketing-generate` | 文案生成：讀策略+情報+產品知識+文風 skill，生成主體文案+圖片 brief | Claude cowork | 手動（逐篇觸發） |
| `/marketing-adapt` | 平台適配：主體文案→各平台版本，套用平台文風 skill，各自寫回 ZenOS | Claude cowork | 手動（逐篇觸發） |
| `/marketing-publish` | 發佈：呼叫 Postiz API 排程發佈 | Claude cowork / runner | 手動 or 專用 runner scheduler |

---

## 開放問題

| # | 問題 | 影響範圍 | 建議 |
|---|------|---------|------|
| 1 | 美編工作流怎麼整合？ | 圖片素材 | 圖片 brief 存為 entry，美編在 Dashboard 看 brief → 外部製作 → 上傳 ZenOS。具體 UI 待 Designer 定義 |
| 2 | 文風 skill 的初始版本誰寫？ | 啟動依賴 | Paceriz 已有 Blog 寫作指引（24 項 Checklist + AI 禁用詞）和 Threads 策略，可作為基礎轉為文風 skill |
| 3 | P0 是否要把圖片附件發佈一併算入驗收？ | 發佈邊界 | 若算 P0，需補圖片上傳與 Postiz 附件 contract；若不算，維持 P1 |
| 4 | 文風預覽測試的「範例主題」從哪來？ | 預覽功能 | 可用最近一個排程主題，或讓使用者自行輸入測試主題 |
| 5 | 長期經營項目的排程是否需要「自動延展」？ | 排程管理 | 例如每兩週自動提醒規劃下一輪，或使用者手動觸發 |
