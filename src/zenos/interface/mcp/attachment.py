"""MCP tool: upload_attachment — upload files to tasks via signed URL."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from zenos.interface.mcp._auth import _current_partner
from zenos.interface.mcp._audit import _audit_log

logger = logging.getLogger(__name__)


async def upload_attachment(
    task_id: str,
    filename: str,
    content_type: str,
    description: str | None = None,
) -> dict:
    """上傳附件到任務（signed URL 模式）。

    流程：
    1. 呼叫此工具 → 取得 signed_put_url（15 分鐘有效）
    2. 用 Bash 執行 curl 上傳檔案到 signed URL：
       curl -X PUT -H "Content-Type: <content_type>" --data-binary @/path/to/file "<signed_put_url>"
    3. 上傳完成後，附件自動關聯到任務，可在 Dashboard 查看

    回傳 attachment_id、proxy_url、signed_put_url。

    Args:
        task_id: 目標任務 ID
        filename: 原始檔名
        content_type: MIME type（如 "image/png", "application/pdf"）
        description: 附件描述（可選）
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    try:
        partner = _current_partner.get()
        if not partner or not partner.get("id"):
            return {"error": "UNAUTHORIZED", "message": "Authentication required"}

        await _ensure_services()

        # Validate task exists and belongs to current partner
        task_obj = await _mcp.task_service._tasks.get_by_id(task_id)
        if task_obj is None:
            return {"error": "NOT_FOUND", "message": f"Task '{task_id}' not found"}

        from zenos.infrastructure.gcs_client import (
            get_default_bucket,
            generate_signed_put_url,
        )

        attachment_id = uuid.uuid4().hex
        gcs_path = f"tasks/{task_id}/attachments/{attachment_id}/{filename}"
        bucket_name = get_default_bucket()

        signed_put_url = generate_signed_put_url(bucket_name, gcs_path, content_type)

        attachment = {
            "id": attachment_id,
            "filename": filename,
            "content_type": content_type,
            "gcs_path": gcs_path,
            "uploaded_by": partner["id"],
            "uploaded": False,
            "description": description or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Append to task's attachments
        task_obj.attachments.append(attachment)
        await _mcp.task_service._tasks.upsert(task_obj)

        result = {
            "attachment_id": attachment_id,
            "proxy_url": f"/attachments/{attachment_id}",
            "signed_put_url": signed_put_url,
        }

        _audit_log(
            event_type="attachment.upload",
            target={"task_id": task_id, "attachment_id": attachment_id},
            changes={"filename": filename, "content_type": content_type, "mode": "signed_url"},
        )
        return result

    except ValueError as e:
        return {"error": "INVALID_INPUT", "message": str(e)}
    except Exception as e:
        logger.exception("upload_attachment failed")
        return {"error": "INTERNAL_ERROR", "message": str(e)}
