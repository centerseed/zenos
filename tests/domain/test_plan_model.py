"""Tests for Plan domain model and PlanStatus enum."""

from __future__ import annotations

from datetime import datetime

import pytest

from zenos.domain.action import Plan, PlanStatus


def test_plan_status_values():
    assert PlanStatus.DRAFT == "draft"
    assert PlanStatus.ACTIVE == "active"
    assert PlanStatus.COMPLETED == "completed"
    assert PlanStatus.CANCELLED == "cancelled"


def test_plan_creation_with_required_fields():
    plan = Plan(goal="Ship v1 feature", status="draft", created_by="pm")
    assert plan.goal == "Ship v1 feature"
    assert plan.status == "draft"
    assert plan.created_by == "pm"
    assert plan.id is None
    assert plan.owner is None
    assert plan.entry_criteria is None
    assert plan.exit_criteria is None
    assert plan.project == ""
    assert plan.result is None


def test_plan_creation_with_all_fields():
    plan = Plan(
        goal="Implement Plan primitive",
        status=PlanStatus.ACTIVE,
        created_by="architect",
        id="plan-001",
        owner="tech-lead",
        entry_criteria="ADR approved",
        exit_criteria="All tasks done and QA passed",
        project="zenos",
        product_id="entity-zenos",
        updated_by="architect",
        result=None,
    )
    assert plan.id == "plan-001"
    assert plan.status == PlanStatus.ACTIVE
    assert plan.owner == "tech-lead"
    assert plan.project == "zenos"
    assert plan.product_id == "entity-zenos"


def test_plan_timestamps_default_to_utcnow():
    before = datetime.utcnow()
    plan = Plan(goal="G", status="draft", created_by="u")
    after = datetime.utcnow()
    assert before <= plan.created_at <= after
    assert before <= plan.updated_at <= after


def test_plan_status_is_string_enum():
    """PlanStatus values must be interchangeable with plain strings."""
    plan = Plan(goal="G", status=PlanStatus.DRAFT, created_by="u")
    assert plan.status == "draft"
    assert isinstance(plan.status, str)


def test_plan_result_starts_none():
    plan = Plan(goal="G", status="draft", created_by="u")
    assert plan.result is None


def test_plan_product_id_optional():
    plan = Plan(goal="G", status="draft", created_by="u")
    assert plan.product_id is None


def test_plan_project_id_alias_writes_back_to_product_id():
    plan = Plan(goal="G", status="draft", created_by="u")
    plan.project_id = "prod-1"
    assert plan.product_id == "prod-1"
    assert plan.project_id == "prod-1"
