---
type: SPEC
id: SPEC-crm-core
status: Under Review
ontology_entity: crm-客戶管理
created: 2026-03-28
updated: 2026-04-10
---

# Feature Spec: CRM 模組

> Layering note: CRM 是建立在 `ZenOS Core` 之上的 application module，不是 ZenOS Core 本身。
> CRM 可橋接 Core entity / task / workspace context，但不得反向改寫 Core 的 ontology、task、access 基本語意。

## 背景與動機

ZenOS 擁有者本身是 AI 顧問公司，主要業務為幫助中小企業導入 AI 與提供顧問諮詢服務。
目前完全沒有系統化記錄客戶接洽狀況，導致：

- 跟進時機靠記憶，容易遺漏
- 無法回顧商機歷史，難以分析哪些客源品質最好
- 多人協作時無法共享客戶狀態

CRM 模組以 ZenOS Core 為基底建立——客戶公司在需要對外共享整棵客戶知識樹時，可橋接為 ZenOS L1 entity；聯絡人則作為該 L1 之下的知識節點。這讓 CRM 資料進入知識圖譜，實現跨模組關聯查詢，同時驗證 ZenOS Core 的多 workspace、knowledge linkage、agent capture 三項核心能力。

## 目標用戶

- **主要用戶**：公司負責人與業務人員（小型團隊，2–5 人）
- **使用場景**：
  - 記錄新接觸的潛在客戶
  - 推進商機漏斗階段
  - 記錄每次跟客戶的互動內容
  - 查詢「這家公司過去談過什麼、現在在哪個階段、約定了哪些交付物」

## 需求

### P0（必須有）

#### 公司管理
- **描述**：建立、查看、編輯客戶公司資料。當該客戶是獨立的分享與協作邊界時，每家公司對應一個 ZenOS L1 entity。
- **欄位**：公司名稱、產業、規模（員工人數區間）、地區、備忘
- **Acceptance Criteria**：
  - Given 用戶在 CRM 新增公司，When 填寫公司名稱並儲存，Then 公司出現在列表，且 ZenOS L1 entity（type: company）同步建立
  - Given 公司已存在，When 用戶編輯欄位，Then 變更同步更新至 ZenOS L1 entity

#### 聯絡人管理
- **描述**：為公司新增聯絡人（窗口）。每個聯絡人對應公司 L1 之下的知識節點，並關聯至所屬公司。
- **欄位**：姓名、職稱、Email、電話、備忘
- **Acceptance Criteria**：
  - Given 用戶新增聯絡人並選擇所屬公司，When 儲存，Then 聯絡人出現在公司下方，ZenOS entity（type: person）建立，並建立與公司 entity 的關聯
  - Given 公司詳情頁，When 查看，Then 列出該公司所有聯絡人

#### 商機（Deal）管理
- **描述**：記錄每一筆顧問案/導入案，追蹤漏斗進度。一家公司可有多筆商機。
- **欄位**：
  - 標題（必填）
  - 所屬公司（必填）
  - 負責人（必填，ZenOS user）
  - 漏斗階段（必填，見下方）
  - 案值金額（選填，TWD）
  - 案子類型（一次性專案 / 顧問合約 / Retainer）
  - 來源類型（轉介紹 / 自開發 / 合作夥伴 / 社群 / 活動）
  - 介紹人（選填，聯絡人或自由文字）
  - 預計成交日（選填）
  - 合約簽署日期（選填）
  - 工作範圍說明（選填，自由文字）
  - 交付物清單（選填，條列）
  - 備忘
- **漏斗階段**：
  ```
  潛在客戶 → 需求訪談 → 提案報價 → 合約議價 → 導入中 → 結案
                                                        ↑
                                         任何階段可標記：流失 / 暫緩
  ```
- **Acceptance Criteria**：
  - Given 用戶新增商機並填寫必填欄位，When 儲存，Then 商機出現在看板對應漏斗欄位
  - Given 商機詳情頁，When 用戶變更漏斗階段，Then 階段立即更新，並在活動紀錄自動新增「階段變更」事件
  - Given 一家公司，When 查看公司詳情，Then 看到該公司所有商機列表與當前階段
  - Given 商機標記為「流失」或「暫緩」，When 查看，Then 預設不顯示在看板，可切換顯示

