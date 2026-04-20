"""AC tests for recent change surfacing."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.action import Task
from zenos.application.action.task_service import TaskResult
from zenos.domain.knowledge import Entity, EntityEntry, Tags
from zenos.infrastructure.context import current_partner_id
from zenos.interface.mcp._auth import _current_partner


def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-1",
        name="Paceriz",
        type="product",
        summary="Running coach product",
        tags=Tags(what=["marketing"], why="growth", how="campaign", who=["team"]),
        level=1,
        status="active",
        parent_id=None,
        confirmed_by_user=True,
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        change_summary=None,
        summary_updated_at=None,
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_doc_entity(**overrides) -> Entity:
    defaults = dict(
        id="doc-1",
        name="Marketing Strategy",
        type="document",
        summary="Marketing strategy doc",
        tags=Tags(what=["marketing"], why="strategy", how="campaign", who=["team"]),
        level=3,
        status="current",
        parent_id="ent-1",
        confirmed_by_user=True,
        created_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        change_summary="Updated campaign scope for Q2",
        summary_updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_entry(**overrides) -> EntityEntry:
    defaults = dict(
        id="entry-1",
        partner_id="partner-abc",
        entity_id="ent-2",
        type="change",
        content="Marketing CTA changed for the landing page",
        status="active",
        context="campaign=threads",
        author="Barry",
        department="marketing",
        source_task_id=None,
        superseded_by=None,
        archive_reason=None,
        created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return EntityEntry(**defaults)


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Publish campaign update",
        status="done",
        priority="medium",
        created_by="partner-abc",
        linked_entities=["ent-1"],
        result="completed",
        project="paceriz",
    )
    defaults.update(overrides)
    return Task(**defaults)


def _configure_repos(
    entities: list[Entity],
    *,
    entry_map: dict[str, list[EntityEntry]] | None = None,
    search_hits: list[dict] | None = None,
    product: Entity | None = None,
) -> None:
    import zenos.interface.mcp as tools_mod

    entity_name_map = {entity.id: entity.name for entity in entities if entity.id}
    tools_mod.entity_repo.list_all = AsyncMock(return_value=entities)
    tools_mod.entity_repo.get_by_name = AsyncMock(
        side_effect=lambda name: next((entity for entity in entities if entity.name == name), product)
    )
    tools_mod.entity_repo.get_by_id = AsyncMock(
        side_effect=lambda entity_id: next((entity for entity in entities if entity.id == entity_id), product)
    )

    if search_hits is None:
        search_hits = []
        for entity_id, entries in (entry_map or {}).items():
            for entry in entries:
                search_hits.append(
                    {
                        "entry": entry,
                        "entity_name": entity_name_map.get(entity_id),
                    }
                )
    tools_mod.entry_repo.search_content = AsyncMock(return_value=search_hits)

    async def _list_by_entity(entity_id: str, status: str | None = "active", department: str | None = None):
        return list((entry_map or {}).get(entity_id, []))

    tools_mod.entry_repo.list_by_entity = AsyncMock(side_effect=_list_by_entity)


def _make_partner_context():
    partner = {"id": "partner-abc", "department": "marketing", "isAdmin": True, "roles": ["admin"]}
    token_partner = _current_partner.set(partner)
    token_pid = current_partner_id.set("partner-abc")
    return token_partner, token_pid


def _reset_partner_context(tokens):
    token_partner, token_pid = tokens
    current_partner_id.reset(token_pid)
    _current_partner.reset(token_partner)


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.entity_repo", new=MagicMock()), \
         patch("zenos.interface.mcp.entry_repo", new=MagicMock()), \
         patch("zenos.interface.mcp._journal_repo", new=None):
        yield


# ---------------------------------------------------------------------------
# AC-RCS-01 ~ AC-RCS-06: contract/workflow behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ac_rcs_01_material_change_without_change_summary_is_rejected():
    """AC-RCS-01: Given material_change 的 document 寫入, When change_summary 缺失, Then MCP 必須直接拒絕，不能把它當完成"""
    from zenos.interface.mcp import write
    import zenos.interface.mcp as tools_mod

    tokens = _make_partner_context()
    try:
        doc_entity = _make_doc_entity()
        tools_mod.ontology_service = MagicMock()
        tools_mod.ontology_service.upsert_document = AsyncMock(return_value=doc_entity)
        tools_mod.entity_repo.get_by_id = AsyncMock(return_value=_make_entity())

        result = await write(
            collection="documents",
            data={
                "title": "Marketing Strategy",
                "source": {"type": "github", "uri": "https://github.com/org/repo/blob/main/marketing.md", "adapter": "github"},
                "tags": {"what": ["marketing"], "why": "strategy", "how": "campaign", "who": ["team"]},
                "summary": "Marketing strategy doc",
                "linked_entity_ids": ["ent-1"],
                "material_change": True,
            },
        )

        assert result["status"] == "rejected"
        assert result["rejection_reason"] == "material_change_requires_change_summary"
        tools_mod.ontology_service.upsert_document.assert_not_called()
    finally:
        _reset_partner_context(tokens)


@pytest.mark.asyncio
async def test_ac_rcs_02_material_change_with_change_summary_is_accepted():
    """AC-RCS-02: Given material_change 的 document 寫入, When change_summary 已提供, Then MCP 必須放行給真正的 document upsert"""
    from zenos.interface.mcp import write
    import zenos.interface.mcp as tools_mod

    tokens = _make_partner_context()
    try:
        doc_entity = _make_doc_entity(
            change_summary="Updated campaign scope for Q2",
            summary_updated_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        )
        tools_mod.ontology_service = MagicMock()
        tools_mod.ontology_service.upsert_document = AsyncMock(return_value=doc_entity)
        tools_mod.entity_repo.get_by_id = AsyncMock(return_value=_make_entity())

        result = await write(
            collection="documents",
            data={
                "title": "Marketing Strategy",
                "source": {"type": "github", "uri": "https://github.com/org/repo/blob/main/marketing.md", "adapter": "github"},
                "tags": {"what": ["marketing"], "why": "strategy", "how": "campaign", "who": ["team"]},
                "summary": "Marketing strategy doc",
                "linked_entity_ids": ["ent-1"],
                "material_change": True,
                "change_summary": "Updated campaign scope for Q2",
            },
        )

        assert result["status"] == "ok"
        assert result["data"]["change_summary"] == "Updated campaign scope for Q2"
        assert result["data"]["summary_updated_at"] == "2026-04-20T00:00:00+00:00"
        tools_mod.ontology_service.upsert_document.assert_awaited_once()
    finally:
        _reset_partner_context(tokens)


@pytest.mark.asyncio
async def test_ac_rcs_03_bundle_operation_material_change_without_change_summary_is_rejected():
    """AC-RCS-03: Given bundle operation 屬實質變更, When payload 沒有 change_summary, Then workflow 必須被拒絕，不能宣稱同步完成"""
    from zenos.interface.mcp import write
    import zenos.interface.mcp as tools_mod

    tokens = _make_partner_context()
    try:
        tools_mod.ontology_service = MagicMock()
        tools_mod.ontology_service.upsert_document = AsyncMock()
        tools_mod.entity_repo.get_by_id = AsyncMock(return_value=_make_entity())

        result = await write(
            collection="documents",
            data={
                "title": "Marketing Strategy",
                "source": {"type": "github", "uri": "https://github.com/org/repo/blob/main/marketing.md", "adapter": "github"},
                "tags": {"what": ["marketing"], "why": "strategy", "how": "campaign", "who": ["team"]},
                "summary": "Marketing strategy doc",
                "linked_entity_ids": ["ent-1"],
                "material_change": True,
                "add_source": {
                    "uri": "https://github.com/org/repo/blob/main/marketing-v2.md",
                    "type": "github",
                    "label": "marketing v2",
                },
            },
        )

        assert result["status"] == "rejected"
        assert result["rejection_reason"] == "material_change_requires_change_summary"
        tools_mod.ontology_service.upsert_document.assert_not_called()
    finally:
        _reset_partner_context(tokens)


@pytest.mark.asyncio
async def test_ac_rcs_04_l2_impact_task_confirm_writes_change_entry():
    """AC-RCS-04: Given 文件更新影響既有 L2, When workflow 完成任務驗收, Then 至少 1 個相關 entity 必須新增 entry(type=\"change\")"""
    from zenos.interface.mcp import confirm
    import zenos.interface.mcp as tools_mod

    tokens = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        _configure_repos([product, module], product=product)
        tools_mod.task_service = MagicMock()
        tools_mod.task_service.confirm_task = AsyncMock(
            return_value=TaskResult(task=_make_task(linked_entities=["ent-2"]), cascade_updates=[])
        )
        tools_mod.task_service.enrich_task = AsyncMock(
            return_value={"expanded_entities": [{"id": "ent-2", "name": "Campaign Ops"}]}
        )
        tools_mod.entry_repo.create = AsyncMock(side_effect=lambda entry: entry)

        entries = [
            {
                "entity_id": "ent-2",
                "type": "change",
                "content": "2026-04-20 Campaign Ops 的外部溝通口徑已改，行銷要同步更新公告。",
                "context": "source=sync",
            }
        ]
        result = await confirm(collection="tasks", id="task-1", accepted=True, entity_entries=entries)

        assert result["status"] == "ok"
        assert tools_mod.entry_repo.create.call_count == 1
        created_entry = tools_mod.entry_repo.create.await_args.args[0]
        assert created_entry.type == "change"
        assert created_entry.entity_id == "ent-2"
        assert "外部溝通口徑" in created_entry.content
    finally:
        _reset_partner_context(tokens)


@pytest.mark.asyncio
async def test_ac_rcs_05_l3_only_change_does_not_invent_change_entry():
    """AC-RCS-05: Given 只有 L3 文件整理、workflow 沒有提供 change entry, Then confirm 不得自己硬補 entry(type=\"change\")"""
    from zenos.interface.mcp import confirm
    import zenos.interface.mcp as tools_mod

    tokens = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        _configure_repos([product, module], product=product)
        tools_mod.task_service = MagicMock()
        tools_mod.task_service.confirm_task = AsyncMock(
            return_value=TaskResult(task=_make_task(linked_entities=["ent-2"]), cascade_updates=[])
        )
        tools_mod.task_service.enrich_task = AsyncMock(
            return_value={"expanded_entities": [{"id": "ent-2", "name": "Campaign Ops"}]}
        )
        tools_mod.entry_repo.create = AsyncMock(side_effect=lambda entry: entry)

        result = await confirm(collection="tasks", id="task-1", accepted=True)

        assert result["status"] == "ok"
        tools_mod.entry_repo.create.assert_not_called()
    finally:
        _reset_partner_context(tokens)


@pytest.mark.asyncio
async def test_ac_rcs_06_change_entry_content_must_describe_impacted_concept():
    """AC-RCS-06: Given workflow 有提供 change entry, Then confirm 必須把內容與 context 原樣寫入，讓受影響概念與對象清楚可查"""
    from zenos.interface.mcp import confirm
    import zenos.interface.mcp as tools_mod

    tokens = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        _configure_repos([product, module], product=product)
        tools_mod.task_service = MagicMock()
        tools_mod.task_service.confirm_task = AsyncMock(
            return_value=TaskResult(task=_make_task(linked_entities=["ent-2"]), cascade_updates=[])
        )
        tools_mod.task_service.enrich_task = AsyncMock(
            return_value={"expanded_entities": [{"id": "ent-2", "name": "Campaign Ops"}]}
        )
        tools_mod.entry_repo.create = AsyncMock(side_effect=lambda entry: entry)

        change_content = "2026-04-20 Campaign Ops 的外部溝通口徑已改，行銷要同步更新公告。"
        result = await confirm(
            collection="tasks",
            id="task-1",
            accepted=True,
            entity_entries=[
                {
                    "entity_id": "ent-2",
                    "type": "change",
                    "content": change_content,
                    "context": "source=sync",
                }
            ],
        )

        assert result["status"] == "ok"
        created_entry = tools_mod.entry_repo.create.await_args.args[0]
        assert created_entry.content == change_content
        assert created_entry.content != "Updated campaign scope for Q2"
        assert "Campaign Ops" in created_entry.content
        assert "行銷" in created_entry.content
    finally:
        _reset_partner_context(tokens)


@pytest.mark.asyncio
async def test_ac_rcs_07_recent_updates_by_product_and_since():
    """AC-RCS-07: Given product=Paceriz 且 since=14d, When 查 recent changes, Then response 必須優先包含最近 14 天內有 change_summary 的 documents 與 entry(type=\"change\")"""
    from zenos.interface.mcp.recent_updates import recent_updates
    import zenos.interface.mcp as tools_mod

    token = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        doc = _make_doc_entity()
        entry = _make_entry(entity_id="ent-2")

        _configure_repos(
            [product, module, doc],
            entry_map={"ent-2": [entry]},
            product=product,
        )
        tools_mod._journal_repo = MagicMock()
        tools_mod._journal_repo.list_recent = AsyncMock(return_value=([], 0))
        tools_mod._ensure_journal_repo = AsyncMock(return_value=None)

        result = await recent_updates(product="Paceriz", since_days=14, limit=10)
        data = result["data"]

        assert result["status"] == "ok"
        assert data["scope"]["resolved_product"] == "Paceriz"
        assert data["count"] == 2
        kinds = {item["kind"] for item in data["results"]}
        assert kinds == {"document_change", "entity_change"}
    finally:
        _reset_partner_context(token)


@pytest.mark.asyncio
async def test_ac_rcs_08_recent_updates_filters_by_topic_then_sorts_by_time():
    """AC-RCS-08: Given product=Paceriz、topic=marketing、since=14d, When 查 recent changes, Then response 必須先過濾 topic 關聯, 再按時間新到舊排序, 而不是只按 semantic score"""
    from zenos.interface.mcp.recent_updates import recent_updates

    token = _make_partner_context()
    try:
        product = _make_entity()
        module_new = _make_entity(id="ent-2", name="Marketing Ops", type="module", level=2, parent_id="ent-1")
        module_old = _make_entity(id="ent-3", name="Marketing Legacy", type="module", level=2, parent_id="ent-1")
        doc_new = _make_doc_entity(id="doc-1", parent_id="ent-3", updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc))
        doc_old = _make_doc_entity(
            id="doc-2",
            name="Marketing Brief",
            parent_id="ent-2",
            updated_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
            summary_updated_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
            change_summary="Marketing copy updated",
        )
        entry_new = _make_entry(id="entry-2", entity_id="ent-2", created_at=datetime(2026, 4, 20, tzinfo=timezone.utc))
        entry_old = _make_entry(id="entry-3", entity_id="ent-3", created_at=datetime(2026, 4, 18, tzinfo=timezone.utc))

        _configure_repos(
            [product, module_new, module_old, doc_new, doc_old],
            entry_map={"ent-2": [entry_new], "ent-3": [entry_old]},
            product=product,
        )

        result = await recent_updates(product="Paceriz", topic="marketing", since_days=14, limit=10)
        data = result["data"]

        assert result["status"] == "ok"
        assert data["count"] == 2
        updated_at_values = [item["updated_at"] for item in data["results"]]
        assert updated_at_values == sorted(updated_at_values, reverse=True)
        assert all(item["topic_match"]["matched"] for item in data["results"])
        assert all(item["kind"] == "document_change" for item in data["results"])
    finally:
        _reset_partner_context(token)


