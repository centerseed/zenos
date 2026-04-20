---
doc_id: SPEC-zen-ink-migration
title: Zen/Ink Design System Migration Spec
type: SPEC
ontology_entity: dashboard-design-system
status: draft
version: "0.1"
date: 2026-04-20
supersedes: null
---

# Zen/Ink Design System Migration Spec

> Goal: 讓 dashboard 產品只有一套視覺語言 — **Zen Ink**（墨白禪意）。
> 把所有 Tailwind/shadcn dark cyan 元件替換或重寫為 Zen Ink primitive 與 inline-style 元件。
> 本 spec 定義盤點、新增元件、token mapping、遷移批次、globals.css 清理計畫。
> Task L3 升級（dispatcher / handoff_events / subtask tree）的 UI 呈現**不在本 spec 範圍**，但 API 預留擴充位。

---

## 0. Design Intent（為什麼要做這件事）

**受眾**：中小企業主、PM、開發團隊——同一個產品、不同 persona，需要**一致的視覺語言**建立信任與熟悉感。

**美學立場**：Zen Ink 不是「又一個 dark mode SaaS」，它是一個**有編輯性格**的工作空間：
- 宣紙紙感（paper warm `#F4EFE4`）取代冷藍漸層 — 降低視覺疲勞、強化閱讀性
- 墨色（ink `#141210`）做主色、朱砂（vermillion `#B63A2C`）當 accent — 對比鮮明且不浮躁
- Serif 標題（Noto Serif TC）＋ sans body — 東方編輯感，建立記憶點
- `borderRadius: 2`（近方正）取代 `rounded-2xl` — 不走當代 SaaS「圓潤親切」路線，走「精確、慎重」

**核心決策**：**不做雙主題**（不保留 dark cyan 當 option）。
雙主題會讓元件維護成本翻倍、設計一致性破碎、使用者認知錯亂。Zen Ink 的 `modes: { light, dark }` 已是內建黑白切換，足夠。

---

## 1. Component Inventory（盤點）

### 1.1 移除 / 不再使用（fully deprecated）

| Path | 目前職責 | 處置 |
|---|---|---|
| `src/components/ui/button.tsx` (shadcn) | 通用 button | 刪除，全部改用 `zen/Btn` |
| `src/components/ui/card.tsx` | shadcn Card | 刪除，Zen 沒有 generic Card，改用 inline panel pattern（見 §2.9） |
| `src/components/ui/badge.tsx` | shadcn badge | 刪除，全部改用 `zen/Chip` |
| `src/components/ui/separator.tsx` | shadcn separator | 刪除，用 `zen/Divider` |
| `src/components/ui/sheet.tsx` | shadcn sheet (Radix) | **保留 Radix 當 behavioral primitive**，但外觀由新 `zen/Drawer` 封裝（§2.5）。callers 改呼叫 `zen/Drawer` |
| `src/components/ui/tooltip.tsx` | Radix Tooltip | 保留 primitive，外觀以 Zen token 重新 style，callsite 改呼叫 `zen/Tooltip`（§2.10） |
| `src/components/ui/toast.tsx` | Radix Toast | 保留 primitive，外觀改走 Zen token（§2.10） |

### 1.2 高互動元件——重寫為 Zen（產品核心）

