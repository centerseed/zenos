"""One-off script: fix Ontology Engine entity sources + deduplicate relationships.

Problem 1: Entity usxpqKXCmxgPNOYzvb9I has 8 sources, 7 are Paceriz docs that
           don't belong. Keep only the REF-ontology-methodology.md source.

Problem 2: Duplicate relationships exist (same source_entity_id + target_id + type).
           Keep the earliest one, delete the rest.

Usage:
    python scripts/fix_sources.py
"""

import asyncio

from google.cloud.firestore import AsyncClient


ENTITY_ID = "usxpqKXCmxgPNOYzvb9I"
CORRECT_SOURCES = [
    {
        "uri": "https://github.com/centerseed/zenos/blob/main/docs/reference/REF-ontology-methodology.md",
        "label": "Ontology 方法論",
        "type": "github",
    }
]


async def fix_sources(db: AsyncClient) -> None:
    """Overwrite sources on the Ontology Engine entity."""
    doc_ref = db.collection("entities").document(ENTITY_ID)
    snap = await doc_ref.get()
    if not snap.exists:
        print(f"  Entity {ENTITY_ID} not found. Skipping.")
        return

    data = snap.to_dict()
    old_sources = data.get("sources", [])
    print(f"  Before: {len(old_sources)} sources")
    for s in old_sources:
        print(f"    - {s.get('label', '?')}: {s.get('uri', '?')}")

    await doc_ref.update({"sources": CORRECT_SOURCES})

    print(f"  After: {len(CORRECT_SOURCES)} source(s)")
    for s in CORRECT_SOURCES:
        print(f"    - {s['label']}: {s['uri']}")


async def dedupe_relationships(db: AsyncClient) -> None:
    """Scan all entities' relationships subcollections and remove duplicates."""
    total_scanned = 0
    total_deleted = 0

    async for entity_doc in db.collection("entities").stream():
        rels_col = entity_doc.reference.collection("relationships")
        rels: list[tuple[str, dict]] = []

        async for rel_doc in rels_col.stream():
            rels.append((rel_doc.id, rel_doc.to_dict()))

        if not rels:
            continue

        # Group by (source_entity_id, target_id, type) — keep first occurrence
        seen: dict[tuple[str, str, str], str] = {}
        to_delete: list[str] = []

        for rel_id, rel_data in rels:
            total_scanned += 1
            key = (
                rel_data.get("sourceEntityId", ""),
                rel_data.get("targetId", ""),
                rel_data.get("type", ""),
            )
            if key in seen:
                to_delete.append(rel_id)
            else:
                seen[key] = rel_id

        for rel_id in to_delete:
            await rels_col.document(rel_id).delete()
            total_deleted += 1

        if to_delete:
            entity_name = entity_doc.to_dict().get("name", entity_doc.id)
            print(f"  Entity '{entity_name}': deleted {len(to_delete)} duplicate(s)")

    print(f"  Total relationships scanned: {total_scanned}")
    print(f"  Total duplicates deleted: {total_deleted}")


async def main() -> None:
    db = AsyncClient(project="zenos-naruvia")

    print("=== Fix 1: Overwrite Ontology Engine entity sources ===")
    await fix_sources(db)

    print()
    print("=== Fix 2: Deduplicate relationships ===")
    await dedupe_relationships(db)

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
