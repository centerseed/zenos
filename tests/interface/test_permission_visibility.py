"""Tests for permission governance Phase 0: visibility filtering + write auth.

Covers:
  - Write-path authorization (existing entity invisible → FORBIDDEN)
  - Confidential entity visibility change blocked for non-admin
  - Task visibility filtering (inherited from linked entities)
  - Protocol visibility filtering (inherited from linked entity)
  - Blindspot visibility filtering (ANY related entity visible → visible)
  - Visibility change audit log emission
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
import logging

import pytest

from zenos.application.ontology_service import UpsertEntityResult
from zenos.domain.models import (
    Blindspot,
    Entity,
    Protocol,
    Tags,
    Task,
    Visibility,
    VISIBILITY_ORDER,
)
from zenos.infrastructure.context import current_partner_department, current_partner_roles


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    """Avoid bootstrapping real SQL repos in interface unit tests."""
    with patch("zenos.interface.tools._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.tools.ontology_service", new=AsyncMock()), \
         patch("zenos.interface.tools.task_service", new=AsyncMock()), \
         patch("zenos.interface.tools.entity_repo", new=AsyncMock()), \
         patch("zenos.interface.tools.entry_repo", new=AsyncMock()):
        yield


def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-1",
        name="TestEntity",
        type="product",
        summary="Test entity",
        tags=Tags(what="test", why="testing", how="pytest", who="dev"),
        status="active",
        confirmed_by_user=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Test task",
        status="todo",
        priority="high",
        created_by="architect",
        description="A test task",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_protocol(**overrides) -> Protocol:
    defaults = dict(
        id="proto-1",
        entity_id="ent-1",
        entity_name="TestEntity",
        content={"what": {}, "why": {}, "how": {}, "who": {}},
        confirmed_by_user=True,
    )
    defaults.update(overrides)
    return Protocol(**defaults)


def _make_blindspot(**overrides) -> Blindspot:
    defaults = dict(
        id="bs-1",
        description="Missing docs",
        severity="yellow",
        related_entity_ids=["ent-1"],
        suggested_action="Add docs",
        status="open",
        confirmed_by_user=False,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Blindspot(**defaults)


class _PartnerContext:
    """Context manager to set partner ContextVars for tests."""

    def __init__(self, partner_id, is_admin=False, roles=None, department="all"):
        self.partner = {"id": partner_id, "isAdmin": is_admin}
        self.roles = roles or []
        self.department = department
        self._tokens = []

    def __enter__(self):
        from zenos.interface.tools import _current_partner
        self._tokens.append(("partner", _current_partner.set(self.partner)))
        self._tokens.append(("roles", current_partner_roles.set(self.roles)))
        self._tokens.append(("dept", current_partner_department.set(self.department)))
        return self

    def __exit__(self, *args):
        from zenos.interface.tools import _current_partner
        for name, token in reversed(self._tokens):
            if name == "partner":
                _current_partner.reset(token)
            elif name == "roles":
                current_partner_roles.reset(token)
            elif name == "dept":
                current_partner_department.reset(token)


# ===========================================================================
# Visibility Enum + VISIBILITY_ORDER
# ===========================================================================

class TestVisibilityEnum:
    def test_enum_values(self):
        assert Visibility.PUBLIC == "public"
        assert Visibility.CONFIDENTIAL == "confidential"

    def test_visibility_order(self):
        assert VISIBILITY_ORDER["public"] < VISIBILITY_ORDER["restricted"]
        assert VISIBILITY_ORDER["restricted"] < VISIBILITY_ORDER["confidential"]
        assert VISIBILITY_ORDER["role-restricted"] < VISIBILITY_ORDER["restricted"]


# ===========================================================================
# Write-path Authorization
# ===========================================================================

@pytest.mark.asyncio
class TestWriteAuth:
    async def test_write_invisible_entity_returns_forbidden(self):
        """Non-admin cannot modify an entity they can't see."""
        from zenos.interface.tools import write

        existing = _make_entity(
            visibility="confidential",
            visible_to_members=["p-owner"],
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=existing)
                mock_repo.get_by_name = AsyncMock(return_value=existing)
                result = await write(
                    collection="entities",
                    data={"id": "ent-1", "summary": "hacked"},
                )
        assert result["error"] == "FORBIDDEN"

    async def test_write_visible_entity_succeeds(self):
        """User who can see the entity can update it."""
        from zenos.interface.tools import write

        existing = _make_entity(visibility="public")
        upsert_result = UpsertEntityResult(
            entity=existing, tag_confidence=None, split_recommendation=None, warnings=[]
        )

        with _PartnerContext("p-user", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.ontology_service") as mock_os:
                mock_repo.get_by_id = AsyncMock(return_value=existing)
                mock_os.upsert_entity = AsyncMock(return_value=upsert_result)
                result = await write(
                    collection="entities",
                    data={"id": "ent-1", "summary": "updated"},
                )
        assert "error" not in result

    async def test_write_new_entity_no_auth_check(self):
        """New entities (no existing) bypass write auth check."""
        from zenos.interface.tools import write

        new_entity = _make_entity(id="ent-new")
        upsert_result = UpsertEntityResult(
            entity=new_entity, tag_confidence=None, split_recommendation=None, warnings=[]
        )

        with _PartnerContext("p-user", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.ontology_service") as mock_os:
                mock_repo.get_by_id = AsyncMock(return_value=None)
                mock_repo.get_by_name = AsyncMock(return_value=None)
                mock_os.upsert_entity = AsyncMock(return_value=upsert_result)
                result = await write(
                    collection="entities",
                    data={"name": "NewEntity", "type": "product",
                          "summary": "new", "tags": {"what": "x", "why": "y", "how": "z", "who": "w"}},
                )
        assert "error" not in result

    async def test_confidential_non_admin_cannot_change_visibility(self):
        """Non-admin cannot modify a confidential entity (it is not visible to them)."""
        from zenos.interface.tools import write

        existing = _make_entity(
            visibility="confidential",
            visible_to_members=["p-member"],
        )

        with _PartnerContext("p-member", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=existing)
                result = await write(
                    collection="entities",
                    data={"id": "ent-1", "visibility": "public"},
                )
        # Under new model: confidential is admin-only, non-admin cannot see it at all
        assert result["error"] == "FORBIDDEN"

    async def test_admin_can_change_confidential_visibility(self):
        """Admin can modify visibility on confidential entity."""
        from zenos.interface.tools import write

        existing = _make_entity(
            visibility="confidential",
            visible_to_members=["p-admin"],
        )
        updated = _make_entity(visibility="public")
        upsert_result = UpsertEntityResult(
            entity=updated, tag_confidence=None, split_recommendation=None, warnings=[]
        )

        with _PartnerContext("p-admin", is_admin=True):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.ontology_service") as mock_os:
                mock_repo.get_by_id = AsyncMock(return_value=existing)
                mock_os.upsert_entity = AsyncMock(return_value=upsert_result)
                result = await write(
                    collection="entities",
                    data={"id": "ent-1", "visibility": "public"},
                )
        assert "error" not in result


# ===========================================================================
# Task Visibility Filtering
# ===========================================================================

@pytest.mark.asyncio
class TestTaskVisibility:
    async def test_task_no_linked_entities_always_visible(self):
        from zenos.interface.tools import _is_task_visible

        task = _make_task(linked_entities=[])
        with _PartnerContext("p-user", is_admin=False):
            assert await _is_task_visible(task) is True

    async def test_task_all_linked_public_visible(self):
        from zenos.interface.tools import _is_task_visible

        task = _make_task(linked_entities=["ent-1"])
        public_entity = _make_entity(visibility="public")

        with _PartnerContext("p-user", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=public_entity)
                assert await _is_task_visible(task) is True

    async def test_task_linked_to_restricted_hidden_from_unauthorized(self):
        from zenos.interface.tools import _is_task_visible

        task = _make_task(linked_entities=["ent-secret"])
        restricted = _make_entity(
            id="ent-secret",
            visibility="confidential",
            visible_to_members=["p-owner"],
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=restricted)
                assert await _is_task_visible(task) is False

    async def test_task_mixed_entities_hidden_if_any_invisible(self):
        from zenos.interface.tools import _is_task_visible

        task = _make_task(linked_entities=["ent-pub", "ent-secret"])
        public = _make_entity(id="ent-pub", visibility="public")
        secret = _make_entity(
            id="ent-secret",
            visibility="confidential",
            visible_to_members=["p-owner"],
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                async def get_by_id(eid):
                    return public if eid == "ent-pub" else secret
                mock_repo.get_by_id = AsyncMock(side_effect=get_by_id)
                assert await _is_task_visible(task) is False

    async def test_admin_sees_all_tasks(self):
        from zenos.interface.tools import _is_task_visible

        task = _make_task(linked_entities=["ent-secret"])
        secret = _make_entity(
            id="ent-secret",
            visibility="confidential",
            visible_to_members=[],
        )

        with _PartnerContext("p-admin", is_admin=True):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=secret)
                assert await _is_task_visible(task) is True

    async def test_search_tasks_filters_by_visibility(self):
        """search(collection="tasks") should exclude tasks linked to invisible entities."""
        from zenos.interface.tools import search

        visible_task = _make_task(id="t-vis", title="Public task", linked_entities=[])
        hidden_task = _make_task(id="t-hid", title="Secret task", linked_entities=["ent-secret"])
        secret = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=[visible_task, hidden_task])
                mock_repo.get_by_id = AsyncMock(return_value=secret)
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in result["tasks"]]
        assert "t-vis" in task_ids
        assert "t-hid" not in task_ids

    async def test_get_task_hidden_returns_not_found(self):
        """get(collection="tasks") returns NOT_FOUND for invisible tasks."""
        from zenos.interface.tools import get

        task = _make_task(linked_entities=["ent-secret"])
        secret = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.get_task_enriched = AsyncMock(return_value=(task, {}))
                mock_repo.get_by_id = AsyncMock(return_value=secret)
                result = await get(collection="tasks", id="task-1")

        assert result["error"] == "NOT_FOUND"


