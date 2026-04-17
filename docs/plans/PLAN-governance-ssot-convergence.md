---
spec:
  - docs/specs/SPEC-governance-guide-contract.md
  - docs/specs/SPEC-governance-framework.md
  - docs/specs/SPEC-governance-observability.md
  - docs/specs/SPEC-document-bundle.md
  - docs/specs/SPEC-doc-governance.md
  - docs/specs/SPEC-mcp-tool-contract.md
  - docs/specs/SPEC-task-governance.md
adr:
  - docs/decisions/ADR-038-governance-ssot-convergence.md
  - docs/decisions/ADR-039-bundle-highlights-deterministic.md
  - docs/decisions/ADR-022-governance-runtime-enforcement.md
plan_id: c107b751208447e6886751e33b87ef9d
created: 2026-04-17
status: draft
---

# PLAN: Governance SSOT Convergence

把治理規則的權威位置從「三地分裂（governance_rules.py / skills/release/zenos-capture / skills/governance/）」收斂成 server `governance_guide` 單一 SSOT；並且修復 LLM 依賴鏈（Gemini 7 天壞零告警、bundle 主路徑依賴 LLM），讓治理 KPI 從 45 回到 70+。

## 背景

上一輪盤點（2026-04-17）發現三個瓶頸：

1. **Gemini 壞 7 天零告警**：`governance_guide` 呼叫 Gemini → `genai_key=None` → 每次 silent fallback，`quality_score=45`、capture 膨脹到 1470 行沒人發現。
2. **SSOT 三地分裂**：同一條治理規則同時存在 server rules、capture skill、governance 目錄，改一處漏兩處。
3. **L2↔L3 斷鏈**：4 個 L2 impact_chain 指向已刪除的 L3，14 份 document 沒有 linked_entity_ids。

用戶於 2026-04-17 拍板：SSOT 選方案 A（`governance_guide` server 端為唯一 SSOT）、不 backfill Gemini、L3 bundle 主路徑拔 LLM 依賴。

## 目標（量化）

| 指標 | 現況 | 目標 | 驗證方式 |
|------|------|------|----------|
| `analyze(system_health)` quality_score | 45 | ≥ 70 | MCP analyze 輸出 |
| `governance_guide` quality_score 失敗項 | 8 | < 3 | MCP analyze 輸出 |
| `skills/release/zenos-capture/SKILL.md` 行數 | 1470 | < 400 | `wc -l` |
| bundle 主路徑 LLM 依賴點 | 2（ADR-039 Follow-up 1,4）| 0 | grep `GeminiClient` in bundle_service |
| L2→L3 斷鏈 impacts | 4 | 0 | `analyze(check_type="ontology_integrity")` |
| 孤兒 document（無 linked_entity_ids）| 14 | 0 | SQL `SELECT count(*) FROM zenos.documents WHERE linked_entity_ids IS NULL OR array_length(...)=0` |
| Cloud Run GeminiException / 7 天 | 數百次 silent | 0（有告警並修復）| Cloud Logging |
| `governance_rules.py` ↔ spec 同步 | 無檢查 | CI lint 綠 | CI job |

---

## 階段 1：止血（P0 並行，~1 週）

**目的**：讓可觀測性恢復，治理不再 silent fail。

### Entry criteria
- SPEC-governance-guide-contract.md、SPEC-governance-observability.md 第八章已合併
- ADR-038、ADR-039 approved

### 交付
- T-01 `governance_guide` content_hash / since_hash 機制 — 對應 SPEC-governance-guide-contract.md AC-P0-1-1~AC-P0-3-3
- T-02 `analyze(check_type="llm_health")` 靜態掃描 — 對應 SPEC-governance-observability.md 第八章 AC-obs8-1~5
- T-03 Gemini `genai_key=None` root cause 修復（ops bug，無 spec）— done = Cloud Logging 連續 7 天 0 次 GeminiException
- T-04 `find_gaps` `'Entity' object has no attribute 'product'` regression 修復

### Exit criteria
- `analyze(check_type="llm_health")` 可偵測到「7 天內 X% 呼叫走 fallback」
- Cloud Run 連續 3 天無 GeminiException（若修 key 不成功，至少 llm_health 能主動顯示 fallback 率並 warning）
- `governance_guide` 回傳新增 `content_hash` 欄位，agent 可用 `since_hash` 做增量

---

## 階段 2：拔 LLM 依賴 + 修斷鏈（P1，~1.5 週）

**目的**：讓 bundle 主路徑不依賴 LLM，把 14 份孤兒 document 重新連回 ontology。

### Entry criteria
- 階段 1 T-01、T-02 已部署 production
- ADR-039（deterministic highlights）approved

