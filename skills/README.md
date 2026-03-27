# ZenOS Skills

ZenOS 的治理能力與操作流程。任何 AI agent 都可以讀取這些 skill 來獲得 ZenOS 治理能力。

---

## 我要做什麼？→ 載入哪個 skill

| 你要做的事 | 載入這個 skill | 路徑 |
|-----------|--------------|------|
| 寫 SPEC、ADR、TD 或任何正式文件 | **文件治理** | `governance/document-governance.md` |
| 建立或審查 L2 知識節點（公司共識概念） | **L2 知識治理** | `governance/l2-knowledge-governance.md` |
| 建票、管票、驗收任務 | **Task 治理** | `governance/task-governance.md` |
| 第一次把專案知識匯入 ZenOS | **知識擷取** | `workflows/knowledge-capture.md` |
| 專案有新 commit，同步 ontology | **知識同步** | `workflows/knowledge-sync.md` |
| 第一次接上 ZenOS MCP | **初始設定** | `workflows/setup.md` |
| 全面治理掃描 + 自動修復 | **治理閉環** | `workflows/governance-loop.md` |

---

## 怎麼讓 agent 用這些 skill？

### 方法 1：直接餵給 agent

在 agent 的 system prompt 或對話開頭加入：

```
在開始工作前，讀取以下技能定義並嚴格遵循：

[必選] skills/governance/document-governance.md — 寫任何正式文件前必讀
[按需] skills/governance/l2-knowledge-governance.md — 涉及 L2 知識節點操作時
[按需] skills/governance/task-governance.md — 需要建票或管票時

讀完後按照技能中的流程執行。ZenOS ontology 操作使用 ZenOS MCP tools。
```

適用於：ChatGPT Custom GPT、Codex、Gemini、自建 agent、任何能讀文字的 LLM。

### 方法 2：Claude Code 用戶

ZenOS 專案的 `.claude/skills/` 已設定好薄殼，輸入 `/zenos-capture`、`/zenos-sync` 等指令會自動導向這裡的 SSOT。

### 方法 3：組合使用

一個 agent 可以同時掛載多個 skill。常見組合：

| 場景 | 載入組合 |
|------|---------|
| PM 寫 spec | `document-governance` + `task-governance` |
| Architect 做技術設計 | `document-governance` + `l2-knowledge-governance` + `task-governance` |
| 首次建構 ontology | `knowledge-capture` + `l2-knowledge-governance` + `document-governance` |
| 日常 commit 後同步 | `knowledge-sync` |
| 治理巡邏 | `governance-loop`（會自動引用其他 governance skill） |

---

## 每個 skill 的觸發時機

Agent 讀到這些關鍵字時，應主動載入對應 skill：

| 關鍵字 / 意圖 | 對應 skill |
|--------------|-----------|
| 「寫 spec」「建文件」「開 ADR」「寫 TD」 | `document-governance` |
| 「這個概念是不是 L2」「三問」「impacts」「升級為 confirmed」 | `l2-knowledge-governance` |
| 「開票」「建 task」「驗收」「linked_entities 怎麼掛」 | `task-governance` |
| 「capture」「建構 ontology」「掃描專案」 | `knowledge-capture` |
| 「sync」「同步」「git 變更」 | `knowledge-sync` |
| 「設定 ZenOS」「接 MCP」「API token」 | `setup` |
| 「治理掃描」「品質分數」「修復 ontology」 | `governance-loop` |

---

## Skill 與 Spec 的分工

| | Spec（`docs/specs/`） | Skill（`skills/`） |
|---|---|---|
| **回答** | 應該做什麼、為什麼 | 怎麼做、步驟是什麼 |
| **讀者** | PM、Architect、人類審查者 | Agent（任何 LLM） |
| **例子** | 「Approved 前 ontology_entity 不得為 TBD」 | 「Step 3c: 若 ontology_entity == TBD，開追蹤 task」 |

每個 governance skill 都標註了它的權威 Spec 來源。若 skill 與 spec 有衝突，以 spec 為準。

---

## 新增 skill 規範

1. 放在 `governance/`（治理規則）或 `workflows/`（操作流程）
2. 必須有 frontmatter：`type: SKILL`、`id`、`status`、`ontology_entity`、`created`、`updated`
3. 開頭標明「權威來源」指向對應的 Spec
4. 具備「適用場景」段落，讓 agent 知道何時該載入
5. 功能與現有 skill 重疊時，修改現有 skill，不另開新 skill
