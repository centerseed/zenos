---
type: SPEC
id: SPEC-governance-guide-contract
status: Under Review
ontology_entity: governance-framework
created: 2026-04-17
updated: 2026-04-23
depends_on: SPEC-mcp-tool-contract, SPEC-ontology-architecture v2 §7, SPEC-task-governance, SPEC-doc-governance, SPEC-governance-framework
runtime_canonical:
  - src/zenos/interface/mcp/governance.py:29 (governance_guide)
  - src/zenos/interface/mcp/governance.py:15 (_VALID_TOPICS — derived from GOVERNANCE_RULES keys)
  - src/zenos/interface/governance_rules.py (GOVERNANCE_RULES dict — topic content source)
---

# Feature Spec: governance_guide 治理規則 SSOT 契約

> **SSOT note：** 本 spec 是 `governance_guide` MCP tool 與治理規則分發路徑的單一真相來源。依 `ADR-038-governance-ssot-convergence`，本 spec 為治理規則分發的權威 contract，優先於 `skills/governance/*.md`。

## 背景與動機

ZenOS 治理規則目前散落於 spec 文字、`skills/governance/*.md`、`skills/release/zenos-capture/SKILL.md`、server 端 `governance_rules.py` 四處。六個月內多次發生規則不同步造成的生產問題：

1. spec 改了但 skill 沒跟上 → agent 讀到舊規則
2. skill 改了但 server 驗證沒跟上 → 規則形同虛設
3. capture SKILL 內嵌規則與 document-governance.md 不一致 → debugger 難以定位

`SPEC-governance-framework` 已提出六層傳播契約，但沒明確指定哪一層是 SSOT。`ADR-038` 拍板：**`governance_guide` MCP tool 為治理規則唯一 SSOT**，local skills 降為人讀 reference。本 spec 把這個決定落實為可驗證的 contract。

## 目標

1. 定義 `governance_guide` tool 的 topic 清單、level 分層、輸入輸出 envelope
2. 定義「spec 修訂 → server rules 同步」的強制 gate
3. 定義 `skills/governance/*.md` 降級為 reference-only 的明文規則
4. 定義治理規則 SSOT 的 CI 稽核機制（不暴露 server runtime `analyze(check_type="governance_ssot")`）

## 非目標

- 不定義各 topic 的具體規則內容（仍由 `SPEC-*-governance.md` 擔任人讀權威）
- 不處理 Internal / Agent-Powered Internal 治理邏輯（見 `SPEC-governance-framework`）
- 不替代 `SPEC-mcp-tool-contract` 對 envelope 的通用規範；本 spec 只補 governance_guide 特有部分

## 需求

### P0-1: governance_guide 的 topic 清單

Server 端必須支援以下 topic（canonical：`src/zenos/interface/mcp/governance.py:15` 的 `_VALID_TOPICS`，其內容由 `src/zenos/interface/governance_rules.py` 的 `GOVERNANCE_RULES` dict keys 派生），每個 topic 至少要有 level 1 / 2 兩個層次的內容：

| topic | 對應的人讀 SPEC | 覆蓋的治理層 |
|-------|----------------|-------------|
| `entity` | `SPEC-ontology-architecture v2 §7`（L2 三問 + impacts gate + lifecycle + entries）| L2 知識節點 |
| `document` | `SPEC-doc-governance §§1-18` | L3-Document 基礎治理 |
| `bundle` | `SPEC-doc-governance §3`（doc_role / sources / bundle_highlights，2026-04-23 已吸收 SPEC-document-bundle）| L3-Document bundle-first 與路由規則 |
| `task` | `SPEC-task-governance` | L3-Action（Task / Plan / Milestone / Subtask）|
| `capture` | `skills/release/zenos-capture/SKILL.md` 的流程骨架 | Capture / Sync 流程 |
| `sync` | 同上 | 增量同步流程 |
| `remediation` | `SPEC-governance-feedback-loop` | 治理缺口修復流程 |

> 這個清單**可擴充但不可縮減**。新增治理模組時必須同步新增 topic + server rules content + 本表一行。
> Runtime 現行版本（canonical: `mcp/governance.py:71-79`）：entity 1.1 / document 2.2 / bundle 1.1 / task 2.0 / capture 1.1 / sync 1.0 / remediation 1.0。

#### Acceptance Criteria

- `AC-P0-1-1` Given agent 呼叫 `governance_guide(topic="bundle")`，When server 處理，Then 回傳 level 1 內容，內容涵蓋 bundle-first 原則、`doc_role=index` 預設、`bundle_highlights` 最低要求
- `AC-P0-1-2` Given agent 呼叫 `governance_guide(topic="unknown_topic")`，When server 處理，Then 回傳 `status="rejected"` + `data.error="UNKNOWN_TOPIC"`（Shape A flat，見 `SPEC-mcp-tool-contract §6.2`）+ `data.message` + `data.available_topics`（平鋪在 `data` root，**不是 `data.error.available_topics`**；canonical: `mcp/governance.py:58-63` + `_common.py:219-224`）
- `AC-P0-1-3` Given server 缺少 topic `bundle` 的內容，When server 啟動，Then 啟動流程失敗（不得帶缺 topic 上線）

