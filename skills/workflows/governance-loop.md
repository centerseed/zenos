---
type: SKILL
id: governance-loop
status: Draft
ontology_entity: TBD
created: 2026-03-27
updated: 2026-03-27
---

> 權威來源：本文件是 `zenos-governance` 治理總控流程的 SSOT。
> `.claude/skills/zenos-governance/SKILL.md` 為舊格式，以本文件為準（本文件為 `skills/workflows/governance-loop.md`）。

# governance-loop — 治理總控閉環

你是 ZenOS 治理總控 agent。目標不是「產生建議」，而是「把治理跑完」。

> 本 skill 統籌三個子流程，各自的詳細規則見：
> - L2 概念節點建立與 impacts 撰寫：`skills/governance/l2-knowledge-governance.md`
> - 文件 entry 治理合規規則：`skills/governance/document-governance.md`
> - 任務建立與狀態管理：`skills/governance/task-governance.md`（若有）

---

## 0) 執行原則

- 優先自動化：可推斷就不要問人。
- 先結構後內容：先修 entity/relationship，再修摘要與標籤。
- 增量優先：除首次建構外，禁止重複全量掃描。
- 任務閉環：治理問題要轉成 task，交付後用 confirm 驗收。

---

## 1) 觸發條件

用戶有以下意圖時啟用本 skill：

- 「接好 ZenOS 後讓 agent 自動跑治理」
- 「掃描完結果不滿意，幫我重整」
- 「現有 Git 專案怎麼持續治理」
- 「不要人工操作，讓 agent 自己做」

---

## 2) 路由決策（必做）

按順序判斷：

1. 尚未接 MCP 或 token 不可用
   - 呼叫 `setup` 流程。
2. 已接 MCP，但該專案從未建庫
   - 呼叫 `knowledge-capture <repo_path>` 做首次建構。
3. 已有 ontology，且專案以 Git 持續演進
   - 呼叫 `knowledge-sync` 做增量同步。
4. 用戶表達「結果不滿意 / 太亂 / 結構不對」
   - 走第 4 節「二次治理迭代」。

---

## 3) 標準治理循環（每次都跑）

1. 盤點現況
   - `analyze(check_type="quality")`
   - `analyze(check_type="staleness")`
   - `analyze(check_type="blindspot")`
2. 分類問題
   - 結構問題：命名混亂、L1/L2 掛錯、孤兒節點、關聯缺失。
   - 內容問題：summary 技術噪音、tags 不完整、文件重複。
   - 流程問題：治理動作沒 task、完成後沒 confirm。
3. 轉任務
   - 每類問題至少建一張 task，必填 acceptance criteria。
4. 執行修復
   - 結構修復：`write(entities/relationships)`
   - 文件修復：`write(documents)` 或 append_sources
5. 驗收回寫
   - task 進 review 後 `confirm(collection="tasks", accepted=true)`
   - 必要時 `mark_stale_entity_ids` 或新增 blindspot。

---

## 4) 二次治理迭代（掃描結果不滿意時）

### 4.1 固定順序

1. 鎖定範圍
   - 只處理最近變更涉及的模組與文件；不要全庫重掃。
2. 重整 L2
   - 先統一 L2 命名規則，再批量修正 `name/parent_id/type`。
   - L2 三問判斷見 `skills/governance/l2-knowledge-governance.md`。
3. 補關聯
   - 每個核心 L2 至少一條高價值 relationship（優先 impacts/depends_on）。
4. 文件降噪
   - 低價值文件轉 stale 或只保留 source，不建立獨立節點。
   - 文件降噪判斷標準見 `skills/governance/document-governance.md`。
5. 最後才修文案
   - 統一 summary/tags 語言，避免先改文案後又被結構改動推翻。

### 4.2 驗收門檻（預設）

- 孤兒節點 = 0
- 重複/歧義命名顯著下降（由 analyze quality 反映）
- 核心 L2 皆有關聯
- 治理任務全部進入 review 或 done

---

## 5) Git 專案的日常治理節奏

- Day 0：`knowledge-capture <repo>` 建立基線。
- 之後每次一批 commits：`knowledge-sync`。
- 每週固定一次：`analyze(all)` + 任務化治理。
- 重大架構變更：針對變更目錄再跑一次 `knowledge-capture <changed_dir>`。

---

## 6) 跨模型通用輸出格式

不論 Claude / ChatGPT / Gemini，都用同一回報格式：

```text
[Governance Status]
- Scope: <repo/module>
- Mode: bootstrap | incremental | remediation
- Quality: <score>/100
- Key Issues: <top 3>

[Actions Executed]
1) <tool call + target>
2) <tool call + target>

[Tasks Created/Updated]
- <task id>: <title> | <status> | <acceptance criteria>

[Next Gate]
- <what must be true before next run>
```

---

## 7) 防呆規則

- 沒有 MCP 連線時，不得假裝治理完成。
- 不能只給建議不落地；至少要建立對應 task。
- `status=done` 不能直接 update，必須走 confirm 驗收。
- 找不到答案時先 `search/get`，不要憑空生成 entity。

---

## 8) 與其他 workflow skills 的關係

- `setup`：處理連線與憑證。
- `knowledge-capture`：首次建構或重大變更重建。
- `knowledge-sync`：Git 增量同步。
- `governance-loop`（本 skill）：統籌決策、修復順序、任務閉環與驗收。
