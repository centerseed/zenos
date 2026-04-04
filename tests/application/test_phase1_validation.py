import pytest
from unittest.mock import AsyncMock, MagicMock
from zenos.application.task_service import TaskService
from zenos.domain.validation import validate_document_frontmatter


def _make_uow_factory():
    """Create a mock UoW factory for testing."""
    uow = MagicMock()
    uow.conn = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    return lambda: uow


def _make_service(entities=None, relationships=None):
    task_repo = AsyncMock()
    task_repo.upsert = AsyncMock(side_effect=lambda t, **kw: t)
    task_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(
        side_effect=lambda eid: entities.get(eid) if entities else None
    )
    entity_repo.upsert = AsyncMock(side_effect=lambda e, **kw: e)
    entity_repo.list_all = AsyncMock(
        return_value=list(entities.values()) if entities else []
    )
    entity_repo.list_by_ids = AsyncMock(
        side_effect=lambda ids: [entities[i] for i in ids if i in entities] if entities else []
    )
    blindspot_repo = AsyncMock()
    blindspot_repo.add = AsyncMock(side_effect=lambda b, **kw: b)
    return TaskService(
        task_repo=task_repo,
        entity_repo=entity_repo,
        blindspot_repo=blindspot_repo,
        relationship_repo=relationships,
        uow_factory=_make_uow_factory(),
    )


def _mock_entity(eid, name="test", etype="module"):
    e = MagicMock()
    e.id = eid
    e.name = name
    e.type = etype
    e.status = "active"
    e.tags = MagicMock(what="x", why="x", how="x", who="x")
    return e


def _mock_relationship(rel_type, target_id):
    r = MagicMock()
    r.type = rel_type
    r.target_entity_id = target_id
    r.source_entity_id = "src"
    return r


@pytest.mark.asyncio
async def test_create_task_rejects_missing_linked_entities():
    svc = _make_service(entities={"e1": _mock_entity("e1")})
    with pytest.raises(ValueError, match="不存在的 entity ID"):
        await svc.create_task({
            "title": "修復登入流程問題",
            "created_by": "agent",
            "linked_entities": ["e1", "e999"],
        })


@pytest.mark.asyncio
async def test_create_task_accepts_valid_linked_entities():
    svc = _make_service(entities={"e1": _mock_entity("e1"), "e2": _mock_entity("e2")})
    result = await svc.create_task({
        "title": "修復登入流程問題",
        "created_by": "agent",
        "linked_entities": ["e1", "e2"],
    })
    assert result.task.title == "修復登入流程問題"


@pytest.mark.asyncio
async def test_create_task_accepts_empty_linked_entities():
    svc = _make_service(entities={})
    result = await svc.create_task({
        "title": "修復登入流程問題",
        "created_by": "agent",
        "linked_entities": [],
    })
    assert result.task is not None


@pytest.mark.asyncio
async def test_confirm_task_returns_suggested_entity_updates():
    e1 = _mock_entity("e1", "API Module", "module")
    e2 = _mock_entity("e2", "Rate Limiter", "module")
    rel_repo = AsyncMock()
    rel_repo.list_by_entity = AsyncMock(return_value=[
        _mock_relationship("impacts", "e2"),
    ])
    entities = {"e1": e1, "e2": e2}
    svc = _make_service(entities=entities, relationships=rel_repo)

    task_mock = MagicMock()
    task_mock.id = "t1"
    task_mock.title = "更新 API 限流"
    task_mock.status = "review"
    task_mock.linked_entities = ["e1"]
    task_mock.linked_blindspot = None
    task_mock.blocked_by = []
    svc._tasks.get_by_id = AsyncMock(return_value=task_mock)
    svc._tasks.list_all = AsyncMock(return_value=[])

    result = await svc.confirm_task("t1", accepted=True, updated_by="agent")
    assert result.suggested_entity_updates is not None
    assert len(result.suggested_entity_updates) == 1
    assert result.suggested_entity_updates[0]["entity_id"] == "e2"


@pytest.mark.asyncio
async def test_confirm_task_no_relationships_returns_empty_suggestions():
    e1 = _mock_entity("e1")
    svc = _make_service(entities={"e1": e1}, relationships=None)

    task_mock = MagicMock()
    task_mock.id = "t1"
    task_mock.title = "修復問題"
    task_mock.status = "review"
    task_mock.linked_entities = ["e1"]
    task_mock.linked_blindspot = None
    task_mock.blocked_by = []
    svc._tasks.get_by_id = AsyncMock(return_value=task_mock)
    svc._tasks.list_all = AsyncMock(return_value=[])

    result = await svc.confirm_task("t1", accepted=True, updated_by="agent")
    assert result.suggested_entity_updates == []


def test_validate_document_frontmatter_missing_title():
    errors, warnings = validate_document_frontmatter({"title": ""})
    assert any("title" in e.lower() or "Title" in e for e in errors)


def test_validate_document_frontmatter_no_linked_entity():
    errors, warnings = validate_document_frontmatter({"title": "Valid Title Here"})
    assert len(errors) == 0
    assert any("entity" in w for w in warnings)
