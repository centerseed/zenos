# Phase 1 — Ontology MVP Feature Spec

> 日期：2026-03-21
> 狀態：Draft
> 作者：PM
> 交付對象：Architect

---

## 問題陳述

ZenOS 的 ontology 目前以 markdown 文件存在（`docs/ontology-instances/paceriz/`），人可讀但機器不可查詢。行銷同事的 AI agent 無法存取這些知識來產出素材。

這個 MVP 要做的事：**把 ontology 從 markdown 搬進 Firestore，透過 MCP 讓外部 AI agent 消費，用 Naruvia 自己做第一個導入實驗。**

## 目標

- 行銷同事的 AI agent 能透過 MCP 查詢 Naruvia 的產品 context，自主產出行銷素材
- Barry 能透過 Claude session + MCP 建構和更新 ontology
- 驗證「ontology → MCP → agent 消費」這條路徑是否走得通

## 非目標（不在範圍內）

- 不做自動觸發的治理流程（git hook、Governance Daemon 是 Phase 2）
- 不做 Dashboard UI
- 不做多租戶（Naruvia 是唯一用戶）
- 不做 Google Drive / Notion adapter（只做 GitHub adapter）
- 不做 Protocol 自動生成（手動寫入 Firestore）

---

## 四個交付物

### 1. Firestore Schema

### 2. MCP Tools 介面

### 3. 治理流程 MVP

### 4. GitHub Adapter

以下逐一定義。

---

## 交付物 1：Firestore Schema

### Collection 總覽

| Collection | 層級 | 用途 | 變動頻率 |
|------------|------|------|----------|
| `entities` | 骨架層 | 產品、模組、目標、角色 | 低（季度） |
| `entities/{id}/relationships` | 骨架層 | 實體間依賴、歸屬、服務關係 | 低 |
| `documents` | 神經層 | 每份文件的語意代理（4D 標籤 + 摘要） | 高（每天） |
| `protocols` | View | Context Protocol，從 ontology 組裝的人可讀 view | 中 |
| `blindspots` | 治理產出 | AI 推斷的盲點與建議 | 中 |

### entities/{entityId}

```
name            string    必填    "Paceriz"
type            string    必填    "product" | "module" | "goal" | "role" | "project"
parentId        string?   選填    module → product 的層級關係，頂層為 null
status          string    必填    "active" | "paused" | "completed" | "planned"
summary         string    必填    一句話描述，非技術語言
tags
  what          string    必填    跟什麼東西有關
  why           string    必填    為什麼存在
  how           string    必填    怎麼運作、什麼階段
  who           string    必填    給誰的、誰負責
details         map       選填    type-specific 的彈性欄位（如 codeLocation、apiEndpoints）
confirmedByUser boolean   必填    false = draft，true = 已確認
createdAt       timestamp 必填
updatedAt       timestamp 必填
```

### entities/{entityId}/relationships/{relId}

```
targetId        string    必填    目標 entity 的 ID
type            string    必填    "depends_on" | "serves" | "owned_by" | "part_of" | "blocks" | "related_to"
description     string    必填    一句話描述這個關係
confirmedByUser boolean   必填
```

### documents/{docId}

```
title           string    必填    人可讀的文件名稱
source
  type          string    必填    "github" | "gdrive" | "notion" | "upload"
  uri           string    必填    agent 可存取的 URI（GitHub URL、Drive file ID...）
  adapter       string    必填    用哪個 adapter 取內容
tags
  what          string[]  必填    關聯的實體名稱（如 ["Paceriz", "ACWR"]）
  why           string    必填    這份文件為什麼存在
  how           string    必填    文件的用途或階段
  who           string[]  必填    目標讀者（如 ["開發", "行銷"]）
linkedEntityIds string[]  必填    關聯的 entity ID 列表
summary         string    必填    2-3 句話的語意摘要（不是全文，是 context）
status          string    必填    "current" | "stale" | "archived" | "draft" | "conflict"
confirmedByUser boolean   必填
lastReviewedAt  timestamp 選填    上次 AI 或人 review 的時間
createdAt       timestamp 必填
updatedAt       timestamp 必填
```

### protocols/{protocolId}

```
entityId        string    必填    這份 Protocol 描述的 entity
entityName      string    必填    冗餘存放，方便查詢
content
  what          map       必填    產品描述、核心能力、現況
  why           map       必填    解決什麼問題、目標、市場定位
  how           map       必填    核心流程、技術現況、進度
  who           map       必填    內部角色、外部用戶、目標客群
gaps            array     選填    [{ description: string, priority: "red"|"yellow"|"green" }]
version         string    必填    "v0.1"
confirmedByUser boolean   必填
generatedAt     timestamp 必填
updatedAt       timestamp 必填
```

