---
doc_id: PB-small-model-dogfood
title: 小模型 Dogfooding 操作指南
type: GUIDE
ontology_entity: MCP 介面設計
status: draft
version: "0.1"
date: 2026-05-02
supersedes: null
---

# 小模型 Dogfooding 操作指南

你要做 ZenOS dogfooding。

## 必填輸入

開始前先取得：

- 測試 L1 名稱：
- 測試 L1 ID：

## 先讀 skill

開始前先讀：

- `skills/README.md`
- `skills/governance/bootstrap-protocol.md`

做不同操作前再讀：

- 要查 context：讀 `skills/governance/bootstrap-protocol.md`
- 要建 task / 更新 task / confirm task：讀 `skills/governance/task-governance.md`
- 要寫 entity / 操作 L2：讀 `skills/governance/l2-knowledge-governance.md`
- 要寫 document / 修 document：讀 `skills/governance/document-governance.md`
- 要 capture：讀 `skills/workflows/knowledge-capture.md`
- 要 sync：讀 `skills/workflows/knowledge-sync.md`
- 要治理掃描：讀 `skills/workflows/governance-loop.md`

## 範圍限制

- 只能針對這個測試 L1 做治理。
- 所有 `search`、`analyze`、`write`、`task` 都必須帶 `product_id="<測試 L1 ID>"`，或只使用這個 L1 底下找到的 entity ID。
- 不要修改其他 L1。
- 不要把正式 ZenOS / Paceriz / 客戶資料當測試對象。
- 不確定某個 entity 是否在測試 L1 底下時，先不要改。

## 你要做的事

1. 找到測試 L1。

2. 列出測試 L1 底下的 L2。

3. 選一個 L2 做治理測試。

4. 對該 L2 跑一次 scoped analyze。

5. 如果 analyze 有問題，挑一個最小問題修。

6. 如果需要新增資料，只能新增到測試 L1 底下。

7. 如果需要建 task，只能建在測試 L1 底下。

8. 如果 tool 失敗，最多重試 3 次。

9. 每次失敗都記錄。

10. 完成後輸出 dogfood report。

## 可以做的測試

- 搜尋測試 L1 的 entity。
- 搜尋測試 L1 底下的 documents。
- 跑 `analyze(check_type="health")`。
- 跑 `analyze(check_type="quality")`。
- 跑 `analyze(check_type="invalid_documents")`。
- 建一個測試 L2。
- 建一個測試 document。
- 建一個測試 task。
- 把測試 task 更新到 `in_progress`。
- 把測試 task 更新到 `review`。
- 驗收測試 task。

## 不可以做的事

- 不要改非測試 L1。
- 不要全 workspace analyze 後直接修。
- 不要建立沒有 `product_id` 的 task。
- 不要建立沒有掛到測試 L1 或其 L2 的 entity。
- 不要 confirm 正式 entity。
- 不要 archive / supersede / delete 任何正式資料。
- 不要 deploy。
- 不要改 code。

## 問題記錄格式

每個問題都用這個格式記：

```md
## Dogfood Issue

測試 L1：
操作：
tool：
input：
result：
重試次數：
最後是否成功：
問題：
```

## 最終回報格式

```md
# Dogfood Report

測試 L1：
測試時間：

## 做了什麼
- 

## 成功的操作
- 

## 失敗或卡住的操作
- 

## 記錄的問題
- 

## 建議優先修
- 
```
