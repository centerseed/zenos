#!/usr/bin/env python3
"""Clean up auto-inferred cross-product related_to relationships.

Only removes relationships where:
  - type = "related_to"
  - description = "auto-inferred"
  - source and target entities belong to different products

Manually created relationships (description != "auto-inferred") are untouched.

Usage:
    python scripts/cleanup_cross_product_related_to.py [--dry-run]
"""
import asyncio
import sys

from google.cloud import firestore


def _get_product_id(entity_id: str, entities: dict[str, dict]) -> str | None:
    """Walk parentId chain upward to find the product ancestor."""
    visited: set[str] = set()
    current = entity_id
    while current and current not in visited:
        visited.add(current)
        ent = entities.get(current)
        if ent is None:
            return None
        if ent.get("type") == "product":
            return current
        current = ent.get("parentId")
    return None


async def main() -> None:
    dry_run = "--dry-run" in sys.argv

    db = firestore.AsyncClient(project="zenos-naruvia")

    # Step 1: Load all entities into memory for parent chain traversal
    print("Loading all entities...")
    entities: dict[str, dict] = {}
    async for doc in db.collection("entities").stream():
        entities[doc.id] = doc.to_dict()
    print(f"  Loaded {len(entities)} entities")

    # Step 2: Scan all relationships via collectionGroup
    print("Scanning relationships...")
    to_delete: list[tuple[str, str]] = []  # (source_entity_id, rel_doc_id)
    total_rels = 0
    total_related_to = 0
    total_auto_inferred = 0

    async for doc in db.collection_group("relationships").stream():
        total_rels += 1
        data = doc.to_dict()
        rel_type = data.get("type", "")
        if rel_type != "related_to":
            continue
        total_related_to += 1

        description = data.get("description", "")
        if description != "auto-inferred":
            continue
        total_auto_inferred += 1

        source_id = data.get("sourceEntityId", "")
        target_id = data.get("targetId", "")

        source_product = _get_product_id(source_id, entities)
        target_product = _get_product_id(target_id, entities)

        # Cross-product: different products, or one/both have no product ancestor
        if source_product and target_product and source_product != target_product:
            # Extract the source entity ID from the document path
            # Path: entities/{sourceEntityId}/relationships/{relId}
            path_parts = doc.reference.path.split("/")
            parent_entity_id = path_parts[1] if len(path_parts) >= 4 else source_id
            to_delete.append((parent_entity_id, doc.id))

            source_name = entities.get(source_id, {}).get("name", source_id)
            target_name = entities.get(target_id, {}).get("name", target_id)
            print(f"  WILL DELETE: {source_name} --related_to--> {target_name} (cross-product)")

    print(f"\nSummary:")
    print(f"  Total relationships: {total_rels}")
    print(f"  Total related_to: {total_related_to}")
    print(f"  Total auto-inferred related_to: {total_auto_inferred}")
    print(f"  Cross-product auto-inferred to delete: {len(to_delete)}")

    if not to_delete:
        print("\nNothing to clean up.")
        return

    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(to_delete)} relationships. Run without --dry-run to execute.")
        return

    # Step 3: Delete
    print(f"\nDeleting {len(to_delete)} relationships...")
    deleted = 0
    for source_entity_id, rel_id in to_delete:
        ref = db.collection("entities").document(source_entity_id).collection("relationships").document(rel_id)
        await ref.delete()
        deleted += 1

    print(f"  Deleted {deleted} cross-product auto-inferred related_to relationships.")


if __name__ == "__main__":
    asyncio.run(main())
