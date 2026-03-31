#!/usr/bin/env python3
"""Backfill task source_metadata actor fields via MCP tool calls.

Usage:
  python scripts/backfill_task_actor_metadata.py --dry-run
  python scripts/backfill_task_actor_metadata.py --apply

Reads MCP endpoint from `.mcp.json` (zenos server URL with api_key).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import requests


UUID32_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def _load_zenos_url() -> str:
    cfg = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
    return cfg["mcpServers"]["zenos"]["url"]


class McpClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._id = 1
        self._initialize()

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = requests.post(
            self.url, headers=self.headers, data=json.dumps(payload), timeout=120
        )
        resp.raise_for_status()
        text = resp.text
        marker = "data: "
        pos = text.rfind(marker)
        if pos == -1:
            raise RuntimeError(f"Unexpected MCP response: {text[:400]}")
        raw_json = text[pos + len(marker):].strip()
        return json.loads(raw_json)

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _initialize(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "actor-backfill", "version": "1.0"},
            },
        }
        self._post(payload)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        data = self._post(payload)
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        result = data.get("result", {})
        content = result.get("content") or []
        if not content:
            return {}
        text = content[0].get("text", "{}")
        return json.loads(text)


def infer_actor(created_by: str) -> tuple[bool, str]:
    creator = (created_by or "").strip()
    if not creator:
        return True, "agent"
    if UUID32_RE.match(creator):
        return False, "agent"
    if creator.lower() == "system":
        return True, "system-auto"
    if creator.endswith("-agent"):
        return True, creator
    return True, "agent"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply
    if args.apply and args.dry_run:
        print("Use either --apply or --dry-run, not both.")
        return 2

    url = _load_zenos_url()
    client = McpClient(url)
    data = client.call_tool("search", {"collection": "tasks", "query": "", "limit": 500})
    tasks = data.get("tasks") or []

    print(f"Scanned tasks: {len(tasks)}")
    touched = 0
    skipped = 0
    errors = 0

    for t in tasks:
        task_id = t.get("id")
        if not task_id:
            skipped += 1
            continue
        source_meta = dict(t.get("source_metadata") or {})
        if "created_via_agent" in source_meta:
            skipped += 1
            continue

        created_by = str(t.get("created_by") or "")
        via_agent, agent_name = infer_actor(created_by)
        # Migrate legacy keys if present
        if "actor_name" in source_meta and not source_meta.get("agent_name"):
            source_meta["agent_name"] = source_meta.get("actor_name")
        if "actor_type" in source_meta and source_meta.get("actor_type") == "human":
            via_agent = False

        if UUID32_RE.match(created_by):
            source_meta["actor_partner_id"] = created_by
        source_meta["created_via_agent"] = via_agent
        source_meta["agent_name"] = source_meta.get("agent_name") or agent_name

        touched += 1
        if dry_run:
            print(
                f"[DRY] {task_id} created_by={created_by!r} -> "
                f"created_via_agent={via_agent}, agent_name={source_meta['agent_name']}"
            )
            continue

        try:
            client.call_tool(
                "task",
                {
                    "action": "update",
                    "id": task_id,
                    "source_metadata": source_meta,
                },
            )
            print(f"[OK] {task_id}")
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"[ERR] {task_id}: {exc}")

    print(
        f"Done. dry_run={dry_run} touched={touched} "
        f"skipped={skipped} errors={errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
