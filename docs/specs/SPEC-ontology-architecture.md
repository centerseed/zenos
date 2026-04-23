---
type: SPEC
id: SPEC-ontology-architecture
status: Approved
version: "2.0"
ontology_entity: ontology-core
created: 2026-03-21
updated: 2026-04-23
supersedes:
  - "v1 (2026-03-21 → 2026-04-09 的所有版本)"
merges:
  - SPEC-l2-entity-redefinition (合併為 §5 L2 章節)
  - SPEC-impact-chain-enhancement (合併為 §8 Relationship 章節)
  - SPEC-knowledge-graph-semantic (合併為 §3 分層模型)
supersede_adrs:
  - ADR-006-entity-project-separation
  - ADR-007-entity-architecture
  - ADR-010-entity-entries
  - ADR-022-document-bundle-architecture
  - ADR-025-zenos-core-layering (部分)
  - ADR-027-layer-contract (部分)
  - ADR-028-plan-primitive (Action Layer 獨立性)
  - ADR-041-pillar-a-semantic-retrieval (embedding 位置)
  - ADR-044-task-ownership-ssot-convergence (task product_id 語意)
  - ADR-046-document-entity-boundary (Document → Entity 收斂規則)
  - ADR-047-l1-level-ssot (L1 level 判定納入本 SPEC)
---

# SPEC: Ontology Architecture v2

**ZenOS 的單一知識圖 canonical 定義。** 所有 entity / relationship / permission / lifecycle / extension 規則以本 SPEC 為 SSOT。

---

## 1. 第一性原理（Axioms）

這 6 條是整個 ontology 的公理。任何後續 SPEC / ADR / 實作若與本節衝突，以本節為準。

1. **Entity = graph node**。Ontology 是圖，entity 是節點，relationship 是邊。不是 dataclass 視覺模型。
2. **Base Entity 只含四件事**：identity（id + name + type_label + level + parent_id）、permission、owner、timestamps。其他任何欄位都屬於 subclass 擴充。
3. **無 ad-hoc unschemed JSON blob**。禁止 `details: dict` 這類無 schema 的 catch-all 欄位（Axiom 3 違反的典型）。**允許** typed JSON column — 前提是 JSON 內結構有明確 domain type（`Tags` / `Source` / `BundleHighlight` / `list[str] acceptance_criteria` / `HandoffEvent` 等），server 反序列化時強制 schema。遇到 extra metadata 需求，要定 subclass table 或擴充既有 typed schema，不要塞 free-form dict。
4. **繼承由內而外擴充**。L1 / L2 / L3 從 BaseEntity 繼承；L3-semantic / L3-action 再從共通 mixin 分叉。每層只加自己該有的欄位。
5. **Schema 結構強制**。DDL（DB 層）拒絕錯放欄位；Python dataclass 繼承強制 type；任何「看條件塞某些 level」的動態邏輯不准存在於 schema 層。
6. **MCP tool shape 以 agent 語意最小化為第一指標**。任何「為了向後相容」增加的 tool 參數一律 reject；tool 合約由本 SPEC 系列（#23 SPEC-mcp-tool-contract）規範。

---

## 2. 範圍

**本 SPEC 定義**：
- BaseEntity / Relationship 的 canonical shape
- L1 / L2 / L3-semantic / L3-action 的分層與各自 subclass schema
- Entity 生命週期狀態機
- 權限模型與 visibility 規則（與 SPEC-identity-and-access 對齊）
- Relationship 語意與 impacts 傳播規則
- Embedding 如何 sidecar 掛載

**本 SPEC 不定義**：
- 治理抽象六維結構（在 SPEC-governance-framework）
- 具體文件 / 任務 / 權限的治理流程（各 subclass SPEC：SPEC-doc-governance / SPEC-task-governance / SPEC-identity-and-access）
- MCP tool 的 I/O 格式（在 SPEC-mcp-tool-contract）
- 實作用的 DDL migration 順序（在 PLAN-ontology-grand-refactor）

---

## 3. 分層模型

整個 ZenOS 是 **單一知識圖**。任何實體都是圖上的節點，包括任務 / 計畫 / 里程碑（從舊架構的 Action Layer 併入）。

```
BaseEntity                                             level = 1 / 2 / 3
  ├── L1Entity（共享根）                                  level=1, parent_id=null
  │
  ├── L2Entity（知識節點）                                 level=2, parent 指向 L1
  │     + SemanticMixin（summary, tags, confirmed_by_user, last_reviewed_at）
  │     + L2 專有：consolidation_mode, 三問 metadata, impacts_gate_passed_at
  │
  ├── L3Semantic（語意知識物件）                           level=3
  │     │  + SemanticMixin
  │     ├── L3DocumentEntity（文件語意代理）
  │     ├── L3RoleEntity（角色）
  │     └── L3ProjectEntity（工作容器）
  │
  └── L3Action（工作項目，舊 Action Layer 併入）            level=3
        + L3TaskBaseEntity（共用 action 欄位）
        ├── L3MilestoneEntity（里程碑 — Goal 合併於此）
        ├── L3PlanEntity（任務群組）
        ├── L3TaskEntity（可執行工作）
        └── L3SubtaskEntity（agent 派工單位）
```

