---
name: Ontology Output 路徑缺口
description: dogfooding 發現 ontology 只有 input（capture）沒有 output（知識→任務派發），這是產品核心價值問題
type: project
---

ADR-004 記錄了 ZenOS 的第二個核心產品缺口：ontology 的 output 路徑。

**事實**：ADR-003 設計了 input 路徑（文件變更→ontology 更新），但 output 路徑（ontology 洞察→任務派發+context 路由）完全不存在。Barry dogfooding 時發現要手動記得哪些問題在哪個 ontology entry，再手動告訴 Architect 去找。

**Why:** 光有知識不夠，知識要能驅動行動。這決定了 ZenOS 跟 "Notion + AI" 的差異化——不只整理知識，還能把洞察推到對的人手上。

**How to apply:** 所有 ontology 相關設計都要考慮 output 路徑。Level 0（capture 時建議建任務+帶 ontology 指針）可以馬上做，不需要基礎設施。ADR-004 在 `docs/decisions/ADR-004-ontology-output-path.md`。
