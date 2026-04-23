---
type: SPEC
id: SPEC-zenos-core
status: Under Review
ontology_entity: zenos-core
created: 2026-04-09
updated: 2026-04-23
depends_on: SPEC-ontology-architecture v2
---

# Feature Spec: ZenOS Core

> **2026-04-23 update**：Action Layer（task / plan）已於 `SPEC-ontology-architecture v2` 併入 Knowledge Layer 成為 L3-Action subclass。本 SPEC 的「核心邊界」列表隨之簡化。

## 1. 目的

本 spec 定義 ZenOS 的平台核心邊界，作為其他 spec 的上位約束。

ZenOS 不是單一 application，而是提供以下共用能力的 platform layer：

- 單一知識圖（含 task/plan/milestone/subtask 作為 L3-Action subclass）與治理 runtime
- document platform contract（L3-Document subclass / source bundle / source rollout）
- identity / workspace / access runtime
- agent / MCP runtime

本 spec 的目的，是把 `ZenOS Core` 與 `Application Layer` 明確切開，避免 CRM、權限管理介面、Zentropy 等應用層能力反向污染 core model。

## 2. 核心原則

1. ZenOS Core 只定義跨 application 共用、需要 server-side 治理與授權保證的能力。
2. ZenOS Core 必須提供穩定的資料 contract，讓多個 application 能共享同一套 knowledge / action / access runtime。
3. Application Layer 可以在 Core 之上定義更細的工作流與 UI，但不得改寫 Core 的基本語意。
4. 只有需要跨 application 共用、需要 server-side 驗收或授權、或需要知識回饋閉環的概念，才可升格進 Core。

## 3. 分層模型

### 3.1 ZenOS Core

ZenOS Core 由五個子層組成：

#### A. Knowledge Layer

職責：

- 定義 L1-L3 entity 模型（canonical：`SPEC-ontology-architecture v2`）
- 定義 relationship、entries、L3-Document proxy、source governance
- 定義 L3-Action subclass（task / plan / milestone / subtask）作為 action runtime
- 提供 knowledge graph、document bundle、action runtime

包含：

- 可被獨立授權與分享的 L1 主軸（例如 `product`、`company`、`person`、`deal`）
- L2 持久知識節點（三問 + impacts gate）
- **L3-Semantic**：document / role / project 等 entity
- **L3-Action**：task / plan / milestone / subtask（原 Action Layer 併入，詳見 `SPEC-task-governance`）
- entity entries（掛載於 L2）
- document bundle（`doc_role` single/index、`bundle_highlights`）

> Goal entity 已於 2026-04-23 合併進 L3-Milestone（`SPEC-ontology-architecture v2 §9.2`）。

#### B. ~~Action Layer~~（已合併進 Knowledge Layer，2026-04-23）

~~承接 knowledge layer 輸出的可執行行動；task / plan orchestration primitive。~~

**本子層已於 `SPEC-ontology-architecture v2` 廢止為獨立子層。** Task / Plan / Milestone / Subtask 全部成為 Knowledge Layer 的 L3-Action subclass，共用 Entity graph、relationships、permission、parent_id 歸屬。治理細則見 `SPEC-task-governance`（改寫中）。

本子層的保留字母 `B` 僅為向後相容下游 spec 引用（`§3.1.C / D / E` 的識別不變）。

#### C. Identity & Access Layer

職責：

- 提供 user / workspace / active workspace context
- 提供 visibility 與授權裁切
- 提供 application surface 的共享邊界
- 提供 auth federation contract，讓外部 app 的 end-user 映射到 ZenOS principal

包含：

- identity（含 identity_link 外部身份映射）
- workspace
- workspace role
- visibility
- subtree authorization
- auth federation（trusted app registry、delegated credential；詳見 SPEC-zenos-auth-federation）

#### D. Agent Runtime Layer

職責：

- 提供 MCP tools 與 workspace-aware context delivery
- 提供 capture / sync / analyze / confirm 等治理入口
- 提供 source read / write / task mutation 的 agent contract

#### E. Document Platform Contract

職責：

- 定義 doc entity 的 `single` / `index` 語意
- 定義 per-source schema 與 status
- 定義 source platform 抽象與 rollout contract

規則：

- doc entity 的多 source 架構屬於 Core，不因 adapter 尚未齊全而延後
- reader adapter 的支援範圍可分階段 rollout
- spec 必須明確區分「Core contract 已定」與「某平台 reader 已落地」

### 3.2 Application Layer

Application Layer 是建立在 ZenOS Core 之上的產品與模組。

目前已知或已規劃的 application 類型包含：

- Zentropy
- CRM / Customer Management
- Access Management UI
- 未來其他 vertical apps

Application Layer 可以：

- 定義自己的 UX、view model、workflow state、細粒度 execution model
- 增加 Core 沒有的 domain object
- 把 app-specific object 映射到 Core 的 entity / task / plan

Application Layer 不得：

- 重新定義 L1-L3 entity 基本語意
- 重新定義 task lifecycle 與 confirm gate
- 繞過 workspace / visibility / authorization
- 假設自己擁有比 Core 更高的權限語意

## 4. Core Capability Boundary

### 4.1 屬於 ZenOS Core 的能力

- ontology schema 與 L1-L3 entity runtime
- relationship / impacts / entries / blindspot / document governance
- task / plan action runtime
- task review / confirm / action-to-knowledge feedback
- doc entity / document bundle / source platform contract
- identity / workspace / active workspace context
- visibility 與 subtree authorization
- MCP / agent-facing tool contract
- capture / sync / analyze / governance loop

### 4.2 不屬於 ZenOS Core 的能力