- **L1** = 共享邊界（可整棵子樹分享給 guest）
- **L2** = 跨角色知識節點（三問 + impacts gate 確保品質）
- **L3-Semantic** = 具體語意物件（文件 / 角色 / 專案容器）
- **L3-Action** = 可執行工作（任務系列）

**關鍵設計決策**：
- L1 pure base（不需要獨立 L1 subclass table，DB 用 `level=1` 區分即可）
- L2 與 L3-Semantic 共用 SemanticMixin，但 lifecycle 不同（L2 有 impacts gate，L3-Semantic 有 supersede / archive 流程）
- L3-Action 自己的 L3TaskBaseEntity 不帶 SemanticMixin（任務不需要 tags / confirmed_by_user）

---

## 4. BaseEntity Schema

### Python
```python
@dataclass
class BaseEntity:
    # Identity
    id: str
    name: str
    type_label: str          # 顯示 label（product / module / document / milestone / task / ...），不做業務分支
    level: int               # 1 / 2 / 3
    parent_id: str | None    # 圖的樹結構；L1 必為 None

    # Lifecycle
    status: EntityStatus     # 見 §9
    created_at: datetime
    updated_at: datetime

    # Permissions（與 SPEC-identity-and-access 對齊）
    visibility: Visibility                 # public / restricted / confidential
    visible_to_roles: list[str]
    visible_to_members: list[str]
    visible_to_departments: list[str]

    # Ownership
    owner: str | None
```

### DB — `entities_base` 表
```sql
CREATE TABLE entities_base (
    id             text PRIMARY KEY,
    partner_id     text NOT NULL REFERENCES partners(id),
    name           text NOT NULL,
    type_label     text NOT NULL,
    level          integer NOT NULL CHECK (level IN (1, 2, 3)),
    parent_id      text REFERENCES entities_base(id) ON DELETE SET NULL,
    status         text NOT NULL,                -- see §9
    visibility     text NOT NULL DEFAULT 'public',
    visible_to_roles        text[] NOT NULL DEFAULT '{}',
    visible_to_members      text[] NOT NULL DEFAULT '{}',
    visible_to_departments  text[] NOT NULL DEFAULT '{}',
    owner          text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),

    UNIQUE (partner_id, id),
    CHECK (level != 1 OR parent_id IS NULL)      -- L1 必無 parent
);
```

**禁用欄位**（結構強制）：
- 無 `details jsonb`（Axiom 3）
- 無 `tags_json`（進 SemanticMixin）
- 無 `summary`（進 SemanticMixin）
- 無 `confirmed_by_user`（進 SemanticMixin）
- 無 type-specific 欄位（由 subclass table 各自擁有）

### L1 判定
```
is_l1(entity) ⟺ entity.level == 1 AND entity.parent_id IS NULL
```
此判定放在 `zenos.domain.knowledge.collaboration_roots.is_collaboration_root_entity`，是 L1 的 SSOT。

---

## 5. SemanticMixin（L2 + L3-Semantic 共用）

```python
@dataclass
class SemanticMixin:
    summary: str
    tags: Tags                    # {what: list[str], why: str, how: str, who: list[str]}
    confirmed_by_user: bool       # draft → confirmed 閘
    last_reviewed_at: datetime | None
```

DB 層：每個 L2 / L3-Semantic subclass table 都有這四欄位（重複 acceptable，因為 sidecar JOIN 粒度自然對齊）。

---

## 6. L1 Entity（共享根）

**用途**：作為知識圖的根節點，代表一個「可分享單位」（a shareable root），L2 / L3 的子樹都掛在底下。

**典型 label**：
- `product`（自己的產品）
- `company`（CRM 客戶公司）
- `person`（CRM 聯絡人）
- `deal`（CRM 交易）
- 未來新 L1 label 加進 `DEFAULT_TYPE_LEVELS` 即可

**Schema**：BaseEntity，無其他欄位。DB 層 level=1 的 row 就是 L1，不開獨立 subclass table。

**規則**：
- 必 `level=1 AND parent_id=null`
- task/plan/milestone 等 L3-Action 透過 `parent_id` 指向 L1（歸屬）或 L2/L3 內嵌結構（排序）
- L1 的 sharing 邊界：對 guest 分享 = guest 獲得整棵 L1 子樹讀權限（結合 visibility 規則）

