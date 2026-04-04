# L2 知識節點治理規則 v1.1（含完整範例）

## 什麼是 L2 Entity
L2 Entity = 公司共識概念。改了它，不同角色（工程師、行銷、老闆）都會受影響。
不是技術模組的文件索引，而是值得被治理傳播追蹤的概念。

## 三問判斷（全通過才能建 L2）
1. 公司共識？任何角色都聽得懂，在不同情境都指向同一件事
2. 改了有 impacts？這個概念改變時，有其他概念必須跟著看
3. 跨時間存活？不會隨某個 sprint 或文件結束而消失

## 關聯語意動詞（verb）
建立 relationship 時必須填 `verb`（2-5 字中文動詞）：
- `type` 是結構分類，`verb` 是語意——沒有 verb 的關聯是有骨架沒血肉
- write 回傳 `suggested_verbs` 時，選最準確的或自行填寫
- 常用動詞：校準、觸發、驅動、限制、依賴、啟用、支撐、規範
- 無法找到合適動詞 → 這條關聯的語意可能不清，考慮重新審視

範例：
```
type: impacts, verb: 校準   → 跑步科學指標 [校準] Race Prediction
type: impacts, verb: 觸發   → 跑步科學指標 [觸發] 行銷定位策略
```

> **Phase 1 統一回傳格式：** 所有 MCP 回傳改為 `{status, data, warnings, suggestions, similar_items, context_bundle, governance_hints}`。資料在 `response["data"]` 下，錯誤用 `response["status"] == "rejected"` 判斷。

> **Server 端驗證：** `confirm` 時 Server 強制驗證 impacts≥1。`write` 回傳 `similar_items` 列出相似 entity。`confirm(tasks)` 回傳 `governance_hints.suggested_entity_updates` 列出需要更新的下游 entity。

## 影響鏈（impact_chain）
`get(collection="entities", id=...)` 回傳包含 `impact_chain`（BFS 多跳，最多 5 跳）：
```
[{from_name, verb, to_name}, ...]
```
- 回答「X 改了影響什麼」→ 直接讀 impact_chain，不需逐跳 get
- 建任務時可用 impact_chain 識別所有需同步的下游概念
