---
type: SPEC
id: SPEC-zen-ink-redesign
status: Draft
created: 2026-04-19
---

# SPEC: Zen Ink 全站設計語言重構

## What
把 ZenOS Landing + dashboard 所有頁面，依照 `dashboard/design-ref/` 的 Zen Ink 設計稿 1:1 落地。UI-only 改版，不動後端、不改功能。設計稿未支援的欄位留空（用 placeholder 或刪除區塊）。

## Why
現有 UI 視覺不一致、資訊密度高、層級感不明。用戶選定 Zen Ink（墨白禪意）為全站統一語言：宣紙背景 + 墨黑 + 朱砂點 + Noto Serif TC 為題、Helvetica + Noto Sans TC 為文、hairline 線條取代框線、sharp corners（radius=2）。

## Scope
1. **Landing (public)** — `src/app/page.tsx` 改為 Zen Ink Variant B（墨白精量企業版）。保留 A/C 變體但隱藏於 `?variant=A|C` query。
2. **Dashboard shell** — `(protected)/layout.tsx` 的 `AppNav` 換成 Zen Ink 側欄（7 項 nav：map/home/tasks/projects/clients/marketing/docs）+ ⌘K 指令面板 + 底部帳號/明暗切換。
3. **6 個主頁 + 4 個第二層**：
   - Knowledge Map (`/knowledge-map`) — 圓點圖 + Inspector
   - Home (`/home` 新增) — 今日工作台（英雄節氣區 + 晨報 + Agent 摘要 + 行程）
   - Tasks (`/tasks`) — 4 欄看板 + Task Drawer（第二層）
   - Projects (`/projects`) — 卡片 list + Project Detail（第二層）
   - Clients (`/clients`) — Pipeline/列表 + Deal Detail（第二層）
   - Marketing (`/marketing`) — Campaign list + Campaign Detail（第二層）
   - Docs (`/docs`) — 三欄 notion-like workspace

## Acceptance Criteria

- **AC-ZEN-01**: Landing 根頁 `/` 預設渲染 Variant B，含 hero / metrics / 4-step workflow / knowledge substrate / 3 個 feature slabs / testimonial / pricing / manifesto / final CTA / footer。
- **AC-ZEN-02**: Landing 支援 `?variant=A` 與 `?variant=C` 切換到濃禪與 AI-native 版。
- **AC-ZEN-03**: 全站載入 Noto Serif TC + Noto Sans TC（Google Fonts 或 next/font）。
- **AC-ZEN-04**: Zen Ink tokens (宣紙/墨/朱砂/青竹/赭石 + 3 種 font + radius=2) 有中央 source（`lib/zen-ink/tokens.ts` 或 `useInk` hook）。
- **AC-ZEN-05**: `(protected)/layout.tsx` 側欄顯示 7 項導航（map 置頂且預設頁），含 InkMark logo、⌘K 按鈕、底部 Barry 帳號 + 明暗切換。
- **AC-ZEN-06**: Knowledge Map 頁渲染 SVG 圓點圖 + Inspector（標籤/Agent 摘要/Relations/近期活動）+ Zoom controls + Legend。
- **AC-ZEN-07**: Home 頁渲染 HeroToday（節氣 SealChop + 日期 + 狀態 chips）+ Priorities / Agent Summary / Schedule 三欄。
- **AC-ZEN-08**: Tasks 頁渲染 HeroToday + 4 tabs + 4 欄看板（todo/active/review/done），卡片支援一/二/三/四筆劃優先級，點擊開啟 TaskDrawer（Agent 建議 + 子任務 + 動態 + 註記輸入）。
- **AC-ZEN-09**: Projects 頁渲染 KPI strip + 2 欄卡片列表（進度條 + healthChip + 成員/任務/文件 meta），點擊開啟 Detail（metrics strip + milestones + activity + 文件 + 成員）。
- **AC-ZEN-10**: Clients 頁渲染 KPI strip + pipeline/list toggle，pipeline 為 5 欄（潛在→訪談→Demo→提案→成交），點擊開啟 Deal Detail（Agent 複盤 + timeline + 承諾事項 + 聯絡人）。
- **AC-ZEN-11**: Marketing 頁渲染 KPI strip + Campaign list，點擊開啟 Detail（6-stage stepper 策略→排程→情報→生成→確認→發佈 + 寫作計畫 + 文風管理 + 右側 AI Rail）。
- **AC-ZEN-12**: Docs 頁為三欄 layout（tree + doc body + outline/AI 建議/引用），tree 分組（Pinned / 個人 / 團隊 / 專案）。
- **AC-ZEN-13**: 所有頁面在 shadcn 既有元件上不破壞（Dialog / Dropdown / 既有 AuthGuard 正常）。
- **AC-ZEN-14**: 設計稿「穀雨」節氣文案、「禪作」印章字樣**不出現**在產品內（Landing 可保留作為視覺元素如大浮水印，但 brand mark 寫「ZenOS」）。
- **AC-ZEN-15**: 無法串接的欄位（如真實任務資料、客戶資料）使用設計稿裡的 demo data，不空白 render。

## Non-goals
- 不對接後端 API。任何 data 直接 inline demo data（與設計稿一致）。
- 不重寫 shadcn 元件庫；新 Zen Ink 元件放在 `src/components/zen/`。
- 不改 routing 結構（除 `/home` 新增）。
- 不做 dark mode runtime toggle（只需 light，tokens 保留 dark 結構以備後用）。