### blindspots/{blindspotId}

```
description     string    必填    盲點描述
severity        string    必填    "red" | "yellow" | "green"
relatedEntityIds string[] 必填    相關的 entity ID
suggestedAction string    必填    建議的行動
status          string    必填    "open" | "acknowledged" | "resolved"
confirmedByUser boolean   必填
createdAt       timestamp 必填
```

### 設計原則

- 所有 collection 都有 `confirmedByUser`，跟資料層共用同一套信任機制
- `source.uri` 必須是 agent 可存取的 URI，禁止 local path
- `tags` 的 What/Who 由 AI 自動標注（高準確），Why/How 標為 draft 待人確認
- `summary` 是語意摘要不是全文節錄——描述這份文件在公司知識網路中的位置
- `linkedEntityIds` 建立神經層 → 骨架層的關聯，支援反向查詢

---

## 交付物 2：MCP Tools 介面

### 消費端（行銷 agent 用）— 唯讀

#### get_protocol

```
用途：取得某個產品/實體的 Context Protocol
輸入：entity_name: string（如 "Paceriz"）
輸出：Protocol 的完整 content（what/why/how/who）+ gaps
場景：行銷 agent 要寫素材前，先讀產品 context
```

#### list_entities

```
用途：列出所有實體，可按 type 過濾
輸入：type?: string（"product" | "module" | "goal" | "role" | "project"）
輸出：entity 列表（name, type, status, summary）
場景：agent 想知道公司有哪些產品、哪些目標
```

#### get_entity

```
用途：取得某個實體的詳情 + 所有 relationships
輸入：entity_name: string
輸出：entity 全部欄位 + relationships 列表
場景：agent 想了解某個模組的依賴關係和現況
```

#### list_blindspots

```
用途：列出盲點，可按實體或嚴重度過濾
輸入：entity_name?: string, severity?: string
輸出：blindspot 列表
場景：agent 想知道有什麼風險或待處理問題
```

#### get_document

```
用途：取得某份文件的語意代理（ontology entry）
輸入：doc_id: string
輸出：document 全部欄位（含 source URI）
場景：agent 想追某份文件的細節，先讀 entry 判斷相關性
```

#### read_source

```
用途：透過 adapter 取得原始文件內容
輸入：doc_id: string
輸出：原始文件的文字內容
場景：agent 讀完 ontology entry 後決定要看原始內容
依賴：GitHub Adapter（Phase 1 唯一實作）
```

#### search_ontology

```
用途：語意搜尋，橫跨 entities + documents + protocols
輸入：query: string
輸出：匹配的 entities / documents / protocols 列表（按相關度排序）
場景：agent 不確定要找什麼，用自然語言探索
備註：MVP 可用關鍵字匹配，Phase 2 再加 embedding
```

### 治理端（Barry 的 Claude session 用）— 讀寫

#### upsert_entity

```
用途：新增或更新骨架層實體
輸入：entity 的所有欄位（id 為選填，有 = 更新，無 = 新增）
輸出：寫入後的 entity（含生成的 id）
場景：Barry 建構或調整 ontology 時
```

#### add_relationship

```
用途：建立兩個實體之間的關係
輸入：source_entity_id, target_entity_id, type, description
輸出：寫入後的 relationship
場景：建構依賴圖
```

#### upsert_document

```
用途：新增或更新神經層 entry
輸入：document 的所有欄位
輸出：寫入後的 document
場景：Barry 把一份文件加入 ontology 索引
```

#### upsert_protocol

```
用途：新增或更新 Context Protocol
輸入：protocol 的所有欄位
輸出：寫入後的 protocol
場景：Barry 建立或更新產品的 Protocol
```

#### add_blindspot

```
用途：記錄一個 AI 推斷的盲點
輸入：blindspot 的所有欄位
輸出：寫入後的 blindspot
場景：Claude 分析後發現問題
```

#### confirm

```
用途：將任何 entry 標記為 confirmedByUser: true
輸入：collection: string, id: string
輸出：更新後的 entry
場景：Barry 確認 AI 的建議
```

#### list_unconfirmed

```
用途：列出所有 confirmedByUser: false 的 entries
輸入：collection?: string（不指定 = 全部）
輸出：未確認的 entries 列表，按 collection 分組
場景：Barry 想知道還有什麼待確認
```

