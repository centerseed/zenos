"""Firestore implementations of all domain Repository protocols."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore  # type: ignore[import-untyped]
from google.cloud.firestore_v1 import AsyncClient  # type: ignore[import-untyped]

from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
    Gap,
    Protocol as OntologyProtocol,
    Relationship,
    Source,
    Tags,
)

# ---------------------------------------------------------------------------
# Firestore client singleton
# ---------------------------------------------------------------------------

_db: AsyncClient | None = None


def get_db() -> AsyncClient:
    """Return a cached AsyncClient instance."""
    global _db  # noqa: PLW0603
    if _db is None:
        _db = firestore.AsyncClient(project="zenos-naruvia")
    return _db


# ---------------------------------------------------------------------------
# snake_case <-> camelCase helpers
# ---------------------------------------------------------------------------

_CAMEL_RE = re.compile(r"([A-Z])")
_SNAKE_RE = re.compile(r"_([a-z])")


def _to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    return _SNAKE_RE.sub(lambda m: m.group(1).upper(), name)


def _to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return _CAMEL_RE.sub(lambda m: f"_{m.group(1).lower()}", name)


def to_firestore_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Convert a flat Python dict (snake_case keys) to Firestore dict (camelCase keys).

    - Recursively converts nested dicts.
    - Converts datetime -> keeps as-is (Firestore SDK handles it).
    - Drops keys whose value is None.
    - Drops the ``id`` key (stored as document ID, not inside the doc).
    """
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key == "id":
            continue
        if value is None:
            continue
        camel = _to_camel(key)
        if isinstance(value, dict):
            out[camel] = to_firestore_dict(value)
        elif isinstance(value, list):
            out[camel] = [
                to_firestore_dict(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            out[camel] = value
    return out


def from_firestore_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Convert a Firestore dict (camelCase keys) to Python dict (snake_case keys).

    Recursively converts nested dicts / lists of dicts.
    """
    out: dict[str, Any] = {}
    for key, value in data.items():
        snake = _to_snake(key)
        if isinstance(value, dict):
            out[snake] = from_firestore_dict(value)
        elif isinstance(value, list):
            out[snake] = [
                from_firestore_dict(v) if isinstance(v, dict) else v for v in value
            ]
        else:
            out[snake] = value
    return out


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(val: Any) -> datetime | None:
    """Coerce a Firestore timestamp or datetime to a tz-aware datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    # google.cloud.firestore returns DatetimeWithNanoseconds (subclass of datetime),
    # so the isinstance check above should catch it.  As a fallback:
    if hasattr(val, "isoformat"):
        return val  # type: ignore[return-value]
    return None


# ---------------------------------------------------------------------------
# Entity helpers
# ---------------------------------------------------------------------------


def _entity_to_dict(entity: Entity) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "name": entity.name,
        "type": entity.type,
        "parent_id": entity.parent_id,
        "status": entity.status,
        "summary": entity.summary,
        "tags": {
            "what": entity.tags.what,
            "why": entity.tags.why,
            "how": entity.tags.how,
            "who": entity.tags.who,
        },
        "details": entity.details,
        "confirmed_by_user": entity.confirmed_by_user,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
    }
    return to_firestore_dict(raw)


def _dict_to_entity(doc_id: str, data: dict[str, Any]) -> Entity:
    d = from_firestore_dict(data)
    tags_raw = d.get("tags", {})
    return Entity(
        id=doc_id,
        name=d.get("name", ""),
        type=d.get("type", ""),
        parent_id=d.get("parent_id"),
        status=d.get("status", "active"),
        summary=d.get("summary", ""),
        tags=Tags(
            what=tags_raw.get("what", ""),
            why=tags_raw.get("why", ""),
            how=tags_raw.get("how", ""),
            who=tags_raw.get("who", ""),
        ),
        details=d.get("details"),
        confirmed_by_user=d.get("confirmed_by_user", False),
        created_at=_to_dt(d.get("created_at")) or _now(),
        updated_at=_to_dt(d.get("updated_at")) or _now(),
    )


# ---------------------------------------------------------------------------
# Relationship helpers
# ---------------------------------------------------------------------------


def _rel_to_dict(rel: Relationship) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "source_entity_id": rel.source_entity_id,
        "target_id": rel.target_id,
        "type": rel.type,
        "description": rel.description,
        "confirmed_by_user": rel.confirmed_by_user,
    }
    return to_firestore_dict(raw)


