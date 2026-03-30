---
type: TD
id: TD-crm-core
status: Draft
ontology_entity: crm-module-architecture
created: 2026-03-28
updated: 2026-03-28
---

# Technical Design: CRM 核心模組

## 對應 Spec

`docs/specs/SPEC-crm-core.md`

架構決策見 `docs/decisions/ADR-011-crm-module-architecture.md`

---

## Component 架構

```
┌─────────────────────────────────────────────────────┐
│  Next.js Dashboard                                  │
│  /app/clients/          (客戶 tab)                  │
│    page.tsx             (Deal Kanban)               │
│    companies/page.tsx   (公司列表)                  │
│    companies/[id]/page.tsx (公司詳情)               │
│    deals/[id]/page.tsx  (商機詳情 + 活動時間軸)     │
└────────────────┬────────────────────────────────────┘
                 │ REST (Firebase ID token)
                 ▼
┌─────────────────────────────────────────────────────┐
│  Starlette App (Cloud Run)                          │
│  src/zenos/interface/crm_dashboard_api.py           │
│  GET/POST /api/crm/companies                        │
│  GET/PUT   /api/crm/companies/{id}                  │
│  GET       /api/crm/companies/{id}/contacts         │
│  GET       /api/crm/companies/{id}/deals            │
│  POST      /api/crm/contacts                        │
│  GET/PUT   /api/crm/contacts/{id}                   │
│  GET/POST  /api/crm/deals                           │
│  GET       /api/crm/deals/{id}                      │
│  PATCH     /api/crm/deals/{id}/stage                │
│  GET/POST  /api/crm/deals/{id}/activities           │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Application Layer                                  │
│  src/zenos/application/crm_service.py               │
│  CrmService                                         │
│    create_company()  →  crm_repo + zenos_write(L1)  │
│    update_company()  →  crm_repo + zenos_write(L1)  │
│    create_contact()  →  crm_repo + zenos_write(L1)  │
│    update_contact()  →  crm_repo + zenos_write(L1)  │
│    create_deal()     →  crm_repo                    │
│    update_deal_stage() → crm_repo + system_activity │
│    create_activity() →  crm_repo                    │
│    list_deals() / list_companies() / list_contacts()│
└────────┬───────────────────┬────────────────────────┘
         │                   │
         ▼                   ▼
┌────────────────┐  ┌────────────────────────────────┐
│ Infrastructure │  │  ZenOS Entity Write             │
│ crm_sql_repo.py│  │  (SqlEntityRepository +        │
│ CrmSqlRepo     │  │   SqlRelationshipRepository)   │
│  crm schema    │  │   zenos schema                 │
└────────────────┘  └────────────────────────────────┘
```

---

## Schema / Migration

### migration: `migrations/20260328_0005_crm_schema.sql`

