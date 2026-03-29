---
type: ADR
id: ADR-010
status: Proposed
created: 2026-03-28
---

# ADR-010: Entity Entries — L2 從文件索引升級為知識容器

## 決策

新增 `entity_entries` 表，讓 L2 entity 能承載時間軸上的結構化知識條目（決策、限制、變更、洞察、脈絡），而不只是 summary + 指向外部文件的指標。

## 背景

### 問題

L2 entity 目前是空殼：一句 summary + 散落在五張表的指標（documents, relationships, blindspots, protocols, tasks）。要理解一個概念的完整脈絡，agent 或人必須 JOIN 五張表再自己拼湊。

更根本的問題：L2 summary 描述的「這個模組做什麼」，agent 讀 code 兩分鐘就能推導。Ontology 的真正價值在於 **code 裡沒有的知識**——為什麼選方案 A 不選 B、哪裡有已知限制、什麼時候做了什麼改變。這些知識目前沒有結構化的存放位置。

### 觸發

PM 在評估 ZenOS 五個核心願景時發現，現有資料結構無法承載：

1. **跨 agent 開發**：agent 切換後 context 消失，因為 L2 只有靜態 summary
2. **非同步對齊**：不知道概念的演化歷程，只能看到最新狀態
3. **PM↔工程師溝通**：決策脈絡沒有結構化記錄，每次都要重新問
4. **跨部門知識沉澱**：會議決定沒有自然的歸屬位置
5. **ERP 理解**：業務含義無處記錄

### 與 Palantir Ontology 的類比

Palantir 的每個 object type 有 properties（靜態屬性）和 time series（時間軸資料流）。ZenOS 的 L2 entity 有 summary + tags（靜態），但缺少時間軸層。Entity entries 填補這個空缺——不是從感測器自動流入的結構化資料，而是從人類/agent 工作中沉澱的結構化知識。

## 方案

### 資料結構

```sql
CREATE TABLE zenos.entity_entries (
  id              text        PRIMARY KEY,
  partner_id      text        NOT NULL,
  entity_id       text        NOT NULL,
  type            text        NOT NULL,
  content         text        NOT NULL,
  context         text,
  author          text,
  department      text,
  source_task_id  text,
  status          text        NOT NULL DEFAULT 'active',
  superseded_by   text,
  archive_reason  text,
  created_at      timestamptz NOT NULL DEFAULT now(),

  UNIQUE (partner_id, id),
  FOREIGN KEY (partner_id, entity_id) REFERENCES zenos.entities(partner_id, id),
  FOREIGN KEY (partner_id, superseded_by) REFERENCES zenos.entity_entries(partner_id, id),
  CONSTRAINT chk_entry_type CHECK (type IN ('decision', 'insight', 'limitation', 'change', 'context')),
  CONSTRAINT chk_entry_department_length CHECK (department IS NULL OR char_length(department) <= 50),
  CONSTRAINT chk_entry_status CHECK (status IN ('active', 'superseded', 'archived')),
  CONSTRAINT chk_entry_content_length CHECK (char_length(content) BETWEEN 1 AND 200),
  CONSTRAINT chk_entry_context_length CHECK (context IS NULL OR char_length(context) <= 200),
  CONSTRAINT chk_entry_superseded_consistency CHECK (
    (status != 'superseded') OR (superseded_by IS NOT NULL)
  ),
  CONSTRAINT chk_entry_archive_reason CHECK (
    archive_reason IS NULL OR archive_reason IN ('merged', 'manual')
  ),
  CONSTRAINT chk_entry_archived_has_reason CHECK (
    (status != 'archived') OR (archive_reason IS NOT NULL)
  )
);

CREATE INDEX idx_entries_partner_entity ON zenos.entity_entries(partner_id, entity_id);
CREATE INDEX idx_entries_partner_entity_type ON zenos.entity_entries(partner_id, entity_id, type);
CREATE INDEX idx_entries_partner_entity_active ON zenos.entity_entries(partner_id, entity_id) WHERE status = 'active';
CREATE INDEX idx_entries_partner_created ON zenos.entity_entries(partner_id, created_at DESC);
```

### 治理規則

#### Server 強制（硬性底線）

