---
type: SPEC
id: SPEC-agent-skill-addon
status: Under Review
ontology_entity: TBD
created: 2026-04-04
updated: 2026-04-04
supersedes: null
---

# Feature Spec: Agent Skill Addon 架構

## 背景與動機

ZenOS 提供一套通用 agent（pm、architect、developer、qa 等），透過 `/zenos-setup` 安裝到客戶專案。通用 agent 定義了角色的核心行為、紅線和工作流程。

但每個客戶專案都有自己的特殊知識：部署流程、技術規範、設計系統、行業慣例。這些知識不屬於通用 agent，但 agent 在執行任務時需要知道。

目前沒有機制讓客戶在不修改通用 agent 的情況下，為 agent 掛載這些專案特定的知識。導致：
- 客戶要麼不掛（agent 缺乏專案 context）
- 要麼直接改通用 agent（下次更新時被覆蓋）

## 目標用戶

**ZenOS 產品團隊**：維護並更新通用 agent skill（`skills/release/`），不管客戶的 addon。

**客戶專案團隊**：為自己的專案撰寫並維護 addon skill，掛載到指定的 agent 角色上。

## 需求

### P0（必須有）

#### 安裝器自更新：先拉最新 `/zenos-setup`，再執行安裝

- **描述**：`/zenos-setup` 執行時，第一步永遠是從 MCP 拉取最新版的安裝器本身，確保後續所有邏輯（拆分、安裝、merge）都是最新的，再繼續執行。
- **Acceptance Criteria**：
  - Given 用戶執行 `/zenos-setup`，When Phase 1 完成，Then `.claude/skills/zenos-setup/SKILL.md` 已是 MCP server 上的最新版本
  - Given Phase 1 MCP 連線失敗，When `/zenos-setup` 繼續執行，Then 以現有版本繼續，並回報警告「安裝器未能更新，使用本地版本」
  - Given Phase 1 更新了安裝器，When 繼續 Phase 2，Then 使用的是剛拉下來的新版邏輯

**兩階段安裝流程：**

```
Phase 1：更新安裝器
  mcp__zenos__setup(action="get_installer")
  → 回傳最新 /zenos-setup skill 內容
  → 寫入 .claude/skills/zenos-setup/SKILL.md

Phase 2：執行安裝（用剛更新的安裝器邏輯）
  Step 1. 偵測本地既有 skill
          → 讀取 .claude/skills/{role}/SKILL.md（若存在）

  Step 2. 拆分（本地 AI 執行）
          → 有既有 skill → 分析並拆出專案特定內容到 skills/addons/
          → 無既有 skill → 跳過，建立空的 skills/addons/

  Step 3. 拉通用 agent
          mcp__zenos__setup(action="get_skills")
          → 回傳最新通用 skill 內容（architect/developer/qa/pm 等）
          → 寫入 skills/release/

  Step 4. 組裝薄殼
          → 通用 SKILL.md + 末尾 addon 載入指示
          → 寫入 .claude/skills/{role}/SKILL.md
```

#### 安裝時自動偵測並拆分既有 Skill

- **描述**：Phase 2 Step 2 由本地 AI 執行：讀取既有 skill 文件，判斷哪些內容屬於通用、哪些屬於專案特定，將專案特定部分存到 `skills/addons/`。
- **Acceptance Criteria**：
  - Given 專案已有自訂的 `.claude/skills/developer/SKILL.md`（含通用內容 + 公司 SQL 規範），When `/zenos-setup` 執行，Then 公司 SQL 規範被拆出存到 `skills/addons/developer/`，通用部分被最新版本替換
  - Given 全新專案（無任何既有 skill），When `/zenos-setup` 執行，Then 直接安裝通用 agent，建立空的 `skills/addons/` 目錄，不報錯
  - Given 拆分完成，When agent 啟動，Then 行為與拆分前相同（通用能力 + 專案特定能力都有）
  - Given 拆分時 AI 不確定某段內容歸屬，When 拆分完成，Then 該段內容被標記為 `needs_review: true` 並回報給用戶確認

**拆分判斷標準（給 AI 的依據）：**

| 屬於通用 agent | 屬於專案 addon |
|---------------|---------------|
| 角色定位、紅線、工作流程 | 特定技術棧（Cloud Run、iOS、Rails 等） |
| 治理規則（task/文件/L2） | 部署指令與環境設定 |
| 與 ZenOS MCP 互動模式 | 多租戶 SQL pattern、ORM 用法 |
| 通用 coding standard | 公司命名規範、UI 設計系統 |
| 通用安全 checklist | 客戶特定的合規要求 |

#### Addon Skill 格式

- **描述**：Addon skill 是一個 Markdown 文件，定義在特定情境下 agent 應該知道什麼或如何行動。
- **Acceptance Criteria**：
  - Given 客戶在 `skills/addons/{role}/{name}.md` 建立一個文件，When agent 執行對應角色時，Then agent 能讀到並遵守該 addon 的內容
  - Given addon 文件有 frontmatter，When agent 讀取時，Then agent 能識別觸發條件（什麼時候套用這個 addon）

