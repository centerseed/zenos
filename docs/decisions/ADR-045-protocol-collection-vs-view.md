---
doc_id: ADR-045-protocol-collection-vs-view
title: 決策紀錄：Protocol 收斂為 derived collection，不是 view
type: DECISION
ontology_entity: Knowledge Layer
status: Accepted
version: "1.0"
date: 2026-04-22
accepted_at: 2026-04-23
supersedes: null
---

# ADR-045: Protocol 是 derived collection，不是 view

## Context

ZenOS 文件層長期描述 Context Protocol 是「ontology 的 view」：

- `SPEC-ontology-architecture` 第 250 行：「Context Protocol 不是 ontology 本身，它是 ontology 的 view。就像 SQL 的 view，底層資料變了 view 就自動更新。」
- `docs/reference/REF-ontology-current-state.md:33`：「Context Protocol | ZenOS 核心產出物 | ✅ 模板驗證中 | Ontology 的 view — 從 ontology 自動生成，人微調確認」

但 code 把 Protocol 實作為**獨立持久化 collection**：

- `src/zenos/domain/knowledge/repositories.py:80` `ProtocolRepository` 暴露 `upsert / list_unconfirmed / list_all(confirmed_only=...)`
- `src/zenos/domain/knowledge/models.py:127` `Protocol` dataclass 帶 `confirmed_by_user`、`version`、`generated_at`、`updated_at` 等 lifecycle 欄位
- `migrations/20260325_0001_sql_cutover_init.sql` 建立 `protocols` table，每 entity 一個 row（`uq_protocols_partner_entity unique`）
- 4 個 production caller 把 Protocol 當一級 collection：
  1. `interface/mcp/search.py:589/591`：MCP search 暴露 `list_all(confirmed_only=...)`
  2. `interface/dashboard_api.py:2998`：Dashboard 注入 `SqlProtocolRepository`
  3. `application/knowledge/governance_service.py:534/574`：quality check 拿 `protocol.confirmed_by_user` 算 KPI
  4. `application/knowledge/ontology_service.py:3167`：`upsert_protocol` 是公開 service method
- `src/zenos/domain/governance.py:1115` `run_quality_check` 把 `unconfirmed protocols` 計入 quality 分母

**矛盾的本質：** 一個真正的 view 不會有 `confirmed_by_user`——view 沒有獨立於底層資料的存在，沒有「人有沒有確認過」這個狀態。Protocol 既然有「人確認後凍結」的 lifecycle，它就不再是 view，而是從 ontology 推導出的**衍生物**（derived artifact）。

這份 ADR 收束 Protocol 的定位歧義，避免後續的設計、文件、與實作繼續錯位。

## Decision Drivers

- 對外契約穩定優先：MCP `list_all(confirmed_only=...)` 與 dashboard caller 是已上線契約
- Quality KPI 演算法已經依賴 `protocol.confirmed_by_user`，不能無痛抽掉
- Protocol 有獨立 lifecycle（生成 → 待確認 → 確認 → 凍結 → 後續更新），這跟 view 的「即時 reflect 底層」語意不相容
- 文件與實作必須對齊，避免新加入者繼續被「Protocol 是 view」誤導

## Decision

### D1. 承認 Protocol 是 derived collection，不再描述為 view

`Protocol` 是從 entity / entries / relationships 推導生成、但有獨立 lifecycle 與人確認狀態的一級 collection。它**不是** view，因為：

1. View 的定義是「即時反映底層資料」——Protocol 有 `confirmed_by_user` 凍結機制，不即時反映
2. View 沒有 generation timestamp 與獨立 lifecycle——Protocol 有 `generated_at`、`updated_at`、版本演化
3. View 不應暴露 `upsert` mutation——Protocol 在 `ProtocolRepository` 是一級 mutation API

### D2. 保留 `protocols` table、`Protocol` dataclass、`ProtocolRepository`

不廢表、不廢 dataclass、不廢 repository。理由：

- 4 個 production caller 已綁定，廢表的下游 spec amendment 與 caller refactor 成本顯著高於文件 amendment
- `confirmed_by_user` 已是 quality KPI 的一部分，廢掉等於同步重設 KPI 演算法
- Dashboard 與 MCP 對外契約已穩定，使用者熟悉「Protocol 待確認」這個概念

### D3. `Protocol.version` 不在本 ADR 拍板，先做語意調查

初版 draft 把 `version` 判為 dead column，事後 grep 證實這是錯判。`version` 實際被以下路徑使用：

- `src/zenos/domain/search.py:82`：`_collect_searchable_text_protocol(protocol)` 把 version 序列化進 search index
- `src/zenos/application/knowledge/ontology_service.py:3157`：`upsert_protocol` 接 `data.get("version", "1.0")` 並寫入
- `src/zenos/infrastructure/knowledge/sql_protocol_repo.py:20`、`firestore_repo.py:296`：SQL 與 Firestore repo 都序列化 version

但這些 use site 全部都是「序列化／寫入／放進 search text」，**沒有任何邏輯分支真的依 version 值做不同行為**（沒看到 `if protocol.version == ...` 之類）。所以 version 的真實狀態介於「dead」與「live」之間：欄位有資料流，但沒有業務語意。

