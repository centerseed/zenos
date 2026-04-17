---
doc_id: ADR-039-l3-bundle-llm-dependency-removal
title: 決策紀錄：L3 Bundle 路徑移除 Server 端 LLM 依賴
type: DECISION
ontology_entity: L3 文件治理
status: Approved
version: "1.0"
date: 2026-04-17
supersedes: null
---

# ADR-039: L3 Bundle 路徑移除 Server 端 LLM 依賴

## Context

過去 7 天 Gemini API 故障，觀察到 L3 document bundle 相關路徑部分退化——雖然 `SPEC-document-bundle` D7 和「明確不包含」章節已明文寫「server 不引入 LLM 自動摘要依賴」，但實作上仍有 server 端呼叫 Gemini 的 code path（推測用於 doc entity summary 輔助、或 bundle_highlights 建議生成）。

問題本質：LLM 依賴應在 **agent 端**（使用者的 Claude / Gemini session，有完整 context 且成本由 caller 承擔），不是 **server 端**（成本由 ZenOS 承擔、有 rate limit 風險、故障會癱瘓所有客戶）。

User 質疑：L3 bundle 為什麼需要 Gemini？——這個質疑是對的。本 ADR 的工作是把 spec 層已經寫好的原則，落實到實作決策。

## Decision Drivers

- Spec 已明文 server 不做 LLM，實作必須對齊
- 單一 LLM provider 故障不得癱瘓治理關鍵路徑
- 把語意判斷留給 agent 端大模型，讓 server 保持低成本高穩定
- 需要保留「deterministic fallback」確保即使 agent LLM 不給 suggestion，bundle 仍能成立

## Decision

### D1. `bundle_highlights` 的建議值由 server deterministic 產生

Server 在 `write(add_source)` / `write(update_source)` 完成後，於 `suggestions` 欄位回傳 deterministic 計算的 `bundle_highlights_suggestion`：

- 若某 source `is_primary=true` → suggestion 裡該 source 的 `priority="primary"`
- 否則依 `doc_type` 分級：`SPEC` / `DECISION` → `primary`；`DESIGN` / `TEST` → `important`；其他 → `supporting`
- `headline` 從 source.label 或外部文件 H1 / frontmatter title 取（server 不做遠端拉取；以 caller 傳入的 metadata 為準）
- `reason_to_read` 留空，由 agent 端 LLM 決定填入什麼（這是唯一需要語意的欄位）

若同 bundle 已有 `bundle_highlights`，server 僅回傳 diff suggestion，不覆寫。

### D2. `change_summary` 由 agent 寫，server 不生成

與 ADR-022 D7 一致，server 不介入 change_summary 內容生成。server 責任僅限於：

- 維護 `summary_updated_at` / `highlights_updated_at` timestamp
- 超過 90 天未更新且期間有 source mutation → 在 `governance_hints.health_signal` 回 warning
- 在 `suggestions` 提醒 agent 需要更新

### D3. Doc entity summary / tags 由 agent 端 LLM 產生

`zenos-capture` 在建立新 L3 document entity 時，`summary` / `tags.why` / `tags.how` 這類需要語意濃縮的欄位，由 agent 端 LLM 在 capture 那一輪的 context 裡產生，塞進 `write(collection="documents")` 的 payload。

Server 端若仍有 Gemini 輔助 code path，降級為 **optional enrichment**（失敗時忽略，不阻擋 write）。主路徑不依賴 server LLM。

### D4. 不做 Gemini 故障 backfill

過去 7 天因 Gemini 故障而未生成 bundle_highlights / summary 的 document，不做批次 backfill。理由：

- Agent 在下一次 capture / sync 時會自然補齊
- Backfill 成本（逐個 document re-process + cross-LLM compatibility）遠高於效益
- ADR-022 D8（自然演進）已定性支持這種漸進修正

只在 `analyze(check_type="health")` 新增一項 KPI：`bundle_highlights_coverage`（有 highlights 的 index doc / 所有 index doc 比率），讓治理 review 可見缺口。

### D5. Server 端 LLM 依賴點列白名單

Server 端允許的 LLM 依賴點，僅限以下（均為 Agent-Powered Internal 或 Internal 飛輪，非關鍵路徑）：

- L2 三問判斷的語意閘（Flash Lite, 93% accuracy 的判斷 prompt）— 失敗時 degrade 為「接受 caller 的 boolean」
- Summary 腐化偵測的語意比對（Quality Intelligence 付費層）— 失敗時跳過該項檢查
- **不在白名單**：bundle_highlights 生成、change_summary 生成、doc entity summary 首次生成、任何 write 主路徑的阻擋性 LLM call

新增 server 端 LLM call 必須寫 ADR 評估，不得隱式進入主路徑。

## Consequences

### Positive

- Gemini / 任何單一 LLM provider 故障不再影響 L3 bundle 寫入
- Server 運營成本降低（bundle-related LLM call 歸零）
- Agent 端 caller 自然承擔 LLM 成本（符合商業模型）
- bundle_highlights 的 deterministic suggestion 比 LLM 生成更可預期、更好除錯

### Negative

- bundle_highlights 的 `reason_to_read` 只有在 agent 端 LLM 主動寫入時才有內容；若 caller 是輕量 MCP client（不帶 LLM），這欄位會空白
  - 緩解：Dashboard 顯示時對空 `reason_to_read` 套用 fallback「{doc_type} • {priority}」
- deterministic 排序可能誤判某個 `DESIGN` 其實比 `SPEC` 更值得先讀
  - 緩解：agent 端 LLM 可覆寫 suggestion

### Risks

- 實作時若沒確實把 server 端 Gemini call 清乾淨，仍會殘留關鍵路徑依賴
  - 緩解：`analyze(check_type="llm_health")` 列出 server 端所有 LLM 依賴點

## Follow-up

1. 修訂 `SPEC-document-bundle`：補 deterministic `bundle_highlights_suggestion` 的 AC
2. 修訂 `ADR-022`：D7 補強文字
3. 修訂 `SPEC-governance-observability`：新增 `analyze(check_type="llm_health")`
4. 實作：移除 server 端 bundle 路徑的 Gemini call（開 task）
5. 實作：deterministic `bundle_highlights_suggestion` 生成器（開 task）
