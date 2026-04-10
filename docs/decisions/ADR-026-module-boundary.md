---
doc_id: ADR-026-module-boundary
title: 決策紀錄：Module Boundary — Code 層面落地分層
type: DECISION
ontology_entity: zenos-core
status: Draft
version: "1.0"
date: 2026-04-09
supersedes: null
---

# ADR-026: Module Boundary — Code 層面落地分層

## Context

ADR-025 定義了 ZenOS 五層概念分層模型，但明確聲明「五層是概念分層，不是部署分層」——所有層共享同一個 Python backend。問題是：概念分層如果沒有 code 結構做 enforce，分層只存在於 spec 裡，不存在於 codebase 裡。

現狀：

- `domain/models.py` 是 471 行的單體檔案，Knowledge Layer 的 Entity、Action Layer 的 Task、Identity Layer 的 UserPrincipal/AccessPolicy、Document Platform 的 DocRole/SourceStatus 全部混在一起
- `domain/repositories.py` 258 行，EntityRepository 和 TaskRepository 共處一室
- `infrastructure/sql_repo.py` 2514 行，14 個 class 全塞在一個檔案裡
- `interface/tools.py` 3951 行，包含 MCP tool 定義 + auth helper + visibility helper + serialize helper + audit log，職責完全沒有分離
- `application/` 有 10 個平面檔案，無 sub-package 分組

這些不是「將來會出問題」——它們已經在阻礙開發。每次改一個 tool 都要在 3951 行的檔案裡翻找；models.py 的每一次修改都影響所有層的 domain object。

用戶已確認三個決策方向：
1. 直接改所有 import path——不保留 re-export shim，一次性遷移
2. import-linter 加入 CI
3. 先拆再加功能——Phase 1 拆 module，然後才做 Plan 和 Auth Federation

## Decision Drivers

- 概念分層必須可 enforce，否則形同虛設
- 中小企業團隊（2-5 人），目錄結構不能太深、太碎
- 遷移必須是一個 atomic commit——不能出現「拆了一半」的中間狀態
- 既有 57 個測試檔案 + 2 個 script 的 import 必須一起改
- 不能影響 deploy pipeline（Cloud Run + Firebase Hosting）

## Decision

### D1. 目錄結構：按概念層拆 sub-package

