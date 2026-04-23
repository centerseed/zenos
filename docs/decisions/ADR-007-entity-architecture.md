---
type: ADR
id: ADR-007-entity-architecture
status: Approved
ontology_entity: TBD
created: 2026-03-23
updated: 2026-04-23
superseded_sections:
  - "L1 單一 type 定義"（2026-04-23 由 ADR-047 改為 level-based 判定；type 降為 UI label）
---

# ADR-007: Entity 架構決策

> 從 `docs/spec.md` Part 7.2 搬出。
> **2026-04-23 update：** L1 的「product 單一 type」定義已由 ADR-047 supersede。
> 實際判定走 `level == 1 AND parent_id IS NULL`；type（product/company/person/…）為 UI 識別 label，不再作為業務邏輯的 gate。


### Ontology 就是 Entity 的總和

```
Firestore
├── entities/          ← 所有知識節點（product, L2 governance concepts, document, goal, role, project）
├── relationships/     ← 節點之間的連線
├── blindspots/        ← AI 發現的知識缺口
├── tasks/             ← 行動層（不是 entity，透過 linkedEntities 連到 ontology）
└── protocols/         ← Context Protocol（ontology 的 view）
```

### Entity 分層

```
第一層（共享根）  level=1 任何 type   ← 預設 label=product；CRM 擴充含 company/person/deal
                                        判定走 level，不走 type（ADR-047）
第二層（治理概念）module + governance concepts
                  ← L1 底下的長期共識概念，可是業務模組也可是治理節點
第三層（應用）    document         ← 高價值文件的語意代理
                  goal             ← 公司或產品的目標
                  role             ← 職能角色
                  project          ← Phase 1 才加，有始有終的工作容器
```

第一、二層是每間公司的基礎建設，30 分鐘對話就能建立。第三層按需生長。

> **L1 的本質（ADR-047）：** L1 是「共享邊界」（collaboration root）——可以整棵子樹分享給別的用戶的底層節點。
> 所有 L1 entity 一律透過 `product_id` 當 API 語彙，無論 type 是什麼；UI 可用 type 決定 icon / 分類顯示，但不過濾。

### Entity 的邊界

**三個判斷標準：**

1. **跨專案/跨時間存活？** → 存活 = entity，做完就結束 = task
2. **有 What/Why/How/Who 可以描述？** → 有 = entity，沒有 = 不是 entity
3. **能成為其他知識的錨點？** → 能 = entity，不能 = entity.sources 就好

**最精簡規則：如果這個東西消失了，AI agent 回答問題時會少一塊重要 context → entity。不會 → 不是 entity。**

**容易搞混的邊界：**

| 是 entity | 不是 entity |
|-----------|------------|
| 「Dashboard v1 規格書」(document) — 有自己的 summary/tags，被多個 module 引用 | 「meeting-notes-0323.md」 — 只是某個 entity 的 sources 參考 |
| 「Dashboard v1 重新設計」(project) — 有多個任務，持續數週 | 「實作 GraphCanvas 元件」 — 單一可交付 → task |
| 「讓跑者安全進步」(goal) — 跨季度、影響多個 module 的方向 | 「下週修完 ACWR bug」 — 短期行動 → task |

### Task 不是 Entity

Task 有自己的 collection，跟 entity schema 完全不同：

| | Entity | Task |
|---|---|---|
| 核心屬性 | name, summary, tags{what,why,how,who} | title, assignee, due_date, acceptance_criteria |
| 生命週期 | active → paused → archived | backlog → todo → in_progress → review → done |
| 在知識地圖上 | 是（節點） | 否（在詳情面板裡列出） |
| 對 AI 的價值 | 「公司有什麼知識」 | 「現在在做什麼行動」 |

Task 透過 `linkedEntities` 連到 entity，是 ontology 的**消費者**，不是 ontology 的一部分。

### Entity 與 Project 分離

**Project 是 entity(type="project")，但跟 product/module 的性質不同。**

Entity(product/module) = 長期知識（跨專案存活）
Entity(project) = 短期工作容器（有始有終）

Project archive 時，底下連結的 product/module entity 繼續活著。知識不跟著專案死。

- **Phase 0**：不建 project entity。Product entity 加 `owner` 欄位，直接當專案入口（小公司夠用）
- **Phase 1**：當有客戶需要「一個產品多條工作線」時，加 project entity

### Entity 生命週期

| 狀態 | 意義 |
|------|------|
| `active` | 現在在用 |
| `paused` | 暫停但可能回來 |
| `archived` | 收掉了，但知識保留，AI 可查歷史 |

### Entity 用語規範

Entity 是技術術語，對外永遠不出現。

| 場景 | 怎麼稱呼 |
|------|---------|
| 知識地圖 UI | **節點**（或直接顯示 type：產品/模組/文件/目標） |
| 行銷 / 老闆對話 | 不用統稱。說「產品」「模組」「文件」具體名字 |
| 導入對話 | 「AI 幫你畫出公司的知識地圖，每個點就是公司的一個組成部分」 |
| 技術文件 / 開發 | entity |

**導入時的關鍵展示策略：** 知識地圖直接展示 entity 關係圖，給客戶一個全新的視角看待公司資料。如果把 entity 包裝成熟悉的「專案」「任務」，就跟 Jira/Trello 沒有差異。ZenOS 的差異化就在於讓客戶看到「原來我的公司知識長這樣」——這個 wow moment 是任何 kanban 工具做不到的。

詳見 ADR-006。

---