---

## 7. L2 Entity（知識節點）

**用途**：跨角色公司共識概念。改了會影響多個下游。

**Schema**：
```python
@dataclass
class L2Entity(BaseEntity, SemanticMixin):
    consolidation_mode: ConsolidationMode       # global | incremental
    q1_cross_role: bool | None                  # 三問 metadata
    q2_downstream_impact: bool | None
    q3_company_consensus: bool | None
    impacts_gate_passed_at: datetime | None     # 三問 + impacts 皆過的時間戳
```

```sql
CREATE TABLE entity_l2 (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    summary text NOT NULL,
    tags_json jsonb NOT NULL DEFAULT '{}',
    confirmed_by_user boolean NOT NULL DEFAULT false,
    last_reviewed_at timestamptz,
    consolidation_mode text NOT NULL DEFAULT 'incremental' CHECK (consolidation_mode IN ('global', 'incremental')),
    q1_cross_role boolean,
    q2_downstream_impact boolean,
    q3_company_consensus boolean,
    impacts_gate_passed_at timestamptz
);
```

### 7.1 三問 + impacts gate

L2 新建一律 `status='active'` + `confirmed_by_user=false`（即 §7.2 的 Draft 態）。升為 Confirmed（`confirmed_by_user=true`）必經 `confirm` 流程，server 強制三條：

1. 三問全過（q1/q2/q3 為 `true`）
2. ≥1 條 `impacts` relationship 指向其他 entity，且描述具體（含 `→` 或等效語意）
3. summary 跨角色可讀（LLM 評分 ≥ threshold；軟規則）

Violation → reject；`force=true` 走過需要 `manual_override_reason` 並標記。

### 7.2 L2 Lifecycle

L2 有 **兩個正交 state**：

1. `confirmed_by_user: bool`（gate 維度）— 是否通過三問 + impacts gate
2. `BaseEntity.status: EntityStatus`（業務 lifecycle 維度）— `active` 或 `stale`

組合語意：

| confirmed_by_user | status | 意義 |
|---|---|---|
| `false` | `active` | **Draft** 態（新建預設）|
| `true` | `active` | **Confirmed** 態（穩定運作）|
| `true` | `stale` | **Stale** 態（impacts 斷鏈 / 久未 review，待 re-confirm 或降級）|

```
(false, active)  ─── 三問+impacts 過 ──► (true, active)
                                              │
                                              ▼（impacts 斷鏈 / review 逾期）
(true, active) ◄── re-review confirm ─── (true, stale)
```

- Draft 是唯一合法初始態；server 強制新建 L2 時 `confirmed_by_user=false, status='active'`
- **L2 沒有 `archived` 終態**。要收掉 L2 只有三條路：降為 `sources` 掛在別的 entity / 降為 `L3-Document` / 物理刪除（admin script，非 MCP）
- `status` 的 `paused / completed / planned / draft / current / conflict / archived` 不適用 L2

### 7.3 Entity Entries（L2 的結構化記憶）

L2 可掛載 **EntityEntry**（時間軸知識條目），記錄 decision / insight / limitation / change / context。

- **Entry 專屬於 L2**：L3 entity 不掛 entry（有其他機制，例如 task.result / document.content）
- 飽和機制：單一 L2 active entries ≥ 20 觸發 consolidation proposal
- Schema / 治理：獨立 `entity_entries` 表，規範在 **SPEC-entry-consolidation-skill** + **SPEC-entry-distillation-quality**

---

## 8. L3-Semantic Entities

### 8.1 L3DocumentEntity（文件語意代理）

舊 `Document` collection 於 ADR-046 起併入 entity。本 SPEC 固化為 L3 subclass，`documents` 表已於 ADR-047 後繼 migration 刪除。

```python
@dataclass
class L3DocumentEntity(BaseEntity, SemanticMixin):
    sources: list[Source]                       # primary file + additional refs
    doc_role: DocRole                           # single | index
    bundle_highlights: list[BundleHighlight]
    highlights_updated_at: datetime | None
    change_summary: str | None
    summary_updated_at: datetime | None
```

```sql
CREATE TABLE entity_l3_document (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    summary text NOT NULL,
    tags_json jsonb NOT NULL DEFAULT '{}',
    confirmed_by_user boolean NOT NULL DEFAULT false,
    last_reviewed_at timestamptz,
    sources_json jsonb NOT NULL DEFAULT '[]',
    doc_role text NOT NULL DEFAULT 'single' CHECK (doc_role IN ('single', 'index')),
    bundle_highlights_json jsonb NOT NULL DEFAULT '[]',
    highlights_updated_at timestamptz,
    change_summary text,
    summary_updated_at timestamptz,
    CHECK (doc_role = 'single' OR bundle_highlights_json != '[]')   -- index 必須有 highlights
);
```

