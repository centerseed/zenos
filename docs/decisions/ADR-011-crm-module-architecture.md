---
type: ADR
id: ADR-011
status: Draft
ontology_entity: crm-module-architecture
created: 2026-03-28
updated: 2026-03-28
---

# ADR-011: CRM 模組架構——獨立 Schema + ZenOS L1 橋接

## 背景

SPEC-crm-core 要求在 ZenOS 平台上建立 CRM 核心模組。需要決策三件事：

1. CRM 資料應存在哪個 PostgreSQL schema？
2. 商機（Deal）是否需要橋接為 ZenOS L1 entity？
3. 重大商機狀態變更是否觸發 ZenOS governance 三問 pipeline？

## 決策

### 決策 1：CRM 資料存放在獨立 `crm` schema

採用獨立的 PostgreSQL schema `crm`，cross-schema 外鍵引用 `zenos.partners`。

### 決策 2：商機不橋接 ZenOS L1 entity，只有公司和聯絡人橋接

僅 `crm.companies`（type: company）和 `crm.contacts`（type: person）橋接為 ZenOS L1 entity。Deal 是銷售管道的短暫狀態資料，不是穩定的組織知識概念。

同時，`zenos.entities` 的 type check constraint 需擴充，加入 `company` 和 `person` 兩個合法類型。

### 決策 3：Phase 0 不觸發 governance pipeline

商機狀態變更不主動觸發 governance 三問。理由：CRM 橋接的公司/聯絡人 entity 已在知識圖譜中，governance 在 entity 層自然會覆蓋。Deal 的 lifecycle 觸發點留待 Phase 1 根據實際使用模式設計。

## 考慮過的替代方案

| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|
| CRM 資料混入 `zenos` schema | 少一個 schema，查詢不需 cross-schema | 污染核心 ontology 表空間；未來切割困難 | 不選 |
| 商機橋接為 ZenOS entity | 知識地圖能看到商機節點 | Deal 狀態變動頻繁，會產生大量 entity mutation；且 Deal 不是「公司知識」而是「銷售事件」 | 不選（P2 再評估） |
| 商機橋接為 ZenOS Task | 語意更接近（可追蹤進度） | Task 是 action layer，不是 entity layer；Deal 有獨特的漏斗欄位無法對應 Task schema | 不選 |
| 進入「導入中」觸發 governance | 驗證 ontology output path | 增加複雜度；且 governance AI 評估的對象是 entity，不是 deal；Phase 0 先求穩定 | Phase 1 再評估 |

## 後果

1. **schema 隔離**：CRM 資料可獨立維護、備份、遷移，不影響核心 ontology
2. **entity 擴充**：entities 表新增 `company` 和 `person` type，影響 domain model 和 DB constraint
3. **知識地圖整合**：客戶公司和聯絡人天然出現在知識圖譜，可進行跨模組關聯查詢
4. **治理延後**：Deal lifecycle → governance 連結留待 Phase 1，需補 ADR
