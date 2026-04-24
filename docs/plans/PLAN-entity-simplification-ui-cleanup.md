---
spec: null  # UI-only followup; driven by ADR-047 D7 + ADR-048 + CLAUDE.md hard constraint 6
driver_docs:
  - docs/decisions/ADR-047-l1-level-ssot.md
  - docs/decisions/ADR-048-grand-ontology-refactor.md
created: 2026-04-24
status: in-progress
---

# PLAN: Entity Simplification UI Cleanup

ADR-047（L1 = level-based，type 降為 label）與 Wave 9 L3-Action migration 的 server 側工作已全部落地，但 S06 dashboard 層只完成了 `isL1Entity` helper 導入與部分入口。UI 其餘表面（filter、copilot prompt、文案、視覺差異化）還殘留舊的「L1 = product」心智模型。本 PLAN 收掉這筆尾巴。

---

## 治理說明

本 PLAN 的 **驅動文件** 是 ADR-047 D7、ADR-048、CLAUDE.md hard constraint 6，而非獨立 SPEC。依文件治理規則，這些 ADR 屬於 non-executable——**dispatch 前必須先在 ZenOS MCP 建立 task 並帶 `acceptance_criteria`**，以 task 作為真正的 execution claim unit。本 PLAN 只描述 task 群的完成邊界與排程順序，不直接等同於 task。

Architect 每次 dispatch 前流程：
1. `mcp__zenos__task(action="create", acceptance_criteria=[...], ...)` 建立 ZenOS task
2. 產出 AC test stub（前端 vitest `it.fails` 格式）
3. handoff + 啟動 Developer agent

---

## Context

- **ADR-047 D7** 明文要求「所有 `entity.type === "product"` 的過濾判斷全部改用 `isL1Entity` helper；視覺差異（icon/字型/大小）保留 type-based 分支，但篩選邏輯一律走 level」。當前 dashboard 只做了第一句，沒做第二句。
- **CLAUDE.md hard constraint 6**：UI 不出現 entity/ontology；Product→專案（已進一步收斂為「工作台」）。但 Task Hub / Nav / Copilot 多處仍硬寫「產品 / products」。
- **CRM bridge** 建出的 `company / person / deal` 已是合法 L1（ADR-047 D2 + Wave 9 落地），但 portfolio / copilot / health bar 用「產品」視角會漏算這些 L1。

---

## Entry Criteria（本 PLAN 可開工的前置）

- ✅ ADR-047 S01–S07 accepted 並部署 prod（commit `5ae865077`、`8f4e91317` 已 merged）
- ✅ Wave 9 L3-Action migration 落地（prod revision 00214-puc，journal `53dc3510`）
- ✅ dashboard `isL1Entity` helper 已存在（`dashboard/src/lib/entity-level.ts:19`）
- ✅ `ROOT_SURFACE_LABEL_{ZH,EN}` 已定義（`dashboard/src/features/projects/rootLabels.ts:1-2`）

---

## Exit Criteria（本 PLAN 完成判定）

1. 所有 Phase 1–4 task 完成並通過 Architect AC sign-off
2. Dashboard 重新部署（`./scripts/deploy.sh`），UI 端到端冒煙通過
3. Grep 驗證：在下列 **豁免範圍外**，`dashboard/src/` 中無剩餘 `type === "product"` 過濾
   - 豁免 A：`dashboard/src/app/preview/` 全目錄（preview-only，Dev 跑不到）
   - 豁免 B：`KnowledgeGraph.tsx` type-based 視覺 sizing（ADR-047 D7 允許）
   - 豁免 C：`CrmAiPanel.tsx`（CRM-native，company 語境在域內正確）
4. 全域文案 grep-clean（見 AC-ENTSIMP-UI-04 完整掃描範圍）
5. Task Hub Copilot 對「只有 CRM company 的 workspace」能正確輸出 portfolio recap，輸出中無「產品」字樣
6. 本 PLAN 所有 AC test（`dashboard/src/__tests__/entity_simplification_ui_ac.test.ts`）全綠
7. Journal 寫入完成紀錄