**Lifecycle**（合法 status：`draft / current / stale / archived / conflict`，見 §11.2）：
```
draft → current ↔ stale → archived
          │         ▲        ▲
          ├─ conflict ─┘      │
          └───── supersede ───┘
```

治理規則：`SPEC-doc-governance §6`。

### 8.2 L3RoleEntity（角色）

```python
@dataclass
class L3RoleEntity(BaseEntity, SemanticMixin):
    pass   # role 目前不加欄位；language/title 放在 name，責任描述在 summary
```

```sql
CREATE TABLE entity_l3_role (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    summary text NOT NULL,
    tags_json jsonb NOT NULL DEFAULT '{}',
    confirmed_by_user boolean NOT NULL DEFAULT false,
    last_reviewed_at timestamptz
);
```

### 8.3 L3ProjectEntity（工作容器）

```python
@dataclass
class L3ProjectEntity(BaseEntity, SemanticMixin):
    project_kind: str | None          # initiative | campaign | engagement | custom
    started_at: datetime | None
    ended_at: datetime | None
```

```sql
CREATE TABLE entity_l3_project (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    summary text NOT NULL,
    tags_json jsonb NOT NULL DEFAULT '{}',
    confirmed_by_user boolean NOT NULL DEFAULT false,
    last_reviewed_at timestamptz,
    project_kind text,
    started_at timestamptz,
    ended_at timestamptz
);
```

---

## 9. L3-Action Entities（舊 Action Layer 併入）

> **Post-MTI 目標態（Wave 9 migration 完成後）**：所有任務類物件都是 entity，透過 `entities_base` + L3-Action subclass 表（`entity_l3_milestone / plan / task / subtask`）表達；`parent_id`（圖的邊）統一承載歸屬語意；`relationships` 表取代 `task_entities` junction。
>
> **當前 runtime 狀態**（2026-04-23）：
> - `zenos.tasks` / `zenos.plans` 仍為獨立 table（見 `src/zenos/infrastructure/action/sql_task_repo.py` / `sql_plan_repo.py`）
> - Ownership SSOT 為 `product_id`（**ADR-047 D3 canonical**；`governance_rules.py:938 OWNERSHIP_SSOT_PRODUCT_ID`）——新 caller 必傳 `product_id`，`project` 僅為 legacy fallback hint，`project_id` 參數 reject
> - Subtask 仍以 `parent_task_id`（自指）區分，同表 row
> - 本節（§9）描述的 subclass table DDL 與 `parent_id` 統一樹**尚未落地**；落地時程見 Wave 9 migration PLAN
>
> **治理 SSOT 雙視角**：
> - **Canonical schema（未來）**：本節 §9 的 subclass table + `parent_id` 樹
> - **Canonical runtime（今日）**：`SPEC-task-governance §1.1 歸屬語意` + `governance_rules.py §ownership`（`product_id` + `plan_id` + `parent_task_id` 四欄）
> - 兩者在 Wave 9 migration 時由一份 schema migration PLAN 收斂

下列 §9.1-§9.6 的 Python dataclass / DDL / CHECK 為 post-MTI 目標。caller 今日仍以 `SPEC-task-governance` 為 runtime contract。

### 9.1 L3TaskBaseEntity（abstract 基底）

```python
@dataclass
class L3TaskBaseEntity(BaseEntity):
    # 注意：L3-Action 不帶 SemanticMixin — 任務不需要 tags / confirmed_by_user
    description: str
    task_status: TaskStatus                     # todo | in_progress | review | done | cancelled
    assignee: str | None
    dispatcher: str                             # agent:xxx | human[:id]
    acceptance_criteria: list[str]
    priority: Priority
    result: str | None
    handoff_events: list[HandoffEvent]          # 獨立 append-only log（見 §9.6）
```

**規則**：
- Task 系列的 `status`（BaseEntity 的 lifecycle enum）設為 `active`；業務語意的 status 在 `task_status`
- `parent_id` 指向上級（Milestone / Plan / Task）或 L1/L2（根歸屬）
- `linked_entities` 透過 `relationships` 表（知識關聯），禁止自 L1 root

### 9.2 L3MilestoneEntity（里程碑；Goal 合併於此）

舊的「goal entity」（抽象目標）已於本 SPEC supersede，合併進 Milestone。所有帶目標語意的 L3 物件都是 Milestone。

```python
@dataclass
class L3MilestoneEntity(L3TaskBaseEntity):
    target_date: date | None
    completion_criteria: str | None             # 里程碑達成判定
```

