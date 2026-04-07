# Architect 參考資料：調度、治理、決策

本文件是 Architect SKILL.md 的延伸參考，包含 MCP tool 語法、subagent 調度細節、決策框架。

---

## ZenOS Task 操作語法

### 建票

```python
mcp__zenos__task(
    action="create",
    title="動詞開頭的標題",
    description="markdown 格式描述",
    acceptance_criteria=["AC1", "AC2"],   # list[str]
    linked_entities=["entity-id-1"],      # 先 search 找 ID
    priority="critical|high|medium|low",
)
```

> 建票前必讀 `skills/governance/shared-rules.md` 的去重與 linked_entities 規則。

### 更新票狀態

```python
mcp__zenos__task(
    action="update",
    id="task-id",
    status="in_progress",  # todo → in_progress → review → (confirm) → done
    result="交付說明",     # update to review 時必填
)
```

- 改到 `review` 時 result 為必填
- **不能用 update 改成 done**，必須用 `confirm(accepted=True)` 驗收

### 狀態流

```
todo → in_progress → review → (confirm) → done
任何活躍狀態 → cancelled
```

---

## Journal 寫入規則

### 寫入前先查

```python
mcp__zenos__journal_read(limit=20, project="{專案名}")
```

找同主題的近期筆記：
- 同一件事的延續 → 新 summary 包含完整脈絡，讓舊筆記變冗餘
- 新的不相關工作 → 正常新增

### 寫入

summary 必須回答三件事：
1. **做了什麼**（一句話，git log 有的不重複）
2. **為什麼這樣做**（不可從 code 重建的決策或洞察）
3. **下一步或遺留**

```python
mcp__zenos__journal_write(
    summary="{功能/修復}：{關鍵決策}；下一步：{next 或 無}",
    project="{專案名}",
    flow_type="feature",  # 或 "bugfix" / "refactor" / "research"
    tags=["{模組名}"]
)
```

不要寫：file 清單、數量統計、重複 commit message 的內容。

---

## 文件 Frontmatter（必填）

```yaml
---
type: SPEC | ADR | TD | PB | SC | REF
id: {前綴}-{slug}
status: Draft | Under Review | Approved | Superseded | Archived
l2_entity: {ZenOS L2 entity slug}
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### 寫完文件後同步 ZenOS

```python
mcp__zenos__write(
    collection="documents",
    data={
        "doc_id": "SPEC-feature-slug",
        "title": "功能規格：標題",
        "type": "SPEC",
        "ontology_entity": "entity-slug",
        "status": "draft",
        "source": {"uri": "docs/specs/SPEC-feature-slug.md"},
    }
)
```

---

## Subagent 調度細節

### 調度 Developer

1. `Read skills/release/developer/SKILL.md` 完整內容
2. 用 Agent tool 開 subagent，prompt 包含：
   - Developer SKILL.md **全文**
   - Spec 內容（或路徑 + 關鍵段落）
   - 技術設計（或 ADR 路徑 + 關鍵段落）
   - Done Criteria（具體、可驗證，含每個介面參數）
   - 架構約束與安全要求
   - 結尾：「按 Developer skill 流程：實作 → 最小 scope 測試 → simplify → 全套測試 → Completion Report」

### 調度 QA

1. `Read skills/release/qa/SKILL.md` 完整內容
2. 用 Agent tool 開 subagent，prompt 包含：
   - QA SKILL.md **全文**
   - Spec 內容（或路徑 + 關鍵段落）
   - Developer Completion Report
   - P0 測試場景（必須全部通過）
   - P1 測試場景（應該通過）
   - 結尾：「按 QA skill 流程：靜態檢查 → 跑測試 → 場景測試 → QA Verdict」

---

## 決策框架（六約束）

每個技術決策對照這六點：

1. **選型有依據** — 為什麼選這個？取捨是什麼？
2. **依賴方向正確** — 內層沒有 import 外層
3. **從第一性原理出發** — 問題本質是什麼？現有工具能解決嗎？
4. **不重複造輪子** — 有現成好工具就用
5. **不讓架構發散** — 回扣核心技術共識
6. **不過度設計** — YAGNI，現在不需要的彈性不加

重大決策寫 ADR，用 SKILL.md 的 ADR 模板。

---

## 問責原則

- 任務分配不清楚 → Architect 的問題
- 驗收標準沒說清楚 → Architect 的問題
- 技術設計與 PM spec 有落差 → Architect 要在開始前發現
- 部署後服務不可用 → Architect 的問題

## 遇阻處理

任何阻礙（測試資料不足、API 錯誤、環境問題、subagent 失敗）：

1. 方案 A：嘗試其他操作路徑
2. 方案 B：用不同的驗證方法
3. 方案 C：調整測試環境
4. **只有 3+ 個方案都失敗才能向用戶報告**，報告時列出所有嘗試過的方案
