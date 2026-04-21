---
type: DESIGN
id: TD-governed-access-runtime-hardening
status: Draft
ontology_entity: 身份與權限管理
spec: SPEC-google-workspace-per-user-retrieval
created: 2026-04-21
updated: 2026-04-21
---

# 技術設計：Governed Access Runtime Hardening

## 調查報告

### 已讀文件（附具體發現）
- `docs/specs/SPEC-identity-and-access.md` — P0 六條骨架已定，但 `connector scope` 仍只有原則與 AC，沒有 executable runtime contract。
- `docs/specs/SPEC-zenos-external-integration.md` — 外部 app 已要求 `read_source` 受 connector scope + content policy 約束，但沒有 Google Workspace `per_user_live` 的具體規則。
- `docs/specs/SPEC-zenos-auth-federation.md` — delegated credential 已是正式 caller identity；不用另開第二套 auth。
- `docs/specs/SPEC-docs-native-edit-and-helper-ingest.md` — helper summary 路徑已落地；GDrive/Notion 目前仍是 helper-only。
- `docs/decisions/ADR-030-mcp-authorization-hardening.md` — fail-closed 與 JWT scope 已收斂，但 connector scope / per-user source access 尚未被納入。
- `src/zenos/interface/mcp/_visibility.py` — 例外已 fail-closed，但 document visibility 尚未考慮 source scope。
- `src/zenos/interface/mcp/source.py` — 已有 `content_access=summary|full|none`；沒有 connector scope 過濾，也沒有 `per_user_live`。
- `src/zenos/interface/mcp/_auth.py` — JWT `workspace_ids` 與 scope enforcement 已可直接重用。
- `src/zenos/interface/dashboard_api.py` — Dashboard docs list / get 目前直接回 `sources`，沒有 source-level concealment。
- `src/zenos/application/knowledge/ontology_service.py` — write source mutation 尚未保留 `container_id / retrieval_mode / content_access`。

### 搜尋但未找到
- `per-user live retrieval` 的既有 SPEC/TD
- `connectorScopes` runtime model
- 真正的 Google Workspace live reader 實作

### 我不確定的事
- [未確認] 本輪不實作 Google OAuth / token refresh；只實作 server runtime contract 與 live-reader hook。

### 結論
可直接落最小版本：
- `partner.preferences.connectorScopes` 當 workspace connector allowlist
- `source.container_id + retrieval_mode + content_access` 當 source contract
- `read_source` 對 `per_user_live` 只走 live reader，不回退到 shared full-content
- MCP + Dashboard 對 blocked source 做一致 concealment

## AC Compliance Matrix

| AC ID | AC 描述 | 實作位置 | Test Function | 狀態 |
|-------|--------|---------|---------------|------|
| AC-GWPR-01 | connector scope empty allowlist hides doc/source | `source_access_policy.py`, `_visibility.py`, `dashboard_api.py`, `get.py` | `test_ac_gwpr_01_empty_connector_scope_conceals_document` | PASS |
| AC-GWPR-02 | out-of-scope source is concealed on read_source | `source_access_policy.py`, `source.py` | `test_ac_gwpr_02_read_source_out_of_scope_returns_not_found` | PASS |
| AC-GWPR-03 | mixed-source doc only returns in-scope sources | `dashboard_api.py`, `get.py` | `test_ac_gwpr_03_mixed_doc_filters_blocked_sources` | PASS |
| AC-GWPR-04 | per_user_live without live reader returns required error | `source.py` | `test_ac_gwpr_04_per_user_live_without_reader_returns_required` | PASS |
| AC-GWPR-05 | per_user_live with live reader returns full content | `source.py` | `test_ac_gwpr_05_per_user_live_uses_live_reader` | PASS |
| AC-GWPR-06 | per_user_live + summary only returns snapshot summary | `source.py` | `test_ac_gwpr_06_per_user_live_summary_mode_returns_snapshot` | PASS |
| AC-GWPR-07 | blocked docs behave as not found on MCP get/dashboard metadata | `_visibility.py`, `ontology_service.py`, `dashboard_api.py`, `get.py` | `test_ac_gwpr_07_blocked_document_behaves_as_not_found` | PASS |
| AC-GWPR-08 | write path preserves new source access fields | `ontology_service.py` | `test_ac_gwpr_08_write_preserves_source_access_fields` | PASS |