```sql
begin;

-- 1. 擴充 zenos.entities type check constraint（加入 company, person）
alter table zenos.entities
  drop constraint if exists chk_entities_type;

alter table zenos.entities
  add constraint chk_entities_type
  check (type in (
    'product', 'module', 'goal', 'role', 'project', 'document',
    'company', 'person'
  ));

-- 2. 建立 crm schema
create schema if not exists crm;

-- 3. crm.companies
create table if not exists crm.companies (
  id           text primary key,
  partner_id   text not null references zenos.partners(id) on delete cascade,
  name         text not null,
  industry     text,
  size_range   text,   -- '1-10' | '11-50' | '51-200' | '200+'
  region       text,
  notes        text,
  zenos_entity_id text,   -- nullable; FK to zenos.entities.id (soft ref)
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_crm_companies_partner on crm.companies(partner_id);
create index if not exists idx_crm_companies_name    on crm.companies(partner_id, name);

-- 4. crm.contacts
create table if not exists crm.contacts (
  id           text primary key,
  partner_id   text not null references zenos.partners(id) on delete cascade,
  company_id   text not null references crm.companies(id) on delete cascade,
  name         text not null,
  title        text,
  email        text,
  phone        text,
  notes        text,
  zenos_entity_id text,   -- nullable; FK to zenos.entities.id (soft ref)
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_crm_contacts_partner on crm.contacts(partner_id);
create index if not exists idx_crm_contacts_company on crm.contacts(partner_id, company_id);

-- 5. crm.deals
create table if not exists crm.deals (
  id                    text primary key,
  partner_id            text not null references zenos.partners(id) on delete cascade,
  title                 text not null,
  company_id            text not null references crm.companies(id),
  owner_partner_id      text not null references zenos.partners(id),
  funnel_stage          text not null default '潛在客戶',
  amount_twd            integer,
  deal_type             text,
  source_type           text,
  referrer              text,
  expected_close_date   date,
  signed_date           date,
  scope_description     text,
  deliverables          text[] not null default '{}'::text[],
  notes                 text,
  is_closed_lost        boolean not null default false,
  is_on_hold            boolean not null default false,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  constraint chk_deals_funnel_stage check (funnel_stage in (
    '潛在客戶', '需求訪談', '提案報價', '合約議價', '導入中', '結案'
  )),
  constraint chk_deals_deal_type check (deal_type is null or deal_type in (
    '一次性專案', '顧問合約', 'Retainer'
  )),
  constraint chk_deals_source_type check (source_type is null or source_type in (
    '轉介紹', '自開發', '合作夥伴', '社群', '活動'
  ))
);
create index if not exists idx_crm_deals_partner       on crm.deals(partner_id);
create index if not exists idx_crm_deals_company       on crm.deals(partner_id, company_id);
create index if not exists idx_crm_deals_stage         on crm.deals(partner_id, funnel_stage);
create index if not exists idx_crm_deals_owner         on crm.deals(partner_id, owner_partner_id);

-- 6. crm.activities
create table if not exists crm.activities (
  id            text primary key,
  partner_id    text not null references zenos.partners(id) on delete cascade,
  deal_id       text not null references crm.deals(id) on delete cascade,
  activity_type text not null,
  activity_at   timestamptz not null default now(),
  summary       text not null,
  recorded_by   text not null references zenos.partners(id),
  is_system     boolean not null default false,
  created_at    timestamptz not null default now(),
  constraint chk_activities_type check (activity_type in (
    '電話', 'Email', '會議', 'Demo', '備忘', '系統'
  ))
);
create index if not exists idx_crm_activities_deal    on crm.activities(deal_id);
create index if not exists idx_crm_activities_partner on crm.activities(partner_id);

commit;
```

---

## 新增 Domain Models

### `src/zenos/domain/crm_models.py`（新檔案）

```python
# Pure dataclasses — zero external dependencies
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional

class FunnelStage(str, Enum):
    PROSPECT     = "潛在客戶"
    DISCOVERY    = "需求訪談"
    PROPOSAL     = "提案報價"
    NEGOTIATION  = "合約議價"
    ONBOARDING   = "導入中"
    CLOSED_WON   = "結案"

class DealType(str, Enum):
    ONE_TIME  = "一次性專案"
    RETAINER  = "顧問合約"
    RETAINER2 = "Retainer"

class DealSource(str, Enum):
    REFERRAL  = "轉介紹"
    OUTBOUND  = "自開發"
    PARTNER   = "合作夥伴"
    COMMUNITY = "社群"
    EVENT     = "活動"

class ActivityType(str, Enum):
    PHONE   = "電話"
    EMAIL   = "Email"
    MEETING = "會議"
    DEMO    = "Demo"
    NOTE    = "備忘"
    SYSTEM  = "系統"

@dataclass
class Company:
    id: str
    partner_id: str
    name: str
    industry: Optional[str] = None
    size_range: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None
    zenos_entity_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now())
    updated_at: datetime = field(default_factory=lambda: datetime.now())

@dataclass
class Contact:
    id: str
    partner_id: str
    company_id: str
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    zenos_entity_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now())
    updated_at: datetime = field(default_factory=lambda: datetime.now())

@dataclass
class Deal:
    id: str
    partner_id: str
    title: str
    company_id: str
    owner_partner_id: str
    funnel_stage: FunnelStage = FunnelStage.PROSPECT
    amount_twd: Optional[int] = None
    deal_type: Optional[DealType] = None
    source_type: Optional[DealSource] = None
    referrer: Optional[str] = None
    expected_close_date: Optional[date] = None
    signed_date: Optional[date] = None
    scope_description: Optional[str] = None
    deliverables: list[str] = field(default_factory=list)
    notes: Optional[str] = None
    is_closed_lost: bool = False
    is_on_hold: bool = False
    last_activity_at: Optional[datetime] = None  # New: Derived from activities
    created_at: datetime = field(default_factory=lambda: datetime.now())
    updated_at: datetime = field(default_factory=lambda: datetime.now())

@dataclass
class Activity:
    id: str
    partner_id: str
    deal_id: str
    activity_type: ActivityType
    activity_at: datetime
    summary: str
    recorded_by: str
    is_system: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now())
```

