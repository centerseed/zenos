"""Interface tests for /api/ext ingestion facade routes."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from zenos.infrastructure.identity.jwt_service import JwtService
from zenos.interface.ext_ingestion_api import (
    app as ext_ingestion_app,
    _reset_inmemory_state,
    _set_commit_adapters,
    _reset_commit_adapters,
    _clear_service_cache,
)
from zenos.interface.mcp import ApiKeyMiddleware


TEST_SECRET = "jwt-test-secret"  # pragma: allowlist secret
WORKSPACE_HOME = "principal-1"
WORKSPACE_SHARED = "shared-99"

ACTIVE_PARTNER = {
    "id": WORKSPACE_HOME,
    "email": "jwt@test.com",
    "displayName": "JWT Partner",
    "status": "active",
    "isAdmin": False,
    "sharedPartnerId": WORKSPACE_SHARED,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["l1-a"],
    "workspaceRole": "guest",
    "accessMode": "scoped",
}


def _build_token(*, scopes: list[str], workspace_ids: list[str]) -> str:
    service = JwtService(secret=TEST_SECRET)
    return service.sign_delegated_credential(
        principal_id=WORKSPACE_HOME,
        app_id="trusted-app-1",
        workspace_ids=workspace_ids,
        scopes=scopes,
        ttl=3600,
    )


@contextmanager
def _jwt_client():
    class _Repo:
        def __init__(self, _pool):
            pass

        async def get_by_id(self, partner_id: str):
            if partner_id != WORKSPACE_HOME:
                return None
            return dict(ACTIVE_PARTNER)

    inner = Starlette(routes=[Mount("/api/ext", app=ApiKeyMiddleware(ext_ingestion_app))])
    with (
        patch("zenos.interface.mcp._auth._get_jwt_service", return_value=JwtService(secret=TEST_SECRET)),
        patch("zenos.infrastructure.sql_common.get_pool", new=AsyncMock(return_value=object())),
        patch("zenos.infrastructure.identity.SqlPartnerRepository", _Repo),
    ):
        with TestClient(inner, raise_server_exceptions=True) as client:
            yield client


def _ingest_payload(workspace_id: str = WORKSPACE_HOME) -> dict:
    return {
        "workspace_id": workspace_id,
        "product_id": "prod-1",
        "external_user_id": "u-1",
        "external_signal_id": "signal-001",
        "event_type": "task_input",
        "raw_ref": "app://zentropy/signals/signal-001",
        "summary": "Need to draft onboarding checklist",
        "intent": "todo",
        "confidence": 0.82,
        "occurred_at": "2026-04-11T01:23:45Z",
    }


class TestExtIngestionApi:
    def setup_method(self):
        _reset_inmemory_state()
        _reset_commit_adapters()

    def teardown_method(self):
        _clear_service_cache()

    def test_ingest_requires_write_scope(self):
        token = _build_token(scopes=["read"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=_ingest_payload(),
            )
        assert resp.status_code == 403
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "FORBIDDEN"

    def test_review_queue_requires_read_scope(self):
        token = _build_token(scopes=["write"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        with _jwt_client() as client:
            resp = client.get(
                "/api/ext/review-queue",
                headers={"Authorization": f"Bearer {token}"},
                params={"workspace_id": WORKSPACE_HOME, "product_id": "prod-1"},
            )
        assert resp.status_code == 403
        assert resp.json()["data"]["error"] == "FORBIDDEN"

    def test_ingest_workspace_must_be_in_token_workspace_ids(self):
        token = _build_token(scopes=["write"], workspace_ids=[WORKSPACE_HOME])
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=_ingest_payload(workspace_id=WORKSPACE_SHARED),
            )
        assert resp.status_code == 403
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "FORBIDDEN"

    def test_ingest_rejects_non_object_json_body(self):
        token = _build_token(scopes=["write"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=[],
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "INVALID_REQUEST"
        assert "JSON object" in " ".join(body["warnings"])

    def test_ingest_rejects_empty_external_signal_id(self):
        token = _build_token(scopes=["write"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        payload = _ingest_payload()
        payload["external_signal_id"] = None
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "INVALID_REQUEST"
        assert "external_signal_id must be a non-empty string" in " ".join(body["warnings"])

    def test_ingest_is_idempotent_by_external_signal_id_per_workspace(self):
        token = _build_token(scopes=["write"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        with _jwt_client() as client:
            first = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=_ingest_payload(),
            )
            second = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=_ingest_payload(),
            )

        assert first.status_code == 200
        assert second.status_code == 200
        first_body = first.json()
        second_body = second.json()
        assert first_body["data"]["idempotent_replay"] is False
        assert second_body["data"]["idempotent_replay"] is True
        assert first_body["data"]["signal_id"] == second_body["data"]["signal_id"]

    def test_commit_mixed_payload_requires_task_and_write_scopes(self):
        token = _build_token(scopes=["task"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        payload = {
            "workspace_id": WORKSPACE_HOME,
            "product_id": "prod-1",
            "batch_id": "batch-1",
            "task_candidates": [{"title": "Do thing"}],
            "entry_candidates": [{"entity_id": "ent-1", "type": "insight", "content": "x"}],
        }
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        assert resp.status_code == 403
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "FORBIDDEN"

    def test_commit_forwards_product_id_to_task_adapter(self):
        token = _build_token(
            scopes=["read", "write", "task"],
            workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED],
        )
        created_tasks: list[dict] = []

        async def _fake_task_adapter(_workspace_id: str, payload: dict) -> dict:
            created_tasks.append(payload)
            return {"status": "ok", "data": {"id": "task-created-1", "product_id": payload.get("product_id")}}

        async def _fake_entry_adapter(_workspace_id: str, payload: dict) -> dict:
            return {"status": "ok", "data": {"id": "entry-created-1", **payload}}

        _set_commit_adapters(_fake_task_adapter, _fake_entry_adapter)

        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": WORKSPACE_HOME,
                    "product_id": "prod-1",
                    "batch_id": "batch-product-forward",
                    "task_candidates": [{"title": "Create from ingestion"}],
                    "entry_candidates": [],
                },
            )

        assert resp.status_code == 200
        assert created_tasks
        assert created_tasks[0]["product_id"] == "prod-1"

    def test_raw_to_distill_to_commit_to_review_queue(self):
        token = _build_token(
            scopes=["read", "write", "task"],
            workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED],
        )

        created_tasks: list[dict] = []
        created_entries: list[dict] = []

        async def _fake_task_adapter(_workspace_id: str, payload: dict) -> dict:
            created_tasks.append(payload)
            return {"status": "ok", "data": {"id": "task-created-1", "title": payload.get("title")}}

        async def _fake_entry_adapter(_workspace_id: str, payload: dict) -> dict:
            created_entries.append(payload)
            return {"status": "ok", "data": {"id": "entry-created-1", "entity_id": payload.get("entity_id")}}

        _set_commit_adapters(_fake_task_adapter, _fake_entry_adapter)

        with _jwt_client() as client:
            ingest_resp = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    **_ingest_payload(),
                    "event_type": "task_input",
                    "intent": "todo",
                    "external_signal_id": "signal-raw-1",
                },
            )
            assert ingest_resp.status_code == 200

            distill_resp = client.post(
                "/api/ext/signals/distill",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": WORKSPACE_HOME,
                    "product_id": "prod-1",
                    "window": {
                        "from": "2026-04-10T00:00:00Z",
                        "to": "2026-04-12T00:00:00Z",
                    },
                    "max_items": 10,
                },
            )
            assert distill_resp.status_code == 200
            distill_body = distill_resp.json()
            batch_id = distill_body["data"]["batch_id"]
            assert batch_id
            task_candidates = distill_body["data"]["task_candidates"]
            assert len(task_candidates) == 1

            commit_resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": WORKSPACE_HOME,
                    "product_id": "prod-1",
                    "batch_id": batch_id,
                    "task_candidates": [
                        {
                            "title": "Commit task candidate",
                            "description": "from distill",
                            "forbidden_field": "ignored",
                        }
                    ],
                    "entry_candidates": [
                        {
                            "entity_id": "ent-1",
                            "type": "insight",
                            "content": "entry candidate",
                        }
                    ],
                    "l2_update_candidates": [{"entity_id": "l2-1", "summary_patch": "..." }],
                },
            )
            assert commit_resp.status_code == 200
            commit_body = commit_resp.json()
            assert len(commit_body["data"]["committed"]) == 2
            assert len(commit_body["data"]["queued_for_review"]) == 1
            assert any("ignored unknown fields" in w for w in commit_body["warnings"])
            assert created_tasks and created_entries

            queue_resp = client.get(
                "/api/ext/review-queue",
                headers={"Authorization": f"Bearer {token}"},
                params={"workspace_id": WORKSPACE_HOME, "product_id": "prod-1"},
            )
            assert queue_resp.status_code == 200
            queue_body = queue_resp.json()
            assert queue_body["data"]["total"] == 1

    def test_commit_rejects_forbidden_mutation_target(self):
        token = _build_token(
            scopes=["write", "task"],
            workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED],
        )

        async def _fake_task_adapter(_workspace_id: str, payload: dict) -> dict:
            return {"status": "ok", "data": {"id": "task-created-1", "title": payload.get("title")}}

        async def _fake_entry_adapter(_workspace_id: str, payload: dict) -> dict:
            return {"status": "ok", "data": {"id": "entry-created-1", "entity_id": payload.get("entity_id")}}

        _set_commit_adapters(_fake_task_adapter, _fake_entry_adapter)

        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": WORKSPACE_HOME,
                    "product_id": "prod-1",
                    "batch_id": "batch-1",
                    "task_candidates": [
                        {"title": "evil", "collection": "entities"},
                    ],
                    "entry_candidates": [],
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["committed"] == []
        assert len(body["data"]["rejected"]) == 1
        assert body["data"]["rejected"][0]["reason"] == "forbidden mutation target"

    def test_commit_rejects_non_object_json_body(self):
        token = _build_token(
            scopes=["write", "task"],
            workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED],
        )
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json=[],
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "INVALID_REQUEST"
        assert "JSON object" in " ".join(body["warnings"])

    def test_commit_atomic_rolls_back_on_failure(self):
        token = _build_token(
            scopes=["write", "task"],
            workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED],
        )

        with (
            _jwt_client() as client,
            patch(
                "zenos.interface.ext_ingestion_api._commit_atomic",
                new=AsyncMock(side_effect=ValueError("task_candidate[0] rejected: invalid linked entity")),
            ),
        ):
            resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": WORKSPACE_HOME,
                    "product_id": "prod-1",
                    "batch_id": "batch-1",
                    "atomic": True,
                    "task_candidates": [{"title": "Atomic task"}],
                    "entry_candidates": [{"entity_id": "ent-1", "type": "insight", "content": "atomic entry"}],
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["committed"] == []
        assert body["data"]["queued_for_review"] == []
        assert len(body["data"]["rejected"]) == 1
        assert body["data"]["rejected"][0]["type"] == "atomic"
        assert "transaction rolled back" in " ".join(body["warnings"])

    def test_commit_atomic_rejects_oversized_entry_before_commit(self):
        token = _build_token(
            scopes=["write", "task"],
            workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED],
        )

        with (
            _jwt_client() as client,
            patch("zenos.interface.ext_ingestion_api._commit_atomic", new=AsyncMock()) as mock_commit_atomic,
        ):
            resp = client.post(
                "/api/ext/candidates/commit",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "workspace_id": WORKSPACE_HOME,
                    "product_id": "prod-1",
                    "batch_id": "batch-1",
                    "atomic": True,
                    "task_candidates": [],
                    "entry_candidates": [
                        {"entity_id": "ent-1", "type": "insight", "content": "x" * 201},
                    ],
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["committed"] == []
        assert body["data"]["queued_for_review"] == []
        assert len(body["data"]["rejected"]) == 1
        assert body["data"]["rejected"][0]["type"] == "entry"
        assert "content must be 1-200 chars" in body["data"]["rejected"][0]["reason"]
        assert "atomic=true: commit skipped because validation failed" in body["warnings"]
        mock_commit_atomic.assert_not_called()

    def test_ingest_returns_503_when_backend_unavailable(self):
        token = _build_token(scopes=["write"], workspace_ids=[WORKSPACE_HOME, WORKSPACE_SHARED])
        _clear_service_cache()
        with _jwt_client() as client:
            resp = client.post(
                "/api/ext/signals/ingest",
                headers={"Authorization": f"Bearer {token}"},
                json=_ingest_payload(),
            )

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "BACKEND_UNAVAILABLE"
