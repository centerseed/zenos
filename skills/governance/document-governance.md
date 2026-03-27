---
type: SKILL
id: document-governance
status: Draft
ontology_entity: documentation-governance
created: 2026-03-27
updated: 2026-03-27
---

# document-governance：L3 文件治理合規操作

Agent 建立或修改受治理文件時的強制操作序列——把規則轉換成每一步可執行的動作。

---

## 適用場景

在以下情況，Agent 必須載入本 skill 並照流程執行：

- 建立任何新的 `docs/` 下受治理文件（SPEC / ADR / TD / PB / SC / REF）
- 建立新的 `skills/` 下的 SKILL 文件
- 修改現有受治理文件的正文或 frontmatter
- 執行 Supersede 操作（以新文件取代舊文件）
- 執行 Archive 操作（封存退場文件）
- 任何涉及文件 rename / 搬移 / 刪除的操作

**不適用場景**：程式碼註解、docstring、套件 README、Demo 素材、暫存分析結果。

---

## 權威來源

本 skill 的所有規則來源於：`docs/specs/SPEC-doc-governance.md`

當本 skill 與源 spec 有歧義時，以源 spec 為準。本 skill 只翻譯 how，不定義 what。

---

## 四階段合規流程

Agent 每次建立或修改受治理文件時，必須依序完成以下四個階段。不可跳過任何階段。

---

### 階段一：查重與現況確認（寫之前）

**目的**：確保不重複建立已存在的文件，確認既有文件的當前狀態。

**步驟 1a：搜尋 ontology**

```
mcp__zenos__search(
  query="<主題關鍵字>",
  collection="documents"
)
```

判斷：回傳結果中是否有同主題的 L3 document entity？

**步驟 1b：搜尋檔案系統**

```
Glob(pattern="docs/**/<PREFIX>-<主題關鍵字>*.md")
```

或依文件類型搜尋對應目錄：

```
Glob(pattern="docs/specs/SPEC-<slug>*.md")
Glob(pattern="docs/decisions/ADR-*<slug>*.md")
```

判斷：是否有同名或高度相似的文件？

**步驟 1c：確認既有文件狀態**

若找到既有文件，讀取其 frontmatter：

```
Read(file_path="<既有文件路徑>")
```

根據 `status` 決定下一步：

| status | 可執行動作 |
|--------|-----------|
| `Draft` | 可直接修改 |
| `Under Review` | 可直接修改 |
| `Approved` | 進入階段二的「更新 vs 開新」判斷 |
| `Superseded` | 不可修改，必須開新文件 |
| `Archived` | 不可修改，必須開新文件 |

**禁止行為**：未執行步驟 1a 和 1b 就直接建新文件。

---

### 階段二：新建 / 更新 / Supersede 判斷

**目的**：確定本次操作的性質，選擇正確的執行路徑。

**判斷流程**：

```
既有文件存在？
├── 否 → 路徑 A：新建文件
└── 是 → 讀取 status
          ├── Draft / Under Review → 路徑 B：直接更新
          ├── Approved → 判斷變更類型
          │             ├── 實作對齊型 → 路徑 B：直接更新
          │             └── 決策改向型 → 路徑 C：開新文件 + Supersede 舊文件
          └── Superseded / Archived → 路徑 A：新建文件
```

**判斷標準**：

可直接更新（路徑 B）的變更類型：
- 狀態變更（`status` 欄位）
- 錯字修正、語意澄清、補充引用
- frontmatter metadata 更新（`updated`、`ontology_entity`、`superseded_by`）
- 補充實作細節：API endpoint、schema、路徑、元件名稱
- 記錄已完成、已棄用、已延後的實作細節
- 補充 rollout 結果、限制、驗證結果

必須開新文件 + Supersede（路徑 C）的變更類型：
- 需求範圍改變
- 成功標準或驗收標準改變
- 核心使用流程改變
- 架構或技術決策改變
- 責任邊界、依賴關係、對外承諾改變

**ADR 特殊規則**：ADR 正文不可任何修改。新決策一律開新 ADR，舊 ADR 標為 `Superseded`。

---

### 階段三：執行寫入（原子完成）

Git 文件變更與 ontology 同步必須在同一輪操作中完成。不可分批。

---

#### 路徑 A：新建文件

**步驟 A1**：生成正確 frontmatter

```yaml
---
type: <SPEC|ADR|TD|PB|SC|REF|SKILL>
id: <PREFIX>-<slug>
status: Draft
ontology_entity: <entity-slug 或 TBD>
created: <今天日期 YYYY-MM-DD>
updated: <今天日期 YYYY-MM-DD>
---
```

