---
doc_id: ADR-014-knowledge-graph-value-validation
title: 架構決策：知識圖譜價值驗證與消費層投資策略
type: ADR
ontology_entity: 知識圖譜架構
status: approved
version: "1.0"
date: 2026-04-05
supersedes: null
---

# ADR-014：知識圖譜價值驗證與消費層優先策略

## Context

ZenOS 建構在 ontology/知識圖譜上（entity + relation + source），但開發至今：
- 維護成本高（sync/capture/governance 流程複雜）
- 感受不到圖譜產出的 insight
- 無法量化圖譜相比 RAG 的增量價值

2026-04-05 進行多角色 brainstorm（PM / Architect / Challenger），得出以下共識與分歧。

## 三方共識

**圖譜的價值真實存在，但 ZenOS 目前卡在「有結構、沒消費」的斷層。**

1. **有圖但不能用圖的方式查詢**（Architect）：relation table 存在但沒有 graph traversal tool，search/get/analyze 本質是單點查詢或文字匹配
2. **沒有主動回饋迴路**（PM）：sync/capture 跑完後用戶看不到「什麼變了、影響什麼」
3. **L2 三問門檻是正確的設計**（反駁 Challenger 密度論）：圖譜價值不在節點數量，在 relation 品質和可 query 性

## RAG vs 圖譜的技術邊界（Architect 分析）

RAG 結構性失敗的場景：

| Query 類型 | RAG 能力 | 圖譜能力 | 範例 |
|-----------|---------|---------|------|
| 多跳關聯 | ✗ 靠 embedding 撈不到 | ✓ traversal | 「供應商 A 的零件用在哪些客戶的哪些產品？」 |
| 反向影響分析 | ✗ 無方向性概念 | ✓ inbound traversal | 「停用模組 X 會影響哪些流程？」 |
| 缺口偵測 | ✗ 無法搜尋不存在的東西 | ✓ missing relation query | 「哪些產品沒有指定負責人？」 |
| 時序變化追蹤 | ✗ 每次重新搜尋 | ✓ entity 版本 + relation 歷史 | 「這個概念的定義上個月跟現在有什麼不同？」 |
| 跨 agent 一致性 | ✗ 不同 prompt 不同答案 | ✓ 單一節點保證一致 | 「客戶 A 的折扣上限是多少？」多 agent 共用 |

## PM 識別的高價值消費場景

**目前缺失（P0）：**
- **變更觸發通知**：「客戶 A 的窗口被更新了，影響 3 個進行中的專案」
- **變更差異說明**：「這次 sync 新增 5 個節點、修改 2 段關係，摘要如下」

**殺手場景候選：**
- **「誰知道什麼」路由**：圖譜建出 人→專案→領域 關係網，agent 找到「該問的人」而非搜文件
- **跨時間一致性驗證**：「合約 A 跟三個月前的報價 B 矛盾——何時產生的？」

## Decision

### 策略：消費優先，驗證驅動

不急著判斷「圖譜有沒有價值」，先補消費層讓它有機會展示價值，再用數據決定。

### Action Items

| # | 項目 | 目的 | 優先級 |
|---|------|------|--------|
| 1 | 新增 graph-native MCP tools（`find_path`, `find_dependents`, `find_gaps`） | 讓圖譜可以用圖的方式被 query | P0 |
| 2 | sync/capture 完成後產出變更摘要 | 建立用戶回饋迴路 | P0 |
| 3 | 用 10 個真實 query 做對照實驗：graph query vs RAG | 量化圖譜增量價值 | P1 |
| 4 | 重新評估 positioning：從「知識圖譜治理」到「AI agent 共識層 / single source of truth」 | 對齊中小企業真實痛點 | P1 |

### 輕量化方向（Architect 建議）

- entity description/summary 改為 LLM 從 source 即時生成，不手動維護
- ontology type 粗粒度化（5-10 種），細分類用 LLM 動態判斷
- **消費驅動建構**：只在有人問了圖答不了的問題時才補 relation

## 仍然存在的風險

- Graph-native tool 做出來後若真實場景 RAG 已經夠用，圖譜差異化會很薄——但至少有數據判斷
- 「共識層」positioning 需要 PM 進一步驗證中小企業是否真有「多 agent 矛盾」痛點

## 值得進一步探索