| 規則 | 約束 | 設計理由 |
|------|------|---------|
| content 上限 200 字元 | `char_length(content) <= 200` | 100 中文字足以表達一個知識點，強制精簡避免 entry 退化為文件 |
| content 不可為空 | `char_length(content) >= 1` | 空 entry 無意義 |
| context 上限 200 字元 | `char_length(context) <= 200` | 脈絡也要精簡，詳細背景屬於 document 或 sources |
| context 可選 | `NULL allowed` | 降低記錄成本，有些知識點不需要額外解釋 |
| status = superseded 時必填 superseded_by | CHECK constraint | 確保 supersede 鏈可追蹤 |
| 一條 entry 一個 entity | FK to entities，無 join table | L2 語意切割明確，同一件事對不同 L2 一定有不同角度 |
| 沒有 confirmed_by_user | — | entry 是低成本記錄，不走 draft→confirmed 流程 |
| 每個 L2 上限 20 條 active entries | Application 層檢查（**per department**） | 超過代表概念太大應拆分，或需要歸納壓縮 |
| archived 必須帶 archive_reason | `merged` / `manual` | 確保歸檔原因可追蹤 |
| department 來自用戶 profile，不由 agent 判斷 | MCP server 從 partner context 注入 | 防止 agent 填錯或偽造部門；null = 通用知識，所有部門可見 |
| 壓縮只在同 department 內發生 | Application 層 + consolidation prompt | 防止跨部門合併導致少數部門知識被稀釋 |

#### Entry 生命週期

```
active
  ├─ 被新知識明確取代 → superseded (superseded_by = new_entry_id)
  ├─ 歸納合併        → archived (archive_reason = 'merged')
  └─ 用戶手動清理    → archived (archive_reason = 'manual')
```

**歸納機制（Consolidation）**：

當某個 L2 的 active entries 達到 20 條上限時，`analyze` 偵測到飽和：

1. LLM 分析哪些 entries 可合併（同主題多條 → 一條更完整的）
2. 產出歸納 proposal，**必須由人確認**後才執行
3. 被合併的舊 entries → `archived (archive_reason = 'merged')`，新 entry → `active`
4. 歸納後 active count 必須 < 20

**不丟失原則**：archived entries 永遠留在 DB，可用 `search(collection="entries", status="archived")` 找回。

**自然選擇效應**：常被提到的概念不斷有新 entry 進來，歸納時反覆出現的知識自然留在合併後的 entry 裡，冷門知識逐漸壓進 archived。不需要冷卻計時器或使用頻率追蹤。

**設計決策：不做自動 archive**

曾考慮根據「使用頻率」自動 archive 長期未被引用的 entries。否決原因：
- Agent 每次讀 L2 會撈回所有 active entries，無法區分「真的用到」vs「只是讀到」
- 人也無法判斷哪些 entries 被最常使用
- 唯一可靠的淘汰機制是「空間滿了 + 人為判斷」

#### Internal 治理 API（server 端自動偵測）

| 偵測項目 | 觸發條件 | 建議動作 |
|---------|---------|---------|
| 飽和偵測 | 同一 entity 下 active entries >= 20 | 觸發歸納 proposal，人確認後合併 |
| 重複偵測 | 同一 entity 下兩條 entry content 相似度 > 閾值 | 建議合併或 archive 較舊的 |
| 矛盾偵測 | 同一 entity 下 decision A 和 decision B 描述相反 | 建議將舊 decision 標記 superseded |
| summary 漂移 | entries 描述的方向跟 L2 summary 不一致 | 提示 review summary |
| 拆分信號 | 同一 entity 的 entries 明顯分成不相關的兩群 | 建議拆分 L2 |

#### Skill 引導（agent 端判斷）

- 這條知識是不是 code 裡已經有的？→ 有就不記
- 這是 entry 還是 blindspot？→ 事實記錄用 entry，待處理問題用 blindspot
- 100 字能不能講清楚？→ 不能就拆成多條，或者代表粒度太大

### Entry Type 定義

| type | 語意 | 範例 |
|------|------|------|
| `decision` | 做了一個影響概念的決定 | 「選 VDOT 不選心率區間，因為 Garmin 心率前幾分鐘不穩」 |
| `insight` | 發現了重要認知 | 「小模型+全局數據 > 大模型+局部視野」 |
| `limitation` | 發現了限制或約束 | 「LLM JSON 格式問題，需要 retry + fallback parser」 |
| `change` | 概念的定義或實作變了 | 「recovery week 從三級改兩級，跟 weekly plan v2 對齊」 |
| `context` | 補充背景脈絡 | 「這個模組最初是為了解決 X 問題才建的」 |

