# Feature Spec：/zenos-eval — Ontology 品質評估 Skill

**日期**：2026-03-21
**狀態**：草稿，待 Architect 確認

---

## 問題陳述

用戶跑完 `/zenos-capture` 之後，ontology 建在 Firestore 裡，但沒有任何機制能告訴他：
- 文件連得到嗎？摘要跟原文匹配嗎？
- ZenOS 內建 entry 的欄位填得完整嗎？

沒有品質評估，用戶無法信任 ontology，也無法知道哪裡需要補強。

---

## 目標

- 跑完 `/zenos-eval` 後，用戶知道這個 ontology 能不能被信任
- 輸出一份結構化報告，分「可立即修復」和「需要人工確認」兩類問題

## 非目標

- 不自動修復問題（eval 只報告，不寫入）
- 不評估骨架層的「業務正確性」（那是人工判斷）
- 不支援 local file URI（`file://`）——production 不應有此型態

---

## 兩種 Source 型態（核心設計）

| 型態 | source.uri | 來源 | 驗證方式 |
|------|-----------|------|---------|
| A：外部文件 | GitHub URL | `/zenos-capture` 掃目錄 | HTTP fetch + 摘要比對 |
| B：ZenOS 內建 | 空 / null | 對話捕獲 / 直接輸入 | MCP tool 拿 entry + 欄位完整性 |

兩種型態分開評估、分開報告。

---

## 使用情境

```
/zenos-eval                    ← 評估當前專案的 ontology
/zenos-eval Paceriz            ← 評估指定專案名稱的 ontology
/zenos-eval --entity-only      ← 只評估骨架層
/zenos-eval --doc-only         ← 只評估神經層
```

---

## 需求

### P0（核心）

**型態 A：外部文件可達性**
- [ ] Given entry 有 GitHub URL，When eval 執行，Then HTTP GET 該 URL，回傳 200 = ✅，4xx/5xx = ❌
- [ ] Given URL 可達，When eval 執行，Then 讀取文件前 300 字，用 AI 判斷摘要是否忠實反映原文（忠實 / 偏移 / 無關）
- [ ] Given URL 404，Then 標記為「來源失聯」，列入可修復問題清單

**型態 B：ZenOS 內建 entry 完整性**
- [ ] Given entry 無 source.uri，When eval 執行，Then 透過 MCP `get_document()` / `get_entity()` 確認 entry 可被查詢到
- [ ] Given entry 可查詢，Then 檢查必填欄位是否完整：`title`、`summary`、`tags.what`、`tags.why`
- [ ] Given 任何必填欄位為空，Then 標記為「欄位缺失」

### P1（重要）

- [ ] 統計神經層覆蓋率：這個專案有幾個文件 vs ontology 收錄了幾個
- [ ] 統計 confirmed_by_user 比例：多少 entry 已確認 vs draft
- [ ] 骨架層：列出沒有任何 document entry 關聯的實體（孤立實體）

### P2（未來）

- [ ] 偵測重複 entry（相同 source.uri 出現兩次）
- [ ] 摘要新鮮度：對比 git commit 時間 vs entry 建立時間，標記可能過時的 entry

---

## 輸出報告格式

```
📊 Ontology 品質報告：{專案名稱}
評估時間：{timestamp}

── 型態 A：外部文件（{n} 個 entry）──────────────
✅ 可達且摘要匹配：{n} 個
⚠️  摘要偏移（需人工確認）：{n} 個
  • {entry title} — 摘要說「X」但原文講的是「Y」
❌ 來源失聯（URL 無效）：{n} 個
  • {entry title} — {URL} → 404

── 型態 B：ZenOS 內建（{n} 個 entry）──────────────
✅ 完整：{n} 個
⚠️  欄位缺失：{n} 個
  • {entry title} — 缺少：tags.why

── 整體健康分數 ──────────────────────────────────
外部文件可達率：{n}%
內建 entry 完整率：{n}%
confirmed 比例：{n}%（{n}/{total} 個 entry 已確認）

── 建議行動 ──────────────────────────────────────
立即可修：{n} 項（URL 更新、欄位補填）
需人工確認：{n} 項（摘要偏移）
→ 執行 /zenos-capture 補強遺漏的文件
```

---

## 成功指標

- 短期（1 週）：跑完 eval 後，用戶知道要修什麼、怎麼修
- 長期：ontology 的外部文件可達率維持 > 90%

---

## 開放問題

- ⚠️ **待 Architect 確認**：`get_document()` / `get_entity()` MCP tool 現在支援 batch query 嗎？還是要逐一呼叫？（影響效能設計）
- ⚠️ **待 Architect 確認**：AI 摘要忠實度判斷，要用獨立的 Claude call 還是在 skill 執行過程中處理？
- ✅ **已決定**：摘要忠實度採嚴格標準——核心論點必須吻合，不能只是關鍵字重疊。AI 判斷時需確認摘要的主要主張與原文一致，若只是語意相關但重點偏移，標記為「偏移」。
