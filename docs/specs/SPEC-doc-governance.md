---
type: SPEC
id: SPEC-doc-governance
status: Draft
ontology_entity: documentation-governance
created: 2026-03-26
updated: 2026-03-26
---

# Feature Spec: ZenOS-Enabled 專案文件治理規則

## 背景與動機

任何導入 ZenOS 的專案，最終都需要讓文件同時服務三件事：

- 人類可以快速判斷文件是什麼、是否仍有效、應該去哪裡找
- AI 可以穩定解析文件類型、狀態、與 ontology 的對應關係
- 團隊可以知道何時建立新文件、何時更新舊文件、何時封存或刪除

若缺乏統一治理，常見問題包括：

- 不同類型文件混放，難以分辨權威來源
- 檔名與編號沒有一致規則，容易重複或失序
- 暫存稿、handoff、備份檔長期留在主路徑，造成噪音
- 文件與 ontology 無法穩定對應，AI 索引與追蹤失效
- 團隊不知道哪些變更可直接更新、哪些應該另開新文件

本規則的目標是提供一套可跨專案重用的最小治理標準。專案可以在此基礎上增加細則，但不應削弱核心約束。

---

## 適用範圍

本規則適用於：

- 專案內以 Markdown 維護、且需要被 ZenOS 納入知識治理的正式文件
- 放置於 `docs/` 或專案明確宣告為「受治理文件區」的目錄

本規則不自動適用於：

- 程式碼註解、docstring、套件 README
- 純工具層文件（例如 AI agent 本地設定）
- Demo 素材、一次性輸出、暫存分析結果

若專案需要治理上述文件，必須另外明文宣告納入。

---

## 治理原則

1. 每份正式文件都必須可被分類。
2. 每份正式文件都必須可被唯一識別。
3. 每份正式文件都必須有明確生命週期狀態。
4. 每份正式文件都必須可對應到 ontology 概念或明確標示暫無對應。
5. 文件正文的穩定性應高於協作便利性；需要保留歷史時，寧可開新文件，不覆寫既有決策。
6. 專案特例可以存在，但必須明文記錄為 local convention，不可只靠口頭共識。
7. 任何影響文件分類、狀態、命名、取代關係、或 ontology 對應的修改，都必須同步更新 ontology；否則視為未完成變更。

---

## 文件類型定義

| 類型前綴 | 名稱 | 主要用途 |
|---------|------|----------|
| `SPEC-` | Product Spec | 說明需求、範圍、目標與非目標 |
| `ADR-` | Architecture Decision Record | 記錄技術或架構決策與理由 |
| `TD-` | Technical Design | 記錄實作設計、資料結構、API、元件協作 |
| `PB-` | Playbook | 記錄操作手冊、維運流程、部署與故障處置 |
| `SC-` | Scenario | 記錄使用場景、Demo 腳本、服務流程 |
| `REF-` | Reference | 記錄術語、背景知識、長期參考資料 |

如專案需要新增類型，必須先補充到本治理規則或專案附屬規則，再開始使用。

---

## 建議目錄結構

```text
docs/
  specs/        # SPEC-*.md
  decisions/    # ADR-*.md
  designs/      # TD-*.md
  playbooks/    # PB-*.md
  scenarios/    # SC-*.md
  reference/    # REF-*.md
  archive/      # 已封存文件
```

這是建議結構，不是硬性要求。若專案已存在其他結構，至少必須保證：

- 同類型文件有穩定聚集位置
- archive 與 active 文件可被清楚分隔
- 專案文件中有一處記錄「哪些路徑受治理、哪些不受治理」

若專案有既有 canonical 文件可保留原名與原位，必須在專案層規則中明文列為例外。

---

## Frontmatter 規格

每份受治理文件都必須包含 frontmatter：

```yaml
---
type: SPEC | ADR | TD | PB | SC | REF
id: {prefix}-{slug}
status: Draft | Under Review | Approved | Superseded | Archived
ontology_entity: {entity-slug | TBD}
created: YYYY-MM-DD
updated: YYYY-MM-DD
superseded_by: {id}   # 僅當 status: Superseded 時填寫
---
```

