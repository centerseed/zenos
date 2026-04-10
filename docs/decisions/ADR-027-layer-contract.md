---
doc_id: ADR-027-layer-contract
title: 決策紀錄：Layer Contract Protocol — 層間公開介面與呼叫規則
type: DECISION
ontology_entity: zenos-core
status: Draft
version: "1.0"
date: 2026-04-09
supersedes: null
---

# ADR-027: Layer Contract Protocol — 層間公開介面與呼叫規則

## Context

ADR-025 定義五層概念分層模型，ADR-026 定義 module boundary 拆分策略（sub-package + import-linter）。兩份 ADR 解決了「怎麼分」和「怎麼 enforce 分層」，但沒回答：

1. **每一層的 public contract 是什麼？** sub-package 拆完後，`__init__.py` 該 export 哪些 symbol？
2. **跨層呼叫的規則是什麼？** TaskService 需要查 Entity 時，該 import OntologyService 還是 EntityRepository？
3. **tools.py 拆分後，MCP module 怎麼呼叫 application service？** 需不需要一個 facade 或 mediator？
4. **tools.py 裡的 helper function 怎麼歸類？** 哪些是 MCP-specific，哪些其實是 application/domain logic？

這些問題如果不統一決策，ADR-026 的拆分會在實作時出現分歧——不同開發者對「跨層怎麼接」有不同理解，最終分層形同虛設。

### 現狀觀察

**tools.py 如何呼叫 service：**

```python
# interface/tools.py — module-level singleton
ontology_service: OntologyService | None = None
task_service: TaskService | None = None

async def _ensure_services() -> None:
    global ontology_service, task_service
    ontology_service = OntologyService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        ...
    )
    task_service = TaskService(
        task_repo=task_repo,
        entity_repo=entity_repo,
        blindspot_repo=blindspot_repo,
        ...
    )
```

MCP tool function 直接使用 `ontology_service.search(...)`, `task_service.create_task(...)` 等。中間沒有 facade、沒有 mediator——tool function 直接呼叫對應的 application service method。

**Service 之間的依賴方式：**

- `TaskService.__init__` 接收 `entity_repo: EntityRepository` 和 `blindspot_repo: BlindspotRepository`——它透過 repository Protocol 讀取 Knowledge Layer 資料，**不** import `OntologyService`。
- `OntologyService.__init__` 接收五個 repository + `governance_ai` + `source_adapter`——它不知道 `TaskService` 的存在。
- `GovernanceService.__init__` 接收 `task_repo: TaskRepository`——它透過 repository Protocol 讀取 Action Layer 資料，不 import `TaskService`。

**tools.py 的 helper function：**

tools.py 內約 800 行 helper，ADR-026 D5 已決定搬到 `interface/mcp/` 內部模組。但尚未分類「哪些 helper 的邏輯其實屬於 application/domain 層」。

## Decision Drivers

- DDD 的依賴方向規則已由 ADR-026 D3 用 import-linter enforce；layer contract 必須與之一致
- 現有的 service 依賴方式（repository injection）運作良好，不應為了「更乾淨」而引入新抽象
- tools.py 拆成 ~15 個 MCP module 後，必須有明確的「MCP module → service」呼叫慣例
- 過度抽象（facade / mediator / service locator）在 2-5 人團隊是淨負擔

## Decision

### D1. 不新建 facade 或 mediator — MCP module 直接 import 對應 application service

**決策：** ADR-026 拆分後的各 MCP module（`interface/mcp/search.py`、`interface/mcp/task.py` 等）直接 import 對應的 application service class，透過 `interface/mcp/__init__.py` 的 module-level singleton 取得 service instance。

```python
# interface/mcp/task.py
from zenos.interface.mcp import task_service  # module-level singleton

async def handle_task(...):
    result = await task_service.create_task(data)
```

**不建 facade 的理由：**

DDD 的 application layer 本身就是 facade。`OntologyService` 對外暴露 `search()`、`upsert_entity()`、`get_entity()` 等 method，每個 method 對應一個 use case，內部編排 domain logic 和 repository 呼叫。在它上面再加一層 `ZenosFacade`，只是把 `facade.search()` 代理到 `ontology_service.search()`——零語意增值，多一層 indirection。

**不建 mediator 的理由：**

Mediator pattern 的價值在於解耦「請求發送方」和「請求處理方」——發送方不需要知道由誰處理。但 MCP tool 的語意已經決定了它該呼叫哪個 service：`search` tool 一定呼叫 `OntologyService.search()`，`task` tool 一定呼叫 `TaskService`。Mediator 在這裡只增加 dispatch 複雜度，不減少耦合。