注意：新建文件的唯一合法初始狀態為 `Draft`。

**步驟 A2**：確認檔名符合命名規則

查閱「文件類型速查表」確認前綴與 slug 格式。

**步驟 A3**：確認目標目錄

查閱「文件類型速查表」確認正確目錄。

**步驟 A4**：寫入檔案

```
Write(file_path="<正確目錄>/<檔名>.md", content="<完整內容>")
```

**步驟 A5**：建立 L3 document entity

```
mcp__zenos__write(
  collection="documents",
  title="<文件標題>",
  source_uri="<相對路徑>",
  status="draft",
  ontology_entity="<entity-slug 或 TBD>",
  // 其他 metadata
)
```

**步驟 A6**：若 `ontology_entity` 為 TBD

在文件內標記 `TODO: 補齊 ontology_entity` 並開一個追蹤 task：

```
mcp__zenos__task(
  action="create",
  title="補齊 <文件 id> 的 ontology_entity",
  description="文件 <id> 建立時 ontology_entity 為 TBD，需建立對應 L2 entity 後回填"
)
```

---

#### 路徑 B：更新既有文件

**步驟 B1**：更新 frontmatter 的 `updated` 日期

```yaml
updated: <今天日期 YYYY-MM-DD>
```

**步驟 B2**：修改文件內容（僅限合法的更新範圍，見階段二判斷標準）

**步驟 B3**：同步更新 L3 document entity

```
mcp__zenos__write(
  collection="documents",
  id="<既有 entity id>",
  // 只傳需要更新的欄位，未修改欄位不傳（局部更新語意）
  status="<新狀態（如有改變）>",
  updated="<今天日期>"
)
```

---

#### 路徑 C：Supersede 舊文件（原子性要求，步驟 C1-C5 必須在同一輪操作完成）

**步驟 C1**：建立新文件（執行路徑 A 的全部步驟）

新文件正文中必須記錄：

```
> 本文件取代 <舊文件 id>。
```

**步驟 C2**：更新舊文件 frontmatter

```yaml
status: Superseded
superseded_by: <新文件 id>
updated: <今天日期 YYYY-MM-DD>
```

```
Edit(
  file_path="<舊文件路徑>",
  old_string="status: Approved",
  new_string="status: Superseded"
)
// 同樣方式更新 superseded_by 和 updated
```

**步驟 C3**：更新舊文件的 L3 document entity 狀態

```
mcp__zenos__write(
  collection="documents",
  id="<舊文件 entity id>",
  status="superseded",
  superseded_by="<新文件 id>"
)
```

**步驟 C4**：在新文件的 L3 entity 中建立追溯關係（若系統支援）

**步驟 C5**：驗證原子性

確認以下兩項都已完成才算結束：
- 新文件已建立且 L3 entity 已同步
- 舊文件已標記 `Superseded` 且 L3 entity 已更新

---

### 階段四：回填與驗證（寫之後）

**步驟 4a：TBD 回填**

若當前或過去文件的 `ontology_entity` 為 TBD，且現在 L2 entity 已建立：

1. 回填文件 frontmatter 的 `ontology_entity`
2. 更新對應的 L3 document entity
3. 關閉追蹤 task

**步驟 4b：交叉驗證**

確認 Git 文件的 frontmatter `status` 與 ontology L3 entity 的 `status` 一致。若不一致，以 Git 文件為準並修正 ontology。

**步驟 4c：引用檢查**

若本次操作涉及 supersede 或 archive：

```
Grep(pattern="<舊文件 id>", path="docs/")
Grep(pattern="<舊文件 id>", path="skills/")
```

找出所有引用舊文件的位置，評估是否需要更新引用。

---

## 文件類型速查表

| 前綴 | 類型名稱 | 目錄 | 命名格式 | 範例 |
|------|---------|------|---------|------|
| `SPEC-` | Product Spec | `docs/specs/` | `SPEC-{feature-slug}.md` | `SPEC-doc-governance.md` |
| `ADR-` | Architecture Decision Record | `docs/decisions/` | `ADR-{3位數序號}-{decision-slug}.md` | `ADR-004-l2-redefinition.md` |
| `TD-` | Technical Design | `docs/designs/` | `TD-{spec-slug}.md` 或 `TD-{spec-slug}-{layer}.md` | `TD-doc-governance.md` |
| `PB-` | Playbook | `docs/playbooks/` | `PB-{topic-slug}.md` | `PB-deploy-mcp.md` |
| `SC-` | Scenario | `docs/scenarios/` | `SC-{topic-slug}.md` | `SC-partner-onboarding.md` |
| `REF-` | Reference | `docs/reference/` | `REF-{topic-slug}.md` | `REF-glossary.md` |
| `SKILL-` | Skill | `skills/{category}/` | `SKILL-{category}-{name}.md` | `document-governance.md` |

