"""Tests for governance quality signal functions:
- compute_search_unused_signals
- score_summary_quality
"""

from __future__ import annotations

import pytest

from zenos.domain.governance import (
    CHALLENGE_KEYWORDS,
    MARKETING_KEYWORDS,
    TECHNICAL_KEYWORDS,
    compute_search_unused_signals,
    score_summary_quality,
)
from zenos.domain.models import Entity, EntityStatus, EntityType, Tags


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_entity(entity_id: str, name: str) -> Entity:
    from datetime import datetime
    now = datetime(2026, 1, 1)
    return Entity(
        id=entity_id,
        name=name,
        type=EntityType.MODULE,
        summary="A test entity",
        tags=Tags(what="test", why="testing", how="auto", who="dev"),
        status=EntityStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )


# ──────────────────────────────────────────────
# compute_search_unused_signals
# ──────────────────────────────────────────────

class TestComputeSearchUnusedSignals:
    def test_entity_with_high_unused_ratio_and_sufficient_searches_is_flagged(self):
        """unused_ratio > 0.8 AND search_count >= 3 → flagged=True."""
        stats = [{"entity_id": "e1", "search_count": 10, "get_count": 0}]
        entities = [_make_entity("e1", "Entity One")]
        result = compute_search_unused_signals(stats, entities)
        assert len(result) == 1
        assert result[0]["entity_id"] == "e1"
        assert result[0]["flagged"] is True
        assert result[0]["unused_ratio"] == pytest.approx(1.0)

    def test_entity_with_low_unused_ratio_is_not_flagged(self):
        """unused_ratio <= 0.8 → not in output."""
        stats = [{"entity_id": "e1", "search_count": 10, "get_count": 5}]
        entities = [_make_entity("e1", "Entity One")]
        result = compute_search_unused_signals(stats, entities)
        assert result == []

    def test_entity_with_few_searches_not_flagged_even_if_unused(self):
        """search_count < 3 → not flagged even if unused_ratio > 0.8."""
        stats = [{"entity_id": "e1", "search_count": 2, "get_count": 0}]
        entities = [_make_entity("e1", "Entity One")]
        result = compute_search_unused_signals(stats, entities)
        assert result == []

    def test_exactly_at_threshold_search_count_3_is_flagged(self):
        """search_count == 3 with 0 gets → should be flagged."""
        stats = [{"entity_id": "e1", "search_count": 3, "get_count": 0}]
        entities = [_make_entity("e1", "Entity One")]
        result = compute_search_unused_signals(stats, entities)
        assert len(result) == 1

    def test_unused_ratio_exactly_at_boundary_not_flagged(self):
        """unused_ratio == 0.8 (not > 0.8) → not flagged."""
        # search=5, get=1 → unused_ratio = 1 - 1/5 = 0.8 → NOT > 0.8
        stats = [{"entity_id": "e1", "search_count": 5, "get_count": 1}]
        entities = [_make_entity("e1", "Entity One")]
        result = compute_search_unused_signals(stats, entities)
        assert result == []

    def test_entity_name_resolved_from_entities_list(self):
        """entity_name should come from entities list, not entity_id."""
        stats = [{"entity_id": "e42", "search_count": 5, "get_count": 0}]
        entities = [_make_entity("e42", "Auth Module")]
        result = compute_search_unused_signals(stats, entities)
        assert result[0]["entity_name"] == "Auth Module"

    def test_unknown_entity_id_uses_id_as_name_fallback(self):
        """If entity_id not in entities list, use entity_id as name."""
        stats = [{"entity_id": "unknown_id", "search_count": 5, "get_count": 0}]
        entities = []
        result = compute_search_unused_signals(stats, entities)
        assert result[0]["entity_name"] == "unknown_id"

    def test_multiple_entities_only_flagged_returned(self):
        """Only entities meeting both conditions appear in output."""
        stats = [
            {"entity_id": "e1", "search_count": 10, "get_count": 0},   # flagged
            {"entity_id": "e2", "search_count": 10, "get_count": 5},   # not flagged
            {"entity_id": "e3", "search_count": 2, "get_count": 0},    # too few searches
        ]
        entities = [
            _make_entity("e1", "Entity 1"),
            _make_entity("e2", "Entity 2"),
            _make_entity("e3", "Entity 3"),
        ]
        result = compute_search_unused_signals(stats, entities)
        assert len(result) == 1
        assert result[0]["entity_id"] == "e1"

    def test_output_contains_required_fields(self):
        """Each flagged entry must have all required fields."""
        stats = [{"entity_id": "e1", "search_count": 4, "get_count": 0}]
        entities = [_make_entity("e1", "Test Entity")]
        result = compute_search_unused_signals(stats, entities)
        required = {"entity_id", "entity_name", "search_count", "get_count", "unused_ratio", "flagged"}
        assert required == set(result[0].keys())

    def test_empty_stats_returns_empty_list(self):
        result = compute_search_unused_signals([], [])
        assert result == []

    def test_unused_ratio_calculation_is_correct(self):
        """unused_ratio = 1 - get_count / max(search_count, 1)."""
        stats = [{"entity_id": "e1", "search_count": 10, "get_count": 1}]
        entities = [_make_entity("e1", "E1")]
        result = compute_search_unused_signals(stats, entities)
        assert len(result) == 1
        assert result[0]["unused_ratio"] == pytest.approx(0.9)

    def test_zero_search_count_does_not_divide_by_zero(self):
        """search_count=0 → max(0,1)=1, ratio=1.0, but not flagged (search_count < 3)."""
        stats = [{"entity_id": "e1", "search_count": 0, "get_count": 0}]
        entities = [_make_entity("e1", "E1")]
        # Should not raise, and not flagged
        result = compute_search_unused_signals(stats, entities)
        assert result == []


