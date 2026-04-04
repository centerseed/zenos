---
name: zenos-governance
version: 2.0.0
---

# 治理總控閉環工作流程

## 前提條件

- MCP 已連線（`mcp__zenos__search` 可正常呼叫）
- 專案已有初始 ontology（若無，先執行 `/zenos-setup` 和 `/zenos-capture`）

## 步驟

### Step 1：全面分析（analyze）

```python
mcp__zenos__analyze(check_type="all")
```

`check_type` 可選值：
- `"all"` — 執行全部檢查（建議預設使用）
- `"orphans"` — 找出沒有 L2 歸屬的孤立文件
- `"stale"` — 找出長期未更新的 entity
- `"missing_impacts"` — 找出缺少 impacts 的 L2 entity
- `"invalid_documents"` — 找出 title 為裸域名或空值的文件條目

回傳結構包含：問題類型、問題列表、建議修復動作。

### Step 2：檢視分析結果

閱讀分析結果，按問題類型分組：

| 問題類型 | 說明 | 修復動作 |
|----------|------|---------|
| 孤立文件 | document entity 缺少 ontology_entity | 找對應 L2 或建立新 L2 |
| 缺 impacts | L2 entity 沒有 impacts_draft | 推斷並補寫 impacts |
| 過時概念 | entity 長期未更新且無對應文件 | 確認是否仍有效，否則 archive |
| 重複概念 | 兩個 entity 指向同一概念 | 合併，保留主要 entity |
| 無效文件條目 | document entity title 為裸域名或空值 | 執行 analyze invalid_documents + 批次修復或 archive |

### Step 3：自動修復

根據問題類型，呼叫對應修復動作：

**修復孤立文件：**
```python
# 先查詢或建立對應 L2
mcp__zenos__search(collection="entities", query="相關概念名稱")

# 更新文件的 ontology_entity
mcp__zenos__write(
  collection="documents",
  data={
    "doc_id": "orphan-doc-id",
    "ontology_entity": "對應的 L2 概念名稱"
  }
)
```

**補寫缺失的 impacts：**
```python
mcp__zenos__write(
  collection="entities",
  data={
    "id": "entity-uuid-here",
    "layer_decision": {
      "impacts_draft": [
        "概念A 改了 X → 概念B 的 Y 需更新",
        "概念A 新增 Z → 概念C 的邏輯需調整"
      ]
    }
  }
)
```

**Archive 過時概念：**
```python
mcp__zenos__write(
  collection="entities",
  data={
    "id": "entity-uuid-here",
    "status": "archived"
  }
)
```

**修復無效文件條目：**
```python
# Step 1: 偵測無效文件
result = mcp__zenos__analyze(check_type="invalid_documents")

# Step 2: 對 action="propose_title" 的條目，逐一確認
for item in result["invalid_documents"]["items"]:
    if item["action"] == "propose_title" and item["proposed_title"]:
        # 向用戶確認 proposed title
        mcp__zenos__confirm(
            collection="documents",
            id=item["entity_id"],
            action="approve"  # 或 reject
        )
        # 確認後更新 title
        mcp__zenos__write(
            collection="documents",
            id=item["entity_id"],
            data={"title": item["proposed_title"]}
        )

# Step 3: 對 action="auto_archive" 的條目，直接 archive
for item in result["invalid_documents"]["items"]:
    if item["action"] == "auto_archive":
        mcp__zenos__write(
            collection="documents",
            id=item["entity_id"],
            data={"status": "archived"}
        )
```

### Step 4：confirm 提交

```python
mcp__zenos__confirm(batch_id="...", action="approve")
```

若對某個修復不確定，可用 `action="reject"` 略過該項。

### Step 5：再次分析確認改善

```python
mcp__zenos__analyze(check_type="all")
```

比對 Step 1 和 Step 5 的分析結果，確認問題數量減少。若仍有殘留問題，回到 Step 3 繼續修復。

## MCP Tools 使用

- `mcp__zenos__analyze(check_type=...)` — 掃描 ontology 健康度，產生問題報告
- `mcp__zenos__search(collection=..., query=...)` — 查詢現有 entity
- `mcp__zenos__get(collection=..., id=...)` — 取得單一 entity 詳情
- `mcp__zenos__write(collection=..., data=...)` — 提交修復更新
- `mcp__zenos__confirm(batch_id=..., action=...)` — 確認或拒絕批量修復
- `mcp__zenos__task(action="create", ...)` — 建立需要人工處理的修復任務

## 注意事項

- 治理閉環的核心是「分析 → 修復 → 再分析」，不要只執行一次 analyze 就結束
- 不確定的修復（例如合併重複概念）建議建立 Task 交由人工決策，而非強行自動修復
- impacts 的描述要具體，格式為：「A 改了 X → B 的 Y 需更新」，避免模糊描述
- 大量修復時分批 confirm，避免單次操作過多導致難以 rollback