---

## 文案 sweep 完整掃描範圍（S04 執行邊界）

以下為 grep 找到的全部用戶可見「產品 / products」出現點，分三類：

### 必改（進入 S04 scope）

| 位置 | 現況字串 | 建議 |
|------|---------|------|
| `components/AppNav.tsx:14,21` | nav label `"產品"` | `"工作台"` |
| `components/HealthBar.tsx:48` | `"{N} 個產品進行中"` | `"{N} 個工作台進行中"` |
| `components/ProjectProgress.tsx:22` | `"No products yet"` | `"No workspaces yet"` |
| `app/(protected)/tasks/page.tsx:520` | subtitle `"先看所有產品的..."` | `"先看所有工作台的..."` |
| `features/tasks/TaskHubRail.tsx:87` | placeholder `"直接問全產品..."` | `"直接問全工作台..."` |
| `features/tasks/TaskHubRail.tsx:97` | emptyState `"先問哪個產品..."` | `"先問哪個工作台..."` |
| `features/tasks/TaskHubMorningPanel.tsx:53` | `"目前沒有新的跨產品變化。"` | `"...跨工作台..."` |
| `features/tasks/TaskHubMorningPanel.tsx:182` | `"All products"` | `"All workspaces"` |
| `features/tasks/ProductHealthList.tsx:62` | 標題 `"Products by Health"` | `"Workspaces by Health"` |
| `features/tasks/TaskHubRecap.tsx:67` | `"往哪個產品下鑽"` | `"往哪個工作台下鑽"` |
| `features/marketing/MarketingWorkspace.tsx:335` | `"先選產品，再建立..."` | `"先選工作台，再建立..."` |
| `features/marketing/MarketingWorkspace.tsx:354` | placeholder `"產品 ID..."` | `"工作台 ID..."` |

### 豁免（保留，記錄原因）

| 位置 | 原因 |
|------|------|
| `components/zen/LandingFooter.tsx:82` `LandingB.tsx:325,498` | 行銷 landing page，不是 app UI；另立改版決策 |
| `components/OnboardingChecklist.tsx:207,218` | `"產品需求"` 是描述 `/pm` skill 功能，且 PM = product manager 的語境正確 |
| `app/(protected)/home/page.tsx:14` | mock demo 字串，不影響功能 |
| `app/(protected)/setup/page.tsx:38` | `"產品需求"` 同 OnboardingChecklist 理由 |
| `components/ZenShell.tsx:55` | 程式碼 comment，非 UI 文字 |
| `app/(protected)/marketing/page.tsx:31` | `"Q2 產品發表"` 是 mock 標題資料，非術語 |
| `app/(protected)/projects/page.tsx:1723-1725` | 區域變數 `products`（用於 bootstrap logic），非 UI 字串 |
| `app/preview/**` | preview 專用，整批豁免（見 S08） |

---

## Tasks

### Phase 1 — 🔴 Critical bug fix（P0，1 個 PR）

必須先建 ZenOS task 再 dispatch。Phase 1 完成後獨立部署一次，再開 Phase 2。

- [ ] **S01**: HealthBar filter 改 `isL1Entity`
  - Files: `dashboard/src/components/HealthBar.tsx`
  - Done:
    - L11 `entities.filter((e) => e.type === "product")` → `entities.filter(isL1Entity)`
    - L12 `activeProducts` 定義跟著更新
    - L48 文案 `"個產品進行中"` → `"個工作台進行中"`（同 S04，順帶改）
  - Verify: vitest 新增 CRM-only 場景（company L1 被計入、product L1 被計入、L2 module 不計入）

- [ ] **S02**: `isPlaceholderCompletedProject` 收斂
  - Files: `dashboard/src/app/(protected)/projects/page.tsx:86-93`
  - Done:
    - 先讀 `page.tsx:1648` 的 `isPlaceholderCompletedProject` 呼叫脈絡，確認 placeholder bootstrap 實際只產 `type=product`
    - 若確認是 product-only：保留 `type === "product"` 判定，**補 inline comment** 說明此處是有意 type-gate（bootstrap 合約），不是遺漏
    - 補 vitest：「product placeholder 被 filter；非 placeholder 的 company L1 不被誤 filter」
  - Verify: vitest 全綠；`isPlaceholderCompletedProject(companyEntity)` 回傳 false