```sql
CREATE TABLE entity_l3_milestone (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    description text NOT NULL,
    task_status text NOT NULL CHECK (task_status IN ('planned','active','completed','cancelled')),
    assignee text,
    dispatcher text NOT NULL,
    acceptance_criteria_json jsonb NOT NULL DEFAULT '[]',
    priority text NOT NULL DEFAULT 'medium' CHECK (priority IN ('critical','high','medium','low')),
    result text,
    target_date date,
    completion_criteria text
);
```

### 9.3 L3PlanEntity（任務群組）

```python
@dataclass
class L3PlanEntity(L3TaskBaseEntity):
    goal_statement: str
    entry_criteria: str
    exit_criteria: str
```

```sql
CREATE TABLE entity_l3_plan (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    description text NOT NULL,
    task_status text NOT NULL CHECK (task_status IN ('draft','active','completed','cancelled')),
    assignee text,
    dispatcher text NOT NULL,
    acceptance_criteria_json jsonb NOT NULL DEFAULT '[]',
    priority text NOT NULL DEFAULT 'medium',
    result text,
    goal_statement text NOT NULL,
    entry_criteria text NOT NULL,
    exit_criteria text NOT NULL
);
```

### 9.4 L3TaskEntity（可執行工作）

```python
@dataclass
class L3TaskEntity(L3TaskBaseEntity):
    plan_order: int | None          # 在 parent plan 內的順序
    depends_on: list[str]           # 阻塞此 task 的其他 task ids
    blocked_reason: str | None
    due_date: date | None
```

```sql
CREATE TABLE entity_l3_task (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    description text NOT NULL,
    task_status text NOT NULL CHECK (task_status IN ('todo','in_progress','review','done','cancelled')),
    assignee text,
    dispatcher text NOT NULL,
    acceptance_criteria_json jsonb NOT NULL DEFAULT '[]',
    priority text NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    result text,
    plan_order integer,
    depends_on_json jsonb NOT NULL DEFAULT '[]',
    blocked_reason text,
    due_date date,
    CHECK (task_status != 'review' OR result IS NOT NULL)   -- review 必附 result
);
```

### 9.5 L3SubtaskEntity（agent 派工單位）

Subtask 是 Task 的 subclass，語意為 **agent 內部派工用**（非用戶常用）。

```python
@dataclass
class L3SubtaskEntity(L3TaskEntity):
    dispatched_by_agent: str                    # 派工的 agent id
    auto_created: bool = True                   # 多為 agent 自動拆分
```

```sql
CREATE TABLE entity_l3_subtask (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    description text NOT NULL,
    task_status text NOT NULL,
    assignee text,
    dispatcher text NOT NULL,
    acceptance_criteria_json jsonb NOT NULL DEFAULT '[]',
    priority text NOT NULL DEFAULT 'medium',
    result text,
    plan_order integer,
    depends_on_json jsonb NOT NULL DEFAULT '[]',
    blocked_reason text,
    due_date date,
    dispatched_by_agent text NOT NULL,
    auto_created boolean NOT NULL DEFAULT true
);
```

**Subtask vs Task 的語意區別**：
- Task：人類可見的工作項目
- Subtask：agent 為了完成一個 Task，自動拆出的執行子步驟（例如 Developer agent 拆出「寫 X 函式」「補 Y test」）
- Parent 關係：Subtask 的 `parent_id` 必指向一個 L3TaskEntity

### 9.6 HandoffEvent（append-only log）

任務的派工歷史獨立 table（不是 JSON 欄位）：

```sql
CREATE TABLE task_handoff_events (
    id bigserial PRIMARY KEY,
    partner_id text NOT NULL REFERENCES partners(id),
    task_entity_id text NOT NULL REFERENCES entities_base(id) ON DELETE CASCADE,
    from_dispatcher text,
    to_dispatcher text NOT NULL,
    reason text NOT NULL,
    notes text,
    output_ref text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_handoff_events_task ON task_handoff_events(task_entity_id, created_at);
```

append-only：沒有 UPDATE / DELETE API。MCP `write` 對此 collection 僅支援 `create`。

### 9.7 Task 治理

具體治理規則（建票標準、驗收、反饋閉環）在 **SPEC-task-governance**。本 SPEC 只定 schema。

---

## 10. Relationship（圖的邊）

Relationship 是唯一的邊表，**所有 linked_entities 關聯都走這裡**。舊的 `task_entities` / `document_entities` junction 已廢止。

```python
@dataclass
class Relationship:
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    description: str
    confirmed_by_user: bool
    verb: str | None            # 語意動詞補充（例如 "governs" / "consumes"）
    created_at: datetime
    updated_at: datetime
```

