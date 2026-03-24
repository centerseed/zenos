# Feature Spec: L2 節點展開 — Graph 內聯展開 References & Tasks

## 狀態
Delivered — commit 9148344, 2026-03-24

## 背景與動機
目前點 L2 Module 節點只開右側 DetailSheet（list 形式）。
用戶要的是「關聯即知識」：點一個節點，它的 references（documents）和 tasks 直接作為新節點出現在 graph 裡，邊即是關係。
讓知識圖譜從「靜態結構圖」變成「可探索的語意空間」。

## 目標用戶
老闆/PM 在知識地圖上探索某個模組的現況——關心這個模組有哪些文件依據、現在有哪些任務在跑。

---

## 需求

### P0（必須有）

#### 單擊 L2 節點 → graph 就地展開 + checklist 浮出

**描述**：
點一下 L2 Module 節點，graph 立刻展開預設類別的節點，同時浮出一個 checklist popover 讓用戶調整。

展開節點來源：
- **Document 節點**：entity.type = document 且 parentId = 該 module id
- **Task 節點**：tasks.linkedEntities 包含該 module id
- **其他 L3 類型**（Goal / Role / Project）：entity.parentId = 該 module id，對應各自 type

浮出 checklist（預設勾選）：
```
☑ Document
☑ Task
☐ Goal
☐ Role
☐ Project
```

互動行為：
- 點 L2 → 立刻展開 Document + Task 節點 → checklist 同時浮出
- 調整 checklist → graph 即時增刪對應類別節點（不需額外確認）
- checklist 錨定在 L2 節點旁
- 點其他地方關閉 checklist，展開節點保留
- 再次點擊同一 L2 節點 → toggle 收合（所有展開節點消失）

**Acceptance Criteria**：
- Given 知識地圖已載入，When 單擊 Action Layer（L2），Then graph 立刻展開 Action Layer 的 document 和 task 節點，checklist popover 同時顯示
- Given checklist 已浮出，When 取消勾選 Task，Then task 節點從 graph 移除，document 節點保留
- Given checklist 已浮出，When 勾選 Goal，Then Goal 類型節點出現在 graph
- Given Action Layer 已展開，When 再次點擊 Action Layer，Then 所有展開節點收合，checklist 關閉
- 展開動畫：節點從 L2 節點位置向外輻射（從原點長出）

#### 展開節點的邊
**描述**：每個新節點與 L2 節點之間有可見的邊，邊標示關係類型。
- Document / Goal / Role / Project 節點的邊：標 `ref`
- Task 節點的邊：標 `task`

**Acceptance Criteria**：
- Given 展開後，每個展開節點到 L2 節點之間有可見連線
- Task 邊與 Document 邊視覺上可區分（顏色或 dash style）

#### Document / Task 節點視覺
**描述**：
- Document 節點：cyan 色小節點（沿用現有 L3 Document 樣式）
- Task 節點：新增顏色，badge 顯示狀態（todo / in_progress / done / blocked）
- blocked task：紅色強調

**Acceptance Criteria**：
- Given 展開後，Task 節點顯示可辨識的狀態標示
- blocked task 節點有紅色視覺強調

---

### P1（應該有）

#### 點擊展開的 Task 節點 → 顯示任務卡片
**描述**：點 task 節點，右側面板顯示 task 詳情（title / status / priority / description），不跳頁。

**Acceptance Criteria**：
- Given task 節點顯示中，When 點擊，Then 右側顯示該 task 的詳情

#### 展開狀態持久化（session 內）
**描述**：縮放 graph、切換 sidebar filter 後，已展開的 L2 節點保持展開狀態。

**Acceptance Criteria**：
- Given Action Layer 已展開，When 縮放 graph，Then 展開節點不消失

---

### P2（可以有）

#### 多 L2 同時展開
同時展開多個 L2，各自顯示自己的 document/task 節點，checklist 各自獨立。

---

## 明確不包含
- L1 Product 節點不觸發此展開行為
- L3 節點點擊不再向下展開
- Heptabase backlink 反向連結
- sidebar 展開邏輯不修改

---

## 技術約束（給 Architect 參考）
- graph 使用 react-force-graph-2d，節點動態新增透過 `graphData()` 更新，simulation reheat 需評估效能影響
- Task 節點資料已在 page-level state（tasks array），不需新增 API call
- Document/L3 節點 = entities where parentId = moduleId，已有資料
- checklist popover 定位方式參考現有 double-click popover 實作
