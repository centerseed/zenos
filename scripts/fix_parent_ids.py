"""One-off script: fix document entity parentId fields and ensure part_of relationships.

Problem 1: 8 document entities have incorrect parentId values.
           Update each to point to the correct parent module.

Problem 2: After fixing parentId, the corresponding part_of relationship
           may be missing in the entity's relationships subcollection.
           Create it if absent.

Usage:
    python scripts/fix_parent_ids.py
"""

import asyncio

from google.cloud.firestore import AsyncClient


# (doc_entity_id, correct_parent_module_id)
FIXES = [
    ("7xkOJBeV0K4uNzccjuJ0", "usxpqKXCmxgPNOYzvb9I"),  # ZenOS Product Spec → Ontology Engine
    ("5nHKoUtvBq34KSB42mSb", "usxpqKXCmxgPNOYzvb9I"),  # ADR-002 → Ontology Engine
    ("FU1tXzdg2oJhAJe1p63p", "uMY9pF3oezJb4iScIpHX"),  # ADR-006 → Dashboard
    ("T2oCordrRpK1gnd3PpvV", "Llrm0Dz1z4BS41cGq9qW"),  # Paceriz Context Protocol → Adapter 架構
    ("dliWhnS4lIL6jGxSvzRO", "Llrm0Dz1z4BS41cGq9qW"),  # ZenOS Context Protocol → Adapter 架構
    ("i4tV47eo0PA3F3SqivoV", "usxpqKXCmxgPNOYzvb9I"),  # Phase 1 MVP Spec → Ontology Engine
    ("lFWH8XptGlLUpoONAwvj", "zARlcbDRV3y0IXX0jGO9"),  # Foundation P0 Handoff → MCP Server
    ("apEbqweBq9oV5mHMpzlC", "zARlcbDRV3y0IXX0jGO9"),  # Foundation P0 驗證測試 → MCP Server
]


async def fix_parent_ids(db: AsyncClient) -> None:
    """Update parentId on each document entity and print before/after state."""
    for doc_entity_id, new_parent_id in FIXES:
        doc_ref = db.collection("entities").document(doc_entity_id)
        snap = await doc_ref.get()
        if not snap.exists:
            print(f"  [SKIP] Entity {doc_entity_id} not found.")
            continue

        data = snap.to_dict()
        name = data.get("name", doc_entity_id)
        old_parent_id = data.get("parentId", None)

        print(f"  {name}")
        print(f"    Before: parentId = {old_parent_id}")

        await doc_ref.update({"parentId": new_parent_id})

        print(f"    After:  parentId = {new_parent_id}")


async def ensure_part_of_relationships(db: AsyncClient) -> None:
    """For each fix, check if a part_of relationship to the new parent exists. Create if missing."""
    created = 0
    skipped = 0

    for doc_entity_id, new_parent_id in FIXES:
        rels_col = db.collection("entities").document(doc_entity_id).collection("relationships")

        # Check for existing part_of relationship pointing to new parent
        has_existing = False
        async for rel_doc in rels_col.where("type", "==", "part_of").where("targetId", "==", new_parent_id).stream():
            has_existing = True
            break

        entity_snap = await db.collection("entities").document(doc_entity_id).get()
        name = entity_snap.to_dict().get("name", doc_entity_id) if entity_snap.exists else doc_entity_id

        if has_existing:
            print(f"  [EXISTS] {name} → part_of → {new_parent_id}")
            skipped += 1
        else:
            rel_data = {
                "sourceEntityId": doc_entity_id,
                "targetId": new_parent_id,
                "type": "part_of",
                "description": "document belongs to module",
                "confirmedByUser": False,
            }
            await rels_col.add(rel_data)
            print(f"  [CREATED] {name} → part_of → {new_parent_id}")
            created += 1

    print(f"  Total created: {created}, already existed: {skipped}")


async def verify(db: AsyncClient) -> None:
    """Print final state of all fixed entities."""
    for doc_entity_id, expected_parent_id in FIXES:
        snap = await db.collection("entities").document(doc_entity_id).get()
        if not snap.exists:
            print(f"  [MISSING] {doc_entity_id}")
            continue

        data = snap.to_dict()
        name = data.get("name", doc_entity_id)
        actual_parent_id = data.get("parentId", None)
        ok = "OK" if actual_parent_id == expected_parent_id else "MISMATCH"
        print(f"  [{ok}] {name}: parentId = {actual_parent_id}")


async def main() -> None:
    db = AsyncClient(project="zenos-naruvia")

    print("=== Step 1: Fix parentId on 8 document entities ===")
    await fix_parent_ids(db)

    print()
    print("=== Step 2: Ensure part_of relationships ===")
    await ensure_part_of_relationships(db)

    print()
    print("=== Step 3: Verify final state ===")
    await verify(db)

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
