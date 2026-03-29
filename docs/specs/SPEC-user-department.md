---
type: SPEC
id: SPEC-user-department
status: Under Review
l2_entity: 夥伴身份與邀請
created: 2026-03-29
updated: 2026-03-29
---

# Feature Spec: User Department（用戶部門）

## 背景與動機

ZenOS `entity_entries` 新增 `department` 欄位（ADR-010），讓不同部門產生的知識條目能夠隔離——工程部門的決策 entry 不會在壓縮時被行銷部門的 entries 稀釋，反之亦然。

`department` 的值必須從某個地方來。Entry 是治理流程的副產品，由 skill/agent 自動產生，用戶不會手動填 entry 的部門。因此 department 的正確來源是 **user profile**：

```
用戶 profile.department
  → setup skill 注入 local agent context
  → MCP server 在 entry create 時從 session 自動帶入
  → entry 被標記為正確的部門
```

目前 `partners` 表（user profile）沒有 `department` 欄位，導致這條鏈路無法建立。

## 目標用戶

- **Admin**：在 Dashboard 設定公司內每個用戶的部門
- **一般用戶/Agent**：透明受益——不需要做任何事，department 自動注入

## 需求

### P0（必須有）

#### 1. partners 表新增 department 欄位

- **描述**：每個用戶有一個 `department` 字串，代表他所屬的部門。預設值為 `"all"`，代表跨部門或無特定部門（適用於 CEO、VP、尚未設定的用戶）。
- **department 語意**：
  - `"all"` → 跨部門，此用戶產生的 entries 全員可見；此用戶能看到所有部門的 entries
  - `"engineering"`、`"marketing"` 等任意字串 → 部門專屬
- **Acceptance Criteria**：
  - Given 新建用戶，When 未設定 department，Then `department = "all"`
  - Given 用戶 department = `"engineering"`，When 該用戶的 agent 建立 entry，Then entry.department = `"engineering"`
  - Given 用戶 department = `"all"`，When 該用戶的 agent 建立 entry，Then entry.department = `"all"`

#### 2. Admin 管理公司部門清單

- **描述**：每間公司有一份部門清單，由 Admin 維護。清單是公司共用的，`"all"` 是系統保留值，不出現在清單中。Admin 可以新增、重新命名、刪除部門。
- **重新命名行為**：部門重新命名後，所有屬於該部門的用戶 department 自動更新為新名稱，不需要 Admin 逐一修改。
- **刪除行為**：若部門底下仍有用戶，禁止刪除，Admin 必須先將這些用戶重新指派到其他部門。
- **Acceptance Criteria**：
  - Given Admin 在公司設定頁新增部門 `"product"`，Then 該部門出現在所有用戶的部門選單中
  - Given Admin 把部門 `"eng"` 改名為 `"engineering"`，Then 所有 department = `"eng"` 的用戶自動更新為 `"engineering"`；已存在的 entries 保持原值（immutable，不追隨改名）
  - Given Admin 嘗試刪除仍有用戶的部門，Then 系統阻擋並提示需先重新指派用戶
  - Given Admin 刪除一個已無用戶的部門，Then 刪除成功

#### 3. Admin 為用戶指派部門

- **描述**：Admin 在成員管理頁面為每個用戶選擇所屬部門，選項來自公司部門清單。新邀請用戶時可在邀請流程中直接指派。
- **Acceptance Criteria**：
  - Given Admin 進入成員管理頁，When 點擊某個用戶，Then 看到部門下拉選單（選項為公司部門清單）
  - Given Admin 選擇新部門並儲存，Then 該用戶的後續 entry 自動帶新的 department
  - Given Admin 邀請新用戶，When 填寫邀請資訊，Then 可選擇指派部門（可略過，預設 `"all"`）
  - Given 非 Admin 用戶，When 進入成員管理頁，Then 看不到修改部門的入口

#### 3. MCP server 從 session context 自動注入 department 至 entry

- **描述**：當 entry 被建立時，MCP server 從當前請求的 partner context 讀取 `department`，自動填入 `entry.department`。不需要 caller（skill/agent）主動傳這個欄位。
- **Acceptance Criteria**：
  - Given 用戶 A（department = `"marketing"`）的 agent 呼叫 `write(collection="entries", data={...})`，When data 中未帶 department，Then 建立的 entry.department = `"marketing"`
  - Given caller 的 data 中明確帶了 department 欄位，Then server 忽略 caller 傳的值，仍使用 partner context 的 department（防止偽造）

### P1（應該有）

#### 4. Setup skill 將 department 注入 local agent system context

- **描述**：`/zenos-setup` 執行時，從 MCP server 拿到當前用戶的 department，寫入 local agent 的 system context，讓 agent 在執行治理動作（capture、entry 反寫等）時知道自己所在的部門。
- **為什麼是 P1**：即使沒有這步，P0 的 MCP server 注入已能正確標記 entry。但 agent 知道自己的部門後，可以在 capture 流程中做更準確的判斷（如「這條 entry 適合記在工程部門嗎？」）。
- **Acceptance Criteria**：
  - Given `/zenos-setup` 執行完成，When agent 需要部門資訊，Then 可從 context 直接讀取，不需要再呼叫 MCP
  - Given 用戶 department 被 Admin 修改，When 下次執行 `/zenos-setup`，Then agent context 更新為新的 department

#### 5. Entry 搜尋依用戶 department 過濾

- **描述**：`search(collection="entries")` 預設只回傳當前用戶可見的 entries：自己部門的 + `"all"` 的。
- **Acceptance Criteria**：
  - Given 用戶 department = `"engineering"`，When `search(collection="entries")`，Then 只回傳 `engineering` 和 `all` 的 entries，不回傳 `marketing` 的
  - Given 用戶 department = `"all"`，When `search(collection="entries")`，Then 回傳全部 entries
  - Given `get(name=<entity>)`，Then `active_entries` 也依同樣規則過濾

## 明確不包含

- **部門層級結構（部門樹）**：本 spec 目的是防止 entry 壓縮跨部門稀釋，flat string 足夠。部門樹屬於 visibility/permission 設計，是獨立的未來功能
- **一個用戶多個部門**：Phase 0 每人只屬於一個部門（或 `"all"`）
- **部門清單的版本歷史**：不追蹤部門改名的歷史紀錄
- **entry 建立後修改 department**：entry 建立後 department 不可修改（immutable），若判斷錯誤需 archive 重建
- **跨部門 entry 查看的細粒度權限**：`"all"` 是唯一的跨部門值，不做「A 部門可以看 B 部門但 B 不能看 A」的複雜設定

## 技術約束（給 Architect 參考）

- `department` 注入必須在 server 端強制，不信任 caller 傳入的值：防止 agent 誤填或偽造部門
- `partners` 表 `department` 預設值應為 `"all"`（非 null），確保向下相容且不觸發 null check 問題
- Entry 過濾規則：`entry.department = user.department OR entry.department = 'all'`
- 壓縮（consolidate_entries）必須依 department 分組，同組才能合併（見 ADR-010）

## 開放問題

- 無。

## 相關文件

- `docs/decisions/ADR-010-entity-entries.md`（department 欄位來源決策）
- `docs/specs/SPEC-governance-feedback-loop.md`（P1-4 entry 壓縮 workflow，依賴 department 分組）