def _dict_to_rel(doc_id: str, data: dict[str, Any]) -> Relationship:
    d = from_firestore_dict(data)
    return Relationship(
        id=doc_id,
        source_entity_id=d.get("source_entity_id", ""),
        target_id=d.get("target_id", ""),
        type=d.get("type", ""),
        description=d.get("description", ""),
        confirmed_by_user=d.get("confirmed_by_user", False),
    )


# ---------------------------------------------------------------------------
# Document helpers
# ---------------------------------------------------------------------------


def _document_to_dict(doc: Document) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "title": doc.title,
        "source": {
            "type": doc.source.type,
            "uri": doc.source.uri,
            "adapter": doc.source.adapter,
        },
        "tags": {
            "what": doc.tags.what,
            "why": doc.tags.why,
            "how": doc.tags.how,
            "who": doc.tags.who,
        },
        "linked_entity_ids": doc.linked_entity_ids,
        "summary": doc.summary,
        "status": doc.status,
        "confirmed_by_user": doc.confirmed_by_user,
        "last_reviewed_at": doc.last_reviewed_at,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }
    return to_firestore_dict(raw)


def _dict_to_document(doc_id: str, data: dict[str, Any]) -> Document:
    d = from_firestore_dict(data)
    source_raw = d.get("source", {})
    tags_raw = d.get("tags", {})
    return Document(
        id=doc_id,
        title=d.get("title", ""),
        source=Source(
            type=source_raw.get("type", ""),
            uri=source_raw.get("uri", ""),
            adapter=source_raw.get("adapter", ""),
        ),
        tags=DocumentTags(
            what=tags_raw.get("what", []),
            why=tags_raw.get("why", ""),
            how=tags_raw.get("how", ""),
            who=tags_raw.get("who", []),
        ),
        linked_entity_ids=d.get("linked_entity_ids", []),
        summary=d.get("summary", ""),
        status=d.get("status", "draft"),
        confirmed_by_user=d.get("confirmed_by_user", False),
        last_reviewed_at=_to_dt(d.get("last_reviewed_at")),
        created_at=_to_dt(d.get("created_at")) or _now(),
        updated_at=_to_dt(d.get("updated_at")) or _now(),
    )


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------


def _protocol_to_dict(proto: OntologyProtocol) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "entity_id": proto.entity_id,
        "entity_name": proto.entity_name,
        "content": proto.content,
        "gaps": [
            {"description": g.description, "priority": g.priority} for g in proto.gaps
        ],
        "version": proto.version,
        "confirmed_by_user": proto.confirmed_by_user,
        "generated_at": proto.generated_at,
        "updated_at": proto.updated_at,
    }
    return to_firestore_dict(raw)


def _dict_to_protocol(doc_id: str, data: dict[str, Any]) -> OntologyProtocol:
    d = from_firestore_dict(data)
    gaps_raw = d.get("gaps", [])
    gaps = [
        Gap(
            description=g.get("description", ""),
            priority=g.get("priority", "green"),
        )
        for g in gaps_raw
    ]
    return OntologyProtocol(
        id=doc_id,
        entity_id=d.get("entity_id", ""),
        entity_name=d.get("entity_name", ""),
        content=d.get("content", {}),
        gaps=gaps,
        version=d.get("version", "v0.1"),
        confirmed_by_user=d.get("confirmed_by_user", False),
        generated_at=_to_dt(d.get("generated_at")) or _now(),
        updated_at=_to_dt(d.get("updated_at")) or _now(),
    )


# ---------------------------------------------------------------------------
# Blindspot helpers
# ---------------------------------------------------------------------------