**Addon Frontmatter 規格：**
```yaml
---
name: addon 名稱（簡短，英文連字號）
for_role: architect | developer | qa | pm | all
trigger: 何時套用這個 addon（自然語言描述，e.g. "部署相關操作時" / "iOS 開發時"）
---
```

#### Addon 存放位置與命名

- **描述**：客戶的 addon skill 放在專案內固定目錄，不被 zenos-setup 覆蓋。
- **Acceptance Criteria**：
  - Given `skills/addons/` 目錄存在，When `/zenos-setup` 執行更新，Then `skills/addons/` 目錄內容不被修改或刪除
  - Given addon 文件放在 `skills/addons/{role}/`，When agent 啟動，Then agent 知道去這個路徑找對應角色的 addon

**目錄結構：**
```
skills/
  release/        ← ZenOS 維護，zenos-setup 更新
    architect/
    developer/
    ...
  addons/         ← 客戶維護，永不被 zenos-setup 覆蓋
    architect/
      deploy-gcp.md
      internal-review-process.md
    developer/
      ios-coding-conventions.md
      our-commit-format.md
    all/
      company-glossary.md   ← 所有角色都掛
```

#### Agent 自動發現並載入 Addon

- **描述**：agent 啟動時，自動找到並載入 `skills/addons/` 下對應角色的所有 addon。
- **Acceptance Criteria**：
  - Given `skills/addons/developer/` 有 2 個 addon 文件，When developer agent 啟動，Then agent 讀取這 2 個文件，並在對應觸發條件下套用
  - Given `skills/addons/all/` 有 addon 文件，When 任何角色的 agent 啟動，Then 該 addon 也被載入
  - Given `skills/addons/` 目錄不存在，When agent 啟動，Then agent 正常運作，不報錯

**Installed skill 薄殼結構（由 zenos-setup 生成）：**

```markdown
{通用 SKILL.md 完整內容}

---

## 專案 Addon Skills

若 `skills/addons/{role}/` 目錄存在，在開始任何任務前，
用 Read tool 讀取該目錄下所有 .md 文件，按各 addon 的 `trigger` 條件套用。

若 `skills/addons/all/` 目錄存在，也讀取其中所有文件。
```

#### zenos-setup 更新時保留 Addon 指示

- **描述**：更新通用 agent 時，薄殼末尾的 addon 指示段落必須被保留。
- **Acceptance Criteria**：
  - Given agent 薄殼已有「專案 Addon Skills」段落，When `/zenos-setup` 執行更新，Then 段落被保留（通用內容更新，addon 指示不變）
  - Given 尚未有「專案 Addon Skills」段落，When `/zenos-setup` 執行更新，Then 段落被加入

### P1（應該有）

#### Addon 索引文件

- **描述**：`skills/addons/README.md` 列出所有已安裝的 addon，讓團隊一眼看到有哪些擴充。
- **Acceptance Criteria**：
  - Given 新建一個 addon，When 開發者查看 `skills/addons/README.md`，Then 看到該 addon 的摘要（名稱、for_role、trigger）

#### Addon 可標記為條件載入

- **描述**：addon 可以標記 `when` 條件，只在特定情境下套用（而非每次任務都讀）。
- **Acceptance Criteria**：
  - Given addon frontmatter 有 `trigger: "iOS 開發時"`，When developer agent 處理非 iOS 任務，Then agent 可以跳過此 addon 不讀
  - Given addon frontmatter 有 `trigger: "always"`，When agent 任何任務，Then 一定讀取

### P2（可以有）

#### Addon 可跨專案共享

- **描述**：常用的 addon（如「台灣法規合規要求」）可以打包發布，讓多個客戶安裝。
- **Acceptance Criteria**：
  - Given 一個 addon package，When 客戶執行安裝指令，Then addon 被放到 `skills/addons/` 對應目錄

## 明確不包含

- **覆蓋通用 agent 核心行為**：addon 只能「附加」，不能改寫通用 agent 的紅線或工作流程
- **Addon 版本管理**：addon 由客戶自己用 git 管理
- **Addon 之間的依賴關係**：addon 相互獨立

## 技術約束（給 Architect 參考）

- Addon 載入機制必須是 agent-agnostic：不依賴特定 LLM 平台，只靠 Read tool 和 Markdown
- zenos-setup 更新 agent 時，不能用 `shutil.copytree` 直接覆蓋薄殼（會刪掉 addon 指示段落）；需要改為 merge 策略
- Addon 目錄 `skills/addons/` 必須在 `.gitignore` 之外（應 git track）

## 開放問題

- 薄殼的 addon 指示段落用標記（如 `<!-- ADDON_SECTION -->`）來讓 sync script 識別邊界？還是固定在文件末尾偵測？
- 既有 skill 的拆分分析：由 `/zenos-setup` skill（在 Claude Code 裡跑的 AI）負責，還是由 ZenOS MCP `setup` tool 的後端 AI 負責？兩者的 tradeoff：前者可讀取本地文件但無法跨平台；後者跨平台但需要客戶把文件內容上傳給 server 分析。

下一步：Architect 接手做技術設計

> PM 不建 task。行動項目記錄在「開放問題」section，由 Architect 判斷是否開 task。
