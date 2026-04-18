"""Unit tests for src/zenos/interface/mcp/_include.py.

These are *not* spec-compliance tests — they test the helpers in isolation.
Strategy: no mocks needed since all helpers are pure functions.
"""

from __future__ import annotations

import pytest

from zenos.interface.mcp._include import (
    VALID_ENTITY_INCLUDES,
    VALID_SEARCH_INCLUDES,
    build_entity_response,
    build_search_result,
    validate_include,
    _summary_short,
    log_deprecation_warning,
)


# ──────────────────────────────────────────────
# validate_include
# ──────────────────────────────────────────────


class TestValidateInclude:
    def test_none_returns_none_none(self):
        include_set, err = validate_include(None, VALID_ENTITY_INCLUDES)
        assert include_set is None
        assert err is None

    def test_valid_values_return_set(self):
        include_set, err = validate_include(["summary", "relationships"], VALID_ENTITY_INCLUDES)
        assert err is None
        assert include_set == {"summary", "relationships"}

    def test_single_valid_value(self):
        include_set, err = validate_include(["all"], VALID_ENTITY_INCLUDES)
        assert err is None
        assert include_set == {"all"}

    def test_unknown_value_returns_error(self):
        include_set, err = validate_include(["xyz"], VALID_ENTITY_INCLUDES)
        assert include_set is None
        assert err is not None
        assert err["status"] == "rejected"
        assert "xyz" in err["data"]["message"]
        # Error message should list supported values
        for v in sorted(VALID_ENTITY_INCLUDES):
            assert v in err["data"]["message"]

    def test_mixed_valid_and_unknown_returns_error(self):
        include_set, err = validate_include(["summary", "unknown_field"], VALID_ENTITY_INCLUDES)
        assert include_set is None
        assert err is not None

    def test_duplicates_deduped(self):
        include_set, err = validate_include(["summary", "summary", "tags"], VALID_SEARCH_INCLUDES)
        assert err is None
        assert include_set == {"summary", "tags"}

    def test_empty_list_treated_as_valid(self):
        # Empty list is valid — returns empty set, no error
        include_set, err = validate_include([], VALID_ENTITY_INCLUDES)
        assert err is None
        assert include_set == set()

    def test_search_valid_values(self):
        include_set, err = validate_include(["summary", "tags", "full"], VALID_SEARCH_INCLUDES)
        assert err is None
        assert include_set == {"summary", "tags", "full"}

    def test_entity_include_unknown_in_search_valid_set(self):
        # "relationships" is valid for entities but NOT for search
        include_set, err = validate_include(["relationships"], VALID_SEARCH_INCLUDES)
        assert include_set is None
        assert err is not None


# ──────────────────────────────────────────────
# _summary_short
# ──────────────────────────────────────────────


class TestSummaryShort:
    def test_short_text_unchanged(self):
        text = "short text"
        assert _summary_short(text) == text

    def test_exactly_120_codepoints_unchanged(self):
        text = "a" * 120
        assert _summary_short(text) == text
        assert len(_summary_short(text)) == 120

    def test_121_codepoints_truncated_with_ellipsis(self):
        text = "a" * 121
        result = _summary_short(text)
        assert result.endswith("…")
        assert len(result) == 121  # 120 chars + 1 codepoint ellipsis

    def test_chinese_characters_codepoint_count(self):
        # Each Chinese character = 1 codepoint
        text = "測試" * 65  # 130 codepoints
        result = _summary_short(text)
        assert result.endswith("…")
        assert len(result) == 121  # 120 + ellipsis

    def test_none_returns_empty_string(self):
        assert _summary_short(None) == ""

    def test_empty_string_unchanged(self):
        assert _summary_short("") == ""

    def test_mixed_ascii_and_cjk(self):
        # 60 ASCII + 60 CJK = 120 codepoints (no truncation)
        text = "a" * 60 + "中" * 60
        result = _summary_short(text)
        assert result == text
        assert not result.endswith("…")

    def test_mixed_ascii_and_cjk_over_limit(self):
        # 61 ASCII + 60 CJK = 121 codepoints → truncate
        text = "a" * 61 + "中" * 60
        result = _summary_short(text)
        assert result.endswith("…")
        assert len(result) == 121


# ──────────────────────────────────────────────
# build_entity_response
# ──────────────────────────────────────────────


def _make_entity_dict(**overrides) -> dict:
    defaults = {
        "id": "ent-1",
        "name": "Paceriz",
        "type": "product",
        "level": 1,
        "status": "active",
        "summary": "A running coach app",
        "tags": {"what": ["app"], "why": "coaching", "how": "AI", "who": ["runners"]},
        "owner": "Barry",
        "confirmed_by_user": True,
        "parent_id": None,
        "sources": [{"uri": "https://example.com", "label": "docs"}],
    }
    defaults.update(overrides)
    return defaults