@pytest.mark.asyncio
async def test_ac_rcs_09_recent_updates_does_not_depend_on_journal_primary():
    """AC-RCS-09: Given 有對應的 recent changes 結果, When agent 回答最近更新了什麼, Then 不需要先讀 journal 才能找到主要變更"""
    from zenos.interface.mcp.recent_updates import recent_updates
    import zenos.interface.mcp as tools_mod

    token = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        doc = _make_doc_entity()
        entry = _make_entry(entity_id="ent-2")

        _configure_repos(
            [product, module, doc],
            entry_map={"ent-2": [entry]},
            product=product,
        )
        tools_mod._journal_repo = MagicMock()
        tools_mod._journal_repo.list_recent = AsyncMock(return_value=([{"summary": "journal only"}], 1))
        tools_mod._ensure_journal_repo = AsyncMock(return_value=None)

        result = await recent_updates(product="Paceriz", since_days=14, limit=10)

        assert result["status"] == "ok"
        tools_mod._journal_repo.list_recent.assert_not_called()
    finally:
        _reset_partner_context(token)


@pytest.mark.asyncio
async def test_ac_rcs_10_recent_updates_response_includes_why_it_matters():
    """AC-RCS-10: Given recent changes query 命中多筆結果, When response 回傳, Then 每筆結果都必須帶 why_it_matters, 讓 agent 不必二次猜測重要性"""
    from zenos.interface.mcp.recent_updates import recent_updates

    token = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        doc = _make_doc_entity()
        entry = _make_entry(entity_id="ent-2")

        _configure_repos(
            [product, module, doc],
            entry_map={"ent-2": [entry]},
            product=product,
        )

        result = await recent_updates(product="Paceriz", since_days=14, limit=10)
        results = result["data"]["results"]

        assert all(item["why_it_matters"] for item in results)
    finally:
        _reset_partner_context(token)