欄位說明：

- `type`: 文件類型，必須與檔名前綴一致
- `id`: 文件唯一識別碼，跨目錄不可重複
- `status`: 文件生命週期狀態
- `ontology_entity`: 對應的 ontology entity slug；若尚未建好，可暫填 `TBD`
- `created`: 文件首次建立日期
- `updated`: 最近一次合法更新日期
- `superseded_by`: 指向取代它的新文件

`ontology_entity` 是文件與 ontology 的鬆耦合連結。entity 改版時，應優先更新 metadata，而不是搬移文件。

---

## 與 Ontology 的同步規則

文件治理不是獨立系統。對 ZenOS 而言，文件分類的變更若沒有同步回 ontology，就會造成索引、推理、追溯與 routing 斷鏈。

因此，以下變更都必須同步更新 ontology：

- 文件從一種類型改到另一種類型
- 文件 rename、搬移、封存、supersede、刪除
- `ontology_entity` 改變
- canonical 文件、reference 文件、playbook 文件等治理角色改變

同步要求：

- L2 entity 要反映新的治理概念或文件歸屬
- L3 document entity 要反映新的文件 metadata、來源路徑、狀態與關聯
- 若文件被取代，舊 L3 entity 與新 L3 entity 的關係必須可追溯

同步 contract：

- 文件治理的同步操作必須採用局部更新語意。當 caller 只更新 `source.uri`、`status`、frontmatter 或分類結果時，未明示修改的欄位不得被清空。
- L3 document entity 的主要掛載點以 `parent_id` 為準；若系統另外物化 `part_of` 或其他 relationship 作為圖譜邊，必須保證與 `parent_id` 一致，不可一邊存在一邊脫落。
- `linked_entity_ids` 若作為文件同步輸入，必須定義為 `list[str]`。第一個 ID 代表 primary parent，其餘代表額外關聯；不得接受會造成逐字元解析的模糊字串格式。
- 對 rename、reclassify、archive、supersede 這類批次治理操作，系統應提供專用 sync 模式或等價流程，一次處理路徑更新、掛載修復、狀態調整與追溯關係，而不是要求 caller 手動拆成多次危險 write。

完成定義：

- Git 內文件已更新
- 對應 ontology 的 L2 / L3 entity 已更新
- ZenOS ingest / capture / sync 流程重新可用，且不會指向過時 metadata

---

## 命名與編號規則

### SPEC
- 格式：`SPEC-{feature-slug}.md`
- slug 以功能或議題命名，全小寫連字號
- 無流水號，slug 即唯一識別

### ADR
- 格式：`ADR-{3位數序號}-{decision-slug}.md`
- 序號在專案內全域唯一
- 不得重複使用既有序號，即使舊檔已封存也一樣

### TD
- 格式：`TD-{spec-slug}.md` 或 `TD-{spec-slug}-{layer}.md`
- 建議與對應 SPEC slug 對齊

### PB / SC / REF
- 格式：`{PREFIX}-{topic-slug}.md`
- 無編號，以主題命名

---

## 何時開新文件 vs 更新既有文件

本規則的核心不是「已核准文件不能改」，而是區分：

- 實作對齊型更新：反映目前真實狀態，可直接更新
- 決策改向型更新：改變原本承諾或判斷，必須保留版本邊界

### 開新文件
- 全新需求、議題或能力邊界
- 新決策，即使與舊決策高度相關
- 已核准文件出現實質方向改變
- 需要保留獨立審核、討論或驗收歷史

### 可直接更新
- 狀態變更
- 錯字修正、語意澄清、補充引用
- 補寫驗收結果、實際連結、交叉參照
- frontmatter metadata 更新，例如 `status`、`updated`、`ontology_entity`、`superseded_by`
- 實作對齊型更新，例如：
  - 補上最終 API、schema、路徑、元件名稱
  - 記錄已完成、已棄用、已延後的實作細節
  - 補充 rollout、限制、已知差異、驗證結果

