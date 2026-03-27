---
type: SPEC
id: SPEC-doc-governance
status: Approved
ontology_entity: documentation-governance
created: 2026-03-26
updated: 2026-03-27
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
| `SKILL-` | Skill | Agent 行為規範，定義角色、治理操作、工作流程 |

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
skills/         # SKILL-*.md（Agent 行為規範，獨立於 docs/ 的 SSOT）
  roles/        # SKILL-role-*.md
  governance/   # SKILL-gov-*.md
  workflows/    # SKILL-wf-*.md
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

## L3 文件生命週期（Lifecycle State Machine）

### 狀態定義

| 狀態 | 意義 | 進入條件 | 可初始建立？ |
|------|------|----------|------------|
| `Draft` | 草稿，正在撰寫或尚未通過審查 | 新建文件的唯一合法初始狀態 | ✅ 唯一 |
| `Under Review` | 內容完成，等待審查或確認 | 作者認為內容完整，提交審查 | ❌ |
| `Approved` | 已核准，為正式有效文件 | 審查通過 + ontology sync 完成 | ❌ |
| `Superseded` | 已被新文件取代，保留追溯價值 | 新版文件已就位且 `superseded_by` 已填寫 | ❌ |
| `Archived` | 已退場，不再有效但保留歷史 | 文件使命完成或主題不再適用 | ❌ |

### 合法轉換路徑

```
                    審查通過 + ontology sync
  Draft ──────→ Under Review ──────→ Approved
                     │                   │
                     │ 撤回修改           │ 新版取代 or 退場
                     ↓                   ↓
                   Draft            Superseded
                                        │
                                   Archived（可選）
                                        ↑
                                   Approved ──→ Archived（直接退場，無新版取代）
```

### 轉換條件

| 轉換 | 觸發條件 | 誰可觸發 |
|------|---------|---------|
| `Draft → Under Review` | 作者認為內容完整，所有必填欄位已填寫 | PM（SPEC）、Architect（ADR/TD）、作者 |
| `Under Review → Approved` | 審查通過 + `ontology_entity` 不為 TBD（或已明確標記例外）+ L3 entity 已同步 | Architect（技術文件）、PM（需求文件） |
| `Under Review → Draft` | 審查發現需要修改，撤回重寫 | 審查者 |
| `Approved → Superseded` | 新版文件已建立、舊文件 `superseded_by` 已填寫、ontology 追溯關係已建立 | PM / Architect |
| `Approved → Archived` | 文件使命完成且無新版取代（例如已驗收的一次性 TD） | PM / Architect |
| `Superseded → Archived` | 舊文件搬入 `archive/` 目錄 | 任何人（清理操作） |

### 禁止轉換

- `Approved → Draft`：不可倒退。需要改方向時，開新文件 + supersede。
- `Archived → 任何狀態`：已封存不可復活。若概念重新需要，建新文件。
- `Superseded → Approved`：被取代後不可恢復為有效。
- 跳過 `Under Review` 直接 `Draft → Approved`：所有文件都必須經過 review 階段。

### 終態

- `Superseded` 和 `Archived` 為終態，不可再轉換。
- `Superseded` 文件仍可被引用（追溯歷史），但不視為有效文件。

### Approved 前的品質閘

文件從 `Under Review → Approved` 前，必須滿足：

1. frontmatter 所有必填欄位已填寫
2. `ontology_entity` 不為 `TBD`（或已在專案層明文列為允許例外，且有追蹤 task）
3. 對應的 L3 document entity 已在 ontology 中建立或更新
4. 若為 ADR，決策內容已明確記錄理由與替代方案
5. 若為 SPEC，acceptance criteria 已定義

### `ontology_entity: TBD` 治理

- 新建文件時允許 `TBD`，但文件不得在 `TBD` 狀態下通過 `Under Review → Approved`。
- 每個 `TBD` 應在建立時同步開一個追蹤 task（或在文件內標記 TODO）。
- 治理 review 時，累積 TBD 文件數量為治理健康度指標之一。

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

### SKILL
- 格式：`SKILL-{category}-{name}.md`
- category：`role` / `gov` / `wf`（角色 / 治理 / 工作流程）
- 存放路徑：`skills/{roles|governance|workflows}/`
- 無編號，以功能命名

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

## Agent 文件治理合規流程

### 背景

