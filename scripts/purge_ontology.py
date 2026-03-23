"""Admin script: purge all ontology data from Firestore.

Usage:
    python scripts/purge_ontology.py

This is NOT an MCP tool. Destructive operations must only be run
manually by an admin, never exposed to agents.
"""

import asyncio
import sys

from google.cloud.firestore import AsyncClient


async def purge():
    db = AsyncClient(project="zenos-naruvia")

    collections = ["entities", "documents", "protocols", "blindspots"]
    total = 0

    for col_name in collections:
        count = 0
        async for doc in db.collection(col_name).stream():
            if col_name == "entities":
                async for rel_doc in doc.reference.collection("relationships").stream():
                    await rel_doc.reference.delete()
            await doc.reference.delete()
            count += 1
        print(f"  {col_name}: {count} deleted")
        total += count

    print(f"\nTotal: {total} documents purged. Tasks preserved.")


if __name__ == "__main__":
    print("⚠️  This will DELETE ALL ontology data (entities, documents, protocols, blindspots).")
    print("   Tasks will NOT be affected.\n")
    confirm = input("Type 'DELETE' to proceed: ")
    if confirm != "DELETE":
        print("Aborted.")
        sys.exit(1)
    asyncio.run(purge())