**考慮過的替代方案：**

**替代方案 A：建一個 `ApplicationFacade` 統一所有 service 的入口。** 問題：facade 必須 import 所有 service class、轉發所有 method、維護所有參數簽名。每新增一個 service method，facade 也要同步改。2-5 人團隊的維護成本不成比例。

**替代方案 B：用 service locator pattern，MCP module 透過 `get_service("ontology")` 取得 service。** 問題：失去型別安全（`get_service` 回傳 `Any`），IDE 無法自動完成，重構時無法追蹤 caller。

**Tradeoff：** MCP module 直接 import service class = MCP module 知道 application layer 的具體 class name。如果 service class 改名，MCP module 的 import 要跟著改。但這種耦合是必要的——interface layer 本來就依賴 application layer（ADR-026 D3 已允許）。

### D2. 跨層 service 呼叫透過 repository injection，不跨層 import service

**決策：** Service 之間不直接 import 彼此。需要跨層資料時，透過 constructor injection 傳入目標層的 repository Protocol。

**現行做法（已正確，鎖定為規範）：**

```python
# TaskService 需要查 Entity — 注入 EntityRepository，不 import OntologyService
class TaskService:
    def __init__(self,
        task_repo: TaskRepository,        # Action Layer 自己的
        entity_repo: EntityRepository,    # Knowledge Layer 的 repository
        blindspot_repo: BlindspotRepository,  # Knowledge Layer 的 repository
        ...
    ): ...

# GovernanceService 需要查 Task — 注入 TaskRepository，不 import TaskService
class GovernanceService:
    def __init__(self,
        entity_repo: EntityRepository,
        task_repo: TaskRepository,        # Action Layer 的 repository
        ...
    ): ...
```

**為什麼用 repository injection 而不是 service injection：**

1. **依賴方向一致。** Repository Protocol 定義在 domain layer。service import repository Protocol 是 application → domain 的合法方向。如果 TaskService import OntologyService，就變成 application.action → application.knowledge 的跨 package 依賴——雖然 ADR-026 D3 沒明確禁止同層互相 import，但這會讓 service 之間形成 bidirectional dependency（GovernanceService 需要 TaskRepository，TaskService 又需要 OntologyService），最終 service 層變成一團互相引用的義大利麵。

2. **職責清晰。** TaskService 需要的只是「查詢 Entity 是否存在」和「取得 Entity 資料」——這些是 repository 的讀取操作，不需要 OntologyService 的業務邏輯（如 tag confidence 計算、split recommendation）。注入整個 OntologyService 會讓 TaskService 能呼叫它不該呼叫的 method（如 `upsert_entity`），違反最小權限原則。

3. **測試簡單。** Mock 一個 repository Protocol（3-5 個 method）比 mock 一個 service（20+ method）容易得多。

**禁止的模式：**

```python
# 禁止：service 直接 import 另一個 service
from zenos.application.ontology_service import OntologyService

class TaskService:
    def __init__(self, ontology_svc: OntologyService, ...): ...
```

**例外：** 若未來某個 use case 確實需要跨 service 的業務邏輯編排（不只是資料讀取），應在 application 層新建一個 orchestration service（如 `FeedbackService`），由它同時持有多個 repository，而不是讓兩個 service 互相呼叫。目前沒有這種需求。

**Tradeoff：** Repository injection 意味著跨層存取只能做 repository 暴露的操作（CRUD + 查詢），不能呼叫目標 service 的業務邏輯。如果 TaskService 未來需要在建立 task 時觸發 OntologyService 的 enrichment 邏輯，就需要提取成獨立的 orchestration service。這增加了未來的重構成本，但避免了現在就引入不必要的耦合。

### D3. tools.py helper function 歸屬分類

**決策：** 根據 helper 的職責歸類到以下位置。

#### 留在 `interface/mcp/` 的 helper（MCP-specific）

| Helper | 目標檔案 | 理由 |
|--------|----------|------|
| `_serialize`, `_convert_datetimes` | `_common.py` | 將 domain dataclass 轉成 MCP JSON 回應——序列化格式是 interface 關注點 |
| `_unified_response` | `_common.py` | MCP 統一回傳 envelope `{status, data, warnings, ...}`——回應格式是 interface 關注點 |
| `_new_id` | `_common.py` | 生成 UUID 前綴 ID——呼叫方是 MCP tool，不是 domain |
| `_parse_entity_level` | `_common.py` | 從 MCP 參數解析 entity level——參數轉換是 interface 關注點 |
| `_audit_log`, `_schedule_audit_sql_write`, `_write_audit_event`, `_log_tool_event`, `_schedule_tool_event` | `_audit.py` | MCP tool 的 audit trail——審計是 interface 層對 tool 呼叫的追蹤 |
| partner context setup、`_current_partner` | `_auth.py` | MCP partner key 驗證與 context 注入——auth middleware 是 interface 關注點 |
| `_is_entity_visible`, `_guest_allowed_entity_ids`, `_is_task_visible`, `_is_protocol_visible`, `_is_blindspot_visible`, `_check_write_visibility`, `_guest_write_rejection` | `_visibility.py` | MCP-specific 的 visibility filtering——基於 partner context 的前置過濾 |

