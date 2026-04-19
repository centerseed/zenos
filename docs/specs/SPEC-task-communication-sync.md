---
type: SPEC
id: SPEC-task-communication-sync
status: Draft
ontology_entity: action-layer
created: 2026-03-30
updated: 2026-04-19
---

# Feature Spec: Task 通訊同步與知識對齊 (Lowering Communication Cost)

## 背景與動機

在中小企業（SME）的自動化場景中，行銷（如 Amy）與業務最主要的痛點在於「資訊不對稱」與「重複溝通」。
- **問題**：業務傳來的需求不完整、不合規範；行銷需要反覆查閱過去的 Excel 或規則。
- **解決方案**：利用 ZenOS 的 Ontology 連結能力，讓 Task UI 不只是進度表，而是「知識對齊工具」。

## 目標使用者

- **行銷主管 (Amy)**：需要快速審核業務需求，確保符合品牌與通路規範。
- **業務人員 (Barry)**：希望隨手一丟需求就能被正確執行，不用填複雜表單。

## 需求說明

### P0-1 知識脈絡卡 (Context Card)
- **描述**：UI 必須在 Task 詳情頁面直接渲染 `linked_entities` 的內容摘要（what/why/how）。
- **AC**：
  - Given 任務已連結品牌 L2 實體
  - When Amy 打開任務視圖
  - Then 右側或疊層應顯示「品牌禁忌語」與「標準規格」卡片。

### P0-2 原始輸入追溯 (Input Provenance)
- **描述**：AI 提取任務後，必須保留來源資料的映射（如：Excel 座標、圖片截圖）。
- **AC**：
  - When 點擊任務的「來源追溯」按鈕
  - Then UI 應彈出顯示原始的業務對話截圖或 Excel 關鍵分頁片段。

### P1-1 多端同步標識 (Cross-platform Sync Indicator)
- **描述**：顯示此任務目前與哪些外部數據源（External SSOT）保持同步。
- **AC**：
  - UI 應展示同步清單，例如：`[Sync: Google Sheets - Banila Co #L15]`、`[Sync: Digiwin ERP - PO #9527]`。

## 技術約束

- 需要搭配 Agent 端的 OCR 與 NLP 提取能力。
- 外部系統（Excel）的同步狀態需透過 Adapter 定時回報至 Task 元數據中的 `source_metadata`。

## 邊界定義
- 本文件僅定義 UI 呈現邏輯，不涉及 Adapter 的具體實現流程。

## Changelog

- 2026-04-19: reviewed against SPEC-task-governance dispatcher / handoff / subtask semantics; no conflict found, task communication sync remains UI-facing provenance/context scope.
