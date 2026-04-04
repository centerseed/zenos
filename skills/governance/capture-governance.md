# 知識捕獲分層路由規則 v1.0（含完整範例）

> **Phase 1 統一回傳格式：** 所有 MCP 回傳改為 `{status, data, warnings, ...}`。資料在 `response["data"]` 下，rejection 用 `response["status"] == "rejected"` 判斷。結構驗證已移至 Server 端，agent 專注語意判斷。

## 分層路由四步
1. 是否是治理規則或跨角色共識？→ 是：L2 候選（走三問+impacts gate）
2. 是否是正式文件（SPEC/ADR/TD）？→ 是：L3 document entity
3. 是否可指派且可驗收？→ 是：開 Task
4. 以上皆否：掛 entity.sources（不建 entity）

## 完整冷啟動範例（從原始文件到 ontology）

### 原始文件（假設接手一個新專案）
```
- README.md：介紹 ZenOS 是 AI Context 層
- docs/ADR-001.md：決定採用 PostgreSQL
- docs/SPEC-pricing.md：定價模型規格
- docs/SPEC-auth.md：用戶認證規格
- src/models/user.py：用戶資料模型
```

### Step 1：全局閱讀
先讀所有文件，建立整體印象，不急著建 entity。

### Step 2：列出候選概念
從文件中識別反覆出現的詞彙：
- ZenOS（產品概念）
- 定價模型（跨文件出現，有完整規格）
- 用戶認證（有完整規格）
- PostgreSQL（技術選型）
- 用戶資料模型（技術實作）

### Step 3：三問過濾

「定價模型」：
- 公司共識？✓（行銷、工程、法務都理解）
- 改了有 impacts？✓（影響合約、程式碼、文件）
- 跨時間存活？✓（比任何 sprint 都長壽）
→ 通過，L2 候選

「PostgreSQL」：
- 公司共識？△（工程師理解，行銷不需要理解）
- 改了有 impacts？✓（影響部署/遷移腳本）
- 跨時間存活？✓
→ 不通過（q1），降為 ADR 文件

「用戶資料模型」：
- 公司共識？✗（只有工程師理解）
→ 不通過，降為 L3 document 或 sources

### Step 4：推斷 impacts

「定價模型」的 impacts：
- 定價模型 改了費率結構 → 合約模板 的計費條款需更新
- 定價模型 新增方案 → 產品功能門檻 的解鎖邏輯需更新

### Step 5：批量 write

```python
# 建 L2：定價模型
write(
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

# 建 L3 document：PostgreSQL ADR
write(
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
```

## layer_decision 填寫範例：好 vs 不好

### 不好的填寫
```python
layer_decision={
  "q1_persistent": True,
  "q2_cross_role": True,
  "q3_company_consensus": True,
  "impacts_draft": ["影響其他東西"]  # 太模糊
}
```

### 好的填寫
```python
layer_decision={
  "q1_persistent": True,
  "q2_cross_role": True,
  "q3_company_consensus": True,
  "impacts_draft": [
    "定價模型 調整計費週期（月→年） → 合約模板 的自動續約條款需法務重新審核",
    "定價模型 新增企業方案 → 功能存取控制 的企業功能白名單邏輯需更新"
  ]
}
```

## 常見錯誤與修正

錯誤 1：「每個文件都應該有對應的 L2」
→ 不對。文件是 L3，掛在 L2 下面。一個 L2 可以有多份文件。

錯誤 2：「說不出 impacts 沒關係，先建起來再說」
→ 不對。說不出 impacts 是 L3 降級的強烈訊號。強行建立沒有 impacts 的 L2 只會讓 ontology 膨脹卻沒有治理價值。

錯誤 3：「全局讀完再 capture 太慢，邊讀邊 write 比較快」
→ 冷啟動時不要邊讀邊 write。全局視野建立後才能正確判斷 L2 邊界。增量模式才邊讀邊 write。
