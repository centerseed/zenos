# L3 文件治理規則 v1.0（含完整範例）

## 文件的定位
L3 document entity 是正式文件的語意代理——metadata 在 ZenOS，實際內容在外部。
文件不是 L2（文件是 L2 概念的具體體現），不是task（文件沒有 owner 和 AC）。

## 各文件類型完整範例 Frontmatter

SPEC 範例：
```yaml
---
doc_id: SPEC-governance-framework
title: 功能規格：治理框架
type: SPEC
ontology_entity: 知識治理框架
status: approved
version: "1.0"
date: 2026-02-15
supersedes: null
---
```

ADR 範例：
```yaml
---
doc_id: ADR-007-entity-architecture
title: 架構決策：Entity 三層模型
type: ADR
ontology_entity: 知識節點架構
status: approved
version: "1.0"
date: 2026-01-20
supersedes: ADR-003-entity-flat-model
---
```

TD 範例：
```yaml
---
doc_id: TD-three-layer-architecture
title: 技術設計：三層架構實作
type: TD
ontology_entity: 服務分層架構
status: under_review
version: "0.3"
date: 2026-03-01
supersedes: null
---
```

## Supersede 操作步驟（完整流程）

情境：ADR-007 取代了 ADR-003

Step 1：在文件系統建立 ADR-007，frontmatter 加 supersedes: ADR-003
Step 2：在 ZenOS 建 document entity：
```
write(
  collection="documents",
  data={
    "doc_id": "ADR-007-entity-architecture",
    "title": "架構決策：Entity 三層模型",
    "type": "ADR",
    "ontology_entity": "知識節點架構",
    "status": "approved",
    "source": {"uri": "docs/decisions/ADR-007-entity-architecture.md"},
    "supersedes": "ADR-003-entity-flat-model"
  }
)
```
Step 3：更新舊文件 entity：
```
write(
  collection="documents",
  data={
    "doc_id": "ADR-003-entity-flat-model",
    "status": "superseded",
    "superseded_by": "ADR-007-entity-architecture"
  }
)
```
Step 4：建立 relationship：
```
write(
  collection="relationships",
  data={
    "source_entity": "ADR-007-entity-architecture",
    "target_entity": "ADR-003-entity-flat-model",
    "relationship_type": "supersedes"
  }
)
```

## 從 git log 同步 document 狀態的流程

```
1. git log --name-only --since="30 days ago" -- "docs/**/*.md"
   → 找出最近 30 天修改的文件

2. 對每個修改的文件：
   a. 讀取 frontmatter 取得 doc_id 和 type
   b. search(collection="documents", query=doc_id) 找對應 entity
   c. 比對：
      - git 有修改 + ZenOS status=draft → 建議 under_review
      - git 有新文件 + ZenOS 無 entity → 建議建立 entity
      - git 文件已刪除 + ZenOS status=approved → 建議 archived

3. batch write 更新
```

## 常見陷阱

陷阱 1：把 L2 entity 的 summary 當 document
→ summary 是概念描述，不是文件。文件必須有 source.uri。

陷阱 2：不設 ontology_entity
→ 每份文件都是某個 L2 概念的具體化。找不到 L2？先建 L2 再掛文件。

陷阱 3：supersede 時刪除舊文件
→ 不刪除，改 status=superseded。歷史決策需要可追溯。
