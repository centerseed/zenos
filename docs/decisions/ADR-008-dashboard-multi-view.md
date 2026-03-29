---
type: ADR
id: ADR-008-dashboard-multi-view
status: Approved
ontology_entity: TBD
created: 2026-03-23
updated: 2026-03-27
---

# ADR-008: Dashboard 多 View 架構決策

> 從 `docs/spec.md` Part 7.3 搬出。


### 核心概念

**Dashboard 的每個分頁都是同一份 ontology 的不同 view。每個 view 不只是投影（讀），也是編輯入口（寫）。**

### 分頁設計

| 分頁 | Ontology 怎麼投影 | 給誰 |
|------|------------------|------|
| 專案 | Product entity 為中心，底下模組/任務/owner | 老闆/PM 日常用 |
| 知識地圖 | Entity 關係圖，跨專案連結 | 探索/demo 用 |
| 任務 | Tasks linked to entities，kanban/pulse | 執行者追蹤進度 |
| （未來）團隊 | Who/Owner 為中心 | 看誰負責什麼 |
| （未來）文件 | Documents linked to entities | Storage map |

### Dashboard 用語規範

UI 不出現 entity / ontology。

| 技術概念 | UI 顯示 |
|---------|--------|
| Product entity | 專案 |
| Module entity | 模組 |
| Relationship | 關聯 |
| Knowledge Graph view | 知識地圖 |
| Blindspot | AI 發現 |
| confirmedByUser | 已確認 / 草稿 |

### 知識地圖（三欄佈局）

Palantir Foundry 啟發。左側產品選擇 + 中央 force-directed 關係圖 + 右側詳情面板。

詳見 `docs/archive/specs/deferred-2026-03/SPEC-dashboard-v1.md`（目前為 deferred spec）。

---

