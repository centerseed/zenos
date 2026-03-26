# ZenOS 治理品質監控

> 版本：v1.0
> 日期：2026-03-25
> 狀態：proposal
> 角色：PM

---

## 這份文件要解決什麼

ZenOS 的治理品質不能只看「資料有沒有進來」，而要持續回答四個問題：

1. 知識有沒有覆蓋真正重要的實體與流程。
2. 知識有沒有跟上程式、文件、決策與任務變化。
3. Ontology 內部有沒有矛盾、重複、孤兒節點或失聯任務。
4. 知識有沒有真的轉成 blindspot、task、confirm 與 protocol 更新。

治理監控的目標不是做靜態報表，而是形成一個閉環：

`observe -> detect -> assign -> confirm -> learn`

---

## 治理品質的四個維度

### 1. Coverage

衡量 ontology 是否覆蓋真正重要的產品、模組、角色、目標與治理流程。

**核心指標**
- 核心 product 是否存在且為 active。
- 核心 module 是否都有 parent、relationship、owner 或對應確認責任。
- 核心流程是否有對應 protocol 或 document entry。
- 核心 blindspot 是否都有 linked entity 與後續 task。

### 2. Freshness

衡量 ontology 是否跟得上外部事件變化，而不是停留在舊認知。

**核心指標**
- 最近 7 天有變更的文件，是否已更新對應 document entry。
- 最近 14 天有顯著變更的 entity，是否已被確認或標記 stale。
- 變更發生到 ontology 更新的中位延遲。
- stale 文件占比與 stale entity 占比。

### 3. Consistency

衡量 ontology 的結構與語意是否自洽。

**核心指標**
- orphan entity 比例。
- 沒有 linked entities 的 task 比例。
- protocol 缺失率。
- 語意重複與語意衝突的候選數量。
- 缺少具體 `impacts` 的 L2 比例。

### 4. Actionability

衡量知識是否真的轉成可執行治理，而不是累積靜態知識。

**核心指標**
- L2 entity 具備至少 1 條具體 `impacts` 的比例。
- blindspot 轉 task 比例。
- task 進入 review/done 的比例。
- confirm 佇列的平均滯留時間。
- task 完成後是否有回寫 ontology 或標記 stale。

---

## L2 硬規則：沒有 impacts，就不應存在

ZenOS 的 L2 不是用來收納「大主題」，而是用來承載治理傳播路徑。

因此 L2 的最低成立條件是：

1. 是公司共識概念
2. 改了有下游影響
3. 跨時間存活
4. 至少有 1 條具體 `impacts` relationship

如果一個點沒有任何具體 `impacts`，它就不值得存在於 L2。這通常代表它其實是：

- L3 文件摘要
- 某個 L2 底下的實作細節
- 粒度切錯，應拆分或合併
- 一次性活動，不應留在骨架層

治理上的處置規則：

- 新 capture 出來的候選 L2，若沒有 `impacts`，不得直接升為正式 L2
- 既有 L2 若缺 `impacts`，必須在治理 review 中補齊
- 補不出 `impacts` 的既有 L2，應降級、併回其他 L2，或改掛成 document/source

---

## 監控架構：Rules、LLM、Human

ZenOS 的治理監控不應該全交給 LLM。應該做成三層分工。

### A. Rules 層

適合處理可被明確定義為「有沒有」或「超時沒」的問題。

**Rules 必做項目**
- schema 完整性檢查。
- entity 是否缺 parent_id、relationship、protocol。
- document / entity / task 的狀態統計。
- stale 時間窗與治理延遲。
- draft 比例、confirm backlog、blindspot backlog。
- linked entity、linked protocol、linked blindspot 的存在檢查。
- L2 是否缺少至少 1 條具體 `impacts`。

**輸出形式**
- quality score 的結構性項目。
- red / yellow / green 告警。
- 待補欄位與待確認清單。

### B. LLM 層

適合處理需要語意判斷、抽象映射與脈絡推斷的問題。

**LLM 必做項目**
- 語意重複偵測：不同名稱但同一概念的 entity / document / blindspot。
- 語意衝突偵測：不同文件或 protocol 的敘述互相矛盾。
- blindspot 推斷：根據結構與近期事件推斷應該存在但尚未被顯性化的缺口。
- stale impact inference：判斷某次變更是否真的改變知識，以及影響哪些 ontology 節點。
- task-to-ontology linkage：把未明確 linked 的 task 語意對回相關 entity。
- canonical naming：建議實體標準命名與 alias 整理。

