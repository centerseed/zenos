"""Tests for task attachment functionality.

Covers: upload_attachment MCP tool (both modes), task create/update with
attachments, attachment proxy endpoint, and validation logic.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.models import Task


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Fix login",
        status="todo",
        priority="high",
        created_by="architect",
        description="Login broken on iOS",
        assignee="developer",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


# ─────────────────────────────────────────────────
# Attachment validation helpers
# ─────────────────────────────────────────────────


class TestValidateAttachments:
    def test_link_attachment_requires_url(self):
        from zenos.interface.tools import _validate_attachments
        result = _validate_attachments([{"type": "link"}], "partner-1")
        assert isinstance(result, dict) and result["error"] == "INVALID_INPUT"
        assert "url" in result["message"]

    def test_link_attachment_valid(self):
        from zenos.interface.tools import _validate_attachments
        result = _validate_attachments(
            [{"type": "link", "url": "https://example.com"}], "partner-1"
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "link"
        assert result[0]["url"] == "https://example.com"
        assert result[0]["uploaded_by"] == "partner-1"

    def test_image_attachment_requires_id(self):
        from zenos.interface.tools import _validate_attachments
        result = _validate_attachments([{"type": "image"}], "partner-1")
        assert isinstance(result, dict) and result["error"] == "INVALID_INPUT"
        assert "attachment_id" in result["message"]

    def test_file_attachment_with_id(self):
        from zenos.interface.tools import _validate_attachments
        result = _validate_attachments(
            [{"type": "file", "attachment_id": "abc123", "filename": "doc.pdf"}],
            "partner-1",
        )
        assert isinstance(result, list)
        assert result[0]["id"] == "abc123"
        assert result[0]["uploaded_by"] == "partner-1"

    def test_invalid_type_rejected(self):
        from zenos.interface.tools import _validate_attachments
        result = _validate_attachments([{"type": "video"}], "partner-1")
        assert isinstance(result, dict) and result["error"] == "INVALID_INPUT"
        assert "video" in result["message"]

    def test_server_sets_uploaded_by(self):
        """uploaded_by is always set from server partner context."""
        from zenos.interface.tools import _validate_attachments
        result = _validate_attachments(
            [{"type": "link", "url": "https://x.com", "uploaded_by": "hacker"}],
            "real-partner",
        )
        assert isinstance(result, list)
        assert result[0]["uploaded_by"] == "real-partner"

    def test_validate_attachments_merges_gcs_path_from_existing(self):
        """Caller passing only id+type gets gcs_path and content_type merged from existing."""
        from zenos.interface.tools import _validate_attachments

        existing = [
            {
                "id": "att-abc",
                "type": "image",
                "gcs_path": "tasks/t1/attachments/att-abc/photo.jpg",
                "content_type": "image/jpeg",
                "uploaded": True,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        caller_att = [{"type": "image", "id": "att-abc", "filename": "photo.jpg"}]
        result = _validate_attachments(caller_att, "partner-1", existing_attachments=existing)

        assert isinstance(result, list)
        item = result[0]
        assert item["id"] == "att-abc"
        assert item["gcs_path"] == "tasks/t1/attachments/att-abc/photo.jpg"
        assert item["content_type"] == "image/jpeg"
        assert item["uploaded"] is True
        assert item["created_at"] == "2026-01-01T00:00:00+00:00"

    def test_validate_attachments_normalizes_mime_type_to_content_type(self):
        """mime_type passed by caller is converted to content_type."""
        from zenos.interface.tools import _validate_attachments

        caller_att = [{"type": "file", "id": "att-xyz", "filename": "doc.pdf", "mime_type": "application/pdf"}]
        result = _validate_attachments(caller_att, "partner-1")

        assert isinstance(result, list)
        item = result[0]
        assert item["content_type"] == "application/pdf"
        assert "mime_type" not in item


# ─────────────────────────────────────────────────
# Upload attachment MCP tool
# ─────────────────────────────────────────────────


class TestUploadAttachment:
    async def test_upload_signed_url_mode(self):
        from zenos.interface.tools import upload_attachment, _current_partner

        task_obj = _make_task(attachments=[])
        token = _current_partner.set({"id": "partner-1", "defaultProject": "zenos"})

        try:
            with (
                patch("zenos.interface.tools._ensure_services"),
                patch("zenos.interface.tools.task_service") as mock_ts,
                patch("zenos.infrastructure.gcs_client.generate_signed_put_url", return_value="https://signed.url") as mock_sign,
                patch("zenos.infrastructure.gcs_client._get_client") as mock_client,
            ):
                mock_ts._tasks = AsyncMock()
                mock_ts._tasks.get_by_id = AsyncMock(return_value=task_obj)
                mock_ts._tasks.upsert = AsyncMock(return_value=task_obj)

                result = await upload_attachment(
                    task_id="task-1",
                    filename="photo.jpg",
                    content_type="image/jpeg",
                )

                assert "attachment_id" in result
                assert result["signed_put_url"] == "https://signed.url"
                assert result["proxy_url"].startswith("/attachments/")
                mock_sign.assert_called_once()
        finally:
            _current_partner.reset(token)

    async def test_upload_rejects_nonexistent_task(self):
        from zenos.interface.tools import upload_attachment, _current_partner

        token = _current_partner.set({"id": "partner-1", "defaultProject": "zenos"})
        try:
            with (
                patch("zenos.interface.tools._ensure_services"),
                patch("zenos.interface.tools.task_service") as mock_ts,
            ):
                mock_ts._tasks = AsyncMock()
                mock_ts._tasks.get_by_id = AsyncMock(return_value=None)

                result = await upload_attachment(
                    task_id="nonexistent",
                    filename="test.txt",
                    content_type="text/plain",
                )

                assert result["error"] == "NOT_FOUND"
        finally:
            _current_partner.reset(token)

    async def test_upload_requires_auth(self):
        from zenos.interface.tools import upload_attachment, _current_partner

        token = _current_partner.set(None)
        try:
            result = await upload_attachment(
                task_id="task-1",
                filename="test.txt",
                content_type="text/plain",
            )
            assert result["error"] == "UNAUTHORIZED"
        finally:
            _current_partner.reset(token)


# ─────────────────────────────────────────────────
# Task create/update with attachments
# ─────────────────────────────────────────────────


class TestTaskWithAttachments:
    async def test_create_task_with_link_attachments(self):
        from zenos.interface.tools import _task_handler, _current_partner
        from zenos.application.task_service import TaskResult

        t = _make_task(attachments=[])
        create_result = TaskResult(task=t, cascade_updates=[])
        token = _current_partner.set({"id": "partner-1", "defaultProject": "zenos"})

        try:
            with patch("zenos.interface.tools.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)
                mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

                result = await _task_handler(
                    action="create",
                    title="Task with links",
                    created_by="partner-1",
                    attachments=[{"type": "link", "url": "https://example.com"}],
                )

                assert "error" not in result
                call_data = mock_ts.create_task.call_args.args[0]
                assert len(call_data["attachments"]) == 1
                assert call_data["attachments"][0]["type"] == "link"
        finally:
            _current_partner.reset(token)

    async def test_create_task_with_invalid_attachment_type_fails(self):
        from zenos.interface.tools import _task_handler, _current_partner

        token = _current_partner.set({"id": "partner-1", "defaultProject": "zenos"})
        try:
            result = await _task_handler(
                action="create",
                title="Bad task",
                created_by="partner-1",
                attachments=[{"type": "video"}],
            )
            assert result["error"] == "INVALID_INPUT"
        finally:
            _current_partner.reset(token)

    async def test_update_task_replaces_attachments(self):
        from zenos.interface.tools import _task_handler, _current_partner
        from zenos.application.task_service import TaskResult

        old_task = _make_task(
            attachments=[
                {"id": "old-att", "gcs_path": "tasks/task-1/attachments/old-att/f.png", "type": "image"},
            ]
        )
        updated_task = _make_task(
            attachments=[{"id": "new-att", "type": "link", "url": "https://new.com"}]
        )
        update_result = TaskResult(task=updated_task, cascade_updates=[])
        token = _current_partner.set({"id": "partner-1", "defaultProject": "zenos"})

        try:
            with (
                patch("zenos.interface.tools.task_service") as mock_ts,
                patch("zenos.interface.tools._cleanup_removed_attachments") as mock_cleanup,
            ):
                mock_ts._tasks = AsyncMock()
                mock_ts._tasks.get_by_id = AsyncMock(return_value=old_task)
                mock_ts.update_task = AsyncMock(return_value=update_result)
                mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

                result = await _task_handler(
                    action="update",
                    id="task-1",
                    attachments=[{"type": "link", "url": "https://new.com"}],
                )

                assert "error" not in result
                mock_cleanup.assert_called_once()
        finally:
            _current_partner.reset(token)


# ─────────────────────────────────────────────────
# Cleanup removed attachments
# ─────────────────────────────────────────────────


class TestCleanupRemovedAttachments:
    def test_deletes_removed_gcs_attachments(self):
        from zenos.interface.tools import _cleanup_removed_attachments

        old = [
            {"id": "a1", "gcs_path": "tasks/t/attachments/a1/f.png"},
            {"id": "a2", "gcs_path": "tasks/t/attachments/a2/f.pdf"},
        ]
        new = [{"id": "a1", "gcs_path": "tasks/t/attachments/a1/f.png"}]

        with patch("zenos.infrastructure.gcs_client.delete_blob") as mock_del:
            _cleanup_removed_attachments(old, new)
            mock_del.assert_called_once()
            assert "a2" in mock_del.call_args.args[1]

    def test_skips_link_attachments_without_gcs_path(self):
        from zenos.interface.tools import _cleanup_removed_attachments

        old = [{"id": "link1", "type": "link", "url": "https://x.com"}]
        new = []

        with patch("zenos.infrastructure.gcs_client.delete_blob") as mock_del:
            _cleanup_removed_attachments(old, new)
            mock_del.assert_not_called()


# ─────────────────────────────────────────────────
# Serialize with proxy_url
# ─────────────────────────────────────────────────


class TestSerializeAttachments:
    def test_serialize_adds_proxy_url_for_gcs_attachments(self):
        from zenos.interface.tools import _serialize

        t = _make_task(
            attachments=[
                {"id": "att-1", "gcs_path": "tasks/t/attachments/att-1/f.png", "filename": "f.png"},
                {"id": "att-2", "type": "link", "url": "https://example.com"},
            ]
        )
        result = _serialize(t)
        assert result["attachments"][0]["proxy_url"] == "/attachments/att-1"
        assert "proxy_url" not in result["attachments"][1]

    def test_serialize_empty_attachments(self):
        from zenos.interface.tools import _serialize

        t = _make_task(attachments=[])
        result = _serialize(t)
        assert result["attachments"] == []


# ─────────────────────────────────────────────────
# Dashboard API _task_to_dict
# ─────────────────────────────────────────────────


class TestDashboardApiTaskToDict:
    def test_task_to_dict_includes_attachments_with_proxy_url(self):
        from zenos.interface.dashboard_api import _task_to_dict

        t = _make_task(
            attachments=[
                {"id": "att-1", "gcs_path": "tasks/t/attachments/att-1/f.png"},
                {"id": "att-2", "type": "link", "url": "https://x.com"},
            ]
        )
        result = _task_to_dict(t)
        assert "attachments" in result
        assert result["attachments"][0]["proxy_url"] == "/attachments/att-1"
        assert "proxy_url" not in result["attachments"][1]


# ─────────────────────────────────────────────────
# Dashboard API: upload_task_attachment (link type)
# ─────────────────────────────────────────────────


class TestUploadTaskAttachmentLink:
    """Tests for the link attachment branch of POST /api/data/tasks/{taskId}/attachments."""

    async def test_add_link_attachment_saves_to_task(self):
        """Adding a link attachment appends it to the task without GCS interaction."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from zenos.interface.dashboard_api import upload_task_attachment, _task_repo, _repos_ready
        import zenos.interface.dashboard_api as api_module

        task_obj = _make_task(attachments=[])
        mock_task_repo = AsyncMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task_obj)
        mock_task_repo.upsert = AsyncMock(return_value=task_obj)

        original_repos_ready = api_module._repos_ready
        original_task_repo = api_module._task_repo

        api_module._repos_ready = True
        api_module._task_repo = mock_task_repo

        try:
            with (
                patch("zenos.interface.dashboard_api._verify_firebase_token", new=AsyncMock(return_value={"email": "user@example.com"})),
                patch("zenos.interface.dashboard_api._get_partner_by_email_sql", new=AsyncMock(return_value={"id": "partner-1", "sharedPartnerId": None})),
            ):
                app = Starlette(routes=[Route("/api/data/tasks/{taskId}/attachments", upload_task_attachment, methods=["POST"])])
                client = TestClient(app, raise_server_exceptions=True)
                resp = client.post(
                    "/api/data/tasks/task-1/attachments",
                    json={"type": "link", "url": "https://example.com/doc"},
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "attachment_id" in data
                assert "signed_put_url" not in data

                # Verify the attachment was appended to the task
                upsert_call_task = mock_task_repo.upsert.call_args.args[0]
                link_atts = [a for a in upsert_call_task.attachments if a.get("type") == "link"]
                assert len(link_atts) == 1
                assert link_atts[0]["url"] == "https://example.com/doc"
        finally:
            api_module._repos_ready = original_repos_ready
            api_module._task_repo = original_task_repo

    async def test_add_link_attachment_missing_url_returns_400(self):
        """Link attachment without url field returns 400."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from zenos.interface.dashboard_api import upload_task_attachment
        import zenos.interface.dashboard_api as api_module

        original_repos_ready = api_module._repos_ready
        api_module._repos_ready = True

        try:
            with (
                patch("zenos.interface.dashboard_api._verify_firebase_token", new=AsyncMock(return_value={"email": "user@example.com"})),
                patch("zenos.interface.dashboard_api._get_partner_by_email_sql", new=AsyncMock(return_value={"id": "partner-1", "sharedPartnerId": None})),
            ):
                app = Starlette(routes=[Route("/api/data/tasks/{taskId}/attachments", upload_task_attachment, methods=["POST"])])
                client = TestClient(app, raise_server_exceptions=True)
                resp = client.post(
                    "/api/data/tasks/task-1/attachments",
                    json={"type": "link"},
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 400
                assert resp.json()["error"] == "INVALID_INPUT"
        finally:
            api_module._repos_ready = original_repos_ready


# ─────────────────────────────────────────────────
# Dashboard API: get_attachment GCS NotFound → 404
# ─────────────────────────────────────────────────


class TestGetAttachmentGcsNotFound:
    """Tests that get_attachment returns 404 when the GCS object is missing."""

    async def test_gcs_not_found_returns_404(self):
        """When GCS raises NotFound, the endpoint must return 404 not 500."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from zenos.interface.dashboard_api import get_attachment
        import zenos.interface.dashboard_api as api_module
        from google.cloud.exceptions import NotFound as GcsNotFound

        task_with_att = _make_task(
            attachments=[{"id": "att-gcs", "gcs_path": "tasks/task-1/attachments/att-gcs/f.png", "filename": "f.png", "content_type": "image/png"}]
        )
        mock_task_repo = AsyncMock()
        mock_task_repo.find_task_by_attachment_id = AsyncMock(return_value=task_with_att)

        original_repos_ready = api_module._repos_ready
        original_task_repo = api_module._task_repo

        api_module._repos_ready = True
        api_module._task_repo = mock_task_repo

        try:
            with (
                patch("zenos.interface.dashboard_api._verify_firebase_token", new=AsyncMock(return_value={"email": "user@example.com"})),
                patch("zenos.interface.dashboard_api._get_partner_by_email_sql", new=AsyncMock(return_value={"id": "partner-1", "sharedPartnerId": None})),
                patch("zenos.infrastructure.gcs_client.download_blob", side_effect=GcsNotFound("blob not found")),
            ):
                app = Starlette(routes=[Route("/attachments/{attachment_id}", get_attachment, methods=["GET"])])
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(
                    "/attachments/att-gcs",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 404
                assert resp.json()["error"] == "NOT_FOUND"
        finally:
            api_module._repos_ready = original_repos_ready
            api_module._task_repo = original_task_repo

    async def test_gcs_other_error_returns_500(self):
        """When GCS raises a non-NotFound exception, return 500."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from zenos.interface.dashboard_api import get_attachment
        import zenos.interface.dashboard_api as api_module

        task_with_att = _make_task(
            attachments=[{"id": "att-gcs2", "gcs_path": "tasks/task-1/attachments/att-gcs2/f.pdf", "filename": "f.pdf", "content_type": "application/pdf"}]
        )
        mock_task_repo = AsyncMock()
        mock_task_repo.find_task_by_attachment_id = AsyncMock(return_value=task_with_att)

        original_repos_ready = api_module._repos_ready
        original_task_repo = api_module._task_repo

        api_module._repos_ready = True
        api_module._task_repo = mock_task_repo

        try:
            with (
                patch("zenos.interface.dashboard_api._verify_firebase_token", new=AsyncMock(return_value={"email": "user@example.com"})),
                patch("zenos.interface.dashboard_api._get_partner_by_email_sql", new=AsyncMock(return_value={"id": "partner-1", "sharedPartnerId": None})),
                patch("zenos.infrastructure.gcs_client.download_blob", side_effect=ConnectionError("network failure")),
            ):
                app = Starlette(routes=[Route("/attachments/{attachment_id}", get_attachment, methods=["GET"])])
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(
                    "/attachments/att-gcs2",
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 500
                assert resp.json()["error"] == "INTERNAL_ERROR"
        finally:
            api_module._repos_ready = original_repos_ready
            api_module._task_repo = original_task_repo


# ─────────────────────────────────────────────────
# GCS client: generate_signed_put_url with compute credentials
# ─────────────────────────────────────────────────


class TestGenerateSignedPutUrlComputeCredentials:
    """Tests for generate_signed_put_url behaviour under Cloud Run compute credentials."""

    def test_uses_iam_signing_when_sa_email_env_set(self):
        """When GOOGLE_SERVICE_ACCOUNT_EMAIL is set, an IAM Signer is constructed
        and wrapped in service_account.Credentials, then passed to generate_signed_url
        as the 'credentials' kwarg (not service_account_email/access_token)."""
        from unittest.mock import MagicMock, patch, call
        from zenos.infrastructure.gcs_client import generate_signed_put_url

        mock_creds = MagicMock()
        mock_signer = MagicMock()
        mock_signing_credentials = MagicMock()

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_auth_request = MagicMock()

        with (
            patch("zenos.infrastructure.gcs_client._get_client", return_value=mock_client),
            patch.dict("os.environ", {"GOOGLE_SERVICE_ACCOUNT_EMAIL": "sa@project.iam.gserviceaccount.com"}),
            patch("google.auth.default", return_value=(mock_creds, "project")),
            patch("google.auth.transport.requests.Request", return_value=mock_auth_request),
            patch("google.auth.iam.Signer", return_value=mock_signer) as mock_signer_cls,
            patch("google.oauth2.service_account.Credentials", return_value=mock_signing_credentials) as mock_sa_creds_cls,
        ):
            url = generate_signed_put_url("my-bucket", "tasks/t1/att/f.png", "image/png")

        assert url == "https://storage.googleapis.com/signed"
        # credentials.refresh must be called once
        mock_creds.refresh.assert_called_once_with(mock_auth_request)
        # IAM Signer must be constructed with the right SA email
        mock_signer_cls.assert_called_once_with(
            request=mock_auth_request,
            credentials=mock_creds,
            service_account_email="sa@project.iam.gserviceaccount.com",
        )
        # service_account.Credentials must be constructed with the signer
        mock_sa_creds_cls.assert_called_once_with(
            signer=mock_signer,
            service_account_email="sa@project.iam.gserviceaccount.com",
            token_uri="https://oauth2.googleapis.com/token",
        )
        # generate_signed_url must receive signing_credentials, not token/sa_email
        signed_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert signed_kwargs["credentials"] is mock_signing_credentials
        assert "service_account_email" not in signed_kwargs
        assert "access_token" not in signed_kwargs

    def test_skips_iam_signing_when_no_sa_email(self):
        """When no SA email is resolvable, generate_signed_url is called without
        service_account_email / access_token (local dev path)."""
        from unittest.mock import MagicMock, patch
        from zenos.infrastructure.gcs_client import generate_signed_put_url

        mock_creds = MagicMock(spec=[])  # no service_account_email attribute
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/local"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with (
            patch("zenos.infrastructure.gcs_client._get_client", return_value=mock_client),
            patch.dict("os.environ", {}, clear=True),
            patch("google.auth.default", return_value=(mock_creds, "project")),
        ):
            url = generate_signed_put_url("my-bucket", "tasks/t1/att/f.png", "image/png")

        assert url == "https://storage.googleapis.com/local"
        signed_kwargs = mock_blob.generate_signed_url.call_args.kwargs
        assert "service_account_email" not in signed_kwargs
        assert "access_token" not in signed_kwargs
        assert "credentials" not in signed_kwargs

    def test_gcs_error_propagates_to_upload_endpoint(self):
        """When generate_signed_put_url raises, upload_task_attachment returns 500."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.routing import Route
        from zenos.interface.dashboard_api import upload_task_attachment
        import zenos.interface.dashboard_api as api_module

        task_obj = _make_task(attachments=[])
        mock_task_repo = AsyncMock()
        mock_task_repo.get_by_id = AsyncMock(return_value=task_obj)

        original_repos_ready = api_module._repos_ready
        original_task_repo = api_module._task_repo

        api_module._repos_ready = True
        api_module._task_repo = mock_task_repo

        try:
            with (
                patch("zenos.interface.dashboard_api._verify_firebase_token", new=AsyncMock(return_value={"email": "u@x.com"})),
                patch("zenos.interface.dashboard_api._get_partner_by_email_sql", new=AsyncMock(return_value={"id": "p1", "sharedPartnerId": None})),
                patch(
                    "zenos.infrastructure.gcs_client.generate_signed_put_url",
                    side_effect=AttributeError("you need a private key to sign credentials"),
                ),
            ):
                app = Starlette(routes=[Route("/api/data/tasks/{taskId}/attachments", upload_task_attachment, methods=["POST"])])
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.post(
                    "/api/data/tasks/task-1/attachments",
                    json={"type": "file", "filename": "photo.jpg", "content_type": "image/jpeg"},
                    headers={"Authorization": "Bearer test-token"},
                )
                assert resp.status_code == 500
                assert resp.json()["error"] == "GCS_ERROR"
        finally:
            api_module._repos_ready = original_repos_ready
            api_module._task_repo = original_task_repo