### 必須開新版本或 amendment
- 需求範圍改變
- 成功標準或驗收標準改變
- 核心使用流程改變
- 架構或技術決策改變
- 責任邊界、依賴關係、對外承諾改變
- 會影響下游文件、實作責任或跨團隊協作方式的變更

### 不可直接改寫正文
- ADR 的決策內容
- 已 `Approved` 文件中的核心方向、需求邊界、決策結論

判斷原則：

- 如果變更是在說「實際怎麼落地」，通常可直接更新
- 如果變更是在說「原本決定什麼、現在改成別的」，就必須開新版本

若既有文件已 `Approved`，且需要改正文中的實質方向，應建立新文件，並將舊文件標為 `Superseded`。

---

## 人工治理例外

文件治理導入期，可能先需要建立一個暫時性的治理概念或掛載點，再逐步補齊 impacts、關聯或 supporting docs。對這類人工建模情境：

- 系統應提供明確的一級語意，例如 `manual_override_reason`、`provisional=true`、或等價欄位，讓 caller 能表達「這是人工治理例外，不是一般自動推斷成功的 L2」。
- 這類例外必須可審計，並能在後續治理 review 中被列出與補完。
- `force=true` 可作為底層逃生閥，但不應是人工治理流程的唯一正式介面。

---

## Archive 與刪除規則

### 應封存到 `archive/`
- 已完成使命，且保留歷史有價值的 handoff 文件
- 被新版文件完整取代的舊文件
- 已驗收完成、但仍需追溯的任務設計文件

### 可直接刪除
- 明確屬於暫存、備份、或中間產物的檔案，例如 `.bak`
- 已被正式文件吸收、且無追溯價值的訪談草稿或一次性問答
- 可由其他系統穩定重建的產出物

### 封存前必須滿足
- 若文件被取代，舊文件需標記 `status: Superseded` 與 `superseded_by`
- 若文件單純退場但未被新文件取代，應標記 `status: Archived`
- archive 目錄中的文件仍應保留 frontmatter 與原始識別

---

## 專案導入流程

### P0 — 建立治理邊界
- 列出哪些目錄屬於受治理文件區
- 列出哪些目錄或文件類型明確排除
- 指定是否存在 canonical 文件例外

### P1 — 建立一致 metadata
- 為所有受治理文件補齊 frontmatter
- 修正重複 ID、重複 ADR 編號、與不一致前綴
- 將明確屬於備份或噪音的檔案移除

### P2 — 結構整理
- 將正式文件移到穩定類型目錄
- 將 handoff、已完成任務文件、舊版本移入 archive
- 將 reference 類長青文件集中管理

### P3 — 與 ZenOS 對接
- 確保 ZenOS ingest 流程可解析 frontmatter
- 補齊 `ontology_entity`
- 對尚未建好的 ontology 概念，先以 `TBD` 暫掛，後續補建並回填
- 對每次 rename、reclassify、archive、supersede 操作，同步更新對應的 L2 / L3 entity

---

## 專案層可覆寫項目

以下項目可由各專案自行補充，但必須寫成明文規則：

- 哪些目錄納入治理
- 是否保留既有 canonical 文件與其例外命名
- 是否新增文件類型
- archive 的保留年限
- 是否要求某些類型一定綁定特定 ontology 層級

專案層規則不得覆寫以下核心約束：

- 正式文件必須可分類、可識別、可追蹤狀態
- 已核准決策不可被靜默改寫
- 取代關係必須可追溯
- ZenOS ingest 必須能穩定解析 metadata

---

## 技術約束

- frontmatter 格式必須與 ZenOS ingest / capture 流程相容
- `ontology_entity` 若不是 `TBD`，應對應到 ontology 中實際存在的 entity
- 文件治理相關變更不得只改 Git 文件而不改 ontology；L2 / L3 entity 必須與文件現況一致
- 專案若需要更嚴格限制，例如禁止 `TBD` 進入 main branch，應在 CI 或 lint 規則中實作