- **「共識載體」價值假說**（Challenger 提出）：圖譜價值不在查詢，在「所有 agent 讀到同一個事實」。如果成立，ZenOS 的 pitch 從「知識圖譜管理」變成「AI agent 的 single source of truth」
- **反向追溯入口**（PM 提出）：「這個節點從哪幾份文件建出來的？」——來源透明化讓用戶信任圖譜

---

## Round 2：消費場景深入分析（2026-04-05）

### 現有消費端瓶頸（PM 分析）

| Tool | 天花板 |
|------|--------|
| search | 關鍵字比對，無法表達「A 和 B 有什麼關係」，回傳節點列表而非路徑 |
| get | 單點查詢，鄰居要多次 call 再手動組合，graph traversal 外散到 caller |
| analyze | 分析單一節點內容，不是節點在圖中的位置意義 |
| read_source | 繞過 ontology 層，退化成 RAG |
| Dashboard | 只能看不能問，靜態快照無探索起點 |

### Graph-Native Query 的具體業務場景（PM 設計）

**find_path — 10 人軟體外包公司**
業務問「客戶 A 和技術合作夥伴 B 有沒有間接關係？」→ 發現兩者透過現有合約產生間接關係 → 新合約談判時主動揭露利益關係。

**find_dependents — 20 人進出口貿易商**
倉管發現主力供應商因颱風停產 → 查影響鏈：供應商 → SKU → 採購單 → 客戶訂單 → 客戶 → 立刻知道要聯繫哪些客戶、調整哪些交期。

**find_gaps — 15 人設計工作室**
主理人做季度知識地圖健檢 → 發現客戶 B 設計規範是孤島（無 relation）→ 指派補上 derives_from 關係 → AI agent 生成設計提案時不漏掉客戶限制。

### Graph-Native Tool 技術設計（Architect）

**架構現況：**
- 已有 `compute_impact_chain`（application 層 BFS），但每跳兩次 DB query，O(N) round-trip
- Relation table schema: `(id, partner_id, source_entity_id, target_entity_id, type, description, verb, ...)`
- 索引充足：`(partner_id, source_entity_id)`, `(partner_id, target_entity_id)` 已建好
- PostgreSQL recursive CTE 完全可行，中小企業規模（數百~數千 entity）無效能瓶頸

**設計決策：獨立 tool，不擴充 search/get。**

| Tool | Parameters | SQL 策略 | 回傳格式 |
|------|-----------|---------|---------|
| `find_path` | from_entity, to_entity, max_depth(6), relation_types | 單向 recursive CTE + depth limit | `{found, path: [{entity_id, name, edge_type, direction}], depth}` |
| `find_dependents` | entity, direction(downstream/upstream/both), max_depth(5), relation_types | 單向 recursive CTE，取代 compute_impact_chain | `{root, tree: [{from, to, edge_type, depth}], total_affected}` |
| `find_gaps` | gap_type(orphan/undocumented/missing_deps/all), scope_entity | LEFT JOIN + NOT EXISTS | `{gaps: [{type, entity, severity, suggestion}], summary}` |

### Challenger 的二次挑戰

**1. Tool routing 問題（嚴重度：高）**
LLM caller 看到 find_path / find_dependents / search 時，靠什麼判斷該用哪個？description 是唯一線索。如果 caller 90% 退回 search，新 tool 等於建了沒人叫。
→ **啟示：** tool description 的設計和 system prompt 的 decision tree 可能比 tool 本身更重要。

**2. 變更摘要的接收者問題（嚴重度：高）**
sync 觸發者剛做完變更，摘要告訴他「你改了什麼」是零資訊增益。真正需要摘要的是其他團隊成員和下游 agent。沒有推送通道（Slack webhook / dashboard notification / agent memory inject），摘要是沒有讀者的文章。
→ **啟示：** MVP 應從「推送給誰、怎麼推」開始設計，而非從摘要格式開始。

**3. 對照實驗的確認偏誤（嚴重度：中）**
10 個 query 由建圖譜的人設計，自然傾向圖譜擅長的問題。真實用戶的問題更可能是模糊自然語言。
→ **啟示：** query 來源應從真實歷史對話紀錄抽取，或由不知道圖譜結構的外部人設計。

**4. 先用現有工具手動驗證（嚴重度：中）**
get + expand_linked 已能手動完成 multi-hop traversal，只是多步呼叫。先跑 5 個真實場景紀錄結果，成本幾乎為零，能回答「值不值得建 tool」。
→ **啟示：** 在寫新 tool 之前，先做 5 次手動 graph traversal 作為 build/no-build 決策依據。

