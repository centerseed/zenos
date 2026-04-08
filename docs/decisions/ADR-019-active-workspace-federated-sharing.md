---
type: ADR
doc_id: ADR-019-active-workspace-federated-sharing
title: 架構決策：Active Workspace 與 Federated Sharing 模型
ontology_entity: 身份與權限管理
status: superseded
version: "1.0"
date: 2026-04-08
supersedes: ADR-018-identity-access-runtime-alignment
---

# ADR-019: Active Workspace 與 Federated Sharing 模型

> Superseded by `ADR-018 v2` on 2026-04-08.
> 保留此文件作為中間修正決策的追溯紀錄；正式執行模型以 `ADR-018-identity-access-runtime-alignment.md` 為準。

## Context

`ADR-018` 嘗試把 ZenOS 從 company-centric permission 語言收斂到 workspace sharing 模型，但仍留下兩個錯位：

1. 把 `guest` 過度實作成全域低權限帳號，而不是「某個 shared workspace 內的受限角色」
2. 把 `Projects / Tasks only` 的 portal surface 混入主要產品模型，導致同一個 user 在自己的 workspace 中也被誤收斂

在產品確認後，ZenOS 的正確模型是：

- 每個 user 註冊後自動擁有自己的 `home workspace`
- 每個 user 都可以加入其他 workspace
- user 進入不同 workspace 時，會得到不同的 `active workspace context`
- 受限的是「在某個 shared workspace 內能做什麼」，不是這個 user 全域只能用什麼功能
- 目前共享的是知識地圖對應的 L1-L3 與其 task / doc，不是整個 application layer

## Decision

### 1. `active workspace context` 成為正式執行單位

從 ADR-019 起，所有 UI、route guard、API 與 agent 權限判斷，一律以 `active workspace context` 為正式執行單位，而不是以 user 全域角色判斷。

規則：

- 每次登入後一律先進 `home workspace`
- 切換 workspace 時，整個前端 surface 與後端權限都必須重新計算
- 同一個 user 在不同 workspace 內，可以有不同角色與不同可見範圍

### 2. 共享模型採 `federated sharing`，不再保留 portal 主模型

ZenOS 主產品不再以 `client portal` 作為主要身份模型。

正式模型為：

- user 是完整使用者
- workspace 是協作容器
- 分享是以 `product(L1)` 為入口，把 ontology 子樹共享給他人
- shared workspace 的 `guest` 仍可使用 `Knowledge Map`
- shared workspace 的 `guest` / `member` 主導航目前固定為 `Knowledge Map / Products / Tasks`

### 3. `product` 成為共享與導航主軸

- `product` 是 L1 主軸，也是分享授權入口
- `project` 不再視為主導航概念，而是一種 L3 entity
- Web 現有 `Projects` 主導航與文案，應收斂為 `Products`

### 4. 共享邊界只涵蓋 ontology 與其依附資源

當前可共享範圍：

- L1 / L2 / L3 ontology
- task
- doc

當前不共享範圍：

- CRM
- team / setup / company-oriented app modules
- 其他 application layer

這些模組仍只屬於使用者自己的 workspace；未來若企業版要開放，必須透過新 spec / ADR 擴充。

### 5. Guest 不再等於「只能看 Projects / Tasks」

`guest` 的正規語意改為：

- 可進入 shared workspace 的 `Knowledge Map`
- 可看被授權 L1 子樹中的 `public` 節點
- 可建立 task
- 可建立 L3，但必須掛在授權範圍內至少一個 L2
- 不可建立 L1 / L2
- 不可看未授權節點、未授權 impacts、`restricted`、`confidential`

## Consequences

- 正面：
  - `home workspace` 與 `shared workspace` 的心智模型清楚一致
  - `guest` 不再被錯誤視為全域低權限帳號
  - UI、導航、route guard、ontology 授權模型可收斂到同一套語言
- 負面：
  - 既有 `ADR-018` 對 Guest surface 的實作方向需要回退
  - `Projects` 改名 `Products` 會影響前端文案、測試與既有假設
  - `project` 收斂為 L3 entity 後，執行面與知識面必須更清楚分層

## Implementation

1. 以 `active workspace context` 重做前端 nav 與 route guard
2. 將 guest 在 shared workspace 的主導航調整為 `Knowledge Map / Products / Tasks`
3. 將 Web `Projects` 文案與主語意收斂為 `Products`
4. 以 `product(L1)` 作為共享授權入口與 server 查詢裁切基準
5. 補齊多 workspace、guest shared subtree、member 全 workspace、home workspace full app surface 的驗收場景