**SKILL category 對照**：
- `role` → `skills/roles/`
- `gov` → `skills/governance/`
- `wf` → `skills/workflows/`

**ADR 序號規則**：序號在專案內全域唯一，不得重複使用既有序號，即使舊檔已封存。

---

## 生命週期操作指南

### 狀態轉換一覽

| 轉換 | 操作步驟 | 誰可觸發 |
|------|---------|---------|
| `Draft → Under Review` | 確認所有必填欄位已填寫，更新 frontmatter status | PM（SPEC）/ Architect（ADR/TD）/ 作者 |
| `Under Review → Approved` | 確認品質閘（見下方），更新 frontmatter + L3 entity | Architect（技術）/ PM（需求） |
| `Under Review → Draft` | 更新 frontmatter status（撤回修改） | 審查者 |
| `Approved → Superseded` | 執行路徑 C（Supersede 操作） | PM / Architect |
| `Approved → Archived` | 更新 frontmatter status + 搬移至 `docs/archive/` + 更新 L3 entity | PM / Architect |
| `Superseded → Archived` | 搬移至 `docs/archive/`，frontmatter 維持 Superseded | 任何人（清理操作） |

### Under Review → Approved 品質閘

通過前必須滿足全部條件：

- [ ] frontmatter 所有必填欄位已填寫（type / id / status / ontology_entity / created / updated）
- [ ] `ontology_entity` 不為 `TBD`（或已明文列為允許例外且有追蹤 task）
- [ ] 對應的 L3 document entity 已在 ontology 中建立或更新
- [ ] 若為 ADR：決策內容已明確記錄理由與替代方案
- [ ] 若為SPEC：acceptance criteria 已定義

### Archive 操作步驟

1. 更新 frontmatter：`status: Archived`，`updated: 今天`
2. 搬移檔案至 `docs/archive/`（保留原始 frontmatter）
3. 更新 L3 document entity 狀態：`status: archived`（不刪除 entity）
4. 若有其他文件引用此文件，通知 owner 確認引用是否仍有效

---

## Supersede 操作 Checklist

執行 Supersede 前後，逐項確認：

**執行前**
- [ ] 新文件已完整撰寫並通過自我審查
- [ ] 新文件有正確的 frontmatter（`status: Draft`）
- [ ] 確認舊文件的 entity id（用於步驟 C3）

**執行中（同一輪操作原子完成）**
- [ ] 新文件已寫入正確目錄
- [ ] 新文件正文中記錄「本文件取代 {舊文件 id}」
- [ ] 新文件的 L3 entity 已建立（`mcp__zenos__write`）
- [ ] 舊文件 frontmatter 已更新：`status: Superseded`
- [ ] 舊文件 frontmatter 已填寫 `superseded_by: {新文件 id}`
- [ ] 舊文件的 L3 entity 已更新狀態

**執行後驗證**
- [ ] Git diff 確認新文件已建立、舊文件已修改
- [ ] 搜尋舊文件 id，評估其他文件的引用是否需更新
- [ ] Git 文件狀態與 ontology entity 狀態一致

---

## 常見錯誤（禁止的反模式）

### NG-1：未查重就直接建新文件

```
# 錯誤做法
Write(file_path="docs/specs/SPEC-auth.md", ...)
# 正確做法：先執行階段一的 1a + 1b 步驟
```

### NG-2：Supersede 操作分批完成

```
# 錯誤做法
# 第一輪：只建新文件
# 第二輪：才去更新舊文件 frontmatter
# 正確做法：新建 + 舊文件更新必須在同一輪操作中原子完成
```

### NG-3：只改 Git 文件，不更新 ontology

```
# 錯誤做法
Edit(file_path="docs/specs/SPEC-xxx.md", ...)
# 完成後沒有呼叫 mcp__zenos__write
# 正確做法：每次 Git 文件變更都必須同步 ontology
```

### NG-4：修改 Approved 文件的決策方向

```
# 錯誤做法：直接編輯 Approved 文件的核心需求或決策段落
# 正確做法：開新文件 + Supersede 舊文件（路徑 C）
```

### NG-5：修改 ADR 正文

```
# 錯誤做法：Edit ADR 文件的決策內容
# 正確做法：任何 ADR 決策修改都必須開新 ADR
```

### NG-6：從 Approved 倒退回 Draft

