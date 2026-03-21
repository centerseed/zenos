# Rizo AI 教練 — 模組 Ontology

> 骨架層實體 | confirmedByUser：❌

## 這個模組在做什麼

Rizo 是 Paceriz 的 AI 跑步教練。用戶可以跟 Rizo 對話，問關於自己的訓練表現、要怎麼調整、下一步該怎麼練。Rizo 基於統一數據模型分析用戶的運動數據，提供個性化建議。

**這是 Paceriz 的差異化核心** — 市場上有很多運動追蹤 App，但有 AI 教練能根據你的數據給具體建議的很少。

## 依賴

```
統一數據模型 → Rizo 的分析基礎（所有運動數據經過標準化）
訓練計畫系統 → Rizo 知道用戶目前在哪週、目標是什麼
ACWR → Rizo 知道用戶的安全負荷範圍
VDOT → Rizo 知道用戶目前的跑力水平
```

## 相關文件

| 文件 | 用途 | 讀者 |
|------|------|------|
| `1_onboarding.ipynb` | Onboarding 流程 POC（Rizo 首次互動設計）| 了解設計思路 |
| `5_vita_report.ipynb` | Vita 報告 POC（運動表現報告）| 了解報告邏輯 |
| `poc_notebook/agent_vita_modify_training_plan.ipynb` | Agent 修改訓練計畫的 POC | 了解 AI 教練互動設計 |
| `poc_notebook/agent_lanchain_graph.ipynb` | LangChain agent graph POC | 了解 AI 架構實驗 |

## 知識缺口（AI 推斷）

Rizo AI 是 Paceriz 的核心差異化，但相關文件最少。多數知識在 notebook POC 裡，沒有被整理成正式文件。如果要讓行銷夥伴說明「Rizo 能做什麼」，目前沒有一份非技術人員可讀的文件。

## 待決策

- Rizo 的能力邊界是什麼？（能回答什麼、不能回答什麼）
- 需不需要一份面向用戶 / 行銷的 Rizo 能力說明？
