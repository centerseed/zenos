# 訓練計畫系統 — 模組 Ontology

> 骨架層實體 | confirmedByUser：❌

## 這個模組在做什麼

自動產生每週跑步訓練課表。用戶設定目標比賽（例：16 週後跑全馬），系統根據 ACWR 安全機制 + VDOT 跑力 + 用戶實際完成狀況，每週產出個性化課表。

## 現在正在發生什麼

**v2 課表流程重構** — 解決三個問題：
1. 前後端週數計算不一致（時區問題）
2. 依賴 404 錯誤判斷業務狀態
3. 用戶在週日想提前生成下週課表，但舊架構不支援

解法：新增 `GET /plan/race_run/status` API，後端統一管理狀態。前端根據 `next_action` 決定顯示邏輯。

## 依賴

```
ACWR 安全機制 → 確保每週跑量不超過安全閾值
VDOT 跑力 → 決定配速區間
運動數據整合 → 拿到用戶實際完成的訓練數據
用戶目標 → 比賽日期、目標完賽時間
```

## 相關文件

| 文件 | 用途 | 讀者 |
|------|------|------|
| `WEEKLY_PLAN_STATUS_API_SPEC.md` | v2 狀態 API 完整規格 | 前端+後端開發 |
| `IMPLEMENTATION_SUMMARY.md` | v2 實作摘要 | 開發者 |
| `FRONTEND_IMPLEMENTATION_COMPLETE.md` | 前端實作記錄 | 前端開發 |
| `DEBUG_LOGS_GUIDE.md` | Debug 追蹤用 | 開發者 |
| `2_runing_plan.ipynb` | 課表算法 POC | 了解「為什麼這樣設計」 |
| `estimate_target.ipynb` | 目標估算 POC | 了解目標設定邏輯 |

## 待決策

- v2 重構的完成時程？
- 跟 ACWR 安全修復的優先順序？