# ===========================================================================
# Protocol Visibility Filtering
# ===========================================================================

@pytest.mark.asyncio
class TestProtocolVisibility:
    async def test_protocol_visible_when_entity_public(self):
        from zenos.interface.tools import _is_protocol_visible

        proto = _make_protocol(entity_id="ent-1")
        entity = _make_entity(visibility="public")

        with _PartnerContext("p-user", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=entity)
                assert await _is_protocol_visible(proto) is True

    async def test_protocol_hidden_when_entity_invisible(self):
        from zenos.interface.tools import _is_protocol_visible

        proto = _make_protocol(entity_id="ent-secret")
        entity = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=entity)
                assert await _is_protocol_visible(proto) is False

    async def test_protocol_orphan_always_visible(self):
        from zenos.interface.tools import _is_protocol_visible

        proto = _make_protocol(entity_id=None)
        with _PartnerContext("p-user", is_admin=False):
            assert await _is_protocol_visible(proto) is True

    async def test_get_protocol_hidden_returns_not_found(self):
        from zenos.interface.tools import get

        proto = _make_protocol(entity_id="ent-secret")
        entity = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.protocol_repo") as mock_proto_repo:
                mock_proto_repo.get_by_id = AsyncMock(return_value=proto)
                mock_repo.get_by_id = AsyncMock(return_value=entity)
                result = await get(collection="protocols", id="proto-1")

        assert result["error"] == "NOT_FOUND"