#### 活動紀錄（Activity Log）
- **描述**：記錄與客戶的每次互動，時間順序排列，附屬於商機。
- **類型**：電話 / Email / 會議 / Demo / 備忘
- **欄位**：類型、日期時間、內容摘要、記錄人
- **Acceptance Criteria**：
  - Given 用戶在商機詳情頁新增活動，When 填寫類型與摘要並儲存，Then 活動出現在時間軸，最新在上
  - Given 商機漏斗階段變更，When 自動觸發，Then 系統自動新增一筆「階段變更」系統活動

#### CRM Dashboard Tab
- **描述**：在現有 ZenOS Dashboard 加入「客戶」tab，顯示商機看板（Kanban by 漏斗階段）。
- **Acceptance Criteria**：
  - Given 用戶進入 Dashboard，When 點擊「客戶」tab，Then 看到商機看板，各欄對應漏斗階段
  - Given 看板，When 點擊商機卡片，Then 開啟商機詳情（含活動紀錄）
  - Given 看板，When 拖曳商機卡片至另一欄，Then 漏斗階段更新

### P1（應該有）

#### 上次聯絡日提示
- **描述**：在商機卡片上顯示距上次活動的天數，超過 14 天標示警示色。
- **Acceptance Criteria**：
  - Given 商機卡片，When 距上次活動超過 14 天，Then 卡片顯示橘色「N 天未跟進」標籤

#### 公司詳情頁 — ZenOS 知識地圖連結
- **描述**：公司詳情頁提供「在知識地圖查看」連結，跳轉至 ZenOS 知識地圖並聚焦該 entity。
- **Acceptance Criteria**：
  - Given 公司詳情頁，When 點擊「知識地圖」，Then 跳轉至知識地圖並以該公司 entity 為中心顯示

#### 業績總覽
- **描述**：「客戶」tab 頂部顯示本月/累計數字：進行中商機數、本月新增商機、成交案值。
- **Acceptance Criteria**：
  - Given 「客戶」tab，When 頁面載入，Then 頂部顯示三個數字卡片

### P2（可以有）

#### AI 從對話擷取客戶資訊
- **描述**：透過 MCP tool，允許 AI agent 從對話或會議摘要中自動擷取公司/聯絡人/活動資訊並寫入 CRM。
- **Acceptance Criteria**：
  - Given MCP tool `crm_upsert_company`，When AI agent 呼叫並傳入公司資訊，Then 公司建立或更新，ZenOS L1 entity 同步

#### 跨模組關聯查詢
- **描述**：在 ZenOS 知識地圖上，從客戶公司 entity 可以看到所有相關商機與聯絡人節點。
- **Acceptance Criteria**：
  - Given ZenOS 知識地圖，When 點擊客戶公司節點，Then 顯示關聯的聯絡人 entity 與商機摘要

## 明確不包含

- Email 發送功能（不做郵件客戶端）
- 報價單 / 合約文件管理（法律文件、PDF 合約，財務工具另議）
- 自動化工作流程（Pipeline automation，Phase 0 不做）
- 與外部 CRM（Salesforce、HubSpot）同步
- 客戶入口 / 客戶自助頁面

## 技術約束（給 Architect 參考）

- **獨立 schema**：CRM 資料存在獨立的 PostgreSQL schema（`crm`），不直接混用 `zenos` schema
- **ZenOS entity 橋接**：新增/修改公司時，必須同步建立或更新 ZenOS L1 entity（type: company）；新增/修改聯絡人時，必須同步建立或更新其下游 ZenOS entity（type: person）。橋接為非同步可接受，但最終一致性必須保證
- **Core contract 不可改寫**：CRM 可引用 ZenOS Core 的 entity / task / workspace / access contract，但不得自行擴張或覆寫其基礎語意
- **多用戶**：同一 partner 下所有 user 共享可見範圍（Phase 0 不做細粒度權限）
- **MCP 暴露**：P2 的 AI 擷取功能需暴露 MCP tool，命名原則遵循 ZenOS 既有規則
- **Dashboard**：在現有 Next.js dashboard 新增 tab，不是獨立服務

## 開放問題

- **商機是否需要橋接為 ZenOS entity 或 Task？** 目前 spec 以 CRM 自己的資料表管理商機，僅公司橋接為 L1，聯絡人橋接為其下游 entity。若需要在知識地圖上看到商機節點，Architect 需評估是否把商機也寫入 ZenOS entities。
- **ZenOS governance 三問**：商機重大狀態變更（例如：進入「導入中」、「結案」）是否要觸發 ZenOS 治理 pipeline？建議 Architect 評估觸發點。
- **Dashboard tab 命名**：介面顯示「客戶」或「業務」？（遵循 CLAUDE.md：UI 不出現 entity/ontology 字眼）
