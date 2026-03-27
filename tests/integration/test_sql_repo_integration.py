"""Integration tests for sql_repo.py — all tests hit real PostgreSQL.

Tests use a unique TEST_PREFIX per run to avoid collisions with production data.
Test partners are created in setup_module() and CASCADE-deleted in teardown_module(),
which cleans up all child entities, tasks, documents, and join-table rows.
Each test gets its own asyncpg pool (function-scoped) to avoid event-loop conflicts.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Integration tests require a live DB — skip in CI that sets SKIP_INTEGRATION=1
# ---------------------------------------------------------------------------

DB_URL = "postgresql://zenos_api:2b0db7508c18739e11488f36ff6d65ae41fdb3585ec43c99@127.0.0.1:55433/zenos"  # pragma: allowlist secret

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_INTEGRATION") == "1",
    reason="Integration tests skipped (SKIP_INTEGRATION=1)",
)

TEST_PREFIX = f"_test_{uuid.uuid4().hex[:8]}"
TEST_PARTNER_A = f"{TEST_PREFIX}_partner"
TEST_PARTNER_B = f"{TEST_PREFIX}_partner_b"
CONNECT_RETRIES = 5
CONNECT_RETRY_DELAY_SEC = 0.5


# ---------------------------------------------------------------------------
# Module-level setup / teardown for test partners
# ---------------------------------------------------------------------------

async def _connect_with_retry() -> asyncpg.Connection:
    for attempt in range(CONNECT_RETRIES):
        try:
            return await asyncpg.connect(DB_URL)
        except (OSError, ConnectionError, TimeoutError, asyncpg.PostgresError):
            if attempt == CONNECT_RETRIES - 1:
                raise
            await asyncio.sleep(CONNECT_RETRY_DELAY_SEC * (2 ** attempt))


async def _create_pool_with_retry() -> asyncpg.Pool:
    for attempt in range(CONNECT_RETRIES):
        try:
            return await asyncpg.create_pool(DB_URL, min_size=1, max_size=3)
        except (OSError, ConnectionError, TimeoutError, asyncpg.PostgresError):
            if attempt == CONNECT_RETRIES - 1:
                raise
            await asyncio.sleep(CONNECT_RETRY_DELAY_SEC * (2 ** attempt))


def setup_module(module):  # noqa: ARG001
    """Create test partners synchronously before any test runs."""
    async def _setup():
        conn = await _connect_with_retry()
        try:
            await conn.execute(
                """INSERT INTO zenos.partners (id, email, display_name, api_key, status)
                   VALUES ($1, $2, $3, $4, 'active')
                   ON CONFLICT (id) DO NOTHING""",
                TEST_PARTNER_A,
                f"{TEST_PREFIX}_a@test.com",
                f"Test Partner A {TEST_PREFIX}",
                f"{TEST_PREFIX}_key_a",  # pragma: allowlist secret
            )
            await conn.execute(
                """INSERT INTO zenos.partners (id, email, display_name, api_key, status)
                   VALUES ($1, $2, $3, $4, 'active')
                   ON CONFLICT (id) DO NOTHING""",
                TEST_PARTNER_B,
                f"{TEST_PREFIX}_b@test.com",
                f"Test Partner B {TEST_PREFIX}",
                f"{TEST_PREFIX}_key_b",  # pragma: allowlist secret
            )
        finally:
            await conn.close()

    asyncio.run(_setup())


def teardown_module(module):  # noqa: ARG001
    """Delete test partners (CASCADE deletes all related rows) after all tests."""
    async def _teardown():
        # Safety guard: never delete non-test partner rows from shared DB.
        assert TEST_PARTNER_A.startswith(TEST_PREFIX)
        assert TEST_PARTNER_B.startswith(TEST_PREFIX)
        conn = await _connect_with_retry()
        try:
            await conn.execute(
                "DELETE FROM zenos.partners WHERE id = ANY($1::text[])",
                [TEST_PARTNER_A, TEST_PARTNER_B],
            )
        finally:
            await conn.close()

    asyncio.run(_teardown())


# ---------------------------------------------------------------------------
# Per-test pool fixture — creates a fresh pool on each test's own event loop
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def pool():
    """Fresh asyncpg pool per test, tied to the test's own event loop."""
    p = await _create_pool_with_retry()
    yield p
    await p.close()


