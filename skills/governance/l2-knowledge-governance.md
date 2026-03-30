# L2 知識節點治理規則 v1.0（完整版）

## 什麼是 L2 Entity
L2 Entity = 公司共識概念。改了它，不同角色（工程師、行銷、老闆）都會受影響。
不是技術模組的文件索引，而是值得被治理傳播追蹤的概念。

## 三問判斷（全通過才能建 L2）
1. 公司共識？任何角色都聽得懂，在不同情境都指向同一件事
2. 改了有 impacts？這個概念改變時，有其他概念必須跟著看
3. 跨時間存活？不會隨某個 sprint 或文件結束而消失

### 三問判斷範例

✓ 通過的案例：
- 「定價模型」：工程師、行銷、客服都理解，改了會影響文件/合約/程式碼，比任何一個 sprint 都長壽
- 「用戶信任等級」：跨角色共識，改了影響產品流程/合規要求/UI設計，隨產品成長持續存在
- 「知識捕獲分層」：全公司 agent 都依賴，改了影響所有 agent 行為，是持久的架構概念

✗ 不通過的案例：
- 「Sprint-23 auth 模組」：名稱綁定 sprint，不跨時間
- 「login.py 技術實作」：只有工程師理解，不是公司共識
- 「上週的客戶訪談筆記」：一次性資料，不會跨時間存活

## impacts 的正確寫法

具體（正確）：
- 「定價模型 改了費率算法 → 合約模板 的計費條款要重新審」
- 「用戶信任等級 新增等級 → 產品功能門檻 的解鎖條件要更新」

模糊（不正確）：
- 「定價模型 影響 合約」（缺少「改了什麼」和「要跟著看什麼」）
- 「功能 A 相關 功能 B」（「相關」不是 impacts）

## Entity Entries（附加脈絡）
每個 L2 可以有多條 entry，記錄演變脈絡：

- decision：關於這個 entity 的架構決策（≤100字）
- insight：從實際使用中萃取的洞察（≤100字）
- limitation：已知限制或注意事項（≤100字）
- change：重要的狀態變化紀錄（≤100字）
- context：補充背景資訊（≤100字）

所有 entry 限制 100 字。

## Server 硬性底線 vs 可客製化

硬性底線（server 強制）：
- write type=module 必須附 layer_decision（三問答案 + impacts_draft）
- 三問未全通過 → 回傳 LAYER_DOWNGRADE_REQUIRED
- impacts_draft 空 → 回傳 IMPACTS_DRAFT_REQUIRED
- draft → confirmed 必須有 ≥1 有效 impacts

可客製化（partner 設定）：
- impacts 的詳細驗證規則
- 哪些角色可以 confirm entity
- stale 偵測的時間閾值

## 常見錯誤：技術模組降級案例

錯誤判斷 → 正確處理：
- 「auth 模組」（技術模組）→ 降為 L3 document，掛到「用戶認證架構」L2
- 「API v2」（版本標籤）→ 降為 L3 document，掛到對應的服務 L2
- 「資料庫 schema v3」→ 降為 L3 document 或 sources，掛到「資料架構」L2