## Component 架構

```
partner.preferences.connectorScopes
        ↓
application/identity/source_access_policy.py
        ├─ is_source_in_connector_scope()
        ├─ filter_sources_for_partner()
        └─ normalized_retrieval_mode()
        ↓
MCP surface
  - _visibility.py
  - source.py
  - get.py

Dashboard surface
  - dashboard_api.py

Write path
  - ontology_service.py
```

## 介面合約清單

| 函式/API | 參數 | 型別 | 必填 | 說明 |
|----------|------|------|------|------|
| `partner.preferences.connectorScopes.{connector}.containers` | `containers` | `string[]` | 否 | workspace allowlist；若 connector config 存在但清單為空，代表 deny-all |
| `source.container_id` | `container_id` | `string` | 否 | source 所屬 connector container |
| `source.container_ids` | `container_ids` | `string[]` | 否 | 多 container 版本；任一命中 allowlist 即可 |
| `source.retrieval_mode` | `retrieval_mode` | `direct \| snapshot \| per_user_live` | 否 | `per_user_live` 代表全文只能由 live reader 取得 |
| `source.content_access` | `content_access` | `summary \| full \| none` | 否 | 既有暴露層級；搭配 `retrieval_mode` 使用 |
| `source_service.read_source_live()` | `doc_id, source_uri, source, partner` | callable hook | 否 | 若存在，`per_user_live + full` 時由 `source.py` 呼叫 |

## DB Schema 變更

無。

本輪只使用既有 `partners.preferences` JSONB 與 `entities.sources_json` JSONB。`container_id / retrieval_mode / content_access` 都落在 `sources_json` 內。

## 任務拆分

| # | 任務 | 角色 | Done Criteria |
|---|------|------|--------------|
| 1 | 補 spec amendment + 新 spec | Architect | `SPEC-identity-and-access` / `SPEC-zenos-external-integration` / `SPEC-google-workspace-per-user-retrieval` 一致 |
| 2 | 抽 source access policy 共用模組 | Developer | MCP + Dashboard 共用同一套 connector scope / retrieval_mode logic |
| 3 | 補 read path concealment 與 live retrieval gate | Developer | `read_source` / `get` / dashboard docs metadata 符合 AC-GWPR-01~07 |
| 4 | 補 write path source schema 保留 | Developer | `container_id / retrieval_mode / content_access` 被保留在 `sources_json` |
| 5 | 補 spec compliance tests + regression | QA | AC-GWPR-01~08 全 PASS，無既有權限回歸 |

## Risk Assessment

### 1. 不確定的技術點
- 真正的 Google live reader 尚未存在；本輪只定 hook 與 fail-closed 行為。

### 2. 替代方案與選擇理由
- 替代方案：直接做 workspace-shared full ingest。
  不選理由：會把 Google ACL 打平，與 governed access 目標衝突。
- 替代方案：先只補 spec，不動 runtime。
  不選理由：`connector scope` 會繼續停在紙上，無法算完成。

### 3. 需要用戶確認的決策
- 無。你前面已明確選 A：`per-user live retrieval`。

### 4. 最壞情況與修正成本
- 若未來 `partner.preferences.connectorScopes` 不夠用，要搬到正式 workspace/connector table。
  修正成本中等，但不會推翻本輪的 runtime contract。

## Spec Compliance Matrix 對應測試檔

- `tests/spec_compliance/test_google_workspace_per_user_retrieval_ac.py`

## Done Criteria

1. `SPEC-google-workspace-per-user-retrieval` 已建立並帶 AC-GWPR-01~08
2. `TD-governed-access-runtime-hardening` 已補齊 compliance matrix / interface contract / risk / done criteria
3. source access policy 已抽成共用模組，MCP 與 Dashboard 共用
4. `read_source` 對 `per_user_live` 不再回退到 shared full-content
5. MCP `get(document)` 與 Dashboard docs metadata 會過濾 blocked source
6. document visibility 對 all-blocked external docs fail closed
7. write path 保留 `container_id / retrieval_mode / content_access`
8. `tests/spec_compliance/test_google_workspace_per_user_retrieval_ac.py` 全 PASS
