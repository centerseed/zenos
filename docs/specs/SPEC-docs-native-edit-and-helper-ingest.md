---
type: SPEC
id: SPEC-docs-native-edit-and-helper-ingest
status: Under Review
ontology_entity: l3-document
created: 2026-04-20
updated: 2026-04-23
depends_on: SPEC-doc-governance, SPEC-ontology-architecture v2 §8.1, SPEC-document-delivery-layer, SPEC-batch-doc-governance
---

> **Layering note（2026-04-23）**：本 SPEC 原依賴的 `SPEC-document-bundle` 與 `SPEC-doc-source-governance` 已於 2026-04-23 併入 `SPEC-doc-governance`；本 SPEC 內以下敘述的「bundle 基石規則」改以 `SPEC-doc-governance §3`（doc_role / sources / bundle_highlights / URI validation / read_source）為準。為保留歷史可讀性，正文內對 `SPEC-document-bundle` 的引用已全面替換為 `SPEC-doc-governance §3`；少數地方以註記形式保留舊名。

# Feature Spec: Dashboard 原生文件編輯 + Helper Ingest Contract

## 背景與動機

ZenOS 的 L3 document entity 已在 `SPEC-doc-governance §3` 定義為多源語意索引（一個 bundle 對應 1..N 份 source）。但今天非 GitHub 用戶要把資料餵進 ZenOS 仍有結構性缺口：

**缺口 1：沒有原生編輯入口。**
當用戶沒有 GitHub 習慣、也不想先去 Notion 開一份再連回來，目前只能用 `POST /api/docs/{doc_id}/content` 的 REST API，沒有 Dashboard UI。Mockup 的「+新」、編輯器、右側大綱 / AI rail 並不存在。

**缺口 2：Helper ingest 沒有合約。**
為了規避 Google Workspace Add-on 審核與 GDrive CASA 認證，ZenOS **不做原生 OAuth**，改由用戶自己的 Helper（Claude Desktop + Notion MCP + ZenOS MCP 等）在用戶 session 內拉 Notion / GDrive 內容，呼叫 `write(collection="documents")` 推進 ZenOS。但目前 `write` 沒有讓 helper 表達「這份 source 等同於 Notion pageId=xxx」的欄位，無法做 upsert；helper 重跑只會堆新 source，不會收斂。

**缺口 3：Re-sync 行為沒有定義。**
既有 schema 只有 `source_status: valid/stale/unresolvable`，但沒有「用戶按重新同步」、「agent 偵測到 stale 自動拉」的操作行為。結果是外部文件在 Notion 改了，ZenOS 這端不知道，也沒路徑觸發更新。

本 spec 只處理這三個缺口，其餘 L3 文件治理規則（多源聚合、bundle_highlights、URI 驗證、read_source）維持 `SPEC-doc-governance §3` 定義。

### 產品定位

- ZenOS 仍是語意索引層。外部文件的真相來源永遠在原生系統（Notion / GDrive）。
- Helper 模式把 ingestion 責任推到 client 端。ZenOS server 不主動出網抓取任何外部文件。
- 「原生文件」= 用戶主動在 ZenOS 編輯的 markdown；storage 在 GCS private（Delivery Snapshot 模式），source.uri 指回 ZenOS 自身 permalink。

## 目標用戶

| 角色 | 場景 | 核心需求 |
|------|------|---------|
| **SMB 老闆 / PM** | 想把「本週重點」、Sprint 計畫直接寫在 ZenOS，不想學 Git | Dashboard 有 Notion-like 編輯器，儲存即綁 L2 |
| **Notion 重度使用者** | 公司文件散在 Notion，希望 ZenOS 也能看到 | Claude Desktop + Notion MCP + ZenOS MCP，講一句話把 Notion 頁拉進來；下次再講一次能覆蓋更新 |
| **GDrive 用戶** | 想讓 ZenOS 的 agent 能讀到 GDrive 內容，但公司 IT 不想裝新 OAuth 工具 | 同上，helper 用用戶自己 Google 登入的 session 取內容，ZenOS 不碰 OAuth |
| **AI Agent** | 從 L2 取 context 時要能消費 source 內容 | Dashboard 的原生文件內容可讀；Helper 推入的 source 帶可選 snapshot，agent 不總是依賴 helper 現拉 |

