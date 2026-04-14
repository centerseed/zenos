"""Deterministic marketing workflow runtime helpers.

These helpers do not call LLMs directly. They encode the workflow contracts
that the Claude skill / runner path is expected to respect:
plan -> intel -> generate -> adapt -> publish.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Mapping


def compose_style_layers(
    *,
    product_style: str | None = None,
    platform_style: str | None = None,
    project_style: str | None = None,
) -> str:
    sections: list[str] = []
    if product_style and product_style.strip():
        sections.append("# Product Style\n" + product_style.strip())
    if platform_style and platform_style.strip():
        sections.append("# Platform Style\n" + platform_style.strip())
    if project_style and project_style.strip():
        sections.append("# Project Style\n" + project_style.strip())
    return "\n\n".join(sections).strip()


def plan_schedule(
    *,
    strategy: Mapping[str, Any],
    start_date: date | None = None,
    existing_days: list[dict[str, Any]] | None = None,
    horizon_days: int = 14,
) -> list[dict[str, Any]]:
    start = start_date or date.today()
    platforms = [str(item).strip() for item in strategy.get("platforms", []) if str(item).strip()] or ["Threads"]
    audience = ", ".join(str(item).strip() for item in strategy.get("audience", []) if str(item).strip()) or "核心受眾"
    core_message = str(strategy.get("core_message") or strategy.get("coreMessage") or "品牌核心訊息").strip()
    preserved: dict[tuple[str, str], dict[str, Any]] = {}
    for item in existing_days or []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("date") or ""), str(item.get("platform") or ""))
        if str(item.get("status") or "").strip() in {"confirmed", "published"} and all(key):
            preserved[key] = dict(item)

    result: list[dict[str, Any]] = []
    cadence = max(1, horizon_days // max(4, len(platforms)))
    for index in range(min(horizon_days, max(4, len(platforms) * 2))):
        day = start + timedelta(days=index * cadence // 2)
        platform = platforms[index % len(platforms)]
        key = (day.isoformat(), platform)
        if key in preserved:
            result.append(preserved[key])
            continue
        result.append(
            {
                "date": day.isoformat(),
                "platform": platform,
                "topic": f"{core_message}｜{audience} #{index + 1}",
                "reason": f"對齊 {platform} 內容節奏，延伸 {core_message}",
                "status": "suggested",
            }
        )
    return result


def confirmed_topics_to_posts(plan_days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for index, item in enumerate(plan_days, start=1):
        if str(item.get("status") or "").strip() != "confirmed":
            continue
        posts.append(
            {
                "id": f"post-{index}",
                "platform": str(item.get("platform") or "Threads"),
                "title": str(item.get("topic") or "").strip(),
                "preview": str(item.get("reason") or "").strip(),
                "workflow_status": "topic_planned",
            }
        )
    return posts


def build_intel_summary(
    *,
    topic: str,
    keyword_trends: list[str],
    high_performing_examples: list[str],
    reference_notes: list[str] | None = None,
) -> dict[str, Any]:
    direction = reference_notes or [f"把 {topic} 拆成可立刻執行的步驟", f"先破除 {topic} 常見迷思，再導向 CTA"]
    summary = " / ".join(keyword_trends[:3] + high_performing_examples[:2])[:240]
    return {
        "topic": topic,
        "trend_summary": summary,
        "content_direction": direction[:3],
        "examples": high_performing_examples[:3],
        "keywords": keyword_trends[:5],
    }


def intel_writeback(summary: Mapping[str, Any], *, project_id: str, topic: str) -> dict[str, Any]:
    content_direction = summary.get("content_direction") or []
    return {
        "document": {
            "parent_id": project_id,
            "doc_kind": "intel",
            "topic": topic,
            "summary": summary.get("trend_summary") or "",
            "content_direction": list(content_direction),
        },
        "entry": {
            "type": "insight",
            "content": f"{topic}：{(content_direction[0] if content_direction else '補充情報完成')}"[:200],
        },
    }


def run_with_retry(
    operation: Callable[[], Any],
    *,
    retries: int = 3,
    sleep_fn: Callable[[float], None] | None = None,
    retryable_statuses: set[int] | None = None,
) -> tuple[Any, int]:
    retryable = retryable_statuses or {429, 500, 502, 503, 504}
    attempts = 0
    last_error: Exception | None = None
    for backoff in [0, 1, 2, 4][: retries + 1]:
        attempts += 1
        try:
            return operation(), attempts
        except Exception as exc:  # pragma: no cover - exercised by tests
            status_code = getattr(exc, "status_code", None)
            if attempts > retries or status_code not in retryable:
                raise
            last_error = exc
            if sleep_fn is not None:
                sleep_fn(float(backoff))
    if last_error is not None:  # pragma: no cover
        raise last_error
    raise RuntimeError("retry failed without error")


def generate_master_post(
    *,
    project: Mapping[str, Any],
    topic: str,
    intel_summary: Mapping[str, Any],
    style_markdown: str,
    knowledge_map_summary: str,
    revision_note: str | None = None,
    previous_versions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    strategy = project.get("strategy") or {}
    core_message = str(strategy.get("core_message") or strategy.get("coreMessage") or "品牌核心訊息").strip()
    tone = str(strategy.get("tone") or "直接").strip()
    cta = str(strategy.get("cta_strategy") or strategy.get("ctaStrategy") or "引導單一步動作").strip()
    version = max([int(item.get("version") or 0) for item in (previous_versions or [])], default=0) + 1
    body = (
        f"{topic}\n\n"
        f"核心訊息：{core_message}\n"
        f"內容方向：{', '.join(intel_summary.get('content_direction') or [])}\n"
        f"產品知識：{knowledge_map_summary}\n"
        f"語氣：{tone}\n"
        f"CTA：{cta}"
    )
    if revision_note:
        body += f"\n修訂重點：{revision_note}"
    return {
        "title": f"{topic}｜{core_message}",
        "preview": body,
        "image_brief": f"用 {tone} 語氣呈現 {topic}，畫面聚焦 {core_message}",
        "workflow_status": "draft_generated",
        "version": version,
        "used_style_markdown": style_markdown,
        "used_intel_summary": intel_summary.get("trend_summary") or "",
        "used_knowledge_map": knowledge_map_summary,
    }


def adapt_platform_variants(
    *,
    master_post: Mapping[str, Any],
    platforms: list[str],
    platform_styles: Mapping[str, str] | None = None,
    existing_variants: Mapping[str, dict[str, Any]] | None = None,
    revision_platform: str | None = None,
) -> dict[str, dict[str, Any]]:
    variants = dict(existing_variants or {})
    for platform in platforms:
        if revision_platform and platform != revision_platform and platform in variants:
            continue
        style = str((platform_styles or {}).get(platform) or "").strip()
        variants[platform] = {
            "platform": platform,
            "title": f"{master_post.get('title')} [{platform}]",
            "preview": f"{master_post.get('preview')}\n\n平台調整：{platform}\n{style}".strip(),
            "workflow_status": "platform_adapted",
            "style_applied": style,
            "source_version": int(master_post.get("version") or 1),
        }
    return variants


@dataclass
class PostizCredentials:
    base_url: str
    api_token: str


def load_postiz_credentials(env: Mapping[str, str]) -> PostizCredentials:
    base_url = str(env.get("POSTIZ_BASE_URL") or "").strip()
    api_token = str(env.get("POSTIZ_API_TOKEN") or "").strip()
    if not base_url or not api_token:
        raise ValueError("POSTIZ credentials must come from infrastructure env")
    return PostizCredentials(base_url=base_url, api_token=api_token)


def build_postiz_payload(
    *,
    post: Mapping[str, Any],
    schedule_at: str,
    channel_account_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "content": str(post.get("preview") or ""),
        "title": str(post.get("title") or ""),
        "platform": str(post.get("platform") or ""),
        "schedule_at": schedule_at,
        "channel_account_id": channel_account_id,
        "dry_run": dry_run,
    }


def publish_with_postiz(
    *,
    post: Mapping[str, Any],
    schedule_at: str,
    channel_account_id: str,
    dry_run: bool,
    env: Mapping[str, str],
    client: Callable[[PostizCredentials, dict[str, Any]], dict[str, Any]],
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    credentials = load_postiz_credentials(env)
    payload = build_postiz_payload(
        post=post,
        schedule_at=schedule_at,
        channel_account_id=channel_account_id,
        dry_run=dry_run,
    )

    def _call() -> dict[str, Any]:
        return client(credentials, payload)

    if dry_run:
        return {
            "workflow_status": "scheduled",
            "postiz_job_id": "dry-run",
            "published_at": None,
            "payload": payload,
            "attempts": 1,
        }

    result, attempts = run_with_retry(_call, retries=3, sleep_fn=sleep_fn)
    status = str(result.get("status") or "scheduled").strip().lower()
    published_at = result.get("published_at")
    if status not in {"scheduled", "published"}:
        status = "scheduled"
    if status == "published" and not published_at:
        published_at = datetime.now(timezone.utc).isoformat()
    return {
        "workflow_status": status,
        "postiz_job_id": str(result.get("job_id") or ""),
        "published_at": published_at,
        "payload": payload,
        "attempts": attempts,
    }
