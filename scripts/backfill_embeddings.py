#!/usr/bin/env python3
"""Backfill summary embeddings for zenos.entities.

Usage:
    scripts/backfill_embeddings.py [--dry-run] [--only-reembed]

Flags:
    --dry-run     : List the number of entities that will be processed without
                    calling the embedding API or writing to the database.
    --only-reembed: Only process entities with needs_reembed=True (i.e. those
                    whose summary hash has changed or whose previous embed
                    failed). Skips entities that have never been embedded
                    (embedded_summary_hash=None).
    (no flags)    : Process all entities where summary_embedding IS NULL
                    OR needs_reembed=True.

Env:
    DATABASE_URL  — PostgreSQL DSN. Obtained from gcloud secrets or set manually.
    GEMINI_API_KEY — Embedding API key consumed by litellm.

Stats block printed at end of run:
    total:    N
    embedded: N
    skipped:  N
    failed:   N
    duration: Xs
"""

from __future__ import annotations

import argparse
import asyncio
import logging

# Module-level imports so tests can patch these names on this module.
from zenos.application.knowledge.embedding_service import EmbeddingService
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.knowledge import SqlEntityRepository
from zenos.infrastructure.llm_client import create_llm_client
from zenos.infrastructure.sql_common import get_pool

logger = logging.getLogger(__name__)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill summary embeddings for all zenos entities.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print how many entities will be processed without calling the API or writing DB.",
    )
    parser.add_argument(
        "--only-reembed",
        action="store_true",
        default=False,
        help="Only process entities with needs_reembed=True; skip never-embedded entities.",
    )
    return parser


async def _resolve_admin_partner_id(pool) -> str:
    """Return the admin partner ID from the DB.

    Admin scripts run outside of an HTTP request context, so the
    partner_id ContextVar must be seeded manually before any repo call.
    We look up the admin partner (is_admin = true) and use that ID.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id FROM zenos.partners WHERE is_admin = true"
        )
    if not rows:
        raise RuntimeError(
            "No admin partner found (is_admin = true). "
            "Cannot resolve partner_id context for backfill."
        )
    if len(rows) > 1:
        ids = [r["id"] for r in rows]
        raise RuntimeError(
            f"Multiple admin partners found: {ids}. Expected exactly one."
        )
    return rows[0]["id"]


async def main_async(args: argparse.Namespace) -> int:
    """Main async entry point — importable for testing.

    Args:
        args: Parsed argparse namespace with .dry_run and .only_reembed fields.

    Returns:
        Exit code (0 = success, 1 = some embeddings failed).
    """
    pool = await get_pool()

    # Resolve and set the admin partner context required by SqlEntityRepository.
    admin_id = await _resolve_admin_partner_id(pool)
    current_partner_id.set(admin_id)
    logger.debug("backfill: using admin partner_id=%s", admin_id)

    entity_repo = SqlEntityRepository(pool)
    llm_client = create_llm_client()
    service = EmbeddingService(entity_repo=entity_repo, llm_client=llm_client)

    stats = await service.batch_embed_missing(
        dry_run=args.dry_run,
        only_reembed=args.only_reembed,
        rate_limit_per_min=1500,
    )

    # Stats block — format is tested by AC-SEMRET-33.
    duration_str = f"{stats.duration_seconds:.1f}s"
    print(f"total:    {stats.total}")
    print(f"embedded: {stats.embedded}")
    print(f"skipped:  {stats.skipped}")
    print(f"failed:   {stats.failed}")
    print(f"duration: {duration_str}")

    return 1 if stats.failed > 0 else 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = _build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