## Spec 相容性

| Spec | 分析 | 處理方式 |
|------|------|---------|
| **`SPEC-doc-governance §3`**（2026-04-23 吸收舊 `SPEC-document-bundle`）| 多源聚合、bundle_highlights、URI 驗證、read_source 定義維持不變。本 SPEC 在其基礎上擴展三個欄位（external_id、external_updated_at、last_synced_at）並新增 write 的 helper upsert 語義。 | 本 SPEC 引用 bundle 規則為基石，不重新定義既有欄位。**需對 `SPEC-doc-governance` 發 amendment**：將「儲存文件內容 / 文件編輯器」的舊排除條款收斂為本 SPEC 定義的 Delivery Snapshot + Helper snapshot 兩種合法儲存模式（見 §Spec 相容性附記）。 |
| **SPEC-doc-governance** (Approved) | 既有文件治理規則適用。本 spec 不改 frontmatter / doc_type / dispatch gate 規則。 | 無衝突。 |
| **SPEC-ingestion-governance-v2** (Draft) | 該 spec 定義「Zentropy 在 client 端跑沉澱邏輯、用既有 ZenOS MCP tools 做 mutation」的分治邊界。本 spec 的 Helper 模式走同一條路徑（`write(collection="documents")`），不新增 `/api/ext/*` endpoint。 | 相容。本 spec 是該決策的具體落地之一：Helper = 另一種 client-side ingestion agent。 |
| **SPEC-dashboard-ai-rail** | Mockup 右欄「Agent 建議」「Agent 改寫」屬 AI rail 範疇。 | 本 spec 只定義編輯器本體；AI rail 整合走 ai-rail spec，不重定義。 |
| **L2 entity「知識系統 Adapter 策略」** | 該 entity summary 原本把 GDrive OAuth / Notion polling 列為 P2。 | **本 spec 改寫該 L2 的核心決策**：GDrive / Notion / Local 一律走 Helper 模式，ZenOS 不做原生 OAuth。Spec approved 後需 update L2 entity summary 與 sources。 |

**無其他衝突**。已比對 `SPEC-doc-governance`、`SPEC-doc-governance §3`、`SPEC-doc-source-governance` (Superseded)、`SPEC-ingestion-governance-v2`、`SPEC-dashboard-ai-rail`、`SPEC-batch-doc-governance`、`document-governance.md v2.2`。

### Spec 相容性附記（對 SPEC-doc-governance §3 的修訂）

`SPEC-doc-governance §3` §明確不包含 寫：

> - 儲存文件內容 — ZenOS 是語意索引層，不存內容
> - Content snapshot / 快取 — 不做內容副本
> - 文件編輯器 — 不提供文件編輯功能

此三條與 `document-governance.md v2.2` 引入的 Delivery Snapshot 模式已產生矛盾。本 spec 正式修訂：ZenOS 支援**兩種合法儲存模式**——

1. **Delivery Snapshot（原生文件）**：ZenOS 自有 GCS private revision，由用戶在 Dashboard 編輯產生；source.type=`zenos_native`，source.uri=`zenos://docs/{doc_id}/rev/{revision_id}`
2. **Helper-supplied Summary（外部 source 的語意摘要，非全文 mirror）**：helper 在推入 Notion / GDrive source 時，可附帶 ≤10KB 的 `snapshot_summary`——這是 helper 在外部 LLM 產出的**語意摘要**，**不是** raw 全文副本。agent 直接消費此摘要；要看原文，去 `source.uri` 指的外部系統。**ZenOS 永遠不存外部文件的全文 mirror**——這是語意層的紀律，也是 helper 的責任邊界（helper 必須做 meaningful compression，不准 dump）。

兩者都是 optional 副本，不代表 ZenOS 要承擔內容主編輯或版本控制責任。bundle spec 的 exclusions 條文將由 architect 在實作前以 amendment 方式更新。

---

## 需求

### P0（必須有）

#### P0-1: Dashboard 原生文件編輯器

- **描述**：Dashboard 左側 nav「文件」（Docs）提供完整的 Notion-like 編輯體驗——用戶不需離開 ZenOS 就能新增、編輯、儲存 markdown 文件，並綁定 L2。內容寫入走 Delivery Snapshot 模式（GCS private），不經 Git。

