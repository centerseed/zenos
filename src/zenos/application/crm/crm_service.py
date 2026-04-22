"""CRM Application Service — business logic for CRM operations.

Orchestrates CrmSqlRepository, SqlEntityRepository, and
SqlRelationshipRepository. Bridges CRM companies and contacts to ZenOS
L1 entities, ensuring the knowledge graph stays consistent with CRM data.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    AiInsight,
    Company,
    Contact,
    Deal,
    FunnelStage,
    InsightStatus,
    InsightType,
)
from zenos.domain.knowledge import Entity, Relationship, Tags
from zenos.domain.knowledge import EntityRepository, RelationshipRepository
from zenos.domain.repositories import CrmRepository

logger = logging.getLogger(__name__)


def _new_id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.split("T", 1)[0])
    except ValueError:
        return None


class CrmService:
    """Application-layer service for CRM operations.

    Constructor accepts repository instances (dependency injection).
    The crm_repo handles CRM tables; entity_repo and relationship_repo
    handle the ZenOS knowledge graph bridge.
    """

    def __init__(
        self,
        crm_repo: CrmRepository,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository,
    ) -> None:
        self._crm = crm_repo
        self._entities = entity_repo
        self._relationships = relationship_repo

    def _build_deal_projection(
        self,
        deal: Deal,
        activities: list[Activity],
        insights: list[AiInsight],
    ) -> tuple[str, dict]:
        manual_activities = [a for a in activities if not a.is_system]
        latest_activity = max(
            manual_activities,
            key=lambda activity: activity.activity_at,
            default=None,
        )

        def _insight_sort_key(insight: AiInsight) -> datetime:
            metadata = insight.metadata if isinstance(insight.metadata, dict) else {}
            saved_at = metadata.get("saved_at") if insight.insight_type == InsightType.BRIEFING else None
            if isinstance(saved_at, str):
                try:
                    parsed = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed
                except ValueError:
                    pass
            return insight.created_at

        briefings = sorted(
            [i for i in insights if i.insight_type == InsightType.BRIEFING],
            key=_insight_sort_key,
            reverse=True,
        )
        debriefs = sorted(
            [i for i in insights if i.insight_type == InsightType.DEBRIEF],
            key=lambda insight: insight.created_at,
            reverse=True,
        )
        commitments = [i for i in insights if i.insight_type == InsightType.COMMITMENT]

        latest_debrief = debriefs[0] if debriefs else None
        latest_briefing_at = _insight_sort_key(briefings[0]) if briefings else None

        next_steps = (
            latest_debrief.metadata.get("next_steps", [])
            if latest_debrief and isinstance(latest_debrief.metadata, dict)
            else []
        )
        if isinstance(next_steps, list):
            latest_next_step = next(
                (str(step).strip() for step in next_steps if str(step).strip()),
                None,
            )
        elif isinstance(next_steps, str) and next_steps.strip():
            latest_next_step = next_steps.strip()
        else:
            latest_next_step = None

        raw_concerns = (
            latest_debrief.metadata.get("customer_concerns", [])
            if latest_debrief and isinstance(latest_debrief.metadata, dict)
            else []
        )
        if isinstance(raw_concerns, list):
            latest_customer_concerns = [str(item).strip() for item in raw_concerns if str(item).strip()]
        elif isinstance(raw_concerns, str) and raw_concerns.strip():
            latest_customer_concerns = [raw_concerns.strip()]
        else:
            latest_customer_concerns = []

        open_commitments = [c for c in commitments if c.status != InsightStatus.DONE]
        today = _now().date()
        overdue_commitments = [
            c for c in open_commitments
            if _parse_iso_date(
                c.metadata.get("deadline") if isinstance(c.metadata, dict) else None
            ) is not None
            and _parse_iso_date(
                c.metadata.get("deadline") if isinstance(c.metadata, dict) else None
            ) < today
        ]

        amount_str = f"NT${deal.amount_twd:,}" if deal.amount_twd is not None else "金額未定"
        summary_parts = [deal.funnel_stage.value, amount_str]
        if latest_activity is not None:
            summary_parts.append(f"最後互動 {latest_activity.activity_at.date().isoformat()}")

        snapshot = {
            "funnel_stage": deal.funnel_stage.value,
            "amount_twd": deal.amount_twd,
            "last_activity_at": _iso_dt(latest_activity.activity_at if latest_activity else None),
            "expected_close_date": _iso_date(deal.expected_close_date),
            "open_commitments_count": len(open_commitments),
            "overdue_commitments_count": len(overdue_commitments),
            "latest_next_step": latest_next_step,
            "latest_customer_concerns": latest_customer_concerns,
            "latest_briefing_at": _iso_dt(latest_briefing_at),
            "latest_debrief_at": _iso_dt(latest_debrief.created_at if latest_debrief else None),
        }
        return " · ".join(summary_parts), snapshot

    async def sync_deal_projection(self, partner_id: str, deal_id: str) -> Entity | None:
        deal = await self._crm.get_deal(partner_id, deal_id)
        if deal is None or not deal.zenos_entity_id:
            return None

        entity = await self._entities.get_by_id(deal.zenos_entity_id)
        if entity is None:
            return None

        activities = await self._crm.list_activities(partner_id, deal_id)
        insights = await self._crm.list_ai_insights_by_deal(partner_id, deal_id)
        summary, crm_snapshot = self._build_deal_projection(deal, activities, insights)

        existing_details = dict(entity.details or {})
        existing_details["crm_snapshot"] = crm_snapshot

        entity.name = deal.title
        entity.summary = summary
        entity.details = existing_details
        return await self._entities.upsert(entity)

    async def _safe_sync_deal_projection(self, partner_id: str, deal_id: str) -> None:
        try:
            await self.sync_deal_projection(partner_id, deal_id)
        except Exception:
            logger.exception(
                "Failed to sync CRM deal projection for partner=%s deal=%s",
                partner_id,
                deal_id,
            )

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
        """Create a deal and bridge it to a ZenOS L1 entity (type=deal)."""
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

        deal = await self._crm.create_deal(deal)

        # Bridge: create ZenOS L1 entity (type=deal)
        summary, crm_snapshot = self._build_deal_projection(deal, [], [])
        entity = await self._entities.upsert(Entity(
            id=_new_id(),
            name=deal.title,
            type="deal",
            level=1,
            summary=summary,
            details={"crm_snapshot": crm_snapshot},
            tags=Tags(what=["deal"], why="CRM 商機", how="crm", who=["業務"]),
            confirmed_by_user=True,
        ))

        # Link deal entity → company entity via PART_OF relationship
        company = await self._crm.get_company(partner_id, deal.company_id)
        if company and company.zenos_entity_id:
            await self._relationships.add(Relationship(
                id=_new_id(),
                source_entity_id=entity.id,
                target_id=company.zenos_entity_id,
                type="part_of",
                description=f"{deal.title} 屬於公司商機",
            ))

        # Back-fill zenos_entity_id
        deal.zenos_entity_id = entity.id
        await self._crm.update_deal(deal)
        return deal

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
        await self._safe_sync_deal_projection(partner_id, deal_id)
        return deal

    async def update_deal(self, partner_id: str, deal_id: str, data: dict) -> Deal:
        """Update mutable deal fields and re-sync the linked ZenOS projection."""
        from datetime import date
        from zenos.domain.crm_models import DealType, DealSource

        deal = await self._crm.get_deal(partner_id, deal_id)
        if deal is None:
            raise ValueError(f"Deal {deal_id} not found")

        if "title" in data and data["title"] is not None:
            deal.title = str(data["title"]).strip() or deal.title
        if "company_id" in data and data["company_id"] is not None:
            deal.company_id = str(data["company_id"]).strip() or deal.company_id
        if "owner_partner_id" in data and data["owner_partner_id"] is not None:
            deal.owner_partner_id = str(data["owner_partner_id"]).strip() or deal.owner_partner_id
        if "funnel_stage" in data and data["funnel_stage"] is not None:
            deal.funnel_stage = FunnelStage(str(data["funnel_stage"]))
        if "amount_twd" in data:
            deal.amount_twd = data["amount_twd"]
        if "deal_type" in data:
            raw_type = data["deal_type"]
            deal.deal_type = DealType(raw_type) if raw_type else None
        if "source_type" in data:
            raw_source = data["source_type"]
            deal.source_type = DealSource(raw_source) if raw_source else None
        if "referrer" in data:
            deal.referrer = data["referrer"]
        if "scope_description" in data:
            deal.scope_description = data["scope_description"]
        if "deliverables" in data and data["deliverables"] is not None:
            deal.deliverables = data["deliverables"]
        if "notes" in data:
            deal.notes = data["notes"]
        if "is_closed_lost" in data:
            deal.is_closed_lost = bool(data["is_closed_lost"])
        if "is_on_hold" in data:
            deal.is_on_hold = bool(data["is_on_hold"])
        if "expected_close_date" in data:
            val = data["expected_close_date"]
            deal.expected_close_date = (
                None
                if val in (None, "", "null")
                else val if isinstance(val, date) else date.fromisoformat(str(val))
            )
        if "signed_date" in data:
            val = data["signed_date"]
            deal.signed_date = (
                None
                if val in (None, "", "null")
                else val if isinstance(val, date) else date.fromisoformat(str(val))
            )

        updated = await self._crm.update_deal(deal)
        await self._safe_sync_deal_projection(partner_id, deal_id)
        return updated

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
        created = await self._crm.create_activity(activity)
        await self._safe_sync_deal_projection(partner_id, deal_id)
        return created

    async def list_activities(self, partner_id: str, deal_id: str) -> list[Activity]:
        return await self._crm.list_activities(partner_id, deal_id)

    # ── AI Insights ────────────────────────────────────────────────────

    async def get_deal_ai_entries(self, partner_id: str, deal_id: str) -> dict:
        """Return AI insights for a deal, categorised by briefing/debrief/commitment."""
        insights = await self._crm.list_ai_insights_by_deal(partner_id, deal_id)
        briefings = [i for i in insights if i.insight_type == InsightType.BRIEFING]
        debriefs = [i for i in insights if i.insight_type == InsightType.DEBRIEF]
        commitments = [i for i in insights if i.insight_type == InsightType.COMMITMENT]
        return {
            "briefings": briefings,
            "debriefs": debriefs,
            "commitments": commitments,
        }

    async def create_ai_insight(self, partner_id: str, data: dict) -> AiInsight:
        """Create an AI insight from a data dict."""
        raw_type = data["insight_type"]
        insight_type = InsightType(raw_type)
        insight = AiInsight(
            id=_new_id(),
            partner_id=partner_id,
            deal_id=data["deal_id"],
            insight_type=insight_type,
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            activity_id=data.get("activity_id"),
            status=(
                InsightStatus.OPEN
                if insight_type == InsightType.COMMITMENT
                else InsightStatus.ACTIVE
            ),
        )
        created = await self._crm.create_ai_insight(insight)
        await self._safe_sync_deal_projection(partner_id, created.deal_id)
        return created

    async def update_briefing(
        self, partner_id: str, insight_id: str, data: dict
    ) -> AiInsight | None:
        """Update a saved briefing snapshot."""
        insight = await self._crm.get_ai_insight(partner_id, insight_id)
        if insight is None:
            return None
        if insight.insight_type != InsightType.BRIEFING:
            raise ValueError("Only briefing insights can be updated via this endpoint")

        insight.content = data.get("content", insight.content)
        metadata = data.get("metadata")
        if metadata is not None:
            insight.metadata = metadata
        updated = await self._crm.update_ai_insight(insight)
        if updated is not None:
            await self._safe_sync_deal_projection(partner_id, updated.deal_id)
        return updated

    async def delete_briefing(self, partner_id: str, insight_id: str) -> bool:
        """Delete a saved briefing snapshot."""
        insight = await self._crm.get_ai_insight(partner_id, insight_id)
        if insight is None:
            return False
        if insight.insight_type != InsightType.BRIEFING:
            raise ValueError("Only briefing insights can be deleted via this endpoint")
        deleted = await self._crm.delete_ai_insight(partner_id, insight_id)
        if deleted:
            await self._safe_sync_deal_projection(partner_id, insight.deal_id)
        return deleted

    async def update_commitment_status(
        self, partner_id: str, insight_id: str, status: str
    ) -> AiInsight | None:
        """Update commitment status. Only 'open' and 'done' are allowed."""
        if status not in ("open", "done"):
            raise ValueError(f"Invalid status '{status}': only 'open' and 'done' are allowed")
        updated = await self._crm.update_ai_insight_status(partner_id, insight_id, status)
        if updated is not None:
            await self._safe_sync_deal_projection(partner_id, updated.deal_id)
        return updated