| Component | 行數 | 當前行為 | 複雜度 | 依賴 |
|---|---|---|---|---|
| `TaskBoard.tsx` | 370 | Kanban + DnD（dnd-kit）+ drag warning modal | **L** | TaskCard, TaskDetailDrawer, Modal（新） |
| `TaskCard.tsx` | 213 | 任務卡片 + priority/dispatcher/tag chip + hover glow | **M** | Chip, Icon |
| `TaskDetailDrawer.tsx` | 1036 | 側抽屜、inline edit、status dropdown、comments、handoff form、attachments | **L** | Drawer, Input, Textarea, Select, Btn, Chip, Divider |
| `TaskCreateDialog.tsx` | 211 | Modal form（title/desc/priority/assignee/due/project） | **M** | Dialog, Input, Textarea, Select, Btn |
| `TaskFilters.tsx` | 158 | Status multi-select popover + Priority/Project/Dispatcher `<select>` | **M** | Select, Popover（新）, Checkbox |
| `TaskAttachments.tsx` | 441 | 上傳/預覽附件（image/video/pdf/text） | **M** | Btn, Chip, Dialog（for image modal） |
| `KnowledgeGraph.tsx` | 685 | ForceGraph canvas + side legend + tooltip | **S**（已有 `variant="ink"`） | 內建 INK_PALETTE，只需統一 callsite `variant="ink"` |
| `components/ai/CopilotChatViewport.tsx` | 84 | chat message list + streaming bubble | **M** | Card-panel pattern（inline）, Chip |
| `components/ai/CopilotInputBar.tsx` | 108 | textarea + action buttons | **S** | Textarea, Btn |
| `components/ai/CopilotRailShell.tsx` | 241 | Sheet + inline shell + header + diagnostic area（**已用 zen tokens 模擬 shadcn var**） | **M** | Drawer（§2.5）取代 Sheet；移除 `--primary`/`--card` hack |
| `components/ai/GraphContextBadge.tsx` | 233 | details/summary 展開節點清單（**已用 zen tokens**） | **S** | 只需清理 borderRadius 從 14/16/999 → 2 |
| `features/crm/CrmAiPanel.tsx` | 1626 | Briefing/Debrief chat panel + save/load + follow-up draft | **L** | Drawer, Input, Textarea, Btn, Chip, Tab（§2.8） |
| `features/crm/DealDetailWorkspace.tsx` | 890 | Deal detail 多區塊、stage funnel、activity timeline、inline edit | **L** | Input, Textarea, Select, Btn, Chip, Divider, Tab |
| `app/(protected)/clients/deals/[id]/DealDetailClient.tsx` | — | Deal 頁面 orchestrator | **M**（多 shell wrapping） | ZenShell, Section |
| `app/(protected)/clients/deals/[id]/DealInsightsPanel.tsx` | — | AI insight 側欄 | **M** | 同上 |
| `components/AuthGuard.tsx` | 264 | 登入/權限 gate，**已全用 Zen inline styles** | **S** | 只需清除多處重複 `useInk("light")` 為 hoisted const |

### 1.3 總規模
- **約 6,000 行 UI code** 要遷移
- 最重的三個：`CrmAiPanel` (1626) > `TaskDetailDrawer` (1036) > `DealDetailWorkspace` (890)
- 14 個元件直接使用 Tailwind/shadcn dark；8 個元件已部分用 Zen tokens（混合態要拉齊）

---

## 2. 新增 Zen 基礎元件清單（`src/components/zen/`）

**設計原則（全部 primitives 共通）**：
1. Props 皆接 `t: ZenInkTokens`（與 `Btn`/`Chip`/`Section` 一致 — 調用端 `const t = useInk("light")` 後傳入）。**不從內部 `useInk`**，讓 parent 控制 mode、減少 re-render。
2. 全部用 **inline `style`** + 必要 className，不依賴 Tailwind class。避免 globals.css 殘留影響。
3. `borderRadius: t.radius`（= 2）是預設；例外要顯式說明。
4. Font：預設 `t.fontBody`，標題用 `t.fontHead`，code/label 用 `t.fontMono`。
5. Focus ring：一致用 `box-shadow: 0 0 0 2px ${c.vermLine}`（vermillion 細邊）— accessibility 硬要求。

### 2.1 `Input.tsx`

```tsx
interface InputProps {
  t: ZenInkTokens;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "email" | "date" | "number" | "password";
  disabled?: boolean;
  autoFocus?: boolean;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onBlur?: () => void;
  size?: "sm" | "md";
  invalid?: boolean;
  style?: React.CSSProperties;
  "aria-label"?: string;
}
```

**Usage**:
```tsx
<Input t={t} value={title} onChange={setTitle} placeholder="任務標題" />
```

**視覺**：
- Background: `c.surfaceHi`（light mode）/ `c.surface`（dark mode）
- Border: `1px solid c.inkHair` idle → `c.inkHairBold` hover → `c.vermillion` focus
- Padding: `sm=6px 10px / md=9px 12px`；font-size `sm=12 / md=13`；radius `2`

### 2.2 `Textarea.tsx`

```tsx
interface TextareaProps extends Omit<InputProps, "type"> {
  rows?: number;
  resize?: "none" | "vertical";
}
```

**Usage**:
```tsx
<Textarea t={t} value={desc} onChange={setDesc} rows={4} placeholder="任務描述" />
```

視覺規則同 Input，`resize: vertical`；`font-family` 可選 body / mono（CRM email draft 用 mono）。

### 2.3 `Select.tsx`

