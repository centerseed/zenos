# ZenOS SQL 全遷移 Spec

> 日期：2026-03-25
> 狀態：Draft
> 作者：Architect
> 交付對象：Engineering

---

## 問題陳述

ZenOS 目前的 runtime 資料源是 Firestore。當 ontology 節點、關聯、任務與盲點數量增加時，現有查詢模式會出現明顯的高讀取風險：

- 首頁與總覽頁傾向整包載入
- 項目詳情頁存在 N+1 query
- 關聯與統計常在前端補算
- 任務與知識圖譜會把多個 collection 讀取疊加

公司已經有一台可用的 PostgreSQL，因此本案採取**一次性全遷移**：直接把 ZenOS 的主資料層切到 SQL，SQL 成為唯一 source of truth，Firestore 不再承擔線上讀寫。

---

## 目標

- 將 ZenOS 的主要資料與查詢全部搬到 PostgreSQL
- 移除 runtime 對 Firestore 的依賴
- 讓 dashboard、MCP、backend service 都透過同一套 SQL repository 存取資料
- 保留現有 domain model 的語意，但把儲存格式收斂成可 JOIN、可聚合、可索引的 SQL schema
- 避免首頁與總覽頁的全量讀取與 N+1 query

---

## 非目標

- 不做雙寫
- 不做 Firestore fallback
- 不做 SQL / Firestore 同步
- 不保留兩套 source of truth
- 不在這一版處理跨專案共用 SQL 的長期治理流程，只要求 namespace 隔離

---

## 遷移原則

1. SQL 是唯一 runtime 資料源。
2. 所有讀寫都經過 repository layer，不直接由 UI 或 service 層碰資料庫 driver。
3. 所有表都必須帶 `partner_id`，避免共用資料庫互相污染。
4. 關聯性資料以 join table 為主，不使用 Firestore 子集合思維。
5. 可變結構欄位集中放在 `JSONB`，但關鍵查詢欄位必須獨立成欄位並加索引。
6. 以 PostgreSQL 為預設 SQL dialect。
7. 多租戶隔離不能只靠應用層條件，必須由資料庫約束保證。
8. 一次性 cutover 必須有 freeze、final sync、go/no-go gate 與 rollback runbook。

---

## 範圍

這次完整遷移包含：

- `partners`
- `entities`
- `relationships`
- `documents`
- `protocols`
- `blindspots`
- `tasks`
- `usage_logs`

以及對應的 join tables：

- `document_entities`
- `blindspot_entities`
- `task_blockers`
- `task_entities`

---

## 資料模型總覽

### Enum 定義

以下欄位採用文字型 enum 值，應在應用層與資料層保持一致。

- `entity.type`: `product` | `module` | `goal` | `role` | `project` | `document`
- `entity.status`: `active` | `paused` | `completed` | `planned` | `current` | `stale` | `draft` | `conflict`
- `relationship.type`: `depends_on` | `serves` | `owned_by` | `part_of` | `blocks` | `related_to` | `impacts` | `enables`
- `document.status`: `current` | `stale` | `archived` | `draft` | `conflict`
- `blindspot.severity`: `red` | `yellow` | `green`
- `blindspot.status`: `open` | `acknowledged` | `resolved`
- `task.status`: `backlog` | `todo` | `in_progress` | `review` | `done` | `archived` | `blocked` | `cancelled`
- `task.priority`: `critical` | `high` | `medium` | `low`
- `source.type`: `github` | `gdrive` | `notion` | `upload`
- `partner.status`: `invited` | `active` | `suspended`

> 實作要求：
>
> - 欄位型別可維持 `text`，但 migration 必須為所有 enum 欄位加上 `check constraint`。
> - 匯入腳本必須在寫入前清洗舊值；遇到非法 enum 值時應 fail fast，不得靜默寫入。

### 多租戶完整性規則

- 所有業務表都必須同時具備：
  - `primary key (id)` 或等價唯一識別
  - `unique (partner_id, id)`，供複合外鍵使用
- 任何跨表參照若語意上屬於同一租戶，必須使用複合外鍵 `(partner_id, foreign_id)`。
- join table 的主鍵若未包含 `partner_id`，至少也必須以複合外鍵確保兩端 row 與 join row 屬於同一 `partner_id`。
- 若最終採用獨立 schema 隔離，以上規則仍保留，避免共享連線或 migration 腳本誤寫。

