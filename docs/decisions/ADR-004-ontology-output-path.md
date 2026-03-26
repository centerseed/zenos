---
type: ADR
id: ADR-004-ontology-output-path
status: Draft
ontology_entity: action-layer
created: 2026-03-22
updated: 2026-03-26
---

# ADR-004：Ontology Output 路徑——從知識到行動

**日期**：2026-03-22
**狀態**：已識別（待設計）
**來源**：PM session，dogfooding 中發現的第二個核心產品問題

---

## 問題背景

ADR-003 解決了 ontology 的 **input 路徑**（文件變更 → ontology 更新）。
但 dogfooding 揭露了另一條完全缺失的路徑：**output 路徑**（ontology 洞察 → 驅動行動）。

### 實際碰到的場景

Barry 在 PM session 中發現多個需要 Architect 處理的問題（MCP tool description 設計原則、治理觸發架構），這些問題已經被捕獲進 ontology（ADR-003 文件 entry、3 個 blindspots）。但要讓 Architect 行動，Barry 必須：

1. 手動記得有哪些問題
2. 手動記得這些東西在哪個 ontology / 哪個 entry
3. 手動告訴 Architect 去哪裡找相關 context
4. 手動追蹤 Architect 有沒有做

**這跟 ADR-003 發現的「手動觸發 capture 違背核心價值」是同一類問題——把責任放在人身上。**

### 兩條路徑的對比

```
Input 路徑（ADR-003）：文件變更 → Governance Engine → ontology 更新
Output 路徑（本 ADR）：ontology 洞察 → ??? → 任務派發 + context 路由
```

Input 有設計了，Output 完全空白。

---

## 目前能力 vs 缺口

| 能力 | 狀態 | 說明 |
|------|------|------|
| 知識捕獲 | ✅ | `/zenos-capture` |
| 知識存儲 | ✅ | Firestore ontology |
| 知識檢索 | ✅ | MCP `search_ontology` |
| 盲點推斷 | ✅ | `run_blindspot_analysis` |
| 知識 → 任務派發 | ❌ | 不存在 |
| 任務帶 ontology 指針 | ❌ | 不存在 |
| 跨角色 context 路由 | ❌ | 不存在 |

---

## 分階段設計方向

### Level 0（現在可做，不需要基礎設施）

- Blindspot / 文件 entry 建立時，自動建議「這個洞察應該派給誰？建任務嗎？」
- 任務內嵌 ontology 指針（entity ID / document ID / blindspot ID）
- 角色收到任務時，一個指令就能拉到所有相關 context

### Level 1（Phase 0.5）

- Blindspot severity=red → 自動建 draft 任務
- 任務描述自動附帶相關 ontology context 摘要
- 角色切換時（PM → Architect），自動帶 ontology context（handoff 協議整合）

### Level 2（Phase 1+）

- Governance Engine 分析完變更後，不只更新 ontology，還判斷「這需要誰行動？」
- 自動路由規則：架構變更 → Architect、品質問題 → QA、行銷缺口 → PM
- 與 ADR-003 的 Governance Engine 共用，Output 路徑 = Engine 的下游

---

## 產品意義

這不是技術問題，是**產品核心價值問題**：

> 光有知識不夠，知識要能驅動行動。

ZenOS 如果只做到「幫你整理知識」，就跟 Notion + AI 沒有差別。
差異化在於：**ontology 洞察自動變成行動項目，推到對的人手上，附帶完整 context。**

這也直接影響客戶端的價值主張：
- 老闆不只看到全景圖和盲點，還能看到「AI 建議誰該做什麼」
- Agent 不只能查 ontology，還能收到 ontology 驅動的任務

---

## 交給 Architect 的問題

1. Level 0 的最小實作：capture 完自動建議任務，任務怎麼帶 ontology 指針？
2. 任務系統整合：Zentropy 的 task 能不能加 `ontology_refs` 欄位？
3. Handoff 協議整合：角色切換時自動附帶 ontology context 的機制
4. Level 1 的自動路由規則：blindspot severity → 角色 mapping 怎麼設計？

---

## 與其他決策的關係

- **ADR-003（治理觸發）**：互補。ADR-003 = input，ADR-004 = output，共用 Governance Engine
- **MCP tool descriptions 原則**：Output 路徑的任務也透過 MCP 派發，tool descriptions 品質同樣關鍵
- **漸進式信任**：Output 路徑一樣要 draft → confirm，不能自動執行未確認的任務