**兩種形態**：
- `Select`（native `<select>`，樣式覆寫）— 用於簡單枚舉（priority / status / dispatcher）
- `Dropdown`（custom popover）— 用於搜尋、多選、客製 item render（e.g. TaskFilters status multi-select）

```tsx
interface SelectOption {
  value: string;
  label: string;
  tone?: "plain" | "accent" | "jade" | "ocher";  // 可繼承 Chip tone
}

interface SelectProps {
  t: ZenInkTokens;
  value: string | null;
  onChange: (v: string | null) => void;
  options: SelectOption[];
  placeholder?: string;
  size?: "sm" | "md";
  clearable?: boolean;
  disabled?: boolean;
  "aria-label"?: string;
}
```

**Usage**:
```tsx
<Select
  t={t}
  value={priority}
  onChange={setPriority}
  options={[{value:"critical", label:"Critical", tone:"accent"}, ...]}
  placeholder="選擇優先級"
  clearable
/>
```

### 2.4 `Dropdown.tsx`（custom popover）

```tsx
interface DropdownProps<T> {
  t: ZenInkTokens;
  trigger: React.ReactNode;           // the button face
  items: Array<{ value: T; label: React.ReactNode }>;
  selected?: T[];                      // for multi-select
  multiple?: boolean;
  onSelect: (next: T[]) => void;
  maxWidth?: number;
  align?: "left" | "right";
  closeOnSelect?: boolean;             // default: !multiple
}
```

**Usage（TaskFilters status multi-select）**：
```tsx
<Dropdown
  t={t}
  trigger={<Btn t={t} variant="outline" icon={ICONS.filter}>Status ({selectedStatuses.length})</Btn>}
  items={ALL_STATUSES.map(s => ({value: s, label: STATUS_LABELS[s]}))}
  selected={selectedStatuses}
  multiple
  onSelect={onStatusChange}
/>
```

行為：click outside → close；ESC → close；Enter → select highlighted。

### 2.5 `Drawer.tsx`（side panel shell — 用 Radix Dialog 當 primitive）

```tsx
interface DrawerProps {
  t: ZenInkTokens;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: "right" | "left";
  width?: number | string;              // default: 540; "auto" 允許內容撐
  header?: React.ReactNode;              // top band (stays; does not scroll)
  footer?: React.ReactNode;              // bottom band (stays; does not scroll)
  children: React.ReactNode;             // middle scroll area
  /** Optional desktop-inline mode: at >=1280px render inline instead of overlay. Used by CopilotRailShell. */
  desktopInline?: boolean;
  /** Extension point for future Task L3: header slot for dispatcher badge / handoff timeline tabs. */
  headerExtras?: React.ReactNode;
}
```

**Usage**:
```tsx
<Drawer
  t={t}
  open={open}
  onOpenChange={setOpen}
  header={<DrawerHeader title={task.title} subtitle={task.id} onClose={close} />}
  footer={<ActionsBar onSave={...} />}
>
  <TaskDetailBody task={task} />
</Drawer>
```

**視覺**：
- Overlay: `rgba(20,18,16,0.42)` + `backdropFilter: blur(10px)`（light mode）
- Panel: `background: c.paper`, `borderLeft: 1px solid c.inkHair`, `box-shadow: 0 24px 60px rgba(58,52,44,0.10)`
- Header/Footer：`background: c.surface`，`border-(bottom|top): 1px solid c.inkHair`
- 圓角：`0`（drawer 貼邊）

**擴充預留**：`headerExtras` slot 之後可放 dispatcher badge / handoff timeline tab；`children` 是完全自由的 body。

### 2.6 `Dialog.tsx`（modal shell — Radix Dialog）

```tsx
interface DialogProps {
  t: ZenInkTokens;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  size?: "sm" | "md" | "lg";            // width: 400 / 520 / 720
  children: React.ReactNode;
  footer?: React.ReactNode;
  closable?: boolean;                    // default true
}
```

**Usage（TaskCreateDialog）**：
```tsx
<Dialog
  t={t}
  open={isOpen}
  onOpenChange={(v) => !v && onClose()}
  title="新增任務"
  size="md"
  footer={
    <>
      <Btn t={t} variant="ghost" onClick={onClose}>取消</Btn>
      <Btn t={t} variant="ink" onClick={submit} icon={ICONS.plus}>建立任務</Btn>
    </>
  }
>
  <TaskCreateForm ... />
</Dialog>
```

