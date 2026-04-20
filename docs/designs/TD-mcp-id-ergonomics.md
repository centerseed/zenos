---
type: TD
id: TD-mcp-id-ergonomics
spec: SPEC-mcp-id-ergonomics.md
status: Draft
created: 2026-04-20
updated: 2026-04-20
---

# TD: MCP ID Ergonomics & Dogfood Reject-Rate Metric

## 調查報告

（已於對話中產出，關鍵結論）：

- ID 格式：`uuid.uuid4().hex` → 32-char lowercase hex（`_common.py:184`）
- not-found 錯誤分佈：`write.py:667/722`、`get.py:125/315/357/379`（16 處）、`analyze.py:244`、`source.py:66/110/203`、`attachment.py:57`
- 所有 repo 都只有 `get_by_id(x)` 做 exact match，無 prefix 支援
- search 既有 `entity_id` 參數（`search.py:69`），結構上可再加 `id_prefix`

## AC Compliance Matrix

| AC ID | AC 描述（摘要） | 實作位置 | Test Function | 狀態 |
|-------|---------------|---------|---------------|------|
| AC-MIDE-01 | entries write not-found 帶長度診斷 | `src/zenos/interface/mcp/write.py` | `test_ac_mide_01_write_entry_not_found_hint` | STUB |
| AC-MIDE-02 | get/analyze/source/attachment not-found 一致升級 | `get.py`, `analyze.py`, `source.py`, `attachment.py` + `_common.py` | `test_ac_mide_02_get_not_found_hint`, `test_ac_mide_02_analyze_not_found_hint`, `test_ac_mide_02_source_not_found_hint`, `test_ac_mide_02_attachment_not_found_hint` | STUB |
| AC-MIDE-03 | get/search 加 id_prefix 參數 | `get.py`, `search.py` + repo 新增 `find_by_id_prefix` | `test_ac_mide_03_get_id_prefix_unique`, `test_ac_mide_03_get_id_prefix_ambiguous`, `test_ac_mide_03_search_id_prefix_zero` | STUB |
| AC-MIDE-04 | id_prefix 保持 partner 隔離 | `sql_entity_repo.py`, `sql_entity_entry_repo.py` 等 | `test_ac_mide_04_id_prefix_workspace_isolation` | STUB |
| AC-MIDE-05 | write/confirm/handoff 拒絕 id_prefix | `write.py`, `task.py`, `confirm.py` | `test_ac_mide_05_write_rejects_id_prefix`, `test_ac_mide_05_handoff_rejects_id_prefix`, `test_ac_mide_05_confirm_rejects_id_prefix` | STUB |
| AC-MIDE-06 | dogfood reject-rate scanner | `scripts/dogfood/scan_mcp_reject_rate.py` | `test_ac_mide_06_scan_reject_rate_output` | STUB |
| AC-MIDE-07 | dogfood workflow 納入 gate | `skills/workflows/dogfood.md` + release 同步 | manual review + `test_ac_mide_07_dogfood_workflow_mentions_gate` | STUB |
| AC-MIDE-08 | agent skill 加 ID 紀律 | `skills/release/{pm,architect,developer,qa,coach}/SKILL.md` | `test_ac_mide_08_agent_skills_mention_full_id` | STUB |

## Component 架構

### 新增共用 helper（`_common.py`）

```python
# src/zenos/interface/mcp/_common.py
import re

_VALID_ID_RE = re.compile(r"^[0-9a-f]{32}$")

def _validate_id_format(id_value: str) -> str | None:
    """檢查 ID 格式。回傳錯誤訊息，或 None 表示合法。"""
    if not id_value:
        return "id is required"
    if len(id_value) != 32:
        return (
            f"id length mismatch (expected 32, got {len(id_value)}). "
            f"ID 必須為 32 字元 hex。若只記得前綴，請用 search(id_prefix=...) 或 "
            f"get(id_prefix=...) 取完整 ID。"
        )
    if not _VALID_ID_RE.match(id_value.lower()):
        return (
            f"id 含非 hex 字元。ID 必須為 32 字元 lowercase hex。"
            f"請用 search(id_prefix=...) 確認。"
        )
    return None

def _format_not_found(resource: str, id_value: str) -> str:
    """統一 not-found 錯誤訊息。"""
    hint = _validate_id_format(id_value)
    if hint:  # 格式問題優先於 not-found
        return f"{resource} '{id_value}' not found — {hint}"
    return (
        f"{resource} '{id_value}' not found. "
        f"請用 search(query=...) 或 search(id_prefix=...) 確認 ID 正確。"
    )
```

### 讀取端 id_prefix 管線

