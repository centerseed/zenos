# L2 知識節點治理規則 v1.0（含完整範例）

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
6. 通知相關 task 的 linked_entities 更新為新的 L3 entity