視覺：center modal，width 依 size，邊框與 Drawer 一致。

### 2.7 `Checkbox.tsx` / `Radio.tsx`

```tsx
interface CheckboxProps {
  t: ZenInkTokens;
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: React.ReactNode;
  disabled?: boolean;
  size?: "sm" | "md";
}

interface RadioProps<T> {
  t: ZenInkTokens;
  name: string;
  value: T;
  selected: T;
  onChange: (v: T) => void;
  label?: React.ReactNode;
  disabled?: boolean;
}
```

視覺：12×12 方框（`radius: 2`），checked 用 ink 填色 + paper 勾號。Radio 用 vermillion 內圓（突出 accent）。

### 2.8 `Tabs.tsx`

```tsx
interface TabsProps<T extends string> {
  t: ZenInkTokens;
  value: T;
  onChange: (v: T) => void;
  items: Array<{ value: T; label: React.ReactNode; disabled?: boolean }>;
  variant?: "underline" | "segment";   // underline = vermillion bottom bar; segment = ink pill group
}
```

**Usage**（CrmAiPanel FollowUpDraft LINE/Email 切換）：
```tsx
<Tabs t={t} value={activeTab} onChange={setActiveTab} items={[
  {value:"line", label:"LINE"},
  {value:"email", label:"Email"},
]} />
```

### 2.9 `Panel.tsx`（取代 shadcn Card）

Zen 沒有「通用 Card」概念——空殼會變 UI 佔位符。提供一個 minimal Panel primitive 給需要時用，但**鼓勵直接 inline 寫**。

```tsx
interface PanelProps {
  t: ZenInkTokens;
  variant?: "surface" | "surfaceHi" | "paperWarm";  // background tier
  outlined?: boolean;                                 // default true
  padding?: number | string;                          // default 16
  children: React.ReactNode;
  style?: React.CSSProperties;
}
```

**Guidance**：如果只是一次性 inline layout，**不要包 Panel**，直接 `<div style={{...}}>`。Panel 只在「同類 panel 反覆出現」的場合用（e.g. Graph context badge 的 neighbor cards）。

### 2.10 `Tooltip.tsx` / `Toast.tsx`（繼續用 Radix primitive）

保留 Radix 的 behavior，外觀改用 Zen inline style。不需新 API，只要在 `src/components/zen/Tooltip.tsx` re-export with styled trigger。

```tsx
// Tooltip（body dark ink on light, paper on dark — 一致反差）
interface ZenTooltipProps {
  t: ZenInkTokens;
  content: React.ReactNode;
  children: React.ReactNode;  // trigger
  side?: "top" | "bottom" | "left" | "right";
}
```

---

## 3. Token Mapping Table

### 3.1 直接對應

| Tailwind class / CSS var | Zen Ink equivalent | 備註 |
|---|---|---|
| `bg-background` | `c.paper` | page background |
| `bg-card` / `bg-card/70` | `c.surface` | 實體面板。**不做半透明**——Zen 紙感不需要 glass effect |
| `bg-secondary` / `bg-muted` | `c.paperWarm` | 次層 tier |
| `bg-popover` | `c.surfaceHi` | floating panels（dropdown, tooltip body） |
| `text-foreground` | `c.ink` | primary text |
| `text-muted-foreground` | `c.inkMuted` | 次要 text |
| `text-foreground/80` | `c.inkSoft` | emphasis-down, still readable |
| `border-border` / `border-border/60` | `c.inkHair` | 1px hairline |
| `border-border` (emphasis) | `c.inkHairBold` | hover / active border |
| `bg-primary` (teal `#47e5d2`) | **廢棄** | 不映射；原本當 CTA 的改 `Btn variant="ink"`；當 accent 的改 `c.vermillion` |
| `text-primary` | 情境判斷：link = `c.ink underlined`；accent = `c.vermillion` |
| `bg-destructive` / `text-red-400` | `c.vermillion` / `c.seal` | Zen 無獨立 destructive color——朱砂同時承擔 accent + danger；靠 Chip tone + iconography 區分 |
| `text-yellow-400` (warn) | `c.ocher` | 赭石 |
| `text-green-400` (success) | `c.jade` | 青竹 |
| `text-blue-400` (info) | `c.inkMuted` | Zen 無 blue；info 降格到中性 |
| `rounded-lg` / `rounded-xl` / `rounded-2xl` / `rounded-full` | `borderRadius: 2` | **一律 2**。例外：avatar、status dot 保 `50%` |
| `shadow-lg` / `shadow-2xl` | `0 24px 60px rgba(58,52,44,0.10)` | 紙感 shadow 要淺、暖調 |
| `backdrop-blur-sm` | `backdropFilter: blur(10px)` + `rgba(20,18,16,0.42)` overlay | overlay 用 ink semi 不用 black |
| `font-bold` | `fontWeight: 500` + `letterSpacing: 0.02em` | Zen 不用 bold（700）——weight 500 + tracking 已足夠權重 |
| `uppercase tracking-widest` | `fontFamily: fontMono, fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase"` | 標籤/eyebrow 統一用 mono |
| shadcn `--ring` (cyan) | `c.vermLine` | focus outline |