```
caller (get/search with id_prefix)
  ↓
mcp interface layer
  - 驗證 prefix 至少 4 字元、純 hex
  - 呼叫 repo.find_by_id_prefix(prefix, partner_id, limit=11)
  ↓
repo 層新增方法
  - sql_entity_repo.find_by_id_prefix(prefix, partner_id, limit) -> list[Entity]
  - sql_entity_entry_repo.find_by_id_prefix(prefix, partner_id, limit) -> list[EntityEntry]
  - sql_task_repo.find_by_id_prefix(prefix, partner_id, limit) -> list[Task]
  - sql_document_repo.find_by_id_prefix(prefix, partner_id, limit) -> list[Document]
  - sql_blindspot_repo.find_by_id_prefix(prefix, partner_id, limit) -> list[Blindspot]
  SQL: WHERE id LIKE $1 || '%' AND partner_id = $2 LIMIT 11
  limit=11 讓我們能回傳 "超過 10 筆" 語意
  ↓
interface 處理
  - 0 筆 → rejected "id_prefix matches 0 entries"
  - 1 筆 → 回完整 payload（同 exact id 路徑）
  - 2~10 筆 → rejected AMBIGUOUS_PREFIX + candidates list
  - 11 筆 → rejected AMBIGUOUS_PREFIX + "超過 10 筆，請增加 prefix 長度"
```

### 寫入端拒絕 id_prefix

`write.py` / `task.py(action=handoff|update|delete)` / `confirm.py` 入口處：
```python
if id_prefix is not None:
    return _unified_response(
        status="rejected",
        rejection_reason="id_prefix_not_allowed_for_write_ops",
        data={"hint": "write 類操作需完整 32-char id，避免 prefix 碰撞誤傷"},
    )
```

### Dogfood scanner

```
scripts/dogfood/scan_mcp_reject_rate.py
  --since 7d | YYYY-MM-DD
  --transcripts-dir ~/.claude/projects/
  --format json | markdown
  輸出:
    {
      "window": "7d",
      "sessions_scanned": N,
      "total_mcp_calls": M,
      "rejected_count": K,
      "reject_rate": K/M,
      "top_rejection_reasons": [{"reason": ..., "count": ...}, ...],
      "same_input_retries": N,
      "sessions": [{"session_id": ..., "calls": ..., "rejected": ..., "rate": ...}]
    }
```

## 介面合約清單

| 函式/API | 新增參數 | 型別 | 必填 | 說明 |
|----------|---------|------|------|------|
| `get` | `id_prefix` | `str \| None` | 否 | 至少 4 char hex；與 `id` 互斥 |
| `search` | `id_prefix` | `str \| None` | 否 | 至少 4 char hex |
| `write` | — | — | — | 新增內部檢查：`id_prefix` kwarg 若存在一律 reject |
| `confirm` | — | — | — | 同上 |
| `task(action=handoff/update/delete)` | — | — | — | 同上 |
| Repo: `find_by_id_prefix(prefix, partner_id, limit=11)` | — | — | — | 新增於 5 個 repo |

## DB Schema 變更

無。`id` 欄位在 PostgreSQL 已有 B-tree index，`LIKE 'prefix%'` 可走 index range scan。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| S01 | `_common.py` 加 `_validate_id_format` + `_format_not_found`；write/get/analyze/source/attachment 全部改用 | Developer | AC-MIDE-01, AC-MIDE-02 test 從 FAIL → PASS；既有 tests 無 regression |
| S02 | 5 repo 加 `find_by_id_prefix`；get/search 加 `id_prefix` 參數；write/confirm/handoff 拒絕 id_prefix | Developer | AC-MIDE-03, 04, 05 test PASS |
| S03 | `scripts/dogfood/scan_mcp_reject_rate.py` + 對應 test | Developer | AC-MIDE-06 test PASS；可對現有 transcripts 跑出正確統計 |
| S04 | `skills/workflows/dogfood.md` 加 gate；`skills/release/{pm,architect,developer,qa,coach}/SKILL.md` 加 ID 紀律段落；跑 `scripts/sync_skills_from_release.py` | Developer | AC-MIDE-07, 08 test PASS；grep 驗證文字段落存在 |

## Risk Assessment

### 1. 不確定的技術點
- `id LIKE 'prefix%'` 在 Cloud SQL PostgreSQL 實際 query plan？預期走 B-tree index prefix scan，但需 Developer 跑 EXPLAIN 確認
- `~/.claude/projects/` 在 CI 環境不存在；scanner test 需 mock transcript dir

### 2. 替代方案與選擇理由
- **方案 A（選）**：write 不支援 prefix + get/search 支援 + error msg hint
  - 優點：閃避破壞性誤觸；agent 仍能用 prefix 做讀取探查
  - 缺點：agent 需多一次 read round-trip 才拿到 full id 去 write
- **方案 B（否決）**：write 也支援 prefix，碰撞時 reject
  - 缺點：若 partner 資料量大、未來 prefix 碰撞無警示就 archive 錯東西，風險不可逆
- **方案 C（否決）**：只改 error message，不加 prefix 支援
  - 缺點：治標不治本，agent 仍需自己 search 拿 full id

### 3. 需要用戶確認的決策
- prefix 最小長度（目前設 4）— 4 = 16^4 = 65536 namespace，對單 partner ~千筆 entry 碰撞率極低；若 partner 資料規模大到十萬級，應調到 6
- 候選筆數上限（目前設 10，query 到 11 偵測「過多」） — 若實際常見碰撞超過，調整

### 4. 最壞情況與修正成本
- 最壞情況：SQL prefix LIKE 在大表拖慢 query → 加 partial index `CREATE INDEX ON entries (partner_id, id text_pattern_ops)` 補救
- agent skill 變更：只改文件，rollback 成本極低
- error msg 升級：破壞 UI parse 「Entry 'xxx' not found」的 client？grep 現有 code 應無此依賴
