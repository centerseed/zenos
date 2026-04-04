---
name: zenos-capture
version: 3.0.0
---

# 知識捕獲工作流程

## 前提條件

- MCP 已連線（`mcp__zenos__search` 可正常呼叫）
- 待捕獲的內容已在當前對話或指定文件中

## 步驟

### Step 1：全局閱讀

先讀取所有相關文件或對話內容，建立整體印象。**冷啟動時不要邊讀邊 write**，全局視野建立後才能正確判斷 L2 邊界。

### Step 2：列出候選概念

識別文件或對話中反覆出現的詞彙和概念，作為候選清單。

### Step 3：分層路由判斷

對每個候選概念，依序回答以下四個問題：

**問題 1：是否是治理規則或跨角色共識？**
- 是 → L2 候選，走「三問 + impacts gate」（見下方 L2 判斷規則）
- 否 → 繼續問題 2

**問題 2：是否是正式文件（SPEC / ADR / TD）？**
- 是 → L3 document entity，呼叫 `write(collection="documents", ...)`
- 否 → 繼續問題 3

**問題 3：是否可指派且可驗收？**
- 是 → 開 Task，呼叫 `mcp__zenos__task(action="create", ...)`
- 否 → 繼續問題 4

**問題 4：以上皆否**
- → 掛 entity.sources，不建立新 entity

### Step 4：L2 三問判斷（通過才能建 L2）

對 L2 候選概念，需全部回答「是」才能建立 L2 entity：

1. **公司共識？** 任何角色（工程師、行銷、老闆）都聽得懂，在不同情境都指向同一件事
2. **改了有 impacts？** 概念改變時，有其他概念必須跟著看
3. **跨時間存活？** 不會隨某個 sprint 或文件結束而消失

若三問全通過，推斷具體 impacts（格式：「A 改了 X → B 的 Y 需更新」），再建立 L2。

### Step 5：批量 write

```python
# 建立 L2 entity
mcp__zenos__write(
  collection="entities",
  data={
    "name": "定價模型",
    "type": "module",
    "summary": "ZenOS 的訂閱費率結構和計費邏輯",
    "status": "draft",
    "layer_decision": {
      "q1_persistent": True,
      "q2_cross_role": True,
      "q3_company_consensus": True,
      "impacts_draft": [
        "定價模型 改了費率結構 → 合約模板 的計費條款需更新",
        "定價模型 新增方案 → 產品功能門檻 的解鎖邏輯需更新"
      ]
    }
  }
)

# 建立 L3 document entity
mcp__zenos__write(
  collection="documents",
  data={
    "doc_id": "ADR-001-postgresql",
    "title": "架構決策：選用 PostgreSQL",
    "type": "ADR",
    "ontology_entity": "資料儲存架構",
    "status": "approved",
    "source": {"uri": "docs/ADR-001.md"}
  }
)

# 建立 Task
mcp__zenos__task(
  action="create",
  title="更新合約模板計費條款",
  description="定價模型調整後，合約模板需同步更新",
  status="open"
)
```

### Step 6：confirm 提交

```python
mcp__zenos__confirm(batch_id="...", action="approve")
```

### Step 7：記錄工作日誌

```python
mcp__zenos__journal_write(
  summary="zenos-capture：{捕獲了什麼概念/文件，幾個 L2/L3，涉及哪個專案}",
  flow_type="capture",
  project="{專案名稱（如知道）}"
)
```

## MCP Tools 使用

- `mcp__zenos__search(collection=..., query=...)` — 查詢現有 entity，避免重複建立
- `mcp__zenos__write(collection="entities", data=...)` — 建立或更新 L2 entity
- `mcp__zenos__write(collection="documents", data=...)` — 建立 L3 document entity
- `mcp__zenos__task(action="create", ...)` — 建立可指派的 Task
- `mcp__zenos__confirm(batch_id=..., action=...)` — 確認或拒絕批量操作

## 注意事項

- 說不出 impacts 是 L3 降級的強烈訊號，不要強行建立沒有 impacts 的 L2
- 每份 L3 document 都需要 `ontology_entity` 欄位，指向所屬的 L2 概念；找不到 L2 時先建 L2 再掛文件
- 建立前先用 `mcp__zenos__search` 確認概念是否已存在，避免重複
- 增量模式（單一文件或對話）才邊讀邊 write；冷啟動整個專案時，先全局閱讀再批量 write