### 3.2 沒有直接對應——需要新 pattern

| Tailwind 語意 | 為何沒對應 | Zen pattern |
|---|---|---|
| `bg-card/50` glass effect | Zen 是紙，不是玻璃。半透明 card 疊加在 cyan 漸層 bg 上是 dark SaaS 語法 | 用**實體 tier 切換**表達層次：`c.paper` (outer) → `c.paperWarm` (band) → `c.surface` (card) → `c.surfaceHi` (inset)。4 層已夠 — 不要疊半透明 |
| `bg-gradient-to-tr from-indigo-500 to-purple-500`（avatar glow） | gradient avatar 是當代 SaaS 視覺噪音 | 用 `c.vermSoft` background + `c.vermillion` 單字 initial，border `c.vermLine`。簡單、識別性高 |
| 色彩編碼的 dispatcher tags（blue/purple/amber/emerald…） | Zen 色盤只有 ink/vermillion/jade/ocher——**不擴** | 全部 dispatcher 用 `Chip tone="muted"`（body ink color）+ `variant` 區分 shape / weight。**區分靠文字 label + 單色 dot**，不靠顏色。若覺得太單調，可用 `Chip tone="accent"`（vermillion）標示 `human` dispatcher（表示需要人工介入） |
| priority 的紅橘黃藍 | 同上 | `critical/high → Chip tone="accent"`（朱砂）；`medium → tone="ocher"`；`low → tone="muted"`。依 **danger gradient**（朱砂 > 赭石 > 中性）收斂語意 |
| `bg-red-950/10` overdue task card tint | 不用整卡背景色變，會破壞紙感一致性 | 用 **左側 2px vermillion 線**（與 ZenShell active nav 一致的 pattern）+ `c.vermSoft` 色的小 ribbon |
| drag ring-2 ring-primary/40 | cyan ring 不存在 | border 改 `2px solid c.vermillion`，background `c.vermSoft` |
| animated cyan graph-signal / graph-pulse | KnowledgeGraph 動效本體沒問題，只是顏色 | 全部 stroke / shadow 顏色改 `c.vermillion` 變體；動效保留（Canvas ForceGraph 本身管理） |

### 3.3 Dark mode 映射（Zen 內建）

`ZEN_INK.modes.dark` 已備妥。遷移時 **不特別處理 dark**，所有 primitive 用 `t.c.*`（mode-resolved）即可。風險：Zen/Ink dark 目前沒被全站驗證過（見 §6）。

---

## 4. Migration Order（批次規劃）

以**依賴拓樸 + 風險遞增**排序，每批可獨立 ship 並回退。

### Batch 1：Zen Primitives 補齊（無依賴）
**目標**：`Input` / `Textarea` / `Select` / `Dropdown` / `Checkbox` / `Radio` / `Dialog` / `Drawer` / `Tabs` / `Panel` / `Tooltip`（Zen-styled）
**驗收**：
- 每個 primitive 有 Storybook-like demo page（`/_design/primitives`），全 variant、狀態（default / hover / focus / disabled / error）可視化
- light / dark mode 切換都 OK
- keyboard-only 可操作（Tab / Enter / ESC / Space）
- 對比度達 WCAG AA（文字對背景 ≥ 4.5:1；標籤 ≥ 3:1）

### Batch 2：TaskFilters + TaskCreateDialog
**目標**：兩個最小閉環驗證新 primitives 在真實 flow 裡 OK
**依賴**：Batch 1
**複雜度**：M + M
**驗收**：task 頁面新建 + 過濾功能不回歸；視覺統一到 Zen