```
src/zenos/
  domain/
    knowledge/        # Knowledge Layer
      __init__.py
      models.py       — Entity, Relationship, Document, DocumentTags, Source, Protocol, Gap, Tags, EntityEntry
      repositories.py — EntityRepository, RelationshipRepository, DocumentRepository, ProtocolRepository, BlindspotRepository
      enums.py        — EntityType, EntityStatus, RelationshipType, SourceType, DocumentStatus, EntryType, EntryStatus, Severity, BlindspotStatus
    action/           # Action Layer
      __init__.py
      models.py       — Task
      repositories.py — TaskRepository
      enums.py        — TaskStatus, TaskPriority
    identity/         # Identity & Access Layer
      __init__.py
      models.py       — UserPrincipal, AgentPrincipal, AgentScope, AccessPolicy
      enums.py        — Visibility, Classification, InheritanceMode, VISIBILITY_ORDER, CLASSIFICATION_ORDER
    document_platform/  # Document Platform Contract
      __init__.py
      enums.py        — DocRole, SourceStatus, DocStatus
    shared.py         — 跨層共用 value object（SplitRecommendation, TagConfidence, StalenessWarning, QualityCheckItem, QualityReport）
    governance.py     — 不動（已獨立）
    search.py         — 不動（已獨立）
    validation.py     — 不動（已獨立）
    doc_types.py      — 不動（已獨立）
    source_uri_validator.py — 不動（已獨立）
    task_rules.py     — 不動（已獨立）
    partner_access.py — 不動（已獨立）
    crm_models.py     — 不動（已獨立）
  application/
    knowledge/
      __init__.py
      ontology_service.py   — 搬自 application/ontology_service.py
      source_service.py     — 搬自 application/source_service.py
      governance_service.py — 搬自 application/governance_service.py
      governance_ai.py      — 搬自 application/governance_ai.py
    action/
      __init__.py
      task_service.py       — 搬自 application/task_service.py
    identity/
      __init__.py
      workspace_context.py        — 搬自 application/workspace_context.py
      permission_risk_service.py  — 搬自 application/permission_risk_service.py
      policy_suggestion_service.py — 搬自 application/policy_suggestion_service.py
    crm/
      __init__.py
      crm_service.py        — 搬自 application/crm_service.py
  infrastructure/
    knowledge/
      __init__.py
      sql_entity_repo.py         — SqlEntityRepository（從 sql_repo.py 拆出）
      sql_relationship_repo.py   — SqlRelationshipRepository
      sql_document_repo.py       — SqlDocumentRepository
      sql_protocol_repo.py       — SqlProtocolRepository
      sql_blindspot_repo.py      — SqlBlindspotRepository
      sql_entity_entry_repo.py   — SqlEntityEntryRepository
    action/
      __init__.py
      sql_task_repo.py           — SqlTaskRepository, PostgresTaskCommentRepository
    identity/
      __init__.py
      sql_partner_repo.py        — SqlPartnerRepository
      sql_partner_key_validator.py — SqlPartnerKeyValidator
    agent/
      __init__.py
      sql_tool_event_repo.py     — SqlToolEventRepository
      sql_usage_log_repo.py      — SqlUsageLogRepository
      sql_work_journal_repo.py   — SqlWorkJournalRepository
      sql_audit_event_repo.py    — SqlAuditEventRepository
    # 共用基礎設施（不拆 sub-package）
    context.py
    sql_pool.py          — 如果從 context.py 拆出，否則留在 context.py
    unit_of_work.py
    github_adapter.py
    gcs_client.py
    llm_client.py
    email_client.py
    crm_sql_repo.py
    firestore_repo.py    — legacy，保留不動
  interface/
    mcp/                 # MCP tool 入口
      __init__.py        — FastMCP app instance + middleware + _ensure_* init
      _auth.py           — partner context setup（從 tools.py 搬出）
      _common.py         — _serialize, _convert_datetimes, _unified_response, _new_id, _parse_entity_level
      _visibility.py     — _is_entity_visible, _guest_allowed_entity_ids, _is_task_visible, _is_protocol_visible, _is_blindspot_visible, _check_write_visibility, _guest_write_rejection
      _audit.py          — _audit_log, _schedule_audit_sql_write, _write_audit_event, _log_tool_event, _schedule_tool_event
      search.py          — search tool
      get.py             — get tool
      write.py           — write tool
      confirm.py         — confirm tool
      task.py            — task + _task_handler tool
      analyze.py         — analyze tool
      journal.py         — journal_write, journal_read tools
      governance.py      — governance_guide, find_gaps, common_neighbors tools
      source.py          — read_source, batch_update_sources tools
      attachment.py      — upload_attachment tool
      setup.py           — setup tool
      suggest_policy.py  — suggest_policy tool
    # 非 MCP 的 HTTP API（不拆 sub-package）
    dashboard_api.py
    admin_api.py
    crm_dashboard_api.py
    governance_rules.py
    setup_adapters.py
    setup_content.py
```

**為什麼這樣分：**

- domain 按概念層拆四個 sub-package（knowledge / action / identity / document_platform），直接映射 ADR-025 的五層模型。Agent Runtime Layer 沒有自己的 domain object，所以不需要 domain sub-package。
- application 和 infrastructure 按同樣的概念層拆，保持對稱。infrastructure 多了 `agent/` 放 tool event / usage log / journal / audit 這類 agent runtime 的持久化。
- interface/mcp/ 是最大的拆分——3951 行的 tools.py 拆成 ~15 個檔案，每個檔案對應一個 MCP tool 或一組 helper。
- 既有的 domain 獨立檔案（governance.py, search.py, validation.py 等）不動——它們已經是合理的單一職責，強行併入 sub-package 沒有收益。

**考慮過的替代方案：**

**替代方案 A：完全平面，只拆 tools.py。** 只把 tools.py 拆成多個檔案，其他不動。問題：models.py、sql_repo.py 的混亂不解決，概念分層仍然只存在於 spec 裡。改 Entity 的 schema 時仍然要在一個 471 行的檔案裡跟 Task、AccessPolicy 擠在一起。

**替代方案 B：更細的拆分，每個 class 一個檔案。** 例如 `domain/knowledge/entity.py`、`domain/knowledge/relationship.py`。問題：ZenOS 的 domain object 之間有密切的型別引用（Entity 用 Tags、EntityType、EntityStatus），拆太細會導致大量的跨檔 import 和循環依賴風險。模組級別的 `models.py` + `enums.py` 是足夠的粒度。