# ===========================================================================
# Blindspot Visibility Filtering
# ===========================================================================

@pytest.mark.asyncio
class TestBlindspotVisibility:
    async def test_blindspot_visible_if_any_related_visible(self):
        from zenos.interface.tools import _is_blindspot_visible

        bs = _make_blindspot(related_entity_ids=["ent-pub", "ent-secret"])
        public = _make_entity(id="ent-pub", visibility="public")
        secret = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                async def get_by_id(eid):
                    return public if eid == "ent-pub" else secret
                mock_repo.get_by_id = AsyncMock(side_effect=get_by_id)
                assert await _is_blindspot_visible(bs) is True

    async def test_blindspot_hidden_when_all_related_invisible(self):
        from zenos.interface.tools import _is_blindspot_visible

        bs = _make_blindspot(related_entity_ids=["ent-secret"])
        secret = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=secret)
                assert await _is_blindspot_visible(bs) is False

    async def test_blindspot_no_related_always_visible(self):
        from zenos.interface.tools import _is_blindspot_visible

        bs = _make_blindspot(related_entity_ids=[])
        with _PartnerContext("p-user", is_admin=False):
            assert await _is_blindspot_visible(bs) is True

    async def test_get_blindspot_hidden_returns_not_found(self):
        from zenos.interface.tools import get

        bs = _make_blindspot(related_entity_ids=["ent-secret"])
        secret = _make_entity(
            id="ent-secret", visibility="confidential", visible_to_members=["p-owner"]
        )

        with _PartnerContext("p-outsider", is_admin=False):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.blindspot_repo") as mock_bs_repo:
                mock_bs_repo.get_by_id = AsyncMock(return_value=bs)
                mock_repo.get_by_id = AsyncMock(return_value=secret)
                result = await get(collection="blindspots", id="bs-1")

        assert result["error"] == "NOT_FOUND"