### 同時修改 `src/zenos/domain/models.py`

`EntityType` enum 加入兩個值：
```python
COMPANY = "company"
PERSON  = "person"
```

---

## Infrastructure Layer

### `src/zenos/infrastructure/crm_sql_repo.py`（新檔案）

`CrmSqlRepository` 類別，包含：
- `create_company(company: Company) -> Company`
- `get_company(partner_id: str, company_id: str) -> Company | None`
- `update_company(company: Company) -> Company`
- `list_companies(partner_id: str) -> list[Company]`
- `create_contact(contact: Contact) -> Contact`
- `get_contact(partner_id: str, contact_id: str) -> Contact | None`
- `update_contact(contact: Contact) -> Contact`
- `list_contacts(partner_id: str, company_id: str) -> list[Contact]`
- `create_deal(deal: Deal) -> Deal`
- `get_deal(partner_id: str, deal_id: str) -> Deal | None`
- `update_deal(deal: Deal) -> Deal`
- `list_deals(partner_id: str, include_inactive: bool = False) -> list[Deal]`
- `create_activity(activity: Activity) -> Activity`
- `list_activities(partner_id: str, deal_id: str) -> list[Activity]`（降序，最新在前）

---

## Application Layer

### `src/zenos/application/crm_service.py`（新檔案）

`CrmService(crm_repo, entity_repo, relationship_repo)` 類別：

#### 核心邏輯：ZenOS L1 Bridge

```python
async def create_company(partner_id, data) -> Company:
    company = await crm_repo.create_company(...)
    # 同步建立 ZenOS L1 entity（type: company）
    entity = await entity_repo.create(Entity(
        id=new_id(),
        partner_id=partner_id,
        name=company.name,
        type="company",
        level=1,
        summary=f"{company.industry or '未分類'} · {company.region or ''}",
        ...
    ))
    # 回填 zenos_entity_id
    company.zenos_entity_id = entity.id
    await crm_repo.update_company(company)
    return company

async def create_contact(partner_id, data) -> Contact:
    contact = await crm_repo.create_contact(...)
    # 同步建立 ZenOS L1 entity（type: person）
    entity = await entity_repo.create(Entity(
        type="person",
        name=contact.name,
        level=1,
        ...
    ))
    # 建立 contact → company 的 relationship（PART_OF）
    company = await crm_repo.get_company(partner_id, contact.company_id)
    if company.zenos_entity_id:
        await relationship_repo.create(Relationship(
            source_entity_id=entity.id,
            target_entity_id=company.zenos_entity_id,
            type=RelationshipType.PART_OF,
            ...
        ))
    contact.zenos_entity_id = entity.id
    await crm_repo.update_contact(contact)
    return contact

async def update_deal_stage(partner_id, deal_id, new_stage, actor_partner_id) -> Deal:
    deal = await crm_repo.get_deal(partner_id, deal_id)
    old_stage = deal.funnel_stage
    deal.funnel_stage = new_stage
    await crm_repo.update_deal(deal)
    # 自動建立系統活動
    await crm_repo.create_activity(Activity(
        deal_id=deal_id,
        activity_type=ActivityType.SYSTEM,
        summary=f"階段從「{old_stage}」更新為「{new_stage}」",
        recorded_by=actor_partner_id,
        is_system=True,
        ...
    ))
    return deal
```

---

## Dashboard REST API

### `src/zenos/interface/crm_dashboard_api.py`（新檔案）

Firebase ID token auth（與 dashboard_api.py 相同機制），回傳 JSON。

#### Endpoints

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/crm/companies` | 列出所有公司 |
| POST | `/api/crm/companies` | 新增公司 |
| GET | `/api/crm/companies/{id}` | 公司詳情 |
| PUT | `/api/crm/companies/{id}` | 更新公司 |
| GET | `/api/crm/companies/{id}/contacts` | 列出公司聯絡人 |
| GET | `/api/crm/companies/{id}/deals` | 列出公司商機 |
| POST | `/api/crm/contacts` | 新增聯絡人 |
| GET | `/api/crm/contacts/{id}` | 聯絡人詳情 |
| PUT | `/api/crm/contacts/{id}` | 更新聯絡人 |
| GET | `/api/crm/deals` | 列出商機（可加 `?include_inactive=true`） |
| POST | `/api/crm/deals` | 新增商機 |
| GET | `/api/crm/deals/{id}` | 商機詳情 |
| PATCH | `/api/crm/deals/{id}/stage` | 更新漏斗階段 |
| POST | `/api/crm/deals/{id}/activities` | 新增活動 |
| GET | `/api/crm/deals/{id}/activities` | 列出活動（降序） |

在 `tools.py` 的 `main()` 中，把 `crm_dashboard_routes` 加入 Starlette routing。

---

## Frontend 設計

### 新增頁面

```
dashboard/src/app/clients/
  layout.tsx           # 客戶模組共用 layout
  page.tsx             # Deal Kanban（主要入口）
  companies/
    page.tsx           # 公司列表
    [id]/
      page.tsx         # 公司詳情（聯絡人列表 + 商機列表 + 知識地圖連結）
  deals/
    [id]/
      page.tsx         # 商機詳情（活動時間軸、漏斗狀態拖曳）
