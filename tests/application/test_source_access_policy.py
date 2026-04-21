from __future__ import annotations

from zenos.application.identity.source_access_policy import (
    filter_sources_for_partner,
    is_source_in_connector_scope,
    normalized_retrieval_mode,
)


def _partner(connector_scopes: dict | None = None) -> dict:
    return {
        "id": "partner-1",
        "preferences": {"connectorScopes": connector_scopes or {}},
    }


def test_no_connector_scope_config_keeps_legacy_allow():
    source = {"type": "gdrive", "container_id": "drive:finance"}
    assert is_source_in_connector_scope(source, _partner()) is True


def test_connector_scope_empty_allowlist_denies_all():
    source = {"type": "gdrive", "container_id": "drive:finance"}
    partner = _partner({"gdrive": {"containers": []}})
    assert is_source_in_connector_scope(source, partner) is False


def test_missing_container_id_fails_closed_when_scope_exists():
    source = {"type": "gdrive"}
    partner = _partner({"gdrive": {"containers": ["drive:finance"]}})
    assert is_source_in_connector_scope(source, partner) is False


def test_filter_sources_keeps_only_in_scope_sources():
    partner = _partner({"gdrive": {"containers": ["drive:finance"]}})
    sources = [
        {"source_id": "src-1", "type": "gdrive", "container_id": "drive:finance"},
        {"source_id": "src-2", "type": "gdrive", "container_id": "drive:secret"},
        {"source_id": "src-3", "type": "zenos_native", "uri": "/docs/doc-1"},
    ]
    assert [s["source_id"] for s in filter_sources_for_partner(sources, partner)] == ["src-1", "src-3"]


def test_normalized_retrieval_mode_defaults_are_safe():
    assert normalized_retrieval_mode({"type": "github"}) == "direct"
    assert normalized_retrieval_mode({"type": "gdrive"}) == "snapshot"
    assert normalized_retrieval_mode({"type": "gdrive", "retrieval_mode": "per_user_live"}) == "per_user_live"
