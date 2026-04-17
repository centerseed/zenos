"""CRM Dashboard REST API — Firebase ID token auth for CRM endpoints.

Endpoints:
  GET  /api/crm/companies                      — list companies
  POST /api/crm/companies                      — create company
  GET  /api/crm/companies/{id}                 — get company
  PUT  /api/crm/companies/{id}                 — update company
  GET  /api/crm/companies/{id}/contacts        — list company contacts
  GET  /api/crm/companies/{id}/deals           — list company deals
  POST /api/crm/contacts                       — create contact
  GET  /api/crm/contacts/{id}                  — get contact
  PUT  /api/crm/contacts/{id}                  — update contact
  GET  /api/crm/deals                          — list deals
  POST /api/crm/deals                          — create deal
  GET  /api/crm/deals/{id}                     — get deal
  PATCH /api/crm/deals/{id}/stage              — update funnel stage
  GET  /api/crm/deals/{id}/activities          — list activities
  POST /api/crm/deals/{id}/activities          — create activity
  GET  /api/crm/insights                       — deal health insights (stale warnings + pipeline summary)
  GET  /api/crm/settings/stale-thresholds      — get stale threshold config per funnel stage
  PUT  /api/crm/settings/stale-thresholds      — update stale threshold config

Auth: Firebase ID token → email → SQL partners table → partner scope.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from starlette.requests import Request
from starlette.routing import Route

from zenos.domain.crm_models import Activity, AiInsight, Company, Contact, Deal
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.knowledge import SqlEntityRepository, SqlRelationshipRepository
from zenos.infrastructure.sql_common import get_pool
from zenos.interface.admin_api import (
    _cors_headers,
    _error_response,
    _handle_options,
    _json_response,
    _verify_firebase_token,
)
from zenos.interface.dashboard_api import _auth_and_scope

logger = logging.getLogger(__name__)


# ── Lazy-init repositories ─────────────────────────────────────────────

_crm_repos_ready = False
_crm_service = None
_crm_insights_service = None


async def _ensure_crm_service():
    global _crm_repos_ready, _crm_service, _crm_insights_service
    if _crm_repos_ready:
        return _crm_service

    from zenos.application.crm.crm_insights_service import CrmInsightsService
    from zenos.application.crm.crm_service import CrmService
    from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

    pool = await get_pool()
    crm_repo = CrmSqlRepository(pool)
    entity_repo = SqlEntityRepository(pool)
    relationship_repo = SqlRelationshipRepository(pool)
    _crm_service = CrmService(crm_repo, entity_repo, relationship_repo)
    _crm_insights_service = CrmInsightsService(crm_repo)
    _crm_repos_ready = True
    return _crm_service


async def _ensure_insights_service():
    await _ensure_crm_service()
    return _crm_insights_service


# ── Serialization helpers ──────────────────────────────────────────────


def _serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


def _company_to_dict(c: Company) -> dict:
    return _serialize({
        "id": c.id,
        "partnerId": c.partner_id,
        "name": c.name,
        "industry": c.industry,
        "sizeRange": c.size_range,
        "region": c.region,
        "notes": c.notes,
        "zenosEntityId": c.zenos_entity_id,
        "createdAt": c.created_at,
        "updatedAt": c.updated_at,
    })


def _contact_to_dict(c: Contact) -> dict:
    return _serialize({
        "id": c.id,
        "partnerId": c.partner_id,
        "companyId": c.company_id,
        "name": c.name,
        "title": c.title,
        "email": c.email,
        "phone": c.phone,
        "notes": c.notes,
        "zenosEntityId": c.zenos_entity_id,
        "createdAt": c.created_at,
        "updatedAt": c.updated_at,
    })


def _deal_to_dict(d: Deal) -> dict:
    return _serialize({
        "id": d.id,
        "partnerId": d.partner_id,
        "title": d.title,
        "companyId": d.company_id,
        "ownerPartnerId": d.owner_partner_id,
        "funnelStage": d.funnel_stage.value,
        "amountTwd": d.amount_twd,
        "dealType": d.deal_type.value if d.deal_type else None,
        "sourceType": d.source_type.value if d.source_type else None,
        "referrer": d.referrer,
        "expectedCloseDate": d.expected_close_date,
        "signedDate": d.signed_date,
        "scopeDescription": d.scope_description,
        "deliverables": d.deliverables,
        "notes": d.notes,
        "isClosedLost": d.is_closed_lost,
        "isOnHold": d.is_on_hold,
        "createdAt": d.created_at,
        "updatedAt": d.updated_at,
    })


def _activity_to_dict(a: Activity) -> dict:
    return _serialize({
        "id": a.id,
        "partnerId": a.partner_id,
        "dealId": a.deal_id,
        "activityType": a.activity_type.value,
        "activityAt": a.activity_at,
        "summary": a.summary,
        "recordedBy": a.recorded_by,
        "isSystem": a.is_system,
        "createdAt": a.created_at,
    })


def _ai_insight_to_dict(i: AiInsight) -> dict:
    return {
        "id": i.id,
        "partnerId": i.partner_id,
        "dealId": i.deal_id,
        "activityId": i.activity_id,
        "insightType": i.insight_type.value,
        "content": i.content,
        "metadata": i.metadata,
        "status": i.status.value,
        "createdAt": i.created_at.isoformat() if i.created_at else None,
    }


# ── Auth helper ────────────────────────────────────────────────────────


async def _crm_auth(request: Request) -> tuple[str | None, str | None]:
    """Returns (partner_id_for_data, actor_partner_id) or (None, None) on failure."""
    partner, effective_id = await _auth_and_scope(request)
    if not partner or not effective_id:
        return None, None
    # actor = partner's own id (for recorded_by)
    actor_id = partner["id"]
    return effective_id, actor_id


def _internal_error_response(request: Request, action: str, exc: Exception):
    logger.error("%s error: %s", action, exc, exc_info=True)
    return _error_response("INTERNAL_ERROR", str(exc), 500, request=request)


# ── Company endpoints ──────────────────────────────────────────────────


async def list_companies(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        svc = await _ensure_crm_service()
        companies = await svc.list_companies(effective_id)
        return _json_response(
            {"companies": [_company_to_dict(c) for c in companies]},
            request=request,
        )
    except Exception as exc:
        return _internal_error_response(request, "list_companies", exc)
    finally:
        current_partner_id.reset(token)


async def create_company(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        body = await request.json()
        if not body.get("name"):
            return _error_response("BAD_REQUEST", "name is required", 400, request=request)

        svc = await _ensure_crm_service()
        company = await svc.create_company(effective_id, body)
        return _json_response(_company_to_dict(company), status_code=201, request=request)
    except Exception as exc:
        return _internal_error_response(request, "create_company", exc)
    finally:
        current_partner_id.reset(token)


async def get_company(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        company_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        company = await svc.get_company(effective_id, company_id)
        if company is None:
            return _error_response("NOT_FOUND", "Company not found", 404, request=request)
        return _json_response(_company_to_dict(company), request=request)
    except Exception as exc:
        return _internal_error_response(request, "get_company", exc)
    finally:
        current_partner_id.reset(token)


async def update_company(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        company_id = request.path_params["id"]
        body = await request.json()
        svc = await _ensure_crm_service()
        company = await svc.update_company(effective_id, company_id, body)
        return _json_response(_company_to_dict(company), request=request)
    except ValueError as exc:
        return _error_response("NOT_FOUND", str(exc), 404, request=request)
    except Exception as exc:
        return _internal_error_response(request, "update_company", exc)
    finally:
        current_partner_id.reset(token)


async def list_company_contacts(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        company_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        contacts = await svc.list_contacts(effective_id, company_id=company_id)
        return _json_response(
            {"contacts": [_contact_to_dict(c) for c in contacts]},
            request=request,
        )
    except Exception as exc:
        return _internal_error_response(request, "list_company_contacts", exc)
    finally:
        current_partner_id.reset(token)


async def list_company_deals(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        company_id = request.path_params["id"]
        include_inactive = request.query_params.get("include_inactive", "").lower() == "true"
        svc = await _ensure_crm_service()
        all_deals = await svc.list_deals(effective_id, include_inactive=include_inactive)
        company_deals = [d for d in all_deals if d.company_id == company_id]
        return _json_response(
            {"deals": [_deal_to_dict(d) for d in company_deals]},
            request=request,
        )
    except Exception as exc:
        return _internal_error_response(request, "list_company_deals", exc)
    finally:
        current_partner_id.reset(token)


# ── Contact endpoints ──────────────────────────────────────────────────


async def create_contact(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        body = await request.json()
        if not body.get("name") or not body.get("company_id"):
            return _error_response(
                "BAD_REQUEST", "name and company_id are required", 400, request=request
            )
        svc = await _ensure_crm_service()
        contact = await svc.create_contact(effective_id, body)
        return _json_response(_contact_to_dict(contact), status_code=201, request=request)
    except Exception as exc:
        return _internal_error_response(request, "create_contact", exc)
    finally:
        current_partner_id.reset(token)


async def get_contact(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        contact_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        contact = await svc.get_contact(effective_id, contact_id)
        if contact is None:
            return _error_response("NOT_FOUND", "Contact not found", 404, request=request)
        return _json_response(_contact_to_dict(contact), request=request)
    except Exception as exc:
        return _internal_error_response(request, "get_contact", exc)
    finally:
        current_partner_id.reset(token)


async def update_contact(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        contact_id = request.path_params["id"]
        body = await request.json()
        svc = await _ensure_crm_service()
        contact = await svc.update_contact(effective_id, contact_id, body)
        return _json_response(_contact_to_dict(contact), request=request)
    except ValueError as exc:
        return _error_response("NOT_FOUND", str(exc), 404, request=request)
    except Exception as exc:
        return _internal_error_response(request, "update_contact", exc)
    finally:
        current_partner_id.reset(token)


# ── Deal endpoints ─────────────────────────────────────────────────────


async def list_deals(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        include_inactive = request.query_params.get("include_inactive", "").lower() == "true"
        svc = await _ensure_crm_service()
        deals = await svc.list_deals(effective_id, include_inactive=include_inactive)
        return _json_response(
            {"deals": [_deal_to_dict(d) for d in deals]},
            request=request,
        )
    except Exception as exc:
        return _internal_error_response(request, "list_deals", exc)
    finally:
        current_partner_id.reset(token)


async def create_deal(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        body = await request.json()
        if not body.get("title") or not body.get("company_id"):
            return _error_response(
                "BAD_REQUEST", "title and company_id are required", 400, request=request
            )
        # Inject actor as default owner
        if not body.get("owner_partner_id"):
            body["owner_partner_id"] = actor_id
        svc = await _ensure_crm_service()
        deal = await svc.create_deal(effective_id, body)
        return _json_response(_deal_to_dict(deal), status_code=201, request=request)
    except Exception as exc:
        return _internal_error_response(request, "create_deal", exc)
    finally:
        current_partner_id.reset(token)


async def get_deal(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        deal_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        deal = await svc.get_deal(effective_id, deal_id)
        if deal is None:
            return _error_response("NOT_FOUND", "Deal not found", 404, request=request)
        return _json_response(_deal_to_dict(deal), request=request)
    except Exception as exc:
        return _internal_error_response(request, "get_deal", exc)
    finally:
        current_partner_id.reset(token)


async def patch_deal_stage(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        deal_id = request.path_params["id"]
        body = await request.json()
        new_stage = body.get("stage")
        if not new_stage:
            return _error_response("BAD_REQUEST", "stage is required", 400, request=request)

        svc = await _ensure_crm_service()
        deal = await svc.update_deal_stage(
            effective_id, deal_id, new_stage, actor_id or effective_id
        )
        return _json_response(_deal_to_dict(deal), request=request)
    except ValueError as exc:
        return _error_response("NOT_FOUND", str(exc), 404, request=request)
    except Exception as exc:
        return _internal_error_response(request, "patch_deal_stage", exc)
    finally:
        current_partner_id.reset(token)


# ── Activity endpoints ─────────────────────────────────────────────────


async def list_deal_activities(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        deal_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        activities = await svc.list_activities(effective_id, deal_id)
        return _json_response(
            {"activities": [_activity_to_dict(a) for a in activities]},
            request=request,
        )
    except Exception as exc:
        return _internal_error_response(request, "list_deal_activities", exc)
    finally:
        current_partner_id.reset(token)


async def create_deal_activity(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        deal_id = request.path_params["id"]
        body = await request.json()
        if not body.get("summary"):
            return _error_response("BAD_REQUEST", "summary is required", 400, request=request)
        if not body.get("recorded_by"):
            body["recorded_by"] = actor_id or effective_id

        svc = await _ensure_crm_service()
        activity = await svc.create_activity(effective_id, deal_id, body)
        return _json_response(_activity_to_dict(activity), status_code=201, request=request)
    except Exception as exc:
        return _internal_error_response(request, "create_deal_activity", exc)
    finally:
        current_partner_id.reset(token)


# ── AI Insights endpoints ──────────────────────────────────────────────


async def get_deal_ai_entries(request: Request):
    """GET /api/crm/deals/{id}/ai-entries — list briefings, debriefs, and commitments."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        deal_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        entries = await svc.get_deal_ai_entries(effective_id, deal_id)
        return _json_response(
            {
                "briefings": [_ai_insight_to_dict(i) for i in entries["briefings"]],
                "debriefs": [_ai_insight_to_dict(i) for i in entries["debriefs"]],
                "commitments": [_ai_insight_to_dict(i) for i in entries["commitments"]],
            },
            request=request,
        )
    except Exception as exc:
        return _internal_error_response(request, "get_deal_ai_entries", exc)
    finally:
        current_partner_id.reset(token)


