# SPEC: Agent-Aware 權限治理（Permission Governance）

> PM: Codex | Date: 2026-03-26 | Status: Draft
> Supersedes: `docs/archive/specs/SPEC-intra-company-permission.md` as the implementation target

## 問題

ZenOS 的核心價值是讓 AI 與人共用公司 context，但公司真正採用 ZenOS 的前提不是「AI 很懂公司」，而是「AI 懂公司，但不會知道不該知道的事」。

現況有兩個對立風險：

1. 控管太少：高層不敢把財務、人事、法務、客戶合約等資料放進 ontology。
2. 控管太多：每個部門都把資料鎖起來，最後 ZenOS 退化成多個資料孤島，失去 cross-functional context 的價值。

此外，ZenOS 不是只有人會操作。未來權限設定也必須能被 agent 協助完成，例如：

- 根據 entity 類型建議合適的預設權限
- 批次調整某個 L2 domain 底下的權限
- 模擬某次變更會影響哪些人、哪些 agent、哪些 task
- 檢查是否造成資料孤島或過度曝光

因此這份 spec 必須同時滿足三件事：

1. 給人看的產品規格
2. 給 server 強制執行的權限模型
3. 給 agent 正確建議、驗證、模擬、套用的 machine-readable policy schema

---

## 目標

1. 讓 admin 能安心把敏感資料放進 ZenOS。
2. 讓部門主管可以用 role / department 為主的方式管理權限，而不是維護 per-user ACL。
3. 讓 agent 能幫忙設定權限，但高風險變更仍需人工確認。
4. 讓 L2 entity 成為主要權限治理邊界，避免權限碎裂到 document 級造成維護災難。
5. 讓系統能持續檢測並抑制資料孤島化。

---

## 非目標

- 不做時間條件權限，例如「某資料只在月底前可見」。
- 不做複雜 ABAC 規則引擎。
- 不以 per-user ACL 作為日常主模型。
- 不讓 agent 在高風險權限變更上完全自動生效。

---

## 設計原則

### 1. Server-side enforcement

權限過濾必須在 ZenOS server 端執行。前端或 agent 不能自行決定什麼該隱藏。

### 2. L2-first governance

L2 entity 是主要權限治理邊界。L1 太粗，L3/document 太細。

### 3. Role/department first, user exception second

日常操作以 `department` / `role` 為主，`user allow/deny` 只用於少數例外。

### 4. Agent is delegated, not sovereign

Agent 不是獨立權限主體。Agent 的有效權限永遠小於等於 owner user。

### 5. Restrict only where domain boundary exists

只有在實際有敏感邊界的 domain 才收緊，例如財務、人事、法務、核心架構。不要把整個產品樹一刀切成 confidential。

### 6. Every restriction must remain explainable

每次 policy 都要能回答：

- 誰能看
- 為什麼這樣設
- 影響哪些資源
- 是否提高孤島風險

### 7. High-risk changes require confirmation

Agent 可以建議與模擬，但像 `confidential`、大範圍 propagation、移除最後一位 owner 等高風險變更必須經人確認。

---

## 核心概念

### Principal

權限主體。

分為：

- `user`
- `agent`
- `system_admin`

### Resource

受保護資源。

分為：

- `entity`
- `document`
- `protocol`
- `blindspot`
- `task`
- `relationship`
- `source_content`

### Policy

描述某資源對哪些 principal 開放哪些 action 的結構化規則。

### Effective Permission

某 principal 對某 resource 的最終權限，來源為：

`tenant boundary ∩ resource policy ∩ inheritance ∩ principal scope ∩ agent scope`

### Isolation Risk

資源被過度封閉，導致 context 無法在應該流動的地方流動的風險。

### Overexposure Risk

資源開得太寬，導致敏感資訊暴露給不該看到的人或 agent 的風險。

---

## Principal Model

### User

```ts
interface UserPrincipal {
  id: string;
  tenant_id: string;
  department_ids: string[];
  role_ids: string[];
  is_admin: boolean;
  status: "active" | "suspended" | "invited";
}
```

### Agent

```ts
interface AgentPrincipal {
  id: string;
  tenant_id: string;
  owner_user_id: string;
  owner_department_ids: string[];
  owner_role_ids: string[];
  key_status: "active" | "revoked";
  scope: AgentScope;
}
```

### Agent Scope

Agent scope 是對 owner user 權限的再收窄，不可擴權。

```ts
interface AgentScope {
  read_classification_max: "open" | "internal" | "restricted" | "confidential";
  allowed_department_ids: string[];
  allowed_role_ids: string[];
  allowed_entity_ids: string[];
  denied_entity_ids: string[];
  can_write_ontology: boolean;
  can_create_tasks: boolean;
  can_confirm_tasks: boolean;
}
```