#### 需要觀察但目前不搬的 helper

| Helper | 現狀 | 未來考量 |
|--------|------|----------|
| visibility filtering（`_visibility.py` 全部） | 目前只被 MCP tool 使用 | 若 dashboard_api 需要共用同一套 visibility 邏輯，提取到 `application/identity/` 作為 `VisibilityService`。目前 dashboard_api 有自己的 Firebase Auth middleware 和不同的 visibility 判斷方式，強行統一不自然。 |
| `_new_id` | ID 生成邏輯（UUID 前綴） | 若 domain layer 也需要 ID 生成策略，提取到 `domain/shared.py`。目前只有 interface 層在生成 ID。 |

#### 已存在於正確位置的邏輯（不需搬動）

- `workspace_context.py` 的 `resolve_active_workspace_id`、`active_partner_view`、`build_workspace_context_sync` 已在 `application/` 層——它們是 Identity Layer 的 application logic，被 MCP tool 和 dashboard_api 共用，位置正確。
- `domain/partner_access.py` 的 `describe_partner_access`、`is_guest`、`is_unassigned_partner` 已在 domain 層——它們是 Identity Layer 的 domain logic，位置正確。

**判斷原則：** 如果 helper 的輸入/輸出涉及 MCP protocol 概念（partner key、tool response envelope、audit event），它屬於 interface 層。如果 helper 的輸入/輸出只涉及 domain object 和業務規則，它應該在 application 或 domain 層。灰色地帶（如 visibility filtering）遵循 YAGNI——目前只有一個 caller 就留在 caller 附近，出現第二個 caller 時再提取。

### D4. 每一層的 public contract — 用 `__all__` 控制 export

**決策：** 每個 sub-package 的 `__init__.py` 用 `__all__` 明確列出該層的 public contract。不新建 Protocol class 來定義 contract。

**各層 export 清單：**

#### `domain/knowledge/__init__.py`

```python
__all__ = [
    # Models
    "Entity", "Relationship", "Document", "DocumentTags", "Source",
    "Protocol", "Gap", "Tags", "EntityEntry",
    # Enums
    "EntityType", "EntityStatus", "RelationshipType", "SourceType",
    "DocumentStatus", "EntryType", "EntryStatus", "Severity", "BlindspotStatus",
    # Repository Protocols
    "EntityRepository", "RelationshipRepository",
    "DocumentRepository", "ProtocolRepository", "BlindspotRepository",
]
```

#### `domain/action/__init__.py`

```python
__all__ = [
    # Models
    "Task",
    # Enums
    "TaskStatus", "TaskPriority",
    # Repository Protocol
    "TaskRepository",
]
```

#### `domain/identity/__init__.py`

```python
__all__ = [
    # Models
    "UserPrincipal", "AgentPrincipal", "AgentScope", "AccessPolicy",
    # Enums
    "Visibility", "Classification", "InheritanceMode",
    "VISIBILITY_ORDER", "CLASSIFICATION_ORDER",
]
```

#### `domain/document_platform/__init__.py`

```python
__all__ = [
    # Enums
    "DocRole", "SourceStatus", "DocStatus",
]
```

#### `application/knowledge/__init__.py`

```python
__all__ = [
    "OntologyService", "SourceService", "GovernanceService",
]
```

#### `application/action/__init__.py`

```python
__all__ = [
    "TaskService",
]
```

#### `application/identity/__init__.py`

```python
__all__ = [
    "resolve_active_workspace_id", "active_partner_view",
    "build_available_workspaces", "build_workspace_context_sync",
    "PermissionRiskService", "PolicySuggestionService",
]
```

#### `interface/mcp/__init__.py`

```python
__all__ = [
    "mcp",  # FastMCP app instance
]
# module-level singletons (not in __all__, internal to mcp package):
# ontology_service, task_service, governance_service, source_service
```

**為什麼用 `__all__` 而不是顯式 Protocol class：**

