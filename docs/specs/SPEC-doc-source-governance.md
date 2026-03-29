---
type: SPEC
id: SPEC-doc-source-governance
status: Draft
ontology_entity: TBD
created: 2026-03-29
updated: 2026-03-29
---

# Feature Spec: Document Source URI 治理

## 背景與動機

ZenOS document entity 的 `source_uri` 指向外部文件的原始來源（GitHub、Notion、Google Drive、Wiki）。當 source_uri 格式錯誤或原始文件被移動／刪除，Dashboard 上的連結會回傳 404，`read_source` tool 也會失效。

目前缺乏兩件事：
1. Agent 在 capture 時對 source_uri 格式的明確規範（導致寫入相對路徑等錯誤格式）
2. Sync 時的死連結偵測、分級與修復流程

本 spec 定義三個治理時機的完整規則，讓 agent 在 capture、refactor、sync 三個時機都有明確的操作依據。

## 目標用戶

- **agent**：capture 文件時需要知道正確的 source_uri 格式
- **Architect / Developer**：實作 MCP tool 增強與 skill 更新
- **PM / 文件維護者**：搬移文件時需要知道必須同步更新 ontology

## 治理架構

### 三個治理時機

| 時機 | 觸發點 | 責任落點 |
|------|--------|---------|
| **Capture** | agent 呼叫 `write` 建立 document entity | MCP `write` tool（server-side 驗證） |
| **Refactor** | agent 搬移或改名任何文件 | `document-governance` skill（agent 行為協議） |
| **Sync** | `read_source` 收到 404 | MCP `read_source` tool（偵測）+ skill（修復流程） |

### source_status 欄位

Document entity 新增 `source_status` 欄位，三個合法值：

| 值 | 意義 |
|----|------|
| `valid` | source_uri 最近一次存取成功 |
| `stale` | source_uri 存取失敗，但可能是暫時性（權限問題、路徑已移動） |
| `unresolvable` | source_uri 確認無法修復（文件刪除、永久失效） |

### source_status 與 archive 的生命週期關係

Document entity **不允許刪除**，search 預設撈非 archived 的 entity。因此 `source_status` 標記本身不足以讓死連結退出搜尋空間——必須搭配 archive 操作。

**生命週期規則**：

| source_status | 觸發 archive？ | 時機 |
|--------------|--------------|------|
| `stale` | 否 | 等待修復，仍保留在搜尋空間中 |
| `unresolvable` | **是** | 確認 unresolvable 時同步執行 archive |

**Archive 觸發條件**（需滿足其一）：
1. GitHub 替代搜尋找不到同名檔案 → server 自動設 `unresolvable` + archive
2. 用戶拒絕 propose → skill 流程中 agent 執行 archive
3. Notion / GDrive API 明確回傳 deleted → server 自動設 `unresolvable` + archive

Archive 後 entity 退出預設搜尋空間，source_status 仍保留記錄（不清除），便於日後審計。

## 需求

### P0（必須有）

#### Capture 時的 source_uri 格式驗證

- **描述**：`write` tool 在建立 document entity 時，必須驗證 source_uri 格式合法。非法格式直接拒絕並回傳明確錯誤訊息，不寫入 ontology。
- **各類型合法格式**：

  | type | 合法格式 | 常見錯誤範例 |
  |------|---------|------------|
  | `github` | `https://github.com/{owner}/{repo}/blob/{branch}/{path}` | `docs/specs/file.md`（相對路徑） |
  | `notion` | `https://www.notion.so/...` 且 URL 含 UUID 段（32 碼十六進位） | shortened link |
  | `gdrive` | `https://drive.google.com/file/d/{file-id}/view` 或 `/open?id={file-id}` | folder URL |
  | `wiki` | 完整 URL，含 scheme（`https://`） | edit URL（含 `/edit`） |

- **Acceptance Criteria**：
  - Given agent 呼叫 `write` 傳入相對路徑 source_uri，When tool 執行，Then 回傳 400 錯誤，entity **不**寫入 DB
  - Given agent 傳入合法 GitHub URL，When tool 執行，Then entity 正常寫入，`source_status` 預設為 `valid`
  - Given agent 傳入不含 UUID 的 Notion URL，When tool 執行，Then 回傳明確錯誤說明格式要求

#### Sync 時的死連結偵測與 source_status 更新

- **描述**：`read_source` tool 收到 404 時，必須自動更新對應 document entity 的 `source_status`，並回傳結構化錯誤（含 type 資訊供 caller 判斷後續修復策略）。
- **死連結分級規則**：

  | 類型 | 判斷標準 | 自動設定 source_status |
  |------|---------|----------------------|
  | `github` | 404 | `stale`（可能是路徑移動） |
  | `notion` | 404 | `stale`（可能是權限問題）；若 API 明確回 deleted → `unresolvable` |
  | `gdrive` | 403 / 404 | `stale`（403 = 權限）；404 → `unresolvable` |
  | `wiki` | 404 | `stale` |

