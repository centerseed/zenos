---
type: SPEC
id: SPEC-mcp-id-ergonomics
status: Draft
ontology_entity: mcp-interface
created: 2026-04-20
updated: 2026-04-23
depends_on: SPEC-mcp-tool-contract
---

# SPEC: MCP ID Ergonomics & Dogfood Reject-Rate Metric

## 背景

2026-04-19 session `40bfd838...` 產生 12 次 rejected MCP call：
- 10 次 `write(collection="entries", id=<8-char short>)` → agent 從自己寫的 markdown 表格（git-style 短 ID）拿 ID 回頭呼叫，server 找不到
- 2 次 `analyze(check_type="entity_health")` → 缺 `entity_id`，agent 沒讀錯誤訊息就再打一次

**核心問題**：
1. Server error message 太 generic，沒指出 ID 格式要求
2. 讀取操作（get/search）無 prefix 比對，agent 只記得前幾碼就卡死
3. Dogfood workflow 不追蹤 agent 的 rejected-call rate，這類 ergonomics 缺陷不會浮上水面
4. Agent 分析表格用短 ID 再回灌 API 的反模式沒有文字紀律

## 目標

降低 agent 在 ID-based MCP 操作上的 rejected-call rate，讓失敗路徑自帶 recovery hint。

## 非目標

- 破壞性操作（write / task(action=handoff) / confirm）**不支援** prefix match（碰撞可能 archive 錯 entry）
- 不改 ID 格式或長度
- 不動既有 happy path 行為

## P0 Acceptance Criteria

### AC-MIDE-01: Write not-found 錯誤帶 ID 長度診斷
Given `mcp__zenos__write(collection="entries", id="39f160f5", data={"status":"archived","archive_reason":"manual"})`（8-char ID）
When server 查不到該 entry
Then `rejection_reason` 必須包含：(a) 實際傳入長度，(b) 預期長度 32，(c) 建議先 search/get 取完整 ID

### AC-MIDE-02: Get/analyze/source/attachment 的 not-found 一致升級
Given 以下端點傳入不合規 ID（長度 ≠ 32 或非 hex）：
- `get(collection="entities"|"documents"|"blindspots"|"tasks", id=<invalid>)`
- `analyze(check_type="entity_health", entity_id=<invalid>)`
- `source(action="read", doc_id=<invalid>)`
- `attachment(task_id=<invalid>)`
When 回傳 not-found
Then message 必須含 `id length mismatch (expected 32, got N)` 或 `非 hex 格式` 提示，並指向 search 建議

### AC-MIDE-03: search / get 新增 `id_prefix` 參數
Given `get(collection="entities", id_prefix="39f160f5")` 或 `search(collection="entries", id_prefix="39f1")`
When prefix 唯一匹配到 1 筆
Then 回 status=ok，data 為該筆完整記錄（含 full id）

When prefix 匹配 0 筆
Then 回 rejection_reason=`id_prefix '<p>' matches 0 entries`

When prefix 匹配 2+ 筆
Then 回 status=rejected、`rejection_reason=AMBIGUOUS_PREFIX`、`data.candidates=[{id, name, type}]`（最多 10 筆），不回傳原始 payload

### AC-MIDE-04: id_prefix 保持 workspace/partner 隔離
Given partner A 的 entry prefix `abc` 與 partner B 的同 prefix
When partner A 呼叫 `get(id_prefix="abc")`
Then 僅回傳 partner A 的記錄，不洩漏 B 的任何 id 或 metadata

### AC-MIDE-05: write/confirm/handoff 不接受 id_prefix
Given `write(collection="entries", id_prefix="abc", data=...)` 或 `task(action="handoff", id_prefix="abc")` 或 `confirm(id_prefix="abc")`
When 請求到達 server
Then 回 status=rejected、`rejection_reason=id_prefix_not_allowed_for_write_ops`

### AC-MIDE-06: Dogfood rejected-rate scanner
Given `scripts/dogfood/scan_mcp_reject_rate.py` 跑在 `~/.claude/projects/*/` 的 jsonl transcript 上
When 指定時間窗（預設最近 7 天）
Then 輸出每個 session：
- `mcp__zenos__*` 呼叫總數
- `status=rejected` 數量與佔比
- Top 3 `rejection_reason` 分類
- 相同 input retry 數（判斷是否有「沒讀錯誤就重打」pattern）

### AC-MIDE-07: Dogfood workflow 納入 reject-rate gate
Given `skills/workflows/dogfood.md` 的 iteration checklist
When 執行完 iteration
Then checklist 明列「跑 `scan_mcp_reject_rate.py`、reject rate > 5% 或出現新 top reason 需紀錄」

### AC-MIDE-08: Agent skill 加入 ID 使用紀律
Given `skills/release/{pm,architect,developer,qa,coach}/SKILL.md`
When agent 寫分析/報告並打算後續餵回 MCP tool
Then skill 明文規範：「若同一段文本會被自動化管線 consumer，必須保留 32-char full ID；只有純人類可讀摘要才能縮寫」

## Done Criteria

- AC-MIDE-01..08 對應的 test 從 FAIL 變 PASS
- `.venv/bin/pytest tests/spec_compliance/test_mcp_id_ergonomics_ac.py -x` 全綠
- `.venv/bin/pytest tests/ -x` 無 regression
- `python3 scripts/dogfood/scan_mcp_reject_rate.py --since 7d` 可跑並輸出正確 JSON
- deploy 後跑一次 smoke：對 real entry 做 `get(id_prefix=<prefix>)`、`write(id=<8-char>)`，確認新錯誤訊息生效