```sql
CREATE TABLE relationships (
    id text PRIMARY KEY,
    partner_id text NOT NULL REFERENCES partners(id),
    source_entity_id text NOT NULL REFERENCES entities_base(id) ON DELETE CASCADE,
    target_entity_id text NOT NULL REFERENCES entities_base(id) ON DELETE CASCADE,
    type text NOT NULL CHECK (type IN ('depends_on','serves','owned_by','part_of','blocks','related_to','impacts','enables')),
    description text NOT NULL,
    confirmed_by_user boolean NOT NULL DEFAULT false,
    verb text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (partner_id, source_entity_id, target_entity_id, type),
    CHECK (source_entity_id != target_entity_id)
);
```

### 10.1 RelationshipType 語意

| Type | 語意 | 典型用例 |
|------|------|---------|
| `depends_on` | A 需要 B 先存在 | L3-Task A depends_on L3-Task B |
| `serves` | A 為 B 服務 | L2 module serves L1 product |
| `owned_by` | A 由 B 擁有 | L3-Project owned_by L3-Role |
| `part_of` | A 是 B 的一部分 | L2 governance concept part_of L1 product |
| `blocks` | A 阻塞 B | L3-Task blocks L3-Task |
| `related_to` | 弱關聯 | L3-Document related_to L2 |
| `impacts` | A 變更需檢查 B | L2 modulesimpacts L2 module |
| `enables` | A 的存在讓 B 成為可能 | L2 foundation enables L2 feature |

### 10.2 impacts 路徑規範

- **L2 的 impacts gate** 強制 ≥1 條具體 `impacts` relationship
- 「具體」定義：description 需含傳播語意，例：`A 改變閾值 → B 的計算要跟著更新`
- `impacts` 不限 L2 間，也可跨 L3（例：L3-Document impacts L3-Task）

### 10.3 linked_entities 禁止清單

`relationships.source_entity_id` 為任務系列（L3-Action）時，`target_entity_id` 不可指向：
- 自己所屬的 L1（歸屬已由 parent_id 表達，重複會被 server strip）
- 自己（`CHECK source != target`）

### 10.4 圖遍歷（Impact Chain）

Impact chain 是從 relationship 邊沿 BFS 產生的結構化推理。canonical 由 `compute_impact_chain` 實作，MCP `get(collection="entities", include=["impact_chain"])` 回傳。

**雙向能力**：

| 欄位 | 方向 | 語意 |
|------|------|------|
| `impact_chain` | forward（outgoing edges）| 從此節點出發，「我改了會影響誰」|
| `reverse_impact_chain` | backward（incoming edges）| 「誰改了會影響我」|

**硬規則**：
- 最大深度 **5 跳**（server hardcoded；防大圖效能與廣播風暴）；超過回傳 `truncated=true`
- 遍歷**必防循環**（訪問集合追蹤）；循環節點不重複展開
- 兩個欄位作為 **additive** 補入 get response；現有 caller 未帶 include 時行為向後相容
- `top_k_per_hop` 與 intent ranking 由 `SPEC-semantic-retrieval` 定義

**節點對遍歷相對位置的標註**：
- 每筆 chain item 包含 `edge.type`、`edge.description`、`hop`、是否 truncated
- consumer 應以結構化 edge chain 展開 UI / context，不得只讀 neighbor list

### 10.5 圖拓撲分析的保留邊界

- **孤立節點** / **槓桿點（high out-degree）** / **循環依賴** / **目標斷鏈** 等拓撲偵測，屬 governance analyze 範疇（`SPEC-governance-feedback-loop` + `SPEC-governance-observability`），不進 core schema
- Relationship 的 `verb` 欄位保留在 DDL 避免 migration risk，但已於 2026-04-18 停止做為 governance 評分依據（填寫率 8.8%，`description` 已承擔語意）。新 caller 可留空。

---

## 11. Entity Lifecycle

### 11.1 Status enum（統一）

```python
class EntityStatus(str, Enum):
    ACTIVE    = "active"       # 預設穩定狀態
    PAUSED    = "paused"       # 暫停但可能回來
    COMPLETED = "completed"    # 完成（專案 / 里程碑等）
    PLANNED   = "planned"      # 規劃中但尚未啟動
    ARCHIVED  = "archived"     # 收掉但保留歷史
    # 以下僅對特定 subclass 有效：
    CURRENT   = "current"      # L3-document only
    STALE     = "stale"        # L2 / L3-document
    DRAFT     = "draft"        # L2 only（confirm gate）
    CONFLICT  = "conflict"     # L3-document only
```

**舊 `DocumentStatus` 已廢止**；document status 併入 `EntityStatus`。

### 11.2 每 subclass 合法 status

