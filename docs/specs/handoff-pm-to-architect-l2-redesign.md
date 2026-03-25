# PM → Architect 交接：L2 Entity 演算法重新設計

**日期：** 2026-03-24
**PM：** barry
**Architect：** architect
**Spec：** docs/specs/SPEC-l2-entity-redefinition.md

---

## 一句話交接

現有 capture/analyze 是「由下而上、逐檔處理」，產出的是技術模組摘要。
新演算法必須「由上而下、全局統合」，產出公司共識概念 + 具體 impacts 傳播路徑。

---

## 最關鍵的設計約束：全局視野

這不是優化，是根本性的演算法方向改變。

**舊模式（禁止）：**
```
for each file → analyze → emit L2
```

**新模式（必須）：**
```
read all files → global understanding → identify consensus concepts → split by independence → infer impacts
```

「全局視野」的具體意思：LLM 必須在看到所有輸入之後才開始切 L2。不能邊讀邊切。

---

## 修改範圍

Architect 需要評估並修改：

1. **`/zenos-capture` skill 的 L2 推斷邏輯**
   - 現有：逐文件分析並直接輸出 L2
   - 新要求：先批量讀入所有文件，再做全局統合推斷

2. **`governance_ai.py` 或相關 LLM Prompt 設計**
   - 新增「全景建立」步驟（Step 1）
   - 新增「三問篩選閘」邏輯
   - 強化 impacts 推斷（要求具體的傳播路徑，不接受模糊的 `A impacts B`）

3. **Entity schema（如需要）**
   - `level` 欄位是否已正確標記 L2？
   - impacts relationship 的欄位結構是否能存「具體傳播說明」？

4. **可能的測試資料**
   - 用 Paceriz 的現有文件跑 capture，驗證 L2 能拆成至少 3 個獨立概念

---

## PM 驗收方式

Architect 實作完後，PM 用以下方式驗收：

1. **跑 Paceriz capture**：`python -m zenos-capture [paceriz docs dir]`
2. **看 L2 輸出**：「訓練計畫系統」原本是 1 個 L2 → 應該拆成至少 3 個（訓練閉環、ACWR 安全機制、訓練方法論體系）
3. **看 summary**：拿給非工程師讀，他看得懂嗎？
4. **看 impacts**：每條 impacts 能說出「A 的什麼改了 → B 的什麼要跟著看」
5. **行銷 agent 模擬**：只用 `mcp__zenos__search(collection="entities", query="行銷賣點")` 能不能在 30 秒內組出「我們能宣傳什麼」

---

## 不需要 Architect 決策的事

- L1、L3 演算法不動
- 現有已確認 L2 不強制遷移
- Firestore schema 結構不動（只改 LLM prompt 邏輯和 Python 流程）

---

## 優先級

Critical。這是 ZenOS 核心價值路徑：ontology 品質 → AI agent 有用 → 客戶留存。

Ontology 退化成文件索引等於 ZenOS 的核心價值消失。
