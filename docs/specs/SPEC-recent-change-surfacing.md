---
type: SPEC
id: SPEC-recent-change-surfacing
status: Draft
ontology_entity: MCP 介面設計
created: 2026-04-20
updated: 2026-04-20
---

# Feature Spec: Recent Change Surfacing

## 背景與動機

目前 ZenOS 的 `capture` / `sync` 會把知識寫進 `document`、`entity`、`entry`，但「最近更新了什麼」仍然不容易直接回答。

根因不是知識沒進 ontology，而是：
- 文件變更沒有被穩定寫成可消費的 `change_summary`
- 影響既有 L2 的變更沒有被穩定提升成 `entry(type="change")`
- MCP query 沒有把「recent changes」當成正式查詢意圖，只能靠一般 search 猜

本 SPEC 的目標是修正這條鏈：

`capture/sync -> document/entity/entry -> recent changes query`

讓 agent 可以直接回答：
- `Paceriz 最近更新了什麼？`
- `Paceriz 最近行銷有什麼更新？`
- `最近 14 天 App 公告與版本控制有什麼變更？`

## 目標

- 讓每次實質文件變更都留下可查的結構化變更痕跡
- 讓影響 L2 的變更能直接從 entity 層讀到，而不是只埋在 L3 文件
- 讓 MCP 有正式的 recent changes 查詢能力，不再只依賴一般 semantic search

## 非目標

- 不在本輪新增新的 ontology layer
- 不要求 server 自動用 LLM 生成 `change_summary`
- 不重寫既有 semantic retrieval 排序邏輯
- 不處理完整 dashboard feed 視覺設計；本 SPEC 先定義資料與查詢契約

## 需求

### P0

#### R1: `capture/sync` 遇到實質文件變更必寫 `change_summary`

- **描述**：當 `capture` 或 `sync` 判定某份文件發生實質變更時，必須在對應 document entity 寫入 `change_summary`。
- **實質變更定義**：
  - 新增或刪除正式章節
  - acceptance criteria / rule / flow / scope / status 有改動
  - 新增對其他角色有下游影響的資訊
  - 單純 typo、格式、美化、斷行調整不算
- **寫入格式**：`change_summary` 必須是 1-3 句白話摘要，至少包含：
  - 這次改了什麼
  - 為什麼重要
- **Acceptance Criteria**：
  - `AC-RCS-01`：Given `sync` 掃到既有正式文件有實質變更，When 完成 document 寫入，Then 對應 document entity 的 `change_summary` 必須非空，且 `summary_updated_at` 必須更新為本次寫入時間。
  - `AC-RCS-02`：Given 只有 typo / formatting change，When `sync` 完成，Then 不得為此強制覆寫既有 `change_summary`。
  - `AC-RCS-03`：Given agent 執行 `write(collection="documents")` 的 bundle operation（如 `add_source` / `update_source` / `remove_source`），When payload 未帶 `change_summary` 且本次屬實質變更，Then workflow 必須視為未完成，不能宣稱同步完成。

#### R2: 影響既有 L2 的文件變更必寫 `entry(type="change")`

- **描述**：若文件變更不只是文件本身更新，而是改變某個既有 L2 / module 的可消費知識，必須額外在對應 entity 下建立一條 `entry(type="change")`。
- **適用情境**：
  - 行銷定位、產品定位、定價、收費規則、外部溝通方式改變
  - 功能入口、用戶旅程、公告策略、版本控制策略改變
  - 任何「別的角色下次做事時應該知道」的更新
- **不適用情境**：
  - 文件結構整理但沒有改變知識
  - 純內部編輯註記，對其他角色沒有影響
- **entry 格式**：
  - `type = "change"`
  - `content` 必須包含：時間、變更點、受影響面
- **Acceptance Criteria**：
  - `AC-RCS-04`：Given 文件更新影響既有 L2，When `capture` / `sync` 完成，Then 至少 1 個相關 entity 必須新增 `entry(type="change")`。
  - `AC-RCS-05`：Given 文件更新只停留在 L3 敘述，When 對應 L2 的做法、對外說法、下游協作不受影響，Then 不得為了湊數硬建 `entry(type="change")`。
  - `AC-RCS-06`：Given 同一次同步同時更新 document 與 entity change entry，Then `entry.content` 不得只是複製 `change_summary`，而必須明示「哪個概念被改變、誰需要跟著看」。

