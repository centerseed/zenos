"""GCS helpers for task attachment storage.

Provides upload, download, delete, and signed-URL generation for the
attachments bucket. Uses Application Default Credentials (auto-discovered
in Cloud Run).
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from google.cloud import storage  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_BUCKET_NAME = os.environ.get("GCS_ATTACHMENTS_BUCKET", "zenos-naruvia-attachments")

# Module-level lazy singleton
_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = storage.Client()
    return _client


def upload_blob(
    bucket_name: str,
    gcs_path: str,
    data: bytes,
    content_type: str,
) -> None:
    """Upload bytes to a GCS blob."""
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(data, content_type=content_type)
    logger.info("Uploaded %d bytes to gs://%s/%s", len(data), bucket_name, gcs_path)


def generate_signed_put_url(
    bucket_name: str,
    gcs_path: str,
    content_type: str,
    expiry_minutes: int = 15,
) -> str:
    """Generate a signed PUT URL for direct client upload.

    In Cloud Run (no key file), uses IAM signBlob via the compute SA.
    Requires the SA to have the iam.serviceAccountTokenCreator role.
    Locally, falls back to Application Default Credentials.
    """
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)

    kwargs: dict = {
        "version": "v4",
        "expiration": timedelta(minutes=expiry_minutes),
        "method": "PUT",
        "content_type": content_type,
    }

    # Resolve the service account email: env var takes precedence,
    # then we fall back to the credential's own service_account_email.
    sa_email = os.environ.get("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    if not sa_email:
        try:
            import google.auth  # type: ignore[import-untyped]
            creds, _ = google.auth.default()
            sa_email = getattr(creds, "service_account_email", None)
        except Exception:
            pass

    if sa_email and not sa_email.startswith("default"):
        # Cloud Run path: compute credentials have no private key.
        # Use google.auth.iam.Signer to construct signing-capable credentials
        # that pass google-cloud-storage>=2.14's ensure_signed_credentials check.
        import google.auth  # type: ignore[import-untyped]
        import google.auth.iam  # type: ignore[import-untyped]
        import google.auth.transport.requests  # type: ignore[import-untyped]
        from google.oauth2 import service_account  # type: ignore[import-untyped]

        credentials, _ = google.auth.default()
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)

        signer = google.auth.iam.Signer(
            request=auth_request,
            credentials=credentials,
            service_account_email=sa_email,
        )
        signing_credentials = service_account.Credentials(
            signer=signer,
            service_account_email=sa_email,
            token_uri="https://oauth2.googleapis.com/token",
        )
        kwargs["credentials"] = signing_credentials

    url: str = blob.generate_signed_url(**kwargs)
    return url


def download_blob(bucket_name: str, gcs_path: str) -> tuple[bytes, str]:
    """Download a blob and return (data, content_type)."""
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    blob.reload()  # fetch metadata
    data = blob.download_as_bytes()
    return data, blob.content_type or "application/octet-stream"


def delete_blob(bucket_name: str, gcs_path: str) -> None:
    """Delete a blob. Best-effort — logs errors but does not raise."""
    try:
        client = _get_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)
        blob.delete()
        logger.info("Deleted gs://%s/%s", bucket_name, gcs_path)
    except Exception:
        logger.warning("Failed to delete gs://%s/%s", bucket_name, gcs_path, exc_info=True)


def get_default_bucket() -> str:
    """Return the configured attachments bucket name."""
    return _BUCKET_NAME
