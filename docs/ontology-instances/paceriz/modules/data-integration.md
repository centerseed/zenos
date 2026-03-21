# 運動數據整合 — 模組 Ontology

> 骨架層實體 | confirmedByUser：❌

## 這個模組在做什麼

把跑者的運動數據從不同平台（手錶、App）匯入 Paceriz。不管數據來自哪裡，都轉成統一格式（UnifiedWorkoutModel），讓 Rizo AI 和訓練計畫系統可以直接使用。

## 支援的平台

| 平台 | 接入方式 | 狀態 |
|------|---------|------|
| **Garmin** | OAuth + Webhook 即時推送 | ✅ 生產環境 |
| **Apple Health** | App 內手動上傳 | ✅ 生產環境 |
| **Strava** | OAuth（規劃中） | 📋 原定 Q2 2025 |

## 核心技術

**UnifiedWorkoutAdapter** — 統一適配器，把不同平台的數據格式轉成 UnifiedWorkoutModel：
- 基礎指標（距離、時間、心率、配速）
- 進階指標（VDOT、TSS、訓練強度）
- 時間序列（GPS 軌跡、心率曲線）
- 環境數據（溫度、濕度）

**歷史數據處理器** — 用戶綁定帳號後自動掃描最近 60 天數據，並行處理。

## 依賴

```
OAuth 安全框架 → 第三方平台授權
Webhook → Garmin 即時數據推送
GCS → 原始數據保留
Firestore → 結構化數據存儲（workouts_v2）
→ 輸出：統一格式的運動數據 → 給 ACWR、VDOT、Rizo、訓練計畫使用
```

## 相關文件

| 文件 | 用途 | 讀者 |
|------|------|------|
| `marketing/paceriz.md` | 數據整合技術架構全文（395 行）| 開發者（⚠️ 放錯位置，不是行銷素材）|
| `cloud/api_service/FIRESTORE_STRUCTURE.md` | Firestore 完整結構 | 後端開發 |

## 待決策

- Strava 整合的實際時程？（原定 Q2 2025 已過）
- Coros / Polar 還在規劃中嗎？
