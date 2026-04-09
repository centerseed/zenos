"""Tests for doc_types domain module (ADR-022 D2)."""

import pytest
from zenos.domain.doc_types import (
    DOC_TYPE_ALIASES,
    VALID_DOC_TYPES,
    canonical_type,
    ensure_source_ids,
    expand_for_search,
    generate_source_id,
    is_known_doc_type,
)


class TestCanonicalType:
    def test_legacy_adr_maps_to_decision(self):
        assert canonical_type("ADR") == "DECISION"

    def test_legacy_td_maps_to_design(self):
        assert canonical_type("TD") == "DESIGN"

    def test_legacy_tc_maps_to_test(self):
        assert canonical_type("TC") == "TEST"

    def test_legacy_pb_maps_to_guide(self):
        assert canonical_type("PB") == "GUIDE"

    def test_legacy_ref_maps_to_reference(self):
        assert canonical_type("REF") == "REFERENCE"

    def test_new_type_returns_as_is(self):
        assert canonical_type("PLAN") == "PLAN"
        assert canonical_type("CONTRACT") == "CONTRACT"
        assert canonical_type("MEETING") == "MEETING"

    def test_sc_returns_as_is_no_fixed_mapping(self):
        assert canonical_type("SC") == "SC"

    def test_unknown_returns_as_is(self):
        assert canonical_type("FOOBAR") == "FOOBAR"

    def test_spec_stays_spec(self):
        assert canonical_type("SPEC") == "SPEC"


class TestExpandForSearch:
    def test_legacy_adr_expands_to_both(self):
        result = expand_for_search("ADR")
        assert "ADR" in result
        assert "DECISION" in result

    def test_canonical_decision_expands_to_both(self):
        result = expand_for_search("DECISION")
        assert "DECISION" in result
        assert "ADR" in result

    def test_plan_expands_to_self_only(self):
        result = expand_for_search("PLAN")
        assert result == ["PLAN"]

    def test_sc_expands_to_self_only(self):
        result = expand_for_search("SC")
        assert result == ["SC"]

    def test_spec_expands_to_self_only(self):
        # SPEC is both a legacy and new type, no alias
        result = expand_for_search("SPEC")
        assert result == ["SPEC"]

    def test_case_insensitive(self):
        result = expand_for_search("adr")
        assert "ADR" in result
        assert "DECISION" in result


class TestIsKnownDocType:
    def test_valid_new_types(self):
        for t in VALID_DOC_TYPES:
            assert is_known_doc_type(t), f"{t} should be known"

    def test_valid_legacy_types(self):
        for t in DOC_TYPE_ALIASES:
            assert is_known_doc_type(t), f"{t} should be known"

    def test_sc_is_known(self):
        assert is_known_doc_type("SC") is True

    def test_unknown_type(self):
        assert is_known_doc_type("FOOBAR") is False


class TestGenerateSourceId:
    def test_generates_uuid_string(self):
        sid = generate_source_id()
        assert isinstance(sid, str)
        assert len(sid) == 36  # UUID v4 format: 8-4-4-4-12

    def test_uniqueness(self):
        ids = {generate_source_id() for _ in range(100)}
        assert len(ids) == 100


class TestEnsureSourceIds:
    def test_adds_missing_source_ids(self):
        sources = [
            {"uri": "https://example.com/a", "type": "url"},
            {"uri": "https://example.com/b", "type": "url"},
        ]
        result = ensure_source_ids(sources)
        assert all(s.get("source_id") for s in result)
        assert result[0]["source_id"] != result[1]["source_id"]

    def test_preserves_existing_source_ids(self):
        sources = [
            {"uri": "https://example.com/a", "type": "url", "source_id": "existing-123"},
        ]
        result = ensure_source_ids(sources)
        assert result[0]["source_id"] == "existing-123"

    def test_mixed_existing_and_missing(self):
        sources = [
            {"uri": "https://example.com/a", "type": "url", "source_id": "keep-me"},
            {"uri": "https://example.com/b", "type": "url"},
        ]
        result = ensure_source_ids(sources)
        assert result[0]["source_id"] == "keep-me"
        assert result[1]["source_id"]  # generated
        assert result[1]["source_id"] != "keep-me"

    def test_empty_list(self):
        assert ensure_source_ids([]) == []