### 修訂後的 Action Items（Round 3，PM + Architect 驗證後）

| # | 項目 | 時間 | 判斷標準 |
|---|------|------|---------|
| 0a | Relation table 加反向索引 + 檢查 verb 填充率 | 隨時可做，不依賴方向 | — |
| 0b | Dashboard UI 措辭整理 | 隨時可做，不依賴方向 | — |
| 1 | 手動跑 5 個 graph query 場景 | 本週 | 5 場景中 3+ 個摩擦無法用 prompt 化解 → 值得 build tool |
| 2 | Positioning 收斂到「公司知識的單一真相來源」 | 與 #1 同步 | 不急推 agent 共識，等 #1 驗出差異化再決定 |
| 3 | 一切看 #1 結果決定 | #1 之後 | graph-native tool / 變更摘要 / 推送通道 / 對照實驗 |

**#1 的 5 個測試場景（PM 設計）：**
1. 「這個客戶目前跑哪些專案，各專案的負責人是誰？」（3 跳）
2. 「我們有哪些供應商同時供貨給超過兩個產品線？」（聚合）
3. 「這個功能模組上次改動是誰負責，他現在還在公司嗎？」（3 跳 + 狀態）
4. 「A 客戶反映的問題，有沒有其他客戶也踩過同樣的坑？」（橫向關聯）
5. 「這個合約到期前，還有哪些交付物沒完成？」（合約→里程碑→任務→狀態）

**#1 每場景記錄格式（Architect 設計）：**
| 欄位 | 用途 |
|------|------|
| 場景名稱 | 具體業務問題 |
| 起點 entity | 從哪個節點開始 |
| 期望答案 | ground truth |
| 實際操作步驟 | 每次 tool call 的 input/output |
| call 次數 | 總共幾次 get/search |
| 結果正確性 | 與 ground truth 一致嗎 |
| 摩擦點 | 哪步卡住、繞路、資訊不足 |
| 若有專用 tool 會省多少步 | 1 call vs N call |

**PM 對 positioning 的重要警告：**
台灣多數中小企業老闆的問題是「員工有沒有在用 AI」，不是「agent 有沒有共識」。
「AI agent 共識層」太前瞻，先用「公司知識的單一真相來源」——不需要用戶先有 agent 才聽得懂。

---

## Round 4：驗證實驗結果（2026-04-05 執行）

### Action Item 0a 結果：Relation Table 現況

| 項目 | 狀態 | 備註 |
|------|------|------|
| target_entity_id 索引 | ✅ 已有 | `idx_relationships_partner_target` |
| list_by_entity 查詢方向 | ✅ 雙向 | 同時查 source 和 target（`WHERE source_entity_id = $1 OR target_entity_id = $1`） |
| 專用反向查詢方法 | ❌ 無 | 目前靠上層 filter，無 `list_incoming()` |
| verb 欄位 | ✅ 有 | 2026-04-03 migration 新增 |

**結論：反向索引不需要加（已有），但缺專用反向查詢方法。**

### Action Item 1 結果：5 個 Graph Query 場景實測

用現有 MCP tools（search + get）對 ZenOS 自身 ontology 手動模擬 graph traversal。

#### 場景結果總覽

| # | 場景 | Calls | 正確？ | 摩擦 | Prompt 能解？ |
|---|------|-------|--------|------|---------------|
| 1 | 多跳影響鏈（改 VDOT 公式影響誰？） | 1 | ✅ | 低 | ✅ impact_chain 已解決 |
| 2 | 聚合交集（兩模組共同影響誰？） | 2 | ✅ | **高** | ❌ 手動交集易出錯 |
| 3 | 反向影響（改 Action Layer 誰受影響？） | 1 | ✅ | 中 | ⚠️ relationships 欄位雜訊多 |
| 4 | 橫向關聯（兩產品有共同關聯嗎？） | 2 | ✅ | **高** | ❌ 手動比較 |
| 5 | 缺口偵測（哪些 L2 模組是孤島？） | 3-17 | ✅ | **極高** | ❌ O(N) 逐一檢查，根本不可行 |

#### 關鍵發現

**已經很強的：`impact_chain`**
- get 回傳時自動預計算前向影響鏈，場景 1 和 3 用 1 次 call 就解決
- 這是 ZenOS 現有的重大設計優勢