有效權限規則：

`effective_agent_permission = owner_user_permission ∩ agent_scope`

---

## Resource Model

### Entity 是主權限節點

大多數資源預設繼承 entity 權限。

主要原則：

- `entity` 是 primary policy holder
- `document/protocol/blindspot/task/source_content` 預設繼承 linked entity policy
- 若資源沒有 linked entity，則使用自己的獨立 policy

### L2 作為主要治理邊界

建議：

- L1 product/project 預設 `open` 或 `internal`
- L2 module/domain 才是主要限制點
- L3/detail/document/task 多數情況繼承 L2

---

## Classification Model

權限等級採四級：

| Classification | 說明 | 典型場景 |
|---|---|---|
| `open` | 公司內所有 active user/agent 可讀 | 通用產品與流程知識 |
| `internal` | 公司內 active user 可讀，但可被 agent scope 再收窄 | 一般營運資訊 |
| `restricted` | 僅特定部門/角色/授權人員可讀 | 工程架構、投放策略、未公開 roadmap |
| `confidential` | 僅特定高權限群組或明確名單可讀 | 財務、人事、法務、合約、董事會事項 |

規則：

- `open` < `internal` < `restricted` < `confidential`
- 子節點可更嚴，不可更鬆

---

## Policy Schema

這是唯一正式的 machine-readable 權限來源。

```ts
interface AccessPolicy {
  version: "1.0";
  resource_type: "entity" | "document" | "protocol" | "blindspot" | "task" | "relationship" | "source_content";
  resource_id: string;

  classification: "open" | "internal" | "restricted" | "confidential";

  inheritance_mode: "inherit" | "custom";
  inherit_from_parent: boolean;

  read_scope: {
    department_ids: string[];
    role_ids: string[];
    user_ids: string[];
    agent_ids: string[];
  };

  write_scope: {
    department_ids: string[];
    role_ids: string[];
    user_ids: string[];
    agent_ids: string[];
  };

  deny_scope: {
    user_ids: string[];
    agent_ids: string[];
  };

  propagation: {
    to_children: boolean;
    to_documents: boolean;
    to_tasks: boolean;
    to_blindspots: boolean;
    to_protocols: boolean;
    to_source_content: boolean;
  };

  owner_user_id: string | null;
  steward_role_id: string | null;
  reason: string;
  requires_confirmation: boolean;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}
```

### Policy 設計說明

- `classification` 是風險層級，不是完整 ACL。
- `read_scope` / `write_scope` 才是可讀可寫範圍。
- `deny_scope` 是例外拒絕機制，不作為日常主模型。
- `owner_user_id` 是業務 owner。
- `steward_role_id` 是治理責任角色，例如 finance lead、HR lead、legal lead。
- `reason` 必填，避免只留下一堆無意義權限欄位。

---

## Entity Schema 擴充

`Entity` 本身至少新增以下欄位：

```ts
interface EntityPermissionFields {
  classification: "open" | "internal" | "restricted" | "confidential";
  policy_id: string | null;
  owner_user_id: string | null;
  steward_role_id: string | null;
}
```

注意：

- 不把所有 policy 欄位平鋪在 entity 上
- entity 存 policy pointer 與必要摘要欄位
- 完整 rule 存放於 policy layer，避免 schema 爆炸

---

## 預設規則

### 預設 policy

- 新建 L1 entity：預設 `internal`
- 新建 L2 entity：預設 `internal`，agent 可依 template 建議升為 `restricted`
- 新建 L3/detail/document/task：預設 `inherit`

### 何時 agent 可以主動建議升級

名稱、tag、摘要出現高敏感訊號時，agent 可建議但不可直接生效：

- 薪資
- 合約
- 法務
- 財報
- 現金流
- 裁員
- 面試評估
- 績效
- cap table
- acquisition

---

## Inheritance Rules

### 樹狀繼承

- 父 `open` → 子可 `open/internal/restricted/confidential`
- 父 `internal` → 子可 `internal/restricted/confidential`
- 父 `restricted` → 子可 `restricted/confidential`
- 父 `confidential` → 子只能 `confidential`

### Attached resource 繼承

預設繼承 linked entity 的 policy：

- document
- protocol
- blindspot
- task
- source_content

### Relationship 顯示規則

若使用者可見 A 但不可見 B：

- 預設隱藏該 relationship
- Phase 2 才考慮顯示匿名化 relation，如 `Restricted dependency`

---

## Task / Document / Protocol / Blindspot 規則

