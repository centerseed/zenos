# Paceriz — 神經層（文件級 Ontology Entry 索引）

> 版本：v0.1 | 建構日期：2026-03-21 | confirmedByUser：❌
>
> **這份文件是 AI agent 的路由表。** 不是給人讀的（人看 index.md）。
> AI agent 讀這份文件就知道「哪份文件在講什麼、給誰看、跟什麼有關」。

---

## 核心文件（持續維護、高頻使用）

| # | 路徑 | What | Why | How | Who | 關聯模組 | 狀態 |
|---|------|------|-----|-----|-----|---------|------|
| 1 | `cloud/api_service/CLAUDE.md` | API 開發規範 | 開發效率 + 安全 | 架構規則、測試規範、Bug protocol | 開發者（AI） | 全部 | ✅ 現行 |
| 2 | `apps/flutter/CLAUDE.md` | Flutter 開發規範 | 開發效率 | — | 開發者（AI） | Flutter App | ✅ 現行 |
| 3 | `cloud/api_service/FIRESTORE_STRUCTURE.md` | Firestore 完整結構 | 資料模型 SSOT | 所有 Collection 定義 | 後端開發 | 數據整合, 訓練計畫 | ✅ 現行 |
| 4 | `WEEKLY_PLAN_STATUS_API_SPEC.md` | 週課表狀態 API 規格 | v2 課表流程 | 完整 API spec + 流程圖 | 前端+後端 | 訓練計畫 | ✅ 現行 |
| 5 | `web/official_web/README.md` | 官網產品描述 | 對外展示 | 網站結構 + 設計 | 行銷, 用戶 | 官網 | ✅ 現行 |

## 知識文件（低頻更新、有參考價值）

| # | 路徑 | What | Why | Who | 關聯模組 | 狀態 |
|---|------|------|-----|-----|---------|------|
| 6 | `marketing/paceriz.md` | 運動數據整合技術架構 | 系統記錄 | 開發者 | 數據整合 | ⚠️ 放錯位置 + 可能過時（2024-12） |
| 7 | `cloud/api_service/EXPERT_FEEDBACK_ANALYSIS.md` | ACWR 專家回饋 | 安全改善 | 開發者, 產品 | ACWR | ✅ 有待辦 |
| 8 | `cloud/api_service/ACWR_LITERATURE_REVIEW.md` | ACWR 學術文獻 | 設計依據 | 開發者, 專家 | ACWR | ✅ 現行 |
| 9 | `marketing/用戶留存分析使用指南.md` | 留存分析工具 | 行銷數據 | 行銷, 產品 | 用戶分析 | ✅ 現行 |
| 10 | `apps/flutter/APPSTORE_DEPLOYMENT.md` | App Store 部署 | 部署流程 | 開發者 | Flutter App | ✅ 現行 |
| 11 | `IMPLEMENTATION_SUMMARY.md` | v2 課表實作摘要 | 開發記錄 | 開發者 | 訓練計畫 | ✅ 現行 |
| 12 | `cloud/api_service_cleanup/PROJECT_OVERVIEW.md` | API cleanup 概覽 | 重構記錄 | 開發者 | API | ✅ 現行 |

## Notebook POC（算法設計知識）

| # | 路徑 | What | 關聯模組 | 狀態 |
|---|------|------|---------|------|
| 13 | `1_onboarding.ipynb` | Onboarding 流程設計 | Rizo AI | ⚠️ 未索引 |
| 14 | `1.5_habit_plan.ipynb` | 習慣養成計畫 | 訓練計畫 | ⚠️ 未索引 |
| 15 | `2_runing_plan.ipynb` | 跑步計畫算法 | 訓練計畫 | ⚠️ 未索引 |
| 16 | `3. general_plan.ipynb` | 通用計畫設計 | 訓練計畫 | ⚠️ 未索引 |
| 17 | `5_vita_report.ipynb` | 運動報告設計 | Rizo AI | ⚠️ 未索引 |
| 18 | `VDOT.ipynb` | VDOT 計算驗證 | VDOT | ⚠️ 未索引 |
| 19 | `estimate_target.ipynb` | 目標估算邏輯 | 訓練計畫 | ⚠️ 未索引 |
| 20 | `TSB model.ipynb` | TSB 模型實驗 | ACWR | ⚠️ 未索引 |
| 21 | `prompt_dash.ipynb` | Prompt 設計 | Rizo AI | ⚠️ 未索引 |
| 22 | `poc_notebook/agent_vita_modify_training_plan.ipynb` | Agent 修改訓練計畫 | Rizo AI | ⚠️ 未索引 |
| 23 | `poc_notebook/agent_lanchain_graph.ipynb` | LangChain graph 實驗 | Rizo AI | ⚠️ 未索引 |

## 建議歸檔的文件（一次性開發記錄）

| # | 路徑 | 判斷依據 |
|---|------|---------|
| 24 | `cloud/api_service/CRITICAL_ERRORS_FIX_2026-02-07.md` | 帶日期的一次性修復報告 |
| 25 | `cloud/api_service/FINAL_V3_FIX_REPORT.md` | 「FINAL」= 已完成 |
| 26 | `cloud/api_service/COMPLETE_REFACTOR_SUMMARY.md` | 重構完成報告 |
| 27 | `cloud/api_service/V3_COMPLETE_FIX_REPORT.md` | V3 修復報告 |
| 28 | `cloud/api_service/V3_VALIDATION_FIX_REPORT.md` | V3 驗證報告 |
| 29 | `cloud/api_service/V3_ARCHITECTURE_MISMATCH_FIX.md` | 架構修復報告 |
| 30 | `cloud/api_service/INTENSITY_FIX_SUMMARY.md` | 強度修復報告 |
| 31 | `cloud/api_service/SERVICES_REFACTOR_SUMMARY.md` | 重構報告 |
| 32 | `cloud/api_service/IMPORT_SHADOWING_AUDIT.md` | 稽核報告 |
| 33 | `cloud/api_service/REFACTOR_COMPLETE.md` | 重構完成 |
| 34 | `cloud/api_service/CONTEXT_DATA_ANALYSIS.md` | 數據分析記錄 |
| 35 | `cloud/api_service/DOCUMENTATION_SUMMARY.md` | 文件摘要 |
| 36 | `cloud/api_service/FIREBASE_INIT_IMPROVEMENT_PLAN.md` | 改善計畫 |
| 37 | `FRONTEND_IMPLEMENTATION_COMPLETE.md` | 實作完成記錄 |
| 38 | `DEBUG_LOGS_GUIDE.md` | Debug 輔助 |

---

## 統計

| 類別 | 數量 |
|------|------|
| 核心文件（持續維護） | 5 |
| 知識文件（有參考價值） | 7 |
| Notebook POC | 11 |
| 建議歸檔 | 15 |
| **總計** | **38** |

**覆蓋率：** 38 份非程式碼文件中，5 份是核心、7 份有價值、11 份未索引、15 份建議歸檔。如果執行歸檔 + notebook 索引，活文件從 38 份降到 23 份，噪音大幅下降。

---

*AI 自動建構。神經層 entry 的 What/Who 維度信心較高，Why/How 需人確認。*
