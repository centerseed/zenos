#!/usr/bin/env python3
"""Migrate tasks from /tasks/{id} to /partners/{PARTNER_ID}/tasks/{id}.

Usage:
    PARTNER_ID=<id> python scripts/migrate_tasks_to_partner.py [--dry-run]
"""
import asyncio
import os
import sys
from google.cloud import firestore


async def main():
    partner_id = os.environ.get("PARTNER_ID") or (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None)
    dry_run = "--dry-run" in sys.argv

    if not partner_id:
        print("ERROR: Set PARTNER_ID env var or pass as first argument")
        sys.exit(1)

    db = firestore.AsyncClient()

    # Read all existing tasks
    old_col = db.collection("tasks")
    docs = await old_col.get()
    print(f"Found {len(docs)} tasks in /tasks/")

    new_col = db.collection("partners").document(partner_id).collection("tasks")
    migrated = 0

    for doc in docs:
        data = doc.to_dict()
        if "project" not in data:
            data["project"] = ""  # backfill

        if dry_run:
            print(f"  [DRY RUN] Would migrate: {doc.id} — {data.get('title', '')[:50]}")
        else:
            await new_col.document(doc.id).set(data)
            migrated += 1
            print(f"  Migrated: {doc.id} — {data.get('title', '')[:50]}")

    print(f"\nMigration {'simulation' if dry_run else 'complete'}: {migrated if not dry_run else len(docs)} tasks")
    print("NOTE: Old /tasks/ collection NOT deleted. Verify data before manual cleanup.")


if __name__ == "__main__":
    asyncio.run(main())