- **三欄佈局**（對應 mockup）：
  - **左 nav**：「文件」成為 primary navigation 項目
  - **中欄 — 文件列表**：
    - 搜尋框
    - 分組顯示：`PINNED` / `個人` / `團隊` / `專案·{product name}`
    - 每項顯示標題 + updated 日期
    - 「+新」按鈕建立空白文件
  - **右欄 — 編輯區**：
    - 頂部：L2 breadcrumb（`{scope} · {doc_type}`，例：`個人 · WEEKLY`）
    - 標題、作者、更新時間、協作者
    - toolbar：「Agent 改寫」（AI rail）、「引用」、「分享」
    - markdown 編輯區（WYSIWYG 呈現 headings / list / callout / 程式碼區塊）
  - **最右欄 — 大綱 + 引用**：
    - 大綱（從 markdown headings 自動生成，點擊跳錨）
    - AGENT 建議（來自 SPEC-dashboard-ai-rail）
    - 引用·來源（bundle 的其他 source + 使用者手動掛上的 references）

- **儲存語意**：
  - 自動儲存（debounce，每 N 秒或 blur 時）
  - 每次儲存建立新 revision；`primary_snapshot_revision_id` 跟到最新
  - source 結構：新增 `zenos_native` type，uri 指向 ZenOS permalink

- **生命週期行為**：
  - 新建：預設 `doc_role=index`, `status=draft`，預設掛到用戶當前 scope（個人 workspace 或 product）
  - 刪除：軟刪除 → `status=archived`；不物理刪 GCS revision

- **Acceptance Criteria**：
  - `AC-DNH-01` Given 用戶在 Dashboard 點「+新」，When 輸入標題並按儲存，Then 新建 doc entity（`doc_role=index`, `status=draft`）且第一個 source.type=`zenos_native`
  - `AC-DNH-02` Given 已存在的 zenos_native 文件，When 用戶編輯並停留 > N 秒，Then Dashboard 自動觸發 `POST /api/docs/{doc_id}/content` 並建立新 revision
  - `AC-DNH-03` Given 文件有 markdown headings，When 用戶開啟文件，Then 最右欄顯示自動生成的大綱，點擊可跳到對應段落
  - `AC-DNH-04` Given 用戶有 pinned / 個人 / 團隊 / 專案 四類文件，When 打開 docs 頁，Then 中欄按四類分組呈現
  - `AC-DNH-05` Given zenos_native source 的文件，When agent 呼叫 `read_source(doc_id)`，Then 讀到最新 revision 的 markdown content
  - `AC-DNH-06` Given 文件被標 archived，When 用戶在列表檢視，Then 預設不顯示；需切「已封存」才看得到
  - `AC-DNH-07` Given 用戶從列表點一份 zenos_native 文件，When 載入，Then 頂部顯示 L2 breadcrumb（掛載 entity name）與 doc_type

#### P0-2: Helper Ingest Contract（external_id + upsert）

- **描述**：`write(collection="documents")` 擴展 source schema 與 mutation 語義，讓 helper 可用「外部系統的穩定 ID」作 key 對同一份外部文件進行 upsert，重跑 helper 不會堆積 duplicate。

- **Source schema 擴展**（新增 3 欄，皆選填）：

  | 欄位 | 型別 | 說明 |
  |------|------|------|
  | `external_id` | string? | 外部系統的穩定 ID。建議格式：`{source_type}:{id}`。範例：`notion:4a7b...e3f`、`gdrive:1abcXYZ`、`local:{sha256}` |
  | `external_updated_at` | ISO-8601? | helper 從外部系統取得的該文件最後修改時間（由 helper 讀取原系統的 `last_edited_time`） |
  | `last_synced_at` | ISO-8601 | server 管理；helper 每次 upsert 時自動更新為 server now |
  | `snapshot_summary` | text? (**≤10KB**) | helper 產出的**語意摘要**（不是 raw 全文 mirror）。超過 10KB → 410/413 reject。agent 直接消費；要看原文點 source.uri |

- **Upsert 行為**（`write` 的新語義）：
  - 當 `add_source` 或 `update_source` 傳入 `external_id`：
    - 若同一 doc_id 下已有同 `external_id` 的 source → **update** 該 source（覆寫 uri / label / external_updated_at / snapshot_summary / last_synced_at），保留 source_id
    - 否則 → **create** 新 source
  - 若未傳 `external_id` → 維持現有行為（每次 add_source 都建新 source）

