---
doc_id: SPEC-zen-ink-migration-addendum
title: Zen/Ink Migration — Architect Addendum (User Decisions)
type: SPEC
ontology_entity: dashboard-design-system
status: approved
version: "0.1"
date: 2026-04-20
supersedes: null
related: DESIGN-zen-ink-migration.md
---

# Zen/Ink Migration — Architect Addendum

本 addendum 紀錄 Designer spec (`DESIGN-zen-ink-migration.md`) 提交 Architect 後，用戶拍板的 4 項決策與其對 Designer 原文的覆蓋/修正。

> Designer spec 對應條文仍保留其技術細節；**本 addendum 為 SSOT**——Designer spec 與本 addendum 衝突時，以本 addendum 為準。

---

## A1. §6.2 字型取捨 — APPROVED（採 Designer 建議 A）

**用戶決策**：同意 TaskCard title 用 `t.fontBody`（sans），而非 `t.fontHead`（serif）。

**影響**：
- TaskCard：title `fontFamily=t.fontBody`, `fontWeight=500`, `fontSize=13`, `letterSpacing=0.02em`
- 保留 serif 僅用於：頁面 Section heading、Dialog title、CmdK input、Drawer header title
- Batch 3（TaskCard + TaskBoard）的 AC 加入「title 視覺未使用 fontHead」的檢查

**不採**：Designer §6.2 建議 B（Zen Workbench 子變體）——會讓 design system 分叉，拒絕。

---

## A2. §6.3 擴充預留 — APPROVED（Drawer 加 headerExtras slot）

**用戶決策**：同意 `Drawer` 預留 `headerExtras?: React.ReactNode` slot，為未來 Task L3 升級（dispatcher badge / handoff timeline tabs）留位。

**影響**：
- Batch 1 的 `Drawer.tsx` API 必須含 `headerExtras` prop（與 Designer §2.5 原文一致）
- Batch 4（TaskDetailDrawer）即使本次未用 `headerExtras`，也要在 component test 覆蓋「傳入 headerExtras 時 render 在 header 上方或右側」的行為
- **不擴充**到其他 primitive（Dialog 不加，保持 minimal）

---

## A3. §6.4 Radix 策略 — OVERRIDDEN（全部 native 實作，Radix 完全拔除）

**用戶決策推翻 Designer §6.4 原判斷**：不保留 Radix primitive。`sheet` / `tooltip` / `toast` / `dialog` 四項**全部由 Zen native 實作**，不依賴 Radix。

**覆蓋條目**：

| Designer §1.1 原計畫 | 覆蓋後決策 |
|---|---|
| `sheet.tsx`（Radix）保留 primitive，外觀由 `zen/Drawer` 封裝 | `sheet.tsx` 刪除；`zen/Drawer` **完全 native 實作**，自管 focus trap / portal / ARIA |
| `tooltip.tsx`（Radix）保留 primitive，外觀改 Zen token | `tooltip.tsx` 刪除；`zen/Tooltip` **完全 native**，自管 portal / 定位 / hover+focus trigger / delay |
| `toast.tsx`（Radix）保留 primitive，外觀改 Zen token | `toast.tsx` 刪除；`zen/Toast` **完全 native**，自管 portal / queue / auto-dismiss / ARIA live region |
| `Dialog`（Radix Dialog） | `zen/Dialog` **完全 native**，自管 focus trap / portal / ARIA |

**行為契約（Developer 不得省略）**：
每一個 native overlay primitive（Drawer / Dialog / Tooltip / Toast）必須完整實作：

1. **Focus trap**：open 時 focus 進入 panel，Tab 循環不逃脫；close 時 focus 返還到 trigger element
2. **Portal**：render 到 `document.body`（或獨立 portal root），避免被 parent `overflow: hidden` 切掉
3. **ARIA**：
   - Dialog / Drawer：`role="dialog"` + `aria-modal="true"` + `aria-labelledby` / `aria-describedby`
   - Tooltip：`role="tooltip"` + `aria-describedby` 關聯 trigger
   - Toast：`role="status"` 或 `role="alert"` + `aria-live="polite"` / `"assertive"`
