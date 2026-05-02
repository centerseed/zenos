---
doc_id: SPEC-journal-compression-resilience
title: 功能規格：Journal compression resilience
type: SPEC
ontology_entity: MCP 介面設計
status: approved
version: "1.0"
date: 2026-05-01
supersedes: null
---

# 功能規格：Journal compression resilience

## Background

2026-05-01 prod log 顯示 `zenos-mcp-00263-g6s` 在 `_compress_journal` 觸發 LLM structured output parse failure。主流程被 catch 後沒有直接 500，但 traceback 被 Cloud Run / Error Reporting 收成 ERROR group，造成治理健康誤判，且 journal 壓縮沒有完成。

## Scope

- Journal compression 的 LLM 摘要步驟必須降級為 best-effort。
- LLM structured output 失敗時，server 必須使用 deterministic fallback summary 繼續壓縮。
- LLM 摘要失敗不得輸出 traceback 到 Error Reporting。
- DB / repository 失敗仍可保留原有保護與 traceback，避免真正資料層問題被靜音。

## Acceptance Criteria

- `AC-JCR-01` Given journal originals exceed compression threshold and LLM structured summary fails, When `_compress_journal` runs, Then it creates a summary row with deterministic fallback text, deletes compressed originals, and returns `True`.
- `AC-JCR-02` Given LLM structured summary fails, When `_compress_journal` logs the failure, Then the warning does not include `exc_info=True` traceback.
- `AC-JCR-03` Given LLM structured summary succeeds with non-empty summary, When `_compress_journal` runs, Then it uses the LLM summary instead of fallback text.
- `AC-JCR-04` Given `journal_write` triggers compression and LLM summary fails, When the tool returns, Then response remains `status="ok"` with `data.compressed=True`.

## Notes

- This does not change journal retention policy: keep the newest 9 original entries and compress older originals.
- This does not change `create_summary` DB length clamp.
