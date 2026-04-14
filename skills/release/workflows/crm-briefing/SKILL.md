---
name: crm-briefing
description: >
  商談前 AI 簡報流程。依 deal context pack 生成結構化簡報，
  並回寫到 ZenOS deal entity（type: crm_briefing）。
version: 0.1.0
---

# /crm-briefing

## 目的

在每次商談前，以最少準備成本為業務提供完整的客戶洞察與本次建議。

## 輸入契約（Context Pack）

由 Dashboard 前端組裝後傳入：

```json
{
  "scene": "briefing",
  "deal_id": "deal-xxx",
  "company": {
    "name": "...",
    "industry": "...",
    "size_range": "...",
    "region": "..."
  },
  "deal": {
    "title": "...",
    "funnel_stage": "...",
    "deal_type": "...",
    "source_type": "...",
    "amount_twd": 500000,
    "scope_description": "...",
    "deliverables": ["..."]
  },
  "activities_summary": "最近 N 筆活動的摘要（≤1500 字）",
  "contacts": [{ "name": "...", "title": "..." }],
  "previous_briefings_count": 2,
  "suggested_skill": "/crm-briefing"
}
```

## 執行步驟

1. 讀取 deal entity context：
```python
mcp__zenos__get(collection="entities", id="{deal_id}")
```

2. 依可用資料決定產出層級：
   - 資料少（無 activities_summary、無 contacts）：產出基礎區塊（客戶背景 + 本次建議）
   - 資料完整：產出全部區塊

3. 生成結構化簡報（見輸出格式）

4. 回寫 entry 到 ZenOS：
```python
mcp__zenos__write(
    collection="entries",
    type="crm_briefing",
    parent_id="{deal_id}",
    content="<簡報全文>",
    details={
        "funnel_stage": "<漏斗階段>",
        "briefing_version": "<previous_briefings_count + 1>"
    }
)
```

## 輸出格式

每個區塊包含標題和內容。區塊依資料可用性條件產出：

### 區塊 1：客戶背景（必出）

整理 CRM 中的公司基本資訊：
- 公司名稱、產業、規模、地區
- Deal 名稱、類型、金額（TWD）、來源
- 主要聯絡人與職稱

### 區塊 2：互動回顧（有 activities_summary 才產出）

過去所有互動的重點摘要：
- 已討論的核心需求
- 客戶表達過的顧慮或反對意見
- 過去承諾但尚未確認的事項

### 區塊 3：產品現況（有相關 ZenOS entity 才產出）

客戶關心的功能在 ZenOS ontology 中的狀態：
- 功能名稱與當前狀態
- 路線圖位置（若有）
- 替代方案或限制說明

### 區塊 4：本次建議（必出）

依漏斗階段（`deal.funnel_stage`）給出：
- 本次會議目標（1-3 個具體目標）
- 建議準備的素材或 demo
- 應避免的地雷（基於過去互動或階段慣例）

## 分層產出規則

| 資料狀況 | 產出區塊 |
|---------|---------|
| 僅有 company + deal | 區塊 1 + 區塊 4 |
| 有 activities_summary | 區塊 1 + 區塊 2 + 區塊 4 |
| 有相關 entity | 區塊 1 + 區塊 3 + 區塊 4 |
| 資料完整 | 區塊 1 + 區塊 2 + 區塊 3 + 區塊 4 |

## 寫回規範

- entry type：`crm_briefing`
- parent：deal entity（`deal_id`）
- 不新增 MCP tool，只用既有 `get/write`
- 每次商談前執行一次；`briefing_version` 遞增