#### R3: MCP 正式支援 recent changes 查詢

- **描述**：MCP 必須提供正式的「近期更新」查詢入口；查詢語意是 `time + product + topic + relevance`，不是一般 keyword search 的副產品。
- **最低需求**：
  - 支援以 `product` / `product_id` 限定範圍
  - 支援 `since` 或天數視窗
  - 支援 `topic` / query 關鍵詞做主題縮小
  - 優先回傳有 `change_summary` 的 documents 與 `entry(type="change")`
- **Acceptance Criteria**：
  - `AC-RCS-07`：Given `product=Paceriz` 且 `since=14d`，When 查 recent changes，Then response 必須優先包含最近 14 天內有 `change_summary` 的 documents 與 `entry(type="change")`。
  - `AC-RCS-08`：Given `product=Paceriz`、`topic=marketing`、`since=14d`，When 查 recent changes，Then response 必須先過濾 `topic` 關聯，再按時間新到舊排序，而不是只按 semantic score。
  - `AC-RCS-09`：Given 有對應的 recent changes 結果，When agent 回答「最近更新了什麼」，Then 不需要先讀 journal 才能找到主要變更。

#### R4: recent changes response 必須是整理後結果，不是 raw list

- **描述**：recent changes query 的輸出必須是可直接回答使用者的整理結果，而不是 documents / entries dump。
- **每筆結果至少要有**：
  - `kind`: `document_change` 或 `entity_change`
  - `title`
  - `updated_at`
  - `topic_match`
  - `change_summary` 或 `entry.content`
  - `why_it_matters`
  - `related_entity_ids`
- **Acceptance Criteria**：
  - `AC-RCS-10`：Given recent changes query 命中多筆結果，When response 回傳，Then 每筆結果都必須帶 `why_it_matters`，讓 agent 不必二次猜測重要性。
  - `AC-RCS-11`：Given 某筆結果同時有 document change 與 entity change entry，When response 組裝，Then 可以同組呈現，但不得重複列成兩條看起來無關的更新。

### P1

#### R5: `journal` 降為輔助來源，不再是主要變更入口

- **描述**：`journal` 保留為 session provenance，但 recent changes query 不得把 journal 當主資料來源。
- **規則**：
  - primary source: `document.change_summary`
  - secondary source: `entry(type="change")`
  - fallback source: `journal`
- **Acceptance Criteria**：
  - `AC-RCS-12`：Given 有 `change_summary` 或 `entry(type="change")`，When recent changes 組裝結果，Then 不得優先採用 journal summary 蓋過知識層內容。
  - `AC-RCS-13`：Given 某次變更只有 journal、沒有 document/entity change 痕跡，When recent changes 查詢，Then 該結果最多作為 fallback，並標記為治理缺口。

## 查詢介面建議

本輪可接受兩種落地方式，擇一即可：

1. 新增專用 MCP tool，例如 `recent_updates(product, since, topic, limit)`
2. 在既有 `search` 新增明確 mode，例如 `mode="recent_changes"`

限制：
- 不得只是把既有 `search(collection="documents")` 包一層 prompt 假裝完成
- 查詢結果必須以 `change_summary` / `entry(type="change")` 為一級訊號

## 技術約束

- Server 不負責生成語意內容；`change_summary` 與 `entry(type="change")` 內容仍由 agent / workflow 產生
- Workflow 完成條件必須收斂到「是否留下 recent-change 可查痕跡」，不是只有 document source 更新成功
- recent changes query 要能在 `llm_health degraded` 時仍回傳 deterministic baseline 結果；不能完全依賴 embedding 成功

## Done Criteria

- `capture` / `sync` 規則明確要求實質變更必寫 `change_summary`
- 影響 L2 的變更有明確 `entry(type="change")` 觸發規則
- MCP 有正式 recent changes 查詢契約
- agent 可直接回答「某產品某主題最近更新了什麼」，不需要先翻 journal 或靠提示詞猜

## 後續實作切分

1. workflow 規則修正：`knowledge-capture.md`、`knowledge-sync.md`
2. MCP contract：新增 `recent_updates` 或 `search(mode="recent_changes")`
3. server query 組裝：documents + entries 的 recent-change 聚合
4. dashboard 再視需要補產品頁的最近更新區塊