def _make_rel_dict(direction: str = "outgoing") -> dict:
    return {
        "id": "rel-1",
        "source_entity_id": "ent-1",
        "target_id": "ent-2",
        "type": "impacts",
        "description": "Paceriz impacts users",
        "_direction": direction,
    }


class TestBuildEntityResponse:
    def test_summary_only_excludes_heavy_fields(self):
        entity_dict = _make_entity_dict()
        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=None,
            entries=None,
            forward_impact=None,
            reverse_impact=None,
            include_set={"summary"},
        )
        # Must have entity core fields
        assert response["id"] == "ent-1"
        assert response["name"] == "Paceriz"
        assert response["source_count"] == 1  # integer count
        # Must NOT have heavy fields
        assert "sources" not in response
        assert "outgoing_relationships" not in response
        assert "incoming_relationships" not in response
        assert "active_entries" not in response
        assert "impact_chain" not in response
        assert "reverse_impact_chain" not in response

    def test_summary_plus_relationships(self):
        entity_dict = _make_entity_dict()
        rels = [_make_rel_dict("outgoing"), _make_rel_dict("incoming")]
        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=rels,
            entries=None,
            forward_impact=None,
            reverse_impact=None,
            include_set={"summary", "relationships"},
        )
        assert "outgoing_relationships" in response
        assert "incoming_relationships" in response
        assert len(response["outgoing_relationships"]) == 1
        assert len(response["incoming_relationships"]) == 1

    def test_summary_plus_entries_limit_5(self):
        entity_dict = _make_entity_dict()
        entries = [{"id": f"e-{i}", "content": f"entry {i}"} for i in range(10)]
        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=None,
            entries=entries,
            forward_impact=None,
            reverse_impact=None,
            include_set={"summary", "entries"},
        )
        assert "active_entries" in response
        assert len(response["active_entries"]) == 5  # hard limit

    def test_summary_plus_impact_chain(self):
        entity_dict = _make_entity_dict()
        fwd = [{"entity_id": "x", "entity_name": "X", "depth": 1}]
        rev = [{"entity_id": "y", "entity_name": "Y", "depth": 1}]
        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=None,
            entries=None,
            forward_impact=fwd,
            reverse_impact=rev,
            include_set={"summary", "impact_chain"},
        )
        assert response["impact_chain"] == fwd
        assert response["reverse_impact_chain"] == rev

    def test_summary_plus_sources_replaces_source_count(self):
        entity_dict = _make_entity_dict()
        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=None,
            entries=None,
            forward_impact=None,
            reverse_impact=None,
            include_set={"summary", "sources"},
        )
        assert "sources" in response
        assert len(response["sources"]) == 1
        assert "source_count" not in response  # replaced

    def test_summary_only_source_count_zero_when_no_sources(self):
        entity_dict = _make_entity_dict(sources=[])
        response = build_entity_response(
            entity_dict=entity_dict,
            relationships=None,
            entries=None,
            forward_impact=None,
            reverse_impact=None,
            include_set={"summary"},
        )
        assert response["source_count"] == 0


# ──────────────────────────────────────────────
# build_search_result
# ──────────────────────────────────────────────


class TestBuildSearchResult:
    def test_none_include_set_returns_full_with_score(self):
        entity_dict = _make_entity_dict()
        result = build_search_result(entity_dict, score=0.9, include_set=None)
        assert result["score"] == 0.9
        assert "id" in result
        assert "name" in result
        assert "sources" in result  # full dict included

    def test_full_include_returns_full_with_score(self):
        entity_dict = _make_entity_dict()
        result = build_search_result(entity_dict, score=0.8, include_set={"full"})
        assert result["score"] == 0.8
        assert "sources" in result

    def test_summary_include_shape(self):
        entity_dict = _make_entity_dict()
        result = build_search_result(entity_dict, score=0.7, include_set={"summary"})
        expected_keys = {"id", "name", "type", "level", "summary_short", "score"}
        assert set(result.keys()) == expected_keys
        assert result["score"] == 0.7
        assert "sources" not in result
        assert "tags" not in result
        assert "status" not in result
        assert "owner" not in result

    def test_summary_plus_tags(self):
        entity_dict = _make_entity_dict()
        result = build_search_result(entity_dict, score=0.6, include_set={"summary", "tags"})
        assert "tags" in result
        assert "summary_short" in result
        assert "sources" not in result

    def test_summary_short_truncation_in_result(self):
        entity_dict = _make_entity_dict(summary="x" * 200)
        result = build_search_result(entity_dict, score=0.5, include_set={"summary"})
        assert result["summary_short"].endswith("…")
        assert len(result["summary_short"]) == 121  # 120 + ellipsis


# ──────────────────────────────────────────────
# log_deprecation_warning (structural test)
# ──────────────────────────────────────────────


