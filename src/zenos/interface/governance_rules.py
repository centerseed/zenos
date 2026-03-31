"""ZenOS Governance Rules — server-side rule content for governance_guide MCP tool.

規則文本 hardcode 在 server 端，不讀取 local skill 文件。
更新規則只需重新部署 server。

只暴露 External 治理規則（「需要三問通過」），
不暴露 Internal 演算法（LLM 如何判斷三問的 prompt 細節）。

Structure: dict[topic][level] -> str
  topic: entity | document | task | capture
  level: 1 (core summary) | 2 (full rules) | 3 (with examples)
"""

GOVERNANCE_RULES: dict[str, dict[int, str]] = {
    "entity": {
        1: """# L2 知識節點治理規則 v1.0

## 什麼是 L2 Entity
L2 Entity = 公司共識概念。改了它，不同角色（工程師、行銷、老闆）都會受影響。
不是技術模組的文件索引，而是值得被治理傳播追蹤的概念。

## 三問判斷（全通過才能建 L2）
1. 公司共識？任何角色都聽得懂，在不同情境都指向同一件事
2. 改了有 impacts？這個概念改變時，有其他概念必須跟著看
3. 跨時間存活？不會隨某個 sprint 或文件結束而消失

## 硬規則
- 每個 L2 必須至少有 1 條具體 impacts relationship
- impacts 必須說清楚「A 改了什麼 → B 的什麼要跟著看」
- 新建 L2 一律 draft 狀態
- draft → confirmed 必須走 confirm 工具，且需通過 impacts 驗證
- 沒有 impacts 的候選概念，應降為 L3 document 或 sources

## 生命週期
draft → confirmed（三問通過 + ≥1 具體 impacts）
confirmed → stale（impacts 目標失效或過時）
stale → confirmed（重新補齊有效 impacts）

## 分層路由
- 治理規則或跨角色共識 → L2（走三問+impacts gate）
- 正式文件（SPEC/ADR）→ L3 document
- 可指派可驗收的工作 → Task
- 一次性草稿或低價值參考 → entity.sources""",

        2: """# L2 知識節點治理規則 v1.0（完整版）

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
- 「資料庫 schema v3」→ 降為 L3 document 或 sources，掛到「資料架構」L2""",

        3: """# L2 知識節點治理規則 v1.0（含完整範例）

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

## 從一批文件識別 L2（全局統合模式 6 步驟）

Step 1：全局閱讀——先讀所有文件，不急著建 entity
Step 2：列出候選概念——從文件中找出反覆出現、跨角色使用的詞彙
Step 3：三問過濾——對每個候選概念跑三問，排除不通過的
Step 4：切割獨立概念——確保每個 L2 可以獨立改變（不是「某文件的 section」）
Step 5：推斷 impacts——對每個 L2 問：「它改了，哪些其他 L2 要跟著看？」
Step 6：說不出 impacts → 降為 L3 或 sources，不強行建 L2

## impacts 寫法模板（3 個完整範例）

範例 1：定價調整影響合約
```
source_entity: 訂閱定價模型
relationship_type: impacts
target_entity: 合約模板
note: 訂閱定價模型 改了費率結構或計費週期 → 合約模板 的計費條款章節需重新審核確認
```

範例 2：信任等級影響功能解鎖
```
source_entity: 用戶信任等級
relationship_type: impacts
target_entity: 功能存取控制
note: 用戶信任等級 新增或調整等級定義 → 功能存取控制 的各功能解鎖門檻需同步更新
```

範例 3：架構決策影響部署流程
```
source_entity: 服務分層架構
relationship_type: impacts
target_entity: 部署流程
note: 服務分層架構 調整層間依賴方向 → 部署流程 的服務啟動順序需重新驗證
```

## Entity Entry 範例（各 type 各一個）

decision entry：
```
type: decision
content: 決定採用三層架構（L1/L2/L3）而非扁平 entity，原因是需要不同治理強度的分層管理
```

insight entry：
```
type: insight
content: 冷啟動時「說不出 impacts」是最強的 L3 降級訊號，比三問更有判別力
```

limitation entry：
```
type: limitation
content: 跨公司的通用概念（如「客戶」）容易被建成 L2，但缺少公司特定語意，需加 summary 補充
```

change entry：
```
type: change
content: 2026-Q1 將「技術架構」拆成「服務分層架構」和「資料模型架構」兩個獨立 L2
```

context entry：
```
type: context
content: 此 entity 的命名沿用 Phase 0 決策，未來如果用語改變需更新所有 linked_entities
```

## L2 → L3 降級流程（step by step）

1. 確認降級原因（三問哪題沒過 / 說不出 impacts）
2. 建 L3 document entity，type=ADR 或 REF
3. 將原 L2 的 summary / sources 複製到 L3
4. 找到最相關的 L2，設定 ontology_entity 指向它
5. 如果原 L2 已有 confirmed 狀態，先改為 stale，說明降級原因
6. 通知相關 task 的 linked_entities 更新為新的 L3 entity""",
    },

    "document": {
        1: """# L3 文件治理規則 v1.0

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 必要欄位
- title: 文件標題
- type: SPEC / ADR / TD / PB / REF / SC（決策紀錄/技術設計/指南/參考）
- source.uri: 文件的存放位置（GitHub URL 或本地路徑）
- ontology_entity: 掛載到哪個 L2 entity 的名稱
- status: draft / under_review / approved / superseded / archived

## 生命週期
draft → under_review → approved（正式文件）
approved → superseded（被新版取代時，保留原文件，建立指向）
任何狀態 → archived（廢棄）

## 硬規則
- 每份文件必須掛載到至少一個 L2 entity（ontology_entity 必填）
- source.uri 必填（沒有 URI 的文件不值得建 entity）
- supersede 時必須更新被取代文件的 status 並指向新版

## 分類說明
- SPEC: 功能規格（what + why）
- ADR: 架構決策紀錄（why this choice）
- TD: 技術設計（how）
- PB: 操作手冊 / Playbook
- REF: 參考資料（競品分析、研究報告等）
- SC: Script / 腳本文件""",

        2: """# L3 文件治理規則 v1.0（完整版）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 必要欄位
- title: 文件標題
- type: SPEC / ADR / TD / PB / REF / SC
- source.uri: 文件的存放位置（GitHub URL 或本地路徑）
- ontology_entity: 掛載到哪個 L2 entity 的名稱
- status: draft / under_review / approved / superseded / archived

## 完整 Frontmatter 格式
```yaml
---
doc_id: SPEC-feature-name          # 唯一 ID（格式：類型-描述）
title: 功能規格：功能名稱
type: SPEC                          # SPEC|ADR|TD|PB|REF|SC
ontology_entity: L2 Entity 名稱     # 掛載的 L2 entity
status: draft                       # draft|under_review|approved|superseded|archived
version: "0.1"
date: 2026-01-01
supersedes: null                    # 被此文件取代的文件 ID（如有）
---
```

## 生命週期
draft → under_review → approved（正式文件）
approved → superseded（被新版取代時，保留原文件，建立指向）
任何狀態 → archived（廢棄）

## Supersede 流程細節
1. 建立新版文件（新 doc_id，status=draft）
2. 新文件 frontmatter 加 supersedes: 舊文件 ID
3. 舊文件 status 更新為 superseded
4. 在 ZenOS 建 relationship：新文件 supersedes 舊文件
5. 保留舊文件（不刪除），讓歷史可追溯

## Stale 偵測規則
文件可能過時的訊號：
- approved 文件已超過 90 天未被 review
- 掛載的 L2 entity 已變為 stale 狀態
- 相關 task 的 result 顯示文件描述的行為已改變
- git log 顯示實作已大幅偏離文件描述

偵測到 stale 時：建 task 要求 review，tag 文件為 under_review。

## Batch Sync 操作說明
從 git log 批量同步文件狀態：
1. 掃描 git log，找出最近修改的 SPEC/ADR/TD 文件
2. 比對 ZenOS 中對應 document entity 的 status
3. 如果 git 文件有新 commit 但 ZenOS status 仍是 draft → 建議更新為 under_review
4. 如果 git 文件已刪除但 ZenOS 仍 approved → 標記為 archived

## 分類說明（含決策準則）
- SPEC: 功能規格（what + why）—— 面向產品，定義做什麼
- ADR: 架構決策紀錄（why this choice）—— 面向工程，記錄為什麼這樣選
- TD: 技術設計（how）—— 面向實作，說明怎麼做
- PB: 操作手冊 / Playbook —— 面向操作，SOP 類文件
- REF: 參考資料 —— 外部研究、競品分析、不可改變的參考
- SC: Script / 腳本 —— 自動化腳本的說明文件

選型準則：看受眾和目的，不看篇幅。一份短的「為什麼」= ADR，長的「怎麼做」= TD。""",

        3: """# L3 文件治理規則 v1.0（含完整範例）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是 task（文件沒有 owner 和 AC）。

## 各文件類型完整範例 Frontmatter

SPEC 範例：
```yaml
---
doc_id: SPEC-governance-framework
title: 功能規格：治理框架
type: SPEC
ontology_entity: 知識治理框架
status: approved
version: "1.0"
date: 2026-02-15
supersedes: null
---
```

ADR 範例：
```yaml
---
doc_id: ADR-007-entity-architecture
title: 架構決策：Entity 三層模型
type: ADR
ontology_entity: 知識節點架構
status: approved
version: "1.0"
date: 2026-01-20
supersedes: ADR-003-entity-flat-model
---
```

TD 範例：
```yaml
---
doc_id: TD-three-layer-architecture
title: 技術設計：三層架構實作
type: TD
ontology_entity: 服務分層架構
status: under_review
version: "0.3"
date: 2026-03-01
supersedes: null
---
```

## Supersede 操作步驟（完整流程）

情境：ADR-007 取代了 ADR-003

Step 1：在文件系統建立 ADR-007，frontmatter 加 supersedes: ADR-003
Step 2：在 ZenOS 建 document entity：
```
write(
  collection="documents",
  data={
    "doc_id": "ADR-007-entity-architecture",
    "title": "架構決策：Entity 三層模型",
    "type": "ADR",
    "ontology_entity": "知識節點架構",
    "status": "approved",
    "source": {"uri": "docs/decisions/ADR-007-entity-architecture.md"},
    "supersedes": "ADR-003-entity-flat-model"
  }
)
```
Step 3：更新舊文件 entity：
```
write(
  collection="documents",
  data={
    "doc_id": "ADR-003-entity-flat-model",
    "status": "superseded",
    "superseded_by": "ADR-007-entity-architecture"
  }
)
```
Step 4：建立 relationship：
```
write(
  collection="relationships",
  data={
    "source_entity": "ADR-007-entity-architecture",
    "target_entity": "ADR-003-entity-flat-model",
    "relationship_type": "supersedes"
  }
)
```

## 從 git log 同步 document 狀態的流程

```
1. git log --name-only --since="30 days ago" -- "docs/**/*.md"
   → 找出最近 30 天修改的文件

2. 對每個修改的文件：
   a. 讀取 frontmatter 取得 doc_id 和 type
   b. search(collection="documents", query=doc_id) 找對應 entity
   c. 比對：
      - git 有修改 + ZenOS status=draft → 建議 under_review
      - git 有新文件 + ZenOS 無 entity → 建議建立 entity
      - git 文件已刪除 + ZenOS status=approved → 建議 archived

3. batch write 更新
```

## 常見陷阱

陷阱 1：把 L2 entity 的 summary 當 document
→ summary 是概念描述，不是文件。文件必須有 source.uri。

陷阱 2：不設 ontology_entity
→ 每份文件都是某個 L2 概念的具體化。找不到 L2？先建 L2 再掛文件。

陷阱 3：supersede 時刪除舊文件
→ 不刪除，改 status=superseded。歷史決策需要可追溯。""",
    },

    "task": {
        1: """# Task 治理規則 v1.0

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。
每個 task 必須連結回 ontology（linked_entities），讓執行者自動獲得相關 context。

## 建票最小規範
- title: 動詞開頭（「實作 X」「設計 Y」「修復 Z」）
- description: 包含背景、問題、期望結果三段
- acceptance_criteria: 2-5 條，每條可獨立驗收
- linked_entities: 1-3 個相關 entity（最重要的 L2 必須在其中）
- plan_id + plan_order: 如果屬於某個計畫，必填

## 狀態流（2026-03-31）
todo → in_progress → review → done
任何活躍狀態 → cancelled
（不使用 blocked/backlog/archived 狀態；阻塞資訊改用 blocked_by/blocked_reason）

## 欄位責任
- created_by：owner 的 partner.id（MCP 由 API key context 決定）
- assignee：執行者 partner.id（可空，但需有明確責任落點）
- updated_by：最後更新者 partner.id（create 時預設 = created_by）

## 驗收規則
- 完成後必須更新 result 欄位（status=review 時必填）
- done 狀態只能透過 confirm 工具達成
- 知識反饋：task 完成後，從 result 中萃取的 entry/blindspot 應寫回 ontology

## 禁止行為
- title 不動詞開頭
- description 缺少背景/問題/期望結果
- linked_entities 為空
- 完成後不更新 result""",

        2: """# Task 治理規則 v1.0（完整版）

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。
每個 task 必須連結回 ontology（linked_entities），讓執行者自動獲得相關 context。

## 建票最小規範
- title: 動詞開頭（「實作 X」「設計 Y」「修復 Z」）
- description: 包含背景、問題、期望結果三段
- acceptance_criteria: 2-5 條，每條可獨立驗收
- linked_entities: 1-3 個相關 entity（最重要的 L2 必須在其中）
- plan_id + plan_order: 如果屬於某個計畫，必填

## plan_id / plan_order 規則
- plan_id：所屬計畫的 ID。一個計畫通常對應一個 milestone 或 sprint
- plan_order：此 task 在計畫中的執行順序（整數，從 1 開始）
- 沒有 plan 的 task 可以省略，但有 plan_id 時 plan_order 必填
- plan_order 決定 Kanban 的排列順序，也是 AI 優先級推薦的參考

## 狀態流（2026-03-31）
todo → in_progress → review → done
任何活躍狀態 → cancelled
（不使用 blocked/backlog/archived 狀態；阻塞資訊改用 blocked_by/blocked_reason）

## 欄位責任
- created_by：owner 的 partner.id（MCP 由 API key context 決定）
- assignee：執行者 partner.id（可空，但需有明確責任落點）
- updated_by：最後更新者 partner.id（create 時預設 = created_by）

## 驗收規則
- status=review 時 result 必填
- result 格式：描述做了什麼、驗證了什麼、遇到什麼問題
- done 狀態只能透過 confirm 工具達成（不能直接 write status=done）
- confirm 時 QA/reviewer 必須確認每條 acceptance_criteria 都已達成

## 知識反饋閉環
Task 完成後的知識應流回 ontology：
1. 萃取 insight：從 result 中找出值得記錄的技術洞察
2. 寫回 entity entry：write(collection="entity_entries", data={type="insight", ...})
3. 記錄 blindspot：如果過程中發現未知的未知，建 blindspot entity
4. 更新相關 L2：如果 task 改變了某個概念的語意，更新 entity summary

## AI 優先級推薦邏輯
系統根據以下因素自動推薦任務優先順序：
- plan_order（計畫中的順序）
- 與被阻塞依賴（blocked_by）的關係
- linked_entities 的 staleness（對應 L2 是否過時）
- 上次更新時間（越久未動越往前排）
推薦結果僅供參考，人類可覆蓋。""",

        3: """# Task 治理規則 v1.0（含完整範例）

## Task 的定位
Task 不是 entity，是 ontology 的 output path——從知識洞察產生的具體行動。

## 建票範例：好 vs 不好的對比

### 不好的建票
```
title: auth 修改
description: 改一下 auth 相關的東西
acceptance_criteria: 完成
linked_entities: []
```
問題：title 沒動詞、description 缺三段結構、AC 不可驗收、linked_entities 空

### 好的建票
```
title: 實作 JWT refresh token 自動輪換
description: |
  背景：目前 JWT token 有效期 24 小時，用戶需要頻繁重新登入。
  問題：長期有效的 token 如果被竊取，攻擊視窗過大。
  期望結果：access token 有效期縮短為 1 小時，refresh token 自動輪換，
           用戶體驗不受影響。
acceptance_criteria:
  - access token 有效期為 1 小時，超過後自動使用 refresh token 換新
  - refresh token 使用後立即失效（one-time use）
  - 前端無感刷新（用戶不需要重新登入）
  - 所有 token 輪換操作有 audit log
linked_entities: ["用戶認證架構", "資安合規要求"]
plan_id: "plan-q1-security"
plan_order: 3
```

## 知識反饋範例（從 result 萃取 entry 的流程）

完成後的 result：
```
實作了 JWT refresh token 輪換。遇到問題：Redis 在 Cloud Run 無狀態環境下
需要特別處理 token 黑名單。最終採用 short-lived token + DB 記錄已用 token 方案。
性能影響：每次 refresh 多一次 DB 查詢，p99 增加 20ms，可接受。
```

從 result 萃取並寫回 ontology：

insight entry：
```
write(
  collection="entity_entries",
  data={
    "entity_name": "用戶認證架構",
    "type": "insight",
    "content": "Cloud Run 無狀態環境不適合 Redis token 黑名單，改用 DB 記錄已用 token，p99 增加 20ms"
  }
)
```

limitation entry：
```
write(
  collection="entity_entries",
  data={
    "entity_name": "用戶認證架構",
    "type": "limitation",
    "content": "每次 token refresh 需 DB 查詢，高頻刷新場景需要監控"
  }
)
```

## Plan 結構範例

計畫通常對應一個 milestone，tasks 按 plan_order 排序：

```
plan_id: "plan-q1-security"
plan_name: Q1 資安強化

plan_order 1: 審查現有 auth 流程（linked: 用戶認證架構）
plan_order 2: 建立資安 checklist（linked: 資安合規要求）
plan_order 3: 實作 JWT refresh token 輪換（linked: 用戶認證架構, 資安合規要求）
plan_order 4: 滲透測試與修復（linked: 資安合規要求）
plan_order 5: 更新 auth 架構文件（linked: 用戶認證架構）
```

## 禁止行為（含說明）

| 禁止行為 | 原因 |
|---------|------|
| title 不動詞開頭 | 無法快速判斷要做什麼 |
| description 缺三段結構 | 執行者缺少背景，容易做錯方向 |
| linked_entities 為空 | 切斷 task 與知識層的連結，失去 ontology 價值 |
| 完成後不更新 result | 知識無法流回 ontology，形成知識黑洞 |
| 直接 write status=done | 繞過驗收流程，AC 可能未達成 |""",
    },

    "capture": {
        1: """# 知識捕獲分層路由規則 v1.0

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 寫入 L2 的強制要求（Server 端硬性規則）
write(collection="entities", data={type="module", ...}) 時必須附帶 layer_decision：
- q1_persistent: true/false（跨時間存活？）
- q2_cross_role: true/false（跨角色共識？）
- q3_company_consensus: true/false（公司共識？）
- impacts_draft: ["A 改了 X → B 的 Y 要跟著看"] （至少 1 條）

三問未全通過 → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問通過但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

## 冷啟動（首次捕獲一批文件）
Step 1: 讀完所有文件（先全局，後切割）
Step 2: 辨識公司共識概念（三問過濾）
Step 3: 切割獨立的 L2 候選（可獨立改變原則）
Step 4: 推斷 impacts（A 改了 → B 要跟著看）
Step 5: 說不出 impacts → 降為 L3 或 sources
Step 6: 全局確認後，批量 write（帶 layer_decision）""",

        2: """# 知識捕獲分層路由規則 v1.0（完整版）

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 寫入 L2 的強制要求（Server 端硬性規則）
write(collection="entities", data={type="module", ...}) 時必須附帶 layer_decision：
- q1_persistent: true/false（跨時間存活？）
- q2_cross_role: true/false（跨角色共識？）
- q3_company_consensus: true/false（公司共識？）
- impacts_draft: ["A 改了 X → B 的 Y 要跟著看"] （至少 1 條）

三問未全通過 → 系統回傳 LAYER_DOWNGRADE_REQUIRED
三問通過但 impacts_draft 空 → 系統回傳 IMPACTS_DRAFT_REQUIRED

## 錯誤路徑處理

收到 LAYER_DOWNGRADE_REQUIRED 時：
1. 找出哪問沒通過（q1/q2/q3 哪個是 false）
2. 重新考慮是否真的是公司共識概念
3. 如果確實不是 L2 → 改為 L3 document 或 sources
4. 如果認為判斷錯誤 → 在 layer_decision 中補充說明後重試

收到 IMPACTS_DRAFT_REQUIRED 時：
1. 問自己：「這個概念改了，哪個其他概念要跟著看？」
2. 如果真的想不出任何 impacts → 強烈訊號此概念不夠 L2
3. 補充至少一條具體 impacts 後重試

## 增量捕獲 vs 全局統合模式

增量模式（日常使用）：
- 一次捕獲 1-3 個概念
- 適合：開完會、看完一份文件、做完一個 task
- 流程：識別概念 → 三問 → 如通過直接 write

全局統合模式（冷啟動 / 大型 review）：
- 一次處理整個 codebase 或一批文件
- 適合：首次接手專案、季度 ontology review
- 流程：先讀全局，再識別，再統一 write
- 重點：不要邊讀邊 write，等全局視野建立後再決定 L2 邊界

## Impacts 推斷策略

問法 1（改變傳播）：「如果這個概念的定義改了，哪些文件/流程/系統要更新？」
問法 2（依賴關係）：「哪些東西的正確性依賴於這個概念是穩定的？」
問法 3（跨角色影響）：「工程師改了這個，行銷/法務/客服需要知道什麼？」

如果三個問法都問不出答案 → 此概念不是 L2。

## 降級流程細節

降為 L3 document：
- 建 document entity，設 type 和 source.uri
- ontology_entity 指向最相關的 L2
- 適合：有正式文件形式的內容

降為 sources：
- 不建 entity，直接加到現有 L2 的 sources 陣列
- 適合：參考資料、草稿、一次性輸入
- sources 格式：{uri: "...", type: "document|github|notion", synced_at: "..."}""",

        3: """# 知識捕獲分層路由規則 v1.0（含完整範例）

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 完整冷啟動範例（從原始文件到 ontology）

### 原始文件（假設接手一個新專案）
```
- README.md：介紹 ZenOS 是 AI Context 層
- docs/ADR-001.md：決定採用 PostgreSQL
- docs/SPEC-pricing.md：定價模型規格
- docs/SPEC-auth.md：用戶認證規格
- src/models/user.py：用戶資料模型
```

### Step 1：全局閱讀
先讀所有文件，建立整體印象，不急著建 entity。

### Step 2：列出候選概念
從文件中識別反覆出現的詞彙：
- ZenOS（產品概念）
- 定價模型（跨文件出現，有完整規格）
- 用戶認證（有完整規格）
- PostgreSQL（技術選型）
- 用戶資料模型（技術實作）

### Step 3：三問過濾

「定價模型」：
- 公司共識？✓（行銷、工程、法務都理解）
- 改了有 impacts？✓（影響合約、程式碼、文件）
- 跨時間存活？✓（比任何 sprint 都長壽）
→ 通過，L2 候選

「PostgreSQL」：
- 公司共識？△（工程師理解，行銷不需要理解）
- 改了有 impacts？✓（影響部署/遷移腳本）
- 跨時間存活？✓
→ 不通過（q1），降為 ADR 文件

「用戶資料模型」：
- 公司共識？✗（只有工程師理解）
→ 不通過，降為 L3 document 或 sources

### Step 4：推斷 impacts

「定價模型」的 impacts：
- 定價模型 改了費率結構 → 合約模板 的計費條款需更新
- 定價模型 新增方案 → 產品功能門檻 的解鎖邏輯需更新

### Step 5：批量 write

```python
# 建 L2：定價模型
write(
  collection="entities",
  data={
    "name": "定價模型",
    "type": "module",
    "summary": "ZenOS 的訂閱費率結構和計費邏輯",
    "status": "draft",
    "layer_decision": {
      "q1_persistent": True,
      "q2_cross_role": True,
      "q3_company_consensus": True,
      "impacts_draft": [
        "定價模型 改了費率結構 → 合約模板 的計費條款需更新",
        "定價模型 新增方案 → 產品功能門檻 的解鎖邏輯需更新"
      ]
    }
  }
)

# 建 L3 document：PostgreSQL ADR
write(
  collection="documents",
  data={
    "doc_id": "ADR-001-postgresql",
    "title": "架構決策：選用 PostgreSQL",
    "type": "ADR",
    "ontology_entity": "資料儲存架構",
    "status": "approved",
    "source": {"uri": "docs/ADR-001.md"}
  }
)
```

## layer_decision 填寫範例：好 vs 不好

### 不好的填寫
```python
layer_decision={
  "q1_persistent": True,
  "q2_cross_role": True,
  "q3_company_consensus": True,
  "impacts_draft": ["影響其他東西"]  # 太模糊
}
```

### 好的填寫
```python
layer_decision={
  "q1_persistent": True,
  "q2_cross_role": True,
  "q3_company_consensus": True,
  "impacts_draft": [
    "定價模型 調整計費週期（月→年） → 合約模板 的自動續約條款需法務重新審核",
    "定價模型 新增企業方案 → 功能存取控制 的企業功能白名單邏輯需更新"
  ]
}
```

## 常見錯誤與修正

錯誤 1：「每個文件都應該有對應的 L2」
→ 不對。文件是 L3，掛在 L2 下面。一個 L2 可以有多份文件。

錯誤 2：「說不出 impacts 沒關係，先建起來再說」
→ 不對。說不出 impacts 是 L3 降級的強烈訊號。強行建立沒有 impacts 的 L2 只會讓 ontology 膨脹卻沒有治理價值。

錯誤 3：「全局讀完再 capture 太慢，邊讀邊 write 比較快」
→ 冷啟動時不要邊讀邊 write。全局視野建立後才能正確判斷 L2 邊界。增量模式才邊讀邊 write。""",
    },
}