PM 和 Architect agent 是文件的主要建立者。治理規則寫在 spec 裡不夠——agent 必須在寫文件的流程中內建治理檢查點，而非依賴記憶。本節定義 agent 寫文件時的強制動作序列。

### 適用角色

| 角色 | 文件類型 | 合規義務 |
|------|---------|---------|
| PM | SPEC | 完整合規流程 |
| Architect | ADR, TD, 補充 SPEC | 完整合規流程 |
| Developer | 不建立文件 | 發現 spec 與實作不一致時回報，不自行修改 |
| QA | 不建立文件 | 驗收時檢查文件是否合規，不自行修改 |
| zenos-capture | L3 document entity | 合規流程中的 ontology 同步執行者 |
| zenos-sync | L3 document entity | 增量同步時的 frontmatter 解析與狀態對齊 |

### 強制動作序列

Agent 每次建立或修改受治理文件時，必須依序完成以下四個階段。不可跳過任何階段。

#### 階段一：查重與現況確認（寫之前）

```
Agent 要寫/改文件
     │
     ├─ 1a. 搜尋 ontology：search(query="主題關鍵字", collection="documents")
     │       → 是否已有同主題的 L3 document entity？
     │
     ├─ 1b. 搜尋檔案系統：glob docs/ 下同前綴同主題的檔案
     │       → 是否已有同名或高度相似的文件？
     │
     └─ 1c. 若找到既有文件：讀取其 frontmatter，確認 status
            → Draft / Under Review：可直接修改
            → Approved：進入「更新 vs 開新」判斷（階段二）
            → Superseded / Archived：不可修改，必須開新文件
```

**禁止行為**：未搜尋就直接建新文件。

#### 階段二：新建 / 更新 / Supersede 判斷

```
                       既有文件？
                      /          \
                   否              是
                   │               │
              新建文件          讀取 status
                               /    |     \
                          Draft  Approved  Superseded/Archived
                            │       │              │
                       直接更新   判斷變更類型      必須開新文件
                                /         \
                      實作對齊型       決策改向型
                           │               │
                      直接更新         開新文件 + Supersede 舊文件
```

**判斷規則**（引用本 spec「何時開新文件 vs 更新既有文件」）：

- **可直接更新**：狀態變更、錯字修正、補充引用、frontmatter 更新、實作對齊（補 API/schema/路徑）
- **必須開新 + Supersede**：需求範圍改變、成功標準改變、核心流程改變、架構決策改變、責任邊界改變
- **ADR 特殊規則**：ADR 正文不可改寫，新決策一律開新 ADR

#### 階段三：執行寫入（原子完成）

根據階段二的判斷，執行對應的寫入操作。**Git 文件變更與 ontology 同步必須在同一輪操作中完成。**

##### 新建文件

1. 生成正確 frontmatter（`status: Draft`，`created: 今天`，`ontology_entity: {slug 或 TBD}`）
2. 確認檔名符合命名規則（前綴 + slug）
3. 確認目標目錄正確（type → directory 對應）
4. 寫入檔案
5. 呼叫 `mcp__zenos__write(collection="documents")` 建立 L3 document entity
6. 若 `ontology_entity` 為 TBD，開一個追蹤 task 或在文件內標記 TODO

##### 更新既有文件

1. 更新 frontmatter 的 `updated` 日期
2. 修改文件內容（僅限合法的更新範圍）
3. 呼叫 `mcp__zenos__write(collection="documents")` 更新 L3 document entity

##### Supersede 舊文件

1. 建立新文件（按「新建」流程）
2. 更新舊文件 frontmatter：`status: Superseded`，`superseded_by: {新文件 id}`，`updated: 今天`
3. 更新舊文件的 L3 document entity 狀態
4. 在新文件中記錄「本文件取代 {舊文件 id}」
5. 確認 ontology 中新舊文件的追溯關係已建立

**原子性要求**：步驟 1-5 必須在同一輪操作（同一個 commit 或同一次 agent 回應）中完成。不可只建新文件而遺忘更新舊文件。

#### 階段四：回填與驗證（寫之後）

1. **TBD 回填**：若 `ontology_entity` 為 TBD，在 L2 entity 建立後回填文件 frontmatter 與 L3 entity
2. **交叉驗證**：確認 Git 文件的 frontmatter status 與 ontology L3 entity status 一致
3. **引用檢查**：若本次操作涉及 supersede 或 archive，檢查其他文件是否引用了被取代/封存的文件

