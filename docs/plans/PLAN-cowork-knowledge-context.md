---
spec: SPEC-cowork-knowledge-context.md
design: DESIGN-cowork-knowledge-context.md
created: 2026-04-17
status: in-progress
---

# PLAN: Web Cowork 活用知識圖譜的欄位級漸進預填

## Entry Criteria

- SPEC-cowork-knowledge-context status=draft，AC-CKC-01~64 已定義且有 ID
- DESIGN-cowork-knowledge-context 已產出，含 AC Compliance Matrix + Done Criteria
- SPEC-marketing-automation 與 SPEC-crm-intelligence 已補充對應 AC（AC-MKTG-STRATEGY-10~13, AC-CRM-BRIEF-20~22）
- AC test stubs 已建立：
  - `tests/spec_compliance/test_cowork_knowledge_context_ac.py`（27 個 stub）
  - `dashboard/src/__tests__/cowork_knowledge_context_ac.test.ts`（20 個 stub）

## Exit Criteria

- 所有 P0 AC（AC-CKC-01~42）對應 test 從 FAIL 變 PASS
- Paceriz demo 影片交付（涵蓋 AC-CKC-63 四項可視證據）
- L1-only fallback 驗證通過（SME 製造業自動化橋樑 或同等 L1-only 產品）
- 部署到 Firebase Hosting 後 `/api/cowork/graph-context` 實際回應 200 + 非空 neighbors
- Architect 雙階段交付審查（Spec Compliance + Code Quality）通過
- 本 PLAN status=done，journal 寫入

## Tasks

- [ ] **S01**: 實作 Dashboard API `/api/cowork/graph-context` 遍歷 + token budget
  - Files: `dashboard/src/app/api/cowork/graph-context/route.ts`（新）、`dashboard/src/lib/zenos-mcp-client.ts`（如需新增）
  - Verify: `pytest tests/spec_compliance/test_cowork_knowledge_context_ac.py::test_ac_ckc_05 ...13 ...40 -x` PASS；curl localhost 實測 Paceriz seed 回應 + 附實測 token 數報告

- [ ] **S02**: 前端 graph-context client + cowork-helper.ts event 型別擴充 (depends: S01)
  - Files: `dashboard/src/lib/graph-context.ts`（新）、`dashboard/src/lib/cowork-helper.ts`（改 `CoworkStreamEvent`）
  - Verify: `npx vitest run src/__tests__/cowork_knowledge_context_ac.test.ts` AC-CKC-03/04/14/15 PASS；tsc 無錯誤

- [ ] **S03**: CoworkChatSheet 改裝（pre-fetch + prompt inject + 10 輪）+ helper maxTurns 10 (depends: S01, S02)
  - Files: `dashboard/src/components/CoworkChatSheet.tsx`（改）、`dashboard/public/installers/claude-code-helper/server.mjs:629`（改 `6` → `10`）
  - Verify: AC-CKC-01/02/35 vitest PASS；手動開啟 sheet 觀察首輪前有 graph_context_loaded event

- [ ] **S04**: GraphContextBadge component (可並行)
  - Files: `dashboard/src/components/GraphContextBadge.tsx`（新）、vitest snapshot
  - Verify: AC-CKC-20/21/22/23 vitest PASS

- [ ] **S05**: Prompt template + apply 契約驗證 + 漸進規則 (depends: S03)
  - Files: `dashboard/src/lib/cowork-prompt.ts`（新）、`dashboard/src/lib/cowork-apply.ts`（新）
  - Verify: AC-CKC-30/31/32/33/34/41/42 vitest PASS

- [ ] **S06**: Marketing 策略「討論這段」wiring + apply 寫回 ZenOS (depends: S05)
  - Files: `dashboard/src/app/marketing/projects/[id]/*.tsx`（改，具體檔案以實際結構為準）、`dashboard/src/lib/marketing-api.ts`（可能改）
  - Verify: AC-MKTG-STRATEGY-10~13 + AC-CKC-55/56 vitest PASS；手動 Paceriz 官網 Blog 端到端 7 欄位

- [ ] **S07**: CRM Briefing「產品現況」走本 flow + Badge 顯示 (depends: S05)
  - Files: `dashboard/src/app/clients/deals/[id]/DealDetailClient.tsx`（改）、briefing chat component（改）
  - Verify: AC-CRM-BRIEF-20~22 + AC-CKC-50/51 vitest PASS

- [ ] **S08**: Paceriz demo 端到端驗收 + 錄影 (depends: S06)
  - Verify: AC-CKC-60~64 PASS；demo 影片 ≤3 分鐘；L1-only fallback 切換驗證

- [ ] **S09**: 整體 QA + 部署後驗證 (depends: S06, S07, S08)
  - Verify: Firebase Hosting 部署成功；`/api/cowork/graph-context?seed_id={paceriz-entity-id}` 200 + 非空；所有 AC test PASS

## Decisions

- **2026-04-17**: graph_context 由前端組（Dashboard API），helper 維持 prompt-proxy。理由：helper 無 MCP client 能力；前端已是 ZenOS API 一級消費者；不破壞現行授權邊界。
- **2026-04-17**: 對話輪數統一 10（SPEC AC-CKC-35 已更新）。覆蓋 SPEC-marketing-automation 原 8 輪、SPEC-crm-intelligence briefing 原 8 輪。不另開 12 避免 UI state machine 分支。
- **2026-04-17**: verb 不在 scope（使用者指示），fallback 策略用階層 + tags(what/why/who)。若 SPEC-knowledge-graph-semantic 落地 verb 可升級 neighbor schema。
- **2026-04-17**: Token budget 先交付 1500 + 裁切策略；S01 任務必須附實測報告，必要時 PM 簽字後調整。

## Resume Point

尚未開始 dispatch。下一步：建 ZenOS Plan（`mcp__zenos__plan action=create`）拿 plan_id，再以 `mcp__zenos__task` 批量建 9 張票並掛 plan_id + plan_order。之後 dispatch S01 給 Developer subagent。
