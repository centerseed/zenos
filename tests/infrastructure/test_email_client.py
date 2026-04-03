"""Tests for EmailService — covers sent/skipped/failed scenarios."""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from zenos.infrastructure.email_client import EmailService


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _env_with_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env vars to simulate a configured SMTP environment."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("DASHBOARD_URL", "https://example.com")


def _env_without_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove SMTP credentials to simulate unconfigured environment."""
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 1: SMTP not configured — silent False
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_invite_email_returns_false_when_smtp_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_invite_email returns False and does not raise when SMTP_USER/PASSWORD unset."""
    _env_without_smtp(monkeypatch)
    svc = EmailService()

    result = await svc.send_invite_email(
        to_email="user@example.com",
        inviter_name="Alice",
        sign_in_link="https://example.com/signin",
    )

    assert result is False


@pytest.mark.asyncio
async def test_send_comment_notification_returns_false_when_smtp_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_comment_notification returns False and does not raise when SMTP_USER/PASSWORD unset."""
    _env_without_smtp(monkeypatch)
    svc = EmailService()

    result = await svc.send_comment_notification(
        to_email="owner@example.com",
        commenter_name="Bob",
        task_title="Fix the bug",
        content="I looked at this.",
    )

    assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 2: SMTP configured, mock SMTP class — verify correct addressing
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_invite_email_uses_correct_to_and_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_invite_email sends to the right address with the expected subject."""
    _env_with_smtp(monkeypatch)
    svc = EmailService()

    sent_messages: list = []

    mock_smtp_instance = MagicMock()

    def capture_send_message(msg):
        sent_messages.append(msg)

    mock_smtp_instance.__enter__ = lambda s: mock_smtp_instance
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.send_message.side_effect = capture_send_message

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        result = await svc.send_invite_email(
            to_email="invited@example.com",
            inviter_name="Alice",
            sign_in_link="https://example.com/signin?token=abc",
        )

    assert result is True
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["To"] == "invited@example.com"
    assert "Alice" in msg["Subject"]
    assert "邀請" in msg["Subject"]


@pytest.mark.asyncio
async def test_send_comment_notification_uses_correct_to_and_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_comment_notification sends to the right address with the expected subject."""
    _env_with_smtp(monkeypatch)
    svc = EmailService()

    sent_messages: list = []

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__ = lambda s: mock_smtp_instance
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.send_message.side_effect = lambda msg: sent_messages.append(msg)

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        result = await svc.send_comment_notification(
            to_email="owner@example.com",
            commenter_name="Bob",
            task_title="Fix the authentication bug",
            content="I found the root cause.",
        )

    assert result is True
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["To"] == "owner@example.com"
    assert "Fix the authentication bug" in msg["Subject"]
    assert "新留言" in msg["Subject"]


# ──────────────────────────────────────────────────────────────────────────────
# Scenario 3: SMTP configured, send_message raises — returns False, no exception
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_invite_email_returns_false_on_smtp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_invite_email returns False when SMTP raises, and does not re-raise."""
    _env_with_smtp(monkeypatch)
    svc = EmailService()

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__ = lambda s: mock_smtp_instance
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.send_message.side_effect = smtplib.SMTPException("Connection refused")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        result = await svc.send_invite_email(
            to_email="user@example.com",
            inviter_name="Alice",
            sign_in_link="https://example.com/signin",
        )

    assert result is False


@pytest.mark.asyncio
async def test_send_comment_notification_returns_false_on_smtp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_comment_notification returns False when SMTP raises, and does not re-raise."""
    _env_with_smtp(monkeypatch)
    svc = EmailService()

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__ = lambda s: mock_smtp_instance
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.send_message.side_effect = smtplib.SMTPException("Auth failed")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        result = await svc.send_comment_notification(
            to_email="owner@example.com",
            commenter_name="Bob",
            task_title="A task",
            content="A comment",
        )

    assert result is False