**替代方案 C：按 DDD bounded context 而非概念層拆。** 問題：ADR-025 的五層不是 bounded context——Knowledge Layer 和 Action Layer 共享 `linked_entities` 連接，不是各自獨立的 aggregate。按 bounded context 拆會強制複製 shared type，增加不必要的複雜度。

### D2. 遷移策略：一次性，直接改所有 import path

- 不保留 re-export shim（不在舊位置的 `__init__.py` 做 `from .knowledge.models import *`）
- `src/zenos/`、`tests/`、`scripts/` 的 import 一起改
- 一個 git commit 完成全部遷移

**為什麼不漸進式：**

漸進式遷移（先加 re-export shim，再逐步改 import）看似更安全，但實際上更危險：

1. **中間狀態持續時間不可控。** 「之後再改」的 import 永遠不會被改——沒有 CI 強制，舊路徑會一直被用。
2. **re-export shim 是技術債。** shim 存在期間，新 code 不確定該 import 新路徑還是舊路徑，產生認知負擔。
3. **ZenOS 的 codebase 規模可控。** 57 個測試檔 + 2 個 script + ~20 個 src 檔案的 import 修改，不是 monorepo 級別的大工程。全量替換的工作量是 2-4 小時，風險是一次性的。

**Tradeoff：** 一次性遷移如果有 import 沒改到，整個 backend 會啟動失敗。緩解方式：import-linter + pytest 在 commit 前跑過，確保所有 import 都正確。

### D3. 層間 import 規則

用 import-linter 的 contract 語法 enforce 以下規則：

| 規則 | 說明 |
|------|------|
| domain 不 import application / infrastructure / interface | domain 是純 dataclass + typing.Protocol，零外部依賴 |
| application 不 import infrastructure / interface | application 透過 Protocol 依賴 infrastructure，不直接 import |
| infrastructure 不 import interface | infra 提供 repo 實作，不知道 tool / API 的存在 |
| domain.knowledge 不 import domain.action | Knowledge Layer 不知道 Action Layer 的存在 |
| domain.action 可 import domain.knowledge | Task 的 linked_entities 引用 Entity，是有意為之的單向依賴 |
| 所有層可 import domain.shared | shared.py 放的是跨層 value object |
| domain.identity 不 import domain.knowledge / domain.action | Identity Layer 定義 principal 和 policy，不知道具體的 entity 或 task |

**為什麼 action 可以 import knowledge 但反過來不行：**

Task 透過 `linked_entities` 消費 Entity，但 Entity 不知道 Task 的存在。這是 ADR-025 D4 的直接後果——Task 不是 entity，是 entity 的消費者。如果允許 knowledge import action，Entity 就會開始長出 `tasks` 欄位，破壞知識骨架的純粹性。

### D4. import-linter 加入 CI

```toml
# pyproject.toml 或 .importlinter
[importlinter]
root_package = zenos

[importlinter:contract:domain-isolation]
name = Domain layer must not import upper layers
type = forbidden
source_modules =
    zenos.domain
forbidden_modules =
    zenos.application
    zenos.infrastructure
    zenos.interface

[importlinter:contract:application-isolation]
name = Application layer must not import upper layers
type = forbidden
source_modules =
    zenos.application
forbidden_modules =
    zenos.infrastructure
    zenos.interface

[importlinter:contract:infrastructure-isolation]
name = Infrastructure layer must not import interface
type = forbidden
source_modules =
    zenos.infrastructure
forbidden_modules =
    zenos.interface

[importlinter:contract:knowledge-action-direction]
name = Knowledge must not import Action
type = forbidden
source_modules =
    zenos.domain.knowledge
forbidden_modules =
    zenos.domain.action
```

加入 CI pipeline（`.github/workflows/` 或等效），與 pytest 並行執行。失敗即 block merge。

### D5. tools.py 的 auth/visibility helper 搬到 interface/mcp/ 內部模組

tools.py 裡約 800 行的 helper function 不搬到 application/identity/——它們的職責是 MCP-specific 的 auth context setup 和 visibility filtering，不是 application-level 的業務邏輯。搬到 `interface/mcp/_auth.py` 和 `interface/mcp/_visibility.py`。

**原始考慮：** 搬到 application/identity/ 讓 dashboard_api.py 也能共用 visibility 邏輯。但 dashboard_api.py 有自己的 auth middleware（Firebase Auth），visibility 的判斷方式不同。強行抽象會讓兩邊都不自然。

**未來：** 當 dashboard API 和 MCP tool 的 visibility 邏輯確實需要共用時，再提取到 application 層。現在不做——YAGNI。