---

## Schema

### 1. `partners`

共用 SQL 的租戶隔離核心。

```sql
create table partners (
  id text primary key,
  email text not null unique,
  display_name text not null,
  api_key text not null default '',
  authorized_entity_ids text[] not null default '{}'::text[],
  status text not null default 'active',
  is_admin boolean not null default false,
  shared_partner_id text null,
  default_project text null,
  invited_by text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### 說明

- `id` 保留文字型，方便與現有 Firestore ID 直接對應。
- `shared_partner_id` 用於目前系統內的共用夥伴群組邏輯。
- `default_project` 用於 MCP / dashboard 的預設 project scope。
- `authorized_entity_ids` 保留現有授權列表語意，後續如需細分可再拆 join table。
- `status` 必須至少支援 `invited`、`active`、`suspended`。

#### 索引

```sql
create unique index uq_partners_api_key on partners(api_key) where api_key <> '';
create index idx_partners_status on partners(status);
create index idx_partners_shared_partner on partners(shared_partner_id);
create index idx_partners_authorized_entities on partners using gin(authorized_entity_ids);
```

---

### 2. `entities`

骨架層主表，承載 product / module / goal / role / project / document entity。

```sql
create table entities (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  name text not null,
  type text not null,
  level integer null,
  parent_id text null,
  project_id text null,
  status text not null default 'active',
  summary text not null,
  tags_json jsonb not null default '{}'::jsonb,
  details_json jsonb null,
  confirmed_by_user boolean not null default false,
  owner text null,
  sources_json jsonb not null default '[]'::jsonb,
  visibility text not null default 'public',
  last_reviewed_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### `tags_json` 結構

```json
{
  "what": ["..."],
  "why": "...",
  "how": "...",
  "who": ["..."]
}
```

#### `sources_json` 結構

```json
[
  { "uri": "...", "label": "...", "type": "github" }
]
```

#### 索引

```sql
create unique index uq_entities_partner_id_id on entities(partner_id, id);
create index idx_entities_partner_type on entities(partner_id, type);
create index idx_entities_partner_parent on entities(partner_id, parent_id);
create index idx_entities_partner_status on entities(partner_id, status);
create index idx_entities_partner_confirmed on entities(partner_id, confirmed_by_user);
create index idx_entities_partner_name on entities(partner_id, name);
```

#### 說明

- `parent_id` 保留樹狀結構。
- `tags_json` 與 `details_json` 保留彈性，但查詢時不得把主要過濾條件塞回 JSON。
- `sources_json` 先用 JSONB，避免為低頻資料額外拆表。
- `parent_id` 應改為複合外鍵 `(partner_id, parent_id) references entities(partner_id, id)`，避免跨 partner 掛錯父節點。
- 若 Knowledge Map 需要 project scope，`entities` 必須新增 `project_id text null`，代表所屬 root project / product entity。

#### 額外約束

```sql
alter table entities
  add constraint fk_entities_parent
    foreign key (partner_id, parent_id) references entities(partner_id, id) on delete set null,
  add constraint fk_entities_project
    foreign key (partner_id, project_id) references entities(partner_id, id) on delete set null,
  add constraint chk_entities_type
    check (type in ('product', 'module', 'goal', 'role', 'project', 'document')),
  add constraint chk_entities_status
    check (status in ('active', 'paused', 'completed', 'planned', 'current', 'stale', 'draft', 'conflict')),
  add constraint chk_entities_visibility
    check (visibility in ('public', 'restricted')),
  add constraint chk_entities_project_root
    check ((type not in ('product', 'project')) or project_id = id);
```

---

### 3. `relationships`

實體關係表，取代 Firestore subcollection。

```sql
create table relationships (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  source_entity_id text not null,
  target_entity_id text not null,
  type text not null,
  description text not null,
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### 索引

```sql
create unique index uq_relationships_partner_id_id on relationships(partner_id, id);
create index idx_relationships_partner_source on relationships(partner_id, source_entity_id);
create index idx_relationships_partner_target on relationships(partner_id, target_entity_id);
create index idx_relationships_partner_type on relationships(partner_id, type);
create index idx_relationships_partner_source_type on relationships(partner_id, source_entity_id, type);
```

#### 約束

```sql
create unique index uq_relationships_dedup
on relationships(partner_id, source_entity_id, target_entity_id, type);
```

#### 說明

- 關係表只存單向 edge。
- 查詢雙向圖譜時由應用層組裝，不回到 Firestore 子集合模型。
- `source_entity_id` 與 `target_entity_id` 都應使用複合外鍵 `(partner_id, entity_id)` 指向同租戶的 `entities`。

#### 額外約束

```sql
alter table relationships
  add constraint fk_relationships_source
    foreign key (partner_id, source_entity_id) references entities(partner_id, id) on delete cascade,
  add constraint fk_relationships_target
    foreign key (partner_id, target_entity_id) references entities(partner_id, id) on delete cascade,
  add constraint chk_relationships_type
    check (type in ('depends_on', 'serves', 'owned_by', 'part_of', 'blocks', 'related_to', 'impacts', 'enables')),
  add constraint chk_relationships_no_self_loop
    check (source_entity_id <> target_entity_id);
```

---

### 4. `documents`

神經層入口，代表外部文件的語意代理。

```sql
create table documents (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  title text not null,
  source_json jsonb not null,
  tags_json jsonb not null default '{}'::jsonb,
  summary text not null,
  status text not null default 'current',
  confirmed_by_user boolean not null default false,
  last_reviewed_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### `source_json` 結構

```json
{
  "type": "github",
  "uri": "https://...",
  "adapter": "github"
}
```

#### `tags_json` 結構

```json
{
  "what": ["..."],
  "why": "...",
  "how": "...",
  "who": ["..."]
}
```

#### 索引

```sql
create unique index uq_documents_partner_id_id on documents(partner_id, id);
create index idx_documents_partner_status on documents(partner_id, status);
create index idx_documents_partner_confirmed on documents(partner_id, confirmed_by_user);
create index idx_documents_partner_title on documents(partner_id, title);
```

#### 額外約束

```sql
alter table documents
  add constraint chk_documents_status
    check (status in ('current', 'stale', 'archived', 'draft', 'conflict'));
```

---

### 5. `document_entities`

文件與實體的多對多關聯。

```sql
create table document_entities (
  document_id text not null,
  entity_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (document_id, entity_id)
);
```

#### 索引

```sql
create index idx_document_entities_partner_entity on document_entities(partner_id, entity_id);
create index idx_document_entities_partner_document on document_entities(partner_id, document_id);
```

#### 額外約束

```sql
alter table document_entities
  add constraint fk_document_entities_document
    foreign key (partner_id, document_id) references documents(partner_id, id) on delete cascade,
  add constraint fk_document_entities_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade;
```

---

### 6. `protocols`

由 ontology 組裝出來的 view，但仍保留在 SQL 中以供查詢與輸出。

```sql
create table protocols (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  entity_id text not null,
  entity_name text not null,
  content_json jsonb not null,
  gaps_json jsonb not null default '[]'::jsonb,
  version text not null default '1.0',
  confirmed_by_user boolean not null default false,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### `content_json` 結構

```json
{
  "what": {},
  "why": {},
  "how": {},
  "who": {}
}
```

#### `gaps_json` 結構

```json
[
  { "description": "...", "priority": "red" }
]
```

#### 索引

```sql
create unique index uq_protocols_partner_id_id on protocols(partner_id, id);
create unique index uq_protocols_partner_entity on protocols(partner_id, entity_id);
create index idx_protocols_partner_name on protocols(partner_id, entity_name);
create index idx_protocols_partner_confirmed on protocols(partner_id, confirmed_by_user);
```

#### 額外約束

```sql
alter table protocols
  add constraint fk_protocols_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade;
```

---

### 7. `blindspots`

治理輸出表。

```sql
create table blindspots (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  description text not null,
  severity text not null,
  suggested_action text not null,
  status text not null default 'open',
  confirmed_by_user boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### 索引

```sql
create unique index uq_blindspots_partner_id_id on blindspots(partner_id, id);
create index idx_blindspots_partner_status on blindspots(partner_id, status);
create index idx_blindspots_partner_severity on blindspots(partner_id, severity);
create index idx_blindspots_partner_confirmed on blindspots(partner_id, confirmed_by_user);
```

#### 額外約束

```sql
alter table blindspots
  add constraint chk_blindspots_severity
    check (severity in ('red', 'yellow', 'green')),
  add constraint chk_blindspots_status
    check (status in ('open', 'acknowledged', 'resolved'));
```

---

### 8. `blindspot_entities`

盲點與實體的多對多關聯。

```sql
create table blindspot_entities (
  blindspot_id text not null,
  entity_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (blindspot_id, entity_id)
);
```

#### 索引

```sql
create index idx_blindspot_entities_partner_entity on blindspot_entities(partner_id, entity_id);
create index idx_blindspot_entities_partner_blindspot on blindspot_entities(partner_id, blindspot_id);
```

#### 額外約束

```sql
alter table blindspot_entities
  add constraint fk_blindspot_entities_blindspot
    foreign key (partner_id, blindspot_id) references blindspots(partner_id, id) on delete cascade,
  add constraint fk_blindspot_entities_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade;
```

---

### 9. `tasks`

Action layer 主表。

```sql
create table tasks (
  id text primary key,
  partner_id text not null references partners(id) on delete cascade,
  title text not null,
  description text not null default '',
  status text not null default 'backlog',
  priority text not null default 'medium',
  priority_reason text not null default '',
  assignee text null,
  assignee_role_id text null,
  created_by text not null,
  linked_protocol text null,
  linked_blindspot text null,
  source_type text not null default '',
  context_summary text not null default '',
  due_date timestamptz null,
  blocked_reason text null,
  acceptance_criteria_json jsonb not null default '[]'::jsonb,
  completed_by text null,
  confirmed_by_creator boolean not null default false,
  rejection_reason text null,
  result text null,
  project text not null default '',
  project_id text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz null
);
```

#### `blocked_by` 結構

`blocked_by` 不採 JSON 儲存，改用獨立關聯表 `task_blockers`。

#### `acceptance_criteria_json` 結構

```json
["criterion 1", "criterion 2"]
```

#### 索引

```sql
create unique index uq_tasks_partner_id_id on tasks(partner_id, id);
create index idx_tasks_partner_status on tasks(partner_id, status);
create index idx_tasks_partner_assignee on tasks(partner_id, assignee);
create index idx_tasks_partner_created_by on tasks(partner_id, created_by);
create index idx_tasks_partner_project on tasks(partner_id, project);
create index idx_tasks_partner_project_id on tasks(partner_id, project_id);
create index idx_tasks_partner_priority on tasks(partner_id, priority);
create index idx_tasks_partner_due_date on tasks(partner_id, due_date);
create index idx_tasks_partner_linked_blindspot on tasks(partner_id, linked_blindspot);
create index idx_tasks_partner_confirmed on tasks(partner_id, confirmed_by_creator);
```

#### 說明

- `linked_protocol`、`linked_blindspot` 保持單值外鍵，避免不必要的 join table 複雜度。
- `project` 若保留字串欄位，只能作為歷史相容欄位；runtime scope 應以 `project_id` 或明確 join 規則為準。
- `assignee_role_id`、`linked_protocol`、`linked_blindspot` 都應使用複合外鍵綁定同租戶資料。

#### 額外約束

```sql
alter table tasks
  add constraint fk_tasks_assignee_role
    foreign key (partner_id, assignee_role_id) references entities(partner_id, id) on delete set null,
  add constraint fk_tasks_linked_protocol
    foreign key (partner_id, linked_protocol) references protocols(partner_id, id) on delete set null,
  add constraint fk_tasks_linked_blindspot
    foreign key (partner_id, linked_blindspot) references blindspots(partner_id, id) on delete set null,
  add constraint fk_tasks_project
    foreign key (partner_id, project_id) references entities(partner_id, id) on delete set null,
  add constraint chk_tasks_status
    check (status in ('backlog', 'todo', 'in_progress', 'review', 'done', 'archived', 'blocked', 'cancelled')),
  add constraint chk_tasks_priority
    check (priority in ('critical', 'high', 'medium', 'low')),
  add constraint chk_tasks_blocked_reason
    check ((status <> 'blocked') or (blocked_reason is not null and blocked_reason <> '')),
  add constraint chk_tasks_review_result
    check ((status <> 'review') or (result is not null)),
  add constraint chk_tasks_done_completed_at
    check ((status <> 'done') or (completed_at is not null));
```

---

### 10. `task_blockers`

任務之間的 blocker 關係。

```sql
create table task_blockers (
  task_id text not null,
  blocker_task_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (task_id, blocker_task_id)
);
```

#### 索引

```sql
create index idx_task_blockers_partner_task on task_blockers(partner_id, task_id);
create index idx_task_blockers_partner_blocker on task_blockers(partner_id, blocker_task_id);
```

#### 額外約束

```sql
alter table task_blockers
  add constraint fk_task_blockers_task
    foreign key (partner_id, task_id) references tasks(partner_id, id) on delete cascade,
  add constraint fk_task_blockers_blocker
    foreign key (partner_id, blocker_task_id) references tasks(partner_id, id) on delete cascade,
  add constraint chk_task_blockers_no_self
    check (task_id <> blocker_task_id);
```

---

### 11. `task_entities`

任務與實體的多對多關聯。

```sql
create table task_entities (
  task_id text not null,
  entity_id text not null,
  partner_id text not null references partners(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (task_id, entity_id)
);
```

#### 索引

```sql
create index idx_task_entities_partner_entity on task_entities(partner_id, entity_id);
create index idx_task_entities_partner_task on task_entities(partner_id, task_id);
```

#### 額外約束

```sql
alter table task_entities
  add constraint fk_task_entities_task
    foreign key (partner_id, task_id) references tasks(partner_id, id) on delete cascade,
  add constraint fk_task_entities_entity
    foreign key (partner_id, entity_id) references entities(partner_id, id) on delete cascade;
```

---

### 12. `usage_logs`

LLM 使用紀錄與治理觀測資料。

```sql
create table usage_logs (
  id bigserial primary key,
  partner_id text not null references partners(id) on delete cascade,
  model text not null,
  tokens_in integer not null default 0,
  tokens_out integer not null default 0,
  created_at timestamptz not null default now()
);
```

#### 索引

```sql
create index idx_usage_logs_partner_created_at on usage_logs(partner_id, created_at desc);
```

### Project Scope 規則

- `project_id` 定義為知識與任務的主要 scope key，值應指向同租戶下的 root product / project entity。
- `entities.project_id`：
  - root product / project entity 的 `project_id = id`
  - child entity 在 migration 與 runtime 寫入時，必須被展開填入所屬 root `project_id`
- `documents`、`blindspots`、`protocols` 若需高頻 project 篩選，應在第一版就補 `project_id`；若暫不加欄位，則必須在 repository 層定義可預測的 derivation join，且在驗收時用 `EXPLAIN ANALYZE` 驗證成本。
- `relationships` 若 Knowledge Map 以 project scope 為核心畫面，需定義：
  - 僅回傳 `source_entity_id` 與 `target_entity_id` 都落在 scope 內的 edge
  - 跨 project edge 是否顯示、如何標記，由產品規則明確定義，不能留給前端即席判斷

---

## 查詢策略

### Dashboard

- Projects list 直接讀 `entities`，以 `type in ('product', 'project') and project_id = id` 過濾。
- Modules count 由 SQL 聚合取得，不再逐個 product 查 child entities。
- Project detail 直接查：
  - project entity
  - children entities by `project_id`
  - blindspots by `blindspot_entities`
  - document count by `document_entities`
  - relationships by `relationships`

### Tasks

- Pulse view 直接從 `tasks` 查詢，再 JOIN `task_entities` 與 `entities` 取得統計。
- Inbox / Outbox / Review 用 SQL 條件查詢，不在前端大量篩選。
- 任務卡片資料盡量一次帶齊，避免每張卡片再補查 entity。

### Knowledge Map

- 不做全量 Firestore 式整包讀取。
- 預設以 `partner_id` 作用域 + `project` scope 載入。
- 關聯與盲點使用 join table 聚合，不在前端補算整個 graph。
- repository 層必須提供已 scope 化的 query，不接受前端先抓大集合再篩。

---

## 遷移流程

### 1. 建表

- 先在共用 PostgreSQL 建立上述所有表與索引
- schema 必須獨立於其他專案，至少有明確 namespace 或 table prefix

### 2. 匯入資料

- 匯入順序：
  1. `partners`
  2. `entities`
  3. `relationships`
  4. `documents`
  5. `document_entities`
  6. `protocols`
  7. `blindspots`
  8. `blindspot_entities`
  9. `tasks`
  10. `task_blockers`
  11. `task_entities`
  12. `usage_logs`
- 匯入時保留原始 Firestore `id`
- 若原資料內有舊欄位命名差異，先在 migration script 轉換，不要污染 runtime schema
- 匯入腳本必須在 staging schema 先跑資料清洗與 enum 驗證，驗證通過後才寫入正式表
- 匯入期間必須輸出 reconciliation report：筆數、非法值、遺失外鍵、跨租戶參照、空 project scope

### 3. 驗證

- 驗證筆數一致
- 驗證 join 關聯一致
- 抽樣比對幾個 project 的 tree、tasks、blindspots、protocols
- 驗證主要頁面 query 結果與舊 Firestore 結果一致
- 驗證所有複合外鍵與 `check constraint` 均可成功套用，不能靠 `NOT VALID` 留待日後處理
- 以 `EXPLAIN ANALYZE` 驗證首頁、project detail、tasks inbox/review、knowledge map 的主查詢不再出現全表掃描或明顯 N+1 模式

### 4. Freeze 與 Final Sync

- 宣告 cutover window，於開始前先凍結 Firestore 寫入
- 凍結後執行 final import / final sync，只接受同一個資料快照
- final sync 完成後再次跑 reconciliation report 與抽樣驗證
- 只有驗證全綠時，才允許進入正式切換

### 5. 切換

- repository layer 改為 SQL implementation
- 啟用 SQL runtime 寫入
- 移除 runtime Firestore read/write
- 若還保留 Firestore，只能作為冷備份，不得再被應用程式讀取
- 切換完成後立刻執行 smoke test：dashboard、project detail、task create/update/review、MCP search/get/task

### 6. Rollback

- rollback 僅能在 cutover window 內、且 Firestore 冷備仍完整可讀時執行
- 若 smoke test 失敗、主查詢超時、或資料對帳不一致，立即停止 SQL 寫入並回切到 Firestore runtime
- rollback 條件、執行人、開關位置與最長決策時間必須在 cutover 前寫成 runbook
- 一旦 SQL 寫入已對外開放超過 cutover window，除非有資料補償方案，否則不得直接回切

---

## 程式變更範圍

### 後端

- 新增 SQL repository
- 將 entity / relationship / document / protocol / blindspot / task repository 全部切到 SQL
- 刪除 Firestore 依賴
- 更新 MCP tools 與 service layer 的資料存取路徑
- 補齊 migration / reconciliation / smoke test scripts
- 在 CI 或 deploy pipeline 中加入 schema drift 與 migration 驗證

### 前端

- `dashboard/src/lib/firestore.ts` 的資料來源切換為 SQL API 或 SQL-backed RPC
- Projects / Tasks / Knowledge Map 頁面改用 SQL 查詢結果
- 移除對 Firestore SDK 的 runtime 依賴
- 前端不得自行組裝跨頁大型聚合；所需 scope 化資料由 backend query 一次提供

---

## 驗收標準

- ZenOS 線上不再讀 Firestore
- ZenOS 線上不再寫 Firestore
- 首頁與總覽頁不再出現全量掃描與 N+1 query
- 所有核心資料都能在 SQL 中查到
- `entities` / `relationships` / `documents` / `protocols` / `blindspots` / `tasks` 結構已固定
- 共用 SQL 不會被 ZenOS 汙染到其他專案資料
- 主要頁面的功能行為與遷移前一致
- 所有 enum / 狀態機欄位已由 DB constraint 保護
- 所有跨表參照已由複合外鍵保證同租戶一致性
- 已完成 cutover rehearsal，並產出一份可執行 runbook 與 rollback checklist

---

## 風險

- 共用 SQL 若未做好 namespace 隔離，可能汙染其他專案
- `JSONB` 欄位若放入過多查詢條件，會重演 Firestore 的低效查詢問題
- 如果 migration 期間漏掉任何 join table，前端 graph / task 關聯會失真
- 若 runtime code 還殘留 Firestore 存取，會造成切換後的隱性 bug
- 若未定義 project scope 的正規模型，Knowledge Map 與 dashboard 會繼續依賴高成本補算
- 若 freeze / final sync 流程不嚴謹，cutover window 內的新資料可能遺失

---

## 決策紀錄

- 本案採用一次性 cutover，不做過渡雙寫
- SQL 為唯一 runtime source of truth
- schema 先固定，再做實作
- cutover 必須以 runbook 驅動，不接受只有「匯入後直接切」的臨場操作