### P0-2: level 分層

每個 topic 的內容分三層：

- `level=1`：流程概覽，~1k tokens，回答「這個治理模組做什麼、分幾階段、用哪些 tool」
- `level=2`：完整規則，~2-3k tokens，包含 checklist 與邊界條件（**預設**，不傳 level 時回這層）
- `level=3`：範例與模板，~3-5k tokens，好壞對照 + JSON payload

#### Acceptance Criteria

- `AC-P0-2-1` Given agent 呼叫 `governance_guide(topic="task")` 不帶 level，When server 處理，Then 回傳 level 2 內容
- `AC-P0-2-2` Given agent 呼叫 `governance_guide(topic="task", level=3)`，When server 處理，Then 回傳內容 token 數 ≥ level 2，且包含至少 1 個好範例 + 1 個壞範例
- `AC-P0-2-3` Given agent 呼叫 `governance_guide(topic="task", level=99)`，When server 處理，Then 回傳 `status="rejected"` + `data.error="INVALID_LEVEL"`（Shape A flat，`mcp/governance.py:64-69`）
- `AC-P0-2-4` Given level 1 內容 token 數 > 1500 或 level 2 > 4000 或 level 3 > 6000，When server 啟動時的自檢，Then log warning（不阻擋啟動，但進入 observability 指標）

### P0-3: 回傳 envelope

`governance_guide` 的回傳遵循 `SPEC-mcp-tool-contract` 的統一 envelope：

```json
{
  "status": "ok",
  "data": {
    "topic": "bundle",
    "level": 2,
    "content": "...markdown text...",
    "content_version": "2026-04-17T10:30:00Z",
    "content_hash": "sha256:..."
  },
  "warnings": [],
  "suggestions": [],
  "similar_items": [],
  "context_bundle": {},
  "governance_hints": {}
}
```

- `content_version`：server 端 `governance_rules.py` 最後修改時間（用於 client cache 判斷）
- `content_hash`：內容 SHA256，用於「此規則是否與上次讀到的相同」快速判斷

#### Acceptance Criteria

- `AC-P0-3-1` Given agent 呼叫 `governance_guide(topic="task")`，When server 處理成功，Then response 包含 `data.content` / `data.content_version` / `data.content_hash`
- `AC-P0-3-2` Given 同一 topic 的內容未變更，When 多次呼叫，Then 每次回傳的 `content_hash` 相同
- `AC-P0-3-3` Given spec 修訂導致 server rules 重新部署，When agent 呼叫同一 topic，Then 新 `content_hash` 與舊不同

### P0-4: 傳播 Gate — spec 修訂 → server rules 同步

依 ADR-038 D4，`SPEC-*-governance.md` 與 `SPEC-doc-governance`（2026-04-23 後 bundle 已併入此） / `SPEC-mcp-tool-contract` 等治理相關 spec 修訂時：

1. 同一 PR 必須修改 `src/zenos/interface/governance_rules.py` 對應 topic 的內容
2. 未同步的 PR 不得通過 CI
3. spec status 不得從 `Under Review → Approved`，除非 server rules 已部署且 `governance_guide(topic)` 回傳內容與 spec 文字一致

#### Acceptance Criteria

- `AC-P0-4-1` Given PR 修改 `SPEC-task-governance` 但未修改 `governance_rules.py["task"]`，When CI 執行，Then lint 步驟失敗並回報差異
- `AC-P0-4-2` Given spec 處於 `Under Review` 且 governance_rules.py 已同步，When reviewer 批准，Then 可轉 `Approved`
- `AC-P0-4-3` Given spec 處於 `Under Review` 且 governance_rules.py 未同步，When reviewer 嘗試轉 `Approved`，Then 治理流程（analyze / doc write）拒絕狀態轉換
- `AC-P0-4-4` Given 新增治理 topic（例如未來的 `plan`），When spec 新增該 topic 的規則，Then `governance_rules.py` 必須同步新增該 topic 的 level 1/2 內容，缺任一即 CI fail

### P0-5: local skill 降為 reference-only

`skills/governance/*.md`（`capture-governance.md`、`document-governance.md`、`l2-knowledge-governance.md`、`task-governance.md`、`shared-rules.md`）以及 `skills/release/zenos-capture/SKILL.md`：

- 頭部必須加標示：

  ```markdown
  > **Reference only.**
  > SSOT: `governance_guide(topic="...", level=2)` via MCP.
  > This file is a human-readable mirror and MAY LAG the SSOT.
  > Agents must call governance_guide before acting on rules.
  ```

