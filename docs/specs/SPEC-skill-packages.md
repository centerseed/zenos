---
type: SPEC
id: SPEC-skill-packages
status: Draft
l2_entity: Agent 整合架構
created: 2026-04-12
updated: 2026-04-12
---

# Feature Spec: Skill 分類安裝（Skill Packages）

## 背景與動機

ZenOS 的 skill 數量持續增長。目前 `/zenos-setup` 會把所有 skill 整包安裝到使用者的 Claude Code，包括：

- 治理 skill（capture、sync、governance）
- 角色 skill（architect、developer、QA、PM、designer）
- 流程 skill（feature、debug、triage、review）
- 行銷 skill（即將新增的 marketing-* 系列）
- CRM skill（未來）

問題是：**行銷人員不需要 architect/developer/QA 這些開發角色 skill，裝了只會增加 agent context 負擔，還可能被誤觸發。**

反過來也一樣——開發者不需要行銷 skill。

需要一個分包安裝機制，讓不同角色的使用者只安裝跟自己工作相關的 skill。

## 目標用戶

| 角色 | 需要的 skill 包 |
|------|---------------|
| 所有人 | 基礎治理（文件治理、知識地圖操作） |
| 開發團隊 | 基礎治理 + 開發流程（architect、developer、QA、debug、feature、review） |
| 行銷人員 | 基礎治理 + 行銷模組（marketing-intel、marketing-generate 等） |
| 業務人員 | 基礎治理 + CRM 模組（未來） |
| 老闆 | 基礎治理 + brainstorm + challenger（不需要執行層 skill） |

## Spec 相容性

| 文件 | 關係 | 處理 |
|------|------|------|
| SPEC-skill-release-management | 需銜接 | 現有 release 機制管的是 skill 的版本同步，本 spec 加的是安裝時的分類選擇。兩者互補，不衝突 |
| SPEC-agent-skill-addon | 無衝突 | addon 是 skill 內部的擴充機制，本 spec 是安裝時的分包選擇 |
| SPEC-zenos-setup-redesign | 需銜接 | setup 流程需要加入 package 選擇步驟 |
| SPEC-marketing-automation | 依賴本 spec | 行銷模組的 5 個 skill 需要透過本機制分包安裝 |

## 需求

### P0（必須有）

#### Package 定義

- **描述**：在 `skills/release/` 中定義 skill package，每個 package 包含一組相關的 skill 和描述
- **Acceptance Criteria**：
  - Given 存在 package 定義檔，When `/zenos-setup` 讀取，Then 能列出所有可用 package 及其包含的 skill
  - Given 一個 package 定義，When 查看內容，Then 包含：package 名稱、描述、包含的 skill 列表、依賴的其他 package

#### 安裝時選擇

- **描述**：`/zenos-setup` 執行時，顯示可用的 skill package 列表，讓使用者勾選要安裝哪些。基礎治理包為必裝，其餘可選
- **Acceptance Criteria**：
  - Given 使用者執行 `/zenos-setup`，When 進入 skill 安裝步驟，Then 顯示所有 package 並標記哪些是必裝、哪些是可選
  - Given 使用者選擇了「基礎治理 + 行銷模組」，When 安裝完成，Then 只安裝這兩個 package 的 skill，不安裝開發流程的 skill
  - Given 基礎治理包是必裝的，When 使用者嘗試取消勾選，Then 無法取消（或提示為必要）

#### 追加安裝

- **描述**：使用者可以在安裝後追加新的 package，不影響已安裝的 skill
- **Acceptance Criteria**：
  - Given 使用者已安裝基礎治理+行銷，When 執行 `/zenos-setup` 並追加開發流程，Then 新 skill 加入，原有 skill 不受影響

### P1（應該有）

#### Package 依賴解析

- **描述**：Package 之間可以定義依賴。例如行銷模組依賴基礎治理，安裝行銷時自動帶入基礎治理
- **Acceptance Criteria**：
  - Given 行銷模組依賴基礎治理，When 使用者只勾選行銷，Then 基礎治理自動安裝

#### 移除 Package

- **描述**：使用者可以移除不再需要的 package
- **Acceptance Criteria**：
  - Given 使用者已安裝開發流程，When 選擇移除，Then 該 package 的 skill 被清除，其他 package 不受影響
  - Given 基礎治理被其他 package 依賴，When 嘗試移除，Then 提示有依賴，需要先移除依賴方

### P2（可以有）

#### 自訂 Package

- **描述**：使用者可以定義自己的 package，選擇組合不同 skill
- **Acceptance Criteria**：
  - Given 使用者想要一個自訂組合，When 建立自訂 package，Then 可以從所有可用 skill 中挑選

## 明確不包含

- **不做 skill 的動態載入**：skill 仍然是檔案安裝到 `.claude/skills/`，不是運行時動態載入
- **不做權限控制**：不限制使用者安裝某個 package（例如不阻止行銷人員安裝開發包）
- **不做 skill marketplace**：不做線上 skill 商店或社群共享機制

## 技術約束（給 Architect 參考）

| 約束 | 原因 |
|------|------|
| Package 定義存在 `skills/release/` | 遵守 SSOT 紀律，所有 skill/agent 設定只改 release/ |
| 安裝結果仍寫入 `.claude/skills/` | 不改變現有 skill 載入機制，只改安裝過程 |
| `/zenos-setup` 是唯一安裝入口 | 不提供其他安裝途徑，避免不一致 |

## 初始 Package 定義

| Package | 包含的 skill | 必裝？ |
|---------|-------------|--------|
| **基礎治理** | zenos-capture、zenos-sync、zenos-governance、brainstorm、challenger、triage | 是 |
| **開發流程** | architect、developer、QA、PM、designer、feature、debug、review、implement | 否 |
| **行銷模組** | marketing-intel、marketing-plan、marketing-generate、marketing-adapt、marketing-publish | 否 |
| **CRM 模組** | （未來定義） | 否 |

## 開放問題

| # | 問題 | 建議 |
|---|------|------|
| 1 | coach skill 放哪個 package？ | 基礎治理或獨立的「管理者」package |
| 2 | PM skill 是開發流程還是通用？ | PM 寫 spec 是開發流程的一部分，但行銷主管也可能用。建議放開發流程，行銷主管需要時追加 |
| 3 | 現有已安裝整包的用戶怎麼遷移？ | `/zenos-setup` 更新時偵測已有全部 skill → 提示「要不要改為分包管理？」 |
