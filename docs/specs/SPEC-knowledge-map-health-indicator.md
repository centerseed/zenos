---
type: SPEC
id: SPEC-knowledge-map-health-indicator
status: Draft
ontology_entity: 語意治理-pipeline
created: 2026-04-09
updated: 2026-04-09
---

# Feature Spec: 知識地圖治理健康提示

## 第一章：背景與動機

### 問題陳述

ZenOS 的治理健康機制（ADR-020）已在 server 端落地：每次 sync 完成後，系統自動計算 6 項 KPI 並判定整體健康等級（green / yellow / red）。這個信號目前只在 MCP tool 的回傳中附帶，面向的讀者是 agent。

用戶——也就是使用 Dashboard 管理知識地圖的人——完全看不到這個信號。

結果是：**用戶不知道 ontology 品質正在退化，直到 agent 給出的建議開始變差才發現。**

### 用戶原話

> 「分數好不好我自己很難判斷，但我不想爛到當 agent 運作的越來越不如預期才發現這件事。」

### 為什麼現在要做

1. ADR-020 已實作 health signal 計算邏輯，基礎設施已存在。
2. 用戶無法判斷數字好壞，需要系統替他判斷。
3. 問題不是「算不算得出來」，而是「算出來的結果只在 agent 通道，Dashboard 拿不到」。

### 與既有文件的關係

| 文件 | 關係 |
|------|------|
| SPEC-governance-feedback-loop | 定義 server → agent 的被動治理通道（P0-3）。本 Spec 是 Dashboard → 用戶的可見性延伸。 |
| ADR-020 | 本 spec 的 health signal 數據來源。計算邏輯不需重新定義。 |

---

## 第二章：目標用戶

使用 Dashboard 管理 ZenOS 知識地圖的業主或管理員。

- 不懂 KPI 術語（quality_score、unconfirmed_ratio）
- 不需要知道哪個指標出問題
- 不需要看數字
- 只需要知道「現在需不需要做什麼」

---

## 第三章：需求

### P0-1：知識地圖頁面顯示治理健康狀態

系統替用戶判斷。沉默 = 正常。

**AC：**

```
Given 用戶打開知識地圖頁面，
When 治理健康等級為 green，
Then 頁面不顯示任何治理相關提示。
```

```
Given 用戶打開知識地圖頁面，
When 治理健康等級為 yellow，
Then 頁面以溫和樣式顯示一行提示，
  告知「知識地圖有些內容可能需要整理」，
  不遮蓋主要內容，不要求立即行動。
```

```
Given 用戶打開知識地圖頁面，
When 治理健康等級為 red，
Then 頁面顯示稍強提示，
  告知「知識地圖的品質可能正在影響 agent 的建議準確度」，
  附帶行動引導。
```

```
Given 頁面顯示治理提示，
Then 提示不包含 KPI 術語、不顯示數字、不解釋是哪個維度出問題。
```

### P0-2：引導用戶到 Claude Code 執行治理（C 路線）

Dashboard 不直接觸發 AI agent，而是引導用戶回到 Claude Code。

**AC：**

```
Given 治理健康等級為 yellow 或 red，
When 頁面顯示治理提示，
Then 提示附帶引導文字：「請在 Claude Code 中執行 /zenos-governance 進行自動治理」。
```

```
Given 用戶看到引導提示，
Then 提示可複製指令文字（/zenos-governance），方便用戶直接貼到 Claude Code。
```

```
Given 治理健康等級為 red，
Then 引導文字語氣更明確：「建議儘快在 Claude Code 中執行 /zenos-governance」。
```

### P0-3：健康狀態在頁面開啟時取得

允許最多 24 小時延遲，不依賴 cronjob。

**AC：**

```
Given 用戶打開知識地圖頁面，
When 系統有最近 24 小時內計算的健康狀態，
Then 頁面在 2 秒內顯示該狀態。
```

```
Given 用戶打開知識地圖頁面，
When 系統沒有最近 24 小時內的健康狀態，
Then 系統觸發一次輕量計算（analyze check_type="health"），
  或顯示「狀態尚未更新」。
```

```
Given 頁面正在載入健康狀態，
Then 顯示適當的載入狀態，不呈現空白或閃爍。
```

### P1-1：治理完成後，狀態自動更新

```
Given 用戶在 Claude Code 完成 /zenos-governance，
When 下次打開知識地圖頁面，
Then 健康狀態反映治理後的最新結果。
```

---

## 第四章：明確不包含