**輸出形式**
- 候選 merge 建議。
- 候選 conflict 清單。
- 新 blindspot draft。
- 受影響 entity / document / protocol 清單。

### C. Human 層

適合處理組織承諾、責任歸屬與風險接受。

**Human 必做項目**
- confirm AI draft 是否生效。
- 決定重複 entity 是否合併。
- 決定衝突敘述哪一邊是正確現況。
- 接受或退回治理 task。
- 為高風險 blindspot 指派 owner 與期限。

**輸出形式**
- confirmed ontology。
- accepted / rejected task。
- 明確的 ownership 與補強決策。

---

## 監控指標與門檻

### 每日檢查

- 新增或更新的 documents 數量。
- 被標記 stale 的 entities/documents。
- confirm backlog 數量與最久未處理天數。
- 新 blindspots 數量。

**每日紅燈條件**
- 核心 product/module 出現 stale 但 48 小時內沒有治理動作。
- blindspot 新增但沒有 task。
- draft backlog 快速上升且 3 天內無 confirm。

### 每週檢查

- governance score 趨勢。
- orphan entity 比例。
- unlinked task 比例。
- blindspot -> task -> review/done 轉化率。
- 近期高頻變更區域是否已有 protocol 或 owner。

**每週紅燈條件**
- quality score < 70。
- 核心 entity 缺 protocol 或缺 relationship。
- 任一 active L2 缺少具體 `impacts`。
- 連續兩週 freshness score 下滑。

### 每月檢查

- 重複語意清理進度。
- 主要模組的 protocol 完整度。
- 高風險 blindspot 是否持續存在。
- task 完成是否有回寫 ontology。

**每月紅燈條件**
- 同一 blindspot 重複出現但未形成治理閉環。
- 核心模組治理延遲持續高於 14 天。

---

## Governance Score

建議把治理品質收斂成一個趨勢分數，用於 weekly review。

```text
Governance Score =
  Coverage 30%
+ Freshness 30%
+ Consistency 20%
+ Actionability 20%
```

### Coverage Score
- 核心 entity 中，具備 owner / relationship / protocol / impacts 或等價治理資訊的比例。

### Freshness Score
- 最近有實質變更的項目中，在 7 天內完成更新或確認的比例。

### Consistency Score
- 非 orphan、非重複、非衝突，且 L2 具備 impacts 的比例。

### Actionability Score
- L2 具備具體 impacts，且 blindspot 被轉為 task 並被推進到 review/done 的比例。

---

## L1 Product Governance Metrics

L1 代表 product 層。它不是另一套獨立骨架，而是把底下 L2 / L3 的治理狀態做 roll-up，讓管理者快速判斷「這個 product 是否健康、是否需要治理介入」。

### L1 的定位

1. L1 是 product 層的總覽視角。
2. L1 的健康度應該反映底下 L2 的完整度、變更速度與行動閉環。
3. L1 不取代 L2 的 impacts 規則，而是把 L2 的治理狀態彙總成 product 級別指標。
4. L1 適合做儀表板總覽與風險雷達，不適合拿來取代細粒度治理判斷。

### L1 指標維度

#### 1. Product Coverage

衡量一個 product 是否有足夠的治理支撐。

**核心指標**
- product 是否存在且為 active。
- product 是否有 owner 或明確責任人。
- 底下核心 L2 是否存在、是否有對應 relationship、owner、protocol 或確認責任。
- product 相關核心流程是否有 document / protocol entry。

#### 2. Product Freshness

衡量 product 是否跟得上近期變更。

**核心指標**
- 最近 7 天有變更的 product 相關內容，是否已同步更新對應 ontology entry。
- 最近 14 天有顯著變更的 product，是否已確認或標記 stale。
- product 變更到 ontology 更新的中位延遲。
- stale product 與 stale 下層內容的比例。

#### 3. Product Consistency

衡量 product 底下的治理結構是否自洽。

