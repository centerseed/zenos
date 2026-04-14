---
type: ADR
id: ADR-036
status: Draft
ontology_entity: 行銷定位與競爭策略
created: 2026-04-14
updated: 2026-04-14
supersedes: null
---

# ADR-036: 文風 Skill 存儲與組合模型

## Context

`SPEC-marketing-automation` 新增「文風 Skill 體系」P0 需求：使用者需要可組合、可覆寫的多層文風定義來控制 AI 生成文案的語氣和風格。文風需要：

1. **三層組合**：產品級 → 平台級 → 項目級，生成時自動疊加。
2. **可即時修改**：透過 AI 對話或直接編輯，改完馬上生效。
3. **預覽測試**：修改後可即時生成測試文案看效果。
4. **所有人共用**：存在 ZenOS，Claude Code 讀取同一份。

現有架構沒有「文風」的概念，也沒有 L3 document 的三層組合機制。

## Decision

### 1. 文風 skill 存為 ZenOS L3 document（markdown）

每個文風 skill 是一個 L3 document entity，內容為 markdown 格式的文風指令。

```
write(collection="documents", data={
  "doc_id": "STYLE-paceriz-base",
  "title": "文風：Paceriz 品牌基底",
  "type": "GUIDE",
  "ontology_entity": "Paceriz",        // 掛在產品 entity 下
  "status": "approved",
  "source": { "type": "zenos_snapshot" },  // ZenOS Delivery 模式
  "details": {
    "marketing": {
      "style_level": "product",           // product | platform | project
      "style_platform": null,             // platform 級才填，如 "threads"
      "style_project_id": null            // project 級才填
    }
  }
})
```

### 2. 三層掛載規則

| 層級 | parent entity | `style_level` | `style_platform` | `style_project_id` |
|------|--------------|:-------------:|:-----------------:|:-------------------:|
| 產品級 | Product entity | `product` | null | null |
| 平台級 | Product entity | `platform` | `"threads"` / `"blog"` / ... | null |
| 項目級 | 行銷項目 entity | `project` | null | 行銷項目 entity ID |

- 產品級和平台級掛在 product entity 下，跨行銷項目共用
- 項目級掛在特定行銷項目 entity 下，只對該項目生效

### 3. 組合邏輯（生成時）

`/marketing-generate` 和 `/marketing-adapt` 執行時，按以下順序查詢並組合：

```
1. search(collection="documents", product_id=X,
          details.marketing.style_level="product")
   → 取得產品級文風

2. search(collection="documents", product_id=X,
          details.marketing.style_level="platform",
          details.marketing.style_platform=TARGET_PLATFORM)
   → 取得平台級文風（adapt 時用）

3. search(collection="documents",
          details.marketing.style_level="project",
          details.marketing.style_project_id=PROJECT_ID)
   → 取得項目級文風
```

組合方式：三份 markdown 依序串接，後者可覆寫前者的指令。若某層級不存在，跳過不報錯。

### 4. 預覽測試走前端直連 helper（不經後端）

- 使用者按「預覽測試」→ **前端**組裝 prompt：「用以下文風生成一段關於 {範例主題} 的測試文案：{組合後的文風 markdown}」
- **前端直接呼叫本機 helper**（`POST /v1/chat/start`）→ Claude CLI 即時生成 → SSE 串流回前端顯示
- 不經過後端 API server（後端無法連到使用者本機 127.0.0.1 helper）
- 預覽結果不存 ZenOS，不建 entity，純粹前端展示
- 範例主題來源：優先使用最近一個排程主題；無排程時讓使用者自行輸入
- helper 不可用時：預覽按鈕顯示為 disabled，提示「需啟動本機 helper」

### 5. 文風內容格式（markdown）

```markdown
# 品牌語氣
像教練朋友，專業但不冷硬。用「你」不用「您」。

# 禁用詞彙
不要用：賦能、助力、打造、引領、顛覆、痛點

# 句式偏好
- 短句為主，每句不超過 20 字
- 不用被動語態
- 開頭用問句或數據 hook

# 參考範文
像 @跑者山姆 的風格：口語、有梗、偶爾自嘲
```

不限定結構，使用者可自由撰寫。AI 會把整份 markdown 作為 system prompt 的一部分。

## Alternatives

| 方案 | 優點 | 缺點 | 為何不選 |
|------|------|------|---------|
| 文風存在 strategy JSON 的子欄位 | 實作簡單 | 無法跨項目共用（產品級/平台級）；混在策略裡難以獨立管理 | 不符合三層組合需求 |
| 文風存在 repo 的 skill 檔案 | Git 版本管理 | 修改需 commit + sync；非技術人員難以操作 | 不符合「即時修改」需求 |
| 文風存為 ZenOS entry | 利用既有機制 | entry 有 200 字長度限制，文風指令通常更長 | 長度限制過嚴 |
| 新建 marketing_styles table | schema 自由 | 脫離 ZenOS entity 模型 | 違反「不改 Core」約束 |

## Consequences

- 正面：
  - 三層組合覆蓋產品/平台/項目不同粒度的文風需求
  - 存 ZenOS = 所有人共用，改完即生效
  - markdown 格式靈活，非技術人員可直接編輯
  - 預覽測試不污染正式資料
- 負面：
  - 查詢文風需 3 次 search（可考慮 API 層快取）
  - 文風 markdown 無 schema 驗證，品質依賴使用者
  - 三層串接的覆寫語意靠「後者覆寫前者」的慣例，無強制機制
- 後續處理：
  - [待定] 文風版本歷史是否需要（P1 Prompt 模板管理可覆蓋）
  - [待定] 文風 document 的 doc_id 命名規範（建議 `STYLE-{product}-{level}-{platform?}`）

## Implementation

1. 在 marketing API 新增文風 CRUD（不含預覽）：
   - `GET /api/marketing/projects/{id}/styles` → 回傳該項目可用的三層文風（聚合產品級 + 平台級 + 項目級）
   - `PUT /api/marketing/styles/{styleDocId}` → 更新文風內容
   - `POST /api/marketing/styles` → 建立新文風
   - 預覽走前端直連 helper，不經後端 API（後端無法連到使用者本機 helper）
2. 在 Dashboard UI 新增文風管理區塊（項目詳情頁內）
3. 修改 `/marketing-generate` 和 `/marketing-adapt` skill：生成前先查詢並組合文風
4. 建立初始文風 skill（基於 Paceriz 既有 Blog 寫作指引和 Threads 策略）