### Task

Task 是敏感資訊外洩高風險點，因為 title/description 常比 entity 更直接。

規則：

- 若 task 有 linked entities，採 linked entities 中最嚴格 classification
- 若多個 linked entities 權限不同，task 以最嚴格 policy 為基準
- 若 task 無 linked entity，必須有自己的 policy
- 對無權者，預設不顯示該 task

### Document / Protocol / Blindspot

預設：

- 直接繼承 linked entity policy
- 除非 `inheritance_mode = custom`

---

## Template Model

Agent 不應從零發明 policy，應優先套用 template。

```ts
interface PolicyTemplate {
  template_id: string;
  name: string;
  classification: "open" | "internal" | "restricted" | "confidential";
  read_scope: {
    department_ids: string[];
    role_ids: string[];
  };
  write_scope: {
    department_ids: string[];
    role_ids: string[];
  };
  propagation: {
    to_children: boolean;
    to_documents: boolean;
    to_tasks: boolean;
    to_blindspots: boolean;
    to_protocols: boolean;
    to_source_content: boolean;
  };
  requires_confirmation: boolean;
}
```

### 內建模板

- `company_default_internal`
- `department_restricted_engineering`
- `department_restricted_finance`
- `department_restricted_marketing`
- `leadership_confidential`
- `hr_confidential`
- `legal_confidential`
- `inherit_from_entity_default`

---

## Agent Workflow

這一章是本 spec 的核心。權限系統必須可被 agent 正確使用，而不是只能靠人手動點 UI。

### 1. Suggest

Agent 根據以下資訊產出 policy proposal：

- entity type / level
- parent policy
- tags.what / tags.who
- title / summary
- linked resources
- template library

輸出內容：

- 建議 classification
- 建議 template
- 建議 propagation
- 影響摘要
- 風險分數

### 2. Simulate

Agent 在套用前必須模擬影響：

- 影響多少 child entities
- 影響多少 documents / tasks / blindspots / protocols
- 哪些 roles 會新增或失去權限
- 是否造成只有單人可見
- 是否切斷跨部門主要 context 流

### 3. Validate

未通過 validation 的 proposal 不可套用。

### 4. Confirm

高風險 proposal 需人工確認。

### 5. Apply

只有 validation pass 且 confirmation 條件滿足才生效。

---

## Agent Operation Modes

### Low-risk: 可自動生效

- 新建 resource 套用預設 template
- child resource 繼承 parent policy
- 修復缺失欄位，例如補上 owner/steward
- 檢查並修正明顯非法 inheritance

### Medium-risk: 只能 proposal

- `internal -> restricted`
- 調整 read/write role scope
- 批次調整某個 L2 底下的 attached resources
- 調整 agent scope

### High-risk: 必須人工確認

- 任一 resource 升級成 `confidential`
- L1 entity 被設成 `restricted/confidential`
- 影響超過閾值的 propagation
- 移除最後一位 owner 或 steward
- 讓 agent 取得 ontology write / confirm task 等敏感操作

---

## Validation Rules

下列規則由 server 端強制，agent 必須先檢查。

### 結構規則

1. `classification` 必須是四級之一。
2. `confidential` 必須有 `owner_user_id`。
3. `restricted/confidential` 必須有 `steward_role_id` 或 `owner_user_id`。
4. `inheritance_mode = inherit` 時，不可同時寫自訂 scope。

### 繼承規則

5. 子節點不可比父節點更寬鬆。
6. task/document/protocol/blindspot 不可比其 linked entity 更寬鬆。
7. agent scope 不可超過 owner user scope。

### 治理規則

8. `confidential` 不可無 explainable `reason`。
9. `restricted/confidential` 若造成只剩單人可見，需標記高 isolation risk。
10. 單一變更若影響資源數超過閾值，`requires_confirmation = true`。

---

## Risk Scoring

每次 proposal 都需計算兩種風險：

```ts
interface PolicyRiskSummary {
  overexposure_risk_score: number; // 0-100
  isolation_risk_score: number;    // 0-100
  affected_resources_count: number;
  newly_allowed_principals: string[];
  newly_blocked_principals: string[];
  warnings: string[];
}
```

### Isolation Risk 提升條件

- 只剩單人可見
- 切斷主要協作部門可見性
- 大量 L2 domain 被鎖成 confidential
- linked tasks / docs / blindspots 都被一起封閉

### Overexposure Risk 提升條件

- finance / HR / legal 類型仍維持 `open/internal`
- 敏感 entity 可被廣泛 agent 存取
- task title/description 直接暴露敏感資訊

---

## Confirmation Rules

