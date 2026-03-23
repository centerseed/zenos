# ADR-006：Entity 與 Project 分離

**日期**：2026-03-23
**狀態**：已決定

## 決定了什麼

Project 不是 Entity，是 Entity 之上的工作容器。Ontology 層和 Project 層分離。

## 背景

在設計 Dashboard 的過程中，討論了 entity 的本質問題：

- Entity 是公司知識的**語意代理**——長期存在，跨專案存活
- Project 是有目的的**工作活動**——有始有終，完成就 archive
- 兩者的核心屬性完全不同（entity 需要 what/why/how/who，project 需要 owner/deadline/members/status）
- 如果把 project 塞進 entity type，schema 會變髒（entity 需要 deadline 嗎？有些要有些不要）

同時考慮了 SMB 導入門檻：小公司不需要 project 這層額外結構。

## 決定的架構

```
Project 層（按需）     → 有 owner/deadline/members/status
  ↕ linkedEntities       透過 linkedEntities 連到 ontology
Ontology 層（核心）    → entity + relationship + tags
  ↕ 治理規則
治理引擎              → similarity check / blindspot / staleness
```

### 分階段

- **Phase 0**：沒有 projects collection。Product entity 加 `owner` 欄位，直接當專案入口。小公司夠用。
- **Phase 1**：當有客戶需要「一個產品多條工作線」時，加 `projects` collection。

### Entity 生命週期

| 狀態 | 意義 |
|------|------|
| `active` | 現在在用 |
| `paused` | 暫停但可能回來 |
| `archived` | 收掉了，但知識保留 |

- Project archive 時 entity 繼續活著，知識不跟著專案死
- Dashboard 預設只顯示 active，有篩選器可看歷史

## 為什麼這樣決定

1. **Ontology 治理規則保持簡單**——entity 的 CRUD 觸發、四維標籤、confirmedByUser 不需要考慮 project 特有的欄位
2. **不同客戶可以有不同的 project 結構**——有的用 scrum，有的用 kanban，ontology 層不受影響
3. **知識不因專案結束而消失**——entity 是長期資產，project 是短期活動
4. **小公司不需要多一層**——Phase 0 不建 projects collection，漸進式導入

## 放棄的選項

- **Option A：Project 作為 entity type**——schema 會變髒，entity 要 deadline/members 等 nullable 欄位。entity 和 project 生命週期不同，混在一起會造成治理規則複雜化。
- **Option B：不分離，永遠用 product entity 當專案**——無法處理「一個產品多條工作線」的場景。

## 影響

- Entity schema 需要加 `owner` 欄位（Phase 0 最小改動）
- Dashboard 在「專案 view」中以 product entity 為頂層，未來加 project 時用 projects collection
- Ontology 治理引擎不需要改動
- MCP 介面可能需要新增 project 相關的 tools（Phase 1）
