---
name: zenos-sync
description: >
  掃描 git log 找出最近變更的文件，比對 ZenOS ontology，批量 propose 更新。
  支援兩種使用情境：(1) 無引數 = 同步當前專案；(2) 目錄路徑 = 同步指定的外部專案。
  輔助知識同步 skill——定期執行或在大量文件變更後使用，讓 ontology 跟上 codebase 節奏。
  當使用者說「同步 ontology」「sync ZenOS」「掃 git 變更」「更新 ontology」「/zenos-sync」，
  或在一批 commits 後想讓 ontology 跟上，或說「幫我同步 {專案名}」時使用。
  注意：第一次為某個專案建立 ontology 請用 /zenos-capture {目錄}，
  /zenos-sync 是為已有 ontology 的專案做增量同步。
version: 3.0.0
---

# /zenos-sync

**本 skill 的 SSOT 位於 `skills/workflows/knowledge-sync.md`。**

請先用 Read tool 讀取 `skills/workflows/knowledge-sync.md` 的完整內容，然後嚴格按照該文件的流程執行。

相關治理規則：
- L2 概念判斷：`skills/governance/l2-knowledge-governance.md`
- L3 文件建立：`skills/governance/document-governance.md`