---

## 交付物 3：治理流程 MVP

### 概述

Phase 1 的治理流程 = **人觸發 + MCP 讀寫**。沒有自動偵測、沒有 daemon、沒有 webhook。

### 流程一：首次建構 Ontology

```
Barry 開 Claude session
  ├── 「幫我建 Naruvia 的 ontology」
  │
  │   Claude 做的事：
  │   1. 讀現有的 markdown ontology（docs/ontology-instances/paceriz/）
  │   2. 讀 codebase 關鍵文件（CLAUDE.md、README 等）
  │   3. 把骨架層寫入 entities/（confirmedByUser: false）
  │   4. 把關係寫入 relationships/
  │   5. 把文件索引寫入 documents/（source.uri 用 GitHub URL）
  │   6. 推斷盲點寫入 blindspots/
  │   7. 組裝 Protocol 寫入 protocols/
  │
  ├── Barry review
  │   呼叫 list_unconfirmed() → 逐一確認或修改
  │
  └── 完成
      第一版 ontology 在 Firestore 裡，行銷 agent 可以開始用
```

### 流程二：日常更新

```
Barry 開 Claude session
  ├── 「最近改了 ACWR 的邏輯，更新 ontology」
  │
  │   Claude 做的事：
  │   1. 讀 Firestore 現有的 ACWR entity + 相關 documents
  │   2. 讀 codebase 的變更
  │   3. 呼叫 upsert_entity / upsert_document 更新
  │   4. 檢查是否影響其他 entity（級聯影響）
  │   5. 如有新盲點 → add_blindspot
  │   6. 如 Protocol 受影響 → upsert_protocol
  │
  └── Barry 確認 → confirm()
```

### 流程三：行銷 agent 消費

```
行銷同事的 AI agent
  ├── 收到指令「幫我寫 Paceriz 的社群貼文」
  │
  │   Agent 做的事：
  │   1. get_protocol("Paceriz") → 讀產品 context
  │   2. list_entities(type="module") → 知道有哪些功能
  │   3. list_blindspots("Paceriz") → 知道有什麼要避開的
  │   4. 如果需要技術細節 → get_document(id) → read_source(id)
  │   5. 基於以上 context 產出素材
  │
  └── 產出的素材準確度取決於 ontology 的品質
```

---

## 交付物 4：GitHub Adapter

### 用途

讓 MCP 的 `read_source` tool 能透過 GitHub API 讀取 private repo 的檔案內容。

### 介面

```
interface SourceAdapter {
  readContent(uri: string): Promise<string>
  // uri 範例: "https://github.com/havital/cloud/blob/main/api_service/CLAUDE.md"
}
```

### 實作要求

- 用 GitHub API（`GET /repos/{owner}/{repo}/contents/{path}`）
- 認證：Personal Access Token（存在環境變數）
- 錯誤處理：repo 不存在、檔案不存在、權限不足 → 回傳明確錯誤
- 檔案大小限制：GitHub API 對 > 1MB 的檔案需要用 blob API
- **不做快取**（MVP 不需要）

### 設定

```
環境變數：
  GITHUB_TOKEN=ghp_xxxxx
  GITHUB_DEFAULT_OWNER=havital    # 可選，省略 owner 時的預設值
```

---

## 成功條件

- [ ] 行銷同事的 AI agent 呼叫 `get_protocol("Paceriz")`，能拿到完整的產品 context
- [ ] 行銷同事的 AI agent 呼叫 `read_source(doc_id)`，能拿到 GitHub 上的原始檔案內容
- [ ] Barry 能透過 Claude session + MCP tools 建構完整的 Naruvia ontology
- [ ] 所有 ontology entries 都有 confirmedByUser 機制
- [ ] source.uri 全部是可存取的 URI，沒有 local path

## 開放問題（待 Architect 決策）

- [ ] MCP server 的技術棧（Python? TypeScript?）
- [ ] Firestore 的 project 設定（用現有的 havital project 還是開新的？）
- [ ] MCP server 的部署方式（local process? Cloud Run?）
- [ ] search_ontology 的 MVP 實作方式（Firestore 全文搜尋? 關鍵字匹配? Algolia?）
- [ ] 消費端和治理端是同一個 MCP server 還是分開？
- [ ] GitHub adapter 的 token 權限範圍（只讀? 哪些 repo?）

---

*PM 交付。Architect 請基於此 spec 產出技術設計 + 實作任務拆分。*