- **Acceptance Criteria**：
  - Given document entity source_uri 是死連結，When `read_source` 被呼叫，Then entity `source_status` 被更新為 `stale` 或 `unresolvable`
  - Given `read_source` 回傳 404，Then response 包含結構化欄位：`source_type`、`suggested_action`（`search_repo` / `check_permission` / `mark_unresolvable`）
  - Given entity `source_status` 已為 `unresolvable`，When `read_source` 被呼叫，Then 直接回傳錯誤，不再重試

#### GitHub 死連結自動搜尋替代路徑

- **描述**：GitHub 類型的 404 通常是檔案移動或改名造成的，server 應嘗試在同一 repo 中搜尋相同檔名，找到時回傳 propose。
- **搜尋邏輯**：
  1. 解析原 URI，提取 `owner/repo`、`branch`、`filename`（不含路徑）
  2. 在 repo 的 file tree 中搜尋同 `filename`
  3. 找到唯一結果 → 回傳 `proposed_uri`
  4. 找到多個結果 → 回傳所有候選，由 caller 確認
  5. 找不到 → `source_status` 升級為 `unresolvable`
- **Acceptance Criteria**：
  - Given GitHub source_uri 404 且同 repo 可找到同名檔案，When `read_source` 執行，Then response 包含 `proposed_uri`，entity `source_status` 維持 `stale`（等待確認）
  - Given 人工或 agent 確認 propose，When `write` 更新 source_uri，Then entity `source_status` 重設為 `valid`

### P1（應該有）

#### Refactor 時的先查後移協議（document-governance skill 更新）

- **描述**：agent 搬移或改名任何文件前，必須先搜尋 ontology 確認該檔案是否有 document entity。有的話，檔案搬移與 source_uri 更新必須在同一輪操作中完成（原子性）。
- **協議步驟**（加入 `document-governance.md`）：
  1. `mcp__zenos__search(collection="documents", query="<原始 source_uri>")`
  2. 若找到 entity → 執行搬移 + 同步更新 source_uri（路徑 B：直接更新）
  3. 若找不到 entity → 正常搬移，無需額外動作
  4. 禁止：先搬檔案，之後才補更新 ontology（分批 = 違反原子性）
- **Acceptance Criteria**：
  - Given document-governance skill 已更新，When agent 在 refactor 時搬移有 entity 的檔案，Then ontology 在同一輪操作完成更新
  - Given agent 搬移無 entity 的檔案，When 執行，Then 不需要查 ontology 也不需要任何 MCP 操作

#### Sync 修復流程（document-governance skill 更新）

- **描述**：agent 收到 `read_source` 回傳 `stale` + `proposed_uri` 時，進入 propose → confirm 修復流程。
- **流程**：
  1. `read_source` 回傳 `proposed_uri`
  2. Agent 呼叫 `mcp__zenos__confirm` 向用戶確認
  3. 用戶確認 → `mcp__zenos__write` 更新 source_uri，`source_status` 設回 `valid`
  4. 用戶拒絕 → `source_status` 設為 `unresolvable` + **同步執行 archive**（entity 退出搜尋空間）+ 開 blindspot 記錄
- **Acceptance Criteria**：
  - Given `read_source` 回傳 `proposed_uri`，When agent 執行修復流程，Then 必須經過 `confirm` 才能更新 source_uri
  - Given 用戶確認 propose，Then entity source_uri 與 source_status 同步更新為 `valid`
  - Given 用戶拒絕 propose，Then entity 被 archive，source_status 設為 `unresolvable`，且 archive 後不出現在預設 search 結果
  - Given server 自動判定 `unresolvable`（GitHub 找不到同名檔 / Notion 明確 deleted），Then entity 同步 archive，不需人工確認

### P2（可以有）

#### Dashboard 死連結視覺化

- **描述**：Dashboard 在 document entity 的連結旁顯示 `source_status` 標記，讓用戶一眼看出哪些連結需要修復。
- **Acceptance Criteria**：
  - Given entity `source_status` 為 `stale`，Then Dashboard 連結旁顯示警告標記
  - Given entity `source_status` 為 `unresolvable`，Then Dashboard 連結旁顯示錯誤標記，連結變為不可點

## 明確不包含

- **定期主動掃描**：本 spec 不定義排程批次 link checker，僅處理 read_source 觸發時的偵測
- **非 document entity 的 source_uri**：L1/L2 entity 的 sources 欄位不在本 spec 治理範圍內
- **跨 repo 搜尋**：GitHub 替代路徑搜尋僅限同一 repo，不跨 owner

## 技術約束（給 Architect 參考）

- **source_status 欄位**：需加入 `documents` 表 schema，型別 enum，預設值 `valid`
- **GitHub 替代搜尋**：需要 GitHub API token，Architect 決定使用 repo file tree API 或 search API
- **原子性**：skill 協議依賴 agent 遵守，server 端無法強制；需在 skill 文件中清楚標記為強制步驟

## 開放問題

- `source_status` 欄位是加在 `sources` 陣列的每個物件上，還是 document entity 的頂層？（建議：頂層，因一個 entity 通常只有一個 primary source）
- GitHub 替代搜尋是否需要快取 repo file tree，避免每次 404 都打 GitHub API？
