---
name: zenos-capture
description: >
  從當前對話、單一文件、或整個專案目錄擷取知識並寫入 ZenOS ontology。
  三種模式：(1) 無引數 = 從最近對話捕獲；(2) 單一檔案 = 讀該檔案；
  (3) 目錄路徑 = 首次建構模式，自動掃描目錄內所有文件並批量建構 ontology。
  當使用者說「存進 ontology」「記到 ZenOS」「capture 這段」「/zenos-capture」，
  或說「把這個專案加入 ZenOS」「幫我建這個服務的 ontology」「把這個 repo 的文件掃進去」，
  或在討論完某個設計決策後想保存到知識層時，一定要使用這個 skill。
  引數範例：無引數、path/to/file.md、/Users/me/project/（目錄）
version: 3.0.0
---

# /zenos-capture

**本 skill 的 SSOT 位於 `skills/workflows/knowledge-capture.md`。**

請先用 Read tool 讀取 `skills/workflows/knowledge-capture.md` 的完整內容，然後嚴格按照該文件的流程執行。

相關治理規則：
- L2 概念判斷：`skills/governance/l2-knowledge-governance.md`
- L3 文件建立：`skills/governance/document-governance.md`