### 合規違規的偵測

| 違規類型 | 偵測方式 | 偵測時機 |
|---------|---------|---------|
| 重複文件（同主題多份 Draft） | analyze 比對 ontology 中相似 title 的 documents | 定期治理 review |
| Frontmatter 缺失或不一致 | zenos-sync 解析 frontmatter + 比對 ontology | 每次 sync |
| Git 與 ontology 狀態不同步 | zenos-sync 比對文件 status vs entity status | 每次 sync |
| TBD 長期未解決 | analyze 列出 `ontology_entity: TBD` 的文件 | 定期治理 review |
| Supersede 鏈斷裂（舊文件無 superseded_by） | analyze 檢查 Superseded 文件的 frontmatter | 定期治理 review |
| Approved 文件被直接改寫（非合法更新） | git blame + analyze 比對核心段落變更 | Phase 2 自動 lint |

### 與其他治理流程的關係

- **L2 治理**：Agent 建立文件時填寫的 `ontology_entity` 連結 L3 到 L2。L2 狀態變更（confirmed → stale）時，應觸發掛載文件的 review（見 L2 反饋路徑）。
- **Task 治理**：Task 完成後若產出文件（例如 SPEC、TD），該文件的建立必須走本合規流程。Task 的知識反饋閉環包含「產出文件已正確掛載到 ontology」。
- **傳播契約**：本合規流程本身也是治理規則。修改本流程時，適用憲法的傳播契約——必須同步更新 PM/Architect skill 中的對應步驟。

---

## 反饋路徑（Feedback Triggers）

文件治理的變更不是單向操作。以下事件必須觸發對應的反饋動作：

| 觸發事件 | 反饋對象 | 反饋動作 | 自動/人工 |
|---------|---------|---------|----------|
| 文件狀態從 Approved → Superseded | 新文件（superseded_by 指向的文件） | 確認新文件已就位且可消費 | 人工確認 |
| 文件狀態從 Approved → Superseded | 舊文件的 L3 document entity | 更新 entity 狀態 + 建立新舊文件追溯關係 | Phase 0 人工；Phase 1+ 自動 |
| 文件被 rename 或搬移 | 對應的 L3 document entity | 更新 source.uri，確保 ingest 路徑不斷鏈 | 人工處理（應由治理 sync 工具輔助） |
| 文件被 archive | 引用此文件的其他文件與 tasks | 通知 owner 檢查引用是否仍有效 | Phase 0 人工；Phase 1+ analyze 偵測 |
| `ontology_entity` 欄位變更 | 對應的 L2 entity | 檢查 L2 掛載是否仍正確 | 人工確認 |
| 文件類型（type）變更 | 原目錄與新目錄 | 搬移文件到正確目錄、更新索引 | 人工處理 |
| 新文件建立（status: Draft） | 對應的 L2 entity（若 ontology_entity 有值） | 在 L2 下新增 L3 掛載 | Phase 0 人工；Phase 1+ capture 自動 |

### 反饋完整性規則

1. **Supersede 必須雙向可追溯**：舊文件有 `superseded_by`，新文件的 description 或 frontmatter 應記錄它取代了什麼。
2. **路徑變更必須原子完成**：rename/搬移文件時，Git 變更與 ontology entity 更新必須在同一個 commit 或同一輪操作中完成，不得分批留斷鏈。
3. **Archive 不是刪除**：封存後的文件仍保留 frontmatter 與 entity 關聯，ontology 中的 L3 entity 標為 archived 而非刪除。

---

## 衝突仲裁（Conflict Resolution）

### 跨 Spec 衝突

本 spec 治理 L3 文件層。當與其他治理 spec 發生衝突時：

1. 依憲法（`docs/spec.md`）第二節第⑥維度的通用仲裁順序處理。
2. 本 spec 不得覆寫 L2 升降級規則（`SPEC-l2-entity-redefinition` 權威）。
3. 本 spec 不得覆寫 Task 建票品質與驗收規則（`SPEC-task-governance` 權威）。
4. 若文件治理規則與 L2 治理規則在同一 entity 上產生矛盾（例如文件說應 archive 但 L2 認為概念仍 confirmed），以 L2 狀態為準，文件治理配合調整。

### 專案層衝突

專案層規則可補充但不得削弱核心約束（見下方「專案層可覆寫項目」）。專案層規則與本 spec 矛盾時，以本 spec 為準。

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