- [ ] **S03**: taskHubCopilot prompt 中性化
  - Files: `dashboard/src/features/tasks/taskHubCopilot.ts`
  - Done:
    - `context_pack.top_products` → `context_pack.top_workspaces`
    - `item.product` → `item.workspace` / `item.root_name`
    - `recent_changes[].product` → `recent_changes[].workspace`
    - prompt L58, L60, L62, L63 的「產品 / products」→「工作台 / workspaces」
  - Verify: 既有 `taskHubCopilot` test 更新期望值並全綠；手動觸發 CRM-only workspace 的 recap

---

### Phase 2 — 🟡 文案 sweep（P1，1 個 PR）

必須 Phase 1 部署後才開工。

- [ ] **S04**: UI 文案批次改（依上方掃描範圍表格）
  - Files: 全部「必改」欄位的 12 個位置
  - Done:
    - 所有 user-visible 字串無「產品 / products」（豁免清單除外）
    - `grep -rn '產品\|products' dashboard/src/app dashboard/src/features dashboard/src/components` 只剩豁免項目
  - Verify: grep clean + vitest 全綠

- [ ] **S05**: 內部變數 / 檔名 rename（與 S04 同 PR）
  - Files:
    - `app/(protected)/projects/page.tsx:357-366,1587,1781,1829-1830`：`showDormantProducts` → `showDormantWorkspaces`，`onToggleDormantProducts` → `onToggleDormantWorkspaces`
    - `features/tasks/ProductHealthList.tsx` → `WorkspaceHealthList.tsx`（含 import 更新）
  - Done: grep 無殘留舊名；vitest 全綠
  - Verify: `cd dashboard && npx vitest run`

---

### Phase 3 — 🟡 視覺差異化（P1，需 Designer 對齊；獨立 PR）

**Gate：dispatch S06 前先與用戶確認色票映射。**

- [ ] **S06**: Projects 卡片 type-based accent / icon 分支
  - Files: `dashboard/src/app/(protected)/projects/page.tsx:503-504, 820-822`
  - Done:
    - 新增 `resolveL1Accent(type: string)` helper（建議放 `features/projects/rootVisuals.ts`）：`product→vermillion, company→jade, person→muted-warm, deal→accent, else→vermillion`
    - 卡片左上 / 左邊框改用 `resolveL1Accent(proj.type)`
    - 卡片角落加 type badge（小字 label，`< 2px` height）
  - Verify: 視覺 smoke（Designer review）+ product workspace 視覺不變

- [ ] **S07**: KnowledgeGraph node size 改 level-based
  - Files: `dashboard/src/components/KnowledgeGraph.tsx:269`
  - Done:
    - base size 改用 `entity.level`：`level=1 → 16, level=2 → 10, level=3 → 8, else → 8`
    - type-based fine-tune 保留為可選 delta（例如 product 可 +1）
  - Verify: CRM workspace knowledge map 中 company / product 顯示同尺寸

---

### Phase 4 — 🟢 收尾（P2）

- [ ] **S08**: preview 頁評估
  - 實際路徑（已確認）：
    - `dashboard/src/app/preview/page.tsx`
    - `dashboard/src/app/preview/mockup-a/page.tsx`
    - `dashboard/src/app/preview/mockup-b/page.tsx`
    - `dashboard/src/app/preview/mockup-c/page.tsx`
    - `dashboard/src/app/preview/realData.ts`
    - `dashboard/src/app/preview/mockData.ts`
  - Done: 選 (a) 跟著 sweep 改 `isL1Entity` 並更新 mockData；或 (b) 在每個 preview 檔頭加一行 `// preview-only: type filter intentional` 並加進豁免清單
  - Verify: 決策明文記錄在本 PLAN Decisions 區