- **唯一性約束**：
  - 同一 doc_id 下，`external_id` 必須唯一（DB unique constraint）
  - 跨 doc_id 若發現同一 `external_id` 已掛在別的 bundle → write 成功，但 response 附 warning「同一外部文件疑似掛在多個 bundle」

- **Helper 行為期待**（non-normative，寫在 spec 作 contract 說明）：
  - Helper 讀外部系統時，先 list metadata 比對 `external_updated_at`，決定是否要拉 content
  - 每次 helper 同步一份外部文件 → 呼叫 `write(update_source / add_source)` 帶 `external_id` + `external_updated_at` + 可選 `snapshot_summary`

- **Acceptance Criteria**：
  - `AC-DNH-08` Given helper 首次推入 Notion 頁 `external_id="notion:abc"`，When write 執行，Then 建立新 source，server 設 `last_synced_at`
  - `AC-DNH-09` Given helper 第二次推入同一 `external_id="notion:abc"`（同 doc_id）且 uri 或 content 有變，When write 執行，Then **更新既有 source**（保留 source_id），不建新 source
  - `AC-DNH-10` Given helper 第二次推入時 `external_updated_at` 不變且 snapshot_summary 不變，When write 執行，Then 仍接受但 response 註記「no-op」
  - `AC-DNH-11` Given source A 帶 `external_id="notion:abc"` 已在 doc_id=X，When helper 把同 `external_id` 寫入 doc_id=Y，Then write 成功但 response 含 warning `duplicate_external_id_across_bundles`
  - `AC-DNH-12` Given source 有 snapshot_summary，When agent 呼叫 `read_source(doc_id, source_id)`，Then 回傳 snapshot_summary（原始真相仍為 source.uri 指向的外部文件）
  - `AC-DNH-13` Given source 無 snapshot_summary，When agent 呼叫 `read_source`，Then 回傳 `unavailable` 結構 + `setup_hint: "用 Notion MCP 同步這份文件，或在 Dashboard 點重新同步"`
  - `AC-DNH-14` Given 傳入 `external_id` 但格式不合法（例：空字串、未含 `:` 分隔），When write 執行，Then 回傳 400
  - `AC-DNH-14a` Given 傳入的 `snapshot_summary` 超過 10KB（10240 bytes），When write 執行，Then 回傳 413 with code `SNAPSHOT_TOO_LARGE`，並提示 helper「snapshot_summary 是摘要不是 mirror，請先在 helper 端 distill」

#### P0-3: 手動 / Agent 觸發 Re-sync UX

- **描述**：文件詳情頁的每個外部 source 旁顯示 `last_synced_at` 與 stale 提示。用戶可觸發「重新同步」，UX 以複製 Helper prompt 的方式讓用戶回 Claude Desktop 等 MCP client 執行。Agent 在 read 到 stale source 時亦應主動提示。

- **Stale 判斷**：
  - `last_synced_at` 超過 N 天（預設 14）→ Dashboard 標黃色 `stale`
  - 或 `external_updated_at > last_synced_at` 不為真時（helper 上次沒比對到更新）→ 也視同需要手動 re-sync

- **「重新同步」按鈕行為**：
  - 點擊 → 彈出面板顯示建議 Helper prompt（可複製），例：
    ```
    請用 Notion MCP 讀取 https://www.notion.so/... 的最新內容，
    然後用 ZenOS MCP 的 write(update_source) 更新 source_id=<sid>（external_id=notion:abc）
    ```
  - **ZenOS server 不主動觸發任何外部抓取**；所有同步動作需要由用戶端 Helper 執行
  - 完成後 helper 自然走 P0-2 的 upsert 路徑

- **Agent 觸發行為**：
  - Agent 透過 `read_source` 讀到 stale source 時，response 必須含 `staleness_hint` 欄位
  - Agent 可依 hint 主動向用戶建議「是否幫你重新同步」，但**不自動執行**（若 helper 在同一 session，agent 可代為執行）

