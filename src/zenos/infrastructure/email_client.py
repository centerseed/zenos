"""SMTP-based email service for ZenOS notifications.

All configuration is read from environment variables. If not configured,
all send methods return False silently without raising exceptions.

Required env vars:
  SMTP_HOST       — SMTP server hostname (default: smtp.gmail.com)
  SMTP_PORT       — SMTP port (default: 587)
  SMTP_USER       — SMTP login username (required to enable email)
  SMTP_PASSWORD   — SMTP login password (required to enable email)
  FROM_EMAIL      — Sender address (default: SMTP_USER)
  DASHBOARD_URL   — Base URL for dashboard links
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP-based email service for ZenOS notifications.

    All config from env vars. If SMTP_USER or SMTP_PASSWORD is not set,
    all methods return False silently.
    """

    def __init__(self) -> None:
        self._host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self._port = int(os.environ.get("SMTP_PORT", "587"))
        self._user = os.environ.get("SMTP_USER", "")
        self._password = os.environ.get("SMTP_PASSWORD", "")
        self._from_email = os.environ.get("FROM_EMAIL", "") or self._user
        self._dashboard_url = os.environ.get("DASHBOARD_URL", "https://zenos-naruvia.web.app")

    @property
    def _is_configured(self) -> bool:
        return bool(self._user and self._password)

    def _send_sync(self, msg: MIMEMultipart) -> None:
        """Send email synchronously using STARTTLS. Called in executor."""
        with smtplib.SMTP(self._host, self._port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(self._user, self._password)
            smtp.send_message(msg)

    async def _send(self, msg: MIMEMultipart) -> bool:
        """Send message asynchronously in a thread executor."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, msg)
        return True

    def _build_message(self, to_email: str, subject: str, html_body: str, text_body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_email
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    async def send_invite_email(
        self,
        to_email: str,
        inviter_name: str,
        sign_in_link: str,
        expires_in_days: int = 7,
    ) -> bool:
        """Send an invitation email to a new partner.

        Returns True on success, False if not configured or on error.
        """
        if not self._is_configured:
            logger.info("Email not configured, skipping invite email to %s", to_email)
            return False

        subject = f"「{inviter_name} 邀請您加入協作空間」"

        text_body = (
            f"您好，\n\n"
            f"{inviter_name} 邀請您加入 ZenOS 協作空間。\n\n"
            f"請點擊以下連結完成登入：\n{sign_in_link}\n\n"
            f"此邀請連結將在 {expires_in_days} 天後失效。\n\n"
            f"如有任何問題，請聯繫邀請人 {inviter_name}。\n\n"
            f"ZenOS 團隊"
        )

        html_body = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1a1a1a;">您收到了一份協作邀請</h2>
  <p><strong>{inviter_name}</strong> 邀請您加入 ZenOS 協作空間。</p>
  <p style="margin: 32px 0;">
    <a href="{sign_in_link}"
       style="background: #2563eb; color: #fff; padding: 12px 24px;
              text-decoration: none; border-radius: 6px; font-weight: bold;">
      立即加入
    </a>
  </p>
  <p style="color: #666; font-size: 14px;">
    此邀請連結將在 <strong>{expires_in_days} 天</strong>後失效。<br>
    如有任何問題，請聯繫邀請人 {inviter_name}。
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
  <p style="color: #999; font-size: 12px;">ZenOS 協作平台</p>
</body>
</html>"""

        msg = self._build_message(to_email, subject, html_body, text_body)
        try:
            return await self._send(msg)
        except Exception:
            logger.warning("Failed to send invite email to %s", to_email, exc_info=True)
            return False

    async def send_comment_notification(
        self,
        to_email: str,
        commenter_name: str,
        task_title: str,
        content: str,
    ) -> bool:
        """Send a comment notification email to the task owner.

        Returns True on success, False if not configured or on error.
        """
        if not self._is_configured:
            logger.info("Email not configured, skipping comment notification to %s", to_email)
            return False

        subject = f"「{task_title} 有新留言」"
        dashboard_link = self._dashboard_url

        text_body = (
            f"您好，\n\n"
            f"{commenter_name} 在任務「{task_title}」中留言：\n\n"
            f"{content}\n\n"
            f"前往 Dashboard 查看：{dashboard_link}\n\n"
            f"ZenOS 團隊"
        )

        html_body = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1a1a1a;">任務有新留言</h2>
  <p><strong>{commenter_name}</strong> 在任務「<strong>{task_title}</strong>」中留言：</p>
  <blockquote style="border-left: 4px solid #e5e7eb; margin: 16px 0; padding: 12px 16px;
                     background: #f9fafb; color: #374151;">
    {content}
  </blockquote>
  <p style="margin: 24px 0;">
    <a href="{dashboard_link}"
       style="background: #2563eb; color: #fff; padding: 10px 20px;
              text-decoration: none; border-radius: 6px; font-weight: bold;">
      前往 Dashboard
    </a>
  </p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
  <p style="color: #999; font-size: 12px;">ZenOS 協作平台</p>
</body>
</html>"""

        msg = self._build_message(to_email, subject, html_body, text_body)
        try:
            return await self._send(msg)
        except Exception:
            logger.warning("Failed to send comment notification to %s", to_email, exc_info=True)
            return False