class TestLogDeprecationWarning:
    def test_warning_emitted_with_json_body(self, caplog):
        import json
        import logging
        with caplog.at_level(logging.WARNING, logger="zenos.interface.mcp._include"):
            log_deprecation_warning("get", "entities", "partner-123")
        assert len(caplog.records) == 1
        record = caplog.records[0]
        data = json.loads(record.getMessage())
        assert data["event"] == "mcp_include_deprecation"
        assert data["tool"] == "get"
        assert data["collection"] == "entities"
        assert data["caller_id"] == "partner-123"
        assert "timestamp" in data
        assert "Phase B" in data["message"]

    def test_warning_with_none_caller_id(self, caplog):
        import json
        import logging
        with caplog.at_level(logging.WARNING, logger="zenos.interface.mcp._include"):
            log_deprecation_warning("search", "entities", None)
        data = json.loads(caplog.records[0].getMessage())
        assert data["caller_id"] is None


# ──────────────────────────────────────────────
# QA edge case: collection="all" + include
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_collection_all_with_include_does_not_crash():
    """QA risk (a): search(collection="all", query="x", include=["summary"]) must not crash
    or produce wrong assumption. collection="all" goes through keyword-search path which
    does NOT apply the include logic — this confirms no TypeError or silent failure."""
    from unittest.mock import AsyncMock, patch
    from zenos.domain.knowledge import Entity, Tags
    from datetime import datetime, timezone

    fake_entity = Entity(
        id="ent-qa1", name="QA Test Entity", type="product", level=1,
        status="active", summary="summary text", tags=Tags(what=[], why="", how="", who=[]),
        confirmed_by_user=True, owner="QA", parent_id=None, sources=[],
        visibility="public",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    mock_os = AsyncMock()
    mock_os.search = AsyncMock(return_value=[fake_entity])
    mock_ts = AsyncMock()
    mock_ts.list_tasks = AsyncMock(return_value=[])
    mock_er = AsyncMock()
    mock_er.search_content = AsyncMock(return_value=[])

    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.ontology_service", new=mock_os), \
         patch("zenos.interface.mcp.task_service", new=mock_ts), \
         patch("zenos.interface.mcp.entry_repo", new=mock_er):
        from zenos.interface.mcp.search import search
        result = await search(query="x", collection="all", include=["summary"])

    # Must return ok (not crash)
    assert result["status"] == "ok"
    # Note: collection="all" keyword path does NOT apply include projection.
    # Result items in "results" are full serialised objects, not summary shape.
    # This is a known SPEC gap: SPEC only defines include for collection="entities".
    assert "results" in result["data"]


# ──────────────────────────────────────────────
# QA edge case: updated_at=None in entries sort
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_entities_entries_sort_none_updated_at():
    """QA risk (b): entries with updated_at=None must not raise TypeError during sort.

    get.py line 214 sorts entries by updated_at DESC, falling back to created_at.
    If both are None the key function returns None and comparisons raise TypeError.
    This test verifies that at least one fallback is always non-None (or the code
    handles it gracefully).
    """
    from unittest.mock import AsyncMock, patch
    from datetime import datetime, timezone
    from zenos.domain.knowledge import Entity, EntityEntry, Tags
    from zenos.application.knowledge.ontology_service import EntityWithRelationships

    entity = Entity(
        id="ent-sort-1", name="SortTest", type="product", level=1,
        status="active", summary="sort test", tags=Tags(what=[], why="", how="", who=[]),
        confirmed_by_user=True, owner="QA", parent_id=None, sources=[],
        visibility="public",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    ewr = EntityWithRelationships(entity=entity, relationships=[])

    # EntityEntry has no updated_at field (only created_at).
    # get.py sort key: getattr(e, "updated_at", None) or getattr(e, "created_at", None)
    # For all EntityEntry objects, updated_at is always None → falls back to created_at.
    # Verify no TypeError when sorting entries with only created_at present.
    entries_mixed = [
        EntityEntry(
            id="e-1", partner_id="p1", entity_id="ent-sort-1",
            type="decision", content="oldest",
            status="active",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        EntityEntry(
            id="e-2", partner_id="p1", entity_id="ent-sort-1",
            type="decision", content="newest",
            status="active",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        ),
        EntityEntry(
            id="e-3", partner_id="p1", entity_id="ent-sort-1",
            type="decision", content="middle",
            status="active",
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
    ]

    mock_os = AsyncMock()
    mock_os.get_entity = AsyncMock(return_value=ewr)
    mock_os.compute_impact_chain = AsyncMock(return_value=[])
    mock_entry = AsyncMock()
    mock_entry.list_by_entity = AsyncMock(return_value=entries_mixed)

    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.ontology_service", new=mock_os), \
         patch("zenos.interface.mcp.entry_repo", new=mock_entry):
        from zenos.interface.mcp.get import get
        # Should not raise TypeError
        result = await get(collection="entities", name="SortTest", include=["summary", "entries"])

    assert result["status"] == "ok"
    assert "active_entries" in result["data"]
    # Entries should be returned (up to 5)
    assert len(result["data"]["active_entries"]) <= 5
