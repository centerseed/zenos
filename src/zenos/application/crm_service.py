"""CRM Application Service — business logic for CRM operations.

Orchestrates CrmSqlRepository, SqlEntityRepository, and
SqlRelationshipRepository. Bridges CRM companies and contacts to ZenOS
L1 entities, ensuring the knowledge graph stays consistent with CRM data.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    FunnelStage,
)
from zenos.domain.models import Entity, Relationship, Tags


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CrmService:
    """Application-layer service for CRM operations.

    Constructor accepts repository instances (dependency injection).
    The crm_repo handles CRM tables; entity_repo and relationship_repo
    handle the ZenOS knowledge graph bridge.
    """

    def __init__(self, crm_repo: Any, entity_repo: Any, relationship_repo: Any) -> None:
        self._crm = crm_repo
        self._entities = entity_repo
        self._relationships = relationship_repo

    # ── Companies ──────────────────────────────────────────────────────

    async def create_company(self, partner_id: str, data: dict) -> Company:
        """Create a company and bridge it to a ZenOS L1 entity (type=company)."""
        company = Company(
            id=_new_id(),
            partner_id=partner_id,
            name=data["name"],
            industry=data.get("industry"),
            size_range=data.get("size_range"),
            region=data.get("region"),
            notes=data.get("notes"),
        )
        company = await self._crm.create_company(company)

        # Bridge: create ZenOS L1 entity
        entity = await self._entities.upsert(Entity(
            id=_new_id(),
            name=company.name,
            type="company",
            level=1,
            summary=f"{company.industry or '未分類'} · {company.region or ''}".strip(" ·"),
            tags=Tags(what=["company"], why="CRM 客戶公司", how="crm", who=["業務"]),
            confirmed_by_user=True,
        ))

        # Back-fill zenos_entity_id
        company.zenos_entity_id = entity.id
        await self._crm.update_company(company)
        return company

    async def update_company(self, partner_id: str, company_id: str, data: dict) -> Company:
        """Update company fields and sync to ZenOS entity."""
        company = await self._crm.get_company(partner_id, company_id)
        if company is None:
            raise ValueError(f"Company {company_id} not found")

        company.name = data.get("name", company.name)
        company.industry = data.get("industry", company.industry)
        company.size_range = data.get("size_range", company.size_range)
        company.region = data.get("region", company.region)
        company.notes = data.get("notes", company.notes)
        company = await self._crm.update_company(company)

        # Sync ZenOS entity if linked
        if company.zenos_entity_id:
            entity = await self._entities.get_by_id(company.zenos_entity_id)
            if entity:
                entity.name = company.name
                entity.summary = f"{company.industry or '未分類'} · {company.region or ''}".strip(" ·")
                await self._entities.upsert(entity)

        return company

    async def get_company(self, partner_id: str, company_id: str) -> Company | None:
        return await self._crm.get_company(partner_id, company_id)

    async def list_companies(self, partner_id: str) -> list[Company]:
        return await self._crm.list_companies(partner_id)

    # ── Contacts ───────────────────────────────────────────────────────

    async def create_contact(self, partner_id: str, data: dict) -> Contact:
        """Create a contact, bridge to ZenOS entity, and link to company entity."""
        contact = Contact(
            id=_new_id(),
            partner_id=partner_id,
            company_id=data["company_id"],
            name=data["name"],
            title=data.get("title"),
            email=data.get("email"),
            phone=data.get("phone"),
            notes=data.get("notes"),
        )
        contact = await self._crm.create_contact(contact)

        # Bridge: create ZenOS L1 entity (type=person)
        entity = await self._entities.upsert(Entity(
            id=_new_id(),
            name=contact.name,
            type="person",
            level=1,
            summary=f"{contact.title or '聯絡人'} @ {contact.company_id}",
            tags=Tags(what=["person"], why="CRM 聯絡人", how="crm", who=["業務"]),
            confirmed_by_user=True,
        ))

        # Link contact entity → company entity via PART_OF relationship
        company = await self._crm.get_company(partner_id, contact.company_id)
        if company and company.zenos_entity_id:
            await self._relationships.add(Relationship(
                id=_new_id(),
                source_entity_id=entity.id,
                target_id=company.zenos_entity_id,
                type="part_of",
                description=f"{contact.name} 隸屬於公司",
            ))

        # Back-fill zenos_entity_id
        contact.zenos_entity_id = entity.id
        await self._crm.update_contact(contact)
        return contact

    async def update_contact(self, partner_id: str, contact_id: str, data: dict) -> Contact:
        """Update contact fields and sync to ZenOS entity."""
        contact = await self._crm.get_contact(partner_id, contact_id)
        if contact is None:
            raise ValueError(f"Contact {contact_id} not found")

        contact.name = data.get("name", contact.name)
        contact.title = data.get("title", contact.title)
        contact.email = data.get("email", contact.email)
        contact.phone = data.get("phone", contact.phone)
        contact.notes = data.get("notes", contact.notes)
        contact = await self._crm.update_contact(contact)

        # Sync ZenOS entity if linked
        if contact.zenos_entity_id:
            entity = await self._entities.get_by_id(contact.zenos_entity_id)
            if entity:
                entity.name = contact.name
                entity.summary = f"{contact.title or '聯絡人'} @ {contact.company_id}"
                await self._entities.upsert(entity)

        return contact

    async def get_contact(self, partner_id: str, contact_id: str) -> Contact | None:
        return await self._crm.get_contact(partner_id, contact_id)

    async def list_contacts(
        self, partner_id: str, company_id: str | None = None
    ) -> list[Contact]:
        return await self._crm.list_contacts(partner_id, company_id)

    # ── Deals ──────────────────────────────────────────────────────────

    async def create_deal(self, partner_id: str, data: dict) -> Deal:
        """Create a deal (pure CRM, no entity bridge)."""
        from zenos.domain.crm_models import DealType, DealSource

        raw_stage = data.get("funnel_stage", FunnelStage.PROSPECT.value)
        raw_type = data.get("deal_type")
        raw_source = data.get("source_type")

        deal = Deal(
            id=_new_id(),
            partner_id=partner_id,
            title=data["title"],
            company_id=data["company_id"],
            owner_partner_id=data.get("owner_partner_id", partner_id),
            funnel_stage=FunnelStage(raw_stage),
            amount_twd=data.get("amount_twd"),
            deal_type=DealType(raw_type) if raw_type else None,
            source_type=DealSource(raw_source) if raw_source else None,
            referrer=data.get("referrer"),
            scope_description=data.get("scope_description"),
            deliverables=data.get("deliverables", []),
            notes=data.get("notes"),
        )

        # Handle optional date fields
        if data.get("expected_close_date"):
            from datetime import date
            val = data["expected_close_date"]
            deal.expected_close_date = (
                val if isinstance(val, date) else date.fromisoformat(str(val))
            )
        if data.get("signed_date"):
            from datetime import date
            val = data["signed_date"]
            deal.signed_date = (
                val if isinstance(val, date) else date.fromisoformat(str(val))
            )

        return await self._crm.create_deal(deal)

    async def update_deal_stage(
        self, partner_id: str, deal_id: str, new_stage: str, actor_partner_id: str
    ) -> Deal:
        """Update funnel stage and auto-create a system activity recording the change."""
        deal = await self._crm.get_deal(partner_id, deal_id)
        if deal is None:
            raise ValueError(f"Deal {deal_id} not found")

        old_stage = deal.funnel_stage.value
        deal.funnel_stage = FunnelStage(new_stage)
        await self._crm.update_deal(deal)

        # Auto-create system activity
        activity = Activity(
            id=_new_id(),
            partner_id=partner_id,
            deal_id=deal_id,
            activity_type=ActivityType.SYSTEM,
            activity_at=_now(),
            summary=f"階段從「{old_stage}」更新為「{new_stage}」",
            recorded_by=actor_partner_id,
            is_system=True,
        )
        await self._crm.create_activity(activity)
        return deal

    async def get_deal(self, partner_id: str, deal_id: str) -> Deal | None:
        return await self._crm.get_deal(partner_id, deal_id)

    async def list_deals(
        self, partner_id: str, include_inactive: bool = False
    ) -> list[Deal]:
        return await self._crm.list_deals(partner_id, include_inactive)

    # ── Activities ─────────────────────────────────────────────────────

    async def create_activity(self, partner_id: str, deal_id: str, data: dict) -> Activity:
        """Create a manual activity log entry."""
        raw_type = data.get("activity_type", ActivityType.NOTE.value)
        activity_at_raw = data.get("activity_at")
        if activity_at_raw:
            if isinstance(activity_at_raw, datetime):
                activity_at = activity_at_raw
            else:
                activity_at = datetime.fromisoformat(str(activity_at_raw))
                if activity_at.tzinfo is None:
                    activity_at = activity_at.replace(tzinfo=timezone.utc)
        else:
            activity_at = _now()

        activity = Activity(
            id=_new_id(),
            partner_id=partner_id,
            deal_id=deal_id,
            activity_type=ActivityType(raw_type),
            activity_at=activity_at,
            summary=data["summary"],
            recorded_by=data.get("recorded_by", partner_id),
            is_system=False,
        )
        return await self._crm.create_activity(activity)

    async def list_activities(self, partner_id: str, deal_id: str) -> list[Activity]:
        return await self._crm.list_activities(partner_id, deal_id)