- **不顯示 KPI 數字** — quality_score 等指標值不對用戶顯示
- **不區分哪個 KPI 出問題** — 提示不說明具體缺陷方向
- **不從 Dashboard 觸發 AI agent** — Phase 0 不建 agent runtime（見第九章演化路徑）
- **不做治理狀態追蹤** — 不追蹤「治理是否在進行中」
- **不提供歷史趨勢** — 不顯示健康分數走勢
- **不發 email / push notification** — 提示只在知識地圖頁面顯示
- **不限制用戶操作** — 提示是建議，不是阻擋

---

## 第五章：技術約束（給 Architect）

### 需要實作

1. **Dashboard API endpoint**：回傳 overall_level（green / yellow / red），不需暴露完整 KPI。可呼叫 GovernanceService.compute_health_signal() 取得。
2. **Health signal 快取**：batch_update_sources 或 write 操作完成後，將 overall_level 寫入 DB 或快取。頁面開啟時讀取快取，過期（>24h）時重算。

### C 路線已移除的複雜度

- 不需要 agent runtime 基礎設施
- 不需要 WebSocket / SSE 做治理狀態推送
- 不需要 job queue 管理 agent session
- 不需要 human-in-the-loop Dashboard UI
- 不需要治理進度追蹤 API

---

## 第六章：開放問題

1. **yellow 提示文案語氣**：「可能需要整理」vs「偵測到品質下降」——建議先上線再觀察。
2. **yellow 是否可被用戶忽略**：目前定義為持續顯示直到狀態回 green，不提供「已讀」功能。
3. **門檻保守度**：寧可早觸發（多一次不必要整理）而非晚觸發（agent 已在給爛建議）。ADR-020 門檻值在 Phase 0 實測後校準。

---

## 第七章：完成定義

1. 知識地圖頁面正確呈現 green（沉默）/ yellow（溫和提示）/ red（稍強提示 + 引導文字）
2. 引導文字包含可複製的 `/zenos-governance` 指令
3. 健康狀態資料不超過 24 小時舊
4. 提示中不出現任何技術術語或數字

---

## 第八章：Spec 相容性

| 文件 | 關係 |
|------|------|
| SPEC-governance-feedback-loop | 共用 ADR-020 health signal，但服務不同消費者（agent vs 用戶） |
| ADR-020 | 數據來源，計算邏輯不重新定義 |
| SPEC-dashboard-v2-ui-refactor | UI 元件應符合 Dashboard v2 設計系統 |

---

## 第九章：演化路徑——從 C 到 A

### 三條路線對比

| | C（Phase 0） | B（Phase 0.5） | A（Phase 1+） |
|---|---|---|---|
| 執行者 | 用戶在 Claude Code 手動跑 | Server 規則引擎（無 LLM） | Server-side AI agent |
| 能做 | 引導提示 | 確定性修復（刪重複、清孤立） | 完整治理（含語意判斷） |
| 確認方式 | 在 Claude Code 對話中 | 自動或 Dashboard 內確認 | Dashboard 內 human-in-the-loop |
| Dashboard 角色 | 唯讀 + 引導 | 唯讀 + 簡單操作 | 完整治理控制台 |

### Phase 0 → Phase 0.5（C → B）

**觸發條件：** 用戶反饋「每次都要切到 Claude Code 太麻煩」，或治理頻率高到手動不合理。

**前提：**
- Dashboard API 已穩定（本 Spec P0 完成）
- 識別出哪些治理操作是確定性的（不需要 LLM 判斷）

**新增能力：**
- Dashboard 按鈕觸發 server-side 確定性修復（刪重複 blindspot、清孤立關聯、歸檔過期文件）
- 修復完成後自動更新 health signal
- 需要語意判斷的操作仍引導到 Claude Code

### Phase 0.5 → Phase 1+（B → A）

**觸發條件：** 確定性修復覆蓋率不足（大部分問題仍需 AI 判斷），或多用戶場景需要非技術人員也能觸發治理。

**前提：**
- Agent runtime 基礎設施（server-side Claude API 呼叫能力）
- Job queue（治理 session 可能跑數分鐘）
- WebSocket 或 SSE（即時推送治理進度到 Dashboard）
- Human-in-the-loop API（Dashboard 內呈現確認請求、用戶回應後繼續治理）
- Session 安全性（agent 操作需受 partner scope 限制）

**新增能力：**
- Dashboard「啟動自動治理」按鈕直接觸發 AI agent
- Dashboard 內顯示治理進度
- Dashboard 內處理人工確認步驟
- 治理完成後自動更新狀態