1. **現有 repository Protocol 已足夠。** `domain/repositories.py` 用 `typing.Protocol` 定義了 `EntityRepository`、`TaskRepository` 等——這是 domain 層對 infrastructure 層的 contract，已經存在且運作良好。application service 不需要再被 Protocol 化——因為 interface 層直接 import concrete class（D1），沒有「多個實作需要共用同一個介面」的場景。

2. **`__all__` 的維護成本低。** 每次新增 public symbol 時在 `__init__.py` 加一行。Protocol class 需要維護 method signature、參數型別、return type——而 service method 的簽名已經在 class 本身定義了，用 Protocol 重複一遍是純粹的 boilerplate。

3. **import-linter 已 enforce 依賴方向。** `__all__` 控制「可以 import 什麼」，import-linter 控制「可以從哪裡 import」。兩者結合就是完整的 contract enforcement。

**Tradeoff：** `__all__` 是 soft contract——Python 不會阻止 `from zenos.domain.knowledge.models import _internal_helper`。但 import-linter 加上 code review 足以 enforce。對 2-5 人團隊引入 Protocol class 的 boilerplate 成本 > soft contract 的風險。

## Implementation Impact

本 ADR 不產生新 code，而是為 ADR-026 的實作階段提供 contract 規範。

### 對 ADR-026 實作的約束

| 步驟 | 約束 |
|------|------|
| 拆 `domain/models.py` 和 `domain/repositories.py` | 每個 sub-package 的 `__init__.py` 必須按 D4 定義 `__all__` |
| 拆 `interface/tools.py` | MCP module 直接 import application service（D1），helper 按 D3 分類歸檔 |
| 寫 import-linter contract | 補充規則：`application.action` 不 import `application.knowledge`（D2 的落地） |

### 新增 import-linter 規則（補充 ADR-026 D4）

```toml
[importlinter:contract:no-cross-service-import]
name = Application services must not import each other
type = forbidden
source_modules =
    zenos.application.knowledge
    zenos.application.action
    zenos.application.identity
forbidden_modules =
    zenos.application.knowledge
    zenos.application.action
    zenos.application.identity
allow_indirect_imports = false
```

此規則 enforce D2：application sub-package 之間不互相 import。跨層資料存取必須透過 domain layer 的 repository Protocol。

**注意：** import-linter 的 forbidden contract 會禁止 source 和 forbidden 的交集——即每個 application sub-package 不能 import 其他 application sub-package，但可以 import 自己（同 package 內的 import 不受影響）。

### 對既有 code 的影響

- `TaskService` 已遵循 D2（注入 `EntityRepository` 而非 `OntologyService`），無需修改。
- `GovernanceService` 已遵循 D2（注入 `TaskRepository` 而非 `TaskService`），無需修改。
- `workspace_context.py` 已在 application 層，位置正確，無需修改。
- tools.py 的 helper 在 ADR-026 拆分時按 D3 分類即可。

## Consequences

### Positive

- **MCP module 的呼叫慣例統一。** 拆 tools.py 的 15 個開發者不會各自發明不同的 service 呼叫方式。
- **service 之間的依賴方向可 enforce。** import-linter 新規則防止 service 互相 import。
- **helper 歸屬有明確標準。** 拆分時不需要逐個討論「這個 helper 該放哪」。
- **不引入新抽象。** 零 boilerplate、零新 class、零新 pattern——只是把現有慣例文件化。

### Negative

- **`__all__` 是 soft contract。** 靠 code review enforce，不像 Protocol class 有 type checker 支持。
- **禁止 service 互相 import 可能在未來某天需要放寬。** 如果出現需要 orchestrate 多個 service 的 use case，需要新建 orchestration service 而不是放寬此規則。
- **helper 的「觀察但不搬」類別需要持續追蹤。** visibility filtering 是否該提取到 application 層，取決於 dashboard_api 的演化方向，可能在下一個 ADR 才能決定。

## Risks

### 中等風險：`__all__` 不被維護

新增 public symbol 時忘記加到 `__all__`，導致外部無法透過 `from package import symbol` 的方式使用。

**緩解：** 在 code review checklist 加入「新增 public class/function 是否已加入 `__all__`」。可考慮寫一個 CI script 驗證 `__all__` 與實際 public symbol 的一致性，但 Phase 0 靠人工 review 足夠。

### 低風險：repository injection 導致 service constructor 參數過多

目前 `TaskService` 有 7 個 constructor 參數，`OntologyService` 有 7 個。隨著功能增加，可能繼續膨脹。

**緩解：** 當 constructor 參數超過 10 個時，考慮引入 `@dataclass` 的 config object（如 `TaskServiceDeps`）打包依賴。但目前 7 個是可接受的。