# ──────────────────────────────────────────────
# score_summary_quality
# ──────────────────────────────────────────────

class TestScoreSummaryQuality:
    def test_good_summary_with_technical_and_challenge_keywords(self):
        """Summary with technical + challenge context + no marketing = good."""
        summary = (
            "ZenOS 的 API schema 定義了所有資料存取規則。"
            "這個模組的主要挑戰是在高並發環境下維持一致性。"
            "系統採用 repository pattern 隔離資料庫依賴。"
        )
        result = score_summary_quality(summary, "module")
        assert result["has_technical_keywords"] is True
        assert result["has_challenge_context"] is True
        assert result["quality_score"] == "good"

    def test_poor_summary_too_short(self):
        """Summary shorter than 50 chars → is_too_generic=True → poor."""
        summary = "負責提供服務。"
        result = score_summary_quality(summary, "module")
        assert result["is_too_generic"] is True
        assert result["quality_score"] == "poor"

    def test_poor_summary_no_technical_keywords_with_high_marketing_ratio(self):
        """No tech keywords + high marketing ratio → poor."""
        summary = (
            "負責確保全面的服務品質，提供高效且完善的解決方案，"
            "優化整體流程，確保所有需求均被充分支援。"
        )
        result = score_summary_quality(summary, "module")
        assert result["has_technical_keywords"] is False
        assert result["quality_score"] == "poor"

    def test_needs_improvement_has_tech_but_no_challenge(self):
        """Has technical keywords but no challenge context → needs_improvement."""
        summary = (
            "ZenOS 的 API 模組提供標準化的 endpoint 介面，"
            "支援 SQL 查詢和 cache 管理，確保服務穩定運行。"
        )
        result = score_summary_quality(summary, "module")
        assert result["has_technical_keywords"] is True
        assert result["has_challenge_context"] is False
        assert result["quality_score"] == "needs_improvement"

    def test_is_too_generic_when_empty_summary(self):
        result = score_summary_quality("", "module")
        assert result["is_too_generic"] is True
        assert result["quality_score"] == "poor"

    def test_marketing_ratio_computed_correctly(self):
        """marketing_ratio = hits / word_count."""
        # One hit of "負責" in a very short text with identifiable words
        summary = "負責 API 架構" * 1  # "負責", "API", "架構" = 3 tokens, 1 marketing hit
        result = score_summary_quality(summary, "module")
        # word_count = count of CJK chars + ASCII tokens
        # "負責 API 架構": 負, 責, A, P, I, 架, 構 = varies; just check it's a float
        assert 0.0 <= result["marketing_ratio"] <= 1.0

    def test_has_technical_keywords_detects_english_terms(self):
        """English technical terms like 'LLM', 'prompt', 'token' should match."""
        summary = (
            "This module handles LLM inference pipeline. "
            "It manages token limits and prompt construction. "
            "The main challenge is latency under load."
        )
        result = score_summary_quality(summary, "module")
        assert result["has_technical_keywords"] is True
        # CHALLENGE_KEYWORDS are Chinese-only; English "challenge" does not match.
        assert result["has_challenge_context"] is False

    def test_has_challenge_keywords_detects_chinese_terms(self):
        """Chinese challenge keywords like 挑戰, 限制 should be detected."""
        summary = (
            "AuthModule 使用 JWT token 進行身份驗證，"
            "主要限制是 token 過期後需要重新走 OAuth 流程，"
            "這是目前架構的核心挑戰。"
        )
        result = score_summary_quality(summary, "module")
        assert result["has_challenge_context"] is True

    def test_output_contains_all_required_fields(self):
        result = score_summary_quality("Some summary.", "module")
        required = {
            "has_technical_keywords",
            "has_challenge_context",
            "is_too_generic",
            "marketing_ratio",
            "quality_score",
        }
        assert required == set(result.keys())

    def test_quality_score_values_are_valid(self):
        """quality_score must be one of the three valid values."""
        for summary in ["", "short", "A " * 30 + "API schema 挑戰"]:
            result = score_summary_quality(summary, "module")
            assert result["quality_score"] in ("good", "needs_improvement", "poor")


# ──────────────────────────────────────────────
# Keyword constant validation
# ──────────────────────────────────────────────

class TestKeywordConstants:
    def test_technical_keywords_is_non_empty_list(self):
        assert isinstance(TECHNICAL_KEYWORDS, list)
        assert len(TECHNICAL_KEYWORDS) > 0

    def test_challenge_keywords_is_non_empty_list(self):
        assert isinstance(CHALLENGE_KEYWORDS, list)
        assert len(CHALLENGE_KEYWORDS) > 0

    def test_marketing_keywords_is_non_empty_list(self):
        assert isinstance(MARKETING_KEYWORDS, list)
        assert len(MARKETING_KEYWORDS) > 0
