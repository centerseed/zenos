from __future__ import annotations

import copy

import pytest

from zenos.application.identity.home_workspace_bootstrap_service import HomeWorkspaceBootstrapService
from zenos.domain.knowledge import Entity, Relationship, Tags
from zenos.infrastructure.context import current_partner_id


def _tags() -> Tags:
    return Tags(what=["bootstrap"], why="why", how="how", who=["qa"])


class FakeEntityRepo:
    def __init__(self, workspaces: dict[str, list[Entity]]) -> None:
        self.workspaces = {key: [copy.deepcopy(entity) for entity in value] for key, value in workspaces.items()}

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        workspace_id = current_partner_id.get()
        entities = [copy.deepcopy(entity) for entity in self.workspaces.get(workspace_id, [])]
        if type_filter is None:
            return entities
        return [entity for entity in entities if entity.type == type_filter]

    async def upsert(self, entity: Entity) -> Entity:
        workspace_id = current_partner_id.get()
        entities = self.workspaces.setdefault(workspace_id, [])
        entity_to_store = copy.deepcopy(entity)
        if not entity_to_store.id:
            entity_to_store.id = f"{workspace_id}-entity-{len(entities) + 1}"
        for index, existing in enumerate(entities):
            if existing.id == entity_to_store.id:
                entities[index] = entity_to_store
                return copy.deepcopy(entity_to_store)
        entities.append(entity_to_store)
        return copy.deepcopy(entity_to_store)


class FakeRelationshipRepo:
    def __init__(self, workspaces: dict[str, list[Relationship]]) -> None:
        self.workspaces = {key: [copy.deepcopy(rel) for rel in value] for key, value in workspaces.items()}

    async def list_all(self) -> list[Relationship]:
        workspace_id = current_partner_id.get()
        return [copy.deepcopy(rel) for rel in self.workspaces.get(workspace_id, [])]

    async def find_duplicate(
        self,
        source_entity_id: str,
        target_id: str,
        rel_type: str,
    ) -> Relationship | None:
        workspace_id = current_partner_id.get()
        for rel in self.workspaces.get(workspace_id, []):
            if (
                rel.source_entity_id == source_entity_id
                and rel.target_id == target_id
                and rel.type == rel_type
            ):
                return copy.deepcopy(rel)
        return None

    async def add(self, rel: Relationship) -> Relationship:
        workspace_id = current_partner_id.get()
        rel_to_store = copy.deepcopy(rel)
        if not rel_to_store.id:
            rel_to_store.id = f"{workspace_id}-rel-{len(self.workspaces.get(workspace_id, [])) + 1}"
        self.workspaces.setdefault(workspace_id, []).append(rel_to_store)
        return copy.deepcopy(rel_to_store)


@pytest.mark.asyncio
async def test_reapply_preserves_existing_home_copy_and_reports_applied_sources():
    source_product = Entity(
        id="product-1",
        name="Shared Product",
        type="product",
        level=1,
        summary="source summary",
        tags=_tags(),
        status="active",
        visibility="public",
    )
    source_module = Entity(
        id="module-1",
        name="Shared Module",
        type="module",
        level=2,
        parent_id="product-1",
        summary="source module summary",
        tags=_tags(),
        status="active",
        visibility="public",
    )
    target_product = Entity(
        id="guest-product-1",
        name="Guest Product",
        type="product",
        level=1,
        summary="guest local summary",
        tags=Tags(what=["local"], why="guest", how="edit", who=["guest"]),
        status="active",
        visibility="public",
        confirmed_by_user=True,
        owner="Guest",
        details={
            "bootstrap_origin": {
                "source_workspace_id": "owner-shared-id",
                "source_entity_id": "product-1",
                "source_root_entity_id": "product-1",
                "bootstrap_applied_at": "2026-04-22T00:00:00+00:00",
            }
        },
    )
    target_module = Entity(
        id="guest-module-1",
        name="Guest Module",
        type="module",
        level=2,
        parent_id="guest-product-1",
        summary="guest local module summary",
        tags=Tags(what=["local-module"], why="guest", how="edit", who=["guest"]),
        status="active",
        visibility="public",
        confirmed_by_user=True,
        owner="Guest",
        details={
            "bootstrap_origin": {
                "source_workspace_id": "owner-shared-id",
                "source_entity_id": "module-1",
                "source_root_entity_id": "product-1",
                "bootstrap_applied_at": "2026-04-22T00:00:00+00:00",
            }
        },
    )

    entity_repo = FakeEntityRepo(
        {
            "owner-shared-id": [source_product, source_module],
            "guest-home-id": [target_product, target_module],
        }
    )
    relationship_repo = FakeRelationshipRepo(
        {
            "owner-shared-id": [
                Relationship(
                    id="source-rel-1",
                    source_entity_id="product-1",
                    target_id="module-1",
                    type="enables",
                    description="source relation",
                )
            ],
            "guest-home-id": [],
        }
    )

    service = HomeWorkspaceBootstrapService(entity_repo, relationship_repo)
    result = await service.apply(
        source_workspace_id="owner-shared-id",
        target_workspace_id="guest-home-id",
        source_root_entity_ids=["product-1"],
    )

    assert result.applied_source_entity_ids == ["product-1"]
    assert result.copied_root_entity_ids == ["guest-product-1"]
    assert result.copied_entity_count == 0
    assert result.copied_relationship_count == 1
    assert result.skipped_source_entity_ids == []

    refreshed_target_entities = entity_repo.workspaces["guest-home-id"]
    refreshed_product = next(entity for entity in refreshed_target_entities if entity.id == "guest-product-1")
    refreshed_module = next(entity for entity in refreshed_target_entities if entity.id == "guest-module-1")
    assert refreshed_product.summary == "guest local summary"
    assert refreshed_product.owner == "Guest"
    assert refreshed_product.confirmed_by_user is True
    assert refreshed_module.summary == "guest local module summary"
    assert refreshed_module.owner == "Guest"
    assert refreshed_module.confirmed_by_user is True

    target_relationships = relationship_repo.workspaces["guest-home-id"]
    assert len(target_relationships) == 1
    assert target_relationships[0].source_entity_id == "guest-product-1"
    assert target_relationships[0].target_id == "guest-module-1"


@pytest.mark.asyncio
async def test_apply_accepts_company_l1_root():
    source_company = Entity(
        id="company-1",
        name="Banila Co",
        type="company",
        level=1,
        summary="CRM company",
        tags=_tags(),
        status="active",
        visibility="public",
    )
    source_person = Entity(
        id="person-1",
        name="Alice",
        type="person",
        level=1,
        parent_id="company-1",
        summary="contact",
        tags=_tags(),
        status="active",
        visibility="public",
    )

    entity_repo = FakeEntityRepo(
        {
            "owner-shared-id": [source_company, source_person],
            "guest-home-id": [],
        }
    )
    relationship_repo = FakeRelationshipRepo(
        {
            "owner-shared-id": [
                Relationship(
                    id="source-rel-1",
                    source_entity_id="company-1",
                    target_id="person-1",
                    type="enables",
                    description="company relation",
                )
            ],
            "guest-home-id": [],
        }
    )

    service = HomeWorkspaceBootstrapService(entity_repo, relationship_repo)
    result = await service.apply(
        source_workspace_id="owner-shared-id",
        target_workspace_id="guest-home-id",
        source_root_entity_ids=["company-1"],
    )

    assert result.applied_source_entity_ids == ["company-1"]
    assert result.copied_entity_count == 2
    assert result.copied_relationship_count == 1
    assert result.skipped_source_entity_ids == []
