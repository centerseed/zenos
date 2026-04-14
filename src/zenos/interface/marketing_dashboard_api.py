"""Marketing Dashboard REST API.

Primary endpoints:
  GET  /api/marketing/projects
  POST /api/marketing/projects
  GET  /api/marketing/projects/{projectId}
  PUT  /api/marketing/projects/{projectId}/strategy
  POST /api/marketing/projects/{projectId}/topics
  GET  /api/marketing/projects/{projectId}/styles
  POST /api/marketing/styles
  PUT  /api/marketing/styles/{styleDocId}
  POST /api/marketing/posts/{postId}/review

Legacy `/api/marketing/campaigns*` aliases remain temporarily for compatibility.

Auth: Firebase ID token -> partner scope (same as dashboard API).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from zenos.domain.knowledge import Entity, EntityEntry, Tags
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.knowledge import SqlEntityEntryRepository, SqlEntityRepository
from zenos.infrastructure.sql_common import get_pool
from zenos.interface.admin_api import _error_response, _handle_options, _json_response
from zenos.interface.dashboard_api import _auth_and_scope

logger = logging.getLogger(__name__)

POST_WORKFLOW_STATUSES = {
    "topic_planned",
    "intel_ready",
    "draft_generated",
    "draft_confirmed",
    "platform_adapted",
    "platform_confirmed",
    "scheduled",
    "published",
    "failed",
}

LEGACY_POST_STATUS_MAP = {
    "todo": "topic_planned",
    "in_progress": "intel_ready",
    "draft": "topic_planned",
    "review": "draft_generated",
    "pending_review": "draft_generated",
    "approved": "draft_confirmed",
    "request_changes": "intel_ready",
    "rejected": "intel_ready",
    "done": "published",
}

REVIEW_TRANSITIONS = {
    "draft_generated": {
        "approve": "draft_confirmed",
        "request_changes": "intel_ready",
        "reject": "intel_ready",
    },
    "platform_adapted": {
        "approve": "platform_confirmed",
        "request_changes": "draft_confirmed",
        "reject": "draft_confirmed",
    },
}

PROMPT_SKILLS = [
    "marketing-intel",
    "marketing-plan",
    "marketing-generate",
    "marketing-adapt",
    "marketing-publish",
]

PROMPT_SKILL_TITLES = {
    "marketing-intel": "情報蒐集",
    "marketing-plan": "排程規劃",
    "marketing-generate": "主文案生成",
    "marketing-adapt": "多平台適配",
    "marketing-publish": "排程發佈",
}

PROMPT_HUB_NAME = "行銷 Prompt SSOT"

DEFAULT_PROMPT_CONTENT = {
    "marketing-intel": (
        "你是行銷情報分析師。請先摘要近期高互動內容，再輸出可執行的選題建議。"
        "\n輸出格式：\n1. 平台觀察\n2. 高互動樣本\n3. 建議主題（含理由）"
    ),
    "marketing-plan": (
        "你是內容策略規劃師。請根據目標受眾、品牌語氣、歷史成效，產生未來兩週排程。"
        "\n輸出格式：\n1. 每日平台與主題\n2. 每篇目標\n3. 風險與調整建議"
    ),
    "marketing-generate": (
        "你是品牌文案編輯。請根據策略與主題產生一篇主文案與圖片 brief。"
        "\n輸出格式：\n1. Hook\n2. 內文\n3. CTA\n4. 圖片 brief"
    ),
    "marketing-adapt": (
        "你是平台改寫編輯。請把主文案改寫成指定平台版本，保留核心訊息。"
        "\n輸出格式：每平台一段，標示字數限制、hashtag 與 CTA。"
    ),
    "marketing-publish": (
        "你是發佈協調器。請檢查排程參數後輸出可直接送出的發佈命令。"
        "\n需包含：post_id、schedule_at、channel_account_id、dry_run。"
    ),
}


_marketing_repos_ready = False
_entity_repo: SqlEntityRepository | None = None
_entry_repo: SqlEntityEntryRepository | None = None


async def _ensure_marketing_repos() -> None:
    global _marketing_repos_ready, _entity_repo, _entry_repo
    if _marketing_repos_ready:
        return
    pool = await get_pool()
    _entity_repo = SqlEntityRepository(pool)
    _entry_repo = SqlEntityEntryRepository(pool)
    _marketing_repos_ready = True


def _as_list(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(v) for v in raw if v is not None]
    if raw is None:
        return []
    return [str(raw)]


def _as_text_list(raw: object) -> list[str]:
    values = _as_list(raw)
    return [value.strip() for value in values if value and value.strip()]


def _marketing_data(entity: Entity) -> dict:
    details = entity.details if isinstance(entity.details, dict) else {}
    data = details.get("marketing")
    return data if isinstance(data, dict) else {}


def _is_marketing_project(entity: Entity) -> bool:
    if entity.type != "module":
        return False
    marketing = _marketing_data(entity)
    if marketing.get("prompt_ssot") is True:
        return False
    if marketing:
        if str(marketing.get("style_level") or "").strip():
            return False
        return True
    what = [w.lower() for w in _as_list(entity.tags.what)]
    return any(("marketing" in w) or ("行銷" in w) for w in what)


def _project_type(entity: Entity) -> str:
    project_type = str(_marketing_data(entity).get("project_type") or "").strip().lower()
    return project_type if project_type in {"long_term", "short_term"} else "long_term"


def _date_range_payload(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    start = str(raw.get("start") or "").strip()
    end = str(raw.get("end") or "").strip()
    if not start or not end:
        return None
    return {"start": start, "end": end}


def _to_project_status(entity: Entity) -> str:
    marketing = _marketing_data(entity)
    explicit = str(marketing.get("project_status") or marketing.get("campaign_status") or "").strip().lower()
    if explicit in {"active", "blocked", "completed"}:
        return explicit
    if str(marketing.get("block_reason") or "").strip():
        return "blocked"
    raw = str(entity.status or "active").lower()
    if raw in {"done", "archived", "completed"}:
        return "completed"
    if raw in {"blocked", "paused"}:
        return "blocked"
    return "active"


def _to_post_status(post: Entity) -> str:
    marketing = _marketing_data(post)
    raw = str(marketing.get("workflow_status") or post.status or "draft").strip().lower()
    if raw in POST_WORKFLOW_STATUSES:
        return raw
    return LEGACY_POST_STATUS_MAP.get(raw, "topic_planned")


def _style_level(entity: Entity) -> str:
    return str(_marketing_data(entity).get("style_level") or "").strip().lower()


def _is_style_document(entity: Entity) -> bool:
    if entity.type != "document":
        return False
    return _style_level(entity) in {"product", "platform", "project"}


def _is_strategy_document(entity: Entity) -> bool:
    if entity.type != "document":
        return False
    marketing = _marketing_data(entity)
    return str(marketing.get("doc_kind") or "").strip().lower() == "strategy"


def _strategy_summary(strategy: dict) -> str:
    core = str(strategy.get("core_message") or "").strip()
    tone = str(strategy.get("tone") or "").strip()
    platforms = ", ".join(_as_text_list(strategy.get("platforms")))
    parts = [part for part in [core, f"tone={tone}" if tone else "", f"platforms={platforms}" if platforms else ""] if part]
    if not parts:
        return "更新行銷策略"
    return "；".join(parts)[:200]


def _strategy_markdown(strategy: dict, project_type: str) -> str:
    lines = [
        "# Strategy",
        "",
        f"- project_type: {project_type}",
        f"- audience: {', '.join(_as_text_list(strategy.get('audience')))}",
        f"- tone: {str(strategy.get('tone') or '').strip()}",
        f"- core_message: {str(strategy.get('core_message') or '').strip()}",
        f"- platforms: {', '.join(_as_text_list(strategy.get('platforms')))}",
    ]
    if project_type == "long_term":
        lines.extend(
            [
                f"- frequency: {str(strategy.get('frequency') or '').strip()}",
                f"- content_mix: {strategy.get('content_mix') or {}}",
            ]
        )
    if str(strategy.get("campaign_goal") or "").strip():
        lines.append(f"- campaign_goal: {str(strategy.get('campaign_goal') or '').strip()}")
    if str(strategy.get("cta_strategy") or "").strip():
        lines.append(f"- cta_strategy: {str(strategy.get('cta_strategy') or '').strip()}")
    reference_materials = _as_text_list(strategy.get("reference_materials"))
    if reference_materials:
        lines.append(f"- reference_materials: {', '.join(reference_materials)}")
    return "\n".join(lines).strip()


def _strategy_payload(strategy_doc: Entity | None, entries: list[EntityEntry] | None = None, project_type: str = "long_term") -> dict | None:
    if strategy_doc is None:
        if not entries:
            return None
        first = next((e for e in entries if e.type in {"decision", "context"}), None)
        if first is None:
            return None
        return {
            "audience": [],
            "tone": "",
            "coreMessage": "",
            "platforms": [],
            "frequency": "",
            "contentMix": {},
            "campaignGoal": "",
            "ctaStrategy": "",
            "referenceMaterials": [],
            "summaryEntry": first.content,
        }

    marketing = _marketing_data(strategy_doc)
    strategy = marketing.get("strategy")
    if not isinstance(strategy, dict):
        return None
    payload = {
        "documentId": strategy_doc.id,
        "updatedAt": strategy_doc.updated_at.isoformat() if hasattr(strategy_doc.updated_at, "isoformat") else strategy_doc.updated_at,
        "audience": _as_text_list(strategy.get("audience")),
        "tone": str(strategy.get("tone") or "").strip(),
        "coreMessage": str(strategy.get("core_message") or strategy.get("coreMessage") or "").strip(),
        "platforms": _as_text_list(strategy.get("platforms")),
        "frequency": str(strategy.get("frequency") or "").strip(),
        "contentMix": strategy.get("content_mix") if isinstance(strategy.get("content_mix"), dict) else strategy.get("contentMix") if isinstance(strategy.get("contentMix"), dict) else {},
        "campaignGoal": str(strategy.get("campaign_goal") or strategy.get("campaignGoal") or "").strip(),
        "ctaStrategy": str(strategy.get("cta_strategy") or strategy.get("ctaStrategy") or "").strip(),
        "referenceMaterials": _as_text_list(strategy.get("reference_materials") or strategy.get("referenceMaterials")),
        "content": str(marketing.get("strategy_content") or ""),
    }
    if project_type == "short_term":
        payload["frequency"] = ""
        payload["contentMix"] = {}
    if entries:
        first = next((e for e in entries if e.type in {"decision", "context"}), None)
        if first is not None:
            payload["summaryEntry"] = first.content
    return payload


def _style_payload(style_doc: Entity) -> dict:
    marketing = _marketing_data(style_doc)
    return {
        "id": style_doc.id,
        "title": style_doc.name,
        "level": _style_level(style_doc),
        "platform": str(marketing.get("style_platform") or "").strip() or None,
        "projectId": str(marketing.get("style_project_id") or "").strip() or None,
        "content": str(marketing.get("style_content") or ""),
        "updatedAt": style_doc.updated_at.isoformat() if hasattr(style_doc.updated_at, "isoformat") else style_doc.updated_at,
    }


def _normalize_content_plan(marketing: dict) -> list[dict]:
    plans = marketing.get("content_plan")
    if not isinstance(plans, list):
        return []
    result: list[dict] = []
    for item in plans:
        if not isinstance(item, dict):
            continue
        days_raw = item.get("days")
        days: list[dict] = []
        if isinstance(days_raw, list):
            for day in days_raw:
                if not isinstance(day, dict):
                    continue
                status = str(day.get("status") or "suggested")
                if status not in {"published", "confirmed", "suggested"}:
                    status = "suggested"
                days.append(
                    {
                        "day": str(day.get("day") or ""),
                        "platform": str(day.get("platform") or ""),
                        "topic": str(day.get("topic") or ""),
                        "status": status,
                    }
                )
        result.append(
            {
                "weekLabel": str(item.get("week_label") or item.get("weekLabel") or ""),
                "isCurrent": bool(item.get("is_current") or item.get("isCurrent")),
                "days": days,
                "aiNote": str(item.get("ai_note") or item.get("aiNote") or ""),
            }
        )
    return result


def _to_post_dict(post: Entity) -> dict:
    marketing = _marketing_data(post)
    metrics = marketing.get("metrics")
    normalized_metrics = metrics if isinstance(metrics, dict) else None
    return {
        "id": post.id,
        "platform": str(marketing.get("platform") or "Threads"),
        "status": _to_post_status(post),
        "title": post.name,
        "preview": str(marketing.get("preview") or post.summary or ""),
        "imageDesc": str(marketing.get("image_brief") or marketing.get("imageDesc") or ""),
        "scheduledAt": marketing.get("scheduled_at") or marketing.get("scheduledAt"),
        "publishedAt": marketing.get("published_at") or marketing.get("publishedAt"),
        "aiReason": str(marketing.get("ai_reason") or marketing.get("aiReason") or ""),
        "metrics": normalized_metrics,
    }


def _campaign_stats(marketing: dict, posts: list[dict]) -> tuple[dict, dict, dict]:
    stats = marketing.get("stats") if isinstance(marketing.get("stats"), dict) else {}
    trend = marketing.get("trend") if isinstance(marketing.get("trend"), dict) else {}
    review_count = sum(1 for p in posts if p["status"] in {"draft_generated", "platform_adapted"})
    approved_count = sum(1 for p in posts if p["status"] in {"draft_confirmed", "platform_confirmed", "scheduled"})
    published_count = sum(1 for p in posts if p["status"] == "published")
    total_posts = len(posts)
    this_week = {
        "posts": int(stats.get("this_week_posts") or total_posts),
        "approved": int(stats.get("this_week_approved") or approved_count),
        "published": int(stats.get("this_week_published") or published_count),
    }
    normalized_stats = {
        "followers": str(stats.get("followers") or "—"),
        "postsThisMonth": int(stats.get("posts_this_month") or stats.get("postsThisMonth") or total_posts),
        "avgEngagement": str(stats.get("avg_engagement") or stats.get("avgEngagement") or "—"),
    }
    normalized_trend = {
        "followers": str(trend.get("followers") or "—"),
        "engagement": str(trend.get("engagement") or "—"),
    }
    return this_week, normalized_stats, normalized_trend


def _to_project_dict(
    project: Entity,
    posts: list[Entity],
    *,
    strategy_doc: Entity | None = None,
    entries: list[EntityEntry] | None = None,
) -> dict:
    marketing = _marketing_data(project)
    post_dicts = [_to_post_dict(p) for p in posts]
    this_week, stats, trend = _campaign_stats(marketing, post_dicts)
    project_type = _project_type(project)
    strategy = _strategy_payload(strategy_doc, entries=entries, project_type=project_type)
    content_plan = _normalize_content_plan(marketing)
    block_reason = str(marketing.get("block_reason") or marketing.get("blockReason") or "")
    date_range = _date_range_payload(marketing.get("date_range") or marketing.get("dateRange"))

    payload = {
        "id": project.id,
        "name": project.name,
        "description": project.summary,
        "status": _to_project_status(project),
        "projectType": project_type,
        "updatedAt": project.updated_at.isoformat() if hasattr(project.updated_at, "isoformat") else project.updated_at,
        "dateRange": date_range,
        "productId": project.parent_id,
        "blockReason": block_reason or None,
        "thisWeek": this_week,
        "stats": stats,
        "trend": trend,
        "posts": post_dicts,
    }
    if strategy:
        payload["strategy"] = strategy
    if content_plan:
        payload["contentPlan"] = content_plan
    return payload


def _product_group_payload(product: Entity | None, projects: list[dict]) -> dict:
    product_id = product.id if product else None
    product_name = product.name if product else "Unassigned"
    return {
        "product": {
            "id": product_id,
            "name": product_name,
        },
        "projects": sorted(projects, key=lambda item: str(item["name"]).lower()),
    }


def _normalize_prompt_versions(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    versions: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            version = int(item.get("version") or 0)
        except Exception:
            continue
        content = str(item.get("content") or "")
        if version <= 0 or not content:
            continue
        versions.append(
            {
                "version": version,
                "content": content,
                "created_at": str(item.get("created_at") or ""),
                "created_by": str(item.get("created_by") or ""),
                "note": str(item.get("note") or ""),
            }
        )
    versions.sort(key=lambda v: int(v["version"]))
    return versions


def _default_prompt_skill_state(skill: str, now_iso: str) -> dict:
    content = DEFAULT_PROMPT_CONTENT[skill]
    return {
        "published_version": 1,
        "published_content": content,
        "draft_content": content,
        "draft_updated_at": now_iso,
        "versions": [
            {
                "version": 1,
                "content": content,
                "created_at": now_iso,
                "created_by": "system",
                "note": "初始化版本",
            }
        ],
    }


def _ensure_prompt_skills_shape(skills_raw: object, now_iso: str) -> dict:
    skills = skills_raw if isinstance(skills_raw, dict) else {}
    normalized: dict[str, dict] = {}
    for skill in PROMPT_SKILLS:
        raw = skills.get(skill) if isinstance(skills, dict) else None
        if not isinstance(raw, dict):
            normalized[skill] = _default_prompt_skill_state(skill, now_iso)
            continue
        versions = _normalize_prompt_versions(raw.get("versions"))
        published_version = int(raw.get("published_version") or (versions[-1]["version"] if versions else 0))
        published_content = str(raw.get("published_content") or "")
        if not published_content and versions:
            matched = next((v for v in versions if int(v["version"]) == published_version), versions[-1])
            published_content = str(matched.get("content") or "")
        if not published_content:
            default_state = _default_prompt_skill_state(skill, now_iso)
            normalized[skill] = default_state
            continue
        draft_content = str(raw.get("draft_content") or published_content)
        draft_updated_at = str(raw.get("draft_updated_at") or now_iso)
        if not versions:
            versions = [
                {
                    "version": published_version or 1,
                    "content": published_content,
                    "created_at": now_iso,
                    "created_by": "system",
                    "note": "自動補齊版本",
                }
            ]
        normalized[skill] = {
            "published_version": max(1, published_version or 1),
            "published_content": published_content,
            "draft_content": draft_content,
            "draft_updated_at": draft_updated_at,
            "versions": versions,
        }
    return normalized


def _prompt_hub_marketing(entity: Entity) -> dict:
    details = entity.details if isinstance(entity.details, dict) else {}
    marketing = details.get("marketing")
    if not isinstance(marketing, dict):
        marketing = {}
    now_iso = datetime.now(timezone.utc).isoformat()
    skills = _ensure_prompt_skills_shape(marketing.get("prompt_skills"), now_iso)
    marketing["prompt_ssot"] = True
    marketing["prompt_skills"] = skills
    details["marketing"] = marketing
    entity.details = details
    return marketing


def _prompt_payload(skill: str, state: dict) -> dict:
    versions = _normalize_prompt_versions(state.get("versions"))
    published_version = int(state.get("published_version") or 1)
    return {
        "skill": skill,
        "title": PROMPT_SKILL_TITLES.get(skill, skill),
        "publishedVersion": published_version,
        "publishedContent": str(state.get("published_content") or ""),
        "draftContent": str(state.get("draft_content") or ""),
        "draftUpdatedAt": str(state.get("draft_updated_at") or ""),
        "history": [
            {
                "version": int(v["version"]),
                "createdAt": v["created_at"],
                "createdBy": v["created_by"],
                "note": v["note"],
                "isPublished": int(v["version"]) == published_version,
            }
            for v in reversed(versions)
        ],
    }


async def _ensure_prompt_hub_entity(partner: dict, effective_id: str) -> Entity:
    actor = str(partner.get("displayName") or partner.get("email") or "").strip()
    now = datetime.now(timezone.utc)
    token = current_partner_id.set(effective_id)
    try:
        existing = await _entity_repo.get_by_name(PROMPT_HUB_NAME)
        if existing:
            before = str(existing.details or "")
            marketing = _prompt_hub_marketing(existing)
            after = str(existing.details or "")
            changed = before != after
            if changed:
                existing.updated_at = now
                existing = await _entity_repo.upsert(existing)
            return existing

        created = Entity(
            id=uuid.uuid4().hex,
            name=PROMPT_HUB_NAME,
            type="module",
            level=2,
            parent_id=None,
            status="active",
            summary="行銷 prompt 的單一真相來源（SSOT）",
            tags=Tags(
                what=["marketing", "prompt", "ssot"],
                why="全公司共用一致的行銷提示詞",
                how="Web 編輯、版本化發布",
                who=["marketing"],
            ),
            details={
                "marketing": {
                    "prompt_ssot": True,
                    "prompt_skills": {
                        skill: _default_prompt_skill_state(skill, now.isoformat())
                        for skill in PROMPT_SKILLS
                    },
                }
            },
            confirmed_by_user=True,
            sources=[],
            owner=actor or None,
            visibility="public",
            created_at=now,
            updated_at=now,
        )
        created = await _entity_repo.upsert(created)
        return created
    finally:
        current_partner_id.reset(token)


async def list_projects(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    token = current_partner_id.set(effective_id)
    try:
        products = await _entity_repo.list_all(type_filter="product")
        modules = await _entity_repo.list_all(type_filter="module")
        docs = await _entity_repo.list_all(type_filter="document")
        products_by_id = {entity.id: entity for entity in products if entity.id}
        projects = [e for e in modules if _is_marketing_project(e)]
        project_ids = {project.id for project in projects if project.id}
        posts_by_project: dict[str, list[Entity]] = {pid: [] for pid in project_ids}
        strategy_docs_by_project: dict[str, Entity] = {}
        for entity in docs:
            if entity.parent_id in posts_by_project and not _is_style_document(entity) and not _is_strategy_document(entity):
                posts_by_project[entity.parent_id].append(entity)
            if entity.parent_id in project_ids and _is_strategy_document(entity):
                current = strategy_docs_by_project.get(entity.parent_id)
                if (entity.updated_at or datetime.min.replace(tzinfo=timezone.utc)) > (
                    current.updated_at if current and current.updated_at else datetime.min.replace(tzinfo=timezone.utc)
                ):
                    strategy_docs_by_project[entity.parent_id] = entity

        grouped: dict[str, list[dict]] = {}
        for project in projects:
            payload = _to_project_dict(
                project,
                posts_by_project.get(project.id, []),
                strategy_doc=strategy_docs_by_project.get(project.id),
            )
            group_key = project.parent_id or "__ungrouped__"
            grouped.setdefault(group_key, []).append(payload)

        groups = [
            _product_group_payload(products_by_id.get(group_key), grouped_projects)
            for group_key, grouped_projects in grouped.items()
        ]
        groups.sort(key=lambda item: str(item["product"]["name"]).lower())
        return _json_response({"groups": groups}, request=request)
    except Exception as exc:
        logger.error("list_projects failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to list projects", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def create_project(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    name = str(body.get("name") or "").strip()
    description = str(body.get("description") or "").strip()
    product_id = str(body.get("product_id") or body.get("productId") or body.get("parentId") or "").strip() or None
    project_type = str(body.get("project_type") or body.get("projectType") or "").strip().lower()
    date_range = _date_range_payload(body.get("date_range") or body.get("dateRange"))

    if len(name) < 2:
        return _error_response("INVALID_INPUT", "name must be at least 2 chars", 400, request=request)
    if not product_id:
        return _error_response("INVALID_INPUT", "product_id is required", 400, request=request)
    if project_type not in {"long_term", "short_term"}:
        return _error_response("INVALID_INPUT", "project_type must be long_term or short_term", 400, request=request)
    if project_type == "short_term" and date_range is None:
        return _error_response("INVALID_INPUT", "date_range is required for short_term project", 400, request=request)
    if not description:
        description = f"{name} 行銷項目"

    actor = str(partner.get("displayName") or partner.get("email") or "").strip()
    now = datetime.now(timezone.utc)
    project = Entity(
        id=uuid.uuid4().hex,
        name=name,
        type="module",
        level=2,
        parent_id=product_id,
        status="active",
        summary=description,
        tags=Tags(
            what=["marketing", "project"],
            why="提升品牌觸及與轉換",
            how="Web + Claude cowork + runner",
            who=["marketing"],
        ),
        details={
            "marketing": {
                "project_status": "active",
                "project_type": project_type,
                "date_range": date_range,
            }
        },
        confirmed_by_user=True,
        sources=[],
        owner=actor or None,
        visibility="public",
        created_at=now,
        updated_at=now,
    )

    token = current_partner_id.set(effective_id)
    try:
        created = await _entity_repo.upsert(project)
        await _entry_repo.create(
            EntityEntry(
                id=uuid.uuid4().hex,
                partner_id=effective_id,
                entity_id=created.id or project.id or "",
                type="change",
                content=f"由 Dashboard 建立行銷項目：{name}"[:200],
                context="source=dashboard"[:200],
                author=(actor[:120] or None),
            )
        )
        payload = _to_project_dict(created, [])
        return _json_response({"project": payload}, request=request)
    except Exception as exc:
        logger.error("create_project failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to create project", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def projects_collection(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "POST":
        return await create_project(request)
    return await list_projects(request)


async def get_prompt_ssot(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        hub = await _ensure_prompt_hub_entity(partner, effective_id)
        marketing = _prompt_hub_marketing(hub)
        skills = marketing.get("prompt_skills") if isinstance(marketing.get("prompt_skills"), dict) else {}
        prompts = [
            _prompt_payload(skill, skills.get(skill) if isinstance(skills.get(skill), dict) else {})
            for skill in PROMPT_SKILLS
        ]
        return _json_response(
            {
                "hubId": hub.id,
                "prompts": prompts,
            },
            request=request,
        )
    except Exception as exc:
        logger.error("get_prompt_ssot failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to load prompt SSOT", 500, request=request)


async def update_prompt_draft(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    skill = str(request.path_params.get("skill") or "").strip()
    if skill not in PROMPT_SKILLS:
        return _error_response("INVALID_INPUT", "Unsupported skill", 400, request=request)

    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    content = str(body.get("content") or "")
    if len(content.strip()) < 10:
        return _error_response("INVALID_INPUT", "content must be at least 10 chars", 400, request=request)

    await _ensure_marketing_repos()
    actor = str(partner.get("displayName") or partner.get("email") or "").strip()
    token = current_partner_id.set(effective_id)
    try:
        hub = await _ensure_prompt_hub_entity(partner, effective_id)
        marketing = _prompt_hub_marketing(hub)
        skills = marketing.get("prompt_skills") if isinstance(marketing.get("prompt_skills"), dict) else {}
        skill_state = skills.get(skill)
        if not isinstance(skill_state, dict):
            skill_state = _default_prompt_skill_state(skill, datetime.now(timezone.utc).isoformat())
        skill_state["draft_content"] = content
        skill_state["draft_updated_at"] = datetime.now(timezone.utc).isoformat()
        skills[skill] = skill_state
        marketing["prompt_skills"] = skills
        hub.updated_at = datetime.now(timezone.utc)
        saved = await _entity_repo.upsert(hub)

        await _entry_repo.create(
            EntityEntry(
                id=uuid.uuid4().hex,
                partner_id=effective_id,
                entity_id=saved.id or hub.id or "",
                type="change",
                content=f"更新 {skill} 的 draft prompt"[:200],
                context="prompt_draft_update"[:200],
                author=(actor[:120] or None),
            )
        )
        payload = _prompt_payload(skill, skill_state)
        return _json_response({"prompt": payload}, request=request)
    except Exception as exc:
        logger.error("update_prompt_draft failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to update prompt draft", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def publish_prompt(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    skill = str(request.path_params.get("skill") or "").strip()
    if skill not in PROMPT_SKILLS:
        return _error_response("INVALID_INPUT", "Unsupported skill", 400, request=request)

    try:
        body = await request.json()
    except Exception:
        body = {}
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    source_version = body.get("sourceVersion")
    note = str(body.get("note") or "").strip()

    await _ensure_marketing_repos()
    actor = str(partner.get("displayName") or partner.get("email") or "").strip()
    token = current_partner_id.set(effective_id)
    try:
        hub = await _ensure_prompt_hub_entity(partner, effective_id)
        marketing = _prompt_hub_marketing(hub)
        skills = marketing.get("prompt_skills") if isinstance(marketing.get("prompt_skills"), dict) else {}
        skill_state = skills.get(skill)
        if not isinstance(skill_state, dict):
            skill_state = _default_prompt_skill_state(skill, datetime.now(timezone.utc).isoformat())
        versions = _normalize_prompt_versions(skill_state.get("versions"))
        published_version = int(skill_state.get("published_version") or 1)

        publish_content = str(skill_state.get("draft_content") or "").strip()
        if source_version is not None:
            try:
                source_version_num = int(source_version)
            except Exception:
                return _error_response("INVALID_INPUT", "sourceVersion must be integer", 400, request=request)
            matched = next((v for v in versions if int(v["version"]) == source_version_num), None)
            if matched is None:
                return _error_response("NOT_FOUND", "sourceVersion not found", 404, request=request)
            publish_content = str(matched.get("content") or "")
        if len(publish_content) < 10:
            return _error_response("INVALID_INPUT", "publish content is empty", 400, request=request)

        new_version = max([int(v["version"]) for v in versions], default=published_version) + 1
        now_iso = datetime.now(timezone.utc).isoformat()
        versions.append(
            {
                "version": new_version,
                "content": publish_content,
                "created_at": now_iso,
                "created_by": actor or "unknown",
                "note": note or ("回滾發布" if source_version is not None else "發布新版本"),
            }
        )
        skill_state["versions"] = versions
        skill_state["published_version"] = new_version
        skill_state["published_content"] = publish_content
        skill_state["draft_content"] = publish_content
        skill_state["draft_updated_at"] = now_iso
        skills[skill] = skill_state
        marketing["prompt_skills"] = skills

        hub.updated_at = datetime.now(timezone.utc)
        saved = await _entity_repo.upsert(hub)
        await _entry_repo.create(
            EntityEntry(
                id=uuid.uuid4().hex,
                partner_id=effective_id,
                entity_id=saved.id or hub.id or "",
                type="decision",
                content=f"發布 {skill} prompt v{new_version}"[:200],
                context=(note[:200] if note else None),
                author=(actor[:120] or None),
            )
        )
        payload = _prompt_payload(skill, skill_state)
        return _json_response({"prompt": payload}, request=request)
    except Exception as exc:
        logger.error("publish_prompt failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to publish prompt", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def get_project_detail(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    project_id = request.path_params.get("projectId") or request.path_params.get("campaignId")
    token = current_partner_id.set(effective_id)
    try:
        project = await _entity_repo.get_by_id(project_id)
        if project is None or not _is_marketing_project(project):
            return _error_response("NOT_FOUND", "Project not found", 404, request=request)

        docs = await _entity_repo.list_by_parent(project_id)
        posts = [e for e in docs if not _is_style_document(e) and not _is_strategy_document(e)]
        strategy_doc = _find_latest_strategy_doc(docs)
        entries = await _entry_repo.list_by_entity(project_id)
        payload = _to_project_dict(project, posts, strategy_doc=strategy_doc, entries=entries)
        payload["entries"] = [
            {
                "id": e.id,
                "type": e.type,
                "content": e.content,
                "context": e.context,
                "author": e.author,
                "createdAt": e.created_at,
            }
            for e in entries
        ]
        return _json_response({"project": payload}, request=request)
    except Exception as exc:
        logger.error("get_project_detail failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to load project", 500, request=request)
    finally:
        current_partner_id.reset(token)


def _strategy_request(body: dict) -> tuple[dict, str]:
    project_type = str(body.get("project_type") or body.get("projectType") or "").strip().lower()
    audience = _as_text_list(body.get("audience"))
    tone = str(body.get("tone") or "").strip()
    core_message = str(body.get("core_message") or body.get("coreMessage") or "").strip()
    platforms = _as_text_list(body.get("platforms"))
    frequency = str(body.get("frequency") or "").strip()
    content_mix = body.get("content_mix") if isinstance(body.get("content_mix"), dict) else body.get("contentMix") if isinstance(body.get("contentMix"), dict) else {}
    campaign_goal = str(body.get("campaign_goal") or body.get("campaignGoal") or "").strip()
    cta_strategy = str(body.get("cta_strategy") or body.get("ctaStrategy") or "").strip()
    reference_materials = _as_text_list(body.get("reference_materials") or body.get("referenceMaterials"))
    strategy = {
        "audience": audience,
        "tone": tone,
        "core_message": core_message,
        "platforms": platforms,
        "frequency": frequency,
        "content_mix": content_mix,
        "campaign_goal": campaign_goal,
        "cta_strategy": cta_strategy,
        "reference_materials": reference_materials,
    }
    return strategy, project_type


def _find_latest_strategy_doc(docs: list[Entity]) -> Entity | None:
    strategy_docs = [doc for doc in docs if _is_strategy_document(doc)]
    if not strategy_docs:
        return None
    strategy_docs.sort(key=lambda doc: doc.updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return strategy_docs[0]


async def update_project_strategy(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    strategy, request_project_type = _strategy_request(body)
    expected_updated_at = str(body.get("expected_updated_at") or body.get("expectedUpdatedAt") or "").strip() or None
    project_id = request.path_params.get("projectId") or request.path_params.get("campaignId")
    token = current_partner_id.set(effective_id)
    try:
        project = await _entity_repo.get_by_id(project_id)
        if project is None or not _is_marketing_project(project):
            return _error_response("NOT_FOUND", "Project not found", 404, request=request)
        docs = await _entity_repo.list_by_parent(project_id)
        strategy_doc = _find_latest_strategy_doc(docs)

        details = project.details if isinstance(project.details, dict) else {}
        marketing = _marketing_data(project)
        project_type = request_project_type or _project_type(project)
        if not strategy["audience"] or not strategy["tone"] or not strategy["core_message"] or not strategy["platforms"]:
            return _error_response("INVALID_INPUT", "audience, tone, core_message, platforms are required", 400, request=request)
        if project_type == "long_term" and (not strategy["frequency"] or not strategy["content_mix"]):
            return _error_response("INVALID_INPUT", "frequency and content_mix are required for long_term project", 400, request=request)
        if project_type == "short_term":
            strategy["frequency"] = ""
            strategy["content_mix"] = {}

        current_strategy_updated_at = (
            strategy_doc.updated_at.isoformat() if strategy_doc and hasattr(strategy_doc.updated_at, "isoformat") else None
        )
        if expected_updated_at and current_strategy_updated_at and expected_updated_at != current_strategy_updated_at:
            return _error_response("CONFLICT", "strategy updated_at mismatch", 409, request=request)

        marketing["project_type"] = project_type
        marketing["strategy_document_id"] = strategy_doc.id if strategy_doc else marketing.get("strategy_document_id")
        details["marketing"] = marketing
        project.details = details
        project.updated_at = datetime.now(timezone.utc)
        updated_project = await _entity_repo.upsert(project)

        strategy_markdown = _strategy_markdown(strategy, project_type)
        if strategy_doc is None:
            strategy_doc = Entity(
                id=uuid.uuid4().hex,
                name=f"{project.name} Strategy",
                type="document",
                level=3,
                parent_id=project_id,
                status="active",
                summary=_strategy_summary(strategy),
                tags=project.tags,
                details={
                    "marketing": {
                        "doc_kind": "strategy",
                        "project_type": project_type,
                        "strategy": strategy,
                        "strategy_content": strategy_markdown,
                    }
                },
                confirmed_by_user=True,
                sources=[],
                owner=str(partner.get("displayName") or partner.get("email") or "") or None,
                visibility=project.visibility or "public",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        else:
            strategy_details = strategy_doc.details if isinstance(strategy_doc.details, dict) else {}
            strategy_marketing = _marketing_data(strategy_doc)
            strategy_marketing["doc_kind"] = "strategy"
            strategy_marketing["project_type"] = project_type
            strategy_marketing["strategy"] = strategy
            strategy_marketing["strategy_content"] = strategy_markdown
            strategy_details["marketing"] = strategy_marketing
            strategy_doc.details = strategy_details
            strategy_doc.summary = _strategy_summary(strategy)
            strategy_doc.name = f"{project.name} Strategy"
            strategy_doc.updated_at = datetime.now(timezone.utc)
        strategy_doc = await _entity_repo.upsert(strategy_doc)
        marketing["strategy_document_id"] = strategy_doc.id
        details["marketing"] = marketing
        updated_project.details = details
        updated_project = await _entity_repo.upsert(updated_project)

        actor = str(partner.get("displayName") or partner.get("email") or "").strip()
        await _entry_repo.create(
            EntityEntry(
                id=uuid.uuid4().hex,
                partner_id=effective_id,
                entity_id=updated_project.id or project_id,
                type="decision",
                content=_strategy_summary(strategy),
                context=f"project_type={project_type}; strategy_document_id={strategy_doc.id}"[:200],
                author=(actor[:120] or None),
            )
        )

        posts = [entity for entity in docs if not _is_style_document(entity) and not _is_strategy_document(entity)]
        payload = _to_project_dict(updated_project, posts, strategy_doc=strategy_doc)
        return _json_response({"project": payload}, request=request)
    except Exception as exc:
        logger.error("update_project_strategy failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to update strategy", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def create_project_topic(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    topic = str(body.get("topic") or "").strip()
    platform = str(body.get("platform") or "Threads").strip() or "Threads"
    brief = str(body.get("brief") or "").strip()
    ai_reason = str(body.get("aiReason") or "").strip()

    if len(topic) < 2:
        return _error_response("INVALID_INPUT", "topic must be at least 2 chars", 400, request=request)

    project_id = request.path_params.get("projectId") or request.path_params.get("campaignId")
    token = current_partner_id.set(effective_id)
    try:
        project = await _entity_repo.get_by_id(project_id)
        if project is None or not _is_marketing_project(project):
            return _error_response("NOT_FOUND", "Project not found", 404, request=request)

        now = datetime.now(timezone.utc)
        preview = brief or f"主題：{topic}"
        post = Entity(
            id=uuid.uuid4().hex,
            name=topic,
            type="document",
            level=3,
            parent_id=project_id,
            status="draft",
            summary=preview,
            tags=project.tags,
            details={
                "marketing": {
                    "platform": platform,
                    "workflow_status": "topic_planned",
                    "preview": preview,
                    "ai_reason": ai_reason or "主題已建立，下一步請先執行 /marketing-intel 補足情報。",
                    "created_via": "dashboard",
                }
            },
            confirmed_by_user=True,
            sources=[],
            owner=str(partner.get("displayName") or partner.get("email") or "") or None,
            visibility=project.visibility or "public",
            created_at=now,
            updated_at=now,
        )
        created = await _entity_repo.upsert(post)

        entry = EntityEntry(
            id=uuid.uuid4().hex,
            partner_id=effective_id,
            entity_id=created.id or post.id or "",
            type="change",
            content=f"由 Dashboard 建立主題：{topic}"[:200],
            context=f"platform={platform}"[:200],
            author=(str(partner.get("displayName") or partner.get("email") or "")[:120] or None),
        )
        await _entry_repo.create(entry)

        return _json_response({"post": _to_post_dict(created)}, request=request)
    except Exception as exc:
        logger.error("create_project_topic failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to create topic", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def get_project_styles(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    project_id = request.path_params["projectId"]
    token = current_partner_id.set(effective_id)
    try:
        project = await _entity_repo.get_by_id(project_id)
        if project is None or not _is_marketing_project(project):
            return _error_response("NOT_FOUND", "Project not found", 404, request=request)
        product_id = project.parent_id
        product_docs = await _entity_repo.list_by_parent(product_id) if product_id else []
        project_docs = await _entity_repo.list_by_parent(project_id)
        product_styles = []
        platform_styles = []
        project_styles = []
        for doc in project_docs:
            if not _is_style_document(doc):
                continue
            level = _style_level(doc)
            payload = _style_payload(doc)
            if level == "project" and str(payload["projectId"] or "") == project_id:
                project_styles.append(payload)
        for doc in product_docs:
            if not _is_style_document(doc):
                continue
            level = _style_level(doc)
            payload = _style_payload(doc)
            if level == "product" and doc.parent_id == product_id:
                product_styles.append(payload)
            elif level == "platform" and doc.parent_id == product_id:
                platform_styles.append(payload)
        return _json_response(
            {
                "styles": {
                    "product": sorted(product_styles, key=lambda item: str(item["title"]).lower()),
                    "platform": sorted(platform_styles, key=lambda item: str(item["title"]).lower()),
                    "project": sorted(project_styles, key=lambda item: str(item["title"]).lower()),
                }
            },
            request=request,
        )
    except Exception as exc:
        logger.error("get_project_styles failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to load styles", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def create_style(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    level = str(body.get("level") or "").strip().lower()
    title = str(body.get("title") or "").strip()
    content = str(body.get("content") or "")
    product_id = str(body.get("product_id") or body.get("productId") or "").strip() or None
    project_id = str(body.get("project_id") or body.get("projectId") or "").strip() or None
    platform = str(body.get("platform") or "").strip().lower() or None
    if level not in {"product", "platform", "project"}:
        return _error_response("INVALID_INPUT", "level must be product, platform, or project", 400, request=request)
    if len(title) < 2 or len(content.strip()) < 10:
        return _error_response("INVALID_INPUT", "title and content are required", 400, request=request)
    if level in {"product", "platform"} and not product_id:
        return _error_response("INVALID_INPUT", "product_id is required for product/platform styles", 400, request=request)
    if level == "platform" and not platform:
        return _error_response("INVALID_INPUT", "platform is required for platform style", 400, request=request)
    if level == "project" and not project_id:
        return _error_response("INVALID_INPUT", "project_id is required for project style", 400, request=request)

    parent_id = project_id if level == "project" else product_id
    now = datetime.now(timezone.utc)
    actor = str(partner.get("displayName") or partner.get("email") or "").strip()
    style_doc = Entity(
        id=uuid.uuid4().hex,
        name=title,
        type="document",
        level=3,
        parent_id=parent_id,
        status="active",
        summary=content.strip()[:200],
        tags=Tags(what=["marketing", "style"], why="控制文案生成語氣與格式", how="三層 style 組合", who=["marketing"]),
        details={
            "marketing": {
                "style_level": level,
                "style_platform": platform,
                "style_project_id": project_id,
                "style_content": content,
            }
        },
        confirmed_by_user=True,
        sources=[],
        owner=actor or None,
        visibility="public",
        created_at=now,
        updated_at=now,
    )

    token = current_partner_id.set(effective_id)
    try:
        created = await _entity_repo.upsert(style_doc)
        return _json_response({"style": _style_payload(created)}, request=request)
    except Exception as exc:
        logger.error("create_style failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to create style", 500, request=request)
    finally:
        current_partner_id.reset(token)


async def update_style(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    style_doc_id = request.path_params["styleDocId"]
    title = str(body.get("title") or "").strip()
    content = str(body.get("content") or "")

    token = current_partner_id.set(effective_id)
    try:
        style_doc = await _entity_repo.get_by_id(style_doc_id)
        if style_doc is None or not _is_style_document(style_doc):
            return _error_response("NOT_FOUND", "Style not found", 404, request=request)
        marketing = _marketing_data(style_doc)
        if title:
            style_doc.name = title
        if content.strip():
            marketing["style_content"] = content
            style_doc.summary = content.strip()[:200]
        details = style_doc.details if isinstance(style_doc.details, dict) else {}
        details["marketing"] = marketing
        style_doc.details = details
        style_doc.updated_at = datetime.now(timezone.utc)
        updated = await _entity_repo.upsert(style_doc)
        return _json_response({"style": _style_payload(updated)}, request=request)
    except Exception as exc:
        logger.error("update_style failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to update style", 500, request=request)
    finally:
        current_partner_id.reset(token)


def _review_result(current_status: str, action: str) -> tuple[str, str] | None:
    next_status = REVIEW_TRANSITIONS.get(current_status, {}).get(action)
    if next_status is None:
        return None
    if action == "approve":
        return next_status, "decision"
    if action == "request_changes":
        return next_status, "change"
    return next_status, "limitation"


async def review_post(request: Request) -> Response:
    if request.method == "OPTIONS":
        return _handle_options(request)

    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    await _ensure_marketing_repos()
    try:
        body = await request.json()
    except Exception:
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)
    if not isinstance(body, dict):
        return _error_response("INVALID_INPUT", "Body must be an object", 400, request=request)

    action = str(body.get("action") or "").strip()
    if action not in {"approve", "request_changes", "reject"}:
        return _error_response(
            "INVALID_INPUT",
            "action must be one of: approve, request_changes, reject",
            400,
            request=request,
        )
    comment = str(body.get("comment") or "").strip()
    reviewer = str(body.get("reviewer") or partner.get("displayName") or partner.get("email") or "").strip()

    post_id = request.path_params["postId"]
    token = current_partner_id.set(effective_id)
    try:
        post = await _entity_repo.get_by_id(post_id)
        if post is None or post.type != "document":
            return _error_response("NOT_FOUND", "Post not found", 404, request=request)

        marketing = _marketing_data(post)
        current_status = _to_post_status(post)
        transition = _review_result(current_status, action)
        if transition is None:
            allowed = sorted(REVIEW_TRANSITIONS.get(current_status, {}).keys())
            return _error_response(
                "INVALID_STATE_TRANSITION",
                f"Cannot {action} from {current_status}. Allowed actions: {', '.join(allowed) if allowed else 'none'}",
                409,
                request=request,
            )
        new_status, entry_type = transition
        now_iso = datetime.now(timezone.utc).isoformat()
        transition_record = {
            "from_status": current_status,
            "to_status": new_status,
            "timestamp": now_iso,
            "actor": reviewer,
            "action": action,
        }
        history = marketing.get("transition_history") if isinstance(marketing.get("transition_history"), list) else []
        history.append(transition_record)
        marketing["transition_history"] = history[-20:]
        marketing["last_transition"] = transition_record
        marketing["workflow_status"] = new_status
        marketing["last_review_action"] = action
        marketing["last_review_comment"] = comment
        marketing["last_reviewed_by"] = reviewer
        marketing["last_reviewed_at"] = now_iso

        details = post.details if isinstance(post.details, dict) else {}
        details["marketing"] = marketing
        post.details = details
        post.updated_at = datetime.now(timezone.utc)
        updated = await _entity_repo.upsert(post)

        entry_content = comment or (
            "文案已核准，可進入平台適配。" if action == "approve" else "文案已退回，請依意見調整。"
        )
        entry = EntityEntry(
            id=uuid.uuid4().hex,
            partner_id=effective_id,
            entity_id=post_id,
            type=entry_type,
            content=entry_content[:200],
            context=f"review_action={action}; from={current_status}; to={new_status}"[:200],
            author=reviewer[:120] or None,
        )
        await _entry_repo.create(entry)

        return _json_response({"post": _to_post_dict(updated)}, request=request)
    except Exception as exc:
        logger.error("review_post failed: %s", exc, exc_info=True)
        return _error_response("INTERNAL_ERROR", "Failed to review post", 500, request=request)
    finally:
        current_partner_id.reset(token)


marketing_dashboard_routes = [
    Route("/api/marketing/projects", projects_collection, methods=["GET", "POST", "OPTIONS"]),
    Route("/api/marketing/projects/{projectId}", get_project_detail, methods=["GET", "OPTIONS"]),
    Route("/api/marketing/projects/{projectId}/strategy", update_project_strategy, methods=["PUT", "OPTIONS"]),
    Route("/api/marketing/projects/{projectId}/topics", create_project_topic, methods=["POST", "OPTIONS"]),
    Route("/api/marketing/projects/{projectId}/styles", get_project_styles, methods=["GET", "OPTIONS"]),
    Route("/api/marketing/styles", create_style, methods=["POST", "OPTIONS"]),
    Route("/api/marketing/styles/{styleDocId}", update_style, methods=["PUT", "OPTIONS"]),
    Route("/api/marketing/campaigns", projects_collection, methods=["GET", "POST", "OPTIONS"]),
    Route("/api/marketing/campaigns/{campaignId}", get_project_detail, methods=["GET", "OPTIONS"]),
    Route("/api/marketing/campaigns/{campaignId}/strategy", update_project_strategy, methods=["PUT", "OPTIONS"]),
    Route("/api/marketing/campaigns/{campaignId}/topics", create_project_topic, methods=["POST", "OPTIONS"]),
    Route("/api/marketing/posts/{postId}/review", review_post, methods=["POST", "OPTIONS"]),
    Route("/api/marketing/prompts", get_prompt_ssot, methods=["GET", "OPTIONS"]),
    Route("/api/marketing/prompts/{skill}/draft", update_prompt_draft, methods=["PUT", "OPTIONS"]),
    Route("/api/marketing/prompts/{skill}/publish", publish_prompt, methods=["POST", "OPTIONS"]),
]
