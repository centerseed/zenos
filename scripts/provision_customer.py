"""Provision a new customer admin partner document in Firestore.

Usage:
    python scripts/provision_customer.py \
      --project zenos-naruvia \
      --admin-email admin@example.com \
      --display-name "Acme Admin" \
      [--dry-run]
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

from google.cloud import firestore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision a customer admin partner doc")
    parser.add_argument("--project", required=True, help="Target Firebase/GCP project id")
    parser.add_argument("--admin-email", required=True, help="Admin partner email")
    parser.add_argument("--display-name", required=True, help="Admin partner display name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing to Firestore",
    )
    return parser.parse_args()


def build_partner_doc(admin_email: str, display_name: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "email": admin_email.strip().lower(),
        "displayName": display_name.strip(),
        "apiKey": str(uuid.uuid4()),
        "authorizedEntityIds": [],
        "isAdmin": True,
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    }


def print_next_steps(project: str, partner_id: str | None = None) -> None:
    print("\nNext deploy commands:")
    print(f"  firebase use {project}")
    print("  firebase deploy --only hosting")
    print("  firebase deploy --only firestore:rules")
    print("  ./scripts/deploy_mcp.sh")
    if partner_id:
        print(f"\nCreated partner id: {partner_id}")


def main() -> int:
    args = parse_args()
    doc = build_partner_doc(args.admin_email, args.display_name)

    print("Provision request:")
    print(f"  project: {args.project}")
    print(f"  email: {doc['email']}")
    print(f"  displayName: {doc['displayName']}")
    print(f"  isAdmin: {doc['isAdmin']}")
    print(f"  status: {doc['status']}")
    print(f"  dryRun: {args.dry_run}")

    if args.dry_run:
        print("\n--dry-run enabled, no write executed.")
        print_next_steps(args.project, "<dry-run>")
        return 0

    db = firestore.Client(project=args.project)
    existing = list(db.collection("partners").where("email", "==", doc["email"]).limit(1).stream())
    if existing:
        existing_id = existing[0].id
        print(f"\nPartner already exists for {doc['email']}: {existing_id}")
        print_next_steps(args.project, existing_id)
        return 1

    ref = db.collection("partners").document()
    ref.set(doc)
    print("\nPartner created successfully.")
    print_next_steps(args.project, ref.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