## Implementation Impact

### 檔案影響估計

| 類別 | 數量 | 說明 |
|------|------|------|
| 新建 sub-package `__init__.py` | ~15 | domain/knowledge/, domain/action/ 等 |
| 拆分產生的新檔案 | ~25 | models.py 拆 3 份、sql_repo.py 拆 ~10 份、tools.py 拆 ~15 份 |
| 刪除的舊檔案 | 3 | domain/models.py、infrastructure/sql_repo.py、interface/tools.py |
| import 需修改的 test 檔案 | ~57 | 所有引用 zenos.domain.models 或 zenos.interface.tools 的測試 |
| import 需修改的 script 檔案 | 2 | scripts/ 下引用 zenos 的檔案 |
| import 需修改的 src 檔案 | ~20 | application、infrastructure、interface 間的互相引用 |

**總計：** 新建 ~40 檔案、刪除 3 檔案、修改 ~80 檔案。

### 對 test 的影響

- 所有 `from zenos.domain.models import ...` 要改成 `from zenos.domain.knowledge.models import ...` 或對應的 sub-package
- 所有 `from zenos.infrastructure.sql_repo import ...` 要改成對應的 sub-package 檔案
- 測試的邏輯不需要改，只改 import path
- import-linter 會同時驗證 test 的 import 是否合規

### 對 deploy 的影響

- **零影響。** 目錄結構改變不影響 Cloud Run 的 container build（Dockerfile 打包整個 `src/`）和 Firebase Hosting（只管 `dashboard/`）
- `deploy_mcp.sh` 不需要修改——它 build 的是 Python package，不依賴具體的 module path
- 唯一需要確認的：Cloud Run 的 entrypoint 如果引用 `zenos.interface.tools`，需要改成 `zenos.interface.mcp`

## Risks

### 最大風險：一次性遷移時有 import 沒改到

**機率：** 中。80+ 個檔案的 import 修改，靠人工逐一改容易遺漏。

**緩解：**
1. 用 `sed` / IDE 全局替換，不手動逐一改
2. 遷移完立刻跑 `pytest tests/ -x`——任何遺漏的 import 會在 import time 爆炸，不會靜默通過
3. import-linter 做第二道防線

### 中等風險：sub-package 的 `__init__.py` re-export 策略

每個 sub-package 的 `__init__.py` 是否要 re-export 所有 public symbol？如果不 re-export，外部必須 `from zenos.domain.knowledge.models import Entity`（路徑較長）。如果 re-export，`from zenos.domain.knowledge import Entity`（較短但 `__init__.py` 變成隱式 API surface）。

**決策：** 每個 sub-package 的 `__init__.py` re-export 該層的所有 public symbol。理由：import path 過長會讓開發者回去走舊路徑。re-export 的維護成本可控——每個 sub-package 的 symbol 數量不超過 15 個。

### 低風險：tools.py 拆分後的 module-level state 管理

tools.py 有 module-level 的 singleton（`_entity_repo`, `_task_repo` 等全局變數），拆成多個檔案後這些 singleton 需要有一個統一的 home。

**決策：** 放在 `interface/mcp/__init__.py` 裡，各 tool 檔案 import 它。

## Consequences

### Positive

- **概念分層有 code enforce。** import-linter 違反即 CI 失敗，不再是 spec 裡的承諾。
- **單檔案行數大幅降低。** tools.py 3951 行 → 最大單檔 ~400 行；sql_repo.py 2514 行 → 最大單檔 ~350 行。
- **開發效率提升。** 改 Knowledge Layer 的 code 不用翻過 Task 和 AccessPolicy；改一個 MCP tool 不用在 4000 行裡定位。
- **新人 onboarding 更直覺。** 目錄結構直接映射 ADR-025 的概念層，不需要額外的「概念層 → 檔案」mapping 文件。

### Negative

- **一次性遷移的風險視窗。** commit 到 merge 之間，如果有其他 branch 在改 tools.py，會產生大量 merge conflict。緩解：在遷移前宣告 code freeze 窗口。
- **import path 變長。** `from zenos.domain.models import Entity` → `from zenos.domain.knowledge import Entity`（長度差不多）或 `from zenos.domain.knowledge.models import Entity`（較長）。透過 `__init__.py` re-export 緩解。
- **目錄層級加深一層。** `domain/models.py` → `domain/knowledge/models.py`。對檔案總數 < 100 的 codebase 來說，加深一層的 navigation 成本可接受。