@pytest.mark.asyncio
async def test_ac_rcs_11_recent_updates_groups_document_and_entity_change():
    """AC-RCS-11: Given 某筆結果同時有 document change 與 entity change entry, When response 組裝, Then 可以同組呈現, 但不得重複列成兩條看起來無關的更新"""
    from zenos.interface.mcp.recent_updates import recent_updates

    token = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        doc = _make_doc_entity(parent_id="ent-2")
        entry = _make_entry(entity_id="ent-2")

        _configure_repos(
            [product, module, doc],
            entry_map={"ent-2": [entry]},
            product=product,
        )

        result = await recent_updates(product="Paceriz", since_days=14, limit=10)
        results = result["data"]["results"]

        assert len(results) == 1
        assert results[0]["kind"] == "document_change"
        assert len(results[0]["related_change_entries"]) == 1
    finally:
        _reset_partner_context(token)


@pytest.mark.asyncio
async def test_ac_rcs_12_recent_updates_prefers_knowledge_layer_over_journal():
    """AC-RCS-12: Given 有 change_summary 或 entry(type=\"change\"), When recent changes 組裝結果, Then 不得優先採用 journal summary 蓋過知識層內容"""
    from zenos.interface.mcp.recent_updates import recent_updates
    import zenos.interface.mcp as tools_mod

    token = _make_partner_context()
    try:
        product = _make_entity()
        module = _make_entity(id="ent-2", name="Campaign Ops", type="module", level=2, parent_id="ent-1")
        doc = _make_doc_entity(parent_id="ent-2")
        entry = _make_entry(entity_id="ent-2")

        _configure_repos(
            [product, module, doc],
            entry_map={"ent-2": [entry]},
            product=product,
        )
        tools_mod._journal_repo = MagicMock()
        tools_mod._journal_repo.list_recent = AsyncMock(return_value=([{"summary": "journal should lose"}], 1))
        tools_mod._ensure_journal_repo = AsyncMock(return_value=None)

        result = await recent_updates(product="Paceriz", since_days=14, limit=10)
        results = result["data"]["results"]

        assert result["status"] == "ok"
        assert results[0]["source"] == "document.change_summary"
        tools_mod._journal_repo.list_recent.assert_not_called()
    finally:
        _reset_partner_context(token)