@pytest.fixture(autouse=True)
def set_partner_id_a():
    """Default to Partner A for all tests (overridable in specific tests)."""
    from zenos.infrastructure.context import current_partner_id

    token = current_partner_id.set(TEST_PARTNER_A)
    yield
    current_partner_id.reset(token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(name_suffix: str, etype: str = "product", parent_id: str | None = None):
    from zenos.domain.models import Entity, Tags

    return Entity(
        name=f"{TEST_PREFIX}_{name_suffix}",
        type=etype,
        summary=f"Summary for {name_suffix}",
        tags=Tags(what=["testing"], why="for integration test", how="pytest", who=["dev"]),
        level=1,
        status="active",
        parent_id=parent_id,
    )


def _make_task(title_suffix: str, status: str = "todo", assignee: str | None = None):
    from zenos.domain.models import Task

    return Task(
        title=f"{TEST_PREFIX}_{title_suffix}",
        status=status,
        priority="medium",
        created_by="test_runner",
        assignee=assignee,
        project=TEST_PREFIX,
    )


# ---------------------------------------------------------------------------
# 1. Entity CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_create_and_read(pool):
    from zenos.infrastructure.sql_repo import SqlEntityRepository

    repo = SqlEntityRepository(pool)
    entity = _make_entity("create_read")
    saved = await repo.upsert(entity)

    assert saved.id is not None
    fetched = await repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.name == entity.name
    assert fetched.summary == entity.summary
    assert fetched.type == entity.type
    assert fetched.tags.why == "for integration test"
    assert "testing" in fetched.tags.what


@pytest.mark.asyncio
async def test_entity_upsert_update(pool):
    from zenos.infrastructure.sql_repo import SqlEntityRepository

    repo = SqlEntityRepository(pool)
    entity = _make_entity("upsert_update")
    saved = await repo.upsert(entity)
    original_id = saved.id

    saved.name = f"{saved.name}_renamed"
    saved.summary = "Updated summary"
    updated = await repo.upsert(saved)

    assert updated.id == original_id
    fetched = await repo.get_by_id(original_id)
    assert fetched.name == f"{TEST_PREFIX}_upsert_update_renamed"
    assert fetched.summary == "Updated summary"


@pytest.mark.asyncio
async def test_entity_list_all_type_filter(pool):
    from zenos.infrastructure.sql_repo import SqlEntityRepository

    repo = SqlEntityRepository(pool)
    product_e = _make_entity("filter_product", etype="product")
    module_e = _make_entity("filter_module", etype="module")
    await repo.upsert(product_e)
    await repo.upsert(module_e)

    products = await repo.list_all(type_filter="product")
    product_names = {e.name for e in products}
    assert f"{TEST_PREFIX}_filter_product" in product_names
    assert f"{TEST_PREFIX}_filter_module" not in product_names

    modules = await repo.list_all(type_filter="module")
    module_names = {e.name for e in modules}
    assert f"{TEST_PREFIX}_filter_module" in module_names
    assert f"{TEST_PREFIX}_filter_product" not in module_names


@pytest.mark.asyncio
async def test_entity_list_by_parent(pool):
    from zenos.infrastructure.sql_repo import SqlEntityRepository

    repo = SqlEntityRepository(pool)
    parent = _make_entity("parent_node")
    saved_parent = await repo.upsert(parent)

    child = _make_entity("child_node", parent_id=saved_parent.id)
    await repo.upsert(child)

    children = await repo.list_by_parent(saved_parent.id)
    child_names = {e.name for e in children}
    assert f"{TEST_PREFIX}_child_node" in child_names


# ---------------------------------------------------------------------------
# 2. Relationship CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relationship_add_and_list(pool):
    from zenos.domain.models import Relationship
    from zenos.infrastructure.sql_repo import SqlEntityRepository, SqlRelationshipRepository

    entity_repo = SqlEntityRepository(pool)
    rel_repo = SqlRelationshipRepository(pool)

    src = await entity_repo.upsert(_make_entity("rel_src"))
    tgt = await entity_repo.upsert(_make_entity("rel_tgt"))

    rel = Relationship(
        source_entity_id=src.id,
        target_id=tgt.id,
        type="depends_on",
        description="test dependency",
    )
    saved_rel = await rel_repo.add(rel)
    assert saved_rel.id is not None

    by_src = await rel_repo.list_by_entity(src.id)
    assert saved_rel.id in {r.id for r in by_src}

    by_tgt = await rel_repo.list_by_entity(tgt.id)
    assert saved_rel.id in {r.id for r in by_tgt}


@pytest.mark.asyncio
async def test_relationship_find_duplicate(pool):
    from zenos.domain.models import Relationship
    from zenos.infrastructure.sql_repo import SqlEntityRepository, SqlRelationshipRepository

    entity_repo = SqlEntityRepository(pool)
    rel_repo = SqlRelationshipRepository(pool)

    src = await entity_repo.upsert(_make_entity("dup_src"))
    tgt = await entity_repo.upsert(_make_entity("dup_tgt"))

    rel = Relationship(
        source_entity_id=src.id,
        target_id=tgt.id,
        type="serves",
        description="serves relationship",
    )
    saved = await rel_repo.add(rel)

    found = await rel_repo.find_duplicate(src.id, tgt.id, "serves")
    assert found is not None
    assert found.id == saved.id

    not_found = await rel_repo.find_duplicate(src.id, tgt.id, "blocks")
    assert not_found is None


@pytest.mark.asyncio
async def test_relationship_list_all(pool):
    from zenos.domain.models import Relationship
    from zenos.infrastructure.sql_repo import SqlEntityRepository, SqlRelationshipRepository

    entity_repo = SqlEntityRepository(pool)
    rel_repo = SqlRelationshipRepository(pool)

    src = await entity_repo.upsert(_make_entity("listall_src"))
    tgt = await entity_repo.upsert(_make_entity("listall_tgt"))

    rel1 = await rel_repo.add(Relationship(source_entity_id=src.id, target_id=tgt.id, type="related_to", description="r1"))
    rel2 = await rel_repo.add(Relationship(source_entity_id=tgt.id, target_id=src.id, type="impacts", description="r2"))

    all_rels = await rel_repo.list_all()
    all_rel_ids = {r.id for r in all_rels}
    assert rel1.id in all_rel_ids
    assert rel2.id in all_rel_ids


# ---------------------------------------------------------------------------
# 3. Document CRUD + join table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_create_with_linked_entities(pool):
    from zenos.domain.models import Document, DocumentTags, Source
    from zenos.infrastructure.sql_repo import SqlDocumentRepository, SqlEntityRepository

    entity_repo = SqlEntityRepository(pool)
    doc_repo = SqlDocumentRepository(pool)

    entity = await entity_repo.upsert(_make_entity("doc_linked"))

    doc = Document(
        title=f"{TEST_PREFIX}_doc_create",
        source=Source(type="upload", uri="s3://bucket/doc.pdf", adapter="upload"),
        tags=DocumentTags(what=["spec"], why="testing", how="pytest", who=["dev"]),
        summary="Test document",
        linked_entity_ids=[entity.id],
    )
    saved = await doc_repo.upsert(doc)

    assert saved.id is not None
    fetched = await doc_repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.title == doc.title
    assert entity.id in fetched.linked_entity_ids


@pytest.mark.asyncio
async def test_document_update_linked_entities(pool):
    from zenos.domain.models import Document, DocumentTags, Source
    from zenos.infrastructure.sql_repo import SqlDocumentRepository, SqlEntityRepository

    entity_repo = SqlEntityRepository(pool)
    doc_repo = SqlDocumentRepository(pool)

    entity1 = await entity_repo.upsert(_make_entity("doc_upd_e1"))
    entity2 = await entity_repo.upsert(_make_entity("doc_upd_e2"))

    doc = Document(
        title=f"{TEST_PREFIX}_doc_update_links",
        source=Source(type="upload", uri="s3://bucket/d2.pdf", adapter="upload"),
        tags=DocumentTags(what=["spec"], why="testing", how="pytest", who=["dev"]),
        summary="Document to update links",
        linked_entity_ids=[entity1.id],
    )
    saved = await doc_repo.upsert(doc)

    # Replace linked entities: remove entity1, add entity2
    await doc_repo.update_linked_entities(saved.id, [entity2.id])

    fetched = await doc_repo.get_by_id(saved.id)
    assert entity2.id in fetched.linked_entity_ids
    assert entity1.id not in fetched.linked_entity_ids


# ---------------------------------------------------------------------------
# 4. Protocol CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_protocol_create_and_read(pool):
    from zenos.domain.models import Gap
    from zenos.domain.models import Protocol as OntologyProtocol
    from zenos.infrastructure.sql_repo import SqlEntityRepository, SqlProtocolRepository

    entity_repo = SqlEntityRepository(pool)
    proto_repo = SqlProtocolRepository(pool)

    entity = await entity_repo.upsert(_make_entity("proto_entity"))

    protocol = OntologyProtocol(
        entity_id=entity.id,
        entity_name=entity.name,
        content={"what": {"description": "test"}, "why": {}, "how": {}, "who": {}},
        gaps=[Gap(description="missing data", priority="yellow")],
        version="1.0",
    )
    saved = await proto_repo.upsert(protocol)
    assert saved.id is not None

    fetched = await proto_repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.entity_id == entity.id
    assert fetched.content["what"]["description"] == "test"
    assert len(fetched.gaps) == 1
    assert fetched.gaps[0].description == "missing data"
    assert fetched.gaps[0].priority == "yellow"


# ---------------------------------------------------------------------------
# 5. Blindspot CRUD + join table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blindspot_add_with_related_entities(pool):
    from zenos.domain.models import Blindspot
    from zenos.infrastructure.sql_repo import SqlBlindspotRepository, SqlEntityRepository

    entity_repo = SqlEntityRepository(pool)
    bs_repo = SqlBlindspotRepository(pool)

    entity = await entity_repo.upsert(_make_entity("blindspot_entity"))

    blindspot = Blindspot(
        description=f"{TEST_PREFIX} missing context for entity",
        severity="yellow",
        related_entity_ids=[entity.id],
        suggested_action="Add more documentation",
        status="open",
    )
    saved = await bs_repo.add(blindspot)
    assert saved.id is not None

    fetched = await bs_repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.description == blindspot.description
    assert entity.id in fetched.related_entity_ids


# ---------------------------------------------------------------------------
# 6. Task CRUD + join tables
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_create_and_read(pool):
    from zenos.infrastructure.sql_repo import SqlTaskRepository

    repo = SqlTaskRepository(pool)
    task = _make_task("basic_task")
    task.description = "Integration test task"
    task.acceptance_criteria = ["criterion one", "criterion two"]

    saved = await repo.upsert(task)
    assert saved.id is not None

    fetched = await repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.title == task.title
    assert fetched.status == "todo"
    assert fetched.priority == "medium"
    assert fetched.created_by == "test_runner"
    assert "criterion one" in fetched.acceptance_criteria
    assert "criterion two" in fetched.acceptance_criteria


@pytest.mark.asyncio
async def test_task_with_linked_entities_and_blockers(pool):
    from zenos.infrastructure.sql_repo import SqlEntityRepository, SqlTaskRepository

    entity_repo = SqlEntityRepository(pool)
    task_repo = SqlTaskRepository(pool)

    entity = await entity_repo.upsert(_make_entity("task_linked_entity"))

    task1 = _make_task("blocker_task", status="in_progress")
    saved_t1 = await task_repo.upsert(task1)

    task2 = _make_task("blocked_task", status="blocked")
    task2.blocked_reason = "waiting on blocker task"  # required by chk_tasks_blocked_reason
    task2.linked_entities = [entity.id]
    task2.blocked_by = [saved_t1.id]
    saved_t2 = await task_repo.upsert(task2)

    fetched = await task_repo.get_by_id(saved_t2.id)
    assert entity.id in fetched.linked_entities
    assert saved_t1.id in fetched.blocked_by


@pytest.mark.asyncio
async def test_task_list_all_filters(pool):
    from zenos.infrastructure.sql_repo import SqlTaskRepository

    repo = SqlTaskRepository(pool)

    from datetime import datetime, timezone

    t_alice = _make_task("filter_alice", status="todo", assignee="alice")
    t_bob = _make_task("filter_bob", status="done", assignee="bob")
    t_bob.completed_at = datetime.now(timezone.utc)  # required by chk_tasks_done_completed_at
    await repo.upsert(t_alice)
    await repo.upsert(t_bob)

    # Filter by assignee
    alice_tasks = await repo.list_all(assignee="alice", project=TEST_PREFIX)
    alice_titles = {t.title for t in alice_tasks}
    assert f"{TEST_PREFIX}_filter_alice" in alice_titles
    assert f"{TEST_PREFIX}_filter_bob" not in alice_titles

    # Filter by status
    done_tasks = await repo.list_all(status=["done"], project=TEST_PREFIX)
    done_titles = {t.title for t in done_tasks}
    assert f"{TEST_PREFIX}_filter_bob" in done_titles
    assert f"{TEST_PREFIX}_filter_alice" not in done_titles


@pytest.mark.asyncio
async def test_task_plan_fields_roundtrip(pool):
    """Task plan fields should persist and roundtrip through SQL repo."""
    from zenos.infrastructure.sql_repo import SqlTaskRepository

    repo = SqlTaskRepository(pool)
    task = _make_task("plan_roundtrip", status="todo")
    task.plan_id = f"{TEST_PREFIX}_plan_alpha"
    task.plan_order = 2
    task.depends_on_task_ids = ["task-pre-1", "task-pre-2"]

    saved = await repo.upsert(task)
    assert saved.id is not None

    fetched = await repo.get_by_id(saved.id)
    assert fetched is not None
    assert fetched.plan_id == f"{TEST_PREFIX}_plan_alpha"
    assert fetched.plan_order == 2
    assert fetched.depends_on_task_ids == ["task-pre-1", "task-pre-2"]


@pytest.mark.asyncio
async def test_task_plan_order_unique_per_partner_plan(pool):
    """Same partner + plan_id cannot reuse the same plan_order."""
    from zenos.infrastructure.sql_repo import SqlTaskRepository

    repo = SqlTaskRepository(pool)
    plan_id = f"{TEST_PREFIX}_plan_unique"

    t1 = _make_task("plan_unique_1", status="todo")
    t1.plan_id = plan_id
    t1.plan_order = 1
    await repo.upsert(t1)

    t2 = _make_task("plan_unique_2", status="todo")
    t2.plan_id = plan_id
    t2.plan_order = 1

    with pytest.raises(Exception):
        await repo.upsert(t2)


@pytest.mark.asyncio
async def test_task_plan_order_can_repeat_across_plans(pool):
    """The same plan_order is allowed when plan_id differs."""
    from zenos.infrastructure.sql_repo import SqlTaskRepository

    repo = SqlTaskRepository(pool)

    t1 = _make_task("plan_repeat_a", status="todo")
    t1.plan_id = f"{TEST_PREFIX}_plan_a"
    t1.plan_order = 1
    await repo.upsert(t1)

    t2 = _make_task("plan_repeat_b", status="todo")
    t2.plan_id = f"{TEST_PREFIX}_plan_b"
    t2.plan_order = 1
    saved_t2 = await repo.upsert(t2)

    assert saved_t2.id is not None


# ---------------------------------------------------------------------------
# 7. Cross-tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_entity_invisible(pool):
    """Entity created under Partner A must not be visible to Partner B."""
    from zenos.infrastructure.context import current_partner_id
    from zenos.infrastructure.sql_repo import SqlEntityRepository

    repo = SqlEntityRepository(pool)

    entity = _make_entity("tenant_isolation")
    saved = await repo.upsert(entity)
    assert saved.id is not None

    # Switch to Partner B
    token = current_partner_id.set(TEST_PARTNER_B)
    try:
        fetched = await repo.get_by_id(saved.id)
        assert fetched is None, "Partner B should not see Partner A's entity via get_by_id"

        all_entities = await repo.list_all()
        entity_ids = {e.id for e in all_entities}
        assert saved.id not in entity_ids, "Partner B should not see Partner A's entity in list_all"
    finally:
        current_partner_id.reset(token)


@pytest.mark.asyncio
async def test_cross_tenant_upsert_blocked(pool):
    """Partner B upsert with Partner A's entity ID must not overwrite A's data.

    ON CONFLICT (id) DO UPDATE WHERE partner_id = EXCLUDED.partner_id means
    the update is a no-op when partner_ids don't match. Partner A's data is intact.
    """
    from zenos.infrastructure.context import current_partner_id
    from zenos.infrastructure.sql_repo import SqlEntityRepository

    repo = SqlEntityRepository(pool)

    # Partner A creates entity
    entity_a = _make_entity("cross_tenant_upsert")
    entity_a.summary = "Original summary from A"
    saved_a = await repo.upsert(entity_a)

    # Partner B tries to upsert same ID with different data
    token = current_partner_id.set(TEST_PARTNER_B)
    try:
        attacker = _make_entity("cross_tenant_upsert")
        attacker.id = saved_a.id  # Same ID as A's entity
        attacker.summary = "Overwritten by B"
        await repo.upsert(attacker)
    finally:
        current_partner_id.reset(token)

    # Verify Partner A's data is unchanged
    fetched_a = await repo.get_by_id(saved_a.id)
    assert fetched_a is not None
    assert fetched_a.summary == "Original summary from A", (
        f"Partner A's summary should not be overwritten, got: {fetched_a.summary}"
    )


# ---------------------------------------------------------------------------
# 8. Transaction atomicity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_upsert_transaction_rollback(pool):
    """Upsert with a non-existent linked entity should either rollback or succeed.

    We verify the most important invariant: the task record must exist and be
    readable after any outcome. If FK constraint exists, the transaction rolls
    back and the original description is preserved. If no FK, the upsert
    succeeds — still verifiable.
    """
    from zenos.infrastructure.sql_repo import SqlTaskRepository

    repo = SqlTaskRepository(pool)

    task = _make_task("txn_rollback_task")
    task.description = "Original description"
    saved = await repo.upsert(task)
    task_id = saved.id
    original_description = saved.description

    # Upsert same task but with a non-existent linked entity
    saved.description = "Updated description"
    saved.linked_entities = ["nonexistent_entity_id_that_does_not_exist"]

    rolled_back = False
    try:
        await repo.upsert(saved)
    except Exception:
        rolled_back = True

    if rolled_back:
        # FK constraint exists — transaction should have rolled back
        # Re-read with original state
        saved.linked_entities = []
        fetched = await repo.get_by_id(task_id)
        assert fetched is not None, "Task record must still exist after rollback"
        assert fetched.description == original_description, (
            "After rollback, description should be unchanged"
        )
    else:
        # No FK constraint — upsert succeeded; task must still be readable
        fetched = await repo.get_by_id(task_id)
        assert fetched is not None, "Task must still exist after upsert"


# ---------------------------------------------------------------------------
# 9. SqlPartnerKeyValidator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partner_key_validator():
    """Validate using test partner's API key returns correct partner data."""
    import os

    from zenos.infrastructure.sql_repo import SqlPartnerKeyValidator

    os.environ["DATABASE_URL"] = DB_URL

    validator = SqlPartnerKeyValidator(ttl=0)  # ttl=0 forces refresh every call

    api_key = f"{TEST_PREFIX}_key_a"  # pragma: allowlist secret
    result = None
    for attempt in range(CONNECT_RETRIES):
        result = await validator.validate(api_key)
        if result is not None:
            break
        if attempt < CONNECT_RETRIES - 1:
            await asyncio.sleep(CONNECT_RETRY_DELAY_SEC * (2 ** attempt))

    assert result is not None, f"API key {api_key!r} should be valid"
    assert result["id"] == TEST_PARTNER_A
    assert result["email"] == f"{TEST_PREFIX}_a@test.com"
    assert result["status"] == "active"

    # Invalid key should return None
    invalid_result = await validator.validate("totally_invalid_key")
    assert invalid_result is None