4. **鍵盤操作**：
   - Dialog / Drawer：Esc → close；Tab / Shift+Tab 在 trap 內循環
   - Tooltip：focus trigger 顯示、blur 隱藏、Esc 關閉
   - Toast：Esc 關閉可 dismiss 的 toast
5. **Click-outside**：Dialog / Drawer overlay 點擊 → close（可由 `closable` prop 關閉）
6. **Z-index stacking**：定義 z-index scale（建議 `overlay: 1000, drawer: 1001, dialog: 1002, tooltip: 1100, toast: 1200`），避免相互遮擋
7. **Body scroll lock**：Dialog / Drawer open 時鎖 `document.body.overflow`，close 時還原（偵測既有值，避免覆蓋）
8. **SSR safe**：portal 只在 `useEffect` 內建立（Next.js 15 app router 必須過）

Developer 不得以「簡化」「下次再補」為由省略以上任一項，AC 會逐項驗證。

---

## A4. §6.5 / §3.3 Dark Mode — DEFERRED（light-only ship）

**用戶決策**：Zen 目前沒看到 dark mode 實際 render 的 case，本次 Plan **light-only ship**，dark mode 不在 scope。

**覆蓋條目**：

| Designer 原計畫 | 覆蓋後決策 |
|---|---|
| §4 Batch 1 驗收：「light / dark mode 切換都 OK」 | **改為**：「light mode 全 variant + 狀態可視化；dark mode token 接線正確（`useInk("dark")` 能 resolve 出對的 color）但不做 visual pass」 |
| §5.2 globals.css 含 `html.dark` 規則 | **保留 dark CSS variable 定義**（不刪），但不驗證 dark mode render；`ZenShell` 維持 `useInk("light")` hardcode 不動 |
| §6.1 Batch 8 前「dark mode pass」 | **移除**——不在本 Plan 的 exit_criteria |

**Developer 硬約束（每一個 primitive 必遵守）**：
- primitive 的顏色**必須**透過 `t.c.*`（由 caller 傳入的 `t = useInk(mode)` 得出）取得
- **禁止 hardcode hex 色值**（如 `#141210`、`#F4EFE4`），除非是 Zen token 不涵蓋的系統色（如 transparent shadow rgba）
- 未來開啟 dark mode 時，只需把 caller 的 `useInk("light")` 改 `useInk(mode)` 即可零改動 primitive 本體
- AC 包含：`grep` 檢查 primitive 檔案內無 `#[0-9a-f]{6}` 色值（white/black 等極少數例外要註解說明）

---

## Exit Criteria 修訂（Plan 層級）

本 Plan 完成的條件（取代 Designer §8 原寫法）：

1. `dashboard/src/app/globals.css` 已清掉所有 shadcn token（`@theme inline`、`:root { --* }`、shadcn slot override），只剩 Tailwind preflight + 少量 utility + graph animations
2. §1 列出的所有 Tailwind/shadcn dark 元件已遷移成 Zen 語言（以 grep 驗證 Tailwind dark class 回傳 0）
3. **Light mode 全站可用**（dogfood 過 tasks / clients / deals / marketing / docs / knowledge-map / home 7 頁）
4. Dashboard 既有測試全過（`task-operations.test.ts` / `CrmAiPanel.behavior.test.tsx` + 新 primitive test）
5. 部署後瀏覽器 E2E 驗證各頁風格一致、無殘留 cyan / shadcn 視覺
6. Radix dependencies（`@radix-ui/*`）從 `package.json` 全部移除

Dark mode render 可用性 **不**列入本 Plan exit criteria，作為 future work（另開 Plan）。

---

## 不動 Designer 的其他章節

§1.2、§1.3、§2.1–§2.4、§2.6–§2.9、§3.1、§3.2、§4 的 Batch 2–7、§5.1、§5.3、§5.4、§6.6 皆維持 Designer 原文，不修改。
