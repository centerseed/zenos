# PM → Architect 交接：L2 Entity 演算法重新設計

**日期**：2026-03-24
**Spec**：`docs/specs/SPEC-l2-entity-redefinition.md`（Approved）
**已同步**：`docs/spec.md` Part 4 + Part 7.2 + `docs/glossary.md`

---

## 背景

Dogfooding 發現 ontology 退化成文件索引。根本原因：L2 按技術模組切，內容是工程師語言，關聯太少太模糊。PM 已重新定義 L2，Architect 需要重新設計 ZenOS 核心的 capture/analyze 演算法，讓產出符合新定義。

## ⚠️ 最關鍵的設計約束：全局視野

**這次演算法重設計的核心挑戰不是修改現有邏輯，而是根本改變 AI 的思考視角。**

### 現在的演算法怎麼運作

```
逐檔掃描 → 每個檔案/目錄產出一個 entity → 技術視角的 summary → 稀疏的 relationship
```

這是「由下而上、逐檔處理」的模式，結果是：每個 entity 只反映一個檔案的視角，沒有全局觀。

### 新演算法必須怎麼運作

```
讀取所有相關文件 → 以全公司的視野統合理解 → 辨識跨文件的共識概念 → 從全局角度切割 L2 → 推斷概念之間的 impacts 關聯
```

**這是「由上而下、全局統合」的模式。** AI 必須先理解整間公司在做什麼，才能判斷哪些是「任何人都會點頭的共識」，哪些只是某個角色的專屬知識。

### 為什麼這很重要

PM 在這次 dogfooding 中做的事情就是新演算法要自動化的事情：

1. **讀了 spec.md、marketing-one-pager、SPEC-billing、glossary、所有 ADR**——不是逐檔摘要，是讀完全部之後形成全景理解
2. **從全景中辨識出 11 個跨文件的 L2 共識概念**——例如「怎麼收費」這個概念散落在 SPEC-billing + marketing-one-pager + spec.md 三個地方，但它是一個概念
3. **從全局角度推斷 impacts 關聯**——「改定價 → 行銷話術要改 → 客群定位要確認」，這條路徑不存在任何一份文件裡，是從全局理解中推斷出來的
4. **用任何人都聽得懂的語言重新表述**——不是翻譯某一份文件，是把散落在多份文件中的知識統合成一句公司共識

**如果新演算法還是逐檔掃描、逐檔產出，產出的還是會退化成文件索引。** 核心設計必須確保 AI 在產出任何 L2 entity 之前，已經讀過並理解了足夠多的文件來形成全局觀。

### Prompt 設計的關鍵

演算法中給 AI 的 prompt 至少需要解決：

1. **全局統合**：先讀完所有文件，形成「這間公司在做什麼、賣給誰、怎麼運作」的全景理解
2. **共識辨識**：從全景中抽取「任何角色都會同意的事實」，而不是「某份文件的摘要」
3. **獨立性切割**：判斷哪些概念可以獨立改變（= 分成不同 L2），哪些一定連動（= 同一個 L2）
4. **跨角色語言**：用公司共通的語言寫 summary，不是技術語言也不是行銷語言，是共識語言
5. **影響路徑推斷**：從全局理解推斷「A 改了，B 要跟著動」的 impacts 關聯——這需要同時理解 A 和 B 才能判斷

---

## Architect 需要做什麼

### 1. 重新設計 `/zenos-capture` 的 L2 推斷演算法

**現在的問題**：capture 是逐檔掃描、逐檔產出，結果是技術模組（一個 module = 一個技術邊界），summary 是工程師語言，沒有全局觀。

**新的要求**：
- **全局優先**：AI 必須先讀取足夠多的文件形成全景理解，再從全景中切割 L2 概念
- 產出的 L2 entity 是「公司共識概念」，不是技術模組
- 一個技術模組可能拆成多個 L2 entity（按「可獨立改變」切）
- 多份文件中散落的同一個概念，要統合成一個 L2 entity（不是每份文件各建一個）
- Summary 必須用任何人都聽得懂的語言
- Tags.why 從公司/客戶角度寫，不是技術角度
- Tags.who 列出所有相關角色，不只是 owner

**判斷標準（PM 驗收用）**：
1. 公司共識？任何角色都會點頭
2. 改變時有下游影響？
3. 跨時間存活？

### 2. 重新設計 relationship 推斷，特別是 `impacts` 類型

**現在的問題**：relationship 幾乎沒有，ZenOS 自己的 entity 有 0 條 relationship。

**新的要求**：
- `impacts`：A 改了，B 必須跟著檢查（最核心的關係類型）
- `depends_on`：B 要先存在，A 才成立
- `part_of`：A 是 B 的一個組成部分
- `enables`：A 存在讓 B 成為可能

**品質標準**：每條 relationship 必須能具體說出「A 改了什麼的時候，B 的什麼地方要跟著看」。說不出來 = noise，不該建。

### 3. L2 和 L3 的區分機制

**新的要求**：
- Entity schema 上需要有明確標記區分 L2 和 L3（不能只靠 convention）
- L2 的 summary 不能依賴外部文件才能理解——它本身就是完整的共識陳述
- L3 透過 sources 掛在 L2 底下

## PM 驗收方式

Architect 交付後，PM 會用以下方式驗證：

1. **拿 Paceriz 的現有文件跑一次 capture**，檢查產出的 L2 是否符合 spec 中的 Paceriz 實例（訓練流程 V2、安全機制、品質保證、V2 上線狀態等）
2. **檢查 relationship 品質**：每條 impacts 是否能說出具體的「改什麼→影響什麼」
3. **模擬行銷 agent 場景**：只用 MCP query ontology，看能不能在 30 秒內回答「Paceriz 現在有什麼功能可以宣傳」
4. **模擬「改定價」傳播**：更新一個 L2 concept，看 impacts 路徑是否能列出所有需要跟著動的東西

## 開放問題（需要 Architect 決定）

1. L2 entity 是否需要新的 entity type（如 `concept`），還是繼續用 `module` type？
2. 現有 module entity 的遷移策略？
3. `impacts` 要不要區分影響程度（must-update vs should-check）？
4. L2 summary 品質的自動檢查機制？

## 參考文件

- `docs/specs/SPEC-l2-entity-redefinition.md` — 完整 spec
- `docs/spec.md` Part 4 — Entity 分層模型（已更新）
- `docs/spec.md` Part 7.2 — Entity 架構（已更新）
