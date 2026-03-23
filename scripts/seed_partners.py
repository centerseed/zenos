"""Seed partner documents in Firestore.

Usage:
    python scripts/seed_partners.py

Requires GOOGLE_CLOUD_PROJECT env var or defaults to zenos-naruvia.
"""

import uuid
from datetime import datetime, timezone

from google.cloud import firestore


def main():
    db = firestore.Client(project="zenos-naruvia")

    # First, find the Paceriz product entity ID
    entities = db.collection("entities").where("type", "==", "product").stream()
    product_ids = []
    for entity in entities:
        data = entity.to_dict()
        product_ids.append(entity.id)
        print(f"Found product entity: {entity.id} — {data.get('name', '?')}")

    if not product_ids:
        print("No product entities found. Seed ontology first.")
        return

    now = datetime.now(timezone.utc)

    # Barry (admin)
    barry_key = str(uuid.uuid4())
    db.collection("partners").document().set({
        "email": "centerseedwu@gmail.com",
        "displayName": "Barry",
        "apiKey": barry_key,
        "authorizedEntityIds": product_ids,
        "isAdmin": True,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    })
    print(f"\nCreated Barry (admin)")
    print(f"  API Key: {barry_key}")

    # Test marketing partner
    partner_key = str(uuid.uuid4())
    db.collection("partners").document().set({
        "email": "test.partner@gmail.com",
        "displayName": "Marketing Partner (Test)",
        "apiKey": partner_key,
        "authorizedEntityIds": product_ids,
        "isAdmin": False,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    })
    print(f"\nCreated Marketing Partner (Test)")
    print(f"  API Key: {partner_key}")

    print("\nDone! Update the partner emails to real ones before use.")


if __name__ == "__main__":
    main()
