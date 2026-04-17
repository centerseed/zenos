---
doc_id: ADR-038-governance-ssot-convergence
title: 決策紀錄：治理規則 SSOT 收斂到 governance_guide server tool
type: DECISION
ontology_entity: 知識治理框架
status: Approved
version: "1.0"
date: 2026-04-17
supersedes: null
---

# ADR-038: 治理規則 SSOT 收斂到 governance_guide server tool

## Context

ZenOS 治理規則目前同時存在多處：

1. `docs/specs/SPEC-*-governance.md`（spec 權威文字）
2. `skills/governance/*.md`（人讀 + agent 讀的執行手冊）
3. `skills/release/zenos-capture/SKILL.md`（內嵌治理規則與流程）
4. `src/zenos/interface/governance_rules.py`（server 端，供 `governance_guide` MCP tool 回傳）

這四處之間缺少 SSOT 紀律——過去 6 個月發生過多次「改了 spec 忘了改 skill」「改了 skill 忘了改 server rules」「capture SKILL 內嵌規則與 document-governance.md 不一致」的情況。`SPEC-governance-framework` 的傳播契約已指出六層傳播要求，但實務上沒有明確哪一層才是 SSOT，結果是 caller（agent）拿到的規則不穩定。

User pain：7 天內 Gemini 故障導致 L3 bundle 路徑退化時，回頭看治理規則才發現：agent 讀 local skill，server 端驗證讀 governance_rules.py，兩邊規則差一條，debugger 花了 2 小時才定位。

## Decision Drivers

- 治理規則變更時必須有唯一且動態可發布的源頭，不能靠 git merge 同步多份文字
- agent 層（Claude / Gemini / 其他 MCP client）不應該需要下載 local skill 才能取得規則
- skill 文件仍有閱讀價值（人讀 reference），不應強制刪除
- 必須可被 analyze 稽核：當 SSOT 變更後，還有哪些 local 副本未同步

## Decision

### D1. `governance_guide` MCP tool 為治理規則唯一 SSOT

所有 agent-facing 治理規則（External 類，對應 `SPEC-governance-framework` 的外部開放層）一律以 `governance_guide(topic, level)` 回傳內容為準。

- agent 執行治理流程前，**必須**先 call `governance_guide(topic)`，不得假設 local skill 是最新版
- spec 文字（`SPEC-*-governance.md`）仍是人讀權威；但 spec 修訂後必須在同一輪更新 `src/zenos/interface/governance_rules.py`，否則 spec 不得從 `Under Review → Approved`
- `skills/governance/*.md` 和 `skills/release/zenos-capture/SKILL.md` 降為 **人讀 reference**，明文標示「SSOT is governance_guide; this file is a human-readable mirror, may lag」

### D2. governance_rules.py 的結構與規則

- 由新增的 `SPEC-governance-guide-contract` 定義 topic 清單、level 分層、envelope
- server 端規則以 Python literal 形式維護，避免 markdown 解析不穩
- 每次 spec 修訂 PR 必須同步改 `governance_rules.py`，CI 增加 lint：`governance_rules.py` 必須列全 `topics = {entity, document, task, capture, sync, bundle, remediation}`

### D3. local skill 的降級規則

- `skills/governance/*.md` 保留，但：
  - 頭部加標示：`> Reference only. SSOT: governance_guide(topic). This file may lag.`
  - 不再於 spec 修訂時強制同步這些 md
  - zenos-setup 仍會安裝這些 md，但 skill 裡面不再做治理判斷，而是指引 agent 去 call `governance_guide`
- `skills/release/zenos-capture/SKILL.md` 砍到 <200 行（本 ADR 的 follow-up task），保留流程骨架，規則全部動態 pull

### D4. 傳播契約強化

`SPEC-governance-framework` 的六層傳播契約，以下兩層變為**強制 reject gate**（spec 無法 Approved，除非這兩層同步）：

- Layer 2（Server 驗證）：governance_rules.py 已更新
- Layer 3（governance_guide 內容）：`governance_guide(topic)` 回傳已反映新規則

其餘四層仍為 checklist 但非 reject。

### D5. Gemini 修好後不 backfill 這 7 天

ZenOS 過去 7 天因 Gemini 故障導致 L3 bundle 路徑部分退化，本決策**不做歷史 backfill**。理由：(a) 退化期間的 bundle 沒有產生錯誤資料，只是 `bundle_highlights` 稍微晚更新；(b) backfill 需要對歷史 document 逐個 re-process，成本遠高於讓 agent 在下次 capture/sync 時自然更新；(c) `SPEC-document-bundle` 的自然演進原則（D8）本來就接受漸進修正。

## Consequences

### Positive

- Agent 取得的治理規則永遠是最新的（動態 pull），不依賴 skill 安裝版本
- Spec 變更的傳播路徑從「6 層」壓到「2 層 hard gate + 4 層 soft checklist」
- 減少 SKILL.md 膨脹（zenos-capture 預計從 ~650 行砍到 <200 行）
- Gemini / LLM 故障不再影響治理規則取得路徑（governance_guide 是純 string dispatch）

### Negative

- agent 每個 session 要多 call 幾次 governance_guide（~2-3k tokens/topic），不過比起每次載入 15k+ tokens 的 local skill 划算
- 修治理規則的 PR 必須同步改 Python code，對 PM / 非工程師稍微提高門檻
- 舊 session 若依賴 local skill 內嵌規則，升級後會觀察到行為差異（須一次性公告）

### Risks

- 若 governance_rules.py 與 SPEC 文字不同步，比現況更糟（spec 說一套、server 回一套）→ 由 CI lint + `analyze(check_type="governance_ssot")` 雙重把關
- Agent 可能誤以為 local skill 是 SSOT 而不 call governance_guide → 在 skill 頭部的 reference-only 標示必須顯眼

## Follow-up

1. 建立 `SPEC-governance-guide-contract`（本輪同時產出）
2. 修訂 `SPEC-governance-framework`：Layer 2 / Layer 3 升格為 reject gate
3. 修訂 `SPEC-mcp-tool-contract`：為 `governance_guide` 補完整介面定義
4. 修訂 `SPEC-task-governance` / `SPEC-doc-governance`：local skill 降為 reference-only
5. 砍 `skills/release/zenos-capture/SKILL.md` 到 <200 行（開 task）
6. `skills/governance/*.md` 頭部加 reference-only 標示（開 task）
7. CI lint：spec 修訂 PR 檢查 `governance_rules.py` 同步
