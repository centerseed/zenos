# Paceriz — Ontology 全景（骨架層）

> 版本：v0.1 draft | 建構日期：2026-03-21 | confirmedByUser：❌
>
> **這份文件是給老闆看的。** 2 分鐘讀完就知道 Paceriz 全貌。
> 想深入某個模組 → 看 `modules/` 裡對應的檔案。

---

## 一句話

**Paceriz 是 AI 驅動的個人化跑步訓練助手，整合多平台運動數據，用科學化訓練負荷管理幫跑者安全進步。**

## 產品現況

| 欄位 | 內容 |
|------|------|
| 階段 | 已上線 App Store，持續迭代 |
| 公司 | Havital |
| 市場 | 台灣為主（zh-TW 優先） |
| 團隊 | Barry（全端 + 產品決策）|
| 核心差異化 | AI 教練 Rizo + ACWR 科學化訓練安全管理 |

## 功能模組全景

```
Paceriz
  │
  ├── 🤖 Rizo AI 教練 ✅         → modules/rizo-ai.md
  │     基於統一數據模型，提供個性化訓練建議
  │     依賴：運動數據整合 + 訓練計畫
  │
  ├── 📅 訓練計畫系統 ✅（v2 優化中）→ modules/training-plan.md
  │     自動產生週課表、週回顧、提前生成下週課表
  │     依賴：ACWR 安全機制
  │     ⚠️ v2 課表流程正在重構（前後端週數同步問題）
  │
  ├── 🔄 運動數據整合 ✅          → modules/data-integration.md
  │     Garmin✅ Apple Health✅ Strava📋
  │     統一數據模型 + 多平台適配器
  │
  ├── 🛡️ ACWR 安全機制 ✅（有已知問題）→ modules/acwr.md
  │     急慢性訓練負荷比，防止過度訓練
  │     ⚠️ 專家確認三項安全問題待修
  │
  ├── 📊 VDOT 跑力計算 ✅
  │     根據實際表現動態計算跑力值
  │
  ├── 🌐 官方網站 ✅
  │     產品展示 + 下載引導
  │
  └── 📈 用戶留存分析 ✅
        GA4 + Firebase 數據分析工具
```

## 模組間依賴關係

```
用戶的 GPS 手錶（Garmin / Apple Watch）
      │
      ▼
運動數據整合 ──→ 統一數據模型（UnifiedWorkoutModel）
      │                    │
      │                    ▼
      │              VDOT 跑力計算
      │                    │
      ▼                    ▼
ACWR 安全機制 ◄─── 訓練計畫系統
      │                    │
      │                    ▼
      └──────────→ Rizo AI 教練 ──→ 用戶
```

**關鍵依賴鏈：** 運動數據整合 → ACWR → 訓練計畫 → Rizo AI。如果數據整合出問題，整條鏈都受影響。

## 目前活躍目標

| 目標 | 優先級 | 關聯模組 | 狀態 |
|------|--------|---------|------|
| v2 課表流程優化 | ？ | 訓練計畫系統 | 🔄 進行中 |
| ACWR 安全性改善 | ？ | ACWR 安全機制 | 🔄 專家回饋已收到，待排入 |
| Strava 整合 | ？ | 運動數據整合 | 📋 規劃中 |

> ⚠️ **三個目標的優先級還沒有被明確定義。** ACWR 是安全問題（用戶可能受傷），v2 課表是使用體驗，Strava 是市場擴張。老闆需要決定順序。

## ⚠️ AI 發現的盲點

詳見 → [blindspots.md](blindspots.md)

摘要：
1. 🔴 marketing/ 裡沒有行銷素材（全是技術文件）
2. 🔴 ACWR 三項安全問題已確認但未排修復時程
3. 🟡 20+ 份一次性開發報告混在活文件中
4. 🟡 Notebook POC 是寶貴知識但完全沒索引

---

## 導航

| 想知道... | 去看 |
|----------|------|
| Rizo AI 教練能做什麼、怎麼運作 | [modules/rizo-ai.md](modules/rizo-ai.md) |
| 訓練計畫怎麼生成、v2 改了什麼 | [modules/training-plan.md](modules/training-plan.md) |
| 支援哪些手錶、數據怎麼進來 | [modules/data-integration.md](modules/data-integration.md) |
| ACWR 是什麼、專家說了什麼問題 | [modules/acwr.md](modules/acwr.md) |
| 有什麼風險和盲點 | [blindspots.md](blindspots.md) |
| 每份文件的索引（AI agent 用） | [neural-layer.md](neural-layer.md) |

---

*AI 從 45 份文件自動建構。骨架層需 Barry 確認後生效。*
