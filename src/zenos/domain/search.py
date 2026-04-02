"""In-memory keyword search across ontology objects — zero external deps."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Document, DocumentTags, Entity, Protocol, Tags


@dataclass
class SearchResult:
    """A single search hit."""
    type: str       # "entity" | "document" | "protocol"
    id: str | None
    name: str
    summary: str
    score: float    # higher = better match
    ancestors: list[dict] | None = None  # filled by application layer for entity results


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alphanumeric tokens."""
    return [t for t in re.split(r"[\s\-_/.,;:!?()（）。，、；：！？「」『』\[\]{}]+", text.lower()) if t]


def _collect_searchable_text_entity(entity: Entity) -> str:
    """Collect all searchable text from an entity."""
    parts = [entity.name, entity.summary, entity.type]
    if isinstance(entity.tags, Tags):
        what = entity.tags.what
        who = entity.tags.who
        # Handle both list[str] and str formats
        if isinstance(what, list):
            parts.extend(what)
        else:
            parts.append(what)
        parts.append(entity.tags.why)
        parts.append(entity.tags.how)
        if isinstance(who, list):
            parts.extend(who)
        else:
            parts.append(who)
    return " ".join(parts)


def _collect_searchable_text_document(doc: Document) -> str:
    """Collect all searchable text from a document."""
    parts = [doc.title, doc.summary]
    if isinstance(doc.tags, DocumentTags):
        parts.extend(doc.tags.what)
        parts.append(doc.tags.why)
        parts.append(doc.tags.how)
        parts.extend(doc.tags.who)
    return " ".join(parts)


def _collect_searchable_text_protocol(protocol: Protocol) -> str:
    """Collect all searchable text from a protocol."""
    parts = [protocol.entity_name]
    # Flatten content dict values
    if isinstance(protocol.content, dict):
        for val in protocol.content.values():
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, dict):
                for v in val.values():
                    if isinstance(v, str):
                        parts.append(v)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        parts.append(item)
    # Gaps
    for gap in protocol.gaps:
        parts.append(gap.description)
    return " ".join(parts)


def _score_match(query_tokens: list[str], text: str) -> float:
    """Score how well query tokens match a text blob.

    Scoring:
      - Each token that appears in text contributes 1.0
      - Bonus 0.5 for exact substring match (preserves word order)
      - Normalize by number of query tokens
    """
    if not query_tokens:
        return 0.0
    text_lower = text.lower()
    text_tokens = set(_tokenize(text_lower))

    hits = sum(1.0 for qt in query_tokens if qt in text_tokens)
    # Substring bonus: does the full query appear as-is?
    full_query = " ".join(query_tokens)
    substring_bonus = 0.5 if full_query in text_lower else 0.0

    return (hits + substring_bonus) / len(query_tokens)


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
                summary=f"Protocol v{protocol.version}",
                score=score,
            ))

    # Sort by score descending, then by name for stability
    results.sort(key=lambda r: (-r.score, r.name))
    return results
