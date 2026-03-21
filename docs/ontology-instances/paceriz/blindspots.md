# Paceriz — 盲點分析

> AI 從文件交叉比對推斷 | 建構日期：2026-03-21 | confirmedByUser：❌

---

## 🔴 高優先級

### 1. marketing/ 裡沒有行銷素材

**事實：**
- `marketing/paceriz.md` 是 395 行的技術架構文件（Webhook、OAuth、Firestore 結構圖）
- `marketing/` 其他檔案是 Python 分析腳本（firebase_user_analytics.py、run_analysis.py）
- `marketing/用戶留存分析使用指南.md` 是工具使用手冊，不是行銷素材

**推斷：** 行銷夥伴打開 marketing/ 想找素材，找到的全是技術內容。唯一有行銷語言的是 `web/official_web/README.md`，但那在完全不同的路徑。

**影響：** 行銷夥伴無法自主產素材，必須等 Barry 翻譯技術內容 → Barry 成為瓶頸。

**建議動作：** 用 Context Protocol（已有 `context-protocols/paceriz.md`）作為行銷夥伴的入口。或在 marketing/ 新增一份非技術的產品簡介。

---

### 2. ACWR 三項安全問題已確認但未排修復時程

**事實：**
- `EXPERT_FEEDBACK_ANALYSIS.md` 明確標記三項為「✅ 確定有問題」
- 第一週無保護（ACWR = 9999）、Taper 後恢復缺失、邏輯一致性衝突
- 文件標記部分為「暫不修改，等待用戶反饋」

**推斷：** 這些是訓練安全問題（用戶可能因過度訓練受傷），但沒有看到對應的修復 task 或時程。同時 Strava 整合也在規劃中。

**影響：** 如果有用戶在第一週因沒有 ACWR 保護而受傷，比「還不支援 Strava」嚴重得多。安全 > 功能。

**建議動作：** 明確定義 ACWR 修復 vs Strava 整合 vs v2 課表的優先順序。

---

## 🟡 中優先級

### 3. 一次性開發報告混在活文件中

**事實：** `cloud/api_service/` 下有 ~15 份 MD 文件是開發過程的一次性記錄：
- `CRITICAL_ERRORS_FIX_2026-02-07.md`
- `FINAL_V3_FIX_REPORT.md`
- `COMPLETE_REFACTOR_SUMMARY.md`
- `SERVICES_REFACTOR_SUMMARY.md`
- `V3_*` 系列（3 份）
- `INTENSITY_FIX_SUMMARY.md`
- `IMPORT_SHADOWING_AUDIT.md`
- 等等

同時有 ~5 份是活的文件：`CLAUDE.md`、`FIRESTORE_STRUCTURE.md`、`EXPERT_FEEDBACK_ANALYSIS.md`、`ACWR_LITERATURE_REVIEW.md`。

**推斷：** 新開發者或 AI agent 進到這個資料夾，分不清哪些是最新的、哪些已經過時。一次性報告的價值在產生當下，之後很少被重讀。

**影響：** 知識噪音高。AI 讀這些文件浪費 token 且可能讀到過時資訊。

**建議動作：** 把一次性報告移到 `archive/` 或 `dev-history/`。10 分鐘的整理工作。

---

### 4. Notebook POC 是寶貴知識但完全沒索引

**事實：** 根目錄有 8 個 notebook，`poc_notebook/` 裡有 3 個 agent 實驗。命名方式暗示這是從 Paceriz 最早期開始的算法設計過程：
- `1_onboarding.ipynb` → `1.5_habit_plan.ipynb` → `2_runing_plan.ipynb` → `3. general_plan.ipynb` → `5_vita_report.ipynb`
- `VDOT.ipynb`、`estimate_target.ipynb`、`TSB model.ipynb`
- `poc_notebook/agent_vita_modify_training_plan.ipynb`

**推斷：** 這些記錄了「為什麼 Paceriz 這樣設計」的思考過程。但沒有任何索引說明每個 notebook 在做什麼、哪些結論被採用、哪些被放棄。

**影響：** 如果未來有新開發者加入，或需要回溯設計決策，這些知識可能流失。

**建議動作：** 為每個 notebook 建立一行描述的索引表。不需要詳細文件，一張表就夠。

---

## 🟢 觀察中

### 5. Rizo AI 是核心差異化但文件最少

**事實：** Rizo AI 是 Paceriz 區別於其他跑步 App 的核心功能，但相關的非程式碼文件只有 notebook POC。沒有正式的能力說明、限制邊界、或面向非技術人員的介紹。

**推斷：** 行銷夥伴如果要寫「Rizo 能做什麼」的素材，目前無從著手。

### 6. 時間線斷裂：2024-12 到 2026-03

**事實：** `marketing/paceriz.md` 最後更新標記 2024-12-25，`FIRESTORE_STRUCTURE.md` 標記 2025-11-19，但 `CRITICAL_ERRORS_FIX_2026-02-07.md` 是 2026-02。中間有超過一年的演進，但 paceriz.md 的系統架構圖可能已經過時。

**推斷：** 最完整的技術架構文件可能不再反映當前架構。

---

*盲點從文件交叉比對自動推斷，不代表一定存在。所有建議需 Barry 確認。*