- 規則細節允許與 SSOT 同步，但不再是 reject 條件；修訂 SSOT 時不強制同步這些 md
- zenos-setup 仍安裝這些檔案（給人讀），但 agent runtime 不得引用它們作為治理依據

#### Acceptance Criteria

- `AC-P0-5-1` Given `skills/governance/task-governance.md` 不含 reference-only 標示，When CI lint，Then 失敗
- `AC-P0-5-2` Given agent skill（如 architect/pm/zenos-capture）內的治理判斷步驟，When 讀取 skill 內容，Then 步驟明確要求先 call `governance_guide`，不得直接引用 local skill 內容做判斷
- `AC-P0-5-3` Given `skills/release/zenos-capture/SKILL.md` 行數，When 砍檔完成，Then 行數 < 200（follow-up task）

### P0-6: SSOT 稽核 — CI-only lint

SSOT 漂移檢查保留，但**只在 CI / 測試環境執行**，不再作為 server runtime analyze check：

- 比對 `governance_rules.py` 每個 topic 的內容，與對應 spec 文字的主要規則區塊
- 比對 `skills/governance/*.md` 是否含 reference-only 標示
- 比對 `skills/release/zenos-capture/SKILL.md` 是否 < 200 行
- 允許用 `scripts/lint_governance_ssot.py`、pytest，或等價的 CI lint 實作

設計原則：

- production server 不再嘗試讀取 repo filesystem 來做 SSOT audit
- `governance_ssot` 不進 `analyze(check_type="health" | "all")` 的 health KPI
- drift 屬於發版前契約問題，應在 CI fail，而不是在線上 runtime 才發現

#### Acceptance Criteria

- `AC-P0-6-1` Given server rules 與 spec 差異超過純格式，When CI lint 執行，Then fail 並回報 drift summary
- `AC-P0-6-2` Given `skills/governance/*.md` 缺少 reference-only 標示，When CI lint 執行，Then fail 並指出缺標示檔案
- `AC-P0-6-3` Given 所有 SSOT 層同步，When CI lint 執行，Then lint pass
- `AC-P0-6-4` Given caller 呼叫 `analyze(check_type="governance_ssot")`，When server runtime 處理，Then 回傳 `INVALID_INPUT`

### P1-1: content_hash 快取機制

Client（agent / dashboard）可透過 `content_hash` 判斷是否需要重新展示：

- 若 client 已有該 topic+level 的快取，傳入 `If-None-Match: <hash>` 等價的查詢參數 `since_hash`
- server 若 hash 未變，回傳 `status="ok"`, `data={topic, level, unchanged: true}`，不重複傳整份 content

#### Acceptance Criteria

- `AC-P1-1-1` Given client 傳入 `since_hash=<當前 hash>`，When 內容未變，Then 回傳 `data.unchanged=true`，content 欄位省略
- `AC-P1-1-2` Given client 傳入 `since_hash=<過期 hash>`，When server 處理，Then 回傳完整 content + 新 hash

### P2-1: topic 之間的 cross-ref

level 2/3 內容中，引用其他 topic 時必須用統一標記：

```
{{governance_guide:document#P0-1}}
```

agent 端可選擇是否展開該引用（避免 payload 無限展開）。

---

## 明確不包含

- 不自動從 `SPEC-*-governance.md` markdown 解析生成 server rules（手工同步以保證規則 literal 正確）
- 不提供 content 的「寫入」API——governance_rules.py 只能由 PR 修改
- 不處理 Internal / Agent-Powered Internal 規則的暴露（那不屬於 External 層，見 `SPEC-governance-framework`）

## 技術約束

- 本 spec 的實作依賴 `SPEC-mcp-tool-contract` 的 envelope 規範
- `governance_ssot` 不再是 Base Layer analyze tool 的 runtime check type
- CI lint 的 spec↔server_rules diff 機制可用 pytest、獨立 lint script 或 GitHub Action，實作由 Architect 決定

## 與其他文件的關係

| 文件 | 關係 |
|------|------|
| `ADR-038-governance-ssot-convergence` | 本 spec 落實 ADR-038 的決策 |
| `SPEC-governance-framework` | 本 spec 是 framework 第三層（server 驗證）的 contract |
| `SPEC-mcp-tool-contract` | 本 spec 擴充 mcp contract 對 governance_guide 的定義 |
| `SPEC-*-governance.md` | 人讀權威；本 spec 管理它們如何傳播到 server rules |
| `skills/governance/*.md` | 降級為 reference-only；本 spec 定義降級規則 |

## 完成定義

1. `governance_guide` 的 7 個 topic 全部有 level 1/2 內容（level 3 為 P1）
2. CI lint 啟用 spec↔server_rules diff 檢查
3. 所有 `skills/governance/*.md` 含 reference-only 標示
4. `skills/release/zenos-capture/SKILL.md` < 200 行
5. CI lint / 測試已覆蓋 governance SSOT drift，且 production server 不再暴露 `analyze(check_type="governance_ssot")`
