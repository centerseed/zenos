"""Update partner authorizedEntityIds to include all current product entities.

Usage:
    python scripts/update_partner_entities.py
"""

from google.cloud import firestore


def main():
    db = firestore.Client(project="zenos-naruvia")

    # Get all current product entity IDs
    entities = db.collection("entities").where("type", "==", "product").stream()
    product_ids = []
    for entity in entities:
        data = entity.to_dict()
        product_ids.append(entity.id)
        print(f"Product: {entity.id} — {data.get('name', '?')}")

    if not product_ids:
        print("No product entities found.")
        return

    print(f"\nTotal products: {len(product_ids)}")

    # Update all active partners
    partners = db.collection("partners").where("status", "==", "active").stream()
    for partner in partners:
        data = partner.to_dict()
        current = set(data.get("authorizedEntityIds", []))
        updated = set(product_ids)

        missing = updated - current
        if missing:
            partner.reference.update({"authorizedEntityIds": product_ids})
            print(f"\nUpdated {data.get('displayName')}: added {len(missing)} entities")
            for eid in missing:
                print(f"  + {eid}")
        else:
            print(f"\n{data.get('displayName')}: already up to date")

    print("\nDone!")


if __name__ == "__main__":
    main()