async def create_deal_ai_insight(request: Request):
    """POST /api/crm/deals/{id}/ai-insights — create a new AI insight for a deal."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        deal_id = request.path_params["id"]
        body = await request.json()
        if not body.get("insight_type"):
            return _error_response("BAD_REQUEST", "insight_type is required", 400, request=request)
        body["deal_id"] = deal_id

        svc = await _ensure_crm_service()
        insight = await svc.create_ai_insight(effective_id, body)
        return _json_response(_ai_insight_to_dict(insight), status_code=201, request=request)
    except ValueError as exc:
        return _error_response("BAD_REQUEST", str(exc), 400, request=request)
    except Exception as exc:
        return _internal_error_response(request, "create_deal_ai_insight", exc)
    finally:
        current_partner_id.reset(token)


async def patch_commitment_status(request: Request):
    """PATCH /api/crm/commitments/{id} — update status of a commitment insight."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        insight_id = request.path_params["id"]
        body = await request.json()
        status = body.get("status")
        if not status:
            return _error_response("BAD_REQUEST", "status is required", 400, request=request)

        svc = await _ensure_crm_service()
        insight = await svc.update_commitment_status(effective_id, insight_id, status)
        if insight is None:
            return _error_response("NOT_FOUND", "Commitment not found", 404, request=request)
        return _json_response(_ai_insight_to_dict(insight), request=request)
    except ValueError as exc:
        return _error_response("BAD_REQUEST", str(exc), 400, request=request)
    except Exception as exc:
        return _internal_error_response(request, "patch_commitment_status", exc)
    finally:
        current_partner_id.reset(token)