### Batch 3：TaskCard + TaskBoard
**目標**：Kanban 全面 Zen 化，包含 DnD 視覺回饋、drag warning modal
**依賴**：Batch 1（Dialog for drag warning）
**複雜度**：M + L
**驗收**：
- DnD 不回歸（dnd-kit 保留）
- priority / dispatcher / overdue 靠 Chip tone + dot + line 表達，不靠多彩背景
- Plan group header 改用 `InkMark` 旁 + `Divider`

### Batch 4：TaskDetailDrawer + TaskAttachments
**目標**：最重的一個元件——側抽屜、inline edit、status dropdown、comments、handoff、attachments
**依賴**：Batch 1-3
**複雜度**：L + M
**驗收**：所有 inline edit / state transition / comment CRUD / attachment upload 不回歸；headerExtras slot 預留未來 Task L3 timeline

### Batch 5：AI Copilot（Chat + Input + Rail + GraphContextBadge）
**目標**：4 個 AI 元件統一
**依賴**：Batch 1（Drawer 取代 Sheet）
**複雜度**：M + S + M + S
**驗收**：
- `CopilotRailShell` 移除 `--primary`/`--card` CSS var hack（原本是因為底下用 shadcn）
- streaming 游標動畫改 `c.vermillion` 閃爍
- GraphContextBadge 所有 radius 從 14/16/999 → 2，保留 tier layering

### Batch 6：CRM（DealDetailWorkspace + CrmAiPanel + DealInsightsPanel + DealDetailClient）
**目標**：Deal 詳細頁全面 Zen 化
**依賴**：Batch 1, 5
**複雜度**：L + L + M + M（最重批次）
**驗收**：
- Stage funnel visualization（6 階段 progress）用 `c.inkHair` line + `c.vermillion` active dot
- Activity timeline 用 `Divider vertical` + date mono label
- AI briefing / debrief panel 用 Drawer + CopilotChatViewport
- FollowUpDraft LINE/Email tab 用新 Tabs

### Batch 7：KnowledgeGraph + AuthGuard cleanup
**目標**：
- `KnowledgeGraph`：強制 `variant="ink"`，callsite 掃一輪
- `AuthGuard`：已全 Zen，只做 hoist `useInk` 消除重複
**依賴**：無
**複雜度**：S + S

### Batch 8：globals.css 清理 + shadcn ui/ 刪除
**目標**：
- 重寫 `globals.css`（見 §5）
- 刪 `src/components/ui/button.tsx`, `card.tsx`, `badge.tsx`, `separator.tsx`
- `sheet.tsx` / `tooltip.tsx` / `toast.tsx` 保留 Radix primitive，但 style 移除、callsite 全改 `zen/Drawer` 等
**依賴**：Batch 1-7 全部完成
**複雜度**：M（高風險——會 break 任何沒遷走的 callsite；CI `grep` Tailwind class 做 safety net）
**驗收**：
- `rg "bg-card|bg-primary|bg-secondary|text-muted-foreground|rounded-xl|rounded-2xl"` on `src/**` 回傳 0
- 頁面實測（dogfood）：tasks / clients / deals / marketing / docs / knowledge-map / home 全部 Zen

---

## 5. `globals.css` 清理計畫

### 5.1 現狀痛點
- `@import "shadcn/tailwind.css"` 引入一大堆 shadcn token
- `:root` 裡塞 30+ CSS variables（`--background: #08131f` 等）——Zen 用不到
- `html/body` 有 `radial-gradient` cyan 漸層背景——與紙感直接衝突
- 強制 override 所有 input / textarea / select 的視覺（lines 132-165）——新 `Input` primitive 完全 inline style，這些是冗餘且有害
- 大量 `.bg-card\/50`, `.bg-blue-900\/50` utility override——遷移後應全部消失

### 5.2 目標骨架

