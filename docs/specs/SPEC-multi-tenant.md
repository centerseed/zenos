# Feature Spec: Multi-Tenant 架構（一客戶一 Firebase Project）

## 狀態
Approved

## 背景與動機

ZenOS 目前的 `partners` collection 混合了兩個語意不清楚的概念：

1. **公司（租戶）**：使用 ZenOS 的客戶公司
2. **用戶（成員）**：這間公司的員工

在 Phase 0 只有一個客戶（Paceriz）時，這個模糊沒有造成問題。但當 ZenOS 要服務第二間、第三間客戶公司時，這個設計就會崩潰：不同公司的資料混在同一個 Firestore，只靠 backend code 的紀律來隔離，這是安全隱患，也是架構債。

此外，部分客戶（特別是有資安要求的中型企業）希望能**自主掌控資料**，不接受 SaaS 式的資料集中。需要一條地端部署路徑。

這個 Feature Spec 定義的是：讓 ZenOS 從「單一客戶 PoC」演進為「可服務多間客戶公司的產品」。

---

## 目標用戶

| 用戶 | 場景 |
|------|------|
| ZenOS 新客戶公司 | 簽約後，有一個獨立、隔離的 ZenOS instance 可以使用 |
| 客戶公司的管理員 | 能邀請成員、管理自己公司的 ZenOS，不能看到其他公司的資料 |
| ZenOS 營運人員 | 能為新客戶開設 instance，推送版本更新，不需要手動維護每個客戶的資料 |
| 有資安需求的客戶 IT | 能把 ZenOS 部署在自己公司的 infra 上，自主控制資料 |

---

## 需求

### P0（必須有）

#### 1. 每間客戶公司有獨立的資料隔離

- **描述**：每間客戶公司的資料（entities、tasks、成員清單）在資料庫層物理隔離，不靠 backend code 的過濾來維持。一間公司的管理員或成員，在任何情況下都看不到其他公司的資料。
- **Acceptance Criteria**：
  - Given 客戶 A 和客戶 B 各有自己的 ZenOS instance，When 客戶 A 的管理員查詢 entities，Then 只能看到屬於客戶 A 的資料，即使知道客戶 B 的 instance URL 也無法存取。
  - Given 兩間公司使用同一個 ZenOS 版本，When 其中一間公司的資料被刪除或損毀，Then 另一間公司不受影響。

#### 2. 語意澄清：`partners` collection = 這間公司的成員清單

- **描述**：在新架構下，每個 Firebase Project 只服務一間公司。`partners` collection 裡的每筆資料代表這間公司的一個**成員**（員工或合作夥伴），不再有「哪間公司」的混淆。`isAdmin` 欄位代表這個成員是否有權限管理這個 ZenOS instance（邀請成員、調整設定）。
- **Acceptance Criteria**：
  - Given 一個 ZenOS instance，When 查看 `partners` collection，Then 所有文件都是這間公司的成員，沒有跨公司的混淆。
  - Given 一個有 `isAdmin: true` 的成員，When 他登入 Dashboard，Then 能看到成員管理介面；一般成員看不到這個介面。

#### 3. 現有客戶（Paceriz）無縫 migration

- **描述**：Paceriz 是目前唯一的生產客戶。架構升級不能中斷 Paceriz 的服務。Migration 完成後，Paceriz 的所有資料（entities、tasks、成員）必須完整保留，MCP 連線不中斷。
- **Acceptance Criteria**：
  - Given Paceriz 目前的所有資料，When migration 完成，Then entities 數量、tasks 數量、成員清單與 migration 前一致。
  - Given Paceriz 的 MCP partner key，When migration 完成後用同樣的 key 連線，Then MCP tools 正常運作。
  - Given migration 執行期間，When Paceriz 的成員在使用 ZenOS，Then 服務中斷時間不超過 X 分鐘。（X 待與 Paceriz 確認可接受的維護窗口）

#### 4. 新客戶開設 instance 流程

- **描述**：ZenOS 營運人員能為新客戶開設一個新的 ZenOS instance。新 instance 包含：獨立的資料儲存、一個初始管理員帳號、可以立刻連線的 MCP endpoint。
- **Acceptance Criteria**：
  - Given 一筆新客戶的基本資料（公司名稱、管理員 email），When 營運人員執行開設流程，Then 新 instance 在 N 分鐘內可用（N 待 Architect 評估）。
  - Given 新 instance 建立完成，When 管理員用初始帳號登入，Then 能看到空的 ZenOS Dashboard，並能邀請其他成員。
  - Given 新 instance 建立完成，When 用新的 MCP partner key 測試連線，Then 能成功呼叫 MCP tools。

#### 5. 版本更新集中推送