async def patch_briefing(request: Request):
    """PATCH /api/crm/briefings/{id} — update a saved briefing snapshot."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        insight_id = request.path_params["id"]
        body = await request.json()
        if "content" not in body and "metadata" not in body:
            return _error_response(
                "BAD_REQUEST",
                "content or metadata is required",
                400,
                request=request,
            )

        svc = await _ensure_crm_service()
        insight = await svc.update_briefing(effective_id, insight_id, body)
        if insight is None:
            return _error_response("NOT_FOUND", "Briefing not found", 404, request=request)
        return _json_response(_ai_insight_to_dict(insight), request=request)
    except ValueError as exc:
        return _error_response("BAD_REQUEST", str(exc), 400, request=request)
    except Exception as exc:
        return _internal_error_response(request, "patch_briefing", exc)
    finally:
        current_partner_id.reset(token)


async def delete_briefing(request: Request):
    """DELETE /api/crm/briefings/{id} — delete a saved briefing snapshot."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        insight_id = request.path_params["id"]
        svc = await _ensure_crm_service()
        deleted = await svc.delete_briefing(effective_id, insight_id)
        if not deleted:
            return _error_response("NOT_FOUND", "Briefing not found", 404, request=request)
        from starlette.responses import Response
        return Response(status_code=204, headers=dict(_cors_headers(request)))
    except ValueError as exc:
        return _error_response("BAD_REQUEST", str(exc), 400, request=request)
    except Exception as exc:
        return _internal_error_response(request, "delete_briefing", exc)
    finally:
        current_partner_id.reset(token)