```

### 導覽更新

在現有 Dashboard sidebar/nav 中加入「客戶」tab，路由至 `/clients`。

### Kanban 實作

- 使用 `@dnd-kit/core` + `@dnd-kit/sortable`（與現有 tasks kanban 若有 dnd 則沿用）
- 欄位對應 `FunnelStage`（6 欄 + 可切換的流失/暫緩欄）
- 卡片拖曳觸發 `PATCH /api/crm/deals/{id}/stage`

### API 層

新增 `dashboard/src/lib/crm-api.ts`，使用現有 `apiFetch` 封裝 CRM REST 呼叫。

### P1：上次聯絡日提示

在 Deal 卡片計算 `lastActivity` 與今日差距，超過 14 天顯示橘色標籤。

---

## Spec 介面合約

| 介面 | 參數/行為 | Done Criteria 對應 |
|------|----------|--------------------|
| `create_company()` | 必須建立 ZenOS entity type=company | DC-B1: 新增公司後 zenos.entities 有對應 row |
| `create_contact()` | 必須建立 entity type=person + PART_OF relationship | DC-B2: 新增聯絡人後 relationships 有 PART_OF row |
| `update_deal_stage()` | 必須自動建立 is_system=true Activity | DC-B3: 每次 stage patch 後 activities 有新系統記錄 |
| `list_deals()` | include_inactive=False 時過濾 is_closed_lost & is_on_hold | DC-B4: 預設看板不顯示流失/暫緩商機 |
| `PATCH /stage` | body: `{"stage": "..."}` | DC-F1: 拖曳卡片呼叫此 endpoint 並立即更新看板 |

---

## 任務拆分

| 任務 | plan_id | plan_order | 負責 | Done Criteria |
|------|---------|-----------|------|---------------|
| DB Migration + Backend 實作 | crm-core | 2 | Developer | migration 可執行；Company/Contact/Deal/Activity CRUD；ZenOS L1 bridge；系統活動自動建立；單元測試通過 |
| Frontend 客戶 tab + Kanban + 詳情頁 | crm-core | 3 | Developer | 客戶 tab 可點擊；Kanban 顯示商機；拖曳更新 stage；商機詳情頁含活動時間軸；公司/聯絡人 CRUD |
| QA 端到端驗收 | crm-core | 4 | QA | P0 AC 全部通過；ZenOS L1 bridge 驗證；多用戶共享可見性；QA Verdict: PASS |

---

## 風險與不確定性

### 我不確定的地方

- **zenos_entity_id soft ref**：entities 表有 `(partner_id, id)` composite unique，但 crm.companies.zenos_entity_id 只存 entity.id。若 partner_id 不同，可能查到錯誤 entity。實作時需確保 CrmService 在查詢時帶 partner_id 過濾。
- **dnd-kit 是否已安裝**：現有 dashboard 不確定是否有 drag-and-drop 套件。若沒有，需 `npm install @dnd-kit/core @dnd-kit/sortable`。

### 可能的替代方案

- Kanban 不用 dnd-kit 改用原生 HTML5 DnD API：可減少依賴，但 UX 較差。保留 dnd-kit 方案。

### 需要用戶確認的決策

- 無。三個開放問題已在 ADR-011 決策完畢。

### 最壞情況

- entity type 擴充的 migration 若失敗（DB 連線問題）：會阻塞整個 CRM 上線。**緩解：migration 有 rollback 機制，只影響 CRM 功能，不影響現有 ontology 運作**。
- ZenOS L1 bridge 失敗（entity_repo write error）：目前設計是同步橋接，若 bridge 失敗會導致 company 建立失敗。這是正確行為（維持一致性），錯誤訊息需要清楚。
