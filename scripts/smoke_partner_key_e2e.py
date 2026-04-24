#!/usr/bin/env python3
"""Smoke-test the deployed MCP service through a real partner API key.

The script intentionally never prints the API key. It can either use
ZENOS_E2E_API_KEY or read an active partner key from DATABASE_URL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import asyncpg
from fastmcp.client import Client


DEFAULT_URL = "https://zenos-mcp-s5oifosv3a-de.a.run.app/mcp"


def _rewrite_local_proxy_url(database_url: str) -> str:
    proxy_port = os.getenv("DB_PROXY_PORT")
    if not proxy_port:
        return database_url
    return database_url.replace("@localhost/", f"@127.0.0.1:{proxy_port}/").replace(
        "@localhost:5432/", f"@127.0.0.1:{proxy_port}/"
    )


def _url_with_api_key(base_url: str, api_key: str, project: str | None) -> str:
    split = urlsplit(base_url)
    query_parts = [part for part in split.query.split("&") if part]
    query_parts.append(f"api_key={quote(api_key, safe='')}")
    if project:
        query_parts.append(f"project={quote(project, safe='')}")
    return urlunsplit((split.scheme, split.netloc, split.path, "&".join(query_parts), split.fragment))


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if getattr(result, "structured_content", None):
        payload = result.structured_content
        if isinstance(payload, dict):
            return payload
    content = getattr(result, "content", None) or []
    if content and hasattr(content[0], "text"):
        return json.loads(content[0].text)
    raise RuntimeError(f"Unsupported tool result shape: {type(result)!r}")


async def _load_partner_key(database_url: str, partner_id: str | None) -> tuple[str, str]:
    conn = await asyncpg.connect(_rewrite_local_proxy_url(database_url))
    try:
        if partner_id:
            row = await conn.fetchrow(
                "SELECT id, api_key FROM zenos.partners WHERE id = $1 AND status = 'active'",
                partner_id,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT p.id, p.api_key
                FROM zenos.partners p
                WHERE p.status = 'active' AND p.api_key IS NOT NULL
                ORDER BY p.updated_at DESC NULLS LAST, p.id
                LIMIT 1
                """
            )
    finally:
        await conn.close()
    if row is None:
        raise RuntimeError("No active partner with api_key found")
    return str(row["id"]), str(row["api_key"])


async def _table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    row = await conn.fetchrow("SELECT to_regclass($1) IS NOT NULL AS exists", f"zenos.{table_name}")
    return bool(row and row["exists"])


