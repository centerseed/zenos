# ADR-005：Dashboard 全景圖 Graph Library 選型

**狀態**：Accepted
**日期**：2026-03-22

## 背景

Dashboard 首頁要從 project card grid 改成公司知識關係圖（graph visualization），讓老闆打開就看到公司被「AI 看透了」的感覺。需要選一個能產生動態、有生命力的 graph 的前端 library。

## 決定

**使用 `react-force-graph-2d`**（底層是 force-graph + d3-force）。

## 考慮過的選項

| 選項 | 動態感 | React 整合 | 效能 | 開發速度 | 美學匹配度 |
|------|--------|-----------|------|----------|-----------|
| react-force-graph-2d | High | 原生 wrapper | Canvas, 極佳 | 快 | Obsidian / Neo4j 風格 ✅ |
| React Flow (@xyflow/react) | Mid | 原生 React | DOM, 佳 | 快 | 流程圖風格，偏工程工具 |
| D3 手寫 force-directed | High | 需手動整合 | SVG/Canvas | 慢 | 完全自由但工作量大 |
| Cytoscape.js | Mid | 需包裝 | Canvas | 中 | 偏學術，dated |
| Sigma.js | High | 需包裝 | WebGL, 極佳 | 中 | 大規模圖專用，殺雞用牛刀 |

## 取捨分析

- React Flow 的優勢是 React 生態系最成熟，但它的設計語言偏向 flow chart / node editor，不是我們要的「知識網絡飄浮感」
- D3 手寫給最大自由度，但開發成本高，且 React + D3 的 DOM ownership 衝突需要小心處理
- react-force-graph-2d 用 Canvas 渲染（效能好），底層是 d3-force（物理模擬），開箱即有節點浮動、zoom/pan、hover/click callback
- SMB 場景 entities < 50，不需要 Sigma.js 的 WebGL 大規模圖能力

## 後果

- 變得更容易的事：Demo 時圖有生命力，節點自然浮動、hover 發光、click 展開
- 變得更困難的事：Canvas 上的自定義 tooltip/overlay 需要 HTML overlay layer
- 未來需要重新評估的事：如果需要在圖上做拖曳連線、新增 entity 等編輯操作，可能需要切回 React Flow

## 行動項目

- [x] Architect 確認選型
- [ ] Developer 安裝 `react-force-graph-2d` + 實作 KnowledgeGraph component
