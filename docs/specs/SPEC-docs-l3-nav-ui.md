---
type: SPEC
id: SPEC-docs-l3-nav-ui
status: Under Review
l2_entity: jN076EgEmQcUrOLrtAwd
created: 2026-04-27
updated: 2026-04-27
---

# Feature Spec: 文件 UI — L3 Entity 導航展開

## 背景與動機

ZenOS 的 L3 document entity 已支援 `doc_role: "single" | "index"`，每個 entity 可掛多個 sources。但現有兩個文件介面完全沒有反映這個結構：

1. **專案「文件」分頁**：把所有 L3 entities 攤平成 2 欄 card grid。有 248 份文件時完全不可導航。
2. **`/docs` 編輯頁 sidebar**：以 L2 entity 名稱分組後顯示 L3 entities 的扁平列表，L3 entity 是 leaf node，沒有展開 sources 的能力。

結果是：ZenOS 的知識結構（L3 作為 document index）在 UI 層完全不可見，用戶無法用它來導航文件。

## 目標用戶

| 用戶 | 場景 |
|------|------|
| 老闆／PM（Barry） | 在專案頁快速瀏覽某個 L3 知識索引下掛了哪些 sources，不需要離開專案頁 |
| 文件編輯者 | 在 `/docs` 頁導航到特定 L3 entity 的某個 source，開始編輯 |

## Spec 相容性

已比對既有規格：
- `SPEC-document-bundle.md`：定義 L3 doc entity 的 single/index 模型與 sources 結構
- `SPEC-docs-native-edit-and-helper-ingest.md`：覆蓋 zenos_native、snapshot summary 讀取語意
- `SPEC-document-delivery-layer.md`：定義 source content 讀取路徑（GCS、read_source）

**衝突：無。** 本 spec 只定義 UI 導航行為，不改變 document 資料模型、sources 結構、或 delivery 機制。

## 需求

### P0（必須有）

#### R1：專案「文件」分頁 — L3 entity 展開列表

- **描述**：移除扁平 2 欄 card grid，改為可展開的 L3 entity accordion 列表。每個 L3 row 展開後顯示 sources 子列表；點擊 source 在頁面內顯示 inline preview（source metadata + snapshot summary 片段），不離開專案頁。
- **Acceptance Criteria**：
  - `AC-DOCNAV-01`：Given 專案有 L3 document entities，When 用戶點擊「文件」分頁，Then 顯示可展開的 L3 entity 列表，不是扁平 grid
  - `AC-DOCNAV-02`：Given L3 entity row 已渲染，When 用戶點擊該 row，Then 展開顯示該 entity 的 sources 子列表
  - `AC-DOCNAV-03`：Given sources 子列表已展開，When 用戶點擊一個 source，Then 在頁面內顯示 inline preview（source 名稱、type、狀態、更新時間 + snapshot summary 文字片段），不跳轉頁面
  - `AC-DOCNAV-04`：Given L3 entity 有 0 個 sources，When 展開，Then 顯示「尚無來源」空狀態

#### R2：`/docs` 頁 sidebar — L3 entity 可展開節點

- **描述**：sidebar 的 L3 entity 列表項目改為可展開節點；展開後顯示 sources 子列表；點擊 source 載入其內容至中間編輯器。`doc_role: "single"` 的 entity 直接點擊仍載入內容（維持現有行為）；`doc_role: "index"` 的 entity 直接點擊改為展開 sources 列表。
- **Acceptance Criteria**：
  - `AC-DOCNAV-05`：Given sidebar 顯示 L3 entity，When 用戶點擊展開箭頭，Then 顯示 sources 作為縮排子項目
  - `AC-DOCNAV-06`：Given sources 子列表已展開，When 用戶點擊一個 source，Then 中間編輯器載入該 source 的內容
  - `AC-DOCNAV-07`：Given L3 entity `doc_role: "single"`，When 用戶點擊 entity 名稱，Then 直接載入內容到編輯器（維持現有行為）
  - `AC-DOCNAV-08`：Given L3 entity `doc_role: "index"`，When 用戶點擊 entity 名稱，Then 展開 sources 列表（不直接載入）

### P1（應該有）

#### R3：Source count badge

- **描述**：L3 entity row 顯示 source 數量徽章（例如「3 sources」），讓用戶在展開前知道規模。
- **Acceptance Criteria**：
  - `AC-DOCNAV-09`：Given L3 entity 有 N 個 sources，When 渲染 row，Then 顯示「N sources」badge（N=0 顯示「—」）

## 明確不包含

- 不改變 document 資料模型（L3 entity 定義、sources 結構、doc_role 語意）
- 不在專案頁嵌入完整文件編輯器
- 不改變 `/docs` 中間編輯器和右欄 sources panel 的行為
- 不處理 entity status 顯示邏輯（「暫停」bug 另立 ticket）

## 技術約束（給 Architect 參考）

- `listDocs` 目前回傳的 Entity 可能不含完整 sources 陣列；專案頁展開時可能需要 lazy-load（或在 list API 補 `source_count` + `sources` preview）
- 專案頁 inline preview 的 snapshot summary 需確認讀取路徑（source 的 `snapshot_summary` 欄位 vs. 呼叫 `getDocumentContent`）
- `DocListSidebar` 已有 `doc.docRole === "index"` 判斷，可作為展開行為分流的切入點

## 開放問題

1. **inline preview source count**：專案頁 sources 子列表是一次全載還是有分頁上限（建議 Architect 決定）
2. **Status bug**：原心生技 entity 顯示「暫停」但任務進行中，需獨立 debug ticket
