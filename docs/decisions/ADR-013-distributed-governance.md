---
type: ADR
id: ADR-013
status: Accepted
created: 2026-04-04
updated: 2026-04-04
---

# ADR-013: 分散治理模型——Agent 端語意判斷 vs Server 端結構執法

## 決策

將治理責任明確分成兩層：

- **Agent 端**：負責語意判斷（三問、分類、撰寫內容、填欄位）
- **Server 端**：負責結構執法（格式驗證、狀態機、去重、品質閘）

**原則：Agent 做語意判斷，Server 做結構執法。**

## 背景

### 現狀（全 Agent 端治理）

目前治理規則以 Skill 的形式提供給 Agent 執行：

- Agent 讀取 governance skill，自行判斷是否符合規則
- Server 端（MCP tools）幾乎不做主動驗證，只做 CRUD
- 規則的執行依賴 Agent 完整閱讀並遵循 skill 內容

### 問題

**可靠性：** Agent 處理複雜多步驟流程時容易遺漏步驟、跳過檢查，尤其當 skill 文件超過 100 行後，遵循率顯著下降。

**可維護性：** 治理邏輯散落在各個 skill 文件。Skill 越豐富，複製貼上的治理邏輯越多，越難同步更新。

**競爭力：** Skill 是開放的（客戶可以複製），但 Server 端驗證邏輯是閉源的。若治理智慧全在 Skill，則核心競爭力可被複製。

**用戶鎖定：** Ontology 資料是用戶的資產，但若 Server 不提供有意義的驗證和建議，用戶遷移成本低，鎖定效應弱。

## 決策理由

### 為什麼 Agent 端保留語意判斷

語意判斷需要 LLM：

- 三問（公司共識？有下游影響？跨角色可讀？）需要理解內容語意
- 撰寫 summary / impacts 需要文字生成能力
- 判斷新建 vs 更新現有文件需要語境理解

這些任務無法用規則引擎替代，必須由 Agent 承擔。

### 為什麼 Server 端承擔結構執法

結構驗證不需要 LLM，且應由 Server 強制：

- Frontmatter 格式、狀態機合法性、欄位完整性——純規則，確定性高
- 去重偵測（similar_items）——向量相似度計算，不需要語意理解
- 品質閘（Approved 前的門檻）——必須強制，不能依賴 Agent 自律
- 傳播觸發（impacts 變動 → 通知下游）——事件驅動，適合 Server 端

**關鍵原則：Server 拒絕的操作，Agent 無法繞過；Agent 的建議，Server 不會假設。**

## 具體責任分配

### L2 知識節點

| 層 | 負責事項 |
|----|---------|
| **Agent** | 三問判斷、撰寫 summary、撰寫 impacts 描述 |
| **Server** | impacts ≥ 1 檢查（reject）、verb 非空（reject）、重複偵測（回傳 similar）、stale 偵測（analyze）、entry 歸納觸發 |

### L3 文件

| 層 | 負責事項 |
|----|---------|
| **Agent** | 撰寫內容、填 frontmatter、判斷新建 vs 更新 |
| **Server** | frontmatter 格式驗證（reject）、查重（回傳 similar）、ontology_entity 存在性（reject）、supersede 原子操作、狀態轉換合法性（reject）、Approved 品質閘 |

### Task

| 層 | 負責事項 |
|----|---------|
| **Agent** | 撰寫 title / description / AC |
| **Server** | 動詞開頭檢查（reject）、AC 數量提醒（warning）、去重（回傳 similar）、linked_entities 存在性（reject）、狀態機強制（reject）、review 時 result 必填（reject）、知識反饋建議（suggested_feedback） |

## 對 Skill 的影響

分散治理後，Skill 可以大幅精簡：

- 從「完整流程腳本（200+ 行）」變成「語意判斷指引（< 50 行）」
- Skill 只需要說「做什麼語意判斷」，不需要說「怎麼驗格式」（Server 會驗）
- Skill 開放（可複製）→ 競爭壁壘在 Server 端，不在 Skill

**Skill 的定位轉變：**

```
現在：Skill = 流程腳本（含格式驗證、狀態機邏輯）
目標：Skill = 語意判斷指引（判斷什麼是 L2、怎麼寫 impacts）
```

## 演進路線

```
Phase 0.5（當前）
  豐富 MCP 回傳值：warnings、suggested_actions、similar_items
  Agent 開始讀取並回應 Server 的建議
  Skill 逐步精簡（移除已由 Server 驗證的規則）

Phase 1（Server 執法）
  Server 端狀態機強制（非法轉換 reject）
  supersede 原子操作（一次呼叫完成舊→新）
  similar_items 在 write 時自動回傳
  Skill 精簡為 < 50 行純語意指引

Phase 2（智慧建議）
  analyze 自動建議修復方向
  Governance lint API（可整合 CI）
  治理 Dashboard（健康度可視化）
  suggested_feedback 自動從 task result 萃取知識建議
```

## 考慮過的替代方案

### 方案 A：維持全 Agent 端治理（現狀）

**否決原因：**
- 可靠性問題無解：Skill 越長，Agent 遵循率越低
- 競爭力問題無解：核心治理邏輯全部開放
- 鎖定效應弱：Server 沒有實質價值，用戶可輕易遷移

### 方案 B：全 Server 端治理（Server 包含 LLM）

將語意判斷也移至 Server 端（Server 內嵌 LLM 做三問判斷、生成 summary）。

**否決原因：**
- Server 端 LLM 推論成本高，延遲不可控
- 語意判斷需要用戶脈絡（Agent 已有的 context），Server 端沒有
- 用戶失去對語意判斷的控制權，難以客製化
- 過度工程：Agent 本來就擅長語意，強迫 Server 重做是浪費

## 影響文件

- `docs/spec.md`（治理憲法）：加入分散治理模型章節，更新演進路徑
- `SPEC-governance-framework`：更新傳播契約，加入 Server 端驗證層的角色
- `SPEC-l2-entity-redefinition`：標記哪些規則由 Server 強制執行
- `SPEC-doc-governance`：標記哪些規則由 Server 強制執行
- `SPEC-task-governance`：標記哪些規則由 Server 強制執行
- `skills/governance/`：逐步精簡，移除已由 Server 驗證的規則

## 相關文件

- `SPEC-governance-framework`（治理規則抽象框架）
- `ADR-012-mcp-write-safety`（MCP 寫入安全策略）
- `SPEC-governance-feedback-loop`（治理反饋閉環）
