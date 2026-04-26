"""Canonical linkage helpers for L3 document entities."""

from __future__ import annotations

from zenos.domain.knowledge import Document, Entity, Relationship, RelationshipType


DOCUMENT_LINK_REL_TYPES = frozenset({
    RelationshipType.PART_OF,
    RelationshipType.RELATED_TO,
})


def dedupe_ids(values: list[str | None]) -> list[str]:
    """Return stable, non-empty IDs with duplicates removed."""
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def get_document_linked_entity_ids(
    doc: Entity | Document,
    relationships: list[Relationship] | tuple[Relationship, ...] | None = None,
) -> list[str]:
    """Resolve all entities linked to a document.

    Runtime still has two document representations:
    - legacy ``Document.linked_entity_ids``
    - L3 ``Entity(type="document")`` with ``parent_id`` plus graph edges

    Treat ``parent_id`` / ``part_of`` as the primary link and ``related_to`` as
    additional first-class links. Callers should not infer this contract locally.
    """
    linked: list[str | None] = []

    if isinstance(doc, Document):
        linked.extend(doc.linked_entity_ids)
    else:
        linked.append(doc.parent_id)

    doc_id = doc.id
    if doc_id:
        for rel in relationships or []:
            if rel.source_entity_id != doc_id:
                continue
            if rel.type not in DOCUMENT_LINK_REL_TYPES:
                continue
            linked.append(rel.target_id)

    return dedupe_ids(linked)