### 產出方式

Entry 是工作的副產品，不是額外的文件撰寫：

| 觸發情境 | 產出方式 | entry type |
|---------|---------|-----------|
| `/zenos-capture` 識別到決策 | skill 半自動萃取 | decision / insight |
| Task 完成 result 包含學習 | 從 result 萃取 | limitation / change |
| Agent 踩坑解決 | 提示「要不要記一條」 | limitation |
| 概念定義或實作變了 | 手動或 capture 觸發 | change |

### 與現有結構的分工

| 結構 | 定位 | 生命週期 |
|------|------|---------|
| **Entry** | 事實記錄（永久） | 只增不刪，可壓縮/archive |
| **Blindspot** | 待處理問題 | open → acknowledged → resolved |
| **Document** | 外部文件指標 | current → stale → archived |
| **Sources** | URI 連結 | 靜態列表 |
| **Protocol** | 操作指南 | 靜態，可版本化 |

### 搜尋整合

`search` tool 需要擴展為可搜尋 entries：
- `search(query="VDOT")` 應能搜到 entity entries 的 content
- 搜尋結果回傳 entry 所屬的 entity，提供完整脈絡

### 治理（Internal API）

Entry 治理是 server 端 Internal 治理的核心場景：
- **壓縮**：同一 L2 下多條相似 entry → 合併
- **矛盾偵測**：entry A 和 entry B 描述衝突 → 標記
- **summary 漂移**：entries 方向跟 summary 不一致 → 提示 review
- **拆分信號**：entries 分成兩群不相關主題 → 建議拆分 L2
- **膨脹控制**：entries 過多且無法壓縮 → 建議拆分 L2 或 archive 舊 entries

## 考慮過的替代方案

### 方案 A：擴展 details_json

把 entries 放在 entity 的 `details_json` JSONB 欄位裡。

**否決原因**：JSONB array 無法高效查詢、無法建索引、無法做 per-entry 的 foreign key（如 source_task_id）。

### 方案 B：用 blindspots 和 task results 替代

不新增結構，把決策記在 blindspot 裡、把脈絡記在 task result 裡。

**否決原因**：語意不對。Blindspot 有生命週期（open→resolved），決策記錄不應該被「resolved」。Task result 綁定在 task 生命週期裡，概念層的知識不應該只能透過 task 存取。

### 方案 C：完整的 changelog 表（追蹤所有欄位變更）

記錄 entity 每個欄位的每次變更歷史。

**否決原因**：解決的是不同的問題。Changelog 追蹤「什麼被改了」（diff），entry 記錄「為什麼這樣做」（context）。兩者互補但不能互相替代。Changelog 可以未來再加，不影響 entry 的設計。

## 影響

- **SPEC-l2-entity-redefinition**：已更新，加入 Entity Entries 章節
- **SPEC-ontology-architecture**：已更新，加入 Entity Entries 資料結構說明
- **MCP tools**：`write` 和 `search` 需要支援 entries collection
- **Capture skill**：需要在知識分析時識別 entry 候選
- **Migration**：需要新增 entity_entries 表
- **Dashboard**：entity 詳情面板需要展示 entries 時間軸

## 依賴與降級行為

### User Profile 依賴

`department` 欄位的值來源是 user profile 的部門欄位（尚未實作）。降級行為：

- User profile 尚未有 `department` 欄位 → MCP server join 不到值 → `department = null`
- `department = null` 的 entry 對所有部門可見，行為與原始設計相同
- 因此 User Profile 功能上線前，系統完全向下相容，不需要 migration

### 完整啟用條件

1. User profile 新增 `department` 欄位
2. MCP server 在 entry create 時從 partner context 自動注入 `department`
3. Setup skill 確認 local agent context 帶有用戶部門資訊
4. 壓縮演算法（`consolidate_entries`）依 department 分組後各自壓縮

## 相關文件

- `SPEC-l2-entity-redefinition`（L2 核心價值重定義）
- `SPEC-ontology-architecture`（Entity 分層模型）
- `SPEC-governance-feedback-loop`（Entry 治理與品質回饋）
- `ADR-007-entity-architecture`（Entity 三層模型）