async def _load_product_id(database_url: str, partner_id: str, explicit_product_id: str | None) -> str:
    if explicit_product_id:
        return explicit_product_id
    conn = await asyncpg.connect(_rewrite_local_proxy_url(database_url))
    try:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM zenos.entities
            WHERE partner_id = $1 AND type = 'product' AND status IN ('active', 'current', 'draft')
            ORDER BY (lower(name) = 'zenos') DESC, updated_at DESC NULLS LAST, id
            LIMIT 1
            """,
            partner_id,
        )
    finally:
        await conn.close()
    if row is None:
        raise RuntimeError(f"No product entity found for partner {partner_id}")
    return str(row["id"])


async def _cleanup_task_flow(database_url: str, partner_id: str, task_id: str) -> None:
    conn = await asyncpg.connect(_rewrite_local_proxy_url(database_url))
    try:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM zenos.entity_entries WHERE partner_id = $1 AND source_task_id = $2",
                partner_id,
                task_id,
            )
            await conn.execute(
                "DELETE FROM zenos.task_handoff_events WHERE partner_id = $1 AND task_entity_id = $2",
                partner_id,
                task_id,
            )
            await conn.execute(
                """
                DELETE FROM zenos.relationships
                WHERE partner_id = $1 AND (source_entity_id = $2 OR target_entity_id = $2)
                """,
                partner_id,
                task_id,
            )
            await conn.execute(
                "DELETE FROM zenos.entity_l3_task WHERE partner_id = $1 AND entity_id = $2",
                partner_id,
                task_id,
            )
            await conn.execute(
                "DELETE FROM zenos.entities_base WHERE partner_id = $1 AND id = $2",
                partner_id,
                task_id,
            )
    finally:
        await conn.close()


async def _inspect_task_flow_storage(database_url: str, partner_id: str, task_id: str) -> dict[str, Any]:
    conn = await asyncpg.connect(_rewrite_local_proxy_url(database_url))
    try:
        legacy_tasks_exists = await _table_exists(conn, "tasks")
        legacy_task_entities_exists = await _table_exists(conn, "task_entities")
        legacy_tasks_sql = (
            "(SELECT COUNT(*) FROM zenos.tasks WHERE partner_id = $1 AND id = $2)"
            if legacy_tasks_exists
            else "0"
        )
        legacy_task_entities_sql = (
            "(SELECT COUNT(*) FROM zenos.task_entities WHERE partner_id = $1 AND task_id = $2)"
            if legacy_task_entities_exists
            else "0"
        )
        row = await conn.fetchrow(
            f"""
            SELECT
              {legacy_tasks_sql} AS legacy_tasks,
              {legacy_task_entities_sql} AS legacy_task_entities,
              (SELECT COUNT(*) FROM zenos.entities_base WHERE partner_id = $1 AND id = $2) AS entities_base,
              (SELECT COUNT(*) FROM zenos.entity_l3_task WHERE partner_id = $1 AND entity_id = $2) AS entity_l3_task,
              (SELECT COUNT(*) FROM zenos.relationships WHERE partner_id = $1 AND (source_entity_id = $2 OR target_entity_id = $2)) AS relationships,
              (SELECT COUNT(*) FROM zenos.entity_entries WHERE partner_id = $1 AND source_task_id = $2) AS entity_entries,
              (SELECT COUNT(*) FROM zenos.task_handoff_events WHERE partner_id = $1 AND task_entity_id = $2) AS handoff_events
            """,
            partner_id,
            task_id,
        )
    finally:
        await conn.close()
    if row is None:
        return {}
    storage = {key: int(row[key]) for key in row.keys()}
    storage["legacy_tasks_table_present"] = legacy_tasks_exists
    storage["legacy_task_entities_table_present"] = legacy_task_entities_exists
    return storage


async def _run_task_flow(
    client: Client,
    *,
    product_id: str,
    cleanup: bool,
    database_url: str | None,
    partner_id: str,
) -> dict[str, Any]:
    suffix = str(int(time.time()))
    title = f"Wave 9 E04 partner-key e2e smoke {suffix}"
    created_task_id: str | None = None
    storage: dict[str, int] = {}
    try:
        create_payload = _tool_result_payload(
            await client.call_tool(
                "task",
                {
                    "action": "create",
                    "title": title,
                    "description": "Temporary partner-key e2e task for Wave 9 cutover verification.",
                    "product_id": product_id,
                    "linked_entities": [product_id],
                    "priority": "medium",
                    "source_type": "e2e",
                    "source_metadata": {"e2e": "wave9-e04", "cleanup": cleanup},
                    "acceptance_criteria": ["Partner-key create/update/handoff/confirm succeeds."],
                },
            )
        )
        if create_payload.get("status") != "ok":
            raise RuntimeError(f"task create failed: {create_payload}")
        created_task_id = create_payload["data"]["id"]

        update_payload = _tool_result_payload(
            await client.call_tool(
                "task",
                {
                    "action": "update",
                    "id": created_task_id,
                    "status": "in_progress",
                    "result": "Wave 9 E04 e2e task reached in_progress via partner key.",
                },
            )
        )
        if update_payload.get("status") != "ok":
            raise RuntimeError(f"task update failed: {update_payload}")

        handoff_payload = _tool_result_payload(
            await client.call_tool(
                "task",
                {
                    "action": "handoff",
                    "id": created_task_id,
                    "to_dispatcher": "agent:qa",
                    "reason": "Wave 9 E04 partner-key e2e handoff verification.",
                    "output_ref": product_id,
                },
            )
        )
        if handoff_payload.get("status") != "ok":
            raise RuntimeError(f"task handoff failed: {handoff_payload}")

        confirm_payload = _tool_result_payload(
            await client.call_tool(
                "confirm",
                {
                    "collection": "tasks",
                    "id": created_task_id,
                    "accepted": True,
                    "entity_entries": [
                        {
                            "entity_id": product_id,
                            "type": "change",
                            "content": "Wave 9 E04 partner-key e2e verified deployed MCP task flow.",
                        }
                    ],
                },
            )
        )
        if confirm_payload.get("status") != "ok":
            raise RuntimeError(f"task confirm failed: {confirm_payload}")

        if database_url:
            storage = await _inspect_task_flow_storage(database_url, partner_id, created_task_id)

        return {"status": "ok", "task_id": created_task_id, "storage": storage}
    finally:
        if cleanup and created_task_id:
            if not database_url:
                raise RuntimeError("DATABASE_URL is required for --cleanup-task-flow")
            await _cleanup_task_flow(database_url, partner_id, created_task_id)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--partner-id")
    parser.add_argument("--product-id")
    parser.add_argument("--project", default="zenos")
    parser.add_argument("--write-journal", action="store_true")
    parser.add_argument("--full-task-flow", action="store_true")
    parser.add_argument("--cleanup-task-flow", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL")
    api_key = os.getenv("ZENOS_E2E_API_KEY")
    partner_id = args.partner_id or os.getenv("ZENOS_E2E_PARTNER_ID")
    if api_key:
        effective_partner = partner_id or "(from env key)"
    else:
        if not database_url:
            raise RuntimeError("DATABASE_URL or ZENOS_E2E_API_KEY is required")
        effective_partner, api_key = await _load_partner_key(database_url, partner_id)
    product_id = None
    if args.full_task_flow:
        if not database_url:
            raise RuntimeError("DATABASE_URL is required for --full-task-flow product lookup/cleanup")
        if effective_partner == "(from env key)":
            raise RuntimeError("--partner-id is required with ZENOS_E2E_API_KEY and --full-task-flow")
        product_id = await _load_product_id(database_url, effective_partner, args.product_id)

    client_url = _url_with_api_key(args.url, api_key, args.project)
    async with Client(client_url, timeout=30) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        for required in {"search", "journal_write"}:
            if required not in tool_names:
                raise RuntimeError(f"Required tool missing: {required}")

        search_result = await client.call_tool(
            "search",
            {
                "collection": "tasks",
                "query": "",
                "project": args.project,
                "limit": 1,
            },
        )
        search_payload = _tool_result_payload(search_result)
        if search_payload.get("status") != "ok":
            raise RuntimeError(f"search failed: {search_payload}")

        journal_status = "skipped"
        if args.write_journal:
            journal_result = await client.call_tool(
                "journal_write",
                {
                    "project": args.project,
                    "flow_type": "migration",
                    "tags": ["wave9", "e04"],
                    "summary": "Wave 9 E04 partner-key e2e smoke passed through deployed MCP.",
                },
            )
            journal_payload = _tool_result_payload(journal_result)
            if journal_payload.get("status") != "ok":
                raise RuntimeError(f"journal_write failed: {journal_payload}")
            journal_status = "ok"

        task_flow_status: dict[str, Any] | str = "skipped"
        if args.full_task_flow:
            assert product_id is not None
            task_flow_status = await _run_task_flow(
                client,
                product_id=product_id,
                cleanup=args.cleanup_task_flow,
                database_url=database_url,
                partner_id=effective_partner,
            )

    print(
        json.dumps(
            {
                "status": "ok",
                "partner_id": effective_partner,
                "url": args.url,
                "tool_count": len(tool_names),
                "search": "ok",
                "journal_write": journal_status,
                "task_flow": task_flow_status,
                "cleanup": bool(args.cleanup_task_flow and args.full_task_flow),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