- **描述**：ZenOS 更新（bug fix、新功能）能統一推送到所有客戶的 instance，不需要逐一手動操作每個客戶的環境。
- **Acceptance Criteria**：
  - Given 一個新版本的 ZenOS，When 觸發更新流程，Then 所有客戶的 instance 都拿到新版本，不需要對每個客戶個別操作。
  - Given 更新完成，When 任意客戶用 MCP 連線，Then 回應行為符合新版本的預期。

---

### P1（應該有）

#### 6. 地端部署支援

- **描述**：有資安需求的客戶 IT 能把 ZenOS 部署在自己掌控的 infra 上（自建伺服器、私有雲）。ZenOS 提供標準的打包產物（Docker image）和部署文件，客戶 IT 自行完成部署和後續更新。
- **Acceptance Criteria**：
  - Given 部署文件和 Docker image，When 一個沒有 ZenOS 背景的系統管理員按步驟操作，Then 能在自己的 infra 上把 ZenOS 跑起來。
  - Given 地端部署的 ZenOS instance，When 使用 MCP tools，Then 功能與雲端版本一致。
  - Given ZenOS 發布新版本，When 客戶 IT 想更新，Then 能按文件自行 pull 新 image 並升級，不需要 ZenOS 人員介入。

---

### P2（可以有）

#### 7. 地端部署的授權管理

- **描述**：地端部署的客戶，ZenOS 能知道他們是否在有效的授權期間內使用，到期提醒。（不一定要技術強制，但要有機制讓雙方都知道狀態。）
- **Acceptance Criteria**：
  - Given 一個地端部署的 instance，When 授權到期日前 30 天，Then 管理員會收到提醒。
  - Given 授權到期，When 管理員登入 Dashboard，Then 看到續約提示。

---

## 明確不包含

- 跨公司共享資料或 entity（各公司的資料完全隔離，不做跨租戶功能）
- 自助開設 instance（Phase 0/1 由 ZenOS 營運人員手動開設，不做自助 signup 流程）
- 地端部署的遠端監控（ZenOS 不主動連回地端客戶的 instance 收集資料）
- 多地域 / 多雲部署（暫不納入，地端部署本身就解決資料主權需求）

---

## 技術約束（給 Architect 參考）

- **資料隔離層級**：要求在 DB 層物理隔離（不靠 backend code 過濾），Architect 決定實作方式
- **MCP server 共用 image**：同一個 Docker image 要能服務不同客戶，靠啟動時的設定決定連哪個 Firebase Project
- **Migration 必須可回滾**：Paceriz 是生產系統，migration 期間要有能回到舊狀態的方案
- **地端部署打包**：Docker image + 部署文件，不需要用到 GCP 原生服務

---

## 開放問題

1. **Paceriz migration 的維護窗口**：需要與 Paceriz 確認可接受的服務中斷時間（分鐘級？小時級？需要安排在特定時段？）

2. **新客戶開設流程的操作者**：是 ZenOS 工程師跑 script？還是要有一個 ops dashboard 讓非技術人員也能操作？Phase 1 最低限度是什麼？

3. **地端授權管理機制**：P2 的授權提醒，是用 email 通知？還是 Dashboard 內建提示？如果客戶 IT 把 Dashboard 也關掉了怎麼辦？（暫時先不做強制機制，但要確認這個邊界）

4. **地端部署支援的 Firebase 替代方案**：地端客戶未必能用 Firebase（特別是國內有 GCP 限制的環境），Architect 需要評估 Firestore 以外的儲存層是否要在 Phase 1 抽象化，或先鎖定 Firebase 地端（Firebase Emulator / 自建 Firebase）。

5. **MCP partner key 在新架構下的生命週期**：新架構下，partner key 是跟著 Firebase Project（instance 層級）？還是跟著個別成員？需要 Architect 確認設計方向。

6. **LLM cost 模型**：ZenOS AI 功能（如 ontology 分析、盲點推斷）的 LLM 費用由誰負擔？是否每間公司提供自己的 LLM key？

---

## 開放問題解答

1. **Migration window**：不需要維護窗口。`zenos-naruvia` 本身就是 Paceriz 的 Firebase project，現有資料不動。
2. **新客戶開設流程**：Phase 0 工程師跑 script，不做 ops dashboard。
3. **地端授權**：P2，暫不實作。
4. **Storage 抽象化**：先鎖定 Firebase，有需求再抽象。
5. **MCP partner key 層級**：成員層級（per-member apiKey），保留 agent identity 追蹤。
6. **LLM cost 模型**：一間公司一把 LLM key（ZenOS 的 AI 功能用），員工 agent 的 LLM key 不在 ZenOS 範圍。
