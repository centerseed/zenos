"""SearchService — Application layer for entity search with mode support.

Responsibilities:
- keyword mode: current substring search, backward compat, no embed API call
- semantic mode: embed query → pgvector cosine sort → return with score
- hybrid mode (default): 0.7 * semantic + 0.3 * keyword_boolean, score_breakdown attached
- empty query fallback: hybrid/semantic + empty query → degrade to keyword
- API fail fallback: embed_query returns None → fallback to keyword + WARNING

Design constraints (ADR-041 S05):
- SearchService is injected with entity_repo and embedding_service via DI
- All fallback logic is in this service layer; interface/mcp/search.py has no branching
- keyword_matches is a pure function — independently testable
- score_breakdown is always returned (OQ-2 Architect decision: default return)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

HYBRID_SEMANTIC_WEIGHT = 0.7
HYBRID_KEYWORD_WEIGHT = 0.3

VALID_MODES = {"keyword", "semantic", "hybrid"}


def keyword_matches(query: str, entity: Any) -> int:
    """Return 1 if query (substring) appears in entity name/summary/tags; else 0.

    Pure function — no side effects, independently testable.

    Tags structure: {what: list[str], why: str, how: str, who: list[str]}
    Applies OQ-4 Architect ruling: flatten what/who, include why/how directly.

    Args:
        query: The search query string.
        entity: An Entity domain object with .name, .summary, .tags attributes.

    Returns:
        1 if query substring found in any field, 0 otherwise.
    """
    if not query:
        return 0

    q = query.lower()
    pool: list[str] = []

    def _push(value: Any) -> None:
        """Coerce any tag value (str / list / nested / None) to flat list[str] in pool."""
        if value is None:
            return
        if isinstance(value, str):
            if value:
                pool.append(value)
            return
        if isinstance(value, (list, tuple, set)):
            for v in value:
                _push(v)
            return
        pool.append(str(value))

    _push(entity.name)
    _push(entity.summary)

    tags = entity.tags
    if tags:
        _push(tags.what)
        _push(tags.who)
        _push(tags.why)
        _push(tags.how)

    return 1 if any(q in s.lower() for s in pool if isinstance(s, str) and s) else 0


class SearchService:
    """Application service for entity search across keyword / semantic / hybrid modes."""

    def __init__(self, entity_repo: Any, embedding_service: Any) -> None:
        self._repo = entity_repo
        self._embedding_service = embedding_service

    async def search_entities(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        limit: int = 200,
        filters: dict | None = None,
    ) -> list[dict]:
        """Search entities and return serialisable result dicts with score + score_breakdown.

        Args:
            query:   Search query string. Empty string = list-all in keyword mode.
            mode:    One of "keyword", "semantic", "hybrid". Default "hybrid".
            limit:   Maximum results to return.
            filters: Optional filters forwarded to repo (visibility, etc.).

        Returns:
            List of dicts. Each dict contains entity fields (from list_all or
            search_by_vector) plus:
              - score: float
              - score_breakdown: {"semantic": float | None, "keyword": float | None}

        Fallback rules:
            - empty query + hybrid/semantic → degrade to keyword, score_breakdown.semantic = null
            - embed_query returns None (API fail) → fallback to keyword + WARNING
        """
        if mode not in VALID_MODES:
            logger.warning(
                "search_entities: unknown mode %r, falling back to 'keyword'", mode
            )
            mode = "keyword"

        # Rule: empty query + hybrid/semantic → degrade to keyword
        effective_query = query.strip()
        if not effective_query and mode in ("hybrid", "semantic"):
            return await self._keyword_search(query, limit=limit, filters=filters, semantic_null=True)

        if mode == "keyword":
            return await self._keyword_search(query, limit=limit, filters=filters, semantic_null=False)

        if mode == "semantic":
            return await self._semantic_search(query, limit=limit, filters=filters)

        # hybrid (default)
        return await self._hybrid_search(query, limit=limit, filters=filters)

    # ------------------------------------------------------------------
    # Private mode implementations
    # ------------------------------------------------------------------

    async def _keyword_search(
        self,
        query: str,
        *,
        limit: int,
        filters: dict | None,
        semantic_null: bool,
    ) -> list[dict]:
        """Keyword substring search across name/summary/tags.

        Args:
            semantic_null: If True, score_breakdown.semantic = None (empty-query degrade path).
                           If False, normal keyword mode where semantic is not applicable.
        """
        all_entities = await self._repo.list_all()
        q = query.strip()

        if q:
            matched = [e for e in all_entities if keyword_matches(q, e)]
        else:
            matched = list(all_entities)

        results = []
        for entity in matched[:limit]:
            kw_score = keyword_matches(q, entity) if q else 0.0
            results.append(
                _entity_to_result(
                    entity,
                    score=float(kw_score),
                    score_breakdown={
                        "semantic": None,
                        "keyword": float(kw_score) if not semantic_null else None,
                    },
                )
            )
        return results

    async def _semantic_search(
        self,
        query: str,
        *,
        limit: int,
        filters: dict | None,
    ) -> list[dict]:
        """Semantic (vector) search via pgvector cosine.

        Falls back to keyword search with WARNING if embed_query returns None.
        """
        query_vec = await self._embedding_service.embed_query(query)
        if query_vec is None:
            logger.warning(
                "search_entities: embed_query returned None for query=%r, "
                "falling back to keyword mode",
                query,
            )
            return await self._keyword_search(query, limit=limit, filters=filters, semantic_null=False)

        pairs = await self._repo.search_by_vector(query_vec, limit=limit, filters=filters)
        results = []
        for entity, cosine_score in pairs:
            results.append(
                _entity_to_result(
                    entity,
                    score=cosine_score,
                    score_breakdown={"semantic": cosine_score, "keyword": None},
                )
            )
        return results

    async def _hybrid_search(
        self,
        query: str,
        *,
        limit: int,
        filters: dict | None,
    ) -> list[dict]:
        """Hybrid search: 0.7 * semantic_cosine + 0.3 * keyword_boolean.

        Falls back to keyword search with WARNING if embed_query returns None.
        """
        query_vec = await self._embedding_service.embed_query(query)
        if query_vec is None:
            logger.warning(
                "search_entities: embed_query returned None for query=%r, "
                "falling back to keyword mode (hybrid → keyword fallback)",
                query,
            )
            return await self._keyword_search(query, limit=limit, filters=filters, semantic_null=False)

        # Use a larger internal limit so keyword re-ranking can surface keyword-only matches
        fetch_limit = max(limit * 3, 200)
        pairs = await self._repo.search_by_vector(query_vec, limit=fetch_limit, filters=filters)

        q = query.strip()
        scored: list[tuple[Any, float, float, float]] = []  # (entity, final, semantic, keyword)
        seen_ids: set[str] = set()

        for entity, cosine_score in pairs:
            kw = float(keyword_matches(q, entity))
            final = HYBRID_SEMANTIC_WEIGHT * cosine_score + HYBRID_KEYWORD_WEIGHT * kw
            scored.append((entity, final, cosine_score, kw))
            if entity.id:
                seen_ids.add(entity.id)

        # Also include keyword-only matches that may be below pgvector threshold
        # (entities without embedding won't appear in search_by_vector)
        all_entities = await self._repo.list_all()
        for entity in all_entities:
            if entity.id in seen_ids:
                continue
            kw = float(keyword_matches(q, entity))
            if kw > 0:
                final = HYBRID_KEYWORD_WEIGHT * kw  # semantic = 0 for unembedded
                scored.append((entity, final, 0.0, kw))

        # Sort by final score descending
        scored.sort(key=lambda t: t[1], reverse=True)

        results = []
        for entity, final, sem, kw in scored[:limit]:
            results.append(
                _entity_to_result(
                    entity,
                    score=final,
                    score_breakdown={"semantic": sem, "keyword": kw},
                )
            )
        return results


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _entity_to_result(entity: Any, score: float, score_breakdown: dict) -> dict:
    """Convert an Entity domain object to a serialisable result dict.

    Note: This produces a minimal dict with the key fields needed by the MCP
    search path. The interface layer (search.py) will call _serialize on the
    Entity before passing it here in the wired path; in the SearchService we
    store the Entity directly and let search.py do the full serialisation.

    We keep entity as a raw domain object here so the interface layer can
    apply _serialize and build_search_result on top. Instead, we store a
    reference and add score metadata.
    """
    return {
        "_entity": entity,
        "score": round(score, 6),
        "score_breakdown": {
            "semantic": round(score_breakdown["semantic"], 6) if score_breakdown.get("semantic") is not None else None,
            "keyword": round(score_breakdown["keyword"], 6) if score_breakdown.get("keyword") is not None else None,
        },
    }
