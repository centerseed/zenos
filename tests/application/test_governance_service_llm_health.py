from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from zenos.application.knowledge.governance_service import GovernanceService
from zenos.domain.knowledge import Blindspot, Entity, Protocol, Tags


def _entity(entity_id: str = "ent-1") -> Entity:
    now = datetime.now(timezone.utc)
    return Entity(
        id=entity_id,
        name="Quality Intelligence",
        type="module",
        summary="Tracks governance quality.",
        tags=Tags(what=["signals"], why="quality", how="analyze", who=["PM"]),
        status="active",
        confirmed_by_user=True,
        created_at=now,
        updated_at=now,
    )


def _blindspot() -> Blindspot:
    return Blindspot(
        description="issue",
        severity="yellow",
        related_entity_ids=["ent-1"],
        suggested_action="fix",
        confirmed_by_user=False,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_analyze_llm_health_reports_provider_and_findings():
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()
    protocol_repo = AsyncMock()
    blindspot_repo = AsyncMock()
    usage_logs = AsyncMock()
    usage_logs.summarize_provider_health = AsyncMock(return_value=[
        {
            "provider": "gemini",
            "model": "gemini/gemini-2.5-flash-lite",
            "success_count_7d": 1,
            "fallback_count_7d": 3,
            "exception_count_7d": 1,
            "last_success_at": datetime.now(timezone.utc),
            "success_count_1h": 0,
            "fallback_count_1h": 0,
            "exception_count_1h": 0,
        }
    ])
    governance_ai = SimpleNamespace(
        _llm=SimpleNamespace(model="gemini/gemini-2.5-flash-lite", api_key="key"),
    )
    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
        usage_log_repo=usage_logs,
        governance_ai=governance_ai,
    )

    result = await service.analyze_llm_health("partner-1")

    assert result["check_type"] == "llm_health"
    assert result["provider_status"][0]["name"] == "gemini"
    assert result["provider_status"][0]["fallback_count_7d"] == 3
    assert any(item["path_category"] == "critical" for item in result["dependency_points"])
    assert any(item["type"] == "critical_path_llm_dependency" for item in result["findings"])


@pytest.mark.asyncio
async def test_compute_health_signal_includes_llm_health_kpi(monkeypatch):
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()
    protocol_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    entity_repo.list_all = AsyncMock(return_value=[_entity()])
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=Protocol(
        entity_id="ent-1",
        entity_name="Quality Intelligence",
        content={"what": {}, "why": {}, "how": {}, "who": {}},
        confirmed_by_user=True,
        generated_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ))
    blindspot_repo.list_all = AsyncMock(return_value=[_blindspot()])

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )
    service.analyze_llm_health = AsyncMock(return_value={
        "check_type": "llm_health",
        "provider_status": [],
        "dependency_points": [],
        "findings": [
            {
                "severity": "red",
                "type": "provider_down",
                "location": "gemini",
                "description": "API key missing",
            }
        ],
        "overall_level": "red",
    })

    monkeypatch.setattr(
        "zenos.infrastructure.context.current_partner_id",
        SimpleNamespace(get=lambda: "partner-1"),
    )

    result = await service.compute_health_signal()

    assert result["kpis"]["llm_health"]["level"] == "red"
    assert result["overall_level"] == "red"
    assert any(item["kpi"] == "llm_health" for item in result["red_reasons"])


@pytest.mark.asyncio
async def test_compute_health_signal_includes_bundle_highlights_coverage(monkeypatch):
    now = datetime.now(timezone.utc)
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()
    protocol_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    entity_repo.list_all = AsyncMock(return_value=[
        _entity(),
        Entity(
            id="doc-1",
            name="Bundle A",
            type="document",
            summary="indexed doc",
            tags=Tags(what=["spec"], why="share", how="index", who=["PM"]),
            status="current",
            confirmed_by_user=True,
            created_at=now,
            updated_at=now,
            doc_role="index",
            bundle_highlights=[{
                "source_id": "src-1",
                "headline": "Primary",
                "reason_to_read": "Read this first",
                "priority": "primary",
            }],
        ),
        Entity(
            id="doc-2",
            name="Bundle B",
            type="document",
            summary="indexed doc",
            tags=Tags(what=["spec"], why="share", how="index", who=["PM"]),
            status="current",
            confirmed_by_user=True,
            created_at=now,
            updated_at=now,
            doc_role="index",
            bundle_highlights=[],
        ),
    ])
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)
    blindspot_repo.list_all = AsyncMock(return_value=[])

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )
    service.analyze_llm_health = AsyncMock(return_value={
        "check_type": "llm_health",
        "provider_status": [],
        "dependency_points": [],
        "findings": [],
        "overall_level": "green",
    })

    monkeypatch.setattr(
        "zenos.infrastructure.context.current_partner_id",
        SimpleNamespace(get=lambda: "partner-1"),
    )

    result = await service.compute_health_signal()

    assert result["kpis"]["bundle_highlights_coverage"]["value"] == 0.5
    assert result["kpis"]["bundle_highlights_coverage"]["level"] == "yellow"


@pytest.mark.asyncio
async def test_compute_health_signal_includes_governance_ssot(monkeypatch):
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()
    protocol_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    entity_repo.list_all = AsyncMock(return_value=[_entity()])
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)
    blindspot_repo.list_all = AsyncMock(return_value=[])

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )
    service.analyze_llm_health = AsyncMock(return_value={
        "check_type": "llm_health",
        "provider_status": [],
        "dependency_points": [],
        "findings": [],
        "overall_level": "green",
    })

    monkeypatch.setattr(
        "zenos.infrastructure.context.current_partner_id",
        SimpleNamespace(get=lambda: "partner-1"),
    )
    monkeypatch.setattr(
        "zenos.application.knowledge.governance_service.run_governance_ssot_audit",
        lambda: {
            "check_type": "governance_ssot",
            "findings": [{
                "severity": "red",
                "type": "spec_server_rules_drift",
                "diff_summary": "drift",
            }],
            "overall_level": "red",
        },
    )

    result = await service.compute_health_signal()

    assert result["kpis"]["governance_ssot"]["level"] == "red"
    assert result["governance_ssot"]["overall_level"] == "red"
    assert any(item["kpi"] == "governance_ssot" for item in result["red_reasons"])


@pytest.mark.asyncio
async def test_analyze_llm_health_treats_literal_none_key_as_missing():
    usage_logs = AsyncMock()
    usage_logs.summarize_provider_health = AsyncMock(return_value=[])
    service = GovernanceService(
        entity_repo=AsyncMock(),
        relationship_repo=AsyncMock(),
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
        usage_log_repo=usage_logs,
        governance_ai=SimpleNamespace(
            _llm=SimpleNamespace(model="gemini/gemini-2.5-flash-lite", api_key="None"),
        ),
    )

    result = await service.analyze_llm_health("partner-1")

    assert result["provider_status"][0]["status"] == "down"
    assert "API key missing" in result["provider_status"][0]["notes"]
