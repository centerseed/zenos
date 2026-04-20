"""ZenOS MCP Server — interface/mcp package.

This package replaces the monolithic interface/tools.py.
Entry point: python -m zenos.interface.mcp

Architecture:
  __init__.py      — FastMCP app instance, middleware, singletons, _ensure_* init
  _auth.py         — partner context ContextVar, ApiKeyMiddleware, SseApiKeyPropagator
  _common.py       — _serialize, _unified_response, _new_id, _parse_entity_level, etc.
  _visibility.py   — _is_entity_visible, _is_task_visible, etc.
  _audit.py        — _audit_log, _schedule_tool_event, etc.
  search.py        — search tool
  get.py           — get tool
  write.py         — write tool
  confirm.py       — confirm tool
  task.py          — task + _task_handler tool
  analyze.py       — analyze tool
  journal.py       — journal_write, journal_read tools
  recent_updates.py — recent_updates tool
  governance.py    — governance_guide, find_gaps, common_neighbors tools
  source.py        — read_source, batch_update_sources tools
  attachment.py    — upload_attachment tool
  setup.py         — setup tool
  suggest_policy.py — suggest_policy tool
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

try:
    from fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - test fallback when fastmcp is absent
    class FastMCP:  # type: ignore[override]
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def tool(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

load_dotenv()

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# MCP server instance
# ──────────────────────────────────────────────

mcp = FastMCP("ZenOS Ontology")

# ──────────────────────────────────────────────
# Dependency injection — repositories & services
# ──────────────────────────────────────────────

from zenos.application.knowledge.governance_ai import GovernanceAI
from zenos.application.knowledge.governance_service import GovernanceService
from zenos.application.knowledge.ontology_service import OntologyService
from zenos.application.knowledge.source_service import SourceService
from zenos.application.knowledge.embedding_service import EmbeddingService
from zenos.application.knowledge.search_service import SearchService as _SearchService
from zenos.application.action.plan_service import PlanService
from zenos.application.action.task_service import TaskService
from zenos.infrastructure.llm_client import create_llm_client
from zenos.infrastructure.unit_of_work import UnitOfWork
from zenos.infrastructure.action import SqlPlanRepository, SqlTaskRepository
from zenos.infrastructure.agent import SqlToolEventRepository, SqlUsageLogRepository, SqlWorkJournalRepository
from zenos.infrastructure.knowledge import SqlBlindspotRepository, SqlDocumentRepository, SqlEntityEntryRepository, SqlEntityRepository, SqlProtocolRepository, SqlRelationshipRepository
from zenos.infrastructure.sql_common import get_pool
from zenos.infrastructure.github_adapter import GitHubAdapter

# Repositories initialised lazily with the shared asyncpg pool.
_repos_ready: bool = False
entity_repo: SqlEntityRepository | None = None
relationship_repo: SqlRelationshipRepository | None = None
document_repo: SqlDocumentRepository | None = None
protocol_repo: SqlProtocolRepository | None = None
blindspot_repo: SqlBlindspotRepository | None = None
task_repo: SqlTaskRepository | None = None
entry_repo: SqlEntityEntryRepository | None = None
plan_repo: SqlPlanRepository | None = None


async def _ensure_repos() -> None:
    """Lazily initialise all SQL repositories on first tool invocation."""
    global _repos_ready, entity_repo, relationship_repo, document_repo
    global protocol_repo, blindspot_repo, task_repo, entry_repo, plan_repo
    if _repos_ready:
        return
    pool = await get_pool()
    entity_repo = SqlEntityRepository(pool)
    relationship_repo = SqlRelationshipRepository(pool)
    document_repo = SqlDocumentRepository(pool)
    protocol_repo = SqlProtocolRepository(pool)
    blindspot_repo = SqlBlindspotRepository(pool)
    task_repo = SqlTaskRepository(pool)
    entry_repo = SqlEntityEntryRepository(pool)
    plan_repo = SqlPlanRepository(pool)
    _repos_ready = True


source_adapter = GitHubAdapter()

# GovernanceAI: LLM-based auto-inference (optional, depends on env config)
_governance_ai: GovernanceAI | None = None
_usage_log_repo: SqlUsageLogRepository | None = None
_tool_event_repo: SqlToolEventRepository | None = None
_journal_repo: SqlWorkJournalRepository | None = None


async def _ensure_governance_ai() -> None:
    """Wire GovernanceAI with SqlUsageLogRepository after pool is available."""
    global _governance_ai, _usage_log_repo, _tool_event_repo
    if _governance_ai is not None:
        return
    try:
        pool = await get_pool()
        _usage_log_repo = SqlUsageLogRepository(pool)
        _tool_event_repo = SqlToolEventRepository(pool)
        llm_client = create_llm_client()
        from zenos.infrastructure.context import current_partner_id as _ctx_partner_id
        _governance_ai = GovernanceAI(
            llm_client,
            usage_log_repo=_usage_log_repo,
            get_partner_id=_ctx_partner_id.get,
        )
        logger.info("GovernanceAI initialized with model: %s", llm_client.model)
    except Exception:
        logger.warning("GovernanceAI disabled: LLM client initialization failed", exc_info=True)


async def _ensure_journal_repo() -> None:
    """Lazily initialise SqlWorkJournalRepository after pool is available."""
    global _journal_repo
    if _journal_repo is not None:
        return
    pool = await get_pool()
    _journal_repo = SqlWorkJournalRepository(pool)


async def _compress_journal(partner_id: str) -> None:
    """Compress old non-summary journal entries into a single summary row.

    Keeps the most recent 9 originals intact; compresses any older originals
    via LLM into a single is_summary=TRUE entry then deletes the originals.
    On any failure, logs a warning and returns without raising.
    """
    from datetime import datetime, timezone

    try:
        await _ensure_journal_repo()
        assert _journal_repo is not None
        async with _journal_repo._pool.acquire() as _conn:
            total_originals: int = await _conn.fetchval(
                "SELECT COUNT(*) FROM zenos.work_journal"
                " WHERE partner_id = $1 AND is_summary = FALSE",
                partner_id,
            )
        to_compress = total_originals - 9
        if to_compress <= 0:
            return
        entries = await _journal_repo.list_oldest_originals(
            partner_id=partner_id, limit=to_compress
        )
        if not entries:
            return

        formatted = "\n\n".join(
            f"[{e['created_at']}] project={e['project']} flow={e['flow_type']}\n{e['summary']}"
            for e in entries
        )
        prompt = (
            f"以下是 {len(entries)} 則工作日誌，請壓縮成一則不超過 300 字的摘要。\n"
            "保留：完成的功能、遺留問題、重要決策、涉及的專案與技術。\n"
            "直接輸出摘要，無需前言。\n\n"
            f"{formatted}"
        )

        from pydantic import BaseModel as _BaseModel

        class _SummaryOut(_BaseModel):
            summary: str

        llm = create_llm_client()
        result = llm.chat_structured(
            messages=[{"role": "user", "content": prompt}],
            response_schema=_SummaryOut,
        )

        as_of = datetime.now(tz=timezone.utc)

        # Collect metadata from compressed entries
        projects = list({e["project"] for e in entries if e["project"]})
        flow_types = list({e["flow_type"] for e in entries if e["flow_type"]})
        all_tags: list[str] = []
        for e in entries:
            all_tags.extend(e.get("tags") or [])
        unique_tags = list(dict.fromkeys(all_tags))

        ids = [str(e["id"]) for e in entries]
        await _journal_repo.create_summary(
            partner_id=partner_id,
            summary=result.summary,
            project=projects[0] if len(projects) == 1 else None,
            flow_type=flow_types[0] if len(flow_types) == 1 else None,
            tags=unique_tags,
            as_of=as_of,
        )
        await _journal_repo.delete_by_ids(partner_id=partner_id, ids=ids)
    except Exception:
        logger.warning("_compress_journal failed, skipping compression", exc_info=True)


# Services wired lazily after _ensure_repos() runs.
ontology_service: OntologyService | None = None
governance_service: GovernanceService | None = None
source_service: SourceService | None = None
task_service: TaskService | None = None
plan_service: PlanService | None = None
embedding_service: EmbeddingService | None = None
search_service: _SearchService | None = None

# Keep a strong reference to background embed tasks to prevent GC-initiated cancellation.
_background_tasks: set = set()


def _schedule_embed(eid: str) -> None:
    """Fire-and-forget async embed hook.

    Schedules compute_and_store(eid) as a background asyncio task.
    Failures are logged at WARNING and never bubble to the caller.
    Uses a strong-reference set to prevent the task from being GC'd mid-flight.
    """
    import asyncio

    if embedding_service is None:
        return

    async def _run() -> None:
        try:
            await embedding_service.compute_and_store(eid)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning(
                "embed failed in background",
                extra={"entity_id": eid, "error": str(exc)},
            )

    try:
        task = asyncio.create_task(_run())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        # No running event loop in this context — skip silently.
        logger.debug("_schedule_embed: no running event loop, skipping embed for %s", eid)


async def _ensure_services() -> None:
    """Wire services once repos are ready."""
    global ontology_service, governance_service, source_service, task_service, plan_service, embedding_service, search_service
    await _ensure_repos()
    await _ensure_governance_ai()
    if embedding_service is None:
        _llm_client = create_llm_client()
        embedding_service = EmbeddingService(entity_repo=entity_repo, llm_client=_llm_client)
    if search_service is None:
        search_service = _SearchService(entity_repo=entity_repo, embedding_service=embedding_service)
    if ontology_service is None:
        ontology_service = OntologyService(
            entity_repo=entity_repo,
            relationship_repo=relationship_repo,
            document_repo=document_repo,
            protocol_repo=protocol_repo,
            blindspot_repo=blindspot_repo,
            governance_ai=_governance_ai,
            source_adapter=source_adapter,
            embedding_service=embedding_service,
        )
    if governance_service is None:
        governance_service = GovernanceService(
            entity_repo=entity_repo,
            relationship_repo=relationship_repo,
            protocol_repo=protocol_repo,
            blindspot_repo=blindspot_repo,
            task_repo=task_repo,
            usage_log_repo=_usage_log_repo,
            governance_ai=_governance_ai,
        )
    if source_service is None:
        source_service = SourceService(
            entity_repo=entity_repo,
            source_adapter=source_adapter,
        )
    if plan_service is None:
        plan_service = PlanService(
            plan_repo=plan_repo,
            task_repo=task_repo,
        )
    if task_service is None:
        task_service = TaskService(
            task_repo=task_repo,
            entity_repo=entity_repo,
            blindspot_repo=blindspot_repo,
            governance_ai=_governance_ai,
            relationship_repo=relationship_repo,
            uow_factory=lambda: UnitOfWork(task_repo._pool),
            plan_repo=plan_repo,
        )


# ──────────────────────────────────────────────
# Tool registration
# All tool functions are imported here and registered with @mcp.tool().
# Tool modules use lazy function-level imports from this __init__.py to
# avoid circular import at module load time.
# ──────────────────────────────────────────────

from zenos.interface.mcp.search import search as _search_fn
from zenos.interface.mcp.get import get as _get_fn
from zenos.interface.mcp.write import write as _write_fn
from zenos.interface.mcp.confirm import confirm as _confirm_fn
from zenos.interface.mcp.task import task as _task_fn, _task_handler
from zenos.interface.mcp.plan import plan as _plan_fn, _plan_handler
from zenos.interface.mcp.analyze import analyze as _analyze_fn
from zenos.interface.mcp.journal import journal_write as _journal_write_fn, journal_read as _journal_read_fn
from zenos.interface.mcp.recent_updates import recent_updates as _recent_updates_fn
from zenos.interface.mcp.governance import (
    governance_guide as _governance_guide_fn,
    find_gaps as _find_gaps_fn,
    common_neighbors as _common_neighbors_fn,
)
from zenos.interface.mcp.source import read_source as _read_source_fn, batch_update_sources as _batch_update_sources_fn
from zenos.interface.mcp.attachment import upload_attachment as _upload_attachment_fn
from zenos.interface.mcp.setup import setup as _setup_fn
from zenos.interface.mcp.suggest_policy import suggest_policy as _suggest_policy_fn
from zenos.interface.mcp.workspace import list_workspaces as _list_workspaces_fn
from zenos.interface.mcp._scope import require_scope, TOOL_SCOPE_MAP

# Register tools with the MCP instance — each handler is wrapped with require_scope
# to enforce JWT scope constraints (API key path always has full scopes).
search = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_search_fn))
get = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_get_fn))
write = mcp.tool(tags={"write"}, annotations={"idempotentHint": True})(require_scope("write")(_write_fn))
confirm = mcp.tool(tags={"write"})(require_scope("write")(_confirm_fn))
task = mcp.tool(tags={"write"})(require_scope("task")(_task_fn))
plan = mcp.tool(tags={"write"})(require_scope("task")(_plan_fn))
analyze = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_analyze_fn))
journal_write = mcp.tool(tags={"write"})(require_scope("write")(_journal_write_fn))
journal_read = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_journal_read_fn))
recent_updates = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_recent_updates_fn))
governance_guide = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_governance_guide_fn))
find_gaps = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_find_gaps_fn))
common_neighbors = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_common_neighbors_fn))
read_source = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_read_source_fn))
batch_update_sources = mcp.tool(tags={"write"}, annotations={"idempotentHint": True})(require_scope("write")(_batch_update_sources_fn))
upload_attachment = mcp.tool(tags={"write"})(require_scope("write")(_upload_attachment_fn))
setup = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_setup_fn))
suggest_policy = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_suggest_policy_fn))
list_workspaces = mcp.tool(tags={"read"}, annotations={"readOnlyHint": True})(require_scope("read")(_list_workspaces_fn))

# Re-export auth middleware for use in __main__.py and tests
from zenos.interface.mcp._auth import (
    ApiKeyMiddleware,
    SseApiKeyPropagator,
    _current_partner,
    _apply_workspace_override,
)

# Re-export helpers used by tests
from zenos.interface.mcp._common import (
    _serialize,
    _unified_response,
    _parse_entity_level,
)
from zenos.interface.mcp._visibility import (
    _is_task_visible,
    _is_blindspot_visible,
    _is_protocol_visible,
)
from zenos.interface.mcp._audit import _schedule_audit_sql_write
from zenos.interface.mcp.task import (
    _validate_attachments,
    _cleanup_removed_attachments,
)
from zenos.interface.mcp.plan import _plan_handler

__all__ = [
    "mcp",
    "ApiKeyMiddleware",
    "SseApiKeyPropagator",
    "_ensure_services",
    "_ensure_repos",
    "_ensure_governance_ai",
    "_ensure_journal_repo",
    "_compress_journal",
    "_task_handler",
    "_plan_handler",
    # singletons
    "entity_repo",
    "relationship_repo",
    "document_repo",
    "protocol_repo",
    "blindspot_repo",
    "task_repo",
    "entry_repo",
    "plan_repo",
    "ontology_service",
    "governance_service",
    "source_service",
    "task_service",
    "plan_service",
    "search_service",
    "_governance_ai",
    "_tool_event_repo",
    "_journal_repo",
    # registered tools (wrapped)
    "search",
    "get",
    "write",
    "confirm",
    "task",
    "plan",
    "analyze",
    "journal_write",
    "journal_read",
    "recent_updates",
    "governance_guide",
    "find_gaps",
    "common_neighbors",
    "read_source",
    "batch_update_sources",
    "upload_attachment",
    "setup",
    "suggest_policy",
]