- **Acceptance Criteria**：
  - `AC-DNH-15` Given source 的 `last_synced_at` 超過 14 天，When Dashboard 顯示該 source，Then 顯示 `stale` 黃色標記與「重新同步」按鈕
  - `AC-DNH-16` Given 用戶點「重新同步」，When 面板展開，Then 顯示可複製的 Helper prompt，包含 source_id 與 external_id
  - `AC-DNH-17` Given agent 呼叫 `read_source` 讀到 stale source，When 回傳，Then response 含 `staleness_hint`（含 last_synced_at、建議動作）
  - `AC-DNH-18` Given helper 完成 re-sync（走 update_source with external_id），When write 返回，Then Dashboard 下次開啟時 stale 標記消失
  - `AC-DNH-19` Given `external_updated_at > last_synced_at`（極不尋常，代表 helper 推了舊版），When Dashboard 顯示，Then 顯示 warning「推入內容可能較舊」

#### P0-4: 多 Source 並存於同一 L3（Helper + 原生 + GitHub 混合）

- **描述**：一個 L3 index doc entity 必須能同時容納以下 source 組合：`zenos_native` 原生文件、`github` 外部連結、helper 推入的 `notion/gdrive/local`。Dashboard 必須正確顯示混合 source 清單。

- **顯示規則**：
  - 沿用 `SPEC-doc-governance §3` §P0-9 的分組顯示（按 doc_type）
  - 本 spec 補充：source.type 決定每個 source 的 badge（ZenOS / GitHub / Notion / GDrive / Local）
  - 使用者點 `zenos_native` source → 留在 Dashboard 內的 reader / editor
  - 使用者點 `github / notion / gdrive` source → 新分頁開外部

- **Acceptance Criteria**：
  - `AC-DNH-20` Given index entity 有 1 個 `zenos_native` + 1 個 `notion` + 1 個 `github` source，When Dashboard 顯示，Then 三個 source 皆可見，各帶正確 badge
  - `AC-DNH-21` Given 使用者點 `zenos_native` source，When 觸發，Then 導航到 Dashboard 內 reader / editor（**不開新分頁**）
  - `AC-DNH-22` Given 使用者點外部 source（github/notion/gdrive），When 觸發，Then 開新分頁到 external URL

#### P0-5: MCP `write` 原生 capture 寫 GCS（initial_content）

- **背景**：今天 `write(collection="documents")` 只建 entity metadata；要把 markdown 內容寫進 GCS 必須額外呼叫 `POST /api/docs/{doc_id}/content`（dashboard REST API），這條路徑只有 dashboard frontend 用，MCP agent 走不到。zenos-capture skill 對 local md 檔因此只能走 `local` source + `snapshot_summary`（≤10KB 摘要），造成「Dashboard 點進去看不到完整內容」的 UX 缺口。

- **描述**：`write(collection="documents")` 擴展接受 `initial_content` 參數，server 端建立 doc entity 時同時：
  1. 建立 `zenos_native` source，`uri=/docs/{doc_id}`、`is_primary=true`、`source_status=valid`
  2. 把 markdown 內容寫進 GCS private revision（重用 `_publish_document_snapshot_internal` 的 GCS write 邏輯，但跳過 GitHub adapter 讀取段）
  3. 設 doc entity 的 `primary_snapshot_revision_id`
  讓 zenos-capture skill / Helper / 任何 MCP caller 一次呼叫完成 entity 建立 + 內容上傳，agent 與 Dashboard 立即可讀。

- **接口擴展**：
  | 欄位 | 型別 | 說明 |
  |------|------|------|
  | `initial_content` | string? | markdown 內容；上限 1 MB（1048576 bytes，與 snapshot_summary 10 KB 摘要上限不同——這是真實文件 storage 的合理上限） |

- **Server 行為**：
  - 接受 `initial_content` 後，內部走 GCS write 路徑（不呼叫 GitHub adapter）
  - 自動產生並寫入 zenos_native source 進 sources 列表
  - 只支援 create（新建 doc 時）；update 既有 doc 內容請走既有 `POST /api/docs/{doc_id}/content`
  - 與 `initial_content` 互斥：傳 `initial_content` 時不可同時傳 `sources`（避免 primary 衝突；要混合外部 source 走後續 `add_source` 加入）

