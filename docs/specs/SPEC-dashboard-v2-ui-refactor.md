---
type: SPEC
id: SPEC-dashboard-v2-ui-refactor
status: Draft
ontology_entity: dashboard
created: 2026-03-30
updated: 2026-04-23
depends_on: SPEC-mcp-tool-contract, SPEC-ontology-architecture v2
---

# ZenOS Dashboard UI v2 — 知識導航與側邊欄協作規格

**版本**：2.0（frontmatter 標準化於 2026-04-23）
**關聯文件**：`SPEC-dashboard-v1.md`（基礎）、`TD-dashboard-v1-implementation.md`（實作參考）

---

## 1. 核心願景：圖表協作 (Graph-List Synergy)

在 v1 中，我們試圖在圖譜上展示所有資訊，導致 L2 展開時視覺過載。v2 重新定義「關聯性即資訊」的展現方式：

*   **圖譜 (Graph)**：展現 **「結構化資訊 (Structure)」**。重點在於 L1 (Product) 與 L2 (Module) 之間的依賴、影響與包含關係。它是公司的「知識地圖」。
*   **側邊欄 (Side Panel)**：展現 **「內容化資訊 (Content)」**。重點在於 Task (行動) 與 Document (依據) 的細節。它是該知識點的「數位雙生 (Digital Twin)」。

## 2. 圖譜行為變更 (Graph Behavior)

### 2.1 節點收斂
*   **預設視圖**：僅顯示 L1 (Product) 與 L2 (Module) 節點。
*   **移除 L3 自動展開**：點擊 L2 節點時，**不再**於圖譜上展開 Task 與 Document 節點。
*   **移除視覺噪音**：
    *   移除節點右上角的「任務數量藍色 Badge」。
    *   移除圖譜上的 Document 節點（除非切換至「深度探索模式」）。

### 2.2 互動反饋
*   **單擊 (Single Click)**：選中 L2 節點，高亮其直接關聯的 L1/L2，並**同步開啟右側詳情面板**。
*   **雙擊 (Double Click)**：圖譜平移 (Pan) 並縮放 (Zoom) 聚焦該節點，但不展開 L3 節點。

## 3. 右側詳情面板優化 (Enhanced Side Panel)

側邊欄將從單純的「屬性列表」升級為「行動與參考中心」。

### 3.1 資訊架構 (Information Hierarchy)
1.  **Header (Metadata)**：名稱、Summary、Owner、Tags (W/W/H/W)。
2.  **Action Layer (Tasks)**：
    *   **分類顯示**：分為 `進行中 (In Progress)`、`待驗收 (Review)`、`待處理 (Backlog)`。
    *   **關聯提示**：若 Task 連結自 Blindspot，顯示紅色警告圖示。
    *   **快速操作**：在側邊欄直接點擊可跳轉至該任務的詳細編輯/驗收頁面。
3.  **Reference Layer (Documents)**：
    *   **分類顯示**：分為 `核心規格 (Spec)`、`決策紀錄 (ADR)`、`外部參考 (Sources)`。
    *   **預覽互動**：點擊文件名稱，可直接在側邊欄內預覽內容（若為 markdown）或另開分頁。
4.  **Dependency Layer (Relationships)**：
    *   列出 `依賴於 (Depends on)` 與 `服務於 (Serves)` 的其他 L2 節點。
    *   點擊此處的節點 Chip，圖譜自動聚焦至該節點。

## 4. 圖表連動機制 (Sync Mechanism)

為了保留「關聯感」，側邊欄與圖譜需具備動態連動：
*   **Hover 高亮**：當滑鼠在側邊欄的 Task 或 Document 上 hover 時，圖譜中央被選中的 L2 節點應產生脈衝效果 (Pulse Effect)，強化「這些內容屬於它」的視覺連結。
*   **導航連動**：點擊側邊欄「關聯實體」中的 Entity Chip，圖譜需執行平滑過渡動畫，選中新節點並更新側邊欄內容。

## 5. 使用者體驗改善 (UX Improvements)

*   **空間配置**：
    *   左側邊欄：導航與過濾（230px）。
    *   中央：純淨的知識圖譜（Flexible）。
    *   右側詳情：富文本與行動中心（400px，較 v1 略寬以容納更多資訊）。
*   **視覺減負**：
    *   L2 節點大小根據其「知識權重（關聯文件與任務的加權總和）」微調，但不噴射子節點。
    *   當側邊欄開啟時，圖譜自動向左偏移，避免選中節點被側邊欄遮擋。

## 6. 技術實作建議

*   **State Management**：使用全域 Store (如 Zustand) 記錄 `selectedEntityId`。側邊欄根據此 ID 即時從 Firestore 或快取中 fetch 關聯的 Task 與 Doc。
*   **Force-graph 調整**：關閉 `onNodeClick` 中的 `expandChildren` 邏輯。
*   **組件解耦**：將側邊欄內的 `TaskList` 與 `DocList` 製作為獨立的智慧組件 (Smart Components)，以便在其他頁面（如專案頁）複用。

---

**PM 結論**：v2 的核心是將「複雜度」從不擅長處理大量文字的「圖」轉移到擅長處理清單的「表」，同時維持兩者之間的動態連結，確保「關聯性」這一核心資訊不丟失。
