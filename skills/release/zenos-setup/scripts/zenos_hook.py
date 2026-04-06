#!/usr/bin/env python3
"""
ZenOS PreToolUse Hook (matcher: Agent)
每次啟動 subagent 前，自動把 ZenOS 脈絡注入進 agent 的 prompt。
URL 從 .claude/mcp.json 自動讀取，無需手動配置。
"""

import json
import os
import sys
import urllib.request
import urllib.error

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def get_zenos_url() -> str | None:
    mcp_path = os.path.join(os.getcwd(), ".claude", "mcp.json")
    try:
        with open(mcp_path) as f:
            config = json.load(f)
        servers = config.get("mcpServers", {})
        zenos = servers.get("zenos", {})
        return zenos.get("url")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def call_mcp(url: str, method_name: str, arguments: dict) -> dict | None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": method_name, "arguments": arguments},
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
    except urllib.error.URLError:
        return None

    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                envelope = json.loads(line[6:])
                content = envelope.get("result", {}).get("content", [])
                if content:
                    return json.loads(content[0]["text"])
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
    return None


def format_journal(entries: list) -> str:
    if not entries:
        return "（無近期紀錄）"
    lines = []
    for e in entries[:15]:
        ts = e.get("created_at", "")[:10]
        summary = e.get("summary", "").strip()
        tags = ", ".join(e.get("tags", []))
        tag_str = f" [{tags}]" if tags else ""
        lines.append(f"- {ts}{tag_str} {summary}")
    return "\n".join(lines)


def format_entities(entities: list) -> str:
    if not entities:
        return "（無 L2 模組）"
    lines = []
    for e in sorted(entities, key=lambda x: x.get("name", "")):
        name = e.get("name", "")
        summary = (e.get("summary") or "").strip()
        lines.append(f"- **{name}**: {summary}" if summary else f"- **{name}**")
    return "\n".join(lines)


def build_context(url: str) -> str:
    project = ""
    if "project=" in url:
        project = url.split("project=")[-1].split("&")[0]

    journal_result = call_mcp(url, "journal_read", {"project": project, "limit": 15})
    journal_entries = []
    if journal_result:
        journal_entries = journal_result.get("data", {}).get("entries", [])

    entities_result = call_mcp(
        url, "search", {"query": "module", "collection": "entities", "limit": 50}
    )
    l2_entities = []
    if entities_result:
        all_entities = entities_result.get("entities", [])
        l2_entities = [e for e in all_entities if e.get("level") == 2]

    project_label = f"（{project} 專案）" if project else ""
    return f"""## ZenOS 脈絡注入{project_label}

### 近期工作紀錄（最新 15 筆）
{format_journal(journal_entries)}

### L2 核心模組清單（{len(l2_entities)} 個）
{format_entities(l2_entities)}

> 如需特定模組詳細資訊，用 `mcp__zenos__get(collection="entities", name="<模組名稱>")` 查詢。
> **開始任何任務前，先確認 journal 是否有相關決策脈絡，再看 code。**

---
"""


def main():
    raw = sys.stdin.read()
    try:
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    tool_input = hook_input.get("tool_input", {})

    url = get_zenos_url()
    if url:
        original_prompt = tool_input.get("prompt", "")
        context = build_context(url)
        tool_input = {**tool_input, "prompt": context + original_prompt}

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": tool_input,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
