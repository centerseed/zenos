"""In-memory keyword search across ontology objects — zero external deps."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .knowledge import Document, Entity, Protocol, Tags


@dataclass
class SearchResult:
    """A single search hit."""
    type: str       # "entity" | "document" | "protocol"
    id: str | None
    name: str
    summary: str
    score: float    # higher = better match
    ancestors: list[dict] | None = None  # filled by application layer for entity results


_CJK_RANGE = re.compile(r"[\u4e00-\u9fff]")


def _stringify_search_part(value: object) -> list[str]:
    """Flatten arbitrary metadata into searchable strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.extend(_stringify_search_part(key))
            parts.extend(_stringify_search_part(item))
        return parts
    if isinstance(value, (list, tuple, set, frozenset)):
        parts: list[str] = []
        for item in value:
            parts.extend(_stringify_search_part(item))
        return parts
    return [str(value)]


def _cjk_bigrams(token: str) -> list[str]:
    """Generate bigrams from a CJK token.

    E.g. "語意治理" → ["語意", "意治", "治理"]
    """
    return [token[i : i + 2] for i in range(len(token) - 1)]


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens; CJK tokens also produce bigrams."""
    raw_tokens = [t for t in re.split(r"[\s\-_/.,;:!?()（）。，、；：！？「」『』\[\]{}]+", text.lower()) if t]
    result: list[str] = []
    for token in raw_tokens:
        result.append(token)
        if _CJK_RANGE.search(token) and len(token) >= 2:
            result.extend(_cjk_bigrams(token))
    return result


def _collect_searchable_text_entity(entity: Entity) -> str:
    """Collect all searchable text from an entity."""
    parts = _stringify_search_part([entity.name, entity.summary, entity.type])
    if isinstance(entity.tags, Tags):
        parts.extend(_stringify_search_part(entity.tags.what))
        parts.extend(_stringify_search_part(entity.tags.why))
        parts.extend(_stringify_search_part(entity.tags.how))
        parts.extend(_stringify_search_part(entity.tags.who))
    # ADR-022: Include per-source doc_type so doc_type searches hit bundle sources
    if entity.sources:
        for src in entity.sources:
            if isinstance(src, dict):
                parts.extend(_stringify_search_part(src.get("doc_type")))
                parts.extend(_stringify_search_part(src.get("label")))
                parts.extend(_stringify_search_part(src.get("uri")))
    return " ".join(parts)


def _collect_searchable_text_document(doc: Document) -> str:
    """Collect all searchable text from a document."""
    parts = _stringify_search_part([doc.title, doc.summary])
    parts.extend(_stringify_search_part(doc.tags.what))
    parts.extend(_stringify_search_part(doc.tags.why))
    parts.extend(_stringify_search_part(doc.tags.how))
    parts.extend(_stringify_search_part(doc.tags.who))
    return " ".join(parts)


def _collect_searchable_text_protocol(protocol: Protocol) -> str:
    """Collect all searchable text from a protocol."""
    parts = _stringify_search_part(protocol.entity_name)
    parts.extend(_stringify_search_part(protocol.content))
    # Gaps
    for gap in protocol.gaps:
        parts.extend(_stringify_search_part(gap.description))
    return " ".join(parts)


def _score_match(query_tokens: list[str], text: str) -> float:
    """Score how well query tokens match a text blob.

    Scoring per query token:
      - 1.0  if the token is a full token in the text
      - 0.7  if the token is a substring of the full text (partial match)
      - 0.0  otherwise
    Plus a bonus 0.5 if the full joined query appears verbatim in the text.
    Normalize by number of query tokens.
    """
    if not query_tokens:
        return 0.0
    text_lower = text.lower()
    text_tokens = set(_tokenize(text_lower))

    token_score = 0.0
    for qt in query_tokens:
        if qt in text_tokens:
            token_score += 1.0
        elif qt in text_lower:
            token_score += 0.7

    # Substring bonus: does the full query appear as-is?
    full_query = " ".join(query_tokens)
    substring_bonus = 0.5 if full_query in text_lower else 0.0

    return (token_score + substring_bonus) / len(query_tokens)


def search_ontology(
    query: str,
    entities: list[Entity],
    documents: list[Document],
    protocols: list[Protocol],
    *,
    max_level: int | None = None,
) -> list[SearchResult]:
    """Search across entities, documents, and protocols by keyword matching.

    Steps:
      1. Tokenize the query
      2. Match tokens against name, summary, and tags of each object
      3. Score by match ratio
      4. Return results sorted by score descending (only score > 0)

    Args:
        max_level: If set, only include entities with level <= max_level.
                   Entities with level=None are treated as L1 (included when max_level >= 1).
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    results: list[SearchResult] = []

    # Filter entities by level if requested
    if max_level is not None:
        entities = [
            e for e in entities
            if (e.level or 1) <= max_level
        ]

    # Search entities
    for entity in entities:
        text = _collect_searchable_text_entity(entity)
        score = _score_match(query_tokens, text)
        if score > 0:
            results.append(SearchResult(
                type="entity",
                id=entity.id,
                name=entity.name,
                summary=entity.summary,
                score=score,
            ))

    # Search documents
    for doc in documents:
        text = _collect_searchable_text_document(doc)
        score = _score_match(query_tokens, text)
        if score > 0:
            results.append(SearchResult(
                type="document",
                id=doc.id,
                name=doc.title,
                summary=doc.summary,
                score=score,
            ))

    # Search protocols
    for protocol in protocols:
        text = _collect_searchable_text_protocol(protocol)
        score = _score_match(query_tokens, text)
        if score > 0:
            results.append(SearchResult(
                type="protocol",
                id=protocol.id,
                name=protocol.entity_name,
                # Keep version visible in search results as artifact metadata;
                # ranking does not depend on protocol.version.
                summary=f"Protocol v{protocol.version}",
                score=score,
            ))

    # Sort by score descending, then by name for stability
    results.sort(key=lambda r: (-r.score, r.name))
    return results
