"""Provision partner documents in Firestore for a new customer tenant.

Two modes
---------
1. Admin mode (default):
   Creates the initial admin partner for a new tenant.

   python scripts/provision_customer.py \\
     --project zenos-naruvia \\
     --admin-email admin@example.com \\
     --display-name "Acme Admin" \\
     [--dry-run]

2. Member mode (--member):
   Adds a non-admin member to an existing tenant.  Requires --admin-id so
   that ``sharedPartnerId`` is set correctly.

   python scripts/provision_customer.py \\
     --project zenos-naruvia \\
     --admin-email ignored@example.com \\
     --display-name "ignored" \\
     --member \\
     --member-email member@example.com \\
     --member-display-name "Acme Member" \\
     --admin-id <admin-partner-id> \\
     [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone

from google.cloud import firestore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision a customer partner doc (admin or member)"
    )
    parser.add_argument("--project", required=True, help="Target Firebase/GCP project id")
    parser.add_argument("--admin-email", required=True, help="Admin partner email (used in admin mode)")
    parser.add_argument("--display-name", required=True, help="Admin partner display name (used in admin mode)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing to Firestore",
    )
    # Member mode flags
    parser.add_argument(
        "--member",
        action="store_true",
        help="Create a non-admin member partner instead of an admin partner",
    )
    parser.add_argument("--member-email", help="Member partner email (required with --member)")
    parser.add_argument("--member-display-name", help="Member partner display name (required with --member)")
    parser.add_argument(
        "--admin-id",
        help="Admin partner id to set as sharedPartnerId (required with --member)",
    )
    return parser.parse_args()


def build_admin_partner_doc(admin_email: str, display_name: str) -> dict:
    """Build a Firestore document for an admin partner.

    Admin partners have ``sharedPartnerId = null`` (absent from the doc) because
    they themselves are the canonical partition key for the tenant.
    """
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


def build_member_partner_doc(member_email: str, display_name: str, admin_id: str) -> dict:
    """Build a Firestore document for a non-admin member partner.

    Non-admin partners must have ``sharedPartnerId = admin_id`` so that their
    read/write operations route to the admin's data partition.
    """
    now = datetime.now(timezone.utc)
    return {
        "email": member_email.strip().lower(),
        "displayName": display_name.strip(),
        "apiKey": str(uuid.uuid4()),
        "authorizedEntityIds": [],
        "isAdmin": False,
        "sharedPartnerId": admin_id,
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


def _provision_admin(args: argparse.Namespace) -> int:
    """Create or verify the admin partner document."""
    doc = build_admin_partner_doc(args.admin_email, args.display_name)

    print("Provision request (admin):")
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
    print("\nAdmin partner created successfully.")
    print_next_steps(args.project, ref.id)
    return 0


def _provision_member(args: argparse.Namespace) -> int:
    """Create a non-admin member partner with sharedPartnerId set to admin_id."""
    if not args.member_email:
        print("ERROR: --member-email is required when using --member", file=sys.stderr)
        return 2
    if not args.member_display_name:
        print("ERROR: --member-display-name is required when using --member", file=sys.stderr)
        return 2
    if not args.admin_id:
        print("ERROR: --admin-id is required when using --member", file=sys.stderr)
        return 2

    doc = build_member_partner_doc(args.member_email, args.member_display_name, args.admin_id)

    print("Provision request (member):")
    print(f"  project: {args.project}")
    print(f"  email: {doc['email']}")
    print(f"  displayName: {doc['displayName']}")
    print(f"  isAdmin: {doc['isAdmin']}")
    print(f"  sharedPartnerId: {doc['sharedPartnerId']}")
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
    print("\nMember partner created successfully.")
    print_next_steps(args.project, ref.id)
    return 0


def main() -> int:
    args = parse_args()
    if args.member:
        return _provision_member(args)
    return _provision_admin(args)


if __name__ == "__main__":
    raise SystemExit(main())
