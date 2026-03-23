#!/usr/bin/env python3
"""ZenOS MCP Setup Script

Usage:
    python setup.py --token <api_token> [--cloud-run-url <url>]
    python setup.py --local --gcp-project <project> --github-token <token>
"""

import argparse
import json
import os
import sys

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


def setup_cloud(token: str, url: str) -> None:
    config = load_existing(MCP_CONFIG_PATH)
    config["mcpServers"]["zenos"] = {
        "type": "http",
        "url": f"{url}?api_key={token}",
    }
    save(MCP_CONFIG_PATH, config)
    print(f"✅ ZenOS Cloud MCP 設定完成")
    print(f"   Server: {url}")
    print(f"   設定檔: {MCP_CONFIG_PATH}")


def setup_local(gcp_project: str, github_token: str, venv_python: str) -> None:
    config = load_existing(MCP_CONFIG_PATH)
    config["mcpServers"]["zenos-local"] = {
        "type": "stdio",
        "command": venv_python,
        "args": ["-m", "zenos.interface.tools"],
        "env": {
            "GITHUB_TOKEN": github_token,
            "GOOGLE_CLOUD_PROJECT": gcp_project,
            "MCP_TRANSPORT": "stdio",
        },
        "cwd": os.getcwd(),
    }
    save(MCP_CONFIG_PATH, config)
    print(f"✅ ZenOS Local MCP 設定完成")
    print(f"   GCP Project: {gcp_project}")
    print(f"   設定檔: {MCP_CONFIG_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ZenOS MCP Setup")
    parser.add_argument("--token", help="ZenOS API token（Cloud Run 用）")
    parser.add_argument("--cloud-run-url", default=CLOUD_RUN_BASE,
                        help=f"Cloud Run URL（預設：{CLOUD_RUN_BASE}）")
    parser.add_argument("--local", action="store_true", help="設定本地 MCP（開發用）")
    parser.add_argument("--gcp-project", help="Google Cloud Project ID")
    parser.add_argument("--github-token", help="GitHub Personal Access Token")
    parser.add_argument("--venv-python", default=".venv/bin/python",
                        help="Python 虛擬環境路徑（預設：.venv/bin/python）")
    args = parser.parse_args()

    if not args.token and not args.local:
        print("❌ 請提供 --token 或 --local")
        parser.print_help()
        sys.exit(1)

    if args.token:
        setup_cloud(args.token, args.cloud_run_url)

    if args.local:
        if not args.gcp_project or not args.github_token:
            print("❌ --local 模式需要 --gcp-project 和 --github-token")
            sys.exit(1)
        setup_local(args.gcp_project, args.github_token, args.venv_python)

    print()
    print("📌 下一步：重啟 Claude Code 讓 MCP 設定生效")
    print("   重啟後輸入 /zenos-capture 開始使用")


if __name__ == "__main__":
    main()
