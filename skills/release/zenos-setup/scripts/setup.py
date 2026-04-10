#!/usr/bin/env python3
"""ZenOS MCP Setup Script

Usage:
    python setup.py --token <api_token> [--project <project>] [--cloud-run-url <url>]
    python setup.py --update --project <project>
    python setup.py --update --token <new_token>
    python setup.py --local --gcp-project <project> --github-token <token>
"""

import argparse
import json
import os
import sys
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

CLOUD_RUN_BASE = "https://zenos-mcp-165893875709.asia-east1.run.app/mcp"
MCP_CONFIG_PATH = ".claude/mcp.json"


def load_existing(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"mcpServers": {}}


def save(path: str, config: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def _build_cloud_url(base_url: str, token: str, project: str = "") -> str:
    """Build the full MCP URL with query parameters."""
    params: dict[str, str] = {"api_key": token}
    if project:
        params["project"] = project
    return f"{base_url}?{urlencode(params)}"


def _parse_existing_url(url: str) -> Tuple[str, str, str]:
    """Parse an existing MCP URL into (base_url, token, project).

    Returns:
        Tuple of (base_url_without_query, api_key, project).
        Missing values are returned as empty strings.
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    qs = parse_qs(parsed.query)
    token = qs.get("api_key", [""])[0]
    project = qs.get("project", [""])[0]
    return base_url, token, project


def setup_cloud(token: str, url: str, project: str = "") -> None:
    config = load_existing(MCP_CONFIG_PATH)
    config["mcpServers"]["zenos"] = {
        "type": "http",
        "url": _build_cloud_url(url, token, project),
    }
    save(MCP_CONFIG_PATH, config)
    print("OK ZenOS Cloud MCP config written")
    print(f"   Server: {url}")
    if project:
        print(f"   Project: {project}")
    print(f"   Config: {MCP_CONFIG_PATH}")


def update_cloud(token: Optional[str], project: Optional[str]) -> None:
    """Update existing cloud MCP config, preserving unspecified values."""
    config = load_existing(MCP_CONFIG_PATH)
    zenos = config.get("mcpServers", {}).get("zenos")
    if not zenos or "url" not in zenos:
        print("ERROR: No existing zenos server found in .claude/mcp.json")
        sys.exit(1)

    base_url, existing_token, existing_project = _parse_existing_url(zenos["url"])
    final_token = token if token is not None else existing_token
    final_project = project if project is not None else existing_project

    if not final_token:
        print("ERROR: No token found in existing config and none provided")
        sys.exit(1)

    zenos["url"] = _build_cloud_url(base_url, final_token, final_project)
    save(MCP_CONFIG_PATH, config)
    print("OK ZenOS Cloud MCP config updated")
    print(f"   Server: {base_url}")
    if final_project:
        print(f"   Project: {final_project}")
    print(f"   Config: {MCP_CONFIG_PATH}")


def setup_local(gcp_project: str, github_token: str, venv_python: str) -> None:
    config = load_existing(MCP_CONFIG_PATH)
    config["mcpServers"]["zenos-local"] = {
        "type": "stdio",
        "command": venv_python,
        "args": ["-m", "zenos.interface.mcp"],
        "env": {
            "GITHUB_TOKEN": github_token,
            "GOOGLE_CLOUD_PROJECT": gcp_project,
            "MCP_TRANSPORT": "stdio",
        },
        "cwd": os.getcwd(),
    }
    save(MCP_CONFIG_PATH, config)
    print("OK ZenOS Local MCP config written")
    print(f"   GCP Project: {gcp_project}")
    print(f"   Config: {MCP_CONFIG_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ZenOS MCP Setup")
    parser.add_argument("--token", help="ZenOS API token (Cloud Run)")
    parser.add_argument("--project", help="ZenOS project name (optional)")
    parser.add_argument("--update", action="store_true",
                        help="Update existing config (preserve unspecified values)")
    parser.add_argument("--cloud-run-url", default=CLOUD_RUN_BASE,
                        help=f"Cloud Run URL (default: {CLOUD_RUN_BASE})")
    parser.add_argument("--local", action="store_true", help="Local MCP setup (dev)")
    parser.add_argument("--gcp-project", help="Google Cloud Project ID")
    parser.add_argument("--github-token", help="GitHub Personal Access Token")
    parser.add_argument("--venv-python", default=".venv/bin/python",
                        help="Python venv path (default: .venv/bin/python)")
    args = parser.parse_args()

    if args.update:
        if not args.token and not args.project:
            print("ERROR: --update requires at least one of --token or --project")
            sys.exit(1)
        update_cloud(args.token, args.project)
    elif args.token:
        setup_cloud(args.token, args.cloud_run_url, args.project or "")
    elif args.local:
        if not args.gcp_project or not args.github_token:
            print("ERROR: --local requires --gcp-project and --github-token")
            sys.exit(1)
        setup_local(args.gcp_project, args.github_token, args.venv_python)
    else:
        print("ERROR: Provide --token, --update, or --local")
        parser.print_help()
        sys.exit(1)

    print()
    print("Next: Restart Claude Code for MCP config to take effect")


if __name__ == "__main__":
    main()