- CRM 的 deal pipeline 與 activity UX
- 權限設定後台的具體產品介面
- Zentropy 的 milestone、consensus flow、daily execution UX
- app-specific checklist、subtask、routine、execution step
- 單一 application 專屬的 dashboard surface 與操作習慣
- application 自己的 end-user authentication provider

## 5. L3-Action Subclass（原 Action Layer，已併入 Knowledge Layer）

> **2026-04-23 update**：舊 §5.1 Task / §5.2 Plan / §5.3 Subtask 的「不是 entity」語意已廢止。Task / Plan / Milestone / Subtask 全部成為 L3-Action subclass，屬於 Knowledge Layer 的一部分。Goal 合併進 Milestone。
>
> 本節僅保留邊界宣告，細節 canonical 定義在 `SPEC-ontology-architecture v2 §9` + 治理細則在 `SPEC-task-governance`。

### 5.1 邊界宣告

- **Milestone / Plan / Task / Subtask** 皆為 L3-Action subclass
- 它們是 `entities_base` row，`level=3`，各有自己的 subclass table（`entity_l3_milestone / entity_l3_plan / entity_l3_task / entity_l3_subtask`）
- 繼承 `BaseEntity`（permission / parent_id / owner / timestamps）+ 共用 `L3TaskBaseEntity`（description / task_status / assignee / dispatcher / acceptance_criteria / priority / result / handoff_events）
- `linked_entities` 透過 `relationships` 表，與 L1/L2/L3-Semantic 一致
- `parent_id` 表達歸屬（例：task.parent_id 指向 plan 或直接 L1）

### 5.2 廢止項目

以下舊敘述於本 SPEC 版次起廢止：

- ~~「Task 不是 entity」~~ → Task 是 `entity_l3_task` row
- ~~「Plan 不是 entity」~~ → Plan 是 `entity_l3_plan` row
- ~~「Subtask 不屬於 ZenOS Core」~~ → Subtask 是 `entity_l3_subtask` row，屬 Core L3-Action subclass，語意為 agent 派工子單位
- ~~`plan_id` / `plan_order` 欄位獨立於 entity~~ → `plan_order` 留在 `entity_l3_task`；「task 屬於哪個 plan」用 `parent_id` 表達

### 5.3 細節指引

| 主題 | 位置 |
|------|------|
| Canonical schema（DDL / Python dataclass） | `SPEC-ontology-architecture v2 §9` |
| 業務 lifecycle（`task_status` state machine） | `SPEC-ontology-architecture v2 §11.2` |
| 品質門檻 / handoff chain / 驗收流程 | `SPEC-task-governance`（改寫中）|
| 與 L1/L2/L3-Semantic 的關聯規則 | `SPEC-ontology-architecture v2 §10 Relationship` |
| MCP tool shape | `SPEC-mcp-tool-contract`（改寫中）|

## 6. Application Mapping Contract

Application Layer 可以定義更細的 execution model，但必須遵守以下映射規則：

1. app 的 milestone / phase，可映射到一個或多個 Core Plan。
2. app 的 task，若需要跨人協作、授權控管、驗收與知識回饋，必須映射到 Core Task。
3. app 的 subtask / checklist / internal step，若不需要上述能力，應留在 app 內部，不得強制寫入 Core。
4. app 不得以 subtask 取代 Core Task 的驗收邊界。

## 7. 共享與權限邊界

跨 workspace 共享的正式範圍，以 ZenOS Core contract 為準：

- L1-L3 entity
- document
- task
- plan metadata（若 task orchestration 需要）

其中 `L1` 的正式語意是「workspace 內可被獨立授權與分享的主軸 root」。
`product` 是最常見的 L1 類型，但不是唯一類型；在 B2B 協作場景下，`company/customer/account` 也可作為 L1，只要它承擔的是一整棵可分享 ontology subtree 的授權邊界，而不只是 application 自己的 view model。

Application-specific object 是否可共享，必須額外由各 app spec 明確定義；不得自動假設可沿用 Core 共享規則。

## 8. 與既有 Spec 的關係

本 spec 為下列文件的上位邊界：

- `SPEC-ontology-architecture`
- `SPEC-task-governance`
- `SPEC-identity-and-access`
- `SPEC-zenos-auth-federation`
- `SPEC-crm-core`

對齊規則：

1. `SPEC-ontology-architecture v2` 為 Knowledge Layer canonical SSOT；Task / Plan / Milestone / Subtask 全部為 L3-Action subclass（`entity_l3_task / plan / milestone / subtask`），屬 Knowledge Layer 一部分。
2. `SPEC-task-governance` 負責 L3-Action subclass 的治理規則（`task_status` state machine、handoff chain、confirm/accept、entity_entries 回饋），不重新定義 schema。
3. `SPEC-identity-and-access` 負責 Core Identity & Access Layer 與共享邊界。
4. `SPEC-zenos-auth-federation` 負責 Identity & Access Layer 的外部接入 contract（federation exchange、delegated credential、identity link）。
5. `SPEC-crm-core` 等應用層 spec 必須明確標示自己是建立在 ZenOS Core 之上的 application module。

## 9. 非目標

- 不在本 spec 內定義某個 application 的完整 UX。
- 不在本 spec 內定義 CRM、Zentropy 或 Access Management 的產品需求細節。
- 不在本 spec 內定義 app-specific subtask schema。

## 10. 後續要求

後續所有新增 spec 若涉及下列主題，必須先聲明自己位於哪一層：

- entity / knowledge / document / entries
- task / plan / review / confirm
- workspace / visibility / access
- app-specific workflow / milestone / checklist / portal surface

若無法判定所屬層級，必須先回到本 spec 做邊界澄清，不得直接擴張現有模型。