def _blindspot_to_dict(bs: Blindspot) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "description": bs.description,
        "severity": bs.severity,
        "related_entity_ids": bs.related_entity_ids,
        "suggested_action": bs.suggested_action,
        "status": bs.status,
        "confirmed_by_user": bs.confirmed_by_user,
        "created_at": bs.created_at,
    }
    return to_firestore_dict(raw)


def _dict_to_blindspot(doc_id: str, data: dict[str, Any]) -> Blindspot:
    d = from_firestore_dict(data)
    return Blindspot(
        id=doc_id,
        description=d.get("description", ""),
        severity=d.get("severity", "green"),
        related_entity_ids=d.get("related_entity_ids", []),
        suggested_action=d.get("suggested_action", ""),
        status=d.get("status", "open"),
        confirmed_by_user=d.get("confirmed_by_user", False),
        created_at=_to_dt(d.get("created_at")) or _now(),
    )


# ===================================================================
# Repository implementations
# ===================================================================


class FirestoreEntityRepository:
    """Firestore-backed EntityRepository."""

    def __init__(self, db: AsyncClient | None = None) -> None:
        self._db = db or get_db()
        self._col = self._db.collection("entities")

    async def get_by_id(self, entity_id: str) -> Entity | None:
        snap = await self._col.document(entity_id).get()
        if not snap.exists:
            return None
        return _dict_to_entity(snap.id, snap.to_dict())  # type: ignore[arg-type]

    async def get_by_name(self, name: str) -> Entity | None:
        query = self._col.where("name", "==", name).limit(1)
        docs = query.stream()
        async for doc in docs:
            return _dict_to_entity(doc.id, doc.to_dict())
        return None

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        q: Any = self._col
        if type_filter is not None:
            q = q.where("type", "==", type_filter)
        results: list[Entity] = []
        async for doc in q.stream():
            results.append(_dict_to_entity(doc.id, doc.to_dict()))
        return results

    async def upsert(self, entity: Entity) -> Entity:
        now = _now()
        entity.updated_at = now
        data = _entity_to_dict(entity)

        if entity.id is None:
            # New entity: auto-generate ID
            entity.created_at = now
            data["createdAt"] = now
            _, doc_ref = await self._col.add(data)
            entity.id = doc_ref.id
        else:
            # Existing entity: merge
            await self._col.document(entity.id).set(data, merge=True)

        return entity

    async def list_unconfirmed(self) -> list[Entity]:
        query = self._col.where("confirmedByUser", "==", False)
        results: list[Entity] = []
        async for doc in query.stream():
            results.append(_dict_to_entity(doc.id, doc.to_dict()))
        return results


class FirestoreRelationshipRepository:
    """Firestore-backed RelationshipRepository.

    Relationships are stored as sub-collections under their source entity:
    ``entities/{source_entity_id}/relationships/{relId}``
    """

    def __init__(self, db: AsyncClient | None = None) -> None:
        self._db = db or get_db()

    def _col(self, entity_id: str) -> Any:
        return self._db.collection("entities").document(entity_id).collection("relationships")

    async def list_by_entity(self, entity_id: str) -> list[Relationship]:
        results: list[Relationship] = []
        async for doc in self._col(entity_id).stream():
            results.append(_dict_to_rel(doc.id, doc.to_dict()))
        return results

    async def add(self, rel: Relationship) -> Relationship:
        data = _rel_to_dict(rel)
        col = self._col(rel.source_entity_id)

        if rel.id is None:
            _, doc_ref = await col.add(data)
            rel.id = doc_ref.id
        else:
            await col.document(rel.id).set(data, merge=True)

        return rel


