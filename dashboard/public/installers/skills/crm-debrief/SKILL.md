---
name: crm-debrief
description: >
  會後自動分析 Activity 摘要，產出洞察和 follow-up 草稿（LINE + Email 雙版本），
  並回寫 crm_debrief 與 crm_commitment entries 到 ZenOS deal entity。
version: 0.1.0
---

# /crm-debrief

## 目的

會議結束後，立即從使用者輸入的 Activity 摘要提煉關鍵洞察、承諾事項，
並生成可直接發送的 follow-up 草稿，降低業務會後整理成本。

## 輸入契約（Context Pack）

由 Dashboard 前端組裝後傳入：

```json
{
  "scene": "debrief",
  "deal_id": "deal-xxx",
  "company_name": "...",
  "deal_title": "...",
  "funnel_stage": "需求訪談",
  "activity": {
    "type": "會議",
    "summary": "使用者剛寫的完整 Activity 摘要"
  },
  "recent_commitments": ["上次承諾事項..."],
  "suggested_skill": "/crm-debrief"
}
```

## 執行步驟

1. 讀取 deal entity context：
```python
mcp__zenos__get(collection="entities", id="{deal_id}")
```

2. 分析 `activity.summary`，提取以下資訊：
   - 關鍵決策（明確決定的事）
   - 客戶顧慮（疑慮、反對意見、未解問題）
   - 承諾事項（我方承諾 / 客戶承諾，含預估期限）
   - 階段推進判斷（依當前 funnel_stage 評估是否該推進）
   - 下一步行動（具體事項與時間）

3. 生成 follow-up 草稿（兩個版本，見輸出格式）

4. 回寫 debrief entry：
```python
mcp__zenos__write(
    collection="entries",
    type="crm_debrief",
    parent_id="{deal_id}",
    content="<debrief 全文>",
    details={
        "funnel_stage": "<漏斗階段>",
        "activity_type": "<activity.type>",
        "stage_advance_suggested": true | false
    }
)
```

5. 每個承諾事項獨立寫為 entry：
```python
mcp__zenos__write(
    collection="entries",
    type="crm_commitment",
    parent_id="{deal_id}",
    content="<承諾描述>",
    details={
        "owner": "我方 | 客戶",
        "deadline": "YYYY-MM-DD 或自然語言期限",
        "status": "open"
    }
)
```

## 輸出格式

### 區塊 1：關鍵決策

這次會議明確決定的事項（若無則標記「本次無明確決策」）：
- 每項決策一行，格式：`[決策內容]`

### 區塊 2：客戶顧慮

客戶表達的疑慮與反對意見：
- 每項顧慮一行，格式：`[顧慮內容] — 建議回應方向`

### 區塊 3：承諾事項

分我方承諾與客戶承諾兩欄：

**我方承諾：**
- `[事項] — 建議期限：[日期]`

**客戶承諾：**
- `[事項] — 預期時間：[日期]`

### 區塊 4：階段建議

依 `funnel_stage` 評估：
- 當前階段：`[funnel_stage]`
- 建議：推進至下一階段 / 維持當前階段 / 需補充資訊後再評估
- 判斷依據：`[1-2 句說明]`

### 區塊 5：下一步行動

具體行動清單：
- `[行動事項] — 負責人：[我方/客戶] — 期限：[日期]`

### 區塊 6：Follow-up 草稿

#### LINE 版本

規範：
- 長度：≤300 字
- 語氣：口語、有溫度，避免 email 格式用語（如「敬啟者」「敬祝」）
- 結構：問候 → 重點摘要 → 下一步 → 結尾
- Emoji：允許 ≤3 個，置於自然斷句處，不堆疊

格式範例：
```
[問候語] 感謝今天的時間！

今天確認了 [重點 1] 和 [重點 2]。

接下來我這邊會在 [期限] 前準備好 [事項]，你們這邊也麻煩確認 [客戶承諾事項]。

有任何問題隨時找我！😊
```

#### Email 版本

規範：
- 長度：≤500 字（不含主旨行）
- 語氣：專業但友善
- 結構：主旨行 → 感謝 → 摘要 → 承諾確認 → 下一步 → 結尾

格式範例：
```
主旨：[會議主題] 會後紀錄與後續事項 — [公司名稱]

您好，

感謝今天撥冗與我們會面。以下是今天會議的摘要與後續安排：

[重點摘要]

承諾事項確認：
- 我方：[事項]（期限：[日期]）
- 貴方：[事項]（期限：[日期]）

下一步：
[下一步行動]

如有任何問題，歡迎隨時聯繫。

[業務姓名]
```

## 寫回規範

| 內容 | entry type | parent |
|------|-----------|--------|
| Debrief 整體 | `crm_debrief` | deal entity |
| 每個承諾事項 | `crm_commitment` | deal entity |

- 不新增 MCP tool，只用既有 `get/write`
- `crm_commitment` 的 `status` 初始為 `open`，由業務手動更新為 `done`
- 每次會議後執行一次；同一 deal 可有多筆 `crm_debrief`