| Subclass | 合法 status | 狀態機 |
|----------|-----------|--------|
| Subclass | 業務 status 欄位 | 合法值 | 狀態機 |
|----------|-----------------|-------|--------|
| L1 | `BaseEntity.status` | `active / paused / archived` | active ↔ paused → archived |
| L2 | `BaseEntity.status` + `confirmed_by_user` 二維（見 §7.2） | status: `active / stale`；confirmed: bool | (false,active) draft → (true,active) confirmed → (true,stale) → (true,active) |
| L3-Document | `BaseEntity.status` | `draft / current / stale / archived / conflict` | draft → current → stale → archived（supersede 可 fork） |
| L3-Role | `BaseEntity.status` | `active / archived` | active → archived |
| L3-Project | `BaseEntity.status` | `planned / active / paused / completed / archived` | planned → active → paused / completed → archived |
| L3-Milestone | `task_status`（BaseEntity.status 恆 active） | `planned / active / completed / cancelled` | planned → active → completed / cancelled |
| L3-Plan | `task_status`（BaseEntity.status 恆 active） | `draft / active / completed / cancelled` | draft → active → completed / cancelled |
| L3-Task | `task_status`（BaseEntity.status 恆 active） | `todo / in_progress / review / done / cancelled` | todo → in_progress → review → done / cancelled |
| L3-Subtask | 同 Task | 同 Task | 同 Task |

> **規則**：L3-Action 系列（Milestone / Plan / Task / Subtask）的 `BaseEntity.status` **恆為 `active`**。業務 lifecycle 由專屬 `task_status` 表達。Base status 用於 entity graph 存在與否（active / archived）。

---

## 12. Embedding（sidecar）

embedding metadata 不放 BaseEntity，**獨立 sidecar table**。任何 L2 / L3-Semantic entity 都可選擇性 embed（L1 / L3-Action 通常不 embed）。

```sql
CREATE TABLE entity_embeddings (
    entity_id text PRIMARY KEY REFERENCES entities_base(id) ON DELETE CASCADE,
    summary_embedding vector(768),
    embedded_summary_hash text,
    embedding_model text,
    embedded_at timestamptz
);
CREATE INDEX idx_entity_embeddings_hnsw ON entity_embeddings USING hnsw (summary_embedding vector_cosine_ops);
```

**設計原因**：
- 不是每個 entity 都 embed（Axiom 2：base 不扛）
- Embedding 更新頻率 ≠ entity 更新頻率
- pgvector HNSW index 的 VACUUM 成本隔離

---

## 13. 權限模型（對齊 SPEC-identity-and-access）

- `visibility`：`public`（任何有權限的 partner 都能看）/ `restricted`（需 explicit grant）/ `confidential`（owner + 明確授權）
- `visible_to_roles / members / departments`：白名單（與 visibility 同時 evaluate）
- **L1 的 sharing 語意**：對 guest 分享 L1 entity，guest 獲得整棵 L1 子樹的讀權限（受每個節點自己的 visibility 限制）
- 完整規則在 SPEC-identity-and-access

---

## 14. Governance 對照（引用 SPEC-governance-framework）

每個 subclass 都依 SPEC-governance-framework 六維結構定治理：

| Subclass | Quality Gate | Lifecycle | Relation | Feedback | 衝突仲裁 |
|----------|-------------|-----------|----------|---------|---------|
| L1 | — (base) | §11.2 | 無 parent | — | 本 SPEC |
| L2 | 三問+impacts (§7.1) | §11.2 | ≥1 impacts | Entry saturation | SPEC-l2 ⊂ 本 SPEC |
| L3-Document | Frontmatter + source | §11.2 | parent_id | supersede chain | SPEC-doc-governance |
| L3-Role | — | §11.2 | 無 | — | 本 SPEC |
| L3-Project | — | §11.2 | parent_id | 完成通知 | 本 SPEC |
| L3-Milestone | completion_criteria | §11.2 | parent_id / depends_on | 完成通知 | SPEC-task-governance |
| L3-Plan | entry/exit criteria | §11.2 | children tasks | 完成彙總 | SPEC-task-governance |
| L3-Task | title + AC + acceptance | §11.2 (task_status) | parent_id | knowledge writeback | SPEC-task-governance |
| L3-Subtask | 同 Task | 同 Task | parent task | 同 Task | SPEC-task-governance |

---

## 15. 禁止模式（Axiom 5 的具體化）

以下寫入一律被 DDL 或 service 層 reject：

1. `level=1 AND parent_id != NULL`
2. BaseEntity row 含非 schema 欄位（DB 本身阻擋）
3. L1 row 試圖寫入 `entity_l2` / `entity_l3_*` 子表
4. Relationship.source / target 指向不存在 entity_id（FK 保證）
5. L2 entity 首次寫入 `status != 'draft'`（service 強制）
6. L2 升 `active` 未過三問 + impacts gate（service 強制）
7. L3-Task.status='review' 無 result（CHECK constraint）
8. MCP tool 傳入 `project_id` / `details` / 任何不在本 SPEC 列出的欄位（全面 reject）