class FirestoreDocumentRepository:
    """Firestore-backed DocumentRepository."""

    def __init__(self, db: AsyncClient | None = None) -> None:
        self._db = db or get_db()
        self._col = self._db.collection("documents")

    async def get_by_id(self, doc_id: str) -> Document | None:
        snap = await self._col.document(doc_id).get()
        if not snap.exists:
            return None
        return _dict_to_document(snap.id, snap.to_dict())  # type: ignore[arg-type]

    async def list_all(self) -> list[Document]:
        results: list[Document] = []
        async for doc in self._col.stream():
            results.append(_dict_to_document(doc.id, doc.to_dict()))
        return results

    async def upsert(self, doc: Document) -> Document:
        now = _now()
        doc.updated_at = now
        data = _document_to_dict(doc)

        if doc.id is None:
            doc.created_at = now
            data["createdAt"] = now
            _, doc_ref = await self._col.add(data)
            doc.id = doc_ref.id
        else:
            await self._col.document(doc.id).set(data, merge=True)

        return doc

    async def list_by_entity(self, entity_id: str) -> list[Document]:
        query = self._col.where("linkedEntityIds", "array_contains", entity_id)
        results: list[Document] = []
        async for doc in query.stream():
            results.append(_dict_to_document(doc.id, doc.to_dict()))
        return results

    async def list_unconfirmed(self) -> list[Document]:
        query = self._col.where("confirmedByUser", "==", False)
        results: list[Document] = []
        async for doc in query.stream():
            results.append(_dict_to_document(doc.id, doc.to_dict()))
        return results


class FirestoreProtocolRepository:
    """Firestore-backed ProtocolRepository."""

    def __init__(self, db: AsyncClient | None = None) -> None:
        self._db = db or get_db()
        self._col = self._db.collection("protocols")

    async def get_by_entity(self, entity_id: str) -> OntologyProtocol | None:
        query = self._col.where("entityId", "==", entity_id).limit(1)
        async for doc in query.stream():
            return _dict_to_protocol(doc.id, doc.to_dict())
        return None

    async def get_by_entity_name(self, name: str) -> OntologyProtocol | None:
        query = self._col.where("entityName", "==", name).limit(1)
        async for doc in query.stream():
            return _dict_to_protocol(doc.id, doc.to_dict())
        return None

    async def upsert(self, protocol: OntologyProtocol) -> OntologyProtocol:
        now = _now()
        protocol.updated_at = now
        data = _protocol_to_dict(protocol)

        if protocol.id is None:
            protocol.generated_at = now
            data["generatedAt"] = now
            _, doc_ref = await self._col.add(data)
            protocol.id = doc_ref.id
        else:
            await self._col.document(protocol.id).set(data, merge=True)

        return protocol

    async def list_unconfirmed(self) -> list[OntologyProtocol]:
        query = self._col.where("confirmedByUser", "==", False)
        results: list[OntologyProtocol] = []
        async for doc in query.stream():
            results.append(_dict_to_protocol(doc.id, doc.to_dict()))
        return results


class FirestoreBlindspotRepository:
    """Firestore-backed BlindspotRepository."""

    def __init__(self, db: AsyncClient | None = None) -> None:
        self._db = db or get_db()
        self._col = self._db.collection("blindspots")

    async def list_all(
        self,
        entity_id: str | None = None,
        severity: str | None = None,
    ) -> list[Blindspot]:
        q: Any = self._col
        if entity_id is not None:
            q = q.where("relatedEntityIds", "array_contains", entity_id)
        if severity is not None:
            q = q.where("severity", "==", severity)
        results: list[Blindspot] = []
        async for doc in q.stream():
            results.append(_dict_to_blindspot(doc.id, doc.to_dict()))
        return results

    async def add(self, blindspot: Blindspot) -> Blindspot:
        now = _now()
        if blindspot.created_at is None:  # type: ignore[comparison-overlap]
            blindspot.created_at = now
        data = _blindspot_to_dict(blindspot)

        if blindspot.id is None:
            _, doc_ref = await self._col.add(data)
            blindspot.id = doc_ref.id
        else:
            await self._col.document(blindspot.id).set(data, merge=True)

        return blindspot

    async def list_unconfirmed(self) -> list[Blindspot]:
        query = self._col.where("confirmedByUser", "==", False)
        results: list[Blindspot] = []
        async for doc in query.stream():
            results.append(_dict_to_blindspot(doc.id, doc.to_dict()))
        return results