# ── CRM Insights endpoint (deal health) ───────────────────────────────


async def get_insights(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        svc = await _ensure_insights_service()
        result = await svc.compute_insights(effective_id)
        return _json_response(result, request=request)
    except Exception as exc:
        return _internal_error_response(request, "get_insights", exc)
    finally:
        current_partner_id.reset(token)


# ── Stale-thresholds settings endpoints ───────────────────────────────


async def get_stale_thresholds(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        svc = await _ensure_insights_service()
        thresholds = await svc.get_stale_thresholds(effective_id)
        return _json_response(thresholds, request=request)
    except Exception as exc:
        return _internal_error_response(request, "get_stale_thresholds", exc)
    finally:
        current_partner_id.reset(token)


async def put_stale_thresholds(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)

    effective_id, actor_id = await _crm_auth(request)
    if not effective_id:
        return _error_response("UNAUTHORIZED", "Invalid token", 401, request=request)

    token = current_partner_id.set(effective_id)
    try:
        body = await request.json()
        if not isinstance(body, dict):
            return _error_response("BAD_REQUEST", "body must be a JSON object", 400, request=request)

        # Validate: all values must be positive integers
        for stage, days in body.items():
            if not isinstance(days, int) or days <= 0:
                return _error_response(
                    "BAD_REQUEST",
                    f"threshold for '{stage}' must be a positive integer",
                    400,
                    request=request,
                )

        svc = await _ensure_insights_service()
        await svc.save_stale_thresholds(effective_id, body)
        thresholds = await svc.get_stale_thresholds(effective_id)
        return _json_response(thresholds, request=request)
    except Exception as exc:
        return _internal_error_response(request, "put_stale_thresholds", exc)
    finally:
        current_partner_id.reset(token)


async def stale_thresholds_handler(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "PUT":
        return await put_stale_thresholds(request)
    return await get_stale_thresholds(request)


# ── Combined handlers (dispatch on method) ────────────────────────────


async def companies_collection(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "POST":
        return await create_company(request)
    return await list_companies(request)


async def company_detail(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "PUT":
        return await update_company(request)
    return await get_company(request)


async def contacts_collection(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    return await create_contact(request)


async def contact_detail(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "PUT":
        return await update_contact(request)
    return await get_contact(request)


async def deals_collection(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "POST":
        return await create_deal(request)
    return await list_deals(request)


async def deal_activities_collection(request: Request):
    if request.method == "OPTIONS":
        return _handle_options(request)
    if request.method == "POST":
        return await create_deal_activity(request)
    return await list_deal_activities(request)


# ── Route definitions ──────────────────────────────────────────────────

crm_dashboard_routes = [
    Route("/api/crm/companies",                   companies_collection,       methods=["GET", "POST", "OPTIONS"]),
    Route("/api/crm/companies/{id}",              company_detail,             methods=["GET", "PUT", "OPTIONS"]),
    Route("/api/crm/companies/{id}/contacts",     list_company_contacts,      methods=["GET", "OPTIONS"]),
    Route("/api/crm/companies/{id}/deals",        list_company_deals,         methods=["GET", "OPTIONS"]),
    Route("/api/crm/contacts",                    contacts_collection,        methods=["POST", "OPTIONS"]),
    Route("/api/crm/contacts/{id}",               contact_detail,             methods=["GET", "PUT", "OPTIONS"]),
    Route("/api/crm/deals",                       deals_collection,           methods=["GET", "POST", "OPTIONS"]),
    Route("/api/crm/deals/{id}",                  get_deal,                   methods=["GET", "OPTIONS"]),
    Route("/api/crm/deals/{id}/stage",            patch_deal_stage,           methods=["PATCH", "OPTIONS"]),
    Route("/api/crm/deals/{id}/activities",       deal_activities_collection, methods=["GET", "POST", "OPTIONS"]),
    Route("/api/crm/deals/{id}/ai-entries",       get_deal_ai_entries,        methods=["GET", "OPTIONS"]),
    Route("/api/crm/deals/{id}/ai-insights",      create_deal_ai_insight,     methods=["POST", "OPTIONS"]),
    Route("/api/crm/briefings/{id}",              patch_briefing,             methods=["PATCH", "OPTIONS"]),
    Route("/api/crm/briefings/{id}",              delete_briefing,            methods=["DELETE", "OPTIONS"]),
    Route("/api/crm/commitments/{id}",            patch_commitment_status,    methods=["PATCH", "OPTIONS"]),
    Route("/api/crm/insights",                    get_insights,               methods=["GET", "OPTIONS"]),
    Route("/api/crm/settings/stale-thresholds",   stale_thresholds_handler,   methods=["GET", "PUT", "OPTIONS"]),
]