---

## 16. Migration 策略

**現在是 ZenOS 在 pre-customer 階段唯一的 destructive 窗口**。執行策略：

1. **Phase A — Backup**：dump 現行 `zenos.entities / tasks / plans / documents / relationships / entity_entries / task_entities / blindspot_entities` 成 JSON + snapshot_id
2. **Phase B — Drop**：drop 舊表（含 ADR-046 尚未 drop 的 documents table、舊 task_entities / zenos.tasks / zenos.plans）
3. **Phase C — Create**：依本 SPEC DDL create new tables（entities_base + 5 subclass + relationships + embedding sidecar + handoff_events）
4. **Phase D — Restore**：依下表 mapping 把 backup JSON 分派到 new tables

| 舊 row | 新表 |
|--------|------|
| `entities WHERE type='product' AND parent_id IS NULL` | `entities_base` (level=1) |
| `entities WHERE type='company' / 'person' / 'deal' AND parent_id IS NULL` | `entities_base` (level=1) |
| `entities WHERE type='module'` | `entities_base` + `entity_l2` |
| `entities WHERE type='document'` | `entities_base` + `entity_l3_document` |
| `entities WHERE type='goal'` | `entities_base` + `entity_l3_milestone`（**Goal 合併**）|
| `entities WHERE type='role'` | `entities_base` + `entity_l3_role` |
| `entities WHERE type='project'` | `entities_base` + `entity_l3_project` |
| `tasks` rows | `entities_base` (level=3, type_label='task') + `entity_l3_task`；`parent_id = (original product_id 或 plan_id)` |
| `plans` rows | `entities_base` (level=3, type_label='plan') + `entity_l3_plan` |
| `task_entities` rows | `relationships` (type='related_to' 或繼承自原 linked_entities 的語意) |
| `document_entities` rows | `relationships` (type='related_to') |
| `entity_entries` | 不動（仍掛 L2 entity） |

5. **Phase E — Validate**：
   - 每個舊 row 都有對應新 row
   - FK 完整
   - CHECK 全通過
   - 試跑 MCP search / get / write 全 smoke

具體 DDL / SQL / rollback snapshot 在 **PLAN-ontology-grand-refactor**（master PLAN）。

---

## 17. 明確不包含

- 不定義 `EntityType` enum 的 full list（那是 label 清單，屬配置，不是 canonical spec 範圍）
- 不定義 MCP `write(entity)` 的 I/O schema 細節（在 SPEC-mcp-tool-contract）
- 不定義 CRM bridge（L1 CRM label + `zenos.companies` sidecar）的實作細節（在 SPEC-crm-core）
- 不定義 Dashboard UI 對 subclass 的渲染（在 SPEC-dashboard-*）
- 不定義 governance LLM 的 prompt（屬 internal，見 SPEC-governance-framework 的 Agent-Powered Internal 分類）

---

## 18. 完成定義

1. 本 SPEC 列入 `REF-active-spec-surface`
2. `SPEC-l2-entity-redefinition` / `SPEC-impact-chain-enhancement` / `SPEC-knowledge-graph-semantic` 三份合併後刪除或加 supersede marker 指向本 SPEC
3. 上節列出的 11 份 ADR 全數加 `superseded_by: SPEC-ontology-architecture v2` 標記
4. ADR-048-grand-ontology-refactor 建立，引用本 SPEC 為 canonical
5. PLAN-ontology-grand-refactor 建立，含 Phase A-E migration + Wave 化實作順序
6. 各 subclass SPEC（task-governance / doc-governance / identity-and-access / governance-framework / mcp-tool-contract）依本 SPEC 改寫完成

---

## 19. 相關文件

| 類型 | 文件 | 關係 |
|------|------|------|
| 索引 | `docs/refactor-index.md` | 整體 refactor 範圍與執行順序 |
| SPEC | SPEC-task-governance | L3-Action subclass 治理細則 |
| SPEC | SPEC-doc-governance | L3-Document subclass 治理細則 |
| SPEC | SPEC-identity-and-access | 權限模型細則 |
| SPEC | SPEC-governance-framework | 六維治理抽象 |
| SPEC | SPEC-mcp-tool-contract | MCP tool shape（Axiom 6 落地）|
| SPEC | SPEC-entry-consolidation-skill | L2 entry 飽和管理 |
| SPEC | SPEC-semantic-retrieval | embedding sidecar 使用 |
| SPEC | SPEC-document-delivery-layer | L3-Document delivery sidecar（revisions / share_tokens）|
| ADR | ADR-048-grand-ontology-refactor | 本次 refactor 的總決策文件（引用本 SPEC）|
| PLAN | PLAN-ontology-grand-refactor | 執行 wave + migration 步驟 |