本 ADR 不在這份決策裡處理 version，避免錯誤刪除。**先做一份輕量調查**，回答以下三個問題：

1. 線上 `protocols.version` 是否有 row 的值不是 `"1.0"` 預設值？
2. 是否有任何 dashboard / MCP caller 依 version 值做顯示或過濾？
3. 是否有 spec / ADR 預期 Protocol 隨 entity 演化要產生 v1.1 / v2.0 的版本概念？

調查結束後，再開一份輕量 follow-up（ADR 或 task）決定保留／升格為真實版本欄位／刪除。

## Open Investigation
- Protocol.version 語意調查：見 D3，列為本 ADR 通過後的 follow-up 工作

### D4. SPEC / REF 文件 amendment（原 D4，未變）

更新以下文件，移除「view」描述：

- `SPEC-ontology-architecture` 第 250 行，改為描述 Protocol 是「derived collection — 從 ontology 自動生成、有獨立 lifecycle、需人確認」
- `docs/reference/REF-ontology-current-state.md:33` Context Protocol row 的「說明」欄位
- 任何其他描述 Protocol 為 view 的文件（搜尋 `"Protocol.*view"` 全文）

## Alternatives

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| **A. 收斂到 view（廢 table）** | 文件最純粹，「ontology = graph + view」的 mental model 維持簡潔 | 4 個 caller 全要改、quality KPI 重設計、MCP `list_all(confirmed_only=...)` 介面要廢、Dashboard caller 失去「待確認 protocol」概念。下游成本至少 1-2 週 + 多份 spec amendment | 實作已經走太遠，硬拉回 view 不成比例 |
| **B. 收斂到 collection（本 ADR 採用）** | 文件對齊實作、零 caller 改動、KPI 邏輯維持、刪 version 死欄位順帶清理 | 「ontology = graph + 純 view」這個簡潔 mental model 變得不純粹，要承認衍生物也是 ontology 的一部分 | （採用） |
| **C. 維持模糊（不收斂）** | 零工 | 新加入者持續被誤導；後續每次討論 Protocol 都要重新解釋為什麼文件說 view 但 code 說 collection；文件信譽下降 | 治理債務只會越積越大 |

## Consequences

### Positive
- 文件與實作對齊，新加入者讀 SPEC 不再被「view」描述誤導
- 刪掉 `version` 死欄位，schema 更精簡
- 為後續設計討論（例：是否再多一層 derived view 在 Protocol 之上）留下乾淨基礎

### Negative
- 「Knowledge Layer = entities + relationships + entries + derived collections」需要正式承認，meta-model 不再只是 graph
- 需要回頭審視其他「描述為 view 但實作為 collection」的物件（例如未來可能的 dashboard summary、bundle preview），確保命名一致

### Risks
- 若 D3 的 `version` 刪除沒做完整 grep，可能有遺漏的 caller。需要 implementation 階段加 grep gate
- 若 D4 的文件 amendment 沒做齊，可能還會有「view」描述殘留。需要交付前做 grep `"Protocol.*view"` 全文搜尋

## Implementation Notes

實作切片：

1. SPEC amendment：`SPEC-ontology-architecture` line 250 段落改寫，把「view」改為「derived collection」並解釋 lifecycle
2. REF amendment：`REF-ontology-current-state.md:33` Context Protocol row 的「說明」欄位
3. 全文 grep gate：交付前確認 `docs/` 下沒有殘留的「Protocol.*view」描述

## Follow-up（ADR 通過同輪必建）

ADR 進入 `Accepted` 的同一個 session，Architect 必須立即用 `mcp__zenos__task` 建立 1 張 follow-up task，**不可推到實作時「順手做」**——避免文件拍板但追蹤未落地。

Task 模板：

- **Title**：「釐清 Protocol.version 的語意」
- **Goal**：根據 ADR-045 D3 三個調查問題，回答 `protocols.version` 的真實狀態
- **Acceptance Criteria**：
  1. 線上 query：列出 `protocols.version` 各 distinct 值與 row 數，產出統計報告
  2. Caller 盤點：列出所有讀寫 `version` 的 caller（dashboard / MCP / search index / repo），逐一說明該 caller 是否依值做行為分支
  3. Spec / ADR 搜尋：確認是否有任何文件預期 Protocol 隨 entity 演化要產生 v1.1 / v2.0
  4. 拍板結論：保留為 user-facing revision / 升格為 internal schema version（綁 schema migration） / 或直接刪除
  5. 同步修正：依拍板結論一次處理 `_collect_searchable_text_protocol` (search.py:82)、`upsert_protocol` contract (ontology_service.py:3157)、SQL/Firestore repo serialization、Protocol dataclass 欄位
- **Linked entities**：ADR-045

## Rollout

單階段：D1+D2+D3+D4 一起交付。沒有 phased rollout 必要——文件 amendment 與 dead column 移除互不阻塞。

## Follow-up

- 後續若決定真的需要一層「即時 view」（例如 dashboard widget 要動態組裝），那一層的命名應避免再叫 Protocol，避免歧義復發。建議命名為 `EntityViewProjection` 或類似明確標示「即時組裝」的詞。
- ADR-046（Document/Entity boundary）若決定收斂方向也牽動 Protocol（Protocol 內容引用 entity / document），需確認兩份 ADR 不互相矛盾。