```css
/* globals.css — Zen Ink only */
@import "tailwindcss";  /* 保留 Tailwind preflight（reset）+ 少量 utility（spacing / flex / grid） */

/* NOTE: 不再引入 shadcn/tailwind.css。shadcn theme tokens 全廢棄。 */

@layer base {
  html {
    background: #F4EFE4;  /* ZEN_INK.modes.light.paper */
    color-scheme: light;
    overscroll-behavior-y: none;
  }
  html.dark {
    background: #0D0C0A;  /* ZEN_INK.modes.dark.paper */
    color-scheme: dark;
  }
  body {
    min-height: 100vh;
    font-family: "Helvetica Neue", Helvetica, "Noto Sans TC", "PingFang TC", system-ui, sans-serif;
    color: #141210;
    background: inherit;
  }
  html.dark body {
    color: #ECE5D3;
  }

  /* Global focus ring — vermillion hairline */
  :focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px rgba(182, 58, 44, 0.42);
  }

  ::selection {
    background: rgba(182, 58, 44, 0.24);
    color: #141210;
  }
}

/* KnowledgeGraph animations（保留 — 視覺動效本體不動） */
@layer utilities {
  .graph-core-glow { animation: graph-pulse 6s ease-in-out infinite; }
  .graph-hub       { animation: graph-breathe 5.5s ease-in-out infinite; }
  .graph-node      { animation: graph-float 6s ease-in-out infinite; }
  .graph-node-a { animation-delay: -0.2s; }
  .graph-node-b { animation-delay: -1.4s; }
  .graph-node-c { animation-delay: -2.2s; }
  .graph-node-d { animation-delay: -3.3s; }
  .graph-node-e { animation-delay: -4.1s; }
  .graph-line      { animation: graph-line-fade 4.5s ease-in-out infinite; }
  .graph-line-2, .graph-signal-2 { animation-delay: -1.3s; }
  .graph-line-3, .graph-signal-3 { animation-delay: -2.4s; }
  .graph-line-4 { animation-delay: -0.8s; }
  .graph-line-5 { animation-delay: -1.9s; }
  .graph-line-6 { animation-delay: -2.8s; }
  .graph-line-7 { animation-delay: -3.4s; }
  .graph-line-8 { animation-delay: -4s; }
  .graph-signal {
    stroke-dasharray: 14 120;
    stroke-dashoffset: 140;
    filter: drop-shadow(0 0 6px rgba(182, 58, 44, 0.45));  /* was cyan; now vermillion */
    animation: graph-travel 3.6s linear infinite;
  }
}

@keyframes graph-float { 0%,100% { transform: translate3d(0,0,0) scale(1); } 50% { transform: translate3d(0,-8px,0) scale(1.06); } }
@keyframes graph-breathe { 0%,100% { transform: translate(-50%,-50%) scale(1); } 50% { transform: translate(-50%,-50%) scale(1.06); } }
@keyframes graph-pulse { 0%,100% { opacity: 0.5; transform: translate(-50%,-50%) scale(1); } 50% { opacity: 0.9; transform: translate(-50%,-50%) scale(1.18); } }
@keyframes graph-line-fade { 0%,100% { opacity: 0.28; } 50% { opacity: 0.65; } }
@keyframes graph-travel { from { stroke-dashoffset: 140; } to { stroke-dashoffset: 0; } }

@media (prefers-reduced-motion: reduce) {
  .graph-core-glow, .graph-hub, .graph-node, .graph-line, .graph-signal {
    animation: none !important;
  }
}
```

### 5.3 刪除清單
- `@import "tw-animate-css"`、`@import "shadcn/tailwind.css"`
- `@theme inline { ... --color-* 全部 ... }` 整塊
- `:root { --background / --foreground / --card / ... 全部 30+ }` 整塊
- `:where(input,textarea,select)` override 整塊（新 `Input`/`Textarea`/`Select` 自管）
- `[data-slot="card"]` / `[data-slot="sheet-content"]` 等 shadcn slot override
- 所有 `.bg-card\/50`、`.bg-blue-900\/50`、`.border-border\/30` 等 utility override（Batch 8 完成後無人 import）

### 5.4 保留清單
- Tailwind preflight（reset）
- Tailwind spacing / flex / grid utility（`flex`, `gap-4`, `grid-cols-2` 等仍會在 layout 使用）
- KnowledgeGraph 動效 keyframes
- `prefers-reduced-motion` 總開關

---

## 6. 風險與開放問題

### 6.1 Zen Ink dark mode 尚未全面驗證
**現狀**：`ZenShell.tsx` 寫死 `useInk("light")`，dark mode token 存在但從未被全站 render。
**風險**：Batch 1 的 primitive 要同時支援 dark，但沒有真實頁面測試過。
**建議**：
- Batch 1 demo page 強制做 light / dark toggle
- Batch 8 前加一個「dark mode pass」：在 `ZenShell` 加入 mode toggle 的實際行為（non-op 改成 真的切換），做一輪 dogfood
- 若 dark mode 在 2 週內沒有產品需求，**可以先 ship light-only**，dark 作為 feature flag 保留

