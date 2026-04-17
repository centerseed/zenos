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
DEFAULT_CLAUDE_MCP_CONFIG_PATH = ".claude/mcp.json"
DEFAULT_CODEX_MCP_CONFIG_PATH = ".mcp.json"
# Backward-compatible constant for older tests and callers.
MCP_CONFIG_PATH = DEFAULT_CLAUDE_MCP_CONFIG_PATH


def resolve_mcp_config_path(platform: str) -> str:
    if platform in {"auto", "claude"} and MCP_CONFIG_PATH:
        return MCP_CONFIG_PATH
    if platform == "codex":
        return DEFAULT_CODEX_MCP_CONFIG_PATH
    if platform == "claude":
        return DEFAULT_CLAUDE_MCP_CONFIG_PATH

    if os.path.exists(DEFAULT_CODEX_MCP_CONFIG_PATH):
        return DEFAULT_CODEX_MCP_CONFIG_PATH
    if os.path.exists(DEFAULT_CLAUDE_MCP_CONFIG_PATH):
        return DEFAULT_CLAUDE_MCP_CONFIG_PATH
    return DEFAULT_CLAUDE_MCP_CONFIG_PATH


def load_existing(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"mcpServers": {}}


def save(path: str, config: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
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


def setup_cloud(
    token: str,
    url: str,
    project: str = "",
    config_path: str | None = None,
) -> None:
    config_path = config_path or MCP_CONFIG_PATH
    config = load_existing(config_path)
    config["mcpServers"]["zenos"] = {
        "type": "http",
        "url": _build_cloud_url(url, token, project),
    }
    save(config_path, config)
    print("OK ZenOS Cloud MCP config written")
    print(f"   Server: {url}")
    if project:
        print(f"   Project: {project}")
    print(f"   Config: {config_path}")


def update_cloud(
    token: Optional[str],
    project: Optional[str],
    config_path: str | None = None,
) -> None:
    """Update existing cloud MCP config, preserving unspecified values."""
    config_path = config_path or MCP_CONFIG_PATH
    config = load_existing(config_path)
    zenos = config.get("mcpServers", {}).get("zenos")
    if not zenos or "url" not in zenos:
        print(f"ERROR: No existing zenos server found in {config_path}")
        sys.exit(1)

    base_url, existing_token, existing_project = _parse_existing_url(zenos["url"])
    final_token = token if token is not None else existing_token
    final_project = project if project is not None else existing_project

    if not final_token:
        print("ERROR: No token found in existing config and none provided")
        sys.exit(1)

    zenos["url"] = _build_cloud_url(base_url, final_token, final_project)
    save(config_path, config)
    print("OK ZenOS Cloud MCP config updated")
    print(f"   Server: {base_url}")
    if final_project:
        print(f"   Project: {final_project}")
    print(f"   Config: {config_path}")


def setup_local(
    gcp_project: str,
    github_token: str,
    venv_python: str,
    config_path: str | None = None,
) -> None:
    config_path = config_path or MCP_CONFIG_PATH
    config = load_existing(config_path)
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
    save(config_path, config)
    print("OK ZenOS Local MCP config written")
    print(f"   GCP Project: {gcp_project}")
    print(f"   Config: {config_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ZenOS MCP Setup")
    parser.add_argument("--token", help="ZenOS API token (Cloud Run)")
    parser.add_argument("--project", help="ZenOS project name (optional)")
    parser.add_argument("--update", action="store_true",
                        help="Update existing config (preserve unspecified values)")
    parser.add_argument("--cloud-run-url", default=CLOUD_RUN_BASE,
                        help=f"Cloud Run URL (default: {CLOUD_RUN_BASE})")
    parser.add_argument("--local", action="store_true", help="Local MCP setup (dev)")
    parser.add_argument(
        "--platform",
        choices=["auto", "claude", "codex"],
        default="auto",
        help="Target MCP config style (default: auto-detect)",
    )
    parser.add_argument("--gcp-project", help="Google Cloud Project ID")
    parser.add_argument("--github-token", help="GitHub Personal Access Token")
    parser.add_argument("--venv-python", default=".venv/bin/python",
                        help="Python venv path (default: .venv/bin/python)")
    args = parser.parse_args()
    config_path = resolve_mcp_config_path(args.platform)

    if args.update:
        if not args.token and not args.project:
            print("ERROR: --update requires at least one of --token or --project")
            sys.exit(1)
        update_cloud(args.token, args.project, config_path)
    elif args.token:
        setup_cloud(args.token, args.cloud_run_url, args.project or "", config_path)
    elif args.local:
        if not args.gcp_project or not args.github_token:
            print("ERROR: --local requires --gcp-project and --github-token")
            sys.exit(1)
        setup_local(args.gcp_project, args.github_token, args.venv_python, config_path)
    else:
        print("ERROR: Provide --token, --update, or --local")
        parser.print_help()
        sys.exit(1)

    print()
    print("Next: Restart your agent client for MCP config to take effect")


if __name__ == "__main__":
    main()