# ===========================================================================
# Visibility Change Audit Log
# ===========================================================================

@pytest.mark.asyncio
class TestVisibilityAuditLog:
    async def test_visibility_change_emits_governance_audit(self):
        """When visibility fields change, a governance.visibility.change event is emitted."""
        from zenos.interface.tools import write

        existing = _make_entity(visibility="public")
        updated = _make_entity(visibility="restricted", visible_to_roles=["finance"])
        upsert_result = UpsertEntityResult(
            entity=updated, tag_confidence=None, split_recommendation=None, warnings=[]
        )

        with _PartnerContext("p-admin", is_admin=True):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.ontology_service") as mock_os, \
                 patch("zenos.interface.tools._audit_log") as mock_audit:
                mock_repo.get_by_id = AsyncMock(return_value=existing)
                mock_os.upsert_entity = AsyncMock(return_value=upsert_result)

                await write(
                    collection="entities",
                    data={"id": "ent-1", "visibility": "restricted",
                          "visible_to_roles": ["finance"]},
                )

            # Should have 2 audit calls: entity.upsert + visibility.change
            event_types = [c.kwargs.get("event_type") or c.args[0]
                          for c in mock_audit.call_args_list
                          if c.args or c.kwargs]
            # Check via keyword args
            governance_calls = [
                c for c in mock_audit.call_args_list
                if "governance.visibility.change" in str(c)
            ]
            assert len(governance_calls) >= 1

    async def test_no_visibility_change_no_extra_audit(self):
        """When visibility is unchanged, no governance.visibility.change event."""
        from zenos.interface.tools import write

        existing = _make_entity(visibility="public")
        upsert_result = UpsertEntityResult(
            entity=existing, tag_confidence=None, split_recommendation=None, warnings=[]
        )

        with _PartnerContext("p-admin", is_admin=True):
            with patch("zenos.interface.tools.entity_repo") as mock_repo, \
                 patch("zenos.interface.tools.ontology_service") as mock_os, \
                 patch("zenos.interface.tools._audit_log") as mock_audit:
                mock_repo.get_by_id = AsyncMock(return_value=existing)
                mock_os.upsert_entity = AsyncMock(return_value=upsert_result)

                await write(
                    collection="entities",
                    data={"id": "ent-1", "summary": "just text change"},
                )

            governance_calls = [
                c for c in mock_audit.call_args_list
                if "governance.visibility.change" in str(c)
            ]
            assert len(governance_calls) == 0
