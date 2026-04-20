---
type: BACKLOG
id: BACKLOG-zen-ink-data-gaps
status: Open
created: 2026-04-19
related_spec: SPEC-zen-ink-real-data.md
---

# BACKLOG: Zen Ink 真實資料接線的後端缺口

此文件記錄 P0 接線階段所有以 `—`（em-dash）佔位的欄位，以及對應的後端缺口。每一項是未來 Sprint 的候選 item。

## Knowledge Map (`/knowledge-map`)

| 欄位 | 目前顯示 | 後端缺口 | 建議 API shape |
|---|---|---|---|
| 節點 `meta`（"12 個任務 · 3 個阻塞"）| `entity.owner` or `—` | 無聚合 endpoint | `getEntityStats(entityId)` → `{ taskCount, blockedCount, docCount }` |
| Inspector「近期活動」 | `—` 單行 | 無 activity feed API | `getEntityActivity(entityId, limit)` → `Activity[]` |
| Zoom controls | 靜態按鈕 | N/A (frontend only) | 接 pan/zoom library（react-svg-pan-zoom） |

## Projects (`/projects`)

| 欄位 | 目前顯示 | 後端缺口 | 建議 |
|---|---|---|---|
| 卡片 `code` 前綴 | `entity.id.slice(0,8)` | Entity 無 code 欄位 | 加 `Entity.code: string \| null` |
| 健康狀態（順利/風險/暫停）| 從 entity.status 推 | `status` 語意不對應健康度 | 加 `Entity.healthLevel?: "green" \| "yellow" \| "red"` |
| 成員數 | `—` | Entity 無 members 陣列 | `getEntityMembers(entityId)` → `Partner[]` |
| 文件數 | `—` | 無聚合 count | `getEntityStats` 內含 |
| 截止日 | `—` | Entity 無 due_date | 加 `Entity.dueDate?: Date` |
| Milestones | "無里程碑資料" | 無 milestone concept | `getEntityMilestones(entityId)` → `Milestone[]` |
| 近期動態 | `—` | 同 Map 的 activity | 共用 `getEntityActivity` |
| KPI「本週到期」 | `—` | 依賴 due_date | 依 due_date 補上後可算 |
| KPI「待分派任務」 | `—` | Task.assignee 存在但需批次 | `getUnassignedTasks(workspace)` |
| Detail 文件 tab | `—` | 無 related docs API | `getEntityDocuments(entityId)` → `Document[]` |
| Detail 成員 tab | 只顯示 owner | `getEntityMembers` |
| Detail 時程 tab | `—` | 需 milestones + timeline | 合併 milestones + activity |

## Clients (`/clients`)

| 欄位 | 目前顯示 | 後端缺口 | 建議 |
|---|---|---|---|
| 聯絡人 sidebar | `—` | DealDetail 未呼叫 `getCompanyContacts` | Detail view 加第二次 API call |
| Deal owner 顯示名 | partner UUID 原字串 | 無 partner join | Deal 回傳時 join `ownerDisplayName` |
| 承諾事項 CRUD | 只讀不可寫 | `createCommitment` / `deleteCommitment` API 缺 | 加對應 mutation |

## Marketing (`/marketing`)

| 欄位 | 目前顯示 | 後端缺口 | 建議 |
|---|---|---|---|
| KPI「本月觸及」| `—` | 無 post performance API | `getMarketingMetrics(workspace, period)` |
| KPI「轉換率」| `—` | 同上 | 同上 |
| KPI「Agent 草稿」 | `—` 或 prompts count | 無 draft state aggregation | `getMarketingDrafts(workspace)` |
| `channel` 欄位 | 用 description 替代 | 無獨立 channel 欄位 | 加 `MarketingProject.channel?: string` |
| `perf` bar | 永遠 0%/`—` | 無 per-campaign metrics | 同上 metrics API |
| 6-stage stepper mapping | 純前端狀態 | 後端無對應 stage 欄位 | `MarketingProject.stage: 0-5` |
| AI rail（cowork integration）| `—` | cowork workspace integration 尚未接 | Phase 2 cowork API |
| 新 Campaign flow | disabled | 需 product picker + createMarketingProject wiring | UX 設計後接 |
| Style delete | 無按鈕 | 無 `deleteMarketingStyle` API | 加 DELETE endpoint |

## MCP 設定頁 (`/agent`)

| 欄位 | 目前顯示 | 後端缺口 | 建議 |
|---|---|---|---|
| MCP server registry | 單一 hosted | 無 server registry | Phase 2: `getMCPServers(partner)` |
| 「新增 server」按鈕 | 隱藏 | 同上 | 同上 |
| 健康檢查 heuristic | `res.ok \|\| 405` | MCP 無 `/health` endpoint | 後端加 `GET /health` 回 `{ok: true}` |
| LOCAL HELPER KPI | `—` | 瀏覽器無法偵測本地 CLI | 需 CLI 主動 ping dashboard（Phase 3） |
| SKILLS KPI（本地 runs/version）| `—` | 同上 | 同上 |
| `.claude/mcp.json` / `settings.json` 讀寫 | `—`（只給複製 snippet） | 瀏覽器無法讀本地 FS | 永遠是 dashboard 限制；繼續靠 CLI |

## 共用

- **Zen Ink 視覺準則**：所有空值一律 em-dash `—`（不是 `N/A` / `null` / 留白 / loading…）
- **Empty state 文案**：保持中文 + 節氣風格，配色用 `c.inkFaint`（最淡墨）

## 優先級建議（給下次 Sprint）

**P1 — 使用體驗明顯感到「缺東西」**
1. Projects 健康狀態 + due_date + members
2. Knowledge Map 節點 stats（taskCount / blockedCount）
3. Clients owner 顯示名 join

**P2 — 功能完整性補強**
4. Marketing metrics API + channel 欄位
5. Entity activity feed（Map + Projects 共用）
6. Milestones concept

**P3 — 進階整合**
7. MCP `/health` endpoint
8. cowork integration for Marketing AI rail
9. Local CLI ↔ dashboard state sync