**3/5 場景摩擦無法用 prompt 化解：**
1. **缺口偵測（場景 5）**：「找不存在的關聯」需要逐一 get 所有 entity，O(N) 無解 → **最強的 graph tool 論據**
2. **集合交集（場景 2, 4）**：找共同鄰居需要多次 get + 手動比較，規模大時易錯 → **中等價值**
3. **反向 traversal（場景 3）**：可用但雜訊多 → **低價值，改善 UX 即可**

#### Graph Query Tool 的 ROI 排序

| 能力 | 現有 search/get | 專用 tool | 增量價值 |
|------|----------------|----------|---------|
| 前向 traversal | impact_chain（優秀） | 相同 | 無 |
| 缺口偵測 | O(N) 逐一 get，不可行 | 1 call | **極高** |
| 集合交集 | 手動比較，易錯 | 1 call | **中** |
| 反向 traversal | relationships 欄位（雜訊多） | 乾淨的 tree | 低 |

---

## Final Verdict：產品驗證結果（2026-04-05）

### 跨產品驗證數據

| 產品 | L2 模組數 | 有 relationship 的 L2 | impact_chain 有效 | find_gaps 有效 |
|------|----------|----------------------|-------------------|---------------|
| ZenOS | ~12 | 大部分 | ✅（Action Layer 等） | ✅（精準找到 Quality Intelligence orphan） |
| Paceriz | 9 | 部分（跑步科學指標 6 rels） | ✅（VDOT→訓練計畫→AI教練，3 跳） | ✅（L2 ≥ 5，有意義） |
| naru_agent | 0 | — | N/A（無 L2） | ❌（2 entity，全是噪音） |
| SME 製造業 | 0 | — | N/A（無 L2） | ❌（2 entity，全是噪音） |

### 殺手 insight：impact_chain 在 Paceriz 上的真實價值

```
問題：「改了 VDOT 公式會影響什麼？」

impact_chain 回答（1 call）：
  跑步科學指標 --enables--> 訓練計畫系統 --impacts--> Rizo AI 教練
  跑步科學指標 --enables--> 訓練閉環分析
  跑步科學指標 --impacts--> 資料結構與存儲 --impacts--> 運動數據接入

RAG 能回答嗎？不行。RAG 找到「提到 VDOT 的文件」，但無法推出
「VDOT 改了 → Rizo AI 教練的配速建議也要跟著改」這個三跳因果鏈。
```

### 結論

**圖譜值得繼續投資。殺手能力是 impact_chain，不是 find_gaps。**

| 能力 | 價值等級 | 證據 | 投資方向 |
|------|---------|------|---------|
| **impact_chain** | **核心差異化** | Paceriz 三跳因果鏈，RAG 做不到 | 加強：反向 chain、Dashboard 視覺化、主動推送 |
| **find_gaps** | 中等，受規模限制 | ZenOS 有效，naru_agent 噪音 | 加成熟度閾值（L2 < 5 時提示而非報告） |
| **incoming/outgoing 分離** | 中等 | Action Layer 3 out / 22 in 清楚區分方向 | 已完成，保持 |
| **common_neighbors** | 低，無自然觸發場景 | 技術正確但無業務需求 | 暫緩觀察 |

### 對原始問題的回答

> 「我目前沒辦法從知識圖譜中得到更多 insight，但維護知識圖譜付出很多管理成本。」

**原因不是圖譜沒價值，是你一直在投資建構端而忽略了消費端。**

impact_chain 已經能產出 RAG 做不到的 insight（跨模組因果鏈），但這個能力被埋在 `get` 的回傳值裡，沒有被主動展示、沒有被推送、沒有被 Dashboard 視覺化。用戶不知道它存在，所以感受不到。

### 下一階段投資方向

重心從「ontology 維護自動化」轉向「impact_chain 的消費場景最大化」：

1. **反向 impact chain**：「改了 X 會影響誰」目前只有前向。反向（「誰影響我」）同等重要
2. **Dashboard 影響鏈視覺化**：點擊節點時直接顯示上下游影響路徑，而非只顯示直接鄰居
3. **變更推送**：sync 更新節點後，自動通知影響鏈上的下游節點 owner
4. **Positioning**：impact_chain 就是「公司知識的因果追溯能力」——這比「知識圖譜治理」和「AI agent 共識層」都更具體、更容易被中小企業理解
