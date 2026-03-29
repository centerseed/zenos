"""PostgreSQL implementation of the CRM repository.

All tables live under the ``crm`` schema. Every method receives
``partner_id`` as an explicit argument for multi-tenant isolation.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    DealSource,
    DealType,
    FunnelStage,
)

CRM_SCHEMA = "crm"


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    return None


def _to_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return None


def _row_to_company(row: asyncpg.Record) -> Company:
    return Company(
        id=row["id"],
        partner_id=row["partner_id"],
        name=row["name"],
        industry=row["industry"],
        size_range=row["size_range"],
        region=row["region"],
        notes=row["notes"],
        zenos_entity_id=row["zenos_entity_id"],
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


def _row_to_contact(row: asyncpg.Record) -> Contact:
    return Contact(
        id=row["id"],
        partner_id=row["partner_id"],
        company_id=row["company_id"],
        name=row["name"],
        title=row["title"],
        email=row["email"],
        phone=row["phone"],
        notes=row["notes"],
        zenos_entity_id=row["zenos_entity_id"],
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


def _row_to_deal(row: asyncpg.Record) -> Deal:
    raw_stage = row["funnel_stage"]
    raw_type = row["deal_type"]
    raw_source = row["source_type"]
    return Deal(
        id=row["id"],
        partner_id=row["partner_id"],
        title=row["title"],
        company_id=row["company_id"],
        owner_partner_id=row["owner_partner_id"],
        funnel_stage=FunnelStage(raw_stage) if raw_stage else FunnelStage.PROSPECT,
        amount_twd=row["amount_twd"],
        deal_type=DealType(raw_type) if raw_type else None,
        source_type=DealSource(raw_source) if raw_source else None,
        referrer=row["referrer"],
        expected_close_date=_to_date(row["expected_close_date"]),
        signed_date=_to_date(row["signed_date"]),
        scope_description=row["scope_description"],
        deliverables=list(row["deliverables"] or []),
        notes=row["notes"],
        is_closed_lost=row["is_closed_lost"],
        is_on_hold=row["is_on_hold"],
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


def _row_to_activity(row: asyncpg.Record) -> Activity:
    raw_type = row["activity_type"]
    return Activity(
        id=row["id"],
        partner_id=row["partner_id"],
        deal_id=row["deal_id"],
        activity_type=ActivityType(raw_type),
        activity_at=_to_dt(row["activity_at"]) or _now(),
        summary=row["summary"],
        recorded_by=row["recorded_by"],
        is_system=row["is_system"],
        created_at=_to_dt(row["created_at"]) or _now(),
    )


class CrmSqlRepository:
    """PostgreSQL-backed CRM repository for companies, contacts, deals, activities."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Companies ──────────────────────────────────────────────────────

    async def create_company(self, company: Company) -> Company:
        """Insert a new company row. Sets id/timestamps if not provided."""
        now = _now()
        if not company.id:
            company.id = _new_id()
        company.created_at = now
        company.updated_at = now

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {CRM_SCHEMA}.companies
                  (id, partner_id, name, industry, size_range, region, notes,
                   zenos_entity_id, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                """,
                company.id, company.partner_id, company.name,
                company.industry, company.size_range, company.region,
                company.notes, company.zenos_entity_id,
                company.created_at, company.updated_at,
            )
        return company

    async def get_company(self, partner_id: str, company_id: str) -> Company | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {CRM_SCHEMA}.companies WHERE id=$1 AND partner_id=$2",
                company_id, partner_id,
            )
        return _row_to_company(row) if row else None

    async def update_company(self, company: Company) -> Company:
        company.updated_at = _now()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {CRM_SCHEMA}.companies
                SET name=$1, industry=$2, size_range=$3, region=$4, notes=$5,
                    zenos_entity_id=$6, updated_at=$7
                WHERE id=$8 AND partner_id=$9
                """,
                company.name, company.industry, company.size_range,
                company.region, company.notes, company.zenos_entity_id,
                company.updated_at, company.id, company.partner_id,
            )
        return company

    async def list_companies(self, partner_id: str) -> list[Company]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {CRM_SCHEMA}.companies WHERE partner_id=$1 ORDER BY name",
                partner_id,
            )
        return [_row_to_company(r) for r in rows]

    # ── Contacts ───────────────────────────────────────────────────────

    async def create_contact(self, contact: Contact) -> Contact:
        now = _now()
        if not contact.id:
            contact.id = _new_id()
        contact.created_at = now
        contact.updated_at = now

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {CRM_SCHEMA}.contacts
                  (id, partner_id, company_id, name, title, email, phone, notes,
                   zenos_entity_id, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                """,
                contact.id, contact.partner_id, contact.company_id,
                contact.name, contact.title, contact.email, contact.phone,
                contact.notes, contact.zenos_entity_id,
                contact.created_at, contact.updated_at,
            )
        return contact

    async def get_contact(self, partner_id: str, contact_id: str) -> Contact | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {CRM_SCHEMA}.contacts WHERE id=$1 AND partner_id=$2",
                contact_id, partner_id,
            )
        return _row_to_contact(row) if row else None

    async def update_contact(self, contact: Contact) -> Contact:
        contact.updated_at = _now()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {CRM_SCHEMA}.contacts
                SET name=$1, title=$2, email=$3, phone=$4, notes=$5,
                    zenos_entity_id=$6, updated_at=$7
                WHERE id=$8 AND partner_id=$9
                """,
                contact.name, contact.title, contact.email, contact.phone,
                contact.notes, contact.zenos_entity_id,
                contact.updated_at, contact.id, contact.partner_id,
            )
        return contact

    async def list_contacts(
        self, partner_id: str, company_id: str | None = None
    ) -> list[Contact]:
        """List contacts, optionally filtered by company_id."""
        async with self._pool.acquire() as conn:
            if company_id:
                rows = await conn.fetch(
                    f"""SELECT * FROM {CRM_SCHEMA}.contacts
                        WHERE partner_id=$1 AND company_id=$2 ORDER BY name""",
                    partner_id, company_id,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT * FROM {CRM_SCHEMA}.contacts WHERE partner_id=$1 ORDER BY name",
                    partner_id,
                )
        return [_row_to_contact(r) for r in rows]

    # ── Deals ──────────────────────────────────────────────────────────

    async def create_deal(self, deal: Deal) -> Deal:
        now = _now()
        if not deal.id:
            deal.id = _new_id()
        deal.created_at = now
        deal.updated_at = now

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {CRM_SCHEMA}.deals
                  (id, partner_id, title, company_id, owner_partner_id,
                   funnel_stage, amount_twd, deal_type, source_type, referrer,
                   expected_close_date, signed_date, scope_description,
                   deliverables, notes, is_closed_lost, is_on_hold,
                   created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                """,
                deal.id, deal.partner_id, deal.title, deal.company_id,
                deal.owner_partner_id, deal.funnel_stage.value,
                deal.amount_twd,
                deal.deal_type.value if deal.deal_type else None,
                deal.source_type.value if deal.source_type else None,
                deal.referrer, deal.expected_close_date, deal.signed_date,
                deal.scope_description, deal.deliverables, deal.notes,
                deal.is_closed_lost, deal.is_on_hold,
                deal.created_at, deal.updated_at,
            )
        return deal

    async def get_deal(self, partner_id: str, deal_id: str) -> Deal | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {CRM_SCHEMA}.deals WHERE id=$1 AND partner_id=$2",
                deal_id, partner_id,
            )
        return _row_to_deal(row) if row else None

    async def update_deal(self, deal: Deal) -> Deal:
        deal.updated_at = _now()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {CRM_SCHEMA}.deals
                SET title=$1, funnel_stage=$2, amount_twd=$3, deal_type=$4,
                    source_type=$5, referrer=$6, expected_close_date=$7,
                    signed_date=$8, scope_description=$9, deliverables=$10,
                    notes=$11, is_closed_lost=$12, is_on_hold=$13, updated_at=$14
                WHERE id=$15 AND partner_id=$16
                """,
                deal.title, deal.funnel_stage.value, deal.amount_twd,
                deal.deal_type.value if deal.deal_type else None,
                deal.source_type.value if deal.source_type else None,
                deal.referrer, deal.expected_close_date, deal.signed_date,
                deal.scope_description, deal.deliverables, deal.notes,
                deal.is_closed_lost, deal.is_on_hold, deal.updated_at,
                deal.id, deal.partner_id,
            )
        return deal

    async def list_deals(
        self, partner_id: str, include_inactive: bool = False
    ) -> list[Deal]:
        """List deals. By default, excludes closed-lost and on-hold deals."""
        async with self._pool.acquire() as conn:
            if include_inactive:
                rows = await conn.fetch(
                    f"""SELECT * FROM {CRM_SCHEMA}.deals
                        WHERE partner_id=$1 ORDER BY created_at DESC""",
                    partner_id,
                )
            else:
                rows = await conn.fetch(
                    f"""SELECT * FROM {CRM_SCHEMA}.deals
                        WHERE partner_id=$1
                          AND is_closed_lost = false
                          AND is_on_hold = false
                        ORDER BY created_at DESC""",
                    partner_id,
                )
        return [_row_to_deal(r) for r in rows]

    # ── Activities ─────────────────────────────────────────────────────

    async def create_activity(self, activity: Activity) -> Activity:
        now = _now()
        if not activity.id:
            activity.id = _new_id()
        activity.created_at = now

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {CRM_SCHEMA}.activities
                  (id, partner_id, deal_id, activity_type, activity_at,
                   summary, recorded_by, is_system, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                """,
                activity.id, activity.partner_id, activity.deal_id,
                activity.activity_type.value, activity.activity_at,
                activity.summary, activity.recorded_by, activity.is_system,
                activity.created_at,
            )
        return activity

    async def list_activities(
        self, partner_id: str, deal_id: str
    ) -> list[Activity]:
        """List activities for a deal, sorted by activity_at DESC (newest first)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {CRM_SCHEMA}.activities
                    WHERE partner_id=$1 AND deal_id=$2
                    ORDER BY activity_at DESC""",
                partner_id, deal_id,
            )
        return [_row_to_activity(r) for r in rows]
