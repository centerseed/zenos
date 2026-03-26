# Feature Spec: 操作審計記錄（Audit Log）

## 狀態
Under Review

## 背景與動機
ZenOS 是 to B 服務，企業管理員需要掌握「誰動了什麼、什麼時候動的」。缺乏操作記錄會導致：
1. 發生爭議時無法舉證
2. 資料被意外修改時無法回溯

## 目標用戶
- **企業主（Owner）**：查看全部成員的所有操作記錄，用於合規舉證
- **被授權管理員（Admin）**：同上，查看全公司操作記錄
- **一般成員**：不在本功能範圍內（無權查看 audit log）

## 需求

### P0（必須有）

#### 權限變更記錄
- **描述**：當任何成員的角色被修改時，系統自動記錄此操作
- **Acceptance Criteria**：
  - Given 管理員將成員 A 的角色從 Member 改為 Admin，When 操作完成，Then 系統記錄一筆 audit log，包含：操作者、操作時間、被操作對象、角色變更前後值
  - Given Agent 執行權限變更，When 操作完成，Then 同樣產生 audit log，操作者為該 Agent 身份

#### 成員邀請/移除記錄
- **描述**：當成員被邀請加入或被移除時，系統自動記錄此操作
- **Acceptance Criteria**：
  - Given 管理員邀請新成員，When 邀請送出，Then 系統記錄操作者、時間、被邀請者 email
  - Given 管理員移除成員，When 操作完成，Then 系統記錄操作者、時間、被移除者身份

#### 知識節點異動記錄
- **描述**：當知識節點（Entity）被新增、修改、刪除時，系統自動記錄此操作
- **Acceptance Criteria**：
  - Given 任何人新增一個節點，When 操作完成，Then 系統記錄操作者、時間、節點名稱與類型
  - Given 任何人修改一個節點，When 操作完成，Then 系統記錄操作者、時間、節點 ID、異動欄位前後值
  - Given 任何人刪除一個節點，When 操作完成，Then 系統記錄操作者、時間、被刪除節點的快照

#### 管理員可在 Dashboard 查詢操作記錄
- **描述**：企業主與 Admin 可在 Dashboard 瀏覽並篩選所有操作記錄
- **Acceptance Criteria**：
  - Given 管理員進入 Audit Log 頁面，When 頁面載入，Then 顯示該 partner 所有操作記錄，依時間倒序排列
  - Given 管理員設定時間範圍篩選，When 套用篩選，Then 只顯示該時間範圍內的記錄
  - Given 管理員按操作類型篩選（權限/成員/節點），When 套用篩選，Then 只顯示對應類型的記錄
  - Given 管理員按操作人篩選，When 套用篩選，Then 只顯示該操作者的記錄
  - Given 一般成員進入 Audit Log 頁面，When 頁面載入，Then 顯示無權限錯誤，無法查看任何記錄

### P1（應該有）

#### 任務指派/狀態變更記錄
- **描述**：當任務被指派或狀態被變更時，系統自動記錄此操作
- **Acceptance Criteria**：
  - Given 任何人指派任務給某人，When 操作完成，Then 系統記錄操作者、時間、任務 ID、指派對象
  - Given 任何人變更任務狀態，When 操作完成，Then 系統記錄操作者、時間、任務 ID、狀態前後值

## 明確不包含
- 一般成員查看 audit log
- audit log 記錄可被刪除或修改（記錄本身不可竄改）
- 登入/登出記錄（Phase 0 不做）
- 匯出 audit log 為 CSV/PDF（Phase 0 不做）

## 技術約束（給 Architect 參考）
- **不可竄改**：audit log 寫入後只能讀，不能刪改，需在 storage 層面確保
- **統一操作者格式**：Agent 操作者與人操作者用同一套記錄格式，不做區分
- **記錄結構**：每筆記錄需包含 operator（操作者 UID）、action（操作類型）、target（操作對象 ID）、timestamp、diff（異動前後內容）
- **即時性**：操作發生時同步寫入記錄，不得非同步延遲

## 開放問題
- 無