@pytest.mark.asyncio
async def test_ac_rcs_13_journal_only_result_marked_as_governance_gap():
    """AC-RCS-13: Given 某次變更只有 journal、沒有 document/entity change 痕跡, When recent changes 查詢, Then 該結果最多作為 fallback, 並標記為治理缺口"""
    from zenos.interface.mcp.recent_updates import recent_updates
    import zenos.interface.mcp as tools_mod

    token = _make_partner_context()
    try:
        product = _make_entity()
        _configure_repos([product], entry_map={}, product=product)
        tools_mod._journal_repo = MagicMock()
        tools_mod._journal_repo.list_recent = AsyncMock(
            return_value=(
                [
                    {
                        "id": "journal-1",
                        "created_at": datetime(2026, 4, 20, tzinfo=timezone.utc),
                        "project": "Paceriz",
                        "flow_type": "research",
                        "summary": "Only journal evidence for a release note",
                        "tags": ["marketing"],
                        "is_summary": False,
                    }
                ],
                1,
            )
        )
        tools_mod._ensure_journal_repo = AsyncMock(return_value=None)

        result = await recent_updates(product="Paceriz", since_days=14, limit=10)
        data = result["data"]

        assert result["status"] == "ok"
        assert data["fallback_used"] is True
        assert data["governance_gap"] is True
        assert data["results"][0]["source"] == "journal"
        assert data["results"][0]["governance_gap"] is True
    finally:
        _reset_partner_context(token)