```
# 錯誤做法：將 Approved 文件的 status 改為 Draft
# 正確做法：不可倒退。需要修改方向時，開新文件 + Supersede
```

### NG-7：復活已封存文件

```
# 錯誤做法：修改 Archived 或 Superseded 文件的狀態或內容
# 正確做法：若概念需要重新使用，建立新文件
```

### NG-8：ontology_entity: TBD 進入 Approved

```
# 錯誤做法：ontology_entity 為 TBD 的文件通過 Under Review → Approved
# 正確做法：Approved 前必須解決 TBD，或明文列為例外並有追蹤 task
```

---

## 文件正文模板

以下模板供 Agent 建立新文件時使用。frontmatter 規格見「階段三 → 路徑 A → 步驟 A1」。

### SPEC 模板

```markdown
# Feature Spec: {功能名稱}

## 背景與動機
為什麼要做這個功能？解決什麼問題？

## 目標用戶
誰會用？什麼場景？

## 需求

### P0（必須有）

#### {需求名稱}
- **描述**：{用戶視角的行為描述}
- **Acceptance Criteria**：
  - Given {前置條件}, When {操作}, Then {期望結果}

### P1（應該有）
### P2（可以有）

## 明確不包含
- {不做的事情}

## 技術約束（給 Architect 參考）
- {約束}：{原因}

## 開放問題
- {待釐清的問題}
```

### ADR 模板

```markdown
# ADR-{序號}: {決策標題}

## 背景
為什麼需要做這個決策？

## 決策
選了什麼？

## 考慮過的替代方案
| 方案 | 優點 | 缺點 | 為什麼不選 |
|------|------|------|-----------|

## 後果
這個決策帶來什麼影響？
```

**ADR 特殊規則**：ADR 序號在專案內全域唯一，不得重複使用。建立前先 `ls docs/decisions/` 確認最新序號。

### TD 模板

```markdown
# Technical Design: {功能名稱}

## 對應 Spec
{SPEC-* 文件路徑}

## Component 架構
{架構圖或說明}

## Schema / Migration（如涉及）
{SQL DDL 或說明}

## MCP Tool 介面（如涉及）
{tool 簽名 + 參數說明}

## 任務拆分
| 任務 | 負責 | Done Criteria |
|------|------|---------------|

## Spec 介面合約
| 介面 | 參數/行為 | Done Criteria 對應 |
|------|----------|--------------------|

## 風險與不確定性
{不確定的技術點}
```

### SKILL 模板

```markdown
# {Skill 名稱}

{一句話定位}

## 適用場景
{什麼時候 Agent 要載入這個 skill}

## 權威來源
{引用的 SPEC 文件路徑}

## 操作流程
{具體步驟和 MCP 呼叫}
```

---

## Ontology 同步 MCP 呼叫參考

建立或更新文件後，必須同步 ontology。以下為各操作的 MCP 呼叫模式：

### 建立 L3 document entity

```python
mcp__zenos__write(
    collection="documents",
    data={
        "title": "{文件標題}",
        "summary": "{一句話描述此文件的目標}",
        "status": "draft",
        "tags": {"what": ["{文件類型}", "{主題}"], "why": "{解決什麼問題}", "how": "{文件類型}", "who": ["{目標讀者}"]},
        "source": {"uri": "{GitHub URL 或相對路徑}", "label": "{檔名}", "type": "github"},
        "linked_entity_ids": ["{ontology_entity 對應的 L2 entity id}"]
    }
)
```

### 更新 L3 document entity

```python
mcp__zenos__write(
    collection="documents",
    id="{既有 entity id}",
    data={
        "status": "{新狀態}",
        # 只傳需要更新的欄位（局部更新語意）
    }
)
```

### Supersede：更新舊文件 entity

```python
mcp__zenos__write(
    collection="documents",
    id="{舊文件 entity id}",
    data={
        "status": "superseded",
        "details": {"superseded_by": "{新文件 id}"}
    }
)
```

### Archive：封存文件 entity

```python
mcp__zenos__write(
    collection="documents",
    id="{文件 entity id}",
    data={"status": "archived"}
)
```

---

## 與其他 skill 的關係

- **l2-knowledge-governance**：L2 概念操作。建立 L2 後，相關文件的 `ontology_entity` 應回填。
- **task-governance**：Task 治理。Task 完成後若產出文件，該文件必須走本 skill 合規流程。
- **knowledge-sync**：增量同步時偵測 Git 與 ontology 不一致，應按本 skill 修正。
- **SPEC-doc-governance**：本 skill 的唯一規則來源。本 skill 是 how，SPEC 是 what。