- **Acceptance Criteria**：
  - `AC-DNH-29` Given `write(collection="documents", data={..., initial_content="...md..."})` 建新 doc，When write 執行，Then 建立 doc entity + zenos_native source + GCS revision，response data 含 doc_id、revision_id、source_id
  - `AC-DNH-30` Given write 帶 `initial_content` 成功建立後，When agent 呼叫 `read_source(doc_id)`，Then 回傳完整 markdown 內容（`content_type="full"`，內容 = 原 initial_content）
  - `AC-DNH-31` Given `initial_content` 大小超過 1 MB（1048576 bytes），When write 執行，Then 回傳 413 with code `INITIAL_CONTENT_TOO_LARGE`
  - `AC-DNH-32` Given write 同時傳 `initial_content` 和 `sources`，When write 執行，Then 回傳 400 with code `INITIAL_CONTENT_REQUIRES_NO_SOURCES`，message 提示二選一
  - `AC-DNH-33` Given update 既有 `doc_id` 時傳入 `initial_content`，When write 執行，Then 回傳 400 with code `INITIAL_CONTENT_CREATE_ONLY`，message 提示更新內容走 `POST /api/docs/{doc_id}/content`

---

### P1（應該有）

#### P1-1: Helper 參考實作（Dogfood reference）

- **描述**：提供一份 reference helper 實作（建議：Claude Desktop + Notion MCP + ZenOS MCP 的 slash command），讓 dogfood 用戶能最小摩擦地開始用。
- **Acceptance Criteria**：
  - `AC-DNH-23` Given Claude Desktop 已裝 Notion MCP + ZenOS MCP，When 用戶說「把這個 Notion 頁同步到 ZenOS」，Then helper 能正確呼叫 P0-2 的 upsert 路徑

#### P1-2: Dashboard 插入「引用」

- **描述**：編輯器 toolbar 的「引用」按鈕，讓用戶從 ontology（L2 / L3 / task）中選一個節點插入到文件中，作為可點擊 backlink。
- **Acceptance Criteria**：
  - `AC-DNH-24` Given 用戶在編輯器按「引用」，When 選擇 L2 entity，Then 文件內插入 `[[{entity_name}]]` 並建立 relationship
  - `AC-DNH-25` Given 文件有引用的 entity，When 在右欄「引用·來源」顯示，Then 列出被引用的節點與來源文件

#### P1-3: Pin / Unpin

- **描述**：文件可被 pin 到列表頂端。
- **Acceptance Criteria**：
  - `AC-DNH-26` Given 用戶 pin 一份文件，When 下次開啟 docs 頁，Then 該文件顯示在 `PINNED` 分組

#### P1-4: Local 檔案拖曳上傳

- **描述**：用戶將 .md 檔拖曳到 Dashboard 編輯器 → 建立新 source，`external_id` 設為 `local:{sha256_of_content}`。若檔案 ≤10KB，snapshot_summary 直接設為檔案內容；若 >10KB，前端提示用戶先做摘要或選 `+新` 走 zenos_native（GCS revision，不受 10KB 限制）。
- **Acceptance Criteria**：
  - `AC-DNH-27` Given 用戶拖一份 .md 進編輯器，When drop，Then 建立新 source，external_id 為 sha256 hash
  - `AC-DNH-28` Given 用戶拖同一份檔案第二次（content 相同），When drop，Then 走 upsert（no-op）

---

### P2（可以有）

#### P2-1: 分享連結

- **描述**：zenos_native 文件可產生 share link，讓非 workspace 成員訪問（read-only）。

#### P2-2: 協作者即時共編

- **描述**：多人同時編輯同一份 zenos_native 文件（OT / CRDT）。Phase 1 不做，先做 last-write-wins。

#### P2-3: Helper 自動 Poll Stale

- **描述**：Helper 可定期跑 `search(collection="documents", source_status="stale")` 找出需 re-sync 的 source，自動重跑。用戶不需手動觸發。（Phase 2 才做 — 要先評估 token 成本。）

---

## 明確不包含

