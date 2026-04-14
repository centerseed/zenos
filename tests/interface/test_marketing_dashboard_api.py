"""Tests for Marketing Dashboard REST API handlers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from zenos.domain.knowledge import Entity, Tags


def _make_request(
    method: str = "GET",
    headers: dict | None = None,
    path_params: dict | None = None,
    query_params: dict | None = None,
    json_body: dict | None = None,
) -> MagicMock:
    req = MagicMock()
    req.method = method
    req.headers = headers or {}
    req.path_params = path_params or {}
    req.query_params = query_params or {}
    req.json = AsyncMock(return_value=json_body or {})
    return req


def _partner() -> dict:
    return {
        "id": "p1",
        "email": "user@test.com",
        "displayName": "Test User",
        "isAdmin": False,
    }


def _product_entity(eid: str = "prod-1", name: str = "Paceriz") -> Entity:
    return Entity(
        id=eid,
        name=name,
        type="product",
        level=1,
        parent_id=None,
        status="active",
        summary=f"{name} product",
        tags=Tags(what=["product"], why="", how="", who=[]),
        details={},
        confirmed_by_user=True,
        sources=[],
        owner="Alice",
        visibility="public",
        created_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
    )


def _project_entity(eid: str = "proj-1", parent_id: str = "prod-1", project_type: str = "long_term") -> Entity:
    return Entity(
        id=eid,
        name="官網 Blog",
        type="module",
        level=2,
        parent_id=parent_id,
        status="active",
        summary="教跑者怎麼練",
        tags=Tags(what=["marketing"], why="", how="", who=[]),
        details={
            "marketing": {
                "project_status": "active",
                "project_type": project_type,
            }
        },
        confirmed_by_user=True,
        sources=[],
        owner="Alice",
        visibility="public",
        created_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
    )


def _post_entity(eid: str, parent_id: str, workflow_status: str) -> Entity:
    return Entity(
        id=eid,
        name=f"post-{eid}",
        type="document",
        level=3,
        parent_id=parent_id,
        status=workflow_status,
        summary="post preview",
        tags=Tags(what=["marketing"], why="", how="", who=[]),
        details={
            "marketing": {
                "platform": "Threads",
                "workflow_status": workflow_status,
                "preview": "preview text",
            }
        },
        confirmed_by_user=True,
        sources=[],
        owner="Alice",
        visibility="public",
        created_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
    )


def _strategy_doc_entity(
    eid: str = "strategy-1",
    parent_id: str = "proj-1",
    *,
    updated_at: datetime | None = None,
    project_type: str = "long_term",
) -> Entity:
    stamp = updated_at or datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
    return Entity(
        id=eid,
        name="官網 Blog Strategy",
        type="document",
        level=3,
        parent_id=parent_id,
        status="active",
        summary="先建立穩定跑步習慣；tone=專業；platforms=threads, blog",
        tags=Tags(what=["marketing", "strategy"], why="", how="", who=[]),
        details={
            "marketing": {
                "doc_kind": "strategy",
                "project_type": project_type,
                "strategy": {
                    "audience": ["A 層"],
                    "tone": "專業",
                    "core_message": "先建立穩定跑步習慣",
                    "platforms": ["threads", "blog"],
                    "frequency": "每週 3 篇",
                    "content_mix": {"education": 70, "product": 30},
                    "cta_strategy": "引導免費試用",
                },
                "strategy_content": "# Strategy\n- core_message: 先建立穩定跑步習慣",
            }
        },
        confirmed_by_user=True,
        sources=[],
        owner="Alice",
        visibility="public",
        created_at=stamp,
        updated_at=stamp,
    )


def _style_entity(
    eid: str,
    parent_id: str,
    level: str,
    *,
    platform: str | None = None,
    project_id: str | None = None,
) -> Entity:
    return Entity(
        id=eid,
        name=f"{level}-style",
        type="document",
        level=3,
        parent_id=parent_id,
        status="active",
        summary="style preview",
        tags=Tags(what=["marketing", "style"], why="", how="", who=[]),
        details={
            "marketing": {
                "style_level": level,
                "style_platform": platform,
                "style_project_id": project_id,
                "style_content": f"{level} content",
            }
        },
        confirmed_by_user=True,
        sources=[],
        owner="Alice",
        visibility="public",
        created_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 12, tzinfo=timezone.utc),
    )


class TestProjects:
    async def test_list_projects_returns_product_grouped_payload(self):
        from zenos.interface.marketing_dashboard_api import list_projects

        request = _make_request(headers={"authorization": "Bearer token"})
        product = _product_entity("prod-1", "Paceriz")
        project = _project_entity("proj-1", "prod-1")
        review_post = _post_entity("p1", "proj-1", "draft_generated")
        published_post = _post_entity("p2", "proj-1", "published")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            async def list_all(*, type_filter=None):
                if type_filter == "product":
                    return [product]
                if type_filter == "module":
                    return [project]
                if type_filter == "document":
                    return [review_post, published_post]
                return []

            mock_entity_repo.list_all = AsyncMock(side_effect=list_all)
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await list_projects(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert len(body["groups"]) == 1
        group = body["groups"][0]
        assert group["product"]["id"] == "prod-1"
        assert group["product"]["name"] == "Paceriz"
        assert len(group["projects"]) == 1
        assert group["projects"][0]["id"] == "proj-1"
        assert group["projects"][0]["projectType"] == "long_term"
        assert group["projects"][0]["thisWeek"]["published"] == 1

    async def test_get_project_detail_returns_project_payload(self):
        from zenos.interface.marketing_dashboard_api import get_project_detail

        request = _make_request(
            headers={"authorization": "Bearer token"},
            path_params={"projectId": "proj-1"},
        )
        project = _project_entity("proj-1", "prod-1")
        draft_post = _post_entity("p1", "proj-1", "topic_planned")
        strategy_doc = _strategy_doc_entity(parent_id="proj-1")

        mock_entry = MagicMock()
        mock_entry.id = "entry-1"
        mock_entry.type = "decision"
        mock_entry.content = "strategy note"
        mock_entry.context = "ctx"
        mock_entry.author = "Alice"
        mock_entry.created_at = datetime(2026, 4, 12, tzinfo=timezone.utc)

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api._entry_repo"
        ) as mock_entry_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=project)
            mock_entity_repo.list_by_parent = AsyncMock(return_value=[draft_post, strategy_doc])
            mock_entry_repo.list_by_entity = AsyncMock(return_value=[mock_entry])
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await get_project_detail(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["project"]["id"] == "proj-1"
        assert body["project"]["projectType"] == "long_term"
        assert body["project"]["strategy"]["documentId"] == strategy_doc.id
        assert len(body["project"]["posts"]) == 1
        assert len(body["project"]["entries"]) == 1

    async def test_create_project_requires_date_range_for_short_term(self):
        from zenos.interface.marketing_dashboard_api import create_project

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer token"},
            json_body={"productId": "prod-1", "name": "夏季增肌挑戰", "projectType": "short_term"},
        )

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ):
            resp = await create_project(request)

        assert resp.status_code == 400

    async def test_create_project_returns_project_payload(self):
        from zenos.interface.marketing_dashboard_api import create_project

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer token"},
            json_body={
                "productId": "prod-1",
                "name": "夏季增肌挑戰",
                "projectType": "short_term",
                "dateRange": {"start": "2026-05-01", "end": "2026-05-31"},
            },
        )

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api._entry_repo"
        ) as mock_entry_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.upsert = AsyncMock(side_effect=lambda entity: entity)
            mock_entry_repo.create = AsyncMock()
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await create_project(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["project"]["name"] == "夏季增肌挑戰"
        assert body["project"]["projectType"] == "short_term"
        assert body["project"]["dateRange"]["start"] == "2026-05-01"

    async def test_update_project_strategy_validates_required_fields(self):
        from zenos.interface.marketing_dashboard_api import update_project_strategy

        request = _make_request(
            method="PUT",
            headers={"authorization": "Bearer token"},
            path_params={"projectId": "proj-1"},
            json_body={"tone": "專業友善"},
        )
        project = _project_entity("proj-1", "prod-1")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=project)
            mock_entity_repo.list_by_parent = AsyncMock(return_value=[])
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await update_project_strategy(request)

        assert resp.status_code == 400

    async def test_update_project_strategy_returns_new_schema(self):
        from zenos.interface.marketing_dashboard_api import update_project_strategy

        existing_strategy_doc = _strategy_doc_entity(
            parent_id="proj-1",
            updated_at=datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        )
        original_updated_at = existing_strategy_doc.updated_at.isoformat()
        request = _make_request(
            method="PUT",
            headers={"authorization": "Bearer token"},
            path_params={"projectId": "proj-1"},
            json_body={
                "audience": ["跑步新手", "準備回歸訓練的人"],
                "tone": "專業友善",
                "coreMessage": "先恢復穩定跑步頻率",
                "platforms": ["threads", "blog"],
                "frequency": "每週 2 篇",
                "contentMix": {"education": 70, "product": 30},
                "ctaStrategy": "引導免費試用",
                "expectedUpdatedAt": existing_strategy_doc.updated_at.isoformat(),
            },
        )
        project = _project_entity("proj-1", "prod-1")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api._entry_repo"
        ) as mock_entry_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=project)
            mock_entity_repo.upsert = AsyncMock(side_effect=lambda entity: entity)
            mock_entity_repo.list_by_parent = AsyncMock(return_value=[existing_strategy_doc])
            mock_entry_repo.create = AsyncMock()
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await update_project_strategy(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["project"]["strategy"]["audience"] == ["跑步新手", "準備回歸訓練的人"]
        assert body["project"]["strategy"]["ctaStrategy"] == "引導免費試用"
        assert body["project"]["strategy"]["frequency"] == "每週 2 篇"
        assert body["project"]["strategy"]["documentId"] == existing_strategy_doc.id
        assert body["project"]["strategy"]["updatedAt"] != original_updated_at

    async def test_update_project_strategy_returns_409_on_conflict(self):
        from zenos.interface.marketing_dashboard_api import update_project_strategy

        strategy_doc = _strategy_doc_entity(
            parent_id="proj-1",
            updated_at=datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
        )
        request = _make_request(
            method="PUT",
            headers={"authorization": "Bearer token"},
            path_params={"projectId": "proj-1"},
            json_body={
                "audience": ["跑步新手"],
                "tone": "專業友善",
                "coreMessage": "先恢復穩定跑步頻率",
                "platforms": ["threads", "blog"],
                "frequency": "每週 2 篇",
                "contentMix": {"education": 70, "product": 30},
                "expectedUpdatedAt": "2026-04-12T08:59:59+00:00",
            },
        )
        project = _project_entity("proj-1", "prod-1")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=project)
            mock_entity_repo.list_by_parent = AsyncMock(return_value=[strategy_doc])
            mock_entity_repo.upsert = AsyncMock()
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await update_project_strategy(request)

        assert resp.status_code == 409
        mock_entity_repo.upsert.assert_not_called()

    async def test_get_project_styles_returns_grouped_styles(self):
        from zenos.interface.marketing_dashboard_api import get_project_styles

        request = _make_request(
            headers={"authorization": "Bearer token"},
            path_params={"projectId": "proj-1"},
        )
        project = _project_entity("proj-1", "prod-1")
        product_style = _style_entity("s1", "prod-1", "product")
        platform_style = _style_entity("s2", "prod-1", "platform", platform="threads")
        project_style = _style_entity("s3", "proj-1", "project", project_id="proj-1")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=project)
            mock_entity_repo.list_by_parent = AsyncMock(side_effect=[[product_style, platform_style], [project_style]])
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await get_project_styles(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert len(body["styles"]["product"]) == 1
        assert len(body["styles"]["platform"]) == 1
        assert len(body["styles"]["project"]) == 1

    async def test_update_project_content_plan_persists_schedule(self):
        from zenos.interface.marketing_dashboard_api import update_project_content_plan

        request = _make_request(
            method="PUT",
            headers={"authorization": "Bearer token"},
            path_params={"projectId": "proj-1"},
            json_body={
                "contentPlan": [
                    {
                        "weekLabel": "Week 1",
                        "isCurrent": True,
                        "days": [
                            {
                                "day": "Mon",
                                "platform": "Threads",
                                "topic": "主題 A",
                                "status": "suggested",
                            }
                        ],
                        "aiNote": "先從暖身切入",
                    }
                ]
            },
        )
        project = _project_entity("proj-1", "prod-1")
        strategy_doc = _strategy_doc_entity(parent_id="proj-1")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api._entry_repo"
        ) as mock_entry_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=project)
            mock_entity_repo.upsert = AsyncMock(side_effect=lambda entity: entity)
            mock_entity_repo.list_by_parent = AsyncMock(return_value=[strategy_doc])
            mock_entry_repo.create = AsyncMock()
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await update_project_content_plan(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["project"]["contentPlan"][0]["weekLabel"] == "Week 1"
        assert body["project"]["contentPlan"][0]["days"][0]["topic"] == "主題 A"


class TestReviewPost:
    async def test_updates_post_status_and_writes_transition_audit(self):
        from zenos.interface.marketing_dashboard_api import review_post

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer token"},
            path_params={"postId": "p1"},
            json_body={"action": "approve", "comment": "looks good", "reviewer": "CMO"},
        )
        post = _post_entity("p1", "proj-1", "draft_generated")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api._entry_repo"
        ) as mock_entry_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=post)
            mock_entity_repo.upsert = AsyncMock(side_effect=lambda entity: entity)
            mock_entry_repo.create = AsyncMock()
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await review_post(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["post"]["status"] == "draft_confirmed"
        transition = post.details["marketing"]["last_transition"]
        assert transition["from_status"] == "draft_generated"
        assert transition["to_status"] == "draft_confirmed"
        assert post.details["marketing"]["transition_history"][-1]["action"] == "approve"
        mock_entry_repo.create.assert_called_once()
        assert "from=draft_generated" in mock_entry_repo.create.call_args.args[0].context
        assert "to=draft_confirmed" in mock_entry_repo.create.call_args.args[0].context

    async def test_rejects_invalid_transition(self):
        from zenos.interface.marketing_dashboard_api import review_post

        request = _make_request(
            method="POST",
            headers={"authorization": "Bearer token"},
            path_params={"postId": "p1"},
            json_body={"action": "approve", "comment": "looks good", "reviewer": "CMO"},
        )
        post = _post_entity("p1", "proj-1", "topic_planned")

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._entity_repo"
        ) as mock_entity_repo, patch(
            "zenos.interface.marketing_dashboard_api._entry_repo"
        ) as mock_entry_repo, patch(
            "zenos.interface.marketing_dashboard_api.current_partner_id"
        ) as mock_ctx:
            mock_entity_repo.get_by_id = AsyncMock(return_value=post)
            mock_entity_repo.upsert = AsyncMock()
            mock_entry_repo.create = AsyncMock()
            mock_ctx.set = MagicMock(return_value="ctx-token")
            mock_ctx.reset = MagicMock()

            resp = await review_post(request)

        assert resp.status_code == 409
        mock_entity_repo.upsert.assert_not_called()
        mock_entry_repo.create.assert_not_called()


class TestPromptSsot:
    def _prompt_hub_entity(self) -> Entity:
        now = datetime(2026, 4, 13, tzinfo=timezone.utc).isoformat()
        return Entity(
            id="hub-1",
            name="行銷 Prompt SSOT",
            type="module",
            level=2,
            parent_id=None,
            status="active",
            summary="ssot",
            tags=Tags(what=["marketing"], why="", how="", who=[]),
            details={
                "marketing": {
                    "prompt_ssot": True,
                    "prompt_skills": {
                        "marketing-generate": {
                            "published_version": 1,
                            "published_content": "v1 content",
                            "draft_content": "v1 content",
                            "draft_updated_at": now,
                            "versions": [
                                {
                                    "version": 1,
                                    "content": "v1 content",
                                    "created_at": now,
                                    "created_by": "system",
                                    "note": "init",
                                }
                            ],
                        }
                    },
                }
            },
            confirmed_by_user=True,
            sources=[],
            owner="Alice",
            visibility="public",
            created_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 13, tzinfo=timezone.utc),
        )

    async def test_get_prompt_ssot_returns_prompts(self):
        from zenos.interface.marketing_dashboard_api import get_prompt_ssot

        request = _make_request(headers={"authorization": "Bearer token"})
        hub = self._prompt_hub_entity()

        with patch(
            "zenos.interface.marketing_dashboard_api._auth_and_scope",
            return_value=(_partner(), "effective-partner"),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_marketing_repos",
            new=AsyncMock(return_value=None),
        ), patch(
            "zenos.interface.marketing_dashboard_api._ensure_prompt_hub_entity",
            new=AsyncMock(return_value=hub),
        ):
            resp = await get_prompt_ssot(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["hubId"] == "hub-1"
        assert len(body["prompts"]) == 5
