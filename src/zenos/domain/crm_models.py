"""CRM Domain Models — pure dataclasses, zero external dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional


class FunnelStage(str, Enum):
    PROSPECT    = "潛在客戶"
    DISCOVERY   = "需求訪談"
    PROPOSAL    = "提案報價"
    NEGOTIATION = "合約議價"
    ONBOARDING  = "導入中"
    CLOSED_WON  = "結案"


class DealType(str, Enum):
    ONE_TIME    = "一次性專案"
    CONSULTING  = "顧問合約"
    RETAINER    = "Retainer"


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
    """A CRM company record, bridged to a ZenOS L1 entity."""

    id: str
    partner_id: str
    name: str
    industry: Optional[str] = None
    size_range: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None
    zenos_entity_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Contact:
    """A CRM contact (person) attached to a company."""

    id: str
    partner_id: str
    company_id: str
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    zenos_entity_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Deal:
    """A sales deal / opportunity attached to a company."""

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
    zenos_entity_id: Optional[str] = None
    is_closed_lost: bool = False
    is_on_hold: bool = False
    last_activity_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Activity:
    """A log entry for an interaction related to a deal."""

    id: str
    partner_id: str
    deal_id: str
    activity_type: ActivityType
    activity_at: datetime
    summary: str
    recorded_by: str
    is_system: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InsightType(str, Enum):
    BRIEFING   = "briefing"
    DEBRIEF    = "debrief"
    COMMITMENT = "commitment"


class InsightStatus(str, Enum):
    ACTIVE   = "active"
    OPEN     = "open"
    DONE     = "done"
    ARCHIVED = "archived"


@dataclass
class AiInsight:
    """A CRM AI insight (briefing/debrief/commitment) attached to a deal."""

    id: str
    partner_id: str
    deal_id: str
    insight_type: InsightType
    content: str = ""
    metadata: dict = field(default_factory=dict)
    activity_id: Optional[str] = None
    status: InsightStatus = InsightStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
