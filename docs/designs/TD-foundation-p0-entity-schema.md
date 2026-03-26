# 基礎層 P0 — Architect 任務規格

**日期**：2026-03-23
**前置**：spec.md Part 7.2（Entity 架構）、Part 7.6（權限模型）
**優先級**：P0 — Dashboard 知識地圖的前置條件

---

## 背景

Entity 架構經過重新設計（詳見 spec.md Part 7.2），核心變更：

1. **Document 是 entity(type="document")**，不再是獨立 collection
2. Entity 新增 `owner`、`sources`、`visibility` 三個欄位
3. Task 不是 entity，保持獨立 collection

這些變更影響 MCP Server 的驗證規則和 Skill 的行為。Dashboard 知識地圖需要這些欄位才能正常運作。

---

## 任務 1：Entity Schema 擴展

### 1a. 新增 entity type: `document`

MCP Server 的 entity type 驗證目前允許：`product` / `module` / `goal` / `role` / `project`

**改為**：`product` / `module` / `goal` / `role` / `project` / `document`

Document entity 的特殊規則：
- `parent_id` 非必填（document 可以不屬於特定 module）
- 建議有 `linked_entity_ids`（連到相關的 entity），但非強制
- tags 的 `what` 和 `who` 可以是 array（跟其他 entity 一樣是 string 也行，Phase 0 不強制）

### 1b. Entity 新增 `owner` 欄位

```python
# entities/{id}
owner: str | None = None    # Phase 0: 簡單的名字字串（如 "Barry"）
                              # Phase 1: 改為 reference to member
```

- MCP `write(collection="entities")` 接受 `owner` 參數
- MCP `search` / `get` 回傳中包含 `owner`
- 非必填，預設 null

### 1c. Entity 新增 `sources` 欄位

```python
# entities/{id}
sources: list[dict] | None = None
# 每個 source:
# {
#   "uri": str,       # "github://owner/repo/path" 或 URL
#   "label": str,     # 顯示名稱
#   "type": str       # "github" | "gdrive" | "notion" | "url"
# }
```

- MCP `write(collection="entities")` 接受 `sources` 參數
- 可以整個 array 覆寫，或用 `append_sources` 參數追加（避免覆蓋已有的 sources）
- MCP `get` 回傳中包含 `sources`
- 非必填，預設 null 或空 array

### 1d. Entity 新增 `visibility` 欄位

```python
# entities/{id}
visibility: str = "public"   # "public" | "restricted"
```

- MCP `write(collection="entities")` 接受 `visibility` 參數
- 預設 "public"
- Phase 0 暫不在 search/get 做 visibility 過濾（任務 2 處理）

---

## 任務 2：MCP Server 權限過濾（P1，任務 1 完成後再做）

### 2a. Search/Get 加 visibility 過濾

根據 MCP token 對應的 partner 的 `isAdmin` 欄位：
- `isAdmin = true` → 看到所有 entity（包含 restricted）
- `isAdmin = false` → search/get 自動過濾掉 `visibility = "restricted"` 的 entity

### 2b. Write 加權限檢查

- `isAdmin = true` → 可以寫任何 entity
- `isAdmin = false` → 只能寫 `authorizedEntityIds` 範圍內的 entity，且不能修改 `visibility` 欄位

---

## 任務 3：/zenos-capture Skill 更新（P1，任務 1 完成後再做）

### 3a. 掃目錄時建 document entity 而非 documents collection entry

目前 `/zenos-capture` 掃到 .md 文件時呼叫：
```
write(collection="documents", data={title, source, tags, summary, ...})
```

改為：
```
write(collection="entities", data={
  name: 文件標題,
  type: "document",
  summary: 語意摘要,
  tags: {what, why, how, who},
  parent_id: 所屬 module 的 entity ID（如能判斷）,
  sources: [{ uri: GitHub URL, label: 檔名, type: "github" }],
  confirmed_by_user: false
})
```

### 3b. 低價值文件改為填 sources

P0/P1 等級文件 → 建 document entity（出現在知識地圖上）
P2/P3 等級文件 → 追加到所屬 entity 的 `sources` 欄位（不出現在知識地圖上）

判斷依據：
- P0/P1（spec、架構、PRD）→ 有獨立的語意價值，值得成為節點
- P2/P3（guides、雜項）→ 只是參考資料，掛在 entity.sources 就好

### 3c. /zenos-sync 同步更新

`/zenos-sync` 偵測到文件變更時，同樣遵循上述邏輯：
- 高價值文件變更 → 更新對應的 document entity
- 低價值文件變更 → 更新對應 entity 的 sources

---

## 驗收條件

### 任務 1 驗收（P0）

1. `mcp__zenos__write(collection="entities", data={type: "document", name: "test", ...})` 成功建立
2. `mcp__zenos__write(collection="entities", data={..., owner: "Barry"})` 成功寫入 owner
3. `mcp__zenos__write(collection="entities", data={..., sources: [{uri: "...", label: "...", type: "github"}]})` 成功寫入 sources
4. `mcp__zenos__write(collection="entities", data={..., visibility: "restricted"})` 成功寫入
5. `mcp__zenos__get(id=...)` 回傳包含 owner、sources、visibility 欄位
6. `mcp__zenos__search(collection="entities")` 回傳包含新欄位
7. 既有的 entity（product、module）不受影響，新欄位為 null/預設值

### 任務 2 驗收（P1）

1. 用非 admin 的 partner key，search 看不到 `visibility: "restricted"` 的 entity
2. 用 admin key，search 能看到所有 entity

### 任務 3 驗收（P1）

1. `/zenos-capture {目錄}` 對 P0/P1 文件建 document entity
2. `/zenos-capture {目錄}` 對 P2/P3 文件填到 entity.sources
3. Dashboard 知識地圖能顯示 document entity 節點

---

## 不做的事

- ❌ Member model（跟 partner 分離）— Phase 1
- ❌ 繼承式權限（parent restricted → children restricted）— 不做
- ❌ documents collection 遷移 — 目前是空的，不需要遷移
- ❌ entity type enum 以外的新 type — 六種夠了

---

## 依賴關係

```
任務 1（Entity Schema）
  ↓
  ├── Dashboard 知識地圖實作（見 `docs/designs/TD-dashboard-v1-implementation.md`）
  ├── 任務 2（權限過濾）
  └── 任務 3（Skill 更新）
```

**任務 1 是所有後續工作的前置。** 完成後 Dashboard 和 Skill 可以平行開發。

---

## 參考文件

- `docs/spec.md` Part 7.2 — Entity 架構（分層、邊界、sources、用語）
- `docs/spec.md` Part 7.6 — 權限模型
- `docs/spec.md` Part 7.7 — Adapter 可行性
- `docs/designs/TD-dashboard-v1-implementation.md` — Dashboard 實作交接（依賴任務 1）