- **ZenOS 原生 OAuth（Notion / GDrive / Confluence）** — 一律走 Helper 模式。Phase 2 視 dogfood 結果決定是否做 Notion OAuth（審核較輕）。
- **Server 端主動爬取外部系統** — ZenOS server 完全不出網抓外部文件。所有 ingestion 走 client-side Helper。
- **即時 Webhook 變動監聽** — 需 OAuth 支援才能訂 webhook，與上一條同理延後。
- **即時多人共編** — 本 spec 只定 last-write-wins；OT / CRDT 延到 P2。
- **完整 WYSIWYG Rich-text（含 embed、資料庫、block mention）** — Phase 1 只做 markdown-first，embed 類高階功能不做。
- **檔案類型支援除 markdown 外的任何格式** — 不做 .docx / .pdf / 圖檔；外部 source 可掛這些 URL，但 ZenOS 不解析其內容。
- **外部文件全文 mirror** — `snapshot_summary` 是 helper 產出的 ≤10KB 語意摘要，不是全文快取。Helper 不准把整份 Notion 頁 / GDrive 文件丟進來；要看原文請用 `source.uri` 跳外站。
- **Helper 的實作細節** — 本 spec 只定 contract；helper 由用戶自行組合（Claude Desktop / Cursor / ChatGPT 都可）。
- **強制把既有 single-source doc entity 遷移為 index** — 沿用 SPEC-doc-governance §3 的自然演進策略。

---

## 技術約束（給 Architect 參考）

- **Source schema migration**：`sources` 表需加 3 欄位 `external_id` (nullable, string)、`external_updated_at` (nullable, timestamp)、`last_synced_at` (not null, timestamp, default now())。加一條 unique index `(doc_id, external_id)` WHERE `external_id IS NOT NULL`。
- **snapshot_summary 儲存位置**：建議存 `sources` 表的 JSONB 欄位或獨立 content table（per-source revision）。若走後者，需評估與現有 `primary_snapshot_revision_id`（doc 層級）的語意差異——前者是 helper-supplied cache、後者是 ZenOS native delivery。
- **source.type 擴展**：需新增 `zenos_native`、`local` 兩個 type；reader adapter 對應為「讀 GCS revision」、「僅讀 snapshot_summary」。
- **URI contract for zenos_native**：建議 `zenos://docs/{doc_id}/rev/{revision_id}` 或直接用 `/docs/{doc_id}` permalink；Dashboard reader 不走外部跳轉。
- **API**：既有 `POST /api/docs/{doc_id}/content` 可沿用；需確認 Dashboard editor 的 auto-save debounce 與 content size 上限。
- **Dashboard editor 選型**：markdown-first 編輯器候選 tiptap / lexical / milkdown，由 Architect 決定；outline 生成走 client-side markdown AST。
- **影響 impact chain**：`L3 文件治理`（primary）、`知識系統 Adapter 策略`（L2 策略改寫）、`MCP 介面設計`（write mutation 擴展）、`Dashboard 知識地圖`（docs UI 新頁）。
- **SPEC-doc-governance §3 的 exclusions 修訂**：實作前需發 amendment（或 bundle spec 直接 edit），移除兩條互斥條款。
- **Staleness 判斷時窗 N=14 天**：可改為 workspace-level 可設定；Phase 1 先寫死。
- **「推入內容較舊」的 staleness warning**：需防止 helper 覆蓋較新內容；可考慮 P0-2 的 write 擴展為 `if_external_updated_at_matches`（類 ETag）——列為開放問題。

---

## 開放問題

1. ~~**snapshot_summary 是否有大小上限？**~~ → **已決議（2026-04-20）**：10KB 硬上限。snapshot_summary 是語意摘要不是 mirror；helper 必須 distill，超過則 reject 強迫做 meaningful compression。
2. **zenos_native source 能不能被 supersede？** 目前 `supersedes` 機制是 doc entity 層級；若要細到 source 層級需要額外設計。
3. **Helper 與 ZenOS 的 rate-limit 協商**：helper 若一口氣推 50 份文件，會不會打爆 MCP？需要 batch write？
4. **source 層級 ACL**：某些外部 source 只該被特定 workspace 成員看到。P0 先延續現有 workspace-level visibility，是否需更細？
5. **是否把「用戶可在 Dashboard 手動編輯 source.external_id」列為功能？** 當 Notion 頁面被 migrate（ID 換新）時可能需要。傾向 No，保持系統管理。
6. **Helper auto-poll 的 token 預算**：P2-3 延後，但需要先估算一個合理 session-local polling 策略，避免未來重頭設計。