### 交付
- T-05 實作 deterministic `bundle_highlights_suggestion` 生成器 — 對應 SPEC-document-bundle.md AC-P0-12 系列
- T-06 移除 server bundle 主路徑 Gemini call — 對應 ADR-039 Follow-up 4
- T-07 `write(documents)` linked_entity_ids required + reject code — 對應 SPEC-doc-governance.md AC-linked-1~3
- T-08 批量修復 4 個 L2 impacts 斷鏈 + 14 份孤兒 document

### Exit criteria
- bundle_service 主路徑 `grep -r "GeminiClient\|gemini" src/zenos/application/bundle*` 回傳 0 行（或只剩 opt-in re-rank 的註解區塊）
- `write(documents, linked_entity_ids=[])` 回傳 reject code（非 silent accept）
- `analyze(check_type="ontology_integrity")` 報告 broken impact chains = 0
- quality_score 預期從 45 升到 60+

---

## 階段 3：SSOT 收斂（P2，~2 週）

**目的**：把治理規則的權威位置完全收斂到 server，skills 變 reference-only。

### Entry criteria
- 階段 1、2 已上線，KPI 未退化
- 已建立 `governance_rules.py` 的 spec-of-truth 對照表（T-09 前置調研）

### 交付
- T-09 CI lint: spec ↔ governance_rules.py 同步檢查 — 對應 SPEC-governance-guide-contract.md AC-P0-4-1~4
- T-10 實作 `analyze(check_type="governance_ssot")` — 對應 AC-P0-6-1~3
- T-11 砍 `skills/release/zenos-capture/SKILL.md` 到 < 400 行，並於 `skills/governance/` 所有文件加 reference-only header 指向 `governance_guide`

### Exit criteria
- 改治理規則只需要改 `governance_rules.py` + 對應 spec，CI lint 自動 fail 缺一邊的 PR
- capture skill 行數 < 400
- `analyze(check_type="governance_ssot")` 回傳 no divergence

---

## 階段 4：量化治理成效（P3，~0.5 週）

**目的**：把 bundle 品質接入可觀測迴圈，避免再次 silent degradation。

### Entry criteria
- 階段 2、3 已上線

### 交付
- T-12 實作 `bundle_highlights_coverage` KPI — 對應 SPEC-document-bundle.md AC-P0-14

### Exit criteria
- analyze KPI 面板可顯示 bundle highlights coverage %
- 月底覆盤以此指標衡量 bundle 健康度

---

## 依賴圖

```
T-01 ┐
T-02 ├→ T-05 ┐
T-03 ┘       ├→ T-06 ┐
T-04         │       ├→ T-09 ┐
             T-07 ┐   │       ├→ T-10 ┐
             T-08 ┘   │       │       ├→ T-11 ┐
                      │       │       │       ├→ T-12
                      └───────┴───────┴───────┘
階段 1 並行 → 階段 2 並行（T-05/06 與 T-07/08 兩軌）→ 階段 3 → 階段 4
```

## 風險與回滾

| 風險 | 可能性 | 衝擊 | 緩解 / 回滾 |
|------|--------|------|-------------|
| Gemini key 修復卡住（可能是 secret rotation policy）| 中 | 中 | T-02 的 llm_health 獨立可交付，即使 key 沒修好也能 warn |
| deterministic highlights 品質 < Gemini | 中 | 高 | T-05 保留 feature flag `ZENOS_BUNDLE_HIGHLIGHTS_MODE=deterministic\|llm\|off`，可 rollback；T-12 覆蓋率 KPI 做量化比較 |
| 14 份孤兒 document 無法自動判斷該連到哪 | 中 | 低 | T-08 優先做「自動推薦候選 + 人工 confirm」，不硬 batch link |
| capture skill 拆解後 breaking change | 低 | 中 | T-11 分兩步：先加 reference-only header（向後相容），觀察 1 週，再砍舊內容 |
| CI lint 太嚴導致 PR 被阻塞 | 低 | 低 | T-09 先 `warn-only` 1 週，再改 block |

## 時程估計

| 階段 | 估計 | 備註 |
|------|------|------|
| 階段 1 | 5–7 工作日 | 4 task 並行 |
| 階段 2 | 7–10 工作日 | T-05/06 需驗證 highlights 品質 |
| 階段 3 | 10–14 工作日 | T-11 容易卡 review |
| 階段 4 | 2–3 工作日 | 純 analytics |
| **總計** | **~5 週** | 不含 review 迴圈 |

## Decisions

- 2026-04-17: PLAN 建立。SSOT 採方案 A（server `governance_guide` 唯一 SSOT），不 backfill Gemini，bundle 主路徑拔 LLM。

## Resume Point

尚未啟動。建議從 T-01（content_hash）或 T-03（Gemini root cause）開始——兩者都是其他階段的前置依賴。