### 6.2 Serif + radius 2 在 TaskBoard kanban 會不會過於厚重？
**隱憂**：Serif 標題 + 方正 radius + 紙感背景，在「高密度 resource view」（20+ kanban card × 4 column）可能視覺噪音大，降低掃讀效率。
**建議 A（保守）**：Kanban card title 用 `fontBody`（sans）而非 `fontHead`（serif）——保留 serif 只在頁面 Section heading、Dialog title、CmdK input。這樣 productivity view 仍然清爽。
**建議 B（激進）**：做一個 Zen Ink 子變體 "Zen Workbench"——更緊湊 spacing、全 sans、保留墨紙色但縮 radius 到 1。但這會讓 design system 分叉，我不建議。
**推薦**：A。TaskCard 的 title 用 `fontBody weight:500 size:13 letter:0.02em`，保留 serif 給 Drawer / Dialog / Section。

### 6.3 Task L3 升級的 API 擴充預留
三個未來會加的 UI 呈現，對照 primitive API 確認預留位：

| Task L3 功能 | 對應 UI element | Primitive 擴充位 | 狀態 |
|---|---|---|---|
| dispatcher badge（agent:pm / agent:qa / human…） | TaskCard 左上 Chip + TaskDetailDrawer header | 現有 `Chip tone` 已夠；Drawer `headerExtras` slot | ✅ 預留 |
| handoff_events timeline | TaskDetailDrawer middle scroll 區塊 | Drawer `children` 是開放區塊；無需特別 API | ✅ 無阻礙 |
| subtask tree | TaskCard 下方指示條 + Drawer 內 collapsible tree | 建議 Batch 9（未來）再加 `Tree.tsx` primitive；現在 Drawer body 任意 render，不影響 | ✅ 無阻礙 |
| plan 層級（Plan → Task → Subtask 三層 group） | Kanban column 的 `Plan:` group header 已存在 | TaskBoard 重構時保留 group-by-plan 邏輯，視覺 change only | ✅ 無阻礙 |

**結論**：目前提議的 primitive API **不需要**為 L3 做預先變更，Drawer 的 `headerExtras` slot 已經足夠擴充。

### 6.4 shadcn Radix primitives 保不保留？
**不保**（button / card / badge / separator）：可由 Zen 元件完全替代。
**保 primitive + 換皮**（sheet / tooltip / toast）：Radix 處理 focus trap / aria / portal 的邏輯不簡單，重寫風險高。Zen 只負責外觀，不重造 behavior。

### 6.5 測試策略
- 每個新 primitive 有 `.test.tsx`（React Testing Library）：render, interact, aria 檢查
- 遷移每個元件後，現有 test（`task-operations.test.ts` / `CrmAiPanel.behavior.test.tsx`）**必須全 pass**
- 視覺回歸用人工 dogfood（Batch 8 尾端），不導入自動 visual regression（工具成本高、收益低）

### 6.6 效能
- 所有 primitive 用 inline `style` 物件——每次 render 重建。對高頻 list（kanban 的 100+ card）可能有微觀 perf 影響。
- 建議：TaskCard 用 `useMemo` 包 style 物件；或把大 style 物件抽成 module-level const。
- 不提早優化；Batch 3 完成後跑 React Profiler，有 FPS drop 再處理。

---

## 7. 不在本 spec 範圍

- Task L3 升級的實際 UI 設計（dispatcher badge 具體樣式、handoff_events timeline layout）——遷移完成後另開 Design Spec
- Mobile breakpoint 的深度 rework（目前桌機為主；響應式只保底）
- A11y 之外的 i18n / RTL（Zen 語系為 zh-TW，不考慮 RTL）
- Landing 頁面（`zen/landings/*`）已 Zen，不動

---

## 8. Handoff 給 Architect

1. 先 approve 這份 spec（特別是 §6.2 字型取捨、§6.3 擴充預留、§6.4 primitive 保留策略）
2. 依 §4 批次拆 task：Batch 1 可並行 10 個 primitive 子 task；Batch 2-7 各自為獨立 PR
3. 每個 PR 的 Done Criteria 引用本 spec §2 的 API + §3 的 token mapping
4. Batch 8（globals.css 清理）設為 milestone gate——之前的 batch 不必等