**核心指標**
- product 底下 orphan L2 / document / task 的比例。
- 核心 L2 是否缺 protocol、缺 relationship、缺 impacts。
- 是否存在重複語意或衝突語意。
- product 下層是否有明顯責任斷裂。

#### 4. Product Actionability

衡量 product 是否真的形成治理閉環。

**核心指標**
- product 底下 blindspot 是否有轉成 task。
- task 是否有進入 review / done。
- confirm backlog 是否可控。
- product 變更後是否有回寫 ontology 或標記 stale。
- product 的治理動作是否能形成持續追蹤的 closure。

### L1 Composite Score

建議 product 層的治理健康分數沿用與整體治理品質一致的結構：

```text
L1 Product Governance Score =
  Coverage 30%
+ Freshness 30%
+ Consistency 20%
+ Actionability 20%
```

### L1 健康門檻

可先沿用三色分級，供 Dashboard 與 weekly review 使用：

- 綠：7 日 confirm rate >= 80%，backlog < 10，且無連續 3 日退化。
- 黃：7 日 confirm rate 60%-79%，或 backlog 10-30，或有短期退化跡象。
- 紅：7 日 confirm rate < 60%，或 backlog > 30，或出現明顯事實錯誤 / 缺 impacts 的集中問題。

### L1 Dashboard 建議欄位

- Product 名稱
- L1 Product Governance Score
- 趨勢箭頭
- Coverage / Freshness / Consistency / Actionability 四項分數
- stale 數量
- 缺 impacts 的 L2 數量
- blindspot backlog
- confirm backlog
- 最近更新時間

### L1 與 L2 的關係

- L1 的分數應由底下 L2 / L3 狀態 roll-up 而來。
- L1 不應獨立於 L2 的 impacts 判準存在。
- L1 主要用於總覽與風險篩查，L2 才是主要治理邊界。

## 執行流程

### Daily Governance Loop

1. 收集事件：git、文件、task、confirm。
2. Rules 層先篩選出 stale、orphan、missing link、backlog。
3. 對新候選 L2 強制檢查是否至少有 1 條具體 `impacts`；沒有就退回重切或降級。
4. LLM 層只處理高語意密度案件：duplicate、conflict、blindspot、impact。
5. 產出待確認清單與治理 task。
6. Human confirm 後回寫 ontology，必要時標記 stale entity。

### Weekly Governance Review

1. 跑 `analyze(check_type="all")`。
2. 先看哪些 L2 缺 `impacts`，因為這類節點不算治理完成。
3. 看未通過項目是否集中在某一類模組。
4. 檢查高風險 blindspot 是否都有 owner、task、截止時間。
5. 清理本週的 duplicate/conflict 候選。
6. 更新 protocol 或 governance rule。

### Monthly Audit

1. 檢查 canonical naming 是否持續漂移。
2. 合併重複 entity / document。
3. 關閉已失效的 blindspot。
4. 回顧治理機制本身是否需要調整權重與門檻。

---

## ZenOS 現階段建議落地

### 立即可做

- 固定跑 `analyze(check_type="quality")` 與 `analyze(check_type="blindspot")`。
- 每週 review `search(collection="tasks")` 中與治理相關的 backlog / review / blocked。
- task 驗收時強制檢查是否需要 `mark_stale_entity_ids` 或新增 blindspot。
- 對核心模組建立 protocol 補齊清單。
- 把「L2 缺 impacts」直接視為治理缺陷，而不是可延後補充的欄位。

### Phase 1

- 建立 weekly governance dashboard。
- 建立 duplicate / conflict 候選池。
- 為 stale impact inference 建立標準輸入格式。

### Phase 2

- 將治理監控做成常駐 daemon。
- 將高風險告警自動轉 task。
- 將 confirm backlog 與 protocol regeneration 串成閉環。

---

## 成功標準

這份治理機制上線後，ZenOS 應該達到以下結果：

- 重要知識變更不再依賴人工記憶才被更新。
- ontology 的 draft 不會長期無人驗收。
- 沒有 impacts 的點不會停留在 L2，會被補齊、降級或合併掉。
- blindspot 會穩定轉成 task，而不是只停在分析層。
- LLM 被用在真正需要語意推斷的地方，而不是取代所有規則檢查。
- 每次治理 review 都能形成新的確認、修正或行動，而不是只有觀察。