下列情況必須人工確認：

1. `classification = confidential`
2. L1 entity 被改成 `restricted` 或 `confidential`
3. 影響資源數 > 20
4. 新增或移除高權限角色存取
5. 會造成 `isolation_risk_score >= 70`
6. 會造成 `overexposure_risk_score >= 70`

確認結果：

- `accepted`
- `rejected`
- `accepted_with_modification`

---

## MCP / API Interface

為了讓 agent 穩定操作，需提供專用介面，不應只暴露 generic write。

### Read APIs

- `get_policy(resource_type, resource_id)`
- `list_policy_templates()`
- `audit_policy_exposure(query)`
- `simulate_policy_change(resource_type, resource_id, draft_policy)`

### Proposal / Validation APIs

- `suggest_policy(resource_type, resource_id)`
- `validate_policy(resource_type, resource_id, draft_policy)`
- `propose_policy_change(resource_type, resource_id, draft_policy)`

### Apply APIs

- `apply_policy(resource_type, resource_id, draft_policy, confirmed=false)`
- `assign_agent_scope(agent_id, scope, confirmed=false)`

### Response shape 要求

所有 proposal / validation / simulation response 都至少回傳：

```ts
interface PolicyOperationResult {
  valid: boolean;
  requires_confirmation: boolean;
  policy: AccessPolicy;
  risk_summary: PolicyRiskSummary;
  explanation: {
    summary: string;
    reason_codes: string[];
  };
  errors: string[];
  warnings: string[];
}
```

---

## Audit Log

所有 policy 變更都要留下可審計紀錄。

```ts
interface PolicyAuditEvent {
  event_id: string;
  actor_type: "user" | "agent" | "system";
  actor_id: string;
  operation: "suggest" | "validate" | "propose" | "apply" | "reject";
  resource_type: string;
  resource_id: string;
  before_policy_id: string | null;
  after_policy_id: string | null;
  risk_summary: PolicyRiskSummary;
  confirmation_required: boolean;
  confirmed_by: string | null;
  created_at: string;
}
```

---

## Dashboard Requirements

### Team 頁

需支援：

- 管理 user department / role
- 管理 agent key 與 owner
- 設定 agent scope 上限

### Node Detail / Resource Detail

需支援：

- 顯示 classification
- 顯示套用的 template
- 顯示 owner / steward
- 顯示 propagation 範圍
- 顯示 risk summary
- 顯示「此變更可能造成資料孤島」警示

### Batch Permission UI

需支援：

- 對單一 L2 domain 底下資源批次套用 template
- 顯示受影響資源數
- 顯示新增與失去權限的 principal

---

## Governance Metrics

系統需持續追蹤：

- `restricted/confidential` entity 佔比
- 無 owner 的 restricted/confidential entity 數
- 只有單人可見的 entity 數
- 最近 30 天 policy reject 次數
- 最近 30 天 agent 提案次數與通過率
- 最近 30 天 access denied 次數

若以下任一條件達成，系統應主動產生治理提醒：

- confidential entity 佔比異常上升
- 單人可見 entity 持續增加
- 大量 task 因 linked entity 權限被隱藏

---

## Rollout Plan

### Phase 0: Schema + Enforcement 基礎

- 定義 principal model
- 定義 classification 四級
- 定義 AccessPolicy schema
- server 端接入 read filtering
- `entity/document/task/protocol/blindspot` 基本繼承

### Phase 1: Agent-aware Policy Operations

- template library
- suggest / validate / simulate / apply APIs
- agent scope model
- confirmation gate

### Phase 2: Dashboard Governance UI

- Team role/department 管理
- Resource policy UI
- batch apply UI
- risk summary UI

### Phase 3: Isolation Prevention

- isolation / overexposure analytics
- 定期 review
- 自動治理提醒

---

## 開放問題

1. `department` 與 `role` 是否都由 ontology entity 建模，還是先保留在 partner profile schema？
2. 若 task 連多個 entity 且跨 domain，是否永遠取最嚴格 policy，或可拆成 masked presentation？
3. 是否需要單獨的 `external_vendor` / `contractor` principal 類型？
4. agent scope 是否要支援「只能讀不能 summarise sensitive content」這類更細語意限制？本版先不做。

---

## 成功標準

1. Admin 願意把 finance / HR / legal 類資料放進 ontology。
2. agent 可正確建議與模擬權限設定，而不是亂寫 generic fields。
3. 權限設定時間隨公司成長仍維持可管理，不退化成 per-user ACL 地獄。
4. 權限收緊後，系統仍保有足夠 cross-functional context，不形成大面積資料孤島。