- [ ] **S09**: 端到端驗證 + 部署
  - Done:
    - QA agent 跑完整 UI 冒煙（三場景：product-only workspace / CRM-only workspace / mixed workspace）
    - `./scripts/deploy.sh` 部署 Firebase Hosting
    - 部署後手動驗 (i) HealthBar 計數 (ii) AppNav label (iii) Task Hub recap copy (iv) Projects 卡片視覺差異
    - CRM-only workspace 觸發 Task Hub Copilot → 回應不含「產品」
  - Verify: 用戶視角端到端截圖 / log 留在 QA Verdict

---

## Done Criteria（AC 表）

| AC ID | 描述 | Test Location | 狀態 |
|-------|------|---------------|------|
| AC-ENTSIMP-UI-01 | HealthBar 顯示所有 L1（含 company/person/deal）計數 | `entity_simplification_ui_ac.test.ts::ac01` | STUB |
| AC-ENTSIMP-UI-02 | Placeholder filter 不誤殺 company L1；product placeholder 仍正確被隱藏 | 同上 ::ac02 | STUB |
| AC-ENTSIMP-UI-03 | taskHubCopilot context / prompt 不含「產品」字樣 | 同上 ::ac03 | STUB |
| AC-ENTSIMP-UI-04 | 掃描範圍內 user-visible 字串無「產品 / products」 | grep + 同上 ::ac04 | STUB |
| AC-ENTSIMP-UI-05 | `showDormantProducts` / `ProductHealthList` 已 rename，vitest 全綠 | 同上 ::ac05 | STUB |
| AC-ENTSIMP-UI-06 | Projects 卡片依 type 有不同 accent + badge | 視覺 smoke + 同上 ::ac06 | STUB |
| AC-ENTSIMP-UI-07 | KnowledgeGraph node size 依 level，company/product 同尺寸 | 同上 ::ac07 | STUB |
| AC-ENTSIMP-UI-08 | preview 頁策略明文記錄（改或豁免） | 本 PLAN Decisions | STUB |
| AC-ENTSIMP-UI-09 | 部署後三場景冒煙通過，CRM-only copilot 無「產品」輸出 | QA Verdict | STUB |

AC test stub 檔：`dashboard/src/__tests__/entity_simplification_ui_ac.test.ts`（S01 dispatch 前由 Architect 產出）。

---

## Decisions

- **2026-04-24**: 不產新 SPEC——驅動文件已是 ADR-047 D7 + ADR-048 + CLAUDE.md 硬約束 6。但每個 task 在 ZenOS MCP 建立時帶 acceptance_criteria，AC test stub 是 compliance 唯一追蹤機制。
- **2026-04-24**: Phase 切分邏輯：Phase 1 bug fix 先部署（CRM L1 計數是 data bug）；Phase 2 文案可批次；Phase 3 依賴 Designer 參與放後；Phase 4 收尾最後。
- **2026-04-24**: S02 Done 分支選 (a)（保留 product type gate 並補 comment），前提是盤點 bootstrap 確認 placeholder 只產 product。若發現 company 也有 placeholder，改成 (b) `isL1Entity` + 補足欄位判定。
- **[待確認] S06 色票映射**：`product→vermillion, company→jade, person→muted-warm, deal→accent` — Architect 需在 dispatch S06 前與用戶對齊。

---

## Resume Point

**尚未開始。下一步：**

1. Architect 產出 `dashboard/src/__tests__/entity_simplification_ui_ac.test.ts` 9 條 AC stub（vitest `it.fails` 格式）
2. 建立 ZenOS task（S01，含 acceptance_criteria）
3. Dispatch S01 給 Developer
4. S01→S02→S03 收完，Phase 1 整包 vitest 全綠後部署
5. 部署驗過才開 Phase 2

**未解決決策（Architect 在 S06 dispatch 前必須 resolve）：**
- S06 色票映射是否與用戶對齊？（目前 [待確認]）
- S08 preview 頁選 (a)sweep 還是 (b)豁免？（S08 dispatch 前 resolve）
